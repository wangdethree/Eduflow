import json
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import (
    Course,
    CourseCategory,
    CourseChapter,
    CourseLesson,
    CourseStatus,
)
from app.models.learning import CourseEnrollment, EnrollmentStatus, LessonProgress
from app.models.user import User
from app.services import learning as learning_service
from app.tasks import learning as learning_task


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def eval(self, script, key_count, key, *args):
        if "learned_delta" in script:
            incoming = json.loads(args[0])
            current = json.loads(self.values[key]) if key in self.values else None
            if current and incoming["updated_at"] <= current["updated_at"]:
                return self.values[key]
            incoming["position"] = max(
                current["position"] if current else 0, incoming["position"]
            )
            incoming["learned_seconds"] = (
                current["learned_seconds"] if current else 0
            ) + incoming.pop("learned_delta")
            incoming["progress_percent"] = min(
                100, incoming["position"] / incoming["duration"] * 100
            )
            incoming["is_completed"] = (
                incoming["position"] >= incoming["duration"] * 0.9
                and incoming["learned_seconds"] >= incoming["duration"] * 0.8
            )
            self.values[key] = json.dumps(incoming)
            return self.values[key]
        expected = args[0]
        if self.values.get(key) == expected:
            del self.values[key]
            return 1
        return 0

    async def get(self, key):
        return self.values.get(key)

    async def scan_iter(self, match, count):
        for key in list(self.values):
            if key.startswith("learning:progress:"):
                yield key


async def create_learning_scene() -> tuple[int, int]:
    async with AsyncSessionLocal() as session:
        user = User(
            username="learner",
            email="learner@example.com",
            nickname="学习者",
            password_hash=hash_password("Learn1234"),
        )
        category = CourseCategory(name="学习测试")
        session.add_all([user, category])
        await session.flush()
        course = Course(
            title="Redis 学习进度",
            category_id=category.id,
            teacher_id=user.id,
            status=CourseStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
        session.add(course)
        await session.flush()
        chapter = CourseChapter(course_id=course.id, title="进度设计", sort_order=1)
        session.add(chapter)
        await session.flush()
        lesson = CourseLesson(
            chapter_id=chapter.id,
            title="高频上报",
            duration_seconds=100,
            sort_order=1,
            is_required=True,
        )
        session.add(lesson)
        await session.commit()
        return course.id, lesson.id


async def learner_headers(client) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"account": "learner", "password": "Learn1234"}
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_enroll_progress_final_consistency_and_favorite(client, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(learning_service, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(learning_task, "get_redis_client", lambda: fake_redis)
    course_id, lesson_id = await create_learning_scene()
    headers = await learner_headers(client)
    enrolled = await client.post(f"/api/v1/learning/courses/{course_id}/enroll", headers=headers)
    assert enrolled.status_code == 200

    first = await client.post(
        f"/api/v1/learning/courses/{course_id}/progress",
        headers=headers,
        json={
            "lesson_id": lesson_id,
            "position_seconds": 90,
            "learned_seconds_delta": 60,
            "client_updated_at": 200,
        },
    )
    assert first.json()["data"]["is_completed"] is False
    old = await client.post(
        f"/api/v1/learning/courses/{course_id}/progress",
        headers=headers,
        json={
            "lesson_id": lesson_id,
            "position_seconds": 20,
            "learned_seconds_delta": 60,
            "client_updated_at": 100,
        },
    )
    assert old.json()["data"]["position"] == 90
    completed = await client.post(
        f"/api/v1/learning/courses/{course_id}/progress",
        headers=headers,
        json={
            "lesson_id": lesson_id,
            "position_seconds": 100,
            "learned_seconds_delta": 20,
            "client_updated_at": 300,
        },
    )
    assert completed.json()["data"]["is_completed"] is True
    immediate = await client.get(
        f"/api/v1/learning/lessons/{lesson_id}/progress", headers=headers
    )
    assert immediate.json()["data"]["learned_seconds"] == 80

    assert await learning_task.flush_progress_batch() == 1
    async with AsyncSessionLocal() as session:
        progress = await session.scalar(select(LessonProgress))
        enrollment = await session.scalar(select(CourseEnrollment))
        assert progress is not None and progress.is_completed
        assert enrollment is not None and enrollment.status == EnrollmentStatus.COMPLETED
        assert float(enrollment.progress) == 100

    favorite = await client.post(
        f"/api/v1/learning/courses/{course_id}/favorite", headers=headers
    )
    assert favorite.json()["data"]["is_favorite"] is True
    unfavorite = await client.post(
        f"/api/v1/learning/courses/{course_id}/favorite", headers=headers
    )
    assert unfavorite.json()["data"]["is_favorite"] is False


async def test_progress_requires_enrollment(client, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(learning_service, "get_redis_client", lambda: fake_redis)
    course_id, lesson_id = await create_learning_scene()
    headers = await learner_headers(client)
    response = await client.post(
        f"/api/v1/learning/courses/{course_id}/progress",
        headers=headers,
        json={
            "lesson_id": lesson_id,
            "position_seconds": 10,
            "learned_seconds_delta": 10,
            "client_updated_at": 100,
        },
    )
    assert response.status_code == 409
