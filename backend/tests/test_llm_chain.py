import httpx
import pytest
from google.genai import errors as genai_errors

import app.features.llm.chain as chain_module
from app.core.config import settings
from app.core.exceptions import AllLLMsFailed
from app.features.llm.backup import GroqLLMClient
from app.features.llm.base import LLMClient
from app.features.llm.chain import LLMChain, _is_retryable, _normalized_primary_provider, get_llm_chain
from app.features.llm.gemini import GeminiLLMClient

# Fakes only in the automated suite - no real API calls on every test run (cost, network
# flakiness, determinism). Live Gemini/Groq/chain behavior was manually verified in Step 9
# and is documented in BUILD_LOG.md; re-verify live manually if either provider's API changes.


class WorkingClient(LLMClient):
    def generate(self, prompt, system=None):
        return f"response-to: {prompt}"


class FailingClient(LLMClient):
    def generate(self, prompt, system=None):
        raise RuntimeError("simulated provider failure")


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"{status} error", request=request, response=response)


def _genai_error(cls, code: int) -> genai_errors.APIError:
    return cls(code=code, response_json={"error": {"message": "simulated", "status": "ERROR"}})


def test_primary_success_backup_never_called():
    class ExplodingClient(LLMClient):
        def generate(self, prompt, system=None):
            raise AssertionError("backup should not have been called")

    chain = LLMChain(primary=WorkingClient(), backup=ExplodingClient())
    assert chain.generate("hello") == "response-to: hello"


def test_primary_fails_falls_back_to_backup():
    chain = LLMChain(primary=FailingClient(), backup=WorkingClient())
    assert chain.generate("hello") == "response-to: hello"


def test_both_fail_raises_all_llms_failed():
    chain = LLMChain(primary=FailingClient(), backup=FailingClient())
    with pytest.raises(AllLLMsFailed):
        chain.generate("hello", session_id="sess-123")


# --- error classification (which failures are eligible for fallback) ---------------------

@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_httpx_rate_limit_and_server_errors_are_retryable(status):
    assert _is_retryable(_http_status_error(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_httpx_invalid_request_and_auth_errors_are_not_retryable(status):
    assert _is_retryable(_http_status_error(status)) is False


def test_httpx_timeout_is_retryable():
    assert _is_retryable(httpx.TimeoutException("timed out")) is True


@pytest.mark.parametrize("status", [429, 500, 503])
def test_genai_rate_limit_and_server_errors_are_retryable(status):
    cls = genai_errors.ClientError if status < 500 else genai_errors.ServerError
    assert _is_retryable(_genai_error(cls, status)) is True


@pytest.mark.parametrize("status", [400, 401, 403])
def test_genai_invalid_request_and_auth_errors_are_not_retryable(status):
    assert _is_retryable(_genai_error(genai_errors.ClientError, status)) is False


def test_unclassified_errors_default_to_retryable():
    # Matches the chain's original broad fallback behavior for any error type it doesn't
    # specifically recognize (network failures, unexpected SDK errors, etc.).
    assert _is_retryable(RuntimeError("something unexpected")) is True


# --- non-retryable primary failure: backup is never attempted ----------------------------

def test_non_retryable_primary_failure_skips_backup_and_raises_all_llms_failed():
    class AuthFailingClient(LLMClient):
        def generate(self, prompt, system=None):
            raise _http_status_error(401)

    class ExplodingClient(LLMClient):
        def generate(self, prompt, system=None):
            raise AssertionError("backup should not have been called for a non-retryable error")

    chain = LLMChain(primary=AuthFailingClient(), backup=ExplodingClient())
    with pytest.raises(AllLLMsFailed):
        chain.generate("hello", session_id="sess-456")


def test_retryable_primary_failure_does_fall_back():
    class RateLimitedClient(LLMClient):
        def generate(self, prompt, system=None):
            raise _http_status_error(429)

    chain = LLMChain(primary=RateLimitedClient(), backup=WorkingClient())
    assert chain.generate("hello") == "response-to: hello"


# --- configurable primary provider (LLM_PRIMARY_PROVIDER) --------------------------------

@pytest.fixture(autouse=True)
def _reset_llm_chain_singleton():
    """get_llm_chain() caches a module-level singleton - each test here needs a fresh one
    built from its own monkeypatched setting, and must not leak its singleton to tests
    outside this file either."""
    chain_module._default_chain = None
    yield
    chain_module._default_chain = None


def test_llm_primary_provider_defaults_to_gemini_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "")
    assert _normalized_primary_provider() == "gemini"


def test_llm_primary_provider_rejects_unrecognized_value(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "openai")
    assert _normalized_primary_provider() == "gemini"


def test_llm_primary_provider_accepts_groq_case_insensitively(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "GROQ")
    assert _normalized_primary_provider() == "groq"


def test_get_llm_chain_defaults_to_gemini_primary(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "gemini")
    chain = get_llm_chain()
    assert isinstance(chain._primary, GeminiLLMClient)
    assert isinstance(chain._backup, GroqLLMClient)


def test_get_llm_chain_honors_groq_as_primary(monkeypatch):
    monkeypatch.setattr(settings, "llm_primary_provider", "groq")
    chain = get_llm_chain()
    assert isinstance(chain._primary, GroqLLMClient)
    assert isinstance(chain._backup, GeminiLLMClient)
