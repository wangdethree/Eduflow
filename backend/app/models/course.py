from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class CourseStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    PUBLISHED = "published"
    OFFLINE = "offline"


class LessonType(StrEnum):
    VIDEO = "video"
    ARTICLE = "article"


class CourseCategory(Base, TimestampMixin):
    __tablename__ = "course_categories"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("course_categories.id"))
    sort_order: Mapped[int] = mapped_column(default=0)
    is_enabled: Mapped[bool] = mapped_column(default=True)


class Course(Base, TimestampMixin):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_teacher_status", "teacher_id", "status"),
        Index("ix_courses_category_status", "category_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), index=True)
    subtitle: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str | None] = mapped_column(String(500))
    category_id: Mapped[int] = mapped_column(ForeignKey("course_categories.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[CourseStatus] = mapped_column(default=CourseStatus.DRAFT, index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    total_duration: Mapped[int] = mapped_column(default=0)
    student_count: Mapped[int] = mapped_column(default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[CourseCategory] = relationship(lazy="joined")
    teacher: Mapped["User"] = relationship(lazy="joined")
    chapters: Mapped[list["CourseChapter"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseChapter.sort_order",
        lazy="selectin",
    )
    audits: Mapped[list["CourseAudit"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class CourseChapter(Base, TimestampMixin):
    __tablename__ = "course_chapters"
    __table_args__ = (UniqueConstraint("course_id", "sort_order"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(150))
    sort_order: Mapped[int]

    course: Mapped[Course] = relationship(back_populates="chapters")
    lessons: Mapped[list["CourseLesson"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="CourseLesson.sort_order",
        lazy="selectin",
    )


class CourseLesson(Base, TimestampMixin):
    __tablename__ = "course_lessons"
    __table_args__ = (UniqueConstraint("chapter_id", "sort_order"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("course_chapters.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(150))
    lesson_type: Mapped[LessonType] = mapped_column(default=LessonType.VIDEO)
    content: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[int] = mapped_column(default=0)
    sort_order: Mapped[int]
    is_required: Mapped[bool] = mapped_column(default=True)
    is_free_preview: Mapped[bool] = mapped_column(default=False)

    chapter: Mapped[CourseChapter] = relationship(back_populates="lessons")


class CourseAudit(Base):
    __tablename__ = "course_audits"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    auditor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool]
    opinion: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    course: Mapped[Course] = relationship(back_populates="audits")

