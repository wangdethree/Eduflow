from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

ID_TYPE = BigInteger().with_variant(Integer, "sqlite")


class QuestionType(StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    BOOLEAN = "boolean"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    EXPIRED = "expired"


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    stem: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(index=True)
    correct_answers: Mapped[list[str]] = mapped_column(JSON)
    analysis: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", lazy="selectin"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (UniqueConstraint("question_id", "option_key"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    option_key: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(String(1000))
    question: Mapped[Question] = relationship(back_populates="options")


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(500), default="")
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    questions: Mapped[list["PaperQuestion"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperQuestion.sort_order",
        lazy="selectin",
    )


class PaperQuestion(Base):
    __tablename__ = "paper_questions"
    __table_args__ = (UniqueConstraint("paper_id", "question_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    sort_order: Mapped[int]
    paper: Mapped[Paper] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(lazy="joined")


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int]
    is_published: Mapped[bool] = mapped_column(default=True)
    paper: Mapped[Paper] = relationship(lazy="joined")


class ExamAttempt(Base, TimestampMixin):
    __tablename__ = "exam_attempts"
    __table_args__ = (
        UniqueConstraint("exam_id", "user_id"),
        UniqueConstraint("idempotency_key"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[AttemptStatus] = mapped_column(default=AttemptStatus.IN_PROGRESS)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    objective_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    duration_seconds: Mapped[int] = mapped_column(default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answers: Mapped[list["ExamAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", lazy="selectin"
    )


class ExamAnswer(Base, TimestampMixin):
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    selected_answers: Mapped[list[str]] = mapped_column(JSON)
    is_correct: Mapped[bool]
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    attempt: Mapped[ExamAttempt] = relationship(back_populates="answers")


class WrongQuestion(Base, TimestampMixin):
    __tablename__ = "wrong_questions"
    __table_args__ = (UniqueConstraint("user_id", "question_id"),)

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    wrong_count: Mapped[int] = mapped_column(default=1)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
