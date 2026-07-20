import discord
from bot.database import get_db
from bot.data.wives import WIVES
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT


class TradeView(discord.ui.View):
    """Trade offer view with Accept/Deny buttons. Works for both wives and items."""

    def __init__(self, bot, receiver_id: str, sender_id: str, trade_type: str,
                 sender_name: str, receiver_name: str, channel_id: int, data: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.receiver_id = receiver_id
        self.sender_id = sender_id
        self.trade_type = trade_type  # "wife" or "item"
        self.sender_name = sender_name
        self.receiver_name = receiver_name
        self.channel_id = channel_id
        self.data = data  # {'wife_dbid': int} or {'item_id': int, 'quantity': int}
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
            if self.trade_type == "wife":
                cursor = await db.execute("SELECT * FROM player_wives WHERE id=? AND player_id=?",
                                          (self.data["wife_dbid"], self.sender_id))
                row = await cursor.fetchone()
                if not row:
                    await interaction.followup.send("🤷 Vợ đã biến mất!", ephemeral=True)
                    return
                w = dict(row)
                wd = WIVES.get(w["wife_id"], WIVES[1])
                await db.execute("UPDATE player_wives SET player_id=?, equipped=0 WHERE id=?",
                                  (self.receiver_id, self.data["wife_dbid"]))
                await db.commit()
                from bot.cogs.quest import update_progress
                await update_progress(db, self.receiver_id, 10)
                self.clear_items()
                await interaction.edit_original_response(
                    content=f"🤝 **{self.receiver_name}** nhận **{wd['emoji']} {wd['name']}** từ **{self.sender_name}**!",
                    view=self)

            elif self.trade_type == "item":
                iid = self.data["item_id"]
                is_equip = iid in EQUIPMENT
                item_name = EQUIPMENT[iid]["name"] if is_equip else SHOP_ITEMS[iid]["name"]
                qty = self.data["quantity"]

                if is_equip:
                    cursor = await db.execute(
                        "SELECT id FROM player_equipment WHERE player_id=? AND item_id=? AND equipped=0 LIMIT ?",
                        (self.sender_id, iid, qty))
                    rows = await cursor.fetchall()
                    if len(rows) < qty:
                        await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                        return
                    for r in rows:
                        await db.execute("UPDATE player_equipment SET player_id=?, equipped=0 WHERE id=?",
                                         (self.receiver_id, r[0]))
                else:
                    cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?",
                                               (self.sender_id, iid))
                    row = await cursor.fetchone()
                    if not row or row[0] < qty:
                        await interaction.followup.send("🤷 Hết hàng rồi!", ephemeral=True)
                        return
                    new_qty = row[0] - qty
                    if new_qty <= 0:
                        await db.execute("DELETE FROM inventory WHERE player_id=? AND item_id=?", (self.sender_id, iid))
                    else:
                        await db.execute("UPDATE inventory SET quantity=? WHERE player_id=? AND item_id=?", (new_qty, self.sender_id, iid))
                    r_cursor = await db.execute("SELECT quantity FROM inventory WHERE player_id=? AND item_id=?", (self.receiver_id, iid))
                    r_row = await r_cursor.fetchone()
                    if r_row:
                        await db.execute("UPDATE inventory SET quantity=quantity+? WHERE player_id=? AND item_id=?", (qty, self.receiver_id, iid))
                    else:
                        await db.execute("INSERT INTO inventory (player_id, item_id, quantity) VALUES (?, ?, ?)", (self.receiver_id, iid, qty))
                await db.commit()
                from bot.cogs.quest import update_progress
                await update_progress(db, self.receiver_id, 10)
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
