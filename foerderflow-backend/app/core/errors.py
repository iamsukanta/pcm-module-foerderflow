"""Error handling — reproduces the monolith's `{ error, code }` JSON envelope.

The monolith returns `{ error: <message>, code: <CODE> }` with an HTTP status.
APIError lets routes raise that shape directly; the handler also maps FastAPI's
validation errors into the same envelope so the frontend has one error contract.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, extra: dict | None = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_req: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code, **exc.extra},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        # detail may be a code string (from auth deps) or a human message.
        detail = exc.detail
        code = detail if isinstance(detail, str) and detail.isupper() else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(detail), "code": code},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _req: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validierungsfehler.",
                "code": "VALIDATION_ERROR",
                "details": exc.errors(),
            },
        )
