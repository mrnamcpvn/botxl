"""
Cultivation engine — session toggle model.
!tulyen lần 1: bắt đầu tu luyện (lưu start time)
!tulyen lần 2: kết thúc, tính tu vi theo giờ thực đã ngồi
"""
import time
from bot.config import (
    CULTIVATION_REALMS, CULTIVATION_REALM_ICONS,
    CULTIVATION_BASE_COSTS, CULTIVATION_BREAKTHROUGH_RATES,
    CULTIVATION_FAIL_LOSS_PCT, CULTIVATION_SESSION_TUVI,
    CULTIVATION_COOLDOWN, CULTIVATION_MAX_HOURS,
    CULTIVATION_STAT_BONUS_PER_STAGE,
    CULTIVATION_PASSIVES, get_tuvi_cost,
)

MAX_REALM = len(CULTIVATION_REALMS) - 1  # 6
MAX_STAGE = 9


def realm_name(realm: int, stage: int) -> str:
    name = CULTIVATION_REALMS[realm] if 0 <= realm <= MAX_REALM else "???"
    return f"{name} bậc {stage}"


def realm_icon(realm: int) -> str:
    return CULTIVATION_REALM_ICONS[realm] if 0 <= realm <= MAX_REALM else "❓"


def full_title(realm: int, stage: int) -> str:
    icon = realm_icon(realm)
    return f"{icon} {realm_name(realm, stage)}"


def calc_session_tuvi(realm: int, stage: int, hours: float, role_mult: float = 1.0) -> int:
    """
    Tu vi nhận được dựa trên số giờ đã tu luyện.
    Rate tăng theo stage (bậc 1=1.0x, bậc 9=3.0x) và role_mult.
    Cap tối đa CULTIVATION_MAX_HOURS giờ.
    """
    if realm < 0 or realm > MAX_REALM:
        return 0
    hours = min(hours, CULTIVATION_MAX_HOURS)
    base_per_hour = CULTIVATION_SESSION_TUVI[realm]
    stage_mult = 1.0 + (stage - 1) * 0.25
    from bot.config import get_cultivation_role_mult
    cult_role_mult = get_cultivation_role_mult(role_mult)
    return int(base_per_hour * stage_mult * cult_role_mult * hours)


def is_cultivating(cdata: dict) -> bool:
    """Kiểm tra player đang trong trạng thái tu luyện không."""
    return bool(cdata.get("cultivating", 0))


def get_session_hours(cdata: dict) -> float:
    """Số giờ đã tu luyện kể từ lúc bắt đầu."""
    start = cdata.get("session_start", 0)
    if not start:
        return 0.0
    return (time.time() - start) / 3600


def calc_stat_bonus(realm: int, stage: int) -> float:
    """Tổng % bonus stats từ tu tiên (cộng dồn tất cả bậc đã qua)."""
    total_pct = 0.0
    for r in range(realm):
        total_pct += CULTIVATION_STAT_BONUS_PER_STAGE[r] * 9
    total_pct += CULTIVATION_STAT_BONUS_PER_STAGE[realm] * (stage - 1)
    return total_pct


def get_passive(realm: int) -> str | None:
    return CULTIVATION_PASSIVES.get(realm)


def breakthrough_info(realm: int, stage: int) -> dict:
    if stage >= MAX_STAGE:
        return {"can_break": False, "reason": "max_stage"}
    cost = get_tuvi_cost(realm, stage)
    rate = CULTIVATION_BREAKTHROUGH_RATES[stage - 1]
    return {
        "can_break": True,
        "tuvi_cost": cost,
        "success_rate": rate,
        "fail_loss_pct": CULTIVATION_FAIL_LOSS_PCT,
    }


def ascend_info(realm: int, stage: int) -> dict:
    if stage < MAX_STAGE:
        return {"can_ascend": False, "reason": "not_stage_9"}
    if realm >= MAX_REALM:
        return {"can_ascend": False, "reason": "max_realm"}
    from bot.config import CULTIVATION_ASCEND_ITEMS
    required = CULTIVATION_ASCEND_ITEMS.get(realm, {})
    return {
        "can_ascend": True,
        "next_realm": realm + 1,
        "required_items": required,
    }


def apply_cultivation_bonus(stats: dict, realm: int, stage: int) -> dict:
    """Áp dụng bonus tu tiên vào stats dict. Modifies in-place."""
    pct = calc_stat_bonus(realm, stage)
    if pct <= 0:
        return stats
    mult = 1 + pct / 100
    stats["hp_max"]     = int(stats["hp_max"] * mult)
    stats["attack_min"] = int(stats["attack_min"] * mult)
    stats["attack_max"] = int(stats["attack_max"] * mult)
    stats["defense"]    = int(stats["defense"] * mult)
    if stats.get("spd"):
        stats["spd"]    = int(stats["spd"] * mult)
    if stats.get("crit"):
        stats["crit"]   = int(stats["crit"] * mult)
    if stats.get("pierce"):
        stats["pierce"] = int(stats["pierce"] * mult)
    return stats
