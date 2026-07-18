import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import re
from bot.database import get_db
from bot.data.quiz import QUIZ_QUESTIONS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, DROP_WEIGHTS
from bot.data.shop_items import SHOP_ITEMS

QUIZ_CHANNEL_ID = None  # Auto-detect first text channel
REWARD_COINS = (50, 200)


async def seed_questions(db):
    cursor = await db.execute("SELECT COUNT(*) FROM quiz_questions")
    count = (await cursor.fetchone())[0]
    if count == 0:
        for q in QUIZ_QUESTIONS:
            await db.execute("INSERT INTO quiz_questions (question, answer, category) VALUES (?, ?, ?)",
                             (q["q"], q["a"], q["cat"]))
        await db.commit()


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().strip())


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_question = None
        self.answered = False
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
            except Exception as e:
                pass

    async def _post_question(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM quiz_questions ORDER BY RANDOM() LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                return
            q = dict(row)
            self.active_question = q["answer"]
            self.answered = False

            cat_icon = "🎮" if q["category"] == "game" else "🧠"
            embed = discord.Embed(
                title=f"{cat_icon} CÂU HỎI NHANH!",
                description=f"**{q['question']}**\n\nTrả lời đúng đầu tiên sẽ nhận thưởng! 💰",
                color=0xffaa00
            )
            embed.set_footer(text="Gõ đáp án vào chat | 60s để trả lời")

            ch = self._get_channel()
            if ch:
                msg = await ch.send(embed=embed)
                await asyncio.sleep(60)
                if not self.answered:
                    embed2 = discord.Embed(
                        title="⏰ HẾT GIỜ!",
                        description=f"Không ai trả lời đúng! Đáp án: **{q['answer']}**",
                        color=0xff0000
                    )
                    await msg.edit(embed=embed2)
                self.active_question = None
        finally:
            await db.close()

    def _get_channel(self):
        global QUIZ_CHANNEL_ID
        if QUIZ_CHANNEL_ID:
            ch = self.bot.get_channel(QUIZ_CHANNEL_ID)
            if ch:
                return ch
        for guild in self.bot.guilds:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    QUIZ_CHANNEL_ID = ch.id
                    return ch
        return None

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
        if user_answer == correct:
            self.answered = True
            sid = str(message.author.id)
            db = await get_db()
            try:
                reward_coins = random.randint(*REWARD_COINS)
                reward_parts = [f"💰 +{reward_coins}🪙"]

                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (reward_coins, sid))

                roll = random.random()
                if roll < 0.15:
                    stone = random.choice(["stone_basic", "stone_medium", "stone_advanced"])
                    stone_labels = {"stone_basic": "Đá sơ cấp", "stone_medium": "Đá trung cấp", "stone_advanced": "Đá cao cấp"}
                    stone_qty = random.randint(1, 3)
                    await db.execute(f"INSERT OR REPLACE INTO player_enhance_stones (player_id, {stone}, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0))",
                                     (sid, stone_qty, sid, sid, sid))
                    await db.execute(f"UPDATE player_enhance_stones SET {stone}=COALESCE((SELECT {stone} FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND ({stone} IS NULL OR {stone}=0)",
                                     (sid, sid))
                    reward_parts.append(f"💎 +{stone_qty} {stone_labels[stone]}")
                elif roll < 0.25:
                    consumable = random.choice([i for i, it in SHOP_ITEMS.items() if it["type"] == "consumable"])
                    await db.execute("INSERT OR REPLACE INTO inventory (player_id, item_id, quantity) VALUES (?, ?, COALESCE((SELECT quantity FROM inventory WHERE player_id=? AND item_id=?), 0) + 1)",
                                     (sid, consumable, sid, consumable))
                    reward_parts.append(f"🧪 +{SHOP_ITEMS[consumable]['name']}")
                elif roll < 0.30:
                    total = sum(DROP_WEIGHTS.values())
                    r = random.randint(1, total)
                    cum = 0
                    star = 1
                    for s, w in DROP_WEIGHTS.items():
                        cum += w
                        if r <= cum:
                            star = s
                            break
                    items = [e for eid, e in EQUIPMENT.items() if e["star"] == star]
                    if items:
                        chosen = random.choice(items)
                        eid = [k for k, v in EQUIPMENT.items() if v == chosen][0]
                        await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                                         (sid, eid))
                        reward_parts.append(f"⚒️ +{STAR_LABELS.get(star, '⭐')} {chosen['name']}")

                await db.commit()

                embed = discord.Embed(
                    title="🎉 CHÍNH XÁC!",
                    description=f"**{message.author.display_name}** trả lời đúng!\nĐáp án: **{self.active_question}**\n\n{' | '.join(reward_parts)}",
                    color=0x00ff00
                )
                await message.reply(embed=embed)
                self.active_question = None
            finally:
                await db.close()


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
