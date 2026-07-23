import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from bot.database import get_db
from bot.config import (
    CULTIVATION_REALMS, CULTIVATION_REALM_ICONS,
    CULTIVATION_BREAKTHROUGH_RATES, CULTIVATION_FAIL_LOSS_PCT,
    CULTIVATION_ASCEND_ITEMS, CULTIVATION_ITEM_NAMES,
    CULTIVATION_STAT_BONUS_PER_STAGE, CULTIVATION_PASSIVES,
    CULTIVATION_MAX_HOURS, get_tuvi_cost,
    CULTIVATION_COOLDOWN, CULTIVATION_ITEM_TUVI,
)
from bot.engine.cultivation import (
    calc_session_tuvi, is_cultivating, get_session_hours,
    calc_stat_bonus, full_title, realm_icon, MAX_REALM, MAX_STAGE,
    breakthrough_info, ascend_info,
)

_PASSIVE_LABELS = {
    "coin_boost":        "💰 +10% coin từ NPC",
    "heal_after_win":    "💚 Hồi 10% HP sau thắng trận",
    "drop_boost":        "🎁 +15% drop rate, +10% gem drop",
    "combat_regen":      "🌿 Hồi 5% HP mỗi lượt chiến đấu",
    "pierce_passive":    "🔱 +20% xuyên giáp tất cả đòn",
    "anti_crit":         "🌌 25% thoát CRIT + giảm 20% dmg nhận",
    "cheat_death_cult":  "⚡ Thoát chết 1 lần/trận + hồi 30% HP",
}

_STONE_COLS = {"stone_medium", "stone_advanced"}


def _format_tuvi(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}T"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}p{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}g{m:02d}p"


async def _get_or_create(db, player_id: str) -> dict:
    row = await (await db.execute(
        "SELECT realm, stage, tuvi, tuvi_total, last_collect, cultivating, session_start "
        "FROM cultivation WHERE player_id=?", (player_id,))).fetchone()
    if row:
        return dict(row)
    now = time.time()
    await db.execute(
        "INSERT INTO cultivation (player_id, realm, stage, tuvi, tuvi_total, "
        "last_collect, cultivating, session_start) VALUES (?, 0, 1, 0, 0, ?, 0, 0)",
        (player_id, now))
    await db.commit()
    return {"realm": 0, "stage": 1, "tuvi": 0, "tuvi_total": 0,
            "last_collect": now, "cultivating": 0, "session_start": 0}


async def _get_player_level(db, player_id: str) -> int:
    row = await (await db.execute("SELECT level FROM players WHERE id=?", (player_id,))).fetchone()
    return row[0] if row else 1


async def _get_cult_items(db, player_id: str) -> dict[str, int]:
    cursor = await db.execute(
        "SELECT item_id, quantity FROM cultivation_items WHERE player_id=? AND quantity>0",
        (player_id,))
    return {r[0]: r[1] for r in await cursor.fetchall()}


def _build_status_embed(display_name: str, cdata: dict, level: int,
                         cult_items: dict, avatar_url: str = None,
                         role_mult: float = 1.0) -> discord.Embed:
    realm  = cdata["realm"]
    stage  = cdata["stage"]
    tuvi   = cdata["tuvi"]
    cultivating   = bool(cdata.get("cultivating", 0))
    session_start = cdata.get("session_start", 0)
    total_bonus_pct = calc_stat_bonus(realm, stage)
    passive_key = CULTIVATION_PASSIVES.get(realm)

    colors = [0x90ee90, 0x8B4513, 0xff69b4, 0xffd700, 0xff4500, 0x9400D3, 0x00ffff]
    color = colors[realm] if realm < len(colors) else 0xffffff

    title = full_title(realm, stage)
    embed = discord.Embed(title=f"🏛️ Tu Tiên — {display_name}", color=color)

    # Trạng thái tu luyện
    from bot.config import CULTIVATION_SESSION_TUVI, get_cultivation_role_mult
    _stage_mult = 1.0 + (stage - 1) * 0.25
    _cult_role_mult = get_cultivation_role_mult(role_mult)
    rate_now = _format_tuvi(int(CULTIVATION_SESSION_TUVI[realm] * _stage_mult * _cult_role_mult))

    if cultivating and session_start > 0:
        elapsed_h = (time.time() - session_start) / 3600
        elapsed_h = min(elapsed_h, CULTIVATION_MAX_HOURS)
        pending = calc_session_tuvi(realm, stage, elapsed_h, role_mult)
        elapsed_str = _format_duration(time.time() - session_start)
        status_str = (
            f"🧘 **Đang tu luyện...** ({elapsed_str})\n"
            f"Tu vi tích lũy: **+{_format_tuvi(pending)}**\n"
            f"⚡ Tốc độ: **{rate_now}** tu vi/giờ _(bậc {stage})_\n"
            f"_Gõ `!tulyen` để kết thúc và nhận tu vi_"
        )
    else:
        status_str = (
            f"💤 Chưa tu luyện\n"
            f"⚡ Tốc độ: **{rate_now}** tu vi/giờ _(bậc {stage})_\n"
            f"_Gõ `!tulyen` để bắt đầu ngồi thiền_"
        )

    # Tu Vi progress
    if stage < MAX_STAGE:
        cost = get_tuvi_cost(realm, stage)
        bar_filled = min(10, tuvi * 10 // max(cost, 1))
        bar = "🟣" * bar_filled + "⬛" * (10 - bar_filled)
        embed.add_field(
            name=f"{title}",
            value=(
                f"**Tu Vi:** `{_format_tuvi(tuvi)}/{_format_tuvi(cost)}`  {bar}\n"
                f"{status_str}"
            ),
            inline=False,
        )
    else:
        asc = ascend_info(realm, stage)
        if asc["can_ascend"]:
            req = asc["required_items"]
            req_lines = []
            for iid, qty in req.items():
                have = cult_items.get(iid, 0)
                ok = "✅" if have >= qty else "❌"
                req_lines.append(f"{ok} {CULTIVATION_ITEM_NAMES.get(iid, iid)} ×{qty} (có {have})")
            embed.add_field(
                name=f"{title} — Sẵn Sàng Thăng Cảnh!",
                value=f"{status_str}\n\n📦 **Cống phẩm cần:**\n" + "\n".join(req_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name=f"{title} — ĐỘ KIẾP TỐI CAO",
                value=f"**Tu Vi:** `{_format_tuvi(tuvi)}`\n{status_str}",
                inline=False,
            )

    embed.add_field(name="⚡ Bonus", value=f"+**{total_bonus_pct:.0f}%** tất cả chỉ số", inline=True)

    passive_text = _PASSIVE_LABELS.get(passive_key, "_Chưa có_") if passive_key else "_Chưa có_"
    embed.add_field(name="✨ Passive", value=passive_text, inline=True)

    if cult_items:
        item_lines = [f"{CULTIVATION_ITEM_NAMES.get(k, k)}: **{v}**" for k, v in cult_items.items()]
        embed.add_field(name="📦 Cống Phẩm", value="\n".join(item_lines), inline=False)

    embed.set_footer(text="!tulyen bắt đầu/kết thúc tu luyện | !dotpha đột phá | !thangcanh thăng cảnh giới")
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    return embed


class CultivationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── !tulyen / /tulyen — toggle tu luyện ─────────────────
    @commands.command(name="tulyen", aliases=["tu", "tl"])
    async def tulyen_cmd(self, ctx):
        await self._tulyen(ctx, str(ctx.author.id), ctx.author.display_name,
                           ctx.author.display_avatar.url)

    @app_commands.command(name="tulyen", description="🧘 Bắt đầu/kết thúc tu luyện")
    async def slash_tulyen(self, interaction: discord.Interaction):
        await self._tulyen(interaction, str(interaction.user.id),
                           interaction.user.display_name,
                           interaction.user.display_avatar.url)

    async def _tulyen(self, ctx_or_int, sid: str, display_name: str, avatar_url: str):
        db = await get_db()
        try:
            prow = await (await db.execute(
                "SELECT level, role_mult FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký! `!register`")
                return
            level = prow[0]
            role_mult = prow[1] if prow[1] else 1.0
            cdata = await _get_or_create(db, sid)

            if not cdata.get("cultivating"):
                # ── BẮT ĐẦU TU LUYỆN ──
                # Kiểm tra cooldown sau session trước
                last_collect = cdata.get("last_collect", 0)
                cd_remaining = CULTIVATION_COOLDOWN - (time.time() - last_collect)
                if cd_remaining > 0 and last_collect > 0:
                    await self._reply(ctx_or_int,
                        f"⏳ Vừa tu luyện xong! Đợi **{_format_duration(cd_remaining)}** nữa mới bắt đầu session mới.")
                    return

                now = time.time()
                await db.execute(
                    "UPDATE cultivation SET cultivating=1, session_start=? WHERE player_id=?",
                    (now, sid))
                await db.commit()
                cdata["cultivating"] = 1
                cdata["session_start"] = now

                # Rate tính theo stage + role
                from bot.config import get_cultivation_role_mult
                cult_role_mult = get_cultivation_role_mult(role_mult)
                stage_mult = 1.0 + (cdata["stage"] - 1) * 0.25
                actual_rate = int(CULTIVATION_SESSION_TUVI[cdata["realm"]] * stage_mult * cult_role_mult)
                realm_rate = _format_tuvi(actual_rate)

                # Role label
                role_label = ""
                if cult_role_mult == 3.0:   role_label = " _(Dragon ×3)_"
                elif cult_role_mult == 2.0: role_label = " _(VIP ×2)_"
                elif cult_role_mult == 1.1: role_label = " _(Support ×1.1)_"
                elif cult_role_mult == 0.8: role_label = " _(Blacklist ×0.8)_"

                embed = discord.Embed(
                    title="🧘 Bắt Đầu Tu Luyện!",
                    description=(
                        f"**{display_name}** ngồi vào tư thế thiền định...\n\n"
                        f"📍 Cảnh giới: **{full_title(cdata['realm'], cdata['stage'])}**\n"
                        f"⚡ Tốc độ: **{realm_rate} tu vi/giờ**{role_label}\n\n"
                        f"⚠️ Trong lúc tu luyện **không thể đánh NPC hay vào Dungeon**!\n"
                        f"Gõ `!tulyen` lần nữa để kết thúc và nhận tu vi."
                    ),
                    color=0x9400D3,
                )
                embed.set_footer(text=f"Tối đa {CULTIVATION_MAX_HOURS} giờ/session")
            else:
                # ── KẾT THÚC TU LUYỆN ──
                start = cdata.get("session_start", 0)
                elapsed_h = min((time.time() - start) / 3600, CULTIVATION_MAX_HOURS) if start else 0
                gained = calc_session_tuvi(cdata["realm"], cdata["stage"], elapsed_h, role_mult)

                new_tuvi = cdata["tuvi"] + gained
                new_total = cdata.get("tuvi_total", 0) + gained
                elapsed_str = _format_duration(elapsed_h * 3600)

                await db.execute(
                    "UPDATE cultivation SET cultivating=0, session_start=0, "
                    "tuvi=?, tuvi_total=?, last_collect=? WHERE player_id=?",
                    (new_tuvi, new_total, time.time(), sid))
                await db.commit()
                cdata["cultivating"] = 0
                cdata["tuvi"] = new_tuvi
                cdata["tuvi_total"] = new_total

                if elapsed_h < 1/60:  # dưới 1 phút
                    embed = discord.Embed(
                        title="⏸️ Kết Thúc Tu Luyện",
                        description=(
                            f"Tu luyện quá ngắn (**{elapsed_str}**), không nhận được tu vi!\n"
                            f"Cần ít nhất vài phút để có hiệu quả."
                        ),
                        color=0x888888,
                    )
                else:
                    cult_items = await _get_cult_items(db, sid)
                    embed = _build_status_embed(display_name, cdata, level, cult_items, avatar_url, role_mult)
                    embed.description = (
                        f"⏹️ **Kết thúc tu luyện** sau **{elapsed_str}**\n"
                        f"✅ Nhận **{_format_tuvi(gained)}** tu vi!\n\n"
                    )
                    if isinstance(ctx_or_int, commands.Context):
                        await ctx_or_int.reply(embed=embed)
                    else:
                        await ctx_or_int.response.send_message(embed=embed)
                    return

        finally:
            await db.close()

        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(embed=embed)
        else:
            await ctx_or_int.response.send_message(embed=embed)

    # ── !dotpha / /dotpha ────────────────────────────────────
    @commands.command(name="dotpha", aliases=["dp"])
    async def dotpha_cmd(self, ctx):
        await self._dotpha(ctx, str(ctx.author.id), ctx.author.display_name)

    @app_commands.command(name="dotpha", description="💥 Đột phá lên bậc tiếp theo")
    async def slash_dotpha(self, interaction: discord.Interaction):
        await self._dotpha(interaction, str(interaction.user.id), interaction.user.display_name)

    async def _dotpha(self, ctx_or_int, sid: str, display_name: str):
        db = await get_db()
        try:
            prow = await (await db.execute(
                "SELECT level FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return

            cdata = await _get_or_create(db, sid)

            # Không thể đột phá khi đang tu luyện
            if cdata.get("cultivating"):
                await self._reply(ctx_or_int,
                    "🧘 Đang tu luyện! Gõ `!tulyen` để kết thúc trước.", ephemeral=True)
                return

            realm, stage, tuvi = cdata["realm"], cdata["stage"], cdata["tuvi"]
            info = breakthrough_info(realm, stage)

            if not info["can_break"]:
                await self._reply(ctx_or_int,
                    f"⚠️ Bạn đã đạt bậc 9 của **{CULTIVATION_REALMS[realm]}**!\n"
                    f"Dùng `!thangcanh` để thăng lên cảnh giới mới.")
                return

            cost = info["tuvi_cost"]
            rate = info["success_rate"]

            if tuvi < cost:
                await self._reply(ctx_or_int,
                    f"❌ Chưa đủ tu vi!\n"
                    f"Cần: **{_format_tuvi(cost)}** | Có: **{_format_tuvi(tuvi)}**\n"
                    f"Còn thiếu: **{_format_tuvi(cost - tuvi)}**\n\n"
                    f"_Hãy tiếp tục tu luyện (`!tulyen`)_")
                return

            # Kiểm tra Bùa May Mắn
            charm_row = await (await db.execute(
                "SELECT quantity FROM inventory WHERE player_id=? AND item_id=27", (sid,))).fetchone()
            has_charm = charm_row and charm_row[0] > 0
            if has_charm:
                rate = min(1.0, rate + 0.25)
                await db.execute(
                    "UPDATE inventory SET quantity=quantity-1 WHERE player_id=? AND item_id=27", (sid,))

            title_now  = full_title(realm, stage)
            title_next = full_title(realm, stage + 1)
            success = random.random() < rate

            if success:
                await db.execute(
                    "UPDATE cultivation SET stage=?, tuvi=0 WHERE player_id=?",
                    (stage + 1, sid))
                await db.commit()
                bonus_pct = calc_stat_bonus(realm, stage + 1)
                embed = discord.Embed(
                    title="💥 ĐỘT PHÁ THÀNH CÔNG!",
                    description=(
                        f"🎉 **{display_name}** đột phá thành công!\n\n"
                        f"**{title_now}** → **{title_next}**\n\n"
                        f"⚡ Tổng bonus: **+{bonus_pct:.0f}%** tất cả chỉ số"
                        + (f"\n🍀 Bùa May Mắn đã dùng (+25%)" if has_charm else "")
                    ),
                    color=0x00ff88,
                )
            else:
                loss = int(tuvi * info["fail_loss_pct"] / 100)
                await db.execute(
                    "UPDATE cultivation SET tuvi=? WHERE player_id=?",
                    (max(0, tuvi - loss), sid))
                await db.commit()
                embed = discord.Embed(
                    title="💔 ĐỘT PHÁ THẤT BẠI!",
                    description=(
                        f"**{display_name}** đột phá thất bại!\n\n"
                        f"Vẫn ở **{title_now}**\n"
                        f"💸 Mất **{_format_tuvi(loss)}** tu vi ({info['fail_loss_pct']}%)\n"
                        f"Còn lại: **{_format_tuvi(max(0, tuvi - loss))}**\n\n"
                        f"_Tỉ lệ: {int(rate*100)}% | Tiếp tục tu luyện và thử lại!_"
                        + (f"\n🍀 Bùa May Mắn đã dùng (+25%)" if has_charm else "")
                    ),
                    color=0xff4444,
                )
        finally:
            await db.close()

        await self._reply(ctx_or_int, embed=embed)

    # ── !thangcanh / /thangcanh ──────────────────────────────
    @commands.command(name="thangcanh", aliases=["tc"])
    async def thangcanh_cmd(self, ctx):
        await self._thangcanh(ctx, str(ctx.author.id), ctx.author.display_name)

    @app_commands.command(name="thangcanh", description="🌟 Thăng cảnh giới (cần bậc 9 + cống phẩm)")
    async def slash_thangcanh(self, interaction: discord.Interaction):
        await self._thangcanh(interaction, str(interaction.user.id), interaction.user.display_name)

    async def _thangcanh(self, ctx_or_int, sid: str, display_name: str):
        db = await get_db()
        try:
            if not await (await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))).fetchone():
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return

            cdata = await _get_or_create(db, sid)
            if cdata.get("cultivating"):
                await self._reply(ctx_or_int,
                    "🧘 Đang tu luyện! Gõ `!tulyen` để kết thúc trước.", ephemeral=True)
                return

            realm, stage = cdata["realm"], cdata["stage"]
            asc = ascend_info(realm, stage)

            if not asc["can_ascend"]:
                if asc["reason"] == "not_stage_9":
                    await self._reply(ctx_or_int,
                        f"❌ Cần đạt **{CULTIVATION_REALMS[realm]} bậc 9** trước!\n"
                        f"Hiện tại: {full_title(realm, stage)}")
                else:
                    await self._reply(ctx_or_int,
                        "🌟 Bạn đã đạt cảnh giới tối thượng — **Độ Kiếp bậc 9**!")
                return

            required = asc["required_items"]
            cult_items = await _get_cult_items(db, sid)
            missing = []
            for iid, qty in required.items():
                if iid in _STONE_COLS:
                    srow = await (await db.execute(
                        f"SELECT {iid} FROM player_enhance_stones WHERE player_id=?", (sid,))).fetchone()
                    have = srow[0] if srow else 0
                else:
                    have = cult_items.get(iid, 0)
                if have < qty:
                    missing.append(f"• {CULTIVATION_ITEM_NAMES.get(iid, iid)}: cần {qty}, có {have}")

            if missing:
                await self._reply(ctx_or_int,
                    f"❌ Thiếu cống phẩm để thăng cảnh!\n\n" + "\n".join(missing))
                return

            # Trừ cống phẩm
            for iid, qty in required.items():
                if iid in _STONE_COLS:
                    await db.execute(
                        f"UPDATE player_enhance_stones SET {iid}={iid}-? WHERE player_id=?",
                        (qty, sid))
                else:
                    await db.execute(
                        "UPDATE cultivation_items SET quantity=quantity-? WHERE player_id=? AND item_id=?",
                        (qty, sid, iid))

            next_realm = asc["next_realm"]
            await db.execute(
                "UPDATE cultivation SET realm=?, stage=1, tuvi=0 WHERE player_id=?",
                (next_realm, sid))
            await db.commit()

            passive_text = _PASSIVE_LABELS.get(
                CULTIVATION_PASSIVES.get(next_realm), "") or ""
            bonus_pct = calc_stat_bonus(next_realm, 1)

            embed = discord.Embed(
                title="🌟 THĂNG CẢNH GIỚI!",
                description=(
                    f"✨ **{display_name}** đã thăng cảnh!\n\n"
                    f"{realm_icon(realm)} **{CULTIVATION_REALMS[realm]} bậc 9**\n"
                    f"↓\n"
                    f"{realm_icon(next_realm)} **{CULTIVATION_REALMS[next_realm]} bậc 1**\n\n"
                    f"⚡ Bonus mới: **+{bonus_pct:.0f}%** tất cả chỉ số"
                    + (f"\n✨ **Passive mở khóa:** {passive_text}" if passive_text else "")
                ),
                color=0xffd700,
            )
        finally:
            await db.close()

        await self._reply(ctx_or_int, embed=embed)

    # ── !tutien — xem bảng cảnh giới ────────────────────────
    @commands.command(name="tutien", aliases=["tt"])
    async def tutien_cmd(self, ctx):
        await self._tutien(ctx, str(ctx.author.id), ctx.author.display_avatar.url)

    @app_commands.command(name="tutien", description="📖 Xem bảng cảnh giới tu tiên đầy đủ")
    async def slash_tutien(self, interaction: discord.Interaction):
        await self._tutien(interaction, str(interaction.user.id),
                           interaction.user.display_avatar.url)

    async def _tutien(self, ctx_or_int, sid: str, avatar_url: str):
        db = await get_db()
        try:
            cdata = await _get_or_create(db, sid)
        finally:
            await db.close()

        realm = cdata["realm"]
        stage = cdata["stage"]

        from bot.config import CULTIVATION_SESSION_TUVI
        embed = discord.Embed(title="📖 Bảng Cảnh Giới Tu Tiên", color=0x9400D3)
        embed.set_thumbnail(url=avatar_url)

        for r, (rname, ricon) in enumerate(zip(CULTIVATION_REALMS, CULTIVATION_REALM_ICONS)):
            base = CULTIVATION_SESSION_TUVI[r]
            rate_min = base           # bậc 1: 1.0x
            rate_max = base * 3       # bậc 9: 3.0x
            bonus_per = CULTIVATION_STAT_BONUS_PER_STAGE[r]
            passive_key = CULTIVATION_PASSIVES.get(r)
            passive_text = _PASSIVE_LABELS.get(passive_key, "_Không có_") if passive_key else "_Không có_"
            current = "◀ **Đang ở đây**" if r == realm else ""
            embed.add_field(
                name=f"{ricon} **{rname}** {current}",
                value=(
                    f"Tu vi/giờ: `{_format_tuvi(rate_min)} ~ {_format_tuvi(rate_max)}`"
                    f" _(bậc 1→9)_\n"
                    f"Bonus: +{bonus_per}%/bậc\n"
                    f"Passive: {passive_text}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"Cảnh giới hiện tại: {full_title(realm, stage)}")
        await self._reply(ctx_or_int, embed=embed)

    # ── !dung / /dung — dùng cống phẩm tăng tu vi ────────────
    @commands.command(name="dung", aliases=["use"])
    async def dung_cmd(self, ctx, item_id: str = None, quantity: str = "1"):
        await self._dung(ctx, str(ctx.author.id), ctx.author.display_name, item_id, quantity)

    @app_commands.command(name="dung", description="🌿 Dùng cống phẩm tu tiên để tăng tu vi")
    @app_commands.describe(item_id="Tên cống phẩm (linh_thao, linh_dan, ...)", quantity="Số lượng (mặc định 1)")
    async def slash_dung(self, interaction: discord.Interaction, item_id: str, quantity: str = "1"):
        await self._dung(interaction, str(interaction.user.id), interaction.user.display_name, item_id, quantity)

    async def _dung(self, ctx_or_int, sid: str, display_name: str, item_id: str, quantity: str):
        if not item_id:
            await self._reply(ctx_or_int,
                f"❌ Dùng: `!dung <tên> [sl]`\n"
                f"Cống phẩm: {', '.join(CULTIVATION_ITEM_NAMES.keys())}\n"
                f"VD: `!dung linh_thao 5`")
            return
        try:
            qty = max(1, int(quantity))
        except:
            qty = 1

        if item_id not in CULTIVATION_ITEM_TUVI:
            await self._reply(ctx_or_int,
                f"❌ `{item_id}` không phải cống phẩm!\n"
                f"Dùng: {', '.join(CULTIVATION_ITEM_NAMES.keys())}")
            return

        db = await get_db()
        try:
            cdata = await _get_or_create(db, sid)
            if cdata.get("cultivating"):
                await self._reply(ctx_or_int, "🧘 Đang tu luyện! Gõ `!tulyen` để kết thúc trước.", ephemeral=True)
                return

            cursor = await db.execute(
                "SELECT quantity FROM cultivation_items WHERE player_id=? AND item_id=?",
                (sid, item_id))
            row = await cursor.fetchone()
            have = row[0] if row else 0
            if have < qty:
                await self._reply(ctx_or_int,
                    f"❌ Không đủ **{CULTIVATION_ITEM_NAMES.get(item_id, item_id)}**!\nCó: {have}, cần: {qty}")
                return

            per_item = CULTIVATION_ITEM_TUVI[item_id]
            gained = per_item * qty
            new_tuvi = cdata["tuvi"] + gained
            new_total = cdata.get("tuvi_total", 0) + gained

            new_qty = have - qty
            if new_qty <= 0:
                await db.execute("DELETE FROM cultivation_items WHERE player_id=? AND item_id=?", (sid, item_id))
            else:
                await db.execute("UPDATE cultivation_items SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, sid, item_id))
            await db.execute("UPDATE cultivation SET tuvi=?, tuvi_total=? WHERE player_id=?", (new_tuvi, new_total, sid))
            await db.commit()

            embed = discord.Embed(
                title="🌿 Dùng Cống Phẩm",
                description=(
                    f"**{display_name}** dùng {qty}× **{CULTIVATION_ITEM_NAMES.get(item_id, item_id)}**\n"
                    f"+**{_format_tuvi(gained)}** tu vi!\n\n"
                    f"📊 Tổng tu vi: **{_format_tuvi(new_tuvi)}**"
                ),
                color=0x90ee90,
            )
        finally:
            await db.close()

        await self._reply(ctx_or_int, embed=embed)

    async def _reply(self, ctx_or_int, msg: str = None, embed: discord.Embed = None,
                     ephemeral: bool = False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg or "", embed=embed)
        else:
            await ctx_or_int.response.send_message(msg or "", embed=embed, ephemeral=ephemeral)


# Helper cho CULTIVATION_SESSION_TUVI (dùng trong engine)
from bot.config import CULTIVATION_SESSION_TUVI  # noqa


async def setup(bot):
    await bot.add_cog(CultivationCog(bot))
