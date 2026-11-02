from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "voice_assistant"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 3600

    # LLM providers
    gemini_api_key: str = ""
    backup_llm_provider: str = "groq"
    backup_llm_api_key: str = ""

    # Speech-to-Text: "groq" (cloud, whisper-large-v3-turbo, far more accurate) or "whisper"
    # (local faster-whisper, no network/API key needed but noticeably less accurate)
    stt_provider: str = "groq"
    stt_api_key: str = ""

    # Auth
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    # Static operator list: "username:bcrypt_hash;username2:bcrypt_hash2". No signup flow -
    # operators are provisioned by editing this value (see app/features/auth/repository.py).
    operator_credentials: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    # Comma-separated allowed origins for the separate React+Vite frontend (CORS).
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
