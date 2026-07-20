from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，生产环境通过环境变量覆盖。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EduFlow"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "development-only-secret-key-change-me"
    database_url: str = "sqlite+aiosqlite:///./eduflow.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "eduflow"
    minio_secret_key: str = "eduflow-secret"
    minio_bucket: str = "eduflow"
    minio_secure: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"
    metrics_enabled: bool = True
    observability_probe_interval_seconds: int = Field(default=15, ge=5)
    slow_query_threshold_seconds: float = Field(default=1.0, ge=0)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0, le=1)
    otel_exporter_otlp_traces_endpoint: str | None = None
    otel_service_name: str = "eduflow-backend"
    app_release: str | None = None

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
