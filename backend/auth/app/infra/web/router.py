from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.auth.schemas import (
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.core.auth.service import AuthService
from app.infra.web import handler
from app.infra.web.dependables import get_access_token, get_auth_service

# Routes are mounted at the root; Nginx proxies /api/auth/* and strips the prefix.
router = APIRouter(tags=["auth"])

ServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccessTokenDep = Annotated[str, Depends(get_access_token)]


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
async def register(request: RegisterRequest, service: ServiceDep) -> UserResponse:
    return await handler.register(request, service)


@router.post("/login")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: ServiceDep,
) -> TokenPair:
    return await handler.login(form.username, form.password, service)


@router.post("/refresh")
async def refresh(request: RefreshRequest, service: ServiceDep) -> TokenPair:
    return await handler.refresh(request, service)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    service: ServiceDep,
    access_token: AccessTokenDep,
) -> None:
    await handler.logout(request, access_token, service)
