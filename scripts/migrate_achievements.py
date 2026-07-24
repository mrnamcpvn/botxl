"""Backfill achievements for existing players.

Run from project root:  python scripts/migrate_achievements.py
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

from bot.config import ACHIEVEMENTS


def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS player_achievements (
        player_id TEXT NOT NULL,
        ach_id INTEGER NOT NULL,
        progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        PRIMARY KEY (player_id, ach_id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_logins (
        player_id TEXT NOT NULL,
        week_start TEXT NOT NULL,
        day INTEGER NOT NULL,
        claimed INTEGER DEFAULT 0,
        PRIMARY KEY (player_id, week_start, day)
    )""")

    # Lấy tất cả player
    c.execute("SELECT id, level, wins FROM players")
    players = c.fetchall()

    # Lấy NPC kills cho tất cả player
    c.execute("SELECT player_id, SUM(kills) as total FROM monster_codex GROUP BY player_id")
    npc_kills = {r["player_id"]: r["total"] for r in c.fetchall()}

    # Lấy gacha rolls
    try:
        c.execute("SELECT player_id, roll_count FROM gacha_pity")
        gacha_data = {r["player_id"]: r["roll_count"] for r in c.fetchall()}
    except:
        gacha_data = {}

    # Lấy cultivation realm
    c.execute("SELECT player_id, realm FROM cultivation")
    realms = {r["player_id"]: r["realm"] for r in c.fetchall()}

    # Lấy 6★ count
    try:
        from bot.data.equipment import EQUIPMENT
        six_star_items = [k for k, v in EQUIPMENT.items() if v.get("star") == 6]
        if six_star_items:
            placeholders = ",".join("?" for _ in six_star_items)
            c.execute(f"SELECT player_id, COUNT(*) as cnt FROM player_equipment WHERE item_id IN ({placeholders}) GROUP BY player_id", six_star_items)
            six_star_counts = {r["player_id"]: r["cnt"] for r in c.fetchall()}
        else:
            six_star_counts = {}
    except:
        six_star_counts = {}

    # Lấy enhance milestones
    c.execute("SELECT player_id, MAX(enhance) as max_enh FROM player_equipment GROUP BY player_id")
    enhance_data = {r["player_id"]: r["max_enh"] for r in c.fetchall()}

    count = 0
    for player in players:
        sid = player["id"]
        level = player["level"]
        wins = player["wins"]
        kills = npc_kills.get(sid, 0)
        realm = realms.get(sid, -1)
        six_cnt = six_star_counts.get(sid, 0)
        max_enh = enhance_data.get(sid, 0)

        for ach_id, ach_def in ACHIEVEMENTS.items():
            atype = ach_def["type"]
            target = ach_def["target"]
            progress = 0
            completed = 0

            if atype == "register":
                progress = 1
                completed = 1
            elif atype == "npc_kill":
                progress = min(kills, target)
                completed = 1 if kills >= target else 0
            elif atype == "arena_win":
                progress = min(wins, target)
                completed = 1 if wins >= target else 0
            elif atype == "reach_level":
                progress = min(level, target)
                completed = 1 if level >= target else 0
            elif atype == "enhance_4":
                completed = 1 if max_enh >= 4 else 0
                progress = 1 if completed else 0
            elif atype == "enhance_7":
                completed = 1 if max_enh >= 7 else 0
                progress = 1 if completed else 0
            elif atype == "enhance_9":
                completed = 1 if max_enh >= 9 else 0
                progress = 1 if completed else 0
            elif atype == "cultivate":
                completed = 1 if realm >= 0 else 0
                progress = 1 if completed else 0
            elif atype == "reach_realm":
                completed = 1 if realm >= target else 0
                progress = 1 if completed else 0
            elif atype == "gacha":
                pity = gacha_data.get(sid, 0)
                progress = min(pity, target)
                completed = 1 if pity >= target else 0
            elif atype == "own_6star":
                progress = min(six_cnt, target)
                completed = 1 if six_cnt >= target else 0

            c.execute(
                "INSERT OR REPLACE INTO player_achievements (player_id, ach_id, progress, completed, claimed) VALUES (?,?,?,?,0)",
                (sid, ach_id, progress, completed))
            count += 1

    conn.commit()
    conn.close()
    print(f"Backfilled achievements for {len(players)} players ({count} rows).")


if __name__ == "__main__":
    migrate()
