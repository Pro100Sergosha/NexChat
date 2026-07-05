from uuid import UUID

from app.core.auth.model import User
from app.core.auth.schemas import (
    ChangePasswordRequest,
    ChangeUsernameRequest,
    ForgotPasswordRequest,
    LogoutRequest,
    PublicUser,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenPair,
    UserResponse,
    VerifyEmailRequest,
)
from app.core.auth.service import AuthService


async def register(request: RegisterRequest, service: AuthService) -> UserResponse:
    user = await service.register(request.email, request.username, request.password)
    return UserResponse.model_validate(user)


async def verify_email(request: VerifyEmailRequest, service: AuthService) -> None:
    await service.verify_email(request.token)


async def resend_verification(
    request: ResendVerificationRequest, service: AuthService
) -> None:
    await service.resend_verification(request.email)


async def change_password(
    request: ChangePasswordRequest, user: User, service: AuthService
) -> TokenPair:
    return await service.change_password(
        user.id, request.current_password, request.new_password
    )


async def forgot_password(request: ForgotPasswordRequest, service: AuthService) -> None:
    await service.forgot_password(request.email)


async def reset_password(request: ResetPasswordRequest, service: AuthService) -> None:
    await service.reset_password(request.token, request.new_password)


async def change_username(
    request: ChangeUsernameRequest, user: User, service: AuthService
) -> UserResponse:
    updated = await service.change_username(user.id, request.username)
    return UserResponse.model_validate(updated)


async def get_user(user_id: UUID, service: AuthService) -> PublicUser:
    return PublicUser.model_validate(await service.get_user(user_id))


async def get_user_by_username(username: str, service: AuthService) -> PublicUser:
    return PublicUser.model_validate(await service.get_user_by_username(username))


async def login(email: str, password: str, service: AuthService) -> TokenPair:
    return await service.login(email, password)


async def refresh(request: RefreshRequest, service: AuthService) -> TokenPair:
    return await service.refresh(request.refresh_token)


async def logout(
    request: LogoutRequest, access_token: str, service: AuthService
) -> None:
    await service.logout(request.refresh_token, access_token)


async def me(user: User) -> UserResponse:
    return UserResponse.model_validate(user)
