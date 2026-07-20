from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rbac import OperationLog, Permission, Role, role_permissions, user_roles
from app.models.user import User


class RbacRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_roles(self) -> list[Role]:
        result = await self.session.scalars(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.id)
        )
        return list(result.unique())

    async def get_role(self, role_id: int) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )

    async def get_role_by_code(self, code: str) -> Role | None:
        return await self.session.scalar(select(Role).where(Role.code == code))

    async def list_permissions(self) -> list[Permission]:
        return list(await self.session.scalars(select(Permission).order_by(Permission.code)))

    async def get_permissions(self, ids: list[int]) -> list[Permission]:
        if not ids:
            return []
        return list(await self.session.scalars(select(Permission).where(Permission.id.in_(ids))))

    async def get_roles(self, ids: list[int]) -> list[Role]:
        if not ids:
            return []
        return list(await self.session.scalars(select(Role).where(Role.id.in_(ids))))

    async def user_has_permissions(self, user_id: int, codes: set[str]) -> bool:
        if not codes:
            return True
        statement = (
            select(Permission.code)
            .join(role_permissions, Permission.id == role_permissions.c.permission_id)
            .join(user_roles, role_permissions.c.role_id == user_roles.c.role_id)
            .where(user_roles.c.user_id == user_id, Permission.code.in_(codes))
        )
        granted = set(await self.session.scalars(statement))
        return codes.issubset(granted)

    async def list_users(self) -> list[User]:
        result = await self.session.scalars(
            select(User).where(User.deleted_at.is_(None)).options(selectinload(User.roles))
        )
        return list(result.unique())

    async def list_operation_logs(
        self,
        page: int,
        page_size: int,
        user_id: int | None,
        action: str | None,
        resource_type: str | None,
    ) -> tuple[list[OperationLog], int]:
        filters = []
        if user_id is not None:
            filters.append(OperationLog.user_id == user_id)
        if action:
            filters.append(OperationLog.action.contains(action))
        if resource_type:
            filters.append(OperationLog.resource_type == resource_type)
        total = await self.session.scalar(
            select(func.count(OperationLog.id)).where(*filters)
        ) or 0
        items = await self.session.scalars(
            select(OperationLog)
            .where(*filters)
            .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(items), total
