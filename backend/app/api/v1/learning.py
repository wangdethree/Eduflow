from fastapi import APIRouter

from app.api.deps.auth import CurrentUser, DatabaseSession
from app.core.response import success
from app.repositories.learning import LearningRepository
from app.schemas.learning import EnrollmentResponse, ProgressReportRequest, ProgressResponse
from app.services.learning import LearningService

router = APIRouter(prefix="/learning", tags=["学习中心"])


@router.post("/courses/{course_id}/enroll", summary="加入课程")
async def enroll_course(
    course_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    enrollment = await LearningService(session, current_user).enroll(course_id)
    return success(
        EnrollmentResponse(
            id=enrollment.id,
            course_id=enrollment.course_id,
            status=enrollment.status.value,
            progress=float(enrollment.progress),
        ).model_dump(mode="json")
    )


@router.delete("/courses/{course_id}/enroll", summary="退出课程")
async def withdraw_course(
    course_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await LearningService(session, current_user).withdraw(course_id)
    return success(message="已退出课程")


@router.get("/courses", summary="我的课程")
async def my_courses(current_user: CurrentUser, session: DatabaseSession) -> dict:
    items = await LearningRepository(session).list_enrollments(current_user.id)
    return success(
        [
            EnrollmentResponse(
                id=item.id,
                course_id=item.course_id,
                status=item.status.value,
                progress=float(item.progress),
            ).model_dump(mode="json")
            for item in items
        ]
    )


@router.post("/courses/{course_id}/progress", summary="上报学习进度")
async def report_progress(
    course_id: int,
    payload: ProgressReportRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    data = await LearningService(session, current_user).report_progress(course_id, payload)
    return success(ProgressResponse.model_validate(data).model_dump(mode="json"))


@router.get("/lessons/{lesson_id}/progress", summary="恢复最近学习位置")
async def get_lesson_progress(
    lesson_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    data = await LearningService(session, current_user).get_lesson_progress(lesson_id)
    return success(ProgressResponse.model_validate(data).model_dump(mode="json"))


@router.post("/courses/{course_id}/favorite", summary="收藏或取消收藏")
async def toggle_favorite(
    course_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    enabled = await LearningService(session, current_user).toggle_favorite(course_id)
    return success({"is_favorite": enabled})

