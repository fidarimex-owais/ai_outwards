import httpx

from app.core.config import settings
from app.features.llm.base import LLMClient

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLMClient(LLMClient):
    """Backup LLM provider, used only when the primary (Gemini) fails. Groq exposes an
    OpenAI-compatible chat completions API, called directly via httpx to avoid pulling in
    an extra SDK for a single endpoint."""

    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-oss-20b", max_tokens: int = 4096):
        self._api_key = api_key or settings.backup_llm_api_key
        self._model = model
        # Same reasoning as GeminiLLMClient's max_output_tokens: without an explicit cap, a
        # provider default can be too low for the 16-field batch extraction response and
        # silently truncate the JSON mid-object.
        self._max_tokens = max_tokens

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages, "max_tokens": self._max_tokens},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
