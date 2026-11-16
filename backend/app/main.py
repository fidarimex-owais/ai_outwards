import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.mongodb import close_mongo_connection, connect_to_mongo
from app.core.redis import close_redis_connection, connect_to_redis
from app.features.auth.router import router as auth_router
from app.features.conversation.router import router as conversation_router
from app.features.speech.router import router as speech_router
from app.features.submissions.router import router as submissions_router

# This block = app-wide logging configuration, controlled by settings.log_level (LOG_LEVEL in
# .env). Uvicorn's own --log-level only configures its own "uvicorn"/"uvicorn.error"/
# "uvicorn.access" loggers (confirmed by inspecting uvicorn.config.LOGGING_CONFIG - it has no
# "root" entry), so without this, every app.* logger (e.g. app.features.llm.gemini's
# GEMINI_USAGE lines) inherits the root logger's default WARNING level and INFO lines are
# silently dropped. force=True is deliberately NOT used: the root logger has no handlers at
# this point (nothing else in this app or uvicorn's config touches it), so basicConfig's
# normal "do nothing if root already has handlers" guard never triggers here anyway - using
# force would be an unnecessary, blunter tool that could later strip out some other
# legitimate handler we haven't anticipated.
_VALID_LOG_LEVEL_NAMES = {"CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG", "NOTSET"}
_log_level_name = (settings.log_level or "").strip().upper()
_log_level = getattr(logging, _log_level_name) if _log_level_name in _VALID_LOG_LEVEL_NAMES else logging.INFO
logging.basicConfig(level=_log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    connect_to_redis()
    yield
    close_redis_connection()
    close_mongo_connection()


app = FastAPI(title="Voice Data Collection Assistant", lifespan=lifespan)

# The frontend is now a separate origin (React+Vite dev server on :5173) talking to this API
# on :8000, rather than being served same-origin as before - CORS is required, not optional.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(auth_router)
app.include_router(speech_router)
app.include_router(conversation_router)
app.include_router(submissions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
