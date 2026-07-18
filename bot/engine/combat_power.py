import math
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.engine.battle import get_effective_stats


def calc_combat_power(pdata: dict, wives_data: list = None) -> int:
    eff = get_effective_stats(pdata)

    hp = eff.get("hp_max", 0)
    atk_avg = (eff.get("attack_min", 0) + eff.get("attack_max", 0)) / 2
    defense = eff.get("defense", 0)
    spd = eff.get("spd", 0)
    crit = eff.get("crit", 0)
    pierce = eff.get("pierce", 0)
    dodge = eff.get("dodge", 0)
    reflect_val = eff.get("reflect", 0)
    regen = eff.get("regen_bonus", 0)
    level = pdata.get("level", 1)
    upgrade_hp = pdata.get("upgrade_hp", 0)
    upgrade_atk = pdata.get("upgrade_atk", 0)
    upgrade_def = pdata.get("upgrade_def", 0)
    damage_pct = eff.get("damage_pct", 0)

    total = (
        hp * 1
        + atk_avg * 2
        + defense * 3
        + spd * 10
        + crit * 3
        + pierce * 3
        + dodge * 5
        + reflect_val * 8
        + regen * 4
        + level * 10
        + upgrade_hp * 5
        + upgrade_atk * 8
        + upgrade_def * 8
        + damage_pct * 5
    )

    eq = pdata.get("equipped", {})
    equip_items = pdata.get("_equip_items", {})
    eq_star_total = 0
    for slot, eq_id in eq.items():
        item_id = equip_items.get(str(eq_id))
        if item_id and item_id in EQUIPMENT:
            eq_star_total += EQUIPMENT[item_id]["star"]
    total += eq_star_total * 80

    wife_level_total = 0
    if wives_data:
        for w in wives_data:
            wife_level_total += w.get("level", 0)
    total += wife_level_total * 30

    return int(total)


from bot.database import get_db


async def update_combat_power(player_id: str, pdata: dict = None, wives_data: list = None, db=None):
    own_db = db is None
    if own_db:
        db = await get_db()
    try:
        if pdata is None:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (player_id,))
            row = await cursor.fetchone()
            if not row:
                return
            pdata = dict(row)
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (player_id,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance, hidden_stats FROM player_equipment WHERE player_id=? AND equipped=1", (player_id,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            equip_hidden = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
                hidden = r[3] if len(r) > 3 and r[3] else ""
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    slot = SHOP_ITEMS[eiid]["slot"]
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances
        if wives_data is None:
            w_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (player_id,))
            wives_data = [dict(r) async for r in w_cursor]
        cp = calc_combat_power(pdata, wives_data)
        await db.execute("UPDATE players SET combat_power=? WHERE id=?", (cp, player_id))
        if own_db:
            await db.commit()
    finally:
        if own_db:
            await db.close()
