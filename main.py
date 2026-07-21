import discord
from discord.ext import commands
from bot.config import TOKEN
from bot.logger import logger
from bot.database import init_db
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f"[ONLINE] {bot.user} đã lên đồ!")
    logger.info(f"Server: {len(bot.guilds)} servers")
    for guild in bot.guilds:
        logger.info(f"  - {guild.name} ({guild.id})")
    await asyncio.sleep(3)
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"[SLASH] {guild.name}: {len(synced)} commands synced")
        except Exception as e:
            logger.error(f"[SLASH] {guild.name}: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.reply("🚫 Mày hông đủ quyền để xài vụ này!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"⚠️ Thiếu argument rồi ku! Gõ `!help` để xem hướng dẫn.")
    else:
        await ctx.reply(f"❌ Lỗi: {error}")
        logger.error(f"Command error: {error}", exc_info=True)

async def load_extensions():
    await bot.load_extension("bot.cogs.arena")
    await bot.load_extension("bot.cogs.shop")
    await bot.load_extension("bot.cogs.admin")
    await bot.load_extension("bot.cogs.npc")
    await bot.load_extension("bot.cogs.waifu")
    await bot.load_extension("bot.cogs.trade")
    await bot.load_extension("bot.cogs.enhance")
    await bot.load_extension("bot.cogs.dungeon")
    await bot.load_extension("bot.cogs.thankhi")
    await bot.load_extension("bot.cogs.quiz")
    await bot.load_extension("bot.cogs.quest")
    await bot.load_extension("bot.cogs.arena_tournament")
    await bot.load_extension("bot.cogs.arena_tournament")

async def main():
    await init_db()
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
