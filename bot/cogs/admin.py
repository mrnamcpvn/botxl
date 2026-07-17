import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import time
from bot.database import get_db
from bot.data.classes import CLASSES, DEFAULT_SKILLS, DEFAULT_SKILL_SLOTS
from bot.data.equipment import EQUIPMENT, STAR_LABELS, SLOT_NAMES as EQ_SLOT_NAMES
from bot.logger import logger

ADMIN_IDS = ["454923120986292224"]
DROP_CHANNEL_ID = 1040459995319373864

ROLE_MULTIPLIERS = {
    "Dragon": 3.0,
    "VIP": 1.5,
    "Supporter": 1.2,
    "Coder": 1.1,
    "Unisex": 1.0,
    "Blacklist": 0.8,
}


async def sync_role_mult(db, member_id: str, member_roles: list[str]) -> float:
    mult = 1.0
    for role_name, role_mult in ROLE_MULTIPLIERS.items():
        if role_name in member_roles:
            mult = max(mult, role_mult)
    await db.execute("UPDATE players SET role_mult=? WHERE id=?", (mult, member_id))
    if mult >= 3.0:
        cursor = await db.execute("SELECT class_id FROM players WHERE id=?", (member_id,))
        row = await cursor.fetchone()
        if row and row[0] != "trumcuoi":
            cls = CLASSES["trumcuoi"]
            await db.execute("""UPDATE players SET class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?""",
                              ("trumcuoi", cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], member_id))
            await db.execute("DELETE FROM player_skills WHERE player_id=?", (member_id,))
            await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (member_id,))
            for sk_id in DEFAULT_SKILLS["trumcuoi"]:
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (member_id, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS["trumcuoi"].items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (member_id, slot, sk_id))
    elif mult < 3.0:
        cursor = await db.execute("SELECT class_id FROM players WHERE id=?", (member_id,))
        row = await cursor.fetchone()
        if row and row[0] == "trumcuoi":
            cls = CLASSES["banxabong"]
            await db.execute("""UPDATE players SET class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?""",
                              ("banxabong", cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], member_id))
            await db.execute("DELETE FROM player_skills WHERE player_id=?", (member_id,))
            await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (member_id,))
            for sk_id in DEFAULT_SKILLS["banxabong"]:
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (member_id, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS["banxabong"].items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (member_id, slot, sk_id))
    return mult


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._drop_task = None

    def _is_admin(self, uid: str) -> bool:
        return uid in ADMIN_IDS

    async def cog_load(self):
        self._drop_task = asyncio.create_task(self._auto_drop_loop())

    async def cog_unload(self):
        if self._drop_task:
            self._drop_task.cancel()

    async def _auto_drop_loop(self):
        await self.bot.wait_until_ready()
        logger.info(f"[DROP] Auto-drop loop started, channel={DROP_CHANNEL_ID}")
        while True:
            try:
                delay = random.randint(600, 3540)
                mins = delay // 60
                secs = delay % 60
                logger.info(f"[DROP] Next drop in {mins}p{secs}s")
                await asyncio.sleep(delay)
                ch = self.bot.get_channel(DROP_CHANNEL_ID)
                if ch:
                    await self._do_drop(ch)
                else:
                    logger.error(f"[DROP] Channel {DROP_CHANNEL_ID} not found!")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[DROP] {e}", exc_info=True)

    @commands.command(name="reset")
    async def reset_cmd(self, ctx, member: discord.Member = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        if not member:
            await ctx.reply("❌ !reset @player")
            return
        await self._reset(ctx, member, "!")

    @commands.command(name="givecoins")
    async def givecoins_cmd(self, ctx, member: discord.Member = None, amount: str = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        if not member or not amount:
            await ctx.reply("❌ !givecoins @player <số>")
            return
        try:
            amt = int(amount.strip())
        except:
            await ctx.reply("❌ Số coins không hợp lệ!")
            return
        await self._givecoins(ctx, member, amt, "!")

    @commands.command(name="setclass")
    async def setclass_cmd(self, ctx, member: discord.Member = None, class_id: str = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        if not member or not class_id:
            await ctx.reply("❌ !setclass @player <class_id>")
            return
        await self._setclass(ctx, member, class_id.strip(), "!")

    @commands.command(name="resetallskills")
    async def resetallskills_cmd(self, ctx, member: discord.Member = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        if not member:
            await ctx.reply("❌ !resetallskills @player")
            return
        await self._resetallskills(ctx, member, "!")

    @commands.command(name="syncrole")
    async def syncrole_cmd(self, ctx, member: discord.Member = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        if not member:
            await ctx.reply("❌ !syncrole @player")
            return
        await self._syncrole(ctx, member, "!")

    @commands.command(name="giveart")
    async def giveart_cmd(self, ctx, member: discord.Member = None, amount: str = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!"); return
        if not member or not amount:
            await ctx.reply("❌ !giveart @player <số>"); return
        try: amt = int(amount.strip())
        except: await ctx.reply("❌ Số không hợp lệ!"); return
        sid = str(member.id)
        db = await get_db()
        try:
            await db.execute("""INSERT OR REPLACE INTO player_artifact (player_id, star, stone_count) 
                VALUES (?, COALESCE((SELECT star FROM player_artifact WHERE player_id=?), 0), 
                COALESCE((SELECT stone_count FROM player_artifact WHERE player_id=?), 0) + ?)""",
                (sid, sid, sid, amt))
            await db.commit()
            await ctx.reply(f"💎 Cho {member.display_name} {amt} Đá Thần Khí!")
        finally:
            await db.close()

    async def _reply(self, ctx_or_int, msg):
        if isinstance(ctx_or_int, commands.Context):
            await ctx_or_int.reply(msg)
        else:
            await ctx_or_int.followup.send(msg)

    async def _reset(self, ctx_or_int, member, prefix):
        sid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Player chưa đăng ký!")
                return
            pdata = dict(row)
            class_id = pdata.get("class_id", "banxabong")
            cls = CLASSES.get(class_id, CLASSES["banxabong"])
            await db.execute("""UPDATE players SET hp=?, hp_max=?, attack_min=?, attack_max=?, defense=?, wins=0, losses=0, damage_dealt=0, damage_taken=0, coins=0, xp=0, level=1, stat_points=0, elo=1000, attack_cd=0, special_cd=0, defense_cd=0, upgrade_hp=0, upgrade_atk=0, upgrade_def=0 WHERE id=?""",
                              (cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], sid))
            await db.execute("DELETE FROM inventory WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_equipment WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_skills WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_buffs WHERE player_id=?", (sid,))
            for sk_id in DEFAULT_SKILLS.get(class_id, [1, 5, 10, 14]):
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS.get(class_id, {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await db.commit()
            await self._reply(ctx_or_int, f"✅ Reset **{member.display_name}** thành công!")
        finally:
            await db.close()

    async def _givecoins(self, ctx_or_int, member, amount, prefix):
        sid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))
            if not await cursor.fetchone():
                await self._reply(ctx_or_int, "🤷 Player chưa đăng ký!")
                return
            await db.execute("UPDATE players SET coins=coins+? WHERE id=?", (amount, sid))
            await db.commit()
            sign = "+" if amount >= 0 else ""
            await self._reply(ctx_or_int, f"💰 Đã cho **{member.display_name}** {sign}{amount}🪙!")
        finally:
            await db.close()

    async def _setclass(self, ctx_or_int, member, class_id, prefix):
        if class_id not in CLASSES:
            await self._reply(ctx_or_int, "❌ Không có class này!")
            return
        cls = CLASSES[class_id]
        sid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))
            if not await cursor.fetchone():
                await self._reply(ctx_or_int, "🤷 Player chưa đăng ký!")
                return
            await db.execute("""UPDATE players SET class_id=?, hp=?, hp_max=?, attack_min=?, attack_max=?, defense=? WHERE id=?""",
                              (class_id, cls["hp_base"], cls["hp_base"], cls["atk_base"], cls["atk_base"] + 5, cls["def_base"], sid))
            await db.execute("DELETE FROM player_skills WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (sid,))
            for sk_id in DEFAULT_SKILLS.get(class_id, [1, 5, 10, 14]):
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS.get(class_id, {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await db.commit()
            await self._reply(ctx_or_int, f"✅ Set class **{member.display_name}** → {cls['icon']} {cls['name']}!")
        finally:
            await db.close()

    async def _resetallskills(self, ctx_or_int, member, prefix):
        sid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT class_id FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await self._reply(ctx_or_int, "🤷 Player chưa đăng ký!")
                return
            class_id = row[0]
            await db.execute("DELETE FROM player_skills WHERE player_id=?", (sid,))
            await db.execute("DELETE FROM player_skill_slots WHERE player_id=?", (sid,))
            for sk_id in DEFAULT_SKILLS.get(class_id, [1, 5, 10, 14]):
                await db.execute("INSERT OR IGNORE INTO player_skills (player_id, skill_id) VALUES (?, ?)", (sid, sk_id))
            for slot, sk_id in DEFAULT_SKILL_SLOTS.get(class_id, {"attack": 1, "special": 5, "defense": 10, "passive": 14}).items():
                await db.execute("INSERT OR REPLACE INTO player_skill_slots (player_id, slot, skill_id) VALUES (?, ?, ?)", (sid, slot, sk_id))
            await db.commit()
            await self._reply(ctx_or_int, f"✅ Reset skill **{member.display_name}** về mặc định!")
        finally:
            await db.close()

    async def _syncrole(self, ctx_or_int, member, prefix):
        sid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (sid,))
            if not await cursor.fetchone():
                await self._reply(ctx_or_int, "🤷 Player chưa đăng ký!")
                return
            role_names = [r.name for r in member.roles]
            mult = 1.0
            for rn, rm in ROLE_MULTIPLIERS.items():
                if rn in role_names:
                    mult = max(mult, rm)
            await db.execute("UPDATE players SET role_mult=? WHERE id=?", (mult, sid))
            await db.commit()
            await self._reply(ctx_or_int, f"✅ Sync role **{member.display_name}** → **{mult}×**")
        finally:
            await db.close()

    @commands.command(name="drop_item", aliases=["dropitem", "roi"])
    async def drop_item_cmd(self, ctx):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫 Mày hông đủ quyền!")
            return
        ch = ctx.channel
        await self._do_drop(ch)

    @app_commands.command(name="drop_item", description="👑 Rơi trang bị ngẫu nhiên (admin)")
    async def slash_drop_item(self, interaction: discord.Interaction):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫 Mày hông đủ quyền!", ephemeral=True)
            return
        await interaction.response.send_message("💥 Rơi đồ!", ephemeral=True)
        await self._do_drop(interaction.channel)

    async def _do_drop(self, channel):
        items = [(eid, e) for eid, e in EQUIPMENT.items()]
        if not items:
            return
        eid, equip = random.choice(items)
        stars = STAR_LABELS.get(equip["star"], "⭐")
        slot_name = EQ_SLOT_NAMES.get(equip["slot"], equip["slot"])

        embed = discord.Embed(
            title="💥 RƠI TRANG BỊ!",
            color=0xff6600,
            description=(
                f"# {stars} {equip['name']}\n"
                f"### {slot_name} — {equip['star']}★\n"
                f"```AI NHANH TAY LỤM NÀO!```"
            )
        )

        stat_parts = []
        atk_min, atk_max = None, None
        for k, v in equip["stats"].items():
            if k == "attack_min": atk_min = v
            elif k == "attack_max": atk_max = v
            elif k == "defense": stat_parts.append(f"🛡️+{v}")
            elif k == "hp": stat_parts.append(f"❤️+{v}")
            elif k == "spd": stat_parts.append(f"💨+{v}")
            elif k == "crit": stat_parts.append(f"💥{v}%")
        if atk_min and atk_max:
            stat_parts.insert(0, f"⚔️+{atk_min}~{atk_max}")
        if stat_parts:
            embed.add_field(name="📊 Chỉ số", value=" | ".join(stat_parts), inline=False)

        view = LootDropView(eid, equip["name"])
        msg = await channel.send(embed=embed, view=view)
        view.message = msg

    @app_commands.command(name="reset", description="👑 Reset player (admin)")
    async def slash_reset(self, interaction: discord.Interaction, member: discord.Member):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._reset(interaction, member, "/")

    @app_commands.command(name="givecoins", description="👑 Cho coins (admin)")
    async def slash_givecoins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._givecoins(interaction, member, amount, "/")

    @app_commands.command(name="setclass", description="👑 Set class (admin)")
    async def slash_setclass(self, interaction: discord.Interaction, member: discord.Member, class_id: str):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._setclass(interaction, member, class_id, "/")

    @app_commands.command(name="resetallskills", description="👑 Reset skills (admin)")
    async def slash_resetallskills(self, interaction: discord.Interaction, member: discord.Member):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._resetallskills(interaction, member, "/")

    @app_commands.command(name="syncrole", description="👑 Sync role (admin)")
    async def slash_syncrole(self, interaction: discord.Interaction, member: discord.Member):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._syncrole(interaction, member, "/")

    @app_commands.command(name="forceclean", description="👑 Force clean battles (admin)")
    async def slash_forceclean(self, interaction: discord.Interaction):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._forceclean(interaction, "/")

    @app_commands.command(name="giveall", description="👑 Tặng xu tất cả player (admin)")
    async def slash_giveall(self, interaction: discord.Interaction, amount: str):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer()
        await self._giveall(interaction, amount, "/")

    @app_commands.command(name="sync", description="👑 Sync slash commands (admin)")
    async def slash_sync(self, interaction: discord.Interaction):
        if not self._is_admin(str(interaction.user.id)):
            await interaction.response.send_message("🚫", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        try:
            self.bot.tree.copy_global_to(guild=interaction.guild)
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"✅ Đã sync {len(synced)} slash commands!")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}")

    @commands.command(name="forceclean")
    async def forceclean_cmd(self, ctx):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫"); return
        await self._forceclean(ctx, "!")

    async def _forceclean(self, ctx_or_int, prefix):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM challenges")
            ch_num = (await cursor.fetchone())[0]
            cursor2 = await db.execute("SELECT COUNT(*) FROM active_battles")
            bt_num = (await cursor2.fetchone())[0]
            await db.execute("DELETE FROM challenges")
            await db.execute("DELETE FROM active_battles")
            await db.execute("DELETE FROM battle_status")
            await db.commit()
            await self._reply(ctx_or_int, f"🧹 Đã dọn: {ch_num} challenge + {bt_num} battle kẹt!")
        finally:
            await db.close()

    @commands.command(name="giveall")
    async def giveall_cmd(self, ctx, amount: str = None):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫"); return
        await self._giveall(ctx, amount, "!")

    async def _giveall(self, ctx_or_int, amount: str, prefix: str):
        if not amount:
            await self._reply(ctx_or_int, f"❌ `{prefix}giveall <số>`"); return
        try: amt = int(amount.strip())
        except: await self._reply(ctx_or_int, "❌ Số không hợp lệ!"); return
        if amt <= 0: await self._reply(ctx_or_int, "❌ > 0!"); return
        db = await get_db()
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM players")
            count = (await cursor.fetchone())[0]
            await db.execute("UPDATE players SET coins=coins+?", (amt,))
            await db.commit()
            await self._reply(ctx_or_int, f"💰 Đã tặng {amt}🪙 cho {count} player!")
        finally:
            await db.close()

    @commands.command(name="sync")
    async def sync_cmd(self, ctx):
        if not self._is_admin(str(ctx.author.id)):
            await ctx.reply("🚫"); return
        try:
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            names = [c.name for c in synced]
            await ctx.reply(f"✅ {len(synced)} commands!\n```\n" + "\n".join(sorted(names)) + "\n```")
        except Exception as e:
            await ctx.reply(f"❌ {e}")


class LootDropView(discord.ui.View):
    def __init__(self, equip_id: int, equip_name: str):
        super().__init__(timeout=60)
        self.equip_id = equip_id
        self.equip_name = equip_name
        self.claimed = False

    @discord.ui.button(emoji="🤲", label="LỤM!", style=discord.ButtonStyle.success)
    async def loot_btn(self, interaction: discord.Interaction, button: discord.Button):
        if self.claimed:
            await interaction.response.send_message("👋 Người khác lụm mất rồi!", ephemeral=True)
            return
        self.claimed = True
        uid = str(interaction.user.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (uid,))
            if not await cursor.fetchone():
                await interaction.response.send_message("🤷 Chưa đăng ký! `/register`", ephemeral=True)
                return
            await db.execute("INSERT INTO player_equipment (player_id, item_id, enhance, equipped) VALUES (?, ?, 0, 0)", (uid, self.equip_id))
            await db.commit()

            button.disabled = True
            button.label = f"LỤM BỞI {interaction.user.display_name}"
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"🤲 **{interaction.user.display_name}** lụm được **{self.equip_name}**! `/equip {self.equip_id}` để mang!",
                ephemeral=False)
        finally:
            await db.close()

    async def on_timeout(self):
        if self.claimed:
            return
        for item in self.children:
            item.disabled = True
            item.label = "⏰ HẾT HẠN"
            item.style = discord.ButtonStyle.secondary
        try:
            if hasattr(self, 'message') and self.message:
                embed = self.message.embeds[0] if self.message.embeds else None
                if embed:
                    embed.set_footer(text="⏰ Không có ai lụm!")
                    await self.message.edit(embed=embed, view=self)
        except:
            pass


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
