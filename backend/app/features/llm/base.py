from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interface every LLM provider must implement, so the provider can be swapped
    (Gemini, a backup provider, anything else) without touching any caller.

    Scope is deliberately narrow: given a prompt, return raw text. No JSON parsing,
    no retries, no business logic — that belongs to the caller (e.g. features/extraction)."""

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """Returns the raw text completion for the given prompt."""
        raise NotImplementedError
