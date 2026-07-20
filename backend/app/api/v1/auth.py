from fastapi import APIRouter, Request

from app.api.deps.auth import CurrentUser, DatabaseSession
from app.core.rate_limit import enforce_login_rate_limit, reset_login_rate_limit
from app.core.response import success
from app.schemas.user import (
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", status_code=201, summary="用户注册")
async def register(payload: RegisterRequest, session: DatabaseSession) -> dict:
    user = await AuthService(session).register(payload)
    return success(UserResponse.model_validate(user).model_dump(mode="json"), "注册成功")


@router.post("/login", response_model=None, summary="用户登录")
async def login(payload: LoginRequest, request: Request, session: DatabaseSession) -> dict:
    ip_address = request.client.host if request.client else ""
    await enforce_login_rate_limit(payload.account, ip_address)
    tokens: TokenResponse = await AuthService(session).login(
        payload.account,
        payload.password,
        ip_address=ip_address,
        user_agent=request.headers.get("User-Agent", ""),
    )
    await reset_login_rate_limit(payload.account, ip_address)
    return success(tokens.model_dump(mode="json"), "登录成功")


@router.post("/refresh", summary="刷新 Token")
async def refresh_token(
    payload: RefreshRequest, request: Request, session: DatabaseSession
) -> dict:
    tokens = await AuthService(session).refresh(
        payload.refresh_token,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("User-Agent", ""),
    )
    return success(tokens.model_dump(mode="json"))


@router.post("/logout", summary="退出登录")
async def logout(payload: LogoutRequest, session: DatabaseSession) -> dict:
    await AuthService(session).logout(payload.refresh_token)
    return success(message="退出成功")


@router.get("/me", summary="获取当前用户")
async def get_me(current_user: CurrentUser) -> dict:
    return success(UserResponse.model_validate(current_user).model_dump(mode="json"))


@router.patch("/me", summary="修改个人资料")
async def update_profile(
    payload: ProfileUpdateRequest, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await session.commit()
    await session.refresh(current_user)
    return success(UserResponse.model_validate(current_user).model_dump(mode="json"), "资料已更新")


@router.post("/change-password", summary="修改密码")
async def change_password(
    payload: PasswordChangeRequest, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await AuthService(session).change_password(
        current_user, payload.old_password, payload.new_password
    )
    return success(message="密码已修改，请重新登录")
