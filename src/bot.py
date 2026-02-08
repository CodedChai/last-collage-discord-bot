import discord
from dotenv import load_dotenv
import os
from discord.ext import commands

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


async def main():
    await bot.load_extension("cogs.collage_cog")
    await bot.start(os.getenv("LAST_FM_DISCORD_TOKEN"))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
