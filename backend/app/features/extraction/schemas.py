from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    TEXT = "text"              # company name, brand, line mark, labor name, remarks, etc.
    NUMBER = "number"           # weight, hand quantities, cluster quantity
    VEHICLE_NUMBER = "vehicle_number"
    TIME = "time"                # vehicle in/out time


@dataclass
class ExtractedField:
    value: str | int | None
    source: str          # "rule" | "llm"
    ambiguous: bool = False
