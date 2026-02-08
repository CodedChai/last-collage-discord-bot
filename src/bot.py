import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import aiohttp

from cogs.collage_cog import CollageCog

load_dotenv()


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        await self.add_cog(CollageCog(self))
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} command(s)")

    async def on_ready(self):
        print(f"We have logged in as {self.user}")

    async def close(self):
        await self.session.close()
        await super().close()


if __name__ == "__main__":
    bot = Bot()
    asyncio.run(bot.start(os.getenv("LAST_FM_DISCORD_TOKEN")))
