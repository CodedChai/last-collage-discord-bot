import discord
from dotenv import load_dotenv
import os
from discord.ext import commands
from cogs.collage_cog import CollageCog

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
    await bot.add_cog(CollageCog(bot))
    await bot.start(os.getenv("LAST_FM_DISCORD_TOKEN"))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
