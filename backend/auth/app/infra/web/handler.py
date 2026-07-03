from app.core.auth.model import User
from app.core.auth.schemas import (
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.core.auth.service import AuthService


async def register(request: RegisterRequest, service: AuthService) -> UserResponse:
    user = await service.register(request.email, request.password)
    return UserResponse.model_validate(user)


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
