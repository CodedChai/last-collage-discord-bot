import asyncio
import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from services.lastfm_service import fetch_top_tracks, fetch_top_albums
from services.collage_service import generate_collage

logger = logging.getLogger("lastfm_collage_bot.collage_cog")


class CollageModal(discord.ui.Modal, title="Create Collage"):
    username = discord.ui.TextInput(
        label="Last.fm Username",
        placeholder="Enter your Last.fm username...",
    )

    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        username = self.username.value
        logger.info(
            f"Collage creation requested for user: {username} by {interaction.user}"
        )

        await interaction.response.send_message(
            f"Creating collage for {username}. Please wait a moment.",
            ephemeral=True,
        )

        try:
            top_tracks, top_albums = await asyncio.gather(
                fetch_top_tracks(self.session, username),
                fetch_top_albums(self.session, username),
            )

            if not top_albums or not top_albums.albums:
                logger.warning(f"No data found for Last.fm user: {username}")
                await interaction.followup.send(
                    "No data found for that user. Please ensure scrobbling is enabled for https://last.fm",
                    ephemeral=True,
                )
                return

            buffer = await generate_collage(self.session, top_albums.albums)

            top_5_tracks = "\n".join(
                f"{i + 1}. **{track.artist} - {track.name}** ({track.playcount} plays)"
                for i, track in enumerate(top_tracks.tracks[:5])
            )

            message = f"{username}'s collage\n\n**Top 5 Tracks:**\n{top_5_tracks}"

            await interaction.followup.send(
                content=message, file=discord.File(buffer, filename="collage.png")
            )
            logger.info(f"Successfully created collage for {username}")

        except Exception as e:
            logger.error(f"Error creating collage for {username}: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "An error occurred while creating the collage. Please try again later.",
                    ephemeral=True,
                )
            except:
                pass

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message(
            "Oops! Something went wrong.", ephemeral=True
        )
        traceback.print_exception(type(error), error, error.__traceback__)


class CollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-collage")
    async def create_collage(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CollageModal(self.bot.session))
