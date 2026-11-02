import re
from dataclasses import dataclass

MIN_LENGTH = 1
MAX_LENGTH = 500

# Pure Python rules (MSI level 1) — no LLM call needed to catch these.
_PROMPT_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore (all|any|the)?\s*(previous|prior|above)?\s*instructions",
        r"disregard (all|any|the)?\s*(previous|prior|above)?\s*instructions",
        r"forget (everything|all|your instructions)",
        r"system prompt",
        r"you are now",
        r"act as (a|an)",
        r"new instructions?:",
        r"reveal your (prompt|instructions|rules)",
    ]
]


@dataclass
class GuardResult:
    allowed: bool
    reason: str | None = None  # "empty" | "too_long" | "prompt_injection"


def check_input(text: str) -> GuardResult:
    stripped = text.strip()

    if len(stripped) < MIN_LENGTH:
        return GuardResult(allowed=False, reason="empty")

    if len(stripped) > MAX_LENGTH:
        return GuardResult(allowed=False, reason="too_long")

    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(stripped):
            return GuardResult(allowed=False, reason="prompt_injection")

    return GuardResult(allowed=True)
