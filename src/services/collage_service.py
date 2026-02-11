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

DEFAULT_GRID_SIZE = 3
TILE_SIZE = 300


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


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = os.getenv("FONT_PATH")
    if font_path:
        try:
            font_index = int(os.getenv("FONT_INDEX", "0"))
            return ImageFont.truetype(font_path, size, index=font_index)
        except Exception as e:
            logger.warning(
                f"Failed to load font from {font_path}: {e}. Using default font."
            )
    else:
        logger.debug("FONT_PATH not set, using default font")
    return ImageFont.load_default()


def _draw_outlined_text(draw: ImageDraw.Draw, position: tuple[int, int], text: str, font, outline_range: int = 2):
    x, y = position
    for x_offset in range(-outline_range, outline_range + 1):
        for y_offset in range(-outline_range, outline_range + 1):
            if x_offset != 0 or y_offset != 0:
                draw.text(
                    (x + x_offset, y + y_offset),
                    text,
                    font=font,
                    fill=(0, 0, 0),
                )
    draw.text(position, text, font=font, fill=(255, 255, 255))


def _wrap_text(draw: ImageDraw.Draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def _draw_wrapped_text_bottom_up(draw: ImageDraw.Draw, lines: list[str], font, x: int, y: int, line_spacing: int = 2) -> int:
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    for i, line in enumerate(reversed(lines)):
        y -= line_height
        _draw_outlined_text(draw, (x, y), line, font)
        if i < len(lines) - 1:
            y -= line_spacing
    return y


def _add_overlay(image: Image.Image, album: AlbumModel) -> Image.Image:
    draw = ImageDraw.Draw(image)
    padding = 8
    block_spacing = 6
    max_width = TILE_SIZE - padding * 2
    font = _load_font(24)
    small_font = _load_font(18)

    _draw_outlined_text(draw, (padding, padding), f"{album.playcount} plays", font)

    album_lines = _wrap_text(draw, album.name, small_font, max_width)
    artist_lines = _wrap_text(draw, album.artist, font, max_width)

    y = TILE_SIZE - padding
    y = _draw_wrapped_text_bottom_up(draw, album_lines, small_font, padding, y)
    y -= block_spacing
    _draw_wrapped_text_bottom_up(draw, artist_lines, font, padding, y)

    return image


def _create_placeholder() -> Image.Image:
    return Image.new("RGB", (TILE_SIZE, TILE_SIZE), (30, 30, 30))


async def generate_collage(
    session: aiohttp.ClientSession, albums: list[AlbumModel], grid_size: int = DEFAULT_GRID_SIZE
) -> BytesIO:
    selected_albums = albums[: grid_size * grid_size]
    logger.info(f"Generating {grid_size}x{grid_size} collage with {len(selected_albums)} albums")

    albums_with_urls = [(i, a) for i, a in enumerate(selected_albums) if a.image_url]
    downloaded = await asyncio.gather(
        *(_download_image(session, album.image_url) for _, album in albums_with_urls)
    )

    images: list[Image.Image | None] = [None] * len(selected_albums)
    for (i, _), img in zip(albums_with_urls, downloaded):
        images[i] = img

    successful_downloads = sum(1 for img in images if img is not None)
    logger.info(
        f"Successfully downloaded {successful_downloads}/{len(selected_albums)} album cover images"
    )

    collage_size = grid_size * TILE_SIZE
    collage = Image.new("RGB", (collage_size, collage_size), (0, 0, 0))

    for i, album in enumerate(selected_albums):
        img = images[i] if images[i] is not None else _create_placeholder()
        _add_overlay(img, album)

        row, col = divmod(i, grid_size)
        collage.paste(img, (col * TILE_SIZE, row * TILE_SIZE))

    buffer = BytesIO()
    collage.save(buffer, format="PNG")
    buffer.seek(0)
    logger.info("Collage generated successfully")
    return buffer
