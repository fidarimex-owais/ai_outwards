from google import genai
from google.genai import types

from app.core.config import settings
from app.features.llm.base import LLMClient


class GeminiLLMClient(LLMClient):
    """Primary LLM provider, per the spec: Google Gemini API (free tier)."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash", timeout_ms: int = 15000):
        # An explicit timeout matters here: without one, a stalled request can hang
        # indefinitely instead of raising, which would silently defeat LLMChain's
        # primary -> backup fallback (it can only fall back on a raised exception).
        self._client = genai.Client(
            api_key=api_key or settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        self._model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        config = types.GenerateContentConfig(system_instruction=system) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return (response.text or "").strip()
