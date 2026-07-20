from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    parent_id: int | None = None
    sort_order: int = Field(default=0, ge=0)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None
    sort_order: int


class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    subtitle: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=10000)
    category_id: int
    difficulty: str = Field(default="beginner", pattern=r"^(beginner|intermediate|advanced)$")
    cover_url: str | None = Field(default=None, max_length=500)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    category_id: int | None = None
    difficulty: str | None = Field(
        default=None, pattern=r"^(beginner|intermediate|advanced)$"
    )
    cover_url: str | None = Field(default=None, max_length=500)


class LessonCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    lesson_type: str = Field(default="video", pattern=r"^(video|article)$")
    content: str = Field(default="", max_length=20000)
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    is_required: bool = True
    is_free_preview: bool = False


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    lesson_type: str | None = Field(default=None, pattern=r"^(video|article)$")
    content: str | None = Field(default=None, max_length=20000)
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    sort_order: int | None = Field(default=None, ge=1)
    is_required: bool | None = None
    is_free_preview: bool | None = None


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    lesson_type: str
    content: str
    duration_seconds: int
    sort_order: int
    is_required: bool
    is_free_preview: bool


class ChapterCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    sort_order: int | None = Field(default=None, ge=1)


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    sort_order: int
    lessons: list[LessonResponse] = []


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subtitle: str
    description: str
    cover_url: str | None
    category_id: int
    teacher_id: int
    status: str
    difficulty: str
    total_duration: int
    student_count: int
    published_at: datetime | None
    chapters: list[ChapterResponse] = []
    created_at: datetime


class CourseAuditRequest(BaseModel):
    approved: bool
    opinion: str = Field(default="", max_length=500)
