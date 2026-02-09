import asyncio
import logging
from io import BytesIO

import aiohttp
from PIL import Image

from models import AlbumModel

logger = logging.getLogger('lastfm_collage_bot.collage_service')

GRID_SIZE = 3
TILE_SIZE = 300
COLLAGE_SIZE = GRID_SIZE * TILE_SIZE


async def _download_image(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return Image.open(BytesIO(data)).resize((TILE_SIZE, TILE_SIZE))
            else:
                logger.warning(f"Failed to download image from {url}: HTTP {response.status}")
                return None
    except aiohttp.ClientError as e:
        logger.warning(f"Network error downloading image from {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error processing image from {url}: {e}")
        return None


async def generate_collage(
    session: aiohttp.ClientSession, albums: list[AlbumModel]
) -> BytesIO:
    albums_with_art = [a for a in albums if a.image_url][:GRID_SIZE * GRID_SIZE]
    logger.info(f"Generating collage with {len(albums_with_art)} albums")

    images = await asyncio.gather(
        *(_download_image(session, album.image_url) for album in albums_with_art)
    )

    successful_downloads = sum(1 for img in images if img is not None)
    logger.info(f"Successfully downloaded {successful_downloads}/{len(images)} album cover images")

    collage = Image.new("RGB", (COLLAGE_SIZE, COLLAGE_SIZE), (0, 0, 0))

    for i, img in enumerate(images):
        if img is None:
            continue
        row, col = divmod(i, GRID_SIZE)
        collage.paste(img, (col * TILE_SIZE, row * TILE_SIZE))

    buffer = BytesIO()
    collage.save(buffer, format="PNG")
    buffer.seek(0)
    logger.info("Collage generated successfully")
    return buffer
