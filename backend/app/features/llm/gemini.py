import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.config import settings
from app.features.llm.base import LLMClient

# This logger = quota-diagnosis instrumentation for GeminiLLMClient.generate() only - it
# reads token-usage/timing/error numbers off each call so you can see where Gemini quota is
# actually going, without touching what generate() returns or how LLMChain decides to fall
# back (chain.py's _is_retryable() still sees the exact same exception object, unchanged).
logger = logging.getLogger(__name__)


def _count_or_na(value: int | None) -> str:
    """This helper = safe formatting for an optional token count. usage_metadata, or any
    individual count on it, can be None - this turns that into the literal string "n/a"
    instead of letting a None reach %s and print as the word "None" (or crash elsewhere if
    something later expected an int)."""
    return "n/a" if value is None else str(value)


class GeminiLLMClient(LLMClient):
    """Primary LLM provider, per the spec: Google Gemini API (free tier)."""

    def __init__(
        self, api_key: str | None = None, model: str | None = None,
        timeout_ms: int = 15000, max_output_tokens: int = 4096,
    ):
        # An explicit timeout matters here: without one, a stalled request can hang
        # indefinitely instead of raising, which would silently defeat LLMChain's
        # primary -> backup fallback (it can only fall back on a raised exception).
        self._client = genai.Client(
            api_key=api_key or settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        # This block = model selection for GeminiLLMClient, controlled by GEMINI_MODEL (via
        # settings.gemini_model) so the model id can be switched in .env with no code change.
        # Resolution order: (1) an explicit constructor argument always wins, (2) otherwise
        # settings.gemini_model, (3) the literal "gemini-3.1-flash-lite" if that's empty/
        # whitespace only - the one case worth a warning, since it means GEMINI_MODEL was set
        # to something effectively blank rather than genuinely left at its intended value.
        resolved_model = (model if model is not None else settings.gemini_model) or ""
        resolved_model = resolved_model.strip()
        if not resolved_model:
            logger.warning("GEMINI_MODEL is empty - falling back to gemini-3.1-flash-lite")
            resolved_model = "gemini-3.1-flash-lite"
        self._model = resolved_model
        # Without an explicit cap the SDK/model default can be too low for the batch
        # extraction prompt's response - 16 fields, each with value + display_value + ambiguous,
        # and non-English display values costing more tokens per character - which silently
        # truncates the JSON mid-object instead of erroring. 4096 comfortably covers the
        # largest response this app ever asks for.
        self._max_output_tokens = max_output_tokens

    def generate(self, prompt: str, system: str | None = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self._max_output_tokens,
            # This model "thinks" before answering, and those reasoning tokens are drawn from
            # the same max_output_tokens budget as the visible response - so even a generous
            # cap can still truncate the actual JSON on a harder input, non-deterministically.
            # Every call here is a deterministic structured-extraction task with no need for
            # chain-of-thought, so thinking is switched off entirely: the full budget goes to
            # the response that actually matters.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        # This block = usage logging for quota diagnosis; chain.py's fallback logic is
        # unaffected - the call result/exception is returned/re-raised exactly as before,
        # timing and logging only wrap it, never change it.
        started_at = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except Exception as error:
            elapsed = time.perf_counter() - started_at
            status_code = getattr(error, "code", None) if isinstance(error, genai_errors.APIError) else None
            logger.warning(
                "GEMINI_USAGE call_failed model=%s error_type=%s status_code=%s elapsed_s=%.3f",
                self._model, type(error).__name__, status_code if status_code is not None else "n/a", elapsed,
            )
            raise  # same exception, unchanged - LLMChain's _is_retryable() classifies it as before

        elapsed = time.perf_counter() - started_at
        usage = response.usage_metadata  # may be None - the SDK doesn't guarantee it's set
        if usage is None:
            logger.info(
                "GEMINI_USAGE model=%s prompt_tokens=n/a candidates_tokens=n/a total_tokens=n/a elapsed_s=%.3f "
                "(usage_metadata not returned by SDK)",
                self._model, elapsed,
            )
        else:
            extra = ""
            if usage.thoughts_token_count is not None:
                extra += f" thoughts_tokens={usage.thoughts_token_count}"
            if usage.cached_content_token_count is not None:
                extra += f" cached_tokens={usage.cached_content_token_count}"
            logger.info(
                "GEMINI_USAGE model=%s prompt_tokens=%s candidates_tokens=%s total_tokens=%s elapsed_s=%.3f%s",
                self._model, _count_or_na(usage.prompt_token_count), _count_or_na(usage.candidates_token_count),
                _count_or_na(usage.total_token_count), elapsed, extra,
            )

        return (response.text or "").strip()
