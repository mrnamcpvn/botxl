CLASSES = {
    "banxabong": {
        "name": "Bán Xà Bông", "icon": "🧼",
        "hp_base": 120, "hp_scale": 12,
        "atk_base": 12, "atk_scale": 3,
        "def_base": 10, "def_scale": 2,
        "desc": "Tập tễnh vào đời, đánh ai cũng được",
        "price": 0
    },
    "xola": {
        "name": "Xỏ Lá", "icon": "🤓",
        "hp_base": 200, "hp_scale": 20,
        "atk_base": 6, "atk_scale": 2,
        "def_base": 22, "def_scale": 6,
        "desc": "Siêu trâu, thủ giảm 20% dmg | +HP +DEF -ATK",
        "price": 5000,
        "perk": "defend_reduce"
    },
    "sieunhan": {
        "name": "Siêu Nhân Xà Phòng", "icon": "💪",
        "hp_base": 80, "hp_scale": 8,
        "atk_base": 22, "atk_scale": 6,
        "def_base": 4, "def_scale": 1,
        "desc": "Đòn đầu ×1.5 sát thương | +ATK -HP -DEF",
        "price": 5000,
        "perk": "first_strike"
    },
    "thaychua": {
        "name": "Thầy Chùa", "icon": "🙏",
        "hp_base": 90, "hp_scale": 9,
        "atk_base": 14, "atk_scale": 4,
        "def_base": 6, "def_scale": 2,
        "desc": "CD gốc tất cả skill -1 | skill hồi nhanh hơn",
        "price": 5000,
        "perk": "cd_reduce"
    },
    "muoi": {
        "name": "Con Muỗi", "icon": "🦟",
        "hp_base": 115, "hp_scale": 11,
        "atk_base": 16, "atk_scale": 4,
        "def_base": 6, "def_scale": 1,
        "desc": "Hút 80% dmg gây ra thành HP | +ATK +SPD",
        "price": 10000,
        "perk": "lifesteal_boost"
    },
    "chodien": {
        "name": "Chó Điên", "icon": "🐕",
        "hp_base": 150, "hp_scale": 15,
        "atk_base": 18, "atk_scale": 5,
        "def_base": 8, "def_scale": 2,
        "desc": "Càng đánh càng mạnh, rage ×2.5 | +HP +ATK",
        "price": 10000,
        "perk": "rage_boost"
    },
    "baque": {
        "name": "Ba Que", "icon": "🥢",
        "hp_base": 160, "hp_scale": 16,
        "atk_base": 10, "atk_scale": 3,
        "def_base": 18, "def_scale": 4,
        "desc": "Thoát chết ở 40% HP, giữ 1 máu | +HP +DEF",
        "price": 20000,
        "perk": "last_stand_boost"
    },
    "trumcuoi": {
        "name": "Trùm Cuối", "icon": "👑",
        "hp_base": 200, "hp_scale": 20,
        "atk_base": 20, "atk_scale": 6,
        "def_base": 18, "def_scale": 4,
        "desc": "Huyền thoại sống, cuối cùng vẫn là xỏ lá",
        "price": -1,
        "admin_only": True,
        "perk": "random_buff"
    },
}

PERK_DESCRIPTIONS = {
    "defend_reduce": "Nhận ít dmg hơn 20% nếu đang phòng thủ",
    "first_strike": "Đòn tấn công đầu trận ×1.5",
    "cd_reduce": "CD gốc tất cả skill giảm -1",
    "lifesteal_boost": "Hút máu +30% hiệu quả",
    "rage_boost": "Rage tích +50% nhanh hơn, sát thương rage ×2.5",
    "last_stand_boost": "Thoát chết kích hoạt ở 40% HP",
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
