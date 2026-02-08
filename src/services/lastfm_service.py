import os
import aiohttp
from models import WeeklyTrackChartModel

last_fm_api_key = os.getenv("LAST_FM_API_KEY")


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
