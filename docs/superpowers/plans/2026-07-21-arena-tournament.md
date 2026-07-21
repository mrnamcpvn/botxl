# Đấu Trường Sinh Tử — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated tournament arena where players click Join, get auto-seeded, and AI battles run automatically with live bracket embed updates.

**Architecture:** New `arena_tournament.py` cog manages lifecycle (scheduled + admin start), `arena_ai.py` engine picks skills for AI-controlled battles, `arena_view.py` provides Join button UI. Reuses existing `execute_action()` from `battle.py` and `load_player_full()` from `player_loader.py`.

**Tech Stack:** Python 3.11+, discord.py, aiosqlite

---

## Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add arena config |
| `bot/database.py` | Modify — add arena tables |
| `bot/engine/arena_ai.py` | Create — AI skill picker |
| `bot/views/arena_view.py` | Create — Join + bracket views |
| `bot/cogs/arena_tournament.py` | Create — main cog |
| `main.py` | Modify — load arena_tournament cog |

---

### Task 1: Arena Config Constants

**Files:**
- Modify: `bot/config.py` (append at end)

- [ ] **Step 1: Add arena constants to config**

```python
ARENA_INTERVAL = 3600
ARENA_REGISTER_TIME = 60
ARENA_MIN_PLAYERS = 4
ARENA_MAX_PLAYERS = 8
ARENA_AUTO_ENABLED = True
ARENA_BATTLE_DELAY = 3
ARENA_SHOW_LOG_LINES = 6
```

Insert at end of `bot/config.py` after line 103.

- [ ] **Step 2: Commit**

```bash
git add bot/config.py
git commit -m "feat: add arena tournament config constants"
```

---

### Task 2: Arena Database Tables

**Files:**
- Modify: `bot/database.py`

- [ ] **Step 1: Add arena table SQL to TABLES list**

Add to the `TABLES` list in `bot/database.py` (after line 141, before `]`):

```python
    """CREATE TABLE IF NOT EXISTS arena_tournament (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'registering',
        channel_id TEXT NOT NULL,
        started_by TEXT NOT NULL,
        started_at REAL NOT NULL,
        bracket_json TEXT,
        winner_id TEXT,
        runner_up_id TEXT,
        third_id TEXT,
        finished_at REAL,
        created_at TEXT DEFAULT (datetime('now','+7 hours'))
    )""",
    """CREATE TABLE IF NOT EXISTS arena_participants (
        tournament_id INTEGER REFERENCES arena_tournament(id),
        player_id TEXT NOT NULL,
        cp_at_entry INTEGER DEFAULT 0,
        eliminated_round INTEGER DEFAULT 0,
        final_rank INTEGER DEFAULT 0,
        reward_given INTEGER DEFAULT 0,
        PRIMARY KEY (tournament_id, player_id)
    )""",
```

- [ ] **Step 2: Add indexes to `_create_indexes`**

Add to the `indexes` list in `_create_indexes` function:

```python
        "CREATE INDEX IF NOT EXISTS idx_arena_tournament_status ON arena_tournament(status)",
        "CREATE INDEX IF NOT EXISTS idx_arena_participants_tournament ON arena_participants(tournament_id)",
```

- [ ] **Step 3: Commit**

```bash
git add bot/database.py
git commit -m "feat: add arena_tournament and arena_participants tables"
```

---

### Task 3: AI Skill Picker Engine

**Files:**
- Create: `bot/engine/arena_ai.py`

- [ ] **Step 1: Create the AI picker module**

```python
import random
from bot.data.skills import SKILLS_DB


def _skill_by_id(skill_id: int) -> dict:
    return SKILLS_DB.get(skill_id, SKILLS_DB[1])


def _slot_available(player: dict, slot: str) -> bool:
    cd_key = f"{slot}_cd"
    sid = player.get("skill_equipped", {}).get(slot)
    return sid is not None and player.get(cd_key, 0) <= 0


def _best_skill_in_slot(player: dict, slot: str) -> int:
    sid = player.get("skill_equipped", {}).get(slot)
    return sid if sid else 1


def pick_action(player: dict, opponent: dict, flags: dict) -> dict:
    """
    Choose {type, skill_id} for execute_action().
    player/opponent: dicts with hp, hp_max, attack_cd, special_cd, defense_cd, skill_equipped.
    flags: battle flags (for checking _defending, _burn, etc.)
    """
    hp_pct = player.get("hp", 0) / max(player.get("hp_max", 1), 1) * 100
    opp_hp_pct = opponent.get("hp", 0) / max(opponent.get("hp_max", 1), 1) * 100

    has_burn = flags.get(f"{opponent['id']}_burn") and flags[f"{opponent['id']}_burn"].get("turns", 0) > 0
    is_defending = flags.get(f"{player['id']}_defending", False)

    def_ok = _slot_available(player, "defense")
    atk_ok = _slot_available(player, "attack")
    spc_ok = _slot_available(player, "special")

    # 1. Low HP → defense
    if hp_pct < 30 and def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            return {"type": "defense", "skill_id": sid}

    # 2. Opponent nearly dead → attack
    if opp_hp_pct < 20:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}

    # 3. Opponent burning → attack
    if has_burn and atk_ok:
        return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}

    # 4. Normal — weighted random
    available = []
    weights = []
    if atk_ok:
        available.append(("attack", _best_skill_in_slot(player, "attack")))
        weights.append(50)
    if spc_ok:
        available.append(("special", _best_skill_in_slot(player, "special")))
        weights.append(30)
    if def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            available.append(("defense", sid))
            weights.append(20)

    if not available:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}
        return {"type": "attack", "skill_id": 1}

    choice = random.choices(available, weights=weights, k=1)[0]
    return {"type": choice[0], "skill_id": choice[1]}
```

- [ ] **Step 2: Commit**

```bash
git add bot/engine/arena_ai.py
git commit -m "feat: AI skill picker for arena auto-battles"
```

---

### Task 4: Arena Bracket + Battle Runner Logic

**Files:**
- Create: `bot/cogs/arena_tournament.py` (Part 1 — bracket logic + battle runner)

- [ ] **Step 1: Import scaffolding and cog structure**

```python
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
from bot.engine.rewards import _EQUIP_BY_STAR, _STAR_CUMULATIVE, _TOTAL_WEIGHT
from bot.data.equipment import EQUIPMENT, STAR_LABELS
from bot.utils.player_loader import load_player_full
from bot.views.arena_view import ArenaJoinView, arena_join_view_msg
from bot.logger import logger


class ArenaTournament(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._current_tournament_id: int | None = None
        self._current_status: str | None = None  # 'registering' | 'fighting'
        self._registration_task: asyncio.Task | None = None
        self._fighting_task: asyncio.Task | None = None
        self._countdown_msg: discord.Message | None = None

    async def cog_load(self):
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, status, channel_id FROM arena_tournament WHERE status IN ('registering', 'fighting') ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                self._current_tournament_id = r["id"]
                self._current_status = r["status"]
                logger.info(f"[ARENA] Resuming tournament #{r['id']} ({r['status']})")
                if r["status"] == "registering":
                    self._registration_task = asyncio.create_task(self._registration_phase(r["channel_id"], r["id"]))
                elif r["status"] == "fighting":
                    self._fighting_task = asyncio.create_task(self._fighting_phase(r["channel_id"], r["id"]))
        finally:
            await db.close()
        if ARENA_AUTO_ENABLED:
            self._auto_schedule.start()

    async def cog_unload(self):
        self._auto_schedule.cancel()
        if self._registration_task:
            self._registration_task.cancel()
        if self._fighting_task:
            self._fighting_task.cancel()

    @tasks.loop(seconds=ARENA_INTERVAL)
    async def _auto_schedule(self):
        if not ARENA_AUTO_ENABLED or self._current_status:
            return
        await self.start_tournament(None, "auto")
```

- [ ] **Step 2: Add bracket builder**

```python
    def _build_bracket(self, participants: list[dict]) -> list[dict]:
        """
        Returns list of rounds. Each round: {name, matches: [{p1_id, p1_name, p2_id, p2_name, winner_id, log, p1_hp, p2_hp}], byes: [{id, name}]}
        """
        random.shuffle(participants)
        rounds = []
        current = [{"id": p["player_id"], "name": p["name"], "cp": p["cp_at_entry"]} for p in participants]
        bye_history: set[str] = set()
        round_num = 1

        while len(current) > 1:
            rond = {"name": f"Vòng {round_num}", "matches": [], "byes": []}
            pairs = []
            i = 0
            random.shuffle(current)
            while i + 1 < len(current):
                pairs.append((current[i], current[i + 1]))
                i += 2
            if i < len(current):
                bye_candidates = [p for p in current[i:] if p["id"] not in bye_history]
                if not bye_candidates:
                    bye_candidates = current[i:]
                bye_player = bye_candidates[0]
                bye_history.add(bye_player["id"])
                rond["byes"].append({"id": bye_player["id"], "name": bye_player["name"]})
            for p1, p2 in pairs:
                rond["matches"].append({
                    "p1_id": p1["id"], "p1_name": p1["name"],
                    "p2_id": p2["id"], "p2_name": p2["name"],
                    "winner_id": None, "log": [], "p1_hp": None, "p2_hp": None,
                })
            rounds.append(rond)
            current = [p for p in (current[i:] if i < len(current) else []) if p["id"] not in (b["id"] for b in rond.get("byes", []))]
            round_num += 1

        return rounds
```

Wait — the bracket builder above is wrong. It doesn't actually simulate winners. Let me think again.

Actually the bracket should be built BEFORE fighting. We only build the structure, winners are filled in during the fighting phase. So the bracket is just the initial seeding structure. After each round's fights, we fill in the winners.

The way to handle this is:
1. Shuffle participants
2. Create Round 1: pair adjacent, odd one gets BYE
3. After fights, collect winners + BYE players = next round's participants
4. Repeat until 1 player left

So the bracket building doesn't need winner_id yet — it's built incrementally. Let me restructure:

The `_build_initial_bracket` creates Round 1 structure only. Then `_advance_to_next_round` takes winners + BYE players and creates the next round's structure. Each round's matches are fought, then we advance.

Actually for simplicity, let me build the full bracket structure upfront with all match slots (winner_ids = None), then fill them in as fights complete. The advance is done by reading bracket data.

Let me reconsider. The bracket JSON saved to DB should be the full tournament data. We build the bracket incrementally during the fighting phase.

```python
def _seed_bracket(self, participants):
    """Create initial bracket with R1 match slots, returns bracket dict."""
    shuffled = list(participants)
    random.shuffle(shuffled)
    bracket = {"rounds": [], "participants": {}, "bye_history": []}
    for p in shuffled:
        bracket["participants"][p["player_id"]] = {"name": p["name"], "cp": p["cp_at_entry"]}
    return bracket

def _build_next_round(self, prev_round: dict):
    """Given completed round results, build next round's match slots."""
    # Collect winners + bye players
    # Pair them, assign bye if odd
    # Return new round structure
```

OK this is getting complex. Let me simplify and just write the plan with the key functions. The plan should have actual code though...

Let me write this more carefully. I'll create the tournament cog with all needed methods.<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write">
<｜｜DSML｜｜parameter name="content" string="true"># Đấu Trường Sinh Tử — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated tournament arena where players click Join, get auto-seeded, and AI battles run automatically with live bracket embed updates.

**Architecture:** New `arena_tournament.py` cog manages lifecycle (scheduled + admin start), `arena_ai.py` engine picks skills for AI-controlled battles, `arena_view.py` provides Join button UI. Reuses existing `execute_action()` from `battle.py` and `load_player_full()` from `player_loader.py`.

**Tech Stack:** Python 3.11+, discord.py, aiosqlite

---

## Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add arena config |
| `bot/database.py` | Modify — add arena tables |
| `bot/engine/arena_ai.py` | Create — AI skill picker |
| `bot/views/arena_view.py` | Create — Join + bracket views |
| `bot/cogs/arena_tournament.py` | Create — main cog |
| `main.py` | Modify — load arena_tournament cog |

---

### Task 1: Arena Config Constants

**Files:**
- Modify: `bot/config.py`

- [ ] **Step 1: Append arena constants**

Edit `bot/config.py` — append after line 103:

```python
# ── Arena Tournament ──────────────────────────────────────────
ARENA_INTERVAL = 3600
ARENA_REGISTER_TIME = 60
ARENA_MIN_PLAYERS = 4
ARENA_MAX_PLAYERS = 8
ARENA_AUTO_ENABLED = True
ARENA_BATTLE_DELAY = 3
ARENA_SHOW_LOG_LINES = 6
```

- [ ] **Step 2: Commit**

```bash
git add bot/config.py
git commit -m "feat: add arena tournament config constants"
```

---

### Task 2: Arena Database Tables

**Files:**
- Modify: `bot/database.py`

- [ ] **Step 1: Add arena CREATE TABLE SQL**

In `bot/database.py`, add these entries to the `TABLES` list just before the closing `]` (after line 141):

```python
    """CREATE TABLE IF NOT EXISTS arena_tournament (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'registering',
        channel_id TEXT NOT NULL,
        started_by TEXT NOT NULL,
        started_at REAL NOT NULL,
        bracket_json TEXT,
        winner_id TEXT,
        runner_up_id TEXT,
        third_id TEXT,
        finished_at REAL,
        created_at TEXT DEFAULT (datetime('now','+7 hours'))
    )""",
    """CREATE TABLE IF NOT EXISTS arena_participants (
        tournament_id INTEGER REFERENCES arena_tournament(id),
        player_id TEXT NOT NULL,
        cp_at_entry INTEGER DEFAULT 0,
        eliminated_round INTEGER DEFAULT 0,
        final_rank INTEGER DEFAULT 0,
        reward_given INTEGER DEFAULT 0,
        PRIMARY KEY (tournament_id, player_id)
    )""",
```

- [ ] **Step 2: Add indexes**

In `_create_indexes` function, add to the `indexes` list:

```python
        "CREATE INDEX IF NOT EXISTS idx_arena_tournament_status ON arena_tournament(status)",
        "CREATE INDEX IF NOT EXISTS idx_arena_participants_tournament ON arena_participants(tournament_id)",
```

- [ ] **Step 3: Commit**

```bash
git add bot/database.py
git commit -m "feat: add arena_tournament and arena_participants tables"
```

---

### Task 3: AI Skill Picker

**Files:**
- Create: `bot/engine/arena_ai.py`

- [ ] **Step 1: Write the AI module**

```python
import random
from bot.data.skills import SKILLS_DB


def _skill_by_id(skill_id: int) -> dict:
    return SKILLS_DB.get(skill_id, SKILLS_DB[1])


def _slot_available(player: dict, slot: str) -> bool:
    cd_key = f"{slot}_cd"
    sid = player.get("skill_equipped", {}).get(slot)
    return sid is not None and player.get(cd_key, 0) <= 0


def _best_skill_in_slot(player: dict, slot: str) -> int:
    sid = player.get("skill_equipped", {}).get(slot)
    return sid if sid else 1


def pick_action(player: dict, opponent: dict, flags: dict) -> dict:
    hp_pct = player.get("hp", 0) / max(player.get("hp_max", 1), 1) * 100
    opp_hp_pct = opponent.get("hp", 0) / max(opponent.get("hp_max", 1), 1) * 100

    burn_key = f"{opponent['id']}_burn"
    has_burn = burn_key in flags and flags[burn_key].get("turns", 0) > 0
    is_defending = flags.get(f"{player['id']}_defending", False)

    def_ok = _slot_available(player, "defense")
    atk_ok = _slot_available(player, "attack")
    spc_ok = _slot_available(player, "special")

    if hp_pct < 30 and def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            return {"type": "defense", "skill_id": sid}

    if opp_hp_pct < 20:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}

    if has_burn and atk_ok:
        return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}

    available = []
    weights = []
    if atk_ok:
        available.append(("attack", _best_skill_in_slot(player, "attack")))
        weights.append(50)
    if spc_ok:
        available.append(("special", _best_skill_in_slot(player, "special")))
        weights.append(30)
    if def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            available.append(("defense", sid))
            weights.append(20)

    if not available:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}
        return {"type": "attack", "skill_id": 1}

    choice = random.choices(available, weights=weights, k=1)[0]
    return {"type": choice[0], "skill_id": choice[1]}
```

- [ ] **Step 2: Commit**

```bash
git add bot/engine/arena_ai.py
git commit -m "feat: AI skill picker for arena auto-battles"
```

---

### Task 4: Arena Join View

**Files:**
- Create: `bot/views/arena_view.py`

- [ ] **Step 1: Write the Join button view**

```python
import discord
from bot.database import get_db


class ArenaJoinView(discord.ui.View):
    def __init__(self, tournament_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.tournament_id = tournament_id
        self.channel_id = channel_id
        self.participants: dict[str, str] = {}

    @discord.ui.button(emoji="⚔️", label="Tham Gia", style=discord.ButtonStyle.success, custom_id="arena:join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)

        from bot.config import ARENA_MAX_PLAYERS
        if len(self.participants) >= ARENA_MAX_PLAYERS:
            await interaction.response.send_message(f"🚫 Đã đủ {ARENA_MAX_PLAYERS} người rồi!", ephemeral=True)
            return

        if sid in self.participants:
            await interaction.response.send_message("🤷 Mày đã đăng ký rồi!", ephemeral=True)
            return

        db = await get_db()
        try:
            prow = await (await db.execute("SELECT id, name, combat_power FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await interaction.response.send_message("❌ Đăng ký trước đã: `!register`", ephemeral=True)
                return
            name = prow["name"] or interaction.user.display_name
            cp = prow["combat_power"] or 0

            await db.execute(
                "INSERT OR IGNORE INTO arena_participants (tournament_id, player_id, cp_at_entry) VALUES (?, ?, ?)",
                (self.tournament_id, sid, cp))
            await db.commit()
        finally:
            await db.close()

        self.participants[sid] = name
        await interaction.response.send_message(f"✅ Đã đăng ký! ({len(self.participants)} người)", ephemeral=True)

    @discord.ui.button(emoji="❌", label="Rời", style=discord.ButtonStyle.danger, custom_id="arena:leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid not in self.participants:
            await interaction.response.send_message("🤷 Mày chưa đăng ký mà!", ephemeral=True)
            return

        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM arena_participants WHERE tournament_id=? AND player_id=?",
                (self.tournament_id, sid))
            await db.commit()
        finally:
            await db.close()

        del self.participants[sid]
        await interaction.response.send_message("👋 Đã rời khỏi đấu trường.", ephemeral=True)
```

- [ ] **Step 2: Commit**

```bash
git add bot/views/arena_view.py
git commit -m "feat: arena join/leave button view"
```

---

### Task 5: Arena Tournament Cog — Core Logic

**Files:**
- Create: `bot/cogs/arena_tournament.py`

This is the largest task. The cog contains:
- Tournament lifecycle: start → registering → fighting → rewarding  
- Bracket seeding and round advancement
- Auto-battle runner
- Embed rendering for registration, bracket, and podium phases

- [ ] **Step 1: Imports and cog class skeleton**

```python
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
from bot.engine.rewards import _EQUIP_BY_STAR, _STAR_CUMULATIVE, _TOTAL_WEIGHT
from bot.data.equipment import EQUIPMENT, STAR_LABELS
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
        await self.bot.wait_until_ready()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, status, channel_id FROM arena_tournament WHERE status IN ('registering', 'fighting') ORDER BY id DESC LIMIT 1")
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                self._current_id = r["id"]
                self._current_status = r["status"]
                logger.info(f"[ARENA] Resuming tournament #{r['id']} ({r['status']})")
                if r["status"] == "registering":
                    self._reg_task = asyncio.create_task(self._registration_phase(int(r["channel_id"]), r["id"]))
                elif r["status"] == "fighting":
                    self._fight_task = asyncio.create_task(self._fighting_phase(int(r["channel_id"]), r["id"]))
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
        ch = self.bot.get_channel(0)
        for g in self.bot.guilds:
            for c in g.text_channels:
                if c.permissions_for(g.me).send_messages:
                    ch = c
                    break
            if ch:
                break
        if ch:
            await self.start_tournament(ch, "auto")
```

- [ ] **Step 2: Tournament start method**

```python
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
```

- [ ] **Step 3: Registration phase**

```python
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
```

- [ ] **Step 4: Registration embed builder**

```python
    def _build_reg_embed(self, view: ArenaJoinView, remaining: int) -> discord.Embed:
        count = len(view.participants)
        lines = [f"⏳ Đăng ký kết thúc sau: **{remaining}s**", "", f"👥 Đã đăng ký (**{count}**):"]
        for sid, name in list(view.participants.items())[:ARENA_MAX_PLAYERS]:
            lines.append(f"  • {name}")
        if count == 0:
            lines.append("  *(chưa có ai)*")
        lines.extend(["", f"─────────────────────────", f"Cần ít nhất **{ARENA_MIN_PLAYERS}** người | Đấu auto, không cần thao tác"])
        embed = discord.Embed(
            title="📜 ĐẤU TRƯỜNG SINH TỬ",
            description="\n".join(lines),
            color=0xffaa00,
        )
        embed.set_footer(text=f"ID: #{self._current_id} | Phí: Miễn phí")
        return embed
```

- [ ] **Step 5: Fighting phase — bracket seeding and round-by-round**

```python
    async def _fighting_phase(self, channel_id: int, tid: int, participants: list[dict]):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_tournament(tid)
            return

        for p in participants:
            row = await (await (await get_db()).execute("SELECT name FROM players WHERE id=?", (p["player_id"],))).fetchone()
            p["name"] = row["name"] if row else f"Player{p['player_id']}"
            await (await get_db()).close()

        bracket = {"rounds": [], "participants": {p["player_id"]: {"name": p.get("name", "?"), "cp": p["cp_at_entry"]} for p in participants}}

        current_ids = list(bracket["participants"].keys())
        bye_history: set[str] = set()
        round_num = 1

        embed = await ch.send(embed=discord.Embed(title="⚔️ Đấu Trường Sinh Tử — Đang chia cặp...", color=0xffaa00))
        bracket_msg = embed

        while len(current_ids) > 1:
            random.shuffle(current_ids)
            pairs = []
            i = 0
            while i + 1 < len(current_ids):
                pairs.append((current_ids[i], current_ids[i + 1]))
                i += 2

            byes = []
            if i < len(current_ids):
                candidates = [pid for pid in current_ids[i:] if pid not in bye_history]
                if not candidates:
                    candidates = current_ids[i:]
                bye_pid = candidates[0]
                bye_history.add(bye_pid)
                byes.append(bye_pid)

            rond = {"name": f"Vòng {round_num}", "matches": [], "byes": byes}
            round_winners = []

            for p1_id, p2_id in pairs:
                match = {"p1_id": p1_id, "p2_id": p2_id, "winner_id": None, "log": [], "p1_hp": None, "p2_hp": None}
                winner_id, log, p1_hp, p2_hp = await self._run_ai_battle(p1_id, p2_id)
                match["winner_id"] = winner_id
                match["log"] = log[-ARENA_SHOW_LOG_LINES:]
                match["p1_hp"] = p1_hp
                match["p2_hp"] = p2_hp
                rond["matches"].append(match)
                round_winners.append(winner_id)

                bracket["rounds"].append(rond)
                embed = self._build_bracket_embed(bracket, tid)
                try:
                    await bracket_msg.edit(embed=embed)
                except Exception:
                    pass

            current_ids = round_winners + byes
            round_num += 1
            await asyncio.sleep(ARENA_BATTLE_DELAY)

        winner_id = current_ids[0]
        runner_up_id = None
        third_id = None

        all_finalists = set()
        for r in bracket["rounds"]:
            for m in r["matches"]:
                all_finalists.add(m["p1_id"])
                all_finalists.add(m["p2_id"])
        final_round = bracket["rounds"][-1] if bracket["rounds"] else None
        if final_round and final_round["matches"]:
            fm = final_round["matches"][0]
            runner_up_id = fm["p2_id"] if fm["winner_id"] == fm["p1_id"] else fm["p1_id"]

        if len(participants) >= 6:
            semi = bracket["rounds"][-2] if len(bracket["rounds"]) >= 2 else None
            if semi and semi["matches"]:
                third_candidates = []
                for m in semi["matches"]:
                    loser = m["p2_id"] if m["winner_id"] == m["p1_id"] else m["p1_id"]
                    if loser != winner_id and loser != runner_up_id:
                        third_candidates.append(loser)
                if third_candidates:
                    third_id = third_candidates[0]

        await self._give_rewards(tid, winner_id, runner_up_id, third_id, participants)

        embed = self._build_podium_embed(winner_id, runner_up_id, third_id, bracket["participants"], tid)
        await bracket_msg.edit(embed=embed)

        self._current_id = None
        self._current_status = None
```

Wait — this fighting phase has a bug: `bracket["rounds"].append(rond)` is inside the for-loop over pairs, which means each match creates a new round entry with only one match. That's wrong. The round should be appended once with all matches, after all matches are fought. Let me fix this in the plan.

- [ ] **Step 5 (fixed): Fighting phase**

```python
    async def _fighting_phase(self, channel_id: int, tid: int, participants: list[dict]):
        ch = self.bot.get_channel(channel_id)
        if not ch:
            await self._cancel_tournament(tid)
            return

        for p in participants:
            db2 = await get_db()
            try:
                row = await (await db2.execute("SELECT name FROM players WHERE id=?", (p["player_id"],))).fetchone()
                p["name"] = row["name"] if row else f"Player{p['player_id']}"
            finally:
                await db2.close()

        bracket = {
            "rounds": [],
            "participants": {p["player_id"]: {"name": p.get("name", "?"), "cp": p["cp_at_entry"]} for p in participants}
        }

        current_ids = list(bracket["participants"].keys())
        bye_history: set[str] = set()
        round_num = 1

        embed_msg = await ch.send(embed=discord.Embed(title="⚔️ Đấu Trường Sinh Tử — Đang chia cặp...", color=0xffaa00))

        while len(current_ids) > 1:
            random.shuffle(current_ids)
            pairs = []
            i = 0
            while i + 1 < len(current_ids):
                pairs.append((current_ids[i], current_ids[i + 1]))
                i += 2

            byes = []
            if i < len(current_ids):
                candidates = [pid for pid in current_ids[i:] if pid not in bye_history]
                if not candidates:
                    candidates = current_ids[i:]
                bye_pid = candidates[0]
                bye_history.add(bye_pid)
                byes.append(bye_pid)

            rond = {"name": f"Vòng {round_num}", "matches": [], "byes": byes}

            for p1_id, p2_id in pairs:
                winner_id, log, p1_hp, p2_hp = await self._run_ai_battle(p1_id, p2_id)
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

            embed = self._build_bracket_embed(bracket, tid)
            try:
                await embed_msg.edit(embed=embed)
            except Exception:
                pass
            await asyncio.sleep(ARENA_BATTLE_DELAY)

        winner_id = current_ids[0]
        runner_up_id = None
        third_id = None

        if len(bracket["rounds"]) >= 1:
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
                "UPDATE arena_tournament SET status='done', winner_id=?, runner_up_id=?, third_id=?, finished_at=?, bracket_json=? WHERE id=?",
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

        embed = self._build_podium_embed(winner_id, runner_up_id, third_id, bracket["participants"], tid)
        await embed_msg.edit(embed=embed)

        self._current_id = None
        self._current_status = None
```

- [ ] **Step 6: AI battle runner**

```python
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
        p1_hp, p2_hp = p1["hp"], p2["hp"]

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
                p1_hp = p1["hp"]
                p2_hp = p2["hp"]
                winner_id = result["winner_id"]
                return winner_id, all_logs, p1_hp, p2_hp

            turn = 1 - turn

        hp1 = p1.get("hp", 0)
        hp2 = p2.get("hp", 0)
        if hp1 > hp2:
            return p1_id, all_logs + [f"⏰ Hết lượt! {p1.get('name', '?')} thắng ({hp1} vs {hp2}HP)"], hp1, hp2
        elif hp2 > hp1:
            return p2_id, all_logs + [f"⏰ Hết lượt! {p2.get('name', '?')} thắng ({hp2} vs {hp1}HP)"], hp1, hp2
        return random.choice([p1_id, p2_id]), all_logs + ["⏰ Hòa! Random thắng..."], hp1, hp2
```

- [ ] **Step 7: Bracket embed builder**

```python
    def _build_bracket_embed(self, bracket: dict, tid: int) -> discord.Embed:
        desc_lines = [f"⚔️ **ĐẤU TRƯỜNG SINH TỬ #{tid}** — LIVE\n"]
        parts = bracket["participants"]

        for i, rond in enumerate(bracket["rounds"]):
            desc_lines.append(f"🏟️ **{rond['name']}**")
            for m in rond["matches"]:
                p1n = parts[m["p1_id"]]["name"]
                p2n = parts[m["p2_id"]]["name"]
                if m["winner_id"]:
                    wname = parts[m["winner_id"]]["name"]
                    desc_lines.append(f"  ✅ **{wname}** thắng {p1n if m['winner_id'] != m['p1_id'] else ''}{p2n if m['winner_id'] != m['p2_id'] else ''}")
                    for line in m.get("log", []):
                        desc_lines.append(f"     _{line}_")
                else:
                    desc_lines.append(f"  🔄 **{p1n}** ⚔️ VS 🛡️ **{p2n}**")
            for bye in rond.get("byes", []):
                desc_lines.append(f"  💎 **{parts[bye]['name']}** BYE — vào thẳng vòng sau")
            if i < len(bracket["rounds"]) - 1 or any(not m["winner_id"] for m in rond["matches"]):
                desc_lines.append("")

        return discord.Embed(
            title=f"⚔️ Đấu Trường Sinh Tử #{tid} — LIVE",
            description="\n".join(desc_lines),
            color=0xffaa00,
        )
```

- [ ] **Step 8: Podium embed + reward distributor**

```python
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
                if "equip_chance" in rw and random.random() > rw["equip_chance"]:
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
```

- [ ] **Step 9: Cancel tournament helper**

```python
    async def _cancel_tournament(self, tid: int):
        db = await get_db()
        try:
            await db.execute("UPDATE arena_tournament SET status='cancelled', finished_at=? WHERE id=?", (time.time(), tid))
            await db.commit()
        finally:
            await db.close()
        self._current_id = None
        self._current_status = None
```

- [ ] **Step 10: Commit**

```bash
git add bot/cogs/arena_tournament.py
git commit -m "feat: arena tournament cog — auto-bracket, AI battles, rewards"
```

---

### Task 6: Admin Commands + Wire Up

**Files:**
- Modify: `bot/cogs/arena_tournament.py` (extend)
- Modify: `main.py`

- [ ] **Step 1: Add admin slash commands**

Add these methods to the `ArenaTournament` class in `bot/cogs/arena_tournament.py`:

```python
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
            global ARENA_AUTO_ENABLED
            ARENA_AUTO_ENABLED = not ARENA_AUTO_ENABLED
            if ARENA_AUTO_ENABLED:
                self._auto_schedule.start()
            else:
                self._auto_schedule.cancel()
            status = "BẬT" if ARENA_AUTO_ENABLED else "TẮT"
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
```

- [ ] **Step 2: Add history command**

```python
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
```

- [ ] **Step 3: Register cog in main.py**

In `main.py`, in `load_extensions()`, add after the quiz cog:

```python
    await bot.load_extension("bot.cogs.arena_tournament")
```

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/arena_tournament.py main.py
git commit -m "feat: arena admin commands + history + wire up"
```
