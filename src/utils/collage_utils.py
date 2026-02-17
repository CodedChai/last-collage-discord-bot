import functools
import logging
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from models import AlbumModel

logger = logging.getLogger("lastfm_collage_bot.collage_utils")

TILE_SIZE = 300
DEFAULT_GRID_SIZE = 3

DYNAMIC_GRID_SIZES = [
    (1, 1),  # 1
    (2, 2),  # 4
    (3, 2),  # 6
    (3, 3),  # 9
    (4, 3),  # 12
    (4, 4),  # 16
    (5, 4),  # 20
    (5, 5),  # 25
    (6, 5),  # 30
    (6, 6),  # 36
]


@functools.lru_cache(maxsize=4)
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


def _draw_outlined_text(
    draw: ImageDraw.Draw,
    position: tuple[int, int],
    text: str,
    font,
    outline_range: int = 2,
):
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


def _draw_wrapped_text_bottom_up(
    draw: ImageDraw.Draw, lines: list[str], font, x: int, y: int, line_spacing: int = 2
) -> int:
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


def determine_dynamic_grid_size(albums: list[AlbumModel]) -> tuple[int, int]:
    if not albums:
        return (1, 1)
    best = DYNAMIC_GRID_SIZES[0]
    for i, (cols, rows) in enumerate(DYNAMIC_GRID_SIZES):
        count = cols * rows
        if len(albums) < count:
            break
        if i > 0:
            prev_count = best[0] * best[1]
            first_new_album = albums[prev_count]
            min_plays = 3 if cols * rows > 16 else 2
            if first_new_album.playcount < min_plays:
                break
        best = (cols, rows)
    return best


def resolve_grid_size(
    grid_size_str: str, albums: list[AlbumModel] | None
) -> int | tuple[int, int]:
    if grid_size_str == "dynamic":
        if albums:
            return determine_dynamic_grid_size(albums)
        return (1, 1)
    return int(grid_size_str)


def compose_collage(
    images: list[Image.Image | None],
    albums: list[AlbumModel],
    grid_size: int | tuple[int, int],
) -> BytesIO:
    if isinstance(grid_size, tuple):
        grid_cols, grid_rows = grid_size
    else:
        grid_cols = grid_rows = grid_size

    total_slots = grid_cols * grid_rows
    selected_albums = albums[:total_slots]
    selected_images = images[:total_slots]

    collage = Image.new(
        "RGB", (grid_cols * TILE_SIZE, grid_rows * TILE_SIZE), (0, 0, 0)
    )

    for i, album in enumerate(selected_albums):
        img = (
            selected_images[i]
            if i < len(selected_images) and selected_images[i] is not None
            else _create_placeholder()
        )
        _add_overlay(img, album)

        row, col = divmod(i, grid_cols)
        collage.paste(img, (col * TILE_SIZE, row * TILE_SIZE))

    buffer = BytesIO()
    collage.save(buffer, format="WEBP", quality=85)
    buffer.seek(0)
    return buffer
