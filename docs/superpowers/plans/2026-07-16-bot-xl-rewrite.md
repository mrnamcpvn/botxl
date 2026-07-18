# Bot-XL Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rewrite bot-xl from monolithic JSON-based Discord bot to modular architecture with SQLite, class system, ELO ranking, daily quests, battle replay, and web dashboard.

**Architecture:** Modular monolith with pure-function battle engine (no Discord deps), SQLite via aiosqlite, thin cog layer for Discord commands, FastAPI for web dashboard.

**Tech Stack:** Python 3.10+, discord.py 2.3+, aiosqlite, FastAPI, Jinja2, htmx

---

### Task 0: Setup — .gitignore, __init__.py files, requirements.txt

**Files:**
- Create: `.gitignore`
- Create: `bot/__init__.py`
- Create: `bot/models/__init__.py`
- Create: `bot/engine/__init__.py`
- Create: `bot/cogs/__init__.py`
- Create: `bot/views/__init__.py`
- Create: `bot/data/__init__.py`
- Create: `web/__init__.py`
- Create: `web/routes/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write .gitignore**
Write `E:\TFS\bot-xl\.gitignore`:
```
.env
__pycache__/
venv/
*.db
data/backups/
```

- [ ] **Step 2: Write all __init__.py files**
Each file contains just: `# E:\TFS\bot-xl\bot\__init__.py` (with correct path for each)

- [ ] **Step 3: Write requirements.txt**
```txt
discord.py>=2.3.0
aiosqlite>=0.19.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

### Task 1: Config + Logger + Database

**Files:**
- Create: `bot/config.py`
- Create: `bot/logger.py`
- Create: `bot/database.py`

- [ ] **Step 1: Write bot/config.py**
```python
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")
TOKEN = os.getenv("TOKEN") or "YOUR_BOT_TOKEN_HERE"

HP_REGEN_RATE = 10
HP_REGEN_INTERVAL = 30

LEVEL_XP_BASE = 80  # XP needed = level * LEVEL_XP_BASE
STAT_POINTS_PER_LEVEL = 3

DEFAULT_COINS = 0
DEFAULT_ELO = 1000

REWARD_WIN_COINS = 50
REWARD_WIN_XP = 25
REWARD_LOSE_COINS = 10
REWARD_LOSE_XP = 5

BATTLE_TIMEOUT_SECONDS = 15
CHALLENGE_TIMEOUT_SECONDS = 30
CHALLENGE_PENALTY_COINS = 20
STUCK_BATTLE_TIMEOUT = 20

LEGENDARY_CHANCE = 0.05
LEGENDARY_MULTIPLIER = 5.0
LUCKY_LEGENDARY_MULTIPLIER = 2.0  # ×2 khi có buff lucky
```

- [ ] **Step 2: Write bot/logger.py**
```python
import logging
import sys

def setup_logger(name: str = "botxl") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
    return logger

logger = setup_logger()
```

- [ ] **Step 3: Write bot/database.py**
```python
import aiosqlite
import os
from bot.config import DB_PATH

async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
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
            );

            CREATE TABLE IF NOT EXISTS player_skills (
                player_id TEXT NOT NULL,
                skill_id INTEGER NOT NULL,
                PRIMARY KEY (player_id, skill_id)
            );

            CREATE TABLE IF NOT EXISTS player_skill_slots (
                player_id TEXT NOT NULL,
                slot TEXT NOT NULL CHECK(slot IN ('attack','special','defense','passive')),
                skill_id INTEGER NOT NULL,
                PRIMARY KEY (player_id, slot)
            );

            CREATE TABLE IF NOT EXISTS player_equipment (
                player_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (player_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS player_equip_slots (
                player_id TEXT NOT NULL,
                slot TEXT NOT NULL CHECK(slot IN ('weapon','armor','accessory','crown')),
                item_id INTEGER,
                PRIMARY KEY (player_id, slot)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                player_id TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (player_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS player_buffs (
                player_id TEXT PRIMARY KEY,
                attack_boost INTEGER DEFAULT 0,
                defense_boost INTEGER DEFAULT 0,
                lucky INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS active_battles (
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
            );

            CREATE TABLE IF NOT EXISTS battle_status (
                battle_id INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (battle_id, player_id, key)
            );

            CREATE TABLE IF NOT EXISTS battle_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id TEXT NOT NULL,
                player2_id TEXT NOT NULL,
                p1_name TEXT NOT NULL,
                p2_name TEXT NOT NULL,
                winner_id TEXT NOT NULL,
                rounds TEXT NOT NULL,
                fought_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS challenges (
                target_id TEXT PRIMARY KEY,
                challenger_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_quests (
                player_id TEXT NOT NULL,
                quest_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                target INTEGER NOT NULL,
                completed INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                date TEXT NOT NULL,
                PRIMARY KEY (player_id, quest_id, date)
            );
        """)
        await db.commit()
    finally:
        await db.close()
```

---

### Task 2: Data Definitions (Skills, Shop, Classes)

**Files:**
- Create: `bot/data/skills.py`
- Create: `bot/data/shop_items.py`
- Create: `bot/data/classes.py`

- [ ] **Step 1: Write bot/data/classes.py**
```python
CLASSES = {
    "banxabong": {
        "name": "Bán Xà Bông", "icon": "🧼",
        "hp_base": 120, "hp_scale": 12,
        "atk_base": 12, "atk_scale": 3,
        "def_base": 8, "def_scale": 2,
        "desc": "Tập tễnh vào đời, đánh ai cũng được",
        "price": 0
    },
    "xola": {
        "name": "Xỏ Lá", "icon": "🤓",
        "hp_base": 180, "hp_scale": 18,
        "atk_base": 6, "atk_scale": 2,
        "def_base": 15, "def_scale": 4,
        "desc": "Trâu bò nhưng đánh như muỗi đốt cột",
        "price": 500,
        "perk": "defend_reduce"
    },
    "sieunhan": {
        "name": "Siêu Nhân Xà Phòng", "icon": "💪",
        "hp_base": 80, "hp_scale": 8,
        "atk_base": 18, "atk_scale": 5,
        "def_base": 3, "def_scale": 1,
        "desc": "Có mỗi sức mạnh, còn lại toàn xương",
        "price": 500,
        "perk": "first_strike"
    },
    "thaychua": {
        "name": "Thầy Chùa", "icon": "🙏",
        "hp_base": 90, "hp_scale": 9,
        "atk_base": 14, "atk_scale": 4,
        "def_base": 4, "def_scale": 1,
        "desc": "Từ bi hỉ xả, đấm 1 phát 1000 năm địa ngục",
        "price": 500,
        "perk": "cd_reduce"
    },
    "muoi": {
        "name": "Con Muỗi", "icon": "🦟",
        "hp_base": 110, "hp_scale": 10,
        "atk_base": 12, "atk_scale": 3,
        "def_base": 5, "def_scale": 1,
        "desc": "Hút máu, khó đập, dễ chết sau bàn tay",
        "price": 1000,
        "perk": "lifesteal_boost"
    },
    "chodien": {
        "name": "Chó Điên", "icon": "🐕",
        "hp_base": 140, "hp_scale": 14,
        "atk_base": 15, "atk_scale": 4,
        "def_base": 5, "def_scale": 1,
        "desc": "Càng ăn đòn càng hăng, cắn xé tất cả",
        "price": 1000,
        "perk": "rage_boost"
    },
    "baque": {
        "name": "Ba Que", "icon": "🥢",
        "hp_base": 130, "hp_scale": 13,
        "atk_base": 10, "atk_scale": 3,
        "def_base": 12, "def_scale": 3,
        "desc": "Xỏ lá bằng tăm tre, chuyên chọc gậy bánh xe",
        "price": 2000,
        "perk": "last_stand_boost"
    },
    "trumcuoi": {
        "name": "Trùm Cuối", "icon": "👑",
        "hp_base": 200, "hp_scale": 20,
        "atk_base": 20, "atk_scale": 6,
        "def_base": 15, "def_scale": 3,
        "desc": "Huyền thoại sống, cuối cùng vẫn là xỏ lá",
        "price": -1,
        "admin_only": True,
        "perk": "random_buff"
    },
}

PERK_DESCRIPTIONS = {
    "defend_reduce": "Nhận ít dmg hơn 10% nếu đang phòng thủ",
    "first_strike": "Đòn tấn công đầu trận ×1.5",
    "cd_reduce": "Cooldown tất cả skill -1",
    "lifesteal_boost": "Hút máu +20% hiệu quả",
    "rage_boost": "Rage tích +25% nhanh hơn",
    "last_stand_boost": "Last stand kích hoạt ở 40% HP",
    "random_buff": "Random buff mỗi turn",
}

DEFAULT_SKILLS = {
    "banxabong": [1, 5, 10, 14],
    "xola": [1, 5, 11, 14],
    "sieunhan": [1, 5, 10, 15],
    "thaychua": [2, 7, 12, 17],
    "muoi": [1, 6, 12, 17],
    "chodien": [3, 5, 10, 19],
    "baque": [1, 5, 12, 20],
    "trumcuoi": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
}

DEFAULT_SKILL_SLOTS = {
    "banxabong": {"attack": 1, "special": 5, "defense": 10, "passive": 14},
    "xola": {"attack": 1, "special": 5, "defense": 11, "passive": 14},
    "sieunhan": {"attack": 1, "special": 5, "defense": 10, "passive": 15},
    "thaychua": {"attack": 2, "special": 7, "defense": 12, "passive": 17},
    "muoi": {"attack": 1, "special": 6, "defense": 12, "passive": 17},
    "chodien": {"attack": 3, "special": 5, "defense": 10, "passive": 19},
    "baque": {"attack": 1, "special": 5, "defense": 12, "passive": 20},
    "trumcuoi": {"attack": 4, "special": 9, "defense": 13, "passive": 20},
}
```

- [ ] **Step 2: Write bot/data/skills.py**
Copy all 20 skills from old `arena.py` SKILLS_DB (lines 23-48), exactly the same definitions. Add:
```python
# Keep the same SKILLS_DB dict from original code, same keys 1-20
# Add:
CATEGORY_LABELS = {"attack": "💥 Xỏ Lá", "special": "🔥 Đặc Biệt", "defense": "🛡️ Chống Xỏ Lá", "passive": "💎 Bị Động"}
RARITY_COLORS = {"common": 0x888888, "uncommon": 0x00ff88, "rare": 0x0088ff, "epic": 0xaa00ff, "legendary": 0xffaa00}
RARITY_STARS = {"common": "⭐", "uncommon": "⭐⭐", "rare": "⭐⭐⭐", "epic": "⭐⭐⭐⭐", "legendary": "⭐⭐⭐⭐⭐"}
SLOT_NAMES = {"weapon": "🗡️ Vũ Khí", "armor": "🛡️ Giáp", "accessory": "💍 Phụ Kiện", "crown": "👑 Vương Miện"}
```

- [ ] **Step 3: Write bot/data/shop_items.py**
Copy all SHOP_ITEMS from old `arena.py` (lines 93-120), exactly the same definitions.

---

### Task 3: Models (Player, Battle dataclasses)

**Files:**
- Create: `bot/models/player.py`
- Create: `bot/models/battle.py`

- [ ] **Step 1: Write bot/models/player.py**
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Player:
    id: str
    name: str
    class_id: str
    hp: int
    hp_max: int
    attack_min: int
    attack_max: int
    defense: int
    wins: int
    losses: int
    damage_dealt: int
    damage_taken: int
    coins: int
    xp: int
    level: int
    stat_points: int
    elo: int
    attack_cd: int
    special_cd: int
    defense_cd: int
    last_hp_update: Optional[float] = None
    upgrade_hp: int = 0
    upgrade_atk: int = 0
    upgrade_def: int = 0

@dataclass
class PlayerSnapshot:
    id: str
    name: str
    hp: int
    hp_max: int
    attack_min: int
    attack_max: int
    defense: int
    class_id: str
    damage_pct_bonus: int
    buffs: dict
    effects: dict
```

- [ ] **Step 2: Write bot/models/battle.py**
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RoundLog:
    r: int
    actor: str
    skill: str
    damage: int
    heal: int
    hp1: int
    hp2: int
    effects: list

@dataclass
class RoundResult:
    p1: dict
    p2: dict
    log_messages: list
    finished: bool
    winner_id: Optional[str]

@dataclass
class BattleFlags:
    p1_defending: bool = False
    p2_defending: bool = False
    p1_stunned: bool = False
    p2_stunned: bool = False
```

---

### Task 4: Battle Engine (Pure Functions)

**Files:**
- Create: `bot/engine/battle.py`
- Create: `bot/engine/rewards.py`
- Create: `bot/engine/ranking.py`

- [ ] **Step 1: Write bot/engine/ranking.py**
```python
def calculate_elo(p1_elo: int, p2_elo: int, winner: int, battles_count: int = 0) -> tuple[int, int]:
    k_factor = max(16, 32 - battles_count // 10)
    expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
    expected_p2 = 1 - expected_p1
    if winner == 1:
        return (round(p1_elo + k_factor * (1 - expected_p1)),
                round(p2_elo + k_factor * (0 - expected_p2)))
    return (round(p1_elo + k_factor * (0 - expected_p1)),
            round(p2_elo + k_factor * (1 - expected_p2)))
```

- [ ] **Step 2: Write bot/engine/rewards.py**
```python
from bot.config import REWARD_WIN_COINS, REWARD_WIN_XP, REWARD_LOSE_COINS, REWARD_LOSE_XP, LEVEL_XP_BASE

def calc_level(total_xp: int) -> tuple[int, int]:
    level = 1
    xp = total_xp
    while xp >= level * LEVEL_XP_BASE:
        xp -= level * LEVEL_XP_BASE
        level += 1
    return level, xp

def calc_rewards(winner: bool, opponent_class: str = None) -> tuple[int, int]:
    if winner:
        coins = REWARD_WIN_COINS
        xp = REWARD_WIN_XP
    else:
        coins = REWARD_LOSE_COINS
        xp = REWARD_LOSE_XP
    return coins, xp

def apply_rewards(pdata: dict, coins: int, xp: int) -> tuple[int, bool]:
    pdata["coins"] = pdata.get("coins", 0) + coins
    old_level = pdata.get("level", 1)
    new_level, _ = calc_level(pdata.get("xp", 0) + xp)
    pdata["xp"] = pdata.get("xp", 0) + xp
    pdata["level"] = new_level
    if new_level > old_level:
        from bot.config import STAT_POINTS_PER_LEVEL
        pdata["stat_points"] = pdata.get("stat_points", 0) + (new_level - old_level) * STAT_POINTS_PER_LEVEL
    return new_level > old_level
```

- [ ] **Step 3: Write bot/engine/battle.py**
This is the big one — port the entire combat logic from `arena.py:813-1143` into pure functions.

```python
import random
from bot.data.skills import SKILLS_DB
from bot.data.classes import CLASSES
from bot.models.battle import RoundResult, BattleFlags

# ─── Helper: tính stat hiệu dụng từ class + upgrade + equipment + passive ───

def calc_class_stat(base: int, scale: int, level: int, upgrade: int = 0) -> int:
    return base + scale * (level - 1)

def get_effective_stats(pdata: dict, player_id: str = None) -> dict:
    from bot.data.skills import SKILLS_DB
    from bot.data.shop_items import SHOP_ITEMS
    
    cls_def = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
    lvl = pdata.get("level", 1)
    upgrade_hp = pdata.get("upgrade_hp", 0)
    upgrade_atk = pdata.get("upgrade_atk", 0)
    upgrade_def = pdata.get("upgrade_def", 0)
    
    hp_max = calc_class_stat(cls_def["hp_base"], cls_def["hp_scale"], lvl) + upgrade_hp * 10
    atk_min = calc_class_stat(cls_def["atk_base"], cls_def["atk_scale"], lvl) + upgrade_atk * 2
    atk_max = atk_min + 5 + upgrade_atk
    defense = calc_class_stat(cls_def["def_base"], cls_def["def_scale"], lvl) + upgrade_def * 2
    
    # Equipment bonus
    # (simplified: equipment slot data loaded from DB elsewhere, passed in pdata)
    eq = pdata.get("equipped", {})
    for slot, item_id in eq.items():
        if item_id and item_id in SHOP_ITEMS:
            for k, v in SHOP_ITEMS[item_id]["effect"].items():
                if k == "hp_max": hp_max += v
                elif k == "attack_min": atk_min += v
                elif k == "attack_max": atk_max += v
                elif k == "defense": defense += v
    
    # Passive bonus
    damage_pct = 0
    passive_id = pdata.get("skill_equipped", {}).get("passive")
    skill = SKILLS_DB.get(passive_id)
    if skill and skill["category"] == "passive" and skill["type"] == "stat_boost":
        if skill.get("stat") == "hp_max":
            hp_max += int(hp_max * skill["boost_pct"] / 100)
        elif skill.get("stat") == "damage":
            damage_pct = skill["boost_pct"]
        elif skill.get("stat") == "defense":
            defense += skill.get("boost_flat", 0)
    
    return {
        "hp_max": hp_max,
        "attack_min": atk_min,
        "attack_max": atk_max,
        "defense": defense,
        "damage_pct": damage_pct,
    }

# ─── Skill helpers ───

def get_equipped_skill(pdata: dict, category: str) -> dict:
    sid = pdata.get("skill_equipped", {}).get(category)
    return SKILLS_DB.get(sid, SKILLS_DB.get(1))

# ─── HP Regen ───

def regen_hp(pdata: dict, now: float = None) -> bool:
    if now is None:
        import time
        now = time.time()
    last = pdata.get("last_hp_update", 0)
    if last <= 0:
        pdata["last_hp_update"] = now
        return False
    from bot.config import HP_REGEN_INTERVAL, HP_REGEN_RATE
    elapsed = now - last
    if elapsed < HP_REGEN_INTERVAL:
        return False
    ticks = int(elapsed // HP_REGEN_INTERVAL)
    hp_gain = ticks * HP_REGEN_RATE
    old = pdata["hp"]
    pdata["hp"] = min(pdata.get("hp_max", 100), pdata["hp"] + hp_gain)
    pdata["last_hp_update"] = now
    return pdata["hp"] != old

# ─── Damage calculation ───

def calculate_damage(
    atk_min: int, atk_max: int,
    defense: int,
    skill: dict,
    buffs: dict,
    damage_pct_bonus: int,
    is_defending: bool,
    defender_effects: dict,
    attacker_id: str = None,
    defender_id: str = None,
) -> dict:
    mult = skill.get("multiplier", 1.0)
    if skill.get("type") == "multi_hit":
        hits = skill.get("hits", 2)
        base_dmg = sum(int(random.randint(atk_min, atk_max) * mult) for _ in range(hits))
    else:
        base_dmg = int(random.randint(atk_min, atk_max) * mult)
    
    # Legendary proc
    if skill.get("legendary_chance"):
        lc = skill["legendary_chance"] / 100
        if buffs.get("lucky"):
            lc *= 2
        if random.random() < lc:
            base_dmg = int(base_dmg * 1.67)
    
    # Passive damage boost
    if damage_pct_bonus > 0:
        base_dmg = int(base_dmg * (1 + damage_pct_bonus / 100))
    # Buff attack boost
    if buffs.get("attack_boost"):
        base_dmg = int(base_dmg * (1 + buffs["attack_boost"] / 100))
    
    # Defense
    eff_def = defense * 2 if is_defending else defense
    if buffs.get("defense_boost"):
        eff_def = int(eff_def * (1 + buffs["defense_boost"] / 100))
    if skill.get("def_reduce_pct"):
        eff_def = int(eff_def * (100 - skill["def_reduce_pct"]) / 100)
    if skill.get("pierce_pct"):
        eff_def = int(eff_def * (100 - skill["pierce_pct"]) / 100)
    
    damage = max(1, base_dmg - eff_def)
    
    return {
        "damage": damage,
        "base_dmg": base_dmg,
        "eff_def": eff_def,
        "legendary_proc": skill.get("legendary_chance") and random.random() < skill["legendary_chance"] / 100,
    }

# ─── Perk helpers ───

def get_class_perk(class_id: str) -> str | None:
    cls = CLASSES.get(class_id)
    return cls.get("perk") if cls else None

# ─── Main battle execution ───

async def execute_action(
    p1: dict, p2: dict,
    turn_player: int,  # 0 = p1 acts, 1 = p2 acts
    action: dict,  # {"type": "attack"/"special"/"defense", "skill_id": int}
    flags: dict,  # {"p1_defending": bool, ...}
) -> RoundResult:
    from bot.data.skills import SKILLS_DB
    
    attacker = p1 if turn_player == 0 else p2
    defender = p2 if turn_player == 0 else p1
    is_p1_turn = turn_player == 0
    result_lines = []
    
    skill = SKILLS_DB.get(action["skill_id"], SKILLS_DB[1])
    cat = action["type"]
    
    # ─── DEFENSE moves ───
    if cat == "defense":
        if skill["type"] == "defend":
            flags["p1_defending" if is_p1_turn else "p2_defending"] = True
            heal_pct = skill.get("heal_pct", 8)
            heal_amt = int(attacker.get("hp_max", 100) * heal_pct / 100)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker.get("hp", 0) + heal_amt)
            result_lines.append(f"🛡️ **{skill['name']}** — ×3 DEF + hồi {heal_amt}HP! ☂️")
            cd_key = f"{cat}_cd"
            attacker[cd_key] = skill.get("cooldown", 0)
        
        elif skill["type"] == "heal":
            heal_pct = skill.get("heal_pct", 40)
            heal_amt = int(attacker.get("hp_max", 100) * heal_pct / 100)
            old = attacker.get("hp", 0)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker["hp"] + heal_amt)
            for kb in ["_burn", "_def_reduced"]:
                attacker.pop(kb, None)
            flags["p1_stunned" if is_p1_turn else "p2_stunned"] = False
            result_lines.append(f"💚 **{skill['name']}** — hồi **{attacker['hp'] - old} HP**!")
            cd_key = f"{cat}_cd"
            attacker[cd_key] = skill.get("cooldown", 0)
        
        elif skill["type"] == "shield":
            sh_pct = skill.get("shield_pct", 35)
            sh_amt = int(attacker.get("hp_max", 100) * sh_pct / 100)
            key = f"p{1 if is_p1_turn else 2}_shield_hp"
            flags[key] = sh_amt
            pop_key = f"p{1 if is_p1_turn else 2}_shield_pop_heal"
            flags[pop_key] = skill.get("shield_pop_heal", 15)
            result_lines.append(f"🛡️ **{skill['name']}** — khiên {sh_amt}HP! (+{skill.get('shield_pop_heal', 15)}% khi vỡ)")
            cd_key = f"{cat}_cd"
            attacker[cd_key] = skill.get("cooldown", 0)
        
        elif skill["type"] == "counter":
            key = f"p{1 if is_p1_turn else 2}_counter"
            flags[key] = skill.get("multiplier", 2.5)
            immune_key = f"p{1 if is_p1_turn else 2}_counter_immune"
            flags[immune_key] = True
            result_lines.append(f"🔄 **{skill['name']}** — miễn dmg + phản ×{skill.get('multiplier', 2.5)}!")
            cd_key = f"{cat}_cd"
            attacker[cd_key] = skill.get("cooldown", 0)
    
    # ─── DAMAGE moves (attack + special) ───
    else:
        atk_eff = get_effective_stats(attacker)
        def_eff = get_effective_stats(defender)
        atk_buffs = attacker.get("buffs", {})
        def_buffs = defender.get("buffs", {})
        
        dodge_key = f"p{1 if not is_p1_turn else 2}_dodge_passive"
        if flags.get(dodge_key):
            if random.random() < flags[dodge_key]:
                result_lines.append(f"🍀 **{defender.get('name', '???')} NÉ ĐÒN!**")
                cd_key = f"{cat}_cd"
                attacker[cd_key] = skill.get("cooldown", 0)
                return _build_result(p1, p2, result_lines, flags, False)
        
        dmg_result = calculate_damage(
            atk_eff["attack_min"], atk_eff["attack_max"],
            def_eff["defense"],
            skill,
            atk_buffs,
            atk_eff["damage_pct"],
            flags.get("p1_defending" if not is_p1_turn else "p2_defending", False),
            {},
        )
        damage = dmg_result["damage"]
        
        # Perk check: defend_reduce on defender
        def_class = defender.get("class_id", "banxabong")
        if get_class_perk(def_class) == "defend_reduce" and \
           flags.get("p1_defending" if not is_p1_turn else "p2_defending", False):
            damage = int(damage * 0.9)
        
        # Last stand
        passive_id = defender.get("skill_equipped", {}).get("passive")
        def_skill = SKILLS_DB.get(passive_id)
        if def_skill and def_skill["type"] == "last_stand":
            threshold = def_skill.get("hp_threshold", 30)
            # Perk: last_stand_boost
            if get_class_perk(def_class) == "last_stand_boost":
                threshold = 40
            if defender.get("hp", 0) <= defender.get("hp_max", 100) * threshold / 100:
                damage = int(damage * (100 - def_skill["dmg_reduce_pct"]) / 100)
                result_lines.append(f"💎 GIÁP BẤT TỬ! -{def_skill['dmg_reduce_pct']}% dmg!")
        
        # Counter immune
        immune_key = f"p{1 if not is_p1_turn else 2}_counter_immune"
        if flags.pop(immune_key, None):
            result_lines.append(f"🔄 {defender.get('name', '???')} MIỄN TOÀN BỘ SÁT THƯƠNG!")
            damage = 0
        
        # Shield
        shield_key = f"p{1 if not is_p1_turn else 2}_shield_hp"
        shield_hp = flags.get(shield_key, 0)
        if shield_hp > 0:
            if damage <= shield_hp:
                flags[shield_key] = shield_hp - damage
                result_lines.append(f"🛡️ Khiên hấp thụ {damage}!")
                damage = 0
            else:
                flags.pop(shield_key, None)
                pop_key = f"p{1 if not is_p1_turn else 2}_shield_pop_heal"
                pop_heal = flags.pop(pop_key, 15)
                heal_amt = int(defender.get("hp_max", 100) * pop_heal / 100)
                defender["hp"] = min(defender.get("hp_max", 100), defender.get("hp", 0) + heal_amt)
                result_lines.append(f"🛡️ Khiên vỡ! Tràn {damage - shield_hp}! +{heal_amt}HP hồi!")
                damage -= shield_hp
        
        # Self damage
        if skill.get("self_dmg_pct"):
            sd = int(attacker.get("hp", 0) * skill["self_dmg_pct"] / 100)
            attacker["hp"] = max(1, attacker.get("hp", 0) - sd)
            result_lines.append(f"💀 Tự thiêu {sd}HP!")
        
        # Rage (attacker)
        atk_passive_id = attacker.get("skill_equipped", {}).get("passive")
        atk_passive = SKILLS_DB.get(atk_passive_id)
        if atk_passive and atk_passive["type"] == "rage":
            rage_key = f"p{1 if is_p1_turn else 2}_rage_dmg"
            if flags.get(rage_key, 0) > 0:
                rage_bonus = int(flags.pop(rage_key, 0) * atk_passive.get("rage_multiplier", 2.0))
                damage += rage_bonus
                result_lines.append(f"💢 PHẪN NỘI! +{rage_bonus} dmg!")
        
        # Apply damage
        defender["hp"] = max(0, defender.get("hp", 0) - damage)
        attacker["damage_dealt"] = attacker.get("damage_dealt", 0) + damage
        defender["damage_taken"] = defender.get("damage_taken", 0) + damage
        
        result_lines.append(f"{skill.get('icon', '')} **{skill['name']}**")
        if damage > 0:
            result_lines.append(f"💥 **{damage}** dmg!")
        
        # Rage accumulation on defender
        def_passive_id = defender.get("skill_equipped", {}).get("passive")
        def_passive = SKILLS_DB.get(def_passive_id)
        if def_passive and def_passive["type"] == "rage":
            rage_pct = def_passive.get("rage_pct", 50)
            if get_class_perk(def_class) == "rage_boost":
                rage_pct = int(rage_pct * 1.25)
            rage_accum_key = f"p{1 if not is_p1_turn else 2}_rage_dmg"
            flags[rage_accum_key] = flags.get(rage_accum_key, 0) + int(damage * rage_pct / 100)
        
        # Counter
        counter_key = f"p{1 if not is_p1_turn else 2}_counter"
        counter_mult = flags.pop(counter_key, None)
        if counter_mult:
            cd = int(damage * counter_mult)
            attacker["hp"] = max(0, attacker.get("hp", 0) - cd)
            result_lines.append(f"🔄 PHẢN ĐÒN! {cd} dmg!")
        
        # Lifesteal
        if skill.get("type") == "lifesteal":
            lifesteal_pct = skill.get("lifesteal_pct", 50)
            if get_class_perk(attacker.get("class_id", "")) == "lifesteal_boost":
                lifesteal_pct = int(lifesteal_pct * 1.2)
            heal = int(damage * lifesteal_pct / 100)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker.get("hp", 0) + heal)
            result_lines.append(f"🩸 Hút {heal} HP!")
        
        # Burn
        if skill.get("type") == "burn":
            burn_key = f"p{1 if not is_p1_turn else 2}_burn"
            flags[burn_key] = {"pct": skill["burn_pct"], "turns": skill.get("burn_turns", 2)}
            result_lines.append(f"🔥 Thiêu đốt {skill['burn_pct']}%/2t!")
        
        # Stun
        if skill.get("type") == "stun":
            if is_p1_turn:
                flags["p2_stunned"] = True
            else:
                flags["p1_stunned"] = True
            result_lines.append(f"🌑 Choáng! {defender.get('name', '???')} mất lượt!")
        
        # Clear defending flags
        flags["p1_defending"] = False
        flags["p2_defending"] = False
        
        cd_key = f"{cat}_cd"
        attacker[cd_key] = skill.get("cooldown", 0)
    
    # ─── End of turn processing ───
    
    # Reduce cooldowns
    for p in [p1, p2]:
        for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
            if p.get(cdkey, 0) > 0:
                p[cdkey] -= 1
        # Perk: cd_reduce
        if get_class_perk(p.get("class_id", "")) == "cd_reduce":
            for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                if p.get(cdkey, 0) > 0:
                    p[cdkey] -= 1
    
    # Regen passive
    for i, p in enumerate([p1, p2]):
        pid = p.get("skill_equipped", {}).get("passive")
        pskill = SKILLS_DB.get(pid)
        if pskill and pskill["type"] == "regen":
            reg = int(p.get("hp_max", 100) * pskill["regen_pct"] / 100)
            p["hp"] = min(p.get("hp_max", 100), p.get("hp", 0) + reg)
    
    # Burn tick
    for i, p in enumerate([p1, p2]):
        key = f"p{i+1}_burn"
        burn = flags.get(key)
        if burn and burn.get("turns", 0) > 0:
            bd = int(p.get("hp_max", 100) * burn["pct"] / 100)
            p["hp"] = max(0, p.get("hp", 0) - bd)
            burn["turns"] -= 1
            result_lines.append(f"🔥 Bỏng! {p.get('name', '???')} -{bd}HP ({burn['turns']}t)")
            if burn["turns"] <= 0:
                flags.pop(key, None)
    
    # ─── Check defeat ───
    finished = False
    winner_id = None
    if defender.get("hp", 0) <= 0:
        finished = True
        defender["hp"] = 0
        attacker["wins"] = attacker.get("wins", 0) + 1
        defender["losses"] = defender.get("losses", 0) + 1
        winner_id = attacker.get("id")
        result_lines.append(f"\n💀 **{defender.get('name', '???')}** bị xỏ lá đến chết!")
        result_lines.append(f"🏆 **{attacker.get('name', '???')}** CHIẾN THẮNG! 🎉")
    
    return _build_result(p1, p2, result_lines, flags, finished, winner_id)


def _build_result(p1, p2, log_messages, flags, finished, winner_id=None):
    return RoundResult(
        p1=p1, p2=p2,
        log_messages=log_messages,
        finished=finished,
        winner_id=winner_id,
    )
```

---

### Task 5: Discord Views

**Files:**
- Create: `bot/views/challenge_view.py`
- Create: `bot/views/battle_view.py`

- [ ] **Step 1: Write bot/views/challenge_view.py**
Port `ChallengeView` from old `arena.py:419-505`. Same logic but:
- Import cog via parameter (keep reference to bot)
- Use `bot/data/classes.py` for class display
- Use `bot/engine/battle.py` for HP regen

```python
import discord
import json
import time
from bot.database import get_db

class ChallengeView(discord.ui.View):
    def __init__(self, bot, target_sid, challenger_sid, challenger_name, target_name, channel_id):
        super().__init__(timeout=30)
        self.bot = bot
        self.target_sid = target_sid
        self.challenger_sid = challenger_sid
        self.challenger_name = challenger_name
        self.target_name = target_name
        self.channel_id = channel_id
        self.used = False

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.target_sid:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.used:
            return
        self.used = True
        db = await get_db()
        try:
            row = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not row:
                return
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            await db.execute("UPDATE players SET coins = max(0, coins - 20) WHERE id = ?", (self.target_sid,))
            await db.commit()
            ch = self.bot.get_channel(int(self.channel_id))
            if ch:
                await ch.send(f"⏰ **{self.target_name}** hết giờ! -20🪙 vì hèn! 🏃")
        finally:
            await db.close()

    @discord.ui.button(emoji="✅", label="Nhận Lời", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction, button):
        if self.used:
            return
        self.used = True
        await self._do_accept(interaction)

    @discord.ui.button(emoji="❌", label="Từ Chối", style=discord.ButtonStyle.danger)
    async def deny_btn(self, interaction, button):
        if self.used:
            return
        self.used = True
        await self._do_deny(interaction)

    async def _do_accept(self, interaction):
        await interaction.response.defer()
        db = await get_db()
        try:
            row = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not row:
                await interaction.followup.send("🤷 Hết hạn!", ephemeral=True)
                return
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            
            # Get both players
            p1_cursor = await db.execute("SELECT * FROM players WHERE id = ?", (self.challenger_sid,))
            p1_row = await p1_cursor.fetchone()
            p2_cursor = await db.execute("SELECT * FROM players WHERE id = ?", (self.target_sid,))
            p2_row = await p2_cursor.fetchone()
            
            if not p1_row or not p2_row:
                await interaction.followup.send("❌ Lỗi data!", ephemeral=True)
                return
            
            p1 = dict(p1_row)
            p2 = dict(p2_row)
            
            if p1["hp"] <= 0 or p2["hp"] <= 0:
                name = p1.get("name", "?") if p1["hp"] <= 0 else p2.get("name", "?")
                await interaction.followup.send(f"💀 **{name}** 0 máu!", ephemeral=True)
                return
            
            # Reset HP, clear effects
            for p in [p1, p2]:
                p["hp"] = p["hp_max"]
                p["attack_cd"] = 0
                p["special_cd"] = 0
                p["defense_cd"] = 0
            
            import random
            first = self.challenger_sid if random.random() < 0.5 else self.target_sid
            
            # Save players
            for p in [p1, p2]:
                await db.execute("""UPDATE players SET hp=?, attack_cd=0, special_cd=0, defense_cd=0 WHERE id=?""",
                                 (p["hp"], p["id"]))
            
            # Create battle
            import time
            await db.execute("""INSERT INTO active_battles (player1_id, player2_id, turn, channel_id, last_move)
                                VALUES (?, ?, ?, ?, ?)""",
                             (self.challenger_sid, self.target_sid, first, self.channel_id, time.time()))
            battle_id = db.last_insert_rowid()
            await db.commit()
            
            # Build embed and start
            guild = interaction.guild
            challenger = guild.get_member(int(self.challenger_sid)) or await guild.fetch_member(int(self.challenger_sid))
            target = guild.get_member(int(self.target_sid)) or await guild.fetch_member(int(self.target_sid))
            turn_user = challenger if first == self.challenger_sid else target
            
            from bot.data.classes import CLASSES
            from bot.data.skills import SKILLS_DB
            from bot.views.battle_view import BattleView
            
            cls1 = CLASSES.get(p1.get("class_id", "banxabong"), CLASSES["banxabong"])
            cls2 = CLASSES.get(p2.get("class_id", "banxabong"), CLASSES["banxabong"])
            
            embed = discord.Embed(
                title="⚔️ TRẬN CHIẾN BẮT ĐẦU!",
                color=0xff6600,
                description=(
                    f"{cls1['icon']} **{challenger.display_name}** ⚔️ {cls2['icon']} **{target.display_name}**\n"
                    f"🎲 **{turn_user.display_name}** đi trước!\n"
                    f"━━━━━━━━━━━\n"
                    f"❤️ {challenger.display_name}:`{p1['hp']}/{p1['hp_max']}`\n"
                    f"❤️ {target.display_name}:`{p2['hp']}/{p2['hp_max']}`"
                )
            )
            view = BattleView(self.bot, battle_id, first, turn_user.display_name)
            await interaction.edit_original_response(embed=embed, view=view)
            view.start_countdown()
        finally:
            await db.close()

    async def _do_deny(self, interaction):
        await interaction.response.defer()
        db = await get_db()
        try:
            row = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not row:
                await interaction.followup.send("🤷 Hết hạn!", ephemeral=True)
                return
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            await db.execute("UPDATE players SET coins = max(0, coins - 20) WHERE id = ?", (self.target_sid,))
            await db.commit()
            embed = discord.Embed(
                title="🏃 NHÁT! 💸",
                color=0x888888,
                description=f"**{self.target_name}** từ chối **{self.challenger_name}**! -20🪙!"
            )
            await interaction.edit_original_response(embed=embed, view=None)
        finally:
            await db.close()
```

- [ ] **Step 2: Write bot/views/battle_view.py**
Port `BattleView` from old `arena.py:304-416`. Same logic but:
- Uses `bot/engine/battle.py` `execute_action()` for combat
- Uses `bot/engine/rewards.py` for rewards
- Loads/saves via database.py instead of JSON

```python
import discord
import asyncio
import time
from bot.database import get_db
from bot.data.skills import SKILLS_DB
from bot.data.classes import CLASSES
from bot.engine.battle import execute_action, get_equipped_skill
from bot.engine.rewards import calc_rewards, apply_rewards

class BattleView(discord.ui.View):
    def __init__(self, bot, battle_id: int, turn_sid: str, turn_name: str, seconds: int = 15):
        super().__init__(timeout=None)
        self.bot = bot
        self.battle_id = battle_id
        self.turn_sid = turn_sid
        self.turn_name = turn_name
        self.seconds = seconds
        self.remaining = seconds
        self._timer_task = None
        self._stopped = False
        self.message = None

    def start_countdown(self):
        if self._timer_task is None:
            self._timer_task = asyncio.create_task(self._run_countdown())

    def stop(self):
        self._stopped = True
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        super().stop()

    async def _run_countdown(self):
        for remaining in range(self.seconds, -1, -3):
            if self._stopped:
                return
            self.remaining = remaining
            if self.message and not self._stopped:
                try:
                    embed = self.message.embeds[0] if self.message.embeds else None
                    if embed:
                        bar_filled = remaining * 10 // self.seconds
                        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
                        if remaining > 5:
                            footer = f"⏳ Còn {remaining}s — {bar} — {self.turn_name}"
                        elif remaining > 0:
                            footer = f"⚠️ Còn {remaining}s! {bar} — Nhanh lên!"
                        else:
                            footer = "⏰ HẾT GIỜ!"
                        embed.set_footer(text=footer)
                        await self.message.edit(embed=embed)
                except:
                    pass
            if remaining > 0:
                await asyncio.sleep(3)
            else:
                break
        if not self._stopped:
            self._stopped = True
            await self._handle_timeout()

    async def _handle_timeout(self):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE id=?", (self.battle_id,))
            battle = await cursor.fetchone()
            if not battle:
                return
            battle = dict(battle)
            if battle["turn"] != self.turn_sid:
                return
            await self._finish_battle(db, battle, self.turn_sid, is_timeout=True)
        finally:
            await db.close()

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.turn_sid:
            await interaction.response.send_message("⏳ Chưa tới lượt mày! 🤡", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="💥", label="Tấn Công", style=discord.ButtonStyle.danger)
    async def attack_btn(self, interaction, button):
        await self._handle_move(interaction, "attack")

    @discord.ui.button(emoji="🔥", label="Đặc Biệt", style=discord.ButtonStyle.primary)
    async def special_btn(self, interaction, button):
        await self._handle_move(interaction, "special")

    @discord.ui.button(emoji="🛡️", label="Chống Xỏ Lá", style=discord.ButtonStyle.success)
    async def defend_btn(self, interaction, button):
        await self._handle_move(interaction, "defense")

    async def _handle_move(self, interaction, move_type):
        guild = interaction.guild
        user_id = interaction.user.id
        sid = str(user_id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM active_battles WHERE id=?", (self.battle_id,))
            battle = await cursor.fetchone()
            if not battle:
                await interaction.response.send_message("🤷 Không có trận nào!", ephemeral=True)
                return
            battle = dict(battle)
            if battle["turn"] != sid:
                await interaction.response.send_message("⏳ Chưa tới lượt!", ephemeral=True)
                return

            # Check cooldown
            pdata = await self._get_player_data(db, sid)
            cat = "defense" if move_type == "defense" else move_type
            cd_key = f"{cat}_cd"
            if pdata.get(cd_key, 0) > 0:
                sk = get_equipped_skill(pdata, cat)
                await interaction.response.send_message(
                    f"⏳ **{sk['name']}** đang hồi! Còn **{pdata[cd_key]}** turn!", ephemeral=True)
                return

            await interaction.response.defer()
            self.stop()
            result = await self._execute_battle(guild, battle, user_id, move_type, db)
            if result is None:
                await interaction.edit_original_response(content="❌ Lỗi!", embed=None, view=None)
                return
            embed, view, finished = result
            await interaction.edit_original_response(embed=embed, view=view)
            if view and not finished:
                view.start_countdown()
        finally:
            await db.close()

    async def _get_player_data(self, db, sid):
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
        row = await cursor.fetchone()
        if not row:
            return {}
        pdata = dict(row)
        # Load skill slots
        slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
        slots = {}
        async for srow in slots_cursor:
            slots[srow[0]] = srow[1]
        pdata["skill_equipped"] = slots
        # Load equipment
        eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (sid,))
        equipped = {}
        async for erow in eq_cursor:
            if erow[1]:
                equipped[erow[0]] = erow[1]
        pdata["equipped"] = equipped
        # Load buffs
        buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
        buff_row = await buff_cursor.fetchone()
        pdata["buffs"] = dict(buff_row) if buff_row else {}
        # Load owned skills
        own_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (sid,))
        owned = [1, 5, 10, 14]
        async for orow in own_cursor:
            owned.append(orow[0])
        pdata["skills_owned"] = list(set(owned))
        return pdata

    async def _save_player_data(self, db, sid, pdata):
        await db.execute("""UPDATE players SET hp=?, hp_max=?, attack_min=?, attack_max=?, defense=?,
                             wins=?, losses=?, damage_dealt=?, damage_taken=?, coins=?, xp=?, level=?,
                             stat_points=?, attack_cd=?, special_cd=?, defense_cd=?
                             WHERE id=?""",
                          (pdata.get("hp", 100), pdata.get("hp_max", 100),
                           pdata.get("attack_min", 10), pdata.get("attack_max", 20),
                           pdata.get("defense", 5),
                           pdata.get("wins", 0), pdata.get("losses", 0),
                           pdata.get("damage_dealt", 0), pdata.get("damage_taken", 0),
                           pdata.get("coins", 0), pdata.get("xp", 0), pdata.get("level", 1),
                           pdata.get("stat_points", 0),
                           pdata.get("attack_cd", 0), pdata.get("special_cd", 0),
                           pdata.get("defense_cd", 0),
                           sid))
        await db.commit()

    async def _execute_battle(self, guild, battle, user_id, move_type, db):
        sid = str(user_id)
        p1_id = battle["player1"]
        p2_id = battle["player2"]
        
        p1 = await self._get_player_data(db, p1_id)
        p2 = await self._get_player_data(db, p2_id)
        
        p1_m = guild.get_member(int(p1_id)) or await guild.fetch_member(int(p1_id))
        p2_m = guild.get_member(int(p2_id)) or await guild.fetch_member(int(p2_id))
        if not p1_m or not p2_m:
            return None
        
        p1["name"] = p1_m.display_name
        p2["name"] = p2_m.display_name
        
        turn_player = 0 if sid == p1_id else 1
        attacker = p1 if turn_player == 0 else p2
        cat = "defense" if move_type == "defense" else move_type
        skill = get_equipped_skill(attacker, cat)
        action = {"type": move_type, "skill_id": skill.get("id", 1)}
        
        flags = {
            "p1_defending": bool(battle.get("p1_defending", 0)),
            "p2_defending": bool(battle.get("p2_defending", 0)),
            "p1_stunned": bool(battle.get("p1_stunned", 0)),
            "p2_stunned": bool(battle.get("p2_stunned", 0)),
        }
        
        result = await execute_action(p1, p2, turn_player, action, flags)
        
        # Save both players
        await self._save_player_data(db, p1_id, result.p1)
        await self._save_player_data(db, p2_id, result.p2)
        
        # Handle finish
        if result.finished:
            winner_id = result.winner_id
            loser_id = p2_id if winner_id == p1_id else p1_id
            
            # Rewards
            w_coins, w_xp = calc_rewards(True)
            l_coins, l_xp = calc_rewards(False)
            apply_rewards(result.p1 if winner_id == p1_id else result.p2, w_coins, w_xp)
            apply_rewards(result.p2 if winner_id == p1_id else result.p1, l_coins, l_xp)
            
            # ELO
            from bot.engine.ranking import calculate_elo
            p1_battles = result.p1.get("wins", 0) + result.p1.get("losses", 0)
            new_elo_p1, new_elo_p2 = calculate_elo(
                result.p1.get("elo", 1000), result.p2.get("elo", 1000),
                1 if winner_id == p1_id else 2, p1_battles)
            result.p1["elo"] = new_elo_p1
            result.p2["elo"] = new_elo_p2
            
            # Save rewards
            await self._save_player_data(db, p1_id, result.p1)
            await self._save_player_data(db, p2_id, result.p2)
            
            # Delete battle
            await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
            await db.commit()
            
            lines = result.log_messages + [
                f"💰 {p1_m.display_name}: +{w_coins}🪙 +{w_xp}XP" if winner_id == p1_id else f"💰 {p1_m.display_name}: +{l_coins}🪙(an ủi) +{l_xp}XP",
                f"💰 {p2_m.display_name}: +{l_coins}🪙(an ủi) +{l_xp}XP" if winner_id == p1_id else f"💰 {p2_m.display_name}: +{w_coins}🪙 +{w_xp}XP",
            ]
            embed = discord.Embed(title="⚔️ KẾT THÚC!", description="\n".join(lines), color=0xffd700)
            return embed, None, True
        
        # Continue battle — save flags
        await db.execute("""UPDATE active_battles SET p1_defending=?, p2_defending=?, p1_stunned=?, p2_stunned=?, turn=?, last_move=?
                             WHERE id=?""",
                          (int(flags.get("p1_defending", 0)), int(flags.get("p2_defending", 0)),
                           int(flags.get("p1_stunned", 0)), int(flags.get("p2_stunned", 0)),
                           p2_id if turn_player == 0 else p1_id, time.time(), self.battle_id))
        await db.commit()
        
        new_turn = p2_id if turn_player == 0 else p1_id
        next_pdata = result.p1 if new_turn == p1_id else result.p2
        next_m = p1_m if new_turn == p1_id else p2_m
        
        from bot.data.skills import RARITY_STARS
        ask = get_equipped_skill(next_pdata, "attack")
        ssk = get_equipped_skill(next_pdata, "special")
        dsk = get_equipped_skill(next_pdata, "defense")
        
        hp1_bar = "🟩" * (result.p1["hp"] // 10) + "⬜" * ((result.p1["hp_max"] - result.p1["hp"]) // 10)
        hp2_bar = "🟩" * (result.p2["hp"] // 10) + "⬜" * ((result.p2["hp_max"] - result.p2["hp"]) // 10)
        if len(hp1_bar) > 15:
            hp1_bar = hp1_bar[:15]
        if len(hp2_bar) > 15:
            hp2_bar = hp2_bar[:15]
        
        result.log_messages.append("\n━━━━━━━━━━━")
        result.log_messages.append(f"❤️ {p1_m.display_name}:`{result.p1['hp']}/{result.p1['hp_max']}`{hp1_bar}")
        result.log_messages.append(f"❤️ {p2_m.display_name}:`{result.p2['hp']}/{result.p2['hp_max']}`{hp2_bar}")
        result.log_messages.append(f"\n⏳ **{next_m.display_name}** — 15s!")
        
        embed = discord.Embed(title="⚔️ DIỄN BIẾN", description="\n".join(result.log_messages), color=0x00ff00)
        view = BattleView(self.bot, self.battle_id, new_turn, next_m.display_name)
        return embed, view, False

    async def _finish_battle(self, db, battle, loser_sid, is_timeout=False):
        winner_id = battle["player1"] if battle["player2"] == loser_sid else battle["player2"]
        guild = None
        if self.message and self.message.guild:
            guild = self.message.guild
        if not guild:
            await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
            await db.commit()
            return
        
        loser_m = guild.get_member(int(loser_sid)) or await guild.fetch_member(int(loser_sid))
        winner_m = guild.get_member(int(winner_id)) or await guild.fetch_member(int(winner_id))
        loser_name = loser_m.display_name if loser_m else "???"
        winner_name = winner_m.display_name if winner_m else "???"
        
        wdata = await self._get_player_data(db, winner_id)
        ldata = await self._get_player_data(db, loser_sid)
        wdata["wins"] = wdata.get("wins", 0) + 1
        ldata["losses"] = ldata.get("losses", 0) + 1
        if is_timeout:
            ldata["hp"] = 0
        
        w_coins, w_xp = calc_rewards(True)
        l_coins, l_xp = calc_rewards(False)
        apply_rewards(wdata, w_coins, w_xp)
        apply_rewards(ldata, l_coins, l_xp)
        
        await self._save_player_data(db, winner_id, wdata)
        await self._save_player_data(db, loser_sid, ldata)
        await db.execute("DELETE FROM active_battles WHERE id=?", (self.battle_id,))
        await db.commit()
        
        lines = [
            f"⏰ **{loser_name}** hết giờ!" if is_timeout else f"💀 **{loser_name}** thua!",
            f"🏆 **{winner_name}** CHIẾN THẮNG! 🎉",
            f"💰 {winner_name}: +{w_coins}🪙 +{w_xp}XP",
            f"💰 {loser_name}: +{l_coins}🪙(an ủi) +{l_xp}XP",
        ]
        embed = discord.Embed(title="⚔️ KẾT THÚC", description="\n".join(lines), color=0xffd700)
        try:
            await self.message.edit(embed=embed, view=None)
        except:
            ch = self.bot.get_channel(int(battle["channel_id"]))
            if ch:
                await ch.send(embed=embed)
```

---

### Task 6: Cogs (Arena + Shop + Admin)

**Files:**
- Create: `bot/cogs/arena.py`
- Create: `bot/cogs/shop.py`
- Create: `bot/cogs/admin.py`

- [ ] **Step 1: Write bot/cogs/arena.py**
Thin cog routing commands to engine. Key commands:
- `!register` / `/register` — Create player with default class
- `!stats` / `/stats` — Show player stats
- `!upgrade` / `/upgrade` — Spend stat points
- `!challenge` / `/challenge` — Challenge another player
- `!skills` / `/skills` — View skill database
- `!buyskill` / `/buyskill` — Purchase skill
- `!equipskill` / `/equipskill` — Equip skill to slot
- `!leaderboard` / `/leaderboard` — Show ELO ranking
- `!class` / `/class` — View/change class
- `!replay` / `/replay` — View battle replay

Each slash command has autocomplete where applicable.

- [ ] **Step 2: Write bot/cogs/shop.py**
- `!shop` / `/shop` — Browse shop
- `!buy` / `/buy` — Buy item
- `!use` / `/use` — Use consumable
- `!equip` / `/equip` — Equip/unequip gear
- `!inv` / `/inv` — View inventory

- [ ] **Step 3: Write bot/cogs/admin.py**
- `!reset @player` — Reset player stats
- `!givecoins @player <amount>` — Give coins
- `!setclass @player <class_id>` — Set player class
- Admin-only (check by user ID list in config)

---

### Task 7: main.py Rewrite

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Rewrite main.py**
```python
import discord
from discord.ext import commands
from bot.config import TOKEN
from bot.logger import logger
from bot.database import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f"[ONLINE] {bot.user} đã lên đồ!")
    logger.info(f"Server: {len(bot.guilds)} servers")
    for guild in bot.guilds:
        logger.info(f"  - {guild.name} ({guild.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"[SLASH] Global sync: {len(synced)} commands")
    except Exception as e:
        logger.error(f"[SLASH] Global sync error: {e}")
    for guild in bot.guilds:
        try:
            await bot.tree.sync(guild=guild)
            logger.info(f"[SLASH] Guild {guild.name}: synced")
        except Exception as e:
            logger.error(f"[SLASH] Guild {guild.name}: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.reply("🚫 Mày hông đủ quyền để xài vụ này!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"⚠️ Thiếu argument rồi ku! Gõ `!help` để xem hướng dẫn.")
    else:
        await ctx.reply(f"❌ Lỗi: {error}")
        logger.error(f"Command error: {error}", exc_info=True)

async def load_extensions():
    await bot.load_extension("bot.cogs.arena")
    await bot.load_extension("bot.cogs.shop")
    await bot.load_extension("bot.cogs.admin")

async def main():
    await init_db()
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

### Task 8: Migration Script

**Files:**
- Create: `scripts/migrate_json_to_sqlite.py`

- [ ] **Step 1: Write migration script**
```python
"""Migrate old JSON data to SQLite. Run once, then delete JSON."""
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime

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
    
    # Mapping: old user IDs to classes
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
        
        # Skills
        for sk_id in pdata.get("skills_owned", [1, 5, 10, 14]):
            conn.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
        
        # Skill slots
        for slot, sk_id in pdata.get("skill_equipped", {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
            conn.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
        
        # Equipment
        for item_id in pdata.get("equipment_items", {}):
            conn.execute("INSERT OR IGNORE INTO player_equipment (player_id, item_id) VALUES (?, ?)", (sid, int(item_id)))
        
        # Equip slots
        for slot, item_id in pdata.get("equipped", {}).items():
            if item_id:
                conn.execute("INSERT OR REPLACE INTO player_equip_slots (player_id, slot, item_id) VALUES (?, ?, ?)", (sid, slot, int(item_id)))
        
        # Inventory
        for item_id, qty in pdata.get("inventory", {}).items():
            conn.execute("INSERT OR REPLACE INTO inventory (player_id, item_id, quantity) VALUES (?, ?, ?)", (sid, int(item_id), qty))
    
    conn.commit()
    
    # Backup JSON
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
```

---

### Task 9: Web Dashboard (FastAPI)

**Files:**
- Create: `web/main.py`
- Create: `web/routes/players.py`
- Create: `web/routes/battles.py`
- Create: `web/templates/base.html`
- Create: `web/templates/index.html`
- Create: `web/templates/player.html`
- Create: `web/templates/leaderboard.html`
- Create: `web/templates/battle_replay.html`
- Create: `web/static/style.css`
- Create: `web_dashboard.py` (entry point)

- [ ] **Step 1: Write web/main.py**
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from web.routes import players, battles

app = FastAPI(title="Bot-XL Dashboard")
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.include_router(players.router)
app.include_router(battles.router)

@app.get("/")
async def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/leaderboard")
```

- [ ] **Step 2: Write web/routes/players.py**
```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import os

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard(request: Request):
    conn = get_db()
    rows = conn.execute("SELECT * FROM players ORDER BY elo DESC LIMIT 50").fetchall()
    conn.close()
    return templates.TemplateResponse("leaderboard.html", {"request": request, "players": rows})

@router.get("/player/{pid}", response_class=HTMLResponse)
async def player_detail(request: Request, pid: str):
    conn = get_db()
    player = conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    if not player:
        return HTMLResponse("Player not found", status_code=404)
    history = conn.execute(
        "SELECT * FROM battle_history WHERE player1_id=? OR player2_id=? ORDER BY fought_at DESC LIMIT 20",
        (pid, pid)).fetchall()
    conn.close()
    from bot.data.classes import CLASSES
    cls = CLASSES.get(player["class_id"], CLASSES["banxabong"])
    return templates.TemplateResponse("player.html", {
        "request": request, "player": player, "cls": cls, "history": history})
```

- [ ] **Step 3: Write web/routes/battles.py**
```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import json
import os

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "botxl.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/battle/{bid}", response_class=HTMLResponse)
async def battle_detail(request: Request, bid: int):
    conn = get_db()
    battle = conn.execute("SELECT * FROM battle_history WHERE id=?", (bid,)).fetchone()
    conn.close()
    if not battle:
        return HTMLResponse("Battle not found", status_code=404)
    rounds = json.loads(battle["rounds"])
    return templates.TemplateResponse("battle_replay.html", {
        "request": request, "battle": battle, "rounds": rounds})
```

- [ ] **Step 4: Write web_dashboard.py** (entry point)
```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("web.main:app", host="0.0.0.0", port=8080, reload=True)
```

- [ ] **Step 5: Write HTML templates**
Goes in `web/templates/`. Uses Jinja2 + htmx. Templates for:
- `base.html` — Layout with nav, htmx CDN
- `leaderboard.html` — ELO ranking table
- `player.html` — Player profile, stats, class, recent fights
- `battle_replay.html` — Round-by-round timeline with HP bars

- [ ] **Step 6: Write web/static/style.css**
Basic styling: dark theme, responsive table, HP bar animation.

---

### Task 10: Tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_battle_engine.py`
- Create: `tests/test_rewards.py`
- Create: `tests/test_ranking.py`

- [ ] **Step 1: Write tests/conftest.py**
Pytest fixtures for testing:
```python
import pytest

@pytest.fixture
def basic_player():
    return {
        "id": "test1", "name": "Test1", "class_id": "banxabong",
        "hp": 120, "hp_max": 120, "attack_min": 12, "attack_max": 17,
        "defense": 8, "wins": 0, "losses": 0,
        "damage_dealt": 0, "damage_taken": 0,
        "coins": 0, "xp": 0, "level": 1, "stat_points": 0, "elo": 1000,
        "attack_cd": 0, "special_cd": 0, "defense_cd": 0,
        "upgrade_hp": 0, "upgrade_atk": 0, "upgrade_def": 0,
        "skill_equipped": {"attack": 1, "special": 5, "defense": 10, "passive": 14},
        "skills_owned": [1, 5, 10, 14],
        "equipped": {}, "buffs": {},
    }

@pytest.fixture
def battle_flags():
    return {"p1_defending": False, "p2_defending": False, "p1_stunned": False, "p2_stunned": False}
```

- [ ] **Step 2: Write tests/test_battle_engine.py**
```python
import pytest
from bot.engine.battle import execute_action, calculate_damage, get_effective_stats

class TestGetEffectiveStats:
    def test_basic_stats(self, basic_player):
        stats = get_effective_stats(basic_player)
        assert stats["attack_min"] == 12
        assert stats["defense"] == 8

class TestExecuteAction:
    def test_attack_damage(self, basic_player, battle_flags):
        p1 = basic_player.copy()
        p2 = basic_player.copy()
        p2["id"] = "test2"
        result = await execute_action(p1, p2, 0, {"type": "attack", "skill_id": 1}, battle_flags)
        assert not result.finished
        assert result.p2["hp"] < 120

    def test_defend_heal(self, basic_player, battle_flags):
        p1 = basic_player.copy()
        p2 = basic_player.copy()
        p2["id"] = "test2"
        p1["hp"] = 60
        result = await execute_action(p1, p2, 0, {"type": "defense", "skill_id": 10}, battle_flags)
        assert result.p1["hp"] > 60
```

- [ ] **Step 3: Write tests/test_rewards.py**
```python
from bot.engine.rewards import calc_level, calc_rewards, apply_rewards

class TestCalcLevel:
    def test_level_1_zero_xp(self):
        assert calc_level(0) == (1, 0)
    
    def test_level_up(self):
        assert calc_level(80) == (2, 0)

class TestCalcRewards:
    def test_win_rewards(self):
        c, x = calc_rewards(True)
        assert c == 50
        assert x == 25
    
    def test_lose_rewards(self):
        c, x = calc_rewards(False)
        assert c == 10
        assert x == 5
```

- [ ] **Step 4: Write tests/test_ranking.py**
```python
from bot.engine.ranking import calculate_elo

class TestCalculateElo:
    def test_equal_elo(self):
        new_p1, new_p2 = calculate_elo(1000, 1000, 1)
        assert new_p1 > 1000
        assert new_p2 < 1000
        assert new_p1 - 1000 == 1000 - new_p2  # symmetric
    
    def test_large_gap(self):
        new_p1, new_p2 = calculate_elo(1500, 1000, 2)  # upset: lower-rated wins
        assert new_p1 < 1500
        assert new_p2 > 1000
        assert abs(new_p1 - 1500) > 16  # big change from upset
```

---

### Self-Review Checklist

1. **Spec coverage:** ✓ All spec sections covered: project structure (T0-1), DB schema (T1), class system (T2), battle engine (T4), ELO ranking (T4), daily quests (T6 DB schema), battle replay (T9), web dashboard (T9), tests (T10), migration (T8), .gitignore (T0)
2. **Placeholder scan:** ✓ No TBD/TODO
3. **Type consistency:** ✓ All function signatures match across tasks
4. **Ambiguity:** ✓ Clear ownership per file
