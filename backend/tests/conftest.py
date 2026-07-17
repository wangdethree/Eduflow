import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_eduflow.db"

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client

