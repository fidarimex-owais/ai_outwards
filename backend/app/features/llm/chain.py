import logging

import httpx
from google.genai import errors as genai_errors

from app.core.config import settings
from app.core.exceptions import AllLLMsFailed
from app.features.llm.backup import GroqLLMClient
from app.features.llm.base import LLMClient
from app.features.llm.gemini import GeminiLLMClient

logger = logging.getLogger(__name__)

_VALID_PROVIDERS = {"gemini", "groq"}


def _status_code(error: Exception) -> int | None:
    """Pulls the HTTP-equivalent status code out of either provider's native exception type,
    if it has one. Gemini's SDK (google-genai) raises APIError (code: int); Groq is called
    directly over httpx, which raises HTTPStatusError (response.status_code)."""
    if isinstance(error, genai_errors.APIError):
        return error.code
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code
    return None


def _is_retryable(error: Exception) -> bool:
    """True if this failure is the kind LLMChain should fall back to the other provider for:
    a rate limit (429), a server-side error (5xx), or a timeout. False for any other 4xx - an
    invalid request (400) or an authentication failure (401/403) means the request or
    credentials are themselves broken, which trying a different provider's account won't fix.
    Anything unclassified (network failures, unexpected SDK errors) defaults to retryable,
    matching this chain's original broad fallback behavior for errors it doesn't recognize."""
    code = _status_code(error)
    if code is not None:
        return code == 429 or 500 <= code < 600
    if isinstance(error, httpx.TimeoutException):
        return True
    return True


def _normalized_primary_provider() -> str:
    value = (settings.llm_primary_provider or "").strip().lower()
    if value in _VALID_PROVIDERS:
        return value
    if value:
        logger.warning("Unrecognized LLM_PRIMARY_PROVIDER '%s' - defaulting to 'gemini'.", value)
    return "gemini"


class LLMChain:
    """Tries the primary provider first, falls back to the other provider on a retryable
    failure (rate limit, server error, or timeout). A non-retryable failure (invalid request,
    auth) or a failure of both providers raises AllLLMsFailed, so the caller
    (conversation/service.py) can pause the session and tell the user to retry shortly, per
    the HLD - that contract is the same regardless of which failure path got there."""

    def __init__(
        self, primary: LLMClient, backup: LLMClient, primary_name: str = "primary", backup_name: str = "backup"
    ):
        self._primary = primary
        self._backup = backup
        self._primary_name = primary_name
        self._backup_name = backup_name

    def generate(self, prompt: str, system: str | None = None, session_id: str = "unknown") -> str:
        try:
            result = self._primary.generate(prompt, system)
            logger.info("LLM request served by primary provider (%s) for session %s", self._primary_name, session_id)
            return result
        except Exception as primary_error:
            error_kind = type(primary_error).__name__
            status = _status_code(primary_error)

            if not _is_retryable(primary_error):
                # Deliberately not attempting the backup here: a bad request or bad
                # credentials on this provider won't be fixed by switching accounts, so
                # there's nothing to gain from burning the other provider's quota too.
                logger.warning(
                    "Primary LLM provider (%s) failed with a non-retryable error for session %s "
                    "(%s, status=%s) - not falling back to %s.",
                    self._primary_name, session_id, error_kind, status, self._backup_name,
                )
                raise AllLLMsFailed(
                    session_id,
                    detail=f"primary ({self._primary_name}) failed with a non-retryable error: {error_kind}",
                ) from primary_error

            logger.warning(
                "Primary LLM provider (%s) failed for session %s (%s, status=%s) - falling back to %s.",
                self._primary_name, session_id, error_kind, status, self._backup_name,
            )
            try:
                result = self._backup.generate(prompt, system)
                logger.info(
                    "LLM request served by fallback provider (%s) for session %s", self._backup_name, session_id
                )
                return result
            except Exception as backup_error:
                logger.error(
                    "Both LLM providers failed for session %s (primary %s: %s; backup %s: %s).",
                    session_id, self._primary_name, error_kind, self._backup_name, type(backup_error).__name__,
                )
                raise AllLLMsFailed(
                    session_id,
                    detail=(
                        f"primary ({self._primary_name}) failed ({error_kind}); "
                        f"backup ({self._backup_name}) failed ({type(backup_error).__name__})"
                    ),
                ) from backup_error


_default_chain: LLMChain | None = None


def get_llm_chain() -> LLMChain:
    """FastAPI dependency: a single shared LLMChain instance (both underlying clients are
    cheap to construct - no network call until generate() is actually invoked). Which
    provider is primary vs. fallback is controlled by LLM_PRIMARY_PROVIDER (see
    _normalized_primary_provider); the other provider is always the automatic fallback."""
    global _default_chain
    if _default_chain is None:
        gemini_client = GeminiLLMClient()
        groq_client = GroqLLMClient()
        if _normalized_primary_provider() == "groq":
            _default_chain = LLMChain(primary=groq_client, backup=gemini_client, primary_name="groq", backup_name="gemini")
        else:
            _default_chain = LLMChain(primary=gemini_client, backup=groq_client, primary_name="gemini", backup_name="groq")
    return _default_chain
