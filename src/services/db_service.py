import logging
import os

import aiosqlite

logger = logging.getLogger("lastfm_collage_bot.db_service")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                discord_user_id INTEGER PRIMARY KEY,
                lastfm_username TEXT NOT NULL
            )
            """
        )
        await db.commit()
    logger.info("Database initialized")


async def get_lastfm_username(discord_user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT lastfm_username FROM user_preferences WHERE discord_user_id = ?",
            (discord_user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def save_lastfm_username(discord_user_id: int, lastfm_username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences (discord_user_id, lastfm_username)
            VALUES (?, ?)
            ON CONFLICT(discord_user_id) DO UPDATE SET lastfm_username = excluded.lastfm_username
            """,
            (discord_user_id, lastfm_username),
        )
        await db.commit()
