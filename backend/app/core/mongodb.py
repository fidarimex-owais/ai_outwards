from pymongo import MongoClient, ASCENDING
from pymongo.database import Database

from app.core.config import settings

_client: MongoClient | None = None


def connect_to_mongo() -> None:
    global _client
    _client = MongoClient(settings.mongo_url)
    db = _client[settings.mongo_db_name]
    db["submissions"].create_index([("session_id", ASCENDING)], unique=True)


def close_mongo_connection() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> Database:
    if _client is None:
        raise RuntimeError("MongoDB client not initialized. Call connect_to_mongo() first.")
    return _client[settings.mongo_db_name]
