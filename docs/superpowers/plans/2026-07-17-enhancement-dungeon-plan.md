# Enhancement & Dungeon System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build equipment enhancement (0-9 stars) and "Vực Sâu Xỏ Lá" dungeon (100 floors) with stone drops, merged into a new per-instance equipment schema.

**Architecture:** New equipment table with per-item `id` and `enhance` column replaces quantity-based storage. Enhancement cog + dungeon cog follow existing cog/engine/view patterns. Battle engine applies `1 + enhance * 0.08` multiplier to equipment stats. Dungeon uses existing NPC battle flow adapted for floor progression.

**Tech Stack:** Python 3.12, discord.py 2.3+, aiosqlite, existing battle engine

---

### Task 1: Add config constants

**Files:**
- Modify: `bot/config.py`

- [ ] **Step 1: Add constants to config**

```python
# Enhancement
MAX_ENHANCE = 9
ENHANCE_BONUS_PER_LEVEL = 0.08    # +8% per enhance star

# Stone item IDs (mapped to inventory)
STONE_BASIC_ID = 1001
STONE_MEDIUM_ID = 1002
STONE_ADVANCED_ID = 1003

# Enhance costs: (target_star, stone_id, stone_qty, coin_cost)
ENHANCE_COSTS = {
    1: (STONE_BASIC_ID, 2, 200),
    2: (STONE_BASIC_ID, 4, 200),
    3: (STONE_BASIC_ID, 6, 200),
    4: (STONE_MEDIUM_ID, 2, 500),
    5: (STONE_MEDIUM_ID, 4, 500),
    6: (STONE_MEDIUM_ID, 6, 500),
    7: (STONE_ADVANCED_ID, 2, 1000),
    8: (STONE_ADVANCED_ID, 4, 1000),
    9: (STONE_ADVANCED_ID, 6, 1000),
}

# Enhance success rates: target_star -> probability
ENHANCE_SUCCESS_RATES = {
    1: 1.00, 2: 0.875, 3: 0.75,
    4: 0.625, 5: 0.50, 6: 0.375,
    7: 0.25, 8: 0.175, 9: 0.10,
}

# Dungeon
DUNGEON_MAX_FLOOR = 100
DUNGEON_REQUIRED_LEVEL = 7
DUNGEON_FREE_ENTRIES = 1
DUNGEON_MAX_TICKETS = 2
DUNGEON_TICKET_COST_1 = 200
DUNGEON_TICKET_COST_2 = 400
```

Place these at the end of `bot/config.py`, after the existing constants block (after line 30).

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from bot.config import *; print('OK')"`
Expected: prints `OK` or no output with exit 0.

- [ ] **Step 3: Commit**

```bash
git add bot/config.py
git commit -m "feat: add enhancement and dungeon config constants"
```

---

### Task 2: Database migration — new equipment schema + dungeon tables

**Files:**
- Modify: `bot/database.py`

- [ ] **Step 1: Add migration code to `init_db()`**

After the existing `player_equip_slots` migration block (after line 167, before `await db.commit()`), add:

```python
        # ── Migration: New per-instance equipment table ──
        try:
            await db.execute("INSERT INTO player_equipment_new (player_id, item_id, enhance, equipped) VALUES ('_mig_', 0, 0, 0)")
        except:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS player_equipment_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    enhance INTEGER DEFAULT 0,
                    equipped INTEGER DEFAULT 0
                );

                -- Migrate old equipment: quantity=N -> N rows
                INSERT INTO player_equipment_new (player_id, item_id, enhance, equipped)
                SELECT pe.player_id, pe.item_id, 0, 0
                FROM player_equipment pe
                CROSS JOIN (
                    WITH RECURSIVE cnt(x) AS (
                        SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 100
                    )
                    SELECT x FROM cnt
                ) counter
                WHERE counter.x <= pe.quantity;

                -- Mark equipped items
                UPDATE player_equipment_new
                SET equipped = 1
                WHERE id IN (
                    SELECT pen.id
                    FROM player_equipment_new pen
                    JOIN player_equip_slots pes
                        ON pes.player_id = pen.player_id AND pes.item_id = pen.item_id
                        AND pen.equipped = 0
                );

                DROP TABLE IF EXISTS player_equipment;
                DROP TABLE IF EXISTS player_equip_slots;
                ALTER TABLE player_equipment_new RENAME TO player_equipment;
            """)

        # ── Enhancement stones table ──
        await db.execute("""
            CREATE TABLE IF NOT EXISTS player_enhance_stones (
                player_id TEXT PRIMARY KEY,
                stone_basic INTEGER DEFAULT 0,
                stone_medium INTEGER DEFAULT 0,
                stone_advanced INTEGER DEFAULT 0
            )
        """)

        # ── Dungeon progress table ──
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dungeon_progress (
                player_id TEXT PRIMARY KEY,
                checkpoint INTEGER DEFAULT 0,
                daily_entries INTEGER DEFAULT 0,
                daily_tickets_bought INTEGER DEFAULT 0,
                last_entry_date TEXT DEFAULT '',
                last_week_reset TEXT DEFAULT ''
            )
        """)
```

- [ ] **Step 2: Test the migration**

Write and run a quick test script to verify migration on a copy of the DB:

Run: `python -c "from bot.database import init_db; import asyncio; asyncio.run(init_db()); print('Migration OK')"`
Expected: `Migration OK`

- [ ] **Step 3: Verify old tables are dropped**

Run: `python -c "
import asyncio, aiosqlite
async def check():
    from bot.config import DB_PATH
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    # Check new table exists
    c = await db.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='player_equipment'\")
    r = await c.fetchone()
    print('player_equipment exists:', bool(r))
    # Check old tables gone
    for t in ['player_equip_slots']:
        c = await db.execute(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'\")
        r = await c.fetchone()
        print(f'{t} exists:', bool(r))
    await db.close()
asyncio.run(check())
"`
Expected: player_equipment exists: True, player_equip_slots exists: False

- [ ] **Step 4: Commit**

```bash
git add bot/database.py
git commit -m "feat: migrate equipment to per-instance schema, add stones and dungeon tables"
```

---

### Task 3: Update battle engine for enhance multiplier

**Files:**
- Modify: `bot/engine/battle.py:34-54`

- [ ] **Step 1: Add enhance multiplier in `get_effective_stats()`**

In `bot/engine/battle.py`, add the import at line 7:
```python
from bot.config import HP_REGEN_INTERVAL, HP_REGEN_RATE, ENHANCE_BONUS_PER_LEVEL
```

Then replace lines 33-54 (the equipment application block) with:

```python
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
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from bot.engine.battle import get_effective_stats; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/engine/battle.py
git commit -m "feat: apply enhance multiplier (+8%/star) to equipment stats in battle"
```

---

### Task 4: Update `apply_drop` for new equipment schema

**Files:**
- Modify: `bot/engine/rewards.py:42-62`

- [ ] **Step 1: Change equipment insert to use new schema**

Replace the `elif drop["type"] == "equip":` block (lines 54-62) in `apply_drop()`:

```python
    elif drop["type"] == "equip":
        await db.execute(
            "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
            (player_id, drop["equip_id"])
        )
        return True
```

- [ ] **Step 2: Verify**

Run: `python -c "from bot.engine.rewards import apply_drop, calc_drop; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/engine/rewards.py
git commit -m "fix: update apply_drop to use new per-instance equipment schema"
```

---

### Task 5: Update shop cog — equip/unequip/inv for new schema

**Files:**
- Modify: `bot/cogs/shop.py`

This is a large change touching `_equip`, `_show_inv`, `_unequip`, and all autocomplete methods.

- [ ] **Step 1: Update `_equip` method (lines 160-204)**

Replace the entire `_equip` method:

```python
    async def _equip(self, ctx_or_int, user, item_id, prefix):
        if not item_id:
            await self._reply(ctx_or_int, f"❌ {prefix}equip <số>!")
            return
        try:
            iid = int(item_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số không hợp lệ!")
            return

        uid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance, equipped FROM player_equipment WHERE id=? AND player_id=?",
                (iid, uid))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return
            eq = dict(row)
            real_item_id = eq["item_id"]

            # Determine slot and name
            if real_item_id in SHOP_ITEMS and SHOP_ITEMS[real_item_id]["type"] == "equipment":
                item = SHOP_ITEMS[real_item_id]
                slot = item["slot"]
                slot_name = EQUIP_SLOT_MAP.get(slot, slot)
                name = item["name"]
            elif real_item_id in EQUIPMENT:
                item = EQUIPMENT[real_item_id]
                slot = item["slot"]
                slot_name = EQ_SLOT_NAMES.get(slot, slot)
                name = item["name"]
            else:
                await self._reply(ctx_or_int, "❌ Item không phải trang bị!")
                return

            enhance = eq["enhance"]
            enhance_str = f" +{enhance}" if enhance > 0 else ""

            if eq["equipped"]:
                # Unequip
                await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (iid,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Tháo **{name}{enhance_str}** khỏi {slot_name}!")
            else:
                # Unequip any existing item in same slot
                await db.execute(
                    "UPDATE player_equipment SET equipped=0 WHERE player_id=? AND equipped=1 AND item_id IN (SELECT item_id FROM player_equipment WHERE id IN (SELECT id FROM player_equipment WHERE player_id=?))",
                    (uid, uid))
                # Actually we need to check if any equipped item has the same slot
                equipped_cursor = await db.execute(
                    "SELECT id FROM player_equipment WHERE player_id=? AND equipped=1", (uid,))
                async for erow in equipped_cursor:
                    eid = erow[0]
                    eitem_cursor = await db.execute("SELECT item_id FROM player_equipment WHERE id=?", (eid,))
                    eitem_row = await eitem_cursor.fetchone()
                    if eitem_row:
                        ee_item_id = eitem_row[0]
                        ee_slot = None
                        if ee_item_id in SHOP_ITEMS and SHOP_ITEMS[ee_item_id]["type"] == "equipment":
                            ee_slot = SHOP_ITEMS[ee_item_id]["slot"]
                        elif ee_item_id in EQUIPMENT:
                            ee_slot = EQUIPMENT[ee_item_id]["slot"]
                        if ee_slot == slot:
                            await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (eid,))

                await db.execute("UPDATE player_equipment SET equipped=1 WHERE id=?", (iid,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Trang bị **{name}{enhance_str}** vào {slot_name}!")
        finally:
            await db.close()
```

Wait, the unequip-other-item logic is overly complex with extra queries. Let me simplify:

```python
    async def _equip(self, ctx_or_int, user, item_id, prefix):
        if not item_id:
            await self._reply(ctx_or_int, f"❌ {prefix}equip <số>!")
            return
        try:
            iid = int(item_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số không hợp lệ!")
            return

        uid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance, equipped FROM player_equipment WHERE id=? AND player_id=?",
                (iid, uid))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return
            eq = dict(row)
            real_item_id = eq["item_id"]

            if real_item_id in EQUIPMENT:
                item_def = EQUIPMENT[real_item_id]
                slot = item_def["slot"]
                slot_name = EQ_SLOT_NAMES.get(slot, slot)
                name = item_def["name"]
            elif real_item_id in SHOP_ITEMS and SHOP_ITEMS[real_item_id]["type"] == "equipment":
                item_def = SHOP_ITEMS[real_item_id]
                slot = item_def["slot"]
                slot_name = EQUIP_SLOT_MAP.get(slot, slot)
                name = item_def["name"]
            else:
                await self._reply(ctx_or_int, "❌ Item không phải trang bị!")
                return

            enhance = eq["enhance"]
            enhance_str = f" +{enhance}" if enhance > 0 else ""

            if eq["equipped"]:
                await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (iid,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Tháo **{name}{enhance_str}** khỏi {slot_name}!")
            else:
                # Unequip same-slot items
                equipped_cursor = await db.execute(
                    "SELECT pe.id, pe.item_id FROM player_equipment pe WHERE pe.player_id=? AND pe.equipped=1", (uid,))
                async for erow in equipped_cursor:
                    ee_id = erow[0]
                    ee_item_id = erow[1]
                    ee_slot = None
                    if ee_item_id in EQUIPMENT:
                        ee_slot = EQUIPMENT[ee_item_id]["slot"]
                    elif ee_item_id in SHOP_ITEMS and SHOP_ITEMS[ee_item_id]["type"] == "equipment":
                        ee_slot = SHOP_ITEMS[ee_item_id]["slot"]
                    if ee_slot == slot:
                        await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (ee_id,))

                await db.execute("UPDATE player_equipment SET equipped=1 WHERE id=?", (iid,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Trang bị **{name}{enhance_str}** vào {slot_name}!")
        finally:
            await db.close()
```

- [ ] **Step 2: Update `_show_inv` method (lines 206-296)**

Replace the equipment section (lines 220-279) with:

```python
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance, equipped FROM player_equipment WHERE player_id=? ORDER BY id", (uid,))
            eq_rows = []
            async for r in eq_cursor:
                eq_rows.append(dict(r))
            equipped = {}
            for er in eq_rows:
                if er["equipped"]:
                    slot = None
                    if er["item_id"] in EQUIPMENT:
                        slot = EQUIPMENT[er["item_id"]]["slot"]
                    elif er["item_id"] in SHOP_ITEMS and SHOP_ITEMS[er["item_id"]]["type"] == "equipment":
                        slot = SHOP_ITEMS[er["item_id"]]["slot"]
                    if slot:
                        equipped[slot] = er["id"]
            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?", (uid,))
            stone_row = await stone_cursor.fetchone()
```

Then the equipment display section becomes:

```python
            if eq_rows:
                lines = []
                for slot in ALL_SLOTS:
                    eid = equipped.get(slot)
                    slot_name = EQ_SLOT_NAMES.get(slot, slot)
                    if eid:
                        er = next((r for r in eq_rows if r["id"] == eid), None)
                        if er:
                            eiid = er["item_id"]
                            enh = er["enhance"]
                            enh_str = f" +{enh}" if enh > 0 else ""
                            if eiid in SHOP_ITEMS:
                                lines.append(f"✅ **{slot_name}**: {SHOP_ITEMS[eiid]['name']}{enh_str}")
                            elif eiid in EQUIPMENT:
                                e = EQUIPMENT[eiid]
                                stars = STAR_LABELS.get(e["star"], "⭐")
                                lines.append(f"✅ **{slot_name}**: {stars} {e['name']}{enh_str}")
                    else:
                        lines.append(f"⬜ {slot_name}: (trống)")
                lines.append("")
                for er in eq_rows:
                    eiid = er["item_id"]
                    enh = er["enhance"]
                    enh_str = f" +{enh}" if enh > 0 else ""
                    ee = "✅" if er["equipped"] else "📦"
                    if eiid in SHOP_ITEMS:
                        item = SHOP_ITEMS[eiid]
                        lines.append(f"`ID{er['id']}` {ee} {item['name']}{enh_str}")
                    elif eiid in EQUIPMENT:
                        e = EQUIPMENT[eiid]
                        stars = STAR_LABELS.get(e["star"], "⭐")
                        slot = EQ_SLOT_NAMES.get(e["slot"], e["slot"])
                        lines.append(f"`ID{er['id']}` {ee} {stars} {e['name']}{enh_str} ({slot})")
                if stone_row and (stone_row[0] or stone_row[1] or stone_row[2]):
                    lines.append("")
                    lines.append(f"💎 Đá sơ cấp: {stone_row[0]} | 💎 Đá trung cấp: {stone_row[1]} | 💎 Đá cao cấp: {stone_row[2]}")
                if lines:
                    embed.add_field(name="⚒️ Trang Bị", value="\n".join(lines), inline=False)
```

- [ ] **Step 3: Update `_unequip` method (lines 407-427)**

Replace with:

```python
    async def _unequip(self, ctx_or_int, uid: str, slot: str, prefix: str):
        if not slot or slot not in ALL_SLOTS:
            slots = ", ".join(ALL_SLOTS)
            await self._reply(ctx_or_int, f"❌ Slot: {slots}")
            return
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (uid,))
            found = None
            async for r in cursor:
                eiid = r[1]
                eslot = None
                if eiid in EQUIPMENT:
                    eslot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    eslot = SHOP_ITEMS[eiid]["slot"]
                if eslot == slot:
                    found = dict(r)
                    break
            if not found:
                await self._reply(ctx_or_int, f"⬜ {EQ_SLOT_NAMES.get(slot, slot)} đang trống!")
                return
            await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (found["id"],))
            await db.commit()
            eiid = found["item_id"]
            enh = found.get("enhance", 0)
            enh_str = f" +{enh}" if enh > 0 else ""
            name = str(eiid)
            if eiid in EQUIPMENT: name = EQUIPMENT[eiid]["name"]
            elif eiid in SHOP_ITEMS: name = SHOP_ITEMS[eiid]["name"]
            await self._reply(ctx_or_int, f"✅ Tháo **{name}{enh_str}** khỏi {EQ_SLOT_NAMES.get(slot, slot)}!")
        finally:
            await db.close()
```

- [ ] **Step 4: Update autocomplete methods**

Replace `equip_autocomplete` (lines 358-383) with:

```python
    @slash_equip.autocomplete("item_id")
    async def equip_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance, equipped FROM player_equipment WHERE player_id=?", (uid,))
            choices = []
            async for r in cursor:
                er = dict(r)
                eiid = er["item_id"]
                enh = er["enhance"]
                enh_str = f" +{enh}" if enh > 0 else ""
                name = None
                if eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                    name = SHOP_ITEMS[eiid]["name"]
                elif eiid in EQUIPMENT:
                    name = EQUIPMENT[eiid]["name"]
                if name and (current.lower() in str(er["id"]) or current.lower() in name.lower()):
                    status = "✅" if er["equipped"] else "📦"
                    choices.append(app_commands.Choice(
                        name=f"(ID{er['id']}) {status} {name}{enh_str}"[:100],
                        value=str(er["id"])))
            return choices[:25]
        finally:
            await db.close()
```

- [ ] **Step 5: Update `_buy` for equipment (line 87)**

Replace the equipment insert in `_buy` (line 87):

```python
            elif item["type"] == "equipment":
                await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                                 (uid, iid))
```

- [ ] **Step 6: Verify no syntax errors**

Run: `python -c "from bot.cogs.shop import ShopCog; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add bot/cogs/shop.py
git commit -m "feat: update shop cog for per-instance equipment with enhance display"
```

---

### Task 6: Update NPC and battle view for new equipment schema

**Files:**
- Modify: `bot/cogs/npc.py:198-203`
- Modify: `bot/views/battle_view.py:475-480`

- [ ] **Step 1: Update NPC cog equipment loading**

In `bot/cogs/npc.py`, replace the equip loading block (lines 198-203):

```python
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
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
```

- [ ] **Step 2: Update BattleView equipment loading**

In `bot/views/battle_view.py`, replace the equipment loading in `_load_full_player` (lines 475-480):

```python
        eq_cursor = await db.execute(
            "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (pid,))
        equipped = {}
        equip_items = {}
        equip_enhances = {}
        async for erow in eq_cursor:
            eq_id = erow[0]
            eiid = erow[1]
            enh = erow[2]
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
```

- [ ] **Step 3: Also update arena cog's equipment loading**

Check `bot/cogs/arena.py` for similar equipment loading patterns and update to match.

- [ ] **Step 4: Verify syntax**

Run: `python -c "from bot.cogs.npc import NPCCog; from bot.views.battle_view import BattleView; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add bot/cogs/npc.py bot/views/battle_view.py
git commit -m "fix: update NPC and battle view for new equipment schema with enhance data"
```

---

### Task 7: Create enhancement cog

**Files:**
- Create: `bot/cogs/enhance.py`

- [ ] **Step 1: Write the enhancement cog**

```python
import discord
from discord import app_commands
from discord.ext import commands
import random
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, STAR_LABELS
from bot.config import (
    MAX_ENHANCE, ENHANCE_SUCCESS_RATES, ENHANCE_COSTS,
    STONE_BASIC_ID, STONE_MEDIUM_ID, STONE_ADVANCED_ID,
)

STONE_NAMES = {
    1: "Đá Sơ Cấp",
    2: "Đá Trung Cấp",
    3: "Đá Cao Cấp",
}


class EnhanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cuonghoa", aliases=["enhance"])
    async def cuonghoa_cmd(self, ctx, eq_id: str = None):
        await self._cuonghoa(ctx, str(ctx.author.id), eq_id, ctx.author.display_name, "!")

    @app_commands.command(name="cuonghoa", description="🔨 Cường hóa trang bị")
    @app_commands.describe(eq_id="ID trang bị muốn cường hóa (xem /inv)")
    async def slash_cuonghoa(self, interaction: discord.Interaction, eq_id: str):
        await self._cuonghoa(interaction, str(interaction.user.id), eq_id,
                             interaction.user.display_name, "/")

    @slash_cuonghoa.autocomplete("eq_id")
    async def cuonghoa_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND enhance < ?",
                (uid, MAX_ENHANCE))
            choices = []
            async for r in cursor:
                er = dict(r)
                eiid = er["item_id"]
                enh = er["enhance"]
                name = None
                if eiid in EQUIPMENT:
                    name = EQUIPMENT[eiid]["name"]
                if name and (current.lower() in str(er["id"]) or current.lower() in name.lower()):
                    choices.append(app_commands.Choice(
                        name=f"(ID{er['id']}) {name} +{enh} → +{enh+1}"[:100],
                        value=str(er["id"])))
            return choices[:25]
        finally:
            await db.close()

    async def _cuonghoa(self, ctx_or_int, sid: str, eq_id: str, display_name: str, prefix: str):
        if not eq_id:
            await self._reply(ctx_or_int, f"❌ Dùng: `{prefix}cuonghoa <ID>` (xem ID trong `/inv`)")
            return
        try:
            eid = int(eq_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ ID không hợp lệ!")
            return

        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE id=? AND player_id=?",
                (eid, sid))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return
            eq = dict(row)
            eiid = eq["item_id"]
            if eiid not in EQUIPMENT:
                await self._reply(ctx_or_int, "❌ Chỉ có thể cường hóa trang bị hệ thống mới!")
                return
            current = eq["enhance"]
            if current >= MAX_ENHANCE:
                await self._reply(ctx_or_int, f"⭐ Đã đạt tối đa +{MAX_ENHANCE}!")
                return

            target = current + 1
            cost = ENHANCE_COSTS.get(target)
            if not cost:
                await self._reply(ctx_or_int, "❌ Cấp cường hóa không hợp lệ!")
                return

            stone_id, stone_qty, coin_cost = cost
            stone_key = {STONE_BASIC_ID: "stone_basic", STONE_MEDIUM_ID: "stone_medium",
                         STONE_ADVANCED_ID: "stone_advanced"}.get(stone_id)

            player_cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            player_coins = prow[0]

            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (sid,))
            srow = await stone_cursor.fetchone()
            stones = {"stone_basic": srow[0] if srow else 0,
                      "stone_medium": srow[1] if srow else 0,
                      "stone_advanced": srow[2] if srow else 0}

            if stones.get(stone_key, 0) < stone_qty:
                stone_label = {1: "đá sơ cấp", 2: "đá trung cấp", 3: "đá cao cấp"}
                tier = {STONE_BASIC_ID: 1, STONE_MEDIUM_ID: 2, STONE_ADVANCED_ID: 3}[stone_id]
                await self._reply(ctx_or_int,
                    f"❌ Thiếu đá! Cần **{stone_qty}** {stone_label[tier]}, có **{stones.get(stone_key, 0)}**")
                return

            if player_coins < coin_cost:
                await self._reply(ctx_or_int,
                    f"😅 Nghèo! Cần **{coin_cost}🪙**, có **{player_coins}🪙**")
                return

            success_rate = ENHANCE_SUCCESS_RATES.get(target, 0.5)
            roll = random.random()
            success = roll < success_rate

            equip_name = EQUIPMENT[eiid]["name"]
            stars = STAR_LABELS.get(EQUIPMENT[eiid]["star"], "⭐")

            # Deduct stones and coins
            await db.execute(f"UPDATE player_enhance_stones SET {stone_key}={stone_key}-? WHERE player_id=?",
                             (stone_qty, sid))
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (coin_cost, sid))

            if success:
                await db.execute("UPDATE player_equipment SET enhance=? WHERE id=?", (target, eid))
                await db.commit()
                embed = discord.Embed(
                    title="🔨 CƯỜNG HÓA THÀNH CÔNG!",
                    description=(
                        f"{stars} **{equip_name}**\n"
                        f"⭐ **+{current}** → **+{target}** ✨\n"
                        f"🎯 Tỉ lệ: **{int(success_rate*100)}%** — Roll: **{int(roll*100)}** ✅\n"
                        f"💎 Tốn: {stone_qty} đá | 💰 {coin_cost}🪙"
                    ),
                    color=0x00ff00)
            else:
                await db.commit()
                embed = discord.Embed(
                    title="💥 CƯỜNG HÓA THẤT BẠI!",
                    description=(
                        f"{stars} **{equip_name}**\n"
                        f"⭐ Vẫn giữ **+{current}**\n"
                        f"🎯 Tỉ lệ: **{int(success_rate*100)}%** — Roll: **{int(roll*100)}** ❌\n"
                        f"💎 Mất: {stone_qty} đá | 💰 Mất {coin_cost}🪙"
                    ),
                    color=0xff0000)

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)

        finally:
            await db.close()

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(EnhanceCog(bot))
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from bot.cogs.enhance import EnhanceCog; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/enhance.py
git commit -m "feat: add enhancement cog with cuonghoa command"
```

---

### Task 8: Create dungeon cog

**Files:**
- Create: `bot/cogs/dungeon.py`

- [ ] **Step 1: Write the dungeon cog**

```python
import discord
from discord import app_commands
from discord.ext import commands
import random
import copy
import time
from datetime import datetime, timedelta
from bot.database import get_db
from bot.data.equipment import EQUIPMENT, STAR_LABELS, DROP_WEIGHTS, SLOT_NAMES
from bot.data.classes import CLASSES
from bot.data.skills import SKILLS_DB
from bot.engine.battle import execute_action, get_equipped_skill, regen_hp, get_effective_stats
from bot.engine.rewards import calc_level
from bot.config import (
    DUNGEON_MAX_FLOOR, DUNGEON_REQUIRED_LEVEL,
    DUNGEON_FREE_ENTRIES, DUNGEON_MAX_TICKETS,
    DUNGEON_TICKET_COST_1, DUNGEON_TICKET_COST_2,
    STONE_BASIC_ID, STONE_MEDIUM_ID, STONE_ADVANCED_ID,
)


def generate_dungeon_npc(floor: int) -> dict:
    npc_level = floor + 5
    hp = 80 + npc_level * 15
    atk = 8 + npc_level * 3
    defense = 4 + npc_level * 2
    spd = npc_level
    names = [
        "Quái Vật Bóng Tối", "Thú Dữ Vực Sâu", "Linh Hồn Lạc Lối",
        "Xác Sống Vô Hồn", "Quỷ Dữ Bóng Đêm", "Rồng Đen Hắc Ám",
        "Ma Cà Rồng", "Người Sói", "Quái Nhân Đột Biến",
        "Thằn Lằn Khổng Lồ", "Nhện Tinh", "Bọ Cạp Độc",
        "Dơi Quỷ", "Rắn Độc Vực Sâu", "Quỷ Lửa",
        "Băng Quái", "Lôi Điểu", "Thạch Nhân",
        "Hải Quái", "Phượng Hoàng Bóng Tối",
    ]
    name = random.choice(names)
    boss_names = {10: "BOSS TẦNG 10 - QUỶ VƯƠNG", 20: "BOSS TẦNG 20 - LONG VƯƠNG",
                  30: "BOSS TẦNG 30 - MA VƯƠNG", 40: "BOSS TẦNG 40 - THẦN CHẾT",
                  50: "BOSS TẦNG 50 - DIỆT THẾ", 60: "BOSS TẦNG 60 - HỦY DIỆT",
                  70: "BOSS TẦNG 70 - VÔ CỰC", 80: "BOSS TẦNG 80 - HỖN ĐỘN",
                  90: "BOSS TẦNG 90 - TẬN THẾ", 100: "BOSS CUỐI - CHÚA TỂ VỰC SÂU"}
    if floor in boss_names:
        name = boss_names[floor]
        hp = int(hp * 2)
        atk = int(atk * 1.5)
        defense = int(defense * 1.3)

    return {
        "id": f"dungeon_{floor}",
        "name": name,
        "hp": hp,
        "hp_max": hp,
        "attack_min": atk,
        "attack_max": atk + 5,
        "defense": defense,
        "level": npc_level,
        "class_id": random.choice(["satthu", "phapsu", "dauxe", "bancung", "chemgio", "bongtoi", "thienthan", "banxabong"]),
        "cooldowns": {"attack_cd": 0, "special_cd": 0, "defense_cd": 0},
    }


def calc_dungeon_rewards(floor: int) -> dict:
    rewards = {"stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0},
               "coins": 0, "equipment": []}

    if floor <= 20:
        rewards["stones"]["stone_basic"] = random.randint(1, 4)
        rewards["coins"] = random.randint(50, 200)
    elif floor <= 50:
        rewards["stones"]["stone_medium"] = random.randint(1, 5)
        rewards["coins"] = random.randint(150, 500)
    else:
        rewards["stones"]["stone_advanced"] = random.randint(1, 6)
        rewards["coins"] = random.randint(300, 1200)

    # Equipment drop chance per floor
    if random.random() < 0.08:
        if floor <= 20:
            star_pool = [1, 2]
        elif floor <= 50:
            star_pool = [1, 2, 3, 4]
        else:
            star_pool = list(range(1, 7))
        star = random.choice(star_pool)
        items = [e for eid, e in EQUIPMENT.items() if e["star"] == star]
        if items:
            chosen = random.choice(items)
            eid = [k for k, v in EQUIPMENT.items() if v == chosen][0]
            rewards["equipment"].append({"eid": eid, "name": chosen["name"], "star": star})

    return rewards


class DungeonView(discord.ui.View):
    def __init__(self, cog, player_id: str, floor: int, player_pdata: dict,
                 npc_pdata: dict, player_name: str, accumulated_rewards: dict):
        super().__init__(timeout=None)
        self.cog = cog
        self.player_id = player_id
        self.floor = floor
        self.player_pdata = player_pdata
        self.npc_pdata = npc_pdata
        self.player_name = player_name
        self.accumulated_rewards = accumulated_rewards
        self.finished = False

        pdata = player_pdata
        atk = get_equipped_skill(pdata, "attack")
        spc = get_equipped_skill(pdata, "special")
        dfs = get_equipped_skill(pdata, "defense")

        btn_fight = discord.ui.Button(
            emoji="⚔️", label="Chiến đấu",
            style=discord.ButtonStyle.danger, custom_id="dungeon_fight", row=0)
        btn_fight.callback = self._fight_callback
        self.add_item(btn_fight)

        btn_stop = discord.ui.Button(
            emoji="🏃", label="Dừng & Nhận thưởng",
            style=discord.ButtonStyle.success, custom_id="dungeon_stop", row=0)
        btn_stop.callback = self._stop_callback
        self.add_item(btn_stop)

        btn_atk = discord.ui.Button(
            emoji=atk.get("icon", "💥"), label=atk.get("name", "Tấn Công")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_atk", row=1)
        btn_atk.callback = self._make_move_callback("attack")
        self.add_item(btn_atk)

        btn_spc = discord.ui.Button(
            emoji=spc.get("icon", "🔥"), label=spc.get("name", "Đặc Biệt")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_spc", row=1)
        btn_spc.callback = self._make_move_callback("special")
        self.add_item(btn_spc)

        btn_def = discord.ui.Button(
            emoji=dfs.get("icon", "🛡️"), label=dfs.get("name", "Chống Xỏ Lá")[:80],
            style=discord.ButtonStyle.secondary, custom_id="dungeon_def", row=1)
        btn_def.callback = self._make_move_callback("defense")
        self.add_item(btn_def)

    async def _fight_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog._handle_dungeon_fight(interaction, self)

    async def _stop_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.cog._handle_dungeon_stop(interaction, self, won=False)

    def _make_move_callback(self, move_type: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await self.cog._handle_dungeon_move(interaction, self, move_type)
        return callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True


class DungeonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    def _get_monday(self) -> str:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    @commands.command(name="bicanh")
    async def bicanh_cmd(self, ctx):
        await self._bicanh_entry(ctx, str(ctx.author.id), ctx.author.display_name, "!")

    @app_commands.command(name="bicanh", description="🏰 Vào bí cảnh Vực Sâu Xỏ Lá")
    async def slash_bicanh(self, interaction: discord.Interaction):
        await self._bicanh_entry(interaction, str(interaction.user.id),
                                 interaction.user.display_name, "/")

    async def _bicanh_entry(self, ctx_or_int, sid: str, display_name: str, prefix: str):
        if sid in self.sessions:
            await self._reply(ctx_or_int, "🏰 Mày đang trong bí cảnh rồi!")
            return

        db = await get_db()
        try:
            player_cursor = await db.execute("SELECT level, coins, hp FROM players WHERE id=?", (sid,))
            prow = await player_cursor.fetchone()
            if not prow:
                await self._reply(ctx_or_int, f"🤷 Chưa đăng ký! `{prefix}register`")
                return
            pdata = dict(prow)
            if pdata["level"] < DUNGEON_REQUIRED_LEVEL:
                await self._reply(ctx_or_int,
                    f"🔒 Cần level **{DUNGEON_REQUIRED_LEVEL}**! Mày Lv.{pdata['level']}")
                return

            # Check/reset dungeon progress
            dg_cursor = await db.execute("SELECT * FROM dungeon_progress WHERE player_id=?", (sid,))
            dg_row = await dg_cursor.fetchone()
            if dg_row:
                dg = dict(dg_row)
            else:
                await db.execute(
                    "INSERT INTO dungeon_progress (player_id, checkpoint, daily_entries, daily_tickets_bought, last_entry_date, last_week_reset) VALUES (?, 0, 0, 0, '', '')",
                    (sid,))
                dg = {"checkpoint": 0, "daily_entries": 0, "daily_tickets_bought": 0,
                      "last_entry_date": "", "last_week_reset": ""}

            monday = self._get_monday()
            if dg.get("last_week_reset", "") != monday:
                dg["checkpoint"] = 0
                dg["last_week_reset"] = monday

            today = datetime.now().strftime("%Y-%m-%d")
            if dg.get("last_entry_date", "") != today:
                dg["daily_entries"] = 0
                dg["daily_tickets_bought"] = 0
                dg["last_entry_date"] = today

            # Update week reset
            if dg.get("last_week_reset", "") != monday:
                await db.execute("UPDATE dungeon_progress SET checkpoint=0, last_week_reset=? WHERE player_id=?",
                                 (monday, sid))
            # Update daily reset
            if dg.get("last_entry_date", "") != today:
                await db.execute("UPDATE dungeon_progress SET daily_entries=0, daily_tickets_bought=0, last_entry_date=? WHERE player_id=?",
                                 (today, sid))

            free_used = dg["daily_entries"] >= DUNGEON_FREE_ENTRIES
            tickets_bought = dg.get("daily_tickets_bought", 0)
            total_entries_used = dg["daily_entries"] + tickets_bought

            if free_used and tickets_bought >= DUNGEON_MAX_TICKETS:
                await self._reply(ctx_or_int,
                    f"🏰 Hết lượt hôm nay! (Free: đã dùng, Vé: {tickets_bought}/{DUNGEON_MAX_TICKETS})\n⏰ Reset sau 0h!")
                return

            if free_used:
                cost = DUNGEON_TICKET_COST_1 if tickets_bought == 0 else DUNGEON_TICKET_COST_2
                if pdata["coins"] < cost:
                    await self._reply(ctx_or_int,
                        f"😅 Nghèo! Cần {cost}🪙 mua vé, có {pdata['coins']}🪙")
                    return
                await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))
                await db.execute("UPDATE dungeon_progress SET daily_tickets_bought=daily_tickets_bought+1 WHERE player_id=?", (sid,))
                ticket_msg = f"\n🎫 Mua vé: -{cost}🪙"
            else:
                ticket_msg = ""

            await db.execute("UPDATE dungeon_progress SET daily_entries=daily_entries+1 WHERE player_id=?", (sid,))
            await db.commit()

            next_floor = dg["checkpoint"] + 1
            await self._start_dungeon_floor(ctx_or_int, sid, display_name, next_floor, db, ticket_msg)

        finally:
            await db.close()

    async def _start_dungeon_floor(self, ctx_or_int, sid: str, display_name: str,
                                    floor: int, db, extra_msg: str = ""):
        # Load full player data
        cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
        row = await cursor.fetchone()
        pdata = dict(row)
        regen_hp(pdata)

        slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
        slots = {}
        async for r in slots_cursor:
            slots[r[0]] = r[1]
        pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}

        eq_cursor = await db.execute(
            "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
        equipped = {}
        equip_items = {}
        equip_enhances = {}
        async for r in eq_cursor:
            eq_id = r[0]
            eiid = r[1]
            enh = r[2]
            slot = None
            if eiid in EQUIPMENT:
                slot = EQUIPMENT[eiid]["slot"]
            if slot:
                equipped[slot] = eq_id
                equip_items[str(eq_id)] = eiid
                equip_enhances[str(eq_id)] = enh
        pdata["equipped"] = equipped
        pdata["_equip_items"] = equip_items
        pdata["_equip_enhances"] = equip_enhances

        pdata["attack_cd"] = 0
        pdata["special_cd"] = 0
        pdata["defense_cd"] = 0

        eff = get_effective_stats(pdata)

        npc_data = generate_dungeon_npc(floor)
        npc_data["skill_equipped"] = {"attack": 1, "special": 5, "defense": 10, "passive": 14}
        npc_data["equipped"] = {}
        npc_data["_equip_items"] = {}
        npc_data["_equip_enhances"] = {}
        npc_data["level"] = npc_data.get("level", floor + 5)

        # Accumulated rewards
        rewards = {"stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0},
                   "coins": 0, "equipment": []}

        cls_player = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
        desc = (
            f"🏰 **Tầng {floor}/{DUNGEON_MAX_FLOOR}**\n"
            f"━━━━━━━━━━━\n"
            f"{cls_player['icon']} **{display_name}** Lv.{pdata.get('level', 1)}\n"
            f"👾 **{npc_data['name']}** Lv.{npc_data['level']}\n"
            f"❤️ {display_name}: `{pdata['hp']}/{eff['hp_max']}`\n"
            f"❤️ {npc_data['name']}: `{npc_data['hp']}/{npc_data['hp_max']}`\n"
            f"{extra_msg}"
        )
        embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ", description=desc, color=0x8844ff)

        session = {
            "player_pdata": pdata,
            "npc_pdata": npc_data,
            "npc_name": npc_data["name"],
            "player_name": display_name,
            "floor": floor,
            "flags": {"turn_count": 0},
            "accumulated_rewards": rewards,
        }
        self.sessions[sid] = session

        view = DungeonView(self, sid, floor, pdata, npc_data, display_name, rewards)

        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(embed=embed, view=view)
        else:
            await ctx_or_int.response.send_message(embed=embed, view=view)

    async def _handle_dungeon_fight(self, interaction: discord.Interaction, view: DungeonView):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session or view.finished:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return

        npc_move = self._npc_ai_move(session["npc_pdata"])
        npc_cat = "defense" if npc_move == "defense" else npc_move
        await self._execute_dungeon_turn(interaction, session, view, npc_cat)

    def _npc_ai_move(self, npc: dict) -> str:
        hp_pct = npc["hp"] / max(npc["hp_max"], 1) * 100
        if hp_pct < 30:
            return random.choices(["attack", "special", "defense"], weights=[20, 15, 65])[0]
        elif hp_pct < 60:
            return random.choices(["attack", "special", "defense"], weights=[35, 30, 35])[0]
        else:
            return random.choices(["attack", "special", "defense"], weights=[40, 35, 25])[0]

    async def _handle_dungeon_move(self, interaction: discord.Interaction,
                                    view: DungeonView, move_type: str):
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session or view.finished:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return
        await self._execute_dungeon_turn(interaction, session, view, move_type)

    async def _execute_dungeon_turn(self, interaction: discord.Interaction,
                                     session: dict, view: DungeonView,
                                     player_move_type: str):
        player = session["player_pdata"]
        npc = session["npc_pdata"]
        flags = session["flags"]
        result_lines = []

        cat = "defense" if player_move_type == "defense" else player_move_type
        cd_key = f"{cat}_cd"
        if player.get(cd_key, 0) > 0:
            sk = get_equipped_skill(player, cat)
            await interaction.followup.send(
                f"⏳ **{sk['name']}** đang hồi! Còn **{player[cd_key]}** turn.", ephemeral=True)
            return

        skill = get_equipped_skill(player, cat)
        skill_id = next((sid2 for sid2, s in SKILLS_DB.items() if s["name"] == skill["name"]), 1)

        # Player action
        result = await execute_action(player, npc, 0, {"type": player_move_type, "skill_id": skill_id}, flags)
        player = result["p1"]
        npc = result["p2"]
        result_lines.extend(result["log_messages"])

        if result["finished"]:
            await self._finish_dungeon_floor(interaction, session, view, True, result_lines)
            return

        # NPC action
        for ck in ["attack_cd", "special_cd", "defense_cd"]:
            if npc.get(ck, 0) > 0:
                npc[ck] -= 1

        npc_move = self._npc_ai_move(npc)
        npc_cat = "defense" if npc_move == "defense" else npc_move
        npc_cd_key = f"{npc_cat}_cd"
        if npc.get(npc_cd_key, 0) > 0:
            npc_move = "attack"
            npc_cat = "attack"
            if npc.get("attack_cd", 0) > 0:
                npc_move = "defense"
                npc_cat = "defense"

        npc_skill = get_equipped_skill(npc, npc_cat)
        npc_skill_id = next((sid2 for sid2, s in SKILLS_DB.items() if s["name"] == npc_skill["name"]), 1)
        result_lines.append(f"\n👾 {npc['name']} dùng **{npc_skill['icon']} {npc_skill['name']}**")

        flags["turn_count"] = flags.get("turn_count", 0) + 1
        result = await execute_action(npc, player, 0, {"type": npc_move, "skill_id": npc_skill_id}, flags)
        npc = result["p1"]
        player = result["p2"]
        result_lines.extend(result["log_messages"])

        if result["finished"]:
            await self._finish_dungeon_floor(interaction, session, view, False, result_lines)
            return

        session["player_pdata"] = player
        session["npc_pdata"] = npc
        session["flags"] = flags

        eff = get_effective_stats(player)
        hp1_bar = "🟩" * min(player["hp"] // 10, 15) + "⬜" * max(0, 15 - min(player["hp"] // 10, 15))
        hp2_bar = "🟩" * min(npc["hp"] // 10, 15) + "⬜" * max(0, 15 - min(npc["hp"] // 10, 15))

        result_lines.append("\n━━━━━━━━━━━")
        result_lines.append(f"❤️ {session['player_name']}:`{player['hp']}/{eff['hp_max']}`{hp1_bar}")
        result_lines.append(f"❤️ {npc['name']}:`{npc['hp']}/{npc['hp_max']}`{hp2_bar}")

        desc = session.get("_start_desc", f"🏰 **Tầng {session['floor']}/{DUNGEON_MAX_FLOOR}**")
        embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ",
                              description=desc + "\n\n" + "\n".join(result_lines),
                              color=0x8844ff)
        new_view = DungeonView(self, view.player_id, session["floor"],
                               player, npc, session["player_name"],
                               session["accumulated_rewards"])
        await interaction.edit_original_response(embed=embed, view=new_view)

    async def _finish_dungeon_floor(self, interaction: discord.Interaction,
                                     session: dict, view: DungeonView,
                                     player_wins: bool, result_lines: list):
        view.finished = True
        sid = view.player_id

        if player_wins:
            floor = session["floor"]
            rewards = calc_dungeon_rewards(floor)
            acc = session["accumulated_rewards"]
            for k in ["stone_basic", "stone_medium", "stone_advanced"]:
                acc["stones"][k] = acc["stones"].get(k, 0) + rewards["stones"].get(k, 0)
            acc["coins"] += rewards["coins"]
            acc["equipment"].extend(rewards["equipment"])

            result_lines.append(f"\n✅ Thắng tầng {floor}!")
            result_lines.append(f"💰 +{rewards['coins']}🪙")
            for k, label in [("stone_basic", "Đá sơ cấp"), ("stone_medium", "Đá trung cấp"), ("stone_advanced", "Đá cao cấp")]:
                if rewards["stones"].get(k, 0) > 0:
                    result_lines.append(f"💎 +{rewards['stones'][k]} {label}")
            for eq in rewards["equipment"]:
                stars = STAR_LABELS.get(eq["star"], "⭐")
                result_lines.append(f"⚒️ +{stars} **{eq['name']}**")

            # Update checkpoint
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE dungeon_progress SET checkpoint=MAX(checkpoint, ?) WHERE player_id=?",
                    (floor, sid))
                await db.commit()
            finally:
                await db.close()

            next_floor = floor + 1
            if next_floor > DUNGEON_MAX_FLOOR:
                result_lines.append(f"\n🎉 HOÀN THÀNH 100 TẦNG! Nhận hết thưởng!")
                await self._collect_rewards(interaction, session, sid, result_lines)
                self.sessions.pop(sid, None)
                return

            result_lines.append(f"\n🎯 Sẵn sàng tầng **{next_floor}**!")
            result_lines.append(f"💎 Tích lũy: {acc['coins']}🪙 | Sơ:{acc['stones']['stone_basic']} Trung:{acc['stones']['stone_medium']} Cao:{acc['stones']['stone_advanced']}")

            desc = f"🏰 Đã thắng **tầng {floor}**! → Tầng {next_floor}/{DUNGEON_MAX_FLOOR}"
            embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ - THẮNG!",
                                  description=desc + "\n\n" + "\n".join(result_lines),
                                  color=0x00ff00)

            # Continue to next floor
            player = session["player_pdata"]
            npc_data = generate_dungeon_npc(next_floor)
            npc_data["skill_equipped"] = {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            npc_data["equipped"] = {}
            npc_data["_equip_items"] = {}
            npc_data["_equip_enhances"] = {}
            npc_data["level"] = npc_data.get("level", next_floor + 5)

            session["floor"] = next_floor
            session["npc_pdata"] = npc_data
            session["npc_name"] = npc_data["name"]
            session["flags"] = {"turn_count": 0}
            session["_start_desc"] = desc

            new_view = DungeonView(self, sid, next_floor, player, npc_data,
                                   session["player_name"], acc)
            await interaction.edit_original_response(embed=embed, view=new_view)
        else:
            result_lines.append(f"\n💀 Thua! Nhận thưởng đã tích lũy...")
            await self._collect_rewards(interaction, session, sid, result_lines)
            self.sessions.pop(sid, None)

    async def _handle_dungeon_stop(self, interaction: discord.Interaction,
                                    view: DungeonView, won: bool):
        view.finished = True
        sid = view.player_id
        session = self.sessions.get(sid)
        if not session:
            await interaction.followup.send("🤷 Hết rồi!", ephemeral=True)
            return

        result_lines = [f"🏃 Dừng ở tầng **{session['floor']}**! Nhận thưởng..."]
        await self._collect_rewards(interaction, session, sid, result_lines)
        self.sessions.pop(sid, None)

    async def _collect_rewards(self, interaction: discord.Interaction,
                                session: dict, sid: str, result_lines: list):
        acc = session["accumulated_rewards"]
        db = await get_db()
        try:
            # Save player HP
            player = session["player_pdata"]
            now = time.time()
            await db.execute("""UPDATE players SET hp=?, last_battle_time=?, last_hp_update=?
                                 WHERE id=?""",
                             (max(0, player.get("hp", 0)), now, now, sid))

            # Add stones
            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (sid,))
            srow = await stone_cursor.fetchone()
            if srow:
                await db.execute("""UPDATE player_enhance_stones
                    SET stone_basic=stone_basic+?, stone_medium=stone_medium+?, stone_advanced=stone_advanced+?
                    WHERE player_id=?""",
                    (acc["stones"]["stone_basic"], acc["stones"]["stone_medium"],
                     acc["stones"]["stone_advanced"], sid))
            else:
                await db.execute("""INSERT INTO player_enhance_stones (player_id, stone_basic, stone_medium, stone_advanced)
                    VALUES (?, ?, ?, ?)""",
                    (sid, acc["stones"]["stone_basic"], acc["stones"]["stone_medium"],
                     acc["stones"]["stone_advanced"]))

            # Add coins
            if acc["coins"] > 0:
                await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (acc["coins"], sid))

            # Add equipment
            for eq in acc["equipment"]:
                await db.execute(
                    "INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                    (sid, eq["eid"]))

            await db.commit()

            total_lines = []
            if acc["coins"] > 0:
                total_lines.append(f"💰 Tổng coin: +{acc['coins']}🪙")
            for k, label in [("stone_basic", "Đá sơ cấp"), ("stone_medium", "Đá trung cấp"), ("stone_advanced", "Đá cao cấp")]:
                if acc["stones"].get(k, 0) > 0:
                    total_lines.append(f"💎 {label}: +{acc['stones'][k]}")
            if acc["equipment"]:
                total_lines.append(f"⚒️ Trang bị: {len(acc['equipment'])} món")
            result_lines.append("\n".join(total_lines))

        finally:
            await db.close()

        embed = discord.Embed(title="🏰 VỰC SÂU XỎ LÁ - NHẬN THƯỞNG",
                              description="\n".join(result_lines), color=0xffd700)
        await interaction.edit_original_response(embed=embed, view=None)

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(DungeonCog(bot))
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "from bot.cogs.dungeon import DungeonCog; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/dungeon.py
git commit -m "feat: add dungeon cog with 100-floor Vực Sâu Xỏ Lá"
```

---

### Task 9: Register new cogs in main.py

**Files:**
- Modify: `main.py:41-47`

- [ ] **Step 1: Add new cog loading**

Add after line 47 (`await bot.load_extension("bot.cogs.trade")`):

```python
    await bot.load_extension("bot.cogs.enhance")
    await bot.load_extension("bot.cogs.dungeon")
```

- [ ] **Step 2: Verify**

Run: `python -c "print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: register enhance and dungeon cogs"
```

---

### Task 10: Arena cog equipment loading update

**Files:**
- Modify: `bot/cogs/arena.py` (3 locations: lines 282-287, 854-859, 1190-1195)

- [ ] **Step 1: Update equipment loading at lines 282-287**

Replace:
```python
            eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (sid,))
            equipped = {}
            async for r in eq_cursor:
                if r[1]:
                    equipped[r[0]] = r[1]
            pdata["equipped"] = equipped
```

With:
```python
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (sid,))
            equipped = {}
            equip_items = {}
            equip_enhances = {}
            async for r in eq_cursor:
                eq_id = r[0]
                eiid = r[1]
                enh = r[2]
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                if slot:
                    equipped[slot] = eq_id
                    equip_items[str(eq_id)] = eiid
                    equip_enhances[str(eq_id)] = enh
            pdata["equipped"] = equipped
            pdata["_equip_items"] = equip_items
            pdata["_equip_enhances"] = equip_enhances
```

- [ ] **Step 2: Update equipment loading at lines 854-859**

Replace the same pattern (identical block) with the same code as Step 1.

- [ ] **Step 3: Update equipment loading at lines 1190-1195**

Replace:
```python
        eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (pid,))
        equipped = {}
        async for erow in eq_cursor:
            if erow[1]:
                equipped[erow[0]] = erow[1]
        pdata["equipped"] = equipped
```

With:
```python
        eq_cursor = await db.execute(
            "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (pid,))
        equipped = {}
        equip_items = {}
        equip_enhances = {}
        async for erow in eq_cursor:
            eq_id = erow[0]
            eiid = erow[1]
            enh = erow[2]
            slot = None
            if eiid in EQUIPMENT:
                slot = EQUIPMENT[eiid]["slot"]
            if slot:
                equipped[slot] = eq_id
                equip_items[str(eq_id)] = eiid
                equip_enhances[str(eq_id)] = enh
        pdata["equipped"] = equipped
        pdata["_equip_items"] = equip_items
        pdata["_equip_enhances"] = equip_enhances
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from bot.cogs.arena import Arena; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add bot/cogs/arena.py
git commit -m "fix: update arena cog for new equipment schema with enhance data"
```

---

### Task 11: Final integration test

**Files:**
- Run: `python -m pytest tests/ -v`

- [ ] **Step 1: Run existing tests**

Run: `python -m pytest tests/ -v`
Expected: All existing tests pass (note: may need adjustments for new schema)

- [ ] **Step 2: Run full bot import verification**

Run: `python -c "
import asyncio
async def test():
    from bot.database import init_db; await init_db()
    from bot.cogs.shop import ShopCog; print('ShopCog OK')
    from bot.cogs.enhance import EnhanceCog; print('EnhanceCog OK')
    from bot.cogs.dungeon import DungeonCog; print('DungeonCog OK')
    from bot.engine.battle import get_effective_stats; print('Battle OK')
    from bot.engine.rewards import apply_drop, calc_drop; print('Rewards OK')
    print('ALL IMPORTS OK')
asyncio.run(test())
"`
Expected: All imports OK

- [ ] **Step 3: Commit any test fixes**

```bash
git add -A
git commit -m "fix: test adjustments for enhance/dungeon system"
```
