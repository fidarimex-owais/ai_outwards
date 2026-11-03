import json
import re

from app.features.extraction.prompts import (
    BATCH_EXTRACTION_SYSTEM_PROMPT,
    CORRECTION_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    build_batch_extraction_prompt,
    build_correction_prompt,
    build_extraction_prompt,
)
from app.core.exceptions import ExtractionParseFailed
from app.features.extraction.schemas import ExtractedCorrection, ExtractedField, FieldType
from app.features.llm.chain import LLMChain

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_field(
    field_type: FieldType,
    field_label: str,
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
    language: str = "en",
    is_proper_noun: bool = False,
    allowed_values: list[str] | None = None,
) -> ExtractedField:
    """Extracts one field's value from a spoken/typed answer. Always goes through the LLM -
    understanding what a free-form answer means (in any supported language, in any phrasing)
    is exactly the kind of judgment call Python pattern matching can't make reliably, and
    getting it wrong corrupts the stored data. No keyword/regex shortcut sits in front of
    this."""
    prompt = build_extraction_prompt(field_label, field_type.value, raw_text, language, is_proper_noun, allowed_values)
    raw_response = llm_chain.generate(prompt, system=EXTRACTION_SYSTEM_PROMPT, session_id=session_id)

    parsed = _parse_json_response(raw_response)
    if parsed is None:
        raise ExtractionParseFailed(session_id)

    return ExtractedField(
        value=parsed.get("value"),
        source="llm",
        ambiguous=bool(parsed.get("ambiguous", False)),
        display_value=parsed.get("display_value"),
    )


def extract_batch(
    field_specs: list[tuple[str, str, FieldType, bool, list[str] | None]],
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
    language: str = "en",
) -> dict[str, ExtractedField]:
    """Splits one spoken turn covering several fields into per-field ExtractedFields. Always
    goes through the LLM, same as extract_field() - segmenting free-flowing multi-field speech
    ("company is ABC, plate is MH12AB1234, forty two four-hand...") into the right field
    boundaries and values requires real language understanding, in any supported language.

    field_specs: list of (field_key, label, field_type, is_proper_noun, allowed_values)."""
    prompt = build_batch_extraction_prompt(
        [(k, label, ftype.value, proper, allowed) for k, label, ftype, proper, allowed in field_specs],
        raw_text, language,
    )
    raw_response = llm_chain.generate(prompt, system=BATCH_EXTRACTION_SYSTEM_PROMPT, session_id=session_id)
    parsed = _parse_json_response(raw_response)
    if parsed is None:
        raise ExtractionParseFailed(session_id)

    results: dict[str, ExtractedField] = {}
    for key, _label, _ftype, _proper, _allowed in field_specs:
        entry = parsed.get(key)
        if not isinstance(entry, dict):
            results[key] = ExtractedField(value=None, source="llm", ambiguous=True)
            continue
        results[key] = ExtractedField(
            value=entry.get("value"),
            source="llm",
            ambiguous=bool(entry.get("ambiguous", False)),
            display_value=entry.get("display_value"),
        )
    return results


def extract_correction(
    fields: list[tuple[str, str, FieldType, object, bool, list[str] | None]],
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
    language: str = "en",
) -> ExtractedCorrection:
    """Identifies which single field a free-form spoken correction refers to, and its new
    value - e.g. "Correct the labor name to Sagar Panidrahi" or "change Sagar to Sagar
    Panidrahi" (matching the current value instead of naming the field). Always goes through
    the LLM: picking the right field out of a sentence that names it in the speaker's own
    words, not a machine key, needs real language understanding.

    fields: list of (field_key, label, field_type, current_value, is_proper_noun,
    allowed_values)."""
    prompt = build_correction_prompt(
        [(key, label, ftype.value, current, proper, allowed) for key, label, ftype, current, proper, allowed in fields],
        raw_text,
        language,
    )
    raw_response = llm_chain.generate(prompt, system=CORRECTION_SYSTEM_PROMPT, session_id=session_id)
    parsed = _parse_json_response(raw_response)
    if parsed is None:
        raise ExtractionParseFailed(session_id)

    field_key = parsed.get("field_key")
    valid_keys = {key for key, _label, _ftype, _current, _proper, _allowed in fields}
    if field_key not in valid_keys:
        return ExtractedCorrection(field_key=None, value=None, ambiguous=True)

    return ExtractedCorrection(
        field_key=field_key,
        value=parsed.get("value"),
        ambiguous=bool(parsed.get("ambiguous", False)),
        display_value=parsed.get("display_value"),
    )


def _parse_json_response(raw_response: str) -> dict | None:
    cleaned = _JSON_FENCE_RE.sub("", raw_response).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None
