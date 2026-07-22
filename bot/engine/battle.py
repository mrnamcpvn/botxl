import random
import time
import json
from bot.data.skills import SKILLS_DB
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT, SET_BONUSES
from bot.data.classes import CLASSES
from bot.config import HP_REGEN_INTERVAL, HP_REGEN_PCT, ENHANCE_BONUS_PER_LEVEL, GLOBAL_HP_MULT, GLOBAL_DEF_MULT

# Conversion: raw equipment stat → battle-effective percentage
# raw can reach 500-700 at absolute endgame, so divisors are tuned for balance
BATTLE_STAT_DIVISORS = {"crit": 3, "pierce": 7, "dodge": 5}
BATTLE_STAT_CAPS     = {"crit": 50, "pierce": 35, "dodge": 25}


def stat_to_pct(raw: int, stat_name: str) -> int:
    """Convert raw accumulated stat to effective battle percentage."""
    if raw <= 0:
        return 0
    divisor = BATTLE_STAT_DIVISORS.get(stat_name, 5)
    cap = BATTLE_STAT_CAPS.get(stat_name, 100)
    return min(int(raw / divisor), cap)


def _apply_cd(attacker: dict, skill: dict) -> int:
    cd = skill.get("cooldown", 0)
    if cd > 0 and get_class_perk(attacker.get("class_id", "")) == "cd_reduce":
        cd -= 1
    return cd


def calc_class_stat(base: int, scale: int, level: int) -> int:
    return base + scale * (level - 1)


def get_effective_stats(pdata: dict) -> dict:
    cls_def = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
    lvl = pdata.get("level", 1)

    if pdata.get("_npc_override"):
        hp_max = pdata.get("hp_max", 100)
        atk_min = pdata.get("attack_min", 10)
        atk_max = pdata.get("attack_max", 20)
        defense = pdata.get("defense", 5)
    else:
        upgrade_hp = pdata.get("upgrade_hp", 0)
        upgrade_atk = pdata.get("upgrade_atk", 0)
        upgrade_def = pdata.get("upgrade_def", 0)
        hp_max = calc_class_stat(cls_def["hp_base"], cls_def["hp_scale"], lvl) + upgrade_hp * 10
        atk_min = calc_class_stat(cls_def["atk_base"], cls_def["atk_scale"], lvl) + upgrade_atk * 2
        atk_max = atk_min + 5 + upgrade_atk
        defense = calc_class_stat(cls_def["def_base"], cls_def["def_scale"], lvl) + upgrade_def * 2

    spd = 0
    crit = 0
    pierce = 0
    dodge = 0
    reflect = 0
    regen = 0

    eq = pdata.get("equipped", {})
    equip_items = pdata.get("_equip_items", {})
    equip_enhances = pdata.get("_equip_enhances", {})
    for slot, eq_id in eq.items():
        if not eq_id:
            continue
        item_id = equip_items.get(str(eq_id))
        if item_id and item_id in SHOP_ITEMS:
            for k, v in SHOP_ITEMS[item_id]["effect"].items():
                if k == "hp_max": hp_max += v
                elif k == "attack_min": atk_min += v
                elif k == "attack_max": atk_max += v
                elif k == "defense": defense += v
        elif item_id and item_id in EQUIPMENT:
            enhance = equip_enhances.get(str(eq_id), 0)
            enhance_bonus = ENHANCE_BONUS_PER_LEVEL
            if EQUIPMENT[item_id]["star"] == 6:
                enhance_bonus = 0.12
            elif EQUIPMENT[item_id]["star"] >= 7:
                enhance_bonus = 0.15
            mult = 1 + enhance * enhance_bonus
            for k, v in EQUIPMENT[item_id]["stats"].items():
                val = int(v * mult)
                if k == "hp" or k == "hp_max": hp_max += val
                elif k == "attack_min": atk_min += val
                elif k == "attack_max": atk_max += val
                elif k == "defense": defense += val
                elif k == "spd": spd += val
                elif k == "crit": crit += val
                elif k == "pierce": pierce += val
                elif k == "dodge": dodge += val
                elif k == "reflect": reflect += val
                elif k == "regen": regen += val

    equip_hidden = pdata.get("_equip_hidden", {})
    for slot, eq_id in eq.items():
        hidden_json = equip_hidden.get(str(eq_id), "")
        if hidden_json:
            try:
                hs = json.loads(hidden_json)
                for k, v in hs.items():
                    if k == "hp" or k == "hp_max": hp_max += v
                    elif k == "attack_min": atk_min += v
                    elif k == "attack_max": atk_max += v
                    elif k == "defense": defense += v
                    elif k == "spd": spd += v
                    elif k == "crit": crit += v
                    elif k == "pierce": pierce += v
                    elif k == "dodge": dodge += v
                    elif k == "reflect": reflect += v
                    elif k == "regen": regen += v
            except:
                pass

    # Gem socket stats
    from bot.config import GEM_TYPES
    eq = pdata.get("equipped", {})
    socket_data = pdata.get("_equip_sockets", {})
    for slot, eq_id in eq.items():
        sockets = socket_data.get(str(eq_id), {})
        for sk in ["socket_1", "socket_2", "socket_3", "socket_4"]:
            gem_str = sockets.get(sk, "")
            if not gem_str or ":" not in gem_str:
                continue
            parts = gem_str.split(":")
            gem_type = parts[0]
            gem_level = int(parts[1]) if len(parts) > 1 else 1
            if gem_type not in GEM_TYPES:
                continue
            levels = GEM_TYPES[gem_type]["levels"]
            if gem_level < 1 or gem_level > len(levels):
                continue
            val = levels[gem_level - 1]
            if gem_type == "hp":
                hp_max += val
            elif gem_type == "atk":
                atk_min += val
                atk_max += val
            elif gem_type == "def":
                defense += val
            elif gem_type == "spd":
                spd += val
            elif gem_type == "crit":
                crit += val
            elif gem_type == "pierce":
                pierce += val

    damage_pct = 0
    passive_id = pdata.get("skill_equipped", {}).get("passive")
    skill = SKILLS_DB.get(passive_id)
    if skill and skill["category"] == "passive" and skill["type"] == "stat_boost":
        if skill.get("stat") == "hp_max":
            hp_max += int(hp_max * skill["boost_pct"] / 100)
        elif skill.get("stat") == "damage":
            damage_pct = skill["boost_pct"]
        elif skill.get("stat") == "defense":
            defense += skill.get("boost_flat", 0)

    mult = pdata.get("role_mult", 1.0)
    if mult != 1.0:
        hp_max = int(hp_max * mult)
        atk_min = int(atk_min * mult)
        atk_max = int(atk_max * mult)
        defense = int(defense * mult)

    artifact_star = pdata.get("_artifact_star", 0)
    if artifact_star > 0:
        art_mult = 1 + artifact_star * 0.15
        hp_max = int(hp_max * art_mult)
        atk_min = int(atk_min * art_mult)
        atk_max = int(atk_max * art_mult)
        defense = int(defense * art_mult)
        spd = int(spd * art_mult)
        crit = int(crit * art_mult)
        pierce = int(pierce * art_mult)
        dodge = int(dodge * art_mult)
        reflect = int(reflect * art_mult)
        regen = int(regen * art_mult)

    set_bonus = pdata.get("_set_bonus")
    if set_bonus:
        if set_bonus.get("hp_pct"):
            hp_max = int(hp_max * (1 + set_bonus["hp_pct"] / 100))
        if set_bonus.get("atk_pct"):
            atk_min = int(atk_min * (1 + set_bonus["atk_pct"] / 100))
            atk_max = int(atk_max * (1 + set_bonus["atk_pct"] / 100))
        if set_bonus.get("def_pct"):
            defense = int(defense * (1 + set_bonus["def_pct"] / 100))
        if set_bonus.get("crit"):
            crit += set_bonus["crit"]
        if set_bonus.get("dodge"):
            dodge += set_bonus["dodge"]

    hp_max = int(hp_max * GLOBAL_HP_MULT) if not pdata.get("_npc_override") else hp_max
    defense = int(defense * GLOBAL_DEF_MULT) if not pdata.get("_npc_override") else defense

    return {
        "hp_max": hp_max,
        "attack_min": atk_min,
        "attack_max": atk_max,
        "defense": defense,
        "damage_pct": damage_pct,
        "spd": spd,
        "crit": crit,
        "pierce": pierce,
        "dodge": dodge,
        "reflect": reflect,
        "regen_bonus": regen,
    }


def get_equipped_skill(pdata: dict, category: str) -> dict:
    sid = pdata.get("skill_equipped", {}).get(category)
    return SKILLS_DB.get(sid, SKILLS_DB.get(1))


def regen_hp(pdata: dict, now: float = None) -> bool:
    if now is None:
        now = time.time()
    last = pdata.get("last_hp_update", 0)
    if last <= 0:
        pdata["last_hp_update"] = now
        return False
    elapsed = now - last
    if elapsed < HP_REGEN_INTERVAL:
        return False
    ticks = int(elapsed // HP_REGEN_INTERVAL)
    eff_max = get_effective_stats(pdata).get("hp_max", 100)
    hp_gain = ticks * eff_max * HP_REGEN_PCT // 100
    old = pdata.get("hp", 0)
    pdata["hp"] = min(eff_max, pdata["hp"] + hp_gain)
    pdata["hp"] = max(0, pdata["hp"])
    pdata["last_hp_update"] = now
    return pdata["hp"] != old


def get_class_perk(class_id: str):
    cls = CLASSES.get(class_id)
    return cls.get("perk") if cls else None


async def execute_action(p1: dict, p2: dict, turn_player: int, action: dict, flags: dict):
    attacker = p1 if turn_player == 0 else p2
    defender = p2 if turn_player == 0 else p1
    is_p1_turn = turn_player == 0
    result_lines = []

    skill = SKILLS_DB.get(action["skill_id"], SKILLS_DB[1])
    cat = action["type"]

    # Cache stats một lần cho toàn bộ turn — tránh gọi lại nhiều lần trong cùng 1 action
    _eff_cache: dict[str, dict] = {}

    def _eff(p: dict) -> dict:
        pid = p.get("id", id(p))
        if pid not in _eff_cache:
            _eff_cache[pid] = get_effective_stats(p)
        return _eff_cache[pid]

    # ─── DEFENSE moves ───
    if cat == "defense":
        atk_eff = _eff(attacker)
        if skill["type"] == "defend":
            flags[f"{attacker['id']}_defending"] = True
            heal_pct = skill.get("heal_pct", 8)
            heal_amt = int(atk_eff["hp_max"] * heal_pct / 100)
            attacker["hp"] = min(atk_eff["hp_max"], attacker.get("hp", 0) + heal_amt)
            result_lines.append(f"🛡️ **{skill['name']}** — \u00d73 DEF + h\u1ed3i {heal_amt}HP! \u2602\ufe0f")
            attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)

        elif skill["type"] == "heal":
            heal_pct = skill.get("heal_pct", 40)
            heal_amt = int(_eff(attacker)["hp_max"] * heal_pct / 100)
            old = attacker.get("hp", 0)
            attacker["hp"] = min(atk_eff["hp_max"], attacker["hp"] + heal_amt)
            for kb in ["_burn", "_def_reduced"]:
                attacker.pop(kb, None)
            flags[f"{attacker['id']}_stunned"] = False
            result_lines.append(f"💚 **{skill['name']}** — h\u1ed3i **{attacker['hp'] - old} HP**!")
            attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)

        elif skill["type"] == "shield":
            sh_pct = skill.get("shield_pct", 35)
            sh_amt = int(atk_eff["hp_max"] * sh_pct / 100)
            a_id = attacker["id"]
            flags[f"{a_id}_shield_hp"] = sh_amt
            flags[f"{a_id}_shield_pop_heal"] = skill.get("shield_pop_heal", 15)
            result_lines.append(f"🛡️ **{skill['name']}** — khi\u00ean {sh_amt}HP! (+{skill.get('shield_pop_heal', 15)}% khi v\u1ee1)")
            attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)

        elif skill["type"] == "counter":
            c_mult = skill.get("multiplier", 0.2)
            a_id = attacker["id"]
            flags[f"{a_id}_counter"] = c_mult
            flags[f"{a_id}_counter_active"] = True
            result_lines.append(f"🔄 **{skill['name']}** — gi\u1ea3m 80% dmg + ph\u1ea3n {int(c_mult*100)}%!")
            attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)

    # ─── DAMAGE moves (attack + special) ───
    else:
        atk_eff = _eff(attacker)
        def_eff = _eff(defender)
        atk_buffs = attacker.get("buffs", {})
        def_buffs = defender.get("buffs", {})

        # Dodge passive check
        def_passive = get_equipped_skill(defender, "passive")
        if def_passive["type"] == "dodge":
            if random.random() < def_passive["dodge_chance"] / 100:
                result_lines.append(f"🍀 **{defender.get('name', '???')} N\u00c9 \u0110\u00d2N!**")
                attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)
                hp1 = p1.get("hp", 0)
                hp2 = p2.get("hp", 0)
                for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                    for p in [p1, p2]:
                        if p.get(cdkey, 0) > 0:
                            p[cdkey] -= 1
                result_lines.append(f"❤️ {p1.get('name','?')}:`{p1.get('hp',0)}/{p1.get('hp_max',100)}`")
                result_lines.append(f"❤️ {p2.get('name','?')}:`{p2.get('hp',0)}/{p2.get('hp_max',100)}`")
                return {
                    "p1": p1, "p2": p2,
                    "log_messages": result_lines,
                    "finished": False,
                    "winner_id": None,
                }

        # Equipment-based dodge (NÉ)
        equip_dodge = stat_to_pct(def_eff.get("dodge", 0), "dodge")
        if equip_dodge > 0 and random.random() * 100 < equip_dodge:
            result_lines.append(f"💨 **{defender.get('name', '???')} NÉ ĐÒN ({equip_dodge}%)!**")
            attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)
            for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                for p in [p1, p2]:
                    if p.get(cdkey, 0) > 0:
                        p[cdkey] -= 1
            result_lines.append(f"❤️ {p1.get('name','?')}:`{p1.get('hp',0)}/{p1.get('hp_max',100)}`")
            result_lines.append(f"❤️ {p2.get('name','?')}:`{p2.get('hp',0)}/{p2.get('hp_max',100)}`")
            return {
                "p1": p1, "p2": p2,
                "log_messages": result_lines,
                "finished": False,
                "winner_id": None,
            }

        # Calculate base damage
        mult = skill.get("multiplier", 1.0)
        if skill.get("type") == "multi_hit":
            hits = skill.get("hits", 2)
            total = sum(int(random.randint(atk_eff["attack_min"], atk_eff["attack_max"]) * mult) for _ in range(hits))
            base_dmg = total
            result_lines.append(f"⚔️ **{skill['name']}** — {hits} \u0111\u00f2n!")
        else:
            base_dmg = int(random.randint(atk_eff["attack_min"], atk_eff["attack_max"]) * mult)

        # Legendary proc
        if cat == "special" and skill.get("legendary_chance"):
            lc = skill["legendary_chance"] / 100
            if atk_buffs.get("lucky"):
                lc *= 2
                result_lines.append("🎲 X\u00fac x\u1eafc k\u00edch ho\u1ea1t ×2!")
            if random.random() < lc:
                base_dmg = int(base_dmg * 1.67)
                result_lines.append("🌟 X\u1ece L\u00c1 TH\u1ea6N CH\u01af\u1ee2NG! \u00d75!")

        # Passive damage boost
        if atk_eff["damage_pct"] > 0:
            base_dmg = int(base_dmg * (1 + atk_eff["damage_pct"] / 100))

        # Buff attack boost (3 battles, 30% dmg)
        if atk_buffs.get("attack_boost", 0) > 0:
            base_dmg = int(base_dmg * 1.30)
            result_lines.append("⚡ Bùa Xỏ Lá +30%!")

        # Defense calculation
        defending = flags.get(f"{defender['id']}_defending", False)
        eff_def = def_eff["defense"] * 2 if defending else def_eff["defense"]
        if def_buffs.get("defense_boost", 0) > 0:
            eff_def = int(eff_def * 1.50)
            result_lines.append("🛡️ Giáp Chuối +50%!")
        if skill.get("def_reduce_pct"):
            eff_def = int(eff_def * (100 - skill["def_reduce_pct"]) / 100)
            result_lines.append(f"🌀 -{skill['def_reduce_pct']}% DEF!")
        if skill.get("pierce_pct"):
            eff_def = int(eff_def * (100 - skill["pierce_pct"]) / 100)

        # Equipment-based pierce (XUYÊN)
        equip_pierce = stat_to_pct(atk_eff.get("pierce", 0), "pierce")
        if equip_pierce > 0:
            eff_def = int(eff_def * (100 - equip_pierce) / 100)
            result_lines.append(f"🔱 XUYÊN {equip_pierce}% DEF!")

        damage = max(base_dmg // 4, base_dmg - eff_def)

        # Class perk: defend_reduce
        def_class = defender.get("class_id", "banxabong")
        if get_class_perk(def_class) == "defend_reduce" and defending:
            damage = int(damage * 0.8)

        # Class perk: first_strike
        atk_class = attacker.get("class_id", "banxabong")
        if get_class_perk(atk_class) == "first_strike":
            turn_count = flags.get("turn_count", 0)
            if turn_count == 0:
                damage = int(damage * 1.5)

        # Counter — 80% damage reduction
        d_id = defender["id"]
        original_damage = damage
        if flags.pop(f"{d_id}_counter_active", None):
            damage = max(1, int(damage * 0.2))
            result_lines.append(f"🔄 {defender.get('name', '???')} GI\u1ea2M 80% S\u00c1T TH\u01af\u01a0NG!")

        # Shield
        shield_key = f"{d_id}_shield_hp"
        shield_hp = flags.get(shield_key, 0)
        if shield_hp > 0:
            if damage <= shield_hp:
                flags[shield_key] = shield_hp - damage
                result_lines.append(f"🛡️ Khi\u00ean h\u1ea5p th\u1ee5 {damage}!")
                damage = 0
            else:
                flags.pop(shield_key, None)
                pop_key = f"{d_id}_shield_pop_heal"
                pop_heal = flags.pop(pop_key, 15)
                heal_amt = int(def_eff["hp_max"] * pop_heal / 100)
                defender["hp"] = min(def_eff["hp_max"], defender.get("hp", 0) + heal_amt)
                result_lines.append(f"🛡️ Khi\u00ean v\u1ee1! Tr\u00e0n {damage - shield_hp}! +{heal_amt}HP h\u1ed3i!")
                damage -= shield_hp

        # Self damage
        if skill.get("self_dmg_pct"):
            sd = int(attacker.get("hp", 0) * skill["self_dmg_pct"] / 100)
            attacker["hp"] = max(1, attacker.get("hp", 0) - sd)
            result_lines.append(f"💀 T\u1ef1 thi\u00eau {sd}HP!")

        # Rage (attacker passive)
        atk_passive = get_equipped_skill(attacker, "passive")
        if atk_passive["type"] == "rage":
            rage_key = f"{attacker['id']}_rage_dmg"
            if flags.get(rage_key, 0) > 0:
                rage_mult = atk_passive.get("rage_multiplier", 2.0)
                if get_class_perk(atk_class) == "rage_boost":
                    rage_mult = 2.5
                rage_bonus = int(flags.pop(rage_key, 0) * rage_mult)
                damage += rage_bonus
                result_lines.append(f"💢 PHẪN NỘ! +{rage_bonus} dmg!")

        # Equipment-based crit (CRIT) - final multiplier after all modifiers
        equip_crit = stat_to_pct(atk_eff.get("crit", 0), "crit")
        is_crit = False
        if equip_crit > 0 and random.random() * 100 < equip_crit:
            damage = int(damage * 1.5)
            is_crit = True

        # Cheat Death — né chết + hồi HP, chỉ 1 lần/trận, áp dụng cho cả player lẫn NPC
        cheat_death_proc = False
        cd_key = f"{defender['id']}_cheat_death_used"
        if def_passive["type"] == "cheat_death" and not flags.get(cd_key):
            if damage >= defender.get("hp", 0):
                damage = max(0, defender.get("hp", 0) - 1)
                cheat_death_proc = True
                flags[cd_key] = True
                # Đánh dấu để skip burn tick trong cùng turn này
                flags[f"{defender['id']}_cheat_death_this_turn"] = True

        # Apply damage
        defender["hp"] = max(0, defender.get("hp", 0) - damage)
        attacker["damage_dealt"] = attacker.get("damage_dealt", 0) + damage
        defender["damage_taken"] = defender.get("damage_taken", 0) + damage

        # Cheat death heal (hồi HP sau khi né chết)
        if cheat_death_proc:
            heal_pct = 50
            if get_class_perk(def_class) == "last_stand_boost":
                heal_pct = 70
            heal = int(def_eff["hp_max"] * heal_pct / 100)
            defender["hp"] = min(def_eff["hp_max"], defender["hp"] + heal)
            defender_name = defender.get("name", "???")
            result_lines.append(
                f"💎 **{defender_name}** kích hoạt **CHƯA CHẾT ĐÃ SỐNG LẠI!** "
                f"Thoát chết + hồi **{heal}HP**!"
            )

        result_lines.append(f"{skill.get('icon', '')} **{skill['name']}**")
        if damage > 0:
            crit_tag = " 💥CHÍ MẠNG!" if is_crit else ""
            result_lines.append(f"💥 **{damage}** dmg!{crit_tag}")

        # Rage accumulation on defender
        def_passive2 = get_equipped_skill(defender, "passive")
        if def_passive2["type"] == "rage":
            rage_pct = def_passive2.get("rage_pct", 50)
            if get_class_perk(def_class) == "rage_boost":
                rage_pct = int(rage_pct * 1.5)
            rage_accum_key = f"{defender['id']}_rage_dmg"
            flags[rage_accum_key] = flags.get(rage_accum_key, 0) + int(damage * rage_pct / 100)

        # Counter
        counter_key = f"{d_id}_counter"
        counter_mult = flags.pop(counter_key, None)
        if counter_mult:
            cd = int(original_damage * counter_mult)
            attacker["hp"] = max(0, attacker.get("hp", 0) - cd)
            attacker["damage_taken"] = attacker.get("damage_taken", 0) + cd
            defender["damage_dealt"] = defender.get("damage_dealt", 0) + cd
            result_lines.append(f"🔄 PH\u1ea2N \u0110\u00d2N {int(counter_mult*100)}%! {cd} dmg!")

        # Lifesteal
        if skill.get("type") == "lifesteal":
            lifesteal_pct = skill.get("lifesteal_pct", 50)
            if get_class_perk(attacker.get("class_id", "")) == "lifesteal_boost":
                lifesteal_pct = int(lifesteal_pct * 1.3)
            heal = int(damage * lifesteal_pct / 100)
            attacker["hp"] = min(atk_eff["hp_max"], attacker.get("hp", 0) + heal)
            result_lines.append(f"🩡 H\u00fat {heal} HP!")

        # Burn
        if skill.get("type") == "burn":
            burn_key = f"{defender['id']}_burn"
            flags[burn_key] = {"pct": skill["burn_pct"], "turns": skill.get("burn_turns", 2)}
            result_lines.append(f"🔥 Thi\u00eau \u0111\u1ed1t {skill['burn_pct']}%/2t!")

        # Stun
        if skill.get("type") == "stun":
            flags[f"{defender['id']}_stunned"] = True
            result_lines.append(f"🌑 Cho\u00e1ng! {defender.get('name', '???')} m\u1ea5t l\u01b0\u1ee3t!")

        # Clear defending flags for both
        for p in [p1, p2]:
            flags.pop(f"{p['id']}_defending", None)

        attacker[f"{cat}_cd"] = _apply_cd(attacker, skill)

    # ─── End of turn processing ───

    # Check defeat before any post-turn effects
    finished = False
    winner_id = None
    if p1.get("hp", 0) <= 0:
        finished = True
        p1["hp"] = 0
        winner_id = p2.get("id")
    elif p2.get("hp", 0) <= 0:
        finished = True
        p2["hp"] = 0
        winner_id = p1.get("id")

    if not finished:
        # Increment turn counter
        flags["turn_count"] = flags.get("turn_count", 0) + 1

        # Reduce cooldowns for current player only
        for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
            if attacker.get(cdkey, 0) > 0:
                attacker[cdkey] -= 1

        # Regen passive for both — dùng cache _eff thay vì gọi lại get_effective_stats
        for p in [p1, p2]:
            eff = _eff(p)
            pid = p.get("skill_equipped", {}).get("passive")
            pskill = SKILLS_DB.get(pid)
            if pskill and pskill.get("type") == "regen":
                reg = int(eff["hp_max"] * pskill["regen_pct"] / 100)
                p["hp"] = min(eff["hp_max"], p.get("hp", 0) + reg)

        # Burn tick — dùng cache _eff
        for p in [p1, p2]:
            eff = _eff(p)
            key = f"{p['id']}_burn"
            burn = flags.get(key)
            # Skip burn nếu cheat_death vừa kích hoạt trong turn này — tránh bị giết ngay sau khi né chết
            just_cheat_death = flags.pop(f"{p['id']}_cheat_death_this_turn", False)
            if burn and burn.get("turns", 0) > 0 and not just_cheat_death:
                bd = int(eff["hp_max"] * burn["pct"] / 100)
                p["hp"] = max(0, p.get("hp", 0) - bd)
                burn["turns"] -= 1
                result_lines.append(f"🔥 Bỏng! {p.get('name', '???')} -{bd}HP ({burn['turns']}t)")
                if burn["turns"] <= 0:
                    flags.pop(key, None)
            elif burn and just_cheat_death:
                # Vẫn giảm turns nhưng không gây damage trong turn này
                burn["turns"] -= 1
                result_lines.append(f"🔥 Bỏng nhẹ! {p.get('name', '???')} chịu được nhờ Chưa Chết Đã Sống Lại! ({burn['turns']}t)")
                if burn["turns"] <= 0:
                    flags.pop(key, None)

        # Check defeat again after burn
        if p1.get("hp", 0) <= 0:
            finished = True
            p1["hp"] = 0
            winner_id = p2.get("id")
            result_lines.append(f"\n🔥 **{p1.get('name', '???')}** ch\u00e1y ch\u1ebft!")
        elif p2.get("hp", 0) <= 0:
            finished = True
            p2["hp"] = 0
            winner_id = p1.get("id")
            result_lines.append(f"\n🔥 **{p2.get('name', '???')}** ch\u00e1y ch\u1ebft!")
    else:
        if p1.get("hp", 0) <= 0:
            loser = p1.get("name", "???")
            winner = p2.get("name", "???")
        else:
            loser = p2.get("name", "???")
            winner = p1.get("name", "???")
        result_lines.append(f"\n💀 **{loser}** b\u1ecb x\u1ecf l\u00e1 \u0111\u1ebfn ch\u1ebft!")
        result_lines.append(f"🏆 **{winner}** CHI\u1ebeN TH\u1eaeNG! 🎉")

    return {
        "p1": p1,
        "p2": p2,
        "log_messages": result_lines,
        "finished": finished,
        "winner_id": winner_id,
    }
