import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import AuthenticationException

password_hash = PasswordHash.recommended()
TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def hash_token(token: str) -> str:
    """数据库只保存令牌摘要，避免数据泄漏后令牌可直接使用。"""

    return hashlib.sha256(token.encode()).hexdigest()


def create_token(
    user_id: int,
    token_type: TokenType,
    *,
    expires_delta: timedelta,
    token_version: int,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "ver": token_version,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise AuthenticationException("Token 无效或已过期") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise AuthenticationException("Token 类型无效")
    return payload

