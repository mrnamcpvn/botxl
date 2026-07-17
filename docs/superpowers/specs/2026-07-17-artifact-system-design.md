# Hệ thống Thần Khí

**Ngày:** 2026-07-17
**Branch:** feature/thankhi

---

## 1. Tổng quan

Thần Khí là vật phẩm đặc biệt có 10 cấp sao (1★→10★). Mỗi sao có tên và ngoại hình GIF khác nhau (theme kiếm hiệp Trung Quốc). Khi kích hoạt và trang bị, tăng % toàn bộ chỉ số người chơi.

---

## 2. Database

### 2.1 Bảng `player_artifact`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `player_id` | TEXT PK | Discord user ID |
| `star` | INTEGER DEFAULT 0 | Cấp sao (0=chưa kích hoạt) |
| `stone_count` | INTEGER DEFAULT 0 | Số đá thần khí đang có |

### 2.2 Migration

```sql
CREATE TABLE IF NOT EXISTS player_artifact (
    player_id TEXT PRIMARY KEY,
    star INTEGER DEFAULT 0,
    stone_count INTEGER DEFAULT 0
);
```

Thêm vào `database.py` như 1 bảng mới trong TABLES list.

---

## 3. Dữ liệu Thần Khí

### 3.1 Định nghĩa 10 sao (`bot/data/artifacts.py`)

Mỗi sao: tên, URL GIF, màu embed, mô tả.

| Sao | Tên | Màu |
|-----|-----|-----|
| 0 | Chưa kích hoạt | 0x888888 |
| 1 | Thanh Phong Kiếm | 0x88ccff |
| 2 | Huyền Thiết Trọng Kiếm | 0x44ff44 |
| 3 | Tử Điện Thần Kiếm | 0xffcc00 |
| 4 | Hắc Ám Ma Kiếm | 0xaa44ff |
| 5 | Xích Viêm Hỏa Kiếm | 0xff4444 |
| 6 | Băng Phách Hàn Kiếm | 0x44ccff |
| 7 | Lôi Thần Chiến Kích | 0xff8800 |
| 8 | Hỗn Độn Thần Thương | 0xcc44ff |
| 9 | Thái Cực Bàn Long Đao | 0xff44aa |
| 10 | Hủy Diệt Thần Kiếm | 0xff0044 |

GIF URLs: lấy từ các nguồn GIF kiếm hiệp online (tenor, giphy...). Fallback: dùng emoji nếu URL lỗi.

### 3.2 Công thức nâng cấp

| Sao đích | Đá cần | Coin | % Boost |
|:---:|:---:|:---:|:---:|
| 1 | 0 | 100,000 | +15% |
| 2 | 1 | 10,000 | +30% |
| 3 | 2 | 20,000 | +45% |
| 4 | 3 | 30,000 | +60% |
| 5 | 4 | 40,000 | +75% |
| 6 | 6 | 50,000 | +90% |
| 7 | 8 | 60,000 | +105% |
| 8 | 10 | 75,000 | +120% |
| 9 | 12 | 90,000 | +135% |
| 10 | 15 | 100,000 | +150% |

- Thất bại: mất đá + coin, giữ nguyên sao
- Tỉ lệ thành công: giống như cường hóa trang bị (100%→0→1, giảm dần còn 10% cho 9→10)

---

## 4. Boost chỉ số

Trong `get_effective_stats()`, sau khi tính xong tất cả chỉ số, áp dụng multiplier từ thần khí:

```python
artifact_mult = 1 + pdata.get("_artifact_star", 0) * 0.15
hp_max = int(hp_max * artifact_mult)
atk_min = int(atk_min * artifact_mult)
atk_max = int(atk_max * artifact_mult)
defense = int(defense * artifact_mult)
spd = int(spd * artifact_mult)
crit = int(crit * artifact_mult)
# ... tất cả chỉ số phụ
```

Star data được load vào `pdata["_artifact_star"]` khi load player (tương tự cách load `_equip_items`).

---

## 5. Lệnh

### `!thankhi` / `/thankhi`

- Hiển thị embed với GIF thần khí hiện tại (hoặc "Chưa kích hoạt")
- Nút ◀ và ▶ để xem các sao khác (preview)
- Nếu chưa kích hoạt: nút "🔓 Kích Hoạt (100,000🪙)"
- Nếu có đủ đá + coin: nút "⬆ Nâng Cấp"
- Hiển thị: tên, sao, GIF, chỉ số boost hiện tại, đá đang có

### `!stats` tab mới

Thêm tab "🔱 Thần Khí" vào StatsView, hiển thị thần khí hiện tại của người chơi.

---

## 6. Nguồn đá thần khí

### Drop từ NPC battle

Sau khi thắng NPC (lv 15+): 5% tỉ lệ rơi 1 viên đá thần khí.

### Drop từ bí cảnh

Tầng 50+: 3% tỉ lệ rơi mỗi tầng thắng.

### Admin command

`!give_stone @player <số>` — thêm đá thần khí cho người chơi.

---

## 7. Files

### Tạo mới
| File | Nội dung |
|:---|:---|
| `bot/data/artifacts.py` | Định nghĩa 10 sao thần khí |
| `bot/views/artifact_view.py` | View hiển thị thần khí với nút prev/next/upgrade |

### Sửa
| File | Thay đổi |
|:---|:---|
| `bot/cogs/shop.py` | Thêm lệnh `!thankhi` / `/thankhi` (hoặc cog riêng) |
| `bot/engine/battle.py` | `get_effective_stats()` áp dụng artifact_mult |
| `bot/views/stats_view.py` | Thêm tab "🔱 Thần Khí" |
| `bot/database.py` | Thêm bảng `player_artifact` |
| `bot/config.py` | Thêm constants: `ARTIFACT_BOOST = 0.15`, `ARTIFACT_UNLOCK_COST = 100000` |
| `bot/cogs/npc.py` | Thêm drop đá thần khí khi thắng NPC lv15+ |
| `bot/cogs/dungeon.py` | Thêm drop đá thần khí tầng 50+ |
| `bot/cogs/admin.py` | Thêm lệnh `!give_stone` |
| `main.py` | Load artifact cog nếu tách riêng |

---

## 8. Constants

```python
ARTIFACT_BOOST_PER_STAR = 0.15
ARTIFACT_UNLOCK_COST = 100000
ARTIFACT_MAX_STAR = 10
ARTIFACT_STONE_DROP_CHANCE = 0.05
ARTIFACT_STONE_DROP_NPC_MIN_LEVEL = 15
ARTIFACT_STONE_DUNGEON_MIN_FLOOR = 50
ARTIFACT_STONE_DUNGEON_CHANCE = 0.03
```
