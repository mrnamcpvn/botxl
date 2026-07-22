"""
Shared utility: load đầy đủ thông tin player từ DB vào dict.
Thay thế code copy-paste ở arena.py, battle_view.py, npc.py, dungeon.py.
"""
import time
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import SET_BONUSES
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
    if not slots:
        # Ghi default skill slots vào DB nếu player chưa có
        default_slots = {"attack": 1, "special": 5, "defense": 10, "passive": 14}
        for slot, skill_id in default_slots.items():
            await db.execute(
                "INSERT OR IGNORE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)",
                (pid, slot, skill_id))
        await db.execute(
            "INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, 1)", (pid,))
        await db.commit()
        slots = default_slots
    pdata["skill_equipped"] = slots

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

    eq_ids = list(equip_items.keys())
    socket_data = {}
    if eq_ids:
        placeholders = ",".join("?" for _ in eq_ids)
        sc = await db.execute(
            f"SELECT equip_instance_id, socket_1, socket_2, socket_3, socket_4 FROM equipment_sockets WHERE equip_instance_id IN ({placeholders})",
            [int(eid) for eid in eq_ids])
        async for sr in sc:
            eid = sr[0]
            socket_data[str(eid)] = {
                "socket_1": sr[1] or "", "socket_2": sr[2] or "",
                "socket_3": sr[3] or "", "socket_4": sr[4] or "",
            }
    pdata["_equip_sockets"] = socket_data

    # Set bonus — tính theo tổng sao thay vì cùng sao
    pdata["_set_bonus"] = None
    total_stars = 0
    equipped_count = 0
    for slot, eq_id in equipped.items():
        item_id = equip_items.get(str(eq_id))
        if item_id and item_id in EQUIPMENT:
            total_stars += EQUIPMENT[item_id]["star"]
            equipped_count += 1
    if equipped_count == 6:
        for min_stars in sorted(SET_BONUSES.keys(), reverse=True):
            if total_stars >= min_stars:
                pdata["_set_bonus"] = SET_BONUSES[min_stars]
                break

    # Buffs
    buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (pid,))
    buff_row = await buff_cursor.fetchone()
    pdata["buffs"] = dict(buff_row) if buff_row else {}

    art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (pid,))
    art_row = await art_cursor.fetchone()
    pdata["_artifact_star"] = art_row[0] if art_row else 0
    pdata["_artifact_stones"] = art_row[1] if art_row else 0

    codex_cursor = await db.execute(
        "SELECT npc_id, kills FROM monster_codex WHERE player_id=?", (pid,))
    codex_kills = {}
    async for cr in codex_cursor:
        codex_kills[str(cr[0])] = cr[1]
    pdata["_codex_kills"] = codex_kills

    # Cultivation (Tu Tiên)
    cult_cursor = await db.execute(
        "SELECT realm, stage, tuvi, last_collect, cultivating, session_start FROM cultivation WHERE player_id=?",
        (pid,))
    cult_row = await cult_cursor.fetchone()
    pdata["_cult_realm"]         = cult_row[0] if cult_row else -1
    pdata["_cult_stage"]         = cult_row[1] if cult_row else 1
    pdata["_cult_tuvi"]          = cult_row[2] if cult_row else 0
    pdata["_cult_last_collect"]  = cult_row[3] if cult_row else 0
    pdata["_cult_cultivating"]   = bool(cult_row[4]) if cult_row else False
    pdata["_cult_session_start"] = cult_row[5] if cult_row else 0

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
