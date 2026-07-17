from pydantic import BaseModel, Field


class ProgressReportRequest(BaseModel):
    lesson_id: int
    position_seconds: int = Field(ge=0)
    learned_seconds_delta: int = Field(ge=0, le=60)
    client_updated_at: int = Field(gt=0)


class ProgressResponse(BaseModel):
    user_id: int
    course_id: int
    lesson_id: int
    position: int
    duration: int
    learned_seconds: int
    progress_percent: float
    is_completed: bool
    updated_at: int


class EnrollmentResponse(BaseModel):
    id: int
    course_id: int
    status: str
    progress: float

