from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    content: str = Field(min_length=2, max_length=10000)
    notification_type: str = Field(pattern=r"^(system|course|exam|grade)$")
    user_ids: list[int] = Field(min_length=1, max_length=1000)

