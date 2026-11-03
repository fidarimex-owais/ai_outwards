from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    TEXT = "text"              # company name, brand, line mark, labor name, remarks, etc.
    NUMBER = "number"           # weight, hand quantities, cluster quantity
    VEHICLE_NUMBER = "vehicle_number"
    TIME = "time"                # vehicle in/out time


@dataclass
class ExtractedField:
    value: str | int | None            # English canonical value - stored, validated
    source: str          # "rule" | "llm"
    ambiguous: bool = False
    # Same value, but in the conversation language (e.g. Devanagari for hi/mr), for echoing
    # back to the user in questions/summaries. Defaults to `value` when there's no difference
    # (numbers, times, vehicle numbers are already language-neutral; English conversations).
    display_value: str | int | None = None

    def __post_init__(self):
        if self.display_value is None:
            self.display_value = self.value


@dataclass
class ExtractedCorrection:
    field_key: str | None  # which field the speaker meant to change, or None if unclear
    value: str | int | None
    ambiguous: bool = False
    display_value: str | int | None = None

    def __post_init__(self):
        if self.display_value is None:
            self.display_value = self.value
