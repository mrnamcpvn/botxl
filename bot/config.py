import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
TOKEN = os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE"
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY") or "botxl-secret-key-change-me"

QUIZ_CHANNEL_ID = int(os.getenv("QUIZ_CHANNEL_ID") or "1040459995319373864")

# Arena Tournament (Đấu Trường Sinh Tử)
ARENA_INTERVAL          = int(os.getenv("ARENA_INTERVAL", "86400"))   # giây giữa 2 mùa auto (mặc định 24h)
ARENA_REGISTER_TIME     = int(os.getenv("ARENA_REGISTER_TIME", "120")) # giây mở đăng ký
ARENA_MIN_PLAYERS       = int(os.getenv("ARENA_MIN_PLAYERS", "4"))
ARENA_MAX_PLAYERS       = int(os.getenv("ARENA_MAX_PLAYERS", "32"))
ARENA_AUTO_ENABLED      = os.getenv("ARENA_AUTO_ENABLED", "false").lower() == "true"
ARENA_BATTLE_DELAY      = float(os.getenv("ARENA_BATTLE_DELAY", "1.5")) # giây delay giữa các trận
ARENA_SHOW_LOG_LINES    = int(os.getenv("ARENA_SHOW_LOG_LINES", "3"))   # số dòng log hiển thị/trận

HP_REGEN_PCT = 10
HP_REGEN_INTERVAL = 30

LEVEL_XP_BASE = 80
STAT_POINTS_PER_LEVEL = 3

DEFAULT_COINS = 0
DEFAULT_ELO = 1000

REWARD_WIN_COINS = 50
REWARD_WIN_XP = 25

BATTLE_TIMEOUT_SECONDS = 15
CHALLENGE_TIMEOUT_SECONDS = 30
CHALLENGE_PENALTY_COINS = 20
STUCK_BATTLE_TIMEOUT = 30
BATTLE_COOLDOWN_SECONDS = 120

LEGENDARY_CHANCE = 0.05
LEGENDARY_MULTIPLIER = 5.0
LUCKY_LEGENDARY_MULTIPLIER = 2.0

# Enhancement
MAX_ENHANCE = 9
ENHANCE_BONUS_PER_LEVEL = 0.08    # +8% per enhance star

# Stone item IDs (mapped to inventory)
STONE_BASIC_ID = 1001
STONE_MEDIUM_ID = 1002
STONE_ADVANCED_ID = 1003

# Enhance costs: (target_star, stone_id, stone_qty, coin_cost)
ENHANCE_COSTS = {
    1: (STONE_BASIC_ID, 2, 200),
    2: (STONE_BASIC_ID, 4, 200),
    3: (STONE_BASIC_ID, 6, 200),
    4: (STONE_MEDIUM_ID, 2, 500),
    5: (STONE_MEDIUM_ID, 4, 500),
    6: (STONE_MEDIUM_ID, 6, 500),
    7: (STONE_ADVANCED_ID, 2, 1000),
    8: (STONE_ADVANCED_ID, 4, 1000),
    9: (STONE_ADVANCED_ID, 6, 1000),
}

# Enhance success rates: target_star -> probability
ENHANCE_SUCCESS_RATES = {
    1: 1.00, 2: 0.875, 3: 0.75,
    4: 0.625, 5: 0.50, 6: 0.375,
    7: 0.25, 8: 0.175, 9: 0.10,
}

# Dungeon
DUNGEON_MAX_FLOOR = 100
DUNGEON_REQUIRED_LEVEL = 7
DUNGEON_FREE_ENTRIES = 1
DUNGEON_MAX_TICKETS = 2
DUNGEON_TICKET_COST_1 = 200
DUNGEON_TICKET_COST_2 = 400

# Artifact (Thần Khí)
ARTIFACT_BOOST_PER_STAR = 0.15
ARTIFACT_UNLOCK_COST = 100000
ARTIFACT_MAX_STAR = 10
ARTIFACT_STONE_DROP_CHANCE = 0.05
ARTIFACT_STONE_DROP_NPC_MIN_LEVEL = 15
ARTIFACT_STONE_DUNGEON_MIN_FLOOR = 50
ARTIFACT_STONE_DUNGEON_CHANCE = 0.03

GLOBAL_HP_MULT = 2
GLOBAL_DEF_MULT = 2

EQUIP_MERGE_COSTS = {
    1: (500, 0.70),
    2: (1000, 0.60),
    3: (2000, 0.50),
    4: (5000, 0.50),
    5: (10000, 0.50),
    6: (50000, 1.00),
}
ARTIFACT_UPGRADE_COSTS = {
    1: (0, 100000),
    2: (10, 100000),
    3: (20, 100000),
    4: (30, 200000),
    5: (40, 200000),
    6: (50, 300000),
    7: (60, 300000),
    8: (70, 400000),
    9: (80, 400000),
    10: (90, 500000),
}

# ── Arena Tournament ──────────────────────────────────────────
ARENA_INTERVAL = 3600
ARENA_REGISTER_TIME = 60
ARENA_MIN_PLAYERS = 4
ARENA_MAX_PLAYERS = 8
ARENA_AUTO_ENABLED = True
ARENA_BATTLE_DELAY = 3
ARENA_SHOW_LOG_LINES = 6

# ── World Boss ──────────────────────────────────────────────
WORLD_BOSS_HOURS = [11, 15, 20]
WORLD_BOSS_REGISTER_TIME = 300
WORLD_BOSS_RESPAWN_DELAY = 15
WORLD_BOSS_CHANNEL_ID = 1529021378416738384
