import discord
from discord import app_commands
from discord.ext import commands
import random
import time
from datetime import datetime, timedelta
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, STAR_LABELS, SLOT_NAMES
from bot.data.classes import CLASSES
from bot.data.skills import SKILLS_DB
from bot.engine.battle import execute_action, get_equipped_skill, regen_hp, get_effective_stats
from bot.config import (
    DUNGEON_MAX_FLOOR, DUNGEON_REQUIRED_LEVEL,
    DUNGEON_FREE_ENTRIES, DUNGEON_MAX_TICKETS,
    DUNGEON_TICKET_COST_1, DUNGEON_TICKET_COST_2,
)


REAL_CLASSES = ["banxabong", "xola", "sieunhan", "thaychua", "muoi", "chodien", "baque"]


def generate_dungeon_npc(floor: int) -> dict:
    npc_level = floor + 5
    hp = 100 + npc_level * 25
    atk = 10 + npc_level * 5
    defense = 5 + npc_level * 3
    names = [
        "Quái Vật Bóng Tối", "Thú Dữ Vực Sâu", "Linh Hồn Lạc Lối",
        "Xác Sống Vô Hồn", "Quỷ Dữ Bóng Đêm", "Rồng Đen Hắc Ám",
        "Ma Cà Rồng", "Người Sói", "Quái Nhân Đột Biến",
        "Thằn Lằn Khổng Lồ", "Nhện Tinh", "Bọ Cạp Độc",
        "Dơi Quỷ", "Rắn Độc Vực Sâu", "Quỷ Lửa",
        "Băng Quái", "Lôi Điểu", "Thạch Nhân",
        "Hải Quái", "Phượng Hoàng Bóng Tối",
    ]
    name = random.choice(names)
    boss_names = {
        10: "BOSS TẦNG 10 - QUỶ VƯƠNG", 20: "BOSS TẦNG 20 - LONG VƯƠNG",
        30: "BOSS TẦNG 30 - MA VƯƠNG", 40: "BOSS TẦNG 40 - THẦN CHẾT",
        50: "BOSS TẦNG 50 - DIỆT THẾ", 60: "BOSS TẦNG 60 - HỦY DIỆT",
        70: "BOSS TẦNG 70 - VÔ CỰC", 80: "BOSS TẦNG 80 - HỖN ĐỘN",
        90: "BOSS TẦNG 90 - TẬN THẾ", 100: "BOSS CUỐI - CHÚA TỂ VỰC SÂU",
    }
    if floor in boss_names:
        name = boss_names[floor]
        hp = int(hp * 2)
        atk = int(atk * 1.5)
        defense = int(defense * 1.3)

    if floor <= 20:
        skills = {"attack": 1, "special": 5, "defense": 10, "passive": 14}
    elif floor <= 50:
        skills = {"attack": 2, "special": 6, "defense": 11, "passive": 17}
    elif floor <= 80:
        skills = {"attack": 3, "special": 7, "defense": 12, "passive": 19}
    else:
        skills = {"attack": 4, "special": 9, "defense": 13, "passive": 20}

    return {
        "id": f"dungeon_{floor}",
        "name": name,
        "hp": hp,
        "hp_max": hp,
        "attack_min": atk,
        "attack_max": atk + 5,
        "defense": defense,
        "level": npc_level,
        "class_id": random.choice(REAL_CLASSES),
        "cooldowns": {"attack_cd": 0, "special_cd": 0, "defense_cd": 0},
        "skill_equipped": skills,
        "_npc_override": True,
    }


def calc_dungeon_rewards(floor: int) -> dict:
    rewards = {
        "stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0, "artifact": 0},
        "coins": 0,
        "equipment": [],
    }

    if floor <= 20:
        rewards["stones"]["stone_basic"] = random.randint(1, 4)
        rewards["coins"] = random.randint(50, 200)
    elif floor <= 50:
        rewards["stones"]["stone_medium"] = random.randint(1, 5)
        rewards["coins"] = random.randint(150, 500)
    else:
        rewards["stones"]["stone_advanced"] = random.randint(1, 6)
        rewards["coins"] = random.randint(300, 1200)

    if random.random() < 0.08:
        if floor <= 20:
            star_pool = [1, 2]
        elif floor <= 50:
            star_pool = [1, 2, 3, 4]
        else:
            star_pool = list(range(1, 7))
        star = random.choice(star_pool)
        items = [e for eid, e in EQUIPMENT.items() if e["star"] == star]
        if items:
            chosen = random.choice(items)
            eid = [k for k, v in EQUIPMENT.items() if v == chosen][0]
            rewards["equipment"].append({"eid": eid, "name": chosen["name"], "star": star})

    if floor >= 50:
        import random
        if random.random() < 0.03:
            rewards["stones"]["artifact"] = 1

    return rewards


class DungeonView(discord.ui.View):
    def __init__(self, cog, player_id: str, floor: int, player_pdata: dict,
                 npc_pdata: dict, player_name: str, accumulated_rewards: dict):
        super().__init__(timeout=None)
        self.cog = cog
        self.player_id = player_id
        self.floor = floor
        self.player_pdata = player_pdata
        self.npc_pdata = npc_pdata
        self.player_name = player_name
        self.accumulated_rewards = accumulated_rewards
        self.finished = False

        pdata = player_pdata
        atk = get_equipped_skill(pdata, "attack")
        spc = get_equipped_skill(pdata, "special")

        btn_fight = discord.ui.Button(
            emoji="⚔️", label="Chiến đấu",
            style=discord.ButtonStyle.danger, custom_id="dungeon_fight", row=0)
        btn_fight.callback = self._fight_callback
        self.add_item(btn_fight)

        btn_stop = discord.ui.Button(
            emoji="🏃", label="Dừng & Nhận thưởng",
            style=discord.ButtonStyle.success, custom_id="dungeon_stop", row=0)
        btn_stop.callback = self._stop_callback
        self.add_item(btn_stop)

        btn_atk = discord.ui.Button(
            emoji=atk.get("icon", "💥"), label=atk.get("name", "Tấn Công")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_atk", row=1)
        btn_atk.callback = self._make_move_callback("attack")
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(
            emoji=spc.get("icon", "🔥"), label=spc.get("name", "Đặc Biệt")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_spc", row=1)
        btn_spc.callback = self._make_move_callback("special")
        self.add_item(btn_spc)

        btn_def = discord.ui.Button(
            emoji="🛡️", label="Chống Xỏ Lá",
            style=discord.ButtonStyle.secondary, custom_id="dungeon_def", row=1)
        btn_def.callback = self._make_move_callback("defense")
        self.add_item(btn_def)

    async def _fight_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog._handle_dungeon_fight(interaction, self)

    async def _stop_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog._handle_dungeon_stop(interaction, self)

    def _make_move_callback(self, move_type: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await self.cog._handle_dungeon_move(interaction, self, move_type)
        return callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True


class DungeonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    def _get_monday(self) -> str:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    @commands.command(name="bicanh")
    async def bicanh_cmd(self, ctx):
        await self._bicanh_entry(ctx, str(ctx.author.id), ctx.author.display_name, "!")

    @app_commands.command(name="bicanh", description="🏰 Vào bí cảnh Vực Sâu Xỏ Lá")
    async def slash_bicanh(self, interaction: discord.Interaction):
        await self._bicanh_entry(interaction, str(interaction.user.id),
                                 interaction.user.display_name, "/")

    async def _bicanh_entry(self, ctx_or_int, sid: str, display_name: str, prefix: str):
        if sid in self.sessions:
            await self._reply(ctx_or_int, "🏰 Mày đang trong bí cảnh rồi!")
            return

        db = await get_db()
        try:
            player_cursor = await db.execute("SELECT level, coins, hp FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, f"🤷 Chưa đăng ký! `{prefix}register`")
                return
            pdata = dict(prow)
            if pdata["level"] < DUNGEON_REQUIRED_LEVEL:
                await self._reply(ctx_or_int,
                    f"🔒 Cần level **{DUNGEON_REQUIRED_LEVEL}**! Mày Lv.{pdata['level']}")
                return

            dg_cursor = await db.execute("SELECT * FROM dungeon_progress WHERE player_id=?", (sid,))
            dg_row = await dg_cursor.fetchone()
            if dg_row:
                dg = dict(dg_row)
            else:
                await db.execute(
                    "INSERT INTO dungeon_progress (player_id, checkpoint, daily_entries, daily_tickets_bought, last_entry_date, last_week_reset) VALUES (?, 0, 0, 0, '', '')",
                    (sid,))
                dg = {"checkpoint": 0, "daily_entries": 0, "daily_tickets_bought": 0,
                      "last_entry_date": "", "last_week_reset": ""}

            monday = self._get_monday()
            if dg.get("last_week_reset", "") != monday:
                dg["checkpoint"] = 0
                dg["last_week_reset"] = monday
                await db.execute("UPDATE dungeon_progress SET checkpoint=0, last_week_reset=? WHERE player_id=?",
                                 (monday, sid))

            today = datetime.now().strftime("%Y-%m-%d")
            if dg.get("last_entry_date", "") != today:
                dg["daily_entries"] = 0
                dg["daily_tickets_bought"] = 0
                dg["last_entry_date"] = today
                await db.execute("UPDATE dungeon_progress SET daily_entries=0, daily_tickets_bought=0, last_entry_date=? WHERE player_id=?",
                                 (today, sid))

            import json
            pending_rewards = dg.get("accumulated_rewards", "")
            if pending_rewards:
                try:
                    saved = json.loads(pending_rewards)
                    if saved.get("coins", 0) > 0 or saved.get("stones", {}).get("stone_basic", 0) > 0 or saved.get("stones", {}).get("stone_medium", 0) > 0 or saved.get("stones", {}).get("stone_advanced", 0) > 0 or saved.get("equipment", []):
                        await self._apply_rewards(db, sid, saved)
                        await db.execute("UPDATE dungeon_progress SET accumulated_rewards='' WHERE player_id=?", (sid,))
                except:
                    pass

            free_used = dg["daily_entries"] >= DUNGEON_FREE_ENTRIES
            tickets_bought = dg.get("daily_tickets_bought", 0)

            if free_used and tickets_bought >= DUNGEON_MAX_TICKETS:
                await self._reply(ctx_or_int,
                    f"🏰 Hết lượt hôm nay! (Free: đã dùng, Vé: {tickets_bought}/{DUNGEON_MAX_TICKETS})\n⏰ Reset sau 0h!")
                return

            ticket_msg = ""
            if free_used:
                cost = DUNGEON_TICKET_COST_1 if tickets_bought == 0 else DUNGEON_TICKET_COST_2
                if pdata["coins"] < cost:
                    await self._reply(ctx_or_int,
                        f"😅 Nghèo! Cần {cost}🪙 mua vé, có {pdata['coins']}🪙")
                    return
                await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))
                await db.execute("UPDATE dungeon_progress SET daily_tickets_bought=daily_tickets_bought+1 WHERE player_id=?", (sid,))
                ticket_msg = f"\n🎫 Mua vé: -{cost}🪙"

            await db.execute("UPDATE dungeon_progress SET daily_entries=daily_entries+1 WHERE player_id=?", (sid,))
            await db.commit()

            next_floor = dg["checkpoint"] + 1
            await self._start_dungeon_floor(ctx_or_int, sid, display_name, next_floor, ticket_msg)

        finally:
            await db.close()

    async def _start_dungeon_floor(self, ctx_or_int, sid: str, display_name: str,
                                    floor: int, extra_msg: str = ""):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            pdata = dict(row)
            regen_hp(pdata)

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
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances

            art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
            art_row = await art_cursor.fetchone()
            pdata["_artifact_star"] = art_row[0] if art_row else 0
            pdata["_artifact_stones"] = art_row[1] if art_row else 0

            pdata["attack_cd"] = 0
            pdata["special_cd"] = 0
            pdata["defense_cd"] = 0

            eff = get_effective_stats(pdata)

            npc_data = generate_dungeon_npc(floor)
            npc_data["equipped"] = {}
            npc_data["_equip_items"] = {}
            npc_data["_equip_enhances"] = {}

            rewards = {"stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0},
                       "coins": 0, "equipment": []}

            cls_player = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
            desc = (
                f"🏰 **Tầng {floor}/{DUNGEON_MAX_FLOOR}**\n"
                f"━━━━━━━━━━━\n"
                f"{cls_player['icon']} **{display_name}** Lv.{pdata.get('level', 1)}\n"
                f"👾 **{npc_data['name']}** Lv.{npc_data['level']}\n"
                f"❤️ {display_name}: `{pdata['hp']}/{eff['hp_max']}`\n"
                f"❤️ {npc_data['name']}: `{npc_data['hp']}/{npc_data['hp_max']}`\n"
                f"{extra_msg}"
            )
            embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ", description=desc, color=0x8844ff)

            session = {
                "player_pdata": pdata,
                "npc_pdata": npc_data,
                "npc_name": npc_data["name"],
                "player_name": display_name,
                "floor": floor,
                "flags": {"turn_count": 0},
                "accumulated_rewards": rewards,
            }
            self.sessions[sid] = session

            view = DungeonView(self, sid, floor, pdata, npc_data, display_name, rewards)

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    def _npc_ai_move(self, npc: dict) -> str:
        hp_pct = npc["hp"] / max(npc["hp_max"], 1) * 100
        if hp_pct < 30:
            return random.choices(["attack", "special", "defense"], weights=[20, 15, 65])[0]
        elif hp_pct < 60:
            return random.choices(["attack", "special", "defense"], weights=[35, 30, 35])[0]
        else:
            return random.choices(["attack", "special", "defense"], weights=[40, 35, 25])[0]

    async def _handle_dungeon_fight(self, interaction: discord.Interaction, view: DungeonView):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session or view.finished:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return
        await self._execute_dungeon_turn(interaction, session, view, "attack")

    async def _handle_dungeon_move(self, interaction: discord.Interaction,
                                    view: DungeonView, move_type: str):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session or view.finished:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return
        await self._execute_dungeon_turn(interaction, session, view, move_type)

    async def _execute_dungeon_turn(self, interaction: discord.Interaction,
                                     session: dict, view: DungeonView,
                                     player_move_type: str):
        player = session["player_pdata"]
        npc = session["npc_pdata"]
        flags = session["flags"]
        result_lines = []

        cat = "defense" if player_move_type == "defense" else player_move_type
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

        result = await execute_action(player, npc, 0, {"type": player_move_type, "skill_id": skill_id}, flags)
        player = result["p1"]
        npc = result["p2"]
        result_lines.extend(result["log_messages"])

        if result["finished"]:
            await self._finish_dungeon_floor(interaction, session, view, player["hp"] > 0, result_lines)
            return

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

        flags["turn_count"] = flags.get("turn_count", 0) + 1
        result = await execute_action(npc, player, 0, {"type": npc_move, "skill_id": npc_skill_id}, flags)
        npc = result["p1"]
        player = result["p2"]
        result_lines.extend(result["log_messages"])

        if result["finished"]:
            await self._finish_dungeon_floor(interaction, session, view, player["hp"] > 0, result_lines)
            return

        session["player_pdata"] = player
        session["npc_pdata"] = npc
        session["flags"] = flags

        eff = get_effective_stats(player)
        bar_len = 10
        pct1 = max(0, min(bar_len, int(player["hp"] / max(eff["hp_max"], 1) * bar_len)))
        hp1_bar = "🟩" * pct1 + "⬜" * (bar_len - pct1)
        pct2 = max(0, min(bar_len, int(npc["hp"] / max(npc["hp_max"], 1) * bar_len)))
        hp2_bar = "🟩" * pct2 + "⬜" * (bar_len - pct2)

        result_lines.append("\n━━━━━━━━━━━")
        result_lines.append(f"❤️ {session['player_name']}:`{player['hp']}/{eff['hp_max']}`{hp1_bar}")
        result_lines.append(f"❤️ {npc['name']}:`{npc['hp']}/{npc['hp_max']}`{hp2_bar}")

        desc = session.get("_start_desc", f"🏰 **Tầng {session['floor']}/{DUNGEON_MAX_FLOOR}**")
        embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ",
                              description=desc + "\n\n" + "\n".join(result_lines),
                              color=0x8844ff)
        new_view = DungeonView(self, view.player_id, session["floor"],
                               player, npc, session["player_name"],
                               session["accumulated_rewards"])
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def _finish_dungeon_floor(self, interaction: discord.Interaction,
                                     session: dict, view: DungeonView,
                                     player_wins: bool, result_lines: list):
        view.finished = True
        sid = view.player_id

        if player_wins:
            floor = session["floor"]
            rewards = calc_dungeon_rewards(floor)
            acc = session["accumulated_rewards"]
            for k in ["stone_basic", "stone_medium", "stone_advanced"]:
                acc["stones"][k] = acc["stones"].get(k, 0) + rewards["stones"].get(k, 0)
            acc["coins"] += rewards["coins"]
            acc["equipment"].extend(rewards["equipment"])

            result_lines.append(f"\n✅ Thắng tầng {floor}!")
            result_lines.append(f"💰 +{rewards['coins']}🪙")
            for k, label in [("stone_basic", "Đá sơ cấp"), ("stone_medium", "Đá trung cấp"), ("stone_advanced", "Đá cao cấp")]:
                if rewards["stones"].get(k, 0) > 0:
                    result_lines.append(f"💎 +{rewards['stones'][k]} {label}")
            for eq in rewards["equipment"]:
                stars = STAR_LABELS.get(eq["star"], "⭐")
                result_lines.append(f"⚒️ +{stars} **{eq['name']}**")

            db = await get_db()
            try:
                import json
                await db.execute(
                    "UPDATE dungeon_progress SET checkpoint=MAX(checkpoint, ?), accumulated_rewards=? WHERE player_id=?",
                    (floor, json.dumps(acc), sid))
                await db.commit()
            finally:
                await db.close()

            next_floor = floor + 1
            if next_floor > DUNGEON_MAX_FLOOR:
                result_lines.append(f"\n🎉 HOÀN THÀNH 100 TẦNG! Nhận hết thưởng!")
                await self._collect_rewards(interaction, session, sid, result_lines)
                self.sessions.pop(sid, None)
                return

            result_lines.append(f"\n🎯 Sẵn sàng tầng **{next_floor}**!")
            result_lines.append(f"💎 Tích lũy: {acc['coins']}🪙 | Sơ:{acc['stones']['stone_basic']} Trung:{acc['stones']['stone_medium']} Cao:{acc['stones']['stone_advanced']}")

            desc = f"🏰 Đã thắng **tầng {floor}**! → Tầng {next_floor}/{DUNGEON_MAX_FLOOR}"
            embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ - THẮNG!",
                                  description=desc + "\n\n" + "\n".join(result_lines),
                                  color=0x00ff00)

            player = session["player_pdata"]
            npc_data = generate_dungeon_npc(next_floor)
            npc_data["equipped"] = {}
            npc_data["_equip_items"] = {}
            npc_data["_equip_enhances"] = {}

            session["floor"] = next_floor
            session["npc_pdata"] = npc_data
            session["npc_name"] = npc_data["name"]
            session["flags"] = {"turn_count": 0}
            session["_start_desc"] = desc

            new_view = DungeonView(self, sid, next_floor, player, npc_data,
                                   session["player_name"], acc)
            await interaction.edit_original_response(embed=embed, view=new_view)
        else:
            result_lines.append(f"\n💀 Thua! Nhận thưởng đã tích lũy...")
            await self._collect_rewards(interaction, session, sid, result_lines)
            self.sessions.pop(sid, None)

    async def _handle_dungeon_stop(self, interaction: discord.Interaction, view: DungeonView):
        view.finished = True
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return

        result_lines = [f"🏃 Dừng ở tầng **{session['floor']}**! Nhận thưởng..."]
        await self._collect_rewards(interaction, session, sid, result_lines)
        self.sessions.pop(sid, None)

    async def _collect_rewards(self, interaction: discord.Interaction,
                                session: dict, sid: str, result_lines: list):
        acc = session["accumulated_rewards"]
        db = await get_db()
        try:
            player = session["player_pdata"]
            now = time.time()
            await db.execute("""UPDATE players SET hp=?, last_battle_time=?, last_hp_update=?
                                 WHERE id=?""",
                             (max(0, player.get("hp", 0)), now, now, sid))

            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (sid,))
            srow = await stone_cursor.fetchone()
            if srow:
                await db.execute("""UPDATE player_enhance_stones
                    SET stone_basic=stone_basic+?, stone_medium=stone_medium+?, stone_advanced=stone_advanced+?
                    WHERE player_id=?""",
                    (acc["stones"]["stone_basic"], acc["stones"]["stone_medium"],
                     acc["stones"]["stone_advanced"], sid))
            else:
                await db.execute("""INSERT INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced)
                    VALUES (?, ?, ?, ?)""",
                     (sid, acc["stones"]["stone_basic"], acc["stones"]["stone_medium"],
                      acc["stones"]["stone_advanced"]))

            if acc["stones"].get("artifact", 0) > 0:
                art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
                art_row = await art_cursor.fetchone()
                if art_row:
                    await db.execute("UPDATE player_artifact SET stone_count=stone_count+? WHERE player_id=?", (acc["stones"]["artifact"], sid))
                else:
                    await db.execute("INSERT INTO player_artifact (player_id, star, stone_count) VALUES (?, 0, ?)", (sid, acc["stones"]["artifact"]))

            if acc["coins"] > 0:
                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (acc["coins"], sid))

            for eq in acc["equipment"]:
                await db.execute(
                    "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                    (sid, eq["eid"]))

            await db.execute("UPDATE dungeon_progress SET accumulated_rewards='' WHERE player_id=?", (sid,))
            await db.commit()

            total_lines = []
            if acc["coins"] > 0:
                total_lines.append(f"💰 Tổng coin: +{acc['coins']}🪙")
            for k, label in [("stone_basic", "Đá sơ cấp"), ("stone_medium", "Đá trung cấp"), ("stone_advanced", "Đá cao cấp")]:
                if acc["stones"].get(k, 0) > 0:
                    total_lines.append(f"💎 {label}: +{acc['stones'][k]}")
            if acc["stones"].get("artifact", 0) > 0:
                total_lines.append(f"💎 Đá thần khí: +{acc['stones']['artifact']}")
            if acc["equipment"]:
                total_lines.append(f"⚒️ Trang bị: {len(acc['equipment'])} món")
            if total_lines:
                result_lines.append("\n".join(total_lines))

        finally:
            await db.close()

        embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ - NHẬN THƯỞNG",
                              description="\n".join(result_lines), color=0xffd700)
        await interaction.edit_original_response(embed=embed, view=None)

    async def _apply_rewards(self, db, sid: str, acc: dict):
        stone_cursor = await db.execute(
            "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?", (sid,))
        srow = await stone_cursor.fetchone()
        if srow:
            await db.execute("""UPDATE player_enhance_stones
                SET stone_basic=stone_basic+?, stone_medium=stone_medium+?, stone_advanced=stone_advanced+?
                WHERE player_id=?""",
                (acc["stones"].get("stone_basic", 0), acc["stones"].get("stone_medium", 0),
                 acc["stones"].get("stone_advanced", 0), sid))
        else:
            await db.execute("INSERT INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, ?, ?)",
                (sid, acc["stones"].get("stone_basic", 0), acc["stones"].get("stone_medium", 0), acc["stones"].get("stone_advanced", 0)))
        if acc.get("coins", 0) > 0:
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (acc["coins"], sid))
        for eq in acc.get("equipment", []):
            await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)", (sid, eq["eid"]))

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(DungeonCog(bot))
