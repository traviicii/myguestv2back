from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorBody, ErrorResponse


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
    async def handle_app_error(_, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_payload(
                "invalid_request",
                "Request validation failed.",
                exc.errors(),
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(_, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload("http_error", message, exc.detail),
        )
