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
