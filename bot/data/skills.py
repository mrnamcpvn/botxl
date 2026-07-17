SKILLS_DB = {
    # ═══════ ATTACK SKILLS ═══════
    1: {"name":"👊 Cú Đấm Ba Que","desc":"Đòn cơ bản, CD thấp","category":"attack","type":"damage","multiplier":1.0,"cooldown":0,"price":0,"rarity":"common","icon":"👊"},
     2: {"name":"⚔️ Chém Treo Đầu Dê","desc":"2 đòn × 1.15x dmg","category":"attack","type":"multi_hit","hits":2,"multiplier":1.15,"cooldown":1,"price":2000,"rarity":"uncommon","icon":"⚔️"},
    3: {"name":"💀 Nổi Điên Bán Thịt Chó","desc":"3x dmg, tự mất 10% HP","category":"attack","type":"damage","multiplier":3.0,"self_dmg_pct":10,"cooldown":2,"price":3500,"rarity":"rare","icon":"💀"},
    4: {"name":"🌀 Đạp Bay Nón Bảo Hiểm","desc":"3 đòn × 1.15x, -30% DEF địch","category":"attack","type":"multi_hit","hits":3,"multiplier":1.15,"def_reduce_pct":30,"cooldown":2,"price":8000,"rarity":"epic","icon":"🌀"},
    # ═══════ SPECIAL SKILLS ═══════
    5: {"name":"🔥 Chọc Gậy Bánh Xe","desc":"2x dmg, 5% legendary 5x","category":"special","type":"damage","multiplier":2.0,"legendary_chance":5,"legendary_mult":5.0,"cooldown":3,"price":0,"rarity":"common","icon":"🔥"},
    6: {"name":"🩸 Hút Máu Bán Muỗi","desc":"2x dmg + hồi 50% dmg","category":"special","type":"lifesteal","multiplier":2.0,"lifesteal_pct":50,"cooldown":3,"price":3500,"rarity":"rare","icon":"🩸"},
    7: {"name":"🔥 Đốt Nhà Hàng Xóm","desc":"2x dmg + đốt 15%/2 turn","category":"special","type":"burn","multiplier":2.0,"burn_pct":15,"burn_turns":2,"cooldown":3,"price":3500,"rarity":"rare","icon":"🔥"},
    8: {"name":"🌑 Tắt Điện Đột Ngột","desc":"2.5x dmg + choáng 1 turn","category":"special","type":"stun","multiplier":2.5,"cooldown":4,"price":5000,"rarity":"epic","icon":"🌑"},
    9: {"name":"⚡ Sét Đánh Ngang Tai","desc":"5x dmg, xuyên 50% DEF","category":"special","type":"pierce","multiplier":5.0,"pierce_pct":50,"cooldown":4,"price":15000,"rarity":"legendary","icon":"⚡"},
    # ═══════ DEFENSE SKILLS ═══════
    10: {"name":"🛡️ Chống Xỏ Lá","desc":"×3 DEF + hồi 8% HP | CD:0","category":"defense","type":"defend","heal_pct":8,"cooldown":0,"price":0,"rarity":"common","icon":"🛡️"},
    11: {"name":"🔄 Gậy Ông Đập Lưng Ông","desc":"Giảm 80% dmg + phản 20% dmg","category":"defense","type":"counter","multiplier":0.2,"cooldown":3,"price":2500,"rarity":"uncommon","icon":"🔄"},
    12: {"name":"💚 Uống Thuốc Dỏm","desc":"Hồi 40% HP + xóa debuff","category":"defense","type":"heal","heal_pct":40,"cooldown":3,"price":3000,"rarity":"rare","icon":"💚"},
    13: {"name":"🛡️ Khiên Nồi Cơm Điện","desc":"Khiên 35% HP + hồi khi vỡ","category":"defense","type":"shield","shield_pct":35,"shield_turns":2,"shield_pop_heal":15,"cooldown":3,"price":6000,"rarity":"rare","icon":"🛡️"},
    # ═══════ PASSIVE SKILLS ═══════
    14: {"name":"❤️ Máu Chó Điên","desc":"+15% max HP vĩnh viễn","category":"passive","type":"stat_boost","stat":"hp_max","boost_pct":15,"price":0,"rarity":"common","icon":"❤️"},
    15: {"name":"⚔️ Tập Tạ Đồng Nát","desc":"+15% sát thương gây ra","category":"passive","type":"stat_boost","stat":"damage","boost_pct":15,"price":3000,"rarity":"rare","icon":"⚔️"},
    16: {"name":"🛡️ Mặc Áo Mưa Sắt","desc":"+30 DEF vĩnh viễn","category":"passive","type":"stat_boost","stat":"defense","boost_flat":30,"price":3000,"rarity":"rare","icon":"🛡️"},
    17: {"name":"💚 Nhỏ Nước Muối","desc":"Hồi 5% max HP mỗi turn","category":"passive","type":"regen","regen_pct":5,"price":3500,"rarity":"rare","icon":"💚"},
    18: {"name":"🍀 Vía Ông Địa","desc":"15% né đòn hoàn toàn","category":"passive","type":"dodge","dodge_chance":15,"price":4000,"rarity":"epic","icon":"🍀"},
    19: {"name":"💢 Điên Không Kịp Thở","desc":"Tích 50% dmg nhận → trả 2x","category":"passive","type":"rage","rage_pct":50,"rage_multiplier":2.0,"price":4000,"rarity":"epic","icon":"💢"},
    20: {"name":"💎 Chưa Chết Đã Sống Lại","desc":"HP<30%: giảm 50% dmg nhận","category":"passive","type":"last_stand","hp_threshold":30,"dmg_reduce_pct":50,"price":15000,"rarity":"legendary","icon":"💎"},
}

CATEGORY_LABELS = {"attack":"💥 Xỏ Lá","special":"🔥 Đặc Biệt","defense":"🛡️ Chống Xỏ Lá","passive":"💎 Bị Động"}
RARITY_COLORS = {"common":0x888888,"uncommon":0x00ff88,"rare":0x0088ff,"epic":0xaa00ff,"legendary":0xffaa00}
RARITY_STARS = {"common":"⭐","uncommon":"⭐⭐","rare":"⭐⭐⭐","epic":"⭐⭐⭐⭐","legendary":"⭐⭐⭐⭐⭐"}
SLOT_NAMES = {"weapon":"🗡️ Vũ Khí","armor":"🛡️ Giáp","accessory":"💍 Phụ Kiện","crown":"👑 Vương Miện"}