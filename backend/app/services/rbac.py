from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, ResourceNotFoundException
from app.models.rbac import OperationLog, Permission, Role
from app.models.user import User, UserStatus
from app.repositories.rbac import RbacRepository
from app.schemas.rbac import PermissionCreate, RoleCreate


class RbacService:
    def __init__(self, session: AsyncSession, operator: User) -> None:
        self.session = session
        self.operator = operator
        self.repository = RbacRepository(session)

    async def create_role(self, payload: RoleCreate) -> Role:
        role = Role(**payload.model_dump())
        self.session.add(role)
        self._log("role:create", "role", payload.code)
        await self._commit_unique("角色编码或名称已存在")
        await self.session.refresh(role, ["permissions"])
        return role

    async def delete_role(self, role_id: int) -> None:
        role = await self.repository.get_role(role_id)
        if role is None:
            raise ResourceNotFoundException("角色不存在", 30005)
        if role.is_system:
            raise ConflictException("系统内置角色不能删除", 30006)
        await self.session.delete(role)
        self._log("role:delete", "role", str(role_id))
        await self.session.commit()

    async def create_permission(self, payload: PermissionCreate) -> Permission:
        permission = Permission(**payload.model_dump())
        self.session.add(permission)
        self._log("permission:create", "permission", payload.code)
        await self._commit_unique("权限编码已存在")
        await self.session.refresh(permission)
        return permission

    async def assign_permissions(self, role_id: int, permission_ids: list[int]) -> Role:
        role = await self.repository.get_role(role_id)
        if role is None:
            raise ResourceNotFoundException("角色不存在", 30005)
        permissions = await self.repository.get_permissions(permission_ids)
        if len(permissions) != len(set(permission_ids)):
            raise ResourceNotFoundException("部分权限不存在", 30007)
        role.permissions = permissions
        self._log("role:assign_permissions", "role", str(role_id), str(permission_ids))
        await self.session.commit()
        await self.session.refresh(role, ["permissions"])
        return role

    async def assign_user_roles(self, user_id: int, role_ids: list[int]) -> User:
        user = await self.session.scalar(
            select(User).where(User.id == user_id).options(selectinload(User.roles))
        )
        if user is None:
            raise ResourceNotFoundException("用户不存在", 30001)
        roles = await self.repository.get_roles(role_ids)
        if len(roles) != len(set(role_ids)):
            raise ResourceNotFoundException("部分角色不存在", 30005)
        user.roles = roles
        user.token_version += 1
        self._log("user:assign_roles", "user", str(user_id), str(role_ids))
        await self.session.commit()
        await self.session.refresh(user, ["roles"])
        return user

    async def change_user_status(self, user_id: int, status: str) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("用户不存在", 30001)
        if user.id == self.operator.id and status == UserStatus.DISABLED:
            raise ConflictException("不能禁用当前登录账号", 30008)
        user.status = UserStatus(status)
        user.token_version += 1
        self._log("user:change_status", "user", str(user_id), status)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def _commit_unique(self, message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictException(message, 30009) from exc

    def _log(self, action: str, resource_type: str, resource_id: str, detail: str = "") -> None:
        self.session.add(
            OperationLog(
                user_id=self.operator.id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                created_at=datetime.now(UTC),
            )
        )

