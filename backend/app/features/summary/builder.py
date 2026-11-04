from app.features.i18n.translations import normalize_language, section_title, total_label, ui_text

SECTIONS = [
    ("Company & Vehicle Details", [
        "company_name", "vehicle_number", "container_number", "brand", "line_supervisor_name", "weight",
    ]),
    ("Banana Hand & Cluster Quantities", [
        "four_hand", "five_hand", "six_hand", "eight_hand", "cluster", "total",
    ]),
    ("Additional Information", [
        "labor_name", "driver_name", "cold_storage_name", "cold_storage_supervisor_name",
        "vehicle_in_time", "vehicle_out_time", "unloading_time",
    ]),
]


def _field_label(key: str, language: str) -> str:
    if key == "total":
        return total_label(language)
    # Imported lazily to avoid a circular import (fields.py doesn't need summary/builder.py,
    # but importing at module load time would still couple the two on startup order).
    from app.features.conversation.fields import get_field

    return get_field(key).localized_label(language)


def build_summary(fields: dict, language: str = "en") -> str:
    """Template-only summary builder, no LLM — per spec, the LLM never touches confirmation
    text. `fields` must contain every field key below (display values - already in the
    conversation language) plus `total` (numeric, already computed)."""
    language = normalize_language(language)
    all_keys = [key for _, field_keys in SECTIONS for key in field_keys]
    missing_keys = [key for key in all_keys if key not in fields]
    if missing_keys:
        raise ValueError(f"Missing fields for summary: {', '.join(missing_keys)}")

    lines = [ui_text("confirm_header", language), ""]
    for section_canonical, field_keys in SECTIONS:
        lines.append(f"{section_title(section_canonical, language)}:")
        for key in field_keys:
            value = fields.get(key)
            display = "—" if value in (None, "") else value
            lines.append(f"  {_field_label(key, language)}: {display}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
