import discord
from bot.database import get_db
from bot.data.classes import CLASSES

# Rank tier badge dựa trên ELO / CP
_RANK_TIERS = [
    (2500, "🔱 Huyền Thoại", 0xffd700),
    (2000, "💎 Kim Cương",   0x44ccff),
    (1600, "🏆 Bạch Kim",    0xeeeeee),
    (1300, "🥇 Vàng",        0xffaa00),
    (1100, "🥈 Bạc",         0x888888),
    (0,    "🥉 Đồng",        0xcd7f32),
]

_MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

_TABS = [
    # (emoji, label, style,  sort_col,        title,            value_fn)
    ("⚔️", "Lực Chiến", discord.ButtonStyle.danger,   "combat_power", "⚔️ BXH Lực Chiến",  lambda v: f"⚔️ **{v:,}**".replace(",", ".")),
    ("📊", "Level",     discord.ButtonStyle.primary,  "level",        "📊 BXH Level",       lambda v: f"Lv.**{v}**"),
    ("🏆", "Thắng",     discord.ButtonStyle.success,  "wins",         "🏆 BXH Chiến Thắng", lambda v: f"**{v}** trận thắng"),
    ("💰", "Coin",      discord.ButtonStyle.secondary,"coins",        "💰 BXH Xu",          lambda v: f"💰 **{v:,}**🪙".replace(",", ".")),
    ("📈", "ELO",       discord.ButtonStyle.primary,  "elo",          "📈 BXH ELO",         lambda v: f"ELO **{v}**"),
    ("🎁", "Weekly",    discord.ButtonStyle.success,  "wins",         "🎁 BXH Tuần Này",    lambda v: f"**{v}** điểm"),
]

WEEKLY_PRIZES = {
    1:  {"coins": 50000, "stone_advanced": 15, "desc": "🏆 Giải Nhất"},
    2:  {"coins": 30000, "stone_advanced": 10, "desc": "🥈 Giải Nhì"},
    3:  {"coins": 20000, "stone_advanced": 5,  "desc": "🥉 Giải Ba"},
    4:  {"coins": 10000, "stone_medium": 10,   "desc": "4️⃣ Giải Tư"},
    5:  {"coins": 5000,  "stone_medium": 5,    "desc": "5️⃣ Giải Năm"},
    6:  {"coins": 3000,  "stone_basic": 10,    "desc": "6️⃣ Giải Sáu"},
    7:  {"coins": 2000,  "stone_basic": 5,     "desc": "7️⃣ Giải Bảy"},
    8:  {"coins": 1000,  "stone_basic": 3,     "desc": "8️⃣ Giải Tám"},
    9:  {"coins": 500,   "stone_basic": 2,     "desc": "9️⃣ Giải Chín"},
    10: {"coins": 500,   "stone_basic": 1,     "desc": "🔟 Giải Mười"},
}


def _rank_badge(elo: int) -> str:
    for threshold, badge, _ in _RANK_TIERS:
        if elo >= threshold:
            return badge
    return "🥉 Đồng"


def _rank_color(elo: int) -> int:
    for threshold, _, color in _RANK_TIERS:
        if elo >= threshold:
            return color
    return 0xcd7f32


def _make_leaderboard_embed(players: list, title: str, sort_col: str, value_fn) -> discord.Embed:
    if not players:
        return discord.Embed(
            title=title, description="📭 Chưa có ai đăng ký!",
            color=0xffd700
        )

    best_elo = players[0].get("elo", 1000)
    color = _rank_color(best_elo)
    embed = discord.Embed(title=title, color=color)

    lines = []
    for i, pd in enumerate(players):
        medal = _MEDALS[i] if i < len(_MEDALS) else f"`#{i+1}`"
        name = pd.get("name", "Unknown")
        cls = CLASSES.get(pd.get("class_id", "banxabong"), CLASSES["banxabong"])
        val = pd.get(sort_col, 0)
        val_str = value_fn(val)

        # Win rate
        total = pd["wins"] + pd["losses"]
        wr = int(pd["wins"] / total * 100) if total > 0 else 0

        # Rank badge chỉ hiện ở tab ELO và Lực Chiến
        rank = _rank_badge(pd.get("elo", 1000))

        lines.append(
            f"{medal} {cls['icon']} **{name}**  {rank}\n"
            f"　{val_str}  ·  {pd['wins']}W/{pd['losses']}L  ·  WR {wr}%"
        )

    embed.description = "\n\n".join(lines)
    embed.set_footer(text=f"Top {len(players)} người chơi")
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, initial_players: list, initial_tab: int = 1):
        super().__init__(timeout=120)
        self._current_tab = initial_tab
        self._build(initial_tab, initial_players)

    def _build(self, tab: int, players: list):
        self.clear_items()
        for i, (emoji, label, style, sort_col, title, val_fn) in enumerate(_TABS):
            active = (i + 1 == tab)
            btn = discord.ui.Button(
                emoji=emoji, label=label,
                style=discord.ButtonStyle.gray if active else style,
                disabled=active,
                custom_id=f"lb_tab_{i}",
                row=i // 3,
            )
            btn.callback = self._make_cb(i + 1)
            self.add_item(btn)

        _, _, _, sort_col, title, val_fn = _TABS[tab - 1]
        self._current_embed = _make_leaderboard_embed(players, title, sort_col, val_fn)

    def _make_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            self._current_tab = tab
            _, _, _, sort_col, title, val_fn = _TABS[tab - 1]
            players = await self._fetch(sort_col)
            self._build(tab, players)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    async def _fetch(self, sort_col: str) -> list:
        db = await get_db()
        try:
            cursor = await db.execute(
                f"SELECT * FROM players ORDER BY {sort_col} DESC LIMIT 10"
            )
            return [dict(r) for r in await cursor.fetchall()]
        finally:
            await db.close()

    @property
    def embed(self) -> discord.Embed:
        return self._current_embed
