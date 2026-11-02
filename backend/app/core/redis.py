import redis

from app.core.config import settings

_client: redis.Redis | None = None


def connect_to_redis() -> None:
    global _client
    _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    _client.ping()


def close_redis_connection() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis client not initialized. Call connect_to_redis() first.")
    return _client
