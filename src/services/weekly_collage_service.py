import asyncio
from dataclasses import dataclass
from typing import Optional

import discord

from models import TopArtistsModel, TopAlbumsModel, TopTracksModel
from services.summary_service import UserListeningData, extract_listening_data


@dataclass
class FetchResult:
    listening_data: UserListeningData
    top_artists: Optional[TopArtistsModel]
    top_albums: Optional[TopAlbumsModel]
    top_tracks: Optional[TopTracksModel]


def get_display_name(member: Optional[discord.Member], lastfm_username: str) -> str:
    return member.display_name if member else lastfm_username


async def fetch_user_listening_data(
    session, lastfm_username: str, display_name: str, period: str = "7day"
) -> FetchResult:
    from services.lastfm_service import (
        fetch_top_artists,
        fetch_top_albums,
        fetch_top_tracks,
    )

    top_artists, top_albums, top_tracks = await asyncio.gather(
        fetch_top_artists(session, lastfm_username, period),
        fetch_top_albums(session, lastfm_username, period),
        fetch_top_tracks(session, lastfm_username, period),
    )

    listening_data = extract_listening_data(display_name, top_artists, top_albums, top_tracks)
    return FetchResult(
        listening_data=listening_data,
        top_artists=top_artists,
        top_albums=top_albums,
        top_tracks=top_tracks,
    )


async def fetch_member_safe(
    guild: discord.Guild, user_id: int
) -> Optional[discord.Member]:
    try:
        return await guild.fetch_member(user_id)
    except Exception:
        return None
