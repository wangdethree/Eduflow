from pydantic import BaseModel, Field


class PresignedUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)
    purpose: str = Field(
        pattern=r"^(avatar|course_cover|course_resource|lesson_attachment|export)$"
    )


class FileResponse(BaseModel):
    id: int
    original_name: str
    content_type: str
    size_bytes: int
    purpose: str
    status: str
    is_public: bool
    url: str | None = None
