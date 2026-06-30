from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.auth.exceptions import (
    InvalidCredentials,
    TokenExpired,
    TokenInvalid,
    TokenRevoked,
    UserAlreadyExists,
    UserNotFound,
)
from app.core.exception import AppException

_STATUS_MAP: dict[type[AppException], int] = {
    UserAlreadyExists: 409,
    UserNotFound: 404,
    InvalidCredentials: 401,
    TokenExpired: 401,
    TokenInvalid: 401,
    TokenRevoked: 401,
}


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.__class__.__name__},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
