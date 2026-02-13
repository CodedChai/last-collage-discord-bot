import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image, ImageDraw, ImageFont

from models import AlbumModel
from utils.collage_utils import (
    TILE_SIZE,
    _add_overlay,
    _create_placeholder,
    _wrap_text,
    determine_dynamic_grid_size,
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
