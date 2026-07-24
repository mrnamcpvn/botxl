import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from bot.database import get_db
from bot.config import DAILY_LOGIN_REWARDS


class DailyLogin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _week_start(self) -> str:
        today = datetime.utcnow()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    def _today_day(self) -> int:
        return datetime.utcnow().weekday()  # 0=Monday ... 6=Sunday

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

    @commands.command(name="daily", aliases=["diemdanh"])
    async def daily_cmd(self, ctx):
        await self._daily(ctx, str(ctx.author.id), ctx.author.display_name, "!")

    @app_commands.command(name="daily", description="📅 Điểm danh nhận quà hàng ngày")
    async def slash_daily(self, interaction: discord.Interaction):
        await self._daily(interaction, str(interaction.user.id), interaction.user.display_name, "/")

    async def _daily(self, ctx_or_int, sid: str, name: str, prefix: str):
        db = await get_db()
        try:
            await self._ensure_player(db, sid)
            ws = self._week_start()
            today = self._today_day()
            day_num = today + 1  # 1-7

            cursor = await db.execute(
                "SELECT claimed FROM daily_logins WHERE player_id=? AND week_start=? AND day=?",
                (sid, ws, day_num))
            row = await cursor.fetchone()
            if row and row[0]:
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply("📅 Hôm nay bạn đã điểm danh rồi! Ngày mai quay lại nhé.")
                else:
                    await ctx_or_int.response.send_message("📅 Hôm nay bạn đã điểm danh rồi! Ngày mai quay lại nhé.", ephemeral=True)
                return

            reward = DAILY_LOGIN_REWARDS.get(day_num, {"coins": 200})
            coins = reward.get("coins", 0)
            stones = reward.get("stones", {})
            gacha_free = reward.get("gacha_free", False)

            await db.execute(
                "INSERT OR REPLACE INTO daily_logins (player_id, week_start, day, claimed) VALUES (?,?,?,1)",
                (sid, ws, day_num))
            if coins:
                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (coins, sid))
            if stones:
                await self._give_stones(db, sid, stones)
            await db.commit()

            lines = [f"📅 **Điểm danh ngày {day_num}/7**"]
            if coins:
                lines.append(f"💰 **+{coins}** coin")
            if stones:
                for k, v in stones.items():
                    label = {"stone_basic": "đá sơ cấp", "stone_medium": "đá trung cấp", "stone_advanced": "đá cao cấp"}.get(k, k)
                    lines.append(f"💎 **+{v}** {label}")
            if gacha_free:
                lines.append("🎰 **+1 lượt quay free!** (dùng `!roll`)")

            embed = discord.Embed(
                title="📅 ĐIỂM DANH THÀNH CÔNG!",
                description="\n".join(lines),
                color=0xf1c40f)
            embed.set_footer(text=f"Còn {7-day_num} ngày nữa là reset | !daily mỗi ngày")

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(DailyLogin(bot))
