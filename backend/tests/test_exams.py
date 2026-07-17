from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import Course, CourseCategory, CourseStatus
from app.models.exam import ExamAnswer, WrongQuestion
from app.models.learning import CourseEnrollment, EnrollmentStatus
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
    exam_id = exam.json()["data"]["id"]
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
