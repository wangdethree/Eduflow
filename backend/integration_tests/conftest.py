import os

import pytest
from httpx import AsyncClient
from minio import Minio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

INTEGRATION_BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://127.0.0.1:8003")
INTEGRATION_DATABASE_URL = os.getenv(
    "INTEGRATION_DATABASE_URL",
    "mysql+asyncmy://eduflow:integration_mysql_password@127.0.0.1:3307/eduflow_integration",
)
INTEGRATION_REDIS_URL = os.getenv("INTEGRATION_REDIS_URL", "redis://127.0.0.1:6381/0")


@pytest.fixture
async def live_client():
    async with AsyncClient(base_url=INTEGRATION_BASE_URL, timeout=20) as client:
        yield client


@pytest.fixture
async def real_session():
    engine = create_async_engine(INTEGRATION_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def real_redis():
    client = Redis.from_url(INTEGRATION_REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def real_minio():
    return Minio(
        os.getenv("INTEGRATION_MINIO_ENDPOINT", "127.0.0.1:9002"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "eduflow-integration"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "integration_minio_password"),
        secure=False,
    )
