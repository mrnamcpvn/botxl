import random
from bot.database import get_db
from bot.data.wives import WIVES

RARITY_DMG_MULT = {"B": 0.5, "A": 0.75, "S": 1.0, "SVIP": 1.5}


async def load_equipped_wives(player_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM player_wives WHERE player_id=? AND equipped=1 ORDER BY id ASC",
            (player_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


def wife_auto_attack(wife: dict, opponent: dict, result_lines: list) -> int:
    wd = WIVES.get(wife["wife_id"], WIVES[1])
    rarity = wd["rarity"]
    level = wife.get("level", 1)
    mult = RARITY_DMG_MULT.get(rarity, 0.5)

    base_dmg = random.randint(4, 10) * level
    dmg = max(1, int(base_dmg * mult))
    opponent["hp"] = max(0, opponent.get("hp", 0) - dmg)

    result_lines.append(
        f"💕 {wd['emoji']} **{wd['name']}** ({wd['rarity']} Lv.{level}) → **-{dmg}HP**!")
    return dmg


def wife_gain_xp(wife: dict, battle_xp: int) -> tuple[int, bool]:
    gained = max(1, int(battle_xp * 0.3))
    old_level = wife.get("level", 1)
    wife["xp"] = wife.get("xp", 0) + gained
    new_level = old_level
    while wife["xp"] >= new_level * 50:
        wife["xp"] -= new_level * 50
        new_level += 1
    wife["level"] = new_level
    return gained, new_level > old_level
