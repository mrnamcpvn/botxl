import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import random
import asyncio
from bot.database import get_db
from bot.config import (
    WORLD_BOSS_HOURS, WORLD_BOSS_REGISTER_TIME,
    WORLD_BOSS_RESPAWN_DELAY, WORLD_BOSS_CHANNEL_ID,
    WORLD_BOSS_ATTACK_INTERVAL,
)
from bot.engine.battle import get_effective_stats
from bot.engine.rewards import _EQUIP_BY_STAR
from bot.data.equipment import EQUIPMENT, STAR_LABELS
from bot.data.skills import SKILLS_DB
from bot.utils.player_loader import load_player_full
from bot.logger import logger

STONE_NAMES = {
    "stone_basic": "Đá Sơ Cấp",
    "stone_medium": "Đá Trung Cấp",
    "stone_advanced": "Đá Cao Cấp",
}


def _get_skill_labels(pdata: dict) -> dict:
    """Lấy icon + tên skill cho 3 slot attack/special/defense."""
    result = {}
    for cat in ("attack", "special", "defense"):
        sid = pdata.get("skill_equipped", {}).get(cat, 1)
        sk = SKILLS_DB.get(sid, SKILLS_DB[1])
        result[cat] = {"icon": sk.get("icon", "❓"), "name": sk.get("name", cat)}
    return result

class WorldBoss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._current_id: int | None = None
        self._current_status: str | None = None
        self._reg_task: asyncio.Task | None = None
        self._fight_task: asyncio.Task | None = None
        self._boss_atk_task: asyncio.Task | None = None
        self._boss: dict | None = None
        # player state: {sid: {damage, deaths, cd_until, name, hp, hp_max}}
        self._players: dict[str, dict] = {}
        self._ranking_msg: discord.Message | None = None
        self._last_hour: int | None = None
        # Lock để tránh race condition khi nhiều player đánh boss cùng lúc
        self._action_lock = asyncio.Lock()
        # Event báo boss đã chết
        self._boss_dead = asyncio.Event()
        # ID người giết boss
        self._killer_id: str | None = None

    async def cog_load(self):
        asyncio.create_task(self._init_on_ready())

    async def _init_on_ready(self):
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, status, channel_id, boss_level, boss_hp, boss_hp_max, "
                "boss_atk_min, boss_atk_max, boss_def FROM world_boss "
                "WHERE status IN ('registering','fighting') ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                if r["status"] == "registering":
                    await db.execute(
                        "UPDATE world_boss SET status='cancelled' WHERE id=?", (r["id"],))
                    await db.commit()
                elif r["status"] == "fighting":
                    self._current_id = r["id"]
                    self._current_status = "fighting"
                    self._boss = {
                        "id": "boss", "name": "🐉 Boss Thế Giới",
                        "level": r["boss_level"],
                        "hp": r["boss_hp"], "hp_max": r["boss_hp_max"],
                        "attack_min": r["boss_atk_min"],
                        "attack_max": r["boss_atk_max"],
                        "defense": r["boss_def"],
                        "crit": 5, "pierce": 10,
                        "_npc_override": True,
                        "class_id": "trumcuoi",
                    }
                    pcursor = await db.execute(
                        "SELECT player_id, total_damage, deaths, death_cooldown_until "
                        "FROM world_boss_participants WHERE boss_id=?", (r["id"],))
                    async for p in pcursor:
                        nrow = await (await db.execute(
                            "SELECT name, hp, hp_max FROM players WHERE id=?", (p[0],))).fetchone()
                        self._players[p[0]] = {
                            "damage": p[1], "deaths": p[2], "cd_until": p[3],
                            "name": nrow["name"] if nrow else p[0],
                            "hp": nrow["hp"] if nrow else 100,
                            "hp_max": nrow["hp_max"] if nrow else 100,
                        }
                    ch = self.bot.get_channel(int(r["channel_id"]))
                    if ch:
                        self._fight_task = asyncio.create_task(
                            self._resume_fight_loop(r["id"], ch))
        except Exception as e:
            logger.error(f"[WORLDBOSS] _init_on_ready lỗi: {e}", exc_info=True)
        finally:
            await db.close()
        self._auto_schedule.start()

    async def cog_unload(self):
        self._auto_schedule.cancel()
        for t in [self._reg_task, self._fight_task, self._boss_atk_task]:
            if t:
                t.cancel()

    @tasks.loop(seconds=60)
    async def _auto_schedule(self):
        now = time.localtime()
        h, m = now.tm_hour, now.tm_min
        if self._current_status is not None:
            return
        if h not in WORLD_BOSS_HOURS:
            return
        if self._last_hour == h or m > 5:
            return
        self._last_hour = h
        ch = self.bot.get_channel(WORLD_BOSS_CHANNEL_ID)
        if ch:
            await self.start_boss(ch)

    async def start_boss(self, channel: discord.TextChannel):
        if self._current_status is not None:
            return
        db = await get_db()
        try:
            cursor = await db.execute(
                "INSERT INTO world_boss (status, channel_id, started_at) VALUES ('registering', ?, ?)",
                (str(WORLD_BOSS_CHANNEL_ID), time.time()))
            await db.commit()
            self._current_id = cursor.lastrowid
        finally:
            await db.close()
        self._current_status = "registering"
        self._boss_dead.clear()
        self._reg_task = asyncio.create_task(
            self._registration_phase(channel.id, self._current_id))

    async def _registration_phase(self, channel_id: int, tid: int):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_boss(tid)
            return

        view = WorldBossJoinView(tid, channel_id)
        embed = self._build_reg_embed(view, WORLD_BOSS_REGISTER_TIME)
        msg = await ch.send(embed=embed, view=view)

        for remaining in range(WORLD_BOSS_REGISTER_TIME - 1, -1, -1):
            await asyncio.sleep(1)
            if self._current_status != "registering":
                return
            try:
                embed = self._build_reg_embed(view, remaining)
                await msg.edit(embed=embed)
            except Exception:
                pass

        view.stop()
        for child in view.children:
            child.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT player_id FROM world_boss_participants WHERE boss_id=?", (tid,))
            rows = await cursor.fetchall()
            ids = [r[0] for r in rows]
        finally:
            await db.close()

        if not ids:
            await msg.edit(content="❌ Không có ai đăng ký! Boss bỏ đi...", embed=None, view=None)
            await self._cancel_boss(tid)
            return

        self._current_status = "fighting"
        db = await get_db()
        try:
            await db.execute("UPDATE world_boss SET status='fighting' WHERE id=?", (tid,))
            await db.commit()
        finally:
            await db.close()

        self._fight_task = asyncio.create_task(self._fighting_phase(channel_id, tid, ids))

    def _build_reg_embed(self, view, remaining: int) -> discord.Embed:
        m, s = divmod(remaining, 60)
        count = len(view.participants)
        lines = [
            f"⏳ Đăng ký kết thúc sau: **{m}:{s:02d}**", "",
            f"👥 Đã đăng ký (**{count}**):",
        ]
        for name in list(view.participants.values())[:20]:
            lines.append(f"  • {name}")
        if count == 0:
            lines.append("  *(chưa có ai)*")
        lines.extend(["", "─" * 25, "Boss tự đánh định kỳ! Bấm nút để phản công!"])
        embed = discord.Embed(
            title="🐉 BOSS THẾ GIỚI XUẤT HIỆN!",
            description="\n".join(lines), color=0xff0000)
        embed.set_footer(text=f"ID: #{self._current_id} | Gây nhiều dmg = thưởng nhiều hơn")
        return embed

    async def _cancel_boss(self, tid: int):
        db = await get_db()
        try:
            await db.execute(
                "UPDATE world_boss SET status='cancelled', finished_at=? WHERE id=?",
                (time.time(), tid))
            await db.commit()
        finally:
            await db.close()
        self._current_id = None
        self._current_status = None
        self._boss = None
        self._players.clear()
        self._ranking_msg = None
        self._killer_id = None
        self._boss_dead.set()  # unlock bất kỳ waiter nào

    async def _fighting_phase(self, channel_id: int, tid: int, player_ids: list[str]):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_boss(tid)
            return
        try:
            # Load player data và tính boss stats
            max_level = 1
            for sid in player_ids:
                db = await get_db()
                try:
                    pdata = await load_player_full(db, sid)
                    if pdata is None:
                        continue
                    eff = get_effective_stats(pdata)
                    lvl = pdata.get("level", 1)
                    if lvl > max_level:
                        max_level = lvl
                    self._players[sid] = {
                        "damage": 0, "deaths": 0, "cd_until": 0,
                        "name": pdata.get("name", f"Player{sid[-4:]}"),
                        # Lưu HP trong state — không load lại từ DB mỗi lần
                        "hp": eff["hp_max"],
                        "hp_max": eff["hp_max"],
                        "pdata": pdata,  # cache để tính stats khi boss attack
                    }
                finally:
                    await db.close()

            n = len(player_ids)
            boss_level = max_level + 30
            # HP đủ cho 5-10 phút chiến đấu
            # Giả sử avg 800 dmg/đòn, đánh mỗi 2-3s → ~300 dmg/s/người
            # 7 phút = 420s × 300 dmg/s × n người = 126,000 HP/người
            boss_hp_max = n * 1200 * 100   # ≈ 120,000 HP/người
            boss_atk_min = boss_level * 5
            boss_atk_max = boss_level * 8
            boss_def = boss_level * 3

            self._boss = {
                "id": "boss", "name": "🐉 Boss Thế Giới",
                "level": boss_level,
                "hp": boss_hp_max, "hp_max": boss_hp_max,
                "attack_min": boss_atk_min, "attack_max": boss_atk_max,
                "defense": boss_def,
                "crit": 5, "pierce": 10,
                "_npc_override": True, "class_id": "trumcuoi",
            }
            self._boss_dead.clear()
            self._killer_id = None

            db = await get_db()
            try:
                await db.execute(
                    "UPDATE world_boss SET boss_level=?, boss_hp=?, boss_hp_max=?, "
                    "boss_atk_min=?, boss_atk_max=?, boss_def=? WHERE id=?",
                    (boss_level, boss_hp_max, boss_hp_max,
                     boss_atk_min, boss_atk_max, boss_def, tid))
                await db.commit()
            finally:
                await db.close()

            # Gửi boss embed công khai
            embed = self._build_boss_embed(tid)
            self._ranking_msg = await ch.send(embed=embed)

            # Gửi DM view cho từng player
            for sid in player_ids:
                ps = self._players.get(sid)
                if not ps:
                    continue
                try:
                    user = await self.bot.fetch_user(int(sid))
                    skill_labels = _get_skill_labels(ps.get("pdata", {}))
                    view = BossBattleView(self, sid, ps["name"], skill_labels)
                    pvt = await user.send(
                        embed=discord.Embed(
                            title="⚔️ Boss Thế Giới!",
                            description=(
                                f"❤️ `{ps['hp']}/{ps['hp_max']}`\n"
                                "Dùng 3 nút bên dưới để chiến đấu!"
                            ),
                            color=0xff0000),
                        view=view)
                    view.message = pvt
                    ps["view"] = view
                except Exception:
                    pass

            # Boss tự attack định kỳ
            self._boss_atk_task = asyncio.create_task(self._boss_auto_attack_loop())

            # Chờ boss chết hoặc bị hủy
            await self._boss_dead.wait()

            if self._boss and self._boss["hp"] <= 0:
                await self._finish_boss(tid, ch, self._killer_id)

        except asyncio.CancelledError:
            await self._cancel_boss(tid)
        except Exception as e:
            logger.error(f"[WORLDBOSS] _fighting_phase lỗi: {e}", exc_info=True)
            await self._cancel_boss(tid)
            try:
                await ch.send("⚠️ Boss gặp lỗi và đã bị hủy!")
            except Exception:
                pass
        finally:
            if self._boss_atk_task:
                self._boss_atk_task.cancel()
                self._boss_atk_task = None
            self._current_id = None
            self._current_status = None

    async def _boss_auto_attack_loop(self):
        """Boss tự tấn công 1 player ngẫu nhiên mỗi WORLD_BOSS_ATTACK_INTERVAL giây."""
        try:
            while True:
                await asyncio.sleep(WORLD_BOSS_ATTACK_INTERVAL)
                if self._boss is None or self._boss["hp"] <= 0:
                    break
                # Chọn target còn sống (không trong cooldown)
                alive = [sid for sid, ps in self._players.items()
                         if ps.get("cd_until", 0) <= time.time() and ps.get("hp", 0) > 0]
                if alive:
                    target = random.choice(alive)
                    await self._boss_attack(target)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[WORLDBOSS] boss_auto_attack_loop lỗi: {e}", exc_info=True)

    async def _process_player_action(self, user_id: str, action_type: str,
                                     view: "BossBattleView",
                                     interaction: discord.Interaction):
        """Xử lý hành động của player. Dùng Lock để tránh race condition."""
        async with self._action_lock:
            # Kiểm tra boss còn sống không — bên trong lock để chắc chắn
            if self._boss is None or self._boss["hp"] <= 0:
                return  # Xử lý UI bên ngoài lock

            ps = self._players.get(user_id)
            if not ps:
                return

            # Kiểm tra CD skill
            skill_cd_key = f"skill_cd_{action_type}"
            cd_until = ps.get(skill_cd_key, 0)
            if cd_until > time.time():
                remaining = int(cd_until - time.time())
                # Trả về flag CD để xử lý bên ngoài lock
                return ("cd", remaining)

            pdata = ps.get("pdata")
            if pdata is None:
                return

            eff = get_effective_stats(pdata)
            atk_min = eff["attack_min"]
            atk_max = eff["attack_max"]

            # Basic attack — skill_id=1, không CD
            if action_type == "basic":
                skill_id = 1
                skill = SKILLS_DB[1]
                skill_cd_key = None
                skill_cooldown_sec = 0
            else:
                # Lấy skill đang equipped — fallback về skill mặc định
                _default_skills = {"attack": 1, "special": 5, "defense": 10}
                skill_id = pdata.get("skill_equipped", {}).get(
                    action_type, _default_skills.get(action_type, 1))
                skill = SKILLS_DB.get(skill_id, SKILLS_DB[1])
                # Set CD cho skill này (dùng cooldown từ SKILLS_DB, tối thiểu 2s real-time)
                skill_cooldown_sec = max(2, skill.get("cooldown", 0) * 3)  # mỗi CD = 3 giây real-time
                skill_cd_key = f"skill_cd_{action_type}"
                ps[skill_cd_key] = time.time() + skill_cooldown_sec

            mult = skill.get("multiplier", 1.0)

            # Tính base damage
            base_dmg = int(random.randint(atk_min, atk_max) * mult)

            # Pierce
            boss_def = self._boss["defense"]
            equip_pierce = eff.get("pierce", 0)
            if equip_pierce > 0:
                boss_def = int(boss_def * (100 - min(equip_pierce, 35)) / 100)
            damage = max(base_dmg // 4, base_dmg - boss_def)

            # Crit
            crit_pct = eff.get("crit", 0)
            is_crit = crit_pct > 0 and random.random() * 100 < crit_pct
            if is_crit:
                damage = int(damage * 1.5)

            # Damage pct passive
            dmg_pct = eff.get("damage_pct", 0)
            if dmg_pct > 0:
                damage = int(damage * (1 + dmg_pct / 100))

            damage = max(1, damage)

            # Giảm HP boss
            self._boss["hp"] = max(0, self._boss["hp"] - damage)
            ps["damage"] = ps.get("damage", 0) + damage
            crit_tag = " 💥CRIT!" if is_crit else ""
            boss_dead = self._boss["hp"] <= 0

            if boss_dead:
                self._boss["hp"] = 0
                self._killer_id = user_id
                self._boss_dead.set()
                return ("boss_dead", damage, crit_tag, skill_cd_key, skill_cooldown_sec)

            return ("hit", damage, crit_tag, skill_cd_key, skill_cooldown_sec)

    async def _handle_player_action(self, user_id: str, action_type: str,
                                    view: "BossBattleView",
                                    interaction: discord.Interaction):
        """Wrapper gọi _process_player_action rồi xử lý UI."""
        # Kiểm tra boss trước khi vào lock
        if self._boss is None or self._boss["hp"] <= 0:
            try:
                for child in view.children:
                    child.disabled = True
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="💀 Boss đã bị hạ rồi!",
                        description="Trận chiến đã kết thúc.",
                        color=0x888888),
                    view=view)
            except Exception:
                pass
            return

        result = await self._process_player_action(user_id, action_type, view, interaction)

        ps = self._players.get(user_id, {})

        if result is None:
            return

        if result[0] == "cd":
            remaining = result[1]
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="⚔️ Đánh Boss!",
                        description=(
                            f"❤️ `{ps.get('hp', 0)}/{ps.get('hp_max', 1)}`\n"
                            f"⏳ Skill đang hồi chiêu! Còn **{remaining}s**"
                        ),
                        color=0xffaa00),
                    view=view)
            except Exception:
                pass
            return

        if result[0] == "boss_dead":
            _, damage, crit_tag, skill_cd_key, _ = result
            # Disable tất cả views ngay lập tức
            for sid, p in self._players.items():
                v = p.get("view")
                if v:
                    for child in v.children:
                        child.disabled = True
                    if v.message and sid != user_id:
                        try:
                            await v.message.edit(
                                embed=discord.Embed(
                                    title="☠️ BOSS ĐÃ BỊ HẠ!",
                                    description=f"🎉 **{ps.get('name','?')}** đã hạ boss!\nĐang tính thưởng...",
                                    color=0xffd700),
                                view=v)
                        except Exception:
                            pass
            # Thông báo cho người giết boss
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="☠️ BOSS ĐÃ BỊ HẠ!",
                        description=f"💥 Đòn cuối của bạn gây **{damage}** dmg!{crit_tag}\n🎉 Bạn đã hạ boss!\nĐang tính thưởng...",
                        color=0xffd700),
                    view=view)
            except Exception:
                pass
            # Ranking embed sẽ được update trong _finish_boss (chỉ 1 lần khi boss chết)
            return

        if result[0] == "hit":
            _, damage, crit_tag, skill_cd_key, skill_cooldown_sec = result
            player_hp_str = f"❤️ `{ps.get('hp', 0)}/{ps.get('hp_max', 1)}`"
            boss_pct = int(self._boss["hp"] / max(self._boss["hp_max"], 1) * 100)
            try:
                await interaction.edit_original_response(
                    embed=discord.Embed(
                        title="⚔️ Đánh Boss!",
                        description=(
                            f"{player_hp_str}\n"
                            f"💥 Gây **{damage}** dmg!{crit_tag}\n"
                            f"🐉 Boss còn **{boss_pct}%** HP\n"
                            f"⏳ Skill hồi sau **{skill_cooldown_sec}s**"
                        ),
                        color=0x00ff00),
                    view=view)
            except Exception:
                pass
            # Không update live ranking embed mỗi lần đánh — chỉ update khi boss chết

    async def _boss_attack(self, target_id: str):
        """Boss tấn công 1 player cụ thể, cập nhật HP trong state."""
        if self._boss is None or self._boss["hp"] <= 0:
            return
        ps = self._players.get(target_id)
        if not ps or ps.get("hp", 0) <= 0:
            return

        hp_max = ps["hp_max"]
        dmg = random.randint(self._boss["attack_min"], self._boss["attack_max"])
        if random.random() * 100 < self._boss.get("crit", 0):
            dmg = int(dmg * 1.5)

        # Lấy defense từ cached pdata
        pdata = ps.get("pdata", {})
        eff = get_effective_stats(pdata) if pdata else {}
        defense = eff.get("defense", 0)
        pierce = self._boss.get("pierce", 0)
        if pierce > 0:
            defense = int(defense * (100 - pierce) / 100)
        final_dmg = max(dmg // 4, dmg - defense)

        ps["hp"] = max(0, ps["hp"] - final_dmg)
        dead = ps["hp"] <= 0

        if dead:
            ps["hp"] = 0
            ps["cd_until"] = time.time() + WORLD_BOSS_RESPAWN_DELAY
            ps["deaths"] = ps.get("deaths", 0) + 1
            # Sau respawn delay — tự hồi sinh
            asyncio.create_task(self._respawn_player(target_id))

        target_view = ps.get("view")
        if target_view and target_view.message:
            try:
                if dead:
                    for child in target_view.children:
                        child.disabled = True
                    desc = (f"🐉 Boss tấn công **{final_dmg}** dmg!\n"
                            f"💀 Bạn đã chết! Hồi sinh sau **{WORLD_BOSS_RESPAWN_DELAY}s**...")
                    color = 0xff0000
                else:
                    desc = (f"🐉 Boss tấn công **{final_dmg}** dmg!\n"
                            f"❤️ `{ps['hp']}/{hp_max}`")
                    color = 0xffaa00
                await target_view.message.edit(
                    embed=discord.Embed(
                        title="⚔️ Đánh Boss!",
                        description=desc, color=color),
                    view=target_view)
            except Exception:
                pass

    async def _respawn_player(self, player_id: str):
        """Tự hồi sinh player sau respawn delay, re-enable buttons."""
        await asyncio.sleep(WORLD_BOSS_RESPAWN_DELAY)
        ps = self._players.get(player_id)
        if not ps or self._boss is None or self._boss["hp"] <= 0:
            return
        ps["hp"] = ps["hp_max"]
        ps["cd_until"] = 0

        target_view = ps.get("view")
        if target_view and target_view.message:
            try:
                for child in target_view.children:
                    child.disabled = False
                await target_view.message.edit(
                    embed=discord.Embed(
                        title="⚔️ Đánh Boss!",
                        description=f"✅ Đã hồi sinh!\n❤️ `{ps['hp']}/{ps['hp_max']}`",
                        color=0x00ff00),
                    view=target_view)
            except Exception:
                pass

    def _build_boss_embed(self, tid: int) -> discord.Embed:
        if self._boss is None:
            return discord.Embed(title="🐉 Boss Thế Giới", description="Đang tải...", color=0xff0000)
        hp = max(0, self._boss["hp"])
        hp_max = self._boss["hp_max"]
        pct = hp / max(hp_max, 1) * 100
        bar_len = 12
        filled = max(0, min(bar_len, round(pct / 100 * bar_len)))
        hp_bar = "🟥" * filled + "⬛" * (bar_len - filled)

        # Thống kê thời gian chưa hoàn thành (tính từ damage đã gây)
        total_dmg = sum(ps.get("damage", 0) for ps in self._players.values())
        dmg_pct = total_dmg / max(hp_max, 1) * 100

        lines = [
            f"**Level:** {self._boss['level']}  ·  ❤️ `{hp:,}/{hp_max:,}` ({pct:.1f}%)".replace(",", "."),
            hp_bar,
            f"💥 Tổng dmg đã gây: `{total_dmg:,}` ({dmg_pct:.1f}%)".replace(",", "."),
            "",
            "🏆 **BẢNG XẾP HẠNG SÁT THƯƠNG:**",
        ]

        sorted_p = sorted(self._players.items(), key=lambda x: x[1]["damage"], reverse=True)
        total_players = len(sorted_p)

        for rank, (sid, ps) in enumerate(sorted_p, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"**{rank}.**")
            dmg = ps.get("damage", 0)
            d_str = f" {ps['deaths']}💀" if ps.get("deaths", 0) > 0 else ""
            cd_tag = " ⏳" if ps.get("cd_until", 0) > time.time() else ""

            # Phần thưởng dự kiến
            rw_preview = self._calc_boss_reward(rank, total_players)
            coins = rw_preview.get("coins", 0)
            stones = rw_preview.get("stones")
            equips = rw_preview.get("equips", [])
            rw_parts = [f"💰~{coins}🪙"]
            if stones:
                stone_abbr = {"stone_basic": "SC", "stone_medium": "TC", "stone_advanced": "CC"}
                rw_parts.append(f"💎×{stones[1]}{stone_abbr.get(stones[0], '')}")
            star_icons = {2: "🟢", 3: "🟡", 4: "🟣", 5: "🔴", 6: "💗"}
            for equip_star, equip_count in equips:
                rw_parts.append(f"⚒️{star_icons.get(equip_star,'⭐')}×{equip_count}")
            rw_str = f" _({' '.join(rw_parts)})_"

            lines.append(
                f"{medal} **{ps['name']}**{cd_tag} — `{dmg:,}` dmg{d_str}{rw_str}".replace(",", ".")
            )

        if not sorted_p:
            lines.append("  *(đang tải...)*")

        embed = discord.Embed(
            title=f"🐉 BOSS THẾ GIỚI #{tid}",
            description="\n".join(lines), color=0xff0000)
        embed.set_footer(text="💡 Gây nhiều dmg = thưởng tốt hơn | ⚔️ Người kết liễu boss nhận thêm 1 trang bị 5★")
        return embed

    async def _finish_boss(self, tid: int, ch: discord.TextChannel, killer_id: str | None = None):
        sorted_p = sorted(self._players.items(), key=lambda x: x[1]["damage"], reverse=True)
        rewards = [
            (sid, rank, self._calc_boss_reward(rank, len(sorted_p)), ps.get("name", "?"))
            for rank, (sid, ps) in enumerate(sorted_p, 1)
        ]
        reward_summaries = await self._apply_boss_rewards(tid, rewards, killer_id)

        lines = [f"💀 **BOSS THẾ GIỚI #{tid} ĐÃ BỊ HẠ!**\n",
                 f"🐉 Lv.{self._boss['level']} | HP: {self._boss['hp_max']:,}".replace(",", "."), ""]
        if killer_id and killer_id in self._players:
            killer_name = self._players[killer_id].get("name", "???")
            lines.append(f"⚔️ **Người kết liễu:** {killer_name} _(+1 trang bị 5★ thưởng thêm)_\n")
        for sid, rank, rw, name in rewards[:10]:
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
            ps = self._players.get(sid, {})
            line = f"{medal} **{name}** — {ps.get('damage', 0)} dmg"
            if sid in reward_summaries:
                line += f"\n{reward_summaries[sid]}"
            lines.append(line)
        lines.append(f"\n👥 **{len(sorted_p)}** người tham gia — Cảm ơn đã chiến đấu!")

        full = "\n".join(lines)
        if len(full) > 3800:
            full = full[:3800] + "\n_...còn nữa_"

        # Update ranking embed công khai
        embed = discord.Embed(title="🐉 Boss Thế Giới Đã Bị Hạ!", description=full, color=0x00ff00)
        if self._ranking_msg:
            try:
                await self._ranking_msg.edit(embed=embed)
            except Exception:
                await ch.send(embed=embed)
        else:
            await ch.send(embed=embed)

        # Gửi DM phần thưởng + disable view cho từng player
        for sid, rank, rw, name in rewards:
            ps = self._players.get(sid, {})
            summary = reward_summaries.get(sid, "")
            v = ps.get("view")
            rank_str = {1: "🥇 Hạng 1", 2: "🥈 Hạng 2", 3: "🥉 Hạng 3"}.get(rank, f"Hạng {rank}")
            dm_embed = discord.Embed(
                title="🏆 Trận Boss Kết Thúc!",
                description=(
                    f"**{rank_str}** với **{ps.get('damage', 0)}** dmg\n\n"
                    f"**🎁 Phần thưởng của bạn:**\n{summary}" if summary
                    else f"**{rank_str}** với **{ps.get('damage', 0)}** dmg\n\n_Không có phần thưởng đặc biệt_"
                ),
                color=0xffd700 if rank <= 3 else 0x00ff88,
            )
            if v and v.message:
                try:
                    for child in v.children:
                        child.disabled = True
                    await v.message.edit(embed=dm_embed, view=v)
                except Exception:
                    pass

        db = await get_db()
        try:
            await db.execute(
                "UPDATE world_boss SET status='done', boss_hp=0, finished_at=? WHERE id=?",
                (time.time(), tid))
            await db.commit()
        finally:
            await db.close()

        self._boss = None
        self._players.clear()
        self._ranking_msg = None

    def _calc_boss_reward(self, rank: int, total: int) -> dict:
        """
        Bảng thưởng theo rank:
        Top 1  : 1.000🪙 · 700XP · 3 Đá Cao Cấp · 1 trang bị 5★
        Top 2  : 800🪙  · 550XP · 2 Đá Cao Cấp · 2 trang bị 4★
        Top 3  : 600🪙  · 400XP · 3 Đá Trung Cấp · 1 trang bị 4★
        Top 4-5: 450🪙  · 280XP · 2 Đá Trung Cấp · 2 trang bị 3★
        Top 6-10: 300🪙 · 160XP · 1 trang bị random 2-3★
        Top 11+: 150🪙  · 60XP
        (+ người kết liễu boss nhận thêm 1 trang bị 5★, xử lý riêng trong _apply_boss_rewards)
        """
        if rank == 1:
            return {
                "coins": random.randint(900, 1100), "xp": 700,
                "stones": ("stone_advanced", random.randint(3, 5)),
                "equips": [(5, 1)],          # [(star, count)]
            }
        elif rank == 2:
            return {
                "coins": random.randint(700, 900), "xp": 550,
                "stones": ("stone_advanced", random.randint(2, 3)),
                "equips": [(4, 2)],
            }
        elif rank == 3:
            return {
                "coins": random.randint(500, 700), "xp": 400,
                "stones": ("stone_medium", random.randint(3, 5)),
                "equips": [(4, 1)],
            }
        elif rank <= 5:
            return {
                "coins": random.randint(400, 500), "xp": random.randint(250, 300),
                "stones": ("stone_medium", random.randint(1, 2)),
                "equips": [(3, 2)],
            }
        elif rank <= 10:
            # 1 trang bị random 2 hoặc 3 sao
            star = random.choice([2, 3])
            return {
                "coins": random.randint(250, 350), "xp": random.randint(130, 180),
                "equips": [(star, 1)],
            }
        else:
            return {"coins": random.randint(100, 200), "xp": 60}

    async def _apply_boss_rewards(self, tid: int, rewards: list,
                                   killer_id: str | None = None) -> dict[str, str]:
        summaries: dict[str, str] = {}
        db = await get_db()
        try:
            for pid, rank, rw, name in rewards:
                coins = rw.get("coins", 0)
                xp = rw.get("xp", 0)
                # Đảm bảo player tồn tại trước khi UPDATE
                prow = await (await db.execute(
                    "SELECT id FROM players WHERE id=?", (pid,))).fetchone()
                if not prow:
                    logger.warning(f"[WORLDBOSS] _apply_boss_rewards: player {pid} không tồn tại, bỏ qua")
                    continue

                await db.execute(
                    "UPDATE players SET coins=coins+?, xp=xp+? WHERE id=?", (coins, xp, pid))
                logger.info(f"[WORLDBOSS] Cộng thưởng {pid} ({name}): +{coins}🪙 +{xp}XP (rank {rank})")
                lines = [f"  • +{coins}🪙 · +{xp}XP"]

                from bot.config import GEM_TYPES
                give_gem = True
                if rank <= 3:
                    gl = random.randint(1, 3)
                elif rank <= 5:
                    gl = random.randint(1, 2)
                else:
                    if random.random() > 0.5:
                        give_gem = False
                    gl = 1
                if give_gem:
                    gt = random.choice(list(GEM_TYPES.keys()))
                    await db.execute(
                        "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                        "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                        (pid, gt, gl))
                    lines.append(f"  • 💎 {GEM_TYPES[gt]['name']} C{gl}")

                # Stones
                stones = rw.get("stones")
                if stones:
                    stype, sqty = stones
                    if stype not in ("stone_basic", "stone_medium", "stone_advanced"):
                        logger.error(f"[WORLDBOSS] stone type không hợp lệ: {stype}")
                    else:
                        await db.execute(
                            "INSERT OR IGNORE INTO player_enhance_stones "
                            "(player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, 0, 0, 0)",
                            (pid,))
                        await db.execute(
                            f"UPDATE player_enhance_stones SET {stype}={stype}+? WHERE player_id=?",
                            (sqty, pid))
                        lines.append(f"  • +{sqty} {STONE_NAMES.get(stype, stype)}")
                        logger.info(f"[WORLDBOSS]   +{sqty} {stype} cho {pid}")

                # Equipment list: [(star, count), ...]
                equips = rw.get("equips", [])
                for equip_star, equip_count in equips:
                    eids = _EQUIP_BY_STAR.get(equip_star, [])
                    if not eids:
                        logger.warning(f"[WORLDBOSS] Không có equipment {equip_star}★ trong _EQUIP_BY_STAR")
                        continue
                    for _ in range(equip_count):
                        eid = random.choice(eids)
                        await db.execute(
                            "INSERT INTO player_equipment "
                            "(player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                            (pid, eid))
                        eq_name = EQUIPMENT.get(eid, {}).get("name", f"ID:{eid}")
                        lines.append(f"  • {STAR_LABELS.get(equip_star,'⭐')} **{eq_name}**")
                        logger.info(f"[WORLDBOSS]   Trang bị {equip_star}★ {eq_name} (id={eid}) cho {pid}")

                # Killer bonus: +1 trang bị 5★
                if pid == killer_id:
                    killer_eids = _EQUIP_BY_STAR.get(5, [])
                    if killer_eids:
                        eid = random.choice(killer_eids)
                        await db.execute(
                            "INSERT INTO player_equipment "
                            "(player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                            (pid, eid))
                        eq_name = EQUIPMENT.get(eid, {}).get("name", f"ID:{eid}")
                        lines.append(f"  • ⚔️ **BONUS KẾT LIỄU:** {STAR_LABELS.get(5,'🔴')} **{eq_name}**")
                        logger.info(f"[WORLDBOSS]   Killer bonus 5★ {eq_name} (id={eid}) cho {pid}")

                await db.execute(
                    "INSERT OR IGNORE INTO world_boss_participants (boss_id, player_id) VALUES (?, ?)",
                    (tid, pid))
                await db.execute(
                    "UPDATE world_boss_participants "
                    "SET reward_given=1, final_rank=?, total_damage=? WHERE boss_id=? AND player_id=?",
                    (rank, self._players.get(pid, {}).get("damage", 0), tid, pid))
                summaries[pid] = "\n".join(lines)

            await db.commit()
            logger.info(f"[WORLDBOSS] _apply_boss_rewards hoàn tất, đã commit {len(summaries)} người")
        except Exception as e:
            logger.error(f"[WORLDBOSS] _apply_boss_rewards lỗi: {e}", exc_info=True)
        finally:
            await db.close()
        return summaries

    async def _resume_fight_loop(self, tid: int, ch: discord.TextChannel):
        """Resume sau bot restart."""
        try:
            embed = self._build_boss_embed(tid)
            self._ranking_msg = await ch.send(embed=embed)
            for sid, ps in self._players.items():
                try:
                    user = await self.bot.fetch_user(int(sid))
                    skill_labels = _get_skill_labels(ps.get("pdata", {}))
                    view = BossBattleView(self, sid, ps.get("name", "?"), skill_labels)
                    pvt = await user.send(
                        embed=discord.Embed(
                            title="⚔️ Boss vẫn còn sống!",
                            description=f"❤️ `{ps['hp']}/{ps['hp_max']}`\nTiếp tục chiến đấu!",
                            color=0xff0000),
                        view=view)
                    view.message = pvt
                    ps["view"] = view
                except Exception:
                    pass
            self._boss_atk_task = asyncio.create_task(self._boss_auto_attack_loop())
            await self._boss_dead.wait()
            if self._boss and self._boss["hp"] <= 0:
                await self._finish_boss(tid, ch, self._killer_id)
        except asyncio.CancelledError:
            await self._cancel_boss(tid)
        except Exception as e:
            logger.error(f"[WORLDBOSS] _resume_fight_loop lỗi: {e}", exc_info=True)
            await self._cancel_boss(tid)
        finally:
            if self._boss_atk_task:
                self._boss_atk_task.cancel()
            self._current_id = None
            self._current_status = None

    @app_commands.command(name="boss", description="👑 Quản lý Boss Thế Giới (admin)")
    @app_commands.default_permissions(administrator=True)
    async def boss_admin(self, interaction: discord.Interaction, action: str):
        from bot.cogs.admin import ADMIN_IDS
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message("🚫", ephemeral=True)
            return
        action = action.lower()
        if action == "start":
            if self._current_status is not None:
                await interaction.response.send_message("⏳ Boss đang chạy rồi!", ephemeral=True)
                return
            await interaction.response.send_message("✅ Đang mở Boss Thế Giới...", ephemeral=True)
            ch = interaction.channel
            await self.start_boss(ch)
        elif action == "stop":
            if self._current_id is None:
                await interaction.response.send_message("🤷 Không có boss nào.", ephemeral=True)
                return
            tid = self._current_id
            if self._reg_task:   self._reg_task.cancel()
            if self._fight_task: self._fight_task.cancel()
            await self._cancel_boss(tid)
            await interaction.response.send_message("🛑 Đã hủy Boss.", ephemeral=True)
        elif action == "status":
            if self._current_id:
                hp = self._boss["hp"] if self._boss else 0
                hp_max = self._boss["hp_max"] if self._boss else 0
                await interaction.response.send_message(
                    f"📊 Boss #{self._current_id} — **{self._current_status}** | HP: {hp}/{hp_max}",
                    ephemeral=True)
            else:
                await interaction.response.send_message("📊 Không có boss nào đang chạy.", ephemeral=True)
        else:
            await interaction.response.send_message("Dùng: `start`, `stop`, `status`", ephemeral=True)

    @boss_admin.autocomplete("action")
    async def boss_action_autocomplete(self, interaction: discord.Interaction, current: str):
        opts = ["start", "stop", "status"]
        return [app_commands.Choice(name=o, value=o) for o in opts if current.lower() in o]

    @app_commands.command(name="wb", description="🐉 Bắt đầu Boss Thế Giới ngay (admin)")
    @app_commands.default_permissions(administrator=True)
    async def wb_start(self, interaction: discord.Interaction):
        """Lệnh nhanh để admin start boss bất kỳ lúc nào, không cần chọn action."""
        from bot.cogs.admin import ADMIN_IDS
        if str(interaction.user.id) not in ADMIN_IDS:
            await interaction.response.send_message("🚫", ephemeral=True)
            return

        if self._current_status is not None:
            status_msg = {
                "registering": f"⏳ Đang mở đăng ký Boss #{self._current_id}!",
                "fighting": f"⚔️ Boss #{self._current_id} đang chiến đấu! HP: {self._boss['hp']}/{self._boss['hp_max']}" if self._boss else "⚔️ Đang có boss chạy!",
            }.get(self._current_status, "⏳ Đang có boss chạy rồi!")
            await interaction.response.send_message(status_msg, ephemeral=True)
            return

        await interaction.response.send_message(
            "✅ **Boss Thế Giới** đang được triệu hồi...\n"
            f"📍 Kênh: <#{WORLD_BOSS_CHANNEL_ID}>",
            ephemeral=True)

        # Mở boss tại channel được cấu hình
        ch = self.bot.get_channel(WORLD_BOSS_CHANNEL_ID)
        if not ch:
            # Fallback: mở tại channel hiện tại nếu không tìm thấy channel cấu hình
            ch = interaction.channel
        await self.start_boss(ch)


class WorldBossJoinView(discord.ui.View):
    def __init__(self, boss_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.boss_id = boss_id
        self.channel_id = channel_id
        self.participants: dict[str, str] = {}

    @discord.ui.button(emoji="⚔️", label="Tham Gia", style=discord.ButtonStyle.danger,
                       custom_id="wb:join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid in self.participants:
            await interaction.response.send_message("🤷 Mày đã đăng ký rồi!", ephemeral=True)
            return
        db = await get_db()
        try:
            prow = await (await db.execute(
                "SELECT id, name FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await interaction.response.send_message(
                    "❌ Đăng ký trước đã: `!register`", ephemeral=True)
                return
            name = prow["name"] or interaction.user.display_name

            # Đảm bảo player có default skill slots trong DB (nếu chưa có)
            default_slots = {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            for slot, skill_id in default_slots.items():
                await db.execute(
                    "INSERT OR IGNORE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)",
                    (sid, slot, skill_id))
            # Đảm bảo player có skill 1 trong danh sách skills sở hữu
            await db.execute(
                "INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, 1)", (sid,))

            await db.execute(
                "INSERT OR IGNORE INTO world_boss_participants (boss_id, player_id) VALUES (?, ?)",
                (self.boss_id, sid))
            await db.commit()
        finally:
            await db.close()
        self.participants[sid] = name
        await interaction.response.send_message(
            f"✅ Đã đăng ký! ({len(self.participants)} người)", ephemeral=True)

    @discord.ui.button(emoji="❌", label="Rời", style=discord.ButtonStyle.secondary,
                       custom_id="wb:leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid not in self.participants:
            await interaction.response.send_message("🤷 Mày chưa đăng ký!", ephemeral=True)
            return
        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM world_boss_participants WHERE boss_id=? AND player_id=?",
                (self.boss_id, sid))
            await db.commit()
        finally:
            await db.close()
        del self.participants[sid]
        await interaction.response.send_message("👋 Đã rời.", ephemeral=True)


class BossBattleView(discord.ui.View):
    def __init__(self, cog: WorldBoss, user_id: str, user_name: str,
                 skill_labels: dict | None = None):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.user_name = user_name
        self.message: discord.Message | None = None

        # skill_labels: {"attack": {"icon": "💥", "name": "Cú Đấm Ba Que"}, ...}
        labels = skill_labels or {}
        atk  = labels.get("attack",  {"icon": "💥", "name": "Attack"})
        spc  = labels.get("special", {"icon": "🔥", "name": "Special"})
        dfs  = labels.get("defense", {"icon": "🛡️", "name": "Defense"})

        # Nút cơ bản — không bao giờ CD, luôn dùng được
        btn_basic = discord.ui.Button(
            emoji="👊",
            label="Cú Đấm Ba Que",
            style=discord.ButtonStyle.secondary,
            custom_id="wb:basic")
        btn_basic.callback = self._basic_cb
        self.add_item(btn_basic)

        btn_atk = discord.ui.Button(
            emoji=atk["icon"],
            label=atk["name"][:80],
            style=discord.ButtonStyle.red,
            custom_id="wb:atk")
        btn_atk.callback = self._atk_cb
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(
            emoji=spc["icon"],
            label=spc["name"][:80],
            style=discord.ButtonStyle.blurple,
            custom_id="wb:spc")
        btn_spc.callback = self._spc_cb
        self.add_item(btn_spc)

        btn_dfs = discord.ui.Button(
            emoji=dfs["icon"],
            label=dfs["name"][:80],
            style=discord.ButtonStyle.green,
            custom_id="wb:def")
        btn_dfs.callback = self._dfs_cb
        self.add_item(btn_dfs)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True

    async def _do_action(self, interaction: discord.Interaction, action_type: str):
        ps = self.cog._players.get(self.user_id)
        if not ps:
            await interaction.response.send_message("❌ Không tìm thấy dữ liệu!", ephemeral=True)
            return
        if ps.get("cd_until", 0) > time.time():
            remaining = int(ps["cd_until"] - time.time())
            await interaction.response.send_message(
                f"⏳ Đang chết, hồi sinh sau **{remaining}s**!", ephemeral=True)
            return
        if self.cog._boss is None or self.cog._boss.get("hp", 0) <= 0:
            await interaction.response.send_message("💀 Boss đã chết rồi!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.cog._handle_player_action(self.user_id, action_type, self, interaction)

    async def _basic_cb(self, interaction: discord.Interaction):
        await self._do_action(interaction, "basic")

    async def _atk_cb(self, interaction: discord.Interaction):
        await self._do_action(interaction, "attack")

    async def _spc_cb(self, interaction: discord.Interaction):
        await self._do_action(interaction, "special")

    async def _dfs_cb(self, interaction: discord.Interaction):
        await self._do_action(interaction, "defense")


async def setup(bot):
    await bot.add_cog(WorldBoss(bot))
