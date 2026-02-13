import asyncio
import datetime
import logging
import traceback
from zoneinfo import ZoneInfo

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from services.lastfm_service import fetch_top_tracks, fetch_top_albums
from services.collage_service import determine_dynamic_grid_size
from services.db_service import (
    save_weekly_schedule,
    get_all_weekly_schedules,
    get_lastfm_username,
    save_lastfm_username,
    get_weekly_subscriber_count,
)
from cogs.collage_utils import build_collage_embed, send_collage

logger = logging.getLogger("lastfm_collage_bot.scheduled_collage_cog")

CT = ZoneInfo("America/Chicago")


class ScheduleWeeklyModal(discord.ui.Modal, title="Join Weekly Collage"):
    username = ui.TextInput(
        label="Last.fm Username",
        placeholder="Enter your Last.fm username...",
    )

    def __init__(
        self, interaction: discord.Interaction, default_username: str | None = None
    ):
        super().__init__()
        self.guild_id = interaction.guild_id
        self.channel_id = interaction.channel_id
        if default_username:
            self.username.default = default_username

    async def on_submit(self, interaction: discord.Interaction):
        username_val = self.username.value
        await save_weekly_schedule(
            username_val, self.guild_id, self.channel_id, interaction.user.id
        )
        await save_lastfm_username(interaction.user.id, username_val)
        count = await get_weekly_subscriber_count(self.guild_id, self.channel_id)
        await interaction.response.send_message(
            f"✅ Welcome! Every Monday at 9 AM CT, a 7-day collage for **{username_val}** will be posted in this channel.",
            ephemeral=True,
        )
        await interaction.channel.send(
            f"🎶 **{interaction.user.display_name}** has joined the weekly jam! Now there are **{count}** participants. Want to join the fun? Use `/join-weekly-collage` to get your own weekly collage!"
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )
        traceback.print_exception(type(error), error, error.__traceback__)


class ScheduledCollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.post_weekly_collages.start()

    async def cog_unload(self):
        self.post_weekly_collages.cancel()

    @app_commands.command(name="join-weekly-collage")
    async def schedule_weekly_collage(self, interaction: discord.Interaction):
        cached_username = await get_lastfm_username(interaction.user.id)
        await interaction.response.send_modal(
            ScheduleWeeklyModal(interaction, default_username=cached_username)
        )

    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=CT))
    async def post_weekly_collages(self):
        now = datetime.datetime.now(CT)
        if now.weekday() != 0:
            return
        await self._post_weekly_collages()

    async def _post_weekly_collages(self):
        schedules = await get_all_weekly_schedules()
        for schedule in schedules:
            lastfm_username = schedule["lastfm_username"]
            guild_id = schedule["guild_id"]
            channel_id = schedule["channel_id"]
            discord_user_id = schedule["discord_user_id"]

            try:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue

                channel = guild.get_channel(channel_id)
                if channel is None:
                    continue

                member = None
                try:
                    member = await guild.fetch_member(discord_user_id)
                except Exception:
                    pass
                display_name = member.display_name if member else lastfm_username

                top_tracks, top_albums = await asyncio.gather(
                    fetch_top_tracks(self.bot.session, lastfm_username, "7day"),
                    fetch_top_albums(self.bot.session, lastfm_username, "7day"),
                )

                grid_size = (
                    determine_dynamic_grid_size(top_albums.albums)
                    if top_albums and top_albums.albums
                    else (1, 1)
                )

                embed = build_collage_embed(display_name, top_tracks, "7day")
                await send_collage(
                    channel, self.bot.session, embed, top_albums, grid_size
                )

                logger.info(
                    f"Posted weekly collage for {lastfm_username} in guild {guild_id}"
                )

            except Exception:
                logger.error(
                    f"Error posting weekly collage for {lastfm_username}",
                    exc_info=True,
                )
                continue

    @post_weekly_collages.before_loop
    async def before_post_weekly_collages(self):
        await self.bot.wait_until_ready()
