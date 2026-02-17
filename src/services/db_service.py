import logging
import os
import time
from contextlib import asynccontextmanager

import asyncpg

from models import UserPreference, WeeklySchedule
from services.metrics_service import DB_QUERY_LATENCY, DB_QUERY_COUNT

logger = logging.getLogger("lastfm_collage_bot.db_service")

DATABASE_URL = os.getenv("DATABASE_URL")


class DatabaseService:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        async with self.pool.acquire() as conn:
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

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
        logger.info("Database connection pool closed")

    @asynccontextmanager
    async def _track_query(self, operation: str):
        start = time.perf_counter()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start
            DB_QUERY_LATENCY.record(duration, {"operation": operation})
            DB_QUERY_COUNT.add(1, {"operation": operation, "status": status})

    async def get_lastfm_username(self, discord_user_id: int) -> str | None:
        async with self._track_query("get_lastfm_username"):
            row = await self.pool.fetchrow(
                "SELECT lastfm_username FROM user_preferences WHERE discord_user_id = $1",
                discord_user_id,
            )
            return row["lastfm_username"] if row else None

    async def save_user_preference(self, preference: UserPreference):
        async with self._track_query("save_user_preference"):
            await self.pool.execute(
                """
                INSERT INTO user_preferences (discord_user_id, lastfm_username)
                VALUES ($1, $2)
                ON CONFLICT(discord_user_id) DO UPDATE SET lastfm_username = excluded.lastfm_username
                """,
                preference.discord_user_id,
                preference.lastfm_username,
            )

    async def save_weekly_schedule(self, schedule: WeeklySchedule):
        async with self._track_query("save_weekly_schedule"):
            await self.pool.execute(
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
        self, guild_id: int, channel_id: int
    ) -> list[WeeklySchedule]:
        async with self._track_query("get_weekly_schedules_for_channel"):
            rows = await self.pool.fetch(
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

    async def get_scheduled_guild_ids(self) -> list[int]:
        async with self._track_query("get_scheduled_guild_ids"):
            rows = await self.pool.fetch("SELECT DISTINCT guild_id FROM weekly_schedules")
            return [row["guild_id"] for row in rows]

    async def get_weekly_subscriber_count(self, guild_id: int, channel_id: int) -> int:
        async with self._track_query("get_weekly_subscriber_count"):
            count = await self.pool.fetchval(
                "SELECT COUNT(DISTINCT discord_user_id) FROM weekly_schedules WHERE guild_id = $1 AND channel_id = $2",
                guild_id,
                channel_id,
            )
            return count or 0

    async def delete_weekly_schedule(self, discord_user_id: int, guild_id: int) -> bool:
        async with self._track_query("delete_weekly_schedule"):
            result = await self.pool.execute(
                "DELETE FROM weekly_schedules WHERE discord_user_id = $1 AND guild_id = $2",
                discord_user_id,
                guild_id,
            )
            return result != "DELETE 0"

    async def get_all_weekly_schedules(self) -> list[WeeklySchedule]:
        async with self._track_query("get_all_weekly_schedules"):
            rows = await self.pool.fetch(
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


_db: DatabaseService | None = None


def get_db() -> DatabaseService:
    if _db is None:
        raise RuntimeError("DatabaseService not initialized; call init_db() first")
    return _db


async def init_db():
    global _db
    _db = DatabaseService()
    await _db.init()


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_lastfm_username(discord_user_id: int) -> str | None:
    return await get_db().get_lastfm_username(discord_user_id)


async def save_user_preference(preference: UserPreference):
    await get_db().save_user_preference(preference)


async def save_weekly_schedule(schedule: WeeklySchedule):
    await get_db().save_weekly_schedule(schedule)


async def get_weekly_schedules_for_channel(
    guild_id: int, channel_id: int
) -> list[WeeklySchedule]:
    return await get_db().get_weekly_schedules_for_channel(guild_id, channel_id)


async def get_scheduled_guild_ids() -> list[int]:
    return await get_db().get_scheduled_guild_ids()


async def get_weekly_subscriber_count(guild_id: int, channel_id: int) -> int:
    return await get_db().get_weekly_subscriber_count(guild_id, channel_id)


async def delete_weekly_schedule(discord_user_id: int, guild_id: int) -> bool:
    return await get_db().delete_weekly_schedule(discord_user_id, guild_id)


async def get_all_weekly_schedules() -> list[WeeklySchedule]:
    return await get_db().get_all_weekly_schedules()
