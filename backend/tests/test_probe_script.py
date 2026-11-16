import scripts.probe_gemini_models as probe

# No network calls anywhere in this file. dry_run() is the function under test for "makes no
# network call" - GeminiLLMClient is monkeypatched to a stub whose __init__ fails the test if
# it's ever instantiated, which is exactly what would happen if dry_run() tried to call out.


class _ClientMustNotBeCreated:
    def __init__(self, *args, **kwargs):
        raise AssertionError("dry_run() must not construct a GeminiLLMClient (no network call)")


def test_dry_run_makes_no_network_call(monkeypatch, capsys):
    monkeypatch.setattr(probe, "GeminiLLMClient", _ClientMustNotBeCreated)

    probe.dry_run()  # would raise AssertionError above if it tried to construct a client

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    for model_id in probe.CANDIDATE_MODELS:
        assert model_id in out


def test_dry_run_output_contains_no_fake_api_key(monkeypatch, capsys):
    monkeypatch.setattr(probe, "GeminiLLMClient", _ClientMustNotBeCreated)
    monkeypatch.setattr(probe.settings, "gemini_api_key", "fake-secret-key-12345")

    probe.dry_run()

    out = capsys.readouterr().out
    assert "fake-secret-key-12345" not in out
    assert "is set" in out  # presence is reported, the value itself is not


def test_live_run_without_api_key_makes_no_network_call(monkeypatch, capsys):
    monkeypatch.setattr(probe, "GeminiLLMClient", _ClientMustNotBeCreated)
    monkeypatch.setattr(probe.settings, "gemini_api_key", "")

    probe.live_run()  # would raise AssertionError above if it tried to construct a client

    out = capsys.readouterr().out
    assert out.strip() == "GEMINI_API_KEY is not set"
