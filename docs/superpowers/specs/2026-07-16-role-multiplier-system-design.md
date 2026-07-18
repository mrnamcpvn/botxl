# Role Multiplier System Design

## Overview
Add a Discord-role-based stat multiplier system. Players with certain Discord roles get boosted stats and optionally discounted skill prices.

## Role → Multiplier Mapping

| Discord Role | Multiplier |
|---|---|
| Dragon | 3.0x |
| VIP | 1.5x |
| Supporter | 1.2x |
| Coder | 1.1x |
| Unisex | 1.0x |
| Blacklist | 0.8x |

If a player has multiple roles, the **highest** multiplier is used.

## Data Changes

### `players` table — new column
```sql
ALTER TABLE players ADD COLUMN role_mult REAL DEFAULT 1.0;
```
Cached multiplier from last sync. Updated via `!syncrole` or `/syncrole`.

### `shop_items.py` — price changes for VIP skills
- Skill 4 (Đạp Bay Nón Bảo Hiểm): 400 → 800
- Skill 9 (Sét Đánh Ngang Tai): 700 → 1500
- Skill 13 (Khiên Nồi Cơm Điện): 300 → 600
- Skill 20 (Chưa Chết Đã Sống Lại): 700 → 1500

## Bot Changes

### New admin command: `!syncrole` / `/syncrole`
- Target: a Discord member
- Checks member's roles → determines highest multiplier
- Updates `role_mult` column in DB
- Replies with multiplier applied

### `_load_full_player()` — load `role_mult`
- Already loads all columns; new column auto-included via `SELECT *`
- No code change needed (but ensure role_mult is in pdata dict)

### `get_effective_stats()` — apply multiplier
- After computing final stats (after class, upgrade, equipment, passive bonuses):
  ```
  stats["hp_max"] = int(stats["hp_max"] * pdata["role_mult"])
  stats["attack_min"] = int(stats["attack_min"] * pdata["role_mult"])
  stats["attack_max"] = int(stats["attack_max"] * pdata["role_mult"])
  stats["defense"] = int(stats["defense"] * pdata["role_mult"])
  ```

## Web Dashboard Changes

### Players route — include role_mult in player detail
- Show role_mult on player page
- Stats displayed already use `get_effective_stats()` which will now apply multiplier

## Database Migration

`bot/database.py` — `init_db()`:
- Add `ALTER TABLE players ADD COLUMN IF NOT EXISTS role_mult REAL DEFAULT 1.0;`
- SQLite does not support `ADD COLUMN IF NOT EXISTS` directly; use a try/except or check column existence

## Per-Player Registration

`register` — set `role_mult` to detected multiplier at registration time:
- After INSERT default player, optionally call a `_sync_role_mult()` helper

## Rollout

1. Migrate DB schema
2. Deploy code
3. Admin runs `!syncrole 454923120986292224` to set multiplier for existing user
