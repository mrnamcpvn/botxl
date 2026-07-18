import aiosqlite
from bot.config import DB_PATH

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH, timeout=10.0)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

TABLES = [
    """CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        class_id TEXT NOT NULL DEFAULT 'banxabong',
        hp INTEGER NOT NULL DEFAULT 120,
        hp_max INTEGER NOT NULL DEFAULT 120,
        attack_min INTEGER NOT NULL DEFAULT 12,
        attack_max INTEGER NOT NULL DEFAULT 17,
        defense INTEGER NOT NULL DEFAULT 8,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        damage_dealt INTEGER NOT NULL DEFAULT 0,
        damage_taken INTEGER NOT NULL DEFAULT 0,
        coins INTEGER NOT NULL DEFAULT 0,
        xp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        stat_points INTEGER NOT NULL DEFAULT 0,
        elo INTEGER NOT NULL DEFAULT 1000,
        attack_cd INTEGER NOT NULL DEFAULT 0,
        special_cd INTEGER NOT NULL DEFAULT 0,
        defense_cd INTEGER NOT NULL DEFAULT 0,
        last_hp_update REAL,
        upgrade_hp INTEGER NOT NULL DEFAULT 0,
        upgrade_atk INTEGER NOT NULL DEFAULT 0,
        upgrade_def INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS player_skills (
        player_id TEXT NOT NULL,
        skill_id INTEGER NOT NULL,
        PRIMARY KEY (player_id, skill_id)
    )""",
    """CREATE TABLE IF NOT EXISTS player_skill_slots (
        player_id TEXT NOT NULL,
        slot TEXT NOT NULL CHECK(slot IN ('attack','special','defense','passive')),
        skill_id INTEGER NOT NULL,
        PRIMARY KEY (player_id, slot)
    )""",
    """CREATE TABLE IF NOT EXISTS player_equipment (
        player_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (player_id, item_id)
    )""",
    """CREATE TABLE IF NOT EXISTS inventory (
        player_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (player_id, item_id)
    )""",
    """CREATE TABLE IF NOT EXISTS player_buffs (
        player_id TEXT PRIMARY KEY,
        attack_boost INTEGER DEFAULT 0,
        defense_boost INTEGER DEFAULT 0,
        lucky INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS active_battles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id TEXT NOT NULL,
        player2_id TEXT NOT NULL,
        turn TEXT NOT NULL,
        p1_defending INTEGER DEFAULT 0,
        p2_defending INTEGER DEFAULT 0,
        p1_stunned INTEGER DEFAULT 0,
        p2_stunned INTEGER DEFAULT 0,
        channel_id TEXT NOT NULL,
        last_move REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS battle_status (
        battle_id INTEGER NOT NULL,
        player_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (battle_id, player_id, key)
    )""",
    """CREATE TABLE IF NOT EXISTS battle_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id TEXT NOT NULL,
        player2_id TEXT NOT NULL,
        p1_name TEXT NOT NULL,
        p2_name TEXT NOT NULL,
        winner_id TEXT NOT NULL,
        rounds TEXT NOT NULL,
        fought_at TEXT DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS challenges (
        target_id TEXT PRIMARY KEY,
        challenger_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        created_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS daily_quests (
        player_id TEXT NOT NULL,
        quest_id INTEGER NOT NULL,
        progress INTEGER DEFAULT 0,
        target INTEGER NOT NULL,
        completed INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0,
        date TEXT NOT NULL,
        PRIMARY KEY (player_id, quest_id, date)
    )""",
    """CREATE TABLE IF NOT EXISTS player_wives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        wife_id INTEGER NOT NULL,
        level INTEGER NOT NULL DEFAULT 1,
        xp INTEGER NOT NULL DEFAULT 0,
        class_id TEXT NOT NULL DEFAULT 'banxabong',
        equipped INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS player_artifact (
        player_id TEXT PRIMARY KEY,
        star INTEGER DEFAULT 0,
        stone_count INTEGER DEFAULT 0
    )""",
]

MIGRATIONS = [
    "ALTER TABLE players ADD COLUMN role_mult REAL DEFAULT 1.0",
    "ALTER TABLE players ADD COLUMN last_battle_time REAL DEFAULT 0",
    "ALTER TABLE players ADD COLUMN combat_power INTEGER DEFAULT 0",
]


async def _run_migrations(db):
    for sql in MIGRATIONS:
        try:
            await db.execute(sql)
        except:
            pass

    try:
        await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES ('_mig_ck_', 0, 0, 0)")
        await db.execute("DELETE FROM player_equipment WHERE player_id='_mig_ck_'")
    except:
        await db.execute("BEGIN")
        try:
            await db.execute("""CREATE TABLE IF NOT EXISTS player_equipment_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                enhance INTEGER DEFAULT 0,
                equipped INTEGER DEFAULT 0
            )""")
            await db.execute("""CREATE TABLE IF NOT EXISTS _mig_numbers (n INTEGER PRIMARY KEY)""")
            values = ",".join(f"({i})" for i in range(1, 101))
            await db.execute(f"INSERT OR IGNORE INTO _mig_numbers (n) VALUES {values}")
            await db.execute("""INSERT INTO player_equipment_new (player_id, item_id, enhance, equipped)
                SELECT pe.player_id, pe.item_id, 0, 0
                FROM player_equipment pe
                JOIN _mig_numbers mn ON mn.n <= pe.quantity""")
            await db.execute("DROP TABLE IF EXISTS player_equipment")
            await db.execute("ALTER TABLE player_equipment_new RENAME TO player_equipment")
            await db.commit()
        except:
            await db.execute("ROLLBACK")
            raise
        try:
            await db.execute("""UPDATE player_equipment SET equipped = 1
                WHERE id IN (SELECT pe.id FROM player_equipment pe
                JOIN player_equip_slots pes ON pes.player_id = pe.player_id
                AND pes.item_id = pe.item_id AND pe.equipped = 0)""")
            await db.execute("DROP TABLE IF EXISTS player_equip_slots")
        except:
            pass
        try:
            await db.execute("DROP TABLE IF EXISTS _mig_numbers")
        except:
            pass

    await db.execute("""CREATE TABLE IF NOT EXISTS player_enhance_stones (
        player_id TEXT PRIMARY KEY,
        stone_basic INTEGER DEFAULT 0,
        stone_medium INTEGER DEFAULT 0,
        stone_advanced INTEGER DEFAULT 0
    )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS dungeon_progress (
        player_id TEXT PRIMARY KEY,
        checkpoint INTEGER DEFAULT 0,
        daily_entries INTEGER DEFAULT 0,
        daily_tickets_bought INTEGER DEFAULT 0,
        last_entry_date TEXT DEFAULT '',
        last_week_reset TEXT DEFAULT '',
        accumulated_rewards TEXT DEFAULT ''
    )""")
    try:
        await db.execute("ALTER TABLE dungeon_progress ADD COLUMN accumulated_rewards TEXT DEFAULT ''")
    except:
        pass


async def init_db():
    db = await get_db()
    try:
        for sql in TABLES:
            await db.execute(sql)
        await _run_migrations(db)
    finally:
        await db.close()
