import re
from dataclasses import dataclass

MIN_LENGTH = 1
# Covers an 18-field answer in verbose English (measured: 555 chars for a real test
# submission) plus headroom, times an assumed 1.3-1.5x margin for Devanagari script
# (Hindi/Marathi), since a single rendered character there is often a base consonant plus
# one or more combining vowel-sign codepoints, each counted separately by len(). That
# multiplier is NOT measured against this app's own Hindi/Marathi usage - re-derive this
# number once a real multi-field Devanagari submission has been captured and measured.
MAX_LENGTH = 1500

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
