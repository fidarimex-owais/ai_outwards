from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AllLLMsFailed,
    InvalidCredentials,
    InvalidTransition,
    SessionExpired,
    SessionNotFound,
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

    @app.exception_handler(AllLLMsFailed)
    async def _all_llms_failed(request: Request, exc: AllLLMsFailed) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "all_llms_failed",
                "detail": "We saved your progress. Please try again shortly.",
            },
        )
