# Thần Khí System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Thần Khí (Divine Artifact) system with 10-star progression, 15% stat boost per star, GIF display, and upgrade mechanics.

**Architecture:** New `player_artifact` table stores star + stone count. Artifact boost multiplier applied in `get_effective_stats()` after equipment. New cog handles `!thankhi` command with interactive prev/next/upgrade buttons. StatsView gets a 4th tab.

**Tech Stack:** Python 3.12, discord.py, aiosqlite, existing battle engine

---

### Task 1: Add config constants + artifact definitions

**Files:**
- Modify: `bot/config.py`
- Create: `bot/data/artifacts.py`

- [ ] **Step 1: Add constants to config.py**

Append to end of `bot/config.py`:

```python
# Artifact (Thần Khí)
ARTIFACT_BOOST_PER_STAR = 0.15
ARTIFACT_UNLOCK_COST = 100000
ARTIFACT_MAX_STAR = 10
ARTIFACT_STONE_DROP_CHANCE = 0.05
ARTIFACT_STONE_DROP_NPC_MIN_LEVEL = 15
ARTIFACT_STONE_DUNGEON_MIN_FLOOR = 50
ARTIFACT_STONE_DUNGEON_CHANCE = 0.03
ARTIFACT_UPGRADE_COSTS = {
    1: (0, 100000),
    2: (1, 10000),
    3: (2, 20000),
    4: (3, 30000),
    5: (4, 40000),
    6: (6, 50000),
    7: (8, 60000),
    8: (10, 75000),
    9: (12, 90000),
    10: (15, 100000),
}
```

- [ ] **Step 2: Create `bot/data/artifacts.py`**

```python
ARTIFACTS = {
    0: {
        "name": "Chưa Kích Hoạt",
        "color": 0x888888,
        "desc": "Dùng `!thankhi` và 100,000🪙 để kích hoạt Thần Khí!",
        "gif_url": "",
    },
    1: {
        "name": "⚔️ Thanh Phong Kiếm",
        "color": 0x88ccff,
        "desc": "Kiếm gió thanh khiết, nhẹ như lông hồng, nhanh như chớp giật.",
        "gif_url": "https://i.pinimg.com/originals/7a/1d/3e/7a1d3e0c8f9b4a5d6e7f8a9b0c1d2e3f.gif",
    },
    2: {
        "name": "🗡️ Huyền Thiết Trọng Kiếm",
        "color": 0x44ff44,
        "desc": "Trọng kiếm đen huyền, trăm cân tung hoành, vạn người khó địch.",
        "gif_url": "https://i.pinimg.com/originals/8b/2e/4f/8b2e4f5c6d7e8f9a0b1c2d3e4f5a6b7c.gif",
    },
    3: {
        "name": "⚡ Tử Điện Thần Kiếm",
        "color": 0xffcc00,
        "desc": "Kiếm mang sấm sét tím, chém tan bầu trời, xé toạc hư không.",
        "gif_url": "https://i.pinimg.com/originals/9c/3f/5a/9c3f5a6b7c8d9e0f1a2b3c4d5e6f7a8b.gif",
    },
    4: {
        "name": "🌑 Hắc Ám Ma Kiếm",
        "color": 0xaa44ff,
        "desc": "Ma kiếm bóng tối, hấp thụ linh hồn, sức mạnh vô biên.",
        "gif_url": "https://i.pinimg.com/originals/0d/1e/2f/0d1e2f3c4b5a6d7e8f9a0b1c2d3e4f5a.gif",
    },
    5: {
        "name": "🔥 Xích Viêm Hỏa Kiếm",
        "color": 0xff4444,
        "desc": "Kiếm lửa đỏ rực, thiêu đốt vạn vật, tro tàn hư ảo.",
        "gif_url": "https://i.pinimg.com/originals/1e/2f/3a/1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b.gif",
    },
    6: {
        "name": "❄️ Băng Phách Hàn Kiếm",
        "color": 0x44ccff,
        "desc": "Hàn kiếm ngàn năm băng giá, đóng băng thời gian, ngưng đọng sinh mệnh.",
        "gif_url": "https://i.pinimg.com/originals/2f/3a/4b/2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c.gif",
    },
    7: {
        "name": "⚡ Lôi Thần Chiến Kích",
        "color": 0xff8800,
        "desc": "Kích thần sấm sét, vung lên trời long đất lở, hạ xuống quỷ khốc thần sầu.",
        "gif_url": "https://i.pinimg.com/originals/3a/4b/5c/3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d.gif",
    },
    8: {
        "name": "🌀 Hỗn Độn Thần Thương",
        "color": 0xcc44ff,
        "desc": "Thương hỗn độn khai thiên lập địa, một kích phá vạn pháp.",
        "gif_url": "https://i.pinimg.com/originals/4b/5c/6d/4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e.gif",
    },
    9: {
        "name": "🐉 Thái Cực Bàn Long Đao",
        "color": 0xff44aa,
        "desc": "Long đao thái cực, uy lực hủy thiên diệt địa, long hồn phụ thể.",
        "gif_url": "https://i.pinimg.com/originals/5c/6d/7e/5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f.gif",
    },
    10: {
        "name": "💀 Hủy Diệt Thần Kiếm",
        "color": 0xff0044,
        "desc": "THẦN KIẾM TỐI THƯỢNG — kết tinh sức mạnh vũ trụ, một nhát chém diệt cả thiên hà.",
        "gif_url": "https://i.pinimg.com/originals/6d/7e/8f/6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a.gif",
    },
}
```

- [ ] **Step 3: Verify imports**

Run: `.\venv\Scripts\python.exe -c "from bot.data.artifacts import ARTIFACTS; print(len(ARTIFACTS))"`
Expected: `11`

- [ ] **Step 4: Commit**

```bash
git add bot/config.py bot/data/artifacts.py
git commit -m "feat: add artifact config constants and 10-star definitions"
```

---

### Task 2: Add player_artifact table

**Files:**
- Modify: `bot/database.py`

- [ ] **Step 1: Add table to TABLES list**

Add this to the `TABLES` list in `bot/database.py`:

```python
    """CREATE TABLE IF NOT EXISTS player_artifact (
        player_id TEXT PRIMARY KEY,
        star INTEGER DEFAULT 0,
        stone_count INTEGER DEFAULT 0
    )""",
```

- [ ] **Step 2: Verify**

Run: `.\venv\Scripts\python.exe -c "import asyncio; from bot.database import init_db; asyncio.run(init_db()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot/database.py
git commit -m "feat: add player_artifact table"
```

---

### Task 3: Apply artifact boost in battle engine

**Files:**
- Modify: `bot/engine/battle.py`

- [ ] **Step 1: Add artifact multiplier in `get_effective_stats()`**

After the role_mult calculation (currently at line ~73), add:

```python
    artifact_star = pdata.get("_artifact_star", 0)
    if artifact_star > 0:
        mult2 = 1 + artifact_star * 0.15
        hp_max = int(hp_max * mult2)
        atk_min = int(atk_min * mult2)
        atk_max = int(atk_max * mult2)
        defense = int(defense * mult2)
        spd = int(spd * mult2)
        crit = int(crit * mult2)
        pierce = int(pierce * mult2)
        dodge = int(dodge * mult2)
        reflect = int(reflect * mult2)
        regen = int(regen * mult2)
```

Add this BEFORE the `return` statement at the end of `get_effective_stats()`.

- [ ] **Step 2: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.engine.battle import get_effective_stats; print('OK')"`
Run: `.\venv\Scripts\python.exe -m pytest tests/ -v`

Expected: All 12 pass

- [ ] **Step 3: Commit**

```bash
git add bot/engine/battle.py
git commit -m "feat: apply artifact star boost multiplier in get_effective_stats"
```

---

### Task 4: Add artifact tab to StatsView

**Files:**
- Modify: `bot/views/stats_view.py`

- [ ] **Step 1: Import ARTIFACTS**

Add to imports at top of file:

```python
from bot.data.artifacts import ARTIFACTS
```

- [ ] **Step 2: Add `_tab4_embed` method**

Add to `StatsView` class:

```python
    def _tab4_embed(self) -> discord.Embed:
        pdata = self.pdata
        star = pdata.get("_artifact_star", 0)
        a = ARTIFACTS.get(star, ARTIFACTS[0])
        embed = discord.Embed(title=f"🔱 Thần Khí — {self.target.display_name}", color=a["color"])
        embed.set_thumbnail(url=self.target.display_avatar.url)
        if star == 0:
            embed.description = "🔒 Chưa kích hoạt\nDùng `!thankhi` để mở khóa với 100,000🪙"
        else:
            boost = int(star * 15)
            embed.description = (
                f"**{a['name']}** ⭐×{star}\n"
                f"*{a['desc']}*\n\n"
                f"⚡ Tăng **{boost}%** toàn bộ chỉ số\n"
                f"💎 Đá thần khí: `{pdata.get('_artifact_stones', 0)}` viên"
            )
            if a.get("gif_url"):
                embed.set_image(url=a["gif_url"])
        return embed
```

- [ ] **Step 3: Update `_build_tab` to add 4th tab**

In `_build_tab`, change the labels list to add a 4th entry:

```python
        labels = [
            ("📊", "Thuộc Tính", discord.ButtonStyle.primary),
            ("⚒️", "Trang Bị", discord.ButtonStyle.success),
            ("🔥", "Kỹ Năng", discord.ButtonStyle.danger),
            ("🔱", "Thần Khí", discord.ButtonStyle.primary),
        ]
```

And change the embeds dict:
```python
        embeds = {1: self._tab1_embed, 2: self._tab2_embed, 3: self._tab3_embed, 4: self._tab4_embed}
```

- [ ] **Step 4: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.views.stats_view import StatsView; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add bot/views/stats_view.py
git commit -m "feat: add artifact tab to stats view"
```

---

### Task 5: Load artifact data in arena/stats

**Files:**
- Modify: `bot/cogs/arena.py` (in the `stats` and `_load_full_player` methods)

- [ ] **Step 1: Load artifact data in stats method**

In arena.py `stats` method (around line 305), before `regen_hp(pdata)`, add:

```python
            art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
            art_row = await art_cursor.fetchone()
            pdata["_artifact_star"] = art_row[0] if art_row else 0
            pdata["_artifact_stones"] = art_row[1] if art_row else 0
```

- [ ] **Step 2: Same in `_load_full_player`**

In `_load_full_player` method (around line 1205), after loading buffs, add the same artifact loading code.

- [ ] **Step 3: Same in `slash_stats` variant (line ~860)**

Add the same artifact loading in the slash_stats handler.

- [ ] **Step 4: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.arena import Arena; print('OK')"`

- [ ] **Step 5: Commit**

```bash
git add bot/cogs/arena.py
git commit -m "feat: load artifact data for stats and battle"
```

---

### Task 6: Create thankhi cog

**Files:**
- Create: `bot/cogs/thankhi.py`

- [ ] **Step 1: Create the cog with dual prefix+slash commands**

```python
import discord
from discord import app_commands
from discord.ext import commands
import random
from bot.database import get_db
from bot.data.artifacts import ARTIFACTS
from bot.config import ARTIFACT_UNLOCK_COST, ARTIFACT_MAX_STAR, ARTIFACT_UPGRADE_COSTS


class ThankhiView(discord.ui.View):
    def __init__(self, star: int, can_upgrade: bool):
        super().__init__(timeout=120)
        self.star = star
        self.can_upgrade = can_upgrade

        prev_btn = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary, custom_id="thk_prev", row=0, disabled=(star <= 0))
        prev_btn.callback = self._make_nav(-1)
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary, custom_id="thk_next", row=0, disabled=(star >= 10))
        next_btn.callback = self._make_nav(1)
        self.add_item(next_btn)

        if star == 0:
            unlock_btn = discord.ui.Button(emoji="🔓", label="Kích Hoạt (100,000🪙)", style=discord.ButtonStyle.success, custom_id="thk_unlock", row=1)
            unlock_btn.callback = self._unlock_callback
            self.add_item(unlock_btn)
        elif can_upgrade and star < ARTIFACT_MAX_STAR:
            upgrade_btn = discord.ui.Button(emoji="⬆", label=f"Nâng Cấp → ★{star+1}", style=discord.ButtonStyle.danger, custom_id="thk_upgrade", row=1)
            upgrade_btn.callback = self._upgrade_callback
            self.add_item(upgrade_btn)

    def _make_nav(self, delta: int):
        async def cb(interaction: discord.Interaction):
            new_star = self.star + delta
            if 0 <= new_star <= 10:
                embed = thankhi_embed(new_star, interaction.user.display_name)
                view = ThankhiView(new_star, False)
                await interaction.response.edit_message(embed=embed, view=view)
        return cb

    async def _unlock_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row or row[0] < ARTIFACT_UNLOCK_COST:
                await interaction.followup.send(f"😅 Cần {ARTIFACT_UNLOCK_COST}🪙!", ephemeral=True)
                return
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (ARTIFACT_UNLOCK_COST, sid))
            await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, 1, 0)", (sid,))
            await db.commit()
            embed = thankhi_embed(1, interaction.user.display_name)
            view = ThankhiView(1, False)
            await interaction.edit_original_response(embed=embed, view=view)
        finally:
            await db.close()

    async def _upgrade_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                return
            current = row[0]
            stones = row[1]
            cost = ARTIFACT_UPGRADE_COSTS.get(current + 1)
            if not cost:
                return
            stone_need, coin_need = cost
            if stones < stone_need:
                await interaction.followup.send(f"😅 Cần {stone_need} đá thần khí, có {stones}!", ephemeral=True)
                return
            pc = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            pr = await pc.fetchone()
            if not pr or pr[0] < coin_need:
                await interaction.followup.send(f"😅 Cần {coin_need}🪙!", ephemeral=True)
                return
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (coin_need, sid))
            await db.execute("UPDATE player_artifact SET star=star+1, stone_count=stone_count-? WHERE player_id=?", (stone_need, sid))
            await db.commit()
            new_star = current + 1
            embed = thankhi_embed(new_star, interaction.user.display_name)
            can_upgrade = new_star < ARTIFACT_MAX_STAR
            view = ThankhiView(new_star, can_upgrade)
            await interaction.edit_original_response(embed=embed, view=view)
        finally:
            await db.close()


def thankhi_embed(star: int, display_name: str) -> discord.Embed:
    a = ARTIFACTS.get(star, ARTIFACTS[0])
    embed = discord.Embed(title=f"🔱 Thần Khí — {display_name}", color=a["color"])
    if star == 0:
        embed.description = "🔒 Chưa kích hoạt\nDùng nút bên dưới để mở khóa với 100,000🪙"
    else:
        boost = int(star * 15)
        embed.description = (
            f"# {a['name']}\n"
            f"⭐ ×{star}  |  ⚡ +{boost}% toàn bộ chỉ số\n"
            f"*{a['desc']}*"
        )
    if a.get("gif_url"):
        embed.set_image(url=a["gif_url"])
    return embed


class ThankhiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="thankhi")
    async def thankhi_cmd(self, ctx):
        await self._thankhi(ctx, str(ctx.author.id), ctx.author.display_name)

    @app_commands.command(name="thankhi", description="🔱 Xem Thần Khí")
    async def slash_thankhi(self, interaction: discord.Interaction):
        await self._thankhi(interaction, str(interaction.user.id), interaction.user.display_name)

    async def _thankhi(self, ctx_or_int, sid: str, display_name: str):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
            row = await cursor.fetchone()
            star = row[0] if row else 0
            stones = row[1] if row else 0
            can_upgrade = False
            if star > 0 and star < ARTIFACT_MAX_STAR:
                cost = ARTIFACT_UPGRADE_COSTS.get(star + 1)
                if cost and stones >= cost[0]:
                    pc = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
                    pr = await pc.fetchone()
                    if pr and pr[0] >= cost[1]:
                        can_upgrade = True
            embed = thankhi_embed(star, display_name)
            if stones > 0:
                embed.set_footer(text=f"💎 Đá thần khí: {stones} viên")
            view = ThankhiView(star, can_upgrade)
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(ThankhiCog(bot))
```

- [ ] **Step 2: Register in main.py**

Add to `load_extensions()`:
```python
await bot.load_extension("bot.cogs.thankhi")
```

- [ ] **Step 3: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.thankhi import ThankhiCog; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/thankhi.py main.py
git commit -m "feat: add thankhi cog with interactive artifact viewer and upgrade"
```

---

### Task 7: Add artifact stone drops to NPC battles

**Files:**
- Modify: `bot/cogs/npc.py`

- [ ] **Step 1: Add stone drop in `_finish_npc_battle`**

In `_finish_npc_battle`, inside the `if player_wins:` block, after the existing drop logic, add:

```python
                if npc.get("level", 0) >= 15 and random.random() < 0.05:
                    await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + 1)",
                                     (sid, sid, sid))
                    result_lines.append("💎 +1 Đá Thần Khí!")
```

- [ ] **Step 2: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.npc import NPCCog; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/npc.py
git commit -m "feat: add artifact stone drop from NPCs level 15+"
```

---

### Task 8: Add artifact stone drops to dungeon

**Files:**
- Modify: `bot/cogs/dungeon.py`

- [ ] **Step 1: Add stone drop in `calc_dungeon_rewards`**

In `calc_dungeon_rewards`, after the existing reward calculation:

```python
    if floor >= 50:
        import random
        if random.random() < 0.03:
            rewards["stones"]["artifact"] = 1
```

And in the rewards dict initialization:
```python
    rewards = {
        "stones": {"stone_basic": 0, "stone_medium": 0, "stone_advanced": 0, "artifact": 0},
        ...
    }
```

- [ ] **Step 2: Save artifact stones in `_collect_rewards`**

In the stone saving section, add after existing stone logic:

```python
            if acc["stones"].get("artifact", 0) > 0:
                art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (sid,))
                art_row = await art_cursor.fetchone()
                if art_row:
                    await db.execute("UPDATE player_artifact SET stone_count=stone_count+? WHERE player_id=?", (acc["stones"]["artifact"], sid))
                else:
                    await db.execute("INSERT INTO player_artifact (player_id, star, stone_count) VALUES (?, 0, ?)", (sid, acc["stones"]["artifact"]))
```

- [ ] **Step 3: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.dungeon import DungeonCog; print('OK')"`

- [ ] **Step 4: Commit**

```bash
git add bot/cogs/dungeon.py
git commit -m "feat: add artifact stone drops from dungeon floor 50+"
```

---

### Task 9: Add admin command

**Files:**
- Modify: `bot/cogs/admin.py`

- [ ] **Step 1: Add command**

Add to AdminCog:

```python
    @commands.command(name="giveart")
    async def giveart_cmd(self, ctx, member: discord.Member = None, amount: str = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!"); return
        if not member or not amount:
            await ctx.reply("❌ !giveart @player <số>"); return
        try: amt = int(amount.strip())
        except: await ctx.reply("❌ Số không hợp lệ!"); return
        sid = str(member.id)
        db = await get_db()
        try:
            await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + ?)",
                             (sid, sid, sid, amt))
            await db.commit()
            await ctx.reply(f"💎 Cho {member.display_name} {amt} Đá Thần Khí!")
        finally:
            await db.close()
```

- [ ] **Step 2: Verify**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.admin import AdminCog; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/admin.py
git commit -m "feat: add admin !giveart command"
```

---

### Task 10: Load artifact data in all player loaders

**Files:**
- Modify: `bot/cogs/npc.py` (in `_start_npc_battle`, after loading buffs)
- Modify: `bot/views/battle_view.py` (in `_load_full_player`, after loading buffs)
- Modify: `bot/views/challenge_view.py` (in accept handler, after loading buffs)
- Modify: `bot/engine/combat_power.py` (in `update_combat_power`, when loading pdata)

- [ ] **Step 1: Add artifact loading in each file**

In all 4 files, where player data is loaded and `pdata["buffs"]` is set, add:

```python
            art_cursor = await db.execute("SELECT star, stone_count FROM player_artifact WHERE player_id=?", (pid,))
            art_row = await art_cursor.fetchone()
            pdata["_artifact_star"] = art_row[0] if art_row else 0
            pdata["_artifact_stones"] = art_row[1] if art_row else 0
```

Use the correct variable name for player ID in each file (`sid`, `pid`, `player_id`).

- [ ] **Step 2: Verify all imports**

Run: `.\venv\Scripts\python.exe -c "from bot.cogs.npc import NPCCog; from bot.views.battle_view import BattleView; from bot.views.challenge_view import ChallengeView; from bot.engine.combat_power import update_combat_power; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add bot/cogs/npc.py bot/views/battle_view.py bot/views/challenge_view.py bot/engine/combat_power.py
git commit -m "feat: load artifact star data in all player data loaders"
```

---

### Task 11: Final integration test

- [ ] **Step 1: Run all tests**

Run: `.\venv\Scripts\python.exe -m pytest tests/ -v`

- [ ] **Step 2: Verify all imports**

```
.\venv\Scripts\python.exe -c "
import asyncio
async def t():
    from bot.database import init_db; await init_db()
    from bot.data.artifacts import ARTIFACTS
    from bot.cogs.thankhi import ThankhiCog
    from bot.views.stats_view import StatsView
    print('ALL OK')
asyncio.run(t())
"
```

- [ ] **Step 3: Commit**

```bash
git commit -m "test: final integration test all pass" --allow-empty
```
