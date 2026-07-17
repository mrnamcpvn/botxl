import discord
import asyncio
import time
import random
import json
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.database import get_db
from bot.data.skills import SKILLS_DB
from bot.data.wives import WIVES, WIFE_XP_SHARE
from bot.engine.battle import execute_action, get_equipped_skill, regen_hp, get_effective_stats
from bot.engine.rewards import calc_rewards, apply_rewards, calc_drop, apply_drop
from bot.engine.ranking import calculate_elo
from bot.engine.combat_power import update_combat_power

RARITY_DMG_MULT = {"B": 0.5, "A": 0.75, "S": 1.0, "SVIP": 1.5}


class BattleView(discord.ui.View):
    def __init__(self, bot, battle_id: int, turn_sid: str, turn_name: str, skill_labels: dict = None, seconds: int = 15):
        super().__init__(timeout=None)
        self.bot = bot
        self.battle_id = battle_id
        self.turn_sid = turn_sid
        self.turn_name = turn_name
        self.seconds = seconds
        self.remaining = seconds
        self._timer_task = None
        self._stopped = False
        self.message = None

        labels = skill_labels or {}
        atk = labels.get("attack", {"icon": "💥", "name": "Tấn Công"})
        spc = labels.get("special", {"icon": "🔥", "name": "Đặc Biệt"})
        dfs = labels.get("defense", {"icon": "🛡️", "name": "Chống Xỏ Lá"})

        btn_atk = discord.ui.Button(emoji=atk["icon"], label=atk["name"], style=discord.ButtonStyle.danger, custom_id="battle_attack", row=0)
        btn_atk.callback = self._make_callback("attack")
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(emoji=spc["icon"], label=spc["name"], style=discord.ButtonStyle.primary, custom_id="battle_special", row=0)
        btn_spc.callback = self._make_callback("special")
        self.add_item(btn_spc)

        btn_def = discord.ui.Button(emoji=dfs["icon"], label=dfs["name"], style=discord.ButtonStyle.success, custom_id="battle_defense", row=0)
        btn_def.callback = self._make_callback("defense")
        self.add_item(btn_def)

    def _make_callback(self, move_type: str):
        async def callback(interaction: discord.Interaction):
            await self._handle_move(interaction, move_type)
        return callback

    def start_countdown(self):
        if self._timer_task is None:
            self._timer_task = asyncio.create_task(self._run_countdown())

    def stop(self):
        self._stopped = True
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        super().stop()

    async def _run_countdown(self):
        for remaining in range(self.seconds, -1, -1):
            if self._stopped:
                return
            self.remaining = remaining
            if self.message and not self._stopped:
                try:
                    embed = self.message.embeds[0] if self.message.embeds else None
                    if embed:
                        bar_filled = remaining * 10 // self.seconds
                        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
                        if remaining > 5:
                            footer = f"⏳ {remaining}s — {bar} — {self.turn_name}"
                        elif remaining > 0:
                            footer = f"⚠️ {remaining}s! {bar} — Nhanh lên!"
                        else:
                            footer = "⏰ HẾT GIỜ!"
                        embed.set_footer(text=footer)
                        await self.message.edit(embed=embed)
                except:
                    pass
            if remaining > 0:
                await asyncio.sleep(1)
            else:
                break
        if not self._stopped:
            self._stopped = True
            await self._handle_timeout()

    async def _handle_timeout(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE id=?", (self.battle_id,))
            battle = await cursor.fetchone()
            if not battle:
                return
            battle = dict(battle)
            if battle["turn"] != self.turn_sid:
                return
            await self._finish_battle(db, battle, self.turn_sid, is_timeout=True)
        finally:
            await db.close()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.turn_sid:
            await interaction.response.send_message("⏳ Chưa tới lượt mày! 🤡", ephemeral=True)
            return False
        return True

    async def _handle_move(self, interaction: discord.Interaction, move_type: str):
        await interaction.response.defer()
        guild = interaction.guild
        user_id = interaction.user.id
        sid = str(user_id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE id=?", (self.battle_id,))
            battle = await cursor.fetchone()
            if not battle:
                await interaction.followup.send("🤷 Không có trận nào!", ephemeral=True)
                return
            battle = dict(battle)
            if battle["turn"] != sid:
                await interaction.followup.send("⏳ Chưa tới lượt!", ephemeral=True)
                return

            cat = "defense" if move_type == "defense" else move_type
            pdata = await self._get_player_data(db, sid)
            cd_key = f"{cat}_cd"
            if pdata.get(cd_key, 0) > 0:
                sk = get_equipped_skill(pdata, cat)
                await interaction.followup.send(
                    f"⏳ **{sk['name']}** đang hồi! Còn **{pdata[cd_key]}** turn!", ephemeral=True)
                return

            is_p1 = sid == battle["player1_id"]
            stunned = bool(battle.get("p1_stunned", 0)) if is_p1 else bool(battle.get("p2_stunned", 0))
            if stunned:
                self.stop()
                await self._handle_stunned_turn(db, battle, guild, sid, pdata, interaction)
                return

            self.stop()
            await self._execute_battle_turn(db, battle, guild, sid, move_type, interaction)
        finally:
            await db.close()

    async def _handle_stunned_turn(self, db, battle, guild, sid, pdata, interaction):
        is_p1 = sid == battle["player1_id"]
        result_lines = []
        p1_id = battle["player1_id"]
        p2_id = battle["player2_id"]

        p1_m = guild.get_member(int(p1_id)) or await guild.fetch_member(int(p1_id))
        p2_m = guild.get_member(int(p2_id)) or await guild.fetch_member(int(p2_id))
        an = p1_m.display_name if is_p1 else p2_m.display_name
        sd = pdata

        result_lines.append(f"🌑 **{an}** bị choáng, mất lượt!")

        # Reduce cooldowns
        for pid in [p1_id, p2_id]:
            pdat = await self._get_player_data(db, pid)
            for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                if pdat.get(cdkey, 0) > 0:
                    pdat[cdkey] -= 1
            await self._save_player_data(db, pid, pdat)

        # Burn tick
        import json
        bs_cursor = await db.execute("SELECT key, value FROM battle_status WHERE battle_id=?",
                                      (self.battle_id,))
        burn_key = "p1_burn" if is_p1 else "p2_burn"
        burn_data = None
        async for bs_row in bs_cursor:
            k = bs_row[0]
            if k == burn_key:
                burn_data = json.loads(bs_row[1])

        if burn_data and burn_data.get("turns", 0) > 0:
            bd = int(sd.get("hp_max", 100) * burn_data["pct"] / 100)
            sd["hp"] = max(0, sd.get("hp", 0) - bd)
            burn_data["turns"] -= 1
            result_lines.append(f"🔥 Bỏng -{bd}HP ({burn_data['turns']}t)")
            if burn_data["turns"] <= 0:
                await db.execute("DELETE FROM battle_status WHERE battle_id=? AND key=?",
                                  (self.battle_id, burn_key))
            else:
                await db.execute("UPDATE battle_status SET value=? WHERE battle_id=? AND key=?",
                                  (json.dumps(burn_data), self.battle_id, burn_key))

        await self._save_player_data(db, sid, sd)

        # Clear stun
        if is_p1:
            await db.execute("UPDATE active_battles SET p1_stunned=0 WHERE id=?", (self.battle_id,))
        else:
            await db.execute("UPDATE active_battles SET p2_stunned=0 WHERE id=?", (self.battle_id,))

        # Check defeat
        if sd.get("hp", 0) <= 0:
            sd["hp"] = 0
            winner_id = p2_id if is_p1 else p1_id
            wdata = await self._get_player_data(db, winner_id)
            wdata["wins"] = wdata.get("wins", 0) + 1
            sd["losses"] = sd.get("losses", 0) + 1
            await self._save_player_data(db, winner_id, wdata)
            await self._save_player_data(db, sid, sd)

            # Rewards + ELO
            w_coins, w_xp = calc_rewards(True, wdata.get("level", 1), sd.get("level", 1))
            l_coins, l_xp = calc_rewards(False)
            apply_rewards(wdata, w_coins, w_xp)
            apply_rewards(sd, l_coins, l_xp)
            p1_battles = wdata.get("wins", 0) + wdata.get("losses", 0)
            w_elo, l_elo = calculate_elo(wdata.get("elo", 1000), sd.get("elo", 1000), 1, p1_battles)
            wdata["elo"] = w_elo
            sd["elo"] = l_elo
            await self._save_player_data(db, winner_id, wdata)
            await self._save_player_data(db, sid, sd)
            await db.execute("UPDATE players SET last_battle_time=? WHERE id=? OR id=?", (time.time(), winner_id, sid))
            await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
            await db.commit()
            await update_combat_power(winner_id)
            await update_combat_power(sid)

            wn = p1_m.display_name if winner_id == p1_id else p2_m.display_name
            embed = discord.Embed(title="⚔️ KẾT THÚC!",
                                  description=f"🌑 {an} choáng+chết!\n🏆 {wn} thắng!\n💰 {wn}: +{w_coins}🪙 +{w_xp}XP",
                                  color=0xffd700)
            await interaction.edit_original_response(embed=embed, view=None)
            return

        # Switch turn
        new_turn = p2_id if is_p1 else p1_id
        await db.execute("UPDATE active_battles SET turn=?, last_move=? WHERE id=?",
                          (new_turn, time.time(), self.battle_id))
        await db.commit()

        next_m = p1_m if new_turn == p1_id else p2_m
        next_pdata = await self._load_full_player(db, new_turn)
        result_lines.append(f"\n⏳ **{next_m.display_name}** — 15s!")
        embed = discord.Embed(title="⚔️ DIỄN BIẾN", description="\n".join(result_lines), color=0x9966ff)
        view = BattleView(self.bot, self.battle_id, new_turn, next_m.display_name, get_skill_labels(next_pdata))
        await interaction.edit_original_response(embed=embed, view=view)
        view.start_countdown()

    async def _execute_battle_turn(self, db, battle, guild, sid, move_type, interaction):
        p1_id = battle["player1_id"]
        p2_id = battle["player2_id"]

        try:
            p1 = await self._load_full_player(db, p1_id)
            p2 = await self._load_full_player(db, p2_id)

            p1_m = guild.get_member(int(p1_id)) or await guild.fetch_member(int(p1_id))
            p2_m = guild.get_member(int(p2_id)) or await guild.fetch_member(int(p2_id))
            if not p1_m or not p2_m:
                await interaction.edit_original_response(content="❌ Mất người chơi!", embed=None, view=None)
                await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
                await db.commit()
                return

            p1["name"] = p1_m.display_name
            p2["name"] = p2_m.display_name

            turn_player = 0 if sid == p1_id else 1
            cat = "defense" if move_type == "defense" else move_type
            skill = get_equipped_skill(p1 if turn_player == 0 else p2, cat)

            flags = {
                "p1_defending": bool(battle.get("p1_defending", 0)),
                "p2_defending": bool(battle.get("p2_defending", 0)),
                "p1_stunned": bool(battle.get("p1_stunned", 0)),
                "p2_stunned": bool(battle.get("p2_stunned", 0)),
                "turn_count": 0,
            }

            bs_cursor = await db.execute("SELECT key, value FROM battle_status WHERE battle_id=?", (self.battle_id,))
            import json
            async for bs_row in bs_cursor:
                flags[bs_row[0]] = json.loads(bs_row[1])

            result = await execute_action(
                p1, p2, turn_player,
                {"type": move_type, "skill_id": skill.get("id", action_skill_id(p1 if turn_player == 0 else p2, move_type))},
                flags
            )

            p1 = result["p1"]
            p2 = result["p2"]

            # --- WIFE ATTACKS ---
            p1_wives_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (p1_id,))
            p1_wives = await p1_wives_cursor.fetchall()
            p2_wives_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (p2_id,))
            p2_wives = await p2_wives_cursor.fetchall()

            if p1_wives:
                result["log_messages"].append("")
                for w in [dict(r) for r in p1_wives]:
                    wd = WIVES.get(w["wife_id"], WIVES[1])
                    mult = RARITY_DMG_MULT.get(wd["rarity"], 0.5)
                    dmg = max(1, int(random.randint(4, 10) * w.get("level", 1) * mult))
                    p2["hp"] = max(0, p2.get("hp", 0) - dmg)
                    result["log_messages"].append(
                        f"💕 {wd['emoji']} **{wd['name']}** ({wd['rarity']} Lv.{w['level']}) → **-{dmg}HP**!")

            if p2_wives:
                result["log_messages"].append("")
                for w in [dict(r) for r in p2_wives]:
                    wd = WIVES.get(w["wife_id"], WIVES[1])
                    mult = RARITY_DMG_MULT.get(wd["rarity"], 0.5)
                    dmg = max(1, int(random.randint(4, 10) * w.get("level", 1) * mult))
                    p1["hp"] = max(0, p1.get("hp", 0) - dmg)
                    result["log_messages"].append(
                        f"💍 {wd['emoji']} **{wd['name']}** ({wd['rarity']} Lv.{w['level']}) → **-{dmg}HP**!")

            # Check if wife attack killed someone
            if p2["hp"] <= 0 and not result["finished"]:
                p2["hp"] = 0
                result["finished"] = True
                result["winner_id"] = p1_id
                result["log_messages"].append(f"\n💕 **{p2['name']}** bị vợ của {p1['name']} hạ gục! 🎉")

            if p1["hp"] <= 0 and not result["finished"]:
                p1["hp"] = 0
                result["finished"] = True
                result["winner_id"] = p2_id
                result["log_messages"].append(f"\n💍 **{p1['name']}** bị vợ của {p2['name']} hạ gục! 🎉")

            await self._save_player_data(db, p1_id, p1)
            await self._save_player_data(db, p2_id, p2)

            if result["finished"]:
                winner_id = result["winner_id"]
                loser_id = p2_id if winner_id == p1_id else p1_id
                winner = p1 if winner_id == p1_id else p2
                loser = p2 if winner_id == p1_id else p1
                w_coins, w_xp = calc_rewards(True, winner.get("level", 1), loser.get("level", 1))
                l_coins, l_xp = calc_rewards(False)
                apply_rewards(winner, w_coins, w_xp)
                apply_rewards(loser, l_coins, l_xp)
                wife_lines = await self._level_wives(db, winner_id, w_xp)
                p1_battles = p1.get("wins", 0) + p1.get("losses", 0)
                new_elo_p1, new_elo_p2 = calculate_elo(
                    p1.get("elo", 1000), p2.get("elo", 1000),
                    1 if winner_id == p1_id else 2, p1_battles)
                p1["elo"] = new_elo_p1
                p2["elo"] = new_elo_p2
                await self._save_player_data(db, p1_id, p1)
                await self._save_player_data(db, p2_id, p2)
                await db.execute("UPDATE players SET last_battle_time=? WHERE id=? OR id=?", (time.time(), p1_id, p2_id))
                await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))

                drop = calc_drop(winner.get("role_mult", 1.0))
                if drop:
                    await apply_drop(db, winner_id, drop)

                await db.execute("UPDATE player_buffs SET lucky=MAX(0, lucky-1) WHERE player_id=? OR player_id=?", (p1_id, p2_id))

                await db.commit()
                await update_combat_power(p1_id)
                await update_combat_power(p2_id)

                lines = result["log_messages"] + [
                    f"💰 {p1_m.display_name if winner_id == p1_id else p2_m.display_name}: +{w_coins}🪙 +{w_xp}XP",
                ]
                if wife_lines:
                    lines.append("")
                    lines.extend(wife_lines)

                if drop:
                    lines.append(f"\n{drop['text']}")
                embed = discord.Embed(title="⚔️ KẾT THÚC!", description="\n".join(lines), color=0xffd700)
                await interaction.edit_original_response(embed=embed, view=None)
                return

            await db.execute("DELETE FROM battle_status WHERE battle_id=?", (self.battle_id,))
            dynamic_keys = {"p1_burn", "p2_burn", "p1_shield_hp", "p2_shield_hp",
                            "p1_shield_pop_heal", "p2_shield_pop_heal",
                            "p1_counter", "p2_counter", "p1_counter_immune", "p2_counter_immune",
                            "p1_rage_dmg", "p2_rage_dmg", "p1_dodge_passive", "p2_dodge_passive", "turn_count"}
            for key, val in flags.items():
                if key in dynamic_keys:
                    pid = p1_id if key.startswith("p1") else (p2_id if key.startswith("p2") else p1_id)
                    await db.execute("INSERT INTO battle_status (battle_id, player_id, key, value) VALUES (?, ?, ?, ?)",
                                      (self.battle_id, pid, key, json.dumps(val)))

            new_turn = p2_id if turn_player == 0 else p1_id
            await db.execute("""UPDATE active_battles SET turn=?, last_move=?,
                                 p1_defending=?, p2_defending=?, p1_stunned=?, p2_stunned=?
                                 WHERE id=?""",
                              (new_turn, time.time(),
                               int(flags.get("p1_defending", 0)), int(flags.get("p2_defending", 0)),
                               int(flags.get("p1_stunned", 0)), int(flags.get("p2_stunned", 0)),
                               self.battle_id))
            await db.commit()

            next_m = p1_m if new_turn == p1_id else p2_m
            next_pdata = p1 if new_turn == p1_id else p2

            eff1 = get_effective_stats(p1)
            eff2 = get_effective_stats(p2)

            ask = get_equipped_skill(next_pdata, "attack")
            ssk = get_equipped_skill(next_pdata, "special")
            dsk = get_equipped_skill(next_pdata, "defense")

            hp1_bar = "🟩" * (min(p1["hp"], 150) // 10) + "⬜" * ((max(eff1["hp_max"], p1["hp"]) - min(p1["hp"], 150)) // 10)
            hp2_bar = "🟩" * (min(p2["hp"], 150) // 10) + "⬜" * ((max(eff2["hp_max"], p2["hp"]) - min(p2["hp"], 150)) // 10)
            if len(hp1_bar) > 15:
                hp1_bar = hp1_bar[:15]
            if len(hp2_bar) > 15:
                hp2_bar = hp2_bar[:15]

            result["log_messages"].append("\n━━━━━━━━━━━")
            result["log_messages"].append(f"❤️ {p1_m.display_name}:`{p1['hp']}/{eff1['hp_max']}`{hp1_bar}")
            result["log_messages"].append(f"❤️ {p2_m.display_name}:`{p2['hp']}/{eff2['hp_max']}`{hp2_bar}")

            for pd, pn in [(p1, p1_m.display_name), (p2, p2_m.display_name)]:
                cds = []
                for cat2 in ["attack", "special", "defense"]:
                    sk = get_equipped_skill(pd, cat2)
                    cd = pd.get(f"{cat2}_cd", 0)
                    icon = sk.get("icon", "❓")
                    cds.append(f"{icon}{'✅' if cd <= 0 else f'⏳{cd}'}")
                result["log_messages"].append(f"  {pn}: {' '.join(cds)}")

            result["log_messages"].append(f"\n⏳ **{next_m.display_name}** — 15s!")

            # --- Wife display ---
            p1_wives_cursor = await db.execute("SELECT pw.* FROM player_wives pw WHERE pw.player_id=? AND pw.equipped=1", (p1_id,))
            p1_wives = await p1_wives_cursor.fetchall()
            p2_wives_cursor = await db.execute("SELECT pw.* FROM player_wives pw WHERE pw.player_id=? AND pw.equipped=1", (p2_id,))
            p2_wives = await p2_wives_cursor.fetchall()
            if p1_wives:
                wlist = []
                for r in p1_wives:
                    w = dict(r)
                    wd = WIVES.get(w["wife_id"], WIVES[1])
                    wlist.append(f"{wd['emoji']} **{wd['name']}** Lv.{w['level']}")
                result["log_messages"].append(f"💍 {p1_m.display_name}: {' | '.join(wlist)}")
            if p2_wives:
                wlist = []
                for r in p2_wives:
                    w = dict(r)
                    wd = WIVES.get(w["wife_id"], WIVES[1])
                    wlist.append(f"{wd['emoji']} **{wd['name']}** Lv.{w['level']}")
                result["log_messages"].append(f"💍 {p2_m.display_name}: {' | '.join(wlist)}")

            embed = discord.Embed(title="⚔️ DIỄN BIẾN", description="\n".join(result["log_messages"]), color=0x00ff00)
            view = BattleView(self.bot, self.battle_id, new_turn, next_m.display_name, get_skill_labels(next_pdata))
            await interaction.edit_original_response(embed=embed, view=view)
            view.start_countdown()
        except Exception as e:
            await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
            await db.execute("DELETE FROM battle_status WHERE battle_id=?", (self.battle_id,))
            await db.commit()
            try:
                await interaction.edit_original_response(content=f"❌ Lỗi battle! Đã hủy.\n`{e}`", embed=None, view=None)
            except:
                pass

    async def _load_full_player(self, db, pid: str) -> dict:
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (pid,))
        row = await cursor.fetchone()
        if not row:
            return {}
        pdata = dict(row)
        regen_hp(pdata)
        # Skills
        slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (pid,))
        slots = {}
        async for srow in slots_cursor:
            slots[srow[0]] = srow[1]
        pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
        # Equipment
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
        # Buffs
        buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (pid,))
        buff_row = await buff_cursor.fetchone()
        pdata["buffs"] = dict(buff_row) if buff_row else {}
        return pdata

    async def _get_player_data(self, db, pid: str) -> dict:
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (pid,))
        row = await cursor.fetchone()
        if not row:
            return {}
        pdata = dict(row)
        regen_hp(pdata)
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
        await db.commit()

    async def _level_wives(self, db, player_id: str, battle_xp: int) -> list[str]:
        gained = max(1, int(battle_xp * WIFE_XP_SHARE))
        lines = []
        if gained <= 0:
            return lines
        cursor = await db.execute(
            "SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (player_id,))
        async for row in cursor:
            w = dict(row)
            wd = WIVES.get(w["wife_id"], WIVES[1])
            new_xp = w["xp"] + gained
            new_level = w["level"]
            leftover = new_xp
            while leftover >= new_level * 50:
                leftover -= new_level * 50
                new_level += 1
            await db.execute("UPDATE player_wives SET xp=?, level=? WHERE id=?",
                              (leftover, new_level, w["id"]))
            lvl_up = f" ⬆Lv.{new_level}!" if new_level > w["level"] else ""
            lines.append(f"💕 {wd['emoji']} **{wd['name']}**: +{gained}XP{lvl_up}")
        return lines

    async def _finish_battle(self, db, battle, loser_sid: str, is_timeout: bool = False):
        winner_id = battle["player1_id"] if battle["player2_id"] == loser_sid else battle["player2_id"]
        guild = self.message.guild if self.message else self.bot.get_guild(int(battle.get("channel_id", "0")))
        if not guild:
            ch = self.bot.get_channel(int(battle.get("channel_id", "0")))
            guild = ch.guild if ch else None
        if not guild:
            await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
            await db.commit()
            return

        loser_m = guild.get_member(int(loser_sid)) or await guild.fetch_member(int(loser_sid))
        winner_m = guild.get_member(int(winner_id)) or await guild.fetch_member(int(winner_id))
        loser_name = loser_m.display_name if loser_m else "???"
        winner_name = winner_m.display_name if winner_m else "???"

        wdata = await self._get_player_data(db, winner_id)
        ldata = await self._get_player_data(db, loser_sid)
        wdata["wins"] = wdata.get("wins", 0) + 1
        ldata["losses"] = ldata.get("losses", 0) + 1
        if is_timeout:
            ldata["hp"] = 0

        w_coins, w_xp = calc_rewards(True, wdata.get("level", 1), ldata.get("level", 1))
        l_coins, l_xp = calc_rewards(False)
        apply_rewards(wdata, w_coins, w_xp)
        apply_rewards(ldata, l_coins, l_xp)
        wife_lines = await self._level_wives(db, winner_id, w_xp)
        p1_battles = wdata.get("wins", 0) + wdata.get("losses", 0)
        w_elo, l_elo = calculate_elo(
            wdata.get("elo", 1000), ldata.get("elo", 1000),
            1, p1_battles)
        wdata["elo"] = w_elo
        ldata["elo"] = l_elo

        await self._save_player_data(db, winner_id, wdata)
        await self._save_player_data(db, loser_sid, ldata)
        await db.execute("UPDATE players SET last_battle_time=? WHERE id=? OR id=?", (time.time(), winner_id, loser_sid))
        await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))

        drop = calc_drop(wdata.get("role_mult", 1.0))
        if drop:
            await apply_drop(db, winner_id, drop)

        await db.execute("UPDATE player_buffs SET lucky=MAX(0, lucky-1) WHERE player_id=? OR player_id=?", (winner_id, loser_sid))

        await db.commit()
        await update_combat_power(winner_id)
        await update_combat_power(loser_sid)

        lines = [
            f"⏰ **{loser_name}** hết giờ!" if is_timeout else f"💀 **{loser_name}** thua!",
            f"🏆 **{winner_name}** CHIẾN THẮNG! 🎉",
            f"💰 {winner_name}: +{w_coins}🪙 +{w_xp}XP",
        ]
        if wife_lines:
            lines.append("")
            lines.extend(wife_lines)

        if drop:
            lines.append(f"\n{drop['text']}")

        embed = discord.Embed(title="⚔️ KẾT THÚC", description="\n".join(lines), color=0xffd700)
        try:
            await self.message.edit(embed=embed, view=None)
        except:
            ch = self.bot.get_channel(int(battle["channel_id"]))
            if ch:
                await ch.send(embed=embed)


def action_skill_id(pdata: dict, move_type: str) -> int:
    """Helper to get the equipped skill ID for a given move type."""
    cat = "defense" if move_type == "defense" else move_type
    sk = get_equipped_skill(pdata, cat)
    for sid, s in SKILLS_DB.items():
        if s["name"] == sk["name"]:
            return sid
    return 1


def get_skill_labels(pdata: dict) -> dict:
    result = {}
    for cat in ["attack", "special", "defense"]:
        sk = get_equipped_skill(pdata, cat)
        result[cat] = {"icon": sk.get("icon", "?"), "name": sk.get("name", cat)}
    return result
