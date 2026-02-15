import asyncio
import enum
import hashlib
import logging
import os
import re
from io import BytesIO

import aiohttp
import redis.asyncio as aioredis
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

MAX_CONCURRENT_DOWNLOADS = 10
IMAGE_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
}
FALLBACK_SIZES = ["500x500", "1000x1000", "174s"]
SIZE_PATTERN = re.compile(r"(/i/u/)[^/]+(/)")


class _MISS(enum.Enum):
    MISS = "MISS"


class ImageCache:
    IMAGE_CACHE_TTL = 29 * 86400
    NEGATIVE_CACHE_TTL = 6 * 3600
    _NEGATIVE_SENTINEL = b"MISS"

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    @staticmethod
    def _cache_key(url: str) -> str:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return f"img:v1:{h}"

    async def get_many(self, urls: list[str]) -> list[Image.Image | None | _MISS]:
        keys = [self._cache_key(u) for u in urls]
        try:
            cached_values = await self._redis.mget(keys)
        except Exception:
            logger.warning("Redis MGET failed, treating all as cache misses")
            return [_MISS.MISS] * len(urls)

        results: list[Image.Image | None | _MISS] = []
        for cached in cached_values:
            if cached is None:
                results.append(_MISS.MISS)
            elif cached == self._NEGATIVE_SENTINEL:
                results.append(None)
            else:
                results.append(Image.frombytes("RGB", (TILE_SIZE, TILE_SIZE), cached))
        return results

    async def put(self, url: str, img: Image.Image | None) -> None:
        key = self._cache_key(url)
        try:
            if img is not None:
                await self._redis.set(key, img.tobytes(), ex=self.IMAGE_CACHE_TTL)
            else:
                await self._redis.set(
                    key, self._NEGATIVE_SENTINEL, ex=self.NEGATIVE_CACHE_TTL
                )
        except Exception:
            logger.warning(f"Redis SET failed for {key}")

    async def close(self) -> None:
        await self._redis.close()


_cache: ImageCache | None = None


async def init_cache() -> None:
    global _cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis = aioredis.from_url(
        redis_url,
        max_connections=20,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
    _cache = ImageCache(redis)


async def close_cache() -> None:
    global _cache
    if _cache is not None:
        await _cache.close()
        _cache = None


def get_cache() -> ImageCache | None:
    return _cache


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
        urls_to_try = [url] + [
            SIZE_PATTERN.sub(rf"\g<1>{size}\2", url) for size in FALLBACK_SIZES
        ]

        for try_url in urls_to_try:
            if try_url != url:
                logger.debug(f"Trying fallback for {url} -> {try_url}")
            data = await _fetch_image_bytes(session, try_url)

            if data is not None:
                img = Image.open(BytesIO(data))
                img = img.convert("RGB")

                if img.size != (TILE_SIZE, TILE_SIZE):
                    img = img.resize((TILE_SIZE, TILE_SIZE), Image.Resampling.LANCZOS)

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
    cache = get_cache()
    albums_with_urls = [(i, a) for i, a in enumerate(albums) if a.image_url]
    urls = [a.image_url for _, a in albums_with_urls]

    images: list[Image.Image | None] = [None] * len(albums)
    to_download: list[tuple[int, str]] = []

    if cache is not None:
        cached_results = await cache.get_many(urls)
        cache_hits = 0
        for (i, _album), url, cached in zip(albums_with_urls, urls, cached_results):
            if cached is _MISS.MISS:
                to_download.append((i, url))
            elif cached is None:
                pass  # negative-cached, leave as None
            else:
                cache_hits += 1
                images[i] = cached
        if cache_hits:
            logger.debug(f"Cache hits: {cache_hits}/{len(urls)}")
    else:
        to_download = [(i, url) for (i, _), url in zip(albums_with_urls, urls)]

    if to_download:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

        async def _limited_download(url: str) -> Image.Image | None:
            async with semaphore:
                return await _download_image(session, url)

        downloaded = await asyncio.gather(
            *(_limited_download(url) for _, url in to_download)
        )

        for (i, url), img in zip(to_download, downloaded):
            images[i] = img
            if cache is not None:
                await cache.put(url, img)

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
