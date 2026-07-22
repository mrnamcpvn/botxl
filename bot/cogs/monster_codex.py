import discord
from discord.ext import commands
from bot.database import get_db
from bot.config import CODEX_DATA, CODEX_MILESTONES
from bot.data.npcs import NPCS
from bot.engine.codex import get_codex_bonuses


class MonsterCodex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="codex", aliases=["dothu"])
    async def codex(self, ctx, npc_num: int = None):
        sid = str(ctx.author.id)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT npc_id, kills FROM monster_codex WHERE player_id=? ORDER BY npc_id", (sid,))
            rows = await cursor.fetchall()
        finally:
            await db.close()

        codex_kills = {str(r[0]): r[1] for r in rows}

        if npc_num:
            await self._show_npc_detail(ctx, npc_num, codex_kills)
            return

        embed = self._build_codex_overview(codex_kills)
        await ctx.reply(embed=embed)

    def _build_codex_overview(self, codex_kills: dict) -> discord.Embed:
        bonuses = get_codex_bonuses(codex_kills) if codex_kills else {}
        total_kills = sum(codex_kills.values())

        lines = []
        for npc_id in sorted(CODEX_DATA.keys()):
            kills = codex_kills.get(str(npc_id), 0)
            cd = CODEX_DATA[npc_id]
            npc = NPCS.get(npc_id, {})
            name = npc.get("name", f"NPC #{npc_id}")
            bonus_type = cd["bonus"]

            tier = 0
            for i, ms in enumerate(CODEX_MILESTONES):
                if kills >= ms:
                    tier = i + 1
                else:
                    break
            tier_str = {0: "⬛", 1: "🥉", 2: "🥈", 3: "🥇", 4: "💎"}.get(tier, "⬛")
            lines.append(f"{tier_str} **{name}**: {kills}/{CODEX_MILESTONES[-1]} ({bonus_type.upper()})")

        bonus_lines = []
        for bt, pct in sorted(bonuses.items()):
            bonus_lines.append(f"{bt.upper()}: +{pct}%")
        bonus_text = " · ".join(bonus_lines) if bonus_lines else "_Chưa có bonus nào_"

        embed = discord.Embed(
            title="📖 Đồ Thư Quái Vật",
            description=f"Tổng kills: **{total_kills}**\n\n" + "\n".join(lines[:15]),
            color=0x8b4513,
        )
        embed.add_field(name="📊 Tổng Bonus", value=bonus_text, inline=False)
        embed.set_footer(text="!codex <số> để xem chi tiết từng NPC")
        return embed

    async def _show_npc_detail(self, ctx, npc_id: int, codex_kills: dict):
        cd = CODEX_DATA.get(npc_id)
        npc = NPCS.get(npc_id)
        if not cd or not npc:
            await ctx.reply("❌ NPC không tồn tại!")
            return

        kills = codex_kills.get(str(npc_id), 0)
        lines = [
            f"**{npc['name']}** — Lv.{npc.get('level', '?')}",
            f"Bonus: **{cd['bonus'].upper()}**",
            f"Đã giết: **{kills}**",
            "",
            "📊 Mốc thưởng:",
        ]
        for i, (ms, pct) in enumerate(zip(CODEX_MILESTONES, cd["tiers"])):
            achieved = "✅" if kills >= ms else "☐"
            lines.append(f"{achieved} {ms} kills → +{pct}% {cd['bonus'].upper()}")

        embed = discord.Embed(
            title=f"📖 Đồ Thư — {npc['name']}",
            description="\n".join(lines),
            color=0x8b4513,
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(MonsterCodex(bot))
