import os

import aiohttp

from models import WeeklyTrackChartModel

last_fm_api_key = os.getenv("LAST_FM_API_KEY")

BASE_URL = "http://ws.audioscrobbler.com/2.0/"
DEFAULT_PARAMS = {
    "api_key": last_fm_api_key,
    "format": "json",
}


async def fetch_top_tracks(session: aiohttp.ClientSession, username: str):
    params = {
        **DEFAULT_PARAMS,
        "method": "user.getweeklytrackchart",
        "user": username,
    }
    async with session.get(BASE_URL, params=params) as response:
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
