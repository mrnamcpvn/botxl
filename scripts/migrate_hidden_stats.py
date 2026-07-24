"""One-time migration: old hidden_stats format → 3-slot format.

Old: {"crit": 5, "hp": 40}       (2 flat stats)
New: {"1":{"k":"crit","v":5}, "2":{"k":"hp","v":40}}  (3 independent slots)

Run from project root:  python scripts/migrate_hidden_stats.py
"""
import json
import os
import sqlite3
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.cogs.enhance import generate_hidden_stat, HIDDEN_STAT_POOLS

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game.db")


def migrate():
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
        if isinstance(first_val, dict):
            continue

        stat_keys = list(old.keys())
        new_data = {}
        for i, k in enumerate(stat_keys[:2]):
            new_data[str(i + 1)] = {"k": k, "v": old[k]}

        from bot.data.equipment import EQUIPMENT
        equip = EQUIPMENT.get(eiid)
        star = equip["star"] if equip else 3

        if enhance >= 7 and "2" not in new_data:
            hs = generate_hidden_stat(star, 2)
            new_data["2"] = json.loads(hs)
        if enhance >= 9 and "3" not in new_data:
            hs = generate_hidden_stat(star, 3)
            new_data["3"] = json.loads(hs)

        cursor.execute("UPDATE player_equipment SET hidden_stats=? WHERE id=?", (json.dumps(new_data), eid))
        count += 1

    conn.commit()
    conn.close()
    print(f"✅ Migrated {count} equipment rows to new 3-slot hidden stat format.")


if __name__ == "__main__":
    migrate()
