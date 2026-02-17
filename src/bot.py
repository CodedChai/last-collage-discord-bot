import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

import aiohttp

from cogs.collage_cog import CollageCog
from cogs.scheduled_collage_cog import ScheduledCollageCog
from cogs.test_commands_cog import TestCommandsCog
from cogs.unsubscribe_cog import UnsubscribeCog
from cogs.view_collage_cog import ViewCollageCog
from services.db_service import init_db, close_db, get_scheduled_guild_ids
from services.collage_service import init_cache, close_cache
from services.metrics_service import start_metrics, ACTIVE_GUILDS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("lastfm_collage_bot")
logging.getLogger("opentelemetry").setLevel(logging.DEBUG)


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        start_metrics()
        await init_db()
        await init_cache()
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "LastFmCollageDiscordBot/1.0"},
            timeout=aiohttp.ClientTimeout(total=30, connect=10),
        )
        await self.add_cog(CollageCog(self))
        await self.add_cog(ScheduledCollageCog(self))
        await self.add_cog(TestCommandsCog(self))
        await self.add_cog(UnsubscribeCog(self))
        await self.add_cog(ViewCollageCog(self))
        synced = await self.tree.sync()
        logger.info(f"Synced {len(synced)} global command(s)")
        guild_ids = await get_scheduled_guild_ids()
        for guild_id in guild_ids:
            guild_synced = await self.tree.sync(guild=discord.Object(id=guild_id))
            logger.info(f"Synced {len(guild_synced)} command(s) to guild {guild_id}")

    async def on_ready(self):
        ACTIVE_GUILDS.set(len(self.guilds))
        logger.info(f"Bot ready: logged in as {self.user}")

    async def on_guild_join(self, guild):
        ACTIVE_GUILDS.inc()

    async def on_guild_remove(self, guild):
        ACTIVE_GUILDS.dec()

    async def close(self):
        await self.session.close()
        await close_cache()
        await close_db()
        await super().close()


if __name__ == "__main__":
    bot = Bot()
    asyncio.run(bot.start(os.getenv("LAST_FM_DISCORD_TOKEN")))
