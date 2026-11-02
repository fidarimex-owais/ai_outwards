import pytest

from app.features.extraction.rules import extract_number, extract_text, extract_vehicle_number


@pytest.mark.parametrize("text, expected", [
    ("42", 42),
    ("weight is 1200 kg", 1200),
    ("forty two", 42),
    ("twenty", 20),
    ("one hundred and five", 105),
    ("two thousand five hundred", 2500),
    ("three", 3),
    ("banana split", None),
    ("", None),
    # a declined/absent quantity is a valid 0, not "unclear"
    ("none", 0), ("None", 0), ("none.", 0), ("no", 0), ("nil", 0), ("nothing", 0), ("zero", 0),
])
def test_extract_number(text, expected):
    assert extract_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("MH12AB1234", "MH12AB1234"),
    ("mh 12 ab 1234", "MH12AB1234"),
    ("MH-12-AB-1234", "MH12AB1234"),
    ("the vehicle number is KA05MX0007", "KA05MX0007"),
    ("no plate given", None),
])
def test_extract_vehicle_number(text, expected):
    assert extract_vehicle_number(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("ABC Traders", "ABC Traders"),
    ("  padded  ", "padded"),
    ("", None),
    ("   ", None),
])
def test_extract_text(text, expected):
    assert extract_text(text) == expected
