from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AllLLMsFailed,
    ExtractionParseFailed,
    InvalidCredentials,
    InvalidTransition,
    SessionExpired,
    SessionNotFound,
    TooManyLoginAttempts,
    UnknownField,
)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotFound)
    async def _session_not_found(request: Request, exc: SessionNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "session_not_found", "detail": str(exc)})

    @app.exception_handler(SessionExpired)
    async def _session_expired(request: Request, exc: SessionExpired) -> JSONResponse:
        return JSONResponse(status_code=410, content={"error": "session_expired", "detail": str(exc)})

    @app.exception_handler(InvalidTransition)
    async def _invalid_transition(request: Request, exc: InvalidTransition) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "invalid_transition", "detail": str(exc)})

    @app.exception_handler(InvalidCredentials)
    async def _invalid_credentials(request: Request, exc: InvalidCredentials) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "invalid_credentials", "detail": str(exc)})

    @app.exception_handler(UnknownField)
    async def _unknown_field(request: Request, exc: UnknownField) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": "unknown_field", "detail": str(exc)})

    @app.exception_handler(TooManyLoginAttempts)
    async def _too_many_login_attempts(request: Request, exc: TooManyLoginAttempts) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": "too_many_login_attempts", "detail": "Too many failed attempts. Try again later."},
        )

    @app.exception_handler(AllLLMsFailed)
    async def _all_llms_failed(request: Request, exc: AllLLMsFailed) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "all_llms_failed",
                "detail": "We saved your progress. Please try again shortly.",
            },
        )

    # Safety net only - every call site that can raise this catches it in-band (see
    # conversation/service.py and submissions/service.py) to ask the user to retry without
    # losing their progress. This 503 only fires if some future call site forgets to.
    @app.exception_handler(ExtractionParseFailed)
    async def _extraction_parse_failed(request: Request, exc: ExtractionParseFailed) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "extraction_parse_failed",
                "detail": "We had trouble processing that. Please try again.",
            },
        )
