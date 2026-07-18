# Hệ thống Cường Hóa Trang Bị & Bí Cảnh Vực Sâu Xỏ Lá

**Ngày:** 2026-07-17
**Trạng thái:** Draft

---

## 1. Tổng quan

Thêm 2 hệ thống liên kết:
- **Cường hóa trang bị:** Nâng cấp trang bị từ 0 → 9 sao, tăng chỉ số theo %, dùng đá cường hóa + coin.
- **Bí cảnh Vực Sâu Xỏ Lá:** Dungeon 100 tầng, nơi nhặt đá cường hóa, coin, và trang bị.

---

## 2. Database

### 2.1 Bảng `player_equipment` (thay thế bảng cũ)

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `id` | INTEGER PK AUTOINCREMENT | ID riêng từng instance trang bị |
| `player_id` | TEXT NOT NULL | Discord user ID |
| `item_id` | INTEGER NOT NULL | Mã trang bị từ `EQUIPMENT` dict |
| `enhance` | INTEGER DEFAULT 0 | Cấp cường hóa (0-9) |
| `equipped` | INTEGER DEFAULT 0 | 1 nếu đang trang bị |

### 2.2 Bảng `player_enhance_stones`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `player_id` | TEXT PK | Discord user ID |
| `stone_basic` | INTEGER DEFAULT 0 | Đá cường hóa sơ cấp |
| `stone_medium` | INTEGER DEFAULT 0 | Đá cường hóa trung cấp |
| `stone_advanced` | INTEGER DEFAULT 0 | Đá cường hóa cao cấp |

### 2.3 Bảng `dungeon_progress`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `player_id` | TEXT PK | Discord user ID |
| `checkpoint` | INTEGER DEFAULT 0 | Tầng cao nhất đã đạt |
| `daily_entries` | INTEGER DEFAULT 0 | Số lần đã vào hôm nay |
| `daily_tickets_bought` | INTEGER DEFAULT 0 | Số vé đã mua hôm nay |
| `last_entry_date` | TEXT | Ngày vào cuối cùng |
| `last_week_reset` | TEXT | Ngày reset checkpoint tuần cuối |

### 2.4 Migration

- Tạo bảng `player_equipment_new` với schema mới
- Copy dữ liệu từ `player_equipment` cũ: mỗi dòng quantity=N tạo N dòng mới với `enhance=0, equipped=0`
- Copy trạng thái equip từ `player_equip_slots` → set `equipped=1` cho các instance tương ứng
- Drop `player_equipment` cũ, rename `player_equipment_new`
- Drop `player_equip_slots`
- Sửa tất cả code tham chiếu cũ

---

## 3. Cường hóa trang bị

### 3.1 Công thức

| Mức hiện tại | Sao đích | % Thành công | Đá cần | Coin phí |
|:---:|:---:|:---:|:---:|:---:|
| 0 | 1 | 100% | Sơ cấp x2 | 200 |
| 1 | 2 | 87.5% | Sơ cấp x4 | 200 |
| 2 | 3 | 75% | Sơ cấp x6 | 200 |
| 3 | 4 | 62.5% | Trung cấp x2 | 500 |
| 4 | 5 | 50% | Trung cấp x4 | 500 |
| 5 | 6 | 37.5% | Trung cấp x6 | 500 |
| 6 | 7 | 25% | Cao cấp x2 | 1000 |
| 7 | 8 | 17.5% | Cao cấp x4 | 1000 |
| 8 | 9 | 10% | Cao cấp x6 | 1000 |

### 3.2 Quy tắc

- **Bonus chỉ số:** +8% chỉ số gốc cho mỗi cấp cường hóa. Với enhance=N, tổng bonus = 1 + N × 0.08.
- **Thất bại:** Mất toàn bộ đá + coin đã bỏ ra, giữ nguyên cấp cường hóa.
- **Giới hạn:** Tối đa 9 sao, không thể cường hóa quá 9.
- **Chọn món:** Người chơi chọn từ inventory, món không cần phải đang trang bị.

### 3.3 Cách áp dụng bonus

Trong `get_effective_stats()` (`bot/engine/battle.py`):
```python
if item_id in EQUIPMENT:
    stats = EQUIPMENT[item_id]["stats"]
    enhance_mult = 1 + enhance_level * 0.08
    for k, v in stats.items():
        # multiply base stats by enhance multiplier
        ...
```

### 3.4 Lệnh

- `!cuonghoa <equipment_id>` / `/cuonghoa <equipment_id>`
  - Kiểm tra: có đủ đá + coin không
  - Roll tỉ lệ thành công
  - Nếu thành công: tăng enhance, thông báo kết quả embed
  - Nếu thất bại: trừ đá + coin, thông báo embed
  - Autocomplete: `/cuonghoa` hiển thị danh sách món đang có kèm cấp cường hóa

---

## 4. Bí cảnh Vực Sâu Xỏ Lá

### 4.1 Thông số

| Tham số | Giá trị |
|:---|:---|
| Số tầng | 100 |
| Yêu cầu level | 7 |
| Free mỗi ngày | 1 lượt |
| Vé mua thêm | Tối đa 2 vé/ngày (vé 1: 200🪙, vé 2: 400🪙) |
| Số trận mỗi lượt | Không giới hạn (đến khi thua hoặc dừng) |
| Checkpoint reset | Hàng tuần (Thứ 2 00:00) |

### 4.2 Phân bố thưởng theo tầng

| Tầng | Đá rơi | Coin | Trang bị rơi |
|:---|:---|:---|:---|
| 1-10 | Sơ cấp x1-2 | 50-100 | 1★ |
| 11-20 | Sơ cấp x2-4 | 100-200 | 1-2★ |
| 21-30 | Trung cấp x1-2 | 150-250 | 1-3★ |
| 31-40 | Trung cấp x2-3 | 200-350 | 1-3★ |
| 41-50 | Trung cấp x3-5 | 250-500 | 1-4★ |
| 51-65 | Cao cấp x1-2 | 300-500 | 1-5★ |
| 66-80 | Cao cấp x2-3 | 400-700 | 1-5★ |
| 81-90 | Cao cấp x3-4 | 500-900 | 1-6★ |
| 91-100 | Cao cấp x4-6 | 700-1200 | 1-6★ |

### 4.3 NPC

- Tự động sinh NPC mỗi tầng với level = tầng + 5 (VD: tầng 25 NPC level 30)
- Chỉ số scale theo level dùng công thức tuyến tính như NPC có sẵn
- NPC có thể dùng 3-4 skill random phù hợp level

### 4.4 Luồng vào bí cảnh

1. Người chơi dùng `!bicanh` → kiểm tra level ≥ 7
2. Kiểm tra còn lượt không (free hoặc còn vé mua)
3. Nếu hết lượt → hỏi mua vé (200/400🪙)
4. Bắt đầu từ checkpoint + 1
5. Hiển thị embed: tầng hiện tại, thưởng đã tích lũy, NPC đối thủ
6. Giao diện nút: **Chiến đấu** | **Dừng & Nhận thưởng**
7. Thắng → lên tầng, cập nhật thưởng, tăng checkpoint
8. Thua → dừng, nhận thưởng đã tích lũy, checkpoint giữ nguyên
9. Tự dừng → nhận thưởng, checkpoint = tầng hiện tại

### 4.5 Tích lũy thưởng trong lượt

- Mỗi tầng thắng: cộng dồn đá + coin + trang bị vào pool
- Khi dừng/thua: cộng toàn bộ vào tài khoản người chơi
- Nếu crash/disconnect: tự động nhận thưởng đã tích lũy

### 4.6 Lệnh

- `!bicanh` / `/bicanh`
  - Hiển thị: checkpoint hiện tại, lượt còn lại hôm nay, vé đã mua
  - Bắt đầu vào bí cảnh nếu còn lượt

---

## 5. Shop - Vé bí cảnh

Thêm vào `bot/data/shop_items.py`:

```python
DUNGEON_TICKET_S1 = 200   # Vé 1
DUNGEON_TICKET_S2 = 400   # Vé 2 (tự động áp dụng sau khi mua vé 1)
```

Vé sẽ được xử lý trong command `!bicanh` (không phải item riêng trong shop inventory) — khi hết lượt, bot tự hỏi mua vé.

---

## 6. Cập nhật `!inv` / `/inv`

- Mỗi món trang bị hiển thị kèm cấp cường hóa (nếu > 0)
- Hiển thị số lượng đá cường hóa đang có
- Format: `🔷 Kiếm Gỗ (+3) - ATK 50-70 → 62-86`

---

## 7. Files cần tạo/sửa

### Tạo mới
| File | Nội dung |
|:---|:---|
| `bot/cogs/enhance.py` | Cog cường hóa: lệnh `/cuonghoa` |
| `bot/cogs/dungeon.py` | Cog bí cảnh: lệnh `/bicanh`, logic dungeon |
| `bot/engine/dungeon.py` | Logic sinh NPC theo tầng, tính thưởng |
| `bot/data/dungeon_npcs.py` | Template NPC dungeon (nếu cần tách) |
| `bot/views/dungeon_view.py` | View nút Chiến đấu / Dừng |

### Sửa
| File | Thay đổi |
|:---|:---|
| `bot/database.py` | Migration schema mới cho `player_equipment`, thêm bảng `player_enhance_stones`, `dungeon_progress` |
| `bot/cogs/shop.py` | Sửa logic equip/unequip dùng schema mới; cập nhật `!inv` hiển thị enhance + đá |
| `bot/engine/battle.py` | `get_effective_stats()` áp dụng enhance multiplier |
| `bot/engine/rewards.py` | Thêm logic drop đá cường hóa |
| `bot/data/shop_items.py` | Thêm config giá vé bí cảnh |
| `bot/config.py` | Thêm constants cho dungeon, enhance |
| `main.py` | Load thêm 2 cog mới |
| `bot/views/battle_view.py` | `get_effective_stats()` nếu cần cập nhật |

---

## 8. Constants (thêm vào `bot/config.py`)

```python
# Enhancement
MAX_ENHANCE = 9
ENHANCE_BONUS_PER_LEVEL = 0.08
ENHANCE_BASE_SUCCESS = 1.0       # 0→1
ENHANCE_MIN_SUCCESS = 0.10       # 8→9

# Stones
STONE_BASIC = "stone_basic"
STONE_MEDIUM = "stone_medium"
STONE_ADVANCED = "stone_advanced"

# Dungeon
DUNGEON_MAX_FLOOR = 100
DUNGEON_REQUIRED_LEVEL = 7
DUNGEON_FREE_ENTRIES = 1
DUNGEON_MAX_TICKETS = 2
DUNGEON_TICKET_COST_1 = 200
DUNGEON_TICKET_COST_2 = 400

# Dungeon stone drops
FLOOR_TIER_1 = 20    # 1-20: basic stones
FLOOR_TIER_2 = 50    # 21-50: medium stones
FLOOR_TIER_3 = 100   # 51-100: advanced stones
```
