import discord
from bot.database import get_db
from bot.data.classes import CLASSES


class LeaderboardView(discord.ui.View):
    def __init__(self, initial_players: list, initial_tab: int = 1):
        super().__init__(timeout=120)
        self._tabs = [
            ("⚔️", "Lực Chiến", discord.ButtonStyle.danger, "combat_power", "⚔️ Lực Chiến", "LC"),
            ("📊", "Level", discord.ButtonStyle.primary, "level", "📊 Level", "Level"),
            ("💰", "Coin", discord.ButtonStyle.success, "coins", "💰 Coin", "Coin"),
        ]
        self._current_tab = initial_tab
        self._build_tab(initial_tab, initial_players)

    def _make_embed(self, players: list, title_label: str, sort_col: str, val_label: str) -> discord.Embed:
        embed = discord.Embed(title=f"🏆 BẢNG XẾP HẠNG — {title_label}", color=0xffd700)
        if not players:
            embed.description = "📭 Chưa ai đăng ký!"
            return embed
        medals = ["🥇", "🥈", "🥉"]
        for i, pd in enumerate(players):
            n = pd.get("name", "Unknown")
            m = medals[i] if i < 3 else f"#{i + 1}"
            val = pd.get(sort_col, 0)
            if sort_col == "coins":
                val_str = f"{val:,}🪙".replace(",", ".")
            elif sort_col == "combat_power":
                val_str = f"⚔️{val:,}".replace(",", ".")
            else:
                val_str = f"Lv.{val}"
            wr = pd["wins"] / (pd["wins"] + pd["losses"]) * 100 if (pd["wins"] + pd["losses"]) > 0 else 0
            cls = CLASSES.get(pd.get("class_id", "banxabong"), CLASSES["banxabong"])
            embed.add_field(name=f"{m} {cls['icon']} {n}",
                            value=f"{val_label}:`{val_str}` 🏆`{pd['wins']}W/{pd['losses']}L` WR{wr:.0f}%",
                            inline=False)
        return embed

    def _build_tab(self, tab: int, players: list):
        self.clear_items()
        for i, (emoji, label, style, _, _, _) in enumerate(self._tabs):
            disabled = (i + 1 == tab)
            btn = discord.ui.Button(emoji=emoji, label=label, style=style if not disabled else discord.ButtonStyle.gray, disabled=disabled, custom_id=f"lb_tab_{i}")
            btn.callback = self._make_tab_cb(i + 1)
            self.add_item(btn)
        _, _, _, sort_col, title_label, val_label = self._tabs[tab - 1]
        self._current_embed = self._make_embed(players, title_label, sort_col, val_label)

    async def _fetch_players(self, sort_col: str) -> list:
        db = await get_db()
        try:
            cursor = await db.execute(f"SELECT * FROM players ORDER BY {sort_col} DESC LIMIT 10")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    def _make_tab_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            self._current_tab = tab
            _, _, _, sort_col, title_label, val_label = self._tabs[tab - 1]
            players = await self._fetch_players(sort_col)
            self._build_tab(tab, players)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    @property
    def embed(self):
        return self._current_embed
