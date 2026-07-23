import discord
from discord import app_commands
from discord.ext import commands
from bot.database import get_db
from bot.data.shop_items import SHOP_ITEMS
from bot.data.equipment import EQUIPMENT
from bot.views.trade_view import TradeView
from bot.config import GEM_TYPES, CULTIVATION_ITEM_NAMES


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="trade", aliases=["doi", "trao"])
    async def trade_cmd(self, ctx, member: discord.Member = None, item_id: str = None, quantity: str = "1"):
        await self._trade_item(ctx, str(ctx.author.id), member, item_id, quantity,
                                ctx.author.display_name, "!")

    @app_commands.command(name="trade", description="🤝 Giao dịch vật phẩm")
    @app_commands.describe(member="Người nhận", item_id="ID vật phẩm / gem (vd: hp:3) / cống phẩm (vd: linh_thao)", quantity="Số lượng (mặc định 1)")
    async def slash_trade(self, interaction: discord.Interaction, member: discord.Member,
                          item_id: str, quantity: str = "1"):
        await self._trade_item(interaction, str(interaction.user.id), member, item_id, quantity,
                                interaction.user.display_name, "/")

    async def _trade_item(self, ctx_or_int, sid: str, member, item_id: str, quantity: str,
                           sender_name: str, prefix: str):
        if not member or not item_id:
            msg = f"❌ `{prefix}trade @player <item_id> [số_lượng]`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        if str(member.id) == sid:
            msg = "🤡 Tự tặng mình?"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        try:
            qty = max(1, int(quantity))
        except:
            qty = 1

        # Xác định loại item
        is_cult = item_id in CULTIVATION_ITEM_NAMES
        is_gem = ":" in item_id and item_id.split(":")[0] in GEM_TYPES
        is_numeric = False
        try:
            int(item_id)
            is_numeric = True
        except:
            pass

        iid = None
        if is_numeric:
            iid = int(item_id)

        if not is_cult and not is_gem and (iid is None or (iid not in SHOP_ITEMS and iid not in EQUIPMENT)):
            msg = f"❌ Không có vật phẩm `{item_id}`! Xem `{prefix}shop` hoặc `/equipment`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        if is_cult:
            item_name = CULTIVATION_ITEM_NAMES[item_id]
            trade_type = "cult"
        elif is_gem:
            parts = item_id.split(":")
            gt, gl = parts[0], int(parts[1])
            gem_info = GEM_TYPES.get(gt, {})
            item_name = f"{gem_info.get('name', gt)} C{gl}"
            trade_type = "gem"
        elif iid in EQUIPMENT:
            item_name = EQUIPMENT[iid]["name"]
            trade_type = "item"
        else:
            item_name = SHOP_ITEMS[iid]["name"]
            trade_type = "item"

        rid = str(member.id)

        db = await get_db()
        try:
            recv_cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (rid,))
            if not await recv_cursor.fetchone():
                msg = f"🤷 {member.display_name} chưa đăng ký!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            # Kiểm tra số lượng sender có
            if trade_type == "cult":
                inv_cursor = await db.execute(
                    "SELECT quantity FROM cultivation_items WHERE player_id=? AND item_id=?",
                    (sid, item_id))
            elif trade_type == "gem":
                parts = item_id.split(":")
                gt, gl = parts[0], int(parts[1])
                inv_cursor = await db.execute(
                    "SELECT quantity FROM player_gems WHERE player_id=? AND gem_type=? AND gem_level=?",
                    (sid, gt, gl))
            elif iid in EQUIPMENT:
                inv_cursor = await db.execute(
                    "SELECT COUNT(*) FROM player_equipment WHERE player_id=? AND item_id=?",
                    (sid, iid))
            else:
                inv_cursor = await db.execute(
                    "SELECT quantity FROM inventory WHERE player_id=? AND item_id=?",
                    (sid, iid))
            inv_row = await inv_cursor.fetchone()
            if not inv_row or inv_row[0] < qty:
                msg = f"😅 Không đủ! Có {inv_row[0] if inv_row else 0} cái."
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            ch_id = ctx_or_int.channel.id if hasattr(ctx_or_int, 'channel') else ctx_or_int.channel_id
            embed = discord.Embed(
                title="🤝 GIAO DỊCH VẬT PHẨM",
                color=0x00aaff,
                description=(
                    f"**{sender_name}** muốn tặng cho **{member.display_name}**:\n\n"
                    f"### {item_name} ×{qty}\n"
                    f"<@{member.id}> bấm ✅ Nhận hoặc ❌ Từ Chối! ⏰ 60s"
                )
            )
            trade_data = {"trade_type": trade_type}
            if trade_type == "cult":
                trade_data["item_id"] = item_id
            elif trade_type == "gem":
                trade_data["gem_type"] = gt
                trade_data["gem_level"] = gl
            else:
                trade_data["item_id"] = iid
            trade_data["quantity"] = qty

            view = TradeView(self.bot, rid, sid, sender_name, member.display_name,
                              ch_id, trade_data)
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.send(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
