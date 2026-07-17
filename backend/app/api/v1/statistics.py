from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.response import success
from app.services.statistics import StatisticsService

router = APIRouter(prefix="/statistics", tags=["数据统计"])
StatisticsViewer = Annotated[object, Depends(require_permissions("statistics:view"))]


@router.get("/teacher/courses/{course_id}", summary="教师课程统计")
async def teacher_course_statistics(
    course_id: int,
    _: StatisticsViewer,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    data = await StatisticsService(session, current_user).teacher_course_statistics(course_id)
    return success(data)


@router.get("/admin/overview", summary="平台运营总览")
async def admin_overview(
    _: StatisticsViewer, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    data = await StatisticsService(session, current_user).admin_overview()
    return success(data)

