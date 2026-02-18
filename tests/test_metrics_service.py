import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from services import metrics_service
from services.metrics_service import (
    _GuildGauge,
    track_command,
    COMMAND_LATENCY,
    COMMAND_COUNT,
)


# --- _GuildGauge ---


class TestGuildGauge:
    def setup_method(self):
        self.gauge = _GuildGauge()

    def test_set(self):
        self.gauge.set(10)
        assert metrics_service._active_guilds == 10

    def test_inc_default(self):
        self.gauge.set(5)
        self.gauge.inc()
        assert metrics_service._active_guilds == 6

    def test_inc_custom_amount(self):
        self.gauge.set(5)
        self.gauge.inc(3)
        assert metrics_service._active_guilds == 8

    def test_dec_default(self):
        self.gauge.set(5)
        self.gauge.dec()
        assert metrics_service._active_guilds == 4

    def test_dec_custom_amount(self):
        self.gauge.set(5)
        self.gauge.dec(2)
        assert metrics_service._active_guilds == 3

    def test_set_overrides_previous(self):
        self.gauge.set(100)
        self.gauge.set(0)
        assert metrics_service._active_guilds == 0


# --- _observe_active_guilds ---


class TestObserveActiveGuilds:
    def test_yields_current_value(self):
        metrics_service._active_guilds = 42
        from services.metrics_service import _observe_active_guilds

        observations = list(_observe_active_guilds(None))
        assert len(observations) == 1
        assert observations[0].value == 42


# --- track_command ---


class TestTrackCommand:
    @pytest.mark.asyncio
    async def test_records_success(self):
        @track_command("test_cmd")
        async def my_func():
            return "ok"

        with patch.object(COMMAND_LATENCY, "record") as mock_latency, \
             patch.object(COMMAND_COUNT, "add") as mock_count:
            result = await my_func()

        assert result == "ok"
        mock_latency.assert_called_once()
        args = mock_latency.call_args
        assert args[0][1] == {"command": "test_cmd"}
        assert isinstance(args[0][0], float)
        assert args[0][0] > 0

        mock_count.assert_called_once_with(
            1, {"command": "test_cmd", "status": "success"}
        )

    @pytest.mark.asyncio
    async def test_records_error_and_reraises(self):
        @track_command("fail_cmd")
        async def my_func():
            raise ValueError("boom")

        with patch.object(COMMAND_LATENCY, "record") as mock_latency, \
             patch.object(COMMAND_COUNT, "add") as mock_count:
            with pytest.raises(ValueError, match="boom"):
                await my_func()

        mock_latency.assert_called_once()
        assert mock_latency.call_args[0][1] == {"command": "fail_cmd"}

        mock_count.assert_called_once_with(
            1, {"command": "fail_cmd", "status": "error"}
        )

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        @track_command("arg_cmd")
        async def my_func(a, b, key=None):
            return (a, b, key)

        with patch.object(COMMAND_LATENCY, "record"), \
             patch.object(COMMAND_COUNT, "add"):
            result = await my_func(1, 2, key="val")

        assert result == (1, 2, "val")

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @track_command("named_cmd")
        async def my_special_func():
            pass

        assert my_special_func.__name__ == "my_special_func"

    @pytest.mark.asyncio
    async def test_return_value_forwarded(self):
        @track_command("ret_cmd")
        async def my_func():
            return {"data": [1, 2, 3]}

        with patch.object(COMMAND_LATENCY, "record"), \
             patch.object(COMMAND_COUNT, "add"):
            result = await my_func()

        assert result == {"data": [1, 2, 3]}


# --- Instrument definitions ---


class TestInstrumentDefinitions:
    """Verify all expected metric instruments are created with correct names."""

    def test_command_latency_name(self):
        assert COMMAND_LATENCY.name == "bot.command.duration"

    def test_command_count_name(self):
        assert COMMAND_COUNT.name == "bot.command.total"

    def test_lastfm_request_latency_name(self):
        assert metrics_service.LASTFM_REQUEST_LATENCY.name == "bot.lastfm.request.duration"

    def test_lastfm_request_count_name(self):
        assert metrics_service.LASTFM_REQUEST_COUNT.name == "bot.lastfm.request.total"

    def test_db_query_latency_name(self):
        assert metrics_service.DB_QUERY_LATENCY.name == "bot.db.query.duration"

    def test_db_query_count_name(self):
        assert metrics_service.DB_QUERY_COUNT.name == "bot.db.query.total"

    def test_image_cache_hits_name(self):
        assert metrics_service.IMAGE_CACHE_HITS.name == "bot.image_cache.hits"

    def test_image_cache_misses_name(self):
        assert metrics_service.IMAGE_CACHE_MISSES.name == "bot.image_cache.misses"

    def test_image_download_latency_name(self):
        assert metrics_service.IMAGE_DOWNLOAD_LATENCY.name == "bot.image_download.duration"

    def test_collage_generation_latency_name(self):
        assert metrics_service.COLLAGE_GENERATION_LATENCY.name == "bot.collage_generation.duration"

    def test_weekly_subscribers_name(self):
        assert metrics_service.WEEKLY_SUBSCRIBERS.name == "bot.weekly_subscribers"

    def test_active_guilds_gauge_name(self):
        assert metrics_service.ACTIVE_GUILDS_GAUGE.name == "bot.active_guilds"
