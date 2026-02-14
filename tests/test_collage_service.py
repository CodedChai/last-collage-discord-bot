import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from io import BytesIO

import pytest
import aiohttp
from aioresponses import aioresponses
from PIL import Image

from models import AlbumModel
from services.collage_service import generate_collage
from utils.collage_utils import TILE_SIZE


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


def make_jpeg_bytes(width=300, height=300, color=(255, 0, 0)):
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def disable_image_cache(monkeypatch):
    import services.collage_service as cs

    monkeypatch.setattr(cs, "_redis", None)


# --- generate_collage ---


class TestGenerateCollage:
    @pytest.mark.asyncio
    async def test_2x2_collage_returns_valid_jpeg(self):
        albums = [
            make_album(
                name=f"Album {i}",
                rank=i + 1,
                playcount=5,
                image_url=f"http://example.com/img{i}.jpg",
            )
            for i in range(4)
        ]
        image_bytes = make_jpeg_bytes()

        with aioresponses() as m:
            for i in range(4):
                m.get(f"http://example.com/img{i}.jpg", body=image_bytes)

            async with aiohttp.ClientSession() as session:
                result = await generate_collage(session, albums, grid_size=2)

        assert isinstance(result, BytesIO)
        data = result.getvalue()
        # JPEG magic bytes: FF D8 FF
        assert data[:3] == b"\xff\xd8\xff"

    @pytest.mark.asyncio
    async def test_2x2_collage_dimensions(self):
        albums = [
            make_album(
                name=f"Album {i}",
                rank=i + 1,
                playcount=5,
                image_url=f"http://example.com/img{i}.jpg",
            )
            for i in range(4)
        ]
        image_bytes = make_jpeg_bytes()

        with aioresponses() as m:
            for i in range(4):
                m.get(f"http://example.com/img{i}.jpg", body=image_bytes)

            async with aiohttp.ClientSession() as session:
                result = await generate_collage(session, albums, grid_size=2)

        img = Image.open(result)
        assert img.size == (2 * TILE_SIZE, 2 * TILE_SIZE)

    @pytest.mark.asyncio
    async def test_tuple_grid_size_dimensions(self):
        albums = [
            make_album(
                name=f"Album {i}",
                rank=i + 1,
                playcount=5,
                image_url=f"http://example.com/img{i}.jpg",
            )
            for i in range(6)
        ]
        image_bytes = make_jpeg_bytes()

        with aioresponses() as m:
            for i in range(6):
                m.get(f"http://example.com/img{i}.jpg", body=image_bytes)

            async with aiohttp.ClientSession() as session:
                result = await generate_collage(session, albums, grid_size=(3, 2))

        img = Image.open(result)
        assert img.size == (3 * TILE_SIZE, 2 * TILE_SIZE)

    @pytest.mark.asyncio
    async def test_albums_without_image_url_get_placeholder(self):
        albums = [
            make_album(name="No Image", rank=1, playcount=5, image_url=None),
            make_album(
                name="Has Image",
                rank=2,
                playcount=5,
                image_url="http://example.com/img.jpg",
            ),
            make_album(name="No Image 2", rank=3, playcount=5, image_url=None),
            make_album(name="No Image 3", rank=4, playcount=5, image_url=None),
        ]
        image_bytes = make_jpeg_bytes(color=(0, 255, 0))

        with aioresponses() as m:
            m.get("http://example.com/img.jpg", body=image_bytes)

            async with aiohttp.ClientSession() as session:
                result = await generate_collage(session, albums, grid_size=2)

        img = Image.open(result)
        assert img.size == (2 * TILE_SIZE, 2 * TILE_SIZE)
        # Top-left tile (no image) should have dark gray placeholder pixels
        pixel = img.getpixel((0, 0))
        # Placeholder is (30, 30, 30) but overlay text may alter some pixels;
        # check a center-ish area away from text
        pixel_center = img.getpixel((TILE_SIZE // 2, TILE_SIZE // 2))
        assert pixel_center[0] < 60 and pixel_center[1] < 60 and pixel_center[2] < 60
