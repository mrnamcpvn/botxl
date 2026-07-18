# Bot-XL Rewrite Design

## Overview
Complete rewrite of bot-xl — a Discord PvP turn-based RPG "Đấu Trường Ba Que Xỏ Lá" — from monolithic JSON-based architecture to modular monolith with SQLite, class system, ELO ranking, daily quests, battle replay, and web dashboard.

## Architecture

### Project Structure
```
bot-xl/
├── main.py                        # Bot entry point
├── web_dashboard.py               # FastAPI server entry point
├── requirements.txt
├── .env
├── .gitignore
├── bot/
│   ├── __init__.py
│   ├── config.py                  # Constants (skills, shop, classes, v.v.)
│   ├── logger.py                  # logging setup
│   ├── database.py                # SQLite connection + migrations
│   ├── models/
│   │   ├── player.py              # Player dataclass
│   │   └── battle.py              # Battle state dataclass
│   ├── engine/
│   │   ├── battle.py              # Pure battle logic (no Discord deps)
│   │   ├── rewards.py             # XP/coin/ELO calculation
│   │   └── ranking.py             # ELO system
│   ├── cogs/
│   │   ├── arena.py               # Core game commands (thin)
│   │   ├── shop.py                # Shop/inventory commands
│   │   └── admin.py               # Admin commands
│   ├── views/
│   │   ├── battle_view.py         # BattleView (Discord UI)
│   │   └── challenge_view.py      # ChallengeView
│   └── data/
│       ├── skills.py              # Skill definitions
│       ├── shop_items.py          # Shop definitions
│       └── classes.py             # Class definitions
├── web/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app init
│   ├── templates/                 # Jinja2
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── player.html
│   │   ├── leaderboard.html
│   │   └── battle_replay.html
│   ├── static/
│   │   ├── style.css
│   │   └── app.js
│   └── routes/
│       ├── players.py
│       └── battles.py
├── scripts/
│   └── migrate_json_to_sqlite.py
└── tests/
    ├── conftest.py
    ├── test_battle_engine.py
    ├── test_rewards.py
    └── test_ranking.py
```

### Key Design Decisions
- **Modular monolith**: Single deployable unit, clear module boundaries
- **SQLite**: aiosqlite with async queries, transaction support, migration from JSON
- **Battle engine**: Pure functions — no Discord dependencies, testable
- **Pattern**: Cog (thin router) → Engine (pure logic) → Data (SQLite)

## Database Schema (SQLite)

### players
Column | Type | Description
-------|------|-------------
id | TEXT PK | Discord user ID
name | TEXT | Display name
class_id | TEXT | Class key (e.g. "banxabong")
hp | INT | Current HP
hp_max | INT | Max HP
attack_min | INT | Min attack
attack_max | INT | Max attack
defense | INT | Defense stat
wins | INT | Total wins
losses | INT | Total losses
damage_dealt | INT | Total damage dealt
damage_taken | INT | Total damage taken
coins | INT | Currency
xp | INT | Experience
level | INT | Current level
stat_points | INT | Unspent stat points
elo | INT | ELO rating (default 1000)
attack_cd | INT | Attack skill cooldown
special_cd | INT | Special skill cooldown
defense_cd | INT | Defense skill cooldown
last_hp_update | REAL | Timestamp for HP regen
created_at | TEXT | Registration timestamp

### player_skills (many-to-many)
- player_id, skill_id (composite PK)

### player_skill_slots (4 equipped skills)
- player_id, slot (attack/special/defense/passive), skill_id

### player_equipment (owned items)
- player_id, item_id, quantity

### player_equip_slots (equipped gear)
- player_id, slot (weapon/armor/accessory/crown), item_id

### inventory (consumables)
- player_id, item_id, quantity

### player_buffs
- player_id, attack_boost, defense_boost, lucky

### active_battles (ongoing fights)
- id, player1_id, player2_id, turn, p1_defending, p2_defending, p1_stunned, p2_stunned, channel_id, last_move, created_at

### battle_status (battle-specific effects like shield, counter, burn, rage)
- battle_id, player_id, key, value

### battle_history (recorded fights for replay)
- id, player1_id, player2_id, p1_name, p2_name, winner_id, rounds (JSON), fought_at

### challenges (pending duel requests)
- target_id, challenger_id, channel_id, created_at

### daily_quests (quest progress tracking)
- player_id, quest_id, progress, target, completed, claimed, date

## Class System

### Class Definitions
| Key | Name | Icon | Price | Perk |
|-----|------|------|-------|------|
| banxabong | Bán Xà Bông | 🧼 | 0 | None (base class) |
| xola | Xỏ Lá | 🤓 | 500 | -10% dmg khi đang phòng thủ |
| sieunhan | Siêu Nhân Xà Phòng | 💪 | 500 | Đòn đầu trận ×1.5 |
| thaychua | Thầy Chùa | 🙏 | 500 | Cooldown tất cả -1 |
| muoi | Con Muỗi | 🦟 | 1000 | Hút máu +20% hiệu quả |
| chodien | Chó Điên | 🐕 | 1000 | Rage tích +25% |
| baque | Ba Que | 🥢 | 2000 | Last stand ở 40% HP |
| trumcuoi | Trùm Cuối Special | 👑 | -1 (admin) | Random buff mỗi turn |

### Stat Scaling
```
hp = class.hp_base + class.hp_scale * (level - 1) + upgrade_hp * 10
atk_min = class.atk_base + class.atk_scale * (level - 1) + upgrade_atk * 2
atk_max = atk_min + 5 + upgrade_atk
def = class.def_base + class.def_scale * (level - 1) + upgrade_def * 2
```

## Battle Engine

Pure function design in `bot/engine/battle.py`:
- `execute_action(p1_snapshot, p2_snapshot, turn_player, action, battle_flags) → RoundResult`
- `calculate_damage(atk_min, atk_max, defense, skill, buffs, damage_pct_bonus, is_defending) → DamageResult`

No Discord dependencies. Cog layer handles:
1. Load from SQLite → build snapshots
2. Call `execute_action()`
3. Save results to SQLite + `battle_history`
4. Render Discord embed

## ELO Ranking

Standard ELO with K=32, K decreases by 1 every 10 fights (min K=16).
```
expected = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
new_elo = player_elo + K * (1 - expected)  # win
new_elo = player_elo + K * (0 - expected)  # loss
```

## Daily Quests

4 quests per day, reset 0h UTC:
1. "Tập Xỏ Lá" — Đánh 3 trận → 50 coins, 30 XP
2. "Vua Xỏ Lá" — Thắng 2 trận → 100 coins, 50 XP
3. "Xả Stress" — Gây 500 dmg → 75 coins, 40 XP
4. "Nạp Năng Lượng" — Dùng 2 item → 40 coins, 20 XP

Auto-track progress, notify on completion, `/quests` command to view/claim.

## Battle Replay

Each round stored as JSON in `battle_history.rounds`:
```json
[
  {"r": 1, "actor": "user_id", "skill": "👊 Cú Đấm Ba Que",
   "damage": 15, "hp1": 100, "hp2": 85, "heal": 0, "effects": ["-15 HP"]}
]
```

Access via `/replay <id>` on Discord and `/battle/{id}` on web.

## Web Dashboard

- **FastAPI** + **Jinja2** + **htmx** (lightweight reactive UI)
- Routes:
  - `/` — Leaderboard + stats overview
  - `/player/{id}` — Profile, class, winrate, recent fights
  - `/battle/{id}` — Replay timeline with animated HP bars
- Runs on separate port (e.g. 8080) alongside bot

## Testing

```
tests/
├── conftest.py           # In-memory SQLite fixtures
├── test_battle_engine.py # 10+ cases for combat: normal, dodge, counter, shield, burn, stun, lifesteal, class perks
├── test_rewards.py       # XP/coin reward calculation
└── test_ranking.py       # ELO edge cases (new players, veterans, upsets)
```

## Migration

`scripts/migrate_json_to_sqlite.py`:
1. Read `data/players.json`, `data/battles.json`, `data/challenges.json`
2. Create SQLite tables
3. Insert all data with field mapping (old JSON fields → new schema)
4. Assign `class_id` based on old VIP/WORST flags
5. Backup JSON to `data/backups/`
6. Remove JSON files

## .gitignore

```
.env
__pycache__/
venv/
*.db
data/backups/
```
