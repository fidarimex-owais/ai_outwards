import pytest

from app.features.summary.builder import build_summary

FULL_FIELDS = {
    "company_name": "ABC Traders", "vehicle_number": "MH12AB1234", "brand": "Chiquita",
    "line_mark": "Line 3", "weight": 1200.5,
    "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2, "total": 40,
    "remarks": "", "labor_name": "Ramesh Kumar", "vehicle_out_time": "14:30",
    "vehicle_in_time": "09:00", "vehicle_for_storage": "Yes", "vehicle_receiver_name": "Suresh",
}


def test_build_summary_contains_all_sections_and_values():
    summary = build_summary(FULL_FIELDS)
    assert "Company & Vehicle Details:" in summary
    assert "Banana Hand & Cluster Quantities:" in summary
    assert "Additional Information:" in summary
    assert "ABC Traders" in summary
    assert "Total Quantity: 40" in summary


def test_build_summary_blank_optional_field_shown_as_em_dash():
    summary = build_summary(FULL_FIELDS)
    remarks_line = [line for line in summary.splitlines() if "Remarks" in line][0]
    assert "—" in remarks_line


def test_build_summary_raises_on_missing_key():
    incomplete = dict(FULL_FIELDS)
    del incomplete["vehicle_number"]
    with pytest.raises(ValueError):
        build_summary(incomplete)
