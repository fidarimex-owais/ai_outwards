from dataclasses import dataclass

from app.core.exceptions import UnknownField
from app.features.extraction.schemas import FieldType
from app.features.i18n.translations import field_label, field_question


@dataclass
class FieldDefinition:
    key: str
    label: str  # canonical English label - used in LLM prompts, never shown to the user directly
    field_type: FieldType
    question: str  # canonical English question - same
    section: str  # display-only grouping; does NOT affect recording/submission flow
    batch: int = 1  # all fields are answered in a single recording (see note below)
    required: bool = True
    # True for fields holding a person/company/place name: the value must be transliterated
    # (sound preserved) rather than translated (meaning preserved) when normalizing non-English
    # speech to English for storage. False means translate the meaning instead (no current
    # field uses False, but the distinction is still enforced in extraction/prompts.py for any
    # future non-proper-noun TEXT field).
    proper_noun: bool = False
    # When set, this field is a closed set rather than open free text: the spoken answer must
    # be fuzzy/phonetically matched to one of these exact predefined values (handling STT
    # spelling slips and mispronunciation), never accepted as arbitrary text. None means open
    # free text, as before.
    allowed_values: list[str] | None = None

    def localized_label(self, language: str) -> str:
        return field_label(self.key, language)

    def localized_question(self, language: str) -> str:
        return field_question(self.key, language)


# Field keys match app/features/summary/builder.py's SECTIONS exactly - both modules must
# agree on these names since a session's `answers` dict is built here and read there.
#
# Every field has batch=1: the whole form is shown and recorded in one go, not
# split into separate recording rounds. `section` groups the questions when they're
# displayed/read back, mirroring summary/builder.py's three sections - it has no effect on
# how answers are collected or submitted. `batch` and `get_batch()` are kept (rather than
# removed) because submit_batch_answer() and _advance() key off of them - making everything
# batch=1 is the minimal way to get "answer everything in one recording" without a second
# code path for it.
_SECTION_VEHICLE = "Company & Vehicle Details"
_SECTION_QUANTITIES = "Banana Hand & Cluster Quantities"
_SECTION_ADDITIONAL = "Additional Information"

# Closed sets: this operation only deals with these known companies/brands, so these two
# fields are fuzzy-matched against a fixed list rather than accepted as open free text (see
# FieldDefinition.allowed_values and extraction/prompts.py's closed-set instruction).
_COMPANY_NAMES = ["Khorale Global", "Rajmata", "Jaywant"]
_BRAND_NAMES = ["Joker Banana", "Banana Man", "Hi Banana"]

FIELD_DEFINITIONS: list[FieldDefinition] = [
    FieldDefinition("company_name", "Company Name", FieldType.TEXT, "What is the company name?", _SECTION_VEHICLE, proper_noun=True, allowed_values=_COMPANY_NAMES),
    FieldDefinition("vehicle_number", "Vehicle Number", FieldType.VEHICLE_NUMBER, "What is the vehicle number?", _SECTION_VEHICLE),
    FieldDefinition("container_number", "Container Number", FieldType.TEXT, "What is the container number?", _SECTION_VEHICLE, proper_noun=True),
    FieldDefinition("brand", "Brand", FieldType.TEXT, "What is the brand?", _SECTION_VEHICLE, proper_noun=True, allowed_values=_BRAND_NAMES),
    FieldDefinition("line_supervisor_name", "Line Supervisor Name", FieldType.TEXT, "What is the line supervisor's name?", _SECTION_VEHICLE, proper_noun=True),
    FieldDefinition("weight", "Weight", FieldType.NUMBER, "What is the weight, in kilograms?", _SECTION_VEHICLE),

    FieldDefinition("four_hand", "Four-Hand Quantity", FieldType.NUMBER, "What is the four-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("five_hand", "Five-Hand Quantity", FieldType.NUMBER, "What is the five-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("six_hand", "Six-Hand Quantity", FieldType.NUMBER, "What is the six-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("eight_hand", "Eight-Hand Quantity", FieldType.NUMBER, "What is the eight-hand quantity?", _SECTION_QUANTITIES),
    FieldDefinition("cluster", "Cluster Quantity", FieldType.NUMBER, "What is the cluster quantity?", _SECTION_QUANTITIES),

    FieldDefinition("labor_name", "Labor Name", FieldType.TEXT, "What is the labor name?", _SECTION_ADDITIONAL, proper_noun=True),
    FieldDefinition("driver_name", "Driver Name", FieldType.TEXT, "What is the driver's name?", _SECTION_ADDITIONAL, proper_noun=True),
    FieldDefinition("cold_storage_name", "Cold Storage Name", FieldType.TEXT, "What is the cold storage name?", _SECTION_ADDITIONAL, proper_noun=True),
    FieldDefinition("cold_storage_supervisor_name", "Cold Storage Supervisor Name", FieldType.TEXT, "What is the cold storage supervisor's name?", _SECTION_ADDITIONAL, proper_noun=True),
    # Order matters here, per spec: Vehicle In Time, then Vehicle Out Time, then Unloading
    # Time - this list's order is also the order fields are asked/displayed in.
    FieldDefinition("vehicle_in_time", "Vehicle In Time", FieldType.TIME, "What is the vehicle in time? Please specify AM or PM.", _SECTION_ADDITIONAL),
    FieldDefinition("vehicle_out_time", "Vehicle Out Time", FieldType.TIME, "What is the vehicle out time? Please specify AM or PM.", _SECTION_ADDITIONAL),
    FieldDefinition("unloading_time", "Unloading Time", FieldType.TIME, "What is the unloading time? Please specify AM or PM.", _SECTION_ADDITIONAL),
]

TOTAL_BATCHES = max(f.batch for f in FIELD_DEFINITIONS)

_BY_KEY = {f.key: f for f in FIELD_DEFINITIONS}


def get_field(key: str) -> FieldDefinition:
    try:
        return _BY_KEY[key]
    except KeyError:
        raise UnknownField(key) from None


def get_batch(batch_number: int) -> list[FieldDefinition]:
    return [f for f in FIELD_DEFINITIONS if f.batch == batch_number]


def all_field_keys() -> list[str]:
    return [f.key for f in FIELD_DEFINITIONS]
