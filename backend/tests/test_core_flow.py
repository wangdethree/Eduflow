import json

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.learning import CourseEnrollment, EnrollmentStatus, LessonProgress
from app.models.rbac import Permission, Role
from app.models.user import User
from app.services import learning as learning_service
from app.tasks import learning as learning_task


class FlowRedis:
    """为核心流程测试提供最小化 Redis 行为。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def eval(self, script, key_count, key, *args):
        incoming = json.loads(args[0])
        if "learned_delta" not in incoming:
            if self.values.get(key) == args[0]:
                del self.values[key]
                return 1
            return 0
        current = json.loads(self.values[key]) if key in self.values else None
        incoming["position"] = max(current["position"] if current else 0, incoming["position"])
        incoming["learned_seconds"] = (current["learned_seconds"] if current else 0) + incoming.pop(
            "learned_delta"
        )
        incoming["progress_percent"] = min(100, incoming["position"] / incoming["duration"] * 100)
        incoming["is_completed"] = (
            incoming["position"] >= incoming["duration"] * 0.9
            and incoming["learned_seconds"] >= incoming["duration"] * 0.8
        )
        self.values[key] = json.dumps(incoming)
        return self.values[key]

    async def get(self, key):
        return self.values.get(key)

    async def scan_iter(self, match, count):
        for key in list(self.values):
            if key.startswith("learning:progress:"):
                yield key


async def create_user(username: str, permissions: list[str] | None = None) -> None:
    async with AsyncSessionLocal() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            nickname=username,
            password_hash=hash_password("Flow12345"),
        )
        if permissions:
            role = Role(name=f"{username}流程角色", code=f"{username}_flow_role")
            role.permissions = [Permission(name=code, code=code) for code in permissions]
            user.roles = [role]
        session.add(user)
        await session.commit()


async def auth_headers(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": "Flow12345"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_publish_enroll_learn_complete_flow(client, monkeypatch):
    """覆盖教师发布、管理员审核、学生加入和完成课程的主链路。"""

    fake_redis = FlowRedis()
    monkeypatch.setattr(learning_service, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(learning_task, "get_redis_client", lambda: fake_redis)

    await create_user("flow_teacher", ["course:create", "course:update", "course:publish"])
    await create_user("flow_auditor", ["course:audit"])
    await create_user("flow_student")
    teacher = await auth_headers(client, "flow_teacher")
    auditor = await auth_headers(client, "flow_auditor")
    student = await auth_headers(client, "flow_student")

    category = await client.post(
        "/api/v1/course-categories",
        headers=auditor,
        json={"name": "核心流程分类", "sort_order": 1},
    )
    assert category.status_code == 201
    course = await client.post(
        "/api/v1/courses",
        headers=teacher,
        json={
            "title": "EduFlow 核心流程课程",
            "description": "用于验证课程学习闭环",
            "category_id": category.json()["data"]["id"],
        },
    )
    assert course.status_code == 201
    course_id = course.json()["data"]["id"]
    chapter = await client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=teacher,
        json={"title": "核心章节"},
    )
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/chapters/{chapter.json()['data']['id']}/lessons",
        headers=teacher,
        json={"title": "核心课时", "duration_seconds": 60},
    )
    lesson_id = lesson.json()["data"]["id"]
    submitted = await client.post(
        f"/api/v1/courses/{course_id}/submit-review", headers=teacher
    )
    assert submitted.json()["data"]["status"] == "pending_review"
    approved = await client.post(
        f"/api/v1/courses/{course_id}/audit",
        headers=auditor,
        json={"approved": True, "opinion": "核心流程验收通过"},
    )
    assert approved.json()["data"]["status"] == "published"

    enrolled = await client.post(
        f"/api/v1/learning/courses/{course_id}/enroll", headers=student
    )
    assert enrolled.status_code == 200
    progress = await client.post(
        f"/api/v1/learning/courses/{course_id}/progress",
        headers=student,
        json={
            "lesson_id": lesson_id,
            "position_seconds": 60,
            "learned_seconds_delta": 60,
            "client_updated_at": 1000,
        },
    )
    assert progress.json()["data"]["is_completed"] is True
    assert await learning_task.flush_progress_batch() == 1

    async with AsyncSessionLocal() as session:
        enrollment = await session.scalar(select(CourseEnrollment))
        lesson_progress = await session.scalar(select(LessonProgress))
        assert enrollment is not None and enrollment.status == EnrollmentStatus.COMPLETED
        assert lesson_progress is not None and lesson_progress.is_completed is True
