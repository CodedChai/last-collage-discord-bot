import logging
import os

import asyncpg

from models import UserPreference, WeeklySchedule

logger = logging.getLogger("lastfm_collage_bot.db_service")

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL)
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                discord_user_id BIGINT PRIMARY KEY,
                lastfm_username TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_schedules (
                lastfm_username TEXT NOT NULL,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                discord_user_id BIGINT NOT NULL,
                PRIMARY KEY (lastfm_username, guild_id)
            )
            """
        )
    logger.info("Database initialized")


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
    logger.info("Database connection pool closed")


async def get_lastfm_username(discord_user_id: int) -> str | None:
    row = await _pool.fetchrow(
        "SELECT lastfm_username FROM user_preferences WHERE discord_user_id = $1",
        discord_user_id,
    )
    return row["lastfm_username"] if row else None


async def save_user_preference(preference: UserPreference):
    await _pool.execute(
        """
        INSERT INTO user_preferences (discord_user_id, lastfm_username)
        VALUES ($1, $2)
        ON CONFLICT(discord_user_id) DO UPDATE SET lastfm_username = excluded.lastfm_username
        """,
        preference.discord_user_id,
        preference.lastfm_username,
    )


async def save_weekly_schedule(schedule: WeeklySchedule):
    await _pool.execute(
        """
        INSERT INTO weekly_schedules (lastfm_username, guild_id, channel_id, discord_user_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT(lastfm_username, guild_id) DO UPDATE SET
            channel_id = excluded.channel_id,
            discord_user_id = excluded.discord_user_id
        """,
        schedule.lastfm_username,
        schedule.guild_id,
        schedule.channel_id,
        schedule.discord_user_id,
    )


async def get_weekly_schedules_for_channel(
    guild_id: int, channel_id: int
) -> list[WeeklySchedule]:
    rows = await _pool.fetch(
        "SELECT lastfm_username, guild_id, channel_id, discord_user_id FROM weekly_schedules WHERE guild_id = $1 AND channel_id = $2",
        guild_id,
        channel_id,
    )
    return [
        WeeklySchedule(
            lastfm_username=row["lastfm_username"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            discord_user_id=row["discord_user_id"],
        )
        for row in rows
    ]


async def get_scheduled_guild_ids() -> list[int]:
    rows = await _pool.fetch("SELECT DISTINCT guild_id FROM weekly_schedules")
    return [row["guild_id"] for row in rows]


async def get_weekly_subscriber_count(guild_id: int, channel_id: int) -> int:
    count = await _pool.fetchval(
        "SELECT COUNT(DISTINCT discord_user_id) FROM weekly_schedules WHERE guild_id = $1 AND channel_id = $2",
        guild_id,
        channel_id,
    )
    return count or 0


async def delete_weekly_schedule(discord_user_id: int, guild_id: int) -> bool:
    result = await _pool.execute(
        "DELETE FROM weekly_schedules WHERE discord_user_id = $1 AND guild_id = $2",
        discord_user_id,
        guild_id,
    )
    return result != "DELETE 0"


async def get_all_weekly_schedules() -> list[WeeklySchedule]:
    rows = await _pool.fetch(
        "SELECT lastfm_username, guild_id, channel_id, discord_user_id FROM weekly_schedules"
    )
    return [
        WeeklySchedule(
            lastfm_username=row["lastfm_username"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            discord_user_id=row["discord_user_id"],
        )
        for row in rows
    ]
