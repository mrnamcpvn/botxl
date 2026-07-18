# Combat Power & Stats Tabs Design

## Summary
Add a "Lực Chiến" (Combat Power) system that aggregates all character attributes into a single power score, and reorganize the `/stats` and `/leaderboard` pages into tabbed views using Discord button components.

## Combat Power Formula

```
LC = HP*1 + ATK_avg*2 + DEF*3 + SPD*10 + CRIT*3 + PIERCE*3 + DODGE*5 + REFLECT*8 + REGEN*4 + Level*10 + EQStarTotal*80 + WifeLevelTotal*30 + UpHP*5 + UpATK*8 + UpDEF*8 + DamagePct*5
```

Where:
- `HP`, `ATK_avg` `= (attack_min + attack_max) / 2`, `DEF`, `SPD`, `CRIT`, `PIERCE`, `DODGE`, `REFLECT`, `REGEN` = effective stats from `get_effective_stats()`
- `EQStarTotal` = sum of `EQUIPMENT[eid].star` for all 6 equipped slots
- `WifeLevelTotal` = sum of `level` for all equipped wives (max 2)
- `UpHP`/`UpATK`/`UpDEF` = `upgrade_hp`/`upgrade_atk`/`upgrade_def`
- `DamagePct` = `damage_pct` from passive skill (if > 0)

New character baseline (level 1, banxabong, no upgrades/equip/wife):
- 120 + 14.5*2 + 8*3 + 0 + 0 + 0 + 0 + 0 + 0 + 10 + 0 + 0 + 0 + 0 + 0 = 183 ≈ 200

### Implementation
- Add `calc_combat_power(pdata, wives_data=None)` to `bot/engine/combat_power.py`
- Also add a standalone SQL query helper for leaderboard sorting (to avoid loading full `get_effective_stats` for every player)
- Store a `combat_power` column in `players` table (updated on `/stats` view and after battles)

## Stats Page: 3-Tab Button View

Replace the current single `stats_embed()` with a `StatsView` (persistent `discord.ui.View`):

### Tab 1: "📊 Thuộc Tính" (Attributes)
- Lực Chiến displayed prominently at top (e.g. `⚔️ Lực Chiến: 1,234`)
- Same as current embed: HP bar, ATK range, DEF, SPD/CRIT, Level/XP, Class, Wins/Losses, Buffs
- Show breakdown: contributions from base stats + equipment + skills + wives

### Tab 2: "⚒️ Trang Bị" (Equipment)
- Per-slot display of equipped items (same as current `⚒️ Trang Bị` field)
- Below: list of owned equipment in inventory (from `player_equipment`)

### Tab 3: "🔥 Kỹ Năng" (Skills)
- 4 equipped skills display (same as current `🔥 Kỹ Năng` field)
- Below: list of all owned skills (from `player_skills`)

### UI
- 3 buttons labeled `📊 Thuộc Tính`, `⚒️ Trang Bị`, `🔥 Kỹ Năng`
- Only the active tab's button is greyed out (disabled style)
- Same embed color `0x00ff88`

## Leaderboard: Multi-Tab Button View

Replace current single leaderboard with `LeaderboardView`:

### Tab 1: "⚔️ Lực Chiến"
- `SELECT * FROM players ORDER BY combat_power DESC LIMIT 10`
- Display: rank, name, class icon, combat power, level, wins/losses

### Tab 2: "📊 Level"
- Same as current ELO leaderboard but renamed to Level sorting
- `SELECT * FROM players ORDER BY level DESC, xp DESC LIMIT 10`

### Tab 3: "💰 Coin"
- `SELECT * FROM players ORDER BY coins DESC LIMIT 10`

## Files Changed

| File | Change |
|---|---|
| `bot/engine/combat_power.py` | **New** — `calc_combat_power()` function |
| `bot/database.py` | Add `combat_power INTEGER DEFAULT 0` column migration |
| `bot/cogs/arena.py` | Refactor `stats_embed` → `StatsView`; refactor leaderboard → `LeaderboardView`; add `_load_pdata()` helper; update slash/prefix commands |
| `bot/views/stats_view.py` | **New** — `StatsView` with 3 tab buttons |
| `bot/views/leaderboard_view.py` | **New** — `LeaderboardView` with 3 tab buttons |
| `bot/engine/battle.py` | No change needed (combat_power formula is separate) |

## Testing

No specific test changes needed — existing battle tests remain valid since combat power is display-only.

## Self-Review

- [x] Placeholders: none
- [x] Internal consistency: formula matches effective stats; tabs split logically
- [x] Scope: focused on stats display + leaderboard; no gameplay changes
- [x] Ambiguity: combat_power updated on `/stats` and after battles; leaderboard sorting is SQL-level
