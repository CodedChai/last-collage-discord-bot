import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from services.lastfm_service import fetch_top_tracks, fetch_top_albums
from services.collage_service import generate_collage


class CollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-collage")
    @app_commands.describe(username="The Last.fm username to create a collage for")
    async def create_collage(self, interaction: discord.Interaction, username: str):
        await interaction.response.send_message(
            f"Creating collage for {username}. Please wait a moment.", ephemeral=True
        )
        top_tracks, top_albums = await asyncio.gather(
            fetch_top_tracks(self.bot.session, username),
            fetch_top_albums(self.bot.session, username),
        )

        if not top_albums or not top_albums.albums:
            await interaction.followup.send(
                "No data found for that user. Please ensure scrobbling is enabled for https://last.fm",
                ephemeral=True,
            )
            return

        buffer = await generate_collage(self.bot.session, top_albums.albums)

        # Build top 5 lists
        top_5_albums = "\n".join(
            f"{i + 1}. **{album.artist} - {album.name}** ({album.playcount} plays)"
            for i, album in enumerate(top_albums.albums[:5])
        )
        top_5_tracks = "\n".join(
            f"{i + 1}. **{track.artist} - {track.name}** ({track.playcount} plays)"
            for i, track in enumerate(top_tracks.tracks[:5])
        )

        message = (
            f"**Top 5 Albums:**\n{top_5_albums}\n\n**Top 5 Tracks:**\n{top_5_tracks}"
        )

        await interaction.followup.send(
            content=message, file=discord.File(buffer, filename="collage.png")
        )
