EXTRACTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a warehouse voice data collection form. "
    "You only extract the single field asked about. You never invent values. "
    "You always respond with JSON only, no other text, no markdown code fences."
)

CORRECTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a warehouse voice data collection form. "
    "The user has already filled in a form and is now speaking a correction to exactly one "
    "field - identifying it by name or by its current (wrong) value, in their own words, not "
    "by a machine key. You figure out which single field they mean and what its new value "
    "should be. You never invent values. You always respond with JSON only, no other text, "
    "no markdown code fences."
)

BATCH_EXTRACTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a warehouse voice data collection form. "
    "The user answers several questions in one continuous spoken turn, in any order, "
    "possibly skipping some. You split that single transcript into the individual fields "
    "listed. You never invent values, and you never carry a value over to a field it "
    "wasn't actually said for. You always respond with JSON only, no other text, no "
    "markdown code fences."
)


def build_extraction_prompt(field_label: str, field_type: str, raw_text: str) -> str:
    return (
        f'Field: "{field_label}" (type: {field_type})\n'
        f'Spoken answer (transcribed, may contain errors): "{raw_text}"\n\n'
        "Extract the value for this field from the spoken answer.\n"
        "- If type is 'time', normalize to 24-hour HH:MM format.\n"
        "- If type is 'number', return a plain number (no units, no words).\n"
        "- If type is 'vehicle_number', return it with no spaces, uppercase.\n"
        "- If type is 'number' and the speaker says there isn't one (e.g. 'none', 'zero', "
        "'no', 'nil'), return 0 - that is a deliberate quantity, not a missing answer.\n"
        "- If the answer is unclear, missing, or doesn't match the field, set value to null "
        "and ambiguous to true.\n\n"
        'Respond with JSON only: {"value": <extracted value or null>, "ambiguous": <true|false>}'
    )


def build_correction_prompt(fields: list[tuple[str, str, str, object]], raw_text: str) -> str:
    """fields: list of (field_key, label, field_type, current_value) for every field on the
    form, so the model can match a spoken reference like "the labor name" or even "change
    Sagar to Sagar Panidrahi" (matching the current value, not the label) to the right key."""
    field_lines = "\n".join(
        f'- "{key}" - "{label}" (type: {ftype}, current value: {current!r})'
        for key, label, ftype, current in fields
    )
    return (
        "Fields currently on the form:\n"
        f"{field_lines}\n\n"
        f'Spoken correction (transcribed, may contain errors): "{raw_text}"\n\n'
        "Identify which ONE field the speaker wants to change, and its new value.\n"
        "- Match by the field's label, by its current value, or by context - whichever the "
        "speaker is clearly referring to.\n"
        "- The new value is what they want it changed TO, never the current/old value.\n"
        "- If type is 'time', normalize to 24-hour HH:MM format.\n"
        "- If type is 'number', return a plain number (no units, no words).\n"
        "- If type is 'vehicle_number', return it with no spaces, uppercase.\n"
        "- If you cannot confidently identify which field is meant, or the new value, set "
        "field_key to null and ambiguous to true.\n\n"
        'Respond with JSON only: {"field_key": <key or null>, "value": <new value or null>, '
        '"ambiguous": <true|false>}'
    )


def build_batch_extraction_prompt(field_specs: list[tuple[str, str, str]], raw_text: str) -> str:
    """field_specs: list of (field_key, label, field_type) for every field in the batch."""
    field_lines = "\n".join(
        f'- "{key}" - "{label}" (type: {ftype})' for key, label, ftype in field_specs
    )
    return (
        "Fields to extract from this one spoken turn:\n"
        f"{field_lines}\n\n"
        f'Spoken answer (transcribed, may contain errors): "{raw_text}"\n\n'
        "For EVERY field key listed above, extract its value from the transcript.\n"
        "- If type is 'time', normalize to 24-hour HH:MM format.\n"
        "- If type is 'number', return a plain number (no units, no words).\n"
        "- If type is 'vehicle_number', return it with no spaces, uppercase.\n"
        "- If type is 'number' and the speaker says there isn't one for that field (e.g. "
        "'cluster is none', 'zero', 'no eight-hand'), return 0 for that field - that is a "
        "deliberate quantity, not a missing answer, so ambiguous stays false.\n"
        "- If a field was not mentioned at all, or is unclear, set its value to null and "
        "ambiguous to true for that field.\n"
        "- If the speaker explicitly declines an optional TEXT field (e.g. says 'no "
        "remarks', 'none', 'nothing'), set its value to an empty string \"\", not the "
        "literal words said - that is a deliberate blank, not a missing answer, so "
        "ambiguous stays false.\n"
        "- Do not guess a value for a field that wasn't actually spoken.\n\n"
        "Respond with JSON only, one entry per field key:\n"
        '{"<field_key>": {"value": <value or null>, "ambiguous": <true|false>}, ...}'
    )
