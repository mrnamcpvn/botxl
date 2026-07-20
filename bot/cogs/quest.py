import discord
from discord import app_commands
from discord.ext import commands
import random
from datetime import datetime
from bot.database import get_db
from bot.data.quests import QUESTS, QUESTS_PER_DAY, QUEST_POOL, QUEST_RESET_COST
from bot.data.shop_items import SHOP_ITEMS


QUESTS_PER_DAY = 5
QUEST_RESET_ITEM_ID = 26


async def ensure_quests(db, player_id: str):
    today = datetime.now().strftime("%Y-%m-%d")
    cursor = await db.execute(
        "SELECT COUNT(*) FROM daily_quests WHERE player_id=? AND date=?", (player_id, today))
    count = (await cursor.fetchone())[0]
    if count == 0:
        selected = random.sample(QUEST_POOL, min(QUESTS_PER_DAY, len(QUEST_POOL)))
        for qid in selected:
            q = QUESTS[qid]
            await db.execute(
                "INSERT INTO daily_quests (player_id, quest_id, progress, target, completed, claimed, date) VALUES (?, ?, 0, ?, 0, 0, ?)",
                (player_id, qid, q["target"], today))
        await db.commit()


async def update_progress(db, player_id: str, quest_id: int, amount: int = 1):
    await ensure_quests(db, player_id)
    today = datetime.now().strftime("%Y-%m-%d")
    await db.execute(
        "UPDATE daily_quests SET progress=MIN(target, progress+?) WHERE player_id=? AND quest_id=? AND date=? AND completed=0",
        (amount, player_id, quest_id, today))
    await db.execute(
        "UPDATE daily_quests SET completed=1 WHERE player_id=? AND quest_id=? AND date=? AND progress>=target",
        (player_id, quest_id, today))
    await db.commit()


class QuestView(discord.ui.View):
    def __init__(self, player_id: str, quests_data: list, completed_count: int, all_claimed: bool):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.quests_data = quests_data
        self.completed_count = completed_count
        self.all_claimed = all_claimed

        for i, qd in enumerate(quests_data):
            q = qd["quest"]
            prog = qd["progress"]
            target = qd["target"]
            done = "✅" if qd["completed"] else ""
            claimed = "🎁" if qd["claimed"] else ""
            label = f"{done}{claimed} {q['name']} ({prog}/{target})"[:80]
            btn = discord.ui.Button(
                label=label, style=discord.ButtonStyle.secondary if not qd["completed"] else discord.ButtonStyle.success,
                custom_id=f"quest_{i}", row=i)
            btn.callback = self._make_quest_cb(i)
            self.add_item(btn)

        if completed_count >= QUESTS_PER_DAY and not all_claimed:
            bonus_btn = discord.ui.Button(
                emoji="🌟", label="Nhận Thưởng Hoàn Thành", style=discord.ButtonStyle.primary,
                custom_id="quest_bonus", row=4)
            bonus_btn.callback = self._bonus_callback
            self.add_item(bonus_btn)

        reset_btn = discord.ui.Button(
            emoji="🎫", label="Reset Quest (500🪙)", style=discord.ButtonStyle.danger,
            custom_id="quest_reset", row=4)
        reset_btn.callback = self._reset_callback
        self.add_item(reset_btn)

    def _make_quest_cb(self, idx: int):
        async def cb(interaction: discord.Interaction):
            await interaction.response.defer()
            qd = self.quests_data[idx]
            if qd["completed"] and not qd["claimed"]:
                await self._claim_quest(interaction, idx)
            else:
                await interaction.followup.send("🤷 Quest này chưa hoàn thành hoặc đã nhận!", ephemeral=True)
        return cb

    async def _claim_quest(self, interaction: discord.Interaction, idx: int):
        qd = self.quests_data[idx]
        q = qd["quest"]
        qid = qd["quest_id"]
        sid = self.player_id
        db = await get_db()
        try:
            row = await (await db.execute(
                "SELECT completed, claimed FROM daily_quests WHERE player_id=? AND quest_id=? AND date=?",
                (sid, qid, datetime.now().strftime("%Y-%m-%d")))).fetchone()
            if not row or not row[0] or row[1]:
                await interaction.followup.send("🤷 Không thể nhận!", ephemeral=True)
                return

            await db.execute(
                "UPDATE daily_quests SET claimed=1 WHERE player_id=? AND quest_id=? AND date=?",
                (sid, qid, datetime.now().strftime("%Y-%m-%d")))

            reward_parts = []
            if q.get("reward_coins"):
                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (q["reward_coins"], sid))
                reward_parts.append(f"💰 +{q['reward_coins']}🪙")
            if q.get("reward_xp"):
                await db.execute("UPDATE players SET xp=xp+? WHERE id=?", (q["reward_xp"], sid))
                reward_parts.append(f"⭐ +{q['reward_xp']}XP")
            if q.get("reward_stone"):
                sk = {"basic": "stone_basic", "medium": "stone_medium", "advanced": "stone_advanced"}.get(q["reward_stone"], q["reward_stone"])
                sq = q.get("reward_stone_qty", 1)
                await db.execute(f"INSERT OR REPLACE INTO player_enhance_stones (player_id, {sk}, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0))",
                                 (sid, sq, sid, sid, sid))
                await db.execute(f"UPDATE player_enhance_stones SET {sk}=COALESCE((SELECT {sk} FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND ({sk} IS NULL OR {sk}=0)",
                                 (sid, sid))
                labels = {"stone_basic": "Đá sơ cấp", "stone_medium": "Đá trung cấp", "stone_advanced": "Đá cao cấp"}
                reward_parts.append(f"💎 +{sq} {labels.get(sk, sk)}")
            if q.get("reward_artifact"):
                await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + ?)",
                                 (sid, sid, sid, q["reward_artifact"]))
                reward_parts.append(f"💎 +{q['reward_artifact']} Đá thần khí")

            await db.execute("INSERT OR REPLACE INTO player_vip_coins (player_id, amount) VALUES (?, COALESCE((SELECT amount FROM player_vip_coins WHERE player_id=?), 0) + 1)",
                             (sid, sid))
            reward_parts.append("🪙 +1 VIP Coin")

            await db.commit()

            qd["claimed"] = True
            await interaction.edit_original_response(content=f"🎉 Nhận thưởng: {' | '.join(reward_parts)}", view=None)
        finally:
            await db.close()

    async def _bonus_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sid = self.player_id
        db = await get_db()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            c = await (await db.execute(
                "SELECT COUNT(*) FROM daily_quests WHERE player_id=? AND date=? AND completed=1",
                (sid, today))).fetchone()
            if c[0] < QUESTS_PER_DAY:
                await interaction.followup.send(f"🤷 Chưa đủ {QUESTS_PER_DAY} quest hoàn thành!", ephemeral=True)
                return

            claimed_check = await (await db.execute(
                "SELECT COUNT(*) FROM daily_quests WHERE player_id=? AND date=? AND claimed=1",
                (sid, today))).fetchone()
            if claimed_check[0] >= QUESTS_PER_DAY:
                await interaction.followup.send("🤷 Đã nhận thưởng hoàn thành rồi!", ephemeral=True)
                return

            await db.execute("UPDATE daily_quests SET claimed=1 WHERE player_id=? AND date=?", (sid, today))
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (1000, sid))
            await db.execute("INSERT OR REPLACE INTO player_enhance_stones (player_id, stone_advanced, stone_basic, stone_medium, stone_advanced) VALUES (?, 1, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), 1)",
                             (sid, sid, sid))
            await db.execute("UPDATE player_enhance_stones SET stone_advanced=COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND (stone_advanced IS NULL OR stone_advanced=0)",
                             (sid, sid))
            await db.execute("INSERT OR REPLACE INTO player_vip_coins (player_id, amount) VALUES (?, COALESCE((SELECT amount FROM player_vip_coins WHERE player_id=?), 0) + 2)",
                             (sid, sid))
            await db.commit()
            await interaction.edit_original_response(content="🌟 HOÀN THÀNH 5/5! +1000🪙 +💎 Đá cao cấp x1 +🪙 2 VIP Coin", view=None)
        finally:
            await db.close()

    async def _reset_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send(
            "🎫 Chọn quest muốn reset bằng cách bấm nút quest đó!\n(Cần vé Reset Quest trong inventory)",
            ephemeral=True)


class QuestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="quest", aliases=["quests", "nv"])
    async def quest_cmd(self, ctx):
        await self._show_quest(ctx, str(ctx.author.id), ctx.author.display_name, "!")

    @app_commands.command(name="quest", description="📋 Xem nhiệm vụ hàng ngày")
    async def slash_quest(self, interaction: discord.Interaction):
        await self._show_quest(interaction, str(interaction.user.id), interaction.user.display_name, "/")

    async def _show_quest(self, ctx_or_int, sid: str, display_name: str, prefix: str):
        db = await get_db()
        try:
            await ensure_quests(db, sid)
            today = datetime.now().strftime("%Y-%m-%d")
            cursor = await db.execute(
                "SELECT * FROM daily_quests WHERE player_id=? AND date=? ORDER BY quest_id", (sid, today))
            rows = await cursor.fetchall()
            if not rows:
                await self._reply(ctx_or_int, "🤷 Không có nhiệm vụ nào!")
                return

            quests_data = []
            completed = 0
            for r in rows:
                rd = dict(r)
                qid = rd["quest_id"]
                q = QUESTS.get(qid)
                if not q:
                    continue
                rd["quest"] = q
                quests_data.append(rd)
                if rd["completed"]:
                    completed += 1

            # Auto-claim completed quests + bonus
            claim_msgs = []
            bonus_given = False
            for qd in quests_data:
                if qd["completed"] and not qd["claimed"]:
                    q = QUESTS.get(qd["quest_id"], {})
                    qd["claimed"] = True
                    if q.get("reward_coins"):
                        await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (q["reward_coins"], sid))
                    if q.get("reward_xp"):
                        await db.execute("UPDATE players SET xp=xp+? WHERE id=?", (q["reward_xp"], sid))
                    if q.get("reward_stone"):
                        sk = {"basic":"stone_basic","medium":"stone_medium","advanced":"stone_advanced"}.get(q["reward_stone"], q["reward_stone"])
                        sq = q.get("reward_stone_qty", 1)
                        await db.execute(f"INSERT OR REPLACE INTO player_enhance_stones (player_id, {sk}, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0))",
                                         (sid, sq, sid, sid, sid))
                        await db.execute(f"UPDATE player_enhance_stones SET {sk}=COALESCE((SELECT {sk} FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND ({sk} IS NULL OR {sk}=0)", (sid, sid))
                    if q.get("reward_artifact"):
                        await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + ?)",
                                         (sid, sid, sid, q["reward_artifact"]))
                    await db.execute("UPDATE daily_quests SET claimed=1 WHERE player_id=? AND quest_id=? AND date=?",
                                     (sid, qd["quest_id"], today))
                    await db.execute("INSERT OR REPLACE INTO player_vip_coins (player_id, amount) VALUES (?, COALESCE((SELECT amount FROM player_vip_coins WHERE player_id=?), 0) + 1)",
                                     (sid, sid))
                    claim_msgs.append(f"🎉 **{q.get('name','?')}**: +{q.get('reward_coins',0)}🪙 +1 VIP")

            if completed >= QUESTS_PER_DAY:
                all_claimed = await (await db.execute(
                    "SELECT COUNT(*) FROM daily_quests WHERE player_id=? AND date=? AND claimed=1", (sid, today))).fetchone()
                if all_claimed[0] >= QUESTS_PER_DAY:
                    bonus_already = await (await db.execute("SELECT 1 FROM daily_quests WHERE player_id=? AND date=? AND claimed=1 LIMIT 1", (sid, today))).fetchone()
                    bonus_given = True

            if claim_msgs:
                await db.commit()

            embed = discord.Embed(
                title=f"📋 Nhiệm Vụ Hàng Ngày — {display_name}",
                description=f"✅ Hoàn thành: **{completed}/{QUESTS_PER_DAY}**\n🎫 Reset: `{prefix}questreset <số>` (cần Vé Reset Quest)",
                color=0xffaa00)

            for i, qd in enumerate(quests_data):
                q = qd["quest"]
                prog = qd["progress"]
                target = qd["target"]
                bar_filled = min(10, prog * 10 // max(target, 1))
                bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
                status = "✅ ĐÃ XONG" if qd["completed"] else ""
                if qd["claimed"]:
                    status = "🎁 ĐÃ NHẬN"
                embed.add_field(
                    name=f"#{i+1} {q['name']} {status}",
                    value=f"{q['desc']}\n`{prog}/{target}` {bar}",
                    inline=False)

            vip_cursor = await db.execute("SELECT amount FROM player_vip_coins WHERE player_id=?", (sid,))
            vip_row = await vip_cursor.fetchone()
            vip_coins = vip_row[0] if vip_row else 0
            embed.set_footer(text=f"🪙 VIP Coins: {vip_coins} | Reset quest cần Vé Reset Quest (shop)")

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)
        finally:
            await db.close()

    @commands.command(name="questreset", aliases=["qr"])
    async def questreset_cmd(self, ctx, quest_num: str = None):
        await self._reset_quest(ctx, str(ctx.author.id), quest_num, "!")

    async def _reset_quest(self, ctx_or_int, sid: str, quest_num: str, prefix: str):
        if not quest_num:
            await self._reply(ctx_or_int, f"❌ {prefix}questreset <số 1-5>")
            return
        try:
            num = int(quest_num.strip())
            if num < 1 or num > 5:
                raise ValueError
        except:
            await self._reply(ctx_or_int, "❌ Số từ 1-5!")
            return

        db = await get_db()
        try:
            inv = await (await db.execute(
                "SELECT quantity FROM inventory WHERE player_id=? AND item_id=?", (sid, QUEST_RESET_ITEM_ID))).fetchone()
            if not inv or inv[0] < 1:
                await self._reply(ctx_or_int, "❌ Cần Vé Reset Quest! Mua ở shop 500🪙")
                return

            today = datetime.now().strftime("%Y-%m-%d")
            cursor = await db.execute(
                "SELECT * FROM daily_quests WHERE player_id=? AND date=? ORDER BY quest_id", (sid, today))
            rows = await cursor.fetchall()
            if num > len(rows):
                await self._reply(ctx_or_int, f"❌ Chỉ có {len(rows)} quest!")
                return

            target_row = rows[num - 1]
            old_qid = target_row["quest_id"]
            old_q = QUESTS.get(old_qid, {})

            available = [qid for qid in QUEST_POOL if qid not in [r["quest_id"] for r in rows]]
            if not available:
                await self._reply(ctx_or_int, "❌ Không còn quest khác để đổi!")
                return
            new_qid = random.choice(available)
            new_q = QUESTS[new_qid]

            await db.execute(
                "DELETE FROM daily_quests WHERE player_id=? AND quest_id=? AND date=?",
                (sid, old_qid, today))
            await db.execute(
                "INSERT INTO daily_quests (player_id, quest_id, progress, target, completed, claimed, date) VALUES (?, ?, 0, ?, 0, 0, ?)",
                (sid, new_qid, new_q["target"], today))

            new_qty = inv[0] - 1
            if new_qty <= 0:
                await db.execute("DELETE FROM inventory WHERE player_id=? AND item_id=?", (sid, QUEST_RESET_ITEM_ID))
            else:
                await db.execute("UPDATE inventory SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, sid, QUEST_RESET_ITEM_ID))

            await db.commit()
            await self._reply(ctx_or_int, f"🎫 Reset **{old_q.get('name', '?')}** → **{new_q['name']}**!")
        finally:
            await db.close()

    @commands.command(name="vip")
    async def vip_cmd(self, ctx):
        await self._show_vip(ctx, str(ctx.author.id))

    @app_commands.command(name="vip", description="🪙 Xem VIP Coin")
    async def slash_vip(self, interaction: discord.Interaction):
        await self._show_vip(interaction, str(interaction.user.id))

    async def _show_vip(self, ctx_or_int, sid: str):
        db = await get_db()
        try:
            row = await (await db.execute("SELECT amount FROM player_vip_coins WHERE player_id=?", (sid,))).fetchone()
            coins = row[0] if row else 0
            embed = discord.Embed(
                title="🪙 VIP Coin",
                description=f"Bạn có **{coins}** VIP Coin\n\n🛒 VIP Shop (sắp ra mắt):\n• Đá thần khí x5: 10 VIP\n• Trang bị 5★: 30 VIP\n• Waifu SVIP: 50 VIP",
                color=0xffd700)
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


async def setup(bot):
    await bot.add_cog(QuestCog(bot))
