import discord

from services.collage_service import generate_collage


async def send_collage(destination, session, embed, top_albums, grid_size):
    has_albums = top_albums and top_albums.albums
    if has_albums:
        buffer = await generate_collage(session, top_albums.albums, grid_size)
        embed.set_image(url="attachment://collage.jpg")
        await destination.send(
            embed=embed, file=discord.File(buffer, filename="collage.jpg")
        )
    else:
        await destination.send(embed=embed)
