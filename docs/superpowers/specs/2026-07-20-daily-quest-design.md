# Hệ thống Nhiệm Vụ Hàng Ngày (Daily Quest)

**Ngày:** 2026-07-20

---

## 1. Tổng quan

Mỗi ngày người chơi nhận 5 nhiệm vụ ngẫu nhiên. Có thể dùng vé reset để chọn reset 1 quest cụ thể. Bảng `daily_quests` đã có sẵn trong DB.

---

## 2. Database

### Bảng `daily_quests` (đã có)

| Cột | Thay đổi |
|-----|----------|
| `player_id, quest_id, date` | Giữ nguyên PK |
| `progress` | Giữ nguyên |
| `target` | Giữ nguyên |
| `completed` | Giữ nguyên |
| `claimed` | Giữ nguyên |

### Bảng mới: `player_vip_coins`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `player_id` | TEXT PK | Discord ID |
| `amount` | INTEGER DEFAULT 0 | Số VIP Coin |

---

## 3. Pool nhiệm vụ (15 loại)

| ID | Tên | Mục tiêu | Thưởng |
|:---:|------|:---:|------|
| 1 | Đánh NPC | Thắng 3 NPC | 500🪙 + 50XP + 1 VIP |
| 2 | Thách PvP | Thắng 2 trận | 800🪙 + 80XP + 1 VIP |
| 3 | Cường Hóa | Cường hóa thành công 1 lần | 300🪙 + Đá sơ cấp x2 + 1 VIP |
| 4 | Mua Sắm | Mua 1 món trong shop | 200🪙 + 30XP + 1 VIP |
| 5 | Dùng Item | Dùng 2 item tiêu hao | 200🪙 + 30XP + 1 VIP |
| 6 | Bí Cảnh | Vào bí cảnh 1 lần | 600🪙 + Đá trung cấp x1 + 1 VIP |
| 7 | Trả Lời Quiz | Trả lời đúng 1 câu | 400🪙 + 40XP + 1 VIP |
| 8 | Nâng Thần Khí | Nâng cấp thần khí 1 lần | 500🪙 + Đá thần khí x1 + 1 VIP |
| 9 | Gacha Waifu | Gacha 1 lần | 300🪙 + 30XP + 1 VIP |
| 10 | Giao Dịch | Trade 1 lần | 300🪙 + 40XP + 1 VIP |
| 11 | Săn Boss | Thắng NPC lv15+ | 700🪙 + 70XP + 1 VIP |
| 12 | Nâng Cấp | Dùng `!upgrade` 1 lần | 300🪙 + 30XP + 1 VIP |
| 13 | Đổi Class | Đổi class 1 lần | 500🪙 + 50XP + 1 VIP |
| 14 | Hồi Máu | Dùng máu gà/bò 1 lần | 200🪙 + 20XP + 1 VIP |
| 15 | Chat Quiz | Trả lời quiz 1 lần | 400🪙 + 40XP + 1 VIP |

---

## 4. Cơ chế

- **Reset 0h**: tự động xóa quest cũ, tạo 5 quest mới random (không trùng)
- **Tiến độ tự động**: mỗi action trong game cập nhật progress của quest tương ứng
- **Claim**: `!quest` hiển thị, khi `completed=1 && claimed=0` → tự động claim khi xem
- **Vé reset quest**: bán trong shop (ID 26), giá 500🪙. Dùng → chọn quest muốn reset → thay bằng quest mới
- **VIP Coin**: mỗi quest hoàn thành +1 VIP Coin. Lưu trong `player_vip_coins`
- **Bonus đủ 5/5**: +1000🪙 + Đá cao cấp x1 + 2 VIP Coin

---

## 5. VIP Coin Shop (tương lai)

| Item | Giá VIP | Mô tả |
|------|:---:|------|
| Đá thần khí x5 | 10 | |
| Trang bị 5★ random | 30 | |
| Waifu SVIP random | 50 | |
| Đá cao cấp x10 | 15 | |
| Reset thần khí | 20 | |

---

## 6. Shop item mới

| ID | Tên | Giá | Mô tả |
|:---:|------|:---:|------|
| 26 | 🎫 Vé Reset Quest | 500🪙 | Chọn reset 1 nhiệm vụ |

---

## 7. Lệnh

- `!quest` / `/quest` — xem 5 nhiệm vụ hôm nay, claim thưởng, chọn reset quest (nếu có vé)
- `!vip` / `/vip` — xem số VIP Coin + shop VIP

---

## 8. Files

| File | Thay đổi |
|:---|:---|
| `bot/cogs/quest.py` | Cog mới: `/quest`, `/vip`, logic nhiệm vụ |
| `bot/data/quests.py` | Pool 15 nhiệm vụ |
| `bot/database.py` | Thêm `player_vip_coins` |
| `bot/cogs/shop.py` | Thêm item 26 (vé reset quest) |
| `bot/data/shop_items.py` | Thêm item 26 |
| `bot/config.py` | Constants |
| `bot/cogs/npc.py` | Hook cập nhật quest progress |
| `bot/cogs/arena.py` | Hook cập nhật quest progress |
| `bot/cogs/dungeon.py` | Hook cập nhật progress |
| `bot/cogs/quiz.py` | Hook cập nhật progress |
| `bot/cogs/waifu.py` | Hook cập nhật progress |
| `bot/cogs/enhance.py` | Hook cập nhật progress |
| `bot/cogs/shop.py` | Hook cập nhật progress |
| `main.py` | Load quest cog |
