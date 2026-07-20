import asyncio
from contextlib import suppress
from time import perf_counter
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis
from sqlalchemy import event, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.db.session import engine

logger = structlog.get_logger()

CELERY_QUEUE_MESSAGES = Gauge(
    "eduflow_celery_queue_messages",
    "Celery 默认队列中等待处理的消息数量",
)
DEPENDENCY_UP = Gauge(
    "eduflow_dependency_up",
    "EduFlow 外部依赖是否可用",
    labelnames=("dependency",),
)
MYSQL_SLOW_QUERIES = Gauge(
    "eduflow_mysql_slow_queries",
    "MySQL 启动以来累计记录的慢查询数量",
)
SQL_QUERY_DURATION = Histogram(
    "eduflow_sql_query_duration_seconds",
    "SQL 查询耗时",
    labelnames=("operation",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

_sql_monitoring_registered = False
_tracing_configured = False
_error_monitoring_configured = False


def _query_operation(statement: str) -> str:
    """只保留 SQL 操作类型，避免产生高基数指标。"""

    parts = statement.lstrip().split(maxsplit=1)
    return parts[0].upper()[:16] if parts else "UNKNOWN"


def register_sql_monitoring(target_engine: Engine = engine.sync_engine) -> None:
    """记录 SQL 耗时，并对超过阈值的语句写入结构化日志。"""

    global _sql_monitoring_registered
    if _sql_monitoring_registered:
        return

    @event.listens_for(target_engine, "before_cursor_execute")
    def before_cursor_execute(
        _connection: Connection,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        context._eduflow_query_started_at = perf_counter()

    @event.listens_for(target_engine, "after_cursor_execute")
    def after_cursor_execute(
        _connection: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        context: Any,
        _executemany: bool,
    ) -> None:
        started_at = getattr(context, "_eduflow_query_started_at", None)
        if started_at is None:
            return
        duration = perf_counter() - started_at
        SQL_QUERY_DURATION.labels(operation=_query_operation(statement)).observe(duration)
        if duration >= settings.slow_query_threshold_seconds:
            logger.warning(
                "slow_query_detected",
                duration_seconds=round(duration, 6),
                statement=statement.strip()[:500],
            )

    _sql_monitoring_registered = True


def configure_error_monitoring() -> None:
    """存在 DSN 时启用 Sentry，未配置时不产生任何外部请求。"""

    global _error_monitoring_configured
    if not settings.sentry_dsn or _error_monitoring_configured:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.app_release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    _error_monitoring_configured = True


def _create_trace_provider(endpoint: str) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": settings.app_env,
                "service.version": settings.app_release or "development",
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return provider


def configure_tracing(app: FastAPI) -> None:
    """存在 OTLP 地址时启用 FastAPI、数据库与 Redis 链路追踪。"""

    global _tracing_configured
    endpoint = settings.otel_exporter_otlp_traces_endpoint
    if not endpoint or _tracing_configured:
        return

    provider = _create_trace_provider(endpoint)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)
    _tracing_configured = True


def configure_worker_observability() -> None:
    """为独立 Celery Worker 进程配置错误采集与 OTLP 导出。"""

    configure_error_monitoring()
    endpoint = settings.otel_exporter_otlp_traces_endpoint
    if not endpoint:
        return
    provider = _create_trace_provider(endpoint)
    trace.set_tracer_provider(provider)
    CeleryInstrumentor().instrument(tracer_provider=provider)


def configure_metrics(app: FastAPI) -> None:
    """暴露 Prometheus 指标，同时排除健康检查和指标端点自身。"""

    if not settings.metrics_enabled:
        return
    Instrumentator(excluded_handlers=["/metrics", "/api/v1/health"]).instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )


async def _probe_redis(url: str, dependency: str) -> Redis:
    client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
    except Exception:
        DEPENDENCY_UP.labels(dependency=dependency).set(0)
        await client.aclose()
        raise
    DEPENDENCY_UP.labels(dependency=dependency).set(1)
    return client


async def collect_dependency_metrics() -> None:
    """采集数据库、Redis 与 Celery 队列状态；单个依赖故障不影响应用。"""

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            DEPENDENCY_UP.labels(dependency="database").set(1)
            if engine.dialect.name == "mysql":
                result = await connection.execute(text("SHOW GLOBAL STATUS LIKE 'Slow_queries'"))
                row = result.first()
                if row:
                    MYSQL_SLOW_QUERIES.set(float(row[1]))
    except Exception as exc:
        DEPENDENCY_UP.labels(dependency="database").set(0)
        logger.warning("dependency_probe_failed", dependency="database", error=str(exc))

    try:
        redis_client = await _probe_redis(settings.redis_url, "redis")
        await redis_client.aclose()
    except Exception as exc:
        logger.warning("dependency_probe_failed", dependency="redis", error=str(exc))

    try:
        broker_client = await _probe_redis(settings.celery_broker_url, "celery_broker")
        CELERY_QUEUE_MESSAGES.set(await broker_client.llen("celery"))
        await broker_client.aclose()
    except Exception as exc:
        logger.warning("dependency_probe_failed", dependency="celery_broker", error=str(exc))


async def _dependency_probe_loop() -> None:
    while True:
        await collect_dependency_metrics()
        await asyncio.sleep(settings.observability_probe_interval_seconds)


def start_dependency_probes() -> asyncio.Task[None]:
    """启动后台依赖探针，任务会由 FastAPI 生命周期统一回收。"""

    return asyncio.create_task(_dependency_probe_loop(), name="observability-dependency-probes")


async def stop_dependency_probes(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def setup_observability(app: FastAPI) -> None:
    configure_error_monitoring()
    register_sql_monitoring()
    configure_metrics(app)
    configure_tracing(app)
