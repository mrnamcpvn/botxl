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
