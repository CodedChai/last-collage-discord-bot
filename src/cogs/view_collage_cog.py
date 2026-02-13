import logging

from discord import app_commands
from discord.ext import commands
from services.db_service import get_weekly_schedules_for_channel

logger = logging.getLogger("lastfm_collage_bot.view_collage_cog")


class ViewCollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="view-weekly-collage")
    async def view_weekly_collage(self, interaction):
        usernames = await get_weekly_schedules_for_channel(
            interaction.guild_id, interaction.channel_id
        )
        if usernames:
            await interaction.response.send_message(
                f"Scheduled usernames for this channel: {', '.join(usernames)}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "No weekly collages scheduled for this channel.",
                ephemeral=True,
            )
