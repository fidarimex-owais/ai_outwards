import logging
from dataclasses import dataclass
from types import SimpleNamespace

from app.core.config import settings
from app.features.llm.gemini import GeminiLLMClient

# No network calls anywhere in this file - same fake-SDK pattern as test_gemini_logging.py:
# GeminiLLMClient is constructed with a fake api_key (never a real one) and its internal SDK
# client is swapped out for a fake object before generate() is ever called.


@dataclass
class _FakeResponse:
    text: str
    usage_metadata: object | None = None


class _FakeModels:
    """Stands in for genai.Client().models - generate_content() records the `model` kwarg
    it was called with (so tests can prove the resolved model actually reaches the API call)
    and returns a canned response instead of making a real request."""

    def __init__(self, response=None):
        self._response = response or _FakeResponse(text="ok")
        self.last_model_kwarg: str | None = None

    def generate_content(self, model, contents, config):
        self.last_model_kwarg = model
        return self._response


def _client_with_fake_sdk(**ctor_kwargs) -> tuple[GeminiLLMClient, _FakeModels]:
    client = GeminiLLMClient(api_key="test", **ctor_kwargs)  # fake key - never used
    fake_models = _FakeModels()
    client._client = SimpleNamespace(models=fake_models)
    return client, fake_models


def test_t1_settings_value_used_when_it_matches_the_hardcoded_default(monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")
    client, _ = _client_with_fake_sdk()
    assert client._model == "gemini-3.1-flash-lite"


def test_t2_settings_value_used_when_different_from_default(monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "some-other-model")
    client, _ = _client_with_fake_sdk()
    assert client._model == "some-other-model"


def test_t3_explicit_constructor_arg_wins_over_settings(monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "some-other-model")
    client, _ = _client_with_fake_sdk(model="ctor-model")
    assert client._model == "ctor-model"


def test_t4_whitespace_only_settings_value_falls_back_and_logs_one_warning(monkeypatch, caplog):
    monkeypatch.setattr(settings, "gemini_model", "   ")
    with caplog.at_level(logging.WARNING):
        client, _ = _client_with_fake_sdk()

    assert client._model == "gemini-3.1-flash-lite"
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["GEMINI_MODEL is empty - falling back to gemini-3.1-flash-lite"]


def test_t5_settings_value_is_stripped(monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "  padded-model  ")
    client, _ = _client_with_fake_sdk()
    assert client._model == "padded-model"


def test_t6_resolved_model_reaches_the_generate_content_call(monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "some-other-model")
    client, fake_models = _client_with_fake_sdk()

    client.generate("some prompt")

    assert fake_models.last_model_kwarg == "some-other-model"


def test_t7_no_log_line_contains_the_fake_api_key(monkeypatch, caplog):
    monkeypatch.setattr(settings, "gemini_model", "   ")  # triggers the one warning line too
    with caplog.at_level(logging.DEBUG):
        client, _ = _client_with_fake_sdk()
        client.generate("some prompt")

    for record in caplog.records:
        assert "test" not in record.message  # the fake api_key="test" must never appear
        assert "api_key" not in record.message.lower()
