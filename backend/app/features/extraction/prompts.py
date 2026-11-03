from app.features.i18n.translations import LANGUAGE_NAMES, normalize_language

_NORMALIZATION_RULES = (
    "- The spoken answer may be in English, Hindi, Marathi, or a mix of these "
    "(code-switching). Regardless of the language spoken, `value` must always be normalized "
    "to English for database storage:\n"
    "  - If type is 'time', normalize to 24-hour HH:MM format.\n"
    "  - If type is 'number', return a plain number (no units, no words), in Arabic digits.\n"
    "  - If type is 'vehicle_number', return it with no spaces, uppercase, Latin letters/digits. "
    "Indian plates have 4 groups - 2 letters, 1-2 digits, 1-2 letters, 4 digits (e.g. "
    "MH12AB1234) - and speakers often read them back in separate chunks joined by a word like "
    "'and', or even as two separate sentences (e.g. 'MH01 and EL6125', or 'MH01... EL6125'). "
    "That is still one complete, unambiguous plate number: concatenate the chunks in the order "
    "given, drop the connecting word, and output it as a single token. Only treat a "
    "vehicle_number answer as ambiguous if the letters/digits themselves don't fit the format "
    "once joined, or genuinely weren't said at all - not because a word like 'and' appeared "
    "between the chunks.\n"
    "  - If a field lists '[one of: ...]', it only accepts one of those exact predefined "
    "values - never arbitrary text, even if type is 'text'. The spoken answer may contain "
    "pronunciation errors or transcription mistakes (e.g. 'Khorale' heard as 'Corale' or "
    "'Coral', 'Banana Man' heard as 'Banana Men'); use fuzzy/phonetic matching to work out "
    "which predefined option was actually meant, and return that option's exact text as "
    "`value` - not the literal (possibly misspelled/mistranscribed) words said. If more than "
    "one option is similarly plausible, or none resemble the spoken answer closely enough to "
    "be confident, set value to null and ambiguous to true for that field - do not guess "
    "between options.\n"
    "  - If type is 'text', is a proper noun field (a person's or company's name), and has no "
    "'[one of: ...]' list, transliterate it into English/Latin script phonetically (preserve "
    "how it sounds - do NOT translate its meaning, a name is not a word to translate).\n"
    "  - If type is 'text' and this is NOT a proper noun field (e.g. remarks, yes/no answers), "
    "translate its meaning into natural English.\n"
    "- `display_value` is the same answer, but written naturally in the conversation language "
    "given above (for 'text' fields this is usually just the original spoken phrase, cleaned "
    "up - or, for a '[one of: ...]' field, the matched predefined option written in that "
    "language; for 'number'/'time'/'vehicle_number' it is identical to `value`, since digits "
    "and plate numbers don't change across languages).\n"
)

EXTRACTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a multilingual (English/Hindi/Marathi) "
    "warehouse voice data collection form. You only extract the single field asked about. "
    "You never invent values. You always respond with JSON only, no other text, no markdown "
    "code fences."
)

CORRECTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a multilingual (English/Hindi/Marathi) "
    "warehouse voice data collection form. The user has already filled in a form and is now "
    "speaking a correction to exactly one field - identifying it by name or by its current "
    "(wrong) value, in their own words, not by a machine key. You figure out which single "
    "field they mean and what its new value should be. You never invent values. You always "
    "respond with JSON only, no other text, no markdown code fences."
)

BATCH_EXTRACTION_SYSTEM_PROMPT = (
    "You are a strict information extractor for a multilingual (English/Hindi/Marathi) "
    "warehouse voice data collection form. The user answers several questions in one "
    "continuous spoken turn, in any order, possibly skipping some, and possibly mixing "
    "languages mid-sentence. You split that single transcript into the individual fields "
    "listed. You never invent values, and you never carry a value over to a field it wasn't "
    "actually said for. You always respond with JSON only, no other text, no markdown code "
    "fences."
)


def _closed_set_note(allowed_values: list[str] | None) -> str:
    if not allowed_values:
        return ""
    options = ", ".join(f'"{v}"' for v in allowed_values)
    return f" [one of: {options}]"


def build_extraction_prompt(
    field_label: str,
    field_type: str,
    raw_text: str,
    language: str = "en",
    is_proper_noun: bool = False,
    allowed_values: list[str] | None = None,
) -> str:
    lang_name = LANGUAGE_NAMES[normalize_language(language)]
    return (
        f'Field: "{field_label}" (type: {field_type}, proper noun: {is_proper_noun})'
        f"{_closed_set_note(allowed_values)}\n"
        f"Conversation language: {lang_name}\n"
        f'Spoken answer (transcribed, may contain errors): "{raw_text}"\n\n'
        "Extract the value for this field from the spoken answer.\n"
        f"{_NORMALIZATION_RULES}"
        "- If type is 'number' and the speaker says there isn't one (e.g. 'none', 'zero', "
        "'no', 'nil', or the equivalent in Hindi/Marathi), return 0 - that is a deliberate "
        "quantity, not a missing answer.\n"
        "- If the answer is unclear, missing, or doesn't match the field, set value to null "
        "and ambiguous to true.\n\n"
        'Respond with JSON only: {"value": <extracted value or null>, "display_value": '
        '<same answer in the conversation language, or null>, "ambiguous": <true|false>}'
    )


def build_correction_prompt(
    fields: list[tuple[str, str, str, object, bool, list[str] | None]], raw_text: str, language: str = "en"
) -> str:
    """fields: list of (field_key, label, field_type, current_value, is_proper_noun,
    allowed_values) for every field on the form, so the model can match a spoken reference
    like "the labor name" or even "change Sagar to Sagar Panidrahi" (matching the current
    value, not the label) to the right key."""
    lang_name = LANGUAGE_NAMES[normalize_language(language)]
    field_lines = "\n".join(
        f'- "{key}" - "{label}" (type: {ftype}, proper noun: {is_proper_noun}, '
        f'current value: {current!r}){_closed_set_note(allowed_values)}'
        for key, label, ftype, current, is_proper_noun, allowed_values in fields
    )
    return (
        "Fields currently on the form:\n"
        f"{field_lines}\n\n"
        f"Conversation language: {lang_name}\n"
        f'Spoken correction (transcribed, may contain errors): "{raw_text}"\n\n'
        "Identify which ONE field the speaker wants to change, and its new value.\n"
        "- Match by the field's label, by its current value, or by context - whichever the "
        "speaker is clearly referring to.\n"
        "- The new value is what they want it changed TO, never the current/old value.\n"
        f"{_NORMALIZATION_RULES}"
        "- If you cannot confidently identify which field is meant, or the new value, set "
        "field_key to null and ambiguous to true.\n\n"
        'Respond with JSON only: {"field_key": <key or null>, "value": <new value or null>, '
        '"display_value": <same new value in the conversation language, or null>, '
        '"ambiguous": <true|false>}'
    )


def build_batch_extraction_prompt(
    field_specs: list[tuple[str, str, str, bool, list[str] | None]], raw_text: str, language: str = "en"
) -> str:
    """field_specs: list of (field_key, label, field_type, is_proper_noun, allowed_values) for
    every field in the batch."""
    lang_name = LANGUAGE_NAMES[normalize_language(language)]
    field_lines = "\n".join(
        f'- "{key}" - "{label}" (type: {ftype}, proper noun: {is_proper_noun}){_closed_set_note(allowed_values)}'
        for key, label, ftype, is_proper_noun, allowed_values in field_specs
    )
    return (
        "Fields to extract from this one spoken turn:\n"
        f"{field_lines}\n\n"
        f"Conversation language: {lang_name}\n"
        f'Spoken answer (transcribed, may contain errors): "{raw_text}"\n\n'
        "For EVERY field key listed above, extract its value from the transcript.\n"
        f"{_NORMALIZATION_RULES}"
        "- If type is 'number' and the speaker says there isn't one for that field (e.g. "
        "'cluster is none', 'zero', 'no eight-hand', or the equivalent in Hindi/Marathi), "
        "return 0 for that field - that is a deliberate quantity, not a missing answer, so "
        "ambiguous stays false.\n"
        "- If a field was not mentioned at all, or is unclear, set its value to null and "
        "ambiguous to true for that field.\n"
        "- If the speaker explicitly declines an optional TEXT field (e.g. says 'no "
        "remarks', 'none', 'nothing', or the equivalent in Hindi/Marathi), set its value to "
        "an empty string \"\", not the literal words said - that is a deliberate blank, not a "
        "missing answer, so ambiguous stays false.\n"
        "- Do not guess a value for a field that wasn't actually spoken.\n\n"
        "Respond with JSON only, one entry per field key:\n"
        '{"<field_key>": {"value": <value or null>, "display_value": <value in the '
        'conversation language, or null>, "ambiguous": <true|false>}, ...}'
    )
