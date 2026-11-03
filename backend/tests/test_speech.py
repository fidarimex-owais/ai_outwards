from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "test_tone.wav"


def test_unauthenticated_transcribe_rejected(unauthed_client):
    with open(FIXTURE, "rb") as f:
        r = unauthed_client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 401


def test_transcribe_runs_the_real_pipeline(client):
    """Not a fake - exercises the real STT provider (Groq's hosted whisper-large-v3-turbo by
    default) end to end through the endpoint -> service -> provider wiring. The fixture is a
    pure tone, not speech, so content is non-deterministic: cloud Whisper sometimes returns ""
    or stray punctuation, sometimes hallucinates a word pulled from the domain-vocabulary
    prompt. Either way the response shape must be well-formed and the request must not error -
    that's what this test actually checks, not the exact hallucinated content."""
    with open(FIXTURE, "rb") as f:
        r = client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 200
    data = r.json()
    assert "text" in data and "confidence" in data and "needs_repeat" in data
    assert isinstance(data["text"], str)
    assert 0.0 <= data["confidence"] <= 1.0
