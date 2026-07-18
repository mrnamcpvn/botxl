# Combat Power & Stats Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Lực Chiến (Combat Power) aggregated stat and reorganize `/stats` and `/leaderboard` into 3-tab button views.

**Architecture:** New `bot/engine/combat_power.py` with `calc_combat_power()`; two new view files (`StatsView`, `LeaderboardView`); DB migration for `combat_power` column; refactor arena.py commands.

**Tech Stack:** Python, discord.py, aiosqlite

---

### Task 1: DB migration — add combat_power column

**Files:**
- Modify: `bot/database.py:143-150`

- [ ] **Step 1: Add migration after existing ALTER TABLE**

In `bot/database.py`, add after line 150 (the `last_battle_time` migration):

```python
        try:
            await db.execute("ALTER TABLE players ADD COLUMN combat_power INTEGER DEFAULT 0")
        except:
            pass
```

- [ ] **Step 2: Verify it runs**

Run: `.\venv\Scripts\python.exe -c "import asyncio; from bot.database import init_db; asyncio.run(init_db())"`
Expected: no errors

---

### Task 2: Create calc_combat_power()

**Files:**
- Create: `bot/engine/combat_power.py`

- [ ] **Step 1: Write the file**

```python
import math
from bot.data.equipment import EQUIPMENT
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

    # Equipment star contribution
    eq = pdata.get("equipped", {})
    eq_star_total = 0
    for slot, item_id in eq.items():
        if item_id and item_id in EQUIPMENT:
            eq_star_total += EQUIPMENT[item_id]["star"]
    total += eq_star_total * 80

    # Wife levels contribution
    wife_level_total = 0
    if wives_data:
        for w in wives_data:
            wife_level_total += w.get("level", 0)
    total += wife_level_total * 30

    return int(total)
```

---

### Task 3: Add update_combat_power helper

**Files:**
- Modify: `bot/engine/combat_power.py`

- [ ] **Step 1: Add async helper function**

Append to `bot/engine/combat_power.py`:

```python
from bot.database import get_db


async def update_combat_power(player_id: str, pdata: dict = None, wives_data: list = None):
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
            eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (player_id,))
            equipped = {}
            async for r in eq_cursor:
                if r[1]:
                    equipped[r[0]] = r[1]
            pdata["equipped"] = equipped
        if wives_data is None:
            w_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (player_id,))
            wives_data = [dict(r) async for r in w_cursor]
        cp = calc_combat_power(pdata, wives_data)
        await db.execute("UPDATE players SET combat_power=? WHERE id=?", (cp, player_id))
        await db.commit()
    finally:
        await db.close()
```

---

### Task 4: Create StatsView (3-tab)

**Files:**
- Create: `bot/views/stats_view.py`

- [ ] **Step 1: Write StatsView**

```python
import discord
from bot.database import get_db
from bot.data.skills import SKILLS_DB, RARITY_STARS, CATEGORY_LABELS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.data.classes import CLASSES
from bot.data.wives import WIVES
from bot.engine.battle import get_effective_stats, get_equipped_skill, regen_hp
from bot.engine.combat_power import calc_combat_power
from bot.config import HP_REGEN_RATE, HP_REGEN_INTERVAL


class StatsView(discord.ui.View):
    def __init__(self, target, pdata: dict, wives_data: list):
        super().__init__(timeout=120)
        self.target = target
        self.pdata = pdata
        self.wives_data = wives_data
        self.eff = get_effective_stats(pdata)
        self._build_tab(1)

    def _tab1_embed(self) -> discord.Embed:
        eff = self.eff
        pdata = self.pdata
        cp = calc_combat_power(pdata, self.wives_data)
        embed = discord.Embed(title=f"📊 {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.add_field(name="⚔️ Lực Chiến", value=f"`{cp:,}`".replace(",", "."), inline=False)

        hp = pdata.get("hp", 0)
        hp_max = eff.get("hp_max", 100)
        hp_bar = "🟩" * (hp // 10) + "⬜" * ((hp_max - hp) // 10)
        if len(hp_bar) > 20:
            hp_bar = hp_bar[:20]
        hp_line = f"`{hp}/{hp_max}`\n{hp_bar}"
        if hp < hp_max:
            hp_line += f"\n💤 Hồi **{HP_REGEN_RATE} HP**/{HP_REGEN_INTERVAL}s..."
        embed.add_field(name="❤️ HP", value=hp_line, inline=False)

        atk_line = f"`{eff['attack_min']} - {eff['attack_max']}`"
        if eff.get("damage_pct", 0) > 0:
            atk_line += f"\n💎 Bị động: +{eff['damage_pct']}% dmg"
        embed.add_field(name="⚔️ Lực Xỏ Lá", value=atk_line, inline=True)

        def_line = f"`{eff['defense']}`"
        embed.add_field(name="🛡️ Lì Đòn", value=def_line, inline=True)

        spd = eff.get("spd", 0)
        crit = eff.get("crit", 0)
        if spd or crit:
            extras = []
            if spd: extras.append(f"💨 **{spd}** SPD")
            if crit: extras.append(f"💥 **{crit}%** CRIT")
            embed.add_field(name="⚡ Chỉ Số Phụ", value="\n".join(extras), inline=True)

        xp = pdata.get("xp", 0)
        level = pdata.get("level", 1)
        from bot.engine.rewards import calc_level
        _, xp_in_level = calc_level(xp)
        xp_needed = level * 80
        bar_filled = min(10, xp_in_level * 10 // xp_needed) if xp_needed > 0 else 0
        xp_bar = "🟦" * bar_filled + "⬜" * (10 - bar_filled)
        embed.add_field(name="📊 Cấp Độ", value=f"`Lv.{level}` | 💰 `{pdata.get('coins', 0)} coins`", inline=True)
        embed.add_field(name="🔮 Kinh Nghiệm", value=f"`{xp_in_level}/{xp_needed}`\n{xp_bar}", inline=True)

        embed.add_field(name="🏆 Thành Tích", value=f"Thắng:`{pdata['wins']}` Thua:`{pdata['losses']}`", inline=False)

        cls = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
        embed.add_field(name="🎭 Class", value=f"{cls['icon']} **{cls['name']}** — {cls['desc']}", inline=False)

        sp = pdata.get("stat_points", 0)
        if sp > 0:
            embed.add_field(name="⭐ Điểm Thuộc Tính", value=f"**{sp} điểm**! Dùng `/upgrade <hp/atk/def>`", inline=False)

        buff = pdata.get("buffs", {})
        if buff:
            bl = []
            if buff.get("attack_boost"):
                bl.append(f"⚡ +{buff['attack_boost']}% dmg")
            if buff.get("defense_boost"):
                bl.append(f"🛡️ +{buff['defense_boost']}% DEF")
            if buff.get("lucky"):
                bl.append(f"🎲 ×2 legendary — còn **{buff['lucky']}** trận")
            if bl:
                embed.add_field(name="🔮 Buff Trận Kế", value="\n".join(bl), inline=False)

        return embed

    def _tab2_embed(self) -> discord.Embed:
        pdata = self.pdata
        embed = discord.Embed(title=f"⚒️ Trang Bị — {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        eq = pdata.get("equipped", {})
        lines = []
        for slot in ["weapon", "armor", "boots", "gloves", "belt", "ring"]:
            eid = eq.get(slot)
            if eid and eid in EQUIPMENT:
                e = EQUIPMENT[eid]
                stars = STAR_LABELS.get(e["star"], "⭐")
                stat_texts = []
                atk_min = None
                atk_max = None
                for k, v in e["stats"].items():
                    if k == "attack_min": atk_min = v
                    elif k == "attack_max": atk_max = v
                    elif k == "defense": stat_texts.append(f"🛡️+{v}")
                    elif k == "hp": stat_texts.append(f"❤️+{v}")
                    elif k == "spd": stat_texts.append(f"💨+{v}")
                    elif k == "crit": stat_texts.append(f"💥{v}%")
                    elif k == "pierce": stat_texts.append(f"🔱{v}%")
                    elif k == "dodge": stat_texts.append(f"🍀{v}%")
                    elif k == "reflect": stat_texts.append(f"🔄{v}%")
                    elif k == "regen": stat_texts.append(f"💚{v}%/t")
                if atk_min is not None and atk_max is not None:
                    stat_texts.insert(0, f"⚔️+{atk_min}~{atk_max}")
                lines.append(f"{EQ_SLOT_NAMES.get(slot, slot)}: {stars} **{e['name']}** ({', '.join(stat_texts)})")
            else:
                lines.append(f"{EQ_SLOT_NAMES.get(slot, slot)}: ❌ Trống")
        embed.add_field(name="Đang Mặc", value="\n".join(lines), inline=False)

        embed.add_field(name="—" * 15, value="**Vật Phẩm Trong Kho:**", inline=False)
        inv_lines = [
            "Dùng `/equip <id>` để mặc",
            "Dùng `/unequip <slot>` để cởi",
        ]
        embed.add_field(name="📦", value="\n".join(inv_lines), inline=False)

        return embed

    def _tab3_embed(self) -> discord.Embed:
        pdata = self.pdata
        embed = discord.Embed(title=f"🔥 Kỹ Năng — {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        skill_parts = []
        for cat in ["attack", "special", "defense", "passive"]:
            sk = get_equipped_skill(pdata, cat)
            cat_icons = {"attack": "💥", "special": "🔥", "defense": "🛡️", "passive": "💎"}
            stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
            if cat == "passive":
                skill_parts.append(f"{cat_icons[cat]} {sk['icon']} **{sk['name']}** {stars}\n　└ _{sk.get('desc', '')}_")
            else:
                cd = pdata.get(f"{cat}_cd", 0)
                cd_str = "✅ Sẵn sàng" if cd <= 0 else f"⏳ CD: `{cd}`"
                skill_parts.append(f"{cat_icons[cat]} {sk['icon']} **{sk['name']}** {stars}\n　└ {sk.get('desc', '')} | {cd_str}")
        embed.add_field(name="🔥 Kỹ Năng (4/4)", value="\n\n".join(skill_parts), inline=False)

        return embed

    def _build_tab(self, tab: int):
        self.clear_items()
        labels = [
            ("📊", "Thuộc Tính", discord.ButtonStyle.primary),
            ("⚒️", "Trang Bị", discord.ButtonStyle.success),
            ("🔥", "Kỹ Năng", discord.ButtonStyle.danger),
        ]
        for i, (emoji, label, style) in enumerate(labels):
            disabled = (i + 1 == tab)
            btn = discord.ui.Button(emoji=emoji, label=label, style=style if not disabled else discord.ButtonStyle.gray, disabled=disabled, custom_id=f"stats_tab_{i}")
            btn.callback = self._make_tab_cb(i + 1)
            self.add_item(btn)

        embeds = {1: self._tab1_embed, 2: self._tab2_embed, 3: self._tab3_embed}
        self._current_embed = embeds[tab]()

    def _make_tab_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            if str(interaction.user.id) != str(self.target.id) and str(interaction.user.id) != str(self.pdata.get("id", "")):
                await interaction.response.send_message("🤡 Của người khác!", ephemeral=True)
                return
            self._build_tab(tab)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    @property
    def embed(self):
        return self._current_embed
```

---

### Task 5: Create LeaderboardView (3-tab)

**Files:**
- Create: `bot/views/leaderboard_view.py`

- [ ] **Step 1: Write LeaderboardView**

```python
import discord
from bot.database import get_db
from bot.data.classes import CLASSES


class LeaderboardView(discord.ui.View):
    def __init__(self, initial_players: list, initial_tab: int = 1):
        super().__init__(timeout=120)
        self._tabs = [
            ("⚔️", "Lực Chiến", discord.ButtonStyle.danger, "combat_power", "⚔️ Lực Chiến", "LC"),
            ("📊", "Level", discord.ButtonStyle.primary, "level", "📊 Level", "Level"),
            ("💰", "Coin", discord.ButtonStyle.success, "coins", "💰 Coin", "Coin"),
        ]
        self._current_tab = initial_tab
        self._build_tab(initial_tab, initial_players)

    def _make_embed(self, players: list, title_label: str, sort_col: str, val_label: str) -> discord.Embed:
        embed = discord.Embed(title=f"🏆 BẢNG XẾP HẠNG — {title_label}", color=0xffd700)
        medals = ["🥇", "🥈", "🥉"]
        for i, pd in enumerate(players):
            n = pd.get("name", "Unknown")
            m = medals[i] if i < 3 else f"#{i + 1}"
            val = pd.get(sort_col, 0)
            if sort_col == "coins":
                val_str = f"{val:,}🪙".replace(",", ".")
            elif sort_col == "combat_power":
                val_str = f"⚔️{val:,}".replace(",", ".")
            else:
                val_str = f"Lv.{val}"
            wr = pd["wins"] / (pd["wins"] + pd["losses"]) * 100 if (pd["wins"] + pd["losses"]) > 0 else 0
            cls = CLASSES.get(pd.get("class_id", "banxabong"), CLASSES["banxabong"])
            embed.add_field(name=f"{m} {cls['icon']} {n}",
                            value=f"{val_label}:`{val_str}` 🏆`{pd['wins']}W/{pd['losses']}L` WR{wr:.0f}%",
                            inline=False)
        return embed

    def _build_tab(self, tab: int, players: list):
        self.clear_items()
        for i, (emoji, label, style, _, _, _) in enumerate(self._tabs):
            disabled = (i + 1 == tab)
            btn = discord.ui.Button(emoji=emoji, label=label, style=style if not disabled else discord.ButtonStyle.gray, disabled=disabled, custom_id=f"lb_tab_{i}")
            btn.callback = self._make_tab_cb(i + 1)
            self.add_item(btn)
        _, _, _, sort_col, title_label, val_label = self._tabs[tab - 1]
        self._current_embed = self._make_embed(players, title_label, sort_col, val_label)

    async def _fetch_players(self, sort_col: str) -> list:
        db = await get_db()
        try:
            cursor = await db.execute(f"SELECT * FROM players ORDER BY {sort_col} DESC LIMIT 10")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    def _make_tab_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            self._current_tab = tab
            _, _, _, sort_col, title_label, val_label = self._tabs[tab - 1]
            players = await self._fetch_players(sort_col)
            self._build_tab(tab, players)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    @property
    def embed(self):
        return self._current_embed
```

---

### Task 6: Refactor stats commands in arena.py

**Files:**
- Modify: `bot/cogs/arena.py:20-124` (stats_embed), `:368-401` (prefix stats), `:936-970` (slash stats)

- [ ] **Step 1: Remove old stats_embed function, keep import of new view**

Remove lines 20-124 (`def stats_embed`). Add import for `StatsView` at top of arena.py:

```python
from bot.views.stats_view import StatsView
from bot.engine.combat_power import update_combat_power
```

- [ ] **Step 2: Update prefix stats command (lines 368-401)**

Replace the stats command body to load wives data and use StatsView:

```python
    @commands.command(name="stats")
    async def stats(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        sid = str(target.id)
        db = await get_db()
        try:
            await self._sync_role_mult(db, target)
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await ctx.reply("🤷 Chưa đăng ký! `!register`")
                return
            pdata = dict(row)
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (sid,))
            equipped = {}
            async for r in eq_cursor:
                if r[1]:
                    equipped[r[0]] = r[1]
            pdata["equipped"] = equipped
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}
            wife_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
            wives_data = [dict(r) async for r in wife_cursor]
            regen_hp(pdata)
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?", (pdata["hp"], pdata.get("last_hp_update", time.time()), sid))
            await update_combat_power(sid, pdata, wives_data)
            await db.commit()

            view = StatsView(target, pdata, wives_data)
            await ctx.send(embed=view.embed, view=view)
        finally:
            await db.close()
```

- [ ] **Step 3: Update slash stats command (lines 936-970)**

Replace similarly to load wives and use StatsView:

```python
    @app_commands.command(name="stats", description="Xem chỉ số")
    @app_commands.describe(member="Ai? (bỏ trống = mình)")
    async def slash_stats(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        sid = str(target.id)
        db = await get_db()
        try:
            await self._sync_role_mult(db, target)
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message("🤷 Chưa đăng ký!", ephemeral=True)
                return
            pdata = dict(row)
            slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (sid,))
            slots = {}
            async for r in slots_cursor:
                slots[r[0]] = r[1]
            pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
            eq_cursor = await db.execute("SELECT slot, item_id FROM player_equip_slots WHERE player_id=?", (sid,))
            equipped = {}
            async for r in eq_cursor:
                if r[1]:
                    equipped[r[0]] = r[1]
            pdata["equipped"] = equipped
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (sid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}
            wife_cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
            wives_data = [dict(r) async for r in wife_cursor]
            regen_hp(pdata)
            await db.execute("UPDATE players SET hp=?, last_hp_update=? WHERE id=?", (pdata["hp"], pdata.get("last_hp_update", time.time()), sid))
            await update_combat_power(sid, pdata, wives_data)
            await db.commit()
            view = StatsView(target, pdata, wives_data)
            await interaction.response.send_message(embed=view.embed, view=view)
        finally:
            await db.close()
```

- [ ] **Step 4: Run bot to verify stats loads**

Run: `.\venv\Scripts\python.exe main.py`
Expected: bot starts, `/stats` shows 3-tab view with Lực Chiến

---

### Task 7: Refactor leaderboard commands

**Files:**
- Modify: `bot/cogs/arena.py:773-795` (prefix lb), `:972-994` (slash lb)

- [ ] **Step 1: Add import**

```python
from bot.views.leaderboard_view import LeaderboardView
```

- [ ] **Step 2: Replace prefix leaderboard (lines 773-795)**

```python
    @commands.command(name="leaderboard", aliases=["bxh"])
    async def leaderboard(self, ctx):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players ORDER BY combat_power DESC LIMIT 10")
            players = [dict(r) async for r in cursor]
            view = LeaderboardView(players, initial_tab=1)
            await ctx.send(embed=view.embed, view=view)
        finally:
            await db.close()
```

- [ ] **Step 3: Replace slash leaderboard (lines 972-994)**

```python
    @app_commands.command(name="leaderboard", description="BXH")
    async def slash_leaderboard(self, interaction: discord.Interaction):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players ORDER BY combat_power DESC LIMIT 10")
            players = [dict(r) async for r in cursor]
            view = LeaderboardView(players, initial_tab=1)
            await interaction.response.send_message(embed=view.embed, view=view)
        finally:
            await db.close()
```

- [ ] **Step 4: Run bot to verify leaderboard loads**

Run: `.\venv\Scripts\python.exe main.py`
Expected: `/leaderboard` shows 3-tab with Lực Chiến/Level/Coin

---

### Task 8: Update combat_power after key actions

**Files:**
- Modify: `bot/cogs/arena.py` (after upgrade, after class change)
- Modify: `bot/cogs/shop.py` (after equip/unequip)
- Modify: `bot/views/battle_view.py` (after PvP battle)
- Modify: `bot/cogs/npc.py` (after NPC battle)

- [ ] **Step 1: After upgrade (arena.py around line 1025)**

Add after `await db.commit()` in both prefix and slash upgrade:

```python
            await update_combat_power(sid)
```

- [ ] **Step 2: After class change (arena.py around line 850)**

Add after `await db.commit()`:

```python
            await update_combat_power(sid)
```

- [ ] **Step 3: After equip/unequip in shop.py**

In `bot/cogs/shop.py`, find the equip handler around line 31 and the unequip handler around line 391. After each `await db.commit()`, add:

```python
from bot.engine.combat_power import update_combat_power

# ... after db.commit() in equip_cmd:
            await update_combat_power(str(ctx.author.id))

# ... after db.commit() in unequip_cmd (if it uses db.commit):
            await update_combat_power(str(ctx.author.id))
```

- [ ] **Step 4: After PvP battle in battle_view.py — 3 locations**

**Location A** — `bot/views/battle_view.py:223` (simple defeat in `_handle_move`):
```python
            await db.commit()
            await update_combat_power(winner_id)
            await update_combat_power(sid)
```

**Location B** — `bot/views/battle_view.py:360` (execute_action defeat):
```python
                await db.commit()
                await update_combat_power(p1_id)
                await update_combat_power(p2_id)
```

**Location C** — `bot/views/battle_view.py:582` (timeout handler `_handle_timeout`):
```python
        await db.commit()
        await update_combat_power(winner_id)
        await update_combat_power(loser_sid)
```

Add import at top of `bot/views/battle_view.py`:
```python
from bot.engine.combat_power import update_combat_power
```

- [ ] **Step 5: After NPC battle in npc.py**

Find the NPC battle end location in `bot/cogs/npc.py` (the commit after rewards) and add:

```python
            await db.commit()
            await update_combat_power(sid)
```

Add import at top of `bot/cogs/npc.py`:
```python
from bot.engine.combat_power import update_combat_power
```

- [ ] **Step 6: After equip/unequip skill (arena.py equipskill)**

In `bot/cogs/arena.py`, find the equipskill command (around line 760-770) and after `await db.commit()` add:

```python
            await update_combat_power(uid)
```

- [ ] **Step 7: Run bot and test all paths**

Run: `.\venv\Scripts\python.exe main.py`
Expected: combat_power updates after upgrade, class change, equip, battle, equipskill
