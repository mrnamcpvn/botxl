import random
import time
from bot.data.skills import SKILLS_DB
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT
from bot.data.classes import CLASSES
from bot.config import HP_REGEN_INTERVAL, HP_REGEN_RATE, ENHANCE_BONUS_PER_LEVEL


def calc_class_stat(base: int, scale: int, level: int) -> int:
    return base + scale * (level - 1)


def get_effective_stats(pdata: dict) -> dict:
    cls_def = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
    lvl = pdata.get("level", 1)
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
            mult = 1 + enhance * ENHANCE_BONUS_PER_LEVEL
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
    hp_gain = ticks * HP_REGEN_RATE
    old = pdata.get("hp", 0)
    eff_max = get_effective_stats(pdata).get("hp_max", 100)
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

    # ─── DEFENSE moves ───
    if cat == "defense":
        if skill["type"] == "defend":
            flags["p1_defending" if is_p1_turn else "p2_defending"] = True
            heal_pct = skill.get("heal_pct", 8)
            heal_amt = int(attacker.get("hp_max", 100) * heal_pct / 100)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker.get("hp", 0) + heal_amt)
            result_lines.append(f"🛡️ **{skill['name']}** — \u00d73 DEF + h\u1ed3i {heal_amt}HP! \u2602\ufe0f")
            attacker[f"{cat}_cd"] = skill.get("cooldown", 0)

        elif skill["type"] == "heal":
            heal_pct = skill.get("heal_pct", 40)
            heal_amt = int(attacker.get("hp_max", 100) * heal_pct / 100)
            old = attacker.get("hp", 0)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker["hp"] + heal_amt)
            for kb in ["_burn", "_def_reduced"]:
                attacker.pop(kb, None)
            if is_p1_turn:
                flags["p1_stunned"] = False
            else:
                flags["p2_stunned"] = False
            result_lines.append(f"💚 **{skill['name']}** — h\u1ed3i **{attacker['hp'] - old} HP**!")
            attacker[f"{cat}_cd"] = skill.get("cooldown", 0)

        elif skill["type"] == "shield":
            sh_pct = skill.get("shield_pct", 35)
            sh_amt = int(attacker.get("hp_max", 100) * sh_pct / 100)
            flags[f"p{1 if is_p1_turn else 2}_shield_hp"] = sh_amt
            flags[f"p{1 if is_p1_turn else 2}_shield_pop_heal"] = skill.get("shield_pop_heal", 15)
            result_lines.append(f"🛡️ **{skill['name']}** — khi\u00ean {sh_amt}HP! (+{skill.get('shield_pop_heal', 15)}% khi v\u1ee1)")
            attacker[f"{cat}_cd"] = skill.get("cooldown", 0)

        elif skill["type"] == "counter":
            flags[f"p{1 if is_p1_turn else 2}_counter"] = skill.get("multiplier", 2.5)
            flags[f"p{1 if is_p1_turn else 2}_counter_immune"] = True
            result_lines.append(f"🔄 **{skill['name']}** — mi\u1ec5n dmg + ph\u1ea3n \u00d7{skill.get('multiplier', 2.5)}!")
            attacker[f"{cat}_cd"] = skill.get("cooldown", 0)

    # ─── DAMAGE moves (attack + special) ───
    else:
        atk_eff = get_effective_stats(attacker)
        def_eff = get_effective_stats(defender)
        atk_buffs = attacker.get("buffs", {})
        def_buffs = defender.get("buffs", {})

        # Dodge passive check
        def_passive = get_equipped_skill(defender, "passive")
        if def_passive["type"] == "dodge":
            if random.random() < def_passive["dodge_chance"] / 100:
                result_lines.append(f"🍀 **{defender.get('name', '???')} N\u00c9 \u0110\u00d2N!**")
                attacker[f"{cat}_cd"] = skill.get("cooldown", 0)
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
        defending = flags.get("p1_defending" if not is_p1_turn else "p2_defending", False)
        eff_def = def_eff["defense"] * 2 if defending else def_eff["defense"]
        if def_buffs.get("defense_boost", 0) > 0:
            eff_def = int(eff_def * 1.50)
            result_lines.append("🛡️ Giáp Chuối +50%!")
        if skill.get("def_reduce_pct"):
            eff_def = int(eff_def * (100 - skill["def_reduce_pct"]) / 100)
            result_lines.append(f"🌀 -{skill['def_reduce_pct']}% DEF!")
        if skill.get("pierce_pct"):
            eff_def = int(eff_def * (100 - skill["pierce_pct"]) / 100)

        damage = max(base_dmg // 4, base_dmg - eff_def)

        # Class perk: defend_reduce
        def_class = defender.get("class_id", "banxabong")
        if get_class_perk(def_class) == "defend_reduce" and defending:
            damage = int(damage * 0.9)

        # Class perk: first_strike
        atk_class = attacker.get("class_id", "banxabong")
        if get_class_perk(atk_class) == "first_strike":
            turn_count = flags.get("turn_count", 0)
            if turn_count == 0:
                damage = int(damage * 1.5)

        # Last Stand (defender passive)
        if def_passive["type"] == "last_stand":
            threshold = def_passive.get("hp_threshold", 30)
            if get_class_perk(def_class) == "last_stand_boost":
                threshold = 40
            if defender.get("hp", 0) <= defender.get("hp_max", 100) * threshold / 100:
                damage = int(damage * (100 - def_passive["dmg_reduce_pct"]) / 100)
                result_lines.append(f"💎 GI\u00c1P B\u1ea4T T\u1eec! -{def_passive['dmg_reduce_pct']}% dmg!")

        # Counter immune
        immune_key = f"p{1 if not is_p1_turn else 2}_counter_immune"
        if flags.pop(immune_key, None):
            result_lines.append(f"🔄 {defender.get('name', '???')} MI\u1ec4N TO\u00c0N B\u1ed8 S\u00c1T TH\u01af\u01a0NG!")
            damage = 0

        # Shield
        shield_key = f"p{1 if not is_p1_turn else 2}_shield_hp"
        shield_hp = flags.get(shield_key, 0)
        if shield_hp > 0:
            if damage <= shield_hp:
                flags[shield_key] = shield_hp - damage
                result_lines.append(f"🛡️ Khi\u00ean h\u1ea5p th\u1ee5 {damage}!")
                damage = 0
            else:
                flags.pop(shield_key, None)
                pop_key = f"p{1 if not is_p1_turn else 2}_shield_pop_heal"
                pop_heal = flags.pop(pop_key, 15)
                heal_amt = int(defender.get("hp_max", 100) * pop_heal / 100)
                defender["hp"] = min(defender.get("hp_max", 100), defender.get("hp", 0) + heal_amt)
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
            rage_key = f"p{1 if is_p1_turn else 2}_rage_dmg"
            if flags.get(rage_key, 0) > 0:
                rage_bonus = int(flags.pop(rage_key, 0) * atk_passive.get("rage_multiplier", 2.0))
                damage += rage_bonus
                result_lines.append(f"💢 PH\u1eaaN N\u1ed8! +{rage_bonus} dmg!")

        # Apply damage
        defender["hp"] = max(0, defender.get("hp", 0) - damage)
        attacker["damage_dealt"] = attacker.get("damage_dealt", 0) + damage
        defender["damage_taken"] = defender.get("damage_taken", 0) + damage

        result_lines.append(f"{skill.get('icon', '')} **{skill['name']}**")
        if damage > 0:
            result_lines.append(f"💥 **{damage}** dmg!")

        # Rage accumulation on defender
        def_passive2 = get_equipped_skill(defender, "passive")
        if def_passive2["type"] == "rage":
            rage_pct = def_passive2.get("rage_pct", 50)
            if get_class_perk(def_class) == "rage_boost":
                rage_pct = int(rage_pct * 1.25)
            rage_accum_key = f"p{1 if not is_p1_turn else 2}_rage_dmg"
            flags[rage_accum_key] = flags.get(rage_accum_key, 0) + int(damage * rage_pct / 100)

        # Counter
        counter_key = f"p{1 if not is_p1_turn else 2}_counter"
        counter_mult = flags.pop(counter_key, None)
        if counter_mult:
            cd = int(damage * counter_mult)
            attacker["hp"] = max(0, attacker.get("hp", 0) - cd)
            attacker["damage_taken"] = attacker.get("damage_taken", 0) + cd
            defender["damage_dealt"] = defender.get("damage_dealt", 0) + cd
            result_lines.append(f"🔄 PH\u1ea2N \u0110\u00d2N! {cd} dmg!")

        # Lifesteal
        if skill.get("type") == "lifesteal":
            lifesteal_pct = skill.get("lifesteal_pct", 50)
            if get_class_perk(attacker.get("class_id", "")) == "lifesteal_boost":
                lifesteal_pct = int(lifesteal_pct * 1.2)
            heal = int(damage * lifesteal_pct / 100)
            attacker["hp"] = min(attacker.get("hp_max", 100), attacker.get("hp", 0) + heal)
            result_lines.append(f"🩡 H\u00fat {heal} HP!")

        # Burn
        if skill.get("type") == "burn":
            burn_key = f"p{1 if not is_p1_turn else 2}_burn"
            flags[burn_key] = {"pct": skill["burn_pct"], "turns": skill.get("burn_turns", 2)}
            result_lines.append(f"🔥 Thi\u00eau \u0111\u1ed1t {skill['burn_pct']}%/2t!")

        # Stun
        if skill.get("type") == "stun":
            if is_p1_turn:
                flags["p2_stunned"] = True
            else:
                flags["p1_stunned"] = True
            result_lines.append(f"🌑 Cho\u00e1ng! {defender.get('name', '???')} m\u1ea5t l\u01b0\u1ee3t!")

        # Clear defending flags
        flags["p1_defending"] = False
        flags["p2_defending"] = False

        attacker[f"{cat}_cd"] = skill.get("cooldown", 0)

    # ─── End of turn processing ───

    # Increment turn counter
    flags["turn_count"] = flags.get("turn_count", 0) + 1

    # Reduce cooldowns
    for p in [p1, p2]:
        for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
            if p.get(cdkey, 0) > 0:
                p[cdkey] -= 1
        if get_class_perk(p.get("class_id", "")) == "cd_reduce":
            for cdkey in ["attack_cd", "special_cd", "defense_cd"]:
                if p.get(cdkey, 0) > 0:
                    p[cdkey] -= 1

    # Regen passive
    for p in [p1, p2]:
        pid = p.get("skill_equipped", {}).get("passive")
        pskill = SKILLS_DB.get(pid)
        if pskill and pskill.get("type") == "regen":
            reg = int(p.get("hp_max", 100) * pskill["regen_pct"] / 100)
            p["hp"] = min(p.get("hp_max", 100), p.get("hp", 0) + reg)

    # Burn tick
    for i, p in enumerate([p1, p2]):
        key = f"p{i+1}_burn"
        burn = flags.get(key)
        if burn and burn.get("turns", 0) > 0:
            bd = int(p.get("hp_max", 100) * burn["pct"] / 100)
            p["hp"] = max(0, p.get("hp", 0) - bd)
            burn["turns"] -= 1
            result_lines.append(f"🔥 B\u1ecfng! {p.get('name', '???')} -{bd}HP ({burn['turns']}t)")
            if burn["turns"] <= 0:
                flags.pop(key, None)

    # ─── Check defeat ───
    finished = False
    winner_id = None
    if defender.get("hp", 0) <= 0:
        finished = True
        defender["hp"] = 0
        winner_id = attacker.get("id")
        result_lines.append(f"\n💀 **{defender.get('name', '???')}** b\u1ecb x\u1ecf l\u00e1 \u0111\u1ebfn ch\u1ebft!")
        result_lines.append(f"🏆 **{attacker.get('name', '???')}** CHI\u1ebeN TH\u1eaeNG! 🎉")

    return {
        "p1": p1,
        "p2": p2,
        "log_messages": result_lines,
        "finished": finished,
        "winner_id": winner_id,
    }
