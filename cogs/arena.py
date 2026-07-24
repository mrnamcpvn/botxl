import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
import time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PLAYERS_FILE = os.path.join(DATA_DIR, "players.json")
CHALLENGES_FILE = os.path.join(DATA_DIR, "challenges.json")
BATTLES_FILE = os.path.join(DATA_DIR, "battles.json")

# ─── VVIP Player ───
VIP_USER = 454923120986292224

# ─── WORST Player ───
WORST_USER = 857876295601225758

# ─── SKILLS DATABASE ───
SKILLS_DB = {
    # ═══════ ATTACK SKILLS (nút "Xỏ Lá") ═══════
    1: {"name":"👊 Cú Đấm Ba Que","desc":"Đòn cơ bản, CD thấp","category":"attack","type":"damage","multiplier":1.0,"cooldown":0,"price":0,"rarity":"common","icon":"👊"},
    2: {"name":"⚔️ Chém Treo Đầu Dê","desc":"2 đòn × 1.3x dmg","category":"attack","type":"multi_hit","hits":2,"multiplier":1.3,"cooldown":1,"price":200,"rarity":"uncommon","icon":"⚔️"},
    3: {"name":"💀 Nổi Điên Bán Thịt Chó","desc":"2.5x dmg, tự mất 15% HP","category":"attack","type":"damage","multiplier":2.5,"self_dmg_pct":15,"cooldown":2,"price":350,"rarity":"rare","icon":"💀"},
    4: {"name":"🌀 Đạp Bay Nón Bảo Hiểm","desc":"3 đòn × 1.1x, -30% DEF địch","category":"attack","type":"multi_hit","hits":3,"multiplier":1.1,"def_reduce_pct":30,"cooldown":2,"price":400,"rarity":"epic","icon":"🌀"},
    # ═══════ SPECIAL SKILLS (nút "Đặc Biệt") ═══════
    5: {"name":"🔥 Chọc Gậy Bánh Xe","desc":"3x dmg, 5% legendary 5x","category":"special","type":"damage","multiplier":3.0,"legendary_chance":5,"legendary_mult":5.0,"cooldown":3,"price":0,"rarity":"common","icon":"🔥"},
    6: {"name":"🩸 Hút Máu Bán Muỗi","desc":"2x dmg + hồi 50% dmg","category":"special","type":"lifesteal","multiplier":2.0,"lifesteal_pct":50,"cooldown":3,"price":350,"rarity":"rare","icon":"🩸"},
    7: {"name":"🔥 Đốt Nhà Hàng Xóm","desc":"2x dmg + đốt 10%/2 turn","category":"special","type":"burn","multiplier":2.0,"burn_pct":10,"burn_turns":2,"cooldown":4,"price":350,"rarity":"rare","icon":"🔥"},
    8: {"name":"🌑 Tắt Điện Đột Ngột","desc":"2.5x dmg + choáng 1 turn","category":"special","type":"stun","multiplier":2.5,"cooldown":5,"price":500,"rarity":"epic","icon":"🌑"},
    9: {"name":"⚡ Sét Đánh Ngang Tai","desc":"5x dmg, xuyên 50% DEF","category":"special","type":"pierce","multiplier":5.0,"pierce_pct":50,"cooldown":4,"price":700,"rarity":"legendary","icon":"⚡"},
    # ═══════ DEFENSE SKILLS (nút "Chống Xỏ Lá") ═══════
    10: {"name":"🛡️ Chống Xỏ Lá","desc":"×3 DEF + hồi 8% HP | CD:0","category":"defense","type":"defend","heal_pct":8,"cooldown":0,"price":0,"rarity":"common","icon":"🛡️"},
    11: {"name":"🔄 Gậy Ông Đập Lưng Ông","desc":"Miễn dmg + phản 2.5x","category":"defense","type":"counter","multiplier":2.5,"cooldown":3,"price":250,"rarity":"uncommon","icon":"🔄"},
     12: {"name":"💚 Uống Thuốc Dỏm","desc":"Hồi 20% HP + xóa debuff","category":"defense","type":"heal","heal_pct":20,"cooldown":4,"price":300,"rarity":"rare","icon":"💚"},
    13: {"name":"🛡️ Khiên Nồi Cơm Điện","desc":"Khiên 35% HP + hồi khi vỡ","category":"defense","type":"shield","shield_pct":35,"shield_turns":2,"shield_pop_heal":15,"cooldown":3,"price":300,"rarity":"rare","icon":"🛡️"},
    # ═══════ PASSIVE SKILLS (luôn active) ═══════
    14: {"name":"❤️ Máu Chó Điên","desc":"+15% max HP vĩnh viễn","category":"passive","type":"stat_boost","stat":"hp_max","boost_pct":15,"price":0,"rarity":"common","icon":"❤️"},
    15: {"name":"⚔️ Tập Tạ Đồng Nát","desc":"+15% sát thương gây ra","category":"passive","type":"stat_boost","stat":"damage","boost_pct":15,"price":300,"rarity":"rare","icon":"⚔️"},
    16: {"name":"🛡️ Mặc Áo Mưa Sắt","desc":"+20 DEF vĩnh viễn","category":"passive","type":"stat_boost","stat":"defense","boost_flat":20,"price":300,"rarity":"rare","icon":"🛡️"},
    17: {"name":"💚 Nhỏ Nước Muối","desc":"Hồi 5% max HP mỗi turn","category":"passive","type":"regen","regen_pct":5,"price":350,"rarity":"rare","icon":"💚"},
    18: {"name":"🍀 Vía Ông Địa","desc":"15% né đòn hoàn toàn","category":"passive","type":"dodge","dodge_chance":15,"price":400,"rarity":"epic","icon":"🍀"},
    19: {"name":"💢 Điên Không Kịp Thở","desc":"Tích 50% dmg nhận → trả 2x","category":"passive","type":"rage","rage_pct":50,"rage_multiplier":2.0,"price":400,"rarity":"epic","icon":"💢"},
    20: {"name":"💎 Chưa Chết Đã Sống Lại","desc":"HP<30%: giảm 50% dmg nhận","category":"passive","type":"last_stand","hp_threshold":30,"dmg_reduce_pct":50,"price":700,"rarity":"legendary","icon":"💎"},
}

CATEGORY_LABELS = {"attack":"💥 Xỏ Lá","special":"🔥 Đặc Biệt","defense":"🛡️ Chống Xỏ Lá","passive":"💎 Bị Động"}

RARITY_COLORS = {"common":0x888888,"uncommon":0x00ff88,"rare":0x0088ff,"epic":0xaa00ff,"legendary":0xffaa00}
RARITY_STARS = {"common":"⭐","uncommon":"⭐⭐","rare":"⭐⭐⭐","epic":"⭐⭐⭐⭐","legendary":"⭐⭐⭐⭐⭐"}

# ─── Default Stats ───
DEFAULT_STATS = {
    "hp":100,"hp_max":100,"attack_min":10,"attack_max":20,"defense":5,
    "wins":0,"losses":0,"damage_dealt":0,"damage_taken":0,
    "coins":0,"xp":0,"level":1,"stat_points":0,
    "inventory":{},"equipment_items":{},
    "equipped":{"weapon":None,"armor":None,"accessory":None,"crown":None},
    "buff":{},
    "skills_owned":[1,5,10,14],
    "skill_equipped":{"attack":1,"special":5,"defense":10,"passive":14},
    "attack_cd":0,"special_cd":0,"defense_cd":0,
}

VIP_STATS = {
    "hp":300,"hp_max":300,"attack_min":20,"attack_max":35,"defense":999,
    "wins":0,"losses":0,"damage_dealt":0,"damage_taken":0,
    "coins":0,"xp":0,"level":1,"stat_points":0,
    "inventory":{},"equipment_items":{},
    "equipped":{"weapon":None,"armor":None,"accessory":None,"crown":None},
    "buff":{},
    "skills_owned":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20],
    "skill_equipped":{"attack":4,"special":9,"defense":13,"passive":20},
    "attack_cd":0,"special_cd":0,"defense_cd":0,
}

WORST_STATS = {
    "hp":30,"hp_max":30,"attack_min":1,"attack_max":3,"defense":0,
    "wins":0,"losses":0,"damage_dealt":0,"damage_taken":0,
    "coins":0,"xp":0,"level":1,"stat_points":0,
    "inventory":{},"equipment_items":{},
    "equipped":{"weapon":None,"armor":None,"accessory":None,"crown":None},
    "buff":{},
    "skills_owned":[1,5,10,14],
    "skill_equipped":{"attack":1,"special":5,"defense":10,"passive":14},
    "attack_cd":0,"special_cd":0,"defense_cd":0,
}

# ─── SHOP ───
SHOP_ITEMS = {
    1:{"name":"🧪 Máu Gà","desc":"Hồi 50% HP","price":30,"type":"consumable","effect":{"hp_restore_percent":50}},
    2:{"name":"🧪 Máu Bò","desc":"Hồi full HP","price":60,"type":"consumable","effect":{"hp_restore_percent":100}},
    3:{"name":"⚡ Bùa Xỏ Lá","desc":"+30% dmg trận kế","price":80,"type":"consumable","effect":{"buff_attack_percent":30}},
    4:{"name":"🛡️ Giáp Chuối","desc":"+50% DEF trận kế","price":50,"type":"consumable","effect":{"buff_defense_percent":50}},
    5:{"name":"🎲 Xúc Xắc","desc":"×2 tỉ lệ legendary trận kế","price":100,"type":"consumable","effect":{"buff_lucky":True}},
    6:{"name":"🗡️ Gậy Chọc Bánh Xe","desc":"+8/+12 ATK","price":300,"type":"equipment","slot":"weapon","effect":{"attack_min":8,"attack_max":12}},
    7:{"name":"🛡️ Khiên Chống Xỏ Lá","desc":"+15 DEF","price":300,"type":"equipment","slot":"armor","effect":{"defense":15}},
    8:{"name":"❤️ Tim Ba Que","desc":"+50 max HP","price":350,"type":"equipment","slot":"accessory","effect":{"hp_max":50}},
    9:{"name":"👑 Vương Miện Xỏ Lá","desc":"+5/8 ATK +10 DEF +30 HP","price":800,"type":"equipment","slot":"crown","effect":{"attack_min":5,"attack_max":8,"defense":10,"hp_max":30}},
    # ─── SKILLS (shop item → skill_id) ───
    10:{"name":"⚔️ Chém Treo Đầu Dê [TẤN CÔNG]","desc":"2 đòn ×1.3x | CD:1","price":200,"type":"skill","skill_id":2},
    11:{"name":"💀 Nổi Điên Bán Thịt Chó [TẤN CÔNG]","desc":"2.5x dmg, -15% HP | CD:2","price":350,"type":"skill","skill_id":3},
    12:{"name":"🌀 Đạp Bay Nón Bảo Hiểm [TẤN CÔNG]","desc":"3 đòn, -30% DEF | CD:2","price":400,"type":"skill","skill_id":4},
    13:{"name":"🩸 Hút Máu Bán Muỗi [ĐẶC BIỆT]","desc":"2x dmg + hồi 50% | CD:3","price":350,"type":"skill","skill_id":6},
    14:{"name":"🔥 Đốt Nhà Hàng Xóm [ĐẶC BIỆT]","desc":"2x + đốt 10%/2t | CD:4","price":350,"type":"skill","skill_id":7},
    15:{"name":"🌑 Tắt Điện Đột Ngột [ĐẶC BIỆT]","desc":"2.5x + choáng | CD:5","price":500,"type":"skill","skill_id":8},
    16:{"name":"⚡ Sét Đánh Ngang Tai [ĐẶC BIỆT]","desc":"5x, xuyên 50% DEF | CD:4","price":700,"type":"skill","skill_id":9},
    17:{"name":"🔄 Gậy Ông Đập Lưng Ông [PHÒNG THỦ]","desc":"Miễn dmg + phản 2.5x | CD:3","price":250,"type":"skill","skill_id":11},
     18:{"name":"💚 Uống Thuốc Dỏm [PHÒNG THỦ]","desc":"Hồi 20% HP + xóa debuff | CD:4","price":300,"type":"skill","skill_id":12},
    19:{"name":"🛡️ Khiên Nồi Cơm Điện [PHÒNG THỦ]","desc":"Khiên 35%/2t + hồi khi vỡ | CD:3","price":300,"type":"skill","skill_id":13},
    20:{"name":"⚔️ Tập Tạ Đồng Nát [BỊ ĐỘNG]","desc":"+15% dmg","price":300,"type":"skill","skill_id":15},
    21:{"name":"🛡️ Mặc Áo Mưa Sắt [BỊ ĐỘNG]","desc":"+20 DEF","price":300,"type":"skill","skill_id":16},
    22:{"name":"💚 Nhỏ Nước Muối [BỊ ĐỘNG]","desc":"Hồi 5%/turn","price":350,"type":"skill","skill_id":17},
    23:{"name":"🍀 Vía Ông Địa [BỊ ĐỘNG]","desc":"15% né đòn","price":400,"type":"skill","skill_id":18},
    24:{"name":"💢 Điên Không Kịp Thở [BỊ ĐỘNG]","desc":"Tích dmg→trả 2x","price":400,"type":"skill","skill_id":19},
    25:{"name":"💎 Chưa Chết Đã Sống Lại [BỊ ĐỘNG]","desc":"HP<30%: -50% dmg","price":700,"type":"skill","skill_id":20},
}

SLOT_NAMES = {"weapon":"🗡️ Vũ Khí","armor":"🛡️ Giáp","accessory":"💍 Phụ Kiện","crown":"👑 Vương Miện"}

# ─── UTILS ───
HP_REGEN_RATE = 10
HP_REGEN_INTERVAL = 30

def regen_hp(pdata):
    now=time.time()
    last=pdata.get("last_hp_update",0)
    if last<=0:pdata["last_hp_update"]=now;return False
    elapsed=now-last
    if elapsed<HP_REGEN_INTERVAL:return False
    ticks=int(elapsed//HP_REGEN_INTERVAL)
    hp_gain=ticks*HP_REGEN_RATE
    old=pdata["hp"]
    pdata["hp"]=min(pdata["hp_max"],pdata["hp"]+hp_gain)
    pdata["last_hp_update"]=now
    return pdata["hp"]!=old

def load_json(path):
    if not os.path.exists(path):return {}
    with open(path,"r")as f:return json.load(f)

def save_json(path,data):
    os.makedirs(os.path.dirname(path),exist_ok=True)
    with open(path,"w")as f:json.dump(data,f,indent=2)

def get_player(user_id):
    players=load_json(PLAYERS_FILE)
    sid=str(user_id)
    if sid not in players:
        if user_id==VIP_USER:players[sid]=VIP_STATS.copy()
        elif user_id==WORST_USER:players[sid]=WORST_STATS.copy()
        else:players[sid]=DEFAULT_STATS.copy()
        players[sid]["last_hp_update"]=time.time()
        players[sid]["hp"]=players[sid]["hp_max"]
        save_json(PLAYERS_FILE,players)
    else:
        pdata=players[sid]
        for k in["skills_owned","skill_equipped","attack_cd","special_cd","defense_cd"]:
            if k not in pdata:
                if user_id==VIP_USER:
                    if k=="skills_owned":pdata[k]=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
                    elif k=="skill_equipped":pdata[k]={"attack":4,"special":9,"defense":13,"passive":20}
                    else:pdata[k]=0
                elif user_id==WORST_USER:
                    if k=="skills_owned":pdata[k]=[1,5,10,14]
                    elif k=="skill_equipped":pdata[k]={"attack":1,"special":5,"defense":10,"passive":14}
                    else:pdata[k]=0
                else:
                    if k=="skills_owned":pdata[k]=[1,5,10,14]
                    elif k=="skill_equipped":pdata[k]={"attack":1,"special":5,"defense":10,"passive":14}
                    else:pdata[k]=0
        if"last_hp_update"not in pdata:pdata["last_hp_update"]=time.time()
        regen_hp(pdata)
    return players[sid],players

def save_player(sid,data,players):
    players[sid]=data;save_json(PLAYERS_FILE,players)

async def resolve_member(guild,user_id):
    try:return await guild.fetch_member(user_id)
    except:return guild.get_member(user_id)

def calc_level(xp):
    level=1
    while xp>=level*80:xp-=level*80;level+=1
    return level,xp

def reward_player(sid,players,winner=True,is_vip_opponent=False,is_worst_opponent=False):
    pdata=players[sid]
    if winner:
        base_coins=50;base_xp=25
        if is_vip_opponent:base_coins*=2;base_xp*=2
        elif is_worst_opponent:base_coins=max(5,base_coins//2);base_xp=max(5,base_xp//2)
    else:base_coins=10;base_xp=5
    pdata["coins"]=pdata.get("coins",0)+base_coins
    pdata["xp"]=pdata.get("xp",0)+base_xp
    old=pdata.get("level",1)
    new_level,_=calc_level(pdata["xp"])
    pdata["level"]=new_level
    if new_level>old:pdata["stat_points"]=pdata.get("stat_points",0)+((new_level-old)*3)
    return base_coins,base_xp,old!=new_level

def get_passive_bonus(pdata):
    """Apply passive skill bonuses to effective stats."""
    pid=pdata.get("skill_equipped",{}).get("passive")
    skill=SKILLS_DB.get(pid)
    bonuses={"hp_max":0,"damage_pct":0,"defense_flat":0}
    if not skill or skill["category"]!="passive":return bonuses
    if skill["type"]=="stat_boost":
        if skill.get("stat")=="hp_max":bonuses["hp_max"]=int(pdata["hp_max"]*skill["boost_pct"]/100)
        elif skill.get("stat")=="damage":bonuses["damage_pct"]=skill["boost_pct"]
        elif skill.get("stat")=="defense":bonuses["defense_flat"]=skill.get("boost_flat",0)
    return bonuses

def get_effective_stats(pdata):
    stats={
        "hp":pdata["hp"],"hp_max":pdata["hp_max"],
        "attack_min":pdata["attack_min"],"attack_max":pdata["attack_max"],
        "defense":pdata["defense"],
    }
    equipped=pdata.get("equipped",{})
    for slot,item_id in equipped.items():
        if item_id and item_id in SHOP_ITEMS:
            for k,v in SHOP_ITEMS[item_id]["effect"].items():
                if k in stats:stats[k]+=v
    pbonus=get_passive_bonus(pdata)
    stats["hp_max"]+=pbonus["hp_max"]
    stats["defense"]+=pbonus["defense_flat"]
    return stats,pbonus

def get_equipped_skill(pdata,category):
    sid=pdata.get("skill_equipped",{}).get(category)
    return SKILLS_DB.get(sid,SKILLS_DB.get(1))

# ─── STATS EMBED ───
def stats_embed(title,player_data,user):
    embed=discord.Embed(title=title,color=0x00ff88)
    embed.set_thumbnail(url=user.display_avatar.url)
    eff,pbonus=get_effective_stats(player_data)

    hp_bar="🟩"*(player_data["hp"]//10)+"⬜"*((eff["hp_max"]-player_data["hp"])//10)
    if len(hp_bar)>20:hp_bar=hp_bar[:20]
    hp_line=f"`{player_data['hp']}/{eff['hp_max']}`\n{hp_bar}"
    if player_data["hp"]<eff["hp_max"]:hp_line+=f"\n💤 Hồi **{HP_REGEN_RATE} HP**/{HP_REGEN_INTERVAL}s..."
    bonus_hp=eff["hp_max"]-player_data["hp_max"]
    if bonus_hp>0:hp_line+=f"\n🟢 (+{bonus_hp} từ t.bị/bị động)"
    embed.add_field(name="❤️ HP",value=hp_line,inline=False)

    atk_line=f"`{eff['attack_min']} - {eff['attack_max']}`"
    bonus_atk_min=eff["attack_min"]-player_data["attack_min"]
    bonus_atk_max=eff["attack_max"]-player_data["attack_max"]
    if bonus_atk_min>0 or bonus_atk_max>0:atk_line+=f"\n🟢 (+{bonus_atk_min}/+{bonus_atk_max})"
    if pbonus["damage_pct"]>0:atk_line+=f"\n💎 Bị động: +{pbonus['damage_pct']}% dmg"
    embed.add_field(name="⚔️ Lực Xỏ Lá",value=atk_line,inline=True)

    def_line=f"`{eff['defense']}`"
    bonus_def=eff["defense"]-player_data["defense"]
    if bonus_def>0:def_line+=f"\n🟢 (+{bonus_def})"
    embed.add_field(name="🛡️ Lì Đòn",value=def_line,inline=True)

    # Show all 4 skills
    skill_parts=[]
    for cat in["attack","special","defense","passive"]:
        sk=get_equipped_skill(player_data,cat)
        cat_icon={"attack":"💥","special":"🔥","defense":"🛡️","passive":"💎"}[cat]
        if cat=="passive":
            skill_parts.append(f"{cat_icon} {sk['icon']} **{sk['name']}** {RARITY_STARS.get(sk['rarity'],'⭐')}\n　└ _{sk['desc']}_")
        else:
            cd_val=player_data.get(f"{cat}_cd",0)
            cd_str="✅ Sẵn sàng" if cd_val<=0 else f"⏳ CD: `{cd_val}`"
            skill_parts.append(f"{cat_icon} {sk['icon']} **{sk['name']}** {RARITY_STARS.get(sk['rarity'],'⭐')}\n　└ {sk['desc']} | {cd_str}")
    embed.add_field(name="🔥 Kỹ Năng (4/4)",value="\n\n".join(skill_parts),inline=False)

    total_xp=player_data.get("xp",0);level=player_data.get("level",1)
    temp_xp=total_xp;temp_lvl=1
    while temp_lvl<level and temp_xp>=temp_lvl*80:temp_xp-=temp_lvl*80;temp_lvl+=1
    xp_in_level=temp_xp;xp_needed=level*80
    bar_filled=min(10,xp_in_level*10//xp_needed)if xp_needed>0 else 0
    xp_bar="🟦"*bar_filled+"⬜"*(10-bar_filled)
    embed.add_field(name="📊 Cấp Độ",value=f"`Lv.{level}` | 💰 `{player_data.get('coins',0)} coins`",inline=True)
    embed.add_field(name="🔮 Kinh Nghiệm",value=f"`{xp_in_level}/{xp_needed}`\n{xp_bar}",inline=True)
    embed.add_field(name="🏆 Thành Tích",value=f"Thắng:`{player_data['wins']}` Thua:`{player_data['losses']}`",inline=False)

    sp=player_data.get("stat_points",0)
    if sp>0:embed.add_field(name="⭐ Điểm Thuộc Tính",value=f"**{sp} điểm**! Dùng `/upgrade <hp/atk/def>`",inline=False)

    buff=player_data.get("buff",{})
    if buff:
        bl=[]
        if buff.get("attack_boost"):bl.append(f"⚡ +{buff['attack_boost']}% dmg")
        if buff.get("defense_boost"):bl.append(f"🛡️ +{buff['defense_boost']}% DEF")
        if buff.get("lucky"):bl.append("🎲 ×2 tỉ lệ legendary")
        if bl:embed.add_field(name="🔮 Buff Trận Kế",value="\n".join(bl),inline=False)

    if user.id==VIP_USER:embed.set_footer(text="👑 VIP - Full Chưa Chết Đã Sống Lại!",icon_url=user.display_avatar.url)
    elif user.id==WORST_USER:embed.set_footer(text="🐔 Gà Xoài - Không giáp, chỉ có ăn đòn!",icon_url=user.display_avatar.url)
    return embed


# ─── BATTLE VIEW ───
class BattleView(discord.ui.View):
    def __init__(self,cog,turn_sid,turn_name,atk_label="Xỏ Lá",sp_label="Đặc Biệt",def_label="Chống Xỏ Lá",seconds=15):
        super().__init__(timeout=None)
        self.cog=cog;self.turn_sid=turn_sid;self.turn_name=turn_name
        self.seconds=seconds;self.remaining=seconds
        self._timer_task=None;self._stopped=False
        # Set button labels
        self.attack_btn.label=atk_label[:80]if len(atk_label)>80 else atk_label
        self.special_btn.label=sp_label[:80]if len(sp_label)>80 else sp_label
        self.defend_btn.label=def_label[:80]if len(def_label)>80 else def_label

    def start_countdown(self):
        if self._timer_task is None:self._timer_task=asyncio.create_task(self._run_countdown())

    def stop(self):
        self._stopped=True
        if self._timer_task and not self._timer_task.done():self._timer_task.cancel()
        super().stop()

    async def _run_countdown(self):
        for remaining in range(self.seconds,-1,-3):
            if self._stopped:return
            self.remaining=remaining
            if self.message and not self._stopped:
                try:
                    embed=self.message.embeds[0]if self.message.embeds else None
                    if embed:
                        bar_filled=remaining*10//self.seconds;bar="🟩"*bar_filled+"⬜"*(10-bar_filled)
                        footer=f"⏳ Còn {remaining}s — {bar} — {self.turn_name}"if remaining>5 else(f"⚠️ Còn {remaining}s! {bar} — Nhanh lên!"if remaining>0 else"⏰ HẾT GIỜ!")
                        embed.set_footer(text=footer)
                        await self.message.edit(embed=embed)
                except:pass
            if remaining>0:await asyncio.sleep(3)
            else:break
        if not self._stopped:
            self._stopped=True
            await self._handle_timeout()

    async def _handle_timeout(self):
        battles=load_json(BATTLES_FILE)
        if self.turn_sid not in battles:return
        battle=battles[self.turn_sid]
        if not battle["active"]:return
        if battle["turn"]!=self.turn_sid:return
        loser_id=self.turn_sid
        winner_id=battle["player1"]if battle["player2"]==loser_id else battle["player2"]
        guild=None
        if self.message and self.message.guild:guild=self.message.guild
        if not guild:battle["active"]=False;battles[battle["player1"]]=battle;battles[battle["player2"]]=battle;save_json(BATTLES_FILE,battles);return
        loser_m=await resolve_member(guild,int(loser_id))
        winner_m=await resolve_member(guild,int(winner_id))
        loser_name=loser_m.display_name if loser_m else f"Unknown"
        winner_name=winner_m.display_name if winner_m else f"Unknown"
        winner_data,players=get_player(int(winner_id))
        loser_data=players[loser_id]
        loser_data["hp"]=0;loser_data["last_hp_update"]=time.time()
        loser_data["losses"]=loser_data.get("losses",0)+1
        winner_data["wins"]=winner_data.get("wins",0)+1
        is_vip=(int(loser_id)==VIP_USER);is_worst=(int(loser_id)==WORST_USER)
        w_coins,w_xp,w_lvlup=reward_player(winner_id,players,True,is_vip,is_worst)
        l_coins,l_xp,l_lvlup=reward_player(loser_id,players,False)
        save_player(winner_id,winner_data,players);save_player(loser_id,loser_data,players)
        for k in list(battles.keys()):
            if k==battle["player1"]or k==battle["player2"]:del battles[k]
        save_json(BATTLES_FILE,battles)
        lines=[
            f"⏰ **{loser_name}** hết giờ!",
            f"🏆 **{winner_name}** CHIẾN THẮNG! 🎉",
            f"💰 {winner_name}: +{w_coins}🪙 +{w_xp}XP{' ⬆️LEVEL UP!'if w_lvlup else''}",
            f"💰 {loser_name}: +{l_coins}🪙(an ủi) +{l_xp}XP{' ⬆️LEVEL UP!'if l_lvlup else''}",
        ]
        embed=discord.Embed(title="⚔️ KẾT THÚC (HẾT GIỜ)",description="\n".join(lines),color=0xffd700)
        try:await self.message.edit(embed=embed,view=None)
        except:
            ch=self.cog.bot.get_channel(int(battle["channel_id"]))
            if ch:await ch.send(embed=embed)

    async def interaction_check(self,interaction):
        if str(interaction.user.id)!=self.turn_sid:
            await interaction.response.send_message("⏳ Chưa tới lượt mày! 🤡",ephemeral=True);return False
        return True

    @discord.ui.button(emoji="💥",label="Tấn Công",style=discord.ButtonStyle.danger)
    async def attack_btn(self,interaction,button):
        await self._handle_move(interaction,"attack")

    @discord.ui.button(emoji="🔥",label="Đặc Biệt",style=discord.ButtonStyle.primary)
    async def special_btn(self,interaction,button):
        await self._handle_move(interaction,"special")

    @discord.ui.button(emoji="🛡️",label="Chống Xỏ Lá",style=discord.ButtonStyle.success)
    async def defend_btn(self,interaction,button):
        await self._handle_move(interaction,"defense")

    async def _handle_move(self,interaction,move_type):
        guild=interaction.guild;user_id=interaction.user.id;sid=str(user_id)
        battles=load_json(BATTLES_FILE)
        if sid not in battles:await interaction.response.send_message("🤷 Không có trận nào!",ephemeral=True);return
        battle=battles[sid]
        if not battle["active"]:await interaction.response.send_message("⚠️ Trận đã kết thúc!",ephemeral=True);return
        pdata,_=get_player(user_id)
        cd_key=f"{move_type}_cd"
        if pdata.get(cd_key,0)>0:
            sk=get_equipped_skill(pdata,move_type if move_type!="defense"else"defense")
            await interaction.response.send_message(f"⏳ **{sk['name']}** đang hồi! Còn **{pdata[cd_key]}** turn!",ephemeral=True);return
        await interaction.response.defer()
        self.stop()
        result=await self.cog._execute_battle_core(guild,battle,user_id,move_type)
        if result is None:await interaction.edit_original_response(content="❌ Lỗi!",embed=None,view=None);return
        embed,view,finished=result
        await interaction.edit_original_response(embed=embed,view=view)
        if view and not finished:view.start_countdown()


# ─── CHALLENGE VIEW ───
class ChallengeView(discord.ui.View):
    def __init__(self,cog,target_sid,challenger_sid,challenger_name,target_name,channel_id):
        super().__init__(timeout=30)
        self.cog=cog;self.target_sid=target_sid;self.challenger_sid=challenger_sid
        self.challenger_name=challenger_name;self.target_name=target_name;self.channel_id=channel_id
        self.used=False

    async def interaction_check(self,interaction):
        if str(interaction.user.id)!=self.target_sid:
            await interaction.response.send_message("🤡 Có phải mày đâu!",ephemeral=True);return False
        return True

    async def on_timeout(self):
        if self.used:return
        self.used=True
        challenges=load_json(CHALLENGES_FILE)
        if self.target_sid not in challenges:return
        del challenges[self.target_sid];save_json(CHALLENGES_FILE,challenges)
        pdata,players=get_player(int(self.target_sid))
        pdata["coins"]=max(0,pdata.get("coins",0)-20)
        save_player(self.target_sid,pdata,players)
        ch=self.cog.bot.get_channel(int(self.channel_id))
        if ch:await ch.send(f"⏰ **{self.target_name}** hết giờ! -20🪙 vì hèn! 🏃")

    @discord.ui.button(emoji="✅",label="Nhận Lời",style=discord.ButtonStyle.success)
    async def accept_btn(self,interaction,button):
        if self.used:return
        self.used=True;await self._do_accept(interaction)

    @discord.ui.button(emoji="❌",label="Từ Chối",style=discord.ButtonStyle.danger)
    async def deny_btn(self,interaction,button):
        if self.used:return
        self.used=True;await self._do_deny(interaction)

    async def _do_accept(self,interaction):
        await interaction.response.defer()
        challenges=load_json(CHALLENGES_FILE)
        if self.target_sid not in challenges:await interaction.followup.send("🤷 Hết hạn!",ephemeral=True);return
        guild=interaction.guild
        challenger=await resolve_member(guild,int(self.challenger_sid))
        target=await resolve_member(guild,int(self.target_sid))
        if not challenger or not target:await interaction.followup.send("❌ Bay khỏi server!",ephemeral=True);del challenges[self.target_sid];save_json(CHALLENGES_FILE,challenges);return
        battles=load_json(BATTLES_FILE)
        p1_data,players=get_player(self.challenger_sid)
        p2_data=players[self.target_sid]
        if p1_data["hp"]<=0 or p2_data["hp"]<=0:
            z=challenger.display_name if p1_data["hp"]<=0 else target.display_name
            await interaction.followup.send(f"💀 **{z}** 0 máu!",ephemeral=True);del challenges[self.target_sid];save_json(CHALLENGES_FILE,challenges);return
        p1_data["hp"]=p1_data["hp_max"];p2_data["hp"]=p2_data["hp_max"]
        for p in[p1_data,p2_data]:
            p["attack_cd"]=0;p["special_cd"]=0;p["defense_cd"]=0
            for kb in["_burn","_shield_hp","_shield_pop_heal","_counter","_counter_immune","_rage_dmg","_def_reduced"]:p.pop(kb,None)
        save_player(self.challenger_sid,p1_data,players);save_player(self.target_sid,p2_data,players)
        first=self.challenger_sid if random.random()<(0.6 if int(self.target_sid)==VIP_USER else 0.5)else self.target_sid
        battle_data={
            "player1":self.challenger_sid,"player2":self.target_sid,"turn":first,
            "p1_defending":False,"p2_defending":False,"p1_stunned":False,"p2_stunned":False,
            "channel_id":self.channel_id,"active":True,"last_move":time.time(),
        }
        battles[self.target_sid]=battle_data;battles[self.challenger_sid]=battle_data
        save_json(BATTLES_FILE,battles)
        del challenges[self.target_sid];save_json(CHALLENGES_FILE,challenges)

        turn_user=challenger if first==self.challenger_sid else target
        turn_pdata=p1_data if first==self.challenger_sid else p2_data
        ask=get_equipped_skill(turn_pdata,"attack")
        ssk=get_equipped_skill(turn_pdata,"special")
        dsk=get_equipped_skill(turn_pdata,"defense")

        embed=discord.Embed(title="⚔️ TRẬN CHIẾN BẮT ĐẦU!",color=0xff6600,
            description=f"**{challenger.display_name}** ⚔️ **{target.display_name}**\n🎲 **{turn_user.display_name}** đi trước!\n━━━━━━━━━━━\n"
                       f"❤️ {challenger.display_name}:`{p1_data['hp']}/{p1_data['hp_max']}`\n"
                       f"❤️ {target.display_name}:`{p2_data['hp']}/{p2_data['hp_max']}`")
        view=BattleView(self.cog,first,turn_user.display_name,ask["name"],ssk["name"],dsk["name"])
        await interaction.edit_original_response(embed=embed,view=view)
        view.start_countdown()

    async def _do_deny(self,interaction):
        await interaction.response.defer()
        challenges=load_json(CHALLENGES_FILE)
        if self.target_sid not in challenges:await interaction.followup.send("🤷 Hết hạn!",ephemeral=True);return
        del challenges[self.target_sid];save_json(CHALLENGES_FILE,challenges)
        pdata,players=get_player(int(self.target_sid))
        pdata["coins"]=max(0,pdata.get("coins",0)-20);save_player(self.target_sid,pdata,players)
        embed=discord.Embed(title="🏃 NHÁT! 💸",color=0x888888,
            description=f"**{self.target_name}** từ chối **{self.challenger_name}**! -20🪙!")
        await interaction.edit_original_response(embed=embed,view=None)


# ─── ARENA COG ───
class Arena(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self._cleanup_stale_sync()
        self._cleanup_task=None

    async def cog_load(self):self._cleanup_task=asyncio.create_task(self._stuck_battle_cleanup_loop())
    async def cog_unload(self):
        if self._cleanup_task:self._cleanup_task.cancel()

    def _cleanup_stale_sync(self):
        try:
            battles=load_json(BATTLES_FILE)
            stale=[k for k,v in battles.items()if not v.get("active")and time.time()-v.get("last_move",0)>300]
            for k in stale:del battles[k]
            if stale:save_json(BATTLES_FILE,battles)
        except:pass

    async def _stuck_battle_cleanup_loop(self):
        await self.bot.wait_until_ready()
        while True:
            try:await asyncio.sleep(15);await self._cleanup_stuck_battles()
            except asyncio.CancelledError:break
            except Exception as e:print(f"[CLEANUP] {e}")

    async def _cleanup_stuck_battles(self):
        battles=load_json(BATTLES_FILE)
        if not battles:return
        now=time.time();cleaned=set();to_cancel=[]
        for sid,battle in list(battles.items()):
            bk=(battle.get("player1"),battle.get("player2"))
            if bk in cleaned:continue
            if not battle.get("active"):cleaned.add(bk);continue
            if now-battle.get("last_move",0)>20:to_cancel.append((battle,bk));cleaned.add(bk)
        if not to_cancel:return
        for battle,bk in to_cancel:
            p1_id,p2_id=battle["player1"],battle["player2"]
            loser_id=battle.get("turn",p1_id)
            winner_id=p2_id if loser_id==p1_id else p1_id
            ch=self.bot.get_channel(int(battle.get("channel_id",0)))
            battle["active"]=False
            wd,players=get_player(int(winner_id));ld=players[loser_id]
            ld["losses"]=ld.get("losses",0)+1;wd["wins"]=wd.get("wins",0)+1
            is_vip=(int(loser_id)==VIP_USER);is_worst=(int(loser_id)==WORST_USER)
            reward_player(winner_id,players,True,is_vip,is_worst)
            reward_player(loser_id,players,False)
            save_player(winner_id,wd,players);save_player(loser_id,ld,players)
            for k in list(battles.keys()):
                if k==p1_id or k==p2_id:del battles[k]
            if ch:
                try:await ch.send(f"🧹 Trận kẹt <@{p1_id}> vs <@{p2_id}> tự hủy!\n🏆 <@{winner_id}> thắng, 💀 <@{loser_id}> thua.")
                except:pass
        save_json(BATTLES_FILE,battles)

    # ─── HELP ───
    @commands.command(name="help")
    async def help_cmd(self,ctx):
        embed=discord.Embed(title="⚔️ Đấu Trường Ba Que Xỏ Lá",color=0xff6600,
            description="Game đấm nhau bằng xỏ lá, khịa nhau, chọc gậy bánh xe!")
        embed.add_field(name="📝 Cơ Bản",value="`!register` `!stats` `!upgrade <hp/atk/def>` `!leaderboard`",inline=False)
        embed.add_field(name="⚔️ Đấm Nhau",value="`!challenge @player` → bấm nút ✅/❌\nBấm 💥🔥🛡️ khi tới lượt (15s)\nTừ chối/hết giờ: -20🪙",inline=False)
        embed.add_field(name="🏪 Shop",value="`!shop` `!buy <số>` `!use <số>` `!equip <số>` `!inv`",inline=False)
        embed.add_field(name="🔥 Kỹ Năng (4 slot)",value="`!skills` — Xem 20 skill\n`!buyskill <số>` — Mua skill\n`!equipskill <loại> <số>` — Gán skill\n　VD:`!equipskill attack 2` → gán Chém Treo Đầu Dê vào nút 💥",inline=False)
        embed.set_footer(text="13 skill chủ động + 7 bị động | Mỗi người 4 skill riêng!")
        await ctx.send(embed=embed)

    # ─── REGISTER ───
    @commands.command(name="register")
    async def register(self,ctx):
        players=load_json(PLAYERS_FILE)
        if str(ctx.author.id)in players:await ctx.reply(f"🤷 {ctx.author.display_name} đăng ký rồi! `/stats`");return
        _,players=get_player(ctx.author.id)
        msg=f"✅ **{ctx.author.display_name}** đăng ký thành công! 💪 Cày lên!"
        if ctx.author.id==VIP_USER:msg="👑 VIP FULL GIÁP BẤT TỬ!"
        elif ctx.author.id==WORST_USER:msg="🐔 GÀ XOÀI KHÔNG GIÁP!"
        await ctx.reply(msg)

    # ─── STATS ───
    @commands.command(name="stats")
    async def stats(self,ctx,member:discord.Member=None):
        target=member or ctx.author
        pdata,_=get_player(target.id)
        embed=stats_embed(f"📊 Chỉ Số {target.display_name}",pdata,target)
        await ctx.send(embed=embed)

    @stats.error
    async def stats_error(self,ctx,error):
        if isinstance(error,commands.BadArgument):await ctx.reply("❌ Tìm không ra!")

    # ─── UPGRADE ───
    @commands.command(name="upgrade",aliases=["nang","+"])
    async def upgrade(self,ctx,stat:str=None):
        if not stat:
            pdata,_=get_player(ctx.author.id)
            sp=pdata.get("stat_points",0)
            await ctx.send(embed=discord.Embed(title="⭐ Nâng Chỉ Số",color=0x00aaff,
                description=f"**{sp} điểm**\n`!upgrade hp` +10 HP\n`!upgrade atk` +2~3 ATK\n`!upgrade def` +2 DEF"));return
        stat=stat.lower().strip()
        if stat not in("hp","atk","def"):await ctx.reply("❌ !upgrade để xem hướng dẫn");return
        pdata,players=get_player(ctx.author.id)
        sp=pdata.get("stat_points",0)
        if sp<1:await ctx.reply("😅 Hết điểm! Đánh nhau lên cấp đi.");return
        if stat=="hp":pdata["hp_max"]+=10;pdata["hp"]+=10;sn="❤️ HP"
        elif stat=="atk":pdata["attack_min"]+=2;pdata["attack_max"]+=3;sn="⚔️ ATK"
        else:pdata["defense"]+=2;sn="🛡️ DEF"
        pdata["stat_points"]=sp-1
        save_player(str(ctx.author.id),pdata,players)
        await ctx.send(embed=discord.Embed(title="⬆️ NÂNG THÀNH CÔNG!",color=0x00ff88,
            description=f"**{sn}** đã tăng! Còn **{sp-1} điểm**."))

    # ─── TEXT FALLBACKS ───
    @commands.command(name="attack",aliases=["xola","xl"])
    async def attack_cmd(self,ctx):
        await self._text_fallback(ctx,"attack")
    @commands.command(name="special",aliases=["dacbiet","db"])
    async def special_cmd(self,ctx):
        await self._text_fallback(ctx,"special")
    @commands.command(name="defend",aliases=["phongthu","pt","thu"])
    async def defend_cmd(self,ctx):
        await self._text_fallback(ctx,"defense")

    async def _text_fallback(self,ctx,move_type):
        battles=load_json(BATTLES_FILE);sid=str(ctx.author.id)
        if sid not in battles:await ctx.reply("🤷 Không có trận!");return
        battle=battles[sid]
        if not battle["active"]:await ctx.reply("⚠️ Trận đã kết thúc!");return
        if battle["turn"]!=sid:await ctx.reply("⏳ Chưa tới lượt! 🤡");return
        pdata,_=get_player(ctx.author.id)
        cd_key=f"{move_type}_cd"
        if pdata.get(cd_key,0)>0:
            cat="defense"if move_type=="defense"else move_type
            sk=get_equipped_skill(pdata,cat)
            await ctx.reply(f"⏳ **{sk['name']}** đang hồi! {pdata[cd_key]} turn.");return
        result=await self._execute_battle_core(ctx.guild,battle,ctx.author.id,move_type)
        if result is None:await ctx.reply("❌ Lỗi!");return
        embed,view,finished=result
        await ctx.send(embed=embed,view=view)
        if view and not finished:view.start_countdown()

    # ─── SKILLS COMMAND ───
    @commands.command(name="skills",aliases=["skill","kynang"])
    async def skills_cmd(self,ctx):
        await self._show_skills(ctx,ctx.author,"!")

    async def _show_skills(self,ctx_or_int,user,prefix):
        pdata,_=get_player(user.id)
        owned=pdata.get("skills_owned",[1,5,10,14])
        equipped=pdata.get("skill_equipped",{"attack":1,"special":5,"defense":10,"passive":14})
        coins=pdata.get("coins",0)

        embed=discord.Embed(title="🔥 KHO KỸ NĂNG (20 SKILL)",color=0xff6600,
            description=f"💰 **{coins} coins** | 4 slot: 💥TấnCông 🔥ĐặcBiệt 🛡️PhòngThủ 💎BịĐộng\n{prefix}buyskill <số> | {prefix}equipskill <loại> <số>")

        for cat in["attack","special","defense","passive"]:
            skills_in_cat=[(sid,s)for sid,s in SKILLS_DB.items()if s["category"]==cat]
            lines=[]
            for sid,sk in skills_in_cat:
                stars=RARITY_STARS.get(sk["rarity"],"⭐")
                is_o=sid in owned;is_e=equipped.get(cat)==sid
                s="✅ ĐANG DÙNG"if is_e else("📦 CÓ"if is_o else f"🪙{sk['price']}")
                cd_text = f"CD:`{sk['cooldown']}`" if 'cooldown' in sk else "💎 BỊ ĐỘNG"
                lines.append(f"`{sid}` {sk['icon']} **{sk['name']}** {stars} | {cd_text} | {s}\n　└ {sk['desc']}")
            embed.add_field(name=f"{CATEGORY_LABELS[cat]}",value="\n".join(lines),inline=False)

        if isinstance(ctx_or_int,discord.ext.commands.Context):
            await ctx_or_int.send(embed=embed)
        else:
            await ctx_or_int.response.send_message(embed=embed)

    # ─── BUYSKILL ───
    @commands.command(name="buyskill",aliases=["muakynang"])
    async def buyskill_cmd(self,ctx,skill_id:str=None):
        await self._buyskill(ctx,ctx.author,skill_id,"!")

    async def _buyskill(self,ctx_or_int,user,skill_id,prefix):
        if not skill_id:
            m=f"❌ {prefix}buyskill <số> để mua! Xem {prefix}skills"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        try:sid=int(skill_id.strip())
        except:
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply("❌ Số!")
            else:await ctx_or_int.response.send_message("❌ Số!",ephemeral=True);return
        if sid not in SKILLS_DB:
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(f"❌ Không có skill {sid}!")
            else:await ctx_or_int.response.send_message(f"❌ Không có skill {sid}!",ephemeral=True);return
        sk=SKILLS_DB[sid]
        if sk["price"]==0:
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply("🤷 Skill miễn phí, có sẵn rồi!")
            else:await ctx_or_int.response.send_message("🤷 Miễn phí!",ephemeral=True);return
        pdata,players=get_player(user.id)
        owned=pdata.get("skills_owned",[1,5,10,14])
        if sid in owned:
            m=f"📦 Đã có {sk['name']}! Dùng {prefix}equipskill"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        coins=pdata.get("coins",0)
        if coins<sk["price"]:
            m=f"😅 Nghèo! Cần {sk['price']}🪙, có {coins}🪙"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        pdata["coins"]=coins-sk["price"];owned.append(sid);pdata["skills_owned"]=owned
        save_player(str(user.id),pdata,players)
        stars=RARITY_STARS.get(sk["rarity"],"⭐")
        m=f"✅ Mua **{sk['icon']} {sk['name']}** {stars}!\n💰 Còn {pdata['coins']}🪙 | {prefix}equipskill {sk['category']} {sid}"
        if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
        else:await ctx_or_int.response.send_message(m)

    # ─── EQUIPSKILL ───
    @commands.command(name="equipskill",aliases=["trangbikynang"])
    async def equipskill_cmd(self,ctx,category:str=None,skill_id:str=None):
        await self._equipskill(ctx,ctx.author,category,skill_id,"!")

    async def _equipskill(self,ctx_or_int,user,category,skill_id,prefix):
        cats=["attack","special","defense","passive"]
        if not category or category not in cats:
            m=f"❌ Dùng: {prefix}equipskill <loại> <số>\nLoại: attack / special / defense / passive"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        if not skill_id:
            pdata,_=get_player(user.id);eq=pdata.get("skill_equipped",{})
            sk=SKILLS_DB.get(eq.get(category),SKILLS_DB[1])
            m=f"🔥 {CATEGORY_LABELS[category]}: **{sk['icon']} {sk['name']}**\n{prefix}equipskill {category} <số>"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        try:sid=int(skill_id.strip())
        except:
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply("❌ Số!");return
            else:await ctx_or_int.response.send_message("❌ Số!",ephemeral=True);return
        if sid not in SKILLS_DB:
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(f"❌ Không có skill {sid}!");return
            else:await ctx_or_int.response.send_message(f"❌ Không có skill {sid}!",ephemeral=True);return
        sk=SKILLS_DB[sid]
        if sk["category"]!=category:
            m=f"❌ Skill {sid} thuộc loại **{CATEGORY_LABELS[sk['category']]}**, không phải {CATEGORY_LABELS[category]}!"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        pdata,players=get_player(user.id)
        owned=pdata.get("skills_owned",[1,5,10,14])
        if sid not in owned:
            m=f"❌ Chưa mua! {prefix}buyskill {sid} ({sk['price']}🪙)"
            if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
            else:await ctx_or_int.response.send_message(m,ephemeral=True);return
        eq=pdata.get("skill_equipped",{"attack":1,"special":5,"defense":10,"passive":14})
        eq[category]=sid;pdata["skill_equipped"]=eq
        save_player(str(user.id),pdata,players)
        m=f"✅ {CATEGORY_LABELS[category]}: **{sk['icon']} {sk['name']}**! 💪"
        if isinstance(ctx_or_int,discord.ext.commands.Context):await ctx_or_int.reply(m)
        else:await ctx_or_int.response.send_message(m)

    # ─── SHOP ───
    @commands.command(name="shop",aliases=["cuahang"])
    async def shop_cmd(self,ctx):
        pdata,_=get_player(ctx.author.id);coins=pdata.get("coins",0)
        embed=discord.Embed(title="🏪 CỬA HÀNG XỎ LÁ",color=0xffaa00,
            description=f"💰 **{coins} coins** | `!buy <số>`\n🔄=1 lần | ♾️=vĩnh viễn | 🔥=kỹ năng")
        cons=[];eqs=[];skls=[]
        for iid,it in SHOP_ITEMS.items():
            cb="✅"if coins>=it["price"]else"❌"
            if it["type"]=="consumable":cons.append(f"`{iid}` {it['name']} 🪙{it['price']} {cb}\n　└ {it['desc']}")
            elif it["type"]=="equipment":eqs.append(f"`{iid}` {it['name']} 🪙{it['price']} {cb}\n　└ {it['desc']}")
            elif it["type"]=="skill":skls.append(f"`{iid}` {it['name']} 🪙{it['price']} {cb}")
        if cons:embed.add_field(name="🧪 Tiêu Hao",value="\n".join(cons),inline=False)
        if eqs:embed.add_field(name="⚔️ Trang Bị",value="\n".join(eqs),inline=False)
        embed.add_field(name="🔥 KỸ NĂNG (mua rồi gán vào slot)",value="\n".join(skls)if skls else"Dùng `!skills` xem chi tiết",inline=False)
        embed.set_footer(text="!skills xem skill | !equipskill <loại> <số>")
        await ctx.send(embed=embed)

    # ─── INVENTORY ───
    @commands.command(name="inventory",aliases=["inv","tui","tuidog"])
    async def inv_cmd(self,ctx):
        pdata,_=get_player(ctx.author.id)
        inv=pdata.get("inventory",{});eq_items=pdata.get("equipment_items",{})
        equipped=pdata.get("equipped",{});eq_sk=pdata.get("skill_equipped",{})
        embed=discord.Embed(title=f"🎒 Túi Đồ {ctx.author.display_name}",color=0xffaa00)
        if inv:
            lines=[f"`{i}` {SHOP_ITEMS[i]['name']} ×**{q}**"for i,q in sorted(inv.items())if i in SHOP_ITEMS]
            if lines:embed.add_field(name="🧪 Tiêu Hao",value="\n".join(lines),inline=False)
        if eq_items:
            lines=[]
            for i in sorted(eq_items):
                it=SHOP_ITEMS.get(i)
                if not it:continue
                e=any(eid==i for eid in equipped.values())
                lines.append(f"`{i}` {it['name']} — {'✅ Mặc'if e else'📦 Kho'}")
            if lines:embed.add_field(name="⚔️ Trang Bị",value="\n".join(lines),inline=False)
        sl=[]
        for sn in["weapon","armor","accessory","crown"]:
            iid=equipped.get(sn);slb=SLOT_NAMES.get(sn,sn)
            sl.append(f"{slb}: {SHOP_ITEMS[iid]['name']}"if iid and iid in SHOP_ITEMS else f"{slb}: 🈳")
        embed.add_field(name="🎽 Đang Mặc",value="\n".join(sl),inline=False)
        # Skills
        skl=[]
        for cat in["attack","special","defense","passive"]:
            sid=eq_sk.get(cat);sk=SKILLS_DB.get(sid,SKILLS_DB[1])
            skl.append(f"{CATEGORY_LABELS[cat]}: {sk['icon']} {sk['name']}")
        embed.add_field(name="🔥 Kỹ Năng (4/4)",value="\n".join(skl),inline=False)
        embed.set_footer(text=f"💰 {pdata.get('coins',0)} coins | !skills")
        await ctx.send(embed=embed)


    # ════════════════════════════════════════════
    #  BATTLE CORE - Skill-based combat engine
    # ════════════════════════════════════════════
    async def _execute_battle_core(self,guild,battle,user_id,move_type):
        battles=load_json(BATTLES_FILE);sid=str(user_id)
        if sid not in battles:return None
        if not battle["active"]:return None
        if battle["turn"]!=sid:return None

        # Check stun
        if sid==battle["player1"]and battle.get("p1_stunned"):
            return await self._skip_stunned(guild,battle,sid,battles)
        if sid==battle["player2"]and battle.get("p2_stunned"):
            return await self._skip_stunned(guild,battle,sid,battles)

        p1=await resolve_member(guild,int(battle["player1"]))
        p2=await resolve_member(guild,int(battle["player2"]))
        if not p1 or not p2:battle["active"]=False;save_json(BATTLES_FILE,battles);return None

        p1_data,players=get_player(battle["player1"])
        p2_data=players[str(battle["player2"])]

        if sid==battle["player1"]:attacker_data,defender_data,attacker,defender=p1_data,p2_data,p1,p2;def_is_p2=True
        else:attacker_data,defender_data,attacker,defender=p2_data,p1_data,p2,p1;def_is_p2=False

        result_lines=[];embed_color=0x00ff00

        # Get attacker's equipped skill for this move
        cat="defense"if move_type=="defense"else move_type
        skill=get_equipped_skill(attacker_data,cat)

        # ─── DEFENSE ───
        if move_type=="defense"and skill["type"]=="defend":
            if def_is_p2:battle["p2_defending"]=True
            else:battle["p1_defending"]=True
            # Heal component
            heal_pct=skill.get("heal_pct",8)
            heal_amt=int(attacker_data["hp_max"]*heal_pct/100)
            attacker_data["hp"]=min(attacker_data["hp_max"],attacker_data["hp"]+heal_amt)
            result_lines.append(f"🛡️ **{skill['name']}** — ×3 DEF + hồi {heal_amt}HP! ☂️")
            embed_color=0x4488ff
            attacker_data[f"{cat}_cd"]=skill["cooldown"]

        # ─── DEFENSE: Heal ───
        elif move_type=="defense"and skill["type"]=="heal":
            heal_pct=skill.get("heal_pct",40)
            heal_amt=int(attacker_data["hp_max"]*heal_pct/100)
            old=attacker_data["hp"]
            attacker_data["hp"]=min(attacker_data["hp_max"],attacker_data["hp"]+heal_amt)
            # Xóa debuff
            cleared=[]
            for kb in["_burn","_def_reduced"]:
                if kb in attacker_data:del attacker_data[kb];cleared.append(kb)
            if def_is_p2:battle["p2_stunned"]=False;cleared.append("stun")
            else:battle["p1_stunned"]=False
            result_lines.append(f"💚 **{skill['name']}** — hồi **{attacker_data['hp']-old} HP**! {'🧹 Xóa debuff!'if cleared else''}")
            embed_color=0x00ff88
            attacker_data[f"{cat}_cd"]=skill["cooldown"]

        # ─── DEFENSE: Shield ───
        elif move_type=="defense"and skill["type"]=="shield":
            sh_pct=skill.get("shield_pct",35)
            sh_amt=int(attacker_data["hp_max"]*sh_pct/100)
            attacker_data["_shield_hp"]=sh_amt
            attacker_data["_shield_pop_heal"]=skill.get("shield_pop_heal",15)
            result_lines.append(f"🛡️ **{skill['name']}** — khiên {sh_amt}HP! (+{skill.get('shield_pop_heal',15)}% khi vỡ)")
            embed_color=0x4488ff
            attacker_data[f"{cat}_cd"]=skill["cooldown"]

        # ─── DEFENSE: Counter ───
        elif move_type=="defense"and skill["type"]=="counter":
            attacker_data["_counter"]=skill.get("multiplier",2.5)
            attacker_data["_counter_immune"]=True  # Miễn toàn bộ dmg turn này
            result_lines.append(f"🔄 **{skill['name']}** — miễn dmg + phản ×{skill.get('multiplier',2.5)}!")
            embed_color=0xff6600
            attacker_data[f"{cat}_cd"]=skill["cooldown"]

        # ─── DAMAGE SKILLS (attack + special) ───
        else:
            atk_eff,pbonus=get_effective_stats(attacker_data)
            def_eff,_=get_effective_stats(defender_data)
            atk_buff=attacker_data.get("buff",{});def_buff=defender_data.get("buff",{})

            # Check counter from defender
            counter_mult=defender_data.pop("_counter",None)

            # Check dodge (passive on defender)
            def_passive=get_equipped_skill(defender_data,"passive")
            if def_passive["type"]=="dodge":
                if random.random()<def_passive["dodge_chance"]/100:
                    result_lines.append(f"🍀 **{defender.display_name} NÉ ĐÒN!** May mắn vãi!")
                    # Still CD
                    attacker_data[f"{cat}_cd"]=skill["cooldown"]
                    return await self._finish_turn(guild,battle,sid,battles,p1_data,p2_data,p1,p2,result_lines,0xffff00)

            # Calculate damage
            mult=skill.get("multiplier",1.0)
            if skill.get("type")=="multi_hit":
                hits=skill.get("hits",2)
                total=sum(int(random.randint(atk_eff["attack_min"],atk_eff["attack_max"])*mult)for _ in range(hits))
                base_dmg=total
                result_lines.append(f"⚔️ **{skill['name']}** — {hits} đòn!")
            else:base_dmg=int(random.randint(atk_eff["attack_min"],atk_eff["attack_max"])*mult)

            # Legendary proc (special skills)
            if cat=="special"and skill.get("legendary_chance"):
                lc=skill["legendary_chance"]/100
                if atk_buff.get("lucky"):lc*=2;atk_buff.pop("lucky");attacker_data["buff"]=atk_buff;result_lines.append("🎲 Xúc xắc kích hoạt!")
                if random.random()<lc:base_dmg=int(base_dmg*1.67);result_lines.append("🌟 XỎ LÁ THẦN CHƯỞNG! ×5!")

            # Passive damage boost
            if pbonus["damage_pct"]>0:base_dmg=int(base_dmg*(1+pbonus["damage_pct"]/100))

            # Attack buff
            if atk_buff.get("attack_boost"):boost=atk_buff["attack_boost"];base_dmg=int(base_dmg*(1+boost/100));result_lines.append(f"⚡ Bùa +{boost}%!");atk_buff.pop("attack_boost");attacker_data["buff"]=atk_buff

            # Defense
            defending=battle.get("p2_defending"if def_is_p2 else"p1_defending",False)
            eff_def=def_eff["defense"]*2 if defending else def_eff["defense"]
            if def_buff.get("defense_boost"):boost=def_buff["defense_boost"];eff_def=int(eff_def*(1+boost/100));result_lines.append(f"🛡️ Giáp Chuối +{boost}%!");def_buff.pop("defense_boost");defender_data["buff"]=def_buff
            if skill.get("def_reduce_pct"):eff_def=int(eff_def*(100-skill["def_reduce_pct"])/100);result_lines.append(f"🌀 -{skill['def_reduce_pct']}% DEF!")
            if skill.get("pierce_pct"):eff_def=int(eff_def*(100-skill["pierce_pct"])/100)

            damage=max(1,base_dmg-eff_def)

            # VIP/WORST
            if defender.id==VIP_USER:damage=max(1,damage//10)
            if defender.id==WORST_USER:damage=int(damage*2)
            if attacker.id==VIP_USER:damage=int(damage*1.5)
            if attacker.id==WORST_USER:damage=max(1,damage//3)

            # Last Stand (passive)
            if def_passive["type"]=="last_stand":
                if defender_data["hp"]<=defender_data["hp_max"]*def_passive["hp_threshold"]/100:
                    damage=int(damage*(100-def_passive["dmg_reduce_pct"])/100)
                    result_lines.append(f"💎 GIÁP BẤT TỬ! -{def_passive['dmg_reduce_pct']}% dmg!")

            # Counter immune (defender used Phản Đòn this turn)
            if defender_data.pop("_counter_immune",None):
                result_lines.append(f"🔄 {defender.display_name} MIỄN TOÀN BỘ SÁT THƯƠNG!")
                damage=0
            # Shield
            sh=defender_data.get("_shield_hp",0)
            if sh>0:
                if damage<=sh:defender_data["_shield_hp"]=sh-damage;result_lines.append(f"🛡️ Khiên hấp thụ {damage}!");damage=0
                else:
                    pop_heal=defender_data.pop("_shield_pop_heal",15)
                    heal_amt=int(defender_data["hp_max"]*pop_heal/100)
                    defender_data["hp"]=min(defender_data["hp_max"],defender_data["hp"]+heal_amt)
                    result_lines.append(f"🛡️ Khiên vỡ! Tràn {damage-sh}! +{heal_amt}HP hồi!");damage-=sh;defender_data["_shield_hp"]=0

            # Self damage
            if skill.get("self_dmg_pct"):sd=int(attacker_data["hp"]*skill["self_dmg_pct"]/100);attacker_data["hp"]=max(1,attacker_data["hp"]-sd);result_lines.append(f"💀 Tự thiêu {sd}HP!")

            # Rage (passive on attacker)
            atk_passive=get_equipped_skill(attacker_data,"passive")
            if atk_passive["type"]=="rage":
                if attacker_data.get("_rage_dmg",0)>0:
                    rage_bonus=int(attacker_data.pop("_rage_dmg",0)*atk_passive.get("rage_multiplier",2.0))
                    damage+=rage_bonus;result_lines.append(f"💢 PHẪN NỘ! +{rage_bonus} dmg!")

            # Apply damage
            defender_data["hp"]=max(0,defender_data["hp"]-damage)
            attacker_data["damage_dealt"]+=damage;defender_data["damage_taken"]+=damage

            emoji="🤜";result_lines.append(f"{skill['icon']} **{skill['name']}** {emoji}")
            # Rage: accumulate on defender
            def_passive2=get_equipped_skill(defender_data,"passive")
            if def_passive2["type"]=="rage":
                defender_data["_rage_dmg"]=defender_data.get("_rage_dmg",0)+int(damage*def_passive2.get("rage_pct",50)/100)

            # Counter
            if counter_mult:
                cd=int(damage*counter_mult);attacker_data["hp"]=max(0,attacker_data["hp"]-cd);attacker_data["damage_taken"]+=cd;defender_data["damage_dealt"]+=cd
                result_lines.append(f"🔄 PHẢN ĐÒN! {cd} dmg!")

            # Lifesteal
            if skill.get("type")=="lifesteal":
                heal=int(damage*skill["lifesteal_pct"]/100);attacker_data["hp"]=min(attacker_data["hp_max"],attacker_data["hp"]+heal)
                result_lines.append(f"🩸 Hút {heal} HP!")
            # Burn
            if skill.get("type")=="burn":
                defender_data["_burn"]={"pct":skill["burn_pct"],"turns":skill.get("burn_turns",2)}
                result_lines.append(f"🔥 Thiêu đốt {skill['burn_pct']}%/2t!")
            # Stun
            if skill.get("type")=="stun":
                if def_is_p2:battle["p2_stunned"]=True
                else:battle["p1_stunned"]=True
                result_lines.append(f"🌑 Choáng! {defender.display_name} mất lượt!")

            # Flavor
            if move_type=="attack"and not skill.get("type")in["multi_hit","lifesteal","burn","stun"]:
                if damage>=50:result_lines.append(f"💥 {damage} dmg! Bom nguyên tử! 💣")
                elif damage>=30:result_lines.append(f"💥 {damage} dmg! Tơi bời hoa lá! 🌪️")
                elif damage>0:result_lines.append(f"💥 {damage} dmg! Chọc gậy bánh xe! 🚲")
            elif move_type=="special":
                result_lines.append(f"💥 **{damage}** dmg!"if damage>0 else"")

            if defending and defender.id==VIP_USER and damage<=1:result_lines.append("🛡️ FULL GIÁP BẤT TỬ!")
            if def_is_p2:battle["p2_defending"]=False
            else:battle["p1_defending"]=False
            attacker_data[f"{cat}_cd"]=skill["cooldown"]

        # Reduce all cooldowns
        for pid in[battle["player1"],battle["player2"]]:
            pdat,_=get_player(pid)
            for cdkey in["attack_cd","special_cd","defense_cd"]:
                if pdat.get(cdkey,0)>0:pdat[cdkey]-=1

        # Regen passive
        atk_passive=get_equipped_skill(attacker_data,"passive")
        if atk_passive["type"]=="regen":
            reg=int(attacker_data["hp_max"]*atk_passive["regen_pct"]/100)
            attacker_data["hp"]=min(attacker_data["hp_max"],attacker_data["hp"]+reg)

        # Burn tick on defender
        burn=defender_data.get("_burn")
        if burn and burn.get("turns",0)>0:
            bd=int(defender_data["hp_max"]*burn["pct"]/100)
            defender_data["hp"]=max(0,defender_data["hp"]-bd);burn["turns"]-=1
            result_lines.append(f"🔥 Bỏng! {defender.display_name} -{bd}HP ({burn['turns']}t)")
            if burn["turns"]<=0:defender_data.pop("_burn",None)

        # Check defeat
        if defender_data["hp"]<=0:
            battle["active"]=False
            attacker_data["wins"]+=1;defender_data["losses"]+=1
            defender_data["hp"]=0;defender_data["last_hp_update"]=time.time()
            for d in[attacker_data,defender_data]:
                for kb in["_burn","_shield_hp","_shield_pop_heal","_counter","_counter_immune","_rage_dmg","_def_reduced"]:d.pop(kb,None)
            is_vip=(defender.id==VIP_USER);is_worst=(defender.id==WORST_USER)
            ac,ax,al=reward_player(battle["player1"]if sid==battle["player1"]else battle["player2"],players,True,is_vip,is_worst)
            dc,dx,dl=reward_player(battle["player2"]if sid==battle["player1"]else battle["player1"],players,False)
            save_player(battle["player1"],p1_data,players);save_player(battle["player2"],p2_data,players)
            bdata=load_json(BATTLES_FILE)
            for k in list(bdata.keys()):
                if k==battle["player1"]or k==battle["player2"]:del bdata[k]
            save_json(BATTLES_FILE,bdata)
            lines=result_lines+[
                f"\n💀 **{defender.display_name}** bị xỏ lá đến chết!",
                f"🏆 **{attacker.display_name}** CHIẾN THẮNG! 🎉",
                f"💰 {attacker.display_name}: +{ac}🪙 +{ax}XP{' ⬆️LV!'if al else''}",
                f"💰 {defender.display_name}: +{dc}🪙 +{dx}XP{' ⬆️LV!'if dl else''}",
            ]
            embed=discord.Embed(title="⚔️ KẾT THÚC!",description="\n".join(lines),color=0xffd700)
            return embed,None,True

        save_player(battle["player1"],p1_data,players);save_player(battle["player2"],p2_data,players)

        # Clear stuns
        for k in["p1_stunned","p2_stunned"]:
            if battle.get(k):battle[k]=False

        # Switch turn
        return await self._finish_turn(guild,battle,sid,battles,p1_data,p2_data,p1,p2,result_lines,embed_color)

    async def _finish_turn(self,guild,battle,sid,battles,p1_data,p2_data,p1,p2,result_lines,embed_color):
        battle["last_move"]=time.time()
        new_turn=battle["player2"]if battle["turn"]==battle["player1"]else battle["player1"]
        battle["turn"]=new_turn
        battles[battle["player1"]]=battle;battles[battle["player2"]]=battle
        save_json(BATTLES_FILE,battles)

        next_pdata=p1_data if new_turn==battle["player1"]else p2_data
        ask=get_equipped_skill(next_pdata,"attack")
        ssk=get_equipped_skill(next_pdata,"special")
        dsk=get_equipped_skill(next_pdata,"defense")

        hp1=f"🟩"*(p1_data["hp"]//10)+f"⬜"*((p1_data["hp_max"]-p1_data["hp"])//10)
        hp2=f"🟩"*(p2_data["hp"]//10)+f"⬜"*((p2_data["hp_max"]-p2_data["hp"])//10)
        if len(hp1)>15:hp1=hp1[:15]
        if len(hp2)>15:hp2=hp2[:15]

        next_m=await resolve_member(guild,int(new_turn))
        result_lines.append("\n━━━━━━━━━━━")
        result_lines.append(f"❤️ {p1.display_name}:`{p1_data['hp']}/{p1_data['hp_max']}`{hp1}")
        result_lines.append(f"❤️ {p2.display_name}:`{p2_data['hp']}/{p2_data['hp_max']}`{hp2}")

        for pd,pn in[(p1_data,p1.display_name),(p2_data,p2.display_name)]:
            fx=[]
            if pd.get("_shield_hp",0)>0:fx.append(f"🛡️{pd['_shield_hp']}")
            if pd.get("_burn"):fx.append(f"🔥{pd['_burn']['turns']}t")
            if pd.get("_counter"):fx.append("🔄 Phản đòn")
            if fx:result_lines.append(f"  {pn}: {' | '.join(fx)}")

        # Show skill cooldowns
        for pd,pn in[(p1_data,p1.display_name),(p2_data,p2.display_name)]:
            cds=[f"{get_equipped_skill(pd,cat)['icon']}"+("✅"if pd.get(f"{cat}_cd",0)<=0 else f"⏳{pd[f'{cat}_cd']}")for cat in["attack","special","defense"]]
            result_lines.append(f"  {pn}: {' '.join(cds)}")

        result_lines.append(f"\n⏳ **{next_m.display_name if next_m else '???'}** — 15s!")
        embed=discord.Embed(title="⚔️ DIỄN BIẾN",description="\n".join(result_lines),color=embed_color)
        view=BattleView(self,new_turn,next_m.display_name if next_m else"???",ask["name"],ssk["name"],dsk["name"])
        return embed,view,False

    async def _skip_stunned(self,guild,battle,sid,battles):
        p1=await resolve_member(guild,int(battle["player1"]))
        p2=await resolve_member(guild,int(battle["player2"]))
        p1_data,players=get_player(battle["player1"]);p2_data=players[str(battle["player2"])]
        an=p1.display_name if sid==battle["player1"]else p2.display_name
        sd=p1_data if sid==battle["player1"]else p2_data

        for pid in[battle["player1"],battle["player2"]]:
            pdat,_=get_player(pid)
            for cdkey in["attack_cd","special_cd","defense_cd"]:
                if pdat.get(cdkey,0)>0:pdat[cdkey]-=1

        rl=[f"🌑 **{an}** bị choáng, mất lượt!"]
        burn=sd.get("_burn")
        if burn and burn.get("turns",0)>0:
            bd=int(sd["hp_max"]*burn["pct"]/100);sd["hp"]=max(0,sd["hp"]-bd);burn["turns"]-=1
            rl.append(f"🔥 Bỏng -{bd}HP ({burn['turns']}t)")
            if burn["turns"]<=0:sd.pop("_burn",None)

        if sid==battle["player1"]:battle["p1_stunned"]=False
        else:battle["p2_stunned"]=False

        save_player(battle["player1"],p1_data,players);save_player(battle["player2"],p2_data,players)

        if sd["hp"]<=0:
            battle["active"]=False;sd["hp"]=0;sd["last_hp_update"]=time.time()
            ws=battle["player2"]if sid==battle["player1"]else battle["player1"]
            wd=p2_data if sid==battle["player1"]else p1_data
            sd["losses"]=sd.get("losses",0)+1;wd["wins"]=wd.get("wins",0)+1
            reward_player(ws,players,True);reward_player(sid,players,False)
            save_player(battle["player1"],p1_data,players);save_player(battle["player2"],p2_data,players)
            bdata=load_json(BATTLES_FILE)
            for k in list(bdata.keys()):
                if k==battle["player1"]or k==battle["player2"]:del bdata[k]
            save_json(BATTLES_FILE,bdata)
            wn=p2.display_name if ws==battle["player2"]else p1.display_name
            return discord.Embed(title="⚔️ KẾT THÚC!",description=f"🌑 {an} choáng+chết!\n🏆 {wn} thắng!",color=0xffd700),None,True

        return await self._finish_turn(guild,battle,sid,battles,p1_data,p2_data,p1,p2,rl,0x9966ff)


    # ════════════════════════════════════════════
    #  SLASH COMMANDS
    # ════════════════════════════════════════════
    async def _sync_helper(self,interaction,msg_type="text"):
        if msg_type=="ephemeral":return await interaction.response.send_message
        return await interaction.followup.send

    @app_commands.command(name="help",description="Xem hướng dẫn")
    async def slash_help(self,interaction:discord.Interaction):
        embed=discord.Embed(title="⚔️ Đấu Trường Ba Que Xỏ Lá",color=0xff6600)
        embed.add_field(name="📝 Cơ Bản",value="/register /stats /upgrade /leaderboard /challenge",inline=False)
        embed.add_field(name="🏪 Shop",value="/shop /buy /use /equip /inv",inline=False)
        embed.add_field(name="🔥 KỸ NĂNG 4 SLOT",value="/skills — 20 skill\n/buyskill <số>\n/equipskill <loại> <số>\nVD: /equipskill attack 2",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="register",description="Đăng ký tham gia")
    async def slash_register(self,interaction:discord.Interaction):
        if str(interaction.user.id)in load_json(PLAYERS_FILE):
            await interaction.response.send_message("🤷 Đăng ký rồi! /stats",ephemeral=True);return
        _,players=get_player(interaction.user.id)
        await interaction.response.send_message(f"✅ {interaction.user.display_name} đăng ký!")

    @app_commands.command(name="stats",description="Xem chỉ số")
    @app_commands.describe(member="Ai? (bỏ trống = mình)")
    async def slash_stats(self,interaction:discord.Interaction,member:discord.Member=None):
        target=member or interaction.user
        pdata,_=get_player(target.id)
        await interaction.response.send_message(embed=stats_embed(f"📊 {target.display_name}",pdata,target))

    @app_commands.command(name="leaderboard",description="BXH")
    async def slash_leaderboard(self,interaction:discord.Interaction):
        players=load_json(PLAYERS_FILE)
        if not players:await interaction.response.send_message("📭 Chưa ai đăng ký!");return
        await interaction.response.defer()
        sp=sorted(players.items(),key=lambda x:x[1]["wins"],reverse=True)
        embed=discord.Embed(title="🏆 BXH",color=0xffd700)
        medals=["🥇","🥈","🥉"]
        for i,(sid,pd)in enumerate(sp[:10]):
            try:u=await self.bot.fetch_user(int(sid));n=u.display_name
            except:n=f"Unknown"
            m=medals[i]if i<3 else f"#{i+1}"
            wr=pd["wins"]/(pd["wins"]+pd["losses"])*100 if(pd["wins"]+pd["losses"])>0 else 0
            embed.add_field(name=f"{m} {n}{'👑'if int(sid)==VIP_USER else'🐔'if int(sid)==WORST_USER else''}",
                value=f"🏆`{pd['wins']}W/{pd['losses']}L`WR{wr:.0f}% Lv.{pd.get('level',1)} 💰{pd.get('coins',0)}",inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="challenge",description="Thách đấu")
    @app_commands.describe(member="Ai?")
    async def slash_challenge(self,interaction:discord.Interaction,member:discord.Member):
        sid=str(member.id);sc=str(interaction.user.id)
        if member.id==interaction.user.id:await interaction.response.send_message("🤡 Tự thách mình?",ephemeral=True);return
        if member.bot:await interaction.response.send_message("🤖 Bot sao đấu?",ephemeral=True);return
        challenges=load_json(CHALLENGES_FILE);battles=load_json(BATTLES_FILE)
        if sid in challenges:await interaction.response.send_message(f"⚠️ {member.display_name} đang có lời thách!",ephemeral=True);return
        if sid in battles:await interaction.response.send_message(f"⚔️ {member.display_name} đang đánh!",ephemeral=True);return
        if sc in battles:await interaction.response.send_message("⚔️ Mày đang đánh!",ephemeral=True);return
        pd,_=get_player(member.id)
        if pd["hp"]<=0:await interaction.response.send_message(f"💀 {member.display_name} 0 máu!",ephemeral=True);return
        md,_=get_player(interaction.user.id)
        if md["hp"]<=0:await interaction.response.send_message("💀 Mày 0 máu!",ephemeral=True);return
        challenges[sid]={"challenger":sc,"channel_id":interaction.channel_id,"time":datetime.now().timestamp()}
        save_json(CHALLENGES_FILE,challenges)
        embed=discord.Embed(title="⚔️ THÁCH ĐẤU!",color=0xff0000,
            description=f"**{interaction.user.display_name}** 👊 **{member.display_name}**!\n<@{member.id}> bấm nút! ⏰30s")
        view=ChallengeView(self,sid,sc,interaction.user.display_name,member.display_name,interaction.channel_id)
        await interaction.response.send_message(embed=embed,view=view)

    @app_commands.command(name="upgrade",description="Nâng chỉ số")
    @app_commands.choices(stat=[
        app_commands.Choice(name="❤️ HP +10",value="hp"),
        app_commands.Choice(name="⚔️ ATK +2~3",value="atk"),
        app_commands.Choice(name="🛡️ DEF +2",value="def"),
    ])
    async def slash_upgrade(self,interaction:discord.Interaction,stat:str):
        pdata,players=get_player(interaction.user.id)
        sp=pdata.get("stat_points",0)
        if sp<1:await interaction.response.send_message("😅 Hết điểm! Đánh nhau đi.",ephemeral=True);return
        if stat=="hp":pdata["hp_max"]+=10;pdata["hp"]+=10;sn="❤️ HP"
        elif stat=="atk":pdata["attack_min"]+=2;pdata["attack_max"]+=3;sn="⚔️ ATK"
        else:pdata["defense"]+=2;sn="🛡️ DEF"
        pdata["stat_points"]=sp-1
        save_player(str(interaction.user.id),pdata,players)
        await interaction.response.send_message(f"⬆️ **{sn}** tăng! Còn {sp-1} điểm.")

    # ─── SKILLS SLASH ───
    @app_commands.command(name="skills",description="🔥 Kho kỹ năng")
    async def slash_skills(self,interaction:discord.Interaction):
        pdata,_=get_player(interaction.user.id)
        owned=pdata.get("skills_owned",[1,5,10,14])
        equipped=pdata.get("skill_equipped",{"attack":1,"special":5,"defense":10,"passive":14})
        coins=pdata.get("coins",0)
        embed=discord.Embed(title="🔥 KHO KỸ NĂNG (20 SKILL)",color=0xff6600,
            description=f"💰 **{coins} coins** | /buyskill <số> | /equipskill <loại> <số>")
        for cat in["attack","special","defense","passive"]:
            skills_in_cat=[(sid,s)for sid,s in SKILLS_DB.items()if s["category"]==cat]
            lines=[]
            for sid,sk in skills_in_cat:
                stars=RARITY_STARS.get(sk["rarity"],"⭐")
                is_o=sid in owned;is_e=equipped.get(cat)==sid
                s="✅ ĐANG DÙNG"if is_e else("📦 CÓ"if is_o else f"🪙{sk['price']}")
                cd_text = f"CD:`{sk['cooldown']}`" if 'cooldown' in sk else "💎 BỊ ĐỘNG"
                lines.append(f"`{sid}` {sk['icon']} **{sk['name']}** {stars} | {cd_text} | {s}\n　└ {sk['desc']}")
            embed.add_field(name=f"{CATEGORY_LABELS[cat]}",value="\n".join(lines),inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buyskill",description="🛒 Mua kỹ năng")
    @app_commands.describe(skill_id="Số skill")
    async def slash_buyskill(self,interaction:discord.Interaction,skill_id:str):
        await self._buyskill(interaction,interaction.user,skill_id,"/")

    @slash_buyskill.autocomplete("skill_id")
    async def buyskill_autocomplete(self,interaction:discord.Interaction,current:str):
        pdata,_=get_player(interaction.user.id);owned=pdata.get("skills_owned",[1,5,10,14]);coins=pdata.get("coins",0)
        choices=[]
        for sid,sk in SKILLS_DB.items():
            if sk["price"]==0 or sid in owned:continue
            if current.lower()in str(sid)or current.lower()in sk["name"].lower():
                can="✅"if coins>=sk["price"]else"❌"
                choices.append(app_commands.Choice(name=f"({sid}) {sk['name']} 🪙{sk['price']} {can}"[:100],value=str(sid)))
        return choices[:25]

    @app_commands.command(name="equipskill",description="🔥 Gán skill vào slot")
    @app_commands.choices(category=[
        app_commands.Choice(name="💥 Tấn Công (nút Xỏ Lá)",value="attack"),
        app_commands.Choice(name="🔥 Đặc Biệt (nút Đặc Biệt)",value="special"),
        app_commands.Choice(name="🛡️ Chống Xỏ Lá (nút Chống Xỏ Lá)",value="defense"),
        app_commands.Choice(name="💎 Bị Động (luôn active)",value="passive"),
    ])
    @app_commands.describe(category="Slot muốn gán",skill_id="Số skill")
    async def slash_equipskill(self,interaction:discord.Interaction,category:str=None,skill_id:str=None):
        await self._equipskill(interaction,interaction.user,category,skill_id,"/")

    @slash_equipskill.autocomplete("skill_id")
    async def equipskill_autocomplete(self,interaction:discord.Interaction,current:str):
        cat=interaction.namespace.get("category")
        if not cat:return[]
        pdata,_=get_player(interaction.user.id);owned=pdata.get("skills_owned",[1,5,10,14]);equipped=pdata.get("skill_equipped",{})
        choices=[]
        for sid in owned:
            sk=SKILLS_DB.get(sid)
            if not sk or sk["category"]!=cat:continue
            if current.lower()in str(sid)or current.lower()in sk["name"].lower():
                s="✅"if equipped.get(cat)==sid else"📦"
                choices.append(app_commands.Choice(name=f"({sid}) {s} {sk['name']}"[:100],value=str(sid)))
        return choices[:25]

    # ─── SHOP SLASH ───
    @app_commands.command(name="shop",description="🏪 Cửa hàng")
    async def slash_shop(self,interaction:discord.Interaction):
        pdata,_=get_player(interaction.user.id);coins=pdata.get("coins",0)
        embed=discord.Embed(title="🏪 CỬA HÀNG",color=0xffaa00,description=f"💰 {coins}🪙 | /buy <số>")
        cons=[];eqs=[]
        for iid,it in SHOP_ITEMS.items():
            cb="✅"if coins>=it["price"]else"❌"
            if it["type"]=="consumable":cons.append(f"`{iid}` {it['name']} 🪙{it['price']} {cb}\n　└ {it['desc']}")
            elif it["type"]=="equipment":eqs.append(f"`{iid}` {it['name']} 🪙{it['price']} {cb}\n　└ {it['desc']}")
        if cons:embed.add_field(name="🧪 Tiêu Hao",value="\n".join(cons),inline=False)
        if eqs:embed.add_field(name="⚔️ Trang Bị",value="\n".join(eqs),inline=False)
        embed.add_field(name="🔥 KỸ NĂNG",value="Dùng `/skills` xem 20 skill + `/buyskill` mua!",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy",description="🛒 Mua đồ")
    @app_commands.describe(item_id="Số món")
    async def slash_buy(self,interaction:discord.Interaction,item_id:str):
        try:iid=int(item_id.strip())
        except:await interaction.response.send_message("❌ Số!",ephemeral=True);return
        if iid not in SHOP_ITEMS:await interaction.response.send_message("❌ Không có!",ephemeral=True);return
        item=SHOP_ITEMS[iid]

        if item["type"]=="skill":
            sk=SKILLS_DB.get(item["skill_id"])
            if not sk:await interaction.response.send_message("❌ Lỗi!",ephemeral=True);return
            pdata,players=get_player(interaction.user.id);owned=pdata.get("skills_owned",[1,5,10,14])
            if item["skill_id"]in owned:await interaction.response.send_message(f"📦 Đã có {sk['name']}! /equipskill",ephemeral=True);return
            coins=pdata.get("coins",0)
            if coins<item["price"]:await interaction.response.send_message(f"😅 Cần {item['price']}🪙, có {coins}🪙",ephemeral=True);return
            pdata["coins"]=coins-item["price"];owned.append(item["skill_id"]);pdata["skills_owned"]=owned
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"✅ Mua **{sk['name']}**! /equipskill {sk['category']} {item['skill_id']}");return

        pdata,players=get_player(interaction.user.id);coins=pdata.get("coins",0)
        if coins<item["price"]:await interaction.response.send_message(f"😅 Cần {item['price']}🪙, có {coins}🪙",ephemeral=True);return
        pdata["coins"]=coins-item["price"]
        if item["type"]=="consumable":
            inv=pdata.get("inventory",{});inv[iid]=inv.get(iid,0)+1;pdata["inventory"]=inv
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"✅ Mua {item['name']}! /use {iid}")
        elif item["type"]=="equipment":
            eq=pdata.get("equipment_items",{})
            if eq.get(iid,0)>=1:await interaction.response.send_message("📦 Đã có!",ephemeral=True);pdata["coins"]=coins;save_player(str(interaction.user.id),pdata,players);return
            eq[iid]=1;pdata["equipment_items"]=eq
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"✅ Mua {item['name']}! /equip {iid}")

    @slash_buy.autocomplete("item_id")
    async def buy_autocomplete(self,interaction:discord.Interaction,current:str):
        pdata,_=get_player(interaction.user.id);coins=pdata.get("coins",0);owned_sk=pdata.get("skills_owned",[1,5,10,14])
        choices=[]
        for iid,it in SHOP_ITEMS.items():
            if it["type"]=="skill"and it.get("skill_id")in owned_sk:continue
            if current.lower()in str(iid)or current.lower()in it["name"].lower():
                can="✅"if coins>=it["price"]else"❌"
                choices.append(app_commands.Choice(name=f"({iid}) {it['name']} 🪙{it['price']} {can}"[:100],value=str(iid)))
        return choices[:25]

    @app_commands.command(name="use",description="💊 Xài đồ")
    @app_commands.describe(item_id="Số món")
    async def slash_use(self,interaction:discord.Interaction,item_id:str):
        try:iid=int(item_id.strip())
        except:await interaction.response.send_message("❌ Số!",ephemeral=True);return
        pdata,players=get_player(interaction.user.id);inv=pdata.get("inventory",{})
        if iid not in inv or inv[iid]<=0:await interaction.response.send_message("📭 Không có!",ephemeral=True);return
        item=SHOP_ITEMS.get(iid)
        if not item or item["type"]!="consumable":await interaction.response.send_message("❌ Không xài được!",ephemeral=True);return
        eff=item["effect"]
        if"hp_restore_percent"in eff:
            hpct=eff["hp_restore_percent"];old=pdata["hp"];mx=pdata["hp_max"]
            nh=mx if hpct>=100 else min(mx,old+max(1,int(mx*hpct/100)))
            if nh<=old:await interaction.response.send_message("❤️ Đầy máu rồi!",ephemeral=True);return
            pdata["hp"]=nh;pdata["last_hp_update"]=time.time()
            inv[iid]-=1
            if inv[iid]<=0:del inv[iid]
            pdata["inventory"]=inv
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"💚 Hồi {nh-old}HP!")
        elif"buff_attack_percent"in eff:
            buf=pdata.get("buff",{});buf["attack_boost"]=eff["buff_attack_percent"];pdata["buff"]=buf
            inv[iid]-=1
            if inv[iid]<=0:del inv[iid]
            pdata["inventory"]=inv
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"⚡ +{eff['buff_attack_percent']}% dmg trận kế!")
        elif"buff_defense_percent"in eff:
            buf=pdata.get("buff",{});buf["defense_boost"]=eff["buff_defense_percent"];pdata["buff"]=buf
            inv[iid]-=1
            if inv[iid]<=0:del inv[iid]
            pdata["inventory"]=inv
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message(f"🛡️ +{eff['buff_defense_percent']}% DEF trận kế!")
        elif"buff_lucky"in eff:
            buf=pdata.get("buff",{});buf["lucky"]=True;pdata["buff"]=buf
            inv[iid]-=1
            if inv[iid]<=0:del inv[iid]
            pdata["inventory"]=inv
            save_player(str(interaction.user.id),pdata,players)
            await interaction.response.send_message("🎲 ×2 legendary trận kế!")

    @slash_use.autocomplete("item_id")
    async def use_autocomplete(self,interaction:discord.Interaction,current:str):
        pdata,_=get_player(interaction.user.id);inv=pdata.get("inventory",{})
        choices=[]
        for iid,qty in inv.items():
            if qty>0:
                it=SHOP_ITEMS.get(iid,{})
                if current.lower()in str(iid)or current.lower()in it.get("name","").lower():
                    choices.append(app_commands.Choice(name=f"({iid}) {it.get('name','?')} ×{qty}"[:100],value=str(iid)))
        return choices[:25]

    @app_commands.command(name="equip",description="🎽 Mặc/tháo trang bị")
    @app_commands.describe(item_id="Số trang bị")
    async def slash_equip(self,interaction:discord.Interaction,item_id:str):
        try:iid=int(item_id.strip())
        except:await interaction.response.send_message("❌ Số!",ephemeral=True);return
        it=SHOP_ITEMS.get(iid)
        if not it or it["type"]!="equipment":await interaction.response.send_message("❌ Không phải trang bị!",ephemeral=True);return
        pdata,players=get_player(interaction.user.id)
        eqi=pdata.get("equipment_items",{})
        if iid not in eqi or eqi[iid]<1:await interaction.response.send_message("📦 Chưa mua!",ephemeral=True);return
        slot=it["slot"];equipped=pdata.get("equipped",{})
        old=equipped.get(slot)
        if old==iid:equipped[slot]=None;pdata["equipped"]=equipped;save_player(str(interaction.user.id),pdata,players);await interaction.response.send_message(f"✅ Tháo {it['name']}!");return
        equipped[slot]=iid;pdata["equipped"]=equipped;save_player(str(interaction.user.id),pdata,players)
        sname=SLOT_NAMES.get(slot,slot)
        m=f"✅ Mặc {it['name']} vào {sname}!"
        if old and old in SHOP_ITEMS:m+=f"\n📦 Tháo {SHOP_ITEMS[old]['name']}"
        await interaction.response.send_message(m)

    @slash_equip.autocomplete("item_id")
    async def equip_autocomplete(self,interaction:discord.Interaction,current:str):
        pdata,_=get_player(interaction.user.id);eqi=pdata.get("equipment_items",{});eqd=pdata.get("equipped",{})
        choices=[]
        for iid in eqi:
            it=SHOP_ITEMS.get(iid)
            if it and(current.lower()in str(iid)or current.lower()in it["name"].lower()):
                s="✅"if any(eid==iid for eid in eqd.values())else"📦"
                choices.append(app_commands.Choice(name=f"({iid}) {s} {it['name']}"[:100],value=str(iid)))
        return choices[:25]

    @app_commands.command(name="inventory",description="🎒 Túi đồ")
    async def slash_inv(self,interaction:discord.Interaction):
        pdata,_=get_player(interaction.user.id)
        inv=pdata.get("inventory",{});eqi=pdata.get("equipment_items",{});eqd=pdata.get("equipped",{});eq_sk=pdata.get("skill_equipped",{})
        embed=discord.Embed(title=f"🎒 Túi {interaction.user.display_name}",color=0xffaa00)
        if inv:
            ls=[f"`{i}` {SHOP_ITEMS[i]['name']} ×**{q}**"for i,q in sorted(inv.items())if i in SHOP_ITEMS]
            if ls:embed.add_field(name="🧪 Tiêu Hao",value="\n".join(ls),inline=False)
        if eqi:
            ls=[f"`{i}` {SHOP_ITEMS[i]['name']} — {'✅'if any(e==i for e in eqd.values())else'📦'}"for i in sorted(eqi)if i in SHOP_ITEMS]
            if ls:embed.add_field(name="⚔️ Trang Bị",value="\n".join(ls),inline=False)
        sl=[]
        for sn in["weapon","armor","accessory","crown"]:
            iid=eqd.get(sn);slb=SLOT_NAMES.get(sn,sn)
            sl.append(f"{slb}: {SHOP_ITEMS[iid]['name']}"if iid and iid in SHOP_ITEMS else f"{slb}: 🈳")
        embed.add_field(name="🎽 Đang Mặc",value="\n".join(sl),inline=False)
        skl=[]
        for cat in["attack","special","defense","passive"]:
            sid=eq_sk.get(cat);sk=SKILLS_DB.get(sid,SKILLS_DB[1])
            cds=""
            if cat!="passive":
                cd_key=f"{cat}_cd"
                cd_val=pdata.get(cd_key,0)
                cds=f" {'✅'if cd_val<=0 else f'⏳{cd_val}'}"
            skl.append(f"{CATEGORY_LABELS[cat]}: {sk['icon']} {sk['name']}{cds}")
        embed.add_field(name="🔥 Kỹ Năng",value="\n".join(skl),inline=False)
        embed.set_footer(text=f"💰 {pdata.get('coins',0)}🪙")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Arena(bot))
