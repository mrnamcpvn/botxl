import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
TOKEN = os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE"
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY") or "botxl-secret-key-change-me"

QUIZ_CHANNEL_ID = int(os.getenv("QUIZ_CHANNEL_ID") or "1040459995319373864")

# World Boss
WORLD_BOSS_CHANNEL_ID   = int(os.getenv("WORLD_BOSS_CHANNEL_ID", "1529021378416738384"))
WORLD_BOSS_HOURS        = [int(h) for h in os.getenv("WORLD_BOSS_HOURS", "11,15,20").split(",")]
WORLD_BOSS_REGISTER_TIME = int(os.getenv("WORLD_BOSS_REGISTER_TIME", "300"))  # giây đăng ký
WORLD_BOSS_RESPAWN_DELAY = int(os.getenv("WORLD_BOSS_RESPAWN_DELAY", "15"))   # giây chờ hồi sinh
WORLD_BOSS_ATTACK_INTERVAL = int(os.getenv("WORLD_BOSS_ATTACK_INTERVAL", "10"))  # giây boss attack 1 lần

# Arena Tournament (Đấu Trường Sinh Tử)
ARENA_INTERVAL          = int(os.getenv("ARENA_INTERVAL", "3600"))    # giây giữa 2 mùa auto
ARENA_REGISTER_TIME     = int(os.getenv("ARENA_REGISTER_TIME", "60")) # giây mở đăng ký
ARENA_MIN_PLAYERS       = int(os.getenv("ARENA_MIN_PLAYERS", "4"))
ARENA_MAX_PLAYERS       = int(os.getenv("ARENA_MAX_PLAYERS", "8"))
ARENA_AUTO_ENABLED      = os.getenv("ARENA_AUTO_ENABLED", "true").lower() == "true"
ARENA_BATTLE_DELAY      = float(os.getenv("ARENA_BATTLE_DELAY", "3.0")) # giây delay giữa các trận
ARENA_SHOW_LOG_LINES    = int(os.getenv("ARENA_SHOW_LOG_LINES", "6"))   # số dòng log hiển thị/trận

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
# (giá trị được load từ env ở trên, không override lại)

# ── Gem Socket / Đá Khảm ────────────────────────────────────
GEM_TYPES = {
    "hp":     {"name": "🔴 Hồng Ngọc",  "stat": "hp",     "levels": [80, 150, 250, 400, 600, 900, 1300, 1800, 2500]},
    "atk":    {"name": "⚔️ Lục Bảo",    "stat": "atk",    "levels": [8, 15, 25, 40, 60, 90, 130, 180, 250]},
    "def":    {"name": "🛡️ Lam Ngọc",   "stat": "def",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "spd":    {"name": "💨 Phong Tinh",  "stat": "spd",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "crit":   {"name": "💥 Huyết Thạch", "stat": "crit",   "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
    "pierce": {"name": "🔱 Tử Tinh",    "stat": "pierce", "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
}
GEM_MAX_LEVEL = 9
GEM_MERGE_COST_PER_LEVEL = 500
GEM_REMOVE_COST_PER_LEVEL = 1000
SOCKETS_BY_STAR = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 4, 8: 4, 9: 4}

# ── Monster Codex / Đồ Thư ──────────────────────────────────
CODEX_MILESTONES = [100, 500, 1000, 10000]

CODEX_DATA = {
    1:  {"bonus": "coin",   "tiers": [4, 8, 12, 20]},
    2:  {"bonus": "xp",     "tiers": [4, 8, 12, 20]},
    3:  {"bonus": "def",    "tiers": [3, 6, 9, 15]},
    4:  {"bonus": "pierce", "tiers": [3, 5, 8, 12]},
    5:  {"bonus": "hp",     "tiers": [3, 5, 8, 12]},
    6:  {"bonus": "spd",    "tiers": [3, 5, 8, 12]},
    7:  {"bonus": "dmg",    "tiers": [3, 5, 8, 11]},
    8:  {"bonus": "crit",   "tiers": [2, 4, 6, 9]},
    9:  {"bonus": "dmg",    "tiers": [3, 6, 9, 14]},
    10: {"bonus": "spd",    "tiers": [3, 5, 8, 11]},
    11: {"bonus": "def",    "tiers": [4, 7, 10, 16]},
    12: {"bonus": "crit",   "tiers": [3, 5, 8, 11]},
    13: {"bonus": "pierce", "tiers": [3, 6, 9, 14]},
    14: {"bonus": "all",    "tiers": [2, 3, 5, 8]},
    15: {"bonus": "drop",   "tiers": [2, 4, 6, 9]},
    16: {"bonus": "spd",    "tiers": [3, 6, 9, 14]},
    17: {"bonus": "hp",     "tiers": [4, 8, 11, 16]},
    18: {"bonus": "xp",     "tiers": [5, 9, 13, 21]},
    19: {"bonus": "dmg",    "tiers": [4, 7, 10, 16]},
    20: {"bonus": "hp",     "tiers": [5, 8, 12, 18]},
    21: {"bonus": "crit",   "tiers": [3, 6, 9, 14]},
    22: {"bonus": "dmg",    "tiers": [4, 8, 11, 16]},
    23: {"bonus": "xp",     "tiers": [6, 10, 15, 23]},
    24: {"bonus": "crit",   "tiers": [4, 7, 10, 15]},
    25: {"bonus": "def",    "tiers": [4, 8, 11, 16]},
    26: {"bonus": "dmg",    "tiers": [5, 8, 12, 18]},
    27: {"bonus": "pierce", "tiers": [4, 8, 11, 16]},
    28: {"bonus": "all",    "tiers": [2, 4, 6, 10]},
    29: {"bonus": "all",    "tiers": [3, 5, 8, 12]},
    30: {"bonus": "all",    "tiers": [3, 6, 9, 14]},
}
