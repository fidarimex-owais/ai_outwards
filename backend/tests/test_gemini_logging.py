import logging
from dataclasses import dataclass
from types import SimpleNamespace

from google.genai import errors as genai_errors

from app.core.config import settings
from app.features.llm.gemini import GeminiLLMClient

# No network calls anywhere in this file - GeminiLLMClient is constructed with a fake api_key
# (never a real one) and its internal SDK client is swapped out for a fake object, so
# generate() never reaches the real Gemini API.


@dataclass
class _FakeResponse:
    text: str
    usage_metadata: object | None


class _FakeModels:
    """Stands in for genai.Client().models - generate_content() just returns whatever
    canned response the test configured, instead of making a real API call."""

    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    def generate_content(self, model, contents, config):
        if self._error is not None:
            raise self._error
        return self._response


def _client_with_fake_sdk(response=None, error: Exception | None = None) -> GeminiLLMClient:
    client = GeminiLLMClient(api_key="test")  # fake key - never used, no network call happens
    client._client = SimpleNamespace(models=_FakeModels(response=response, error=error))
    return client


def test_usage_metadata_present_logs_token_counts(monkeypatch, caplog):
    # Pinned via monkeypatch rather than relying on settings.gemini_model's real default/
    # .env value, so this test's asserted model name never depends on what's in .env.
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")
    usage = SimpleNamespace(
        prompt_token_count=123, candidates_token_count=45, total_token_count=168,
        thoughts_token_count=None, cached_content_token_count=None,
    )
    client = _client_with_fake_sdk(response=_FakeResponse(text="hello", usage_metadata=usage))

    with caplog.at_level(logging.INFO):
        result = client.generate("some prompt")

    assert result == "hello"
    usage_lines = [r.message for r in caplog.records if "GEMINI_USAGE" in r.message]
    assert len(usage_lines) == 1
    line = usage_lines[0]
    assert "prompt_tokens=123" in line
    assert "candidates_tokens=45" in line
    assert "total_tokens=168" in line
    assert "gemini-3.1-flash-lite" in line


def test_usage_metadata_none_does_not_crash_and_logs_na(caplog):
    client = _client_with_fake_sdk(response=_FakeResponse(text="hello", usage_metadata=None))

    with caplog.at_level(logging.INFO):
        result = client.generate("some prompt")

    assert result == "hello"
    usage_lines = [r.message for r in caplog.records if "GEMINI_USAGE" in r.message]
    assert len(usage_lines) == 1
    assert "prompt_tokens=n/a" in usage_lines[0]
    assert "candidates_tokens=n/a" in usage_lines[0]
    assert "total_tokens=n/a" in usage_lines[0]


def test_rate_limit_error_is_logged_with_status_code_and_reraised(caplog):
    error = genai_errors.ClientError(code=429, response_json={"error": {"message": "simulated", "status": "ERROR"}})
    client = _client_with_fake_sdk(error=error)

    with caplog.at_level(logging.WARNING):
        try:
            client.generate("some prompt")
            raised = None
        except Exception as exc:  # noqa: BLE001 - we want to inspect whatever was raised
            raised = exc

    assert raised is error  # the exact same exception object, not wrapped or replaced
    failure_lines = [r.message for r in caplog.records if "call_failed" in r.message]
    assert len(failure_lines) == 1
    assert "status_code=429" in failure_lines[0]
    assert "ClientError" in failure_lines[0]


def test_log_lines_never_contain_the_prompt_or_api_key(caplog):
    secret_prompt = "SECRET_PROMPT_TEXT_12345"
    usage = SimpleNamespace(
        prompt_token_count=10, candidates_token_count=5, total_token_count=15,
        thoughts_token_count=None, cached_content_token_count=None,
    )
    client = _client_with_fake_sdk(response=_FakeResponse(text="irrelevant", usage_metadata=usage))

    with caplog.at_level(logging.INFO):
        client.generate(secret_prompt)

    for record in caplog.records:
        assert secret_prompt not in record.message
        assert "test" not in record.message  # the fake api_key="test" must never appear
        assert "api_key" not in record.message.lower()
