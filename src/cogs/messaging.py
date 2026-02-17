import asyncio
import logging
import time

import discord

from services.collage_service import generate_collage
from services.lastfm_service import fetch_top_tracks, fetch_top_albums
from services.metrics_service import COMMAND_LATENCY, COMMAND_COUNT
from utils.collage_utils import resolve_grid_size
from utils.embed_utils import build_collage_embed

logger = logging.getLogger("lastfm_collage_bot.messaging")


async def fetch_and_send_collage(
    destination,
    session,
    username: str,
    period: str,
    title: str,
    grid_size_str: str = "dynamic",
) -> bool:
    """Fetch Last.fm data and send a collage. Returns True if data was found and sent."""
    start = time.perf_counter()
    status = "success"
    try:
        top_tracks, top_albums = await asyncio.gather(
            fetch_top_tracks(session, username, period),
            fetch_top_albums(session, username, period),
        )

        has_albums = top_albums and top_albums.albums
        has_tracks = top_tracks and top_tracks.tracks

        if not has_albums and not has_tracks:
            return False

        grid_size = resolve_grid_size(
            grid_size_str, top_albums.albums if has_albums else None
        )

        embed = build_collage_embed(title, top_tracks, period)
        await send_collage(destination, session, embed, top_albums, grid_size)
        return True
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        COMMAND_LATENCY.record(duration, {"command": "collage"})
        COMMAND_COUNT.add(1, {"command": "collage", "status": status})


async def send_collage(destination, session, embed, top_albums, grid_size):
    has_albums = top_albums and top_albums.albums
    if has_albums:
        buffer = await generate_collage(session, top_albums.albums, grid_size)
        embed.set_image(url="attachment://collage.webp")
        await destination.send(
            embed=embed, file=discord.File(buffer, filename="collage.webp")
        )
    else:
        await destination.send(embed=embed)


async def send_collage_from_data(
    destination,
    session,
    title: str,
    top_tracks,
    top_albums,
    grid_size_str: str = "dynamic",
):
    """Send a collage from already-fetched data. Used by weekly scheduler to avoid double-fetching."""
    start = time.perf_counter()
    status = "success"
    try:
        has_albums = top_albums and top_albums.albums

        grid_size = resolve_grid_size(
            grid_size_str, top_albums.albums if has_albums else None
        )

        embed = build_collage_embed(title, top_tracks, "7day")
        await send_collage(destination, session, embed, top_albums, grid_size)
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        COMMAND_LATENCY.record(duration, {"command": "weekly_collage"})
        COMMAND_COUNT.add(1, {"command": "weekly_collage", "status": status})
