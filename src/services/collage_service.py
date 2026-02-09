import asyncio
import logging
import os
from io import BytesIO

import aiohttp
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from models import AlbumModel

load_dotenv()

logger = logging.getLogger("lastfm_collage_bot.collage_service")

GRID_SIZE = 3
TILE_SIZE = 300
COLLAGE_SIZE = GRID_SIZE * TILE_SIZE


async def _download_image(
    session: aiohttp.ClientSession, url: str
) -> Image.Image | None:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return Image.open(BytesIO(data)).resize((TILE_SIZE, TILE_SIZE))
            else:
                logger.warning(
                    f"Failed to download image from {url}: HTTP {response.status}"
                )
                return None
    except aiohttp.ClientError as e:
        logger.warning(f"Network error downloading image from {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error processing image from {url}: {e}")
        return None


def _add_play_count_overlay(image: Image.Image, play_count: int) -> Image.Image:
    """Add play count text overlay to the top-left corner of an image."""
    draw = ImageDraw.Draw(image)
    text = f"{play_count} plays"

    font_path = os.getenv("FONT_PATH")
    if font_path:
        try:
            font = ImageFont.truetype(font_path, 24)
        except Exception as e:
            logger.warning(
                f"Failed to load font from {font_path}: {e}. Using default font."
            )
            font = ImageFont.load_default()
    else:
        logger.debug("FONT_PATH not set, using default font")
        font = ImageFont.load_default()

    padding = 8

    outline_range = 2
    for x_offset in range(-outline_range, outline_range + 1):
        for y_offset in range(-outline_range, outline_range + 1):
            if x_offset != 0 or y_offset != 0:
                draw.text(
                    (padding + x_offset, padding + y_offset),
                    text,
                    font=font,
                    fill=(0, 0, 0),
                )

    draw.text((padding, padding), text, font=font, fill=(255, 255, 255))

    return image


async def generate_collage(
    session: aiohttp.ClientSession, albums: list[AlbumModel]
) -> BytesIO:
    albums_with_art = [a for a in albums if a.image_url][: GRID_SIZE * GRID_SIZE]
    logger.info(f"Generating collage with {len(albums_with_art)} albums")

    images = await asyncio.gather(
        *(_download_image(session, album.image_url) for album in albums_with_art)
    )

    successful_downloads = sum(1 for img in images if img is not None)
    logger.info(
        f"Successfully downloaded {successful_downloads}/{len(images)} album cover images"
    )

    collage = Image.new("RGB", (COLLAGE_SIZE, COLLAGE_SIZE), (0, 0, 0))

    for i, img in enumerate(images):
        if img is None:
            continue

        # Add play count overlay to the image
        album = albums_with_art[i]
        img_with_overlay = _add_play_count_overlay(img, album.playcount)

        row, col = divmod(i, GRID_SIZE)
        collage.paste(img_with_overlay, (col * TILE_SIZE, row * TILE_SIZE))

    buffer = BytesIO()
    collage.save(buffer, format="PNG")
    buffer.seek(0)
    logger.info("Collage generated successfully")
    return buffer
