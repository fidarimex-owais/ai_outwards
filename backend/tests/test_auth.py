import pytest

from app.core.config import settings
from app.core.exceptions import InvalidCredentials, TooManyLoginAttempts
from app.core.redis import get_redis
from app.core.security import hash_password
from app.features.auth.service import login


def _set_test_operator(monkeypatch, username="pytest-operator", password="pytest-pass-123"):
    test_hash = hash_password(password)
    monkeypatch.setattr(settings, "operator_credentials", f"{username}:{test_hash}")
    return username, password


def _cleanup_attempts(username: str) -> None:
    # The rate-limit key is now scoped by (client_ip, username) - clean up by pattern rather
    # than assuming a single fixed IP in the key.
    redis_client = get_redis()
    for key in redis_client.keys(f"login_attempts:*:{username}"):
        redis_client.delete(key)


def test_unauthenticated_request_rejected(unauthed_client):
    r = unauthed_client.post("/sessions")
    assert r.status_code == 401


def test_login_wrong_password_rejected(unauthed_client, monkeypatch):
    username, _ = _set_test_operator(monkeypatch)
    r = unauthed_client.post("/auth/login", data={"username": username, "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_rejected(unauthed_client, monkeypatch):
    _set_test_operator(monkeypatch)
    r = unauthed_client.post("/auth/login", data={"username": "ghost", "password": "whatever"})
    assert r.status_code == 401


def test_login_success_and_token_grants_access(unauthed_client, monkeypatch):
    username, password = _set_test_operator(monkeypatch)
    r = unauthed_client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    r = unauthed_client.post("/sessions", headers=headers)
    assert r.status_code == 200


def test_garbage_token_rejected(unauthed_client):
    r = unauthed_client.post("/sessions", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401


def test_repeated_failed_logins_are_rate_limited(unauthed_client, monkeypatch):
    # Regression test: brute-forcing a single account's password was unlimited before this
    # fix - no attempt counter existed anywhere in the login path. All requests here come
    # from the same (TestClient) IP, so this still exercises the per-(IP, username) lockout.
    username, password = _set_test_operator(monkeypatch)
    _cleanup_attempts(username)
    try:
        for _ in range(settings.login_rate_limit_attempts):
            r = unauthed_client.post("/auth/login", data={"username": username, "password": "wrong"})
            assert r.status_code == 401

        r = unauthed_client.post("/auth/login", data={"username": username, "password": "wrong"})
        assert r.status_code == 429

        # Even the correct password is rejected once the limit is hit - the lockout is a
        # per-(IP, username) cooldown, not just a wrong-password filter.
        r = unauthed_client.post("/auth/login", data={"username": username, "password": password})
        assert r.status_code == 429
    finally:
        _cleanup_attempts(username)


def test_successful_login_resets_the_failed_attempt_counter(unauthed_client, monkeypatch):
    username, password = _set_test_operator(monkeypatch)
    _cleanup_attempts(username)
    try:
        unauthed_client.post("/auth/login", data={"username": username, "password": "wrong"})
        unauthed_client.post("/auth/login", data={"username": username, "password": "wrong"})

        r = unauthed_client.post("/auth/login", data={"username": username, "password": password})
        assert r.status_code == 200

        assert get_redis().keys(f"login_attempts:*:{username}") == []
    finally:
        _cleanup_attempts(username)


def test_rate_limit_is_scoped_per_ip_and_does_not_lock_out_other_ips(client, monkeypatch):
    # `client` isn't used directly - this test calls login() in-process - but it brings up
    # the app lifespan (connect_to_redis()) that get_redis() below requires.
    # Regression test: a username-only lockout let anyone who knows a real username lock
    # that account out for everyone, just by deliberately sending wrong passwords - a
    # denial-of-service on the legitimate user. Scoping the counter to (client_ip, username)
    # means an attacker exhausting their own budget from one IP has no effect on the same
    # username logging in correctly from a different IP.
    username, password = _set_test_operator(monkeypatch)
    redis_client = get_redis()
    _cleanup_attempts(username)
    try:
        for _ in range(settings.login_rate_limit_attempts):
            with pytest.raises(InvalidCredentials):
                login(username, "wrong", redis_client, client_ip="203.0.113.1")

        with pytest.raises(TooManyLoginAttempts):
            login(username, "wrong", redis_client, client_ip="203.0.113.1")

        # Same username, the legitimate user's own (different) IP - unaffected by the
        # attacker's lockout above.
        token = login(username, password, redis_client, client_ip="198.51.100.9")
        assert token.access_token
    finally:
        _cleanup_attempts(username)
