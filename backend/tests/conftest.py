import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_eduflow.db"
os.environ["LOGIN_RATE_LIMIT_ENABLED"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.models import *  # noqa: F403


@pytest.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
