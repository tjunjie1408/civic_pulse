"""Stable API error envelope and exception handlers."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from civicpulse.api.dto.common import ApiErrorBody, ApiErrorResponse, JsonScalar


class ApiError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: Mapping[str, JsonScalar] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details or {})


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid4())


def _response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: Mapping[str, JsonScalar] | None = None,
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiErrorBody(
            code=code,
            message=message,
            details=dict(details or {}),
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def handle_api_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        return _response(
            request,
            code="internal_error",
            message="An unexpected internal error occurred.",
            status_code=500,
        )
    return _response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return _response(
            request,
            code="internal_error",
            message="An unexpected internal error occurred.",
            status_code=500,
        )
    return _response(
        request,
        code="validation_error",
        message="Request validation failed.",
        status_code=422,
        details={"error_count": len(exc.errors())},
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    del exc
    return _response(
        request,
        code="internal_error",
        message="An unexpected internal error occurred.",
        status_code=500,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
