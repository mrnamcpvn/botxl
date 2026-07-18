import discord
from discord import app_commands
from discord.ext import commands
import random
import copy
from bot.database import get_db
from bot.data.wives import WIVES, RARITY_WEIGHTS, RARITY_COLOR, RARITY_STARS, GACHA_COST_FIRST, GACHA_COST, MAX_EQUIPPED
from bot.data.classes import CLASSES
from bot.engine.battle import get_effective_stats


def _parse_wife_row(row) -> dict:
    d = dict(row)
    d["wife_data"] = WIVES.get(d.get("wife_id", 1), WIVES[1])
    return d


def _wife_stats(w: dict) -> dict:
    pdata = {
        "class_id": w.get("class_id", "banxabong"),
        "level": w.get("level", 1),
        "upgrade_hp": 0, "upgrade_atk": 0, "upgrade_def": 0,
        "equipped": {}, "skill_equipped": {},
        "role_mult": 1.0,
    }
    return get_effective_stats(pdata)


class WaifuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="waifu_equip", aliases=["vequip", "vo_equip"])
    async def waifu_equip_cmd(self, ctx, wife_dbid: str = None):
        await self._equip_waifu(ctx, str(ctx.author.id), wife_dbid, ctx.author.display_name, "!")

    @app_commands.command(name="waifu_equip", description="💍 Mang Vợ ra trận")
    @app_commands.describe(wife_dbid="ID vợ (xem /waifu)")
    async def slash_waifu_equip(self, interaction: discord.Interaction, wife_dbid: str):
        await self._equip_waifu(interaction, str(interaction.user.id), wife_dbid, interaction.user.display_name, "/")

    async def _equip_waifu(self, ctx_or_int, sid: str, wife_dbid: str, display_name: str, prefix: str):
        if not wife_dbid:
            msg = f"❌ `{prefix}waifu equip <id>` — ID vợ ở `{prefix}waifu`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        try:
            dbid = int(wife_dbid)
        except:
            msg = "❌ ID không hợp lệ!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM player_wives WHERE id=? AND player_id=?", (dbid, sid))
            row = await cursor.fetchone()
            if not row:
                msg = f"🤷 Không có vợ ID `{dbid}`! Xem `{prefix}waifu`"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            w = _parse_wife_row(row)
            currently_equipped = w["equipped"]

            if currently_equipped:
                await db.execute("UPDATE player_wives SET equipped=0 WHERE id=? AND player_id=?", (dbid, sid))
                await db.commit()
                msg = f"💔 Đã cất **{w['wife_data']['emoji']} {w['wife_data']['name']}** vào kho!"
            else:
                cnt_cursor = await db.execute("SELECT COUNT(*) FROM player_wives WHERE player_id=? AND equipped=1", (sid,))
                cnt_row = await cnt_cursor.fetchone()
                if cnt_row[0] >= MAX_EQUIPPED:
                    msg = f"😅 Tối đa {MAX_EQUIPPED} vợ ra trận! Cất bớt đi."
                else:
                    await db.execute("UPDATE player_wives SET equipped=1 WHERE id=? AND player_id=?", (dbid, sid))
                    await db.commit()
                    msg = f"💍 Đã mang **{w['wife_data']['emoji']} {w['wife_data']['name']}** ra trận!"

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg)
        finally:
            await db.close()

    @commands.command(name="waifu", aliases=["gacha", "vo"])
    async def waifu_cmd(self, ctx, *, args: str = ""):
        parts = args.strip().split()
        action = parts[0].lower() if parts else ""
        rest = parts[1:] if len(parts) > 1 else []

        if not action:
            await self._show_waifus(ctx, str(ctx.author.id), "!")
            return
        if action == "pull":
            await self._gacha_pull(ctx, str(ctx.author.id), ctx.author.display_name, "!")
        elif action == "equip" and rest:
            await self._equip_waifu(ctx, str(ctx.author.id), rest[0], ctx.author.display_name, "!")
        elif action == "delete" and rest:
            await self._delete_waifu(ctx, str(ctx.author.id), rest[0], "!")
        elif action == "trade" and len(rest) >= 2:
            try:
                member = await commands.MemberConverter().convert(ctx, rest[0])
                await self._trade_waifu(ctx, str(ctx.author.id), member, rest[1], ctx.author.display_name, "!")
            except:
                await ctx.reply("❌ Không tìm thấy player! `!waifu trade @player <id>`")
        else:
            await ctx.reply("❌ !waifu | !waifu pull | !waifu trade @player <id> | !waifu equip <id> | !waifu delete <id>")

    @app_commands.command(name="waifu", description="💕 Quản lý Vợ")
    async def slash_waifu(self, interaction: discord.Interaction):
        await self._show_waifus(interaction, str(interaction.user.id), "/")

    @app_commands.command(name="gacha", description="🎰 Quay Vợ (lần đầu free)")
    async def slash_gacha(self, interaction: discord.Interaction):
        await self._gacha_pull(interaction, str(interaction.user.id), interaction.user.display_name, "/")

    @commands.command(name="waifu_delete", aliases=["wdelete", "vo_xoa"])
    async def waifu_delete_cmd(self, ctx, wife_dbid: str = None):
        await self._delete_waifu(ctx, str(ctx.author.id), wife_dbid, "!")

    @app_commands.command(name="waifu_delete", description="🗑️ Xóa Vợ")
    @app_commands.describe(wife_dbid="ID vợ (xem /waifu)")
    async def slash_waifu_delete(self, interaction: discord.Interaction, wife_dbid: str):
        await self._delete_waifu(interaction, str(interaction.user.id), wife_dbid, "/")

    async def _delete_waifu(self, ctx_or_int, sid: str, wife_dbid: str, prefix: str):
        if not wife_dbid:
            msg = f"❌ `{prefix}waifu delete <id>`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        try:
            dbid = int(wife_dbid)
        except:
            msg = "❌ ID không hợp lệ!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM player_wives WHERE id=? AND player_id=?", (dbid, sid))
            row = await cursor.fetchone()
            if not row:
                msg = f"🤷 Không có vợ ID `{dbid}`!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return
            w = _parse_wife_row(row)
            wd = w["wife_data"]
            await db.execute("DELETE FROM player_wives WHERE id=? AND player_id=?", (dbid, sid))
            await db.commit()
            msg = f"🗑️ Đã chia tay **{wd['emoji']} {wd['name']}**! 💔"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg)
        finally:
            await db.close()

    @commands.command(name="waifu_trade", aliases=["wtrade", "vo_trade"])
    async def waifu_trade_cmd(self, ctx, member: discord.Member = None, wife_dbid: str = None):
        await self._trade_waifu(ctx, str(ctx.author.id), member, wife_dbid, ctx.author.display_name, "!")

    @app_commands.command(name="waifu_trade", description="🤝 Tặng Vợ cho người khác")
    @app_commands.describe(member="Người nhận", wife_dbid="ID vợ (xem /waifu)")
    async def slash_waifu_trade(self, interaction: discord.Interaction, member: discord.Member, wife_dbid: str):
        await self._trade_waifu(interaction, str(interaction.user.id), member, wife_dbid, interaction.user.display_name, "/")

    async def _trade_waifu(self, ctx_or_int, sid: str, member, wife_dbid: str, sender_name: str, prefix: str):
        if not member or not wife_dbid:
            msg = f"❌ `{prefix}waifu trade @player <id>`"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        if str(member.id) == sid:
            msg = "🤡 Tự tặng mình?"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return
        try:
            dbid = int(wife_dbid)
        except:
            msg = "❌ ID không hợp lệ!"
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.reply(msg)
            else:
                await ctx_or_int.response.send_message(msg, ephemeral=True)
            return

        rid = str(member.id)
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM player_wives WHERE id=? AND player_id=?", (dbid, sid))
            row = await cursor.fetchone()
            if not row:
                msg = f"🤷 Không có vợ ID `{dbid}`!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return
            w = _parse_wife_row(row)
            wd = w["wife_data"]

            recv_cursor = await db.execute("SELECT 1 FROM players WHERE id=?", (rid,))
            if not await recv_cursor.fetchone():
                msg = f"🤷 {member.display_name} chưa đăng ký!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            # Send trade offer with accept/deny buttons
            ch_id = ctx_or_int.channel.id if hasattr(ctx_or_int, 'channel') else ctx_or_int.channel_id
            from bot.views.trade_view import TradeView
            embed = discord.Embed(
                title="🤝 GIAO DỊCH VỢ",
                color=0xff69b4,
                description=(
                    f"**{sender_name}** muốn tặng vợ cho **{member.display_name}**!\n\n"
                    f"### {wd['emoji']} {wd['name']}\n"
                    f"⭐ {wd['rarity']} | Lv.{w['level']}\n"
                    f"*{wd['desc']}*\n\n"
                    f"<@{member.id}> bấm ✅ Nhận hoặc ❌ Từ Chối! ⏰ 60s"
                )
            )
            view = TradeView(self.bot, rid, sid, "wife", sender_name, member.display_name,
                             ch_id, {"wife_dbid": dbid})
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.send(embed=embed, view=view)
            else:
                await ctx_or_int.response.send_message(embed=embed, view=view)
        finally:
            await db.close()

    async def _show_waifus(self, ctx_or_int, sid: str, prefix: str):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM player_wives WHERE player_id=? ORDER BY equipped DESC, id ASC", (sid,))
            rows = await cursor.fetchall()
            wives = [_parse_wife_row(r) for r in rows]

            if not wives:
                msg = f"💕 Chưa có Vợ nào! Dùng `{prefix}gacha` để quay (lần đầu free)!"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            embed = discord.Embed(title=f"💕 HAREM CỦA {ctx_or_int.author.display_name if hasattr(ctx_or_int, 'author') else ctx_or_int.user.display_name}",
                                  color=0xff69b4)
            embed.set_footer(text=f"👥 {len(wives)} vợ | Dùng {prefix}waifu equip <id> | Tối đa {MAX_EQUIPPED} vợ ra trận")

            # Thumbnail = vợ đầu tiên có ảnh
            for w in wives:
                img = w["wife_data"].get("image_url", "")
                if img:
                    embed.set_thumbnail(url=img)
                    break

            for w in wives:
                wd = w["wife_data"]
                stars = RARITY_STARS.get(wd["rarity"], "⭐")
                cls = CLASSES.get(w.get("class_id", "banxabong"), CLASSES["banxabong"])
                eq = "💍 ĐANG MANG" if w["equipped"] else ""
                s = _wife_stats(w)
                embed.add_field(
                    name=f"{'💍' if w['equipped'] else '  '} `{w['id']}` {wd['emoji']} **{wd['name']}** {stars} {cls['icon']}",
                    value=f"❤️ `{s['hp_max']}` ⚔️ `{s['attack_min']}-{s['attack_max']}` 🛡️ `{s['defense']}` | Lv.{w['level']} XP:`{w['xp']}/{w['level']*50}`\n{w['equipped'] and eq or ''}",
                    inline=False)

            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.send(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)
        finally:
            await db.close()

    async def _gacha_pull(self, ctx_or_int, sid: str, display_name: str, prefix: str):
        db = await get_db()
        try:
            cursor = await db.execute("SELECT role_mult, coins FROM players WHERE id=?", (sid,))
            row = await cursor.fetchone()
            if not row:
                msg = f"🤷 Đăng ký trước đi! `{prefix}register`"
                if isinstance(ctx_or_int, commands.Context):
                    await ctx_or_int.reply(msg)
                else:
                    await ctx_or_int.response.send_message(msg, ephemeral=True)
                return

            role_mult = row[0] if row[0] else 1.0
            coins = row[1]

            cnt_cursor = await db.execute("SELECT COUNT(*) FROM player_wives WHERE player_id=?", (sid,))
            cnt_row = await cnt_cursor.fetchone()
            is_first = cnt_row[0] == 0

            if is_first:
                cost = GACHA_COST_FIRST
            else:
                cost = GACHA_COST
                if coins < cost:
                    msg = f"😅 Cần {cost}🪙, có {coins}🪙"
                    if isinstance(ctx_or_int, commands.Context):
                        await ctx_or_int.reply(msg)
                    else:
                        await ctx_or_int.response.send_message(msg, ephemeral=True)
                    return

            # Apply role multiplier to luck
            adjusted_weights = {}
            for rarity, weight in RARITY_WEIGHTS.items():
                if rarity in ("S", "SVIP"):
                    adjusted_weights[rarity] = int(weight * role_mult)
                else:
                    adjusted_weights[rarity] = weight

            pool = []
            for rarity, w in adjusted_weights.items():
                pool.extend([rarity] * w)

            rolled_rarity = random.choice(pool)
            candidates = [w for wid, w in WIVES.items() if w["rarity"] == rolled_rarity]
            wife = random.choice(candidates)

            # Find wife_id
            wife_id = 1
            for wid, w in WIVES.items():
                if w["name"] == wife["name"]:
                    wife_id = wid
                    break

            # Random class
            class_id = random.choice([c for c in CLASSES.keys() if not CLASSES[c].get("admin_only")])

            await db.execute("INSERT INTO player_wives (player_id, wife_id, class_id) VALUES (?, ?, ?)",
                              (sid, wife_id, class_id))
            if cost > 0:
                await db.execute("UPDATE players SET coins=coins-? WHERE id=?", (cost, sid))
            await db.commit()

            stars = RARITY_STARS.get(wife["rarity"], "⭐")
            color = RARITY_COLOR.get(wife["rarity"], 0xff69b4)
            cls = CLASSES.get(class_id, CLASSES["banxabong"])

            embed = discord.Embed(
                title="🎰 GACHA!",
                color=color,
                description=(
                    f"**{display_name}** quay được...\n\n"
                    f"# {wife['emoji']} {wife['name']}\n"
                    f"### {stars} {wife['rarity']}\n"
                    f"*{wife['full']}*\n"
                    f"{wife['desc']}\n\n"
                    f"🎭 Class: {cls['icon']} {cls['name']}\n"
                    f"{'🆓 FREE PULL!' if is_first else f'💰 -{cost}🪙 | Còn {coins - cost}🪙'}"
                )
            )
            if wife.get("image_url"):
                embed.set_thumbnail(url=wife["image_url"])
            if isinstance(ctx_or_int, commands.Context):
                await ctx_or_int.send(embed=embed)
            else:
                await ctx_or_int.response.send_message(embed=embed)
        finally:
            await db.close()


async def setup(bot):
    await bot.add_cog(WaifuCog(bot))
