import re

from app.utils.time_parse import parse_time

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_IGNORE_WORDS = {"and"}
# "Cluster quantity: none" means 0, not "I didn't say a number" - a declined/absent quantity
# is a valid answer for a NUMBER field, not an unclear one.
_ZERO_PHRASES = re.compile(r"^(none|no|nil|nothing)\.?$", re.IGNORECASE)


def _words_to_number(text: str) -> int | None:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    if not tokens:
        return None

    total = 0
    current = 0
    found_any = False

    for tok in tokens:
        if tok in _IGNORE_WORDS:
            continue
        if tok in _UNITS:
            current += _UNITS[tok]
            found_any = True
        elif tok in _TENS:
            current += _TENS[tok]
            found_any = True
        elif tok == "hundred":
            current = (current or 1) * 100
            found_any = True
        elif tok == "thousand":
            total += (current or 1) * 1000
            current = 0
            found_any = True
        else:
            return None  # unrecognized word - don't guess, let MSI escalate to the LLM

    total += current
    return total if found_any else None


def extract_number(text: str) -> int | float | None:
    """Tries digits first (handles '42', '42.5'), falls back to spoken number words
    ('forty two'). Returns None if neither matches, so the MSI router escalates to the LLM."""
    stripped = text.strip()

    match = re.search(r"-?\d+(\.\d+)?", stripped)
    if match:
        num_str = match.group()
        return float(num_str) if "." in num_str else int(num_str)

    if _ZERO_PHRASES.match(stripped):
        return 0

    return _words_to_number(stripped)


def extract_vehicle_number(text: str) -> str | None:
    """Matches the common Indian vehicle plate pattern: 2 letters, 1-2 digits, 1-2 letters,
    4 digits (e.g. 'MH12AB1234'), tolerant of spaces/dashes between groups."""
    match = re.search(
        r"\b([A-Za-z]{2})\s*-?\s*(\d{1,2})\s*-?\s*([A-Za-z]{1,2})\s*-?\s*(\d{4})\b",
        text,
    )
    if not match:
        return None
    return "".join(match.groups()).upper()


def extract_time(text: str) -> str | None:
    """Thin wrapper around utils.time_parse so extraction's rule dispatch stays uniform
    with the other extract_*() functions."""
    return parse_time(text)


def extract_text(text: str) -> str | None:
    """Free-text fields (company name, brand, labor name, remarks, ...) need no real
    extraction, just cleanup. Returns None only for blank input, so the MSI router escalates
    rather than storing an empty string."""
    stripped = text.strip()
    return stripped if stripped else None
