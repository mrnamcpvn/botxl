"""One-time migration: old hidden_stats format → 3-slot format.

Old: {"crit": 5, "hp": 40}       (2 flat stats)
New: {"1":{"k":"crit","v":5}, "2":{"k":"hp","v":40}}  (3 independent slots)

Run from project root:  python scripts/migrate_hidden_stats.py
"""
import json
import os
import sqlite3
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

HIDDEN_STAT_POOLS = {
    "atk_min": {"icon": "⚔️", "label": "Tấn Công Tối Thiểu", "val": lambda s: 2 + s * 3},
    "atk_max": {"icon": "⚔️", "label": "Tấn Công Tối Đa", "val": lambda s: 3 + s * 4},
    "hp": {"icon": "❤️", "label": "HP", "val": lambda s: 20 + s * 15},
    "defense": {"icon": "🛡️", "label": "Phòng Thủ", "val": lambda s: 3 + s * 2},
    "spd": {"icon": "💨", "label": "Tốc Độ", "val": lambda s: 2 + s},
    "crit": {"icon": "💥", "label": "Chí Mạng", "val": lambda s: 2 + s},
    "pierce": {"icon": "🔱", "label": "Xuyên Giáp", "val": lambda s: 2 + s},
    "dodge": {"icon": "🍀", "label": "Né Đòn", "val": lambda s: 1 + s},
    "reflect": {"icon": "🔄", "label": "Phản Đòn", "val": lambda s: 1 + s},
    "regen": {"icon": "💚", "label": "Hồi Phục", "val": lambda s: 1 + s // 2},
}

SLOT_MULTIPLIERS = {1: 1.5, 2: 3.0, 3: 5.0}

def generate_hidden_stat(star: int, slot: int) -> str:
    k = random.choice(list(HIDDEN_STAT_POOLS.keys()))
    pool = HIDDEN_STAT_POOLS[k]
    val = int(pool["val"](star) * SLOT_MULTIPLIERS[slot])
    return json.dumps({"k": k, "v": val})


def migrate():
    from bot.data.equipment import EQUIPMENT
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, item_id, enhance, hidden_stats FROM player_equipment WHERE hidden_stats != ''")
    rows = cursor.fetchall()
    count = 0
    for row in rows:
        eid, eiid, enhance, hidden_raw = row["id"], row["item_id"], row["enhance"], row["hidden_stats"]
        if not hidden_raw:
            continue
        try:
            old = json.loads(hidden_raw)
        except:
            continue
        if not isinstance(old, dict):
            continue

        first_val = next(iter(old.values()), None)
        old_format = not isinstance(first_val, dict)

        if old_format:
            stat_keys = list(old.keys())
            new_data = {}
            new_data["1"] = {"k": stat_keys[0], "v": old[stat_keys[0]]}
            if len(stat_keys) > 1 and enhance >= 7:
                new_data["2"] = {"k": stat_keys[1], "v": old[stat_keys[1]]}

            equip = EQUIPMENT.get(eiid)
            star = equip["star"] if equip else 3

            if enhance >= 7 and "2" not in new_data:
                hs = generate_hidden_stat(star, 2)
                new_data["2"] = json.loads(hs)
            if enhance >= 9 and "3" not in new_data:
                hs = generate_hidden_stat(star, 3)
                new_data["3"] = json.loads(hs)
        else:
            new_data = dict(old)
            changed = False
            if enhance < 7 and "2" in new_data:
                del new_data["2"]
                changed = True
            if enhance < 9 and "3" in new_data:
                del new_data["3"]
                changed = True
            if not changed:
                continue

        cursor.execute("UPDATE player_equipment SET hidden_stats=? WHERE id=?", (json.dumps(new_data), eid))
        count += 1

    conn.commit()
    conn.close()
    print(f"Migrated {count} equipment rows to new 3-slot hidden stat format.")


if __name__ == "__main__":
    migrate()
