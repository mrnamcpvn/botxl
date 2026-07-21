import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import re
from bot.database import get_db
from bot.data.quiz import QUIZ_QUESTIONS
from bot.data.equipment import EQUIPMENT, STAR_LABELS
from bot.data.shop_items import SHOP_ITEMS
from bot.config import QUIZ_CHANNEL_ID
from bot.engine.rewards import _EQUIP_BY_STAR, _STAR_CUMULATIVE, _TOTAL_WEIGHT

REWARD_COINS = (50, 200)


async def seed_questions(db):
    cursor = await db.execute("SELECT COUNT(*) FROM quiz_questions")
    count = (await cursor.fetchone())[0]
    if count < len(QUIZ_QUESTIONS):
        await db.execute("DELETE FROM quiz_questions")
        for q in QUIZ_QUESTIONS:
            await db.execute(
                "INSERT INTO quiz_questions (question, answer, category) VALUES (?, ?, ?)",
                (q["q"], q["a"], q["cat"]))
        await db.commit()


def normalize(s: str) -> str:
    """Chuẩn hóa đáp án: bỏ ký tự đặc biệt, lowercase."""
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_question: str | None = None
        self.answered = False
        # Lock để tránh race condition khi 2 người trả lời cùng lúc
        self._answer_lock = asyncio.Lock()
        self._task = asyncio.create_task(self._quiz_loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()

    async def _quiz_loop(self):
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            await seed_questions(db)
        finally:
            await db.close()
        while True:
            try:
                delay = random.randint(600, 1800)
                await asyncio.sleep(delay)
                await self._post_question()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _post_question(self):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM quiz_questions ORDER BY RANDOM() LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                return
            q = dict(row)
            self.active_question = q["answer"]
            self.answered = False

            cat_icon = {"game": "🎮", "general": "🧠", "dev": "💻"}.get(q["category"], "❓")
            embed = discord.Embed(
                title=f"{cat_icon} CÂU HỎI NHANH!",
                description=f"**{q['question']}**\n\nTrả lời đúng đầu tiên sẽ nhận thưởng! 💰",
                color=0xffaa00,
            )
            embed.set_footer(text="Gõ đáp án vào chat | 60s để trả lời")

            ch = self._get_channel()
            if ch:
                msg = await ch.send(embed=embed)
                await asyncio.sleep(60)
                if not self.answered:
                    embed2 = discord.Embed(
                        title="⏰ HẾT GIỜ!",
                        description=f"Không ai trả lời đúng!\nĐáp án: **{q['answer']}**",
                        color=0xff0000,
                    )
                    await msg.edit(embed=embed2)
                self.active_question = None
        finally:
            await db.close()

    def _get_channel(self):
        return self.bot.get_channel(QUIZ_CHANNEL_ID)

    @commands.command(name="quiz")
    @commands.has_permissions(administrator=True)
    async def quiz_cmd(self, ctx):
        await self._post_question()
        await ctx.message.delete()

    @app_commands.command(name="quiz", description="🎮 Tạo câu hỏi mini game (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def slash_quiz(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Đang tạo câu hỏi...", ephemeral=True)
        await self._post_question()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.active_question or self.answered:
            return

        user_answer = normalize(message.content)
        correct = normalize(self.active_question)
        if user_answer != correct:
            return

        # Lock để đảm bảo chỉ 1 người nhận thưởng dù nhiều người trả lời đúng cùng lúc
        async with self._answer_lock:
            # Double-check sau khi acquire lock — ai thắng trước thì thắng
            if self.answered:
                return
            self.answered = True
            answer_text = self.active_question  # lưu lại vì sẽ xóa bên dưới
            self.active_question = None

        sid = str(message.author.id)
        db = await get_db()
        try:
            # Kiểm tra player có tồn tại không
            prow = await (await db.execute(
                "SELECT id FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                return

            reward_coins = random.randint(*REWARD_COINS)
            reward_parts = [f"💰 +{reward_coins}🪙"]

            await db.execute(
                "UPDATE players SET coins=coins+? WHERE id=?", (reward_coins, sid))

            # Random bonus drop
            roll = random.random()
            if roll < 0.20:
                stone = random.choice(["stone_basic", "stone_medium", "stone_advanced"])
                stone_labels = {
                    "stone_basic": "Đá Sơ Cấp",
                    "stone_medium": "Đá Trung Cấp",
                    "stone_advanced": "Đá Cao Cấp",
                }
                stone_qty = random.randint(1, 3)
                await db.execute(
                    "INSERT OR IGNORE INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, 0, 0, 0)",
                    (sid,))
                await db.execute(
                    f"UPDATE player_enhance_stones SET {stone}={stone}+? WHERE player_id=?",
                    (stone_qty, sid))
                reward_parts.append(f"💎 +{stone_qty} {stone_labels[stone]}")

            elif roll < 0.30:
                consumable_ids = [i for i, it in SHOP_ITEMS.items() if it["type"] == "consumable"]
                consumable = random.choice(consumable_ids)
                await db.execute(
                    "INSERT OR REPLACE INTO inventory (player_id, item_id, quantity) VALUES (?, ?, COALESCE((SELECT quantity FROM inventory WHERE player_id=? AND item_id=?), 0) + 1)",
                    (sid, consumable, sid, consumable))
                reward_parts.append(f"🧪 +{SHOP_ITEMS[consumable]['name']}")

            elif roll < 0.55:
                # Dùng lookup table từ rewards.py — O(1) thay vì O(n)
                r = random.randint(1, _TOTAL_WEIGHT)
                star = 1
                for s, cum in _STAR_CUMULATIVE:
                    if r <= cum:
                        star = s
                        break
                eids = _EQUIP_BY_STAR.get(star, [])
                if eids:
                    eid = random.choice(eids)
                    chosen = EQUIPMENT[eid]
                    await db.execute(
                        "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                        (sid, eid))
                    reward_parts.append(f"⚒️ +{STAR_LABELS.get(star, '⭐')} {chosen['name']}")

            await db.commit()

            # Cập nhật quest progress
            from bot.cogs.quest import update_progress
            await update_progress(db, sid, 7)
            await update_progress(db, sid, 15)

            embed = discord.Embed(
                title="🎉 CHÍNH XÁC!",
                description=(
                    f"**{message.author.display_name}** trả lời đúng!\n"
                    f"Đáp án: **{answer_text}**\n\n"
                    f"{' | '.join(reward_parts)}"
                ),
                color=0x00ff00,
            )
            await message.reply(embed=embed)

        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
