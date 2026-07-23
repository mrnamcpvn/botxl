import discord
from bot.database import get_db
from bot.data.wives import WIVES
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT
from bot.config import GEM_TYPES, CULTIVATION_ITEM_NAMES


class TradeView(discord.ui.View):
    """Trade offer view with Accept/Deny buttons. Works for wives, items, gems, and cultivation items."""

    def __init__(self, bot, receiver_id: str, sender_id: str,
                 sender_name: str, receiver_name: str, channel_id: int, data: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.receiver_id = receiver_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.receiver_name = receiver_name
        self.channel_id = channel_id
        self.data = data  # {trade_type, item_id/gem_type/gem_level, quantity}
        self.used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.used:
            return
        self.used = True
        ch = self.bot.get_channel(self.channel_id)
        if ch:
            await ch.send(f"⏰ **{self.receiver_name}** không phản hồi! Hủy giao dịch.")

    @discord.ui.button(emoji="✅", label="Nhận", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.Button):
        if self.used:
            return
        self.used = True
        await interaction.response.defer()
        db = await get_db()
        try:
            ttype = self.data.get("trade_type", "item")
            sid, rid = self.sender_id, self.receiver_id
            qty = self.data.get("quantity", 1)

            if ttype == "wife":
                cursor = await db.execute("SELECT * FROM player_wives WHERE id=? AND player_id=?",
                                          (self.data["wife_dbid"], sid))
                row = await cursor.fetchone()
                if not row:
                    await interaction.followup.send("🤷 Vợ đã biến mất!", ephemeral=True)
                    return
                w = dict(row)
                wd = WIVES.get(w["wife_id"], WIVES[1])
                await db.execute("UPDATE player_wives SET player_id=?, equipped=0 WHERE id=?",
                                  (rid, self.data["wife_dbid"]))
                await db.commit()
                from bot.cogs.quest import update_progress
                await update_progress(db, rid, 10)
                self.clear_items()
                await interaction.edit_original_response(
                    content=f"🤝 **{self.receiver_name}** nhận **{wd['emoji']} {wd['name']}** từ **{self.sender_name}**!",
                    view=self)

            elif ttype == "cult":
                item_id = self.data["item_id"]
                cursor = await db.execute(
                    "SELECT quantity FROM cultivation_items WHERE player_id=? AND item_id=?",
                    (sid, item_id))
                row = await cursor.fetchone()
                if not row or row[0] < qty:
                    await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                    return
                new_qty = row[0] - qty
                if new_qty <= 0:
                    await db.execute("DELETE FROM cultivation_items WHERE player_id=? AND item_id=?", (sid, item_id))
                else:
                    await db.execute("UPDATE cultivation_items SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, sid, item_id))
                await db.execute(
                    "INSERT INTO cultivation_items (player_id, item_id, quantity) VALUES (?, ?, ?) "
                    "ON CONFLICT(player_id, item_id) DO UPDATE SET quantity=quantity+?",
                    (rid, item_id, qty, qty))
                await db.commit()
                item_name = CULTIVATION_ITEM_NAMES.get(item_id, item_id)
                self.clear_items()
                await interaction.edit_original_response(
                    content=f"🤝 **{self.receiver_name}** nhận {qty}× **{item_name}** từ **{self.sender_name}**!",
                    view=self)

            elif ttype == "gem":
                gt = self.data["gem_type"]
                gl = self.data["gem_level"]
                cursor = await db.execute(
                    "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                    (sid, gt, gl))
                row = await cursor.fetchone()
                if not row or row[0] < qty:
                    await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                    return
                new_qty = row[0] - qty
                if new_qty <= 0:
                    await db.execute("DELETE FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?", (sid, gt, gl))
                else:
                    await db.execute("UPDATE player_gems SET quantity=? WHERE player_id=? AND gem_type=? AND gem_level=?", (new_qty, sid, gt, gl))
                await db.execute(
                    "INSERT INTO player_gems (player_id, gem_type, gem_level, quantity) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(player_id, gem_type, gem_level) DO UPDATE SET quantity=quantity+?",
                    (rid, gt, gl, qty, qty))
                await db.commit()
                gem_info = GEM_TYPES.get(gt, {})
                gem_name = f"{gem_info.get('name', gt)} C{gl}"
                self.clear_items()
                await interaction.edit_original_response(
                    content=f"🤝 **{self.receiver_name}** nhận {qty}× **{gem_name}** từ **{self.sender_name}**!",
                    view=self)

            elif ttype == "item":
                iid = self.data["item_id"]
                is_equip = iid in EQUIPMENT
                item_name = EQUIPMENT[iid]["name"] if is_equip else SHOP_ITEMS[iid]["name"]

                if is_equip:
                    cursor = await db.execute(
                        "SELECT id FROM player_equipment WHERE player_id=? AND item_id=? AND equipped=0 LIMIT ?",
                        (sid, iid, qty))
                    rows = await cursor.fetchall()
                    if len(rows) < qty:
                        await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                        return
                    for r in rows:
                        await db.execute("UPDATE player_equipment SET player_id=?, equipped=0 WHERE id=?",
                                         (rid, r[0]))
                else:
                    cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?",
                                               (sid, iid))
                    row = await cursor.fetchone()
                    if not row or row[0] < qty:
                        await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                        return
                    new_qty = row[0] - qty
                    if new_qty <= 0:
                        await db.execute("DELETE FROM inventory WHERE player_id=? AND item_id=?", (sid, iid))
                    else:
                        await db.execute("UPDATE inventory SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, sid, iid))
                    r_cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?", (rid, iid))
                    r_row = await r_cursor.fetchone()
                    if r_row:
                        await db.execute("UPDATE inventory SET quantity=quantity+? WHERE player_id=? AND item_id=?", (qty, rid, iid))
                    else:
                        await db.execute("INSERT INTO inventory (player_id, item_id, quantity) VALUES (?, ?, ?)", (rid, iid, qty))
                await db.commit()
                from bot.cogs.quest import update_progress
                await update_progress(db, rid, 10)
                self.clear_items()
                await interaction.edit_original_response(
                    content=f"🤝 **{self.receiver_name}** nhận {qty}× **{item_name}** từ **{self.sender_name}**!",
                    view=self)
        finally:
            await db.close()

    @discord.ui.button(emoji="❌", label="Từ Chối", style=discord.ButtonStyle.danger)
    async def deny_btn(self, interaction: discord.Interaction, button: discord.Button):
        if self.used:
            return
        self.used = True
        await interaction.response.defer()
        self.clear_items()
        await interaction.edit_original_response(
            content=f"🚫 **{self.receiver_name}** từ chối giao dịch!",
            view=self)
