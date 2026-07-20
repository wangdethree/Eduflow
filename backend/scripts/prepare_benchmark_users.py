"""通过公开注册接口准备互相隔离的 Locust 压测账号。"""

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def register(base_url: str, username: str, password: str) -> str:
    payload = json.dumps(
        {
            "username": username,
            "email": f"{username}@benchmark.eduflow.example.com",
            "password": password,
            "nickname": f"压测用户 {username}",
        }
    ).encode()
    request = Request(
        f"{base_url.rstrip('/')}/api/v1/auth/register",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 201:
                raise RuntimeError(f"注册 {username} 返回 HTTP {response.status}")
            return "created"
    except HTTPError as exc:
        if exc.code == 409:
            return "existing"
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"注册 {username} 失败：HTTP {exc.code} {detail}") from exc


def main() -> None:
    base_url = os.getenv("BENCHMARK_BASE_URL", "http://127.0.0.1:8003")
    prefix = os.getenv("BENCHMARK_ACCOUNT_PREFIX", "benchmark_user_")
    password = os.getenv("BENCHMARK_PASSWORD", "BenchmarkUser2026!")
    count = int(os.getenv("BENCHMARK_ACCOUNT_COUNT", "50"))
    if count < 1:
        raise ValueError("BENCHMARK_ACCOUNT_COUNT 必须大于 0")

    created = 0
    existing = 0
    for index in range(1, count + 1):
        result = register(base_url, f"{prefix}{index}", password)
        created += result == "created"
        existing += result == "existing"
    print(json.dumps({"created": created, "existing": existing, "count": count}))


if __name__ == "__main__":
    main()
