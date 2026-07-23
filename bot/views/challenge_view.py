import discord
import asyncio
import time
import random
from bot.database import get_db
from bot.cogs.admin import sync_role_mult
from bot.engine.battle import get_effective_stats, regen_hp
from bot.data.equipment import EQUIPMENT
from bot.data.shop_items import SHOP_ITEMS
from bot.views.ui_helpers import hp_bar


class ChallengeView(discord.ui.View):
    def __init__(self, bot, target_sid: str, challenger_sid: str, challenger_name: str, target_name: str, channel_id: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.target_sid = target_sid
        self.challenger_sid = challenger_sid
        self.challenger_name = challenger_name
        self.target_name = target_name
        self.channel_id = channel_id
        self.used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.target_sid:
            await interaction.response.send_message("🤡 Có phải mày đâu!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.used:
            return
        self.used = True
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not await cursor.fetchone():
                return
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            await db.execute("UPDATE players SET coins = MAX(0, coins - 20) WHERE id = ?", (self.target_sid,))
            await db.commit()
            ch = self.bot.get_channel(int(self.channel_id))
            if ch:
                await ch.send(f"⏰ **{self.target_name}** hết giờ! -20🪙 vì hèn! 🏃")
        finally:
            await db.close()

    @discord.ui.button(emoji="✅", label="Nhận Lời", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.Button):
        if self.used:
            return
        self.used = True
        await self._do_accept(interaction)

    @discord.ui.button(emoji="❌", label="Từ Chối", style=discord.ButtonStyle.danger)
    async def deny_btn(self, interaction: discord.Interaction, button: discord.Button):
        if self.used:
            return
        self.used = True
        await self._do_deny(interaction)

    async def _do_accept(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = await get_db()
        try:
            # Kiểm tra đang tu luyện
            for check_sid in [self.challenger_sid, self.target_sid]:
                cult_row = await (await db.execute(
                    "SELECT cultivating FROM cultivation WHERE player_id=?", (check_sid,))).fetchone()
                if cult_row and cult_row[0]:
                    who = "Bạn" if check_sid == self.target_sid else self.challenger_name
                    await interaction.followup.send(
                        f"🧘 **{who}** đang tu luyện! Cần kết thúc trước khi PvP (`!tulyen`).",
                        ephemeral=True)
                    return
            cursor = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not await cursor.fetchone():
                await interaction.followup.send("🤷 Hết hạn!", ephemeral=True)
                return

            # Load both players
            guild = interaction.guild
            challenger = guild.get_member(int(self.challenger_sid)) or await guild.fetch_member(int(self.challenger_sid))
            target_m = guild.get_member(int(self.target_sid)) or await guild.fetch_member(int(self.target_sid))
            if challenger:
                await sync_role_mult(db, self.challenger_sid, [r.name for r in challenger.roles])
            if target_m:
                await sync_role_mult(db, self.target_sid, [r.name for r in target_m.roles])

            p1_cursor = await db.execute("SELECT * FROM players WHERE id = ?", (self.challenger_sid,))
            p1_row = await p1_cursor.fetchone()
            p2_cursor = await db.execute("SELECT * FROM players WHERE id = ?", (self.target_sid,))
            p2_row = await p2_cursor.fetchone()
            if not p1_row or not p2_row:
                await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
                await db.commit()
                await interaction.followup.send("❌ Lỗi data!", ephemeral=True)
                return

            p1 = dict(p1_row)
            p2 = dict(p2_row)

            # Load skill slots
            for pid, pdata in [(self.challenger_sid, p1), (self.target_sid, p2)]:
                slots_cursor = await db.execute("SELECT slot, skill_id FROM player_skill_slots WHERE player_id=?", (pid,))
                slots = {}
                async for row in slots_cursor:
                    slots[row[0]] = row[1]
                pdata["skill_equipped"] = slots if slots else {"attack": 1, "special": 5, "defense": 10, "passive": 14}
                eq_cursor = await db.execute(
                    "SELECT id, item_id, enhance FROM player_equipment WHERE player_id=? AND equipped=1", (pid,))
                equipped = {}
                equip_items = {}
                equip_enhances = {}
                async for erow in eq_cursor:
                    eq_id = erow[0]
                    eiid = erow[1]
                    enh = erow[2]
                    slot = None
                    if eiid in EQUIPMENT:
                        slot = EQUIPMENT[eiid]["slot"]
                    elif eiid in SHOP_ITEMS and SHOP_ITEMS[eiid]["type"] == "equipment":
                        slot = SHOP_ITEMS[eiid]["slot"]
                    if slot:
                        equipped[slot] = eq_id
                        equip_items[str(eq_id)] = eiid
                        equip_enhances[str(eq_id)] = enh
                pdata["equipped"] = equipped
                pdata["_equip_items"] = equip_items
                pdata["_equip_enhances"] = equip_enhances
                buff_cursor = await db.execute("SELECT * FROM player_buffs WHERE player_id=?", (pid,))
                buff_row = await buff_cursor.fetchone()
                pdata["buffs"] = dict(buff_row) if buff_row else {}
                pdata["damage_dealt"] = pdata.get("damage_dealt", 0)
                pdata["damage_taken"] = pdata.get("damage_taken", 0)

            # Regen HP, clear cooldowns
            now = time.time()
            for p in [p1, p2]:
                regen_hp(p, now)
                p["attack_cd"] = 0
                p["special_cd"] = 0
                p["defense_cd"] = 0
                for k in ["_burn", "_shield_hp", "_shield_pop_heal", "_counter", "_counter_immune", "_rage_dmg", "_def_reduced"]:
                    p.pop(k, None)

            if p1["hp"] <= 0 or p2["hp"] <= 0:
                name = p1.get("name", "?") if p1["hp"] <= 0 else p2.get("name", "?")
                await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
                await db.commit()
                await interaction.followup.send(f"💀 **{name}** 0 máu!", ephemeral=True)
                return

            # Save regen'd HP + cleared cooldowns
            for p in [p1, p2]:
                await db.execute("UPDATE players SET hp=?, last_hp_update=?, attack_cd=0, special_cd=0, defense_cd=0 WHERE id=?",
                                 (p["hp"], p.get("last_hp_update", now), p["id"]))

            eff1 = get_effective_stats(p1)
            eff2 = get_effective_stats(p2)
            spd1 = eff1.get("spd", 0)
            spd2 = eff2.get("spd", 0)

            if spd1 > spd2:
                first = self.challenger_sid
            elif spd2 > spd1:
                first = self.target_sid
            else:
                first = self.challenger_sid if random.random() < 0.5 else self.target_sid

            # Reset cooldowns for both players at battle start
            await db.execute("UPDATE players SET attack_cd=0, special_cd=0, defense_cd=0 WHERE id=? OR id=?",
                             (self.challenger_sid, self.target_sid))

            ts = time.time()
            cursor = await db.execute("""INSERT INTO active_battles (player1_id, player2_id, turn, channel_id, last_move)
                                VALUES (?, ?, ?, ?, ?)""",
                              (self.challenger_sid, self.target_sid, first, str(self.channel_id), ts))
            battle_id = cursor.lastrowid

            # Only delete challenge AFTER battle is successfully created
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            await db.commit()

            # Build embed
            turn_user = challenger if first == self.challenger_sid else target_m

            from bot.data.classes import CLASSES
            from bot.views.battle_view import BattleView, get_skill_labels

            cls1 = CLASSES.get(p1.get("class_id", "banxabong"), CLASSES["banxabong"])
            cls2 = CLASSES.get(p2.get("class_id", "banxabong"), CLASSES["banxabong"])

            first_player = p1 if first == self.challenger_sid else p2
            skill_labels = get_skill_labels(first_player)

            embed = discord.Embed(
                title="⚔️ TRẬN CHIẾN BẮT ĐẦU!",
                color=0xff6600,
                description=(
                    f"### {cls1['icon']} {challenger.display_name}  ⚔️  {cls2['icon']} {target_m.display_name}\n"
                    f"─────────────────────\n"
                    f"❤️ **{challenger.display_name}** `{p1['hp']}/{eff1['hp_max']}` {hp_bar(p1['hp'], eff1['hp_max'], 8)}\n"
                    f"❤️ **{target_m.display_name}** `{p2['hp']}/{eff2['hp_max']}` {hp_bar(p2['hp'], eff2['hp_max'], 8)}\n"
                    f"─────────────────────\n"
                    f"🎯 **{turn_user.display_name}** đi trước!"
                )
            )
            view = BattleView(self.bot, battle_id, first, turn_user.display_name, skill_labels)
            await interaction.edit_original_response(embed=embed, view=view)
            view.start_countdown()
        except Exception as e:
            print(f"[CHALLENGE ERROR] {e}")
            try:
                await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)
            except:
                pass
        finally:
            await db.close()

    async def _do_deny(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = await get_db()
        try:
            cursor = await db.execute("SELECT 1 FROM challenges WHERE target_id = ?", (self.target_sid,))
            if not await cursor.fetchone():
                await interaction.followup.send("🤷 Hết hạn!", ephemeral=True)
                return
            await db.execute("DELETE FROM challenges WHERE target_id = ?", (self.target_sid,))
            await db.execute("UPDATE players SET coins = MAX(0, coins - 20) WHERE id = ?", (self.target_sid,))
            await db.commit()
            embed = discord.Embed(
                title="🏃 NHÁT! 💸",
                color=0x888888,
                description=f"**{self.target_name}** từ chối **{self.challenger_name}**! -20🪙!"
            )
            await interaction.edit_original_response(embed=embed, view=None)
        finally:
            await db.close()
