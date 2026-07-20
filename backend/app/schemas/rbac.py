from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PermissionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$", max_length=100)
    description: str = Field(default="", max_length=255)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=50)
    description: str = Field(default="", max_length=255)


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: str
    is_system: bool
    permissions: list[PermissionResponse] = []
    created_at: datetime


class IdListRequest(BaseModel):
    ids: list[int] = Field(max_length=100)


class UserStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(active|disabled)$")


class ManagedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    nickname: str
    status: str
    roles: list[RoleResponse] = []
    created_at: datetime


class OperationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    action: str
    resource_type: str
    resource_id: str
    detail: str
    created_at: datetime
