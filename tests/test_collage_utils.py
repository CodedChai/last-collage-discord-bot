import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image, ImageDraw, ImageFont

from models import AlbumModel, TopArtistsModel, TrackModel
from utils.collage_utils import (
    TILE_SIZE,
    _add_overlay,
    _create_placeholder,
    _wrap_text,
    build_artist_rank_map,
    determine_dynamic_grid_size,
    sort_with_artist_tiebreak,
)


# --- Helpers ---


def make_album(name="Album", artist="Artist", rank=1, playcount=10, image_url=None):
    image_list = []
    if image_url:
        image_list = [{"#text": image_url, "size": "large"}]
    return AlbumModel.model_validate(
        {
            "name": name,
            "artist": {"name": artist},
            "@attr": {"rank": rank},
            "playcount": playcount,
            "image": image_list,
        }
    )


# --- determine_dynamic_grid_size ---


class TestDetermineDynamicGridSize:
    def test_empty_list(self):
        assert determine_dynamic_grid_size([]) == (1, 1)

    def test_single_album(self):
        albums = [make_album(rank=1, playcount=5)]
        assert determine_dynamic_grid_size(albums) == (1, 1)

    def test_four_albums_high_playcount(self):
        albums = [make_album(rank=i + 1, playcount=5) for i in range(4)]
        assert determine_dynamic_grid_size(albums) == (2, 2)

    def test_nine_albums_high_playcount(self):
        albums = [make_album(rank=i + 1, playcount=5) for i in range(9)]
        assert determine_dynamic_grid_size(albums) == (3, 3)

    def test_twenty_five_albums_high_playcount(self):
        albums = [make_album(rank=i + 1, playcount=5) for i in range(25)]
        assert determine_dynamic_grid_size(albums) == (5, 5)

    def test_stops_at_playcount_one_boundary(self):
        # 9 albums: first 4 have playcount > 1, album[4] has playcount = 1
        # After (2,2) fills 4 slots, the 5th album (index 4) has playcount 1 → stop at (2,2)
        albums = []
        for i in range(9):
            pc = 5 if i < 4 else 1
            albums.append(make_album(rank=i + 1, playcount=pc))
        assert determine_dynamic_grid_size(albums) == (2, 2)


# --- _create_placeholder ---


class TestCreatePlaceholder:
    def test_returns_300x300_dark_image(self):
        img = _create_placeholder()
        assert img.size == (TILE_SIZE, TILE_SIZE)
        assert img.mode == "RGB"
        # Check center pixel is dark gray (30, 30, 30)
        assert img.getpixel((150, 150)) == (30, 30, 30)


# --- _add_overlay ---


class TestAddOverlay:
    def test_returns_image_without_error(self):
        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (100, 100, 100))
        album = make_album(name="Test Album", artist="Test Artist", playcount=42)
        result = _add_overlay(img, album)
        assert isinstance(result, Image.Image)
        assert result.size == (TILE_SIZE, TILE_SIZE)

    def test_handles_long_text(self):
        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (100, 100, 100))
        album = make_album(
            name="A Very Long Album Name That Should Wrap",
            artist="An Extremely Long Artist Name For Testing",
            playcount=99,
        )
        result = _add_overlay(img, album)
        assert isinstance(result, Image.Image)


# --- _wrap_text ---


class TestWrapText:
    def test_short_text_single_line(self):
        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        lines = _wrap_text(draw, "Hi", font, max_width=200)
        assert lines == ["Hi"]

    def test_long_text_wraps(self):
        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        long_text = "This is a really long text that should definitely be wrapped into multiple lines"
        lines = _wrap_text(draw, long_text, font, max_width=100)
        assert len(lines) > 1
        # All original words should be present
        assert " ".join(lines) == long_text

    def test_single_word_no_wrap(self):
        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        lines = _wrap_text(draw, "Superlongword", font, max_width=200)
        assert lines == ["Superlongword"]


# --- Helpers for tiebreak tests ---


def make_track(name="Track", artist="Artist", rank=1, playcount=10):
    return TrackModel.model_validate(
        {
            "name": name,
            "artist": {"name": artist},
            "@attr": {"rank": rank},
            "playcount": playcount,
        }
    )


def make_top_artists(artists_data):
    return TopArtistsModel.model_validate(
        {
            "topartists": {
                "artist": [
                    {"name": name, "@attr": {"rank": rank}, "playcount": pc}
                    for name, rank, pc in artists_data
                ]
            }
        }
    )


# --- build_artist_rank_map ---


class TestBuildArtistRankMap:
    def test_returns_empty_for_none(self):
        assert build_artist_rank_map(None) == {}

    def test_builds_lowercase_map(self):
        top_artists = make_top_artists([("Radiohead", 1, 50), ("Björk", 2, 30)])
        result = build_artist_rank_map(top_artists)
        assert result == {"radiohead": 1, "björk": 2}


# --- sort_with_artist_tiebreak ---


class TestSortWithArtistTiebreak:
    def test_no_op_when_no_artist_map(self):
        tracks = [make_track(playcount=5), make_track(playcount=10)]
        result = sort_with_artist_tiebreak(tracks, {})
        assert result is tracks

    def test_sorts_by_playcount_descending(self):
        tracks = [
            make_track(name="Low", artist="A", playcount=3),
            make_track(name="High", artist="B", playcount=10),
        ]
        result = sort_with_artist_tiebreak(tracks, {"a": 1, "b": 2})
        assert [t.name for t in result] == ["High", "Low"]

    def test_tiebreaks_by_artist_rank(self):
        tracks = [
            make_track(name="T1", artist="Worse", playcount=5),
            make_track(name="T2", artist="Better", playcount=5),
        ]
        artist_map = {"better": 1, "worse": 3}
        result = sort_with_artist_tiebreak(tracks, artist_map)
        assert [t.name for t in result] == ["T2", "T1"]

    def test_unknown_artist_sorted_last(self):
        tracks = [
            make_track(name="T1", artist="Unknown", playcount=5),
            make_track(name="T2", artist="Known", playcount=5),
        ]
        artist_map = {"known": 1}
        result = sort_with_artist_tiebreak(tracks, artist_map)
        assert [t.name for t in result] == ["T2", "T1"]

    def test_works_with_albums(self):
        albums = [
            make_album(name="A1", artist="Worse", playcount=5),
            make_album(name="A2", artist="Better", playcount=5),
        ]
        artist_map = {"better": 1, "worse": 2}
        result = sort_with_artist_tiebreak(albums, artist_map)
        assert [a.name for a in result] == ["A2", "A1"]
