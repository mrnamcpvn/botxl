"""
Shared UI helpers dùng chung cho battle, dungeon, NPC embeds.
"""
import discord
from bot.engine.battle import get_effective_stats, get_equipped_skill


# ── HP bar ───────────────────────────────────────────────────
def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """Trả về thanh HP có màu theo % còn lại."""
    if maximum <= 0:
        return "⬛" * length
    pct = current / maximum
    filled = max(0, min(length, round(pct * length)))
    if pct > 0.6:
        fill_char, empty_char = "🟩", "⬜"
    elif pct > 0.3:
        fill_char, empty_char = "🟨", "⬜"
    else:
        fill_char, empty_char = "🟥", "⬜"
    return fill_char * filled + empty_char * (length - filled)


def hp_text(current: int, maximum: int) -> str:
    """Ví dụ: `240/500` 🟩🟩🟩🟨⬜⬜⬜⬜⬜⬜"""
    bar = hp_bar(current, maximum)
    pct = int(current / max(maximum, 1) * 100)
    return f"`{current}/{maximum}` ({pct}%)\n{bar}"


# ── Skill cooldown summary ────────────────────────────────────
def skill_cd_row(pdata: dict, name: str) -> str:
    """
    Ví dụ: ⚔️ Hà Nội Chém ✅  🔥 Đốt Nhà ⏳3  🛡️ Khiên ✅
    """
    parts = []
    for cat, icon in [("attack", ""), ("special", ""), ("defense", "")]:
        sk = get_equipped_skill(pdata, cat)
        cd = pdata.get(f"{cat}_cd", 0)
        sk_icon = sk.get("icon", "❓")
        if cd <= 0:
            parts.append(f"{sk_icon}✅")
        else:
            parts.append(f"{sk_icon}⏳{cd}")
    return f"**{name}**: {' '.join(parts)}"


# ── Compact player status ─────────────────────────────────────
def player_status_field(pdata: dict, member_name: str, turn: bool = False) -> tuple[str, str]:
    """
    Returns (name, value) cho embed.add_field.
    """
    eff = get_effective_stats(pdata)
    hp_cur = pdata.get("hp", 0)
    hp_max = eff["hp_max"]
    bar = hp_bar(hp_cur, hp_max, 8)
    pct = int(hp_cur / max(hp_max, 1) * 100)

    # skill CDs
    cd_parts = []
    for cat in ["attack", "special", "defense"]:
        sk = get_equipped_skill(pdata, cat)
        cd = pdata.get(f"{cat}_cd", 0)
        cd_parts.append(f"{sk.get('icon','?')}{'✅' if cd <= 0 else f'⏳{cd}'}")

    turn_marker = " 👈" if turn else ""
    name = f"{'▶ ' if turn else ''}**{member_name}**{turn_marker}"
    value = (
        f"❤️ `{hp_cur}/{hp_max}` ({pct}%)\n"
        f"{bar}\n"
        f"{' '.join(cd_parts)}"
    )
    return name, value


# ── Divider ───────────────────────────────────────────────────
DIVIDER = "─" * 20


# ── Battle log formatter ──────────────────────────────────────
def format_battle_log(lines: list[str], max_chars: int = 3800) -> str:
    """Join log lines, cắt nếu quá dài."""
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n_..._(còn nữa)"
    return text


# ── Win/Loss result embed ─────────────────────────────────────
def result_embed(
    winner_name: str,
    loser_name: str,
    coins: int,
    xp: int,
    elo_change: int | None,
    drop_text: str | None,
    wife_lines: list[str],
    is_timeout: bool = False,
    extra_lines: list[str] | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title="🏆 KẾT QUẢ TRẬN ĐẤU",
        color=0xffd700,
    )

    # Winner section
    winner_val = f"🥇 **{winner_name}** CHIẾN THẮNG!"
    if coins:
        winner_val += f"\n💰 +**{coins}** 🪙"
    if xp:
        winner_val += f"  ✨ +**{xp}** XP"
    if elo_change is not None and elo_change != 0:
        sign = "+" if elo_change > 0 else ""
        winner_val += f"\n📈 ELO: {sign}{elo_change}"
    embed.add_field(name="✅ Thắng", value=winner_val, inline=False)

    # Loser section
    loser_cause = "⏰ Hết giờ!" if is_timeout else "💀 Thất bại!"
    embed.add_field(name="❌ Thua", value=f"**{loser_name}** — {loser_cause}", inline=False)

    # Drop
    if drop_text:
        embed.add_field(name="🎁 Chiến Lợi Phẩm", value=drop_text, inline=False)

    # Wife XP
    if wife_lines:
        embed.add_field(name="💕 Vợ Tăng Kinh Nghiệm", value="\n".join(wife_lines), inline=False)

    # Extra (artifact stone, etc.)
    if extra_lines:
        embed.add_field(name="🎉 Thêm", value="\n".join(extra_lines), inline=False)

    return embed


# ── NPC difficulty badge ──────────────────────────────────────
def npc_difficulty_badge(npc_level: int) -> str:
    if npc_level <= 5:
        return "🟢 Dễ"
    elif npc_level <= 12:
        return "🟡 Bình Thường"
    elif npc_level <= 20:
        return "🟠 Khó"
    elif npc_level <= 30:
        return "🔴 Rất Khó"
    else:
        return "💀 Cực Khó"


# ── Dungeon floor color ───────────────────────────────────────
def dungeon_floor_color(floor: int) -> int:
    if floor <= 20:
        return 0x44aaff   # xanh dương nhạt
    elif floor <= 50:
        return 0xaa44ff   # tím
    elif floor <= 80:
        return 0xff6600   # cam
    else:
        return 0xff0000   # đỏ boss


def is_boss_floor(floor: int) -> bool:
    return floor % 10 == 0


def dungeon_progress_bar(floor: int, total: int = 100, length: int = 10) -> str:
    filled = max(0, min(length, round(floor / total * length)))
    return "🟪" * filled + "⬛" * (length - filled)
