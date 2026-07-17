from datetime import UTC, datetime

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import Course, CourseCategory, CourseChapter, CourseLesson, CourseStatus
from app.models.learning import CourseEnrollment, EnrollmentStatus, LessonProgress
from app.models.rbac import Permission, Role
from app.models.user import User


async def create_statistics_scene() -> int:
    async with AsyncSessionLocal() as session:
        teacher = User(
            username="stats_teacher",
            email="stats_teacher@example.com",
            nickname="统计教师",
            password_hash=hash_password("Stats1234"),
        )
        student = User(
            username="stats_student",
            email="stats_student@example.com",
            nickname="统计学员",
            password_hash=hash_password("Student123"),
        )
        permission = Permission(name="统计查看", code="statistics:view")
        teacher.roles = [Role(name="统计角色", code="stats_role", permissions=[permission])]
        category = CourseCategory(name="统计测试")
        session.add_all([teacher, student, category])
        await session.flush()
        course = Course(
            title="数据统计课程",
            category_id=category.id,
            teacher_id=teacher.id,
            status=CourseStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
        session.add(course)
        await session.flush()
        chapter = CourseChapter(course_id=course.id, title="统计章节", sort_order=1)
        session.add(chapter)
        await session.flush()
        lesson = CourseLesson(
            chapter_id=chapter.id,
            title="统计课时",
            duration_seconds=100,
            sort_order=1,
            is_required=True,
        )
        session.add(lesson)
        await session.flush()
        session.add_all(
            [
                CourseEnrollment(
                    course_id=course.id,
                    user_id=student.id,
                    status=EnrollmentStatus.COMPLETED,
                    progress=100,
                    enrolled_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                ),
                LessonProgress(
                    user_id=student.id,
                    course_id=course.id,
                    lesson_id=lesson.id,
                    last_position=100,
                    learned_seconds=90,
                    progress_percent=100,
                    is_completed=True,
                    completed_at=datetime.now(UTC),
                    last_learned_at=datetime.now(UTC),
                    client_updated_at=1,
                ),
            ]
        )
        await session.commit()
        return course.id


async def test_teacher_and_admin_statistics(client):
    course_id = await create_statistics_scene()
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": "stats_teacher", "password": "Stats1234"},
    )
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    teacher_stats = await client.get(
        f"/api/v1/statistics/teacher/courses/{course_id}", headers=headers
    )
    data = teacher_stats.json()["data"]
    assert data["student_count"] == 1
    assert data["completion_rate"] == 100
    assert data["chapter_completion"][0]["completion_rate"] == 100
    overview = await client.get("/api/v1/statistics/admin/overview", headers=headers)
    assert overview.json()["data"]["user_total"] == 2
    assert overview.json()["data"]["published_courses"] == 1
