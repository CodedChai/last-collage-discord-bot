import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pytest_asyncio
import aiohttp
from aioresponses import aioresponses

from services import lastfm_service
from services.lastfm_service import (
    BASE_URL,
    LastFmError,
    _check_for_errors,
    fetch_top_tracks,
    fetch_top_albums,
    fetch_top_artists,
)
from models import TopTracksModel, TopAlbumsModel, TopArtistsModel

URL_PATTERN = re.compile(r"^http://ws\.audioscrobbler\.com/2\.0/\??.*$")


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    monkeypatch.setattr(
        lastfm_service,
        "DEFAULT_PARAMS",
        {"api_key": "FAKE_KEY", "format": "json"},
    )


# --- _check_for_errors ---


class TestCheckForErrors:
    def test_no_error_key(self):
        _check_for_errors({"toptracks": {}})

    def test_known_error_code_6(self):
        with pytest.raises(LastFmError) as exc_info:
            _check_for_errors({"error": 6, "message": "User not found"})
        assert exc_info.value.code == 6
        assert "User not found" in exc_info.value.message

    def test_unknown_error_code_uses_response_message(self):
        with pytest.raises(LastFmError) as exc_info:
            _check_for_errors({"error": 99, "message": "Something weird"})
        assert exc_info.value.code == 99
        assert exc_info.value.message == "Something weird"

    def test_unknown_error_code_no_message(self):
        with pytest.raises(LastFmError) as exc_info:
            _check_for_errors({"error": 99})
        assert exc_info.value.code == 99
        assert exc_info.value.message == "An unknown Last.fm error occurred."


# --- fetch_top_tracks ---


VALID_TOP_TRACKS_RESPONSE = {
    "toptracks": {
        "track": [
            {
                "name": "Song",
                "artist": {"name": "Artist"},
                "@attr": {"rank": 1},
                "playcount": 10,
            }
        ]
    }
}


class TestFetchTopTracks:
    @pytest.mark.asyncio
    async def test_success(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload=VALID_TOP_TRACKS_RESPONSE)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_tracks(session, "testuser", "7day")

        assert isinstance(result, TopTracksModel)
        assert len(result.tracks) == 1
        assert result.tracks[0].name == "Song"
        assert result.tracks[0].artist == "Artist"
        assert result.tracks[0].rank == 1
        assert result.tracks[0].playcount == 10

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload={"error": 6, "message": "User not found"})
            async with aiohttp.ClientSession() as session:
                with pytest.raises(LastFmError) as exc_info:
                    await fetch_top_tracks(session, "baduser", "7day")
        assert exc_info.value.code == 6

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, status=500)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_tracks(session, "testuser", "7day")
        assert result is None


# --- fetch_top_albums ---


VALID_TOP_ALBUMS_RESPONSE = {
    "topalbums": {
        "album": [
            {
                "name": "Album",
                "artist": {"name": "Artist"},
                "@attr": {"rank": 1},
                "playcount": 5,
                "image": [{"#text": "http://img.com/pic.jpg", "size": "large"}],
            }
        ]
    }
}


class TestFetchTopAlbums:
    @pytest.mark.asyncio
    async def test_success(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload=VALID_TOP_ALBUMS_RESPONSE)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_albums(session, "testuser", "7day")

        assert isinstance(result, TopAlbumsModel)
        assert len(result.albums) == 1
        assert result.albums[0].name == "Album"
        assert result.albums[0].artist == "Artist"
        assert result.albums[0].rank == 1
        assert result.albums[0].playcount == 5
        assert result.albums[0].image_url == "http://img.com/pic.jpg"

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload={"error": 6, "message": "User not found"})
            async with aiohttp.ClientSession() as session:
                with pytest.raises(LastFmError) as exc_info:
                    await fetch_top_albums(session, "baduser", "7day")
        assert exc_info.value.code == 6

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, status=500)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_albums(session, "testuser", "7day")
        assert result is None


# --- fetch_top_artists ---


VALID_TOP_ARTISTS_RESPONSE = {
    "topartists": {
        "artist": [
            {
                "name": "Artist",
                "@attr": {"rank": 1},
                "playcount": 200,
            }
        ]
    }
}


class TestFetchTopArtists:
    @pytest.mark.asyncio
    async def test_success(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload=VALID_TOP_ARTISTS_RESPONSE)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_artists(session, "testuser", "7day")

        assert isinstance(result, TopArtistsModel)
        assert len(result.artists) == 1
        assert result.artists[0].name == "Artist"
        assert result.artists[0].rank == 1
        assert result.artists[0].playcount == 200

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, payload={"error": 6, "message": "User not found"})
            async with aiohttp.ClientSession() as session:
                with pytest.raises(LastFmError) as exc_info:
                    await fetch_top_artists(session, "baduser", "7day")
        assert exc_info.value.code == 6

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        with aioresponses() as mocked:
            mocked.get(URL_PATTERN, status=500)
            async with aiohttp.ClientSession() as session:
                result = await fetch_top_artists(session, "testuser", "7day")
        assert result is None
