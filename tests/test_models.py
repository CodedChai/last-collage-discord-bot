import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from pydantic import ValidationError

from models import (
    sanitize_username,
    TrackModel,
    TopTracksModel,
    AlbumModel,
    TopAlbumsModel,
    ArtistModel,
    TopArtistsModel,
    CollageRequest,
    WeeklyJoinRequest,
)


# --- sanitize_username ---


class TestSanitizeUsername:
    def test_valid_alphanumeric(self):
        assert sanitize_username("user123") == "user123"

    def test_valid_hyphens_underscores(self):
        assert sanitize_username("my-user_1") == "my-user_1"

    def test_valid_min_length(self):
        assert sanitize_username("ab") == "ab"

    def test_valid_max_length(self):
        assert sanitize_username("a" * 15) == "a" * 15

    def test_strips_leading_trailing_whitespace(self):
        assert sanitize_username("  user123  ") == "user123"

    def test_too_short(self):
        with pytest.raises(ValueError):
            sanitize_username("a")

    def test_too_long(self):
        with pytest.raises(ValueError):
            sanitize_username("a" * 16)

    def test_special_chars(self):
        with pytest.raises(ValueError):
            sanitize_username("user!@#")

    def test_empty(self):
        with pytest.raises(ValueError):
            sanitize_username("")

    def test_whitespace_only(self):
        with pytest.raises(ValueError):
            sanitize_username("   ")


# --- TrackModel ---


class TestTrackModel:
    def test_parses_nested_json(self):
        data = {
            "name": "Song Title",
            "artist": {"name": "Artist Name"},
            "@attr": {"rank": 1},
            "playcount": 42,
        }
        track = TrackModel.model_validate(data)
        assert track.name == "Song Title"
        assert track.artist == "Artist Name"
        assert track.rank == 1
        assert track.playcount == 42

    def test_playcount_as_string_int(self):
        data = {
            "name": "Song",
            "artist": {"name": "Artist"},
            "@attr": {"rank": "3"},
            "playcount": "10",
        }
        track = TrackModel.model_validate(data)
        assert track.playcount == 10
        assert track.rank == 3


# --- TopTracksModel ---


class TestTopTracksModel:
    def test_parses_from_alias_path(self):
        data = {
            "toptracks": {
                "track": [
                    {
                        "name": "Song",
                        "artist": {"name": "Artist"},
                        "@attr": {"rank": 1},
                        "playcount": 5,
                    }
                ]
            }
        }
        result = TopTracksModel.model_validate(data)
        assert len(result.tracks) == 1
        assert result.tracks[0].name == "Song"

    def test_empty_track_list(self):
        data = {"toptracks": {"track": []}}
        result = TopTracksModel.model_validate(data)
        assert result.tracks == []


# --- AlbumModel ---


class TestAlbumModel:
    def test_parses_nested_json(self):
        data = {
            "name": "Album Title",
            "artist": {"name": "Artist Name"},
            "@attr": {"rank": 2},
            "playcount": 100,
            "image": [
                {"#text": "http://img.com/small.jpg", "size": "small"},
                {"#text": "http://img.com/large.jpg", "size": "large"},
            ],
        }
        album = AlbumModel.model_validate(data)
        assert album.name == "Album Title"
        assert album.artist == "Artist Name"
        assert album.rank == 2
        assert album.playcount == 100
        assert album.image_url == "http://img.com/large.jpg"

    def test_extract_image_last_non_empty(self):
        data = {
            "name": "Album",
            "artist": {"name": "Artist"},
            "@attr": {"rank": 1},
            "playcount": 1,
            "image": [
                {"#text": "http://img.com/small.jpg", "size": "small"},
                {"#text": "http://img.com/medium.jpg", "size": "medium"},
                {"#text": "", "size": "large"},
            ],
        }
        album = AlbumModel.model_validate(data)
        assert album.image_url == "http://img.com/medium.jpg"

    def test_extract_image_converts_png_to_jpg(self):
        data = {
            "name": "Album",
            "artist": {"name": "Artist"},
            "@attr": {"rank": 1},
            "playcount": 1,
            "image": [
                {"#text": "http://img.com/cover.png", "size": "large"},
            ],
        }
        album = AlbumModel.model_validate(data)
        assert album.image_url == "http://img.com/cover.jpg"

    def test_extract_image_empty_list(self):
        data = {
            "name": "Album",
            "artist": {"name": "Artist"},
            "@attr": {"rank": 1},
            "playcount": 1,
            "image": [],
        }
        album = AlbumModel.model_validate(data)
        assert album.image_url is None

    def test_extract_image_all_empty_text(self):
        data = {
            "name": "Album",
            "artist": {"name": "Artist"},
            "@attr": {"rank": 1},
            "playcount": 1,
            "image": [
                {"#text": "", "size": "small"},
                {"#text": "", "size": "large"},
            ],
        }
        album = AlbumModel.model_validate(data)
        assert album.image_url is None

    def test_extract_image_missing_field(self):
        data = {
            "name": "Album",
            "artist": {"name": "Artist"},
            "@attr": {"rank": 1},
            "playcount": 1,
        }
        album = AlbumModel.model_validate(data)
        assert album.image_url is None


# --- TopAlbumsModel ---


class TestTopAlbumsModel:
    def test_parses_from_alias_path(self):
        data = {
            "topalbums": {
                "album": [
                    {
                        "name": "Album",
                        "artist": {"name": "Artist"},
                        "@attr": {"rank": 1},
                        "playcount": 50,
                        "image": [],
                    }
                ]
            }
        }
        result = TopAlbumsModel.model_validate(data)
        assert len(result.albums) == 1
        assert result.albums[0].name == "Album"

    def test_empty_album_list(self):
        data = {"topalbums": {"album": []}}
        result = TopAlbumsModel.model_validate(data)
        assert result.albums == []


# --- ArtistModel ---


class TestArtistModel:
    def test_parses_nested_json(self):
        data = {
            "name": "Artist Name",
            "@attr": {"rank": 1},
            "playcount": 200,
        }
        artist = ArtistModel.model_validate(data)
        assert artist.name == "Artist Name"
        assert artist.rank == 1
        assert artist.playcount == 200

    def test_playcount_as_string_int(self):
        data = {
            "name": "Artist",
            "@attr": {"rank": "3"},
            "playcount": "10",
        }
        artist = ArtistModel.model_validate(data)
        assert artist.playcount == 10
        assert artist.rank == 3


# --- TopArtistsModel ---


class TestTopArtistsModel:
    def test_parses_from_alias_path(self):
        data = {
            "topartists": {
                "artist": [
                    {
                        "name": "Artist",
                        "@attr": {"rank": 1},
                        "playcount": 50,
                    }
                ]
            }
        }
        result = TopArtistsModel.model_validate(data)
        assert len(result.artists) == 1
        assert result.artists[0].name == "Artist"

    def test_empty_artist_list(self):
        data = {"topartists": {"artist": []}}
        result = TopArtistsModel.model_validate(data)
        assert result.artists == []


# --- CollageRequest ---


class TestCollageRequest:
    def test_valid_request(self):
        req = CollageRequest(username="user1", period="7day", grid_size="3")
        assert req.username == "user1"
        assert req.period == "7day"
        assert req.grid_size == "3"

    def test_invalid_username(self):
        with pytest.raises(ValidationError):
            CollageRequest(username="!", period="7day", grid_size="3")

    def test_invalid_period(self):
        with pytest.raises(ValidationError):
            CollageRequest(username="user1", period="2weeks", grid_size="3")

    def test_invalid_grid_size(self):
        with pytest.raises(ValidationError):
            CollageRequest(username="user1", period="7day", grid_size="10")


# --- WeeklyJoinRequest ---


class TestWeeklyJoinRequest:
    def test_valid_request(self):
        req = WeeklyJoinRequest(
            username="user1",
            guild_id=123,
            channel_id=456,
            discord_user_id=789,
        )
        assert req.username == "user1"
        assert req.guild_id == 123
        assert req.channel_id == 456
        assert req.discord_user_id == 789

    def test_invalid_username(self):
        with pytest.raises(ValidationError):
            WeeklyJoinRequest(
                username="",
                guild_id=123,
                channel_id=456,
                discord_user_id=789,
            )

    def test_requires_int_ids(self):
        req = WeeklyJoinRequest(
            username="user1",
            guild_id="123",
            channel_id="456",
            discord_user_id="789",
        )
        assert req.guild_id == 123
        assert req.channel_id == 456
        assert req.discord_user_id == 789
