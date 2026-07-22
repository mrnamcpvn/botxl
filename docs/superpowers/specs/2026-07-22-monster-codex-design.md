# Monster Codex / Đồ Thư Quái Vật — Design Spec

## Overview

Track kills per NPC type. Each NPC has 4 milestones (100/500/1K/10K kills) granting permanent % bonus when fighting that specific NPC. Bonus applies to base stats + equipment, after artifact multiplier.

**Scope:** new cog `bot/cogs/monster_codex.py` + DB table + battle engine integration.

---

## 1. Codex Bonuses

| # | NPC | Lv | Bonus | 100 | 500 | 1K | 10K |
|---|-----|----|-------|-----|-----|-----|-----|
| 1 | 🐀 Chuột Cống | 1 | 💰 Coin | +8% | +16% | +24% | +40% |
| 2 | 🐍 Rắn Học Trò | 3 | 📖 XP | +8% | +16% | +24% | +40% |
| 3 | 🦎 Kỳ Đà Cản Mũi | 5 | 🛡️ DEF | +6% | +12% | +18% | +30% |
| 4 | 🐊 Cá Sấu Nước Đục | 8 | 🔱 PIERCE | +5% | +10% | +15% | +25% |
| 5 | 🐉 Rồng Tem Bảo Hành | 12 | ❤️ HP | +5% | +10% | +15% | +25% |
| 6 | 🦅 Đại Bàng Xỏ Lá | 15 | 💨 SPD | +5% | +10% | +15% | +25% |
| 7 | 💀 Tử Thần Bóng Tối | 18 | ⚔️ DMG | +5% | +10% | +15% | +22% |
| 8 | 👹 Diêm Vương Địa Ngục | 21 | 💥 CRIT | +4% | +8% | +12% | +18% |
| 9 | 🐉 Hắc Long Hủy Diệt | 24 | ⚔️ DMG | +6% | +12% | +18% | +28% |
| 10 | ⚡ Lôi Thần Sấm Sét | 27 | 💨 SPD | +5% | +10% | +15% | +22% |
| 11 | 🧊 Băng Thần Vĩnh Cửu | 30 | 🛡️ DEF | +7% | +14% | +20% | +32% |
| 12 | 🔥 Phượng Hoàng Lửa Thiêng | 33 | 💥 CRIT | +5% | +10% | +15% | +22% |
| 13 | 🌌 Chúa Tể Hư Không | 36 | 🔱 PIERCE | +6% | +12% | +18% | +28% |
| 14 | 👑 Vua Quỷ Tận Thế | 39 | 👑 ALL | +3% | +6% | +9% | +15% |
| 15 | 🐲 Hắc Kỳ Lân | 42 | 🎁 Drop | +4% | +8% | +12% | +18% |
| 16 | 🦅 Phong Thần Ưng | 45 | 💨 SPD | +6% | +12% | +18% | +28% |
| 17 | 🐢 Huyền Vũ Thần Quy | 48 | ❤️ HP | +8% | +15% | +22% | +32% |
| 18 | 🦊 Cửu Vĩ Hồ Ly | 51 | 📖 XP | +10% | +18% | +26% | +42% |
| 19 | 🐅 Bạch Hổ Thần Thú | 54 | ⚔️ DMG | +7% | +14% | +20% | +32% |
| 20 | 🐉 Thanh Long Thần Thú | 57 | ❤️ HP | +9% | +16% | +24% | +36% |
| 21 | 🐦 Chu Tước Thần Điểu | 60 | 💥 CRIT | +6% | +12% | +18% | +28% |
| 22 | 👹 A Tu La Chiến Thần | 63 | ⚔️ DMG | +8% | +15% | +22% | +32% |
| 23 | 🧘 Thái Thượng Lão Quân | 66 | 📖 XP | +12% | +20% | +30% | +45% |
| 24 | ⚡ Lôi Công Chấn Thiên | 69 | 💥 CRIT | +7% | +14% | +20% | +30% |
| 25 | 🌊 Cộng Công Thủy Thần | 72 | 🛡️ DEF | +8% | +15% | +22% | +32% |
| 26 | 🔥 Chúc Dung Hỏa Thần | 75 | ⚔️ DMG | +9% | +16% | +24% | +36% |
| 27 | ☀️ Hậu Nghệ Xạ Nhật | 78 | 🔱 PIERCE | +8% | +15% | +22% | +32% |
| 28 | 🌙 Hằng Nga Tiên Tử | 81 | 👑 ALL | +4% | +8% | +12% | +20% |
| 29 | ⚔️ Nhị Lang Thần | 85 | 👑 ALL | +5% | +10% | +15% | +24% |
| 30 | 👑 Ngọc Hoàng Đại Đế | 90 | 👑 ALL | +6% | +12% | +18% | +28% |

Bonus types & multiplier targets:

| Type | Applies to | Coin | XP | Drop |
|------|-----------|------|-----|------|
| 💰 Coin | coin reward when killing this NPC | ✓ | | |
| 📖 XP | XP reward when killing this NPC | | ✓ | |
| ⚔️ DMG | damage dealt to this NPC | | | |
| 🛡️ DEF | defense when fighting this NPC | | | |
| ❤️ HP | max HP when fighting this NPC | | | |
| 💨 SPD | speed when fighting this NPC | | | |
| 💥 CRIT | crit rate when fighting this NPC | | | |
| 🔱 PIERCE | pierce when fighting this NPC | | | |
| 🎁 Drop | drop rate when killing this NPC | | | ✓ |
| 👑 ALL | all combat stats vs this NPC | | | |

---

## 2. Database

```sql
CREATE TABLE monster_codex (
    player_id TEXT NOT NULL,
    npc_id INTEGER NOT NULL,
    kills INTEGER DEFAULT 0,
    PRIMARY KEY (player_id, npc_id)
);
```

---

## 3. Battle Engine Integration

In `get_effective_stats()`, after artifact multiplier, check codex bonus for the current NPC:

```python
if pdata.get("_codex_npc_id"):
    codex_bonus = get_codex_bonus(pdata["_codex_npc_id"], pdata.get("_codex_kills", 0))
    if codex_bonus:
        mult = 1 + codex_bonus / 100
        for stat in codex_bonus_stats:
            stat *= mult
```

Coin/XP/Drop bonuses are applied in the rewards phase, not in `get_effective_stats()`.

---

## 4. Config

```python
CODEX_MILESTONES = [100, 500, 1000, 10000]

CODEX_DATA = {
    1:  {"bonus": "coin",   "tiers": [8, 16, 24, 40]},
    2:  {"bonus": "xp",     "tiers": [8, 16, 24, 40]},
    3:  {"bonus": "def",    "tiers": [6, 12, 18, 30]},
    4:  {"bonus": "pierce", "tiers": [5, 10, 15, 25]},
    5:  {"bonus": "hp",     "tiers": [5, 10, 15, 25]},
    6:  {"bonus": "spd",    "tiers": [5, 10, 15, 25]},
    7:  {"bonus": "dmg",    "tiers": [5, 10, 15, 22]},
    8:  {"bonus": "crit",   "tiers": [4, 8, 12, 18]},
    9:  {"bonus": "dmg",    "tiers": [6, 12, 18, 28]},
    10: {"bonus": "spd",    "tiers": [5, 10, 15, 22]},
    11: {"bonus": "def",    "tiers": [7, 14, 20, 32]},
    12: {"bonus": "crit",   "tiers": [5, 10, 15, 22]},
    13: {"bonus": "pierce", "tiers": [6, 12, 18, 28]},
    14: {"bonus": "all",    "tiers": [3, 6, 9, 15]},
    15: {"bonus": "drop",   "tiers": [4, 8, 12, 18]},
    16: {"bonus": "spd",    "tiers": [6, 12, 18, 28]},
    17: {"bonus": "hp",     "tiers": [8, 15, 22, 32]},
    18: {"bonus": "xp",     "tiers": [10, 18, 26, 42]},
    19: {"bonus": "dmg",    "tiers": [7, 14, 20, 32]},
    20: {"bonus": "hp",     "tiers": [9, 16, 24, 36]},
    21: {"bonus": "crit",   "tiers": [6, 12, 18, 28]},
    22: {"bonus": "dmg",    "tiers": [8, 15, 22, 32]},
    23: {"bonus": "xp",     "tiers": [12, 20, 30, 45]},
    24: {"bonus": "crit",   "tiers": [7, 14, 20, 30]},
    25: {"bonus": "def",    "tiers": [8, 15, 22, 32]},
    26: {"bonus": "dmg",    "tiers": [9, 16, 24, 36]},
    27: {"bonus": "pierce", "tiers": [8, 15, 22, 32]},
    28: {"bonus": "all",    "tiers": [4, 8, 12, 20]},
    29: {"bonus": "all",    "tiers": [5, 10, 15, 24]},
    30: {"bonus": "all",    "tiers": [6, 12, 18, 28]},
}
```

---

## 5. Commands

| Command | Description |
|---------|-------------|
| `!codex` | Xem toàn bộ đồ thư — kill count + bonus đã unlock |
| `!codex <số>` | Xem chi tiết 1 NPC |

---

## 6. Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add CODEX_MILESTONES + CODEX_DATA |
| `bot/database.py` | Modify — add monster_codex table |
| `bot/engine/battle.py` | Modify — apply codex bonus in get_effective_stats |
| `bot/engine/rewards.py` | Modify — apply coin/xp/drop codex bonus |
| `bot/cogs/npc.py` | Modify — increment codex kills on NPC kill |
| `bot/cogs/monster_codex.py` | Create — !codex command |
| `main.py` | Modify — load monster_codex cog |
