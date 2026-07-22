# Mở Rộng Trang Bị + Set Bonus Theo Tổng Sao — Implementation Plan

> **For agentic workers:** Implement directly in this session. These are 3 simple tasks with concrete code.

**Goal:** Add 48 themed equipment items (5-6★ focused on HP/ATK/SPD/PIERCE) + change set bonus from "6 same star" to "minimum total stars".

**Tech Stack:** Python, no new deps.

---

## Files

| File | Action |
|------|--------|
| `bot/data/equipment.py` | Modify — add equipment + change SET_BONUSES |
| `bot/utils/player_loader.py` | Modify — set bonus calc by total stars |
| `bot/cogs/arena.py` | Modify — set bonus calc (2 places) |

---

### Task 1: Add New Equipment + Update SET_BONUSES

**Files:**
- Modify: `bot/data/equipment.py`

**Step A:** Change `SET_BONUSES` from star-keyed to total-stars-keyed:

```python
SET_BONUSES = {
    6:  {"name": "Đồng Nát",   "hp_pct": 5},
    12: {"name": "Tinh Anh",   "hp_pct": 8,  "def_pct": 5},
    18: {"name": "Hiếm Có",     "hp_pct": 10, "atk_pct": 8},
    24: {"name": "Sử Thi",     "hp_pct": 15, "atk_pct": 10, "crit": 5},
    30: {"name": "Huyền Thoại", "hp_pct": 20, "atk_pct": 15, "crit": 8},
    36: {"name": "Thần Thoại",  "hp_pct": 30, "atk_pct": 20, "crit": 10, "dodge": 5},
    42: {"name": "Vũ Trụ",     "hp_pct": 50, "atk_pct": 35, "def_pct": 25, "crit": 15, "dodge": 10},
}
```

**Step B:** Add new equipment items. Append at end of EQUIPMENT dict (before closing `}`):

All new items use IDs 5000+ range. Each set has exact 6 items (one per slot).

```python
    # ═══════ ⭐5 🔴 SET: 🛡️ Giáp Rồng (Tank) ═══════
    5101: {"name":"Long Nha Đao","slot":"weapon","star":5,"stats":{"attack_min":10,"attack_max":18,"hp":25}},
    5102: {"name":"Long Lân Giáp","slot":"armor","star":5,"stats":{"hp":72,"defense":8}},
    5103: {"name":"Long Trảo Hài","slot":"boots","star":5,"stats":{"hp":40,"defense":3,"spd":4}},
    5104: {"name":"Long Cốt Thủ Sáo","slot":"gloves","star":5,"stats":{"hp":40,"defense":4}},
    5105: {"name":"Long Tu Đới","slot":"belt","star":5,"stats":{"hp":52,"defense":5}},
    5106: {"name":"Long Nhãn Giới","slot":"ring","star":5,"stats":{"hp":42,"defense":3}},

    # ⭐5 🔴 SET: ⚔️ Huyết Kiếm (Glass Cannon)
    5201: {"name":"Huyết Kiếm","slot":"weapon","star":5,"stats":{"attack_min":22,"attack_max":32,"crit":5}},
    5202: {"name":"Huyết Chiến Bào","slot":"armor","star":5,"stats":{"hp":22,"attack_min":3,"attack_max":5}},
    5203: {"name":"Huyết Ảnh Hài","slot":"boots","star":5,"stats":{"attack_min":4,"attack_max":6,"spd":6}},
    5204: {"name":"Huyết Thủ Sáo","slot":"gloves","star":5,"stats":{"attack_min":4,"attack_max":6}},
    5205: {"name":"Huyết Ma Đới","slot":"belt","star":5,"stats":{"attack_min":3,"attack_max":5,"crit":3}},
    5206: {"name":"Huyết Nhãn Giới","slot":"ring","star":5,"stats":{"attack_min":4,"attack_max":6}},

    # ⭐5 🔴 SET: 💨 Phong Vân (SPD+DODGE)
    5301: {"name":"Phong Vân Kiếm","slot":"weapon","star":5,"stats":{"attack_min":12,"attack_max":22,"spd":8}},
    5302: {"name":"Phong Vân Giáp","slot":"armor","star":5,"stats":{"hp":40,"defense":4,"spd":3}},
    5303: {"name":"Phong Vân Hài","slot":"boots","star":5,"stats":{"hp":20,"spd":10}},
    5304: {"name":"Phong Vân Thủ Sáo","slot":"gloves","star":5,"stats":{"hp":20,"spd":5}},
    5305: {"name":"Phong Vân Đới","slot":"belt","star":5,"stats":{"hp":30,"spd":4}},
    5306: {"name":"Phong Vân Giới","slot":"ring","star":5,"stats":{"hp":22,"spd":5}},

    # ⭐5 🔴 SET: 🔱 Xuyên Tâm (PIERCE)
    5401: {"name":"Xuyên Tâm Mâu","slot":"weapon","star":5,"stats":{"attack_min":14,"attack_max":24,"pierce":8}},
    5402: {"name":"Xuyên Tâm Giáp","slot":"armor","star":5,"stats":{"hp":42,"defense":5,"pierce":3}},
    5403: {"name":"Xuyên Tâm Hài","slot":"boots","star":5,"stats":{"hp":25,"spd":5,"pierce":4}},
    5404: {"name":"Xuyên Tâm Thủ Sáo","slot":"gloves","star":5,"stats":{"hp":25,"pierce":5}},
    5405: {"name":"Xuyên Tâm Đới","slot":"belt","star":5,"stats":{"hp":32,"pierce":4}},
    5406: {"name":"Xuyên Tâm Giới","slot":"ring","star":5,"stats":{"hp":24,"pierce":4}},

    # ═══════ ⭐6 💗 SET: 💎 Long Giáp (Tank nâng cao) ═══════
    6101: {"name":"Long Thần Đao","slot":"weapon","star":6,"stats":{"attack_min":15,"attack_max":25,"hp":50}},
    6102: {"name":"Long Thần Giáp","slot":"armor","star":6,"stats":{"hp":120,"defense":14}},
    6103: {"name":"Long Thần Hài","slot":"boots","star":6,"stats":{"hp":65,"defense":6,"spd":6}},
    6104: {"name":"Long Thần Thủ Sáo","slot":"gloves","star":6,"stats":{"hp":65,"defense":7}},
    6105: {"name":"Long Thần Đới","slot":"belt","star":6,"stats":{"hp":85,"defense":8}},
    6106: {"name":"Long Thần Giới","slot":"ring","star":6,"stats":{"hp":68,"defense":5}},

    # ⭐6 💗 SET: 🔥 Diệt Thế (Glass Cannon nâng cao)
    6201: {"name":"Diệt Thế Kiếm","slot":"weapon","star":6,"stats":{"attack_min":35,"attack_max":50,"crit":8}},
    6202: {"name":"Diệt Thế Chiến Bào","slot":"armor","star":6,"stats":{"hp":30,"attack_min":5,"attack_max":8}},
    6203: {"name":"Diệt Thế Hài","slot":"boots","star":6,"stats":{"attack_min":6,"attack_max":9,"spd":9}},
    6204: {"name":"Diệt Thế Thủ Sáo","slot":"gloves","star":6,"stats":{"attack_min":7,"attack_max":10}},
    6205: {"name":"Diệt Thế Đới","slot":"belt","star":6,"stats":{"attack_min":5,"attack_max":7,"crit":5}},
    6206: {"name":"Diệt Thế Giới","slot":"ring","star":6,"stats":{"attack_min":6,"attack_max":9}},

    # ⭐6 💗 SET: ⚡ Lôi Phong (SPD+DODGE nâng cao)
    6301: {"name":"Lôi Phong Kiếm","slot":"weapon","star":6,"stats":{"attack_min":18,"attack_max":30,"spd":12}},
    6302: {"name":"Lôi Phong Giáp","slot":"armor","star":6,"stats":{"hp":60,"defense":6,"spd":5}},
    6303: {"name":"Lôi Phong Hài","slot":"boots","star":6,"stats":{"hp":32,"spd":16}},
    6304: {"name":"Lôi Phong Thủ Sáo","slot":"gloves","star":6,"stats":{"hp":32,"spd":8}},
    6305: {"name":"Lôi Phong Đới","slot":"belt","star":6,"stats":{"hp":45,"spd":7}},
    6306: {"name":"Lôi Phong Giới","slot":"ring","star":6,"stats":{"hp":35,"spd":8}},

    # ⭐6 💗 SET: 🌌 Hư Không (PIERCE nâng cao)
    6401: {"name":"Hư Không Mâu","slot":"weapon","star":6,"stats":{"attack_min":20,"attack_max":34,"pierce":14}},
    6402: {"name":"Hư Không Giáp","slot":"armor","star":6,"stats":{"hp":65,"defense":8,"pierce":5}},
    6403: {"name":"Hư Không Hài","slot":"boots","star":6,"stats":{"hp":38,"spd":8,"pierce":6}},
    6404: {"name":"Hư Không Thủ Sáo","slot":"gloves","star":6,"stats":{"hp":38,"pierce":8}},
    6405: {"name":"Hư Không Đới","slot":"belt","star":6,"stats":{"hp":48,"pierce":6}},
    6406: {"name":"Hư Không Giới","slot":"ring","star":6,"stats":{"hp":36,"pierce":7}},
```

Commit: `git add bot/data/equipment.py && git commit -m "feat: 48 themed equipment + set bonus by total stars"`

---

### Task 2: Update Set Bonus Calculation

**Files:**
- Modify: `bot/utils/player_loader.py`
- Modify: `bot/cogs/arena.py`

**Step A: player_loader.py** — Change set bonus logic from "6 same star" to "total stars":

Replace lines 87-98:

Old:
```python
    pdata["_set_bonus"] = None
    stars_per_slot = {}
    for slot, eq_id in equipped.items():
        item_id = equip_items.get(str(eq_id))
        if item_id and item_id in EQUIPMENT:
            stars_per_slot[slot] = EQUIPMENT[item_id]["star"]
    if len(stars_per_slot) == 6:
        star_values = set(stars_per_slot.values())
        if len(star_values) == 1:
            star = star_values.pop()
            pdata["_set_bonus"] = SET_BONUSES.get(star)
```

New:
```python
    pdata["_set_bonus"] = None
    total_stars = 0
    equipped_count = 0
    for slot, eq_id in equipped.items():
        item_id = equip_items.get(str(eq_id))
        if item_id and item_id in EQUIPMENT:
            total_stars += EQUIPMENT[item_id]["star"]
            equipped_count += 1
    if equipped_count == 6:
        for min_stars in sorted(SET_BONUSES.keys(), reverse=True):
            if total_stars >= min_stars:
                pdata["_set_bonus"] = SET_BONUSES[min_stars]
                break
```

**Step B: arena.py** — Same change in 2 places.
Search for code blocks matching the old logic. Use the same replacement pattern. There should be 2 occurrences (prefix stats + slash stats).

Replace this block in both places:
```python
            pdata["_set_bonus"] = None
            stars_per_slot = {}
            for slot, eq_id in equipped.items():
                item_id = equip_items.get(str(eq_id))
                if item_id and item_id in EQUIPMENT:
                    stars_per_slot[slot] = EQUIPMENT[item_id]["star"]
            if len(stars_per_slot) == 6 and len(set(stars_per_slot.values())) == 1:
                pdata["_set_bonus"] = SET_BONUSES.get(list(stars_per_slot.values())[0])
```

With:
```python
            pdata["_set_bonus"] = None
            total_stars = 0
            equipped_count = 0
            for slot, eq_id in equipped.items():
                item_id = equip_items.get(str(eq_id))
                if item_id and item_id in EQUIPMENT:
                    total_stars += EQUIPMENT[item_id]["star"]
                    equipped_count += 1
            if equipped_count == 6:
                for min_stars in sorted(SET_BONUSES.keys(), reverse=True):
                    if total_stars >= min_stars:
                        pdata["_set_bonus"] = SET_BONUSES[min_stars]
                        break
```

Commit: `git add bot/utils/player_loader.py bot/cogs/arena.py && git commit -m "feat: set bonus now based on total stars instead of matching stars"`

---

### Task 3: Update Stats View Set Display

**Files:**
- Modify: `bot/views/stats_view.py`

Find Tab 2 (Trang Bị) where set bonus is displayed (~line 380). The current code looks up set_bonus in SET_BONUSES by star value. Change to iterate and display the correct set name for the total stars.

Read the actual code and update the display to show the total stars and the matching set bonus. Add a line like:
```
🎁 Set: **Thần Thoại** (36/42 sao — 6 món)
```

Where it shows current total stars and the minimum needed for next tier.

Commit: `git add bot/views/stats_view.py && git commit -m "fix: stats view set bonus display for total stars system"`
