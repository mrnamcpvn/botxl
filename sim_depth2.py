import sys; sys.path.insert(0, '.'); import copy
from bot.data.classes import CLASSES
from bot.config import ENHANCE_BONUS_PER_LEVEL, GLOBAL_HP_MULT, GLOBAL_DEF_MULT
from bot.data.equipment import EQUIPMENT

def real_stats(class_id, level, upg_atk, upg_def, upg_hp, role_mult, art_star, stars, enhances):
    cls = CLASSES[class_id]
    eq_atk=eq_hp=eq_def=0
    for star,enh in zip(stars,enhances):
        items=[e for eid,e in EQUIPMENT.items() if e["star"]==star]
        if items:
            m=1+enh*ENHANCE_BONUS_PER_LEVEL
            eq_atk+=int(items[0]["stats"].get("attack_min",0)*m)
            eq_hp +=int(items[0]["stats"].get("hp",items[0]["stats"].get("hp_max",0))*m)
            eq_def+=int(items[0]["stats"].get("defense",0)*m)
    hp  =(cls["hp_base"]+cls["hp_scale"]*(level-1))*GLOBAL_HP_MULT + upg_hp*10 + eq_hp
    atk = cls["atk_base"]+cls["atk_scale"]*(level-1) + upg_atk*2 + eq_atk
    def_=(cls["def_base"]+cls["def_scale"]*(level-1))*GLOBAL_DEF_MULT + upg_def*2 + eq_def
    if role_mult!=1.0: hp=int(hp*role_mult); atk=int(atk*role_mult); def_=int(def_*role_mult)
    if art_star>0:
        m=1+art_star*0.15
        hp=int(hp*m); atk=int(atk*m); def_=int(def_*m)
    return hp, atk, atk+5, def_

def dmg(atk, def_, m=1.0, p=0):
    b=int(atk*m); e=int(def_*(1-p/100))
    return max(1,int(b*max(0.20,1-e/(e+500))))

def dung_npc(floor):
    lvl=floor+5; hp=4000+floor*40
    atk=50+lvl*5
    def_=200+floor*18
    is_b=(floor%10==0)
    if is_b: return int(hp*2),int(atk*2),int(def_*1.3),True
    return hp,atk,def_,False

def simulate(p_hp, p_atk, p_def, max_floor=100):
    curr_hp = p_hp
    for floor in range(1, max_floor+1):
        npc_hp, npc_atk, npc_def, is_boss = dung_npc(floor)
        p_hp_fight = curr_hp
        heal_25 = int(p_hp * 0.08)
        heal_40 = int(p_hp * 0.40)
        heal_cd = 0
        survived = False
        for _ in range(500):
            p_dmg = dmg(p_atk, npc_def, 1.8)
            npc_hp -= p_dmg
            if npc_hp <= 0: survived = True; break
            npc_dmg = dmg(npc_atk, p_def)
            p_hp_fight -= npc_dmg
            if p_hp_fight <= 0: break
            heal_cd = max(0, heal_cd-1)
            if p_hp_fight < p_hp*0.40 and heal_cd==0:
                p_hp_fight = min(p_hp, p_hp_fight+heal_40); heal_cd=3
            elif p_hp_fight < p_hp*0.65:
                p_hp_fight = min(p_hp, p_hp_fight+heal_25)
        if not survived:
            return floor-1, npc_atk, dmg(npc_atk,p_def)
        heal = int(p_hp*(0.50 if is_boss else 0.25))
        curr_hp = min(p_hp, p_hp_fight+heal)
    return max_floor, 0, 0

players = [
    ("Thích Cúng Dường",  "sieunhan",45,123,2,7,1.0,3,[6,6,6,6,6,6],[9,7,8,7,7,7]),
    ("Kang 6 củ",         "sieunhan",47,128,2,7,1.1,1,[6,6,6,6,6,6],[9,7,7,7,7,7]),
    ("Hiệp cái",          "sieunhan",34,92,5,2, 1.1,0,[6,6,6,6,6,6],[7,8,7,7,7,7]),
    ("Thích Anh Hiệp v2", "sieunhan",27,68,0,9, 1.1,0,[5,6,5,6,6,6],[5,6,6,7,6,7]),
    ("Lươn xỏ lá",        "sieunhan",30,81,3,3, 1.0,0,[5,5,4,6,4,6],[5,6,3,6,0,0]),
    ("Hòa 7love",         "baque",   26,71,2,0, 1.0,0,[5,4,6,4,6,5],[4,4,5,3,5,0]),
    ("Cr7",               "muoi",    18,30,0,21,1.0,0,[4,3,5,5,4,4],[3,0,3,6,0,0]),
]

print("=== DUNGEON DEPTH - NPC ATK GIẢM ===\n")
print(f"{'Player':<22} {'HP':>6} {'ATK':>6} {'DEF':>5} | {'MaxFloor':>9} Notes")
print("-"*70)
for p in players:
    name,cls,lv,ua,ud,uh,rm,art,st,en = p
    hp,amin,amax,def_ = real_stats(cls,lv,ua,ud,uh,rm,art,st,en)
    atk=(amin+amax)//2
    max_f, killer_atk, killer_dmg = simulate(hp, atk, def_)
    if max_f >= 100:
        note = "✅ CLEAR T100!"
    else:
        note = f"chết T{max_f+1} (npc_atk={killer_atk}, {killer_dmg}dmg/hit, {hp//max(1,killer_dmg)} hits)"
    print(f"{name:<22} {hp:>6} {atk:>6} {def_:>5} | T{max_f:>8}   {note}")

print()
print("=== NPC STATS MẪU (ATK mới) ===")
print(f"{'Floor':>6} {'HP':>7} {'ATK':>6} {'DEF':>7} {'Boss':>5}")
for f in [1,5,10,20,30,50,70,100]:
    nhp,natk,ndef,isb = dung_npc(f)
    print(f"T{f:<5} {nhp:>7} {natk:>6} {ndef:>7} {'👑' if isb else ''}")
