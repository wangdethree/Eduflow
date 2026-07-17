from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.response import success
from app.repositories.rbac import RbacRepository
from app.schemas.rbac import (
    IdListRequest,
    ManagedUserResponse,
    PermissionCreate,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    UserStatusRequest,
)
from app.services.rbac import RbacService

router = APIRouter(tags=["权限管理"])
RoleManager = Annotated[object, Depends(require_permissions("role:manage"))]
UserManager = Annotated[object, Depends(require_permissions("user:manage"))]


@router.get("/roles", summary="角色列表")
async def list_roles(_: RoleManager, session: DatabaseSession) -> dict:
    roles = await RbacRepository(session).list_roles()
    return success([RoleResponse.model_validate(item).model_dump(mode="json") for item in roles])


@router.post("/roles", status_code=201, summary="创建角色")
async def create_role(
    payload: RoleCreate, _: RoleManager, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    role = await RbacService(session, current_user).create_role(payload)
    return success(RoleResponse.model_validate(role).model_dump(mode="json"), "角色已创建")


@router.delete("/roles/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int, _: RoleManager, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await RbacService(session, current_user).delete_role(role_id)
    return success(message="角色已删除")


@router.put("/roles/{role_id}/permissions", summary="分配角色权限")
async def assign_permissions(
    role_id: int,
    payload: IdListRequest,
    _: RoleManager,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    role = await RbacService(session, current_user).assign_permissions(role_id, payload.ids)
    return success(RoleResponse.model_validate(role).model_dump(mode="json"), "权限已分配")


@router.get("/permissions", summary="权限列表")
async def list_permissions(_: RoleManager, session: DatabaseSession) -> dict:
    permissions = await RbacRepository(session).list_permissions()
    return success(
        [PermissionResponse.model_validate(item).model_dump(mode="json") for item in permissions]
    )


@router.post("/permissions", status_code=201, summary="创建权限")
async def create_permission(
    payload: PermissionCreate,
    _: RoleManager,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    permission = await RbacService(session, current_user).create_permission(payload)
    return success(PermissionResponse.model_validate(permission).model_dump(mode="json"))


@router.get("/users", summary="用户列表")
async def list_users(_: UserManager, session: DatabaseSession) -> dict:
    users = await RbacRepository(session).list_users()
    return success(
        [ManagedUserResponse.model_validate(item).model_dump(mode="json") for item in users]
    )


@router.put("/users/{user_id}/roles", summary="分配用户角色")
async def assign_user_roles(
    user_id: int,
    payload: IdListRequest,
    _: UserManager,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    user = await RbacService(session, current_user).assign_user_roles(user_id, payload.ids)
    return success(ManagedUserResponse.model_validate(user).model_dump(mode="json"))


@router.patch("/users/{user_id}/status", summary="修改用户状态")
async def change_user_status(
    user_id: int,
    payload: UserStatusRequest,
    _: UserManager,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    user = await RbacService(session, current_user).change_user_status(user_id, payload.status)
    return success({"id": user.id, "status": user.status.value})

