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
DUNGEON_MAX_FLOOR = 200
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
    # ══════ THẦN CẢNH (31-40) ══════
    31: {"bonus": "hp",     "tiers": [5, 8, 12, 18]},
    32: {"bonus": "def",    "tiers": [5, 8, 12, 18]},
    33: {"bonus": "dmg",    "tiers": [5, 9, 13, 20]},
    34: {"bonus": "crit",   "tiers": [4, 7, 11, 16]},
    35: {"bonus": "spd",    "tiers": [4, 7, 11, 16]},
    36: {"bonus": "pierce", "tiers": [4, 8, 12, 17]},
    37: {"bonus": "all",    "tiers": [3, 5, 8, 12]},
    38: {"bonus": "drop",   "tiers": [3, 5, 8, 12]},
    39: {"bonus": "xp",     "tiers": [6, 10, 16, 25]},
    40: {"bonus": "all",    "tiers": [4, 7, 10, 16]},
    # ══════ TIÊN CẢNH (41-50) ══════
    41: {"bonus": "hp",     "tiers": [6, 10, 15, 22]},
    42: {"bonus": "dmg",    "tiers": [6, 10, 15, 22]},
    43: {"bonus": "crit",   "tiers": [5, 9, 13, 20]},
    44: {"bonus": "def",    "tiers": [6, 10, 14, 22]},
    45: {"bonus": "pierce", "tiers": [5, 9, 13, 20]},
    46: {"bonus": "all",    "tiers": [3, 6, 9, 14]},
    47: {"bonus": "spd",    "tiers": [5, 9, 13, 19]},
    48: {"bonus": "xp",     "tiers": [8, 14, 20, 30]},
    49: {"bonus": "drop",   "tiers": [4, 7, 10, 15]},
    50: {"bonus": "all",    "tiers": [4, 8, 12, 18]},
    # ══════ THIÊN ĐẾ CẢNH (51-60) ══════
    51: {"bonus": "dmg",    "tiers": [7, 12, 17, 26]},
    52: {"bonus": "crit",   "tiers": [6, 10, 15, 22]},
    53: {"bonus": "hp",     "tiers": [8, 13, 19, 28]},
    54: {"bonus": "def",    "tiers": [7, 12, 17, 26]},
    55: {"bonus": "pierce", "tiers": [6, 10, 15, 22]},
    56: {"bonus": "all",    "tiers": [4, 8, 12, 18]},
    57: {"bonus": "spd",    "tiers": [6, 10, 15, 22]},
    58: {"bonus": "xp",     "tiers": [10, 16, 24, 36]},
    59: {"bonus": "drop",   "tiers": [5, 8, 12, 18]},
    60: {"bonus": "all",    "tiers": [5, 10, 15, 22]},
}

# ── Tu Tiên / Cultivation ─────────────────────────────────────

# Tên cảnh giới (index 0-6)
CULTIVATION_REALMS = [
    "Luyện Khí", "Trúc Cơ", "Kết Đan",
    "Nguyên Anh", "Hóa Thần", "Đại Thừa", "Độ Kiếp",
]

CULTIVATION_REALM_ICONS = ["🌿", "🪨", "💊", "👶", "👻", "🌌", "⚡"]

# Tu vi cần cho mỗi bậc trong từng cảnh giới (8 giá trị = bậc 1→2 đến bậc 8→9)
# Tăng gấp đôi mỗi bậc trong cùng cảnh giới
# Base cost của bậc 1→2 cho từng cảnh giới
CULTIVATION_BASE_COSTS = [
    12_000,           # Luyện Khí   1→2 = 12K  (12 giờ ở rate 1K/giờ)
    500_000,          # Trúc Cơ     1→2 = 500K
    5_000_000,        # Kết Đan     1→2 = 5M
    50_000_000,       # Nguyên Anh  1→2 = 50M
    500_000_000,      # Hóa Thần    1→2 = 500M
    5_000_000_000,    # Đại Thừa    1→2 = 5B
    50_000_000_000,   # Độ Kiếp     1→2 = 50B
]

def get_tuvi_cost(realm: int, stage: int) -> int:
    """Tu vi cần để đột phá từ stage lên stage+1 trong realm.
    Dùng multiplier 1.5x thay vì 2x để tiến trình dễ thở hơn.
    """
    base = CULTIVATION_BASE_COSTS[realm]
    return int(base * (1.5 ** (stage - 1)))

# Tỉ lệ thành công đột phá bậc (stage 1→2 đến 8→9)
CULTIVATION_BREAKTHROUGH_RATES = [0.95, 0.90, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35]

# Phần trăm tu vi mất khi thất bại
CULTIVATION_FAIL_LOSS_PCT = 20

# Tu vi nhận được mỗi lần !tulyen (theo cảnh giới)
CULTIVATION_SESSION_TUVI = [
    1_000,        # Luyện Khí   — 1K/giờ → bậc 1→2 mất 12h ✅
    20_000,       # Trúc Cơ    — 20K/giờ → bậc 1→2 mất 25h
    200_000,      # Kết Đan    — 200K/giờ
    2_000_000,    # Nguyên Anh
    20_000_000,   # Hóa Thần
    200_000_000,  # Đại Thừa
    2_000_000_000,# Độ Kiếp
]

# Cooldown giữa 2 lần !tulyen (giây)
CULTIVATION_COOLDOWN = 1800  # 30 phút

# Tối đa tích lũy 72 giờ (giữ để tương thích, không dùng idle nữa)
CULTIVATION_MAX_HOURS = 72

# Bonus stats % mỗi bậc theo cảnh giới — tăng dần để tạo động lực
# Tổng tích lũy max (Độ Kiếp 9): ~500% all stats
CULTIVATION_STAT_BONUS_PER_STAGE = [4, 5, 6, 7, 8, 10, 12]  # % mỗi bậc

# Passive theo cảnh giới (áp dụng từ bậc 1 trở đi)
CULTIVATION_PASSIVES = {
    0: "coin_boost",        # Luyện Khí: +10% coin từ NPC
    1: "heal_after_win",    # Trúc Cơ: hồi 10% HP sau thắng
    2: "drop_boost",        # Kết Đan: +15% drop rate, +10% gem drop
    3: "combat_regen",      # Nguyên Anh: hồi 5% HP mỗi turn
    4: "pierce_passive",    # Hóa Thần: 20% xuyên giáp
    5: "anti_crit",         # Đại Thừa: 25% miễn crit + -20% dmg nhận
    6: "cheat_death_cult",  # Độ Kiếp: Cheat death 1 lần/trận
}

# Cống phẩm cần để thăng cảnh giới (realm 0→1, 1→2, ...)
# Format: {"item_id": quantity, ...}  item_id là string key trong cultivation_items
CULTIVATION_ASCEND_ITEMS = {
    0: {"linh_thao": 30},                                       # LK→TC
    1: {"linh_dan": 30, "stone_medium": 10},                     # TC→KD
    2: {"dan_thuong_pham": 20, "stone_advanced": 10},            # KD→NA
    3: {"thien_linh_thach": 20, "dan_thuong_pham": 50, "linh_dan": 100},  # NA→HT
    4: {"tien_tinh": 10, "thien_linh_thach": 30, "dan_thuong_pham": 100}, # HT→DT
    5: {"thien_dao_hoa": 2, "tien_tinh": 15, "thien_linh_thach": 50},     # DT→ĐK
}

# Tu vi nhận được khi dùng cống phẩm
CULTIVATION_ITEM_TUVI = {
    "linh_thao":        100,
    "linh_dan":         500,
    "dan_thuong_pham":  2_000,
    "thien_linh_thach": 10_000,
    "tien_tinh":        50_000,
    "thien_dao_hoa":    500_000,
}

# World Boss rare drop rates cho top 1-3
CULTIVATION_RARE_DROP_RATES = {
    "thien_linh_thach": 0.01,   # 1%
    "tien_tinh":        0.0075, # 0.75%
    "thien_dao_hoa":    0.005,  # 0.5%
}
# Phân phối người nhận trong top 3: weight
WORLD_BOSS_TOP3_WEIGHTS = [50, 30, 20]  # top1=50%, top2=30%, top3=20%

# Drop rate cống phẩm từ NPC/Dungeon/Boss (item_id → nguồn)
CULTIVATION_ITEM_DROPS = {
    "linh_thao":       {"npc_level_max": 10,  "chance": 0.075},
    "linh_dan":        {"npc_level_min": 11, "npc_level_max": 20, "chance": 0.05},
    "dan_thuong_pham": {"npc_level_min": 21, "chance": 0.04},
    "thien_linh_thach":{"world_boss": True,  "chance": 0.05},  # 5% drop khi đánh boss
    "tien_tinh":       {"world_boss_top3": True},               # chỉ top 3 boss
    "thien_dao_hoa":   {"world_boss_top1": True},               # chỉ top 1 boss
}

# Tên hiển thị cống phẩm
CULTIVATION_ITEM_NAMES = {
    "linh_thao":        "🌿 Linh Thảo",
    "linh_dan":         "💊 Linh Đan",
    "dan_thuong_pham":  "🔮 Đan Dược Thượng Phẩm",
    "thien_linh_thach": "💎 Thiên Linh Thạch",
    "tien_tinh":        "✨ Tiên Tinh",
    "thien_dao_hoa":    "🌸 Thiên Đạo Hoa",
}

# Tốc độ tu luyện theo role (nhân với rate base khi tính tu vi)
CULTIVATION_ROLE_RATES = {
    "Dragon":    3.0,
    "VIP":       2.0,
    "Supporter": 1.1,
    "Support":   1.1,
    "Coder":     1.0,
    "Unisex":    1.0,
    "Blacklist": 0.8,
}

def get_cultivation_role_mult(role_mult: float) -> float:
    """
    Map role_mult từ DB (Dragon=3.0, VIP=1.5, Supporter=1.2, Coder=1.1, Blacklist=0.8)
    sang cultivation speed multiplier theo yêu cầu.
    """
    if role_mult >= 3.0:  return 3.0   # Dragon  → x3
    if role_mult >= 1.5:  return 2.0   # VIP     → x2
    if role_mult >= 1.2:  return 1.1   # Supporter → x1.1
    if role_mult >= 1.1:  return 1.0   # Coder   → x1.0
    if role_mult <= 0.8:  return 0.8   # Blacklist → x0.8
    return 1.0

# ── Daily Login Rewards ──────────────────────────────────────
DAILY_LOGIN_REWARDS = {
    1: {"coins": 500,  "stones": {"stone_basic": 5}},
    2: {"coins": 500,  "stones": {"stone_basic": 10}},
    3: {"coins": 1000, "stones": {"stone_medium": 3}},
    4: {"coins": 1500, "stones": {"stone_medium": 5}},
    5: {"coins": 3000, "stones": {"stone_advanced": 2}},
    6: {"coins": 5000, "stones": {"stone_basic": 15, "stone_medium": 5}},
    7: {"coins": 10000, "stones": {"stone_advanced": 5}, "gacha_free": True},
}

# ── Achievement System ───────────────────────────────────────
ACHIEVEMENTS = {
    1:  {"name": "🔰 Tân Thủ",           "desc": "Đăng ký tài khoản",                "icon": "🔰", "type": "register",         "target": 1,        "reward_coins": 500},
    2:  {"name": "⚔️ Tập Sự",            "desc": "Giết 100 NPC",                    "icon": "⚔️", "type": "npc_kill",         "target": 100,      "reward_coins": 1000, "reward_stones": {"stone_basic": 10}},
    3:  {"name": "⚔️ Chiến Binh",         "desc": "Giết 1000 NPC",                   "icon": "⚔️", "type": "npc_kill",         "target": 1000,     "reward_coins": 5000, "reward_stones": {"stone_medium": 10}},
    4:  {"name": "⚔️ Tướng Quân",         "desc": "Giết 10000 NPC",                  "icon": "⚔️", "type": "npc_kill",         "target": 10000,    "reward_coins": 20000, "reward_stones": {"stone_advanced": 10}},
    5:  {"name": "🏆 Đấu Sĩ",             "desc": "Thắng 10 trận arena",             "icon": "🏆", "type": "arena_win",        "target": 10,       "reward_coins": 2000, "reward_stones": {"stone_basic": 10}},
    6:  {"name": "🏆 Cao Thủ",            "desc": "Thắng 100 trận arena",            "icon": "🏆", "type": "arena_win",        "target": 100,      "reward_coins": 10000, "reward_stones": {"stone_medium": 10}},
    7:  {"name": "🏆 Huyền Thoại",        "desc": "Thắng 500 trận arena",            "icon": "🏆", "type": "arena_win",        "target": 500,      "reward_coins": 50000, "reward_stones": {"stone_advanced": 10}},
    8:  {"name": "⬆️ Lên Level",          "desc": "Đạt level 30",                    "icon": "⬆️", "type": "reach_level",      "target": 30,       "reward_coins": 3000, "reward_stones": {"stone_medium": 5}},
    9:  {"name": "⬆️ Cao Cấp",            "desc": "Đạt level 50",                    "icon": "⬆️", "type": "reach_level",      "target": 50,       "reward_coins": 8000, "reward_stones": {"stone_advanced": 5}},
    10: {"name": "⬆️ Đỉnh Cao",           "desc": "Đạt level 100",                   "icon": "⬆️", "type": "reach_level",      "target": 100,      "reward_coins": 20000, "reward_stones": {"stone_advanced": 20}},
    11: {"name": "🔨 Thợ Rèn",            "desc": "Có 6 món cường hóa +4",            "icon": "🔨", "type": "enhance_count_4", "target": 6,        "reward_coins": 3000, "reward_stones": {"stone_medium": 10}},
    12: {"name": "🔨 Thợ Cả",             "desc": "Có 6 món cường hóa +7",            "icon": "🔨", "type": "enhance_count_7", "target": 6,        "reward_coins": 10000, "reward_stones": {"stone_advanced": 10}},
    13: {"name": "🔨 Thần Thợ",           "desc": "Có 6 món cường hóa +9",            "icon": "🔨", "type": "enhance_count_9", "target": 6,        "reward_coins": 30000, "reward_stones": {"stone_advanced": 20}},
    14: {"name": "🧘 Tu Sĩ",              "desc": "Tu luyện lần đầu",                "icon": "🧘", "type": "cultivate",         "target": 1,        "reward_coins": 2000, "reward_stones": {"stone_medium": 5}},
    15: {"name": "🧘 Đại Sư",             "desc": "Đạt Trúc Cơ",                     "icon": "🧘", "type": "reach_realm",       "target": 1,        "reward_coins": 10000, "reward_stones": {"stone_advanced": 10}},
    16: {"name": "🧘 Chân Nhân",          "desc": "Đạt Kết Đan",                     "icon": "🧘", "type": "reach_realm",       "target": 2,        "reward_coins": 30000, "reward_stones": {"stone_advanced": 20}},
    17: {"name": "🎰 May Mắn",            "desc": "Quay gacha 1 lần",                "icon": "🎰", "type": "gacha",             "target": 1,        "reward_coins": 1000},
    18: {"name": "🎰 Nghiện Quay",        "desc": "Quay gacha 100 lần",              "icon": "🎰", "type": "gacha",             "target": 100,      "reward_coins": 20000, "reward_stones": {"stone_advanced": 10}},
    19: {"name": "⭐ Thần Thoại",          "desc": "Sở hữu 1 món 7★",                 "icon": "⭐", "type": "own_7star",        "target": 1,        "reward_coins": 10000, "reward_stones": {"stone_advanced": 10}},
    20: {"name": "⭐ Sưu Tập",             "desc": "Sở hữu 5 món 7★",                 "icon": "⭐", "type": "own_7star",        "target": 5,        "reward_coins": 80000, "reward_stones": {"stone_advanced": 40}},
    21: {"name": "💎 Nạm Đá",              "desc": "Gắn đá cấp 5",                    "icon": "💎", "type": "gem_level",         "target": 5,        "reward_coins": 5000, "reward_stones": {"stone_medium": 10}},
    22: {"name": "💎 Thợ Đá",              "desc": "Gắn đá cấp 7",                    "icon": "💎", "type": "gem_level",         "target": 7,        "reward_coins": 15000, "reward_stones": {"stone_advanced": 10}},
    23: {"name": "💎 Đại Sư Đá Quý",       "desc": "Gắn đá cấp 9",                    "icon": "💎", "type": "gem_level",         "target": 9,        "reward_coins": 50000, "reward_stones": {"stone_advanced": 25}},
    24: {"name": "🔄 Thay Tính",           "desc": "Reroll thuộc tính ẩn 1 lần",      "icon": "🔄", "type": "reroll_count",      "target": 1,        "reward_coins": 2000, "reward_stones": {"stone_medium": 5}},
    25: {"name": "🔄 Luyện Tính",          "desc": "Reroll thuộc tính ẩn 10 lần",     "icon": "🔄", "type": "reroll_count",      "target": 10,       "reward_coins": 15000, "reward_stones": {"stone_advanced": 10}},
    26: {"name": "🔄 Ma Tính",             "desc": "Reroll thuộc tính ẩn 50 lần",     "icon": "🔄", "type": "reroll_count",      "target": 50,       "reward_coins": 80000, "reward_stones": {"stone_advanced": 30}},
}
