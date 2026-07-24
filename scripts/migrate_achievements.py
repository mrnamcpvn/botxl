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

    # Lấy 6★ và 7★ count
    try:
        from bot.data.equipment import EQUIPMENT
        six_items = [k for k, v in EQUIPMENT.items() if v.get("star") == 6]
        seven_items = [k for k, v in EQUIPMENT.items() if v.get("star") == 7]
        seven_items = [k for k in seven_items if k in EQUIPMENT]  # chỉ item hệ thống
        six_star_counts = {}
        seven_star_counts = {}
        if six_items:
            ph = ",".join("?" for _ in six_items)
            c.execute(f"SELECT player_id, COUNT(*) as cnt FROM player_equipment WHERE item_id IN ({ph}) GROUP BY player_id", six_items)
            six_star_counts = {r["player_id"]: r["cnt"] for r in c.fetchall()}
        if seven_items:
            ph = ",".join("?" for _ in seven_items)
            c.execute(f"SELECT player_id, COUNT(*) as cnt FROM player_equipment WHERE item_id IN ({ph}) GROUP BY player_id", seven_items)
            seven_star_counts = {r["player_id"]: r["cnt"] for r in c.fetchall()}
    except:
        six_star_counts = {}
        seven_star_counts = {}

    # Lấy enhance count (số món đạt từng mốc)
    c.execute("SELECT player_id, enhance FROM player_equipment")
    enhance_counts = {}  # pid -> {4: count, 7: count, 9: count}
    for r in c.fetchall():
        pid = r["player_id"]
        enh = r["enhance"]
        if pid not in enhance_counts:
            enhance_counts[pid] = {4: 0, 7: 0, 9: 0}
        if enh >= 4: enhance_counts[pid][4] += 1
        if enh >= 7: enhance_counts[pid][7] += 1
        if enh >= 9: enhance_counts[pid][9] += 1

    # Lấy max gem level
    try:
        c.execute("SELECT player_id, MAX(gem_level) as max_lv FROM player_gems WHERE quantity>0 GROUP BY player_id")
        gem_levels = {r["player_id"]: r["max_lv"] for r in c.fetchall()}
    except:
        gem_levels = {}

    count = 0
    for player in players:
        sid = player["id"]
        level = player["level"]
        wins = player["wins"]
        kills = npc_kills.get(sid, 0)
        realm = realms.get(sid, -1)
        six_cnt = six_star_counts.get(sid, 0)
        seven_cnt = seven_star_counts.get(sid, 0)
        enh_cnt = enhance_counts.get(sid, {4: 0, 7: 0, 9: 0})
        max_gem = gem_levels.get(sid, 0)

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
            elif atype == "enhance_count_4":
                c4 = enh_cnt[4]
                progress = min(c4, target)
                completed = 1 if c4 >= target else 0
            elif atype == "enhance_count_7":
                c7 = enh_cnt[7]
                progress = min(c7, target)
                completed = 1 if c7 >= target else 0
            elif atype == "enhance_count_9":
                c9 = enh_cnt[9]
                progress = min(c9, target)
                completed = 1 if c9 >= target else 0
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
            elif atype == "own_7star":
                progress = min(seven_cnt, target)
                completed = 1 if seven_cnt >= target else 0
            elif atype == "gem_level":
                progress = min(max_gem, target)
                completed = 1 if max_gem >= target else 0
            elif atype == "reroll_count":
                # Không thể backfill số lần reroll cũ, mặc định 0
                progress = 0
                completed = 0

            c.execute(
                "INSERT OR REPLACE INTO player_achievements (player_id, ach_id, progress, completed, claimed) VALUES (?,?,?,?,0)",
                (sid, ach_id, progress, completed))
            count += 1

    conn.commit()
    conn.close()
    print(f"Backfilled achievements for {len(players)} players ({count} rows).")


if __name__ == "__main__":
    migrate()
