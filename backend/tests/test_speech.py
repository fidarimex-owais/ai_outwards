from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "test_tone.wav"


def test_unauthenticated_transcribe_rejected(unauthed_client):
    with open(FIXTURE, "rb") as f:
        r = unauthed_client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 401


def test_transcribe_runs_the_real_pipeline(client):
    """Not a fake - exercises the real faster-whisper model (downloaded once, cached).
    The fixture is a pure tone, not speech, so the correct result is empty text / low
    signal, which is itself useful: it proves the endpoint -> service -> provider wiring
    works end to end, and that non-speech audio is handled without error."""
    with open(FIXTURE, "rb") as f:
        r = client.post("/speech/transcribe", files={"audio": ("test.wav", f, "audio/wav")})
    assert r.status_code == 200
    data = r.json()
    assert "text" in data and "confidence" in data and "needs_repeat" in data
    assert data["text"] == ""
    assert data["needs_repeat"] is True  # blank transcription always needs a repeat
