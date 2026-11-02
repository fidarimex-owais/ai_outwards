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
from app.features.extraction.rules import extract_number, extract_text, extract_time, extract_vehicle_number
from app.features.extraction.schemas import ExtractedCorrection, ExtractedField, FieldType
from app.features.llm.chain import LLMChain

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_field(
    field_type: FieldType,
    field_label: str,
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
) -> ExtractedField:
    """MSI entry point for extraction: tries a Python rule first (free, instant), only calls
    the LLM chain when the rule can't confidently handle the field."""
    rule_value = _try_rule(field_type, raw_text)
    if rule_value is not None:
        return ExtractedField(value=rule_value, source="rule")

    return _extract_with_llm(field_type, field_label, raw_text, llm_chain, session_id)


def _try_rule(field_type: FieldType, raw_text: str):
    if field_type == FieldType.TEXT:
        return extract_text(raw_text)
    if field_type == FieldType.NUMBER:
        return extract_number(raw_text)
    if field_type == FieldType.VEHICLE_NUMBER:
        return extract_vehicle_number(raw_text)
    if field_type == FieldType.TIME:
        return extract_time(raw_text)
    return None


def _extract_with_llm(
    field_type: FieldType, field_label: str, raw_text: str, llm_chain: LLMChain, session_id: str
) -> ExtractedField:
    prompt = build_extraction_prompt(field_label, field_type.value, raw_text)
    raw_response = llm_chain.generate(prompt, system=EXTRACTION_SYSTEM_PROMPT, session_id=session_id)

    parsed = _parse_json_response(raw_response)
    if parsed is None:
        return ExtractedField(value=None, source="llm", ambiguous=True)

    return ExtractedField(
        value=parsed.get("value"),
        source="llm",
        ambiguous=bool(parsed.get("ambiguous", False)),
    )


def extract_batch(
    field_specs: list[tuple[str, str, FieldType]],
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
) -> dict[str, ExtractedField]:
    """Splits one spoken turn covering several fields into per-field ExtractedFields. Unlike
    extract_field(), this always goes through the LLM - segmenting free-flowing multi-field
    speech ("company is ABC, plate is MH12AB1234, forty two four-hand...") into the right
    field boundaries requires real language understanding, which Python regex rules can't
    reliably do. This is still the correct MSI tier for this access pattern, not a violation
    of it: MSI means "cheapest method that actually works," and for this shape of input that
    method is the LLM."""
    prompt = build_batch_extraction_prompt([(k, label, ftype.value) for k, label, ftype in field_specs], raw_text)
    raw_response = llm_chain.generate(prompt, system=BATCH_EXTRACTION_SYSTEM_PROMPT, session_id=session_id)
    parsed = _parse_json_response(raw_response)

    results: dict[str, ExtractedField] = {}
    for key, _label, _ftype in field_specs:
        entry = parsed.get(key) if parsed else None
        if not isinstance(entry, dict):
            results[key] = ExtractedField(value=None, source="llm", ambiguous=True)
            continue
        results[key] = ExtractedField(
            value=entry.get("value"),
            source="llm",
            ambiguous=bool(entry.get("ambiguous", False)),
        )
    return results


def extract_correction(
    fields: list[tuple[str, str, FieldType, object]],
    raw_text: str,
    llm_chain: LLMChain,
    session_id: str,
) -> ExtractedCorrection:
    """Identifies which single field a free-form spoken correction refers to, and its new
    value - e.g. "Correct the labor name to Sagar Panidrahi" or "change Sagar to Sagar
    Panidrahi" (matching the current value instead of naming the field). Always goes through
    the LLM: picking the right field out of a sentence that names it in the speaker's own
    words, not a machine key, needs real language understanding."""
    prompt = build_correction_prompt(
        [(key, label, ftype.value, current) for key, label, ftype, current in fields], raw_text
    )
    raw_response = llm_chain.generate(prompt, system=CORRECTION_SYSTEM_PROMPT, session_id=session_id)
    parsed = _parse_json_response(raw_response)
    if parsed is None:
        return ExtractedCorrection(field_key=None, value=None, ambiguous=True)

    field_key = parsed.get("field_key")
    valid_keys = {key for key, _label, _ftype, _current in fields}
    if field_key not in valid_keys:
        return ExtractedCorrection(field_key=None, value=None, ambiguous=True)

    return ExtractedCorrection(
        field_key=field_key, value=parsed.get("value"), ambiguous=bool(parsed.get("ambiguous", False))
    )


def _parse_json_response(raw_response: str) -> dict | None:
    cleaned = _JSON_FENCE_RE.sub("", raw_response).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None
