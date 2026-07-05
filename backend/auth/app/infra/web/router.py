from typing import Annotated

from fastapi import APIRouter, Depends, Response, Security, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.auth.model import User
from app.core.auth.schemas import (
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenPair,
    UserResponse,
    VerifyEmailRequest,
)
from app.core.auth.service import AuthService
from app.infra.web import handler
from app.infra.web.dependables import (
    get_access_token,
    get_auth_service,
    get_current_user,
    oauth2_scheme,
)

# Routes are mounted at the root; Nginx proxies /api/auth/* and strips the prefix.
router = APIRouter(tags=["auth"])

ServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccessTokenDep = Annotated[str, Depends(get_access_token)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


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


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(request: VerifyEmailRequest, service: ServiceDep) -> None:
    await handler.verify_email(request, service)


@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest, service: ServiceDep
) -> Response:
    await handler.resend_verification(request, service)
    # 202 with an empty body — never reveal whether the address existed.
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/refresh")
async def refresh(request: RefreshRequest, service: ServiceDep) -> TokenPair:
    return await handler.refresh(request, service)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Security(oauth2_scheme)],
)
async def logout(
    request: LogoutRequest,
    service: ServiceDep,
    access_token: AccessTokenDep,
) -> None:
    await handler.logout(request, access_token, service)


@router.get("/me", dependencies=[Security(oauth2_scheme)])
async def me(user: CurrentUserDep) -> UserResponse:
    return await handler.me(user)
