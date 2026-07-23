from bot.config import REWARD_WIN_COINS, REWARD_WIN_XP, LEVEL_XP_BASE
import random
from datetime import datetime, timezone, timedelta
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, DROP_WEIGHTS

DROP_CHANCE = 0.15

_HH_SLOTS = [(12, 30, 13, 30), (1, 0, 5, 0)]


def is_happy_hour() -> bool:
    tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    for sh, sm, eh, em in _HH_SLOTS:
        s = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        e = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if s <= e:
            if s <= now <= e:
                return True
        else:
            if now >= s or now <= e:
                return True
    return False

# Build lookup tables một lần khi module load — tránh O(n) scan mỗi drop
_CONSUMABLE_IDS: list[int] = [i for i, it in SHOP_ITEMS.items() if it["type"] == "consumable"]
_EQUIP_BY_STAR: dict[int, list[int]] = {}
for _eid, _e in EQUIPMENT.items():
    _EQUIP_BY_STAR.setdefault(_e["star"], []).append(_eid)
# Cumulative weight table cho weighted random star
_STAR_CUMULATIVE: list[tuple[int, int]] = []
_cum = 0
for _star, _weight in DROP_WEIGHTS.items():
    _cum += _weight
    _STAR_CUMULATIVE.append((_star, _cum))
_TOTAL_WEIGHT: int = _cum


def calc_drop(role_mult: float = 1.0, codex_drop_pct: int = 0, cult_drop_pct: int = 0) -> dict | None:
    chance = DROP_CHANCE * role_mult
    if codex_drop_pct:
        chance *= (1 + codex_drop_pct / 100)
    if cult_drop_pct:
        chance *= (1 + cult_drop_pct / 100)
    if random.random() > chance:
        return None
    roll = random.random()
    if roll < 0.25:
        coins = random.randint(50, 200)
        return {"type": "coins", "amount": coins, "text": f"💰 +{coins}🪙 (rơi từ xác địch!)"}
    elif roll < 0.50:
        item = random.choice(_CONSUMABLE_IDS)
        return {"type": "item", "item_id": item, "item_name": SHOP_ITEMS[item]["name"],
                "text": f"🧪 Rơi: **{SHOP_ITEMS[item]['name']}**!"}
    else:
        # Weighted random star dùng cumulative table — O(n stars) thay vì O(n items)
        r = random.randint(1, _TOTAL_WEIGHT)
        star = 1
        for s, cum in _STAR_CUMULATIVE:
            if r <= cum:
                star = s
                break
        eids = _EQUIP_BY_STAR.get(star)
        if eids:
            eid = random.choice(eids)
            chosen = EQUIPMENT[eid]
            return {"type": "equip", "equip_id": eid, "equip_name": chosen["name"],
                    "star": star, "slot": chosen["slot"],
                    "text": f"⚒️ Rơi: {STAR_LABELS.get(star, '⭐')} **{chosen['name']}**!"}
        return None


async def apply_drop(db, player_id: str, drop: dict) -> bool:
    if drop["type"] == "coins":
        await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (drop["amount"], player_id))
        return True
    elif drop["type"] == "item":
        cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?", (player_id, drop["item_id"]))
        row = await cursor.fetchone()
        if row:
            await db.execute("UPDATE inventory SET quantity=quantity+1 WHERE player_id=? AND item_id=?", (player_id, drop["item_id"]))
        else:
            await db.execute("INSERT INTO inventory (player_id, item_id, quantity) VALUES (?, ?, 1)", (player_id, drop["item_id"]))
        return True
    elif drop["type"] == "equip":
        await db.execute(
            "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
            (player_id, drop["equip_id"])
        )
        return True
    return False


def calc_level(total_xp: int) -> tuple[int, int]:
    level = 1
    xp = total_xp
    while xp >= level * LEVEL_XP_BASE:
        xp -= level * LEVEL_XP_BASE
        level += 1
    return level, xp


def calc_rewards(winner: bool, my_level: int = 1, opponent_level: int = 1) -> tuple[int, int]:
    if not winner:
        return 0, 0
    coins = REWARD_WIN_COINS
    xp = REWARD_WIN_XP
    gap = abs(my_level - opponent_level)
    if my_level < opponent_level:
        mult = 1 + gap * 0.5
        coins = int(coins * mult)
        xp = int(xp * mult)
    elif my_level > opponent_level:
        if gap >= 3:
            return 0, 0
        mult = max(0.1, 1 - gap * 0.3)
        coins = int(coins * mult)
        xp = int(xp * mult)
    return coins, xp


def apply_rewards(pdata: dict, coins: int, xp: int) -> bool:
    pdata["coins"] = pdata.get("coins", 0) + coins
    old_level = pdata.get("level", 1)
    new_level, _ = calc_level(pdata.get("xp", 0) + xp)
    pdata["xp"] = pdata.get("xp", 0) + xp
    pdata["level"] = new_level
    if new_level > old_level:
        from bot.config import STAT_POINTS_PER_LEVEL
        pdata["stat_points"] = pdata.get("stat_points", 0) + (new_level - old_level) * STAT_POINTS_PER_LEVEL
        return True
    return False
