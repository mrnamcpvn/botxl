# ★1=Blue ★2=Green ★3=Yellow ★4=Purple ★5=Red ★6=Gold(Legendary)
STAR_COLORS = {1: 0x4488ff, 2: 0x44ff44, 3: 0xffcc00, 4: 0xaa44ff, 5: 0xff4444, 6: 0xff69b4}
STAR_LABELS = {1: "🔵", 2: "🟢", 3: "🟡", 4: "🟣", 5: "🔴", 6: "💗"}
STAR_NAMES = {1: "Thường", 2: "Cao Cấp", 3: "Hiếm", 4: "Sử Thi", 5: "Huyền Thoại", 6: "Thần Thoại"}
SLOT_NAMES = {
    "weapon": "🗡️ Vũ Khí", "armor": "🛡️ Áo Giáp", "boots": "👢 Giày",
    "gloves": "🧤 Bao Tay", "belt": "🎗️ Dây Lưng", "ring": "💍 Nhẫn"
}
DROP_WEIGHTS = {1: 500, 2: 300, 3: 159, 4: 30, 5: 10, 6: 1}

SET_BONUSES = {
    1: {"name": "Đồng Nát", "hp_pct": 5},
    2: {"name": "Tinh Anh", "hp_pct": 8, "def_pct": 5},
    3: {"name": "Hiếm Có", "hp_pct": 10, "atk_pct": 8},
    4: {"name": "Sử Thi", "hp_pct": 15, "atk_pct": 10, "crit": 5},
    5: {"name": "Huyền Thoại", "hp_pct": 20, "atk_pct": 15, "crit": 8},
    6: {"name": "Thần Thoại", "hp_pct": 30, "atk_pct": 20, "crit": 10, "dodge": 5},
}

EQUIPMENT = {
    # ═══════ ⭐1 🔵 VŨ KHÍ (ATK) ═══════
    101: {"name":"Gậy Tre Làng","slot":"weapon","star":1,"stats":{"attack_min":3,"attack_max":5}},
    102: {"name":"Dao Cạo Râu","slot":"weapon","star":1,"stats":{"attack_min":2,"attack_max":6}},
    103: {"name":"Cây Chổi Cùn","slot":"weapon","star":1,"stats":{"attack_min":4,"attack_max":4}},
    104: {"name":"Cuốc Chim","slot":"weapon","star":1,"stats":{"attack_min":3,"attack_max":5,"crit":2}},

    # ⭐2 🟢 VŨ KHÍ
    201: {"name":"Kiếm Tép Bạc","slot":"weapon","star":2,"stats":{"attack_min":6,"attack_max":10}},
    202: {"name":"Rìu Củi Sắt","slot":"weapon","star":2,"stats":{"attack_min":5,"attack_max":12}},
    203: {"name":"Thương Tre Ngâm","slot":"weapon","star":2,"stats":{"attack_min":8,"attack_max":8}},
    204: {"name":"Côn Nhị Khúc","slot":"weapon","star":2,"stats":{"attack_min":7,"attack_max":9,"spd":2}},

    # ⭐3 🟡 VŨ KHÍ
    301: {"name":"Đao Cương Thi","slot":"weapon","star":3,"stats":{"attack_min":10,"attack_max":18}},
    302: {"name":"Cung Tên Lửa","slot":"weapon","star":3,"stats":{"attack_min":8,"attack_max":22}},
    303: {"name":"Song Kiếm Hắc Ám","slot":"weapon","star":3,"stats":{"attack_min":12,"attack_max":16,"crit":5}},

    # ⭐4 🟣 VŨ KHÍ
    401: {"name":"Gươm Bạch Hổ","slot":"weapon","star":4,"stats":{"attack_min":15,"attack_max":28}},
    402: {"name":"Phủ Việt Huyết","slot":"weapon","star":4,"stats":{"attack_min":20,"attack_max":24}},
    403: {"name":"Xà Mâu Băng Giá","slot":"weapon","star":4,"stats":{"attack_min":18,"attack_max":26,"pierce":8}},

    # ⭐5 🔴 VŨ KHÍ
    501: {"name":"⚔️ Long Đao Hắc Ám","slot":"weapon","star":5,"stats":{"attack_min":25,"attack_max":42}},
    502: {"name":"🗡️ Song Nhận Bão Tố","slot":"weapon","star":5,"stats":{"attack_min":28,"attack_max":38,"spd":5}},
    503: {"name":"🔱 Đinh Ba Hải Thần","slot":"weapon","star":5,"stats":{"attack_min":22,"attack_max":45,"crit":8}},

    # ⭐6 💗 THẦN THOẠI VŨ KHÍ
    601: {"name":"🗡️ Gậy Thần Thor","slot":"weapon","star":6,"stats":{"attack_min":35,"attack_max":58,"crit":10}},
    602: {"name":"⚔️ Excalibur Ba Que","slot":"weapon","star":6,"stats":{"attack_min":40,"attack_max":50,"pierce":15}},
    603: {"name":"🔪 Huyết Kiếm Long Thần","slot":"weapon","star":6,"stats":{"attack_min":38,"attack_max":55,"spd":8,"crit":5}},

    # ═══════ ⭐1 🔵 ÁO GIÁP (DEF+HP) ═══════
    110: {"name":"Áo Mưa Rách","slot":"armor","star":1,"stats":{"defense":3,"hp":10}},
    111: {"name":"Áo Bà Ba","slot":"armor","star":1,"stats":{"defense":2,"hp":15}},
    112: {"name":"Áo Thun Ba Lỗ","slot":"armor","star":1,"stats":{"defense":4,"hp":8}},

    # ⭐2 🟢 ÁO GIÁP
    210: {"name":"Giáp Gỗ Lim","slot":"armor","star":2,"stats":{"defense":7,"hp":25}},
    211: {"name":"Áo Choàng Dơi","slot":"armor","star":2,"stats":{"defense":5,"hp":35}},
    212: {"name":"Giáp Da Thuộc","slot":"armor","star":2,"stats":{"defense":8,"hp":20,"regen":2}},

    # ⭐3 🟡 ÁO GIÁP
    310: {"name":"Giáp Sắt Rỉ","slot":"armor","star":3,"stats":{"defense":12,"hp":50}},
    311: {"name":"Áo Lụa Thần","slot":"armor","star":3,"stats":{"defense":8,"hp":70}},
    312: {"name":"Áo Giáp Xích","slot":"armor","star":3,"stats":{"defense":15,"hp":35,"reflect":3}},

    # ⭐4 🟣 ÁO GIÁP
    410: {"name":"Khiên Rồng Thiêng","slot":"armor","star":4,"stats":{"defense":18,"hp":90}},
    411: {"name":"Giáp Rùa Ngàn Năm","slot":"armor","star":4,"stats":{"defense":22,"hp":60}},
    412: {"name":"Áo Choàng Pháp Sư","slot":"armor","star":4,"stats":{"defense":15,"hp":80,"regen":5}},

    # ⭐5 🔴 ÁO GIÁP
    510: {"name":"🛡️ Thiên Giáp Bất Tử","slot":"armor","star":5,"stats":{"defense":30,"hp":140}},
    511: {"name":"🛡️ Hộ Giáp Rồng Thiêng","slot":"armor","star":5,"stats":{"defense":35,"hp":120,"reflect":5}},

    # ⭐6 💗 THẦN THOẠI ÁO GIÁP
    610: {"name":"🛡️ Khiên Aegis","slot":"armor","star":6,"stats":{"defense":42,"hp":200,"reflect":5}},
    611: {"name":"🛡️ Áo Giáp Thần Thánh","slot":"armor","star":6,"stats":{"defense":48,"hp":180,"regen":8}},

    # ═══════ ⭐1 🔵 GIÀY (SPD) ═══════
    120: {"name":"Dép Tổ Ong","slot":"boots","star":1,"stats":{"spd":2}},
    121: {"name":"Dép Lào Rách","slot":"boots","star":1,"stats":{"spd":1,"defense":1}},
    122: {"name":"Guốc Mộc","slot":"boots","star":1,"stats":{"spd":1,"hp":8}},

    # ⭐2 🟢 GIÀY
    220: {"name":"Giày Vải Bố","slot":"boots","star":2,"stats":{"spd":4,"hp":10}},
    221: {"name":"Xăng-đan Da","slot":"boots","star":2,"stats":{"spd":3,"defense":3}},
    222: {"name":"Dép Cao Su","slot":"boots","star":2,"stats":{"spd":4,"defense":2}},

    # ⭐3 🟡 GIÀY
    320: {"name":"Hài Phong Thần","slot":"boots","star":3,"stats":{"spd":7,"hp":25}},
    321: {"name":"Giày Lính Đánh Thuê","slot":"boots","star":3,"stats":{"spd":6,"defense":5,"hp":10}},

    # ⭐4 🟣 GIÀY
    420: {"name":"Ủng Chiến Binh","slot":"boots","star":4,"stats":{"spd":11,"defense":6}},
    421: {"name":"Hài Tốc Hành","slot":"boots","star":4,"stats":{"spd":12,"hp":20}},

    # ⭐5 🔴 GIÀY
    520: {"name":"👢 Hải Vân Nộ","slot":"boots","star":5,"stats":{"spd":16,"hp":50}},
    521: {"name":"👟 Phong Hỏa Luân","slot":"boots","star":5,"stats":{"spd":18,"defense":10}},

    # ⭐6 💗 THẦN THOẠI GIÀY
    620: {"name":"👟 Lôi Thần Tốc","slot":"boots","star":6,"stats":{"spd":22,"dodge":5}},
    621: {"name":"👢 Hư Không Chi Nộ","slot":"boots","star":6,"stats":{"spd":20,"dodge":8,"hp":30}},

    # ═══════ ⭐1 🔵 BAO TAY (ATK+crit) ═══════
    130: {"name":"Bao Tay Vải","slot":"gloves","star":1,"stats":{"attack_min":2,"attack_max":3}},
    131: {"name":"Găng Tay Lưới","slot":"gloves","star":1,"stats":{"attack_min":1,"attack_max":4}},
    132: {"name":"Bao Tay Đấm Bốc","slot":"gloves","star":1,"stats":{"attack_min":2,"attack_max":3,"crit":1}},

    # ⭐2 🟢 BAO TAY
    230: {"name":"Bao Tay Sắt","slot":"gloves","star":2,"stats":{"attack_min":5,"attack_max":8}},
    231: {"name":"Găng Hổ Phách","slot":"gloves","star":2,"stats":{"attack_min":6,"attack_max":6,"crit":3}},
    232: {"name":"Găng Đồng","slot":"gloves","star":2,"stats":{"attack_min":4,"attack_max":9}},

    # ⭐3 🟡 BAO TAY
    330: {"name":"Thiết Quyền Sáo","slot":"gloves","star":3,"stats":{"attack_min":9,"attack_max":15}},
    331: {"name":"Găng Bạch Kim","slot":"gloves","star":3,"stats":{"attack_min":11,"attack_max":13,"crit":5}},

    # ⭐4 🟣 BAO TAY
    430: {"name":"Kình Thiên Chưởng","slot":"gloves","star":4,"stats":{"attack_min":14,"attack_max":22,"crit":5}},
    431: {"name":"Găng Hỏa Thần","slot":"gloves","star":4,"stats":{"attack_min":16,"attack_max":20,"pierce":8}},

    # ⭐5 🔴 BAO TAY
    530: {"name":"🧤 Quyền Nộ Long","slot":"gloves","star":5,"stats":{"attack_min":22,"attack_max":35}},
    531: {"name":"✊ Thần Quyền Vô Ảnh","slot":"gloves","star":5,"stats":{"attack_min":25,"attack_max":30,"crit":10}},

    # ⭐6 💗 THẦN THOẠI BAO TAY
    630: {"name":"✋ Thiên Ma Thủ","slot":"gloves","star":6,"stats":{"attack_min":30,"attack_max":48,"crit":12}},
    631: {"name":"🤛 Diệt Thần Quyền","slot":"gloves","star":6,"stats":{"attack_min":35,"attack_max":42,"pierce":15,"crit":8}},

    # ═══════ ⭐1 🔵 DÂY LƯNG (HP) ═══════
    140: {"name":"Dây Lưng Vải","slot":"belt","star":1,"stats":{"hp":20}},
    141: {"name":"Thắt Lưng Tre","slot":"belt","star":1,"stats":{"hp":12,"defense":1}},
    142: {"name":"Dây Thừng","slot":"belt","star":1,"stats":{"hp":15,"defense":1}},

    # ⭐2 🟢 DÂY LƯNG
    240: {"name":"Dây Lưng Da","slot":"belt","star":2,"stats":{"hp":45}},
    241: {"name":"Đai Vải Bố","slot":"belt","star":2,"stats":{"hp":35,"defense":3}},

    # ⭐3 🟡 DÂY LƯNG
    340: {"name":"Thắt Lưng Sắt","slot":"belt","star":3,"stats":{"hp":80,"defense":4}},
    341: {"name":"Đai Lưng Chiến Binh","slot":"belt","star":3,"stats":{"hp":65,"defense":8}},

    # ⭐4 🟣 DÂY LƯNG
    440: {"name":"Dây Xích Titan","slot":"belt","star":4,"stats":{"hp":130,"defense":8}},
    441: {"name":"Thắt Lưng Rồng","slot":"belt","star":4,"stats":{"hp":110,"defense":12,"regen":3}},

    # ⭐5 🔴 DÂY LƯNG
    540: {"name":"🎗️ Hắc Long Yêu Đới","slot":"belt","star":5,"stats":{"hp":200,"defense":12}},
        541: {"name":"🎗️ Thiên Thạch Đới","slot":"belt","star":5,"stats":{"hp":170,"defense":18,"regen":5}},

    # ⭐6 💗 THẦN THOẠI DÂY LƯNG
    640: {"name":"🔗 Kim Long Tỏa","slot":"belt","star":6,"stats":{"hp":300,"defense":18,"regen":5}},
    641: {"name":"🔗 Phong Ấn Chi Liên","slot":"belt","star":6,"stats":{"hp":260,"defense":25,"reflect":8}},

    # ═══════ ⭐1 🔵 NHẪN (random all) ═══════
    150: {"name":"Nhẫn Đồng","slot":"ring","star":1,"stats":{"attack_min":1,"attack_max":2,"hp":5}},
    151: {"name":"Nhẫn Sắt","slot":"ring","star":1,"stats":{"defense":2,"hp":8}},
    152: {"name":"Nhẫn Đá","slot":"ring","star":1,"stats":{"attack_min":1,"attack_max":1,"defense":1,"hp":5}},

    # ⭐2 🟢 NHẪN
    250: {"name":"Nhẫn Ngọc Bích","slot":"ring","star":2,"stats":{"attack_min":3,"attack_max":5,"hp":15}},
    251: {"name":"Nhẫn Mã Não","slot":"ring","star":2,"stats":{"defense":4,"hp":20,"spd":1}},

    # ⭐3 🟡 NHẪN
    350: {"name":"Nhẫn Mắt Rắn","slot":"ring","star":3,"stats":{"attack_min":6,"attack_max":9,"defense":4,"crit":4}},
    351: {"name":"Nhẫn Lưu Ly","slot":"ring","star":3,"stats":{"attack_min":5,"attack_max":7,"hp":30,"spd":3}},

    # ⭐4 🟣 NHẪN
    450: {"name":"Nhẫn Hắc Ngọc","slot":"ring","star":4,"stats":{"attack_min":10,"attack_max":14,"hp":40,"spd":3}},
    451: {"name":"Nhẫn Ngọc Lục Bảo","slot":"ring","star":4,"stats":{"defense":10,"hp":50,"regen":5}},

    # ⭐5 🔴 NHẪN
    550: {"name":"💍 Kim Cương Huyết","slot":"ring","star":5,"stats":{"attack_min":15,"attack_max":22,"defense":8,"hp":60}},
    551: {"name":"💍 Nhẫn Phượng Hoàng","slot":"ring","star":5,"stats":{"attack_min":18,"attack_max":20,"hp":50,"crit":10,"spd":5}},

    # ⭐6 💗 THẦN THOẠI NHẪN
    650: {"name":"💎 Nhẫn Vũ Trụ","slot":"ring","star":6,"stats":{"attack_min":22,"attack_max":32,"defense":10,"hp":80,"spd":5,"crit":8}},
    651: {"name":"💎 Nhẫn Hủy Diệt","slot":"ring","star":6,"stats":{"attack_min":28,"attack_max":28,"hp":60,"pierce":20,"dodge":10}},
}


def get_drop() -> dict | None:
    import random
    total = sum(DROP_WEIGHTS.values())
    roll = random.randint(1, total)
    cumulative = 0
    for star, weight in DROP_WEIGHTS.items():
        cumulative += weight
        if roll <= cumulative:
            items = [e for eid, e in EQUIPMENT.items() if e["star"] == star]
            if items:
                chosen = random.choice(items)
                eid = [k for k, v in EQUIPMENT.items() if v == chosen][0]
                return {"eid": eid, "equip": chosen}
    return None
