"""Regenerate hidden stats for ALL equipment (VPS recovery).

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

HIDDEN_STAT_POOLS = [
    "atk_min", "atk_max", "hp", "defense", "spd",
    "crit", "pierce", "dodge", "reflect", "regen",
]
STAT_VAL = {
    "atk_min": lambda s: 2 + s * 3,
    "atk_max": lambda s: 3 + s * 4,
    "hp": lambda s: 20 + s * 15,
    "defense": lambda s: 3 + s * 2,
    "spd": lambda s: 2 + s,
    "crit": lambda s: 2 + s,
    "pierce": lambda s: 2 + s,
    "dodge": lambda s: 1 + s,
    "reflect": lambda s: 1 + s,
    "regen": lambda s: 1 + s // 2,
}
SLOT_MULT = {1: 1.5, 2: 3.0, 3: 5.0}


def generate_slot(star: int, slot: int) -> list:
    count = random.randint(2, 3)
    chosen = random.sample(HIDDEN_STAT_POOLS, min(count, len(HIDDEN_STAT_POOLS)))
    result = []
    for k in chosen:
        val = int(STAT_VAL[k](star) * SLOT_MULT[slot])
        result.append({"k": k, "v": val})
    return result


def migrate():
    from bot.data.equipment import EQUIPMENT
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, item_id, enhance FROM player_equipment WHERE enhance >= 4")
    rows = cursor.fetchall()
    count = 0

    for row in rows:
        eid, eiid, enhance = row["id"], row["item_id"], row["enhance"]
        equip = EQUIPMENT.get(eiid)
        star = equip["star"] if equip else 3

        new_data = {}
        new_data["1"] = generate_slot(star, 1)
        if enhance >= 7:
            new_data["2"] = generate_slot(star, 2)
        if enhance >= 9:
            new_data["3"] = generate_slot(star, 3)

        cursor.execute("UPDATE player_equipment SET hidden_stats=? WHERE id=?", (json.dumps(new_data), eid))
        count += 1

    conn.commit()
    conn.close()
    print(f"Regenerated hidden stats for {count} equipment.")


if __name__ == "__main__":
    migrate()
