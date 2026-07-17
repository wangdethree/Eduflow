from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class FileStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    DELETED = "deleted"


class FilePurpose(StrEnum):
    AVATAR = "avatar"
    COURSE_COVER = "course_cover"
    COURSE_RESOURCE = "course_resource"
    LESSON_ATTACHMENT = "lesson_attachment"
    EXPORT = "export"


class StoredFile(Base, TimestampMixin):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    object_name: Mapped[str] = mapped_column(String(500), unique=True)
    bucket: Mapped[str] = mapped_column(String(100))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    purpose: Mapped[FilePurpose] = mapped_column(index=True)
    status: Mapped[FileStatus] = mapped_column(default=FileStatus.PENDING, index=True)
    is_public: Mapped[bool] = mapped_column(default=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

