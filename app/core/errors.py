import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorBody, ErrorResponse

logger = logging.getLogger("myguest.errors")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _payload(code: str, message: str, details=None) -> dict:
    return ErrorResponse(error=ErrorBody(code=code, message=message, details=details)).model_dump()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", None)
        level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
        logger.log(
            level,
            "app_error request_id=%s method=%s path=%s status=%s code=%s",
            request_id,
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "validation_error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=422,
            content=_payload(
                "invalid_request",
                "Request validation failed.",
                exc.errors(),
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        logger.warning(
            "http_error request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.url.path,
            exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload("http_error", message, exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "unhandled_error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content=_payload(
                "internal_server_error",
                "An unexpected server error occurred.",
            ),
        )
