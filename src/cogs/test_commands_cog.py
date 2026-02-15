"""Test commands for development and debugging."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from services.db_service import get_all_weekly_schedules
from services.summary_service import (
    UserListeningData,
    compute_group_summary,
)
from formatters.summary_formatter import format_summary_text
from services.weekly_collage_service import (
    fetch_user_listening_data,
    fetch_member_safe,
    get_display_name,
)

logger = logging.getLogger("lastfm_collage_bot.test_commands_cog")


async def fetch_all_users_data(
    bot,
    schedules: list,
    guild: discord.Guild,
) -> list[UserListeningData]:
    user_data_list = []

    for schedule in schedules:
        try:
            member = await fetch_member_safe(guild, schedule.discord_user_id)
            display_name = get_display_name(member, schedule.lastfm_username)

            listening_data = await fetch_user_listening_data(
                bot.session, schedule.lastfm_username, display_name
            )
            user_data_list.append(listening_data)

        except Exception:
            logger.error(
                f"Error fetching data for {schedule.lastfm_username}",
                exc_info=True,
            )
            continue

    return user_data_list


class TestCommandsCog(commands.Cog):
    """Development and testing commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="test-weekly-summary",
        description="[TEST] Preview weekly summary for this channel (ephemeral)",
    )
    @app_commands.guild_only()
    async def test_weekly_summary(self, interaction: discord.Interaction):
        """Test command to preview weekly summary without posting to channel."""
        await interaction.response.defer(ephemeral=True)

        schedules = await get_all_weekly_schedules()
        channel_schedules = [
            s
            for s in schedules
            if s.guild_id == interaction.guild_id
            and s.channel_id == interaction.channel_id
        ]

        if not channel_schedules:
            await interaction.followup.send(
                "❌ No weekly schedules found for this channel. Use `/join-weekly-collage` first.",
                ephemeral=True,
            )
            return

        if len(channel_schedules) < 2:
            await interaction.followup.send(
                "⚠️ Need at least 2 users for a group summary. Only found 1 user.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"🔄 Fetching data for {len(channel_schedules)} user(s)...", ephemeral=True
        )

        try:
            guild = self.bot.get_guild(interaction.guild_id)
            user_data_list = await fetch_all_users_data(
                self.bot, channel_schedules, guild
            )

            if len(user_data_list) < 2:
                await interaction.followup.send(
                    "❌ Could not fetch data for enough users. Need at least 2 users with valid Last.fm data.",
                    ephemeral=True,
                )
                return

            summary = compute_group_summary(user_data_list)

            text = format_summary_text(summary)

            test_text = "**[TEST PREVIEW]**\n" + text

            await interaction.followup.send(test_text, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in test-weekly-summary: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error generating summary: {str(e)}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the cog."""
    await bot.add_cog(TestCommandsCog(bot))
