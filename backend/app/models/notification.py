from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class NotificationType(StrEnum):
    SYSTEM = "system"
    COURSE = "course"
    EXAM = "exam"
    GRADE = "grade"


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150))
    content: Mapped[str] = mapped_column(Text)
    notification_type: Mapped[NotificationType] = mapped_column(index=True)
    source_key: Mapped[str | None] = mapped_column(String(150), unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    recipients: Mapped[list["UserNotification"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )


class UserNotification(Base, TimestampMixin):
    __tablename__ = "user_notifications"
    __table_args__ = (UniqueConstraint("notification_id", "user_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification: Mapped[Notification] = relationship(back_populates="recipients", lazy="joined")

