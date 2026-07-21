import discord
from bot.database import get_db


class ArenaJoinView(discord.ui.View):
    def __init__(self, tournament_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.tournament_id = tournament_id
        self.channel_id = channel_id
        self.participants: dict[str, str] = {}

    @discord.ui.button(emoji="⚔️", label="Tham Gia", style=discord.ButtonStyle.success, custom_id="arena:join")
    async def join_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)

        from bot.config import ARENA_MAX_PLAYERS
        if len(self.participants) >= ARENA_MAX_PLAYERS:
            await interaction.response.send_message(f"🚫 Đã đủ {ARENA_MAX_PLAYERS} người rồi!", ephemeral=True)
            return

        if sid in self.participants:
            await interaction.response.send_message("🤷 Mày đã đăng ký rồi!", ephemeral=True)
            return

        db = await get_db()
        try:
            prow = await (await db.execute("SELECT id, name, combat_power FROM players WHERE id=?", (sid,))).fetchone()
            if not prow:
                await interaction.response.send_message("❌ Đăng ký trước đã: `!register`", ephemeral=True)
                return
            name = prow["name"] or interaction.user.display_name
            cp = prow["combat_power"] or 0

            await db.execute(
                "INSERT OR IGNORE INTO arena_participants (tournament_id, player_id, cp_at_entry) VALUES (?, ?, ?)",
                (self.tournament_id, sid, cp))
            await db.commit()
        finally:
            await db.close()

        self.participants[sid] = name
        await interaction.response.send_message(f"✅ Đã đăng ký! ({len(self.participants)} người)", ephemeral=True)

    @discord.ui.button(emoji="❌", label="Rời", style=discord.ButtonStyle.danger, custom_id="arena:leave")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.Button):
        sid = str(interaction.user.id)
        if sid not in self.participants:
            await interaction.response.send_message("🤷 Mày chưa đăng ký mà!", ephemeral=True)
            return

        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM arena_participants WHERE tournament_id=? AND player_id=?",
                (self.tournament_id, sid))
            await db.commit()
        finally:
            await db.close()

        del self.participants[sid]
        await interaction.response.send_message("👋 Đã rời khỏi đấu trường.", ephemeral=True)
