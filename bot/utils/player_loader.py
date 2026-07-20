"""
Shared utility: load đầy đủ thông tin player từ DB vào dict.
Thay thế code copy-paste ở arena.py, battle_view.py, npc.py, dungeon.py.
"""
import time
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.engine.battle import regen_hp


async def load_player_full(db, pid: str, *, reset_cd: bool = False) -> dict | None:
    """
    Load player + skill slots + equipment (kể cả hidden_stats) + buffs.
    Tự động gọi regen_hp.
    Nếu reset_cd=True thì đặt attack/special/defense_cd = 0 (dùng cho NPC/dungeon fights).
    Trả None nếu không tìm thấy player.
    """
    cursor = await db.execute("SELECT * FROM players WHERE id=?", (pid,))
    row = await cursor.fetchone()
    if not row:
        return None
    pdata = dict(row)

    # Skill slots
    slots_cursor = await db.execute(
        "SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (pid,))
    slots = {}
    async for r in slots_cursor:
        slots[r[0]] = r[1]
    pdata["skill_equipped"] = slots if slots else {
        "attack": 1, "special": 5, "defense": 10, "passive": 14
    }

    # Equipment (bao gồm hidden_stats)
    eq_cursor = await db.execute(
        "SELECT id, item_id, enhance, hidden_stats FROM player_equipment WHERE player_id=? AND equipped=1",
        (pid,))
    equipped = {}
    equip_items = {}
    equip_enhances = {}
    equip_hidden = {}
    async for r in eq_cursor:
        eq_id = r[0]
        eiid = r[1]
        enh = r[2]
        hidden = r[3] if r[3] else ""
        slot = None
        if eiid in EQUIPMENT:
            slot = EQUIPMENT[eiid]["slot"]
        elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid].get("type") == "equipment":
            slot = SHOP_ITEMS[eiid]["slot"]
        if slot:
            equipped[slot] = eq_id
            equip_items[str(eq_id)] = eiid
            equip_enhances[str(eq_id)] = enh
            equip_hidden[str(eq_id)] = hidden
    pdata["equipped"] = equipped
    pdata["_equip_items"] = equip_items
    pdata["_equip_enhances"] = equip_enhances
    pdata["_equip_hidden"] = equip_hidden

    # Buffs
    buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (pid,))
    buff_row = await buff_cursor.fetchone()
    pdata["buffs"] = dict(buff_row) if buff_row else {}

    art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (pid,))
    art_row = await art_cursor.fetchone()
    pdata["_artifact_star"] = art_row[0] if art_row else 0
    pdata["_artifact_stones"] = art_row[1] if art_row else 0

    regen_hp(pdata)

    if reset_cd:
        pdata["attack_cd"] = 0
        pdata["special_cd"] = 0
        pdata["defense_cd"] = 0

    return pdata


async def load_equipped_wives(db, pid: str) -> list[dict]:
    """Load danh sách vợ đang equipped của player."""
    cursor = await db.execute(
        "SELECT * FROM player_wives WHERE player_id=? AND equipped=1 ORDER BY id ASC", (pid,))
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def save_player_data(db, pid: str, pdata: dict):
    """Ghi stats player vào DB (không commit)."""
    await db.execute(
        """UPDATE players SET hp=?, hp_max=?, attack_min=?, attack_max=?, defense=?,
             wins=?, losses=?, damage_dealt=?, damage_taken=?, coins=?, xp=?, level=?,
             stat_points=?, elo=?, attack_cd=?, special_cd=?, defense_cd=?, last_hp_update=?
             WHERE id=?""",
        (pdata.get("hp", 100), pdata.get("hp_max", 100),
         pdata.get("attack_min", 10), pdata.get("attack_max", 20),
         pdata.get("defense", 5),
         pdata.get("wins", 0), pdata.get("losses", 0),
         pdata.get("damage_dealt", 0), pdata.get("damage_taken", 0),
         pdata.get("coins", 0), pdata.get("xp", 0), pdata.get("level", 1),
         pdata.get("stat_points", 0), pdata.get("elo", 1000),
         pdata.get("attack_cd", 0), pdata.get("special_cd", 0),
         pdata.get("defense_cd", 0),
         pdata.get("last_hp_update", time.time()),
         pid))


async def level_wives_xp(db, player_id: str, battle_xp: int,
                         xp_share: float = 0.8) -> list[str]:
    """
    Cộng XP cho vợ đang equipped, trả list log lines.
    Dùng chung cho arena, npc, battle_view.
    """
    from bot.data.wives import WIVES
    gained = max(1, int(battle_xp * xp_share))
    lines = []
    if gained <= 0:
        return lines
    cursor = await db.execute(
        "SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (player_id,))
    async for row in cursor:
        w = dict(row)
        wd = WIVES.get(w["wife_id"], WIVES[1])
        new_xp = w["xp"] + gained
        new_level = w["level"]
        leftover = new_xp
        while leftover >= new_level * 50:
            leftover -= new_level * 50
            new_level += 1
        await db.execute("UPDATE player_wives SET xp=?, level=? WHERE id=?",
                         (leftover, new_level, w["id"]))
        lvl_up = f" ⬆Lv.{new_level}!" if new_level > w["level"] else ""
        lines.append(f"💕 {wd['emoji']} **{wd['name']}**: +{gained}XP{lvl_up}")
    return lines
