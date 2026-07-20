import asyncio
import os
from io import BytesIO
from uuid import uuid4

from sqlalchemy import text


async def login(client, account: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"account": account, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_real_mysql_redis_and_minio(real_session, real_redis, real_minio):
    dialect = await real_session.scalar(text("SELECT @@version"))
    assert dialect and "sqlite" not in dialect.lower()

    redis_key = f"integration:ping:{uuid4().hex}"
    assert await real_redis.set(redis_key, "ok", ex=30)
    assert await real_redis.get(redis_key) == "ok"

    bucket = "eduflow"
    if not real_minio.bucket_exists(bucket):
        real_minio.make_bucket(bucket)
    object_name = f"integration/{uuid4().hex}.txt"
    payload = b"EduFlow real MinIO integration"
    real_minio.put_object(bucket, object_name, BytesIO(payload), len(payload), "text/plain")
    response = real_minio.get_object(bucket, object_name)
    try:
        assert response.read() == payload
    finally:
        response.close()
        response.release_conn()
        real_minio.remove_object(bucket, object_name)


async def test_live_course_review_flow(live_client):
    suffix = uuid4().hex[:10]
    admin_headers = await login(
        live_client,
        os.getenv("INITIAL_ADMIN_USERNAME", "benchmark_admin"),
        os.getenv("INITIAL_ADMIN_PASSWORD", "IntegrationAdmin2026!"),
    )
    register = await live_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"teacher_{suffix}",
            "email": f"teacher_{suffix}@example.com",
            "password": "TeacherIntegration2026!",
        },
    )
    assert register.status_code == 201, register.text
    user_id = register.json()["data"]["id"]
    roles = (await live_client.get("/api/v1/roles", headers=admin_headers)).json()["data"]
    teacher_role_id = next(item["id"] for item in roles if item["code"] == "teacher")
    assigned = await live_client.put(
        f"/api/v1/users/{user_id}/roles",
        headers=admin_headers,
        json={"ids": [teacher_role_id]},
    )
    assert assigned.status_code == 200, assigned.text

    teacher_headers = await login(
        live_client, f"teacher_{suffix}", "TeacherIntegration2026!"
    )
    category = await live_client.post(
        "/api/v1/course-categories",
        headers=admin_headers,
        json={"name": f"集成分类 {suffix}"},
    )
    assert category.status_code == 201, category.text
    course = await live_client.post(
        "/api/v1/courses",
        headers=teacher_headers,
        json={
            "title": f"真实环境课程 {suffix}",
            "category_id": category.json()["data"]["id"],
        },
    )
    course_id = course.json()["data"]["id"]
    chapter = await live_client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=teacher_headers,
        json={"title": "真实环境第一章"},
    )
    chapter_id = chapter.json()["data"]["id"]
    lesson = await live_client.post(
        f"/api/v1/courses/{course_id}/chapters/{chapter_id}/lessons",
        headers=teacher_headers,
        json={"title": "MySQL Redis MinIO 联调", "duration_seconds": 300},
    )
    assert lesson.status_code == 201, lesson.text
    submitted = await live_client.post(
        f"/api/v1/courses/{course_id}/submit-review", headers=teacher_headers
    )
    assert submitted.json()["data"]["status"] == "pending_review"

    pending = await live_client.get("/api/v1/admin/courses", headers=admin_headers)
    assert any(item["id"] == course_id for item in pending.json()["data"]["items"])
    audited = await live_client.post(
        f"/api/v1/courses/{course_id}/audit",
        headers=admin_headers,
        json={"approved": True, "opinion": "真实环境集成测试通过"},
    )
    assert audited.json()["data"]["status"] == "published"
    public = await live_client.get(f"/api/v1/courses/{course_id}")
    assert public.status_code == 200
    assert public.json()["data"]["chapters"][0]["lessons"][0]["duration_seconds"] == 300


async def test_same_account_concurrent_login_has_no_deadlock(live_client):
    """回归 MySQL 外键锁与最后登录时间更新之间的并发死锁。"""

    account = os.getenv("INITIAL_ADMIN_USERNAME", "benchmark_admin")
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "IntegrationAdmin2026!")
    responses = await asyncio.gather(
        *[
            live_client.post(
                "/api/v1/auth/login",
                json={"account": account, "password": password},
            )
            for _ in range(20)
        ]
    )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses if response.status_code != 200
    ]
