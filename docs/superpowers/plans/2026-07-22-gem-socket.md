# Gem Socket / Đá Khảm — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add gem socket system — equipment gets 1-4 sockets based on star, players socket/merge/remove gems that add stats in battle.

**Architecture:** New `gem_socket.py` cog for commands + UI. Config defines 6 gem types × 9 levels. DB stores player gem inventory and equipment socket assignments. Battle engine `get_effective_stats()` adds gem stats after equipment stats.

**Tech Stack:** Python 3.11+, discord.py, aiosqlite

---

## Files

| File | Action |
|------|--------|
| `bot/config.py` | Modify — add gem & socket config |
| `bot/database.py` | Modify — add gem tables |
| `bot/cogs/gem_socket.py` | Create — main cog (~300 lines) |
| `bot/engine/battle.py` | Modify — integrate gem stats |
| `bot/utils/player_loader.py` | Modify — load socket data |
| `bot/cogs/npc.py` | Modify — gem drops from NPC |
| `bot/cogs/dungeon.py` | Modify — gem drops from dungeon |
| `bot/cogs/world_boss.py` | Modify — gem drops from world boss |
| `main.py` | Modify — load gem_socket cog |

---

### Task 1: Gem Config

**Files:**
- Modify: `bot/config.py`

- [ ] **Step 1: Append gem & socket config**

Add at end of `bot/config.py`:

```python
# ── Gem Socket / Đá Khảm ────────────────────────────────────
GEM_TYPES = {
    "hp":     {"name": "🔴 Hồng Ngọc",  "stat": "hp",     "levels": [80, 150, 250, 400, 600, 900, 1300, 1800, 2500]},
    "atk":    {"name": "⚔️ Lục Bảo",    "stat": "atk",    "levels": [8, 15, 25, 40, 60, 90, 130, 180, 250]},
    "def":    {"name": "🛡️ Lam Ngọc",   "stat": "def",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "spd":    {"name": "💨 Phong Tinh",  "stat": "spd",    "levels": [5, 10, 18, 30, 45, 65, 90, 120, 160]},
    "crit":   {"name": "💥 Huyết Thạch", "stat": "crit",   "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
    "pierce": {"name": "🔱 Tử Tinh",    "stat": "pierce", "levels": [3, 6, 12, 20, 30, 45, 65, 90, 120]},
}
GEM_MAX_LEVEL = 9
GEM_MERGE_COST_PER_LEVEL = 500
GEM_REMOVE_COST_PER_LEVEL = 1000
SOCKETS_BY_STAR = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 4, 8: 4, 9: 4}
```

- [ ] **Step 2: Commit**

```bash
git add bot/config.py
git commit -m "feat: add gem socket config"
```

---

### Task 2: Gem Database Tables

**Files:**
- Modify: `bot/database.py`

- [ ] **Step 1: Add tables to `TABLES`**

```python
    """CREATE TABLE IF NOT EXISTS player_gems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        gem_type TEXT NOT NULL,
        gem_level INTEGER DEFAULT 1,
        quantity INTEGER DEFAULT 0,
        UNIQUE(player_id, gem_type, gem_level)
    )""",
    """CREATE TABLE IF NOT EXISTS equipment_sockets (
        equip_instance_id INTEGER PRIMARY KEY REFERENCES player_equipment(id),
        socket_1 TEXT DEFAULT '',
        socket_2 TEXT DEFAULT '',
        socket_3 TEXT DEFAULT '',
        socket_4 TEXT DEFAULT ''
    )""",
```

- [ ] **Step 2: Add indexes**

```python
        "CREATE INDEX IF NOT EXISTS idx_player_gems_player ON player_gems(player_id)",
```

- [ ] **Step 3: Commit**

```bash
git add bot/database.py
git commit -m "feat: add player_gems and equipment_sockets tables"
```

---

### Task 3: Player Loader — Load Socket Data

**Files:**
- Modify: `bot/utils/player_loader.py`

- [ ] **Step 1: Add socket loading in `load_player_full`**

In `bot/utils/player_loader.py`, after the equipment loading section (around line 57, after `pdata["_equip_hidden"] = equip_hidden`), add:

```python
    # Gem sockets
    eq_ids = list(equip_items.keys())  # str(eq_id) values
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
```

- [ ] **Step 2: Commit**

```bash
git add bot/utils/player_loader.py
git commit -m "feat: load equipment socket data in player loader"
```

---

### Task 4: Battle Engine — Integrate Gem Stats

**Files:**
- Modify: `bot/engine/battle.py`

- [ ] **Step 1: Add gem stats in `get_effective_stats`**

In `bot/engine/battle.py`, in `get_effective_stats()` after the hidden stats loop (around line 113, after `except: pass`), add:

```python
    # Gem socket stats
    from bot.config import GEM_TYPES
    eq = pdata.get("equipped", {})
    socket_data = pdata.get("_equip_sockets", {})
    for slot, eq_id in eq.items():
        sockets = socket_data.get(str(eq_id), {})
        for sk in ["socket_1", "socket_2", "socket_3", "socket_4"]:
            gem_str = sockets.get(sk, "")
            if not gem_str or ":" not in gem_str:
                continue
            parts = gem_str.split(":")
            gem_type = parts[0]
            gem_level = int(parts[1]) if len(parts) > 1 else 1
            if gem_type not in GEM_TYPES:
                continue
            levels = GEM_TYPES[gem_type]["levels"]
            if gem_level < 1 or gem_level > len(levels):
                continue
            val = levels[gem_level - 1]
            if gem_type == "hp":
                hp_max += val
            elif gem_type == "atk":
                atk_min += val
                atk_max += val
            elif gem_type == "def":
                defense += val
            elif gem_type == "spd":
                spd += val
            elif gem_type == "crit":
                crit += val
            elif gem_type == "pierce":
                pierce += val
```

- [ ] **Step 2: Commit**

```bash
git add bot/engine/battle.py
git commit -m "feat: integrate gem socket stats into battle engine"
```

---

### Task 5: Gem Socket Cog

**Files:**
- Create: `bot/cogs/gem_socket.py`

- [ ] **Step 1: Create the cog with all commands**

```python
import discord
from discord import app_commands
from discord.ext import commands
import random
from bot.database import get_db
from bot.config import GEM_TYPES, GEM_MAX_LEVEL, GEM_MERGE_COST_PER_LEVEL, GEM_REMOVE_COST_PER_LEVEL, SOCKETS_BY_STAR
from bot.data.equipment import EQUIPMENT, SHOP_ITEMS
from bot.logger import logger


class GemSocket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="khoda", aliases=["kho"])
    async def kho_da(self, ctx):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0 ORDER BY gem_type, gem_level",
                (sid,))
            rows = await cursor.fetchall()
        finally:
            await db.close()

        if not rows:
            await ctx.reply("📦 Kho đá trống! Đánh NPC, dungeon, world boss để kiếm đá.")
            return

        # Group by type
        by_type: dict[str, list] = {}
        for r in rows:
            gt = r[0]
            if gt not in by_type:
                by_type[gt] = []
            by_type[gt].append((r[1], r[2]))

        lines = []
        for gt, levels in by_type.items():
            info = GEM_TYPES.get(gt, {})
            name = info.get("name", gt)
            lv_strs = [f"C{lv}x{qty}" for lv, qty in sorted(levels)]
            lines.append(f"{name}: {' | '.join(lv_strs)}")

        embed = discord.Embed(
            title="💎 Kho Đá Quý",
            description="\n".join(lines),
            color=0x9b59b6)
        await ctx.reply(embed=embed)

    @commands.command(name="ghepda", aliases=["ghep"])
    async def ghep_da(self, ctx, gem_type: str, level: int):
        sid = str(ctx.author.id)
        if gem_type not in GEM_TYPES:
            types = ", ".join(GEM_TYPES.keys())
            await ctx.reply(f"❌ Loại đá không hợp lệ! Dùng: `{types}`\nVD: `!ghepda hp 1`")
            return
        if level < 1 or level >= GEM_MAX_LEVEL:
            await ctx.reply(f"❌ Chỉ ghép được từ C1 đến C{GEM_MAX_LEVEL - 1}!")
            return

        target_level = level + 1
        cost = target_level * GEM_MERGE_COST_PER_LEVEL
        info = GEM_TYPES[gem_type]

        db = await get_db()
        try:
            # Check 3 gems of source level
            cursor = await db.execute(
                "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                (sid, gem_type, level))
            row = await cursor.fetchone()
            if not row or row[0] < 3:
                await ctx.reply(f"❌ Cần 3 viên {info['name']} C{level}! Bạn chỉ có {row[0] if row else 0} viên.")
                return

            # Check coins
            crow = await (await db.execute("SELECT coins FROM players WHERE id=?", (sid,))).fetchone()
            if not crow or crow[0] < cost:
                await ctx.reply(f"❌ Không đủ {cost}🪙! Bạn có {crow[0] if crow else 0}🪙.")
                return

            # Deduct 3 source gems + coins
            await db.execute("UPDATE player_gems SET quantity=quantity-3 WHERE player_id=? AND gem_type=? AND gem_level=?", (sid, gem_type, level))
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))

            # Add target gem
            await db.execute(
                "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                (sid, gem_type, target_level))
            await db.commit()
        finally:
            await db.close()

        await ctx.reply(f"✅ Ghép 3× {info['name']} C{level} + {cost}🪙 → 1× **{info['name']} C{target_level}**!")

    @ghep_da.error
    async def ghep_da_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Dùng: `!ghepda <loại> <cấp>`\nVD: `!ghepda hp 1`\nLoại: hp, atk, def, spd, crit, pierce")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("❌ Thiếu tham số! Dùng: `!ghepda hp 1`")

    @commands.command(name="khamda", aliases=["kham"])
    async def kham_da(self, ctx, *, args: str = ""):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1",
                (sid,))
            eq_rows = await cursor.fetchall()
        finally:
            await db.close()

        if not eq_rows:
            await ctx.reply("❌ Bạn chưa có trang bị nào đang mang!")
            return

        # Build select menu for equipment
        options = []
        eq_map = {}
        for r in eq_rows:
            eid_db = r[0]
            item_id = r[1]
            enhance = r[2]
            if item_id in EQUIPMENT:
                eq = EQUIPMENT[item_id]
                slot = eq.get("slot", "?")
                star = eq.get("star", 1)
                num_sockets = SOCKETS_BY_STAR.get(star, 1)
                label = f"{eq['name']} ★{star} [+{enhance}] ({num_sockets} ô)"
                options.append(discord.SelectOption(
                    label=label[:100],
                    value=str(eid_db),
                    description=f"Slot: {slot} | {num_sockets} ô khảm"))
                eq_map[str(eid_db)] = eq

        if not options:
            await ctx.reply("❌ Không có trang bị hợp lệ!")
            return

        view = GemSocketSelectView(sid, eq_map, ctx.author.display_name)
        view.add_item(GemSocketSelect(sid, eq_map, options))
        await ctx.reply("🔮 Chọn trang bị để khảm đá:", view=view)


class GemSocketSelect(discord.ui.Select):
    def __init__(self, user_id: str, eq_map: dict, options: list):
        super().__init__(placeholder="Chọn trang bị...", options=options, min_values=1, max_values=1)
        self.user_id = user_id
        self.eq_map = eq_map

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return
        await interaction.response.defer()
        view = self.view
        if view:
            view.selected_eq_id = self.values[0]
            await view.show_socket_ui(interaction)


class GemSocketSelectView(discord.ui.View):
    def __init__(self, user_id: str, eq_map: dict, display_name: str):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.eq_map = eq_map
        self.display_name = display_name
        self.selected_eq_id: str | None = None

    async def show_socket_ui(self, interaction: discord.Interaction):
        eid = self.selected_eq_id
        eq = self.eq_map[eid]
        star = eq.get("star", 1)
        num_sockets = SOCKETS_BY_STAR.get(star, 1)

        db = await get_db()
        try:
            sc = await db.execute("SELECT socket_1, socket_2, socket_3, socket_4 FROM equipment_sockets WHERE equip_instance_id=?", (int(eid),))
            sr = await sc.fetchone()
            sockets = {}
            if sr:
                for i in range(1, 5):
                    val = sr[i - 1] if sr[i - 1] else ""
                    sockets[f"socket_{i}"] = val
            else:
                for i in range(1, 5):
                    sockets[f"socket_{i}"] = ""

            # Load player gems
            gc = await db.execute(
                "SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0 ORDER BY gem_type, gem_level",
                (self.user_id,))
            gem_rows = await gc.fetchall()
        finally:
            await db.close()

        self.clear_items()

        # Build socket embed
        lines = [f"🔮 **Khảm Đá — {eq['name']} ★{star}**\n"]
        for i in range(1, num_sockets + 1):
            key = f"socket_{i}"
            val = sockets[key]
            if val and ":" in val:
                parts = val.split(":")
                gt = parts[0]
                gl = int(parts[1])
                info = GEM_TYPES.get(gt, {})
                gname = info.get("name", gt)
                gval = info.get("levels", [0])[gl - 1] if gl <= len(info.get("levels", [])) else 0
                stat = info.get("stat", "?")
                remove_cost = gl * GEM_REMOVE_COST_PER_LEVEL
                lines.append(f"Ô {i}: {gname} C{gl} (+{gval} {stat.upper()}) — [Tháo {remove_cost}🪙]")
            else:
                lines.append(f"Ô {i}: 🟫 Trống — [Khảm]")

        # Build gem inventory
        gem_lines = []
        for r in gem_rows:
            gt = r[0]
            gl = r[1]
            qty = r[2]
            info = GEM_TYPES.get(gt, {})
            gname = info.get("name", gt)
            gem_lines.append(f"{gname} C{gl} ×{qty}")

        if gem_lines:
            lines.append(f"\n📦 **Kho đá:**\n" + "\n".join(gem_lines[:10]))

        embed = discord.Embed(
            title=f"🔮 Khảm Đá — {eq['name']}",
            description="\n".join(lines),
            color=0x9b59b6)

        # Add socket buttons (1 per active socket)
        for i in range(1, num_sockets + 1):
            key = f"socket_{i}"
            val = sockets[key]
            if val and ":" in val:
                # Has gem → remove button
                btn = GemSocketButton(
                    self.user_id, eid, key, "remove", eq["name"],
                    f"Tháo ô {i}", i, self.display_name)
            else:
                # Empty → socket button
                btn = GemSocketButton(
                    self.user_id, eid, key, "socket", eq["name"],
                    f"Khảm ô {i}", i, self.display_name)
            self.add_item(btn)

        await interaction.edit_original_response(embed=embed, view=self)


class GemSocketButton(discord.ui.Button):
    def __init__(self, user_id: str, eq_id: str, socket_key: str, action: str,
                 eq_name: str, label: str, socket_num: int, display_name: str):
        style = discord.ButtonStyle.danger if action == "remove" else discord.ButtonStyle.success
        super().__init__(style=style, label=label)
        self.user_id = user_id
        self.eq_id = eq_id
        self.socket_key = socket_key
        self.action = action
        self.eq_name = eq_name
        self.socket_num = socket_num
        self.display_name = display_name

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return

        db = await get_db()
        try:
            # Get current socket data
            sc = await db.execute(
                "SELECT socket_1, socket_2, socket_3, socket_4 FROM equipment_sockets WHERE equip_instance_id=?",
                (int(self.eq_id),))
            sr = await sc.fetchone()

            if self.action == "remove":
                if not sr:
                    await interaction.response.send_message("❌ Ô này đang trống!", ephemeral=True)
                    return
                socket_idx = int(self.socket_key.split("_")[1]) - 1
                val = sr[socket_idx] if sr[socket_idx] else ""
                if not val:
                    await interaction.response.send_message("❌ Ô này đang trống!", ephemeral=True)
                    return

                parts = val.split(":")
                gt = parts[0]
                gl = int(parts[1])
                cost = gl * GEM_REMOVE_COST_PER_LEVEL

                # Check coins
                crow = await (await db.execute("SELECT coins FROM players WHERE id=?", (self.user_id,))).fetchone()
                if not crow or crow[0] < cost:
                    await interaction.response.send_message(
                        f"❌ Không đủ {cost}🪙 để tháo! Bạn có {crow[0] if crow else 0}🪙.", ephemeral=True)
                    return

                # Remove gem, return to inventory, deduct coins
                await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, self.user_id))
                await db.execute(
                    f"UPDATE equipment_sockets SET {self.socket_key}='' WHERE equip_instance_id=?",
                    (int(self.eq_id),))
                await db.execute(
                    "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                    (self.user_id, gt, gl))
                await db.commit()

                info = GEM_TYPES.get(gt, {})
                await interaction.response.send_message(
                    f"✅ Đã tháo {info.get('name', gt)} C{gl} khỏi {self.eq_name} (-{cost}🪙)", ephemeral=True)

            else:  # socket
                # Show gem selection
                gc = await db.execute(
                    "SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0 ORDER BY gem_type, gem_level",
                    (self.user_id,))
                rows = await gc.fetchall()
                if not rows:
                    await interaction.response.send_message("❌ Không có đá trong kho!", ephemeral=True)
                    return

                gem_options = []
                gem_map = {}
                for r in rows:
                    gt = r[0]
                    gl = r[1]
                    qty = r[2]
                    info = GEM_TYPES.get(gt, {})
                    gname = info.get("name", gt)
                    val = info.get("levels", [0])[gl - 1]
                    stat = info.get("stat", "?")
                    key = f"{gt}:{gl}"
                    gem_options.append(discord.SelectOption(
                        label=f"{gname} C{gl} (+{val} {stat.upper()}) ×{qty}",
                        value=key,
                        description=f"Khảm vào {self.eq_name}"))
                    gem_map[key] = (gt, gl)

                gem_view = GemSelectView(self.user_id, self.eq_id, self.socket_key, self.eq_name,
                                         self.socket_num, self.display_name, gem_map)
                gem_view.add_item(GemSelect(self.user_id, gem_options))
                await interaction.response.send_message(
                    f"💎 Chọn đá để khảm vào ô {self.socket_num}:", view=gem_view, ephemeral=True)

        finally:
            await db.close()


class GemSelect(discord.ui.Select):
    def __init__(self, user_id: str, options: list):
        super().__init__(placeholder="Chọn đá...", options=options[:25], min_values=1, max_values=1)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return
        view = self.view
        if view:
            view.selected_gem = self.values[0]
            await view.do_socket(interaction)


class GemSelectView(discord.ui.View):
    def __init__(self, user_id: str, eq_id: str, socket_key: str, eq_name: str,
                 socket_num: int, display_name: str, gem_map: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.eq_id = eq_id
        self.socket_key = socket_key
        self.eq_name = eq_name
        self.socket_num = socket_num
        self.display_name = display_name
        self.gem_map = gem_map
        self.selected_gem: str | None = None

    async def do_socket(self, interaction: discord.Interaction):
        gt, gl = self.gem_map[self.selected_gem]
        db = await get_db()
        try:
            # Check gem still available
            cursor = await db.execute(
                "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                (self.user_id, gt, gl))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await interaction.response.edit_message(content="❌ Không đủ đá!", view=None)
                return

            # Ensure socket row exists
            await db.execute(
                "INSERT OR IGNORE INTO equipment_sockets (equip_instance_id) VALUES (?)",
                (int(self.eq_id),))

            gem_str = f"{gt}:{gl}"
            await db.execute(
                f"UPDATE equipment_sockets SET {self.socket_key}=? WHERE equip_instance_id=?",
                (gem_str, int(self.eq_id)))
            await db.execute(
                "UPDATE player_gems SET quantity=quantity-1 WHERE player_id=? AND gem_type=? AND gem_level=?",
                (self.user_id, gt, gl))
            await db.commit()
        finally:
            await db.close()

        info = GEM_TYPES.get(gt, {})
        val = info.get("levels", [0])[gl - 1]
        stat = info.get("stat", "?")
        await interaction.response.edit_message(
            content=f"✅ Đã khảm {info.get('name', gt)} C{gl} (+{val} {stat.upper()}) vào ô {self.socket_num} của {self.eq_name}!",
            view=None)


async def setup(bot):
    await bot.add_cog(GemSocket(bot))
```

- [ ] **Step 2: Commit**

```bash
git add bot/cogs/gem_socket.py
git commit -m "feat: gem socket cog — khamda, ghepda, khoda commands with UI"
```

---

### Task 6: Gem Drops — NPC, Dungeon, World Boss

**Files:**
- Modify: `bot/cogs/npc.py`
- Modify: `bot/cogs/dungeon.py`
- Modify: `bot/cogs/world_boss.py`

- [ ] **Step 1: NPC gem drops**

In `bot/cogs/npc.py`, after the existing drop logic (around line 564 where `apply_drop` is called), add gem drop logic. Add this helper function at module level:

```python
async def _drop_gem_npc(db, player_id: str, npc_level: int) -> str | None:
    from bot.config import GEM_TYPES
    if npc_level < 10:
        return None
    if random.random() > 0.10:
        return None
    if npc_level <= 19:
        gl = 1
    elif npc_level <= 25:
        gl = 2
    else:
        gl = 3
    gt = random.choice(list(GEM_TYPES.keys()))
    await db.execute(
        "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
        "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
        (player_id, gt, gl))
    return f"💎 Rơi: {GEM_TYPES[gt]['name']} C{gl}!"
```

Then around line 555-559 where `calc_drop` is called, add after the drop display:

```python
                gem_text = await _drop_gem_npc(db, sid, npc_level)
                if gem_text:
                    result_lines.append(gem_text)
```

- [ ] **Step 2: Dungeon gem drops**

In `bot/cogs/dungeon.py`, after the floor reward logic (around line 204 where equipment drop is handled), add:

```python
                # Gem drop
                from bot.config import GEM_TYPES
                floor = current_floor  # or wherever the current floor is stored
                gem_level = None
                if 20 <= floor <= 40:
                    gem_level = 1
                elif 41 <= floor <= 60:
                    gem_level = 2
                elif 61 <= floor <= 80:
                    gem_level = 3
                elif 81 <= floor <= 100:
                    gem_level = 4
                if gem_level and random.random() < 0.08:
                    gt = random.choice(list(GEM_TYPES.keys()))
                    await db.execute(
                        "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                        "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                        (player_id, gt, gem_level))
                    result_lines.append(f"💎 Rơi: {GEM_TYPES[gt]['name']} C{gem_level}!")
```

- [ ] **Step 3: World Boss gem drops**

In `bot/cogs/world_boss.py`, in `_apply_boss_rewards`, after adding coins/XP, add for each participant (not just top ranks):

```python
                # Gem drop for all participants
                from bot.config import GEM_TYPES
                gl = random.randint(1, 3)
                gt = random.choice(list(GEM_TYPES.keys()))
                await db.execute(
                    "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                    (pid, gt, gl))
                info = GEM_TYPES[gt]
                if pid in summaries:
                    summaries[pid] += f"\n  • 💎 {info['name']} C{gl}"
                else:
                    summaries[pid] = f"  • 💎 {info['name']} C{gl}"
```

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/npc.py bot/cogs/dungeon.py bot/cogs/world_boss.py
git commit -m "feat: gem drops from NPC, dungeon, and world boss"
```

---

### Task 7: Wire Up

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Load gem_socket cog**

In `main.py`, in `load_extensions()`, add:

```python
    await bot.load_extension("bot.cogs.gem_socket")
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: wire up gem socket cog"
```
