import discord
from discord import app_commands
from discord.ext import commands
import random
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, STAR_LABELS, STAR_COLORS
from bot.config import (
    MAX_ENHANCE, ENHANCE_SUCCESS_RATES, ENHANCE_COSTS,
    STONE_BASIC_ID, STONE_MEDIUM_ID, STONE_ADVANCED_ID,
)

MILESTONES = {4, 7, 9}
MILESTONE_SLOT = {4: 1, 7: 2, 9: 3}
SLOT_MULTIPLIERS = {1: 1.5, 2: 3.0, 3: 5.0}

HIDDEN_STAT_POOLS = {
    "atk_min": {"icon": "⚔️", "label": "Tấn Công Tối Thiểu", "val": lambda s: 2 + s * 3},
    "atk_max": {"icon": "⚔️", "label": "Tấn Công Tối Đa", "val": lambda s: 3 + s * 4},
    "hp": {"icon": "❤️", "label": "HP", "val": lambda s: 20 + s * 15},
    "defense": {"icon": "🛡️", "label": "Phòng Thủ", "val": lambda s: 3 + s * 2},
    "spd": {"icon": "💨", "label": "Tốc Độ", "val": lambda s: 2 + s},
    "crit": {"icon": "💥", "label": "Chí Mạng", "val": lambda s: 2 + s},
    "pierce": {"icon": "🔱", "label": "Xuyên Giáp", "val": lambda s: 2 + s},
    "dodge": {"icon": "🍀", "label": "Né Đòn", "val": lambda s: 1 + s},
    "reflect": {"icon": "🔄", "label": "Phản Đòn", "val": lambda s: 1 + s},
    "regen": {"icon": "💚", "label": "Hồi Phục", "val": lambda s: 1 + s // 2},
}

def generate_hidden_stat(star: int, slot: int) -> str:
    import random, json
    count = random.randint(2, 3)
    pool_keys = list(HIDDEN_STAT_POOLS.keys())
    chosen = random.sample(pool_keys, min(count, len(pool_keys)))
    result = []
    for k in chosen:
        pool = HIDDEN_STAT_POOLS[k]
        val = int(pool["val"](star) * SLOT_MULTIPLIERS[slot])
        result.append({"k": k, "v": val})
    return json.dumps(result)


class EnhanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cuonghoa", aliases=["enhance"])
    async def cuonghoa_cmd(self, ctx, eq_id: str = None):
        await self._cuonghoa(ctx, str(ctx.author.id), eq_id, ctx.author.display_name, "!")

    @app_commands.command(name="cuonghoa", description="🔨 Cường hóa trang bị")
    @app_commands.describe(eq_id="ID trang bị muốn cường hóa (xem /inv)")
    async def slash_cuonghoa(self, interaction: discord.Interaction, eq_id: str):
        await self._cuonghoa(interaction, str(interaction.user.id), eq_id,
                             interaction.user.display_name, "/")

    @slash_cuonghoa.autocomplete("eq_id")
    async def cuonghoa_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT DISTINCT item_id FROM player_equipment WHERE player_id=? AND enhance < ?",
                (uid, MAX_ENHANCE))
            choices = []
            async for r in cursor:
                eiid = r[0]
                name = None
                if eiid in EQUIPMENT:
                    name = EQUIPMENT[eiid]["name"]
                if name and (current.lower() in str(eiid) or current.lower() in name.lower()):
                    eqr = await db.execute(
                        "SELECT id, enhance FROM player_equipment WHERE player_id=? AND item_id=? AND equipped=0 AND enhance < ? ORDER BY enhance DESC LIMIT 1",
                        (uid, eiid, MAX_ENHANCE))
                    erow = await eqr.fetchone()
                    if erow:
                        enh = erow[1]
                        choices.append(app_commands.Choice(
                            name=f"({eiid}) {name} +{enh} → +{enh+1}"[:100],
                            value=str(erow[0])))
            return choices[:25]
        finally:
            await db.close()

    async def _cuonghoa(self, ctx_or_int, sid: str, eq_id: str, display_name: str, prefix: str):
        if not eq_id:
            await self._reply(ctx_or_int, f"❌ Dùng: `{prefix}cuonghoa <ID>` (xem ID trong `/inv`)")
            return
        try:
            eid = int(eq_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ ID không hợp lệ!")
            return

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE id=? AND player_id=?",
                (eid, sid))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return
            eq = dict(row)
            eiid = eq["item_id"]
            if eiid not in EQUIPMENT:
                await self._reply(ctx_or_int, "❌ Chỉ có thể cường hóa trang bị hệ thống mới!")
                return
            current = eq["enhance"]
            if current >= MAX_ENHANCE:
                await self._reply(ctx_or_int, f"⭐ Đã đạt tối đa +{MAX_ENHANCE}!")
                return

            target = current + 1
            cost = ENHANCE_COSTS.get(target)
            if not cost:
                await self._reply(ctx_or_int, "❌ Cấp cường hóa không hợp lệ!")
                return

            stone_id, stone_qty, coin_cost = cost
            stone_key = {STONE_BASIC_ID: "stone_basic", STONE_MEDIUM_ID: "stone_medium",
                         STONE_ADVANCED_ID: "stone_advanced"}.get(stone_id)

            player_cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            player_coins = prow[0]

            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (sid,))
            srow = await stone_cursor.fetchone()
            stones = {"stone_basic": srow[0] if srow else 0,
                      "stone_medium": srow[1] if srow else 0,
                      "stone_advanced": srow[2] if srow else 0}

            if stones.get(stone_key, 0) < stone_qty:
                stone_label = {1: "đá sơ cấp", 2: "đá trung cấp", 3: "đá cao cấp"}
                tier = {STONE_BASIC_ID: 1, STONE_MEDIUM_ID: 2, STONE_ADVANCED_ID: 3}[stone_id]
                await self._reply(ctx_or_int,
                    f"❌ Thiếu đá! Cần **{stone_qty}** {stone_label[tier]}, có **{stones.get(stone_key, 0)}**")
                return

            if player_coins < coin_cost:
                await self._reply(ctx_or_int,
                    f"😅 Nghèo! Cần **{coin_cost}🪙**, có **{player_coins}🪙**")
                return

            success_rate = ENHANCE_SUCCESS_RATES.get(target, 0.5)
            roll = random.random()
            success = roll < success_rate

            equip_name = EQUIPMENT[eiid]["name"]
            equip_star = EQUIPMENT[eiid]["star"]
            stars = STAR_LABELS.get(equip_star, "⭐")
            embed_color = STAR_COLORS.get(equip_star, 0x00ff00)

            if equip_star == 6:
                equip_name = f"[Thần Thoại] {equip_name}"

            await db.execute(f"UPDATE player_enhance_stones SET {stone_key}={stone_key}-? WHERE player_id=?",
                             (stone_qty, sid))
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (coin_cost, sid))

            if success:
                await db.execute("UPDATE player_equipment SET enhance=? WHERE id=?", (target, eid))
                from bot.cogs.quest import update_progress
                await update_progress(db, sid, 3)
                hidden_msg = ""
                if target in MILESTONES:
                    import json
                    existing = {}
                    cursor = await db.execute(
                        "SELECT hidden_stats FROM player_equipment WHERE id=?", (eid,))
                    row = await cursor.fetchone()
                    if row and row[0]:
                        try:
                            existing = json.loads(row[0])
                        except:
                            existing = {}
                    slot = MILESTONE_SLOT[target]
                    new_stat = generate_hidden_stat(equip_star, slot)
                    existing[str(slot)] = json.loads(new_stat)
                    merged = json.dumps(existing)
                    await db.execute("UPDATE player_equipment SET hidden_stats=? WHERE id=?", (merged, eid))
                    arr = existing[str(slot)]
                    parts = []
                    for item in arr:
                        pool = HIDDEN_STAT_POOLS.get(item["k"], {})
                        parts.append(f"{pool.get('icon','')}+{item['v']} {pool.get('label', item['k'])}")
                    hidden_msg = f"\n🌟 MỞ KHÓA THUỘC TÍNH ẨN {slot}!\n" + "\n".join(parts)
                await db.commit()
                if target >= MAX_ENHANCE:
                    next_str = "🌟 MAX 🌟"
                else:
                    next_str = f"✦+{target}"
                cur_str = f"✦+{current}" if current > 0 else "+0"
                embed = discord.Embed(
                    title="🔨 CƯỜNG HÓA THÀNH CÔNG!",
                    description=(
                        f"{stars} **{equip_name}**\n"
                        f"⭐ **{cur_str}** → **{next_str}** ✨\n"
                        f"🎯 Tỉ lệ: **{int(success_rate*100)}%** — Roll: **{int(roll*100)}** ✅\n"
                        f"💎 Tốn: {stone_qty} đá | 💰 {coin_cost}🪙"
                        f"{hidden_msg}"
                    ),
                    color=embed_color)
            else:
                await db.commit()
                cur_str = f"✦+{current}" if current > 0 else "+0"
                embed = discord.Embed(
                    title="💥 CƯỜNG HÓA THẤT BẠI!",
                    description=(
                        f"{stars} **{equip_name}**\n"
                        f"⭐ Vẫn giữ **{cur_str}**\n"
                        f"🎯 Tỉ lệ: **{int(success_rate*100)}%** — Roll: **{int(roll*100)}** ❌\n"
                        f"💎 Mất: {stone_qty} đá | 💰 Mất {coin_cost}🪙"
                    ),
                    color=0xff0000)

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)

        finally:
            await db.close()

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)

    @commands.command(name="reroll", aliases=["rerollhidden", "rolllai"])
    async def reroll_cmd(self, ctx, eq_id: str = None, slot: str = None):
        await self._reroll(ctx, str(ctx.author.id), eq_id, slot, ctx.author.display_name, "!")

    @app_commands.command(name="reroll", description="🌟 Reroll thuộc tính ẩn của trang bị")
    @app_commands.describe(eq_id="ID trang bị (xem /inv)", slot="Slot 1/2/3 muốn reroll")
    async def slash_reroll(self, interaction: discord.Interaction, eq_id: str, slot: int = None):
        await self._reroll(interaction, str(interaction.user.id), eq_id, str(slot) if slot else None,
                           interaction.user.display_name, "/")

    @slash_reroll.autocomplete("eq_id")
    async def reroll_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND enhance>=4 AND hidden_stats!=''",
                (uid,))
            choices = []
            async for r in cursor:
                eid, eiid, enh = r
                name = EQUIPMENT.get(eiid, {}).get("name", eiid)
                label = f"({eiid}) {name} +{enh}"[:100]
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label, value=str(eid)))
            return choices[:25]
        finally:
            await db.close()

    REROLL_COSTS = {
        1: {"min_enhance": 4, "stone_id": STONE_BASIC_ID, "stone_qty": 20, "coin_cost": 3000},
        2: {"min_enhance": 7, "stone_id": STONE_MEDIUM_ID, "stone_qty": 20, "coin_cost": 6000},
        3: {"min_enhance": 9, "stone_id": STONE_ADVANCED_ID, "stone_qty": 20, "coin_cost": 9000},
    }

    STONE_LABELS = {STONE_BASIC_ID: "đá sơ cấp", STONE_MEDIUM_ID: "đá trung cấp", STONE_ADVANCED_ID: "đá cao cấp"}
    STONE_COLUMNS = {STONE_BASIC_ID: "stone_basic", STONE_MEDIUM_ID: "stone_medium", STONE_ADVANCED_ID: "stone_advanced"}

    async def _reroll(self, ctx_or_int, sid: str, eq_id: str, slot: str, display_name: str, prefix: str):
        if not eq_id:
            await self._reply(ctx_or_int, f"❌ Dùng: `{prefix}reroll <ID> <slot>` (slot 1/2/3)")
            return
        try:
            eid = int(eq_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ ID không hợp lệ!")
            return

        if not slot or slot not in ("1", "2", "3"):
            await self._reply(ctx_or_int, "❌ Chọn slot 1, 2 hoặc 3 để reroll!")
            return
        slot_int = int(slot)

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance, hidden_stats FROM player_equipment WHERE id=? AND player_id=?",
                (eid, sid))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return
            eq = dict(row)
            eiid = eq["item_id"]
            enhance = eq["enhance"]
            hidden = eq["hidden_stats"] or ""

            if eiid not in EQUIPMENT:
                await self._reply(ctx_or_int, "❌ Chỉ reroll được trang bị hệ thống!")
                return
            if not hidden:
                await self._reply(ctx_or_int, "❌ Trang bị chưa có thuộc tính ẩn! Dùng `/cuonghoa` để mở khóa.")
                return

            # Check slot availability based on enhance
            if slot_int == 1 and enhance < 4:
                await self._reply(ctx_or_int, "❌ Slot 1 cần trang bị +4 trở lên!")
                return
            if slot_int == 2 and enhance < 7:
                await self._reply(ctx_or_int, "❌ Slot 2 cần trang bị +7 trở lên!")
                return
            if slot_int == 3 and enhance < 9:
                await self._reply(ctx_or_int, "❌ Slot 3 cần trang bị +9 trở lên!")
                return

            cfg = self.REROLL_COSTS[slot_int]
            stone_key = self.STONE_COLUMNS[cfg["stone_id"]]
            stone_label = self.STONE_LABELS[cfg["stone_id"]]

            player_cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            player_coins = prow[0]

            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (sid,))
            srow = await stone_cursor.fetchone()
            stones = {"stone_basic": srow[0] if srow else 0,
                      "stone_medium": srow[1] if srow else 0,
                      "stone_advanced": srow[2] if srow else 0}

            if stones.get(stone_key, 0) < cfg["stone_qty"]:
                await self._reply(ctx_or_int,
                    f"❌ Thiếu đá! Cần **{cfg['stone_qty']}** {stone_label}, có **{stones.get(stone_key, 0)}**")
                return
            if player_coins < cfg["coin_cost"]:
                await self._reply(ctx_or_int,
                    f"😅 Nghèo! Cần **{cfg['coin_cost']}🪙**, có **{player_coins}🪙**")
                return

            equip_star = EQUIPMENT[eiid]["star"]
            import json
            existing = {}
            try:
                existing = json.loads(hidden) if hidden else {}
            except:
                existing = {}
            new_stat = generate_hidden_stat(equip_star, slot_int)
            existing[str(slot_int)] = json.loads(new_stat)
            merged = json.dumps(existing)
            arr = existing[str(slot_int)]
            parts = []
            for item in arr:
                pool = HIDDEN_STAT_POOLS.get(item["k"], {})
                parts.append(f"{pool.get('icon','')}+{item['v']} {pool.get('label', item['k'])}")

            await db.execute(f"UPDATE player_enhance_stones SET {stone_key}={stone_key}-? WHERE player_id=?",
                             (cfg["stone_qty"], sid))
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cfg["coin_cost"], sid))
            await db.execute("UPDATE player_equipment SET hidden_stats=? WHERE id=?", (merged, eid))
            await db.commit()

            equip_name = EQUIPMENT[eiid]["name"]
            stars = STAR_LABELS.get(equip_star, "⭐")
            embed_color = STAR_COLORS.get(equip_star, 0x00ff00)
            if equip_star == 6:
                equip_name = f"[Thần Thoại] {equip_name}"

            embed = discord.Embed(
                title="🌟 REROLL THUỘC TÍNH ẨN!",
                description=(
                    f"{stars} **{equip_name}** +{enhance}\n"
                    f"🎯 Slot {slot_int}:\n" + "\n".join(parts) +
                    f"\n💰 Mất: {cfg['stone_qty']} {stone_label} | {cfg['coin_cost']}🪙"
                ),
                color=embed_color)
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)

        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(EnhanceCog(bot))
