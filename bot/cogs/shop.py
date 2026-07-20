import discord
from discord import app_commands
from discord.ext import commands
from bot.database import get_db
from bot.data.shop_items import SHOP_ITEMS
from bot.engine.combat_power import update_combat_power
from bot.data.equipment import EQUIPMENT, STAR_LABELS, STAR_NAMES, STAR_COLORS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.data.skills import SKILLS_DB, RARITY_STARS
from bot.engine.rewards import calc_level
from bot.engine.battle import get_effective_stats
from bot.views.inventory_view import InventoryView

EQUIP_SLOT_MAP = {}
ALL_SLOTS = ["weapon", "armor", "boots", "gloves", "belt", "ring"]


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="shop")
    async def shop_cmd(self, ctx):
        await self._show_shop(ctx, ctx.author, "!")

    @commands.command(name="buy")
    async def buy_cmd(self, ctx, item_id: str = None):
        await self._buy(ctx, ctx.author, item_id, "!")

    @commands.command(name="use")
    async def use_cmd(self, ctx, item_id: str = None):
        await self._use(ctx, ctx.author, item_id, "!")

    @commands.command(name="equip")
    async def equip_cmd(self, ctx, item_id: str = None):
        await self._equip(ctx, ctx.author, item_id, "!")

    @commands.command(name="sell")
    async def sell_cmd(self, ctx, item_id: str = None):
        await self._sell(ctx, ctx.author, item_id, "!")

    @commands.command(name="inv", aliases=["inventory"])
    async def inv_cmd(self, ctx):
        await self._show_inv(ctx, ctx.author, "!")

    async def _show_shop(self, ctx_or_int, user, prefix):
        embed = discord.Embed(title="🏪 SHOP BA QUE XỎ LÁ", color=0xffaa00,
                              description=f"💰 Xài lệnh: `{prefix}buy <số>` | `/buy`\n🔥 Kỹ năng xem ở `{prefix}skills` | `/skills`")
        consumables = {k: v for k, v in SHOP_ITEMS.items() if v["type"] == "consumable"}
        con_lines = []
        for iid, item in consumables.items():
            con_lines.append(f"`{iid}` {item['name']} — **{item['price']}🪙**\n　└ {item['desc']}")
        embed.add_field(name="🧪 Tiêu Hao", value="\n".join(con_lines), inline=False)
        if isinstance(ctx_or_int, discord.ext.commands.Context):
            await ctx_or_int.send(embed=embed)
        else:
            await ctx_or_int.response.send_message(embed=embed)

    async def _buy(self, ctx_or_int, user, item_id, prefix):
        if not item_id:
            await self._reply(ctx_or_int, f"❌ {prefix}buy <số>! Xem {prefix}shop")
            return
        try:
            iid = int(item_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số không hợp lệ!")
            return
        if iid not in SHOP_ITEMS:
            await self._reply(ctx_or_int, f"❌ Không có item {iid}!")
            return
        item = SHOP_ITEMS[iid]
        uid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (uid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            pdata = dict(row)
            if pdata["coins"] < item["price"]:
                await self._reply(ctx_or_int, f"😅 Nghèo! Cần {item['price']}🪙, có {pdata['coins']}🪙")
                return
            await db.execute("UPDATE players SET coins=? WHERE id=?", (pdata["coins"] - item["price"], uid))
            if item["type"] == "consumable":
                await db.execute("INSERT OR REPLACE INTO inventory (player_id, item_id, quantity) VALUES (?, ?, COALESCE((SELECT quantity FROM inventory WHERE player_id=? AND item_id=?), 0) + 1)",
                                 (uid, iid, uid, iid))
            elif item["type"] == "equipment":
                await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)",
                                 (uid, iid))
            elif item["type"] == "skill":
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (uid, item["skill_id"]))
            await db.commit()
            await self._reply(ctx_or_int, f"✅ Mua **{item['name']}** thành công!")
            from bot.cogs.quest import update_progress
            await update_progress(db, uid, 4)
        finally:
            await db.close()

    async def _use(self, ctx_or_int, user, item_id, prefix):
        if not item_id:
            await self._reply(ctx_or_int, f"❌ {prefix}use <số>!")
            return
        try:
            iid = int(item_id.strip())
        except:
            await self._reply(ctx_or_int, "❌ Số không hợp lệ!")
            return
        if iid not in SHOP_ITEMS or SHOP_ITEMS[iid]["type"] != "consumable":
            await self._reply(ctx_or_int, "❌ Item không phải đồ tiêu hao!")
            return
        item = SHOP_ITEMS[iid]
        uid = str(user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?", (uid, iid))
            row = await cursor.fetchone()
            if not row or row[0] < 1:
                await self._reply(ctx_or_int, "📭 Không có item này trong kho!")
                return
            player_cursor = await db.execute("SELECT * FROM players WHERE id=?", (uid,))
            player_row = await player_cursor.fetchone()
            if not player_row:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            pdata = dict(player_row)
            effect = item["effect"]
            msg_parts = []
            if "hp_restore_percent" in effect:
                from bot.utils.player_loader import load_player_full
                full = await load_player_full(db, uid)
                eff_max = get_effective_stats(full)["hp_max"] if full else pdata.get("hp_max", 100)
                pct = effect["hp_restore_percent"]
                heal = int(eff_max * pct / 100)
                new_hp = min(eff_max, pdata["hp"] + heal)
                actual = new_hp - pdata["hp"]
                pdata["hp"] = new_hp
                await db.execute("UPDATE players SET hp=? WHERE id=?", (new_hp, uid))
                msg_parts.append(f"❤️ Hồi {actual} HP")
            if "buff_attack_percent" in effect:
                boost = 3
                await db.execute("INSERT OR REPLACE INTO player_buffs (player_id, attack_boost, defense_boost, lucky) VALUES (?, ?, COALESCE((SELECT defense_boost FROM player_buffs WHERE player_id=?), 0), COALESCE((SELECT lucky FROM player_buffs WHERE player_id=?), 0))",
                                 (uid, boost, uid, uid))
                msg_parts.append(f"⚡ +30% dmg trong 3 trận!")
            if "buff_defense_percent" in effect:
                boost = 3
                await db.execute("INSERT OR REPLACE INTO player_buffs (player_id, attack_boost, defense_boost, lucky) VALUES (?, COALESCE((SELECT attack_boost FROM player_buffs WHERE player_id=?), 0), ?, COALESCE((SELECT lucky FROM player_buffs WHERE player_id=?), 0))",
                                 (uid, uid, boost, uid))
                msg_parts.append(f"🛡️ +50% DEF trong 3 trận!")
            if "buff_lucky" in effect:
                lr = 3
                await db.execute("INSERT OR REPLACE INTO player_buffs (player_id, attack_boost, defense_boost, lucky) VALUES (?, COALESCE((SELECT attack_boost FROM player_buffs WHERE player_id=?), 0), COALESCE((SELECT defense_boost FROM player_buffs WHERE player_id=?), 0), ?)",
                                  (uid, uid, uid, lr))
                msg_parts.append(f"🎲 Lucky ×3 trận!")
            new_qty = row[0] - 1
            if new_qty <= 0:
                await db.execute("DELETE FROM inventory WHERE player_id=? AND item_id=?", (uid, iid))
            else:
                await db.execute("UPDATE inventory SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, uid, iid))
            await db.commit()
            parts = " | ".join(msg_parts) if msg_parts else "✅"
            await self._reply(ctx_or_int, f"✅ Dùng **{item['name']}**! {parts}")
        finally:
            await db.close()

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
            if iid in EQUIPMENT:
                item_def = EQUIPMENT[iid]
                slot = item_def["slot"]
                slot_name = EQ_SLOT_NAMES.get(slot, slot)
                name = item_def["name"]
            elif iid in SHOP_ITEMS and SHOP_ITEMS[iid].get("type") == "equipment":
                item_def = SHOP_ITEMS[iid]
                slot = item_def["slot"]
                slot_name = EQUIP_SLOT_MAP.get(slot, slot)
                name = item_def["name"]
            else:
                await self._reply(ctx_or_int, "❌ Item không phải trang bị!")
                return

            cursor = await db.execute(
                "SELECT id, enhance, equipped FROM player_equipment WHERE player_id=? AND item_id=? ORDER BY equipped DESC, id ASC",
                (uid, iid))
            rows = await cursor.fetchall()
            if not rows:
                await self._reply(ctx_or_int, "📭 Không có trang bị này! Xem `/inv`")
                return

            equipped_row = next((r for r in rows if r[2] == 1), None)
            if equipped_row:
                eq_id = equipped_row[0]
                enhance = equipped_row[1]
                enhance_str = f" +{enhance}" if enhance > 0 else ""
                await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (eq_id,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Tháo **{name}{enhance_str}** khỏi {slot_name}!")
            else:
                eq_id = rows[0][0]
                enhance = rows[0][1]
                enhance_str = f" +{enhance}" if enhance > 0 else ""

                equipped_cursor = await db.execute(
                    "SELECT pe.id, pe.item_id FROM player_equipment pe WHERE pe.player_id=? AND pe.equipped=1", (uid,))
                async for erow in equipped_cursor:
                    ee_id = erow[0]
                    ee_item_id = erow[1]
                    ee_slot = None
                    if ee_item_id in EQUIPMENT:
                        ee_slot = EQUIPMENT[ee_item_id]["slot"]
                    elif ee_item_id in SHOP_ITEMS and SHOP_ITEMS[ee_item_id].get("type") == "equipment":
                        ee_slot = SHOP_ITEMS[ee_item_id]["slot"]
                    if ee_slot == slot:
                        await db.execute("UPDATE player_equipment SET equipped=0 WHERE id=?", (ee_id,))

                await db.execute("UPDATE player_equipment SET equipped=1 WHERE id=?", (eq_id,))
                await db.commit()
                await self._reply(ctx_or_int, f"✅ Trang bị **{name}{enhance_str}** vào {slot_name}!")
        finally:
            await db.close()

    async def _show_inv(self, ctx_or_int, user, prefix):
        uid = str(user.id)
        db = await get_db()
        try:
            # Player
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (uid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Chưa đăng ký!")
                return
            pdata = dict(row)

            # Consumables
            inv_cursor = await db.execute(
                "SELECT item_id, quantity FROM inventory WHERE player_id=? AND quantity>0 ORDER BY item_id",
                (uid,))
            consumables = {}
            async for r in inv_cursor:
                consumables[r[0]] = r[1]

            # Equipment (bao gồm hidden_stats để hiện 🌟)
            eq_cursor = await db.execute(
                "SELECT id, item_id, enhance, equipped, hidden_stats FROM player_equipment "
                "WHERE player_id=? ORDER BY equipped DESC, id",
                (uid,))
            eq_rows = []
            async for r in eq_cursor:
                eq_rows.append(dict(r))

            # Enhance stones
            stone_cursor = await db.execute(
                "SELECT stone_basic, stone_medium, stone_advanced FROM player_enhance_stones WHERE player_id=?",
                (uid,))
            stone_row = await stone_cursor.fetchone()

            # Skills
            skill_cursor = await db.execute("SELECT skill_id FROM player_skills WHERE player_id=?", (uid,))
            owned_skills = set()
            async for r in skill_cursor:
                owned_skills.add(r[0])

            slot_skill_cursor = await db.execute(
                "SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (uid,))
            equipped_skills = {}
            async for r in slot_skill_cursor:
                equipped_skills[r[0]] = r[1]

            # Buff
            buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (uid,))
            buff_row = await buff_cursor.fetchone()
            pdata["buffs"] = dict(buff_row) if buff_row else {}

        finally:
            await db.close()

        view = InventoryView(
            user=user,
            pdata=pdata,
            eq_rows=eq_rows,
            consumables=consumables,
            stone_row=stone_row,
            owned_skills=owned_skills,
            equipped_skills=equipped_skills,
        )

        if isinstance(ctx_or_int, discord.ext.commands.Context):
            await ctx_or_int.send(embed=view.embed, view=view)
        else:
            await ctx_or_int.response.send_message(embed=view.embed, view=view)

    async def _reply(self, ctx_or_int, msg, ephemeral=False):
        if isinstance(ctx_or_int, discord.ext.commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.response.send_message(msg, ephemeral=ephemeral)

    @app_commands.command(name="shop", description="🏪 Xem shop")
    async def slash_shop(self, interaction: discord.Interaction):
        await self._show_shop(interaction, interaction.user, "/")

    @app_commands.command(name="buy", description="🛒 Mua item")
    @app_commands.describe(item_id="Số item muốn mua")
    async def slash_buy(self, interaction: discord.Interaction, item_id: str):
        await self._buy(interaction, interaction.user, item_id, "/")

    @slash_buy.autocomplete("item_id")
    async def buy_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT coins FROM players WHERE id=?", (uid,))
            row = await cursor.fetchone()
            coins = row[0] if row else 0
            choices = []
            for iid, item in SHOP_ITEMS.items():
                if current.lower() in str(iid) or current.lower() in item["name"].lower():
                    can = "✅" if coins >= item["price"] else "❌"
                    choices.append(app_commands.Choice(name=f"({iid}) {item['name']} 🪙{item['price']} {can}"[:100], value=str(iid)))
            return choices[:25]
        finally:
            await db.close()

    @app_commands.command(name="use", description="🧪 Dùng item tiêu hao")
    @app_commands.describe(item_id="Số item muốn dùng")
    async def slash_use(self, interaction: discord.Interaction, item_id: str):
        await self._use(interaction, interaction.user, item_id, "/")

    @slash_use.autocomplete("item_id")
    async def use_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT item_id, quantity FROM inventory WHERE player_id=? AND quantity>0", (uid,))
            choices = []
            async for r in cursor:
                iid = r[0]
                qty = r[1]
                item = SHOP_ITEMS.get(iid)
                if item and item["type"] == "consumable":
                    if current.lower() in str(iid) or current.lower() in item["name"].lower():
                        choices.append(app_commands.Choice(name=f"({iid}) {item['name']} ×{qty}"[:100], value=str(iid)))
            return choices[:25]
        finally:
            await db.close()

    @app_commands.command(name="equip", description="🗡️ Trang bị/tháo trang bị")
    @app_commands.describe(item_id="Số item muốn trang bị/tháo")
    async def slash_equip(self, interaction: discord.Interaction, item_id: str):
        await self._equip(interaction, interaction.user, item_id, "/")

    @slash_equip.autocomplete("item_id")
    async def equip_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT DISTINCT item_id FROM player_equipment WHERE player_id=?", (uid,))
            choices = []
            async for r in cursor:
                eiid = r[0]
                name = None
                if eiid in EQUIPMENT:
                    name = EQUIPMENT[eiid]["name"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid].get("type") == "equipment":
                    name = SHOP_ITEMS[eiid]["name"]
                if name and (current.lower() in str(eiid) or current.lower() in name.lower()):
                    eq_cursor = await db.execute(
                        "SELECT COUNT(*) as cnt, MAX(enhance) as max_enh FROM player_equipment WHERE player_id=? AND item_id=?",
                        (uid, eiid))
                    erow = await eq_cursor.fetchone()
                    cnt = erow[0]
                    max_enh = erow[1] or 0
                    enh_str = f" +{max_enh}" if max_enh > 0 else ""
                    eq_cursor2 = await db.execute(
                        "SELECT 1 FROM player_equipment WHERE player_id=? AND item_id=? AND equipped=1",
                        (uid, eiid))
                    is_equipped = await eq_cursor2.fetchone()
                    status = "✅" if is_equipped else "📦"
                    choices.append(app_commands.Choice(
                        name=f"({eiid}) {status} {name}{enh_str} ×{cnt}"[:100],
                        value=str(eiid)))
            return choices[:25]
        finally:
            await db.close()

    @app_commands.command(name="inv", description="🎒 Xem túi đồ")
    async def slash_inv(self, interaction: discord.Interaction):
        await self._show_inv(interaction, interaction.user, "/")

    @app_commands.command(name="sell", description="🛒 Bán hoặc phân giải trang bị")
    @app_commands.describe(item_id="ID trang bị muốn bán (xem /inv)")
    async def slash_sell(self, interaction: discord.Interaction, item_id: str):
        await self._sell(interaction, interaction.user, item_id, "/")

    @slash_sell.autocomplete("item_id")
    async def sell_autocomplete(self, interaction: discord.Interaction, current: str):
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=0", (uid,))
            choices = []
            async for r in cursor:
                eiid = r[1]
                if eiid in EQUIPMENT:
                    e = EQUIPMENT[eiid]
                    stars = STAR_LABELS.get(e["star"], "⭐")
                    enh_str = f" +{r[2]}" if r[2] > 0 else ""
                    name = f"({r[0]}) {stars} {e['name']}{enh_str}"
                    if current.lower() in str(r[0]) or current.lower() in e['name'].lower():
                        choices.append(app_commands.Choice(name=name[:100], value=str(r[0])))
            return choices[:25]
        finally:
            await db.close()

    @commands.command(name="unequip")
    async def unequip_cmd(self, ctx, slot: str = None):
        await self._unequip(ctx, str(ctx.author.id), slot, "!")

    @app_commands.command(name="unequip", description="🔓 Tháo trang bị")
    @app_commands.describe(slot="Slot muốn tháo")
    @app_commands.choices(slot=[
        app_commands.Choice(name="🗡️ Vũ Khí", value="weapon"),
        app_commands.Choice(name="🛡️ Áo Giáp", value="armor"),
        app_commands.Choice(name="👢 Giày", value="boots"),
        app_commands.Choice(name="🧤 Bao Tay", value="gloves"),
        app_commands.Choice(name="🎗️ Dây Lưng", value="belt"),
        app_commands.Choice(name="💍 Nhẫn", value="ring"),
    ])
    async def slash_unequip(self, interaction: discord.Interaction, slot: str):
        await self._unequip(interaction, str(interaction.user.id), slot, "/")

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
                    found = {"id": r[0], "item_id": r[1], "enhance": r[2]}
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

    async def _sell(self, ctx_or_int, user, item_id, prefix):
        if not item_id:
            await self._reply(ctx_or_int, f"❌ {prefix}sell <id> (xem ID trong `/inv`)")
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
            eiid = eq["item_id"]
            if eiid not in EQUIPMENT:
                await self._reply(ctx_or_int, "❌ Chỉ bán được trang bị!")
                return
            if eq["equipped"]:
                await self._reply(ctx_or_int, "❌ Tháo trang bị ra trước khi bán! `/unequip`")
                return

            e = EQUIPMENT[eiid]
            stars = STAR_LABELS.get(e["star"], "⭐")
            price = SELL_PRICES.get(e["star"], 100)
            dm = DISMANTLE_REWARDS.get(e["star"], {})
            dm_parts = [f"{STONE_LABELS.get(k,k)}×{v}" for k, v in dm.items()]

            embed = discord.Embed(
                title="🛒 Bán Trang Bị",
                description=f"{stars} **{e['name']}** +{eq['enhance']}\n\n"
                            f"💰 **Bán**: +{price}🪙\n"
                            f"💎 **Phân Giải**: {', '.join(dm_parts)}",
                color=STAR_COLORS.get(e["star"], 0xffaa00))
            view = SellView(uid, eq["id"], eiid, e["star"], eq["enhance"], e["name"])
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    @commands.command(name="equipment", aliases=["equipments", "trangbi"])
    async def equipment_cmd(self, ctx, slot: str = None):
        slot = (slot or "weapon").lower()
        if slot not in ["weapon", "armor", "boots", "gloves", "belt", "ring"]:
            slot = "weapon"
        embed = _catalog_embed(slot)
        view = EquipCatalogView(slot)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="equipment", description="📋 Danh mục toàn bộ trang bị")
    async def slash_equipment(self, interaction: discord.Interaction):
        embed = _catalog_embed("weapon")
        view = EquipCatalogView("weapon")
        await interaction.response.send_message(embed=embed, view=view)


class EquipCatalogView(discord.ui.View):
    def __init__(self, slot_filter: str = "weapon"):
        super().__init__(timeout=120)
        self.slot_filter = slot_filter
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        row0 = [("weapon", "🗡️ Vũ Khí"), ("armor", "🛡️ Áo Giáp"), ("boots", "👢 Giày")]
        row1 = [("gloves", "🧤 Bao Tay"), ("belt", "🎗️ Dây Lưng"), ("ring", "💍 Nhẫn")]
        for i, (val, label) in enumerate(row0):
            style = discord.ButtonStyle.primary if val == self.slot_filter else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=label, style=style, custom_id=f"cat_{val}", row=0)
            btn.callback = self._make_filter(val)
            self.add_item(btn)
        for val, label in row1:
            style = discord.ButtonStyle.primary if val == self.slot_filter else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=label, style=style, custom_id=f"cat_{val}", row=1)
            btn.callback = self._make_filter(val)
            self.add_item(btn)

    def _make_filter(self, slot: str):
        async def cb(interaction: discord.Interaction):
            self.slot_filter = slot
            embed = _catalog_embed(slot)
            self._update_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
        return cb


def _catalog_embed(slot_filter: str = "weapon") -> discord.Embed:
    items = [(eid, e) for eid, e in EQUIPMENT.items() if e["slot"] == slot_filter]
    items.sort(key=lambda x: x[1]["star"], reverse=True)
    best_star = items[0][1]["star"] if items else 0
    embed_color = STAR_COLORS.get(best_star, 0x00aaff)
    embed = discord.Embed(title=f"📋 TRANG BỊ — {EQ_SLOT_NAMES.get(slot_filter, slot_filter)}", color=embed_color)
    if not items:
        embed.description = "Trống!"
        return embed
    lines = []
    for eid, e in items:
        star = e["star"]
        stars = STAR_LABELS.get(star, "⭐")
        name = e["name"]
        if star == 6:
            name = f"**[Thần Thoại]** {name}"
        stat_parts = []
        atk_min, atk_max = None, None
        for k, v in e["stats"].items():
            if k == "attack_min": atk_min = v
            elif k == "attack_max": atk_max = v
            elif k == "defense": stat_parts.append(f"🛡️{v}")
            elif k == "hp": stat_parts.append(f"❤️{v}")
            elif k == "spd": stat_parts.append(f"💨{v}")
            elif k == "crit": stat_parts.append(f"💥{v}%")
            elif k == "pierce": stat_parts.append(f"🔱{v}%")
            elif k == "dodge": stat_parts.append(f"🍀{v}%")
            elif k == "reflect": stat_parts.append(f"🔄{v}%")
            elif k == "regen": stat_parts.append(f"💚{v}%/t")
        if atk_min is not None and atk_max is not None:
            stat_parts.insert(0, f"⚔️{atk_min}~{atk_max}")
        lines.append(f"`{eid}` {stars} **{e['name']}** ({' '.join(stat_parts)})")
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"⭐ {len(items)} món | Rơi từ PvP & NPC battle")
    return embed


SELL_PRICES = {1: 100, 2: 300, 3: 800, 4: 1200, 5: 2000, 6: 5000}

DISMANTLE_REWARDS = {
    1: {"stone_basic": 1},
    2: {"stone_basic": 2},
    3: {"stone_basic": 3, "stone_medium": 1},
    4: {"stone_basic": 4, "stone_medium": 2},
    5: {"stone_medium": 4, "stone_advanced": 2},
    6: {"stone_medium": 8, "stone_advanced": 3},
}

STONE_LABELS = {"stone_basic": "Đá sơ cấp", "stone_medium": "Đá trung cấp", "stone_advanced": "Đá cao cấp"}


class SellView(discord.ui.View):
    def __init__(self, player_id: str, eq_id: int, item_id: int, star: int, enhance: int, name: str):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.eq_id = eq_id
        self.item_id = item_id
        self.star = star
        self.enhance = enhance
        self.name = name
        self.used = False

        price = SELL_PRICES.get(star, 100)
        btn_sell = discord.ui.Button(
            emoji="💰", label=f"Bán ({price}🪙)", style=discord.ButtonStyle.success, custom_id="sell_coin", row=0)
        btn_sell.callback = self._sell_callback
        self.add_item(btn_sell)

        dm = DISMANTLE_REWARDS.get(star, {})
        dm_parts = [f"{STONE_LABELS.get(k,k)}×{v}" for k, v in dm.items()]
        btn_dismantle = discord.ui.Button(
            emoji="💎", label=f"Phân Giải ({', '.join(dm_parts)})", style=discord.ButtonStyle.primary, custom_id="sell_dismantle", row=0)
        btn_dismantle.callback = self._dismantle_callback
        self.add_item(btn_dismantle)

    async def _sell_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.used:
            return
        self.used = True
        db = await get_db()
        try:
            await db.execute("DELETE FROM player_equipment WHERE id=?", (self.eq_id,))
            price = SELL_PRICES.get(self.star, 100)
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (price, self.player_id))
            await db.commit()
            stars = STAR_LABELS.get(self.star, "⭐")
            await interaction.edit_original_response(
                content=f"💰 Bán {stars} **{self.name}** +{price}🪙", view=None)
        finally:
            await db.close()

    async def _dismantle_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.used:
            return
        self.used = True
        db = await get_db()
        try:
            await db.execute("DELETE FROM player_equipment WHERE id=?", (self.eq_id,))
            dm = DISMANTLE_REWARDS.get(self.star, {})
            for sk, sq in dm.items():
                await db.execute(f"INSERT OR REPLACE INTO player_enhance_stones (player_id, {sk}, stone_basic, stone_medium, stone_advanced) VALUES (?, ?, COALESCE((SELECT stone_basic FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_medium FROM player_enhance_stones WHERE player_id=?), 0), COALESCE((SELECT stone_advanced FROM player_enhance_stones WHERE player_id=?), 0))",
                                 (self.player_id, sq, self.player_id, self.player_id, self.player_id))
                await db.execute(f"UPDATE player_enhance_stones SET {sk}=COALESCE((SELECT {sk} FROM player_enhance_stones WHERE player_id=?), 0) WHERE player_id=? AND ({sk} IS NULL OR {sk}=0)",
                                 (self.player_id, self.player_id))
            await db.commit()
            dm_parts = [f"{STONE_LABELS.get(k,k)}×{v}" for k, v in dm.items()]
            stars = STAR_LABELS.get(self.star, "⭐")
            await interaction.edit_original_response(
                content=f"💎 Phân giải {stars} **{self.name}** → {', '.join(dm_parts)}", view=None)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
