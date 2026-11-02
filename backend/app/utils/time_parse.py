import re

_WORD_HOURS = {
    "twelve": 12, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
}

_PM_RE = re.compile(r"\bp\.?m\.?\b|\bafternoon\b|\bevening\b|\bnight\b")
_AM_RE = re.compile(r"\ba\.?m\.?\b|\bmorning\b")


def _word_or_digit_hour(token: str) -> int | None:
    if token.isdigit():
        hour = int(token)
        return hour if 1 <= hour <= 12 else None
    return _WORD_HOURS.get(token)


def _apply_am_pm(hour: int, minute: int, context: str) -> tuple[int, int]:
    if _PM_RE.search(context) and hour < 12:
        hour += 12
    elif _AM_RE.search(context) and hour == 12:
        hour = 0
    return hour, minute


def parse_time(text: str) -> str | None:
    """Parses common spoken time phrasings into 24-hour 'HH:MM'. Returns None (not a guess)
    for anything it doesn't recognize, so the MSI router escalates to the LLM - this is a
    cost-saving rule layer in front of that escalation, not a replacement for it."""
    stripped = text.strip().lower()

    # digit format: "14:30", "2:30 pm", "9:00am"
    match = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?\b", stripped)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        if match.group(3):
            hour, minute = _apply_am_pm(hour, minute, match.group(3))
        return f"{hour:02d}:{minute:02d}"

    # "9am", "9 pm"
    match = re.search(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b", stripped)
    if match:
        hour = int(match.group(1))
        if not (1 <= hour <= 12):
            return None
        hour, _ = _apply_am_pm(hour, 0, match.group(2))
        return f"{hour:02d}:00"

    # "half past two", "half past two in the afternoon"
    match = re.search(r"\bhalf past (\w+)", stripped)
    if match:
        hour = _word_or_digit_hour(match.group(1))
        if hour is None:
            return None
        hour, minute = _apply_am_pm(hour, 30, stripped)
        return f"{hour:02d}:30"

    # "quarter past two"
    match = re.search(r"\bquarter past (\w+)", stripped)
    if match:
        hour = _word_or_digit_hour(match.group(1))
        if hour is None:
            return None
        hour, minute = _apply_am_pm(hour, 15, stripped)
        return f"{hour:02d}:15"

    # "quarter to five"
    match = re.search(r"\bquarter to (\w+)", stripped)
    if match:
        hour = _word_or_digit_hour(match.group(1))
        if hour is None:
            return None
        hour = (hour - 1) if hour > 1 else 12
        hour, minute = _apply_am_pm(hour, 45, stripped)
        return f"{hour:02d}:45"

    # "nine o'clock", "9 o'clock"
    match = re.search(r"\b(\w+)\s*o.?clock\b", stripped)
    if match:
        hour = _word_or_digit_hour(match.group(1))
        if hour is None:
            return None
        hour, minute = _apply_am_pm(hour, 0, stripped)
        return f"{hour:02d}:00"

    return None
