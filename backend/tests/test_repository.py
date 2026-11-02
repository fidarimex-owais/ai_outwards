"""Verifies conversation/repository.py against the real local Redis instance."""
from app.core import redis as redis_mod
from app.core.exceptions import SessionNotFound
from app.features.conversation.repository import (
    delete_session,
    load_session,
    new_session,
    save_session,
    session_exists,
)
from app.features.conversation.states import SessionState


def test_session_lifecycle_against_live_redis():
    redis_mod.connect_to_redis()
    try:
        client = redis_mod.get_redis()
        sid = "pytest-session-lifecycle"
        delete_session(client, sid)

        assert not session_exists(client, sid)

        session = new_session(sid)
        assert session["state"] == SessionState.IDLE.value
        session["answers"]["company_name"] = "ABC Traders"
        save_session(client, session)

        assert session_exists(client, sid)

        loaded = load_session(client, sid)
        assert loaded["session_id"] == sid
        assert loaded["answers"]["company_name"] == "ABC Traders"

        ttl = client.ttl(f"session:{sid}")
        assert 0 < ttl <= 3600

        delete_session(client, sid)
        assert not session_exists(client, sid)

        try:
            load_session(client, sid)
            assert False, "expected SessionNotFound"
        except SessionNotFound:
            pass
    finally:
        redis_mod.close_redis_connection()
