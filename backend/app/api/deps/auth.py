from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserStatus
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

