from app.features.validation.validators import (
    validate_number,
    validate_text,
    validate_time,
    validate_time_sequence,
    validate_vehicle_number,
)


def test_validate_text_required_ok():
    result = validate_text("ABC Traders", "Company Name")
    assert result.valid and result.value == "ABC Traders"


def test_validate_text_required_blank_rejected():
    assert not validate_text("", "Company Name").valid
    assert not validate_text(None, "Company Name").valid


def test_validate_text_optional_blank_allowed():
    result = validate_text("", "Remarks", required=False)
    assert result.valid and result.value == ""


def test_validate_text_too_long_rejected():
    assert not validate_text("x" * 300, "Company Name").valid


def test_validate_text_closed_set_accepts_exact_predefined_value():
    result = validate_text("Khorale Global", "Company Name", allowed_values=["Khorale Global", "Rajmata", "Jaywant"])
    assert result.valid and result.value == "Khorale Global"


def test_validate_text_closed_set_rejects_value_outside_the_list():
    # Defense in depth: the extraction prompt instructs the LLM to only return one of the
    # predefined options, but this must still catch it here if that's ever not followed,
    # rather than silently storing an unknown company/brand name.
    result = validate_text("Some Random Co", "Company Name", allowed_values=["Khorale Global", "Rajmata", "Jaywant"])
    assert not result.valid


def test_validate_text_no_allowed_values_accepts_anything():
    result = validate_text("Any Free Text At All", "Line Mark", allowed_values=None)
    assert result.valid and result.value == "Any Free Text At All"


def test_validate_number_coercion_and_normalization():
    assert validate_number(42, "Four-Hand").value == 42
    assert validate_number("42", "Four-Hand").value == 42
    assert validate_number(1200.5, "Weight").value == 1200.5


def test_validate_number_rejects_out_of_range_and_non_numeric():
    assert not validate_number(-5, "Four-Hand").valid
    assert not validate_number("abc", "Four-Hand").valid
    assert not validate_number(None, "Four-Hand").valid
    assert not validate_number(5000, "Four-Hand", max_value=1000).valid


def test_validate_vehicle_number():
    assert validate_vehicle_number("MH12AB1234").value == "MH12AB1234"
    assert validate_vehicle_number("mh 12 ab 1234").value == "MH12AB1234"
    assert not validate_vehicle_number("ABCDEFG").valid
    assert not validate_vehicle_number("").valid


def test_validate_time():
    assert validate_time("14:30", "Vehicle Out Time").value == "14:30"
    assert validate_time("9:05", "Vehicle Out Time").value == "09:05"  # zero-padded
    assert not validate_time("25:00", "Vehicle Out Time").valid
    assert not validate_time("14:65", "Vehicle Out Time").valid
    assert not validate_time("half past two", "Vehicle Out Time").valid
    assert not validate_time("", "Vehicle Out Time").valid


def test_validate_time_sequence():
    assert validate_time_sequence("09:00", "14:30", "In", "Out").valid
    assert not validate_time_sequence("09:00", "09:00", "In", "Out").valid  # equal times rejected
    assert not validate_time_sequence("14:30", "09:00", "In", "Out").valid  # out before in
