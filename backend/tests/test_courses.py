from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import CourseCategory
from app.models.rbac import Permission, Role
from app.models.user import User


async def create_actor(username: str, permission_codes: list[str]) -> None:
    async with AsyncSessionLocal() as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            nickname=username,
            password_hash=hash_password("Password123"),
        )
        role = Role(name=f"{username}角色", code=f"{username}_role")
        permissions = []
        for code in permission_codes:
            permission = await session.scalar(select(Permission).where(Permission.code == code))
            permissions.append(permission or Permission(name=code, code=code))
        role.permissions = permissions
        user.roles = [role]
        session.add(user)
        await session.commit()


async def login(client, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"account": username, "password": "Password123"}
    )
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def test_course_creation_review_and_publication(client):
    await create_actor(
        "teacher", ["course:create", "course:update", "course:publish"]
    )
    await create_actor("auditor", ["course:audit"])
    teacher_headers = await login(client, "teacher")
    auditor_headers = await login(client, "auditor")

    category = await client.post(
        "/api/v1/course-categories",
        headers=auditor_headers,
        json={"name": "Python 开发", "sort_order": 1},
    )
    category_id = category.json()["data"]["id"]
    created = await client.post(
        "/api/v1/courses",
        headers=teacher_headers,
        json={
            "title": "FastAPI 工程实践",
            "description": "从零掌握异步 API 开发",
            "category_id": category_id,
            "difficulty": "intermediate",
        },
    )
    assert created.status_code == 201
    course_id = created.json()["data"]["id"]

    empty_submit = await client.post(
        f"/api/v1/courses/{course_id}/submit-review", headers=teacher_headers
    )
    assert empty_submit.status_code == 409
    chapter = await client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=teacher_headers,
        json={"title": "第一章 快速开始"},
    )
    chapter_id = chapter.json()["data"]["id"]
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/chapters/{chapter_id}/lessons",
        headers=teacher_headers,
        json={"title": "创建第一个接口", "duration_seconds": 600},
    )
    assert lesson.status_code == 201
    lesson_id = lesson.json()["data"]["id"]

    second_chapter = await client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=teacher_headers,
        json={"title": "第二章 深入实践"},
    )
    second_chapter_id = second_chapter.json()["data"]["id"]
    moved_chapter = await client.patch(
        f"/api/v1/courses/{course_id}/chapters/{second_chapter_id}",
        headers=teacher_headers,
        json={"title": "第一章 工程实践", "sort_order": 1},
    )
    assert moved_chapter.json()["data"]["sort_order"] == 1
    extra_lesson = await client.post(
        f"/api/v1/courses/{course_id}/chapters/{second_chapter_id}/lessons",
        headers=teacher_headers,
        json={"title": "依赖注入实践", "duration_seconds": 120},
    )
    extra_lesson_id = extra_lesson.json()["data"]["id"]
    updated_lesson = await client.patch(
        f"/api/v1/courses/{course_id}/chapters/{second_chapter_id}/lessons/{extra_lesson_id}",
        headers=teacher_headers,
        json={"title": "依赖注入与测试", "duration_seconds": 300},
    )
    assert updated_lesson.json()["data"]["duration_seconds"] == 300
    disposable_lesson = await client.post(
        f"/api/v1/courses/{course_id}/chapters/{second_chapter_id}/lessons",
        headers=teacher_headers,
        json={"title": "待删除课时", "duration_seconds": 60},
    )
    deleted_lesson = await client.delete(
        f"/api/v1/courses/{course_id}/chapters/{second_chapter_id}/lessons/"
        f"{disposable_lesson.json()['data']['id']}",
        headers=teacher_headers,
    )
    assert deleted_lesson.status_code == 200
    disposable_chapter = await client.post(
        f"/api/v1/courses/{course_id}/chapters",
        headers=teacher_headers,
        json={"title": "待删除章节"},
    )
    deleted_chapter = await client.delete(
        f"/api/v1/courses/{course_id}/chapters/{disposable_chapter.json()['data']['id']}",
        headers=teacher_headers,
    )
    assert deleted_chapter.status_code == 200
    teacher_detail = await client.get(
        f"/api/v1/teacher/courses/{course_id}", headers=teacher_headers
    )
    detail_data = teacher_detail.json()["data"]
    assert detail_data["total_duration"] == 900
    assert [chapter["sort_order"] for chapter in detail_data["chapters"]] == [1, 2]
    assert any(
        item["id"] == lesson_id
        for chapter in detail_data["chapters"]
        for item in chapter["lessons"]
    )

    submitted = await client.post(
        f"/api/v1/courses/{course_id}/submit-review", headers=teacher_headers
    )
    assert submitted.json()["data"]["status"] == "pending_review"

    pending_courses = await client.get("/api/v1/admin/courses", headers=auditor_headers)
    assert pending_courses.status_code == 200
    assert pending_courses.json()["data"]["items"][0]["id"] == course_id

    teacher_audit = await client.post(
        f"/api/v1/courses/{course_id}/audit",
        headers=teacher_headers,
        json={"approved": True},
    )
    assert teacher_audit.status_code == 403
    audited = await client.post(
        f"/api/v1/courses/{course_id}/audit",
        headers=auditor_headers,
        json={"approved": True, "opinion": "内容完整"},
    )
    assert audited.json()["data"]["status"] == "published"

    public_list = await client.get("/api/v1/courses", params={"keyword": "FastAPI"})
    assert public_list.json()["data"]["total"] == 1
    detail = await client.get(f"/api/v1/courses/{course_id}")
    assert detail.json()["data"]["total_duration"] == 900


async def test_teacher_cannot_edit_another_teachers_course(client):
    await create_actor("teacher_a", ["course:create", "course:update"])
    await create_actor("teacher_b", ["course:create", "course:update"])
    async with AsyncSessionLocal() as session:
        category = CourseCategory(name="后端开发")
        session.add(category)
        await session.commit()
        category_id = category.id
    headers_a = await login(client, "teacher_a")
    headers_b = await login(client, "teacher_b")
    created = await client.post(
        "/api/v1/courses",
        headers=headers_a,
        json={"title": "课程 A", "category_id": category_id},
    )
    course_id = created.json()["data"]["id"]
    response = await client.patch(
        f"/api/v1/courses/{course_id}", headers=headers_b, json={"title": "越权修改"}
    )
    assert response.status_code == 403


async def test_draft_course_is_not_public(client):
    await create_actor("draft_teacher", ["course:create"])
    async with AsyncSessionLocal() as session:
        category = CourseCategory(name="测试分类")
        session.add(category)
        await session.commit()
        category_id = category.id
    headers = await login(client, "draft_teacher")
    created = await client.post(
        "/api/v1/courses",
        headers=headers,
        json={"title": "未发布课程", "category_id": category_id},
    )
    course_id = created.json()["data"]["id"]
    response = await client.get(f"/api/v1/courses/{course_id}")
    assert response.status_code == 404
