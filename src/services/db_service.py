import logging
import os

import aiosqlite

from models import UserPreference, WeeklySchedule

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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_schedules (
                lastfm_username TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                discord_user_id INTEGER NOT NULL,
                PRIMARY KEY (lastfm_username, guild_id)
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


async def save_user_preference(preference: UserPreference):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences (discord_user_id, lastfm_username)
            VALUES (?, ?)
            ON CONFLICT(discord_user_id) DO UPDATE SET lastfm_username = excluded.lastfm_username
            """,
            (preference.discord_user_id, preference.lastfm_username),
        )
        await db.commit()


async def save_weekly_schedule(schedule: WeeklySchedule):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO weekly_schedules (lastfm_username, guild_id, channel_id, discord_user_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(lastfm_username, guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                discord_user_id = excluded.discord_user_id
            """,
            (schedule.lastfm_username, schedule.guild_id, schedule.channel_id, schedule.discord_user_id),
        )
        await db.commit()


async def get_weekly_schedules_for_channel(guild_id: int, channel_id: int) -> list[WeeklySchedule]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT lastfm_username, guild_id, channel_id, discord_user_id FROM weekly_schedules WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        )
        rows = await cursor.fetchall()
        return [
            WeeklySchedule(
                lastfm_username=row[0],
                guild_id=row[1],
                channel_id=row[2],
                discord_user_id=row[3],
            )
            for row in rows
        ]


async def get_scheduled_guild_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT guild_id FROM weekly_schedules"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_weekly_subscriber_count(guild_id: int, channel_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT discord_user_id) FROM weekly_schedules WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def delete_weekly_schedule(discord_user_id: int, guild_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM weekly_schedules WHERE discord_user_id = ? AND guild_id = ?",
            (discord_user_id, guild_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_weekly_schedules() -> list[WeeklySchedule]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT lastfm_username, guild_id, channel_id, discord_user_id FROM weekly_schedules"
        )
        rows = await cursor.fetchall()
        return [
            WeeklySchedule(
                lastfm_username=row[0],
                guild_id=row[1],
                channel_id=row[2],
                discord_user_id=row[3],
            )
            for row in rows
        ]
