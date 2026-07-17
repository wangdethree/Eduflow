from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionCreate(BaseModel):
    stem: str = Field(min_length=2, max_length=5000)
    question_type: str = Field(pattern=r"^(single|multiple|boolean)$")
    options: dict[str, str] = Field(default_factory=dict)
    correct_answers: list[str] = Field(min_length=1)
    analysis: str = Field(default="", max_length=5000)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")

    @model_validator(mode="after")
    def validate_answers(self):
        answers = set(self.correct_answers)
        if self.question_type == "single" and len(answers) != 1:
            raise ValueError("单选题必须且只能有一个正确答案")
        if self.question_type == "multiple" and len(answers) < 2:
            raise ValueError("多选题至少需要两个正确答案")
        if self.question_type == "boolean" and answers not in ({"true"}, {"false"}):
            raise ValueError("判断题答案必须是 true 或 false")
        if self.question_type != "boolean" and not answers.issubset(self.options):
            raise ValueError("正确答案必须存在于选项中")
        return self


class PaperCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=500)


class PaperQuestionCreate(BaseModel):
    question_id: int
    score: Decimal = Field(gt=0, le=100)


class ExamCreate(BaseModel):
    course_id: int
    paper_id: int
    title: str = Field(min_length=2, max_length=150)
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int = Field(gt=0, le=1440)

    @field_validator("ends_at")
    @classmethod
    def end_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("考试时间必须包含时区")
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("考试结束时间必须晚于开始时间")
        return self


class AnswerSubmit(BaseModel):
    question_id: int
    selected_answers: list[str] = Field(max_length=20)


class ExamSubmitRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=64)
    answers: list[AnswerSubmit] = Field(max_length=500)


class AttemptResponse(BaseModel):
    id: int
    exam_id: int
    status: str
    objective_score: float
    total_score: float
    started_at: datetime
    submitted_at: datetime | None

