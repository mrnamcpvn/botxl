import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, timedelta
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, DROP_WEIGHTS, STAR_LABELS, STAR_NAMES, STAR_COLORS, SLOT_NAMES

ROLL_COST = 1000
PITY_MAX = 100

TZ_UTC7 = timezone(timedelta(hours=7))

HAPPY_HOUR_SLOTS = [
    (12, 30, 13, 30),
    (1, 0, 5, 0),
]

HH_WEIGHT_MULT = {1: 1, 2: 1.5, 3: 2, 4: 4, 5: 6, 6: 8}

STAR_EMOJIS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐", 6: "🌟🌟🌟🌟🌟🌟", 7: "👑👑👑👑👑👑👑"}
SET_NAMES = {
    5101: "🛡️ Long Uy", 5102: "🛡️ Long Uy", 5103: "🛡️ Long Uy", 5104: "🛡️ Long Uy", 5105: "🛡️ Long Uy", 5106: "🛡️ Long Uy",
    5201: "⚔️ Huyết Kiếm", 5202: "⚔️ Huyết Kiếm", 5203: "⚔️ Huyết Kiếm", 5204: "⚔️ Huyết Kiếm", 5205: "⚔️ Huyết Kiếm", 5206: "⚔️ Huyết Kiếm",
    5301: "💨 Phong Vân", 5302: "💨 Phong Vân", 5303: "💨 Phong Vân", 5304: "💨 Phong Vân", 5305: "💨 Phong Vân", 5306: "💨 Phong Vân",
    5401: "🔱 Xuyên Tâm", 5402: "🔱 Xuyên Tâm", 5403: "🔱 Xuyên Tâm", 5404: "🔱 Xuyên Tâm", 5405: "🔱 Xuyên Tâm", 5406: "🔱 Xuyên Tâm",
    6101: "💎 Long Thần", 6102: "💎 Long Thần", 6103: "💎 Long Thần", 6104: "💎 Long Thần", 6105: "💎 Long Thần", 6106: "💎 Long Thần",
    6201: "🔥 Diệt Thế", 6202: "🔥 Diệt Thế", 6203: "🔥 Diệt Thế", 6204: "🔥 Diệt Thế", 6205: "🔥 Diệt Thế", 6206: "🔥 Diệt Thế",
    6301: "⚡ Lôi Phong", 6302: "⚡ Lôi Phong", 6303: "⚡ Lôi Phong", 6304: "⚡ Lôi Phong", 6305: "⚡ Lôi Phong", 6306: "⚡ Lôi Phong",
    6401: "🌌 Hư Không", 6402: "🌌 Hư Không", 6403: "🌌 Hư Không", 6404: "🌌 Hư Không", 6405: "🌌 Hư Không", 6406: "🌌 Hư Không",
}

SLOT_ICONS = {"weapon": "🗡️", "armor": "🛡️", "boots": "👢", "gloves": "🧤", "belt": "🎗️", "ring": "💍"}

TIER_BORDERS = {
    1: "▰▰▰▰▰▰▰▰▰▰",
    2: "▰▰▰▰▰▰▰▰▰▰",
    3: "▰▰▰▰▰▰▰▰▰▰",
    4: "▰▰▰▰▰▰▰▰▰▰",
    5: "════════════════════",
    6: "✧══════════════════✧",
}

STAT_ICONS = {"hp": "❤️", "defense": "🛡️", "spd": "💨", "crit": "💥", "pierce": "🔱", "dodge": "🌀", "reflect": "🔄", "regen": "💚"}

PITY_BAR_LENGTH = 20


def _is_happy_hour() -> bool:
    now = datetime.now(TZ_UTC7)
    for sh, sm, eh, em in HAPPY_HOUR_SLOTS:
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if start <= end:
            if start <= now <= end:
                return True
        else:
            if now >= start or now <= end:
                return True
    return False


def _build_hh_weights() -> dict:
    return {star: int(weight * HH_WEIGHT_MULT.get(star, 1)) for star, weight in DROP_WEIGHTS.items()}


class GachaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _roll_star(self, force_6star: bool) -> int:
        if force_6star:
            return 6
        weights = _build_hh_weights() if _is_happy_hour() else DROP_WEIGHTS
        total = sum(weights.values())
        roll = random.randint(1, total)
        cumulative = 0
        for star, weight in sorted(weights.items()):
            cumulative += weight
            if roll <= cumulative:
                return star
        return 1

    def _pick_equip(self, star: int) -> tuple[int, dict]:
        candidates = [(eid, e) for eid, e in EQUIPMENT.items() if e["star"] == star]
        if not candidates:
            return None, None
        return random.choice(candidates)

    def _pity_bar(self, count: int) -> str:
        filled = min(count, PITY_MAX)
        fill = filled * PITY_BAR_LENGTH // PITY_MAX
        empty = PITY_BAR_LENGTH - fill
        return f"`{'█' * fill}{'░' * empty}`"

    def _format_stat_value(self, key: str, value) -> str:
        icon = STAT_ICONS.get(key, "")
        return f"{icon}**+{value}**"

    @commands.command(name="roll", aliases=["quay"])
    async def roll_cmd(self, ctx):
        await self._roll(ctx, ctx.author)

    @commands.command(name="giovang", aliases=["hh", "happyhour"])
    async def giovang_cmd(self, ctx):
        hh_slots = "**12:30 - 13:30** và **01:00 - 05:00** (giờ Việt Nam)"
        active = _is_happy_hour()
        embed = discord.Embed(
            title="🔥 GIỜ VÀNG" if active else "⏰ Giờ Vàng",
            description=(
                f"Khung giờ: {hh_slots}\n\n"
                f"**Trạng thái:** {'🔥 **ĐANG HOẠT ĐỘNG!**' if active else '❌ Chưa tới giờ'}\n\n"
                "Khi Giờ Vàng kích hoạt:\n"
                "• Tỉ lệ 4★ tăng từ **3% → 8.2%**\n"
                "• Tỉ lệ 5★ tăng từ **1% → 4.1%**\n"
                "• Tỉ lệ 6★ tăng từ **0.1% → 0.55%**\n"
                "• Dùng `!roll` để quay ngay!"
            ),
            color=0xff6600 if active else 0x888888)
        embed.set_footer(text="Giờ Vàng tính theo múi giờ Việt Nam (UTC+7)")
        await ctx.reply(embed=embed)

    async def _roll(self, ctx, user):
        pid = str(user.id)
        db = await get_db()
        try:
            crow = await db.execute("SELECT coins FROM players WHERE id=?", (pid,))
            player = await crow.fetchone()
            if not player:
                await ctx.reply("😅 Chưa có tài khoản! Hãy đánh nhau trước.")
                return
            coins = player[0]
            if coins < ROLL_COST:
                await ctx.reply(f"😅 Nghèo! Cần **{ROLL_COST}🪙**, có **{coins}🪙**")
                return

            prow = await db.execute("SELECT roll_count FROM gacha_pity WHERE player_id=?", (pid,))
            r = await prow.fetchone()
            pity = r[0] if r else 0

            is_hh = _is_happy_hour()
            force_6 = pity >= PITY_MAX - 1
            star = self._roll_star(force_6)
            eid, equip = self._pick_equip(star)
            if not eid:
                await ctx.reply("❌ Lỗi: không có trang bị phù hợp.")
                return

            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (ROLL_COST, pid))
            await db.execute(
                "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                (pid, eid))

            new_pity = 0 if star == 6 else pity + 1
            await db.execute(
                "INSERT INTO gacha_pity (player_id, roll_count) VALUES (?, ?) "
                "ON CONFLICT(player_id) DO UPDATE SET roll_count=?",
                (pid, new_pity, new_pity))
            await db.commit()

            coins_left = coins - ROLL_COST
            stats = equip.get("stats", {})
            star_emojis = STAR_EMOJIS.get(star, "⭐")
            star_name = STAR_NAMES.get(star, "")
            color = STAR_COLORS.get(star, 0xffffff)
            slot_icon = SLOT_ICONS.get(equip["slot"], "")
            slot_name = SLOT_NAMES.get(equip["slot"], equip["slot"])
            border = TIER_BORDERS.get(star, "")
            set_name = SET_NAMES.get(eid)

            embed = discord.Embed(color=color)

            top_line = f"{border}\n{star_emojis}"
            embed.description = top_line

            item_line = f"**{equip['name']}**"
            if set_name:
                item_line += f"\n└ {set_name}"
            item_line += f"\n└ {slot_icon} {slot_name}"

            stat_lines = []
            if "attack_min" in stats:
                stat_lines.append(f"⚔️**+{stats['attack_min']}~{stats['attack_max']}**")
            if "hp" in stats:
                stat_lines.append(self._format_stat_value("hp", stats["hp"]))
            if "defense" in stats:
                stat_lines.append(self._format_stat_value("defense", stats["defense"]))
            for k in ("spd", "crit", "pierce", "dodge", "reflect", "regen"):
                if k in stats:
                    stat_lines.append(self._format_stat_value(k, stats[k]))

            rarity_label = f"**[ {star_emojis} {star_name} ]**"
            embed.add_field(name=rarity_label, value=item_line, inline=False)

            if stat_lines:
                embed.add_field(name="📊 Chỉ Số", value=" | ".join(stat_lines), inline=False)

            pity_filled = self._pity_bar(new_pity)
            pity_label = f"🎯 Bảo Hành: **{new_pity}/{PITY_MAX}**"
            if star == 6:
                pity_label += " 🌟 ĐÃ KÍCH HOẠT!"
            elif force_6:
                pity_label += " ⚠️ LẦN CUỐI!"
            embed.add_field(name=pity_label, value=f"{pity_filled} `{new_pity}/{PITY_MAX}`", inline=False)

            embed.set_footer(text=f"💰 {coins_left}🪙 còn lại | {user.display_name}", icon_url=user.display_avatar.url)

            if star >= 5:
                embed.add_field(name="", value="🎉 CHÚC MỪNG! 🎉" if star == 5 else "✨🌟 **TUYỆT VỜI!** 🌟✨", inline=False)

            if star == 6:
                embed.title = "🌟✨🌈 **TRÚNG ĐỘC ĐẮC!** 🌈✨🌟"
                if force_6:
                    embed.description = f"{border}\n{star_emojis}\n💎 **BẢO HÀNH 6 SAO KÍCH HOẠT!** 💎"
                embed.add_field(name="", value="╔══════════════════════╗\n║  🎊 **6 SAO THẦN THOẠI** 🎊  ║\n╚══════════════════════╝", inline=False)
            else:
                embed.title = "🎰 Quay Trang Bị"

            if is_hh:
                embed.title = f"🔥 {embed.title}"
                hh_bar = f"`{'🟡' * PITY_BAR_LENGTH}`"
                embed.add_field(name="⏰ **GIỜ VÀNG**", value=f"{hh_bar}\n🔥 Tỉ lệ 4★-6★ tăng vọt! Chớp cơ hội!", inline=False)

            result_msg = await ctx.reply(embed=embed)

            try:
                await result_msg.add_reaction("🎰")
            except Exception:
                pass

        except Exception as e:
            await ctx.reply(f"❌ Lỗi: {e}")
            raise
        finally:
            await db.close()

async def setup(bot):
    await bot.add_cog(GachaCog(bot))
