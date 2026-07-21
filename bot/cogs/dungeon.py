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
from bot.utils.player_loader import load_player_full
from bot.views.ui_helpers import (
    hp_bar, format_battle_log, result_embed,
    dungeon_floor_color, is_boss_floor, dungeon_progress_bar
)


REAL_CLASSES = ["banxabong", "xola", "sieunhan", "thaychua", "muoi", "chodien", "baque"]


# ── Dungeon embed helpers ─────────────────────────────────────────────────────

def _dungeon_header_embed(floor: int, player_name: str, pdata: dict,
                           npc_data: dict, extra_msg: str = "") -> discord.Embed:
    """Embed hiển thị trạng thái tầng dungeon."""
    eff = get_effective_stats(pdata)
    cls_player = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])

    is_boss = is_boss_floor(floor)
    color = dungeon_floor_color(floor)
    title = f"⚔️ BOSS TẦNG {floor}!" if is_boss else f"🏰 Vực Sâu Xỏ Lá — Tầng {floor}"

    prog_bar = dungeon_progress_bar(floor, DUNGEON_MAX_FLOOR, 10)

    # HP bars
    p_bar = hp_bar(pdata["hp"], eff["hp_max"], 8)
    n_bar = hp_bar(npc_data["hp"], npc_data["hp_max"], 8)
    p_pct = int(pdata["hp"] / max(eff["hp_max"], 1) * 100)
    n_pct = int(npc_data["hp"] / max(npc_data["hp_max"], 1) * 100)

    desc = (
        f"**Tiến Độ:** {prog_bar} `{floor}/{DUNGEON_MAX_FLOOR}`\n"
        f"{'─' * 28}\n"
        f"{cls_player['icon']} **{player_name}** Lv.{pdata.get('level', 1)}\n"
        f"❤️ `{pdata['hp']}/{eff['hp_max']}` ({p_pct}%)  {p_bar}\n\n"
        f"{'💀' if is_boss else '👾'} **{npc_data['name']}** Lv.{npc_data['level']}\n"
        f"❤️ `{npc_data['hp']}/{npc_data['hp_max']}` ({n_pct}%)  {n_bar}"
    )
    if extra_msg:
        desc += f"\n{'─' * 28}\n{extra_msg}"

    embed = discord.Embed(title=title, description=desc, color=color)
    if is_boss:
        embed.set_footer(text="⚠️ BOSS ROUND — Nguy hiểm cao!")
    return embed


def _dungeon_battle_embed(floor: int, player_name: str, pdata: dict,
                           npc_data: dict, log_lines: list[str]) -> discord.Embed:
    """Embed hiển thị diễn biến chiến đấu trong dungeon."""
    eff = get_effective_stats(pdata)
    is_boss = is_boss_floor(floor)
    color = dungeon_floor_color(floor)

    p_bar = hp_bar(pdata["hp"], eff["hp_max"], 8)
    n_bar = hp_bar(npc_data["hp"], npc_data["hp_max"], 8)
    p_pct = int(pdata["hp"] / max(eff["hp_max"], 1) * 100)
    n_pct = int(npc_data["hp"] / max(npc_data["hp_max"], 1) * 100)

    # Skill CDs
    cd_parts = []
    for cat in ["attack", "special", "defense"]:
        sk = get_equipped_skill(pdata, cat)
        cd = pdata.get(f"{cat}_cd", 0)
        cd_parts.append(f"{sk.get('icon','?')}{'✅' if cd <= 0 else f'⏳{cd}'}")

    status_block = (
        f"**{player_name}** `{pdata['hp']}/{eff['hp_max']}` ({p_pct}%)\n"
        f"{p_bar}  {' '.join(cd_parts)}\n\n"
        f"**{npc_data['name']}** `{npc_data['hp']}/{npc_data['hp_max']}` ({n_pct}%)\n"
        f"{n_bar}"
    )

    log_text = format_battle_log(log_lines, max_chars=1800)

    embed = discord.Embed(
        title=f"{'💀 BOSS' if is_boss else '👾 Dungeon'} — Tầng {floor}/{DUNGEON_MAX_FLOOR}",
        color=color
    )
    embed.add_field(name="📊 Trạng Thái", value=status_block, inline=False)
    if log_text:
        embed.add_field(name="⚔️ Diễn Biến", value=log_text, inline=False)
    prog_bar = dungeon_progress_bar(floor, DUNGEON_MAX_FLOOR, 10)
    embed.set_footer(text=f"Tiến độ: {prog_bar} {floor}/{DUNGEON_MAX_FLOOR}")
    return embed


def _dungeon_reward_embed(acc: dict, floor: int, title: str) -> discord.Embed:
    """Embed hiển thị thưởng dungeon."""
    embed = discord.Embed(title=f"🏆 {title}", color=0xffd700)

    reward_lines = []
    if acc["coins"] > 0:
        reward_lines.append(f"💰 **{acc['coins']:,} 🪙**".replace(",", "."))
    for k, label, emoji in [
        ("stone_basic", "Đá Sơ Cấp", "🔵"),
        ("stone_medium", "Đá Trung Cấp", "🟢"),
        ("stone_advanced", "Đá Cao Cấp", "🔴"),
    ]:
        v = acc["stones"].get(k, 0)
        if v > 0:
            reward_lines.append(f"{emoji} **{v}x** {label}")
    for eq in acc["equipment"]:
        stars = STAR_LABELS.get(eq["star"], "⭐")
        reward_lines.append(f"⚒️ {stars} **{eq['name']}**")

    embed.description = "\n".join(reward_lines) if reward_lines else "_Không có gì..._"

    prog = dungeon_progress_bar(floor, DUNGEON_MAX_FLOOR, 10)
    embed.set_footer(text=f"Dừng ở tầng {floor}/{DUNGEON_MAX_FLOOR}  ·  {prog}")
    return embed


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
        hp = int(hp * 7)
        atk = int(atk * 7)
        defense = int(defense * 7)
    else:
        hp = int(hp * 3)
        atk = int(atk * 3)
        defense = int(defense * 3)

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
        "stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0},
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

    return rewards


class DungeonView(discord.ui.View):
    def __init__(self, cog, player_id: str, floor: int, player_pdata: dict,
                 npc_pdata: dict, player_name: str, accumulated_rewards: dict,
                 run_id: str = ""):
        super().__init__(timeout=180)
        self.cog = cog
        self.player_id = player_id
        self.floor = floor
        self.player_pdata = player_pdata
        self.npc_pdata = npc_pdata
        self.player_name = player_name
        self.accumulated_rewards = accumulated_rewards
        self.finished = False
        self._run_id = run_id

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

        btn_basic = discord.ui.Button(
            emoji="👊", label="Cú Đấm Ba Que",
            style=discord.ButtonStyle.secondary, custom_id="dungeon_basic", row=1)
        btn_basic.callback = self._make_move_callback("basic")
        self.add_item(btn_basic)

        btn_atk = discord.ui.Button(
            emoji=atk.get("icon", "💥"), label=atk.get("name", "Tấn Công")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_atk", row=2)
        btn_atk.callback = self._make_move_callback("attack")
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(
            emoji=spc.get("icon", "🔥"), label=spc.get("name", "Đặc Biệt")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_spc", row=2)
        btn_spc.callback = self._make_move_callback("special")
        self.add_item(btn_spc)

        btn_def = discord.ui.Button(
            emoji="🛡️", label="Chống Xỏ Lá",
            style=discord.ButtonStyle.secondary, custom_id="dungeon_def", row=2)
        btn_def.callback = self._make_move_callback("defense")
        self.add_item(btn_def)

    async def on_timeout(self):
        if self.finished or getattr(self, '_handling', False):
            return
        self.finished = True
        sid = self.player_id
        session = self.cog.sessions.get(sid)
        if not session or session.get("_run_id") != self._run_id:
            return
        self.cog.sessions.pop(sid, None)
        if session:
            db = await get_db()
            try:
                acc = session["accumulated_rewards"]
                player = session["player_pdata"]
                now = time.time()
                await db.execute("UPDATE players SET hp=?, last_battle_time=?, last_hp_update=? WHERE id=?",
                                 (max(0, player.get("hp", 0)), now, now, sid))
                if acc["coins"] > 0:
                    await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (acc["coins"], sid))
                for sk, sq in acc["stones"].items():
                    if sq > 0 and sk in ("stone_basic", "stone_medium", "stone_advanced"):
                        await db.execute("INSERT OR IGNORE INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, 0, 0, 0)", (sid,))
                        await db.execute(f"UPDATE player_enhance_stones SET {sk}={sk}+? WHERE player_id=?", (sq, sid))
                for eq in acc["equipment"]:
                    await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)", (sid, eq["eid"]))
                await db.execute("UPDATE dungeon_progress SET accumulated_rewards='' WHERE player_id=?", (sid,))
                await db.commit()

                # Build reward summary
                desc = f"⏰ **Hết thời gian ở tầng {self.floor}!**\n\n🏃 Đã nhận thưởng tích lũy:\n"
                desc += f"💰 **{acc['coins']}**🪙"
                for sk, label in [("stone_basic", "Đá sơ cấp"), ("stone_medium", "Đá trung cấp"), ("stone_advanced", "Đá cao cấp")]:
                    if acc["stones"].get(sk, 0) > 0:
                        desc += f"\n💎 **{acc['stones'][sk]}** {label}"
                for eq in acc["equipment"]:
                    stars = STAR_LABELS.get(eq["star"], "⭐")
                    desc += f"\n⚒️ {stars} **{eq['name']}**"
                embed = discord.Embed(title="🏰 Bí Cảnh Vực Sâu", description=desc, color=0xff8800)
                if "_message" in session:
                    await session["_message"].edit(embed=embed, view=None)
            finally:
                await db.close()

    async def _fight_callback(self, interaction: discord.Interaction):
        self._handling = True
        await interaction.response.defer()
        await self.cog._handle_dungeon_fight(interaction, self)

    async def _stop_callback(self, interaction: discord.Interaction):
        self._handling = True
        await interaction.response.defer()
        await self.cog._handle_dungeon_stop(interaction, self)

    def _make_move_callback(self, move_type: str):
        async def callback(interaction: discord.Interaction):
            self._handling = True
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
        await interaction.response.defer()
        await self._bicanh_entry(interaction, str(interaction.user.id),
                                 interaction.user.display_name, "/")

    async def _bicanh_entry(self, ctx_or_int, sid: str, display_name: str, prefix: str):
        if sid in self.sessions:
            await self._reply(ctx_or_int, "🏰 Mày đang trong bí cảnh rồi!")
            return

        db = await get_db()
        try:
            player_cursor = await db.execute("SELECT level, coins, hp, role_mult FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, f"🤷 Chưa đăng ký! `{prefix}register`")
                return
            pdata = dict(prow)

            # Sync role_mult from Discord roles
            if isinstance(ctx_or_int, commands.Context):
                guild = ctx_or_int.guild
            else:
                guild = ctx_or_int.guild
            if guild:
                member = guild.get_member(int(sid))
                if not member:
                    try:
                        member = await guild.fetch_member(int(sid))
                    except:
                        pass
                if member:
                    from bot.cogs.admin import sync_role_mult
                    await sync_role_mult(db, sid, [r.name for r in member.roles])
                    pc = await db.execute("SELECT role_mult FROM players WHERE id=?", (sid,))
                    pr = await pc.fetchone()
                    if pr:
                        pdata["role_mult"] = pr[0]

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

            free_used = dg["daily_entries"] >= DUNGEON_FREE_ENTRIES
            tickets_bought = dg.get("daily_tickets_bought", 0)
            is_dragon = pdata.get("role_mult", 1.0) >= 3.0

            if not is_dragon and free_used and tickets_bought >= DUNGEON_MAX_TICKETS:
                await self._reply(ctx_or_int,
                    f"🏰 Hết lượt hôm nay! (Free: đã dùng, Vé: {tickets_bought}/{DUNGEON_MAX_TICKETS})\n⏰ Reset sau 0h!")
                return

            ticket_msg = ""
            if free_used and not is_dragon:
                cost = DUNGEON_TICKET_COST_1 if tickets_bought == 0 else DUNGEON_TICKET_COST_2
                if pdata["coins"] < cost:
                    await self._reply(ctx_or_int,
                        f"😅 Nghèo! Cần {cost}🪙 mua vé, có {pdata['coins']}🪙")
                    return
                await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))
                await db.execute("UPDATE dungeon_progress SET daily_tickets_bought=daily_tickets_bought+1 WHERE player_id=?", (sid,))
                ticket_msg = f"\n🎫 Mua vé: -{cost}🪙"

            if not is_dragon:
                await db.execute("UPDATE dungeon_progress SET daily_entries=daily_entries+1 WHERE player_id=?", (sid,))
            await db.commit()

            next_floor = dg["checkpoint"] + 1
            from bot.cogs.quest import update_progress
            await update_progress(db, sid, 6)
            await self._start_dungeon_floor(ctx_or_int, sid, display_name, next_floor, ticket_msg)

        finally:
            await db.close()

    async def _start_dungeon_floor(self, ctx_or_int, sid: str, display_name: str,
                                    floor: int, extra_msg: str = ""):
        db = await get_db()
        try:
            # Dùng shared utility — bao gồm hidden_stats (fix bug cũ thiếu hidden stats)
            pdata = await load_player_full(db, sid, reset_cd=True)
            if pdata is None:
                await self._reply(ctx_or_int, "❌ Không tìm thấy dữ liệu người chơi!")
                return

            eff = get_effective_stats(pdata)

            # Full heal at dungeon entry
            pdata["hp"] = eff["hp_max"]

            npc_data = generate_dungeon_npc(floor)
            npc_data["equipped"] = {}
            npc_data["_equip_items"] = {}
            npc_data["_equip_enhances"] = {}

            rewards = {"stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0},
                       "coins": 0, "equipment": []}

            embed = _dungeon_header_embed(floor, display_name, pdata, npc_data, extra_msg)

            run_id = str(time.time())
            session = {
                "player_pdata": pdata,
                "npc_pdata": npc_data,
                "npc_name": npc_data["name"],
                "player_name": display_name,
                "floor": floor,
                "flags": {"turn_count": 0},
                "accumulated_rewards": rewards,
                "_run_id": run_id,
            }
            self.sessions[sid] = session

            view = DungeonView(self, sid, floor, pdata, npc_data, display_name, rewards, run_id)

            if isinstance(ctx_or_int, commands.Context):
                msg = await ctx_or_int.reply(embed=embed, view=view)
            elif ctx_or_int.response.is_done():
                await ctx_or_int.edit_original_response(embed=embed, view=view)
                msg = await ctx_or_int.original_response()
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
                msg = await ctx_or_int.original_response()
            session["_message"] = msg
        finally:
            await db.close()

    def _npc_ai_move(self, npc: dict) -> str:
        hp_pct = npc["hp"] / max(npc["hp_max"], 1) * 100
        if hp_pct < 30:
            return random.choices(["attack", "special", "defense"], weights=[35, 25, 40])[0]
        elif hp_pct < 60:
            return random.choices(["attack", "special", "defense"], weights=[35, 30, 35])[0]
        else:
            return random.choices(["attack", "special", "defense"], weights=[40, 35, 25])[0]

    async def _handle_dungeon_fight(self, interaction: discord.Interaction, view: DungeonView):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session:
            await self._recover_dungeon(interaction, sid)
            return
        if view.finished:
            await interaction.followup.send("🤷 Trận đã kết thúc!", ephemeral=True)
            return
        await self._execute_dungeon_turn(interaction, session, view, "attack")

    async def _handle_dungeon_move(self, interaction: discord.Interaction,
                                    view: DungeonView, move_type: str):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session:
            await self._recover_dungeon(interaction, sid)
            return
        if view.finished:
            await interaction.followup.send("🤷 Trận đã kết thúc!", ephemeral=True)
            return
        await self._execute_dungeon_turn(interaction, session, view, move_type)

    async def _recover_dungeon(self, interaction: discord.Interaction, sid: str):
        db = await get_db()
        try:
            dg = await (await db.execute("SELECT checkpoint FROM dungeon_progress WHERE player_id=?", (sid,))).fetchone()
            if dg:
                floor = dg[0] + 1
                await self._start_dungeon_floor(interaction, sid, interaction.user.display_name, floor, "\n🔄 Khôi phục phiên!")
            else:
                await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
        finally:
            await db.close()

    async def _execute_dungeon_turn(self, interaction: discord.Interaction,
                                     session: dict, view: DungeonView,
                                     player_move_type: str):
        flags = session["flags"]

        # Prevent concurrent turns (double-click guard)
        if flags.get("_turn_in_progress"):
            await interaction.followup.send("⏳ Đợi lượt trước xử lý xong đã!", ephemeral=True)
            return
        flags["_turn_in_progress"] = True

        player = session["player_pdata"]
        npc = session["npc_pdata"]
        result_lines = []

        if player_move_type == "basic":
            skill_id = 1
        else:
            cat = "defense" if player_move_type == "defense" else player_move_type
            cd_key = f"{cat}_cd"
            if player.get(cd_key, 0) > 0:
                sk = get_equipped_skill(player, cat)
                await interaction.followup.send(
                    f"⏳ **{sk['name']}** đang hồi! Còn **{player[cd_key]}** turn.", ephemeral=True)
                flags.pop("_turn_in_progress", None)
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
            flags.pop("_turn_in_progress", None)
            await self._finish_dungeon_floor(interaction, session, view, player["hp"] > 0, result_lines)
            return

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

        embed = _dungeon_battle_embed(
            session["floor"], session["player_name"], player, npc, result_lines
        )
        new_view = DungeonView(self, view.player_id, session["floor"],
                                player, npc, session["player_name"],
                                session["accumulated_rewards"],
                                session.get("_run_id", ""))
        await session["_message"].edit(embed=embed, view=new_view)
        flags.pop("_turn_in_progress", None)

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
                await db.execute(
                    "UPDATE dungeon_progress SET checkpoint=MAX(checkpoint, ?) WHERE player_id=?",
                    (floor, sid))
                await db.commit()
            finally:
                await db.close()

            # Heal between floors: 50% after boss, 25% after regular
            player = session["player_pdata"]
            eff = get_effective_stats(player)
            heal_pct = 50 if floor % 10 == 0 else 25
            heal_amt = int(eff["hp_max"] * heal_pct / 100)
            player["hp"] = min(eff["hp_max"], player.get("hp", 0) + heal_amt)
            result_lines.append(f"💚 Hồi {heal_pct}% HP (+{heal_amt}) sau tầng {floor}!")

            next_floor = floor + 1
            if next_floor > DUNGEON_MAX_FLOOR:
                result_lines.append(f"\n🎉 HOÀN THÀNH 100 TẦNG! Nhận hết thưởng!")
                await self._collect_rewards(interaction, session, sid, result_lines)
                self.sessions.pop(sid, None)
                return

            result_lines.append(f"\n🎯 Sẵn sàng tầng **{next_floor}**!")
            result_lines.append(f"💎 Tích lũy: {acc['coins']}🪙 | Sơ:{acc['stones']['stone_basic']} Trung:{acc['stones']['stone_medium']} Cao:{acc['stones']['stone_advanced']}")

            npc_data = generate_dungeon_npc(next_floor)
            npc_data["equipped"] = {}
            npc_data["_equip_items"] = {}
            npc_data["_equip_enhances"] = {}

            session["floor"] = next_floor
            session["npc_pdata"] = npc_data
            session["npc_name"] = npc_data["name"]
            session["flags"] = {"turn_count": 0}

            embed = _dungeon_battle_embed(next_floor, session["player_name"], player, npc_data, result_lines)

            new_view = DungeonView(self, sid, next_floor, player, npc_data,
                                    session["player_name"], acc,
                                    session.get("_run_id", ""))
            await session["_message"].edit(embed=embed, view=new_view)
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

            if acc["coins"] > 0:
                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (acc["coins"], sid))

            for eq in acc["equipment"]:
                await db.execute(
                    "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                    (sid, eq["eid"]))

            await db.commit()

        finally:
            await db.close()

        floor = session.get("floor", 0)
        embed = _dungeon_reward_embed(acc, floor, "Nhận Thưởng Bí Cảnh")
        await session["_message"].edit(embed=embed, view=None)

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        elif ctx_or_int.response.is_done():
            await ctx_or_int.followup.send(msg, ephemeral=ephemeral)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(DungeonCog(bot))
