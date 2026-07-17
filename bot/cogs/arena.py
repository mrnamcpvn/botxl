import discord
from discord import app_commands
from discord.ext import commands
import time
import json
import asyncio
from bot.database import get_db
from bot.data.skills import SKILLS_DB, CATEGORY_LABELS, RARITY_COLORS, RARITY_STARS, SLOT_NAMES
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT
from bot.data.classes import CLASSES, PERK_DESCRIPTIONS, DEFAULT_SKILLS, DEFAULT_SKILL_SLOTS
from bot.engine.battle import get_effective_stats, get_equipped_skill, regen_hp, get_class_perk, calc_class_stat
from bot.engine.rewards import calc_level, calc_rewards, apply_rewards
from bot.engine.ranking import calculate_elo
from bot.config import HP_REGEN_RATE, HP_REGEN_INTERVAL, STUCK_BATTLE_TIMEOUT, CHALLENGE_TIMEOUT_SECONDS, BATTLE_COOLDOWN_SECONDS
from bot.logger import logger
from bot.cogs.admin import ROLE_MULTIPLIERS
from bot.views.stats_view import StatsView
from bot.views.leaderboard_view import LeaderboardView
from bot.engine.combat_power import update_combat_power


def action_skill_id(pdata: dict, move_type: str) -> int:
    cat = "defense" if move_type == "defense" else move_type
    sk = get_equipped_skill(pdata, cat)
    for sid, s in SKILLS_DB.items():
        if s["name"] == sk["name"]:
            return sid
    return 1


class Arena(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cleanup_task = None

    async def cog_load(self):
        self._cleanup_task = asyncio.create_task(self._stuck_battle_cleanup_loop())

    async def cog_unload(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()

    async def _stuck_battle_cleanup_loop(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                await asyncio.sleep(15)
                await self._cleanup_stuck_battles()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CLEANUP] {e}")

    async def _cleanup_stuck_battles(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE last_move < ?", (time.time() - STUCK_BATTLE_TIMEOUT,))
            stale = await cursor.fetchall()
            for battle in stale:
                try:
                    battle = dict(battle)
                    p1_id = battle["player1_id"]
                    p2_id = battle["player2_id"]
                    winner_id = battle.get("turn", p1_id)
                    loser_id = p2_id if winner_id == p1_id else p1_id
                    wdata = dict(await (await db.execute("SELECT * FROM players WHERE id=?", (winner_id,))).fetchone() or {})
                    ldata = dict(await (await db.execute("SELECT * FROM players WHERE id=?", (loser_id,))).fetchone() or {})
                    if wdata:
                        wdata["wins"] = wdata.get("wins", 0) + 1
                        await db.execute("UPDATE players SET wins=?, last_battle_time=? WHERE id=?", (wdata["wins"], time.time(), winner_id))
                    if ldata:
                        ldata["losses"] = ldata.get("losses", 0) + 1
                        await db.execute("UPDATE players SET losses=?, last_battle_time=? WHERE id=?", (ldata["losses"], time.time(), loser_id))
                    await db.execute("DELETE FROM active_battles WHERE id=?", (battle["id"],))
                    await db.execute("DELETE FROM battle_status WHERE battle_id=?", (battle["id"],))
                    ch = self.bot.get_channel(int(battle["channel_id"]))
                    if ch:
                        try:
                            await ch.send(f"🧹 Trận kẹt <@{p1_id}> vs <@{p2_id}> tự hủy!\n🏆 <@{winner_id}> thắng.")
                        except:
                            pass
                except Exception as e:
                    logger.error(f"[CLEANUP] Lỗi battle {battle.get('id', '?')}: {e}")
            await db.execute("DELETE FROM challenges WHERE created_at < ?", (time.time() - CHALLENGE_TIMEOUT_SECONDS,))
            await db.commit()
        finally:
            await db.close()

    @commands.command(name="trogiup", aliases=["help", "h"])
    async def help_cmd(self, ctx):
        embed = discord.Embed(title="⚔️ Đấu Trường Ba Que Xỏ Lá", color=0xff6600,
                              description="Game đấm nhau bằng xỏ lá, khịa nhau, chọc gậy bánh xe!")
        embed.add_field(name="📝 Cơ Bản", value="`!register` `!stats` `!upgrade <hp/atk/def>` `!leaderboard`", inline=False)
        embed.add_field(name="⚔️ Đấm Nhau", value="`!challenge @player` → bấm nút ✅/❌\nBấm 💥🔥🛡️ khi tới lượt (15s)\nTừ chối/hết giờ: -20🪙", inline=False)
        embed.add_field(name="🏪 Shop", value="`!shop` `!buy <số>` `!use <số>` `!equip <số>` `!inv`", inline=False)
        embed.add_field(name="🔥 Kỹ Năng (4 slot)", value="`!skills` — Xem 20 skill\n`!buyskill <số>` — Mua skill\n`!equipskill <loại> <số>` — Gán skill", inline=False)
        embed.add_field(name="🎭 Class", value="`!class` — Xem/dổi class", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="attack", aliases=["xola", "xl"])
    async def attack_cmd(self, ctx):
        await self._text_fallback(ctx, "attack")

    @commands.command(name="special", aliases=["dacbiet", "db"])
    async def special_cmd(self, ctx):
        await self._text_fallback(ctx, "special")

    @commands.command(name="defend", aliases=["phongthu", "pt", "thu"])
    async def defend_cmd(self, ctx):
        await self._text_fallback(ctx, "defense")

    async def _text_fallback(self, ctx, move_type):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE player1_id=? OR player2_id=?", (sid, sid))
            battle = await cursor.fetchone()
            if not battle:
                await ctx.reply("🤷 Không có trận nào!")
                return
            battle = dict(battle)
            if battle["turn"] != sid:
                await ctx.reply("⏳ Chưa tới lượt!")
                return

            cat = "defense" if move_type == "defense" else move_type
            pdata = await self._get_player_data(db, sid)
            cd_key = f"{cat}_cd"
            if pdata.get(cd_key, 0) > 0:
                sk = get_equipped_skill(pdata, cat)
                await ctx.reply(f"⏳ **{sk['name']}** đang hồi! Còn **{pdata[cd_key]}** turn!")
                return

            is_p1 = sid == battle["player1_id"]
            stunned = bool(battle.get("p1_stunned", 0)) if is_p1 else bool(battle.get("p2_stunned", 0))
            if stunned:
                await ctx.reply("🌑 Đang bị choáng, mất lượt!")
                return

            guild = ctx.guild
            p1_id = battle["player1_id"]
            p2_id = battle["player2_id"]

            p1 = await self._load_full_player(db, p1_id)
            p2 = await self._load_full_player(db, p2_id)

            p1_m = guild.get_member(int(p1_id))
            p2_m = guild.get_member(int(p2_id))

            p1["name"] = p1_m.display_name if p1_m else p1_id
            p2["name"] = p2_m.display_name if p2_m else p2_id

            turn_player = 0 if sid == p1_id else 1
            skill = get_equipped_skill(p1 if turn_player == 0 else p2, cat)

            flags = {
                "p1_defending": bool(battle.get("p1_defending", 0)),
                "p2_defending": bool(battle.get("p2_defending", 0)),
                "p1_stunned": bool(battle.get("p1_stunned", 0)),
                "p2_stunned": bool(battle.get("p2_stunned", 0)),
                "turn_count": 0,
            }

            # Load dynamic effects from battle_status
            import json
            bs_cursor = await db.execute("SELECT key, value FROM battle_status WHERE battle_id=?", (battle["id"],))
            async for bs_row in bs_cursor:
                flags[bs_row[0]] = json.loads(bs_row[1])

            from bot.engine.battle import execute_action
            result = await execute_action(
                p1, p2, turn_player,
                {"type": move_type, "skill_id": action_skill_id(p1 if turn_player == 0 else p2, move_type)},
                flags
            )

            p1 = result["p1"]
            p2 = result["p2"]

            await self._save_player_data(db, p1_id, p1)
            await self._save_player_data(db, p2_id, p2)

            if result["finished"]:
                winner_id = result["winner_id"]
                winner = p1 if winner_id == p1_id else p2
                loser = p2 if winner_id == p1_id else p1
                w_coins, w_xp = calc_rewards(True, winner.get("level", 1), loser.get("level", 1))
                l_coins, l_xp = calc_rewards(False)
                apply_rewards(p1 if winner_id == p1_id else p2, w_coins, w_xp)
                apply_rewards(p2 if winner_id == p1_id else p1, l_coins, l_xp)
                p1_battles = p1.get("wins", 0) + p1.get("losses", 0)
                new_elo_p1, new_elo_p2 = calculate_elo(
                    p1.get("elo", 1000), p2.get("elo", 1000),
                    1 if winner_id == p1_id else 2, p1_battles)
                p1["elo"] = new_elo_p1
                p2["elo"] = new_elo_p2
                await self._save_player_data(db, p1_id, p1)
                await self._save_player_data(db, p2_id, p2)
                await db.execute("UPDATE players SET last_battle_time=? WHERE id=? OR id=?", (time.time(), p1_id, p2_id))
                await db.execute("DELETE FROM active_battles WHERE id=?", (battle["id"],))
                await db.commit()

                lines = result["log_messages"]
                embed = discord.Embed(title="⚔️ KẾT THÚC!", description="\n".join(lines), color=0xffd700)
                await ctx.send(embed=embed)
            else:
                new_turn = p2_id if turn_player == 0 else p1_id
                await db.execute("UPDATE active_battles SET turn=?, last_move=?, p1_defending=?, p2_defending=?, p1_stunned=?, p2_stunned=? WHERE id=?",
                                 (new_turn, time.time(),
                                  int(flags.get("p1_defending", 0)), int(flags.get("p2_defending", 0)),
                                  int(flags.get("p1_stunned", 0)), int(flags.get("p2_stunned", 0)),
                                  battle["id"]))

                # Save dynamic effects to battle_status
                await db.execute("DELETE FROM battle_status WHERE battle_id=?", (battle["id"],))
                dynamic_keys = {"p1_burn", "p2_burn", "p1_shield_hp", "p2_shield_hp",
                                "p1_shield_pop_heal", "p2_shield_pop_heal",
                                "p1_counter", "p2_counter", "p1_counter_immune", "p2_counter_immune",
                                "p1_rage_dmg", "p2_rage_dmg", "p1_dodge_passive", "p2_dodge_passive", "turn_count"}
                for key, val in flags.items():
                    if key in dynamic_keys:
                        pid = p1_id if key.startswith("p1") else (p2_id if key.startswith("p2") else p1_id)
                        await db.execute("INSERT INTO battle_status (battle_id, player_id, key, value) VALUES (?, ?, ?, ?)",
                                          (battle["id"], pid, key, json.dumps(val)))

                await db.commit()

                next_m = p1_m if new_turn == p1_id else p2_m
                result["log_messages"].append(f"\n⏳ Lượt **{next_m.display_name}** (bấm nút để đánh)!")
                embed = discord.Embed(title="⚔️ DIỄN BIẾN", description="\n".join(result["log_messages"]), color=0x00ff00)
                await ctx.send(embed=embed)
        finally:
            await db.close()

    @commands.command(name="register")
    async def register(self, ctx):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))
            if await cursor.fetchone():
                await ctx.reply(f"🤷 {ctx.author.display_name} đăng ký rồi! `/stats`")
                return

            cls = CLASSES["banxabong"]
            await db.execute("""INSERT INTO players (id, name, class_id, hp, hp_max, attack_min, attack_max, defense, coins, last_hp_update)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (sid, ctx.author.display_name, "banxabong",
                               cls["hp_base"], cls["hp_base"],
                               cls["atk_base"], cls["atk_base"] + 5,
                               cls["def_base"], 0, time.time()))

            for sk_id in DEFAULT_SKILLS["banxabong"]:
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS["banxabong"].items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await self._sync_role_mult(db, ctx.author)
            await db.commit()
            await ctx.reply(f"✅ **{ctx.author.display_name}** đăng ký thành công! 💪")
        finally:
            await db.close()

    @commands.command(name="stats")
    async def stats(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        sid = str(target.id)
        db = await get_db()
        try:
            await self._sync_role_mult(db, target)
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await ctx.reply("🤷 Chưa đăng ký! `!register`")
                return
            pdata = dict(row)
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    slot = SHOP_ITEMS[eiid]["slot"]
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}
            wife_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
            wives_data = [dict(r) async for r in wife_cursor]
            regen_hp(pdata)
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?", (pdata["hp"], pdata.get("last_hp_update", time.time()), sid))
            await update_combat_power(sid, pdata, wives_data)
            await db.commit()

            view = StatsView(target, pdata, wives_data)
            await ctx.send(embed=view.embed, view=view)
        finally:
            await db.close()

    @stats.error
    async def stats_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Tìm không ra!")

    @commands.command(name="upgrade", aliases=["nang", "+"])
    async def upgrade(self, ctx, stat: str = None):
        if not stat:
            sid = str(ctx.author.id)
            db = await get_db()
            try:
                cursor = await db.execute("SELECT stat_points FROM players WHERE id=?", (sid,))
                row = await cursor.fetchone()
                sp = row[0] if row else 0
                await ctx.send(embed=discord.Embed(title="⭐ Nâng Chỉ Số", color=0x00aaff,
                    description=f"**{sp} điểm**\n`!upgrade hp` +10 HP\n`!upgrade atk` +2~3 ATK\n`!upgrade def` +2 DEF"))
            finally:
                await db.close()
            return
        stat = stat.lower().strip()
        if stat not in ("hp", "atk", "def"):
            await ctx.reply("❌ !upgrade để xem hướng dẫn")
            return
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await ctx.reply("😅 Chưa đăng ký!")
                return
            pdata = dict(row)
            sp = pdata.get("stat_points", 0)
            if sp < 1:
                await ctx.reply("😅 Hết điểm! Đánh nhau lên cấp đi.")
                return
            if stat == "hp":
                new_hp_max = pdata["hp_max"] + 10
                new_hp = pdata["hp"] + 10
                await db.execute("UPDATE players SET hp_max=?, hp=?, upgrade_hp=upgrade_hp+1, stat_points=? WHERE id=?",
                                 (new_hp_max, new_hp, sp - 1, sid))
                sn = "❤️ HP"
            elif stat == "atk":
                await db.execute("UPDATE players SET attack_min=attack_min+2, attack_max=attack_max+3, upgrade_atk=upgrade_atk+1, stat_points=? WHERE id=?",
                                 (sp - 1, sid))
                sn = "⚔️ ATK"
            else:
                await db.execute("UPDATE players SET defense=defense+2, upgrade_def=upgrade_def+1, stat_points=? WHERE id=?",
                                 (sp - 1, sid))
                sn = "🛡️ DEF"
            await db.commit()
            await update_combat_power(sid)
            await ctx.send(embed=discord.Embed(title="⬆️ NÂNG THÀNH CÔNG!", color=0x00ff88,
                                                description=f"**{sn}** đã tăng! Còn **{sp - 1} điểm**."))
        finally:
            await db.close()

    @commands.command(name="challenge")
    async def challenge(self, ctx, member: discord.Member = None):
        if not member:
            await ctx.reply("❌ !challenge @player")
            return
        if member.id == ctx.author.id:
            await ctx.reply("🤡 Tự thách mình?")
            return
        if member.bot:
            await ctx.reply("🤖 Bot sao đấu?")
            return
        sid = str(member.id)
        sc = str(ctx.author.id)
        db = await get_db()
        try:
            now = time.time()
            for check_sid, check_name in [(sid, member.display_name), (sc, ctx.author.display_name)]:
                cursor = await db.execute("SELECT role_mult, last_battle_time FROM players WHERE id=?", (check_sid,))
                row = await cursor.fetchone()
                if row and row[0] < 3.0 and row[1] > 0:
                    remaining = BATTLE_COOLDOWN_SECONDS - int(now - row[1])
                    if remaining > 0:
                        mins = remaining // 60
                        secs = remaining % 60
                        await ctx.reply(f"⏳ **{check_name}** hồi chiêu! Còn {mins}p{secs}s nữa mới được đánh tiếp.")
                        return

            ch_cursor = await db.execute("SELECT 1 FROM challenges WHERE target_id=? OR challenger_id=?", (sid, sc))
            if await ch_cursor.fetchone():
                await ctx.reply(f"⚠️ Có người đang liên quan lời thách!")
                return
            ch_cursor2 = await db.execute("SELECT 1 FROM challenges WHERE target_id=? OR challenger_id=?", (sc, sid))
            if await ch_cursor2.fetchone():
                await ctx.reply(f"⚠️ Có người đang liên quan lời thách!")
                return
            b_cursor = await db.execute("SELECT 1 FROM active_battles WHERE player1_id=? OR player2_id=?", (sid, sid))
            if await b_cursor.fetchone():
                await ctx.reply(f"⚔️ {member.display_name} đang đánh!")
                return
            b2_cursor = await db.execute("SELECT 1 FROM active_battles WHERE player1_id=? OR player2_id=?", (sc, sc))
            if await b2_cursor.fetchone():
                await ctx.reply("⚔️ Mày đang đánh!")
                return
            pd_cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            pd_row = await pd_cursor.fetchone()
            if not pd_row:
                await ctx.reply(f"💀 {member.display_name} chưa đăng ký!")
                return
            pd = dict(pd_row)
            regen_hp(pd)
            if pd["hp"] <= 0:
                await ctx.reply(f"💀 {member.display_name} 0 máu!")
                return
            md_cursor = await db.execute("SELECT * FROM players WHERE id=?", (sc,))
            md_row = await md_cursor.fetchone()
            if not md_row:
                await ctx.reply("💀 Mày chưa đăng ký!")
                return
            md = dict(md_row)
            regen_hp(md)
            if md["hp"] <= 0:
                await ctx.reply("💀 Mày 0 máu!")
                return
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?",
                              (pd["hp"], pd.get("last_hp_update", time.time()), sid))
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?",
                              (md["hp"], md.get("last_hp_update", time.time()), sc))
            await db.execute("INSERT INTO challenges (target_id, challenger_id, channel_id, created_at) VALUES (?, ?, ?, ?)",
                              (sid, sc, str(ctx.channel.id), time.time()))
            await db.commit()
            embed = discord.Embed(title="⚔️ THÁCH ĐẤU!", color=0xff0000,
                                  description=f"**{ctx.author.display_name}** 👊 **{member.display_name}**!\n<@{member.id}> bấm nút! ⏰30s")
            from bot.views.challenge_view import ChallengeView
            view = ChallengeView(self.bot, sid, sc, ctx.author.display_name, member.display_name, ctx.channel.id)
            await ctx.send(embed=embed, view=view)
        finally:
            await db.close()

    @commands.command(name="give", aliases=["chuyentien", "tien"])
    async def give_cmd(self, ctx, member: discord.Member = None, amount: str = None):
        await self._give_coins(ctx, str(ctx.author.id), member, amount, "!")

    @app_commands.command(name="give", description="💰 Chuyển xu cho người khác")
    @app_commands.describe(member="Người nhận", amount="Số xu")
    async def slash_give(self, interaction: discord.Interaction, member: discord.Member, amount: str):
        await self._give_coins(interaction, str(interaction.user.id), member, amount, "/")

    async def _give_coins(self, ctx_or_int, sid: str, member, amount: str, prefix: str):
        if not member or not amount:
            msg = f"❌ `{prefix}give @player <số>`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        if str(member.id) == sid:
            msg = "🤡 Tự chuyển cho mình?"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        try:
            amt = int(amount.strip())
        except:
            msg = "❌ Số không hợp lệ!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        if amt <= 0:
            msg = "❌ Số phải > 0!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        rid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                msg = "🤷 Chưa đăng ký!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return
            if row[0] < amt:
                msg = f"😅 Không đủ! Có {row[0]}🪙, cần {amt}🪙"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            recv_cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (rid,))
            if not await recv_cursor.fetchone():
                msg = f"🤷 {member.display_name} chưa đăng ký!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (amt, sid))
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (amt, rid))
            await db.commit()
            msg = f"💰 Đã chuyển **{amt}🪙** cho **{member.display_name}**!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg)
        finally:
            await db.close()

    @commands.command(name="skills", aliases=["skill", "kynang"])
    async def skills_cmd(self, ctx):
        await self._show_skills(ctx, ctx.author, "!")

    async def _show_skills(self, ctx_or_int, user, prefix):
        sid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            pdata = dict(row)
            own_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (sid,))
            owned = [1, 5, 10, 14]
            async for r in own_cursor:
                owned.append(r[0])
            owned = list(set(owned))
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            equipped = {}
            async for r in slots_cursor:
                equipped[r[0]] = r[1]
            coins = pdata.get("coins", 0)

            from bot.data.equipment import STAR_LABELS as SKILL_STAR_LABELS
            embed = discord.Embed(title="🔥 KHO KỸ NĂNG", color=0xff6600,
                                  description=f"💰 **{coins} coins** | {prefix}buyskill <số> | {prefix}equipskill <loại> <số>")
            cat = "attack"
            skills = [(sid2, s) for sid2, s in SKILLS_DB.items() if s["category"] == cat]
            lines = []
            for sid2, sk in skills:
                stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
                is_o = sid2 in owned
                is_e = equipped.get(cat) == sid2
                st = "✅ ĐANG DÙNG" if is_e else ("📦 CÓ" if is_o else f"🪙{sk.get('price', 0)}")
                cd_t = f"CD:`{sk['cooldown']}`" if 'cooldown' in sk else "💎 BỊ ĐỘNG"
                lines.append(f"`{sid2}` {sk['icon']} **{sk['name']}** {stars} | {cd_t} | {st}\n　└ {sk['desc']}")
            embed.description += f"\n\n### {CATEGORY_LABELS[cat]}\n" + "\n".join(lines)

            view = SkillFilterView(cat, owned, equipped, coins, prefix)
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.send(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, discord.ext.commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)

    @commands.command(name="buyskill", aliases=["muakynang"])
    async def buyskill_cmd(self, ctx, skill_id: str = None):
        await self._buyskill(ctx, ctx.author, skill_id, "!")

    async def _buyskill(self, ctx_or_int, user, skill_id, prefix):
        if not skill_id:
            msg = f"❌ {prefix}buyskill <số> để mua! Xem {prefix}skills"
            await self._reply(ctx_or_int, msg)
            return
        try:
            sid = int(skill_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số!")
            return
        if sid not in SKILLS_DB:
            await self._reply(ctx_or_int, f"❌ Không có skill {sid}!")
            return
        sk = SKILLS_DB[sid]
        if sk.get("price", 0) == 0:
            await self._reply(ctx_or_int, "🤷 Skill miễn phí, có sẵn rồi!")
            return
        uid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (uid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            pdata = dict(row)
            owned_list = []
            own_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (uid,))
            async for r in own_cursor:
                owned_list.append(r[0])
            if sid in owned_list:
                await self._reply(ctx_or_int, f"📦 Đã có {sk['name']}!")
                return
            coins = pdata.get("coins", 0)
            if coins < sk["price"]:
                await self._reply(ctx_or_int, f"😅 Nghèo! Cần {sk['price']}🪙, có {coins}🪙")
                return
            await db.execute("UPDATE players SET coins=? WHERE id=?", (coins - sk["price"], uid))
            await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (uid, sid))
            await db.commit()
            stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
            msg = f"✅ Mua **{sk['icon']} {sk['name']}** {stars}!\n💰 Còn {coins - sk['price']}🪙 | {prefix}equipskill {sk['category']} {sid}"
            await self._reply(ctx_or_int, msg)
        finally:
            await db.close()

    @commands.command(name="equipskill", aliases=["trangbikynang"])
    async def equipskill_cmd(self, ctx, category: str = None, skill_id: str = None):
        await self._equipskill(ctx, ctx.author, category, skill_id, "!")

    async def _equipskill(self, ctx_or_int, user, category, skill_id, prefix):
        cats = ["attack", "special", "defense", "passive"]
        if not category or category not in cats:
            msg = f"❌ Dùng: {prefix}equipskill <loại> <số>\nLoại: attack / special / defense / passive"
            await self._reply(ctx_or_int, msg)
            return
        if not skill_id:
            uid = str(user.id)
            db = await get_db()
            try:
                cursor = await db.execute("SELECT skill_id FROM player_skill_slots WHERE player_id=? AND slot=?", (uid, category))
                row = await cursor.fetchone()
                sid = row[0] if row else 1
                sk = SKILLS_DB.get(sid, SKILLS_DB[1])
                msg = f"🔥 {CATEGORY_LABELS[category]}: **{sk['icon']} {sk['name']}**\n{prefix}equipskill {category} <số>"
                await self._reply(ctx_or_int, msg)
            finally:
                await db.close()
            return
        try:
            sid = int(skill_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số!")
            return
        if sid not in SKILLS_DB:
            await self._reply(ctx_or_int, f"❌ Không có skill {sid}!")
            return
        sk = SKILLS_DB[sid]
        if sk["category"] != category:
            await self._reply(ctx_or_int, f"❌ Skill {sid} thuộc loại **{CATEGORY_LABELS[sk['category']]}**, không phải {CATEGORY_LABELS[category]}!")
            return
        uid = str(user.id)
        db = await get_db()
        try:
            own_cursor = await db.execute("SELECT 1 FROM player_skills WHERE player_id=? AND skill_id=?", (uid, sid))
            if not await own_cursor.fetchone():
                await self._reply(ctx_or_int, f"❌ Chưa mua! {prefix}buyskill {sid} ({sk.get('price', 0)}🪙)")
                return
            await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)",
                              (uid, category, sid))
            await db.commit()
            await update_combat_power(uid)
            msg = f"✅ {CATEGORY_LABELS[category]}: **{sk['icon']} {sk['name']}**! 💪"
            await self._reply(ctx_or_int, msg)
        finally:
            await db.close()

    @commands.command(name="leaderboard", aliases=["bxh"])
    async def leaderboard(self, ctx):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players ORDER BY combat_power DESC LIMIT 10")
            players = [dict(r) async for r in cursor]
            view = LeaderboardView(players, initial_tab=1)
            await ctx.send(embed=view.embed, view=view)
        finally:
            await db.close()

    @commands.command(name="class", aliases=["classs"])
    async def class_cmd(self, ctx, class_id: str = None):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await ctx.reply("🤷 Chưa đăng ký!")
                return
            pdata = dict(row)
            current = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])

            if not class_id:
                embed = discord.Embed(title="🎭 Class", color=0xffaa00,
                                      description=f"**Hiện tại**: {current['icon']} {current['name']}\n{current['desc']}\n💰 Coins: {pdata.get('coins', 0)}")
                for cid, cls in CLASSES.items():
                    price_str = "👑 Admin" if cls.get("admin_only") else (f"🪙{cls['price']}" if cls['price'] > 0 else "✅ Free")
                    perk_str = ""
                    if cls.get("perk"):
                        perk_str = f"\n　└ {PERK_DESCRIPTIONS.get(cls['perk'], '')}"
                    emoji = "👉" if cid == pdata.get("class_id", "banxabong") else "  "
                    embed.add_field(name=f"{emoji} {cls['icon']} {cls['name']} {price_str}",
                                    value=f"{cls['desc']}{perk_str}", inline=False)
                await ctx.send(embed=embed)
                return

            if class_id not in CLASSES:
                await ctx.reply("❌ Không có class này!")
                return
            new_cls = CLASSES[class_id]
            if new_cls.get("admin_only"):
                await ctx.reply("👑 Class này chỉ dành cho admin!")
                return
            if class_id == pdata.get("class_id", "banxabong"):
                await ctx.reply("🤷 Đang xài class này rồi!")
                return
            price = new_cls.get("price", 0)
            coins = pdata.get("coins", 0)
            if price > 0 and coins < price:
                await ctx.reply(f"😅 Cần {price}🪙, có {coins}🪙")
                return

            await db.execute("UPDATE players SET coins=?, class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?",
                              (coins - price if price > 0 else coins,
                               class_id,
                               new_cls["hp_base"], new_cls["hp_base"],
                               new_cls["atk_base"], new_cls["atk_base"] + 5,
                               new_cls["def_base"], sid))
            for sk_id in DEFAULT_SKILLS.get(class_id, [1, 5, 10, 14]):
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS.get(class_id, {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await db.commit()
            await update_combat_power(sid)
            await ctx.reply(f"✅ **Chuyển class thành công!** {new_cls['icon']} {new_cls['name']}")
        finally:
            await db.close()

    @commands.command(name="replay")
    async def replay(self, ctx, battle_id: str = None):
        if not battle_id:
            await ctx.reply("❌ !replay <id>")
            return
        try:
            bid = int(battle_id.strip())
        except:
            await ctx.reply("❌ Số!")
            return
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM battle_history WHERE id=?", (bid,))
            row = await cursor.fetchone()
            if not row:
                await ctx.reply("📭 Không tìm thấy trận!")
                return
            battle = dict(row)
            rounds = json.loads(battle["rounds"])
            p1n = battle["p1_name"]
            p2n = battle["p2_name"]
            winner = battle["winner_id"]
            lines = [f"🏆 **{p1n}** vs **{p2n}**"]
            for r in rounds[:20]:
                actor = r.get("actor", "?")
                skill = r.get("skill", "?")
                dmg = r.get("damage", 0)
                heal = r.get("heal", 0)
                hp1 = r.get("hp1", "?")
                hp2 = r.get("hp2", "?")
                line = f"`R{r.get('r', '?')}` {actor} dùng {skill}"
                if dmg:
                    line += f" **-{dmg}HP**"
                if heal:
                    line += f" **+{heal}HP**"
                line += f" | {p1n}:{hp1} {p2n}:{hp2}"
                lines.append(line)
            if len(rounds) > 20:
                lines.append(f"... và {len(rounds) - 20} round nữa")
            wn = p1n if winner == battle.get("player1_id") else p2n
            lines.append(f"\n🏆 **{wn}** THẮNG!")
            embed = discord.Embed(title=f"⚔️ REPLAY #{bid}", description="\n".join(lines), color=0xffaa00)
            await ctx.send(embed=embed)
        finally:
            await db.close()

    @app_commands.command(name="trogiup", description="Xem hướng dẫn")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="⚔️ Đấu Trường Ba Que Xỏ Lá", color=0xff6600)
        embed.add_field(name="📝 Cơ Bản", value="/register /stats /upgrade /leaderboard /challenge /class", inline=False)
        embed.add_field(name="🏪 Shop", value="/shop /buy /use /equip /inv", inline=False)
        embed.add_field(name="🔥 KỸ NĂNG", value="/skills /buyskill /equipskill", inline=False)
        embed.add_field(name="🎭 Class", value="/class — Xem/dổi class", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="register", description="Đăng ký tham gia")
    async def slash_register(self, interaction: discord.Interaction):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))
            if await cursor.fetchone():
                await interaction.response.send_message("🤷 Đăng ký rồi! /stats", ephemeral=True)
                return
            cls = CLASSES["banxabong"]
            await db.execute("""INSERT INTO players (id, name, class_id, hp, hp_max, attack_min, attack_max, defense, coins, last_hp_update)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                              (sid, interaction.user.display_name, "banxabong",
                               cls["hp_base"], cls["hp_base"],
                               cls["atk_base"], cls["atk_base"] + 5,
                               cls["def_base"], 0, time.time()))
            for sk_id in DEFAULT_SKILLS["banxabong"]:
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS["banxabong"].items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await self._sync_role_mult(db, interaction.user)
            await db.commit()
            await interaction.response.send_message(f"✅ {interaction.user.display_name} đăng ký!")
        finally:
            await db.close()

    @app_commands.command(name="stats", description="Xem chỉ số")
    @app_commands.describe(member="Ai? (bỏ trống = mình)")
    async def slash_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        sid = str(target.id)
        db = await get_db()
        try:
            await self._sync_role_mult(db, target)
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("🤷 Chưa đăng ký!", ephemeral=True)
                return
            pdata = dict(row)
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    slot = SHOP_ITEMS[eiid]["slot"]
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}
            wife_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
            wives_data = [dict(r) async for r in wife_cursor]
            regen_hp(pdata)
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?", (pdata["hp"], pdata.get("last_hp_update", time.time()), sid))
            await update_combat_power(sid, pdata, wives_data)
            await db.commit()
            view = StatsView(target, pdata, wives_data)
            await interaction.response.send_message(embed=view.embed, view=view)
        finally:
            await db.close()

    @app_commands.command(name="leaderboard", description="BXH")
    async def slash_leaderboard(self, interaction: discord.Interaction):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players ORDER BY combat_power DESC LIMIT 10")
            players = [dict(r) async for r in cursor]
            view = LeaderboardView(players, initial_tab=1)
            await interaction.response.send_message(embed=view.embed, view=view)
        finally:
            await db.close()

    @app_commands.command(name="upgrade", description="Nâng chỉ số")
    @app_commands.choices(stat=[
        app_commands.Choice(name="❤️ HP +10", value="hp"),
        app_commands.Choice(name="⚔️ ATK +2~3", value="atk"),
        app_commands.Choice(name="🛡️ DEF +2", value="def"),
    ])
    async def slash_upgrade(self, interaction: discord.Interaction, stat: str):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("😅 Chưa đăng ký!", ephemeral=True)
                return
            pdata = dict(row)
            sp = pdata.get("stat_points", 0)
            if sp < 1:
                await interaction.response.send_message("😅 Hết điểm! Đánh nhau đi.", ephemeral=True)
                return
            if stat == "hp":
                await db.execute("UPDATE players SET hp_max=hp_max+10, hp=hp+10, upgrade_hp=upgrade_hp+1, stat_points=? WHERE id=?", (sp - 1, sid))
                sn = "❤️ HP"
            elif stat == "atk":
                await db.execute("UPDATE players SET attack_min=attack_min+2, attack_max=attack_max+3, upgrade_atk=upgrade_atk+1, stat_points=? WHERE id=?", (sp - 1, sid))
                sn = "⚔️ ATK"
            else:
                await db.execute("UPDATE players SET defense=defense+2, upgrade_def=upgrade_def+1, stat_points=? WHERE id=?", (sp - 1, sid))
                sn = "🛡️ DEF"
            await db.commit()
            await update_combat_power(sid)
            await interaction.response.send_message(f"⬆️ **{sn}** tăng! Còn {sp - 1} điểm.")
        finally:
            await db.close()

    @app_commands.command(name="challenge", description="Thách đấu")
    @app_commands.describe(member="Ai?")
    async def slash_challenge(self, interaction: discord.Interaction, member: discord.Member):
        if member.id == interaction.user.id:
            await interaction.response.send_message("🤡 Tự thách mình?", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("🤖 Bot sao đấu?", ephemeral=True)
            return
        sid = str(member.id)
        sc = str(interaction.user.id)
        db = await get_db()
        try:
            now = time.time()
            for check_sid, check_name in [(sid, member.display_name), (sc, interaction.user.display_name)]:
                cursor = await db.execute("SELECT role_mult, last_battle_time FROM players WHERE id=?", (check_sid,))
                row = await cursor.fetchone()
                if row and row[0] < 3.0 and row[1] > 0:
                    remaining = BATTLE_COOLDOWN_SECONDS - int(now - row[1])
                    if remaining > 0:
                        mins = remaining // 60
                        secs = remaining % 60
                        await interaction.response.send_message(f"⏳ **{check_name}** hồi chiêu! Còn {mins}p{secs}s nữa.", ephemeral=True)
                        return

            for check_sid, check_name in [(sid, member.display_name), (sc, interaction.user.display_name)]:
                ch_cursor = await db.execute("SELECT 1 FROM challenges WHERE target_id=? OR challenger_id=?", (check_sid, check_sid))
                if await ch_cursor.fetchone():
                    await interaction.response.send_message(f"⚠️ {check_name} đang liên quan lời thách!", ephemeral=True)
                    return
                b_cursor = await db.execute("SELECT 1 FROM active_battles WHERE player1_id=? OR player2_id=?", (check_sid, check_sid))
                if await b_cursor.fetchone():
                    await interaction.response.send_message(f"⚔️ {check_name} đang đánh!", ephemeral=True)
                    return
                hp_cursor = await db.execute("SELECT * FROM players WHERE id=?", (check_sid,))
                hp_row = await hp_cursor.fetchone()
                if not hp_row:
                    await interaction.response.send_message(f"💀 {check_name} chưa đăng ký!", ephemeral=True)
                    return
                pcheck = dict(hp_row)
                regen_hp(pcheck)
                if pcheck["hp"] <= 0:
                    await interaction.response.send_message(f"💀 {check_name} 0 máu!", ephemeral=True)
                    return
                await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?",
                                  (pcheck["hp"], pcheck.get("last_hp_update", time.time()), check_sid))
            await db.execute("INSERT INTO challenges (target_id, challenger_id, channel_id, created_at) VALUES (?, ?, ?, ?)",
                              (sid, sc, str(interaction.channel_id), time.time()))
            await db.commit()
            embed = discord.Embed(title="⚔️ THÁCH ĐẤU!", color=0xff0000,
                                  description=f"**{interaction.user.display_name}** 👊 **{member.display_name}**!\n<@{member.id}> bấm nút! ⏰30s")
            from bot.views.challenge_view import ChallengeView
            view = ChallengeView(self.bot, sid, sc, interaction.user.display_name, member.display_name, interaction.channel_id)
            await interaction.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    @app_commands.command(name="skills", description="🔥 Kho kỹ năng")
    async def slash_skills(self, interaction: discord.Interaction):
        await self._show_skills(interaction, interaction.user, "/")

    @app_commands.command(name="buyskill", description="🛒 Mua kỹ năng")
    @app_commands.describe(skill_id="Số skill")
    async def slash_buyskill(self, interaction: discord.Interaction, skill_id: str):
        await self._buyskill(interaction, interaction.user, skill_id, "/")

    @slash_buyskill.autocomplete("skill_id")
    async def buyskill_autocomplete(self, interaction: discord.Interaction, current: str):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            coins = row[0] if row else 0
            owned_set = set()
            own_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (sid,))
            async for r in own_cursor:
                owned_set.add(r[0])
            choices = []
            for sid2, sk in SKILLS_DB.items():
                if sk.get("price", 0) == 0 or sid2 in owned_set:
                    continue
                if current.lower() in str(sid2) or current.lower() in sk["name"].lower():
                    can = "✅" if coins >= sk["price"] else "❌"
                    choices.append(app_commands.Choice(name=f"({sid2}) {sk['name']} 🪙{sk['price']} {can}"[:100], value=str(sid2)))
            return choices[:25]
        finally:
            await db.close()

    @app_commands.command(name="equipskill", description="🔥 Gán skill vào slot")
    @app_commands.choices(category=[
        app_commands.Choice(name="💥 Tấn Công (nút Xỏ Lá)", value="attack"),
        app_commands.Choice(name="🔥 Đặc Biệt (nút Đặc Biệt)", value="special"),
        app_commands.Choice(name="🛡️ Chống Xỏ Lá (nút Chống Xỏ Lá)", value="defense"),
        app_commands.Choice(name="💎 Bị Động (luôn active)", value="passive"),
    ])
    @app_commands.describe(category="Slot muốn gán", skill_id="Số skill")
    async def slash_equipskill(self, interaction: discord.Interaction, category: str = None, skill_id: str = None):
        await self._equipskill(interaction, interaction.user, category, skill_id, "/")

    @slash_equipskill.autocomplete("skill_id")
    async def equipskill_autocomplete(self, interaction: discord.Interaction, current: str):
        cat = getattr(interaction.namespace, 'category', None)
        if not cat:
            return []
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            own_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (sid,))
            owned = [r[0] async for r in own_cursor]
            eq_cursor = await db.execute("SELECT skill_id FROM player_skill_slots WHERE player_id=? AND slot=?", (sid, cat))
            eq_row = await eq_cursor.fetchone()
            equipped_id = eq_row[0] if eq_row else None
            choices = []
            for sid2 in owned:
                sk = SKILLS_DB.get(sid2)
                if not sk or sk["category"] != cat:
                    continue
                if current.lower() in str(sid2) or current.lower() in sk["name"].lower():
                    s = "✅" if equipped_id == sid2 else "📦"
                    choices.append(app_commands.Choice(name=f"({sid2}) {s} {sk['name']}"[:100], value=str(sid2)))
            return choices[:25]
        finally:
            await db.close()

    @app_commands.command(name="class", description="🎭 Xem/dổi class")
    @app_commands.describe(class_id="Class muốn dổi (bỏ trống để xem)")
    async def slash_class(self, interaction: discord.Interaction, class_id: str = None):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("🤷 Chưa đăng ký!", ephemeral=True)
                return
            pdata = dict(row)
            current = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])

            if not class_id:
                embed = discord.Embed(title="🎭 Class", color=0xffaa00,
                                      description=f"**Hiện tại**: {current['icon']} {current['name']}\n💰 Coins: {pdata.get('coins', 0)}")
                for cid, cls in CLASSES.items():
                    price_str = "👑 Admin" if cls.get("admin_only") else (f"🪙{cls['price']}" if cls['price'] > 0 else "✅ Free")
                    perk_str = ""
                    if cls.get("perk"):
                        perk_str = f"\n　└ {PERK_DESCRIPTIONS.get(cls['perk'], '')}"
                    emoji = "👉" if cid == pdata.get("class_id", "banxabong") else "  "
                    embed.add_field(name=f"{emoji} {cls['icon']} {cls['name']} {price_str}", value=f"{cls['desc']}{perk_str}", inline=False)
                await interaction.response.send_message(embed=embed)
                return

            if class_id not in CLASSES:
                await interaction.response.send_message("❌ Không có class này!", ephemeral=True)
                return
            new_cls = CLASSES[class_id]
            if new_cls.get("admin_only"):
                await interaction.response.send_message("👑 Class này chỉ dành cho admin!", ephemeral=True)
                return
            if class_id == pdata.get("class_id", "banxabong"):
                await interaction.response.send_message("🤷 Đang xài class này rồi!", ephemeral=True)
                return
            price = new_cls.get("price", 0)
            coins = pdata.get("coins", 0)
            if price > 0 and coins < price:
                await interaction.response.send_message(f"😅 Cần {price}🪙, có {coins}🪙", ephemeral=True)
                return
            await db.execute("UPDATE players SET coins=?, class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?",
                              (coins - price if price > 0 else coins, class_id,
                               new_cls["hp_base"], new_cls["hp_base"],
                               new_cls["atk_base"], new_cls["atk_base"] + 5,
                               new_cls["def_base"], sid))
            for sk_id in DEFAULT_SKILLS.get(class_id, [1, 5, 10, 14]):
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS.get(class_id, {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await db.commit()
            await interaction.response.send_message(f"✅ **Chuyển class thành công!** {new_cls['icon']} {new_cls['name']}")
        finally:
            await db.close()

    @slash_class.autocomplete("class_id")
    async def class_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        for cid, cls in CLASSES.items():
            if cls.get("admin_only"):
                continue
            if current.lower() in cid or current.lower() in cls["name"].lower():
                choices.append(app_commands.Choice(name=f"{cls['icon']} {cls['name']} 🪙{cls['price']}"[:100], value=cid))
        return choices[:25]

    @app_commands.command(name="replay", description="Xem lại trận đấu")
    @app_commands.describe(battle_id="ID trận đấu")
    async def slash_replay(self, interaction: discord.Interaction, battle_id: str):
        try:
            bid = int(battle_id.strip())
        except:
            await interaction.response.send_message("❌ Số!", ephemeral=True)
            return
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM battle_history WHERE id=?", (bid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("📭 Không tìm thấy trận!", ephemeral=True)
                return
            battle = dict(row)
            rounds = json.loads(battle["rounds"])
            p1n = battle["p1_name"]
            p2n = battle["p2_name"]
            winner = battle["winner_id"]
            lines = [f"🏆 **{p1n}** vs **{p2n}**"]
            for r in rounds[:20]:
                actor = r.get("actor", "?")
                skill = r.get("skill", "?")
                dmg = r.get("damage", 0)
                heal = r.get("heal", 0)
                hp1 = r.get("hp1", "?")
                hp2 = r.get("hp2", "?")
                line = f"`R{r.get('r', '?')}` {actor} dùng {skill}"
                if dmg:
                    line += f" **-{dmg}HP**"
                if heal:
                    line += f" **+{heal}HP**"
                line += f" | {p1n}:{hp1} {p2n}:{hp2}"
                lines.append(line)
            if len(rounds) > 20:
                lines.append(f"... và {len(rounds) - 20} round nữa")
            wn = p1n if winner == battle.get("player1_id") else p2n
            lines.append(f"\n🏆 **{wn}** THẮNG!")
            embed = discord.Embed(title=f"⚔️ REPLAY #{bid}", description="\n".join(lines), color=0xffaa00)
            await interaction.response.send_message(embed=embed)
        finally:
            await db.close()

    @slash_replay.autocomplete("battle_id")
    async def replay_autocomplete(self, interaction: discord.Interaction, current: str):
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id FROM battle_history WHERE player1_id=? OR player2_id=? ORDER BY id DESC LIMIT 10",
                (sid, sid))
            ids = [r[0] async for r in cursor]
            choices = []
            for bid in ids:
                if current.lower() in str(bid):
                    choices.append(app_commands.Choice(name=f"Trận #{bid}", value=str(bid)))
            return choices[:25]
        finally:
            await db.close()

    async def _get_player_data(self, db, pid: str) -> dict:
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (pid,))
        row = await cursor.fetchone()
        if not row:
            return {}
        return dict(row)

    async def _load_full_player(self, db, pid: str) -> dict:
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (pid,))
        row = await cursor.fetchone()
        if not row:
            return {}
        pdata = dict(row)
        regen_hp(pdata)
        slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (pid,))
        slots = {}
        async for srow in slots_cursor:
            slots[srow[0]] = srow[1]
        pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
        eq_cursor = await db.execute(
            "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (pid,))
        equipped = {}
        equip_items = {}
        equip_enhances = {}
        async for erow in eq_cursor:
            eq_id = erow[0]
            eiid = erow[1]
            enh = erow[2]
            slot = None
            if eiid in EQUIPMENT:
                slot = EQUIPMENT[eiid]["slot"]
            elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                slot = SHOP_ITEMS[eiid]["slot"]
            if slot:
                equipped[slot] = eq_id
                equip_items[str(eq_id)] = eiid
                equip_enhances[str(eq_id)] = enh
        pdata["equipped"] = equipped
        pdata["_equip_items"] = equip_items
        pdata["_equip_enhances"] = equip_enhances
        buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (pid,))
        buff_row = await buff_cursor.fetchone()
        pdata["buffs"] = dict(buff_row) if buff_row else {}
        return pdata

    async def _save_player_data(self, db, pid: str, pdata: dict):
        await db.execute("""UPDATE players SET hp=?, hp_max=?, attack_min=?, attack_max=?, defense=?,
                             wins=?, losses=?, damage_dealt=?, damage_taken=?, coins=?, xp=?, level=?,
                             stat_points=?, elo=?, attack_cd=?, special_cd=?, defense_cd=?, last_hp_update=?
                             WHERE id=?""",
                          (pdata.get("hp", 100), pdata.get("hp_max", 100),
                           pdata.get("attack_min", 10), pdata.get("attack_max", 20),
                           pdata.get("defense", 5),
                           pdata.get("wins", 0), pdata.get("losses", 0),
                           pdata.get("damage_dealt", 0), pdata.get("damage_taken", 0),
                           pdata.get("coins", 0), pdata.get("xp", 0), pdata.get("level", 1),
                           pdata.get("stat_points", 0), pdata.get("elo", 1000),
                           pdata.get("attack_cd", 0), pdata.get("special_cd", 0),
                           pdata.get("defense_cd", 0),
                           pdata.get("last_hp_update", time.time()),
                           pid))

    async def _sync_role_mult(self, db, member: discord.Member):
        role_names = [r.name for r in member.roles]
        mult = 1.0
        for rn, rm in ROLE_MULTIPLIERS.items():
            if rn in role_names:
                mult = max(mult, rm)
        sid = str(member.id)
        await db.execute("UPDATE players SET role_mult=? WHERE id=?", (mult, sid))
        if mult >= 3.0:
            cursor = await db.execute("SELECT class_id FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if row and row[0] != "trumcuoi":
                cls = CLASSES["trumcuoi"]
                await db.execute("""UPDATE players SET class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?""",
                                  ("trumcuoi", cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], sid))
                await db.execute("DELETE FROM player_skills WHERE player_id=?", (sid,))
                await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (sid,))
                for sk_id in DEFAULT_SKILLS["trumcuoi"]:
                    await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
                for slot, sk_id in DEFAULT_SKILL_SLOTS["trumcuoi"].items():
                    await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
        elif mult < 3.0:
            cursor = await db.execute("SELECT class_id FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if row and row[0] == "trumcuoi":
                cls = CLASSES["banxabong"]
                await db.execute("""UPDATE players SET class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?""",
                                  ("banxabong", cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], sid))
                await db.execute("DELETE FROM player_skills WHERE player_id=?", (sid,))
                await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (sid,))
                for sk_id in DEFAULT_SKILLS["banxabong"]:
                    await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
                for slot, sk_id in DEFAULT_SKILL_SLOTS["banxabong"].items():
                    await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))


class SkillFilterView(discord.ui.View):
    def __init__(self, cat: str, owned: list, equipped: dict, coins: int, prefix: str):
        super().__init__(timeout=120)
        self.cat = cat
        self.owned = owned
        self.equipped = equipped
        self.coins = coins
        self.prefix = prefix
        self._update()

    def _update(self):
        self.clear_items()
        cats = [("attack", "Xo La"), ("special", "Dac Biet"), ("defense", "Phong Thu"), ("passive", "Bi Dong")]
        for cv, cl in cats:
            style = discord.ButtonStyle.primary if cv == self.cat else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=cl, style=style, custom_id=f"skill_{cv}", row=0)
            btn.callback = self._make_cb(cv)
            self.add_item(btn)

    def _make_cb(self, cat: str):
        async def cb(interaction: discord.Interaction):
            self.cat = cat
            embed = discord.Embed(title="KHO KY NANG", color=0xff6600,
                                  description=f"{self.coins} coins | {self.prefix}buyskill | {self.prefix}equipskill")
            skills = [(sid2, s) for sid2, s in SKILLS_DB.items() if s["category"] == cat]
            lines = []
            for sid2, sk in skills:
                stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
                is_o = sid2 in self.owned
                is_e = self.equipped.get(cat) == sid2
                st = "DANG DUNG" if is_e else ("CO" if is_o else f"{sk.get('price', 0)} coin")
                cd_t = f"CD:{sk['cooldown']}" if 'cooldown' in sk else "BI DONG"
                lines.append(f"`{sid2}` {sk['icon']} {sk['name']} {stars} | {cd_t} | {st}")
                lines.append(f"  {sk['desc']}")
            embed.description += f"\n\n### {CATEGORY_LABELS[cat]}\n" + "\n".join(lines)
            self._update()
            await interaction.response.edit_message(embed=embed, view=self)
        return cb


async def setup(bot):
    await bot.add_cog(Arena(bot))
