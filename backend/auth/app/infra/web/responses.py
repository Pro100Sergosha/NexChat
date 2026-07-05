from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.auth.exceptions import (
    EmailAlreadyVerified,
    EmailNotVerified,
    InvalidCredentials,
    NotAuthenticated,
    TokenExpired,
    TokenInvalid,
    TokenRevoked,
    TooManyAttempts,
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
    NotAuthenticated: 401,
    TooManyAttempts: 429,
    EmailNotVerified: 403,
    EmailAlreadyVerified: 409,
}

_SKIP_LOC_PARTS = {"body", "query", "path", "header", "cookie"}


def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    status_code = _STATUS_MAP.get(type(exc), 400)
    return JSONResponse(
        status_code=status_code,
        content={"code": exc.code, "message": exc.message},
    )


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(part) for part in loc if str(part) not in _SKIP_LOC_PARTS]
    return parts[-1] if parts else "field"


def _friendly_message(error: dict[str, Any]) -> str:
    field = _field_name(error["loc"])
    display = field.replace("_", " ").capitalize()
    err_type = error["type"]
    ctx = error.get("ctx", {})

    if err_type == "missing":
        return f"{display} is required"
    if err_type == "string_too_short":
        return f"{display} must be at least {ctx['min_length']} characters"
    if err_type == "string_too_long":
        return f"{display} must be at most {ctx['max_length']} characters"
    if field == "email":
        return "The email address is not valid"
    if err_type == "value_error":
        # custom field_validator ValueError — the raw msg is prefixed with
        # "Value error, "; our validators already name the field, so strip it.
        return str(error["msg"]).removeprefix("Value error, ")
    return str(error["msg"])


def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    message = _friendly_message(exc.errors()[0])
    return JSONResponse(
        status_code=422,
        content={"code": "validation_error", "message": message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
