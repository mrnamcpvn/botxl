import discord
from discord import app_commands
from discord.ext import commands, tasks
import time
import random
import json
import asyncio
from bot.database import get_db
from bot.config import (
    ARENA_INTERVAL, ARENA_REGISTER_TIME, ARENA_MIN_PLAYERS,
    ARENA_MAX_PLAYERS, ARENA_AUTO_ENABLED, ARENA_BATTLE_DELAY,
    ARENA_SHOW_LOG_LINES,
)
from bot.engine.battle import execute_action, get_effective_stats
from bot.engine.arena_ai import pick_action
from bot.engine.rewards import _EQUIP_BY_STAR
from bot.utils.player_loader import load_player_full
from bot.views.arena_view import ArenaJoinView
from bot.logger import logger


class ArenaTournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._current_id: int | None = None
        self._current_status: str | None = None
        self._reg_task: asyncio.Task | None = None
        self._fight_task: asyncio.Task | None = None

    async def cog_load(self):
        # Dùng create_task để không block cog_load — wait_until_ready() cần event loop đã chạy
        asyncio.create_task(self._init_on_ready())

    async def _init_on_ready(self):
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, status, channel_id FROM arena_tournament "
                "WHERE status IN ('registering', 'fighting') ORDER BY id DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                self._current_id = r["id"]
                self._current_status = r["status"]
                logger.info(f"[ARENA] Resuming tournament #{r['id']} ({r['status']})")
                if r["status"] == "registering":
                    # Reset về cancelled nếu bot đã restart — không thể resume đăng ký
                    await db.execute(
                        "UPDATE arena_tournament SET status='cancelled', finished_at=? WHERE id=?",
                        (time.time(), r["id"]))
                    await db.commit()
                    self._current_id = None
                    self._current_status = None
                elif r["status"] == "fighting":
                    # Resume fighting phase với participants từ DB
                    pcursor = await db.execute(
                        "SELECT player_id, cp_at_entry FROM arena_participants WHERE tournament_id=?",
                        (r["id"],))
                    participants = [dict(p) for p in await pcursor.fetchall()]
                    if participants:
                        self._fight_task = asyncio.create_task(
                            self._fighting_phase(int(r["channel_id"]), r["id"], participants))
                    else:
                        await db.execute(
                            "UPDATE arena_tournament SET status='cancelled', finished_at=? WHERE id=?",
                            (time.time(), r["id"]))
                        await db.commit()
                        self._current_id = None
                        self._current_status = None
        except Exception as e:
            logger.error(f"[ARENA] _init_on_ready lỗi: {e}", exc_info=True)
        finally:
            await db.close()

        if ARENA_AUTO_ENABLED:
            self._auto_schedule.start()

    async def cog_unload(self):
        self._auto_schedule.cancel()
        for t in [self._reg_task, self._fight_task]:
            if t:
                t.cancel()

    @tasks.loop(seconds=ARENA_INTERVAL)
    async def _auto_schedule(self):
        if not ARENA_AUTO_ENABLED or self._current_status is not None:
            return
        ch = None
        for g in self.bot.guilds:
            for c in g.text_channels:
                if c.permissions_for(g.me).send_messages:
                    ch = c
                    break
            if ch:
                break
        if ch:
            await self.start_tournament(ch, "auto")

    async def start_tournament(self, channel: discord.TextChannel, started_by: str):
        if self._current_status is not None:
            await channel.send("⏳ Đang có đấu trường đang chạy rồi!")
            return

        db = await get_db()
        try:
            cursor = await db.execute(
                "INSERT INTO arena_tournament (status, channel_id, started_by, started_at) VALUES ('registering', ?, ?, ?)",
                (str(channel.id), started_by, time.time()))
            await db.commit()
            tid = cursor.lastrowid
        finally:
            await db.close()

        self._current_id = tid
        self._current_status = "registering"
        self._reg_task = asyncio.create_task(self._registration_phase(channel.id, tid))

    async def _registration_phase(self, channel_id: int, tid: int):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_tournament(tid)
            return

        view = ArenaJoinView(tid, channel_id)

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT p.player_id, pl.name FROM arena_participants p JOIN players pl ON pl.id=p.player_id WHERE p.tournament_id=?",
                (tid,))
            async for r in cursor:
                view.participants[r[0]] = r[1] or r[0]
        finally:
            await db.close()

        embed = self._build_reg_embed(view, ARENA_REGISTER_TIME)
        msg = await ch.send(embed=embed, view=view)

        for remaining in range(ARENA_REGISTER_TIME - 1, -1, -1):
            await asyncio.sleep(1)
            if self._current_status != "registering":
                return
            try:
                embed = self._build_reg_embed(view, remaining)
                await msg.edit(embed=embed)
            except Exception:
                pass

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT player_id, cp_at_entry FROM arena_participants WHERE tournament_id=?", (tid,))
            rows = await cursor.fetchall()
            participants = [dict(r) for r in rows]
        finally:
            await db.close()

        if len(participants) < ARENA_MIN_PLAYERS:
            await msg.edit(content=f"❌ Không đủ {ARENA_MIN_PLAYERS} người! Đấu trường bị hủy.", embed=None, view=None)
            await self._cancel_tournament(tid)
            return

        view.stop()
        for child in view.children:
            child.disabled = True
        await msg.edit(view=view)

        self._current_status = "fighting"
        db = await get_db()
        try:
            await db.execute("UPDATE arena_tournament SET status='fighting' WHERE id=?", (tid,))
            await db.commit()
        finally:
            await db.close()

        self._fight_task = asyncio.create_task(self._fighting_phase(channel_id, tid, participants))

    def _build_reg_embed(self, view: ArenaJoinView, remaining: int) -> discord.Embed:
        count = len(view.participants)
        lines = [f"⏳ Đăng ký kết thúc sau: **{remaining}s**", "", f"👥 Đã đăng ký (**{count}**):"]
        for sid, name in list(view.participants.items())[:ARENA_MAX_PLAYERS]:
            lines.append(f"  • {name}")
        if count == 0:
            lines.append("  *(chưa có ai)*")
        lines.extend(["", f"{'─' * 25}", f"Cần ít nhất **{ARENA_MIN_PLAYERS}** người | Đấu auto, không cần thao tác"])
        embed = discord.Embed(
            title="📜 ĐẤU TRƯỜNG SINH TỬ",
            description="\n".join(lines),
            color=0xffaa00,
        )
        embed.set_footer(text=f"ID: #{self._current_id} | Phí: Miễn phí")
        return embed

    async def _fighting_phase(self, channel_id: int, tid: int, participants: list[dict]):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            logger.error(f"[ARENA] Channel {channel_id} không tìm thấy, hủy tournament #{tid}")
            await self._cancel_tournament(tid)
            return

        try:
            # Load tên player
            for p in participants:
                db2 = await get_db()
                try:
                    row = await (await db2.execute(
                        "SELECT name FROM players WHERE id=?", (p["player_id"],))).fetchone()
                    p["name"] = row["name"] if row and row["name"] else f"Player{p['player_id'][-4:]}"
                finally:
                    await db2.close()

            bracket = {
                "rounds": [],
                "participants": {
                    p["player_id"]: {"name": p.get("name", "?"), "cp": p.get("cp_at_entry", 0)}
                    for p in participants
                }
            }

            current_ids = list(bracket["participants"].keys())
            bye_history: set[str] = set()
            round_num = 1

            embed_msg = await ch.send(embed=discord.Embed(
                title="⚔️ Đấu Trường Sinh Tử — Đang chia cặp...", color=0xffaa00))

            while len(current_ids) > 1:
                random.shuffle(current_ids)
                pairs = []
                i = 0
                while i + 1 < len(current_ids):
                    pairs.append((current_ids[i], current_ids[i + 1]))
                    i += 2

                byes = []
                if i < len(current_ids):
                    # Ưu tiên người chưa được bye
                    candidates = [pid for pid in current_ids[i:] if pid not in bye_history]
                    if not candidates:
                        candidates = current_ids[i:]
                    bye_pid = candidates[0]
                    bye_history.add(bye_pid)
                    byes.append(bye_pid)

                rond = {"name": f"Vòng {round_num}", "matches": [], "byes": byes}

                for p1_id, p2_id in pairs:
                    winner_id, log, p1_hp, p2_hp = await self._run_ai_battle(p1_id, p2_id)
                    # Fallback nếu winner_id là None
                    if winner_id is None:
                        winner_id = p1_id
                    rond["matches"].append({
                        "p1_id": p1_id, "p2_id": p2_id,
                        "winner_id": winner_id,
                        "log": log[-ARENA_SHOW_LOG_LINES:],
                        "p1_hp": p1_hp, "p2_hp": p2_hp,
                    })

                bracket["rounds"].append(rond)

                round_winners = [m["winner_id"] for m in rond["matches"]]
                current_ids = round_winners + byes
                round_num += 1

                try:
                    embed = self._build_bracket_embed(bracket, tid)
                    await embed_msg.edit(embed=embed)
                except Exception as e:
                    logger.warning(f"[ARENA] Edit bracket embed lỗi: {e}")
                await asyncio.sleep(ARENA_BATTLE_DELAY)

            winner_id = current_ids[0] if current_ids else None
            if winner_id is None:
                logger.error(f"[ARENA] Tournament #{tid} kết thúc không có winner!")
                await self._cancel_tournament(tid)
                return

            runner_up_id = None
            third_id = None

            if bracket["rounds"]:
                final_round = bracket["rounds"][-1]
                if final_round["matches"]:
                    fm = final_round["matches"][0]
                    runner_up_id = fm["p2_id"] if fm["winner_id"] == fm["p1_id"] else fm["p1_id"]

            if len(participants) >= 6 and len(bracket["rounds"]) >= 2:
                semi = bracket["rounds"][-2]
                losers = []
                for m in semi["matches"]:
                    loser = m["p2_id"] if m["winner_id"] == m["p1_id"] else m["p1_id"]
                    if loser != winner_id and loser != runner_up_id:
                        losers.append(loser)
                if losers:
                    third_id = losers[0]

            await self._give_rewards(tid, winner_id, runner_up_id, third_id, participants)

            db = await get_db()
            try:
                await db.execute(
                    "UPDATE arena_tournament SET status='done', winner_id=?, runner_up_id=?, third_id=?, "
                    "finished_at=?, bracket_json=? WHERE id=?",
                    (winner_id, runner_up_id, third_id, time.time(), json.dumps(bracket), tid))
                await db.execute(
                    "UPDATE arena_participants SET final_rank=1 WHERE tournament_id=? AND player_id=?",
                    (tid, winner_id))
                if runner_up_id:
                    await db.execute(
                        "UPDATE arena_participants SET final_rank=2 WHERE tournament_id=? AND player_id=?",
                        (tid, runner_up_id))
                if third_id:
                    await db.execute(
                        "UPDATE arena_participants SET final_rank=3 WHERE tournament_id=? AND player_id=?",
                        (tid, third_id))
                await db.commit()
            finally:
                await db.close()

            embed = self._build_podium_embed(
                winner_id, runner_up_id, third_id, bracket["participants"], tid)
            try:
                await embed_msg.edit(embed=embed)
            except Exception:
                await ch.send(embed=embed)

        except asyncio.CancelledError:
            logger.info(f"[ARENA] Tournament #{tid} bị hủy (CancelledError)")
            await self._cancel_tournament(tid)
            return
        except Exception as e:
            logger.error(f"[ARENA] _fighting_phase lỗi: {e}", exc_info=True)
            await self._cancel_tournament(tid)
            try:
                await ch.send(f"⚠️ Đấu trường #{tid} gặp lỗi và đã bị hủy. Xin lỗi!")
            except Exception:
                pass
        finally:
            self._current_id = None
            self._current_status = None

    async def _run_ai_battle(self, p1_id: str, p2_id: str) -> tuple[str | None, list[str], int, int]:
        db = await get_db()
        try:
            p1 = await load_player_full(db, p1_id, reset_cd=True)
            p2 = await load_player_full(db, p2_id, reset_cd=True)
        finally:
            await db.close()

        if not p1 or not p2:
            winner = p1_id if p1 and not p2 else (p2_id if p2 else p1_id)
            return winner, ["⚠️ Đối thủ không tồn tại, auto-thắng."], p1.get("hp", 0) if p1 else 0, p2.get("hp", 0) if p2 else 0

        p1["id"] = p1_id
        p2["id"] = p2_id

        eff1 = get_effective_stats(p1)
        eff2 = get_effective_stats(p2)
        p1["hp"] = eff1["hp_max"]
        p2["hp"] = eff2["hp_max"]
        p1["hp_max"] = eff1["hp_max"]
        p2["hp_max"] = eff2["hp_max"]

        spd1 = eff1.get("spd", 0)
        spd2 = eff2.get("spd", 0)
        if spd1 > spd2:
            turn = 0
        elif spd2 > spd1:
            turn = 1
        else:
            turn = random.randint(0, 1)

        flags: dict = {"turn_count": 0}
        all_logs: list[str] = []
        max_turns = 60

        for _ in range(max_turns):
            current = p1 if turn == 0 else p2
            opponent = p2 if turn == 0 else p1

            if flags.get(f"{current['id']}_stunned", False):
                flags.pop(f"{current['id']}_stunned", None)
                all_logs.append(f"🌑 {current.get('name', '?')} choáng, mất lượt!")
                for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                    if current.get(cdkey, 0) > 0:
                        current[cdkey] -= 1
                turn = 1 - turn
                continue

            action = pick_action(current, opponent, flags)
            result = await execute_action(p1, p2, turn, action, flags)
            all_logs.extend(result["log_messages"])

            if result["finished"]:
                return result["winner_id"], all_logs, p1.get("hp", 0), p2.get("hp", 0)

            turn = 1 - turn

        hp1 = p1.get("hp", 0)
        hp2 = p2.get("hp", 0)
        if hp1 > hp2:
            return p1_id, all_logs + [f"⏰ Hết lượt! {p1.get('name', '?')} thắng ({hp1} vs {hp2}HP)"], hp1, hp2
        elif hp2 > hp1:
            return p2_id, all_logs + [f"⏰ Hết lượt! {p2.get('name', '?')} thắng ({hp2} vs {hp1}HP)"], hp1, hp2
        return random.choice([p1_id, p2_id]), all_logs + ["⏰ Hòa! Random thắng..."], hp1, hp2

    def _build_bracket_embed(self, bracket: dict, tid: int) -> discord.Embed:
        desc_lines = [f"⚔️ **ĐẤU TRƯỜNG SINH TỬ #{tid}** — LIVE\n"]
        parts = bracket["participants"]

        for i, rond in enumerate(bracket["rounds"]):
            desc_lines.append(f"🏟️ **{rond['name']}**")
            for m in rond["matches"]:
                # Safe get tên — không crash nếu player không có trong parts
                p1n = parts.get(m["p1_id"], {}).get("name", f"ID{m['p1_id'][-4:]}")
                p2n = parts.get(m["p2_id"], {}).get("name", f"ID{m['p2_id'][-4:]}")
                if m.get("winner_id"):
                    wname = parts.get(m["winner_id"], {}).get("name", "?")
                    loser_name = p2n if m["winner_id"] == m["p1_id"] else p1n
                    desc_lines.append(f"  ✅ **{wname}** thắng {loser_name}")
                    for line in m.get("log", []):
                        if line.strip():
                            desc_lines.append(f"     _{line[:80]}_")
                else:
                    desc_lines.append(f"  🔄 **{p1n}** ⚔️ VS 🛡️ **{p2n}**")
            for bye in rond.get("byes", []):
                bname = parts.get(bye, {}).get("name", f"ID{bye[-4:]}")
                desc_lines.append(f"  💎 **{bname}** BYE — vào thẳng vòng sau")
            desc_lines.append("")

        # Cắt nếu quá dài (Discord embed limit 4096)
        full = "\n".join(desc_lines)
        if len(full) > 3800:
            full = full[:3800] + "\n_...còn nữa_"

        return discord.Embed(
            title=f"⚔️ Đấu Trường Sinh Tử #{tid} — LIVE",
            description=full,
            color=0xffaa00,
        )

    def _build_podium_embed(self, winner_id: str, runner_up_id: str | None, third_id: str | None, parts: dict, tid: int) -> discord.Embed:
        desc_lines = [f"🏆 **ĐẤU TRƯỜNG SINH TỬ #{tid} — KẾT THÚC**\n"]
        desc_lines.append(f"🥇 **{parts[winner_id]['name']}** — Quán Quân")
        if runner_up_id:
            desc_lines.append(f"🥈 **{parts[runner_up_id]['name']}** — Á Quân")
        if third_id:
            desc_lines.append(f"🥉 **{parts[third_id]['name']}** — Hạng Ba")
        desc_lines.append("\nPhần thưởng đã được gửi! Hẹn gặp lại mùa sau ⚔️")
        return discord.Embed(
            title=f"🏆 Đấu Trường Sinh Tử #{tid}",
            description="\n".join(desc_lines),
            color=0x00ff00,
        )

    async def _give_rewards(self, tid: int, winner_id: str, runner_up_id: str | None, third_id: str | None, participants: list[dict]):
        rewards = []

        if winner_id:
            rewards.append((winner_id, 1, {
                "coins": random.randint(200, 400),
                "xp": 100,
                "vip": 2,
                "stones": ("stone_advanced", random.randint(3, 5)),
                "equip_star": 4,
            }))
        if runner_up_id:
            rewards.append((runner_up_id, 2, {
                "coins": random.randint(100, 200),
                "xp": 50,
                "vip": 1,
                "stones": ("stone_medium", random.randint(1, 3)),
                "equip_star": 3,
            }))
        if third_id and len(participants) >= 6:
            rewards.append((third_id, 3, {
                "coins": random.randint(50, 100),
                "xp": 25,
                "vip": 0,
                "stones": ("stone_basic", random.randint(5, 10)),
                "equip_star": 3,
                "equip_chance": 0.5,
            }))

        db = await get_db()
        try:
            for pid, rank, rw in rewards:
                await db.execute("UPDATE players SET coins=coins+?, xp=xp+? WHERE id=?", (rw["coins"], rw["xp"], pid))

                if rw["vip"] > 0:
                    await db.execute(
                        "INSERT OR REPLACE INTO player_vip_coins (player_id, amount) VALUES (?, COALESCE((SELECT amount FROM player_vip_coins WHERE player_id=?), 0) + ?)",
                        (pid, pid, rw["vip"]))

                stone_type, stone_qty = rw["stones"]
                stone_col = stone_type
                await db.execute(
                    "INSERT OR IGNORE INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced) VALUES (?, 0, 0, 0)",
                    (pid,))
                await db.execute(
                    f"UPDATE player_enhance_stones SET {stone_col}={stone_col}+? WHERE player_id=?", (stone_qty, pid))

                star = rw["equip_star"]
                # equip_chance: xác suất NHẬN đồ (không phải bỏ qua)
                chance = rw.get("equip_chance", 1.0)
                if random.random() > chance:
                    # Không nhận đồ lần này
                    await db.execute(
                        "UPDATE arena_participants SET reward_given=1, final_rank=? WHERE tournament_id=? AND player_id=?",
                        (rank, tid, pid))
                    continue
                eids = _EQUIP_BY_STAR.get(star, [])
                if eids:
                    eid = random.choice(eids)
                    await db.execute(
                        "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                        (pid, eid))

                await db.execute(
                    "UPDATE arena_participants SET reward_given=1, final_rank=? WHERE tournament_id=? AND player_id=?",
                    (rank, tid, pid))

            await db.commit()
        finally:
            await db.close()

    @app_commands.command(name="arena", description="🎮 Quản lý Đấu Trường Sinh Tử")
    @app_commands.default_permissions(administrator=True)
    async def arena_admin(self, interaction: discord.Interaction, action: str):
        action = action.lower()
        if action == "start":
            if self._current_status is not None:
                await interaction.response.send_message("⏳ Đang có đấu trường chạy rồi!", ephemeral=True)
                return
            await interaction.response.send_message("✅ Đang mở đấu trường...", ephemeral=True)
            await self.start_tournament(interaction.channel, str(interaction.user.id))

        elif action == "stop":
            if self._current_id is None:
                await interaction.response.send_message("🤷 Không có đấu trường nào đang chạy.", ephemeral=True)
                return
            await self._cancel_tournament(self._current_id)
            if self._reg_task:
                self._reg_task.cancel()
            if self._fight_task:
                self._fight_task.cancel()
            await interaction.response.send_message("🛑 Đã hủy đấu trường.", ephemeral=True)

        elif action == "toggle":
            import bot.config as cfg
            cfg.ARENA_AUTO_ENABLED = not cfg.ARENA_AUTO_ENABLED
            if cfg.ARENA_AUTO_ENABLED:
                if not self._auto_schedule.is_running():
                    self._auto_schedule.start()
            else:
                if self._auto_schedule.is_running():
                    self._auto_schedule.cancel()
            status = "BẬT" if cfg.ARENA_AUTO_ENABLED else "TẮT"
            await interaction.response.send_message(f"🔁 Auto-schedule: **{status}**", ephemeral=True)

        elif action == "status":
            if self._current_id:
                status = self._current_status or "?"
                await interaction.response.send_message(f"📊 Tournament #{self._current_id} — **{status}**", ephemeral=True)
            else:
                await interaction.response.send_message("📊 Không có đấu trường đang chạy.", ephemeral=True)

        else:
            await interaction.response.send_message("Dùng: `start`, `stop`, `toggle`, `status`", ephemeral=True)

    @arena_admin.autocomplete("action")
    async def arena_action_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["start", "stop", "toggle", "status"]
        return [app_commands.Choice(name=o, value=o) for o in options if current.lower() in o.lower()]

    @app_commands.command(name="arenahistory", description="📜 Lịch sử Đấu Trường Sinh Tử")
    async def arena_history(self, interaction: discord.Interaction):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, winner_id, runner_up_id, third_id, finished_at FROM arena_tournament WHERE status='done' ORDER BY id DESC LIMIT 5")
            rows = await cursor.fetchall()
        finally:
            await db.close()

        if not rows:
            await interaction.response.send_message("📜 Chưa có mùa giải nào!", ephemeral=True)
            return

        lines = []
        for r in rows:
            r = dict(r)
            lines.append(f"#{r['id']} — {r.get('finished_at', '?')}")
            if r.get("winner_id"):
                lines.append(f"  🥇 <@{r['winner_id']}>")
            if r.get("runner_up_id"):
                lines.append(f"  🥈 <@{r['runner_up_id']}>")
            if r.get("third_id"):
                lines.append(f"  🥉 <@{r['third_id']}>")

        embed = discord.Embed(
            title="📜 Lịch Sử Đấu Trường Sinh Tử",
            description="\n".join(lines),
            color=0x3498db,
        )
        await interaction.response.send_message(embed=embed)

    async def _cancel_tournament(self, tid: int):
        db = await get_db()
        try:
            await db.execute("UPDATE arena_tournament SET status='cancelled', finished_at=? WHERE id=?", (time.time(), tid))
            await db.commit()
        finally:
            await db.close()
        self._current_id = None
        self._current_status = None


async def setup(bot):
    await bot.add_cog(ArenaTournament(bot))
