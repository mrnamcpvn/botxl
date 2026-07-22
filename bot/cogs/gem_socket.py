import discord
from discord import app_commands
from discord.ext import commands
import random
from bot.database import get_db
from bot.config import GEM_TYPES, GEM_MAX_LEVEL, GEM_MERGE_COST_PER_LEVEL, GEM_REMOVE_COST_PER_LEVEL, SOCKETS_BY_STAR
from bot.data.equipment import EQUIPMENT
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
            cursor = await db.execute(
                "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                (sid, gem_type, level))
            row = await cursor.fetchone()
            if not row or row[0] < 3:
                await ctx.reply(f"❌ Cần 3 viên {info['name']} C{level}! Bạn chỉ có {row[0] if row else 0} viên.")
                return

            crow = await (await db.execute("SELECT coins FROM players WHERE id=?", (sid,))).fetchone()
            if not crow or crow[0] < cost:
                await ctx.reply(f"❌ Không đủ {cost}🪙! Bạn có {crow[0] if crow else 0}🪙.")
                return

            await db.execute("UPDATE player_gems SET quantity=quantity-3 WHERE player_id=? AND gem_type=? AND gem_level=?", (sid, gem_type, level))
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))

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
                val = str(eid_db)
                options.append(discord.SelectOption(
                    label=label[:100],
                    value=val,
                    description=f"Slot: {slot} | {num_sockets} ô khảm"))
                eq_map[val] = eq

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

            gc = await db.execute(
                "SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0 ORDER BY gem_type, gem_level",
                (self.user_id,))
            gem_rows = await gc.fetchall()
        finally:
            await db.close()

        self.clear_items()

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
                levels = info.get("levels", [0])
                gval = levels[gl - 1] if gl <= len(levels) else 0
                stat = info.get("stat", "?")
                remove_cost = gl * GEM_REMOVE_COST_PER_LEVEL
                lines.append(f"Ô {i}: {gname} C{gl} (+{gval} {stat.upper()}) — [Tháo {remove_cost}🪙]")
            else:
                lines.append(f"Ô {i}: 🟫 Trống — [Khảm]")

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

        for i in range(1, num_sockets + 1):
            key = f"socket_{i}"
            val = sockets[key]
            if val and ":" in val:
                btn = GemSocketButton(
                    self.user_id, eid, key, "remove", eq["name"],
                    f"Tháo ô {i}", i, self.display_name)
            else:
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

                crow = await (await db.execute("SELECT coins FROM players WHERE id=?", (self.user_id,))).fetchone()
                if not crow or crow[0] < cost:
                    await interaction.response.send_message(
                        f"❌ Không đủ {cost}🪙 để tháo! Bạn có {crow[0] if crow else 0}🪙.", ephemeral=True)
                    return

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

            else:
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
                    levels = info.get("levels", [0])
                    val = levels[gl - 1] if gl <= len(levels) else 0
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
            cursor = await db.execute(
                "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                (self.user_id, gt, gl))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await interaction.response.edit_message(content="❌ Không đủ đá!", view=None)
                return

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
        levels = info.get("levels", [0])
        val = levels[gl - 1] if gl <= len(levels) else 0
        stat = info.get("stat", "?")
        await interaction.response.edit_message(
            content=f"✅ Đã khảm {info.get('name', gt)} C{gl} (+{val} {stat.upper()}) vào ô {self.socket_num} của {self.eq_name}!",
            view=None)


async def setup(bot):
    await bot.add_cog(GemSocket(bot))
