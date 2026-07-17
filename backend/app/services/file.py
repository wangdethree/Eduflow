from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    PermissionDeniedException,
    ResourceNotFoundException,
)
from app.models.file import FilePurpose, FileStatus, StoredFile
from app.models.user import User
from app.schemas.file import PresignedUploadRequest

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
DOCUMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "video/mp4",
}
PURPOSE_LIMITS = {
    FilePurpose.AVATAR: 5 * 1024 * 1024,
    FilePurpose.COURSE_COVER: 10 * 1024 * 1024,
    FilePurpose.COURSE_RESOURCE: 100 * 1024 * 1024,
    FilePurpose.LESSON_ATTACHMENT: 100 * 1024 * 1024,
    FilePurpose.EXPORT: 100 * 1024 * 1024,
}


def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


class FileStorageService:
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
        self.client = get_minio_client()

    async def create_upload(self, payload: PresignedUploadRequest) -> tuple[StoredFile, str]:
        purpose = FilePurpose(payload.purpose)
        self._validate_file(payload, purpose)
        extension = Path(payload.filename).suffix.lower()
        object_name = (
            f"{purpose.value}/{datetime.now(UTC):%Y/%m/%d}/"
            f"{self.current_user.id}/{uuid4().hex}{extension}"
        )
        stored_file = StoredFile(
            owner_id=self.current_user.id,
            original_name=Path(payload.filename).name,
            object_name=object_name,
            bucket=settings.minio_bucket,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            purpose=purpose,
            is_public=purpose in {FilePurpose.AVATAR, FilePurpose.COURSE_COVER},
        )
        self.session.add(stored_file)
        await self.session.commit()
        await self.session.refresh(stored_file)
        upload_url = self.client.presigned_put_object(
            settings.minio_bucket, object_name, expires=timedelta(minutes=15)
        )
        return stored_file, upload_url

    async def complete_upload(self, file_id: int) -> StoredFile:
        stored_file = await self._owned_file(file_id)
        if stored_file.status != FileStatus.PENDING:
            raise ConflictException("文件已确认或已删除", 70003)
        stat = self.client.stat_object(stored_file.bucket, stored_file.object_name)
        if stat.size != stored_file.size_bytes:
            raise ConflictException("实际文件大小与申请不一致", 70004)
        if stat.content_type and stat.content_type != stored_file.content_type:
            raise ConflictException("实际文件类型与申请不一致", 70005)
        stored_file.status = FileStatus.READY
        stored_file.uploaded_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(stored_file)
        return stored_file

    async def get_download_url(self, file_id: int) -> tuple[StoredFile, str]:
        stored_file = await self.session.get(StoredFile, file_id)
        if stored_file is None or stored_file.status != FileStatus.READY:
            raise ResourceNotFoundException("文件不存在", 70001)
        if not stored_file.is_public and stored_file.owner_id != self.current_user.id:
            raise PermissionDeniedException("无权访问该私有文件")
        url = self.client.presigned_get_object(
            stored_file.bucket, stored_file.object_name, expires=timedelta(minutes=15)
        )
        return stored_file, url

    async def delete_file(self, file_id: int) -> None:
        stored_file = await self._owned_file(file_id)
        if stored_file.status == FileStatus.DELETED:
            return
        if stored_file.status == FileStatus.READY:
            self.client.remove_object(stored_file.bucket, stored_file.object_name)
        stored_file.status = FileStatus.DELETED
        stored_file.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def _owned_file(self, file_id: int) -> StoredFile:
        stored_file = await self.session.get(StoredFile, file_id)
        if stored_file is None:
            raise ResourceNotFoundException("文件不存在", 70001)
        if stored_file.owner_id != self.current_user.id:
            raise PermissionDeniedException("无权操作其他用户的文件")
        return stored_file

    @staticmethod
    def _validate_file(payload: PresignedUploadRequest, purpose: FilePurpose) -> None:
        if payload.size_bytes > PURPOSE_LIMITS[purpose]:
            raise ConflictException("文件超过该用途允许的大小", 70002)
        allowed_types = (
            IMAGE_TYPES
            if purpose in {FilePurpose.AVATAR, FilePurpose.COURSE_COVER}
            else DOCUMENT_TYPES
        )
        if payload.content_type not in allowed_types:
            raise ConflictException("不支持的文件类型", 70006)
        suffix = Path(payload.filename).suffix.lower()
        if not suffix or "/" in payload.filename or "\\" in payload.filename:
            raise ConflictException("文件名或扩展名无效", 70007)
