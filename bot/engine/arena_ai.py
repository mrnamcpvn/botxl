import random
from bot.data.skills import SKILLS_DB


def _skill_by_id(skill_id: int) -> dict:
    return SKILLS_DB.get(skill_id, SKILLS_DB[1])


def _slot_available(player: dict, slot: str) -> bool:
    cd_key = f"{slot}_cd"
    sid = player.get("skill_equipped", {}).get(slot)
    return sid is not None and player.get(cd_key, 0) <= 0


def _best_skill_in_slot(player: dict, slot: str) -> int:
    sid = player.get("skill_equipped", {}).get(slot)
    return sid if sid else 1


def pick_action(player: dict, opponent: dict, flags: dict) -> dict:
    hp_pct = player.get("hp", 0) / max(player.get("hp_max", 1), 1) * 100
    opp_hp_pct = opponent.get("hp", 0) / max(opponent.get("hp_max", 1), 1) * 100

    burn_key = f"{opponent['id']}_burn"
    has_burn = burn_key in flags and flags[burn_key].get("turns", 0) > 0
    is_defending = flags.get(f"{player['id']}_defending", False)

    def_ok = _slot_available(player, "defense")
    atk_ok = _slot_available(player, "attack")
    spc_ok = _slot_available(player, "special")

    if hp_pct < 30 and def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            return {"type": "defense", "skill_id": sid}

    if opp_hp_pct < 20:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}

    if has_burn and atk_ok:
        return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}

    available = []
    weights = []
    if atk_ok:
        available.append(("attack", _best_skill_in_slot(player, "attack")))
        weights.append(50)
    if spc_ok:
        available.append(("special", _best_skill_in_slot(player, "special")))
        weights.append(30)
    if def_ok:
        sid = _best_skill_in_slot(player, "defense")
        skill = _skill_by_id(sid)
        if skill.get("type") != "defend" or not is_defending:
            available.append(("defense", sid))
            weights.append(20)

    if not available:
        if atk_ok:
            return {"type": "attack", "skill_id": _best_skill_in_slot(player, "attack")}
        if spc_ok:
            return {"type": "special", "skill_id": _best_skill_in_slot(player, "special")}
        return {"type": "attack", "skill_id": 1}

    choice = random.choices(available, weights=weights, k=1)[0]
    return {"type": choice[0], "skill_id": choice[1]}
