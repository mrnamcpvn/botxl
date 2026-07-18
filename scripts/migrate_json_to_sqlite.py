"""Migrate old JSON data to SQLite. Run once, then delete JSON."""
import json
import os
import shutil
import sqlite3
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def migrate():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    players = load_json(os.path.join(DATA_DIR, "players.json"))
    battles = load_json(os.path.join(DATA_DIR, "battles.json"))
    challenges = load_json(os.path.join(DATA_DIR, "challenges.json"))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY, name TEXT DEFAULT '', class_id TEXT DEFAULT 'banxabong',
            hp INTEGER DEFAULT 120, hp_max INTEGER DEFAULT 120,
            attack_min INTEGER DEFAULT 12, attack_max INTEGER DEFAULT 17,
            defense INTEGER DEFAULT 8, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
            damage_dealt INTEGER DEFAULT 0, damage_taken INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            stat_points INTEGER DEFAULT 0, elo INTEGER DEFAULT 1000,
            attack_cd INTEGER DEFAULT 0, special_cd INTEGER DEFAULT 0, defense_cd INTEGER DEFAULT 0,
            last_hp_update REAL, upgrade_hp INTEGER DEFAULT 0, upgrade_atk INTEGER DEFAULT 0, upgrade_def INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS player_skills (player_id TEXT, skill_id INTEGER, PRIMARY KEY (player_id, skill_id));
        CREATE TABLE IF NOT EXISTS player_skill_slots (player_id TEXT, slot TEXT, skill_id INTEGER, PRIMARY KEY (player_id, slot));
        CREATE TABLE IF NOT EXISTS player_equipment (player_id TEXT, item_id INTEGER, quantity INTEGER DEFAULT 1, PRIMARY KEY (player_id, item_id));
        CREATE TABLE IF NOT EXISTS player_equip_slots (player_id TEXT, slot TEXT, item_id INTEGER, PRIMARY KEY (player_id, slot));
        CREATE TABLE IF NOT EXISTS inventory (player_id TEXT, item_id INTEGER, quantity INTEGER DEFAULT 0, PRIMARY KEY (player_id, item_id));
        CREATE TABLE IF NOT EXISTS player_buffs (player_id TEXT PRIMARY KEY, attack_boost INTEGER DEFAULT 0, defense_boost INTEGER DEFAULT 0, lucky INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS active_battles (id INTEGER PRIMARY KEY AUTOINCREMENT, player1_id TEXT, player2_id TEXT, turn TEXT, p1_defending INTEGER DEFAULT 0, p2_defending INTEGER DEFAULT 0, p1_stunned INTEGER DEFAULT 0, p2_stunned INTEGER DEFAULT 0, channel_id TEXT, last_move REAL);
        CREATE TABLE IF NOT EXISTS battle_status (battle_id INTEGER, player_id TEXT, key TEXT, value TEXT, PRIMARY KEY (battle_id, player_id, key));
        CREATE TABLE IF NOT EXISTS battle_history (id INTEGER PRIMARY KEY AUTOINCREMENT, player1_id TEXT, player2_id TEXT, p1_name TEXT, p2_name TEXT, winner_id TEXT, rounds TEXT, fought_at TEXT);
        CREATE TABLE IF NOT EXISTS challenges (target_id TEXT PRIMARY KEY, challenger_id TEXT, channel_id TEXT, created_at REAL);
        CREATE TABLE IF NOT EXISTS daily_quests (player_id TEXT, quest_id INTEGER, progress INTEGER DEFAULT 0, target INTEGER NOT NULL, completed INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0, date TEXT, PRIMARY KEY (player_id, quest_id, date));
    """)

    VIP_USER = "454923120986292224"
    WORST_USER = "857876295601225758"

    for sid, pdata in players.items():
        class_id = "banxabong"
        if sid == VIP_USER:
            class_id = "trumcuoi"
        elif sid == WORST_USER:
            class_id = "xola"

        hp_max = pdata.get("hp_max", 100)
        conn.execute("""INSERT OR REPLACE INTO players
            (id, name, class_id, hp, hp_max, attack_min, attack_max, defense, wins, losses,
             damage_dealt, damage_taken, coins, xp, level, stat_points, elo, last_hp_update)
            VALUES (?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1000, ?)""",
            (sid, class_id, pdata.get("hp", hp_max), hp_max,
             pdata.get("attack_min", 10), pdata.get("attack_max", 20),
             pdata.get("defense", 5),
             pdata.get("wins", 0), pdata.get("losses", 0),
             pdata.get("damage_dealt", 0), pdata.get("damage_taken", 0),
             pdata.get("coins", 0), pdata.get("xp", 0),
             pdata.get("level", 1), pdata.get("stat_points", 0),
             pdata.get("last_hp_update", time.time())))

        for sk_id in pdata.get("skills_owned", [1, 5, 10, 14]):
            conn.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))

        for slot, sk_id in pdata.get("skill_equipped", {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
            conn.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))

        for item_id in pdata.get("equipment_items", {}):
            conn.execute("INSERT OR IGNORE INTO player_equipment (player_id, item_id) VALUES (?, ?)", (sid, int(item_id)))

        for slot, item_id in pdata.get("equipped", {}).items():
            if item_id:
                conn.execute("INSERT OR REPLACE INTO player_equip_slots (player_id, slot, item_id) VALUES (?, ?, ?)", (sid, slot, int(item_id)))

        for item_id, qty in pdata.get("inventory", {}).items():
            conn.execute("INSERT OR REPLACE INTO inventory (player_id, item_id, quantity) VALUES (?, ?, ?)", (sid, int(item_id), qty))

    conn.commit()

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for fname in ["players.json", "battles.json", "challenges.json"]:
        src = os.path.join(DATA_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BACKUP_DIR, fname + ".bak"))
            os.remove(src)

    conn.close()
    print(f"Migration complete! Data migrated to {DB_PATH}")
    print(f"JSON files backed up to {BACKUP_DIR}")

if __name__ == "__main__":
    migrate()
