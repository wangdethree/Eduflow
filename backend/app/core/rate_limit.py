import hashlib
from typing import Any

import structlog
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import RateLimitException
from app.core.redis import get_redis_client

logger = structlog.get_logger()

LOGIN_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


def _digest(value: str) -> str:
    """限流键不保存明文账号或 IP，降低 Redis 数据泄露影响。"""

    return hashlib.sha256(value.encode()).hexdigest()


def _login_keys(account: str, ip_address: str) -> list[str]:
    normalized_account = account.strip().lower()
    normalized_ip = ip_address.strip() or "unknown"
    return [
        f"security:login:account:{_digest(normalized_account)}",
        f"security:login:ip:{_digest(normalized_ip)}",
    ]


async def enforce_login_rate_limit(account: str, ip_address: str) -> None:
    """按账号和 IP 执行固定窗口限流，Redis 故障时降级放行。"""

    if not settings.login_rate_limit_enabled:
        return
    redis_client = get_redis_client()
    try:
        for key in _login_keys(account, ip_address):
            result: Any = await redis_client.eval(
                LOGIN_RATE_LIMIT_SCRIPT,
                1,
                key,
                settings.login_rate_limit_window_seconds,
            )
            count, ttl = int(result[0]), int(result[1])
            if count > settings.login_rate_limit_attempts:
                await logger.awarning(
                    "login_rate_limit_exceeded",
                    account_hash=_digest(account.strip().lower()),
                    ip_hash=_digest(ip_address.strip() or "unknown"),
                    retry_after=max(1, ttl),
                )
                raise RateLimitException(ttl)
    except RateLimitException:
        raise
    except (RedisError, OSError) as exc:
        await logger.awarning("login_rate_limit_unavailable", error=str(exc))


async def reset_login_rate_limit(account: str, ip_address: str) -> None:
    """登录成功后清理本次账号和 IP 的失败窗口。"""

    if not settings.login_rate_limit_enabled:
        return
    try:
        await get_redis_client().delete(*_login_keys(account, ip_address))
    except (RedisError, OSError) as exc:
        await logger.awarning("login_rate_limit_reset_failed", error=str(exc))
