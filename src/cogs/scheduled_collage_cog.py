import asyncio
import datetime
import logging
import traceback
from collections import defaultdict
from zoneinfo import ZoneInfo

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from pydantic import ValidationError
from models import WeeklyJoinRequest, WeeklySchedule, UserPreference
from services.db_service import (
    save_weekly_schedule,
    get_all_weekly_schedules,
    get_lastfm_username,
    save_user_preference,
    get_weekly_subscriber_count,
)
from services.lastfm_service import (
    fetch_top_artists,
    fetch_top_albums,
    fetch_top_tracks,
)
from services.summary_service import (
    extract_listening_data,
    compute_group_summary,
    format_summary_text,
)
from cogs.messaging import send_collage_from_data
from utils.embed_utils import EMBED_COLOR

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
        try:
            request = WeeklyJoinRequest(
                username=self.username.value,
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                discord_user_id=interaction.user.id,
            )
        except ValidationError as e:
            error_msg = e.errors()[0]["msg"] if e.errors() else "Invalid input."
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        await save_weekly_schedule(
            WeeklySchedule(
                lastfm_username=request.username,
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                discord_user_id=request.discord_user_id,
            )
        )
        await save_user_preference(
            UserPreference(
                discord_user_id=interaction.user.id, lastfm_username=request.username
            )
        )
        count = await get_weekly_subscriber_count(self.guild_id, self.channel_id)
        await interaction.response.send_message(
            f"✅ Welcome! Every Monday at 9 AM CT, a 7-day collage for **{request.username}** will be posted in this channel.",
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

    @app_commands.command(
        name="join-weekly-collage",
        description="Join the weekly collage schedule for this channel",
    )
    @app_commands.guild_only()
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

        channels: dict[tuple[int, int], list[WeeklySchedule]] = defaultdict(list)
        for schedule in schedules:
            channels[(schedule.guild_id, schedule.channel_id)].append(schedule)

        for (guild_id, channel_id), channel_schedules in channels.items():
            await self._post_channel_collages(guild_id, channel_id, channel_schedules)

    async def _post_channel_collages(
        self, guild_id: int, channel_id: int, schedules: list[WeeklySchedule]
    ):
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        user_data_list = []

        for schedule in schedules:
            try:
                _, listening_data = await self._post_single_collage(
                    guild, channel, schedule
                )
                if listening_data is not None:
                    user_data_list.append(listening_data)
            except Exception:
                logger.error(
                    f"Error posting weekly collage for {schedule.lastfm_username}",
                    exc_info=True,
                )
                continue

        if len(user_data_list) >= 2:
            summary = compute_group_summary(user_data_list)
            text = format_summary_text(summary)
            embed = discord.Embed(
                title="Weekly Group Summary",
                description=text,
                color=EMBED_COLOR,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_footer(text=f"{summary.user_count} participants this week")
            await channel.send(embed=embed)

    async def _post_single_collage(self, guild, channel, schedule):
        member = None
        try:
            member = await guild.fetch_member(schedule.discord_user_id)
        except Exception:
            pass
        display_name = member.display_name if member else schedule.lastfm_username

        top_artists, top_albums, top_tracks = await asyncio.gather(
            fetch_top_artists(self.bot.session, schedule.lastfm_username, "7day"),
            fetch_top_albums(self.bot.session, schedule.lastfm_username, "7day"),
            fetch_top_tracks(self.bot.session, schedule.lastfm_username, "7day"),
        )

        title = f"{display_name}'s Weekly Collage"
        has_albums = top_albums and top_albums.albums
        has_tracks = top_tracks and top_tracks.tracks

        if has_albums or has_tracks:
            await send_collage_from_data(
                channel, self.bot.session, title, top_tracks, top_albums
            )

        listening_data = extract_listening_data(
            display_name, top_artists, top_albums, top_tracks
        )

        logger.info(
            f"Posted weekly collage for {schedule.lastfm_username} in guild {guild.id}"
        )
        return display_name, listening_data

    @post_weekly_collages.before_loop
    async def before_post_weekly_collages(self):
        await self.bot.wait_until_ready()
