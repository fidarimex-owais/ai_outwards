import httpx

from app.core.config import settings
from app.features.llm.base import LLMClient

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqLLMClient(LLMClient):
    """Backup LLM provider, used only when the primary (Gemini) fails. Groq exposes an
    OpenAI-compatible chat completions API, called directly via httpx to avoid pulling in
    an extra SDK for a single endpoint."""

    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-oss-20b"):
        self._api_key = api_key or settings.backup_llm_api_key
        self._model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
