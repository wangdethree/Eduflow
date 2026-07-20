import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from minio import Minio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def api_request(
    method: str, path: str, payload: dict | None = None, headers: dict | None = None
) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{os.getenv('INTEGRATION_BASE_URL', 'http://127.0.0.1:8000')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} 失败：HTTP {exc.code} {detail}") from exc


def login(account: str, password: str) -> dict[str, str]:
    result = api_request(
        "POST", "/api/v1/auth/login", {"account": account, "password": password}
    )
    return {"Authorization": f"Bearer {result['data']['access_token']}"}


async def verify_infrastructure() -> dict:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    async with engine.connect() as connection:
        mysql_version = await connection.scalar(text("SELECT VERSION()"))
    await engine.dispose()

    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    redis_key = f"integration:verify:{uuid4().hex}"
    await redis.set(redis_key, "ok", ex=30)
    assert await redis.get(redis_key) == "ok"
    redis_version = (await redis.info("server"))["redis_version"]
    await redis.aclose()

    minio = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )
    bucket = os.getenv("MINIO_BUCKET", "eduflow")
    if not minio.bucket_exists(bucket):
        minio.make_bucket(bucket)
    object_name = f"integration/{uuid4().hex}.txt"
    content = b"EduFlow real MinIO integration"
    minio.put_object(bucket, object_name, BytesIO(content), len(content), "text/plain")
    response = minio.get_object(bucket, object_name)
    try:
        assert response.read() == content
    finally:
        response.close()
        response.release_conn()
        minio.remove_object(bucket, object_name)

    return {
        "mysql_version": mysql_version,
        "redis_version": redis_version,
        "minio_endpoint": os.environ["MINIO_ENDPOINT"],
    }


def verify_course_flow() -> dict:
    suffix = uuid4().hex[:10]
    admin_headers = login(
        os.getenv("INITIAL_ADMIN_USERNAME", "benchmark_admin"),
        os.getenv("INITIAL_ADMIN_PASSWORD", "IntegrationAdmin2026!"),
    )
    registered = api_request(
        "POST",
        "/api/v1/auth/register",
        {
            "username": f"teacher_{suffix}",
            "email": f"teacher_{suffix}@example.com",
            "password": "TeacherIntegration2026!",
        },
    )
    user_id = registered["data"]["id"]
    roles = api_request("GET", "/api/v1/roles", headers=admin_headers)["data"]
    teacher_role_id = next(item["id"] for item in roles if item["code"] == "teacher")
    api_request(
        "PUT",
        f"/api/v1/users/{user_id}/roles",
        {"ids": [teacher_role_id]},
        admin_headers,
    )
    teacher_headers = login(f"teacher_{suffix}", "TeacherIntegration2026!")
    category = api_request(
        "POST",
        "/api/v1/course-categories",
        {"name": f"集成分类 {suffix}"},
        admin_headers,
    )
    course = api_request(
        "POST",
        "/api/v1/courses",
        {"title": f"真实环境课程 {suffix}", "category_id": category["data"]["id"]},
        teacher_headers,
    )
    course_id = course["data"]["id"]
    chapter = api_request(
        "POST",
        f"/api/v1/courses/{course_id}/chapters",
        {"title": "真实环境第一章"},
        teacher_headers,
    )
    api_request(
        "POST",
        f"/api/v1/courses/{course_id}/chapters/{chapter['data']['id']}/lessons",
        {"title": "MySQL Redis MinIO 联调", "duration_seconds": 300},
        teacher_headers,
    )
    submitted = api_request(
        "POST", f"/api/v1/courses/{course_id}/submit-review", headers=teacher_headers
    )
    assert submitted["data"]["status"] == "pending_review"
    pending = api_request("GET", "/api/v1/admin/courses", headers=admin_headers)
    assert any(item["id"] == course_id for item in pending["data"]["items"])
    audited = api_request(
        "POST",
        f"/api/v1/courses/{course_id}/audit",
        {"approved": True, "opinion": "真实环境集成验证通过"},
        admin_headers,
    )
    assert audited["data"]["status"] == "published"
    public = api_request("GET", f"/api/v1/courses/{course_id}")
    assert public["data"]["chapters"][0]["lessons"][0]["duration_seconds"] == 300
    return {"teacher_user_id": user_id, "published_course_id": course_id}


def verify_concurrent_login() -> dict:
    """在真实 MySQL 上验证同账号并发登录不会再触发锁升级死锁。"""

    account = os.getenv("INITIAL_ADMIN_USERNAME", "benchmark_admin")
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "IntegrationAdmin2026!")
    concurrency = 20
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        tokens = list(executor.map(lambda _: login(account, password), range(concurrency)))
    assert all(item["Authorization"].startswith("Bearer ") for item in tokens)
    return {"concurrent_logins": concurrency}


async def main() -> None:
    infrastructure = await verify_infrastructure()
    course_flow = await asyncio.to_thread(verify_course_flow)
    concurrent_login = await asyncio.to_thread(verify_concurrent_login)
    print(
        json.dumps(
            {"status": "passed", **infrastructure, **course_flow, **concurrent_login},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
