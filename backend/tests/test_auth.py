from app.core.config import settings
from app.core.security import hash_password


def _set_test_operator(monkeypatch, username="pytest-operator", password="pytest-pass-123"):
    test_hash = hash_password(password)
    monkeypatch.setattr(settings, "operator_credentials", f"{username}:{test_hash}")
    return username, password


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
