import discord
from dotenv import load_dotenv
import os
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
from models import WeeklyTrackChartModel

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = commands.Bot(command_prefix="!", intents=intents)
last_fm_api_key = os.getenv("LAST_FM_API_KEY")


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


# TODO: I'm pretty sure I'm not handling sessions properly
async def fetch_top_tracks(username: str):
    # TODO: Use params instead of f-strings for URL construction
    url = f"http://ws.audioscrobbler.com/2.0/?method=user.getweeklytrackchart&user={username}&api_key={last_fm_api_key}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                track_chart = WeeklyTrackChartModel.model_validate(data)
                print(f"Top tracks for {username}:")
                for track in track_chart.tracks:
                    print(
                        f"{track.rank}. {track.artist} - {track.name} (Playcount: {track.playcount})"
                    )
                return track_chart
            else:
                print(f"Failed to fetch top tracks for {username}: {response.status}")
                return []


@client.tree.command(name="create-collage")
@app_commands.describe(username="The Last.fm username to create a collage for")
async def create_collage(interaction: discord.Interaction, username: str):
    await interaction.response.send_message(f"Creating collage for {username}...")
    # Here you would add the logic to create the collage using the Last.fm API
    # For example, you could fetch the user's top artists and create a collage image
    # Once the collage is created, you can send it back to the user
    # await interaction.followup.send(file=discord.File("path_to_collage_image.png"))
    await fetch_top_tracks(username)


client.run(os.getenv("LAST_FM_DISCORD_TOKEN"))
