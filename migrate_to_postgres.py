"""One-time migration script: SQLite (bot.db) → Railway PostgreSQL.

Usage:
    DATABASE_URL="postgresql://..." python migrate_to_postgres.py [path/to/bot.db]

Defaults to src/bot.db if no path is given.
"""

import asyncio
import sqlite3
import sys

import asyncpg

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL")
SQLITE_PATH = sys.argv[1] if len(sys.argv) > 1 else "src/bot.db"


async def migrate():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is not set.")
        sys.exit(1)

    # --- Read from SQLite ---
    print(f"Reading from SQLite: {SQLITE_PATH}")
    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row

    prefs = src.execute(
        "SELECT discord_user_id, lastfm_username FROM user_preferences"
    ).fetchall()
    schedules = src.execute(
        "SELECT lastfm_username, guild_id, channel_id, discord_user_id FROM weekly_schedules"
    ).fetchall()
    src.close()

    print(f"  Found {len(prefs)} user_preferences rows")
    print(f"  Found {len(schedules)} weekly_schedules rows")

    # --- Write to PostgreSQL ---
    print(f"Connecting to PostgreSQL...")
    conn = await asyncpg.connect(DATABASE_URL)

    # Ensure tables exist
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            discord_user_id BIGINT PRIMARY KEY,
            lastfm_username TEXT NOT NULL,
            created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_ts TIMESTAMPTZ NOT NULL DEFAULT now()
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
            created_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (lastfm_username, guild_id)
        )
        """
    )

    # Add timestamp columns if they don't already exist
    for table in ("user_preferences", "weekly_schedules"):
        for col in ("created_ts", "updated_ts"):
            await conn.execute(f"""
                ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} TIMESTAMPTZ NOT NULL DEFAULT now()
            """)

    # Insert user_preferences
    if prefs:
        await conn.executemany(
            """
            INSERT INTO user_preferences (discord_user_id, lastfm_username)
            VALUES ($1, $2)
            ON CONFLICT (discord_user_id) DO UPDATE SET lastfm_username = EXCLUDED.lastfm_username, updated_ts = now()
            """,
            [(int(r["discord_user_id"]), r["lastfm_username"]) for r in prefs],
        )
    print(f"  Inserted {len(prefs)} user_preferences rows")

    # Insert weekly_schedules
    if schedules:
        await conn.executemany(
            """
            INSERT INTO weekly_schedules (lastfm_username, guild_id, channel_id, discord_user_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (lastfm_username, guild_id) DO UPDATE SET
                channel_id = EXCLUDED.channel_id,
                discord_user_id = EXCLUDED.discord_user_id,
                updated_ts = now()
            """,
            [
                (
                    r["lastfm_username"],
                    int(r["guild_id"]),
                    int(r["channel_id"]),
                    int(r["discord_user_id"]),
                )
                for r in schedules
            ],
        )
    print(f"  Inserted {len(schedules)} weekly_schedules rows")

    # --- Print migrated data from PostgreSQL ---
    print("\n--- Migrated user_preferences ---")
    pg_prefs = await conn.fetch(
        "SELECT discord_user_id, lastfm_username, created_ts, updated_ts FROM user_preferences ORDER BY discord_user_id"
    )
    for row in pg_prefs:
        print(
            f"  discord_user_id={row['discord_user_id']}, lastfm_username={row['lastfm_username']}, created_ts={row['created_ts']}, updated_ts={row['updated_ts']}"
        )

    print("\n--- Migrated weekly_schedules ---")
    pg_schedules = await conn.fetch(
        "SELECT lastfm_username, guild_id, channel_id, discord_user_id, created_ts, updated_ts FROM weekly_schedules ORDER BY lastfm_username, guild_id"
    )
    for row in pg_schedules:
        print(
            f"  lastfm_username={row['lastfm_username']}, guild_id={row['guild_id']}, channel_id={row['channel_id']}, discord_user_id={row['discord_user_id']}, created_ts={row['created_ts']}, updated_ts={row['updated_ts']}"
        )

    await conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
