"""Diagnostic script, NOT part of the app - probes whether the two Gemini Lite model
candidates (being considered as a replacement for the rate-limited default,
"gemini-3.8-flash") actually work with this app's production call shape (same timeout,
max_output_tokens, thinking_config, and usage logging as GeminiLLMClient.generate()).

Two modes:
  - Dry run (default, no flags): makes NO network call. Only prints what --live would send.
  - --live: makes exactly ONE real request per candidate model (2 total), which consumes
    2 requests of GEMINI_API_KEY's daily free-tier quota. Run it sparingly.

Never prints the API key, the prompt text, the full response text, or .env contents.
"""
import argparse
import logging
import re
import sys
import time
from pathlib import Path

# Makes `app.*` importable when this script is run directly from the backend/ folder
# (python scripts/probe_gemini_models.py) - Python would otherwise only put this script's
# own directory (scripts/) on sys.path, not the backend/ repo root the `app` package lives in.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import errors as genai_errors  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.features.conversation.fields import FIELD_DEFINITIONS  # noqa: E402
from app.features.extraction.prompts import (  # noqa: E402
    BATCH_EXTRACTION_SYSTEM_PROMPT,
    build_batch_extraction_prompt,
)
from app.features.extraction.router_msi import _parse_json_response  # noqa: E402
from app.features.llm.gemini import GeminiLLMClient  # noqa: E402

# This = the two candidate model ids approved for probing, and the fixed dummy transcript -
# no real user data, matching what was approved before this script was written.
CANDIDATE_MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
DUMMY_TRANSCRIPT = (
    "company is Test Traders, vehicle MH12AB1234, brand Test, four hand ten, five hand twenty, "
    "cluster none, labor name Ravi, vehicle in time two thirty PM"
)

# Matches the exact GEMINI_USAGE success line format gemini.py logs, so this script can
# report the same token counts production already emits, instead of re-implementing that
# extraction separately (see _UsageCapture below).
_USAGE_RE = re.compile(r"prompt_tokens=(\S+) candidates_tokens=(\S+) total_tokens=(\S+)")


def _build_field_specs() -> list[tuple[str, str, str, bool, list[str] | None]]:
    """This function = the same (key, label, field_type, proper_noun, allowed_values) shape
    build_batch_extraction_prompt() expects, built from every field currently on the form."""
    return [(f.key, f.label, f.field_type.value, f.proper_noun, f.allowed_values) for f in FIELD_DEFINITIONS]


def _build_prompt() -> str:
    """This function = the one prompt both candidate models are probed with - identical for
    both, so any difference in their behavior is about the model, not the input."""
    return build_batch_extraction_prompt(_build_field_specs(), DUMMY_TRANSCRIPT, "en")


class _UsageCapture(logging.Handler):
    """This class = a temporary log handler that captures the GEMINI_USAGE line
    GeminiLLMClient.generate() already emits for a successful call, so this script reports
    the real production token counts without duplicating that extraction logic itself."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.prompt_tokens = "n/a"
        self.candidates_tokens = "n/a"
        self.total_tokens = "n/a"

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if "GEMINI_USAGE" in message and "call_failed" not in message:
            match = _USAGE_RE.search(message)
            if match:
                self.prompt_tokens, self.candidates_tokens, self.total_tokens = match.groups()


def _probe_one_model(model_id: str, prompt: str) -> None:
    """This function = one real, single-attempt probe call for one candidate model, through
    the real GeminiLLMClient (same timeout/max_output_tokens/thinking_config/usage-logging as
    production - only the model id differs), then reports exactly the items approved: id,
    success/failure, error type/status, elapsed time, token counts, JSON-parseability (via
    the same _parse_json_response() production uses), and how many field keys came back
    non-null. Never prints the prompt text or the response text."""
    client = GeminiLLMClient(model=model_id)
    gemini_logger = logging.getLogger("app.features.llm.gemini")
    capture = _UsageCapture()
    gemini_logger.addHandler(capture)

    started_at = time.perf_counter()
    try:
        raw_response = client.generate(prompt, system=BATCH_EXTRACTION_SYSTEM_PROMPT)
    except Exception as error:
        elapsed = time.perf_counter() - started_at
        status_code = getattr(error, "code", None) if isinstance(error, genai_errors.APIError) else None
        print(
            f"model={model_id} result=FAILURE error_type={type(error).__name__} "
            f"status_code={status_code if status_code is not None else 'n/a'} elapsed_s={elapsed:.3f} "
            f"prompt_tokens=n/a candidates_tokens=n/a total_tokens=n/a "
            f"parses_as_json=n/a fields_non_null=n/a key_missing=n/a"
        )
        return
    finally:
        gemini_logger.removeHandler(capture)

    elapsed = time.perf_counter() - started_at
    parsed = _parse_json_response(raw_response)  # the exact function production uses to parse this
    parses_as_json = parsed is not None

    if parsed is None:
        fields_non_null = "n/a"
        key_missing = "n/a"
    else:
        total_fields = len(FIELD_DEFINITIONS)
        non_null = sum(
            1 for f in FIELD_DEFINITIONS
            if isinstance(parsed.get(f.key), dict) and parsed[f.key].get("value") is not None
        )
        fields_non_null = f"{non_null}/{total_fields}"
        key_missing = str(any(f.key not in parsed for f in FIELD_DEFINITIONS))

    print(
        f"model={model_id} result=SUCCESS error_type=n/a status_code=n/a elapsed_s={elapsed:.3f} "
        f"prompt_tokens={capture.prompt_tokens} candidates_tokens={capture.candidates_tokens} "
        f"total_tokens={capture.total_tokens} parses_as_json={parses_as_json} "
        f"fields_non_null={fields_non_null} key_missing={key_missing}"
    )


def dry_run() -> None:
    """This function = the default, network-free mode. Prints what --live would send,
    without constructing any Gemini client or making any call."""
    prompt = _build_prompt()
    num_fields = len(FIELD_DEFINITIONS)
    print("DRY RUN - no network calls made.")
    print(f"GEMINI_API_KEY is {'set' if settings.gemini_api_key else 'NOT set'} (value never printed).")
    print()
    for model_id in CANDIDATE_MODELS:
        print(
            f"model={model_id} resolved_model={model_id} prompt_chars={len(prompt)} "
            f"fields={num_fields} thinking_config=ThinkingConfig(thinking_budget=0)"
        )


def live_run() -> None:
    """This function = the real-call mode (--live only). Exactly one call per candidate
    model, in order, no retries, no loops - 2 total requests against daily quota."""
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set")
        return

    prompt = _build_prompt()
    for model_id in CANDIDATE_MODELS:
        _probe_one_model(model_id, prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe candidate Gemini Lite models (diagnostic only).")
    parser.add_argument(
        "--live", action="store_true",
        help="Make real API calls (consumes 2 requests of daily quota). Default is a dry run with no network calls.",
    )
    args = parser.parse_args()
    live_run() if args.live else dry_run()


if __name__ == "__main__":
    main()
