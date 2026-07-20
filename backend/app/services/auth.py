import json
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException, ConflictException
from app.core.security import create_token, decode_token, hash_password, hash_token, verify_password
from app.models.rbac import OperationLog
from app.models.user import LoginLog, RefreshToken, User, UserStatus
from app.repositories.user import UserRepository
from app.schemas.user import RegisterRequest, TokenResponse, UserResponse

logger = structlog.get_logger()


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
        response = self._issue_token_pair(user)
        await self.session.commit()

        # 登录日志和刷新令牌均通过外键引用用户。先提交这些记录，再在独立事务中
        # 更新最后登录时间，可避免同一账号并发登录时 MySQL 的外键锁升级死锁。
        try:
            await self.users.update_last_login(user.id, datetime.now(UTC))
            await self.session.commit()
        except OperationalError as exc:
            if not self._is_mysql_lock_conflict(exc):
                raise
            # 最后登录时间是辅助信息，锁冲突不应使已成功签发的令牌返回 500。
            await self.session.rollback()
            await logger.awarning(
                "last_login_update_skipped",
                user_id=user.id,
                database_error_code=self._database_error_code(exc),
            )
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

    async def refresh(
        self, raw_token: str, *, ip_address: str = "", user_agent: str = ""
    ) -> TokenResponse:
        payload = decode_token(raw_token, "refresh")
        stored = await self.users.get_refresh_token(payload["jti"], for_update=True)
        now = datetime.now(UTC)
        if stored is not None and (
            stored.revoked_at is not None or hash_token(raw_token) != stored.token_hash
        ):
            await self._handle_refresh_token_replay(stored, now, ip_address, user_agent)
            raise AuthenticationException("Refresh Token 已失效")
        if (
            stored is None
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

    async def _handle_refresh_token_replay(
        self,
        stored: RefreshToken,
        detected_at: datetime,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """重放意味着令牌可能泄漏，立即终止该用户所有现有会话。"""

        user = await self.users.get_by_id(stored.user_id)
        if user is not None:
            user.token_version += 1
        await self.users.revoke_all_tokens(stored.user_id, detected_at)
        self.session.add(
            OperationLog(
                user_id=stored.user_id,
                action="security:refresh_replay",
                resource_type="user_session",
                resource_id=str(stored.user_id),
                detail=json.dumps(
                    {
                        "ip_address": ip_address,
                        "user_agent": user_agent[:500],
                        "token_jti": stored.jti,
                    },
                    ensure_ascii=False,
                ),
                created_at=detected_at,
            )
        )
        await self.session.commit()
        await logger.acritical(
            "refresh_token_replay_detected",
            user_id=stored.user_id,
            token_jti=stored.jti,
            ip_address=ip_address,
        )

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

    @staticmethod
    def _database_error_code(exc: OperationalError) -> int | None:
        args = getattr(exc.orig, "args", ())
        return args[0] if args and isinstance(args[0], int) else None

    @classmethod
    def _is_mysql_lock_conflict(cls, exc: OperationalError) -> bool:
        # 1213 为死锁，1205 为锁等待超时，均可安全忽略本次辅助字段更新。
        return cls._database_error_code(exc) in {1205, 1213}
