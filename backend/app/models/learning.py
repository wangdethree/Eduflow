from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class CourseEnrollment(Base, TimestampMixin):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[EnrollmentStatus] = mapped_column(default=EnrollmentStatus.ACTIVE)
    progress: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CourseFavorite(Base, TimestampMixin):
    __tablename__ = "course_favorites"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class LessonProgress(Base, TimestampMixin):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("course_lessons.id"), index=True)
    last_position: Mapped[int] = mapped_column(default=0)
    learned_seconds: Mapped[int] = mapped_column(default=0)
    progress_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    is_completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_updated_at: Mapped[int] = mapped_column(default=0)


class LearningDailyStat(Base, TimestampMixin):
    __tablename__ = "learning_daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "course_id", "stat_date"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    stat_date: Mapped[date] = mapped_column(Date)
    learned_seconds: Mapped[int] = mapped_column(default=0)
    completed_lessons: Mapped[int] = mapped_column(default=0)
