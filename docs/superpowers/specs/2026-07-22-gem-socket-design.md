# Gem Socket / Đá Khảm — Design Spec

## Overview

Each equipment has 1-4 socket slots (based on star tier). Players can socket gems that add fixed stats. Gems drop from NPCs, dungeon, and world boss. 3 gems of same type+level can merge to a higher level (costs coins). Gems can be removed (costs coins, gem preserved).

**Scope:** new cog `bot/cogs/gem_socket.py` + DB tables + config + battle engine integration.

---

## 1. Gem Types & Stats

| Gem | Stat | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
|-----|------|----|----|----|----|----|----|----|----|----|
| 🔴 Hồng Ngọc | HP | 80 | 150 | 250 | 400 | 600 | 900 | 1300 | 1800 | 2500 |
| ⚔️ Lục Bảo | ATK | 8 | 15 | 25 | 40 | 60 | 90 | 130 | 180 | 250 |
| 🛡️ Lam Ngọc | DEF | 5 | 10 | 18 | 30 | 45 | 65 | 90 | 120 | 160 |
| 💨 Phong Tinh | SPD | 5 | 10 | 18 | 30 | 45 | 65 | 90 | 120 | 160 |
| 💥 Huyết Thạch | CRIT | 3 | 6 | 12 | 20 | 30 | 45 | 65 | 90 | 120 |
| 🔱 Tử Tinh | PIERCE | 3 | 6 | 12 | 20 | 30 | 45 | 65 | 90 | 120 |

ATK applies to both `attack_min` and `attack_max`. CRIT/PIERCE are raw stats (divided by 3 and 7 respectively in battle engine).

---

## 2. Socket Slots Per Equipment Star

| Star | Sockets |
|------|---------|
| 1-3★ | 1 |
| 4-5★ | 2 |
| 6★ | 3 |
| 7-9★ | 4 (future) |

---

## 3. Gem Sources (Drop Rates)

### NPC

| NPC Level | Gem Level | Drop Rate |
|-----------|-----------|-----------|
| 10-19 | C1 | 10% |
| 20-25 | C2 | 10% |
| 26-30 | C3 | 10% |

Drop: random gem type, 1 quantity.

### Dungeon

| Dungeon Floor | Gem Level | Drop Rate |
|---------------|-----------|-----------|
| 20-40 | C1 | 8% per floor |
| 41-60 | C2 | 8% per floor |
| 61-80 | C3 | 8% per floor |
| 81-100 | C4 | 8% per floor |

### World Boss

On boss death: each participant gets 1 random gem C1-C3 (100% drop).

---

## 4. Gem Merge (Ghép Đá)

```
3 viên cùng loại + cùng cấp + coin → 1 viên cấp +1

Cost = target_level × 500 coin
Example: 3× Hồng Ngọc C1 + 1000🪙 → 1× Hồng Ngọc C2
```

---

## 5. Gem Socket / Remove

### Socket (Khảm)
- Click equipment → select empty socket → select gem from inventory
- Free (no cost to socket)

### Remove (Tháo)
```
Cost = gem_level × 1000 coin
Gem returned to inventory (not destroyed)
```

---

## 6. Commands

| Command | Description |
|---------|-------------|
| `!khamda @trangbi` | Open socket UI for an equipped item |
| `!ghepda <type> <level>` | Merge 3 gems to next level |
| `!khoda` | View gem inventory |

---

## 7. Database

```sql
CREATE TABLE player_gems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    gem_type TEXT NOT NULL,
    gem_level INTEGER DEFAULT 1,
    quantity INTEGER DEFAULT 0,
    UNIQUE(player_id, gem_type, gem_level)
);

CREATE TABLE equipment_sockets (
    equip_instance_id INTEGER PRIMARY KEY REFERENCES player_equipment(id),
    socket_1 TEXT DEFAULT '',
    socket_2 TEXT DEFAULT '',
    socket_3 TEXT DEFAULT '',
    socket_4 TEXT DEFAULT ''
);
```

Socket values store `"gem_type:gem_level"`, e.g. `"hp:5"` or empty string.

---

## 8. Battle Engine Integration

In `get_effective_stats()` in `bot/engine/battle.py`, after loading equipment stats, also load socket gems and add their stats:

```python
# After equipment stat loop, add gem stats
eq = pdata.get("equipped", {})
for slot, eq_id in eq.items():
    if not eq_id:
        continue
    socket_data = pdata.get("_equip_sockets", {}).get(str(eq_id), {})
    for sk in ["socket_1", "socket_2", "socket_3", "socket_4"]:
        gem_str = socket_data.get(sk, "")
        if not gem_str:
            continue
        gem_type, gem_level = gem_str.split(":")
        gem_level = int(gem_level)
        stat_val = GEM_STATS[gem_type][gem_level - 1]
        if gem_type == "hp":
            hp_max += stat_val
        elif gem_type == "atk":
            atk_min += stat_val
            atk_max += stat_val
        elif gem_type == "def":
            defense += stat_val
        elif gem_type == "spd":
            spd += stat_val
        elif gem_type == "crit":
            crit += stat_val
        elif gem_type == "pierce":
            pierce += stat_val
```

---

## 9. Config

```python
GEM_TYPES = {
    "hp":     {"name": "🔴 Hồng Ngọc",  "stat": "hp",     "levels": [80, 150, 250, 400, 600, 900, 1300, 1800, 2500]},
    "atk":    {"name": "⚔️ Lục Bảo",    "stat": "atk",    "levels": [8, 15, 25, 40, 60, 90, 130, 180, 250]},
    "def":    {"name": "🛡️ Lam Ngọc",   "stat": "def",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "spd":    {"name": "💨 Phong Tinh",  "stat": "spd",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "crit":   {"name": "💥 Huyết Thạch", "stat": "crit",   "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
    "pierce": {"name": "🔱 Tử Tinh",    "stat": "pierce", "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
}
GEM_MAX_LEVEL = 9
GEM_MERGE_COST_PER_LEVEL = 500
GEM_REMOVE_COST_PER_LEVEL = 1000

SOCKETS_BY_STAR = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 4, 8: 4, 9: 4}
```

## 10. Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add gem config |
| `bot/database.py` | Modify — add gem tables |
| `bot/cogs/gem_socket.py` | Create — main cog |
| `bot/engine/battle.py` | Modify — integrate gem stats |
| `main.py` | Modify — load gem_socket cog |

---

## 11. Edge Cases

- Socket on unequipped items: not supported — only equipped items can be socketed
- Removing gem with full inventory: gem lost (warn player)
- Merging beyond C9: not allowed
- Socketing incompatible gem type: all types compatible with all equipment
- Equipment transferred/traded: sockets cleared
