from google import genai
from google.genai import types

from app.core.config import settings
from app.features.llm.base import LLMClient


class GeminiLLMClient(LLMClient):
    """Primary LLM provider, per the spec: Google Gemini API (free tier)."""

    def __init__(
        self, api_key: str | None = None, model: str = "gemini-3.8-flash",
        timeout_ms: int = 15000, max_output_tokens: int = 4096,
    ):
        # An explicit timeout matters here: without one, a stalled request can hang
        # indefinitely instead of raising, which would silently defeat LLMChain's
        # primary -> backup fallback (it can only fall back on a raised exception).
        self._client = genai.Client(
            api_key=api_key or settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        self._model = model
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
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return (response.text or "").strip()
