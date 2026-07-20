"""
InventoryView — Túi đồ với tabs + phân trang.

Tabs:
  🎒 Tổng Quan  — slot đang mặc + đá cường hóa + buff
  ⚒️ Trang Bị   — danh sách kho đồ, phân trang 10/trang
  🧪 Tiêu Hao   — consumables
  🔥 Kỹ Năng    — skills đang sở hữu, phân trang 10/trang
"""

import json
import discord
from bot.data.equipment import EQUIPMENT, STAR_LABELS, STAR_COLORS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.data.shop_items import SHOP_ITEMS
from bot.data.skills import SKILLS_DB, RARITY_STARS, CATEGORY_LABELS
from bot.config import ENHANCE_BONUS_PER_LEVEL, MAX_ENHANCE
from bot.cogs.enhance import HIDDEN_STAT_POOLS

# Discord field value limit
_FIELD_LIMIT = 1024
# Items per page
_PAGE_SIZE = 10

ALL_SLOTS = ["weapon", "armor", "boots", "gloves", "belt", "ring"]

RARITY_COLORS_MAP = {
    "common": 0x888888, "uncommon": 0x00ff88,
    "rare": 0x0088ff, "epic": 0xaa00ff, "legendary": 0xffaa00,
}

# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _enh_str(enh: int) -> str:
    if enh >= MAX_ENHANCE:
        return " 🌟MAX"
    return f" ✦+{enh}" if enh > 0 else ""


def _equip_line(er: dict) -> str:
    """Tạo 1 dòng hiển thị cho 1 equipment row."""
    eiid = er["item_id"]
    enh = er.get("enhance", 0)
    eq_flag = "✅" if er.get("equipped") else "📦"
    enh_s = _enh_str(enh)

    if eiid in EQUIPMENT:
        e = EQUIPMENT[eiid]
        star = e["star"]
        stars = STAR_LABELS.get(star, "⭐")
        name = e["name"]
        if star == 6:
            name = f"[✨] {name}"
        slot_name = EQ_SLOT_NAMES.get(e["slot"], e["slot"])

        # Stats tóm tắt
        mult = 1 + enh * ENHANCE_BONUS_PER_LEVEL
        stats = e["stats"]
        parts = []
        atk_min = int(stats.get("attack_min", 0) * mult)
        atk_max = int(stats.get("attack_max", 0) * mult)
        if atk_min or atk_max:
            parts.append(f"⚔️{atk_min}~{atk_max}")
        if stats.get("defense"):
            parts.append(f"🛡️{int(stats['defense'] * mult)}")
        if stats.get("hp"):
            parts.append(f"❤️{int(stats['hp'] * mult)}")
        if stats.get("spd"):
            parts.append(f"💨{int(stats['spd'] * mult)}")
        if stats.get("crit"):
            parts.append(f"💥{int(stats['crit'] * mult)}%")

        # Hidden stats
        hidden_json = er.get("hidden_stats", "")
        hidden_tag = " 🌟" if hidden_json else ""

        stat_s = f" `{' '.join(parts)}`" if parts else ""
        return f"{eq_flag} `{er['id']}` {stars} **{name}**{enh_s}{hidden_tag} {stat_s} _{slot_name}_"

    elif eiid in SHOP_ITEMS:
        item = SHOP_ITEMS[eiid]
        return f"{eq_flag} `{er['id']}` {item['name']}{enh_s}"

    return f"{eq_flag} `{er['id']}` `item#{eiid}`{enh_s}"


def _chunks(lst: list, n: int) -> list[list]:
    return [lst[i:i + n] for i in range(0, len(lst), n)] if lst else [[]]


# ────────────────────────────────────────────────────────────
# InventoryView
# ────────────────────────────────────────────────────────────

class InventoryView(discord.ui.View):
    """
    Dữ liệu đã được load bên ngoài và truyền vào:
      pdata        — dict player (đã có level, coins, hp...)
      eq_rows      — list[dict] từ player_equipment
      consumables  — dict {item_id: qty}
      stone_row    — tuple (basic, medium, advanced) hoặc None
      owned_skills — set[int]
      equipped_skills — dict {slot: skill_id}
      user         — discord.Member
    """

    # Tab IDs
    TAB_OVERVIEW = 0
    TAB_EQUIP    = 1
    TAB_CONSUMABLE = 2
    TAB_SKILL    = 3

    def __init__(self, user: discord.Member, pdata: dict, eq_rows: list,
                 consumables: dict, stone_row, owned_skills: set,
                 equipped_skills: dict):
        super().__init__(timeout=180)
        self.user = user
        self.pdata = pdata
        self.eq_rows = eq_rows
        self.consumables = consumables
        self.stone_row = stone_row
        self.owned_skills = owned_skills
        self.equipped_skills = equipped_skills

        # Precompute equipped slot → row id
        self._equipped_by_slot: dict[str, int] = {}
        for er in eq_rows:
            if er.get("equipped"):
                eiid = er["item_id"]
                slot = None
                if eiid in EQUIPMENT:
                    slot = EQUIPMENT[eiid]["slot"]
                elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid].get("type") == "equipment":
                    slot = SHOP_ITEMS[eiid]["slot"]
                if slot:
                    self._equipped_by_slot[slot] = er["id"]

        # Precompute best star for embed color
        best_star = 0
        for er in eq_rows:
            if er.get("equipped") and er["item_id"] in EQUIPMENT:
                best_star = max(best_star, EQUIPMENT[er["item_id"]]["star"])
        self._base_color = STAR_COLORS.get(best_star, 0x5865f2)

        # Pagination state
        self._tab = self.TAB_OVERVIEW
        self._page = 0

        self._rebuild()

    # ── Public property ──────────────────────────────────────

    @property
    def embed(self) -> discord.Embed:
        return self._embed

    # ── Build ─────────────────────────────────────────────────

    def _rebuild(self):
        self.clear_items()
        self._build_tab_buttons()

        if self._tab == self.TAB_OVERVIEW:
            self._embed = self._embed_overview()
        elif self._tab == self.TAB_EQUIP:
            self._build_pager(self._equip_pages())
            self._embed = self._embed_equip()
        elif self._tab == self.TAB_CONSUMABLE:
            self._embed = self._embed_consumable()
        elif self._tab == self.TAB_SKILL:
            self._build_pager(self._skill_pages())
            self._embed = self._embed_skill()

    def _build_tab_buttons(self):
        tabs = [
            (self.TAB_OVERVIEW,    "🎒", "Tổng Quan",  discord.ButtonStyle.secondary),
            (self.TAB_EQUIP,       "⚒️", "Trang Bị",   discord.ButtonStyle.primary),
            (self.TAB_CONSUMABLE,  "🧪", "Tiêu Hao",   discord.ButtonStyle.success),
            (self.TAB_SKILL,       "🔥", "Kỹ Năng",    discord.ButtonStyle.danger),
        ]
        for tid, emoji, label, style in tabs:
            active = (tid == self._tab)
            btn = discord.ui.Button(
                emoji=emoji, label=label,
                style=discord.ButtonStyle.gray if active else style,
                disabled=active,
                custom_id=f"inv_tab_{tid}",
                row=0,
            )
            btn.callback = self._make_tab_cb(tid)
            self.add_item(btn)

    def _build_pager(self, pages: list[list]):
        """Thêm nút ◀ / trang / ▶ vào row 1 nếu cần."""
        if len(pages) <= 1:
            return
        total = len(pages)
        cur = self._page

        prev_btn = discord.ui.Button(
            emoji="◀", style=discord.ButtonStyle.secondary,
            disabled=(cur == 0), custom_id="inv_prev", row=1,
        )
        prev_btn.callback = self._prev_cb

        page_btn = discord.ui.Button(
            label=f"{cur + 1}/{total}", style=discord.ButtonStyle.secondary,
            disabled=True, custom_id="inv_page_info", row=1,
        )

        next_btn = discord.ui.Button(
            emoji="▶", style=discord.ButtonStyle.secondary,
            disabled=(cur >= total - 1), custom_id="inv_next", row=1,
        )
        next_btn.callback = self._next_cb

        self.add_item(prev_btn)
        self.add_item(page_btn)
        self.add_item(next_btn)

    # ── Tab callbacks ─────────────────────────────────────────

    def _make_tab_cb(self, tid: int):
        async def cb(interaction: discord.Interaction):
            if str(interaction.user.id) != str(self.user.id):
                await interaction.response.send_message("🤡 Đây không phải túi đồ của mày!", ephemeral=True)
                return
            self._tab = tid
            self._page = 0
            self._rebuild()
            await interaction.response.edit_message(embed=self._embed, view=self)
        return cb

    async def _prev_cb(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.user.id):
            await interaction.response.send_message("🤡 Không phải của mày!", ephemeral=True)
            return
        self._page = max(0, self._page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._embed, view=self)

    async def _next_cb(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.user.id):
            await interaction.response.send_message("🤡 Không phải của mày!", ephemeral=True)
            return
        pages = (self._equip_pages() if self._tab == self.TAB_EQUIP
                 else self._skill_pages())
        self._page = min(len(pages) - 1, self._page + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._embed, view=self)

    # ── Pages helpers ─────────────────────────────────────────

    def _equip_pages(self) -> list[list]:
        return _chunks(self.eq_rows, _PAGE_SIZE)

    def _skill_pages(self) -> list[list]:
        items = sorted(self.owned_skills)
        return _chunks(items, _PAGE_SIZE)

    # ── Embeds ────────────────────────────────────────────────

    def _header_embed(self, title: str, color: int) -> discord.Embed:
        from bot.engine.rewards import calc_level
        level, _ = calc_level(self.pdata.get("xp", 0))
        coins = self.pdata.get("coins", 0)
        embed = discord.Embed(title=title, color=color)
        embed.set_author(
            name=self.user.display_name,
            icon_url=self.user.display_avatar.url,
        )
        embed.set_footer(text=f"Lv.{level}  ·  💰 {coins:,} 🪙".replace(",", "."))
        return embed

    # ── Tab 0: Tổng Quan ──────────────────────────────────────

    def _embed_overview(self) -> discord.Embed:
        embed = self._header_embed(f"🎒 Túi Đồ — {self.user.display_name}", self._base_color)
        embed.set_thumbnail(url=self.user.display_avatar.url)

        # ── Đang mặc ──
        worn_lines = []
        for slot in ALL_SLOTS:
            slot_name = EQ_SLOT_NAMES.get(slot, slot)
            eq_id = self._equipped_by_slot.get(slot)
            er = next((r for r in self.eq_rows if r["id"] == eq_id), None) if eq_id else None
            if er:
                eiid = er["item_id"]
                enh = er.get("enhance", 0)
                enh_s = _enh_str(enh)
                if eiid in EQUIPMENT:
                    e = EQUIPMENT[eiid]
                    stars = STAR_LABELS.get(e["star"], "⭐")
                    name = e["name"]
                    if e["star"] == 6:
                        name = f"✨ {name}"
                    worn_lines.append(f"{slot_name}: {stars} **{name}**{enh_s}")
                elif eiid in SHOP_ITEMS:
                    worn_lines.append(f"{slot_name}: {SHOP_ITEMS[eiid]['name']}{enh_s}")
            else:
                worn_lines.append(f"{slot_name}: ▫️ _trống_")

        embed.add_field(
            name="⚔️ Đang Mặc",
            value="\n".join(worn_lines) or "_(chưa có gì)_",
            inline=False,
        )

        # ── Đá cường hóa ──
        if self.stone_row:
            sb, sm, sa = (self.stone_row[0] or 0, self.stone_row[1] or 0, self.stone_row[2] or 0)
            if sb or sm or sa:
                stone_text = (
                    f"🔵 Sơ Cấp: **{sb}**\n"
                    f"🟢 Trung Cấp: **{sm}**\n"
                    f"🔴 Cao Cấp: **{sa}**"
                )
                embed.add_field(name="💎 Đá Cường Hóa", value=stone_text, inline=True)

        # ── Buff ──
        buff = self.pdata.get("buffs", {})
        if buff:
            bl = []
            if buff.get("attack_boost", 0) > 0:
                bl.append(f"⚡ +30% dmg — còn **{buff['attack_boost']}** trận")
            if buff.get("defense_boost", 0) > 0:
                bl.append(f"🛡️ +50% DEF — còn **{buff['defense_boost']}** trận")
            if buff.get("lucky", 0) > 0:
                bl.append(f"🎲 ×2 legendary — còn **{buff['lucky']}** trận")
            if bl:
                embed.add_field(name="🔮 Buff Đang Có", value="\n".join(bl), inline=True)

        # ── Thống kê nhanh ──
        total_eq = len(self.eq_rows)
        total_con = sum(self.consumables.values())
        total_sk = len(self.owned_skills)
        embed.add_field(
            name="📊 Tổng Kho",
            value=(
                f"⚒️ Trang bị: **{total_eq}** món\n"
                f"🧪 Tiêu hao: **{total_con}** cái\n"
                f"🔥 Kỹ năng: **{total_sk}** skill"
            ),
            inline=True,
        )

        embed.add_field(
            name="💡 Hướng Dẫn",
            value=(
                "`/equip <id>` mặc/tháo trang bị\n"
                "`/unequip <slot>` tháo theo slot\n"
                "`/use <id>` dùng tiêu hao\n"
                "`/cuonghoa <id>` cường hóa"
            ),
            inline=False,
        )
        return embed

    # ── Tab 1: Trang Bị ───────────────────────────────────────

    def _embed_equip(self) -> discord.Embed:
        pages = self._equip_pages()
        page_items = pages[self._page] if pages else []
        total_pages = len(pages)
        total_items = len(self.eq_rows)

        embed = self._header_embed(
            f"⚒️ Kho Trang Bị — {total_items} món",
            self._base_color,
        )

        if not self.eq_rows:
            embed.description = "_(Kho trống — đi đánh NPC hoặc PvP để kiếm đồ!)_"
            return embed

        lines = []
        for er in page_items:
            lines.append(_equip_line(er))

        # Đảm bảo không vượt 1024 chars
        field_val = "\n".join(lines)
        if len(field_val) > _FIELD_LIMIT:
            # Cắt xuống an toàn
            field_val = field_val[:_FIELD_LIMIT - 20] + "\n_...còn nữa_"

        embed.add_field(
            name=f"📦 Kho ({self._page * _PAGE_SIZE + 1}–{min((self._page + 1) * _PAGE_SIZE, total_items)} / {total_items})",
            value=field_val,
            inline=False,
        )

        # Legend
        embed.add_field(
            name="🔖 Ký Hiệu",
            value="✅ đang mặc  ·  📦 trong kho  ·  🌟 có hidden stats",
            inline=False,
        )

        if total_pages > 1:
            embed.set_footer(
                text=f"Trang {self._page + 1}/{total_pages}  ·  Lv.{self.pdata.get('level',1)}  ·  💰 {self.pdata.get('coins',0):,} 🪙".replace(",", ".")
            )
        return embed

    # ── Tab 2: Tiêu Hao ───────────────────────────────────────

    def _embed_consumable(self) -> discord.Embed:
        embed = self._header_embed("🧪 Vật Phẩm Tiêu Hao", 0x57f287)

        if not self.consumables:
            embed.description = "_(Không có vật phẩm tiêu hao — mua ở `/shop`)_"
            return embed

        lines = []
        for iid, qty in self.consumables.items():
            item = SHOP_ITEMS.get(iid)
            if not item:
                continue
            lines.append(
                f"🔹 `{iid}` **{item['name']}** ×**{qty}**\n"
                f"　└ _{item['desc']}_"
            )

        field_val = "\n".join(lines)
        if len(field_val) > _FIELD_LIMIT:
            field_val = field_val[:_FIELD_LIMIT - 20] + "\n_...còn nữa_"

        embed.add_field(name="🎒 Đang Có", value=field_val, inline=False)
        embed.add_field(
            name="💡 Cách Dùng",
            value="`/use <id>` — dùng ngay\n`/buy <id>` — mua thêm ở `/shop`",
            inline=False,
        )
        return embed

    # ── Tab 3: Kỹ Năng ────────────────────────────────────────

    def _embed_skill(self) -> discord.Embed:
        pages = self._skill_pages()
        page_items = pages[self._page] if pages else []
        total_pages = len(pages)
        total_items = len(self.owned_skills)

        embed = self._header_embed(
            f"🔥 Kho Kỹ Năng — {total_items} skill",
            0xff6600,
        )

        if not self.owned_skills:
            embed.description = "_(Chưa có skill nào — mua ở `/skills`)_"
            return embed

        # Nhóm theo category
        cat_groups: dict[str, list[str]] = {
            "attack": [], "special": [], "defense": [], "passive": []
        }
        cat_icons = {"attack": "💥", "special": "🔥", "defense": "🛡️", "passive": "💎"}

        for sid in page_items:
            sk = SKILLS_DB.get(sid)
            if not sk:
                continue
            stars = RARITY_STARS.get(sk.get("rarity", "common"), "⭐")
            cat = sk.get("category", "attack")
            is_equipped = (self.equipped_skills.get(cat) == sid)
            status = "✅" if is_equipped else "📦"

            if cat == "passive":
                line = f"{status} `{sid}` {sk['icon']} **{sk['name']}** {stars}"
            else:
                cd = sk.get("cooldown", 0)
                line = f"{status} `{sid}` {sk['icon']} **{sk['name']}** {stars} `CD:{cd}`"

            cat_groups.get(cat, cat_groups["attack"]).append(line)

        for cat in ["attack", "special", "defense", "passive"]:
            lines = cat_groups[cat]
            if not lines:
                continue
            cat_label = CATEGORY_LABELS.get(cat, cat)
            field_val = "\n".join(lines)
            if len(field_val) > _FIELD_LIMIT:
                field_val = field_val[:_FIELD_LIMIT - 20] + "\n_...còn nữa_"
            embed.add_field(
                name=f"{cat_icons[cat]} {cat_label}",
                value=field_val,
                inline=False,
            )

        if total_pages > 1:
            embed.set_footer(
                text=f"Trang {self._page + 1}/{total_pages}  ·  Lv.{self.pdata.get('level',1)}  ·  💰 {self.pdata.get('coins',0):,} 🪙".replace(",", ".")
            )

        embed.add_field(
            name="💡 Cách Dùng",
            value="`/equipskill <loại> <id>` — gán skill\n`/buyskill <id>` — mua skill mới",
            inline=False,
        )
        return embed
