import logging
import os
import aiohttp
from dotenv import load_dotenv
from models import TopTracksModel, TopAlbumsModel

load_dotenv()

logger = logging.getLogger('lastfm_collage_bot.lastfm_service')

BASE_URL = "http://ws.audioscrobbler.com/2.0/"

DEFAULT_PARAMS = {
    "api_key": os.getenv("LAST_FM_API_KEY"),
    "format": "json",
}


async def fetch_top_tracks(session: aiohttp.ClientSession, username: str, period: str = "7day"):
    params = {
        **DEFAULT_PARAMS,
        "method": "user.getTopTracks",
        "user": username,
        "period": period,
    }
    try:
        async with session.get(BASE_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                top_tracks = TopTracksModel.model_validate(data)
                logger.info(f"Successfully fetched {len(top_tracks.tracks)} top tracks for {username}")
                return top_tracks
            else:
                logger.error(f"Failed to fetch top tracks for {username}: HTTP {response.status}")
                return []
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching top tracks for {username}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching top tracks for {username}: {e}", exc_info=True)
        return []


async def fetch_top_albums(session: aiohttp.ClientSession, username: str, period: str = "7day"):
    params = {
        **DEFAULT_PARAMS,
        "method": "user.getTopAlbums",
        "user": username,
        "period": period,
    }
    try:
        async with session.get(BASE_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                top_albums = TopAlbumsModel.model_validate(data)
                logger.info(f"Successfully fetched {len(top_albums.albums)} top albums for {username}")
                return top_albums
            else:
                logger.error(f"Failed to fetch top albums for {username}: HTTP {response.status}")
                return []
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching top albums for {username}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching top albums for {username}: {e}", exc_info=True)
        return []
