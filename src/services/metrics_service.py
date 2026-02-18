import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger("lastfm_collage_bot.metrics")

# Configure OTel meter provider
_resource = Resource.create({
    "service.name": os.getenv("OTEL_SERVICE_NAME", "lastfm-collage-bot"),
})
_exporter = OTLPMetricExporter()
_reader = PeriodicExportingMetricReader(_exporter, export_interval_millis=60_000)
_provider = MeterProvider(resource=_resource, metric_readers=[_reader])
metrics.set_meter_provider(_provider)

_meter = metrics.get_meter("lastfm-collage-bot")

# Command metrics
COMMAND_LATENCY = _meter.create_histogram(
    "bot.command.duration",
    description="Slash command execution time",
    unit="s",
)
COMMAND_COUNT = _meter.create_counter(
    "bot.command.total",
    description="Slash command invocation count",
)

# Last.fm API metrics
LASTFM_REQUEST_LATENCY = _meter.create_histogram(
    "bot.lastfm.request.duration",
    description="Last.fm API call duration",
    unit="s",
)
LASTFM_REQUEST_COUNT = _meter.create_counter(
    "bot.lastfm.request.total",
    description="Last.fm API call count",
)

# Database metrics
DB_QUERY_LATENCY = _meter.create_histogram(
    "bot.db.query.duration",
    description="Database query duration",
    unit="s",
)
DB_QUERY_COUNT = _meter.create_counter(
    "bot.db.query.total",
    description="Database query count",
)

# Image cache metrics
IMAGE_CACHE_HITS = _meter.create_counter(
    "bot.image_cache.hits",
    description="Image cache hit count",
)
IMAGE_CACHE_MISSES = _meter.create_counter(
    "bot.image_cache.misses",
    description="Image cache miss count",
)

# Image download metrics
IMAGE_DOWNLOAD_LATENCY = _meter.create_histogram(
    "bot.image_download.duration",
    description="Image download time",
    unit="s",
)

# Collage generation metrics
COLLAGE_GENERATION_LATENCY = _meter.create_histogram(
    "bot.collage_generation.duration",
    description="Total collage generation time",
    unit="s",
)

# Bot metrics - track guild count with observable gauge
_active_guilds = 0


def _observe_active_guilds(options):
    yield metrics.Observation(_active_guilds)


ACTIVE_GUILDS_GAUGE = _meter.create_observable_gauge(
    "bot.active_guilds",
    callbacks=[_observe_active_guilds],
    description="Number of guilds the bot is in",
)

WEEKLY_SUBSCRIBERS = _meter.create_up_down_counter(
    "bot.weekly_subscribers",
    description="Total weekly schedule subscribers",
)


class _GuildGauge:
    """Wrapper to provide set/inc/dec interface for the observable gauge."""

    def set(self, value):
        global _active_guilds
        _active_guilds = value

    def inc(self, amount=1):
        global _active_guilds
        _active_guilds += amount

    def dec(self, amount=1):
        global _active_guilds
        _active_guilds -= amount


ACTIVE_GUILDS = _GuildGauge()


def start_metrics():
    _tracer_provider = TracerProvider(resource=_resource)
    _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_tracer_provider)

    AioHttpClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()

    logger.info(
        "OpenTelemetry metrics and tracing configured (export interval: 60s)"
    )
