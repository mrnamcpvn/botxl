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
        pass

    async def _cancel_boss(self, tid: int):
        pass
