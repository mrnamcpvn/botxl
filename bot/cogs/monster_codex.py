import discord
from discord import app_commands
from discord.ext import commands
from bot.database import get_db
from bot.config import CODEX_DATA, CODEX_MILESTONES
from bot.data.npcs import NPC_DEFINITIONS
from bot.engine.codex import get_codex_bonuses

# NPC_DEFINITIONS dùng string key ("1", "2"...) — map về int key để khớp CODEX_DATA
_NPC_BY_INT: dict[int, dict] = {int(k): v for k, v in NPC_DEFINITIONS.items()}


class MonsterCodex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="codex", aliases=["dothu"])
    async def codex_cmd(self, ctx, npc_num: int = None):
        sid = str(ctx.author.id)
        codex_kills = await self._load_kills(sid)
        if npc_num:
            await self._show_npc_detail(ctx, npc_num, codex_kills)
        else:
            embed = self._build_codex_overview(codex_kills)
            await ctx.reply(embed=embed)

    @app_commands.command(name="codex", description="📖 Xem Đồ Thư Quái Vật — kill count & bonus")
    @app_commands.describe(npc_id="Số NPC muốn xem chi tiết (bỏ trống = xem tổng quan)")
    async def slash_codex(self, interaction: discord.Interaction, npc_id: int = None):
        sid = str(interaction.user.id)
        codex_kills = await self._load_kills(sid)
        if npc_id:
            await self._show_npc_detail(interaction, npc_id, codex_kills)
        else:
            embed = self._build_codex_overview(codex_kills)
            await interaction.response.send_message(embed=embed)

    @slash_codex.autocomplete("npc_id")
    async def codex_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        for npc_id, cd in CODEX_DATA.items():
            npc = _NPC_BY_INT.get(npc_id, {})
            name = npc.get("name", f"NPC #{npc_id}")
            label = f"#{npc_id} {name} (+{cd['bonus'].upper()})"
            if not current or current in str(npc_id) or current.lower() in name.lower():
                choices.append(app_commands.Choice(name=label[:100], value=npc_id))
        return choices[:25]

    async def _load_kills(self, sid: str) -> dict:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT npc_id, kills FROM monster_codex WHERE player_id=? ORDER BY npc_id", (sid,))
            rows = await cursor.fetchall()
        finally:
            await db.close()
        return {str(r[0]): r[1] for r in rows}

    def _build_codex_overview(self, codex_kills: dict) -> discord.Embed:
        bonuses = get_codex_bonuses(codex_kills) if codex_kills else {}
        total_kills = sum(codex_kills.values())

        lines = []
        for npc_id in sorted(CODEX_DATA.keys()):
            kills = codex_kills.get(str(npc_id), 0)
            cd = CODEX_DATA[npc_id]
            npc = _NPC_BY_INT.get(npc_id, {})
            name = npc.get("name", f"NPC #{npc_id}")
            bonus_type = cd["bonus"]

            # Tính tier đã đạt — milestones tăng dần nên dùng sum thay vì break
            tier = sum(1 for ms in CODEX_MILESTONES if kills >= ms)
            tier_str = {0: "⬛", 1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}.get(tier, "⬛")

            # Progress đến milestone tiếp theo
            next_ms = next((ms for ms in CODEX_MILESTONES if kills < ms), None)
            if next_ms:
                progress = f"{kills}/{next_ms}"
            else:
                progress = f"{kills} ✅MAX"

            lines.append(f"{tier_str} **{name}** `{progress}` (+{bonus_type.upper()})")

        bonus_lines = []
        stat_labels = {
            "coin": "💰 COIN", "xp": "⭐ XP", "hp": "❤️ HP", "dmg": "⚔️ DMG",
            "def": "🛡️ DEF", "spd": "💨 SPD", "crit": "💥 CRIT",
            "pierce": "🔱 PIERCE", "drop": "🎁 DROP", "all": "✨ ALL",
        }
        for bt, pct in sorted(bonuses.items()):
            label = stat_labels.get(bt, bt.upper())
            bonus_lines.append(f"{label} **+{pct}%**")
        bonus_text = "  ·  ".join(bonus_lines) if bonus_lines else "_Chưa có bonus nào_"

        # Chia thành 2 cột (15 NPC mỗi cột)
        half = len(lines) // 2 + len(lines) % 2
        embed = discord.Embed(
            title="📖 Đồ Thư Quái Vật",
            description=f"⚔️ Tổng kills: **{total_kills:,}**\n\n"
                        f"_Giết đủ số lượng để nhận bonus vĩnh viễn_".replace(",", "."),
            color=0x8b4513,
        )
        embed.add_field(name="Trang 1", value="\n".join(lines[:half]) or "_Trống_", inline=True)
        embed.add_field(name="Trang 2", value="\n".join(lines[half:]) or "_Trống_", inline=True)
        embed.add_field(name="📊 Tổng Bonus Hiện Tại", value=bonus_text, inline=False)
        embed.set_footer(text=f"!codex <1-30> để xem chi tiết | Milestone: {' → '.join(str(m) for m in CODEX_MILESTONES)} kills")
        return embed

    async def _show_npc_detail(self, ctx, npc_id: int, codex_kills: dict):
        cd = CODEX_DATA.get(npc_id)
        npc = _NPC_BY_INT.get(npc_id)
        if not cd or not npc:
            msg = f"❌ NPC #{npc_id} không tồn tại! Chọn từ 1-{max(CODEX_DATA.keys())}"
            if isinstance(ctx, commands.Context):
                await ctx.reply(msg)
            else:
                await ctx.response.send_message(msg, ephemeral=True)
            return

        kills = codex_kills.get(str(npc_id), 0)
        tier = sum(1 for ms in CODEX_MILESTONES if kills >= ms)
        tier_str = {0: "⬛", 1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}.get(tier, "⬛")

        stat_labels = {
            "coin": "💰 Coin", "xp": "⭐ XP", "hp": "❤️ HP", "dmg": "⚔️ DMG",
            "def": "🛡️ DEF", "spd": "💨 SPD", "crit": "💥 CRIT",
            "pierce": "🔱 PIERCE", "drop": "🎁 DROP", "all": "✨ ALL Stats",
        }
        bonus_label = stat_labels.get(cd["bonus"], cd["bonus"].upper())

        # Progress bar đến milestone tiếp theo
        next_ms = next((ms for ms in CODEX_MILESTONES if kills < ms), None)
        if next_ms:
            bar_len = 10
            filled = min(bar_len, kills * bar_len // next_ms)
            progress_bar = "🟫" * filled + "⬛" * (bar_len - filled)
            progress_str = f"`{kills}/{next_ms}` {progress_bar}"
        else:
            progress_str = f"`{kills}` — 💎 **ĐÃ ĐẠT MAX!**"

        lines = [
            f"{tier_str} **{npc['name']}** — Lv.{npc.get('level', '?')}",
            f"Bonus: **{bonus_label}**",
            f"Đã giết: {progress_str}",
            "",
            "📊 **Mốc thưởng:**",
        ]
        cumulative = 0
        for i, (ms, pct) in enumerate(zip(CODEX_MILESTONES, cd["tiers"])):
            achieved = "✅" if kills >= ms else ("🔜" if kills >= (CODEX_MILESTONES[i-1] if i > 0 else 0) else "☐")
            cumulative += pct
            lines.append(f"{achieved} **{ms:,}** kills → +{pct}% {bonus_label} _(tổng: +{cumulative}%)_".replace(",", "."))

        embed = discord.Embed(
            title=f"📖 Đồ Thư — {npc['name']}",
            description="\n".join(lines),
            color=0x8b4513,
        )
        embed.set_footer(text="!codex để xem toàn bộ đồ thư")
        if isinstance(ctx, commands.Context):
            await ctx.reply(embed=embed)
        else:
            await ctx.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(MonsterCodex(bot))
