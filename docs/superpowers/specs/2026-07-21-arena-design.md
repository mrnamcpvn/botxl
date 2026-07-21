# Đấu Trường Sinh Tử — Design Spec

## Overview

Automated tournament arena for the Discord bot. Players click **Join** to enter a bracket-based elimination tournament. All battles are **full-auto** — the bot runs the existing `execute_action()` engine with an AI skill picker. Live embed updates show the bracket and battle logs. Top 3 players get rewards.

**Scope:** new cog `bot/cogs/arena_tournament.py` + AI skill picker in `bot/engine/` + DB tables + config.

---

## 1. Tournament Flow

### 1.1 Lifecycle

```
SCHEDULED (auto every 1h) or ADMIN START
        │
        ▼
🟢 REGISTERING (60s)
   └─ Embed + "⚔️ Tham Gia" button
   └─ Live participant list with CP
        │
        ├─ < 4 players → CANCELLED (embed update, done)
        │
        ▼
🔴 SEEDING (instant)
   └─ Random bracket seeding
   └─ Handle odd numbers via BYE (see 1.2)
   └─ Bracket JSON saved to DB
        │
        ▼
⚔️ FIGHTING (per-round, sequential)
   └─ Round 1 → winners advance, bracket embed updated
   └─ Round 2 → ...
   └─ Final → champion declared
   └─ Battle logs appended to bracket embed
        │
        ▼
🏆 REWARDING
   └─ #1, #2, #3 rewards granted
   └─ Final embed with podium
```

### 1.2 BYE Handling (odd player count)

BYE = random player who hasn't had a BYE this tournament, advances free. No player gets BYE twice in the same tournament. If all remaining players have already had a BYE, pick randomly.

| Total | Round 1 | Round 2 | Final | BYEs |
|-------|---------|---------|-------|------|
| 4 | 2 matches → 2 win | — | 2 players | 0 |
| 5 | 2 matches → 2 win + 1 bye | 3 players (1 bye) | 2 players | 2 total |
| 6 | 3 matches → 3 win | 3 players (1 bye) | 2 players | 1 total |
| 7 | 3 matches → 3 win + 1 bye | 3 players (1 bye) | 2 players | 2 total |
| 8 | 4 matches → 4 win | 2 matches → 2 win | 2 players | 0 |

Algorithm:
1. Shuffle all participants randomly.
2. If `len(participants) <= 2`: direct final.
3. Pair adjacent players: `(pairs = [(p[i], p[i+1]) for i in range(0, len, 2)])`.
4. If odd count, last unpaired gets BYE.
5. Winners + bye player → next round. Repeat.

---

## 2. AI Skill Picker (`bot/engine/arena_ai.py`)

### 2.1 Function signature

```python
def pick_action(player: dict, opponent: dict, flags: dict, eff_stats: dict) -> tuple[str, dict]:
    """
    Return (slot_category, skill_dict) — one of 'attack', 'special', 'defense'.
    slot_category maps to the player's equipped skill slot.
    """
```

### 2.2 Decision tree

```
1. HP < 30%
   → DEFENSE slot: heal skill (if off CD) else default defend skill.
   → If no defense slot equipped → fall to step 4.

2. Opponent HP < 20%
   → ATTACK slot: multi_hit skill (if off CD) else highest-dmg skill.

3. Opponent has active burn
   → ATTACK slot: highest-dmg skill (burn chip + hit = lethal pressure).

4. Normal state — weighted random:
   - 50% ATTACK slot
   - 30% SPECIAL slot
   - 20% DEFENSE slot

   Within slot: pick highest damage multiplier skill that is off CD.
   If no skill off CD in that slot → pick another slot.
   If ALL slots on CD → default basic attack (slot 0, no skill — engine handles).
```

### 2.3 Edge cases

- **Stun**: engine handles — action skipped, `result_lines` records it.
- **Cheat death**: engine handles passively.
- **Burn / Regen ticks**: engine handles per-turn.
- **Defend state**: AI does NOT spam defend consecutively; if `_defending` flag is already true, bias away from defense slot.

---

## 3. UI / Embeds

### 3.1 Registration Embed

```
📜 ĐẤU TRƯỜNG SINH TỬ
─────────────────────────
⏳ Đăng ký kết thúc sau: {countdown}s

👥 Đã đăng ký ({count}):
  {emoji} @Player1  ⚔️ CP {cp}
  ...

[⚔️ Tham Gia]  [❌ Rời]  buttons

─────────────────────────
Cần ít nhất 4 người | Đấu auto, không cần thao tác
```

Footer: `"ID: #{tournament_id} | Phí: Miễn phí"`

### 3.2 Bracket Embed (live update during fights)

```
⚔️ ĐẤU TRƯỜNG SINH TỬ #{id} — LIVE
─────────────────────────

🏟️ VÒNG 1
  ✅ @Nam  thắng @Huy
  ✅ @An   thắng @Bình
  💎 @Khôi BYE

🏟️ BÁN KẾT (đang đấu...)
  🔄 @Nam ⚔️ VS 🛡️ @An
  ⏳ @Khôi chờ

🏟️ CHUNG KẾT
  ???
```

Each match appends a collapsible battle log (last 6 lines shown, `...xem thêm` in full log via replay-like format).

### 3.3 Final Podium Embed

```
🏆 ĐẤU TRƯỜNG SINH TỬ #{id} — KẾT THÚC
─────────────────────────
🥇 @Nam   — Quán Quân
🥈 @An    — Á Quân
🥉 @Khôi  — Hạng Ba

Phần thưởng đã được gửi! Hẹn gặp lại mùa sau ⚔️
```

---

## 4. Rewards

| Rank | Equipment | Stones | Coins | XP | VIP |
|------|-----------|--------|-------|-----|-----|
| 🥇 #1 | ★★★★ guaranteed | 3-5 Advanced | 200-400 | 100 | +2 |
| 🥈 #2 | ★★★ guaranteed | 1-3 Medium | 100-200 | 50 | +1 |
| 🥉 #3 (≥6 players) | ★★★ 50% | 5-10 Basic | 50-100 | 25 | — |
| #4+ | — | — | — | 10-20 | — |

Equipment roll uses existing `_EQUIP_BY_STAR` / `_STAR_CUMULATIVE` from `bot/engine/rewards.py`.

---

## 5. Database

### Table `arena_tournament`

```sql
CREATE TABLE arena_tournament (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'registering',  -- registering|fighting|done|cancelled
    channel_id TEXT NOT NULL,
    started_by TEXT NOT NULL,                     -- 'auto' or admin Discord ID
    started_at REAL NOT NULL,
    bracket_json TEXT,                            -- full bracket data as JSON
    winner_id TEXT,
    runner_up_id TEXT,
    third_id TEXT,
    finished_at REAL,
    created_at TEXT DEFAULT (datetime('now','+7 hours'))
);
```

### Table `arena_participants`

```sql
CREATE TABLE arena_participants (
    tournament_id INTEGER REFERENCES arena_tournament(id),
    player_id TEXT NOT NULL,
    cp_at_entry INTEGER DEFAULT 0,
    eliminated_round INTEGER DEFAULT 0,           -- round where eliminated
    final_rank INTEGER DEFAULT 0,                 -- 1,2,3 or 0
    reward_given INTEGER DEFAULT 0,
    PRIMARY KEY (tournament_id, player_id)
);
```

---

## 6. Admin Commands

| Command | Permission | Description |
|---------|-----------|-------------|
| `/arena start` | Admin | Force-start tournament immediately |
| `/arena stop` | Admin | Cancel current tournament |
| `/arena toggle` | Admin | Enable/disable auto-schedule |
| `/arena status` | Admin | Show current tournament state |
| `/arena history` | Anyone | Last 5 tournaments with winners |

---

## 7. Config (`bot/config.py` additions)

```python
ARENA_INTERVAL = 3600            # seconds between auto tournaments
ARENA_REGISTER_TIME = 60         # registration window in seconds
ARENA_MIN_PLAYERS = 4
ARENA_MAX_PLAYERS = 8
ARENA_AUTO_ENABLED = True
ARENA_BATTLE_DELAY = 3           # seconds pause between rounds (for viewing)
ARENA_SHOW_LOG_LINES = 6         # max battle log lines in bracket embed
```

---

## 8. Files to create/modify

| File | Action |
|------|--------|
| `bot/cogs/arena_tournament.py` | **New** — main cog (lifecycle, embeds, bracket logic) |
| `bot/engine/arena_ai.py` | **New** — AI skill picker |
| `bot/config.py` | **Modify** — add arena config constants |
| `bot/database.py` | **Modify** — add arena_tournament, arena_participants tables |
| `bot/views/arena_view.py` | **New** — Join button view, bracket view |

---

## 9. Edge Cases & Safety

- Player dies mid-tournament (HP = 0 from previous battle) → HP restored to full after each match. Arena battles use a separate HP pool; world HP is untouched.
- Player disconnects / leaves server mid-tournament → still fights (data in DB).
- Concurrent tournaments → NOT allowed. Check `status NOT IN ('done', 'cancelled')` before starting.
- Server restart during tournament → on cog load, check for in-progress tournament and resume.
- No participants in a round (all BYE exhausted) → impossible by construction; max 2 BYEs and at least 2 players per round.

---

## 10. Bracket JSON Structure

```json
{
  "rounds": [
    {
      "name": "Vòng 1",
      "matches": [
        {
          "p1_id": "123",
          "p1_name": "Nam",
          "p2_id": "456",
          "p2_name": "Huy",
          "winner_id": "123",
          "log": ["⚔️ Nam dùng Chém Mạnh -42HP ...", "🔥 Huy dùng Thiêu Đốt ...", "💀 Huy thua!"],
          "p1_hp_remaining": 156,
          "p2_hp_remaining": 0
        }
      ],
      "byes": [{"id": "789", "name": "Khôi"}]
    }
  ],
  "players": {"123": 4200, "456": 3800, "789": 5100}
}
```
