from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.chat.exceptions import (
    ChatAppException,
    ConversationNotFound,
    MessageContentEmpty,
    MessageTooLong,
    NotAuthenticated,
    NotParticipant,
    SelfConversationNotAllowed,
    TokenExpired,
    TokenInvalid,
)

_STATUS_MAP: dict[type[ChatAppException], int] = {
    ConversationNotFound: 404,
    NotParticipant: 404,
    SelfConversationNotAllowed: 422,
    MessageContentEmpty: 422,
    MessageTooLong: 422,
    TokenInvalid: 401,
    TokenExpired: 401,
    NotAuthenticated: 401,
}

_SKIP_LOC_PARTS = {"body", "query", "path", "header", "cookie"}


def app_exception_handler(_: Request, exc: ChatAppException) -> JSONResponse:
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
    err_type = error["type"]
    ctx = error.get("ctx", {})

    if err_type == "missing":
        return f"{field} is required"
    if err_type == "string_too_short":
        return f"{field} must be at least {ctx['min_length']} characters"
    if err_type == "string_too_long":
        return f"{field} must be at most {ctx['max_length']} characters"
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
    app.add_exception_handler(ChatAppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
