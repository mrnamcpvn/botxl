import discord
from bot.data.skills import SKILLS_DB, RARITY_STARS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.data.classes import CLASSES
from bot.engine.battle import get_effective_stats, get_equipped_skill
from bot.engine.combat_power import calc_combat_power
from bot.config import HP_REGEN_RATE, HP_REGEN_INTERVAL, ENHANCE_BONUS_PER_LEVEL


class StatsView(discord.ui.View):
    def __init__(self, target, pdata: dict, wives_data: list):
        super().__init__(timeout=120)
        self.target = target
        self.pdata = pdata
        self.wives_data = wives_data
        self.eff = get_effective_stats(pdata)
        self._build_tab(1)

    def _tab1_embed(self) -> discord.Embed:
        eff = self.eff
        pdata = self.pdata
        cp = calc_combat_power(pdata, self.wives_data)
        embed = discord.Embed(title=f"📊 {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.add_field(name="⚔️ Lực Chiến", value=f"`{cp:,}`".replace(",", "."), inline=False)

        hp = pdata.get("hp", 0)
        hp_max = eff.get("hp_max", 100)
        hp_bar = "🟩" * (hp // 10) + "⬜" * ((hp_max - hp) // 10)
        if len(hp_bar) > 20:
            hp_bar = hp_bar[:20]
        hp_line = f"`{hp}/{hp_max}`\n{hp_bar}"
        if hp < hp_max:
            hp_line += f"\n💤 Hồi **{HP_REGEN_RATE} HP**/{HP_REGEN_INTERVAL}s..."
        embed.add_field(name="❤️ HP", value=hp_line, inline=False)

        atk_line = f"`{eff['attack_min']} - {eff['attack_max']}`"
        if eff.get("damage_pct", 0) > 0:
            atk_line += f"\n💎 Bị động: +{eff['damage_pct']}% dmg"
        embed.add_field(name="⚔️ Lực Xỏ Lá", value=atk_line, inline=True)

        def_line = f"`{eff['defense']}`"
        embed.add_field(name="🛡️ Lì Đòn", value=def_line, inline=True)

        spd = eff.get("spd", 0)
        crit = eff.get("crit", 0)
        if spd or crit:
            extras = []
            if spd: extras.append(f"💨 **{spd}** SPD")
            if crit: extras.append(f"💥 **{crit}%** CRIT")
            embed.add_field(name="⚡ Chỉ Số Phụ", value="\n".join(extras), inline=True)

        xp = pdata.get("xp", 0)
        level = pdata.get("level", 1)
        from bot.engine.rewards import calc_level
        _, xp_in_level = calc_level(xp)
        xp_needed = level * 80
        bar_filled = min(10, xp_in_level * 10 // xp_needed) if xp_needed > 0 else 0
        xp_bar = "🟦" * bar_filled + "⬜" * (10 - bar_filled)
        embed.add_field(name="📊 Cấp Độ", value=f"`Lv.{level}` | 💰 `{pdata.get('coins', 0)} coins`", inline=True)
        embed.add_field(name="🔮 Kinh Nghiệm", value=f"`{xp_in_level}/{xp_needed}`\n{xp_bar}", inline=True)

        embed.add_field(name="🏆 Thành Tích", value=f"Thắng:`{pdata['wins']}` Thua:`{pdata['losses']}`", inline=False)

        cls = CLASSES.get(pdata.get("class_id", "banxabong"), CLASSES["banxabong"])
        embed.add_field(name="🎭 Class", value=f"{cls['icon']} **{cls['name']}** — {cls['desc']}", inline=False)

        sp = pdata.get("stat_points", 0)
        if sp > 0:
            embed.add_field(name="⭐ Điểm Thuộc Tính", value=f"**{sp} điểm**! Dùng `/upgrade <hp/atk/def>`", inline=False)

        buff = pdata.get("buffs", {})
        if buff:
            bl = []
            if buff.get("attack_boost"):
                bl.append(f"⚡ +{buff['attack_boost']}% dmg")
            if buff.get("defense_boost"):
                bl.append(f"🛡️ +{buff['defense_boost']}% DEF")
            if buff.get("lucky"):
                bl.append(f"🎲 ×2 legendary — còn **{buff['lucky']}** trận")
            if bl:
                embed.add_field(name="🔮 Buff Trận Kế", value="\n".join(bl), inline=False)

        return embed

    def _tab2_embed(self) -> discord.Embed:
        pdata = self.pdata
        embed = discord.Embed(title=f"⚒️ Trang Bị — {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        eq = pdata.get("equipped", {})
        equip_items = pdata.get("_equip_items", {})
        equip_enhances = pdata.get("_equip_enhances", {})
        lines = []
        for slot in ["weapon", "armor", "boots", "gloves", "belt", "ring"]:
            eq_id = eq.get(slot)
            item_id = equip_items.get(str(eq_id)) if eq_id else None
            if item_id and item_id in EQUIPMENT:
                e = EQUIPMENT[item_id]
                enhance = equip_enhances.get(str(eq_id), 0)
                mult = 1 + enhance * ENHANCE_BONUS_PER_LEVEL
                stars = STAR_LABELS.get(e["star"], "⭐")
                enhance_str = f" +{enhance}" if enhance > 0 else ""
                stat_texts = []
                atk_min = None
                atk_max = None
                for k, v in e["stats"].items():
                    val = int(v * mult)
                    if k == "attack_min": atk_min = val
                    elif k == "attack_max": atk_max = val
                    elif k == "defense": stat_texts.append(f"🛡️+{val}")
                    elif k == "hp": stat_texts.append(f"❤️+{val}")
                    elif k == "spd": stat_texts.append(f"💨+{val}")
                    elif k == "crit": stat_texts.append(f"💥{val}%")
                    elif k == "pierce": stat_texts.append(f"🔱{val}%")
                    elif k == "dodge": stat_texts.append(f"🍀{val}%")
                    elif k == "reflect": stat_texts.append(f"🔄{val}%")
                    elif k == "regen": stat_texts.append(f"💚{val}%/t")
                if atk_min is not None and atk_max is not None:
                    stat_texts.insert(0, f"⚔️+{atk_min}~{atk_max}")
                lines.append(f"{EQ_SLOT_NAMES.get(slot, slot)}: {stars} **{e['name']}**{enhance_str} ({', '.join(stat_texts)})")
            else:
                lines.append(f"{EQ_SLOT_NAMES.get(slot, slot)}: ❌ Trống")
        embed.add_field(name="Đang Mặc", value="\n".join(lines), inline=False)

        embed.add_field(name="📦 Vật Phẩm Trong Kho", value="Dùng `/equip <id>` để mặc\nDùng `/unequip <slot>` để cởi", inline=False)

        return embed

    def _tab3_embed(self) -> discord.Embed:
        pdata = self.pdata
        embed = discord.Embed(title=f"🔥 Kỹ Năng — {self.target.display_name}", color=0x00ff88)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        skill_parts = []
        for cat in ["attack", "special", "defense", "passive"]:
            sk = get_equipped_skill(pdata, cat)
            cat_icons = {"attack": "💥", "special": "🔥", "defense": "🛡️", "passive": "💎"}
            stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
            if cat == "passive":
                skill_parts.append(f"{cat_icons[cat]} {sk['icon']} **{sk['name']}** {stars}\n　└ _{sk.get('desc', '')}_")
            else:
                cd = pdata.get(f"{cat}_cd", 0)
                cd_str = "✅ Sẵn sàng" if cd <= 0 else f"⏳ CD: `{cd}`"
                skill_parts.append(f"{cat_icons[cat]} {sk['icon']} **{sk['name']}** {stars}\n　└ {sk.get('desc', '')} | {cd_str}")
        embed.add_field(name="🔥 Kỹ Năng (4/4)", value="\n\n".join(skill_parts), inline=False)

        return embed

    def _build_tab(self, tab: int):
        self.clear_items()
        labels = [
            ("📊", "Thuộc Tính", discord.ButtonStyle.primary),
            ("⚒️", "Trang Bị", discord.ButtonStyle.success),
            ("🔥", "Kỹ Năng", discord.ButtonStyle.danger),
        ]
        for i, (emoji, label, style) in enumerate(labels):
            disabled = (i + 1 == tab)
            btn = discord.ui.Button(emoji=emoji, label=label, style=style if not disabled else discord.ButtonStyle.gray, disabled=disabled, custom_id=f"stats_tab_{i}")
            btn.callback = self._make_tab_cb(i + 1)
            self.add_item(btn)

        embeds = {1: self._tab1_embed, 2: self._tab2_embed, 3: self._tab3_embed}
        self._current_embed = embeds[tab]()

    def _make_tab_cb(self, tab: int):
        async def cb(interaction: discord.Interaction):
            if str(interaction.user.id) != str(self.target.id):
                await interaction.response.send_message("🤡 Của người khác!", ephemeral=True)
                return
            self._build_tab(tab)
            await interaction.response.edit_message(embed=self._current_embed, view=self)
        return cb

    @property
    def embed(self):
        return self._current_embed
