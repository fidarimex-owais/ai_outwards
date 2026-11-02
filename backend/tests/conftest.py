import pytest
from fastapi.testclient import TestClient

from app.core.mongodb import get_db
from app.features.auth.dependencies import get_current_user
from app.features.llm.base import LLMClient
from app.features.llm.chain import LLMChain, get_llm_chain
from app.main import app


class FakeLLM(LLMClient):
    """Returns a canned JSON response when the prompt contains a matching substring, so
    TIME-field extraction (the only field type with no Python rule) is deterministic in
    tests - no real API calls, no cost, no network flakiness."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}

    def generate(self, prompt: str, system: str | None = None) -> str:
        for needle, response in self._responses.items():
            if needle in prompt:
                return response
        return '{"value": null, "ambiguous": true}'


@pytest.fixture
def client():
    """TestClient with the real app lifespan - connects to the real local Mongo + Redis,
    consistent with how every feature in this project has been verified."""
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _bypass_auth():
    """Every test is authenticated as a fixed fake user by default, so tests don't depend
    on whatever operator credentials happen to be in .env. test_auth.py explicitly removes
    this override to test the real login/token-verification path."""
    app.dependency_overrides[get_current_user] = lambda: "test-operator"
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def unauthed_client(client):
    """Same client, but with the auth bypass removed for this test only."""
    app.dependency_overrides.pop(get_current_user, None)
    yield client


@pytest.fixture
def fake_llm(client):
    """Overrides the LLM chain with canned responses. Returns the override function so a
    test can call it with a {prompt_substring: json_response} mapping."""
    def _install(responses: dict[str, str] | None = None) -> LLMChain:
        chain = LLMChain(primary=FakeLLM(responses), backup=FakeLLM(responses))
        app.dependency_overrides[get_llm_chain] = lambda: chain
        return chain

    yield _install
    app.dependency_overrides.pop(get_llm_chain, None)


@pytest.fixture
def created_sessions(client):
    """Tests that create real submissions append the session_id here; cleaned up from
    MongoDB after the test so the real submissions collection doesn't accumulate test data."""
    ids: list[str] = []
    yield ids
    if ids:
        db = get_db()
        db["submissions"].delete_many({"session_id": {"$in": ids}})
