from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException, ConflictException
from app.core.security import create_token, decode_token, hash_password, hash_token, verify_password
from app.models.user import LoginLog, RefreshToken, User, UserStatus
from app.repositories.user import UserRepository
from app.schemas.user import RegisterRequest, TokenResponse, UserResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
        email = payload.email.lower()
        if await self.users.username_or_email_exists(payload.username, email):
            raise ConflictException("用户名或邮箱已被使用", 30004)
        user = User(
            username=payload.username,
            email=email,
            password_hash=hash_password(payload.password),
            nickname=payload.nickname or payload.username,
        )
        self.users.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def login(
        self, account: str, password: str, *, ip_address: str, user_agent: str
    ) -> TokenResponse:
        user = await self.users.get_by_account(account)
        valid = user is not None and verify_password(password, user.password_hash)
        reason = None
        if not valid:
            reason = "账号或密码错误"
        elif user.status != UserStatus.ACTIVE:
            reason = "用户已禁用"
        self.users.add_login_log(
            LoginLog(
                user_id=user.id if user else None,
                account=account,
                ip_address=ip_address,
                user_agent=user_agent[:1000],
                success=reason is None,
                failure_reason=reason,
                created_at=datetime.now(UTC),
            )
        )
        if reason:
            await self.session.commit()
            raise AuthenticationException(reason)
        assert user is not None
        user.last_login_at = datetime.now(UTC)
        response = self._issue_token_pair(user)
        await self.session.commit()
        return response

    def _issue_token_pair(self, user: User) -> TokenResponse:
        access, _, _ = create_token(
            user.id,
            "access",
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            token_version=user.token_version,
        )
        refresh, jti, expires_at = create_token(
            user.id,
            "refresh",
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
            token_version=user.token_version,
        )
        self.users.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                jti=jti,
                token_hash=hash_token(refresh),
                expires_at=expires_at,
            )
        )
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )

    async def refresh(self, raw_token: str) -> TokenResponse:
        payload = decode_token(raw_token, "refresh")
        stored = await self.users.get_refresh_token(payload["jti"])
        now = datetime.now(UTC)
        if (
            stored is None
            or stored.revoked_at is not None
            or hash_token(raw_token) != stored.token_hash
            or self._is_expired(stored.expires_at, now)
        ):
            raise AuthenticationException("Refresh Token 已失效")
        user = await self.users.get_by_id(int(payload["sub"]))
        if user is None or user.status != UserStatus.ACTIVE or payload["ver"] != user.token_version:
            raise AuthenticationException("用户状态已变更，请重新登录")
        stored.revoked_at = now
        response = self._issue_token_pair(user)
        await self.session.commit()
        return response

    async def logout(self, raw_token: str) -> None:
        payload = decode_token(raw_token, "refresh")
        stored = await self.users.get_refresh_token(payload["jti"])
        if stored and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise AuthenticationException("原密码错误")
        if verify_password(new_password, user.password_hash):
            raise ConflictException("新密码不能与原密码相同")
        now = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        await self.users.revoke_all_tokens(user.id, now)
        await self.session.commit()

    @staticmethod
    def _is_expired(value: datetime, now: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value <= now

