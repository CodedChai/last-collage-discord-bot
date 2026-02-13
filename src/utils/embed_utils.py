import datetime
from urllib.parse import quote_plus

import discord

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
