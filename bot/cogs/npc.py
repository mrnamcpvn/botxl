import discord
from discord import app_commands
from discord.ext import commands
import random
import time
import copy
from bot.database import get_db
from bot.data.npcs import NPC_DEFINITIONS
from bot.data.classes import CLASSES
from bot.data.skills import SKILLS_DB
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.engine.battle import execute_action, get_equipped_skill, regen_hp, get_effective_stats
from bot.engine.rewards import calc_rewards, apply_rewards, calc_drop, apply_drop
from bot.engine.ranking import calculate_elo
from bot.config import BATTLE_COOLDOWN_SECONDS
from bot.data.wives import WIVES, WIFE_XP_SHARE
from bot.engine.combat_power import update_combat_power

RARITY_DMG_MULT = {"B": 0.5, "A": 0.75, "S": 1.0, "SVIP": 1.5}


class NPCBattleView(discord.ui.View):
    def __init__(self, cog, player_id: str, npc_id: str, player_pdata: dict, npc_pdata: dict,
                 npc_name: str, player_name: str, first_is_player: bool):
        super().__init__(timeout=None)
        self.cog = cog
        self.player_id = player_id
        self.npc_id = npc_id
        self.player_pdata = player_pdata
        self.npc_pdata = npc_pdata
        self.npc_name = npc_name
        self.player_name = player_name
        self.first_is_player = first_is_player
        self.turn_count = 0
        self.finished = False

        pdata = player_pdata
        atk = get_equipped_skill(pdata, "attack")
        spc = get_equipped_skill(pdata, "special")
        dfs = get_equipped_skill(pdata, "defense")

        btn_basic = discord.ui.Button(
            emoji="👊", label="Cú Đấm Ba Que",
            style=discord.ButtonStyle.secondary, custom_id="npc_basic", row=0)
        btn_basic.callback = self._make_callback("basic")
        self.add_item(btn_basic)

        btn_atk = discord.ui.Button(
            emoji=atk.get("icon", "💥"), label=atk.get("name", "Tấn Công")[:80],
            style=discord.ButtonStyle.danger, custom_id="npc_attack", row=1)
        btn_atk.callback = self._make_callback("attack")
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(
            emoji=spc.get("icon", "🔥"), label=spc.get("name", "Đặc Biệt")[:80],
            style=discord.ButtonStyle.primary, custom_id="npc_special", row=1)
        btn_spc.callback = self._make_callback("special")
        self.add_item(btn_spc)

        btn_def = discord.ui.Button(
            emoji=dfs.get("icon", "🛡️"), label=dfs.get("name", "Chống Xỏ Lá")[:80],
            style=discord.ButtonStyle.success, custom_id="npc_defense", row=1)
        btn_def.callback = self._make_callback("defense")
        self.add_item(btn_def)

    def _make_callback(self, move_type: str):
        async def callback(interaction: discord.Interaction):
            await self.cog._handle_npc_move(interaction, self, move_type)
        return callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True


class NPCCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    def _npc_embed(self, member) -> discord.Embed:
        embed = discord.Embed(title="👾 BẢNG NPC", color=0x9966ff,
                              description="Dùng `!npc <số>` hoặc `/npc challenge <số>` để thách đấu!")
        for nid, npc in NPC_DEFINITIONS.items():
            cls = CLASSES.get(npc["class_id"], CLASSES["banxabong"])
            embed.add_field(
                name=f"`{nid}` {npc['name']} {cls['icon']} Lv.{npc['level']}",
                value=f"❤️ `{npc['hp_max']}` ⚔️ `{npc['attack_min']}-{npc['attack_max']}` 🛡️ `{npc['defense']}`",
                inline=False)
        return embed

    def _npc_ai_move(self, npc: dict) -> str:
        hp_pct = npc["hp"] / max(npc["hp_max"], 1) * 100
        if hp_pct < 30:
            return random.choices(["attack", "special", "defense"], weights=[20, 15, 65])[0]
        elif hp_pct < 60:
            return random.choices(["attack", "special", "defense"], weights=[35, 30, 35])[0]
        else:
            return random.choices(["attack", "special", "defense"], weights=[40, 35, 25])[0]

    @commands.command(name="npc")
    async def npc_cmd(self, ctx, npc_id: str = None):
        if npc_id:
            await self._start_npc_battle(ctx, str(ctx.author.id), npc_id, ctx.author.display_name, "!")
            return
        try:
            embed = self._npc_embed(ctx.author)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.reply(f"❌ Lỗi: {e}")

    @app_commands.command(name="npc", description="📜 Xem danh sách NPC")
    async def slash_npc_list(self, interaction: discord.Interaction):
        embed = self._npc_embed(interaction.user)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="npc_challenge", description="⚔️ Thách đấu NPC")
    @app_commands.describe(npc_id="Số NPC (xem /npc)")
    async def slash_npc_challenge(self, interaction: discord.Interaction, npc_id: str):
        await self._start_npc_battle(interaction, str(interaction.user.id), npc_id,
                                     interaction.user.display_name, "/")

    @slash_npc_challenge.autocomplete("npc_id")
    async def npc_challenge_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        for nid, npc in NPC_DEFINITIONS.items():
            if current.lower() in nid or current.lower() in npc["name"].lower():
                choices.append(app_commands.Choice(name=f"({nid}) {npc['name']}"[:100], value=nid))
        return choices[:25]

    async def _start_npc_battle(self, ctx_or_int, sid: str, npc_id: str, display_name: str, prefix: str):
        if npc_id not in NPC_DEFINITIONS:
            msg = f"❌ Không có NPC này! Xem `{prefix}npc`"
            if isinstance(ctx_or_int, discord.ext.commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        if sid in self.sessions:
            msg = "⚔️ Mày đang đánh NPC rồi!"
            if isinstance(ctx_or_int, discord.ext.commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                msg = f"🤷 Chưa đăng ký! `{prefix}register`"
                if isinstance(ctx_or_int, discord.ext.commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return
            pdata = dict(row)

            battle_check = await db.execute("SELECT 1 FROM active_battles WHERE player1_id=? OR player2_id=?", (sid, sid))
            if await battle_check.fetchone():
                msg = "⚔️ Mày đang đánh PvP rồi!"
                if isinstance(ctx_or_int, discord.ext.commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return
            challenge_check = await db.execute("SELECT 1 FROM challenges WHERE target_id=? OR challenger_id=?", (sid, sid))
            if await challenge_check.fetchone():
                msg = "⚠️ Mày đang có lời thách PvP!"
                if isinstance(ctx_or_int, discord.ext.commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            if pdata.get("role_mult", 1.0) < 3.0 and pdata.get("last_battle_time", 0) > 0:
                remaining = BATTLE_COOLDOWN_SECONDS - int(time.time() - pdata["last_battle_time"])
                if remaining > 0:
                    mins = remaining // 60
                    secs = remaining % 60
                    msg = f"⏳ Hồi chiêu! Còn {mins}p{secs}s nữa."
                    if isinstance(ctx_or_int, discord.ext.commands.Context):
                        await ctx_or_int.reply(msg)
                    else:
                        await ctx_or_int.response.send_message(msg, ephemeral=True)
                    return

            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance, hidden_stats FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            equip_hidden = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
                hidden = r[3] if len(r) > 3 and r[3] else ""
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    slot = SHOP_ITEMS[eiid]["slot"]
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
                    equip_hidden[str(eq_id)] = hidden
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances
            pdata["_equip_hidden"] = equip_hidden
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}
            art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
            art_row = await art_cursor.fetchone()
            pdata["_artifact_star"] = art_row[0] if art_row else 0
            pdata["_artifact_stones"] = art_row[1] if art_row else 0
            pdata["damage_dealt"] = pdata.get("damage_dealt", 0)
            pdata["damage_taken"] = pdata.get("damage_taken", 0)
            pdata["attack_cd"] = 0
            pdata["special_cd"] = 0
            pdata["defense_cd"] = 0
            regen_hp(pdata)

            if pdata.get("hp", 0) <= 0:
                msg = "💀 Mày 0 máu!"
                if isinstance(ctx_or_int, discord.ext.commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            npc_data = copy.deepcopy(NPC_DEFINITIONS[npc_id])
            npc_data["id"] = f"npc_{npc_id}"
            npc_data["name"] = npc_data["name"]
            npc_data["cooldowns"] = {"attack_cd": 0, "special_cd": 0, "defense_cd": 0}

            eff = get_effective_stats(pdata)
            cls_npc = CLASSES.get(npc_data["class_id"], CLASSES["banxabong"])
            cls_player = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])

            embed = discord.Embed(
                title=f"👾 THÁCH NPC: {npc_data['name']}",
                color=0x9966ff,
                description=(
                    f"{cls_player['icon']} **{display_name}** Lv.{pdata.get('level',1)}"
                    f" ⚔️ {cls_npc['icon']} **{npc_data['name']}** Lv.{npc_data['level']}\n"
                    f"━━━━━━━━━━━\n"
                    f"❤️ {display_name}: `{pdata['hp']}/{eff['hp_max']}`\n"
                    f"❤️ {npc_data['name']}: `{npc_data['hp']}/{npc_data['hp_max']}`\n"
                    f"🎲 **{display_name}** đi trước!"
                )
            )

            session = {
                "player_pdata": pdata,
                "npc_pdata": npc_data,
                "npc_name": npc_data["name"],
                "player_name": display_name,
                "flags": {"turn_count": 0},
            }
            self.sessions[sid] = session

            view = NPCBattleView(self, sid, npc_id, pdata, npc_data,
                                 npc_data["name"], display_name, True)

            if isinstance(ctx_or_int, discord.ext.commands.Context):
                await ctx_or_int.send(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    async def _handle_npc_move(self, interaction: discord.Interaction,
                                view: NPCBattleView, move_type: str):
        await interaction.response.defer()
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session or view.finished:
            await interaction.followup.send("🤷 Hết trận rồi!", ephemeral=True)
            return

        player = session["player_pdata"]
        npc = session["npc_pdata"]
        flags = session["flags"]
        result_lines = []

        if move_type == "basic":
            skill_id = 1
        else:
            cat = "defense" if move_type == "defense" else move_type
            cd_key = f"{cat}_cd"
            if player.get(cd_key, 0) > 0:
                sk = get_equipped_skill(player, cat)
                await interaction.followup.send(
                    f"⏳ **{sk['name']}** đang hồi! Còn **{player[cd_key]}** turn.", ephemeral=True)
                return
            skill = get_equipped_skill(player, cat)
            skill_id = None
            for sid2, s in SKILLS_DB.items():
                if s["name"] == skill["name"]:
                    skill_id = sid2
                    break
            if skill_id is None:
                skill_id = 1

        # --- Player action ---
        flags["turn_count"] = flags.get("turn_count", 0)
        action = {"type": move_type, "skill_id": skill_id}
        result = await execute_action(player, npc, 0, action, flags)
        player = result["p1"]
        npc = result["p2"]
        result_lines.extend(result["log_messages"])

        if result["finished"]:
            await self._finish_npc_battle(interaction, session, view, player, npc, result_lines, npc["hp"] <= 0)
            return

        # --- NPC action ---
        npc_stunned = flags.get(f"{npc['id']}_stunned", False)
        if npc_stunned:
            flags.pop(f"{npc['id']}_stunned", None)
            result_lines.append(f"\n🌑 **{npc['name']}** bị choáng, mất lượt!")
        else:
            npc_move = self._npc_ai_move(npc)
            npc_cat = "defense" if npc_move == "defense" else npc_move
            npc_cd_key = f"{npc_cat}_cd"
            if npc.get(npc_cd_key, 0) > 0:
                npc_move = "attack"
                npc_cat = "attack"
                if npc.get("attack_cd", 0) > 0:
                    npc_move = "defense"
                    npc_cat = "defense"

            npc_skill = get_equipped_skill(npc, npc_cat)
            npc_skill_id = None
            for sid2, s in SKILLS_DB.items():
                if s["name"] == npc_skill["name"]:
                    npc_skill_id = sid2
                    break
            if npc_skill_id is None:
                npc_skill_id = 1

            result_lines.append(f"\n👾 {npc['name']} dùng **{npc_skill['icon']} {npc_skill['name']}**")

            npc_action = {"type": npc_move, "skill_id": npc_skill_id}
            flags["turn_count"] = flags.get("turn_count", 0) + 1
            result = await execute_action(npc, player, 0, npc_action, flags)
            npc = result["p1"]
            player = result["p2"]
            result_lines.extend(result["log_messages"])

            if result["finished"]:
                await self._finish_npc_battle(interaction, session, view, player, npc, result_lines, player["hp"] > 0)
                return

        # --- WIFE ATTACKS ---
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
            wives = [dict(r) for r in await cursor.fetchall()]
        finally:
            await db.close()
        for w in wives:
            wd = WIVES.get(w["wife_id"], WIVES[1])
            mult = RARITY_DMG_MULT.get(wd["rarity"], 0.5)
            dmg = max(1, int(random.randint(4, 10) * w.get("level", 1) * mult))
            npc["hp"] = max(0, npc["hp"] - dmg)
            result_lines.append(
                f"💕 {wd['emoji']} **{wd['name']}** ({wd['rarity']} Lv.{w['level']}) → **-{dmg}HP**!")

        if npc["hp"] <= 0:
            result_lines.append(f"\n💕 **{npc['name']}** bị vợ hạ gục! 🎉")
            await self._finish_npc_battle(interaction, session, view, player, npc, result_lines, npc["hp"] <= 0)
            return

        session["player_pdata"] = player
        session["npc_pdata"] = npc
        session["flags"] = flags

        eff = get_effective_stats(player)
        bar_len = 10
        pct1 = max(0, min(10, int(player["hp"] / max(eff["hp_max"], 1) * bar_len)))
        hp1_bar = "🟩" * pct1 + "⬜" * (bar_len - pct1)
        pct2 = max(0, min(10, int(npc["hp"] / max(npc["hp_max"], 1) * bar_len)))
        hp2_bar = "🟩" * pct2 + "⬜" * (bar_len - pct2)

        result_lines.append("\n━━━━━━━━━━━")
        result_lines.append(f"❤️ {session['player_name']}:`{player['hp']}/{eff['hp_max']}`{hp1_bar}")
        result_lines.append(f"❤️ {npc['name']}:`{npc['hp']}/{npc['hp_max']}`{hp2_bar}")

        # Wife display
        db2 = await get_db()
        try:
            wife_cursor = await db2.execute("SELECT pw.* FROM player_wives pw WHERE pw.player_id=? AND pw.equipped=1", (sid,))
            wife_rows = [dict(r) for r in await wife_cursor.fetchall()]
        finally:
            await db2.close()
        if wife_rows:
            wlist = []
            for wr in wife_rows:
                wd = WIVES.get(wr["wife_id"], WIVES[1])
                wlist.append(f"{wd['emoji']} **{wd['name']}** Lv.{wr['level']}")
            result_lines.append(f"💍 Vợ: {' | '.join(wlist)}")

        embed = discord.Embed(title="👾 NPC BATTLE", description="\n".join(result_lines), color=0x9966ff)
        new_view = NPCBattleView(self, sid, view.npc_id, player, npc,
                                 npc["name"], session["player_name"], True)
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def _finish_npc_battle(self, interaction, session, view, player, npc, result_lines, player_wins):
        view.finished = True
        sid = view.player_id
        result_lines.append("\n" + ("-" * 20))

        if player_wins:
            result_lines.append(f"🏆 **{session['player_name']}** thắng NPC **{npc['name']}**! 🎉")
        else:
            result_lines.append(f"💀 **{session['player_name']}** thua NPC **{npc['name']}**!")

        # Save player data
        db = await get_db()
        try:
            now = time.time()
            p_eff = get_effective_stats(player)

            if player_wins:
                nlevel = npc.get("level", 1)
                w_coins, w_xp = calc_rewards(True, player.get("level", 1), nlevel)
                # 50% of PvP rewards for NPCs
                w_coins = int(w_coins * 0.5)
                w_xp = int(w_xp * 0.5)
                apply_rewards(player, w_coins, w_xp)
                wife_lines = await self._level_wives(db, sid, w_xp)
                player["wins"] = player.get("wins", 0) + 1
                result_lines.append(f"💰 {session['player_name']}: +{w_coins}🪙 +{w_xp}XP")
                if wife_lines:
                    result_lines.extend(wife_lines)

                drop = calc_drop(player.get("role_mult", 1.0))
                if drop:
                    await apply_drop(db, sid, drop)
                    if drop["type"] == "coins":
                        player["coins"] = player.get("coins", 0) + drop["amount"]
                    result_lines.append(f"\n{drop['text']}")

                await db.execute("UPDATE player_buffs SET attack_boost=MAX(0, attack_boost-1), defense_boost=MAX(0, defense_boost-1), lucky=MAX(0, lucky-1) WHERE player_id=?", (sid,))

                if npc.get("level", 0) >= 15:
                    if random.random() < 0.05:
                        await db.execute("""INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) 
                            VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), 
                            COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + 1)""",
                            (sid, sid, sid))
                        result_lines.append("💎 +1 Đá Thần Khí!")
            else:
                w_coins, w_xp = 0, 0
                player["losses"] = player.get("losses", 0) + 1

            await db.execute("""UPDATE players SET hp=?, wins=?, losses=?, coins=?, xp=?, level=?,
                                 stat_points=?, last_battle_time=?, last_hp_update=?
                                 WHERE id=?""",
                              (max(0, player["hp"]), player.get("wins", 0), player.get("losses", 0),
                               player.get("coins", 0), player.get("xp", 0), player.get("level", 1),
                               player.get("stat_points", 0), now, now, sid))
            await db.commit()
            await update_combat_power(sid)
        finally:
            await db.close()

        self.sessions.pop(sid, None)
        embed = discord.Embed(title="👾 NPC BATTLE - KẾT THÚC", description="\n".join(result_lines),
                              color=0xffd700 if player_wins else 0xff0000)
        await interaction.edit_original_response(embed=embed, view=None)

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


async def setup(bot):
    await bot.add_cog(NPCCog(bot))
