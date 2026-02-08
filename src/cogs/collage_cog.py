import discord
from discord import app_commands
from discord.ext import commands
from services.lastfm_service import fetch_top_tracks


class CollageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-collage")
    @app_commands.describe(username="The Last.fm username to create a collage for")
    async def create_collage(self, interaction: discord.Interaction, username: str):
        await interaction.response.send_message(f"Creating collage for {username}...")
        await fetch_top_tracks(username)
