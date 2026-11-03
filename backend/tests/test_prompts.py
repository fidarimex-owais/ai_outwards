from app.features.extraction.prompts import (
    build_batch_extraction_prompt,
    build_correction_prompt,
    build_extraction_prompt,
)

_COMPANIES = ["Khorale Global", "Rajmata", "Jaywant"]


def test_single_field_prompt_lists_closed_set_candidates():
    prompt = build_extraction_prompt(
        "Company Name", "text", "corale global", "en", True, _COMPANIES,
    )
    assert '[one of: "Khorale Global", "Rajmata", "Jaywant"]' in prompt


def test_single_field_prompt_omits_closed_set_note_when_none():
    # The shared normalization rules explain the "[one of: ...]" notation in general terms
    # (so that phrase legitimately appears in every prompt) - what must NOT happen is this
    # specific field's own header line picking one up when it has no allowed_values.
    prompt = build_extraction_prompt("Line Mark", "text", "anything", "en", True, None)
    field_line = prompt.splitlines()[0]
    assert field_line.startswith('Field: "Line Mark"')
    assert "[one of:" not in field_line


def test_batch_prompt_lists_closed_set_candidates_per_field():
    prompt = build_batch_extraction_prompt(
        [
            ("company_name", "Company Name", "text", True, _COMPANIES),
            ("line_mark", "Line Mark", "text", True, None),
        ],
        "some spoken text",
        "en",
    )
    assert '"company_name"' in prompt
    assert '[one of: "Khorale Global", "Rajmata", "Jaywant"]' in prompt
    # line_mark has no allowed_values - its line must not pick up the note meant for company_name
    line_mark_line = next(line for line in prompt.splitlines() if '"line_mark"' in line)
    assert "[one of:" not in line_mark_line


def test_correction_prompt_lists_closed_set_candidates():
    prompt = build_correction_prompt(
        [("company_name", "Company Name", "text", "Khorale Global", True, _COMPANIES)],
        "change the company to Rajmata",
        "en",
    )
    assert '[one of: "Khorale Global", "Rajmata", "Jaywant"]' in prompt
