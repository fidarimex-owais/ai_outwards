import pytest

from app.utils.time_parse import parse_time


@pytest.mark.parametrize("text, expected", [
    ("14:30", "14:30"),
    ("2:30 pm", "14:30"),
    ("9:00am", "09:00"),
    ("9am", "09:00"),
    ("9 pm", "21:00"),
    ("half past two", "02:30"),
    ("half past two in the afternoon", "14:30"),
    ("quarter past nine", "09:15"),
    ("quarter to five", "04:45"),
    ("quarter to five in the evening", "16:45"),
    ("nine o clock", "09:00"),
    ("nine oclock in the morning", "09:00"),
    ("around three-ish, not sure", None),
    ("", None),
    ("25:00", None),
])
def test_parse_time(text, expected):
    assert parse_time(text) == expected
