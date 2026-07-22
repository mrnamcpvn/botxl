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
        await self._show_gem_inventory(ctx, str(ctx.author.id))

    @app_commands.command(name="khoda", description="💎 Xem kho đá quý")
    async def slash_kho_da(self, interaction: discord.Interaction):
        await self._show_gem_inventory(interaction, str(interaction.user.id))

    async def _show_gem_inventory(self, ctx_or_int, sid: str):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT gem_type, gem_level, quantity FROM player_gems WHERE player_id=? AND quantity>0 ORDER BY gem_type, gem_level",
                (sid,))
            rows = await cursor.fetchall()
        finally:
            await db.close()

        if not rows:
            msg = "📦 Kho đá trống! Đánh NPC Lv.10+, dungeon tầng 20+, world boss để kiếm đá."
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg)
            return

        by_type: dict[str, list] = {}
        for r in rows:
            gt = r[0]
            if gt not in by_type:
                by_type[gt] = []
            by_type[gt].append((r[1], r[2]))

        # Tính tổng stat nếu khảm tất cả
        total_stats: dict[str, int] = {}
        lines = []
        for gt, levels in by_type.items():
            info = GEM_TYPES.get(gt, {})
            name = info.get("name", gt)
            stat = info.get("stat", gt)
            gem_levels_vals = info.get("levels", [])
            lv_strs = []
            for lv, qty in sorted(levels):
                val = gem_levels_vals[lv - 1] if lv <= len(gem_levels_vals) else 0
                lv_strs.append(f"C{lv}×{qty} _(+{val})_")
                # Tổng stat tất cả đá đang có
                total_stats[stat] = total_stats.get(stat, 0) + val * qty
            lines.append(f"{name}: {' | '.join(lv_strs)}")

        # Tổng stat summary
        stat_lines = []
        stat_labels = {"hp": "❤️ HP", "atk": "⚔️ ATK", "def": "🛡️ DEF",
                       "spd": "💨 SPD", "crit": "💥 CRIT", "pierce": "🔱 PIERCE"}
        for st, val in total_stats.items():
            if val > 0:
                stat_lines.append(f"{stat_labels.get(st, st)}: +{val}")

        desc = "\n".join(lines)
        if stat_lines:
            desc += f"\n\n📊 **Tổng nếu khảm hết:** {' · '.join(stat_lines)}"

        embed = discord.Embed(
            title="💎 Kho Đá Quý",
            description=desc,
            color=0x9b59b6)
        embed.set_footer(text="!khamda để khảm vào trang bị | !ghepda <loại> <cấp> để ghép")

        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(embed=embed)
        else:
            await ctx_or_int.response.send_message(embed=embed)

    @commands.command(name="ghepda", aliases=["ghep"])
    async def ghep_da(self, ctx, gem_type: str, level: int):
        await self._ghep_da(ctx, str(ctx.author.id), gem_type, level)

    @app_commands.command(name="ghepda", description="🔄 Ghép 3 đá cùng loại cùng cấp → 1 đá cấp cao hơn")
    @app_commands.describe(gem_type="Loại đá (hp/atk/def/spd/crit/pierce)", level="Cấp đá muốn ghép (1-8)")
    @app_commands.choices(gem_type=[
        app_commands.Choice(name="🔴 Hồng Ngọc (HP)", value="hp"),
        app_commands.Choice(name="⚔️ Lục Bảo (ATK)", value="atk"),
        app_commands.Choice(name="🛡️ Lam Ngọc (DEF)", value="def"),
        app_commands.Choice(name="💨 Phong Tinh (SPD)", value="spd"),
        app_commands.Choice(name="💥 Huyết Thạch (CRIT)", value="crit"),
        app_commands.Choice(name="🔱 Tử Tinh (PIERCE)", value="pierce"),
    ])
    async def slash_ghep_da(self, interaction: discord.Interaction, gem_type: str, level: int):
        await self._ghep_da(interaction, str(interaction.user.id), gem_type, level)

    async def _ghep_da(self, ctx_or_int, sid: str, gem_type: str, level: int):
        if gem_type not in GEM_TYPES:
            types = ", ".join(GEM_TYPES.keys())
            msg = f"❌ Loại đá không hợp lệ! Dùng: `{types}`\nVD: `!ghepda hp 1`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        if level < 1 or level >= GEM_MAX_LEVEL:
            msg = f"❌ Chỉ ghép được từ C1 đến C{GEM_MAX_LEVEL - 1}!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
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
                msg = f"❌ Cần 3 viên {info['name']} C{level}! Bạn chỉ có {row[0] if row else 0} viên."
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            crow = await (await db.execute("SELECT coins FROM players WHERE id=?", (sid,))).fetchone()
            if not crow or crow[0] < cost:
                msg = f"❌ Không đủ {cost}🪙! Bạn có {crow[0] if crow else 0}🪙."
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
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

        levels_vals = info.get("levels", [])
        new_val = levels_vals[target_level - 1] if target_level <= len(levels_vals) else 0
        stat = info.get("stat", "?")
        msg = (f"✅ Ghép 3× {info['name']} C{level} + {cost}🪙 → 1× **{info['name']} C{target_level}**!\n"
               f"📈 +{new_val} {stat.upper()}")
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg)

    @ghep_da.error
    async def ghep_da_error(self, ctx, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.reply("❌ Dùng: `!ghepda <loại> <cấp>`\nVD: `!ghepda hp 1`\nLoại: hp, atk, def, spd, crit, pierce")

    @commands.command(name="khamda", aliases=["kham"])
    async def kham_da(self, ctx):
        await self._khamda_entry(ctx, str(ctx.author.id), ctx.author.display_name)

    @app_commands.command(name="khamda", description="🔮 Khảm/tháo đá quý vào trang bị")
    async def slash_kham_da(self, interaction: discord.Interaction):
        await self._khamda_entry(interaction, str(interaction.user.id), interaction.user.display_name)

    async def _khamda_entry(self, ctx_or_int, sid: str, display_name: str):
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1",
                (sid,))
            eq_rows = await cursor.fetchall()
        finally:
            await db.close()

        if not eq_rows:
            msg = "❌ Bạn chưa có trang bị nào đang mang!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
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
            msg = "❌ Không có trang bị hợp lệ! (Chỉ hỗ trợ trang bị hệ thống)"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        view = GemSocketSelectView(sid, eq_map, display_name)
        view.add_item(GemSocketSelect(sid, eq_map, options))
        msg = "🔮 Chọn trang bị để khảm đá:"
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg, view=view)
        else:
            await ctx_or_int.response.send_message(msg, view=view)

    @commands.command(name="huongdanda", aliases=["gemhelp"])
    async def huong_dan_da(self, ctx):
        embed = self._build_gem_help_embed()
        await ctx.reply(embed=embed)

    @app_commands.command(name="huongdanda", description="💎 Hướng dẫn hệ thống Đá Khảm")
    async def slash_huong_dan_da(self, interaction: discord.Interaction):
        embed = self._build_gem_help_embed()
        await interaction.response.send_message(embed=embed)

    def _build_gem_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💎 Hướng Dẫn Đá Khảm (Gem Socket)",
            description=(
                "Khảm đá quý vào trang bị để tăng chỉ số! Mỗi trang bị có số ô socket tùy theo sao.\n\n"
            ),
            color=0x9b59b6,
        )

        embed.add_field(
            name="📊 Số ô socket theo sao",
            value=(
                "⭐ 1-3★ → **1 ô**\n"
                "⭐ 4-5★ → **2 ô**\n"
                "⭐ 6★ → **3 ô**\n"
                "⭐ 7-9★ → **4 ô** (tương lai)"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔴 Các loại đá quý",
            value=(
                "🔴 **Hồng Ngọc** — +HP (max C9: +2500)\n"
                "⚔️ **Lục Bảo** — +ATK (max C9: +250)\n"
                "🛡️ **Lam Ngọc** — +DEF (max C9: +160)\n"
                "💨 **Phong Tinh** — +SPD (max C9: +160)\n"
                "💥 **Huyết Thạch** — +CRIT (max C9: +120)\n"
                "🔱 **Tử Tinh** — +PIERCE (max C9: +120)"
            ),
            inline=False,
        )

        embed.add_field(
            name="⛏️ Nguồn rơi",
            value=(
                "• **NPC Lv 10-19** → Đá C1 (10%)\n"
                "• **NPC Lv 20-25** → Đá C2 (10%)\n"
                "• **NPC Lv 26-30** → Đá C3 (10%)\n"
                "• **Dungeon 20-40** → Đá C1 (8%)\n"
                "• **Dungeon 41-60** → Đá C2 (8%)\n"
                "• **Dungeon 61-80** → Đá C3 (8%)\n"
                "• **Dungeon 81-100** → Đá C4 (8%)\n"
                "• **World Boss** → C1-C3 (100%)"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔄 Ghép đá",
            value=(
                "`!ghepda <loại> <cấp>` hoặc `/ghepda`\n"
                "3 viên cùng loại + coin → 1 viên cấp cao hơn\n"
                "Phí = cấp đích × 500🪙\n"
                "VD: `!ghepda hp 1` → 3× Hồng Ngọc C1 + 1.000🪙 → C2"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔮 Khảm & Tháo",
            value=(
                "`!khamda` hoặc `/khamda` — Mở giao diện khảm/tháo đá\n"
                "Khảm mới vào ô trống: **miễn phí**\n"
                "Tháo đá hoặc đổi đá: **cấp đá × 1.000🪙**\n"
                "Đá tháo ra được hoàn lại kho, không mất"
            ),
            inline=False,
        )

        embed.add_field(
            name="📦 Xem kho & Xem trên stats",
            value=(
                "`!khoda` hoặc `/khoda` — Xem kho đá + tổng stat tiềm năng\n"
                "`/stats` → Tab **💎 Đá Khảm** — Xem đá đang khảm trên từng trang bị"
            ),
            inline=False,
        )

        embed.set_footer(text="💡 Mẹo: Ưu tiên khảm đá vào trang bị 5-6★ để có nhiều ô socket hơn!")
        return embed


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
            # Kiểm tra đủ đá
            cursor = await db.execute(
                "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                (self.user_id, gt, gl))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await interaction.response.edit_message(content="❌ Không đủ đá!", view=None)
                return

            # Kiểm tra ô hiện tại có đá chưa — nếu có thì trả lại
            sc = await db.execute(
                "SELECT socket_1, socket_2, socket_3, socket_4 FROM equipment_sockets WHERE equip_instance_id=?",
                (int(self.eq_id),))
            sr = await sc.fetchone()
            socket_idx = int(self.socket_key.split("_")[1]) - 1
            old_gem_str = (sr[socket_idx] if sr and sr[socket_idx] else "") if sr else ""

            refund_msg = ""
            if old_gem_str and ":" in old_gem_str:
                old_parts = old_gem_str.split(":")
                old_gt, old_gl = old_parts[0], int(old_parts[1])
                remove_cost = old_gl * GEM_REMOVE_COST_PER_LEVEL

                # Tính phí tháo đá cũ trước khi khảm mới
                crow = await (await db.execute(
                    "SELECT coins FROM players WHERE id=?", (self.user_id,))).fetchone()
                if not crow or crow[0] < remove_cost:
                    coins_have = crow[0] if crow else 0
                    old_info = GEM_TYPES.get(old_gt, {})
                    await interaction.response.edit_message(
                        content=(
                            f"❌ Ô này đang có **{old_info.get('name', old_gt)} C{old_gl}**!\n"
                            f"Cần **{remove_cost}🪙** để tháo ra trước, bạn có **{coins_have}🪙**."
                        ),
                        view=None)
                    return

                # Trừ coin tháo + trả lại đá cũ
                await db.execute(
                    "UPDATE players SET coins=coins-? WHERE id=?", (remove_cost, self.user_id))
                await db.execute(
                    "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+1",
                    (self.user_id, old_gt, old_gl))
                old_info = GEM_TYPES.get(old_gt, {})
                refund_msg = f"\n↩️ Tháo {old_info.get('name', old_gt)} C{old_gl} (-{remove_cost}🪙, trả lại kho)"

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
            content=f"✅ Đã khảm {info.get('name', gt)} C{gl} (+{val} {stat.upper()}) vào ô {self.socket_num} của {self.eq_name}!{refund_msg}",
            view=None)


async def setup(bot):
    await bot.add_cog(GemSocket(bot))
