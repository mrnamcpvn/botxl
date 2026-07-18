from bot.config import REWARD_WIN_COINS, REWARD_WIN_XP, LEVEL_XP_BASE
import random
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, DROP_WEIGHTS

DROP_CHANCE = 0.08


def calc_drop(role_mult: float = 1.0) -> dict | None:
    chance = DROP_CHANCE * role_mult
    if random.random() > chance:
        return None
    roll = random.random()
    if roll < 0.25:
        coins = random.randint(50, 200)
        return {"type": "coins", "amount": coins, "text": f"💰 +{coins}🪙 (rơi từ xác địch!)"}
    elif roll < 0.50:
        item = random.choice([i for i, it in SHOP_ITEMS.items() if it["type"] == "consumable"])
        return {"type": "item", "item_id": item, "item_name": SHOP_ITEMS[item]["name"],
                "text": f"🧪 Rơi: **{SHOP_ITEMS[item]['name']}**!"}
    else:
        # Equipment drop using rarity weights
        total = sum(DROP_WEIGHTS.values())
        r = random.randint(1, total)
        cum = 0
        star = 1
        for s, w in DROP_WEIGHTS.items():
            cum += w
            if r <= cum:
                star = s
                break
        items = [e for eid, e in EQUIPMENT.items() if e["star"] == star]
        if items:
            chosen = random.choice(items)
            eid = [k for k, v in EQUIPMENT.items() if v == chosen][0]
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
