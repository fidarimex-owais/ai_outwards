import logging

from app.core.exceptions import AllLLMsFailed
from app.features.llm.backup import GroqLLMClient
from app.features.llm.base import LLMClient
from app.features.llm.gemini import GeminiLLMClient

logger = logging.getLogger(__name__)


class LLMChain:
    """Tries the primary provider first, falls back to backup on failure. If both fail,
    raises AllLLMsFailed so the caller (conversation/service.py) can pause the session and
    tell the user to retry shortly, per the HLD."""

    def __init__(self, primary: LLMClient, backup: LLMClient):
        self._primary = primary
        self._backup = backup

    def generate(self, prompt: str, system: str | None = None, session_id: str = "unknown") -> str:
        try:
            return self._primary.generate(prompt, system)
        except Exception as primary_error:
            # Logged, not swallowed silently: a misconfigured/renamed primary model would
            # otherwise degrade to the backup permanently with zero visibility that anything
            # was wrong. The primary -> backup fallback behavior itself is unchanged.
            logger.warning("Primary LLM provider failed for session %s: %s", session_id, primary_error)
            try:
                return self._backup.generate(prompt, system)
            except Exception as backup_error:
                raise AllLLMsFailed(
                    session_id,
                    detail=f"primary failed ({primary_error}); backup failed ({backup_error})",
                ) from backup_error


_default_chain: LLMChain | None = None


def get_llm_chain() -> LLMChain:
    """FastAPI dependency: a single shared LLMChain instance (both underlying clients are
    cheap to construct - no network call until generate() is actually invoked)."""
    global _default_chain
    if _default_chain is None:
        _default_chain = LLMChain(primary=GeminiLLMClient(), backup=GroqLLMClient())
    return _default_chain
