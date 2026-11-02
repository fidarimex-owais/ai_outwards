from dataclasses import dataclass

from app.features.extraction.schemas import FieldType


@dataclass
class FieldDefinition:
    key: str
    label: str
    field_type: FieldType
    question: str
    section: str  # display-only grouping; does NOT affect recording/submission flow
    batch: int = 1  # all fields are answered in a single recording (see note below)
    required: bool = True


# Field keys match app/features/summary/builder.py's SECTIONS exactly - both modules must
# agree on these names since a session's `answers` dict is built here and read there.
#
# Every field has batch=1: the whole 16-field form is shown and recorded in one go, not
# split into separate recording rounds. `section` groups the questions when they're
# displayed/read back, mirroring summary/builder.py's three sections - it has no effect on
# how answers are collected or submitted. `batch` and `get_batch()` are kept (rather than
# removed) because submit_batch_answer() and _advance() key off of them - making everything
# batch=1 is the minimal way to get "answer everything in one recording" without a second
# code path for it.
_SECTION_VEHICLE = "Company & Vehicle Details"
_SECTION_QUANTITIES = "Banana Hand & Cluster Quantities"
_SECTION_ADDITIONAL = "Additional Information"

FIELD_DEFINITIONS: list[FieldDefinition] = [
    FieldDefinition("company_name", "Company Name", FieldType.TEXT, "What is the company name?", _SECTION_VEHICLE),
    FieldDefinition("vehicle_number", "Vehicle Number", FieldType.VEHICLE_NUMBER, "What is the vehicle number?", _SECTION_VEHICLE),
    FieldDefinition("brand", "Brand", FieldType.TEXT, "What is the brand?", _SECTION_VEHICLE),
    FieldDefinition("line_mark", "Line Mark", FieldType.TEXT, "What is the line mark?", _SECTION_VEHICLE),
    FieldDefinition("weight", "Weight", FieldType.NUMBER, "What is the weight, in kilograms?", _SECTION_VEHICLE),

    FieldDefinition("four_hand", "Four-Hand Quantity", FieldType.NUMBER, "What is the four-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("five_hand", "Five-Hand Quantity", FieldType.NUMBER, "What is the five-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("six_hand", "Six-Hand Quantity", FieldType.NUMBER, "What is the six-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("eight_hand", "Eight-Hand Quantity", FieldType.NUMBER, "What is the eight-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("cluster", "Cluster Quantity", FieldType.NUMBER, "What is the cluster quantity?", _SECTION_QUANTITIES),

    FieldDefinition("remarks", "Remarks", FieldType.TEXT, "Any remarks? You can say none.", _SECTION_ADDITIONAL, required=False),
    FieldDefinition("labor_name", "Labor Name", FieldType.TEXT, "What is the labor name?", _SECTION_ADDITIONAL),
    FieldDefinition("vehicle_out_time", "Vehicle Out Time", FieldType.TIME, "What is the vehicle out time?", _SECTION_ADDITIONAL),
    FieldDefinition("vehicle_in_time", "Vehicle In Time", FieldType.TIME, "What is the vehicle in time?", _SECTION_ADDITIONAL),
    FieldDefinition("vehicle_for_storage", "Vehicle for Storage", FieldType.TEXT, "Is the vehicle for storage?", _SECTION_ADDITIONAL),
    FieldDefinition("vehicle_receiver_name", "Vehicle Receiver Name", FieldType.TEXT, "Who is the vehicle receiver?", _SECTION_ADDITIONAL),
]

TOTAL_BATCHES = max(f.batch for f in FIELD_DEFINITIONS)

_BY_KEY = {f.key: f for f in FIELD_DEFINITIONS}


def get_field(key: str) -> FieldDefinition:
    return _BY_KEY[key]


def get_batch(batch_number: int) -> list[FieldDefinition]:
    return [f for f in FIELD_DEFINITIONS if f.batch == batch_number]


def all_field_keys() -> list[str]:
    return [f.key for f in FIELD_DEFINITIONS]
