import asyncio
import logging
import os
import re
from io import BytesIO

import aiohttp
import diskcache
from dotenv import load_dotenv
from PIL import Image
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from models import AlbumModel
from utils.collage_utils import TILE_SIZE, compose_collage, DEFAULT_GRID_SIZE

load_dotenv()

logger = logging.getLogger("lastfm_collage_bot.collage_service")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "image_cache")
CACHE_SIZE_LIMIT = int(os.getenv("IMAGE_CACHE_SIZE_MB", "500")) * 1024 * 1024
image_cache = diskcache.Cache(CACHE_DIR, size_limit=CACHE_SIZE_LIMIT)

MAX_CONCURRENT_DOWNLOADS = 10
IMAGE_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
}
FALLBACK_SIZES = ["500x500", "1000x1000", "174s"]
SIZE_PATTERN = re.compile(r"(/i/u/)[^/]+(/)")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
    retry=retry_if_exception_type(aiohttp.ClientError),
    reraise=True,
)
async def _fetch_image_bytes(session: aiohttp.ClientSession, url: str) -> bytes | None:
    async with session.get(url, headers=IMAGE_DOWNLOAD_HEADERS) as response:
        if response.status == 200:
            return await response.read()
        elif response.status == 404:
            return None
        else:
            logger.warning(
                f"Failed to download image from {url}: HTTP {response.status}"
            )
            return None


async def _download_image(
    session: aiohttp.ClientSession, url: str
) -> Image.Image | None:
    try:
        cached = image_cache.get(url)
        if cached is not None:
            logger.info(f"Cache hit for {url}")
            raw_bytes, size, mode = cached
            return Image.frombytes(mode, size, raw_bytes)

        urls_to_try = [url] + [
            SIZE_PATTERN.sub(rf"\g<1>{size}\2", url) for size in FALLBACK_SIZES
        ]

        for try_url in urls_to_try:
            if try_url != url:
                logger.info(f"Trying fallback for {url} -> {try_url}")
            data = await _fetch_image_bytes(session, try_url)

            if data is not None:
                img = Image.open(BytesIO(data))
                img = img.convert("RGB")

                if img.size != (TILE_SIZE, TILE_SIZE):
                    img = img.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)

                image_cache.set(url, (img.tobytes(), img.size, img.mode))

                return img

        logger.warning(f"All image sizes failed for {url}")
        return None
    except aiohttp.ClientError as e:
        logger.warning(f"Network error downloading image from {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error processing image from {url}: {e}")
        return None


async def download_album_images(
    session: aiohttp.ClientSession, albums: list[AlbumModel]
) -> list[Image.Image | None]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

    async def _limited_download(url: str) -> Image.Image | None:
        async with semaphore:
            return await _download_image(session, url)

    albums_with_urls = [(i, a) for i, a in enumerate(albums) if a.image_url]
    downloaded = await asyncio.gather(
        *(_limited_download(album.image_url) for _, album in albums_with_urls)
    )

    images: list[Image.Image | None] = [None] * len(albums)
    for (i, _), img in zip(albums_with_urls, downloaded):
        images[i] = img

    successful_downloads = sum(1 for img in images if img is not None)
    logger.info(
        f"Successfully downloaded {successful_downloads}/{len(albums)} album cover images"
    )
    return images


async def generate_collage(
    session: aiohttp.ClientSession,
    albums: list[AlbumModel],
    grid_size: int | tuple[int, int] = DEFAULT_GRID_SIZE,
) -> BytesIO:
    if isinstance(grid_size, tuple):
        grid_cols, grid_rows = grid_size
    else:
        grid_cols = grid_rows = grid_size

    total_slots = grid_cols * grid_rows
    selected_albums = albums[:total_slots]
    logger.info(
        f"Generating {grid_cols}x{grid_rows} collage with {len(selected_albums)} albums"
    )

    images = await download_album_images(session, selected_albums)
    result = compose_collage(images, selected_albums, grid_size)

    logger.info("Collage generated successfully")
    return result
