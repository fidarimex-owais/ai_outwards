import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.features.speech.base import STTClient, STTResult
from app.features.speech.provider import get_stt_client
from app.features.speech.router import MAX_UPLOAD_BYTES, _UPLOAD_READ_CHUNK_SIZE, transcribe
from app.main import app

FIXTURE = Path(__file__).parent / "fixtures" / "test_tone.wav"


class _FakeSTTClient(STTClient):
    """No network/model call - used for every test below except the one explicitly marked
    @pytest.mark.live, which is excluded from a plain `pytest -q` run (see pytest.ini)."""

    def transcribe(self, audio_bytes: bytes, audio_format: str = "wav", language: str = "en") -> STTResult:
        return STTResult(text="fake", confidence=1.0)


def test_unauthenticated_transcribe_rejected(unauthed_client):
    with open(FIXTURE, "rb") as f:
        r = unauthed_client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 401


def test_transcribe_pipeline_wiring_with_fake_stt(client):
    """Default (non-live) coverage for the endpoint -> service -> provider wiring, using the
    fake STT client - no network call. The real-provider equivalent of this test is
    test_transcribe_runs_the_real_pipeline_live below, which is excluded from a plain
    `pytest -q` run."""
    app.dependency_overrides[get_stt_client] = lambda: _FakeSTTClient()
    try:
        with open(FIXTURE, "rb") as f:
            r = client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
        assert r.status_code == 200
        data = r.json()
        assert "text" in data and "confidence" in data and "needs_repeat" in data
        assert isinstance(data["text"], str)
        assert 0.0 <= data["confidence"] <= 1.0
    finally:
        app.dependency_overrides.pop(get_stt_client, None)


@pytest.mark.live
def test_transcribe_runs_the_real_pipeline_live(client, monkeypatch):
    """Not a fake - exercises the real STT provider end to end through the endpoint ->
    service -> provider wiring. Pinned to "groq" via monkeypatch (not read from real .env)
    so which provider this test exercises is deterministic regardless of local STT_PROVIDER -
    the real GROQ_API_KEY/BACKUP_LLM_API_KEY from .env is still needed to actually
    authenticate, since that's the whole point of a live test.

    Excluded by default (see pytest.ini's `addopts = -m "not live"`) - run on purpose with:
        python -m pytest -m live -q

    The fixture is a pure tone, not speech, so content is non-deterministic: cloud Whisper
    sometimes returns "" or stray punctuation, sometimes hallucinates a word pulled from the
    domain-vocabulary prompt. Either way the response shape must be well-formed and the
    request must not error - that's what this test actually checks, not the exact
    hallucinated content."""
    monkeypatch.setattr(settings, "stt_provider", "groq")
    with open(FIXTURE, "rb") as f:
        r = client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 200
    data = r.json()
    assert "text" in data and "confidence" in data and "needs_repeat" in data
    assert isinstance(data["text"], str)
    assert 0.0 <= data["confidence"] <= 1.0


def test_oversized_upload_rejected_with_413(client):
    app.dependency_overrides[get_stt_client] = lambda: _FakeSTTClient()
    try:
        oversized = io.BytesIO(b"\x00" * (MAX_UPLOAD_BYTES + 1024 * 1024))
        r = client.post("/speech/transcribe", files={"audio": ("big.wav", oversized, "audio/wav")})
        assert r.status_code == 413
    finally:
        app.dependency_overrides.pop(get_stt_client, None)


def test_normal_sized_upload_passes(client):
    app.dependency_overrides[get_stt_client] = lambda: _FakeSTTClient()
    try:
        small = io.BytesIO(b"\x00" * 1024)
        r = client.post("/speech/transcribe", files={"audio": ("small.wav", small, "audio/wav")})
        assert r.status_code == 200
        assert r.json()["text"] == "fake"
    finally:
        app.dependency_overrides.pop(get_stt_client, None)


class _CountingHugeFile:
    """Simulates a file-like object that could serve a huge amount of data, tracking how many
    bytes this router's own read loop actually consumed - used to prove the oversized-upload
    rejection stops after about one cap's worth of reads, rather than draining everything."""

    def __init__(self):
        self.total_served = 0

    def read(self, size: int) -> bytes:
        self.total_served += size
        return b"\x00" * size


def test_oversized_upload_rejected_without_reading_the_whole_body():
    # Calls the route function directly (bypassing FastAPI's request/dependency injection
    # entirely - transcribe() is just a plain function) so the fake file's .read() calls can
    # be counted directly, proving the capped-chunk loop in router.py stops early instead of
    # draining an arbitrarily large body into memory.
    fake_audio = SimpleNamespace(file=_CountingHugeFile(), filename="huge.wav")
    fake_request = SimpleNamespace(headers={})  # no Content-Length - forces the chunked-read path

    with pytest.raises(HTTPException) as exc_info:
        transcribe(fake_request, fake_audio, language="en", stt_client=_FakeSTTClient())

    assert exc_info.value.status_code == 413
    # Must stop at or shortly after the cap - not anywhere close to what a real huge file
    # (this fake could serve limitlessly) would otherwise total.
    assert fake_audio.file.total_served <= MAX_UPLOAD_BYTES + _UPLOAD_READ_CHUNK_SIZE
