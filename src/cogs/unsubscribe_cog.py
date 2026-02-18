import logging

from discord import app_commands
from discord.ext import commands
from services.db_service import delete_weekly_schedule
from services.metrics_service import track_command

logger = logging.getLogger("lastfm_collage_bot.unsubscribe_cog")


class UnsubscribeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="unsubscribe-weekly-collage",
        description="Unsubscribe from the weekly collage schedule for this channel",
    )
    @app_commands.guild_only()
    @track_command("unsubscribe_weekly_collage")
    async def unsubscribe_weekly_collage(self, interaction):
        removed = await delete_weekly_schedule(
            interaction.user.id, interaction.guild_id
        )
        if removed:
            await interaction.response.send_message(
                "👋 You've been unsubscribed from the weekly collage. We'll miss you!",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Hmm, looks like you weren't subscribed to a weekly collage here. "
                "Use `/join-weekly-collage` if you'd like to get started!",
                ephemeral=True,
            )
