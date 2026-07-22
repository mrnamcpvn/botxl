import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import random
import json
import asyncio
from bot.database import get_db
from bot.config import (
    WORLD_BOSS_HOURS, WORLD_BOSS_REGISTER_TIME,
    WORLD_BOSS_RESPAWN_DELAY, WORLD_BOSS_CHANNEL_ID,
)
from bot.engine.battle import execute_action, get_effective_stats, calc_class_stat
from bot.engine.rewards import _EQUIP_BY_STAR
from bot.data.equipment import EQUIPMENT, STAR_LABELS
from bot.data.classes import CLASSES
from bot.utils.player_loader import load_player_full
from bot.logger import logger

STONE_NAMES = {"stone_basic": "Đá Sơ Cấp", "stone_medium": "Đá Trung Cấp", "stone_advanced": "Đá Cao Cấp"}


class WorldBoss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._current_id: int | None = None
        self._current_status: str | None = None
        self._reg_task: asyncio.Task | None = None
        self._fight_task: asyncio.Task | None = None
        self._boss: dict | None = None
        self._players: dict[str, dict] = {}
        self._ranking_msg: discord.Message | None = None
        self._last_hour: int | None = None

    async def cog_load(self):
        asyncio.create_task(self._init_on_ready())

    async def _init_on_ready(self):
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, status, channel_id, boss_level, boss_hp, boss_hp_max, "
                "boss_atk_min, boss_atk_max, boss_def FROM world_boss "
                "WHERE status IN ('registering', 'fighting') ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                self._current_id = r["id"]
                self._current_status = r["status"]
                logger.info(f"[WORLDBOSS] Resuming boss #{r['id']} ({r['status']})")
                if r["status"] == "registering":
                    await db.execute(
                        "UPDATE world_boss SET status='cancelled' WHERE id=?", (r["id"],))
                    await db.commit()
                    self._current_id = None
                    self._current_status = None
                elif r["status"] == "fighting":
                    self._boss = {
                        "id": "boss", "name": "🐉 Boss Thế Giới",
                        "level": r["boss_level"], "hp": r["boss_hp"], "hp_max": r["boss_hp_max"],
                        "attack_min": r["boss_atk_min"], "attack_max": r["boss_atk_max"],
                        "defense": r["boss_def"], "_npc_override": True,
                        "skill_equipped": {}, "buffs": {}, "class_id": "trumcuoi",
                    }
                    pcursor = await db.execute(
                        "SELECT player_id, total_damage, deaths, death_cooldown_until FROM world_boss_participants WHERE boss_id=?",
                        (r["id"],))
                    async for p in pcursor:
                        self._players[p[0]] = {"damage": p[1], "deaths": p[2], "cd_until": p[3]}
        except Exception as e:
            logger.error(f"[WORLDBOSS] _init_on_ready lỗi: {e}", exc_info=True)
        finally:
            await db.close()
        self._auto_schedule.start()

    async def cog_unload(self):
        self._auto_schedule.cancel()
        for t in [self._reg_task, self._fight_task]:
            if t:
                t.cancel()

    @tasks.loop(seconds=60)
    async def _auto_schedule(self):
        now = time.localtime()
        current_hour = now.tm_hour
        current_min = now.tm_min

        if self._current_status is not None:
            return
        if current_hour not in WORLD_BOSS_HOURS:
            return
        if self._last_hour == current_hour or current_min > 5:
            return

        self._last_hour = current_hour
        ch = self.bot.get_channel(WORLD_BOSS_CHANNEL_ID)
        if ch:
            await self.start_boss(ch)

    async def start_boss(self, channel: discord.TextChannel):
        if self._current_status is not None:
            return
        db = await get_db()
        try:
            cursor = await db.execute(
                "INSERT INTO world_boss (status, channel_id, boss_level, boss_hp, boss_hp_max, "
                "boss_atk_min, boss_atk_max, boss_def, started_at) "
                "VALUES ('registering', ?, 0, 0, 0, 0, 0, 0, ?)",
                (str(WORLD_BOSS_CHANNEL_ID), time.time()))
            await db.commit()
            self._current_id = cursor.lastrowid
        finally:
            await db.close()

        self._current_status = "registering"
        self._reg_task = asyncio.create_task(self._registration_phase(channel.id, self._current_id))

    async def _registration_phase(self, channel_id: int, tid: int):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_boss(tid)
            return

        view = WorldBossJoinView(tid, channel_id)

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT p.player_id, pl.name FROM world_boss_participants p "
                "JOIN players pl ON pl.id=p.player_id WHERE p.boss_id=?", (tid,))
            async for r in cursor:
                view.participants[r[0]] = r[1] or r[0]
        finally:
            await db.close()

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
        await msg.edit(view=view)

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT player_id FROM world_boss_participants WHERE boss_id=?", (tid,))
            rows = await cursor.fetchall()
            ids = [r[0] for r in rows]
        finally:
            await db.close()

        if not ids:
            await msg.edit(content="❌ Không có ai đăng ký! Boss bỏ đi rồi...", embed=None, view=None)
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
            f"⏳ Đăng ký kết thúc sau: **{m}:{s:02d}**",
            "",
            f"👥 Đã đăng ký (**{count}**):",
        ]
        for name in list(view.participants.values())[:20]:
            lines.append(f"  • {name}")
        if count == 0:
            lines.append("  *(chưa có ai)*")
        lines.extend(["", f"{'─' * 25}", "Boss auto-đánh, bạn tự chọn skill để đánh boss!"])
        embed = discord.Embed(
            title="🐉 BOSS THẾ GIỚI XUẤT HIỆN!",
            description="\n".join(lines),
            color=0xff0000,
        )
        embed.set_footer(text=f"ID: #{self._current_id} | ⚔️ Ra đòn càng nhiều thưởng càng cao")
        return embed

    async def _cancel_boss(self, tid: int):
        db = await get_db()
        try:
            await db.execute("UPDATE world_boss SET status='cancelled', finished_at=? WHERE id=?", (time.time(), tid))
            await db.commit()
        finally:
            await db.close()
        self._current_id = None
        self._current_status = None
        self._boss = None
        self._players.clear()

    async def _fighting_phase(self, channel_id: int, tid: int, player_ids: list[str]):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_boss(tid)
            return

        try:
            max_level = 1
            for sid in player_ids:
                db = await get_db()
                try:
                    prow = await (await db.execute("SELECT level, name FROM players WHERE id=?", (sid,))).fetchone()
                    if prow:
                        lvl = prow["level"]
                        if lvl > max_level:
                            max_level = lvl
                        self._players[sid] = {
                            "damage": 0, "deaths": 0, "cd_until": 0,
                            "name": prow["name"] or f"Player{sid[-4:]}",
                        }
                finally:
                    await db.close()

            boss_level = max_level + 30
            n = len(player_ids)
            boss_hp_max = int(80 * n * 200)
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
                "_npc_override": True,
                "skill_equipped": {}, "buffs": {},
                "class_id": "trumcuoi",
                "attack_cd": 0, "special_cd": 0, "defense_cd": 0,
            }

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

            embed = self._build_boss_embed(tid)
            self._ranking_msg = await ch.send(embed=embed)

            for sid in player_ids:
                try:
                    user = await self.bot.fetch_user(int(sid))
                    view = BossBattleView(self, sid, self._players[sid]["name"])
                    pvt = await user.send(
                        embed=discord.Embed(
                            title="⚔️ Đánh Boss!",
                            description="Dùng 3 nút bên dưới để đánh boss.\n"
                                        "💥 Attack | 🔥 Special | 🛡️ Defense",
                            color=0xff0000),
                        view=view)
                    view.message = pvt
                    self._players[sid]["view"] = view
                except Exception:
                    pass

            while True:
                await asyncio.sleep(1)
                if self._boss["hp"] <= 0:
                    break
                if self._current_status != "fighting":
                    return

            await self._finish_boss(tid, ch)
        except asyncio.CancelledError:
            await self._cancel_boss(tid)
        except Exception as e:
            logger.error(f"[WORLDBOSS] _fighting_phase lỗi: {e}", exc_info=True)
            await self._cancel_boss(tid)
            try:
                await ch.send(f"⚠️ Boss #{tid} gặp lỗi và đã bị hủy!")
            except Exception:
                pass
        finally:
            self._current_id = None
            self._current_status = None

    async def _process_player_action(self, user_id: str, user_name: str, action_type: str,
                                     view: BossBattleView, interaction: discord.Interaction):
        if self._boss is None or self._boss.get("hp", 0) <= 0:
            return

        db = await get_db()
        try:
            pdata = await load_player_full(db, user_id, reset_cd=False)
            if not pdata:
                return
        finally:
            await db.close()

        pdata["id"] = user_id
        pdata["name"] = user_name
        pdata["hp"] = pdata.get("hp", pdata.get("hp_max", 100))
        if pdata["hp"] <= 0:
            pdata["hp"] = pdata.get("hp_max", 100)

        eff = get_effective_stats(pdata)
        pdata["hp_max"] = eff["hp_max"]
        if pdata["hp"] > eff["hp_max"]:
            pdata["hp"] = eff["hp_max"]

        skill_id = 1
        slot = pdata.get("skill_equipped", {}).get(action_type)
        if slot:
            skill_id = slot

        prev_boss_hp = self._boss["hp"]
        flags: dict = {}
        result = await execute_action(pdata, self._boss, 0, {"type": action_type, "skill_id": skill_id}, flags)

        dmg_to_boss = prev_boss_hp - self._boss["hp"]
        if dmg_to_boss < 0:
            dmg_to_boss = 0
        self._players[user_id]["damage"] = self._players[user_id].get("damage", 0) + dmg_to_boss

        if pdata["hp"] <= 0:
            self._players[user_id]["cd_until"] = time.time() + WORLD_BOSS_RESPAWN_DELAY
            self._players[user_id]["deaths"] = self._players[user_id].get("deaths", 0) + 1
            respawn_text = f"\n💀 Bạn đã chết! Hồi sinh sau {WORLD_BOSS_RESPAWN_DELAY}s..."
        else:
            self._players[user_id]["cd_until"] = 0
            respawn_text = ""

        hp_text = f"❤️ {pdata['hp']}/{pdata['hp_max']}"
        btn_update = False
        if self._players[user_id]["cd_until"] > time.time():
            for child in view.children:
                child.disabled = True
            btn_update = True

        try:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="⚔️ Đánh Boss!",
                    description=f"{hp_text}\n💥 Gây **{dmg_to_boss}** dmg!{respawn_text}",
                    color=0xff0000 if pdata["hp"] <= 0 else 0x00ff00),
                view=view if btn_update else None)
        except Exception:
            pass

        if self._boss["hp"] <= 0:
            return

        alive_ids = [sid for sid, ps in self._players.items() if ps.get("cd_until", 0) <= time.time()]
        if alive_ids:
            target_id = random.choice(alive_ids)
            await self._boss_attack(target_id)

        if self._ranking_msg and self._boss["hp"] > 0:
            try:
                embed = self._build_boss_embed(self._current_id)
                await self._ranking_msg.edit(embed=embed)
            except Exception:
                pass

    async def _boss_attack(self, target_id: str):
        if self._boss is None or self._boss["hp"] <= 0:
            return

        db = await get_db()
        try:
            tdata = await load_player_full(db, target_id, reset_cd=False)
            if not tdata:
                return
        finally:
            await db.close()

        tdata["id"] = target_id
        tdata["name"] = self._players[target_id].get("name", "?")
        eff = get_effective_stats(tdata)
        tdata["hp_max"] = eff["hp_max"]
        if tdata.get("hp", 0) <= 0 or tdata["hp"] > eff["hp_max"]:
            tdata["hp"] = eff["hp_max"]

        dmg = random.randint(self._boss["attack_min"], self._boss["attack_max"])
        crit_roll = random.random() * 100 < self._boss.get("crit", 0)
        if crit_roll:
            dmg = int(dmg * 1.5)

        pierce = self._boss.get("pierce", 0)
        if pierce > 0:
            eff_def = int(eff["defense"] * (100 - pierce) / 100)
        else:
            eff_def = eff["defense"]

        final_dmg = max(dmg // 4, dmg - eff_def)
        tdata["hp"] = max(0, tdata.get("hp", 0) - final_dmg)

        target_view = self._players[target_id].get("view")
        if target_view and target_view.message:
            try:
                if tdata["hp"] <= 0:
                    self._players[target_id]["cd_until"] = time.time() + WORLD_BOSS_RESPAWN_DELAY
                    self._players[target_id]["deaths"] = self._players[target_id].get("deaths", 0) + 1
                    for child in target_view.children:
                        child.disabled = True
                    status = f"💀 Boss đánh **{final_dmg}** dmg! Bạn đã chết! Hồi sinh sau {WORLD_BOSS_RESPAWN_DELAY}s..."
                else:
                    status = f"🛡️ Boss đánh **{final_dmg}** dmg!"
                await target_view.message.edit(
                    embed=discord.Embed(
                        title=f"⚔️ Đánh Boss! | ❤️ {tdata['hp']}/{tdata['hp_max']}",
                        description=status,
                        color=0xff0000 if tdata["hp"] <= 0 else 0xffaa00),
                    view=target_view if tdata["hp"] <= 0 else None)
            except Exception:
                pass

    def _build_boss_embed(self, tid: int) -> discord.Embed:
        return discord.Embed(title="🐉 Boss Thế Giới", description="Đang tải...", color=0xff0000)

    async def _finish_boss(self, tid: int, ch: discord.TextChannel):
        pass


class WorldBossJoinView(discord.ui.View):
    def __init__(self, boss_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.boss_id = boss_id
        self.channel_id = channel_id
        self.participants: dict[str, str] = {}

    @discord.ui.button(emoji="⚔️", label="Tham Gia", style=discord.ButtonStyle.danger, custom_id="wb:join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid in self.participants:
            await interaction.response.send_message("🤷 Mày đã đăng ký rồi!", ephemeral=True)
            return

        db = await get_db()
        try:
            prow = await (await db.execute("SELECT id, name FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await interaction.response.send_message("❌ Đăng ký trước đã: `!register`", ephemeral=True)
                return
            name = prow["name"] or interaction.user.display_name
            await db.execute(
                "INSERT OR IGNORE INTO world_boss_participants (boss_id, player_id) VALUES (?, ?)",
                (self.boss_id, sid))
            await db.commit()
        finally:
            await db.close()

        self.participants[sid] = name
        await interaction.response.send_message(f"✅ Đã đăng ký! ({len(self.participants)} người)", ephemeral=True)

    @discord.ui.button(emoji="❌", label="Rời", style=discord.ButtonStyle.secondary, custom_id="wb:leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid not in self.participants:
            await interaction.response.send_message("🤷 Mày chưa đăng ký mà!", ephemeral=True)
            return
        db = await get_db()
        try:
            await db.execute("DELETE FROM world_boss_participants WHERE boss_id=? AND player_id=?",
                             (self.boss_id, sid))
            await db.commit()
        finally:
            await db.close()
        del self.participants[sid]
        await interaction.response.send_message("👋 Đã rời.", ephemeral=True)

class BossBattleView(discord.ui.View):
    def __init__(self, cog, user_id: str, user_name: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id
        self.user_name = user_name
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True

    async def _do_action(self, interaction: discord.Interaction, action_type: str):
        player_state = self.cog._players.get(self.user_id)
        if not player_state:
            await interaction.response.send_message("❌ Không tìm thấy dữ liệu!", ephemeral=True)
            return
        if player_state.get("cd_until", 0) > time.time():
            remaining = int(player_state["cd_until"] - time.time())
            await interaction.response.send_message(f"⏳ Hồi sinh sau **{remaining}s** nữa!", ephemeral=True)
            return
        if self.cog._boss is None or self.cog._boss.get("hp", 0) <= 0:
            await interaction.response.send_message("💀 Boss đã chết rồi!", ephemeral=True)
            return

        await interaction.response.defer()
        await self.cog._process_player_action(self.user_id, self.user_name, action_type, self, interaction)

    @discord.ui.button(emoji="💥", label="Attack", style=discord.ButtonStyle.red, custom_id="wb:atk")
    async def atk_btn(self, interaction: discord.Interaction, button: discord.Button):
        await self._do_action(interaction, "attack")

    @discord.ui.button(emoji="🔥", label="Special", style=discord.ButtonStyle.blurple, custom_id="wb:spc")
    async def spc_btn(self, interaction: discord.Interaction, button: discord.Button):
        await self._do_action(interaction, "special")

    @discord.ui.button(emoji="🛡️", label="Defense", style=discord.ButtonStyle.green, custom_id="wb:def")
    async def def_btn(self, interaction: discord.Interaction, button: discord.Button):
        await self._do_action(interaction, "defense")
