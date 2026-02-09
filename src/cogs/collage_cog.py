import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands
from services.lastfm_service import fetch_top_tracks, fetch_top_albums
from services.collage_service import generate_collage

logger = logging.getLogger("lastfm_collage_bot.collage_cog")


class CollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-collage")
    @app_commands.describe(username="The Last.fm username to create a collage for")
    async def create_collage(self, interaction: discord.Interaction, username: str):
        logger.info(
            f"Collage creation requested for user: {username} by {interaction.user}"
        )

        try:
            await interaction.response.send_message(
                f"Creating collage for {username}. Please wait a moment.",
                ephemeral=True,
            )

            top_tracks, top_albums = await asyncio.gather(
                fetch_top_tracks(self.bot.session, username),
                fetch_top_albums(self.bot.session, username),
            )

            if not top_albums or not top_albums.albums:
                logger.warning(f"No data found for Last.fm user: {username}")
                await interaction.followup.send(
                    "No data found for that user. Please ensure scrobbling is enabled for https://last.fm",
                    ephemeral=True,
                )
                return

            buffer = await generate_collage(self.bot.session, top_albums.albums)

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
                pass  # Interaction may have already timed out
