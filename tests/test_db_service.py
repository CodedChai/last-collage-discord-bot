import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pytest_asyncio

from models import UserPreference, WeeklySchedule
from services import db_service
from services.db_service import (
    init_db,
    save_user_preference,
    get_lastfm_username,
    save_weekly_schedule,
    get_weekly_schedules_for_channel,
    get_scheduled_guild_ids,
    get_weekly_subscriber_count,
    delete_weekly_schedule,
    get_all_weekly_schedules,
)


@pytest_asyncio.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_service, "DB_PATH", str(tmp_path / "test.db"))
    await init_db()
    yield


# --- init_db ---


@pytest.mark.asyncio
async def test_init_db_creates_tables(db):
    import aiosqlite

    async with aiosqlite.connect(db_service.DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    assert "user_preferences" in tables
    assert "weekly_schedules" in tables


@pytest.mark.asyncio
async def test_init_db_idempotent(db):
    await init_db()
    import aiosqlite

    async with aiosqlite.connect(db_service.DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
    assert "user_preferences" in tables
    assert "weekly_schedules" in tables


# --- save_user_preference / get_lastfm_username ---


@pytest.mark.asyncio
async def test_save_and_get_user_preference(db):
    pref = UserPreference(discord_user_id=123, lastfm_username="alice")
    await save_user_preference(pref)
    result = await get_lastfm_username(123)
    assert result == "alice"


@pytest.mark.asyncio
async def test_get_lastfm_username_unknown_user(db):
    result = await get_lastfm_username(999)
    assert result is None


@pytest.mark.asyncio
async def test_save_user_preference_upsert(db):
    pref = UserPreference(discord_user_id=123, lastfm_username="alice")
    await save_user_preference(pref)
    updated = UserPreference(discord_user_id=123, lastfm_username="bob")
    await save_user_preference(updated)
    result = await get_lastfm_username(123)
    assert result == "bob"


# --- save_weekly_schedule / get_weekly_schedules_for_channel ---


@pytest.mark.asyncio
async def test_save_and_get_weekly_schedule(db):
    schedule = WeeklySchedule(
        lastfm_username="alice", guild_id=1, channel_id=10, discord_user_id=100
    )
    await save_weekly_schedule(schedule)
    results = await get_weekly_schedules_for_channel(1, 10)
    assert len(results) == 1
    assert results[0].lastfm_username == "alice"
    assert results[0].guild_id == 1
    assert results[0].channel_id == 10
    assert results[0].discord_user_id == 100


@pytest.mark.asyncio
async def test_get_weekly_schedules_for_unknown_channel(db):
    results = await get_weekly_schedules_for_channel(999, 888)
    assert results == []


@pytest.mark.asyncio
async def test_save_weekly_schedule_upsert(db):
    schedule = WeeklySchedule(
        lastfm_username="alice", guild_id=1, channel_id=10, discord_user_id=100
    )
    await save_weekly_schedule(schedule)
    updated = WeeklySchedule(
        lastfm_username="alice", guild_id=1, channel_id=20, discord_user_id=200
    )
    await save_weekly_schedule(updated)
    results_old = await get_weekly_schedules_for_channel(1, 10)
    assert results_old == []
    results_new = await get_weekly_schedules_for_channel(1, 20)
    assert len(results_new) == 1
    assert results_new[0].channel_id == 20
    assert results_new[0].discord_user_id == 200


# --- get_scheduled_guild_ids ---


@pytest.mark.asyncio
async def test_get_scheduled_guild_ids(db):
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="a", guild_id=1, channel_id=10, discord_user_id=100
        )
    )
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="b", guild_id=2, channel_id=20, discord_user_id=200
        )
    )
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="c", guild_id=1, channel_id=11, discord_user_id=300
        )
    )
    guild_ids = await get_scheduled_guild_ids()
    assert sorted(guild_ids) == [1, 2]


# --- get_weekly_subscriber_count ---


@pytest.mark.asyncio
async def test_get_weekly_subscriber_count(db):
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="a", guild_id=1, channel_id=10, discord_user_id=100
        )
    )
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="b", guild_id=1, channel_id=10, discord_user_id=200
        )
    )
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="c", guild_id=1, channel_id=99, discord_user_id=300
        )
    )
    count = await get_weekly_subscriber_count(1, 10)
    assert count == 2


# --- delete_weekly_schedule ---


@pytest.mark.asyncio
async def test_delete_weekly_schedule_returns_true(db):
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="a", guild_id=1, channel_id=10, discord_user_id=100
        )
    )
    result = await delete_weekly_schedule(100, 1)
    assert result is True


@pytest.mark.asyncio
async def test_delete_weekly_schedule_returns_false_when_missing(db):
    result = await delete_weekly_schedule(999, 999)
    assert result is False


@pytest.mark.asyncio
async def test_delete_weekly_schedule_removes_from_queries(db):
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="a", guild_id=1, channel_id=10, discord_user_id=100
        )
    )
    await delete_weekly_schedule(100, 1)
    results = await get_weekly_schedules_for_channel(1, 10)
    assert results == []
    guild_ids = await get_scheduled_guild_ids()
    assert 1 not in guild_ids


# --- get_all_weekly_schedules ---


@pytest.mark.asyncio
async def test_get_all_weekly_schedules(db):
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="a", guild_id=1, channel_id=10, discord_user_id=100
        )
    )
    await save_weekly_schedule(
        WeeklySchedule(
            lastfm_username="b", guild_id=2, channel_id=20, discord_user_id=200
        )
    )
    all_schedules = await get_all_weekly_schedules()
    assert len(all_schedules) == 2
    usernames = {s.lastfm_username for s in all_schedules}
    assert usernames == {"a", "b"}
