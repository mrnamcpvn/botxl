# Monster Codex / Đồ Thư Quái Vật — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Track kills per NPC — at milestones unlock permanent % stat bonuses applied globally. `!codex` command to view progress.

**Architecture:** `monster_codex.py` cog for the view command. Config stores all 30 NPC codex data. `npc.py` increments kill count on NPC death. Battle engine + rewards apply bonuses.

**Tech Stack:** Python 3.11+, discord.py, aiosqlite

---

## Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add CODEX_MILESTONES + CODEX_DATA |
| `bot/database.py` | Modify — add monster_codex table |
| `bot/cogs/monster_codex.py` | Create — !codex command |
| `bot/engine/battle.py` | Modify — apply combat codex bonus |
| `bot/engine/rewards.py` | Modify — apply coin/xp/drop codex bonus |
| `bot/cogs/npc.py` | Modify — increment kills on NPC death |
| `main.py` | Modify — load monster_codex cog |

---

### Task 1: Codex Config

**Files:**
- Modify: `bot/config.py`

Append at end:

```python
# ── Monster Codex / Đồ Thư ──────────────────────────────────
CODEX_MILESTONES = [100, 500, 1000, 10000]

CODEX_DATA = {
    1:  {"bonus": "coin",   "tiers": [4, 8, 12, 20]},
    2:  {"bonus": "xp",     "tiers": [4, 8, 12, 20]},
    3:  {"bonus": "def",    "tiers": [3, 6, 9, 15]},
    4:  {"bonus": "pierce", "tiers": [3, 5, 8, 12]},
    5:  {"bonus": "hp",     "tiers": [3, 5, 8, 12]},
    6:  {"bonus": "spd",    "tiers": [3, 5, 8, 12]},
    7:  {"bonus": "dmg",    "tiers": [3, 5, 8, 11]},
    8:  {"bonus": "crit",   "tiers": [2, 4, 6, 9]},
    9:  {"bonus": "dmg",    "tiers": [3, 6, 9, 14]},
    10: {"bonus": "spd",    "tiers": [3, 5, 8, 11]},
    11: {"bonus": "def",    "tiers": [4, 7, 10, 16]},
    12: {"bonus": "crit",   "tiers": [3, 5, 8, 11]},
    13: {"bonus": "pierce", "tiers": [3, 6, 9, 14]},
    14: {"bonus": "all",    "tiers": [2, 3, 5, 8]},
    15: {"bonus": "drop",   "tiers": [2, 4, 6, 9]},
    16: {"bonus": "spd",    "tiers": [3, 6, 9, 14]},
    17: {"bonus": "hp",     "tiers": [4, 8, 11, 16]},
    18: {"bonus": "xp",     "tiers": [5, 9, 13, 21]},
    19: {"bonus": "dmg",    "tiers": [4, 7, 10, 16]},
    20: {"bonus": "hp",     "tiers": [5, 8, 12, 18]},
    21: {"bonus": "crit",   "tiers": [3, 6, 9, 14]},
    22: {"bonus": "dmg",    "tiers": [4, 8, 11, 16]},
    23: {"bonus": "xp",     "tiers": [6, 10, 15, 23]},
    24: {"bonus": "crit",   "tiers": [4, 7, 10, 15]},
    25: {"bonus": "def",    "tiers": [4, 8, 11, 16]},
    26: {"bonus": "dmg",    "tiers": [5, 8, 12, 18]},
    27: {"bonus": "pierce", "tiers": [4, 8, 11, 16]},
    28: {"bonus": "all",    "tiers": [2, 4, 6, 10]},
    29: {"bonus": "all",    "tiers": [3, 5, 8, 12]},
    30: {"bonus": "all",    "tiers": [3, 6, 9, 14]},
}
```

Commit: `git add bot/config.py && git commit -m "feat: add codex config"`

---

### Task 2: Codex DB Table

**Files:**
- Modify: `bot/database.py`

Add to TABLES:

```python
    """CREATE TABLE IF NOT EXISTS monster_codex (
        player_id TEXT NOT NULL,
        npc_id INTEGER NOT NULL,
        kills INTEGER DEFAULT 0,
        PRIMARY KEY (player_id, npc_id)
    )""",
```

Add index:

```python
        "CREATE INDEX IF NOT EXISTS idx_monster_codex_player ON monster_codex(player_id)",
```

Commit: `git add bot/database.py && git commit -m "feat: add monster_codex table"`

---

### Task 3: Codex Bonus Helper + Battle Engine

**Files:**
- Modify: `bot/engine/battle.py`

In `bot/engine/battle.py`, add this helper function at module level:

```python
def get_codex_bonus(pdata: dict) -> dict:
    """Returns dict of bonus % multipliers from monster codex."""
    from bot.config import CODEX_DATA, CODEX_MILESTONES
    codex_kills = pdata.get("_codex_kills", {})
    if not codex_kills:
        return {}
    bonuses: dict[str, int] = {}
    for npc_id_str, kills in codex_kills.items():
        npc_id = int(npc_id_str)
        cd = CODEX_DATA.get(npc_id)
        if not cd:
            continue
        bonus_type = cd["bonus"]
        for i, milestone in enumerate(CODEX_MILESTONES):
            if kills >= milestone:
                tier_bonus = cd["tiers"][i] if i < len(cd["tiers"]) else cd["tiers"][-1]
                bonuses[bonus_type] = bonuses.get(bonus_type, 0) + tier_bonus
            else:
                break
    return bonuses
```

Then in `get_effective_stats()`, after the gem stats section (after the codex bonus check — actually we want codex AFTER artifact multiplier to avoid double-dipping), add at the end of the function, just before `return`, when stats are already computed:

After the `hp_max = int(hp_max * GLOBAL_HP_MULT)` line (around line 161), add:

```python
    # Monster Codex bonus (global, permanent)
    codex = get_codex_bonus(pdata)
    if codex:
        mult_all = 1 + codex.get("all", 0) / 100
        mult_hp = 1 + (codex.get("hp", 0) + codex.get("all", 0)) / 100
        mult_dmg = 1 + (codex.get("dmg", 0) + codex.get("all", 0)) / 100
        mult_def = 1 + (codex.get("def", 0) + codex.get("all", 0)) / 100
        hp_max = int(hp_max * mult_hp)
        atk_min = int(atk_min * mult_dmg)
        atk_max = int(atk_max * mult_dmg)
        defense = int(defense * mult_def)
        spd += int(spd * (codex.get("spd", 0) + codex.get("all", 0)) / 100)
        crit += int(crit * (codex.get("crit", 0) + codex.get("all", 0)) / 100)
        pierce += int(pierce * (codex.get("pierce", 0) + codex.get("all", 0)) / 100)
```

Commit: `git add bot/engine/battle.py && git commit -m "feat: apply codex bonuses in battle engine"`

---

### Task 4: Codex Coin/XP/Drop Bonus in Rewards

**Files:**
- Modify: `bot/engine/rewards.py`

In `calc_rewards()`, add codex multiplier for coin + XP:

At the end of the function, just before `return coins, xp`:

```python
    return coins, xp
```

Change to:

```python
    from bot.config import CODEX_DATA, CODEX_MILESTONES
    # Codex coin/xp bonus
    codex_kills = getattr(calc_rewards, '_codex_kills', {})
    codex_coin_bonus = 0
    codex_xp_bonus = 0
    codex_drop_bonus = 0
    for npc_id_str, kills in codex_kills.items():
        cd = CODEX_DATA.get(int(npc_id_str))
        if not cd:
            continue
        bt = cd["bonus"]
        for i, ms in enumerate(CODEX_MILESTONES):
            if kills >= ms and i < len(cd["tiers"]):
                if bt == "coin":
                    codex_coin_bonus += cd["tiers"][i]
                elif bt == "xp":
                    codex_xp_bonus += cd["tiers"][i]
                elif bt == "drop":
                    codex_drop_bonus += cd["tiers"][i]
                elif bt == "all":
                    codex_coin_bonus += cd["tiers"][i]
                    codex_xp_bonus += cd["tiers"][i]
                    codex_drop_bonus += cd["tiers"][i]
            else:
                break
    coins = int(coins * (1 + codex_coin_bonus / 100))
    xp = int(xp * (1 + codex_xp_bonus / 100))
    return coins, xp
```

Wait — this approach is flawed. `calc_rewards` doesn't have access to codex data per-player. The codex bonus for coin/XP/drop should be applied in the NPC fight handler (npc.py) after rewards are calculated.

Let me fix: instead of modifying `rewards.py`, apply the bonus in `npc.py` after `calc_rewards()`. But for drops, I need to check `calc_drop()` which already uses `DROP_CHANCE`.

Actually simpler: add a helper in the codex module to compute coin/xp/drop bonus from codex data, and call it in npc.py.

Let me restructure:

Create `bot/engine/codex.py` (or put a helper in config/npc.py):

Actually simplest: put the helper in `bot/config.py` or create a small utility. But we don't want to create too many files. Let me just apply the coin/xp bonus directly in npc.py and the drop bonus in the drop calculation.

**Revised approach for Task 4:** Modify `bot/cogs/npc.py` to apply codex coin/xp bonus. Modify `bot/engine/rewards.py` `calc_drop()` to accept and apply codex drop bonus.

Let me split this into what actually goes in the plan: modify npc.py for coin/xp/drop, and keep it simple.

Actually, let me also think about where to put the codex bonus retrieval. The helper `get_codex_bonus()` in battle.py is for combat stats. For coin/XP/drop, I need a separate function or access the same logic.

Best: create a small utility function in `bot/engine/codex.py`:

```python
def get_codex_stats(codex_kills: dict) -> dict[str, int]:
    """Returns {bonus_type: total_%} from all codex entries."""
    from bot.config import CODEX_DATA, CODEX_MILESTONES
    bonuses = {}
    for npc_id_str, kills in codex_kills.items():
        cd = CODEX_DATA.get(int(npc_id_str))
        if not cd:
            continue
        bt = cd["bonus"]
        for i, ms in enumerate(CODEX_MILESTONES):
            if kills >= ms and i < len(cd["tiers"]):
                bonuses[bt] = bonuses.get(bt, 0) + cd["tiers"][i]
            else:
                break
    return bonuses
```

Then `get_codex_bonus(pdata)` in battle.py and the coin/xp bonus in npc.py can both use this.

OK let me write the clean plan with this approach.<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write">
<｜｜DSML｜｜parameter name="content" string="true"># Monster Codex / Đồ Thư Quái Vật — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Track kills per NPC — at milestones unlock permanent % stat bonuses applied globally. `!codex` command to view progress.

**Architecture:** `monster_codex.py` cog for the view command. Config stores all 30 NPC codex data. `npc.py` increments kill count on NPC death. Battle engine + rewards apply bonuses. Shared helper in `bot/engine/codex.py`.

**Tech Stack:** Python 3.11+, discord.py, aiosqlite

---

## Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add CODEX_MILESTONES + CODEX_DATA |
| `bot/database.py` | Modify — add monster_codex table |
| `bot/engine/codex.py` | Create — codex bonus calculator |
| `bot/engine/battle.py` | Modify — apply combat codex bonus |
| `bot/engine/rewards.py` | Modify — apply drop codex bonus |
| `bot/cogs/npc.py` | Modify — increment kills + apply coin/xp bonus |
| `bot/cogs/monster_codex.py` | Create — !codex command |
| `main.py` | Modify — load monster_codex cog |

---

### Task 1: Codex Config

**Files:**
- Modify: `bot/config.py`

Append at end:

```python
# ── Monster Codex / Đồ Thư ──────────────────────────────────
CODEX_MILESTONES = [100, 500, 1000, 10000]

CODEX_DATA = {
    1:  {"bonus": "coin",   "tiers": [4, 8, 12, 20]},
    2:  {"bonus": "xp",     "tiers": [4, 8, 12, 20]},
    3:  {"bonus": "def",    "tiers": [3, 6, 9, 15]},
    4:  {"bonus": "pierce", "tiers": [3, 5, 8, 12]},
    5:  {"bonus": "hp",     "tiers": [3, 5, 8, 12]},
    6:  {"bonus": "spd",    "tiers": [3, 5, 8, 12]},
    7:  {"bonus": "dmg",    "tiers": [3, 5, 8, 11]},
    8:  {"bonus": "crit",   "tiers": [2, 4, 6, 9]},
    9:  {"bonus": "dmg",    "tiers": [3, 6, 9, 14]},
    10: {"bonus": "spd",    "tiers": [3, 5, 8, 11]},
    11: {"bonus": "def",    "tiers": [4, 7, 10, 16]},
    12: {"bonus": "crit",   "tiers": [3, 5, 8, 11]},
    13: {"bonus": "pierce", "tiers": [3, 6, 9, 14]},
    14: {"bonus": "all",    "tiers": [2, 3, 5, 8]},
    15: {"bonus": "drop",   "tiers": [2, 4, 6, 9]},
    16: {"bonus": "spd",    "tiers": [3, 6, 9, 14]},
    17: {"bonus": "hp",     "tiers": [4, 8, 11, 16]},
    18: {"bonus": "xp",     "tiers": [5, 9, 13, 21]},
    19: {"bonus": "dmg",    "tiers": [4, 7, 10, 16]},
    20: {"bonus": "hp",     "tiers": [5, 8, 12, 18]},
    21: {"bonus": "crit",   "tiers": [3, 6, 9, 14]},
    22: {"bonus": "dmg",    "tiers": [4, 8, 11, 16]},
    23: {"bonus": "xp",     "tiers": [6, 10, 15, 23]},
    24: {"bonus": "crit",   "tiers": [4, 7, 10, 15]},
    25: {"bonus": "def",    "tiers": [4, 8, 11, 16]},
    26: {"bonus": "dmg",    "tiers": [5, 8, 12, 18]},
    27: {"bonus": "pierce", "tiers": [4, 8, 11, 16]},
    28: {"bonus": "all",    "tiers": [2, 4, 6, 10]},
    29: {"bonus": "all",    "tiers": [3, 5, 8, 12]},
    30: {"bonus": "all",    "tiers": [3, 6, 9, 14]},
}
```

Commit: `git add bot/config.py && git commit -m "feat: add codex config"`

---

### Task 2: Codex DB Table

**Files:**
- Modify: `bot/database.py`

Add to TABLES list (before `]`):

```python
    """CREATE TABLE IF NOT EXISTS monster_codex (
        player_id TEXT NOT NULL,
        npc_id INTEGER NOT NULL,
        kills INTEGER DEFAULT 0,
        PRIMARY KEY (player_id, npc_id)
    )""",
```

Add to `_create_indexes`:

```python
        "CREATE INDEX IF NOT EXISTS idx_monster_codex_player ON monster_codex(player_id)",
```

Commit: `git add bot/database.py && git commit -m "feat: add monster_codex table"`

---

### Task 3: Codex Bonus Calculator (Shared Engine)

**Files:**
- Create: `bot/engine/codex.py`

```python
from bot.config import CODEX_DATA, CODEX_MILESTONES


def get_codex_bonuses(codex_kills: dict[str, int]) -> dict[str, int]:
    """Tính tổng % bonus từ tất cả codex entries.
    Returns {bonus_type: total_pct} (coin, xp, dmg, hp, def, spd, crit, pierce, drop, all)
    """
    bonuses: dict[str, int] = {}
    for npc_id_str, kills in codex_kills.items():
        npc_id = int(npc_id_str)
        cd = CODEX_DATA.get(npc_id)
        if not cd:
            continue
        bt = cd["bonus"]
        for i, ms in enumerate(CODEX_MILESTONES):
            if kills >= ms and i < len(cd["tiers"]):
                bonuses[bt] = bonuses.get(bt, 0) + cd["tiers"][i]
            else:
                break
    return bonuses
```

Commit: `git add bot/engine/codex.py && git commit -m "feat: codex bonus calculator engine"`

---

### Task 4: Apply Codex in Battle Engine

**Files:**
- Modify: `bot/engine/battle.py`

In `bot/engine/battle.py`, import codex at top:

```python
from bot.engine.codex import get_codex_bonuses
```

In `get_effective_stats()`, after the global multiplier section (lines `hp_max = int(hp_max * GLOBAL_HP_MULT)...`), add before `return`:

```python
    # Monster Codex bonus (global, permanent, áp sau artifact để không nhân kép)
    codex_kills = pdata.get("_codex_kills", {})
    if codex_kills:
        cb = get_codex_bonuses(codex_kills)
        if cb:
            all_pct = cb.get("all", 0)
            mult_hp = 1 + (cb.get("hp", 0) + all_pct) / 100
            mult_dmg = 1 + (cb.get("dmg", 0) + all_pct) / 100
            mult_def = 1 + (cb.get("def", 0) + all_pct) / 100
            hp_max = int(hp_max * mult_hp)
            atk_min = int(atk_min * mult_dmg)
            atk_max = int(atk_max * mult_dmg)
            defense = int(defense * mult_def)
            spd += spd * (cb.get("spd", 0) + all_pct) // 100
            crit += crit * (cb.get("crit", 0) + all_pct) // 100
            pierce += pierce * (cb.get("pierce", 0) + all_pct) // 100
```

Commit: `git add bot/engine/battle.py && git commit -m "feat: apply codex combat bonuses in battle engine"`

---

### Task 5: Apply Codex Coin/XP/Drop + NPC Kill Tracking

**Files:**
- Modify: `bot/cogs/npc.py`
- Modify: `bot/engine/rewards.py`

**Step A: npc.py — track kills + apply coin/xp bonus**

In `bot/cogs/npc.py`, in `_finish_npc_battle` (the NPC death handler), after the player wins (around line 550-560 where rewards are distributed):

```python
            # Codex: tăng kill count
            await db.execute(
                "INSERT INTO monster_codex (player_id, npc_id, kills) VALUES (?, ?, 1) "
                "ON CONFLICT(player_id, npc_id) DO UPDATE SET kills=kills+1",
                (sid, npc_id))
            await db.commit()

            # Codex coin/xp bonus
            codex_cursor = await db.execute(
                "SELECT npc_id, kills FROM monster_codex WHERE player_id=?", (sid,))
            codex_kills = {str(r[0]): r[1] for r in await codex_cursor.fetchall()}
            cb = get_codex_bonuses(codex_kills)
            if cb:
                coin_pct = cb.get("coin", 0) + cb.get("all", 0)
                xp_pct = cb.get("xp", 0) + cb.get("all", 0)
                if coin_pct:
                    extra_coins = int(reward_coins * coin_pct / 100)
                    player["coins"] = player.get("coins", 0) + extra_coins
                    reward_coins += extra_coins
                    result_lines.append(f"📖 Codex: +{extra_coins}🪙 (+{coin_pct}%)")
                if xp_pct:
                    extra_xp = int(reward_xp * xp_pct / 100)
                    player["xp"] = player.get("xp", 0) + extra_xp
                    reward_xp += extra_xp
                    result_lines.append(f"📖 Codex: +{extra_xp}XP (+{xp_pct}%)")
```

Add import at top of npc.py:

```python
from bot.engine.codex import get_codex_bonuses
```

**Step B: rewards.py — codex drop bonus**

In `bot/engine/rewards.py`, in `calc_drop()`, add codex drop bonus. The function currently takes `role_mult`. Add a new parameter `codex_drop_pct`:

```python
def calc_drop(role_mult: float = 1.0, codex_drop_pct: int = 0) -> dict | None:
    chance = DROP_CHANCE * role_mult
    if codex_drop_pct:
        chance *= (1 + codex_drop_pct / 100)
    if random.random() > chance:
        return None
    ...
```

Then in npc.py where `calc_drop` is called, pass the drop bonus:

```python
                drop_pct = cb.get("drop", 0) + cb.get("all", 0) if cb else 0
                drop = calc_drop(player.get("role_mult", 1.0), drop_pct)
```

Also update the import in npc.py to include the updated signature. The battle_view.py also calls `calc_drop` — it should pass 0 (no codex bonus in PvP).

Commit: `git add bot/cogs/npc.py bot/engine/rewards.py && git commit -m "feat: codex kill tracking + coin/xp/drop bonuses in NPC fights"`

---

### Task 6: Codex Cog (View Command)

**Files:**
- Create: `bot/cogs/monster_codex.py`

```python
import discord
from discord.ext import commands
from bot.database import get_db
from bot.config import CODEX_DATA, CODEX_MILESTONES
from bot.data.npcs import NPCS
from bot.engine.codex import get_codex_bonuses


class MonsterCodex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="codex", aliases=["dothu"])
    async def codex(self, ctx, npc_num: int = None):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT npc_id, kills FROM monster_codex WHERE player_id=? ORDER BY npc_id", (sid,))
            rows = await cursor.fetchall()
        finally:
            await db.close()

        codex_kills = {str(r[0]): r[1] for r in rows}

        if npc_num:
            await self._show_npc_detail(ctx, npc_num, codex_kills)
            return

        embed = self._build_codex_overview(codex_kills)
        await ctx.reply(embed=embed)

    def _build_codex_overview(self, codex_kills: dict) -> discord.Embed:
        bonuses = get_codex_bonuses(codex_kills) if codex_kills else {}
        total_kills = sum(codex_kills.values())

        lines = []
        completed = 0
        for npc_id in sorted(CODEX_DATA.keys()):
            kills = codex_kills.get(str(npc_id), 0)
            cd = CODEX_DATA[npc_id]
            npc = NPCS.get(npc_id, {})
            name = npc.get("name", f"NPC #{npc_id}")
            bonus_type = cd["bonus"]

            tier = 0
            for i, ms in enumerate(CODEX_MILESTONES):
                if kills >= ms:
                    tier = i + 1
                else:
                    break
            tier_str = {0: "⬛", 1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}.get(tier, "⬛")
            lines.append(f"{tier_str} **{name}**: {kills}/{CODEX_MILESTONES[-1]} ({bonus_type.upper()})")

        bonus_lines = []
        for bt, pct in bonuses.items():
            bonus_lines.append(f"{bt.upper()}: +{pct}%")
        bonus_text = " · ".join(bonus_lines) if bonus_lines else "_Chưa có bonus nào_"

        embed = discord.Embed(
            title="📖 Đồ Thư Quái Vật",
            description=f"Tổng kills: **{total_kills}**\n\n" + "\n".join(lines[:15]),
            color=0x8b4513,
        )
        embed.add_field(name="📊 Tổng Bonus", value=bonus_text, inline=False)
        embed.set_footer(text="!codex <số> để xem chi tiết từng NPC")
        return embed

    async def _show_npc_detail(self, ctx, npc_id: int, codex_kills: dict):
        cd = CODEX_DATA.get(npc_id)
        npc = NPCS.get(npc_id)
        if not cd or not npc:
            await ctx.reply("❌ NPC không tồn tại!")
            return

        kills = codex_kills.get(str(npc_id), 0)
        lines = [
            f"**{npc['name']}** — Lv.{npc.get('level', '?')}",
            f"Bonus: **{cd['bonus'].upper()}**",
            f"Đã giết: **{kills}**",
            "",
            "📊 Mốc thưởng:",
        ]
        tier_labels = {0: "⬛ Chưa đạt", 1: "🥉 Đồng", 2: "🥈 Bạc", 3: "🥇 Vàng", 4: "💎 Kim Cương"}
        for i, (ms, pct) in enumerate(zip(CODEX_MILESTONES, cd["tiers"])):
            achieved = "✅" if kills >= ms else "☐"
            lines.append(f"{achieved} {ms} kills → +{pct}% {cd['bonus'].upper()} ({tier_labels.get(i+1, '')})")

        embed = discord.Embed(
            title=f"📖 Đồ Thư — {npc['name']}",
            description="\n".join(lines),
            color=0x8b4513,
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(MonsterCodex(bot))
```

Commit: `git add bot/cogs/monster_codex.py && git commit -m "feat: monster codex cog — !codex command"`

---

### Task 7: Load codex kills in player loader + wire up

**Files:**
- Modify: `bot/utils/player_loader.py`
- Modify: `main.py`

**Step A: player_loader.py** — load codex kills for battle engine access. Add after `pdata["_artifact_stones"] = ...` (around line 84):

```python
    codex_cursor = await db.execute(
        "SELECT npc_id, kills FROM monster_codex WHERE player_id=?", (pid,))
    codex_kills = {}
    async for cr in codex_cursor:
        codex_kills[str(cr[0])] = cr[1]
    pdata["_codex_kills"] = codex_kills
```

**Step B: main.py** — in `load_extensions()`, add:

```python
    await bot.load_extension("bot.cogs.monster_codex")
```

Commit: `git add bot/utils/player_loader.py main.py && git commit -m "feat: load codex kills in player loader + wire up"`
