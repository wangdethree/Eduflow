from fastapi import APIRouter

from app.core.response import success

router = APIRouter(tags=["系统"])


@router.get("/health", summary="健康检查")
async def health_check() -> dict:
    return success({"status": "ok", "service": "eduflow-backend"})

