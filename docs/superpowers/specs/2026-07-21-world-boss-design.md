# Boss Thế Giới — Design Spec

## Overview

Daily world boss event at 11h, 15h, 20h. Players register within 5 minutes, then all fight the boss simultaneously using the existing PvP skill system. Boss attacks 1 random player per turn. When a player dies, 15s respawn delay. Top damage dealers get rewards.

**Scope:** new cog `bot/cogs/world_boss.py` + DB tables + config.

---

## 1. Flow

```
⏰ 11h / 15h / 20h
        │
        ▼
🟢 REGISTERING (5 phút)
   └─ Embed + "⚔️ Tham Gia" button + countdown
        │
        ▼
🔴 FIGHTING
   Boss spawn với HP scaled theo số người + level
   Mỗi player: BattleView 3 nút (Attack/Special/Defense)
   Boss: 1 attack/round vào 1 player random
   Player chết → 15s cooldown → full HP hồi sinh → đánh tiếp
        │
        ▼
💀 BOSS DIES → REWARDING
   Damage ranking → top N nhận thưởng
```

---

## 2. Boss Stats

```python
boss_level = max(player_levels) + 30

# Dùng class "Trùm Cuối" làm base, scale theo level
boss_hp = trung_bình_dmg × số_player × số_lượt_10_phút
        ≈ 80 × n × 200
        ≈ 16000 × n

# ATK đủ mạnh để 2-3 hit hạ player trung bình
boss_atk_min = boss_level * 5
boss_atk_max = boss_level * 8
boss_def = boss_level * 3

boss_crit = 5%
boss_pierce = 10%
```

Boss KHÔNG bị stun. Burn hoạt động bình thường. Boss KHÔNG có wife, passive, buff.

---

## 3. Battle Mechanic

- Mỗi player tự click Attack/Special/Defense, không giới hạn thời gian
- Sau mỗi action của player → `execute_action(player, boss)` → damage boss
- Sau mỗi player action → boss phản công 1 player random
- Boss có `_npc_override=True` để bypass stat scaling
- Cooldown skill: giảm 1 sau mỗi lượt của player đó (không phải lượt boss)
- Khi boss chết → gửi embed tổng kết

### Player death:
```
if player_hp <= 0:
    player.hp = 0
    death_cooldown_until = now + 15s
    total_deaths += 1
    nút chuyển thành "⏳ Hồi sinh 15s..."
    Không thể bấm nút
Sau 15s → full HP → nút hoạt động lại
```

---

## 4. Rewards

| Rank | Trang bị | Đá | EXP | Coin |
|------|----------|-----|-----|------|
| 🥇 #1 | ★★★★ x1 | Cao cấp 5-8 | 600 | 800-1000 |
| 🥈 #2 | ★★★ x2 | Trung cấp 3-5 | 450 | 600-800 |
| 🥉 #3 | ★★★ x1 | Sơ cấp 5-10 | 300 | 400-600 |
| #4-5 | — | — | 150-240 | 300-500 |
| #6-10 | — | — | 60-120 | 200-300 |
| #11+ | — | — | 30 | 100-200 |

---

## 5. UI

### Registration Embed
```
🐉 BOSS THẾ GIỚI XUẤT HIỆN!
─────────────────────────
⏳ Đăng ký kết thúc sau: {countdown}s

👥 Đã đăng ký ({count}):
  • @Player1
  • @Player2

[⚔️ Tham Gia] [❌ Rời]
─────────────────────────
ID: #{boss_id} | Đánh lúc: {time}
```

### Fighting Embed (live update)
```
🐉 BOSS THẾ GIỚI #{id} — LIVE
━━━━━━━━━━━━━━━━━━━━
Level: {level}
❤️ HP: {current}/{max} 🟩🟩🟩🟩🟩🟨⬜⬜⬜⬜ ({pct}%)

🏆 BẢNG XẾP HẠNG SÁT THƯƠNG:
🥇 @Player1 — {dmg} dmg (💀x{deaths})
🥈 @Player2 — {dmg} dmg (💀x{deaths})
...
```

Mỗi player có **BattleView riêng** (3 nút như PvP), gửi qua ephemeral message.

### Podium Embed
```
💀 BOSS THẾ GIỚI #{id} ĐÃ BỊ HẠ!
━━━━━━━━━━━━━━━━━━━━
Tổng thời gian: X phút Y giây

🥇 @Player1 — {dmg} dmg
  • +900🪙 · +600XP · +6 Đá Cao Cấp · ★★★★ Huyết Kiếm

🥈 @Player2 — {dmg} dmg
  • +700🪙 · +450XP · +4 Đá Trung Cấp · ★★★ Giáp Sắt x2

...

👥 {total} người tham gia
```

---

## 6. Database

```sql
CREATE TABLE world_boss (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'registering',
    channel_id TEXT NOT NULL,
    boss_level INTEGER NOT NULL,
    boss_hp INTEGER NOT NULL,
    boss_hp_max INTEGER NOT NULL,
    boss_atk_min INTEGER NOT NULL,
    boss_atk_max INTEGER NOT NULL,
    boss_def INTEGER NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    created_at TEXT DEFAULT (datetime('now','+7 hours'))
);

CREATE TABLE world_boss_participants (
    boss_id INTEGER REFERENCES world_boss(id),
    player_id TEXT NOT NULL,
    total_damage INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    death_cooldown_until REAL DEFAULT 0,
    final_rank INTEGER DEFAULT 0,
    reward_given INTEGER DEFAULT 0,
    PRIMARY KEY (boss_id, player_id)
);
```

---

## 7. Config

```python
WORLD_BOSS_HOURS = [11, 15, 20]
WORLD_BOSS_REGISTER_TIME = 300
WORLD_BOSS_RESPAWN_DELAY = 15
WORLD_BOSS_CHANNEL_ID = 1529021378416738384
```

---

## 8. Files

| File | Action |
|------|--------|
| `bot/cogs/world_boss.py` | **New** — main cog |
| `bot/config.py` | **Modify** — add world boss config |
| `bot/database.py` | **Modify** — add world boss tables |
| `main.py` | **Modify** — load world_boss cog |

---

## 9. Edge Cases

- **Boss fight kéo dài qua giờ tiếp theo**: Không ảnh hưởng — chỉ check `_current_status is None` trước khi spawn boss mới
- **No player registers**: Hủy sau 5 phút, không spawn boss
- **1 player**: Vẫn đánh, nhận thưởng #1
- **Bot restart mid-fight**: Resume từ DB (status='fighting')
- **Player thoát game/disconnect**: Vẫn trong fight, damage = 0 từ lúc thoát
