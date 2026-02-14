import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from models import UserPreference, WeeklySchedule
from services import db_service
from services.db_service import (
    save_user_preference,
    get_lastfm_username,
    save_weekly_schedule,
    get_weekly_schedules_for_channel,
    get_scheduled_guild_ids,
    get_weekly_subscriber_count,
    delete_weekly_schedule,
    get_all_weekly_schedules,
)


@pytest.fixture
def mock_pool(monkeypatch):
    pool = AsyncMock()
    monkeypatch.setattr(db_service, "_pool", pool)
    return pool


# --- save_user_preference / get_lastfm_username ---


@pytest.mark.asyncio
async def test_save_and_get_user_preference(mock_pool):
    mock_pool.execute.return_value = "INSERT 0 1"
    pref = UserPreference(discord_user_id=123, lastfm_username="alice")
    await save_user_preference(pref)
    mock_pool.execute.assert_awaited_once()
    call_args = mock_pool.execute.call_args
    assert 123 in call_args[0]
    assert "alice" in call_args[0]


@pytest.mark.asyncio
async def test_get_lastfm_username_found(mock_pool):
    mock_pool.fetchrow.return_value = {"lastfm_username": "alice"}
    result = await get_lastfm_username(123)
    assert result == "alice"
    mock_pool.fetchrow.assert_awaited_once()
    call_args = mock_pool.fetchrow.call_args
    assert 123 in call_args[0]


@pytest.mark.asyncio
async def test_get_lastfm_username_unknown_user(mock_pool):
    mock_pool.fetchrow.return_value = None
    result = await get_lastfm_username(999)
    assert result is None


@pytest.mark.asyncio
async def test_save_user_preference_upsert(mock_pool):
    mock_pool.execute.return_value = "INSERT 0 1"
    pref = UserPreference(discord_user_id=123, lastfm_username="alice")
    await save_user_preference(pref)
    updated = UserPreference(discord_user_id=123, lastfm_username="bob")
    await save_user_preference(updated)
    assert mock_pool.execute.await_count == 2
    second_call_args = mock_pool.execute.call_args_list[1][0]
    assert "bob" in second_call_args


# --- save_weekly_schedule / get_weekly_schedules_for_channel ---


@pytest.mark.asyncio
async def test_save_and_get_weekly_schedule(mock_pool):
    mock_pool.execute.return_value = "INSERT 0 1"
    schedule = WeeklySchedule(
        lastfm_username="alice", guild_id=1, channel_id=10, discord_user_id=100
    )
    await save_weekly_schedule(schedule)
    mock_pool.execute.assert_awaited_once()
    call_args = mock_pool.execute.call_args[0]
    assert "alice" in call_args
    assert 1 in call_args
    assert 10 in call_args
    assert 100 in call_args


@pytest.mark.asyncio
async def test_get_weekly_schedules_for_channel(mock_pool):
    mock_pool.fetch.return_value = [
        {
            "lastfm_username": "alice",
            "guild_id": 1,
            "channel_id": 10,
            "discord_user_id": 100,
        }
    ]
    results = await get_weekly_schedules_for_channel(1, 10)
    assert len(results) == 1
    assert results[0].lastfm_username == "alice"
    assert results[0].guild_id == 1
    assert results[0].channel_id == 10
    assert results[0].discord_user_id == 100
    mock_pool.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_weekly_schedules_for_unknown_channel(mock_pool):
    mock_pool.fetch.return_value = []
    results = await get_weekly_schedules_for_channel(999, 888)
    assert results == []


# --- get_scheduled_guild_ids ---


@pytest.mark.asyncio
async def test_get_scheduled_guild_ids(mock_pool):
    mock_pool.fetch.return_value = [
        {"guild_id": 1},
        {"guild_id": 2},
    ]
    guild_ids = await get_scheduled_guild_ids()
    assert sorted(guild_ids) == [1, 2]
    mock_pool.fetch.assert_awaited_once()


# --- get_weekly_subscriber_count ---


@pytest.mark.asyncio
async def test_get_weekly_subscriber_count(mock_pool):
    mock_pool.fetchval.return_value = 2
    count = await get_weekly_subscriber_count(1, 10)
    assert count == 2
    mock_pool.fetchval.assert_awaited_once()
    call_args = mock_pool.fetchval.call_args[0]
    assert 1 in call_args
    assert 10 in call_args


# --- delete_weekly_schedule ---


@pytest.mark.asyncio
async def test_delete_weekly_schedule_returns_true(mock_pool):
    mock_pool.execute.return_value = "DELETE 1"
    result = await delete_weekly_schedule(100, 1)
    assert result is True
    mock_pool.execute.assert_awaited_once()
    call_args = mock_pool.execute.call_args[0]
    assert 100 in call_args
    assert 1 in call_args


@pytest.mark.asyncio
async def test_delete_weekly_schedule_returns_false_when_missing(mock_pool):
    mock_pool.execute.return_value = "DELETE 0"
    result = await delete_weekly_schedule(999, 999)
    assert result is False


# --- get_all_weekly_schedules ---


@pytest.mark.asyncio
async def test_get_all_weekly_schedules(mock_pool):
    mock_pool.fetch.return_value = [
        {
            "lastfm_username": "a",
            "guild_id": 1,
            "channel_id": 10,
            "discord_user_id": 100,
        },
        {
            "lastfm_username": "b",
            "guild_id": 2,
            "channel_id": 20,
            "discord_user_id": 200,
        },
    ]
    all_schedules = await get_all_weekly_schedules()
    assert len(all_schedules) == 2
    usernames = {s.lastfm_username for s in all_schedules}
    assert usernames == {"a", "b"}
    mock_pool.fetch.assert_awaited_once()
