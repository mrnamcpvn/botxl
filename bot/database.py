import aiosqlite
import logging
from bot.config import DB_PATH

logger = logging.getLogger(__name__)


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
    """CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        category TEXT DEFAULT 'general'
    )""",
    """CREATE TABLE IF NOT EXISTS arena_tournament (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'registering',
        channel_id TEXT NOT NULL,
        started_by TEXT NOT NULL DEFAULT 'auto',
        started_at REAL,
        finished_at REAL,
        winner_id TEXT,
        runner_up_id TEXT,
        third_id TEXT,
        bracket_json TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS arena_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        player_id TEXT NOT NULL,
        cp_at_entry INTEGER DEFAULT 0,
        final_rank INTEGER DEFAULT 0,
        reward_given INTEGER DEFAULT 0,
        UNIQUE(tournament_id, player_id)
    )""",
    """CREATE TABLE IF NOT EXISTS world_boss (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'registering',
        channel_id TEXT NOT NULL,
        boss_level INTEGER DEFAULT 0,
        boss_hp INTEGER DEFAULT 0,
        boss_hp_max INTEGER DEFAULT 0,
        boss_atk_min INTEGER DEFAULT 0,
        boss_atk_max INTEGER DEFAULT 0,
        boss_def INTEGER DEFAULT 0,
        started_at REAL,
        finished_at REAL
    )""",
    """CREATE TABLE IF NOT EXISTS world_boss_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        boss_id INTEGER NOT NULL,
        player_id TEXT NOT NULL,
        total_damage INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        death_cooldown_until REAL DEFAULT 0,
        final_rank INTEGER DEFAULT 0,
        reward_given INTEGER DEFAULT 0,
        UNIQUE(boss_id, player_id)
    )""",
    """CREATE TABLE IF NOT EXISTS player_vip_coins (
        player_id TEXT PRIMARY KEY,
        amount INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS player_gems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        gem_type TEXT NOT NULL,
        gem_level INTEGER DEFAULT 1,
        quantity INTEGER DEFAULT 0,
        UNIQUE(player_id, gem_type, gem_level)
    )""",
    """CREATE TABLE IF NOT EXISTS equipment_sockets (
        equip_instance_id INTEGER PRIMARY KEY REFERENCES player_equipment(id),
        socket_1 TEXT DEFAULT '',
        socket_2 TEXT DEFAULT '',
        socket_3 TEXT DEFAULT '',
        socket_4 TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS monster_codex (
        player_id TEXT NOT NULL,
        npc_id INTEGER NOT NULL,
        kills INTEGER DEFAULT 0,
        PRIMARY KEY (player_id, npc_id)
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
        except Exception:
            pass  # Column đã tồn tại — bỏ qua

    try:
        # Kiểm tra xem player_equipment đã có cột enhance chưa
        await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES ('_mig_ck_', 0, 0, 0)")
        await db.execute("DELETE FROM player_equipment WHERE player_id='_mig_ck_'")
    except Exception:
        # Cần migrate từ schema cũ (quantity-based) sang per-instance
        await db.execute("BEGIN")
        try:
            await db.execute("""CREATE TABLE IF NOT EXISTS player_equipment_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                enhance INTEGER DEFAULT 0,
                equipped INTEGER DEFAULT 0,
                hidden_stats TEXT DEFAULT ''
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
            logger.info("[DB] Migrated player_equipment to per-instance schema")
        except Exception as e:
            await db.execute("ROLLBACK")
            logger.error(f"[DB] Migration failed: {e}")
            raise
        try:
            await db.execute("""UPDATE player_equipment SET equipped = 1
                WHERE id IN (SELECT pe.id FROM player_equipment pe
                JOIN player_equip_slots pes ON pes.player_id = pe.player_id
                AND pes.item_id = pe.item_id AND pe.equipped = 0)""")
            await db.execute("DROP TABLE IF EXISTS player_equip_slots")
        except Exception:
            pass
        try:
            await db.execute("DROP TABLE IF EXISTS _mig_numbers")
        except Exception:
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
        await db.execute("ALTER TABLE player_equipment ADD COLUMN hidden_stats TEXT DEFAULT ''")
    except Exception:
        pass  # Cột đã tồn tại


async def init_db():
    db = await get_db()
    try:
        for sql in TABLES:
            await db.execute(sql)
        await _run_migrations(db)
        await _create_indexes(db)
        await db.commit()
    finally:
        await db.close()


async def _create_indexes(db):
    """
    Indexes cho các query hot nhất:
    - player_equipment: filter equipped=1 theo player_id (load gear mỗi command)
    - player_wives: filter equipped=1 theo player_id (hiển thị battle)
    - active_battles: lookup theo player1_id/player2_id (check battle state)
    - battle_history: query theo player1/player2 (replay command)
    - players: sort theo combat_power (leaderboard)
    - challenges: lookup theo challenger_id (check challenge state)
    """
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_player_equipment_player_equipped ON player_equipment(player_id, equipped)",
        "CREATE INDEX IF NOT EXISTS idx_player_wives_player_equipped ON player_wives(player_id, equipped)",
        "CREATE INDEX IF NOT EXISTS idx_active_battles_p1 ON active_battles(player1_id)",
        "CREATE INDEX IF NOT EXISTS idx_active_battles_p2 ON active_battles(player2_id)",
        "CREATE INDEX IF NOT EXISTS idx_battle_history_p1 ON battle_history(player1_id)",
        "CREATE INDEX IF NOT EXISTS idx_battle_history_p2 ON battle_history(player2_id)",
        "CREATE INDEX IF NOT EXISTS idx_players_combat_power ON players(combat_power DESC)",
        "CREATE INDEX IF NOT EXISTS idx_challenges_challenger ON challenges(challenger_id)",
        "CREATE INDEX IF NOT EXISTS idx_player_skill_slots_player ON player_skill_slots(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_battle_status_battle ON battle_status(battle_id)",
        "CREATE INDEX IF NOT EXISTS idx_arena_tournament_status ON arena_tournament(status)",
        "CREATE INDEX IF NOT EXISTS idx_arena_participants_tid ON arena_participants(tournament_id)",
        "CREATE INDEX IF NOT EXISTS idx_world_boss_status ON world_boss(status)",
        "CREATE INDEX IF NOT EXISTS idx_world_boss_participants_bid ON world_boss_participants(boss_id)",
        "CREATE INDEX IF NOT EXISTS idx_player_gems_player ON player_gems(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_monster_codex_player ON monster_codex(player_id)",
    ]
    for sql in indexes:
        try:
            await db.execute(sql)
        except Exception:
            pass
