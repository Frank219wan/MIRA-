"""Consistent public API errors without stack-trace leakage."""

from __future__ import annotations

import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(
        self, code: str, message: str, details: Any = None, status_code: int = 400
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code


def error_body(
    code: str, message: str, details: Any = None, request_id: str | None = None
) -> dict[str, Any]:
    body = {"error": {"code": code, "message": message, "details": details}}
    if request_id is not None:
        body["request_id"] = request_id
    return body


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            error_body(
                exc.code, exc.message, exc.details, getattr(request.state, "request_id", None)
            )
        ),
    )


async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    code = "invalid_tutorial_input" if request.url.path == "/tutorials/parse" else "invalid_request_payload"
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_body(
                code,
                "Request payload validation failed.",
                exc.errors(),
                getattr(request.state, "request_id", None),
            )
        ),
    )


async def unexpected_error_handler(request: Request, __: Exception) -> JSONResponse:
    logging.getLogger("mira").exception(
        "unexpected_api_error request_id=%s", getattr(request.state, "request_id", None)
    )
    return JSONResponse(
        status_code=500,
        content=error_body(
            "internal_error", "Unexpected server error.", request_id=getattr(request.state, "request_id", None)
        ),
    )
