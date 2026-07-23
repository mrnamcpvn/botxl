import discord
from discord.ext import commands
from bot.data.skills import SKILLS_DB


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    HELP_DATA = {
        "co_ban": {
            "name": "📝 Cơ Bản",
            "description": (
                "`!register` — Đăng ký tài khoản\n"
                "`!stats` — Xem chỉ số nhân vật\n"
                "`!upgrade <hp/atk/def>` — Nâng cấp chỉ số\n"
                "`!leaderboard` — Bảng xếp hạng\n"
                "`!trogiup` — Xem hướng dẫn này"
            ),
        },
        "dam_nhau": {
            "name": "⚔️ Đấm Nhau (PvP)",
            "description": (
                "`!challenge @player` — Thách đấu người khác\n"
                "Bấm ✅ để nhận lời, ❌ để từ chối\n"
                "Khi tới lượt: bấm 💥 Attack / 🔥 Special / 🛡️ Defense\n"
                "⏱ Mỗi lượt 15s, hết giờ = thua\n"
                "Từ chối/hết giờ challenge: -20🪙"
            ),
        },
        "shop": {
            "name": "🏪 Shop",
            "description": (
                "`!shop` — Xem cửa hàng\n"
                "`!buy <số>` — Mua vật phẩm\n"
                "`!use <số>` — Dùng vật phẩm\n"
                "`!equip <số>` — Mang trang bị\n"
                "`!inv` — Xem túi đồ\n"
                "`!sell <id> [số lượng]` — Bán vật phẩm"
            ),
        },
        "ky_nang": {
            "name": "🔥 Kỹ Năng",
            "description": (
                "`!skills` — Xem tất cả kỹ năng (20 skill)\n"
                "`!buyskill <số>` — Mua kỹ năng\n"
                "`!equipskill <loại> <số>` — Gán skill vào slot\n"
                "Slot: `attack` `special` `defense` `passive`\n"
                "VD: `!equipskill special 7`"
            ),
        },
        "class": {
            "name": "🎭 Class",
            "description": (
                "`!class` — Xem danh sách class\n"
                "`!class <tên>` — Đổi class (tốn 5000🪙)\n"
                "Mỗi class có perk + chỉ số riêng"
            ),
        },
        "nang_cap": {
            "name": "⚒️ Nâng Cấp",
            "description": (
                "`!enhance` — Mở giao diện cường hóa\n"
                "Dùng đá Sơ Cấp / Trung Cấp / Cao Cấp để nâng sao trang bị\n"
                "Cấp càng cao tỉ lệ thành công càng thấp\n"
                "Nâng cấp thành công có thể unlock hidden stats"
            ),
        },
        "dungeon": {
            "name": "🏰 Bí Cảnh",
            "description": (
                "`!dungeon` — Vào bí cảnh (yêu cầu Lv.7+)\n"
                "Đánh từng tầng, boss mỗi 10 tầng\n"
                "Thưởng: đá cường hóa, coin, XP, trang bị\n"
                "1 lượt/ngày, mua thêm lượt bằng coin"
            ),
        },
        "thankhi": {
            "name": "🔱 Thần Khí",
            "description": (
                "`!thankhi` — Xem thần khí\n"
                "Tăng tất cả chỉ số theo sao (max 10★)\n"
                "Kích hoạt: 100,000🪙 + Đá Thần Khí\n"
                "Đá rơi từ NPC Lv.15+, dungeon tầng 50+"
            ),
        },
        "quest": {
            "name": "📋 Nhiệm Vụ",
            "description": (
                "`!quest` — Xem nhiệm vụ hàng ngày\n"
                "Hoàn thành quest → nhận thưởng\n"
                "Làm đủ tất cả → bonus thêm!\n"
                "Reset lúc 0:00 mỗi ngày"
            ),
        },
        "arena": {
            "name": "🏟️ Đấu Trường Sinh Tử",
            "description": (
                "`/arena start` — Admin mở đấu trường\n"
                "Tự động mở lúc 8h, 10h, 14h, 16h\n"
                "Bấm ⚔️ Tham Gia để đăng ký\n"
                "Bot tự chia cặp + đánh auto\n"
                "Thưởng top 1-3: đồ, đá, coin, XP"
            ),
        },
        "world_boss": {
            "name": "🐉 Boss Thế Giới",
            "description": (
                "Tự động xuất hiện lúc 11h, 15h, 20h\n"
                "Bấm ⚔️ Tham Gia để đăng ký (5 phút)\n"
                "Mỗi người tự chọn skill đánh boss\n"
                "Boss đánh random 1 người mỗi lượt\n"
                "Chết → 15s hồi sinh → đánh tiếp\n"
                "Thưởng theo damage ranking"
            ),
        },
        "gem": {
            "name": "💎 Đá Khảm",
            "description": (
                "`!khamda` — Khảm/tháo đá vào trang bị\n"
                "`!khoda` — Xem kho đá\n"
                "`!ghepda <loại> <cấp>` — Ghép 3 đá → 1 đá cấp cao\n"
                "`!huongdanda` — Hướng dẫn chi tiết\n"
                "6 loại: Hồng Ngọc (HP), Lục Bảo (ATK), Lam Ngọc (DEF),\n"
                "Phong Tinh (SPD), Huyết Thạch (CRIT), Tử Tinh (PIERCE)\n"
                "Rơi từ NPC Lv.10+, Dungeon 20+, World Boss"
            ),
        },
        "codex": {
            "name": "📖 Đồ Thư Quái Vật",
            "description": (
                "`!codex` — Xem đồ thư toàn bộ NPC\n"
                "`!codex <số>` — Chi tiết từng NPC\n"
                "Giết NPC → tích lũy kills → unlock bonus vĩnh viễn\n"
                "4 mốc: 100 / 500 / 1K / 10K kills\n"
                "Bonus: coin, xp, dmg, hp, def, spd, crit, pierce, drop"
            ),
        },
        "quiz": {
            "name": "🎮 Quiz",
            "description": (
                "Bot tự động ra câu hỏi mỗi 10-30 phút\n"
                "Gõ đáp án vào chat để trả lời\n"
                "Đúng → nhận coin + bonus (đá, đồ, consumable)"
            ),
        },
        "trade": {
            "name": "🤝 Trade",
            "description": (
                "`!trade @player` — Gửi yêu cầu trade\n"
                "Trao đổi coin, vật phẩm, trang bị\n"
                "Cả 2 bên xác nhận → giao dịch hoàn tất"
            ),
        },
        "waifu": {
            "name": "💕 Waifu",
            "description": (
                "`!waifu` — Gacha vợ\n"
                "Vợ hỗ trợ trong battle (tấn công thêm)\n"
                "Level vợ càng cao → damage càng mạnh\n"
                "`!equipwife <id>` — Chọn vợ ra trận"
            ),
        },
        "cultivation": {
            "name": "🧘 Tu Tiên",
            "description": (
                "`!tulyen` — Bắt đầu tu luyện (tích lũy tu vi)\n"
                "`!ketthuc` — Kết thúc và nhận tu vi\n"
                "`!dotpha` — Đột phá lên bậc tiếp theo\n"
                "`!thangcanh` — Thăng cảnh giới (cần cống phẩm)\n"
                "`!dung <tên>` — Dùng cống phẩm tăng tu vi\n"
                "7 cảnh giới: Luyện Khí → Trúc Cơ → Kết Đan →\n"
                "Nguyên Anh → Hóa Thần → Đại Thừa → Độ Kiếp\n"
                "Mỗi cảnh giới +% stat + passive đặc biệt"
            ),
        },
    }

    HELP_ORDER = [
        "co_ban", "dam_nhau", "shop", "ky_nang", "class",
        "nang_cap", "dungeon", "thankhi", "quest",
        "arena", "world_boss", "gem", "codex",
        "cultivation", "quiz", "trade", "waifu",
    ]

    @commands.command(name="trogiup", aliases=["h", "help"])
    async def tro_giup(self, ctx):
        options = []
        for key in self.HELP_ORDER:
            data = self.HELP_DATA[key]
            options.append(discord.SelectOption(
                label=data["name"],
                value=key,
                description=data["description"].split("\n")[0][:100],
            ))

        view = HelpSelectView(self.HELP_DATA, options)
        embed = self._build_help_embed(self.HELP_DATA[self.HELP_ORDER[0]], self.HELP_ORDER[0])
        await ctx.reply(embed=embed, view=view)

    def _build_help_embed(self, data: dict, key: str) -> discord.Embed:
        idx = self.HELP_ORDER.index(key) + 1
        total = len(self.HELP_ORDER)
        return discord.Embed(
            title=data["name"],
            description=data["description"],
            color=0xff6600,
        ).set_footer(text=f"📖 {idx}/{total} — Chọn tab bên dưới để xem các chức năng khác")


class HelpSelectView(discord.ui.View):
    def __init__(self, help_data: dict, options: list):
        super().__init__(timeout=300)
        self.help_data = help_data
        self.add_item(HelpSelect(help_data, options))


class HelpSelect(discord.ui.Select):
    def __init__(self, help_data: dict, options: list):
        super().__init__(
            placeholder="📖 Chọn chức năng để xem hướng dẫn...",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.help_data = help_data

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        data = self.help_data[key]
        embed = discord.Embed(
            title=data["name"],
            description=data["description"],
            color=0xff6600,
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
