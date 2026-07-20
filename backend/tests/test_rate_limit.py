import pytest

from app.api.v1 import auth as auth_api
from app.core import rate_limit
from app.core.exceptions import RateLimitException


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    async def eval(self, _script: str, _key_count: int, key: str, window: int):
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], window]

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.counts.pop(key, None)


async def test_login_rate_limit_and_reset(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr(rate_limit.settings, "login_rate_limit_enabled", True)
    monkeypatch.setattr(rate_limit.settings, "login_rate_limit_attempts", 2)
    monkeypatch.setattr(rate_limit, "get_redis_client", lambda: redis_client)

    await rate_limit.enforce_login_rate_limit("Student01", "127.0.0.1")
    await rate_limit.enforce_login_rate_limit("student01", "127.0.0.1")
    with pytest.raises(RateLimitException) as exc_info:
        await rate_limit.enforce_login_rate_limit("student01", "127.0.0.1")

    assert exc_info.value.data["retry_after"] == 300
    assert all("student01" not in key for key in redis_client.counts)

    await rate_limit.reset_login_rate_limit("student01", "127.0.0.1")
    assert redis_client.counts == {}


async def test_login_rate_limit_response_has_retry_after(client, monkeypatch):
    async def reject_login(_account: str, _ip_address: str) -> None:
        raise RateLimitException(45)

    monkeypatch.setattr(auth_api, "enforce_login_rate_limit", reject_login)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "blocked-user", "password": "Password123"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "45"
    assert response.json()["code"] == 20005
