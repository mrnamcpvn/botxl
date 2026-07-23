import discord
from discord.ext import commands
import random
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, DROP_WEIGHTS, STAR_LABELS, STAR_NAMES, STAR_COLORS, SLOT_NAMES

ROLL_COST = 1000
PITY_MAX = 100

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

class GachaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _get_pity(self, player_id: str) -> int:
        db = await get_db()
        row = await db.execute("SELECT roll_count FROM gacha_pity WHERE player_id=?", (player_id,))
        r = await row.fetchone()
        await db.close()
        return r[0] if r else 0

    async def _set_pity(self, player_id: str, count: int):
        db = await get_db()
        await db.execute(
            "INSERT INTO gacha_pity (player_id, roll_count) VALUES (?, ?) "
            "ON CONFLICT(player_id) DO UPDATE SET roll_count=?",
            (player_id, count, count))
        await db.commit()
        await db.close()

    def _roll_star(self, force_6star: bool) -> int:
        if force_6star:
            return 6
        total = sum(DROP_WEIGHTS.values())
        roll = random.randint(1, total)
        cumulative = 0
        for star, weight in sorted(DROP_WEIGHTS.items()):
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

            pity = await self._get_pity(pid)
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
            await self._set_pity(pid, new_pity)

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
