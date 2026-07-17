from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserStatus
from app.repositories.rbac import RbacRepository
from app.repositories.user import UserRepository

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise AuthenticationException("缺少 Access Token", 20001)
    payload = decode_token(credentials.credentials, "access")
    user = await UserRepository(session).get_by_id(int(payload["sub"]))
    if user is None or user.status != UserStatus.ACTIVE or payload["ver"] != user.token_version:
        raise AuthenticationException("用户不存在、已禁用或登录状态已失效")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


def require_permissions(*permission_codes: str) -> Callable:
    """声明式接口权限依赖，传入的权限必须全部具备。"""

    async def permission_checker(
        current_user: CurrentUser, session: DatabaseSession
    ) -> User:
        from app.core.exceptions import PermissionDeniedException

        allowed = await RbacRepository(session).user_has_permissions(
            current_user.id, set(permission_codes)
        )
        if not allowed:
            raise PermissionDeniedException("当前角色没有所需接口权限")
        return current_user

    return permission_checker
