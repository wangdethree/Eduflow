from typing import Any

from fastapi import APIRouter

from app.api.deps.auth import CurrentUser, DatabaseSession
from app.core.response import success
from app.schemas.file import FileResponse, PresignedUploadRequest
from app.services.file import FileStorageService

router = APIRouter(prefix="/files", tags=["文件管理"])


def serialize_file(stored_file: Any, url: str | None = None) -> dict:
    return FileResponse(
        id=stored_file.id,
        original_name=stored_file.original_name,
        content_type=stored_file.content_type,
        size_bytes=stored_file.size_bytes,
        purpose=stored_file.purpose.value,
        status=stored_file.status.value,
        is_public=stored_file.is_public,
        url=url,
    ).model_dump(mode="json")


@router.post("/presigned-upload", status_code=201, summary="申请上传签名")
async def create_presigned_upload(
    payload: PresignedUploadRequest, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    stored_file, url = await FileStorageService(session, current_user).create_upload(payload)
    return success(serialize_file(stored_file, url))


@router.post("/{file_id}/complete", summary="确认上传完成")
async def complete_upload(
    file_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    stored_file = await FileStorageService(session, current_user).complete_upload(file_id)
    return success(serialize_file(stored_file), "上传已确认")


@router.get("/{file_id}/download", summary="获取临时下载地址")
async def get_download_url(
    file_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    stored_file, url = await FileStorageService(session, current_user).get_download_url(file_id)
    return success(serialize_file(stored_file, url))


@router.delete("/{file_id}", summary="删除文件")
async def delete_file(file_id: int, current_user: CurrentUser, session: DatabaseSession) -> dict:
    await FileStorageService(session, current_user).delete_file(file_id)
    return success(message="文件已删除")
