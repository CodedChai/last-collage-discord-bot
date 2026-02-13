import datetime
from urllib.parse import quote_plus

import discord

from services.collage_service import generate_collage

EMBED_COLOR = 0x1DB954

PERIOD_LABELS = {
    "7day": "7 Days",
    "1month": "1 Month",
    "3month": "3 Months",
    "6month": "6 Months",
    "12month": "12 Months",
    "overall": "Overall",
}


def format_top_tracks(tracks, limit=5):
    return "\n".join(
        f"{i + 1}. [{track.artist} - {track.name}]"
        f"(https://www.youtube.com/results?search_query={quote_plus(f'{track.artist} {track.name}')})"
        f" ({track.playcount} plays)"
        for i, track in enumerate(tracks[:limit])
    )


def build_collage_embed(title, top_tracks, period_val):
    has_tracks = top_tracks and top_tracks.tracks
    if has_tracks:
        description = f"**Top 5 Tracks:**\n{format_top_tracks(top_tracks.tracks)}"
    else:
        description = "*No tracks found for this period.*"

    period_label = PERIOD_LABELS.get(period_val, period_val)
    embed = discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    embed.set_footer(text=f"Period: {period_label}")
    return embed


async def send_collage(destination, session, embed, top_albums, grid_size):
    has_albums = top_albums and top_albums.albums
    if has_albums:
        buffer = await generate_collage(session, top_albums.albums, grid_size)
        embed.set_image(url="attachment://collage.jpg")
        await destination.send(
            embed=embed, file=discord.File(buffer, filename="collage.jpg")
        )
    else:
        await destination.send(embed=embed)
