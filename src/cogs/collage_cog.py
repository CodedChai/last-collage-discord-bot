import asyncio
import datetime
import logging
import traceback
from urllib.parse import quote_plus

import discord
from discord import app_commands, ui
from discord.ext import commands
from services.lastfm_service import fetch_top_tracks, fetch_top_albums, LastFmError
from services.collage_service import generate_collage

logger = logging.getLogger("lastfm_collage_bot.collage_cog")

EMBED_COLOR = 0x1DB954

PERIOD_LABELS = {
    "7day": "7 Days",
    "1month": "1 Month",
    "3month": "3 Months",
    "6month": "6 Months",
    "12month": "12 Months",
    "overall": "Overall",
}

PERIOD_OPTIONS = [
    discord.SelectOption(label="7 Days", value="7day", default=True),
    discord.SelectOption(label="1 Month", value="1month"),
    discord.SelectOption(label="3 Months", value="3month"),
    discord.SelectOption(label="6 Months", value="6month"),
    discord.SelectOption(label="12 Months", value="12month"),
    discord.SelectOption(label="Overall", value="overall"),
]

GRID_SIZE_OPTIONS = [
    discord.SelectOption(label="2x2", value="2"),
    discord.SelectOption(label="3x3", value="3", default=True),
    discord.SelectOption(label="4x4", value="4"),
    discord.SelectOption(label="5x5", value="5"),
]


class CollageModal(discord.ui.Modal, title="Create Collage"):
    username = ui.Label(
        text="Last.fm Username",
        component=ui.TextInput(placeholder="Enter your Last.fm username..."),
    )
    period = ui.Label(
        text="Time Period",
        component=ui.Select(options=PERIOD_OPTIONS),
    )
    grid_size = ui.Label(
        text="Grid Size",
        component=ui.Select(options=GRID_SIZE_OPTIONS),
    )

    def __init__(self, session):
        super().__init__()
        self.session = session

    async def on_submit(self, interaction: discord.Interaction):
        username_val = self.username.component.value
        period_val = self.period.component.values[0]
        grid_size_val = int(self.grid_size.component.values[0])

        logger.info(
            f"Collage creation requested for user: {username_val}, period: {period_val}, "
            f"grid: {grid_size_val}x{grid_size_val} by {interaction.user}"
        )

        await interaction.response.send_message(
            f"Creating collage for {username_val}. Please wait a moment.",
            ephemeral=True,
        )

        try:
            top_tracks, top_albums = await asyncio.gather(
                fetch_top_tracks(self.session, username_val, period_val),
                fetch_top_albums(self.session, username_val, period_val),
            )

            has_albums = top_albums and top_albums.albums
            has_tracks = top_tracks and top_tracks.tracks

            if not has_albums and not has_tracks:
                logger.warning(f"No data found for Last.fm user: {username_val}")
                await interaction.followup.send(
                    "No data found for that user. Please ensure scrobbling is enabled for https://last.fm",
                    ephemeral=True,
                )
                return

            if has_tracks:
                top_5_tracks = "\n".join(
                    f"{i + 1}. [{track.artist} - {track.name}]"
                    f"(https://www.youtube.com/results?search_query={quote_plus(f'{track.artist} {track.name}')})"
                    f" ({track.playcount} plays)"
                    for i, track in enumerate(top_tracks.tracks[:5])
                )
                description = f"**Top 5 Tracks:**\n{top_5_tracks}"
            else:
                description = "*No tracks found for this period.*"

            period_label = PERIOD_LABELS.get(period_val, period_val)
            embed = discord.Embed(
                title=f"{username_val}'s collage",
                description=description,
                color=EMBED_COLOR,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_footer(text=f"Period: {period_label}")

            if has_albums:
                buffer = await generate_collage(self.session, top_albums.albums, grid_size_val)
                embed.set_image(url="attachment://collage.png")
                await interaction.followup.send(
                    embed=embed, file=discord.File(buffer, filename="collage.png")
                )
            else:
                await interaction.followup.send(embed=embed)
            logger.info(f"Successfully created collage for {username_val}")

        except LastFmError as e:
            logger.warning(f"Last.fm API error for {username_val}: {e.message} (code {e.code})")
            await interaction.followup.send(e.message, ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating collage for {username_val}: {e}", exc_info=True)
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
