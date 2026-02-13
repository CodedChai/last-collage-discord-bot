import logging
import os
import aiohttp
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from models import TopTracksModel, TopAlbumsModel

load_dotenv()

logger = logging.getLogger('lastfm_collage_bot.lastfm_service')

BASE_URL = "http://ws.audioscrobbler.com/2.0/"

DEFAULT_PARAMS = {
    "api_key": os.getenv("LAST_FM_API_KEY"),
    "format": "json",
}

LASTFM_ERROR_MESSAGES = {
    6: "User not found. Please check the username and try again.",
    8: "Last.fm is experiencing issues. Please try again later.",
    10: "Invalid API key. Please contact the bot administrator.",
    11: "Last.fm is temporarily offline. Please try again later.",
    16: "A temporary error occurred on Last.fm. Please try again.",
    26: "The API key has been suspended. Please contact the bot administrator.",
    29: "Too many requests. Please wait a moment and try again.",
}


class LastFmError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)


def _check_for_errors(data: dict):
    if "error" in data:
        code = data["error"]
        message = LASTFM_ERROR_MESSAGES.get(code, data.get("message", "An unknown Last.fm error occurred."))
        raise LastFmError(code, message)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(aiohttp.ClientError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
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
                _check_for_errors(data)
                top_tracks = TopTracksModel.model_validate(data)
                logger.info(f"Successfully fetched {len(top_tracks.tracks)} top tracks for {username}")
                return top_tracks
            else:
                logger.error(f"Failed to fetch top tracks for {username}: HTTP {response.status}")
                return None
    except LastFmError:
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching top tracks for {username}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching top tracks for {username}: {e}", exc_info=True)
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(aiohttp.ClientError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
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
                _check_for_errors(data)
                top_albums = TopAlbumsModel.model_validate(data)
                logger.info(f"Successfully fetched {len(top_albums.albums)} top albums for {username}")
                return top_albums
            else:
                logger.error(f"Failed to fetch top albums for {username}: HTTP {response.status}")
                return None
    except LastFmError:
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching top albums for {username}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching top albums for {username}: {e}", exc_info=True)
        return None
