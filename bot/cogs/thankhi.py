import discord
from discord import app_commands
from discord.ext import commands
from bot.database import get_db
from bot.data.artifacts import ARTIFACTS
from bot.config import ARTIFACT_UNLOCK_COST, ARTIFACT_MAX_STAR, ARTIFACT_UPGRADE_COSTS


def thankhi_embed(star: int, display_name: str, stones: int = 0) -> discord.Embed:
    """Embed hiển thị Thần Khí — đẹp hơn với star rating và preview nâng cấp."""
    a = ARTIFACTS.get(star, ARTIFACTS[0])

    # Star display
    star_filled = "⭐" * star
    star_empty = "✩" * (ARTIFACT_MAX_STAR - star)

    if star == 0:
        embed = discord.Embed(
            title="🔒 Thần Khí — Chưa Kích Hoạt",
            description=(
                "Thần Khí là vũ khí tối thượng tăng **toàn bộ chỉ số**.\n\n"
                f"💰 Chi phí kích hoạt: **{ARTIFACT_UNLOCK_COST:,} 🪙**\n"
                "🪨 Đá thần khí kiếm từ NPC Lv.15+ và Dungeon tầng 50+"
            ),
            color=0x888888
        )
        embed.set_footer(text="Dùng nút bên dưới để kích hoạt")
        return embed

    boost = star * 15
    next_star = star + 1
    can_upgrade = next_star <= ARTIFACT_MAX_STAR
    next_cost = ARTIFACT_UPGRADE_COSTS.get(next_star, (0, 0)) if can_upgrade else None

    desc = (
        f"# {a.get('emoji', '')} {a['name']}\n"
        f"### {star_filled}{star_empty}\n"
        f"*{a['desc']}*\n\n"
        f"⚡ **+{boost}%** tất cả chỉ số"
    )

    if stones > 0:
        desc += f"\n💎 Đá thần khí: **{stones}** viên"

    if can_upgrade and next_cost:
        stone_need, coin_need = next_cost
        desc += (
            f"\n\n{'─' * 22}\n"
            f"**Nâng lên ★{next_star}:**\n"
            f"💎 {stone_need} đá  ·  💰 {coin_need:,} 🪙"
        )
    elif star >= ARTIFACT_MAX_STAR:
        desc += f"\n\n🌟 **ĐÃ ĐẠT CẤP ĐỘ TỐI ĐA!**"

    embed = discord.Embed(title="🔱 Thần Khí", description=desc.replace(",", "."), color=a["color"])

    if a.get("gif_url"):
        embed.set_image(url=a["gif_url"])

    return embed


class ThankhiView(discord.ui.View):
    def __init__(self, star: int, can_upgrade: bool):
        super().__init__(timeout=120)
        self.star = star
        self.can_upgrade = can_upgrade

        prev_btn = discord.ui.Button(emoji="◀", style=discord.ButtonStyle.secondary,
            custom_id="thk_prev", row=0, disabled=(star <= 0))
        prev_btn.callback = self._make_nav(-1)
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(emoji="▶", style=discord.ButtonStyle.secondary,
            custom_id="thk_next", row=0, disabled=(star >= 10))
        next_btn.callback = self._make_nav(1)
        self.add_item(next_btn)

        if star == 0:
            unlock_btn = discord.ui.Button(emoji="🔓", label="Kích Hoạt (100,000🪙)",
                style=discord.ButtonStyle.success, custom_id="thk_unlock", row=1)
            unlock_btn.callback = self._unlock_callback
            self.add_item(unlock_btn)
        elif can_upgrade and star < ARTIFACT_MAX_STAR:
            upgrade_btn = discord.ui.Button(emoji="⬆", label=f"Nâng Cấp → ★{star+1}",
                style=discord.ButtonStyle.danger, custom_id="thk_upgrade", row=1)
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
                await interaction.followup.send(f"😅 Cần {ARTIFACT_UNLOCK_COST:,}🪙!".replace(",", "."), ephemeral=True)
                return
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (ARTIFACT_UNLOCK_COST, sid))
            await db.execute("INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) VALUES (?, 1, 0)", (sid,))
            await db.commit()
            embed = thankhi_embed(1, interaction.user.display_name, stones=0)
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
                await interaction.followup.send(f"😅 Cần **{stone_need}** đá, có **{stones}**!", ephemeral=True)
                return
            pc = await db.execute("SELECT coins FROM players WHERE id=?", (sid,))
            pr = await pc.fetchone()
            if not pr or pr[0] < coin_need:
                await interaction.followup.send(f"😅 Cần **{coin_need:,}**🪙!".replace(",", "."), ephemeral=True)
                return
            await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (coin_need, sid))
            await db.execute("UPDATE player_artifact SET star=star+1, stone_count=stone_count-? WHERE player_id=?", (stone_need, sid))
            await db.commit()
            new_star = current + 1
            # Lấy stones mới sau khi trừ
            new_stones = stones - stone_need
            embed = thankhi_embed(new_star, interaction.user.display_name, stones=new_stones)
            can_upgrade = new_star < ARTIFACT_MAX_STAR
            view = ThankhiView(new_star, can_upgrade)
            await interaction.edit_original_response(embed=embed, view=view)
        finally:
            await db.close()


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
            embed = thankhi_embed(star, display_name, stones=stones)
            view = ThankhiView(star, can_upgrade)
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(ThankhiCog(bot))
