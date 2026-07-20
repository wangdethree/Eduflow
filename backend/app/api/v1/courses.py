from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.response import success
from app.models.course import CourseStatus
from app.repositories.course import CourseRepository
from app.schemas.course import (
    CategoryCreate,
    CategoryResponse,
    ChapterCreate,
    ChapterResponse,
    ChapterUpdate,
    CourseAuditRequest,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    LessonCreate,
    LessonResponse,
    LessonUpdate,
)
from app.services.course import CourseService

router = APIRouter(tags=["课程中心"])
CourseCreator = Annotated[object, Depends(require_permissions("course:create"))]
CourseEditor = Annotated[object, Depends(require_permissions("course:update"))]
CourseAuditor = Annotated[object, Depends(require_permissions("course:audit"))]
CoursePublisher = Annotated[object, Depends(require_permissions("course:publish"))]


@router.get("/course-categories", summary="课程分类")
async def list_categories(session: DatabaseSession) -> dict:
    items = await CourseRepository(session).list_categories()
    return success(
        [CategoryResponse.model_validate(item).model_dump(mode="json") for item in items]
    )


@router.post("/course-categories", status_code=201, summary="创建课程分类")
async def create_category(
    payload: CategoryCreate,
    _: CourseAuditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    item = await CourseService(session, current_user).create_category(payload)
    return success(CategoryResponse.model_validate(item).model_dump(mode="json"))


@router.get("/courses", summary="公开课程列表")
async def list_courses(
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    category_id: int | None = None,
) -> dict:
    items, total = await CourseRepository(session).list_public(
        page, page_size, keyword, category_id
    )
    return success(
        {
            "items": [
                CourseResponse.model_validate(item).model_dump(mode="json") for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        }
    )


@router.get("/courses/{course_id}", summary="公开课程详情")
async def get_course(course_id: int, session: DatabaseSession) -> dict:
    from app.core.exceptions import ResourceNotFoundException

    course = await CourseRepository(session).get_public_course(course_id)
    if course is None:
        raise ResourceNotFoundException("课程不存在", 40001)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.get("/teacher/courses", summary="教师课程列表")
async def teacher_courses(
    current_user: CurrentUser, _: CourseEditor, session: DatabaseSession
) -> dict:
    items = await CourseRepository(session).list_teacher_courses(current_user.id)
    return success([CourseResponse.model_validate(item).model_dump(mode="json") for item in items])


@router.get("/teacher/courses/{course_id}", summary="教师课程详情")
async def teacher_course_detail(
    course_id: int, current_user: CurrentUser, _: CourseEditor, session: DatabaseSession
) -> dict:
    course = await CourseService(session, current_user).get_owned_course(course_id)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.get("/admin/courses", summary="管理端课程列表")
async def admin_courses(
    session: DatabaseSession,
    _: CourseAuditor,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: CourseStatus | None = CourseStatus.PENDING_REVIEW,
    keyword: str | None = Query(default=None, max_length=100),
) -> dict:
    items, total = await CourseRepository(session).list_for_audit(
        page, page_size, status, keyword
    )
    return success(
        {
            "items": [
                CourseResponse.model_validate(item).model_dump(mode="json") for item in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        }
    )


@router.post("/courses", status_code=201, summary="创建课程")
async def create_course(
    payload: CourseCreate,
    _: CourseCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    course = await CourseService(session, current_user).create_course(payload)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.patch("/courses/{course_id}", summary="编辑课程")
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    course = await CourseService(session, current_user).update_course(course_id, payload)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.delete("/courses/{course_id}", summary="删除草稿课程")
async def delete_course(
    course_id: int, _: CourseEditor, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await CourseService(session, current_user).delete_draft(course_id)
    return success(message="课程已删除")


@router.post("/courses/{course_id}/chapters", status_code=201, summary="创建章节")
async def add_chapter(
    course_id: int,
    payload: ChapterCreate,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    chapter = await CourseService(session, current_user).add_chapter(course_id, payload)
    return success(ChapterResponse.model_validate(chapter).model_dump(mode="json"))


@router.patch("/courses/{course_id}/chapters/{chapter_id}", summary="编辑章节")
async def update_chapter(
    course_id: int,
    chapter_id: int,
    payload: ChapterUpdate,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    chapter = await CourseService(session, current_user).update_chapter(
        course_id, chapter_id, payload
    )
    return success(ChapterResponse.model_validate(chapter).model_dump(mode="json"))


@router.delete("/courses/{course_id}/chapters/{chapter_id}", summary="删除章节")
async def delete_chapter(
    course_id: int,
    chapter_id: int,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    await CourseService(session, current_user).delete_chapter(course_id, chapter_id)
    return success(message="章节已删除")


@router.post(
    "/courses/{course_id}/chapters/{chapter_id}/lessons", status_code=201, summary="创建课时"
)
async def add_lesson(
    course_id: int,
    chapter_id: int,
    payload: LessonCreate,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    lesson = await CourseService(session, current_user).add_lesson(course_id, chapter_id, payload)
    return success(LessonResponse.model_validate(lesson).model_dump(mode="json"))


@router.patch(
    "/courses/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}", summary="编辑课时"
)
async def update_lesson(
    course_id: int,
    chapter_id: int,
    lesson_id: int,
    payload: LessonUpdate,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    lesson = await CourseService(session, current_user).update_lesson(
        course_id, chapter_id, lesson_id, payload
    )
    return success(LessonResponse.model_validate(lesson).model_dump(mode="json"))


@router.delete(
    "/courses/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}", summary="删除课时"
)
async def delete_lesson(
    course_id: int,
    chapter_id: int,
    lesson_id: int,
    _: CourseEditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    await CourseService(session, current_user).delete_lesson(course_id, chapter_id, lesson_id)
    return success(message="课时已删除")


@router.post("/courses/{course_id}/submit-review", summary="提交课程审核")
async def submit_review(
    course_id: int, _: CourseEditor, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    course = await CourseService(session, current_user).submit_review(course_id)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.post("/courses/{course_id}/audit", summary="审核课程")
async def audit_course(
    course_id: int,
    payload: CourseAuditRequest,
    _: CourseAuditor,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    course = await CourseService(session, current_user).audit(
        course_id, payload.approved, payload.opinion
    )
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))


@router.post("/courses/{course_id}/offline", summary="下架课程")
async def offline_course(
    course_id: int, _: CoursePublisher, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    course = await CourseService(session, current_user).offline(course_id)
    return success(CourseResponse.model_validate(course).model_dump(mode="json"))
