import asyncio
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import Course, CourseCategory, CourseStatus
from app.models.exam import ExamAnswer, WrongQuestion
from app.models.learning import CourseEnrollment, EnrollmentStatus
from app.models.notification import Notification, UserNotification
from app.models.rbac import Permission, Role
from app.models.user import User
from app.services import exam as exam_service


class FakeRedisLock:
    def __init__(self) -> None:
        self.values = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def eval(self, script, key_count, key, expected):
        if self.values.get(key) == expected:
            del self.values[key]
            return 1
        return 0


class ContendedRedisLock(FakeRedisLock):
    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        # 给第二个并发请求留出观察锁的时间，稳定复现重复提交分支。
        await asyncio.sleep(0.1)
        return True


class UnavailableRedisLock(FakeRedisLock):
    async def set(self, key, value, ex=None, nx=False):
        raise RedisError("Redis unavailable")


async def create_exam_scene() -> int:
    async with AsyncSessionLocal() as session:
        teacher = User(
            username="exam_teacher",
            email="exam_teacher@example.com",
            nickname="考试教师",
            password_hash=hash_password("Teacher123"),
        )
        student = User(
            username="exam_student",
            email="exam_student@example.com",
            nickname="考生",
            password_hash=hash_password("Student123"),
        )
        permission = Permission(name="考试创建", code="exam:create")
        role = Role(name="考试教师", code="exam_teacher_role", permissions=[permission])
        teacher.roles = [role]
        category = CourseCategory(name="考试测试")
        session.add_all([teacher, student, category])
        await session.flush()
        course = Course(
            title="Python 阶段测验",
            category_id=category.id,
            teacher_id=teacher.id,
            status=CourseStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
        session.add(course)
        await session.flush()
        session.add(
            CourseEnrollment(
                course_id=course.id,
                user_id=student.id,
                status=EnrollmentStatus.ACTIVE,
                enrolled_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return course.id


async def login(client, account: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"account": account, "password": password}
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def create_ready_submission(client, monkeypatch, redis) -> tuple[int, dict, dict]:
    monkeypatch.setattr(exam_service, "get_redis_client", lambda: redis)
    course_id = await create_exam_scene()
    teacher_headers = await login(client, "exam_teacher", "Teacher123")
    student_headers = await login(client, "exam_student", "Student123")
    question = await client.post(
        "/api/v1/questions",
        headers=teacher_headers,
        json={
            "stem": "并发提交应如何处理？",
            "question_type": "single",
            "options": {"A": "加分布式锁", "B": "重复写入"},
            "correct_answers": ["A"],
        },
    )
    question_id = question.json()["data"]["id"]
    paper = await client.post(
        "/api/v1/papers", headers=teacher_headers, json={"title": "并发提交试卷"}
    )
    paper_id = paper.json()["data"]["id"]
    await client.post(
        f"/api/v1/papers/{paper_id}/questions",
        headers=teacher_headers,
        json={"question_id": question_id, "score": 10},
    )
    now = datetime.now(UTC)
    exam = await client.post(
        "/api/v1/exams",
        headers=teacher_headers,
        json={
            "course_id": course_id,
            "paper_id": paper_id,
            "title": "并发提交考试",
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "duration_minutes": 60,
        },
    )
    exam_id = exam.json()["data"]["id"]
    await client.post(f"/api/v1/exams/{exam_id}/start", headers=student_headers)
    submission = {
        "idempotency_key": "concurrent-submit-0001",
        "answers": [{"question_id": question_id, "selected_answers": ["A"]}],
    }
    return exam_id, student_headers, submission


async def test_exam_auto_grading_idempotency_and_wrong_book(client, monkeypatch):
    fake_redis = FakeRedisLock()
    monkeypatch.setattr(exam_service, "get_redis_client", lambda: fake_redis)
    course_id = await create_exam_scene()
    teacher_headers = await login(client, "exam_teacher", "Teacher123")
    student_headers = await login(client, "exam_student", "Student123")

    q1 = await client.post(
        "/api/v1/questions",
        headers=teacher_headers,
        json={
            "stem": "Python 中哪个关键字定义函数？",
            "question_type": "single",
            "options": {"A": "def", "B": "class"},
            "correct_answers": ["A"],
        },
    )
    q2 = await client.post(
        "/api/v1/questions",
        headers=teacher_headers,
        json={
            "stem": "以下哪些是可变类型？",
            "question_type": "multiple",
            "options": {"A": "list", "B": "dict", "C": "tuple"},
            "correct_answers": ["A", "B"],
        },
    )
    paper = await client.post(
        "/api/v1/papers", headers=teacher_headers, json={"title": "Python 基础试卷"}
    )
    paper_id = paper.json()["data"]["id"]
    for question_id in (q1.json()["data"]["id"], q2.json()["data"]["id"]):
        response = await client.post(
            f"/api/v1/papers/{paper_id}/questions",
            headers=teacher_headers,
            json={"question_id": question_id, "score": 5},
        )
        assert response.status_code == 200
    now = datetime.now(UTC)
    exam = await client.post(
        "/api/v1/exams",
        headers=teacher_headers,
        json={
            "course_id": course_id,
            "paper_id": paper_id,
            "title": "Python 阶段考试",
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "duration_minutes": 60,
        },
    )
    assert exam.status_code == 201
    exam_id = exam.json()["data"]["id"]
    async with AsyncSessionLocal() as session:
        publish_notice = await session.scalar(
            select(Notification).where(Notification.source_key == f"exam_publish:{exam_id}")
        )
        assert publish_notice is not None
        assert await session.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.notification_id == publish_notice.id
            )
        ) == 1
    started = await client.post(f"/api/v1/exams/{exam_id}/start", headers=student_headers)
    assert len(started.json()["data"]["questions"]) == 2
    submission = {
        "idempotency_key": "submit-test-00000001",
        "answers": [
            {"question_id": q1.json()["data"]["id"], "selected_answers": ["A"]},
            {"question_id": q2.json()["data"]["id"], "selected_answers": ["A"]},
        ],
    }
    graded = await client.post(
        f"/api/v1/exams/{exam_id}/submit", headers=student_headers, json=submission
    )
    assert graded.json()["data"]["objective_score"] == 5
    duplicate = await client.post(
        f"/api/v1/exams/{exam_id}/submit", headers=student_headers, json=submission
    )
    assert duplicate.json()["data"]["id"] == graded.json()["data"]["id"]

    wrong = await client.get("/api/v1/wrong-questions", headers=student_headers)
    assert wrong.json()["data"][0]["wrong_count"] == 1
    async with AsyncSessionLocal() as session:
        assert await session.scalar(select(func.count(ExamAnswer.id))) == 2
        assert await session.scalar(select(func.count(WrongQuestion.id))) == 1


async def test_teacher_question_bank_and_paper_management(client):
    await create_exam_scene()
    headers = await login(client, "exam_teacher", "Teacher123")
    created = await client.post(
        "/api/v1/questions",
        headers=headers,
        json={
            "stem": "FastAPI 默认使用哪种数据校验库？",
            "question_type": "single",
            "options": {"A": "Pydantic", "B": "Marshmallow"},
            "correct_answers": ["A"],
            "difficulty": "easy",
        },
    )
    question_id = created.json()["data"]["id"]
    questions = await client.get("/api/v1/questions", headers=headers)
    assert questions.json()["data"][0]["id"] == question_id

    updated = await client.put(
        f"/api/v1/questions/{question_id}",
        headers=headers,
        json={
            "stem": "FastAPI 主要使用哪种数据校验库？",
            "question_type": "single",
            "options": {"A": "Pydantic", "B": "Jinja2"},
            "correct_answers": ["A"],
            "analysis": "请求模型由 Pydantic 校验。",
            "difficulty": "medium",
        },
    )
    assert updated.json()["data"]["difficulty"] == "medium"

    paper = await client.post(
        "/api/v1/papers",
        headers=headers,
        json={"title": "FastAPI 入门试卷", "description": "教师题库管理测试"},
    )
    paper_id = paper.json()["data"]["id"]
    await client.post(
        f"/api/v1/papers/{paper_id}/questions",
        headers=headers,
        json={"question_id": question_id, "score": 10},
    )
    papers = await client.get("/api/v1/papers", headers=headers)
    assert papers.json()["data"][0]["questions"][0]["question"]["id"] == question_id
    detail = await client.get(f"/api/v1/papers/{paper_id}", headers=headers)
    assert detail.json()["data"]["total_score"] == 10

    rescored = await client.patch(
        f"/api/v1/papers/{paper_id}/questions/{question_id}",
        headers=headers,
        json={"score": 15},
    )
    assert rescored.json()["data"]["total_score"] == 15
    in_use = await client.delete(f"/api/v1/questions/{question_id}", headers=headers)
    assert in_use.status_code == 409

    removed = await client.delete(
        f"/api/v1/papers/{paper_id}/questions/{question_id}", headers=headers
    )
    assert removed.json()["data"]["total_score"] == 0
    deleted_question = await client.delete(
        f"/api/v1/questions/{question_id}", headers=headers
    )
    assert deleted_question.status_code == 200
    assert (await client.delete(f"/api/v1/papers/{paper_id}", headers=headers)).status_code == 200


async def test_concurrent_exam_submission_only_grades_once(client, monkeypatch):
    exam_id, headers, submission = await create_ready_submission(
        client, monkeypatch, ContendedRedisLock()
    )
    responses = await asyncio.gather(
        *[
            client.post(
                f"/api/v1/exams/{exam_id}/submit", headers=headers, json=submission
            )
            for _ in range(2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == 60014
    async with AsyncSessionLocal() as session:
        assert await session.scalar(select(func.count(ExamAnswer.id))) == 1


async def test_exam_submission_returns_503_when_redis_is_unavailable(
    client, monkeypatch
):
    exam_id, headers, submission = await create_ready_submission(
        client, monkeypatch, UnavailableRedisLock()
    )
    response = await client.post(
        f"/api/v1/exams/{exam_id}/submit", headers=headers, json=submission
    )
    assert response.status_code == 503
    assert response.json()["code"] == 90001
    async with AsyncSessionLocal() as session:
        assert await session.scalar(select(func.count(ExamAnswer.id))) == 0
