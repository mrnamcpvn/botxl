import discord
from discord import app_commands
from discord.ext import commands
from bot.database import get_db
from bot.config import ACHIEVEMENTS


class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_player(self, db, sid: str):
        await db.execute("INSERT OR IGNORE INTO players (id) VALUES (?)", (sid,))

    async def _give_stones(self, db, sid: str, stones: dict):
        if not stones:
            return
        sets = []
        vals = []
        for k, v in stones.items():
            sets.append(f"{k}={k}+?")
            vals.append(v)
        if sets:
            await db.execute(
                "INSERT INTO player_enhance_stones (player_id) VALUES (?) ON CONFLICT(player_id) DO UPDATE SET "
                + ", ".join(sets),
                (sid, *vals))

    async def update_progress(self, db, sid: str, ach_type: str, amount: int = 1):
        await self._ensure_player(db, sid)
        for ach_id, ach_def in ACHIEVEMENTS.items():
            if ach_def["type"] != ach_type:
                continue

            cursor = await db.execute(
                "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
                (sid, ach_id))
            row = await cursor.fetchone()
            if row and row[2]:
                continue

            old_progress = row[0] if row else 0
            completed = row[1] if row else 0
            new_progress = old_progress + amount
            target = ach_def["target"]

            if new_progress >= target and not completed:
                completed = 1

            await db.execute(
                "INSERT OR REPLACE INTO player_achievements (player_id, ach_id, progress, completed, claimed) VALUES (?,?,?,?,0)",
                (sid, ach_id, new_progress, completed))

    async def claim_reward(self, db, sid: str, ach_id: int) -> str:
        cursor = await db.execute(
            "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
            (sid, ach_id))
        row = await cursor.fetchone()
        if not row or not row[1]:
            return "❌ Chưa hoàn thành!"
        if row[2]:
            return "✅ Đã nhận thưởng rồi!"

        ach_def = ACHIEVEMENTS.get(ach_id)
        if not ach_def:
            return "❌ ID không hợp lệ!"

        coins = ach_def.get("reward_coins", 0)
        stones = ach_def.get("reward_stones", {})

        if coins:
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (coins, sid))
        if stones:
            await self._give_stones(db, sid, stones)
        await db.execute(
            "UPDATE player_achievements SET claimed=1 WHERE player_id=? AND ach_id=?",
            (sid, ach_id))

        parts = []
        if coins:
            parts.append(f"💰 +{coins} coin")
        if stones:
            for k, v in stones.items():
                label = {"stone_basic": "đá sơ cấp", "stone_medium": "đá trung cấp", "stone_advanced": "đá cao cấp"}.get(k, k)
                parts.append(f"💎 +{v} {label}")
        return "🎉 **" + ach_def["name"] + "** hoàn thành!\n" + "\n".join(parts)

    @commands.command(name="achievement", aliases=["achievements", "thanhtuu"])
    async def ach_cmd(self, ctx, *args):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            await self._ensure_player(db, sid)
            if args and args[0].isdigit():
                ach_id = int(args[0])
                cursor = await db.execute(
                    "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
                    (sid, ach_id))
                row = await cursor.fetchone()
                ach_def = ACHIEVEMENTS.get(ach_id)
                if not ach_def:
                    await ctx.reply("❌ Thành tựu không tồn tại!")
                    return
                ach_name = ach_def.get("name", f"#{ach_id}")
                target = ach_def["target"]
                progress = row[0] if row else 0
                completed = row[1] if row else 0
                claimed = row[2] if row else 0
                status = "✅ Đã nhận" if claimed else ("🏆 Hoàn thành" if completed else f"⏳ {progress}/{target}")
                reward_parts = []
                if ach_def.get("reward_coins"):
                    reward_parts.append(f"💰 {ach_def['reward_coins']}")
                for k, v in ach_def.get("reward_stones", {}).items():
                    label = {"stone_basic": "đá sơ cấp", "stone_medium": "đá trung cấp", "stone_advanced": "đá cao cấp"}.get(k, k)
                    reward_parts.append(f"💎 {v} {label}")
                embed = discord.Embed(
                    title=ach_name,
                    description=(
                        f"{ach_def.get('icon', '📌')} {ach_def['desc']}\n"
                        f"Tiến độ: **{status}**\n"
                        f"Thưởng: {'  '.join(reward_parts)}"
                    ),
                    color=0xf1c40f if completed else 0x888888)
                if completed and not claimed:
                    embed.add_field(name="📥 Nhận thưởng", value=f"Dùng `!achievement claim {ach_id}`", inline=False)
                await ctx.reply(embed=embed)
            elif args and args[0].lower() == "claim" and len(args) > 1 and args[1].isdigit():
                ach_id = int(args[1])
                msg = await self.claim_reward(db, sid, ach_id)
                await db.commit()
                await ctx.reply(msg)
            else:
                await self._show_list(ctx, db, sid)
        finally:
            await db.close()

    @app_commands.command(name="achievement", description="🏆 Xem thành tựu và nhận thưởng")
    @app_commands.describe(ach_id="ID thành tựu (bỏ trống = xem danh sách)")
    async def slash_ach(self, interaction: discord.Interaction, ach_id: int = None):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            await self._ensure_player(db, sid)
            if ach_id:
                cursor = await db.execute(
                    "SELECT progress, completed, claimed FROM player_achievements WHERE player_id=? AND ach_id=?",
                    (sid, ach_id))
                row = await cursor.fetchone()
                ach_def = ACHIEVEMENTS.get(ach_id)
                if not ach_def:
                    await interaction.response.send_message("❌ Thành tựu không tồn tại!", ephemeral=True)
                    return
                ach_name = ach_def.get("name", f"#{ach_id}")
                target = ach_def["target"]
                progress = row[0] if row else 0
                completed = row[1] if row else 0
                claimed = row[2] if row else 0
                status = "✅ Đã nhận" if claimed else ("🏆 Hoàn thành" if completed else f"⏳ {progress}/{target}")
                reward_parts = []
                if ach_def.get("reward_coins"):
                    reward_parts.append(f"💰 {ach_def['reward_coins']}")
                for k, v in ach_def.get("reward_stones", {}).items():
                    label = {"stone_basic": "đá sơ cấp", "stone_medium": "đá trung cấp", "stone_advanced": "đá cao cấp"}.get(k, k)
                    reward_parts.append(f"💎 {v} {label}")
                embed = discord.Embed(
                    title=ach_name,
                    description=(
                        f"{ach_def.get('icon', '📌')} {ach_def['desc']}\n"
                        f"Tiến độ: **{status}**\n"
                        f"Thưởng: {'  '.join(reward_parts)}"
                    ),
                    color=0xf1c40f if completed else 0x888888)
                if completed and not claimed:
                    embed.add_field(name="📥 Nhận thưởng", value=f"Dùng `!achievement claim {ach_id}` hoặc bấm nút Claim",
                                    inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                await self._show_list(interaction, db, sid)
        finally:
            await db.close()

    async def _show_list(self, ctx_or_int, db, sid):
        cursor = await db.execute(
            "SELECT ach_id, progress, completed, claimed FROM player_achievements WHERE player_id=?",
            (sid,))
        player_achs = {r[0]: {"p": r[1], "c": r[2], "cl": r[3]} for r in await cursor.fetchall()}

        lines = []
        total_completed = 0
        for ach_id in sorted(ACHIEVEMENTS.keys()):
            ach_def = ACHIEVEMENTS[ach_id]
            data = player_achs.get(ach_id, {"p": 0, "c": 0, "cl": 0})
            status = "✅" if data["cl"] else ("🏆" if data["c"] else "⬜")
            if data["c"]:
                total_completed += 1
            lines.append(f"{status} `#{ach_id:02d}` {ach_def['name']}")

        embed = discord.Embed(
            title="🏆 Thành Tựu",
            description=f"Hoàn thành: **{total_completed}/{len(ACHIEVEMENTS)}**\n\n"
                        f"{chr(10).join(lines)}",
            color=0xf1c40f)
        embed.set_footer(text="!achievement <ID> để xem chi tiết | !achievement claim <ID> nhận thưởng")
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(embed=embed)
        else:
            await ctx_or_int.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Achievements(bot))
