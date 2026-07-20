"""
StatsView — 4 tabs: Thuộc Tính / Trang Bị / Kỹ Năng / Thần Khí
Redesign: compact layout, màu sắc nhất quán, HP bar động, stat diffs rõ ràng.
"""
import json
import discord
from bot.data.skills import SKILLS_DB, RARITY_STARS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, STAR_COLORS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.data.classes import CLASSES
from bot.engine.battle import get_effective_stats, get_equipped_skill
from bot.engine.combat_power import calc_combat_power
from bot.config import HP_REGEN_RATE, HP_REGEN_INTERVAL, ENHANCE_BONUS_PER_LEVEL, MAX_ENHANCE
from bot.data.artifacts import ARTIFACTS
from bot.cogs.enhance import HIDDEN_STAT_POOLS
from bot.views.ui_helpers import hp_bar


# ── Rank tier (giống leaderboard) ────────────────────────────
_RANK_TIERS = [
    (2500, "🔱 Huyền Thoại", 0xffd700),
    (2000, "💎 Kim Cương",   0x44ccff),
    (1600, "🏆 Bạch Kim",    0xeeeeee),
    (1300, "🥇 Vàng",        0xffaa00),
    (1100, "🥈 Bạc",         0x888888),
    (0,    "🥉 Đồng",        0xcd7f32),
]

_RARITY_COLORS = {
    "common": 0x888888, "uncommon": 0x00ff88,
    "rare": 0x0088ff, "epic": 0xaa00ff, "legendary": 0xffaa00,
}

_SKILL_CAT_ICON = {"attack": "💥", "special": "🔥", "defense": "🛡️", "passive": "💎"}
_SKILL_CAT_LABEL = {"attack": "Tấn Công", "special": "Đặc Biệt", "defense": "Phòng Thủ", "passive": "Bị Động"}

ALL_EQUIP_SLOTS = ["weapon", "armor", "boots", "gloves", "belt", "ring"]


def _rank_badge(elo: int) -> tuple[str, int]:
    for thr, badge, color in _RANK_TIERS:
        if elo >= thr:
            return badge, color
    return "🥉 Đồng", 0xcd7f32


def _xp_bar(xp_cur: int, xp_need: int, length: int = 10) -> str:
    filled = min(length, xp_cur * length // max(xp_need, 1))
    return "🟦" * filled + "⬜" * (length - filled)


class StatsView(discord.ui.View):
    def __init__(self, target, pdata: dict, wives_data: list):
        super().__init__(timeout=120)
        self.target = target
        self.pdata = pdata
        self.wives_data = wives_data
        self.eff = get_effective_stats(pdata)
        self._build_tab(1)

    # ── Tab builder ───────────────────────────────────────────

    def _build_tab(self, tab: int):
        self.clear_items()
        tabs = [
            (1, "📊", "Chỉ Số",    discord.ButtonStyle.primary),
            (2, "⚒️", "Trang Bị",  discord.ButtonStyle.success),
            (3, "🔥", "Kỹ Năng",   discord.ButtonStyle.danger),
            (4, "🔱", "Thần Khí",  discord.ButtonStyle.secondary),
        ]
        for tid, emoji, label, style in tabs:
            active = (tid == tab)
            btn = discord.ui.Button(
                emoji=emoji, label=label,
                style=discord.ButtonStyle.gray if active else style,
                disabled=active,
                custom_id=f"stats_tab_{tid}",
                row=0,
            )
            btn.callback = self._make_cb(tid)
            self.add_item(btn)

        builders = {1: self._tab1, 2: self._tab2, 3: self._tab3, 4: self._tab4}
        self._current_embed = builders[tab]()

    def _make_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            if str(interaction.user.id) != str(self.target.id):
                await interaction.response.send_message("🤡 Của người khác!", ephemeral=True)
                return
            self._build_tab(tab)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    @property
    def embed(self) -> discord.Embed:
        return self._current_embed

    # ── Tab 1: Chỉ Số ─────────────────────────────────────────

    def _tab1(self) -> discord.Embed:
        from bot.engine.rewards import calc_level
        eff = self.eff
        pdata = self.pdata
        cp = calc_combat_power(pdata, self.wives_data)
        elo = pdata.get("elo", 1000)
        rank_badge, rank_color = _rank_badge(elo)

        embed = discord.Embed(color=rank_color)
        embed.set_author(
            name=f"{self.target.display_name}  —  {rank_badge}",
            icon_url=self.target.display_avatar.url,
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)

        # ── Combat Power ──
        embed.add_field(
            name="⚔️ Lực Chiến",
            value=f"**`{cp:,}`**".replace(",", "."),
            inline=True,
        )
        embed.add_field(
            name="📈 ELO",
            value=f"**`{elo}`**  {rank_badge}",
            inline=True,
        )

        # ── Level + XP ──
        level = pdata.get("level", 1)
        _, xp_cur = calc_level(pdata.get("xp", 0))
        xp_need = level * 80
        xbar = _xp_bar(xp_cur, xp_need, 10)
        coins = pdata.get("coins", 0)
        embed.add_field(
            name="📊 Cấp Độ",
            value=f"**Lv.{level}**  ·  💰 `{coins:,}`🪙\n`{xp_cur}/{xp_need}` {xbar}".replace(",", "."),
            inline=False,
        )

        # ── HP ──
        hp = pdata.get("hp", 0)
        hp_max = eff["hp_max"]
        hbar = hp_bar(hp, hp_max, 10)
        pct = int(hp / max(hp_max, 1) * 100)
        regen_note = f"\n💤 Hồi +**{HP_REGEN_RATE}HP** mỗi {HP_REGEN_INTERVAL}s" if hp < hp_max else ""
        embed.add_field(
            name="❤️ HP",
            value=f"`{hp}/{hp_max}` ({pct}%)\n{hbar}{regen_note}",
            inline=False,
        )

        # ── Offensive stats ──
        atk_min, atk_max = eff["attack_min"], eff["attack_max"]
        dmg_pct = eff.get("damage_pct", 0)
        atk_val = f"`{atk_min} — {atk_max}`"
        if dmg_pct:
            atk_val += f"  _(+{dmg_pct}% từ bị động)_"
        embed.add_field(name="⚔️ Tấn Công", value=atk_val, inline=True)
        embed.add_field(name="🛡️ Phòng Thủ", value=f"`{eff['defense']}`", inline=True)

        # ── Secondary stats ──
        sec = []
        if eff.get("spd"):     sec.append(f"💨 SPD **{eff['spd']}**")
        if eff.get("crit"):    sec.append(f"💥 CRIT **{eff['crit']}%**")
        if eff.get("pierce"):  sec.append(f"🔱 XUYÊN **{eff['pierce']}%**")
        if eff.get("dodge"):   sec.append(f"🍀 NÉ **{eff['dodge']}%**")
        if eff.get("reflect"): sec.append(f"🔄 PHẢN **{eff['reflect']}%**")
        if eff.get("regen_bonus"): sec.append(f"💚 HỒI **{eff['regen_bonus']}%/t**")
        if sec:
            embed.add_field(name="⚡ Chỉ Số Phụ", value="  ".join(sec), inline=False)

        # ── Class + perk ──
        cls = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
        perk_key = cls.get("perk", "")
        from bot.data.classes import PERK_DESCRIPTIONS
        perk_desc = PERK_DESCRIPTIONS.get(perk_key, "")
        cls_val = f"{cls['icon']} **{cls['name']}**\n_{cls['desc']}_"
        if perk_desc:
            cls_val += f"\n✨ _Perk: {perk_desc}_"
        embed.add_field(name="🎭 Class", value=cls_val, inline=False)

        # ── W/L record ──
        wins = pdata.get("wins", 0)
        losses = pdata.get("losses", 0)
        total = wins + losses
        wr = int(wins / total * 100) if total > 0 else 0
        embed.add_field(
            name="🏆 Thành Tích",
            value=f"**{wins}W** / **{losses}L**  ·  WR **{wr}%**",
            inline=True,
        )
        embed.add_field(
            name="💥 Sát Thương",
            value=f"Gây: `{pdata.get('damage_dealt', 0):,}`\nNhận: `{pdata.get('damage_taken', 0):,}`".replace(",", "."),
            inline=True,
        )

        # ── Stat points ──
        sp = pdata.get("stat_points", 0)
        if sp > 0:
            embed.add_field(
                name="⭐ Điểm Thuộc Tính",
                value=f"Có **{sp}** điểm! Dùng `/upgrade <hp/atk/def>`",
                inline=False,
            )

        # ── Buffs ──
        buff = pdata.get("buffs", {})
        bl = []
        if buff.get("attack_boost", 0) > 0:
            bl.append(f"⚡ +30% dmg — còn **{buff['attack_boost']}** trận")
        if buff.get("defense_boost", 0) > 0:
            bl.append(f"🛡️ +50% DEF — còn **{buff['defense_boost']}** trận")
        if buff.get("lucky", 0) > 0:
            bl.append(f"🎲 ×2 legendary — còn **{buff['lucky']}** trận")
        if bl:
            embed.add_field(name="🔮 Buff Đang Có", value="\n".join(bl), inline=False)

        # ── Wives ──
        if self.wives_data:
            wlines = []
            from bot.data.wives import WIVES, RARITY_STARS as W_STARS
            for w in self.wives_data:
                wd = WIVES.get(w.get("wife_id", 1), WIVES[1])
                stars = W_STARS.get(wd["rarity"], "⭐")
                status = "💍" if w.get("equipped") else "📦"
                wlines.append(f"{status} {wd['emoji']} **{wd['name']}** {stars} Lv.{w['level']}")
            embed.add_field(
                name=f"💕 Vợ ({len(self.wives_data)})",
                value="\n".join(wlines),
                inline=False,
            )

        embed.set_footer(text="Tab ⚒️ xem trang bị  ·  🔥 xem kỹ năng  ·  🔱 xem thần khí")
        return embed

    # ── Tab 2: Trang Bị ───────────────────────────────────────

    def _tab2(self) -> discord.Embed:
        pdata = self.pdata
        eq = pdata.get("equipped", {})
        equip_items = pdata.get("_equip_items", {})
        equip_enhances = pdata.get("_equip_enhances", {})
        equip_hidden = pdata.get("_equip_hidden", {})

        best_star = 0
        for slot in ALL_EQUIP_SLOTS:
            eq_id = eq.get(slot)
            item_id = equip_items.get(str(eq_id)) if eq_id else None
            if item_id and item_id in EQUIPMENT:
                best_star = max(best_star, EQUIPMENT[item_id]["star"])

        color = STAR_COLORS.get(best_star, 0x5865f2)
        embed = discord.Embed(
            title=f"⚒️ Trang Bị — {self.target.display_name}",
            color=color,
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)

        lines = []
        for slot in ALL_EQUIP_SLOTS:
            slot_label = EQ_SLOT_NAMES.get(slot, slot)
            eq_id = eq.get(slot)
            item_id = equip_items.get(str(eq_id)) if eq_id else None

            if item_id and item_id in EQUIPMENT:
                e = EQUIPMENT[item_id]
                star = e["star"]
                enhance = equip_enhances.get(str(eq_id), 0)
                mult = 1 + enhance * ENHANCE_BONUS_PER_LEVEL
                star_label = STAR_LABELS.get(star, "⭐")

                if enhance >= MAX_ENHANCE:
                    enh_str = " 🌟MAX"
                elif enhance > 0:
                    enh_str = f" ✦+{enhance}"
                else:
                    enh_str = ""

                name = e["name"]
                if star == 6:
                    name = f"✨ {name}"

                # Stats line
                stats = e["stats"]
                sp = []
                atk_min = int(stats.get("attack_min", 0) * mult)
                atk_max = int(stats.get("attack_max", 0) * mult)
                if atk_min or atk_max:
                    # Power bar based on star+enhance
                    ratio = 0.2 + (star / 6) * 0.5 + (enhance / MAX_ENHANCE) * 0.3
                    filled = max(1, min(8, int(8 * ratio)))
                    pbar = "█" * filled + "░" * (8 - filled)
                    sp.append(f"⚔️`{atk_min}~{atk_max}` {pbar}")
                for k, v in stats.items():
                    if k in ("attack_min", "attack_max"):
                        continue
                    val = int(v * mult)
                    mapping = {"defense": f"🛡️{val}", "hp": f"❤️{val}", "spd": f"💨{val}",
                               "crit": f"💥{val}%", "pierce": f"🔱{val}%",
                               "dodge": f"🍀{val}%", "reflect": f"🔄{val}%", "regen": f"💚{val}%"}
                    if k in mapping:
                        sp.append(mapping[k])

                # Hidden stats
                hidden_json = equip_hidden.get(str(eq_id), "")
                hidden_str = ""
                if hidden_json:
                    try:
                        hs = json.loads(hidden_json)
                        hparts = []
                        for hk, hv in hs.items():
                            pool = HIDDEN_STAT_POOLS.get(hk, {})
                            hparts.append(f"{pool.get('icon','')}+{hv}")
                        hidden_str = f"\n　🌟 Ẩn: {'  '.join(hparts)}"
                    except Exception:
                        pass

                lines.append(
                    f"**{slot_label}**: {star_label} **{name}**{enh_str}\n"
                    f"　└ {'  '.join(sp)}{hidden_str}"
                )
            else:
                lines.append(f"**{slot_label}**: ▫️ _Trống_")

        embed.add_field(name="🧥 Đang Mặc", value="\n".join(lines) or "_(chưa có gì)_", inline=False)

        set_bonus = pdata.get("_set_bonus")
        if set_bonus:
            from bot.data.equipment import SET_BONUSES as SB
            for star, sb in SB.items():
                if sb == set_bonus:
                    parts = []
                    if sb.get("hp_pct"): parts.append(f"❤️ +{sb['hp_pct']}% HP")
                    if sb.get("atk_pct"): parts.append(f"⚔️ +{sb['atk_pct']}% ATK")
                    if sb.get("def_pct"): parts.append(f"🛡️ +{sb['def_pct']}% DEF")
                    if sb.get("crit"): parts.append(f"💥 +{sb['crit']}% Crit")
                    if sb.get("dodge"): parts.append(f"🍀 +{sb['dodge']}% Dodge")
                    embed.add_field(
                        name=f"🌟 SET {sb['name']} ★{star} KÍCH HOẠT!",
                        value=" · ".join(parts),
                        inline=False)
                    break

        embed.add_field(
            name="💡 Lệnh",
            value="`/equip <id>` mặc  ·  `/unequip <slot>` tháo  ·  `/cuonghoa <id>` cường hóa",
            inline=False,
        )
        if best_star > 0:
            embed.set_footer(text=f"⭐ Trang bị cao nhất: {'★' * best_star}  ·  Tối đa 6 sao")
        return embed

    # ── Tab 3: Kỹ Năng ────────────────────────────────────────

    def _tab3(self) -> discord.Embed:
        pdata = self.pdata
        embed = discord.Embed(
            title=f"🔥 Kỹ Năng — {self.target.display_name}",
            color=0xff6600,
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)

        for cat in ["attack", "special", "defense", "passive"]:
            sk = get_equipped_skill(pdata, cat)
            stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
            icon = _SKILL_CAT_ICON[cat]
            label = _SKILL_CAT_LABEL[cat]
            rarity_color_hex = _RARITY_COLORS.get(sk.get("rarity", "common"), 0x888888)

            if cat == "passive":
                val = (
                    f"{sk['icon']} **{sk['name']}** {stars}\n"
                    f"_{sk.get('desc', '')}_\n"
                    f"💎 Luôn hoạt động"
                )
            else:
                cd = pdata.get(f"{cat}_cd", 0)
                cd_str = "✅ **Sẵn sàng**" if cd <= 0 else f"⏳ Hồi chiêu còn **{cd}** lượt"
                val = (
                    f"{sk['icon']} **{sk['name']}** {stars}\n"
                    f"_{sk.get('desc', '')}_\n"
                    f"{cd_str}"
                )

            embed.add_field(name=f"{icon} {label}", value=val, inline=False)

        embed.add_field(
            name="💡 Lệnh",
            value="`/skills` xem kho  ·  `/equipskill <loại> <id>` gán  ·  `/buyskill <id>` mua",
            inline=False,
        )
        embed.set_footer(text="4/4 slot đang dùng")
        return embed

    # ── Tab 4: Thần Khí ───────────────────────────────────────

    def _tab4(self) -> discord.Embed:
        pdata = self.pdata
        star = pdata.get("_artifact_star", 0)
        stones = pdata.get("_artifact_stones", 0)
        a = ARTIFACTS.get(star, ARTIFACTS[0])

        embed = discord.Embed(title="🔱 Thần Khí", color=a["color"])
        embed.set_thumbnail(url=self.target.display_avatar.url)

        if star == 0:
            embed.description = (
                "🔒 **Chưa kích hoạt**\n\n"
                "Thần Khí tăng toàn bộ chỉ số của bạn.\n"
                "💰 Chi phí: **100,000 🪙**\n"
                "📜 Dùng `/thankhi` để mở khoá"
            )
        else:
            from bot.config import ARTIFACT_MAX_STAR, ARTIFACT_UPGRADE_COSTS
            boost = star * 15
            star_filled = "⭐" * star
            star_empty = "✩" * (ARTIFACT_MAX_STAR - star)

            embed.description = (
                f"# {a.get('emoji', '')} {a['name']}\n"
                f"### {star_filled}{star_empty}\n\n"
                f"*{a['desc']}*\n\n"
                f"⚡ **+{boost}%** toàn bộ chỉ số"
            )

            if stones > 0:
                embed.add_field(name="💎 Đá Thần Khí", value=f"**{stones}** viên", inline=True)

            next_star = star + 1
            if next_star <= ARTIFACT_MAX_STAR:
                cost = ARTIFACT_UPGRADE_COSTS.get(next_star, (0, 0))
                embed.add_field(
                    name=f"⬆️ Nâng lên ★{next_star}",
                    value=f"💎 **{cost[0]}** đá  ·  💰 **{cost[1]:,}**🪙".replace(",", "."),
                    inline=True,
                )
            else:
                embed.add_field(name="🌟 Trạng Thái", value="**ĐẠT CẤP ĐỘ TỐI ĐA!**", inline=True)

            if a.get("gif_url"):
                embed.set_image(url=a["gif_url"])

        embed.set_footer(text="Dùng /thankhi để quản lý Thần Khí")
        return embed
