import os
import sys
from io import BytesIO
from unittest.mock import AsyncMock, patch

import discord
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cogs.messaging import send_collage


# --- send_collage ---


class TestSendCollage:
    @pytest.mark.asyncio
    async def test_with_albums_sends_file_and_embed(self):
        destination = AsyncMock()
        session = AsyncMock()
        embed = discord.Embed(title="Test")

        from models import TopAlbumsModel

        top_albums = TopAlbumsModel.model_validate(
            {
                "topalbums": {
                    "album": [
                        {
                            "name": "Album",
                            "artist": {"name": "Art"},
                            "@attr": {"rank": 1},
                            "playcount": 5,
                            "image": [],
                        },
                    ]
                }
            }
        )

        fake_buffer = BytesIO(b"fake image data")
        with patch(
            "cogs.messaging.generate_collage", return_value=fake_buffer
        ) as mock_gen:
            await send_collage(destination, session, embed, top_albums, 3)
            mock_gen.assert_awaited_once_with(session, top_albums.albums, 3)

        destination.send.assert_awaited_once()
        call_kwargs = destination.send.call_args.kwargs
        assert call_kwargs["embed"] is embed
        assert isinstance(call_kwargs["file"], discord.File)
        assert embed.image.url == "attachment://collage.webp"

    @pytest.mark.asyncio
    async def test_none_albums_sends_embed_only(self):
        destination = AsyncMock()
        session = AsyncMock()
        embed = discord.Embed(title="Test")

        await send_collage(destination, session, embed, None, 3)

        destination.send.assert_awaited_once_with(embed=embed)

    @pytest.mark.asyncio
    async def test_empty_albums_sends_embed_only(self):
        destination = AsyncMock()
        session = AsyncMock()
        embed = discord.Embed(title="Test")

        from models import TopAlbumsModel

        top_albums = TopAlbumsModel.model_validate({"topalbums": {"album": []}})

        await send_collage(destination, session, embed, top_albums, 3)

        destination.send.assert_awaited_once_with(embed=embed)
