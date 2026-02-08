import os

import aiohttp

from models import TopTracksModel, TopAlbumsModel

last_fm_api_key = os.getenv("LAST_FM_API_KEY")

BASE_URL = "http://ws.audioscrobbler.com/2.0/"
DEFAULT_PARAMS = {
    "api_key": last_fm_api_key,
    "format": "json",
}


async def fetch_top_tracks(session: aiohttp.ClientSession, username: str):
    params = {
        **DEFAULT_PARAMS,
        "method": "user.getTopTracks",
        "user": username,
        "period": "7day",
    }
    async with session.get(BASE_URL, params=params) as response:
        if response.status == 200:
            data = await response.json()
            top_tracks = TopTracksModel.model_validate(data)
            print(f"Top tracks for {username}:")
            for track in top_tracks.tracks:
                print(
                    f"{track.rank}. {track.artist} - {track.name} (Playcount: {track.playcount})"
                )
            return top_tracks
        else:
            print(f"Failed to fetch top tracks for {username}: {response.status}")
            return []


async def fetch_top_albums(session: aiohttp.ClientSession, username: str):
    params = {
        **DEFAULT_PARAMS,
        "method": "user.getTopAlbums",
        "user": username,
        "period": "7day",
    }
    async with session.get(BASE_URL, params=params) as response:
        if response.status == 200:
            data = await response.json()
            top_albums = TopAlbumsModel.model_validate(data)
            print(f"Top albums for {username}:")
            for album in top_albums.albums:
                print(
                    f"{album.rank}. {album.artist} - {album.name} (Playcount: {album.playcount}) Image: {album.image_url}"
                )
            return top_albums
        else:
            print(f"Failed to fetch top albums for {username}: {response.status}")
            return []
