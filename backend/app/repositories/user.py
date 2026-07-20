from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import LoginLog, RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_account(self, account: str) -> User | None:
        statement = select(User).where(
            User.deleted_at.is_(None),
            or_(User.username == account, User.email == account.lower()),
        )
        return await self.session.scalar(statement)

    async def username_or_email_exists(self, username: str, email: str) -> bool:
        statement = select(User.id).where(or_(User.username == username, User.email == email))
        return await self.session.scalar(statement) is not None

    def add(self, user: User) -> None:
        self.session.add(user)

    def add_login_log(self, log: LoginLog) -> None:
        self.session.add(log)

    def add_refresh_token(self, token: RefreshToken) -> None:
        self.session.add(token)

    async def update_last_login(self, user_id: int, logged_in_at: datetime) -> None:
        """独立更新最后登录时间，避免与令牌外键写入形成锁升级死锁。"""

        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=logged_in_at)
            .execution_options(synchronize_session=False)
        )

    async def get_refresh_token(self, jti: str) -> RefreshToken | None:
        return await self.session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))

    async def revoke_all_tokens(self, user_id: int, revoked_at: datetime) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
