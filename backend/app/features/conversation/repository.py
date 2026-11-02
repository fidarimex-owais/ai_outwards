import json
from datetime import datetime, timezone

import redis

from app.core.config import settings
from app.core.exceptions import SessionNotFound
from app.features.conversation.states import SessionState

_KEY_PREFIX = "session:"


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


def new_session(session_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "session_id": session_id,
        "state": SessionState.IDLE.value,
        "current_batch": 1,
        "answers": {},
        "pending_clarification_field": None,
        "created_at": now,
        "updated_at": now,
    }


def save_session(client: redis.Redis, session: dict) -> None:
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.set(_key(session["session_id"]), json.dumps(session), ex=settings.session_ttl_seconds)


def load_session(client: redis.Redis, session_id: str) -> dict:
    raw = client.get(_key(session_id))
    if raw is None:
        raise SessionNotFound(session_id)
    return json.loads(raw)


def delete_session(client: redis.Redis, session_id: str) -> None:
    client.delete(_key(session_id))


def session_exists(client: redis.Redis, session_id: str) -> bool:
    return bool(client.exists(_key(session_id)))
