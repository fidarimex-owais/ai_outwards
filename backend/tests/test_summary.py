import pytest

from app.features.summary.builder import build_summary

FULL_FIELDS = {
    "company_name": "ABC Traders", "vehicle_number": "MH12AB1234", "container_number": "MSKU1234567",
    "brand": "Chiquita", "line_supervisor_name": "Prakash Jadhav", "weight": 1200.5,
    "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2, "total": 40,
    "labor_name": "Ramesh Kumar", "driver_name": "Mahesh Yadav",
    "cold_storage_name": "Shivam Cold Storage", "cold_storage_supervisor_name": "",
    "vehicle_in_time": "09:00", "vehicle_out_time": "14:30", "unloading_time": "16:00",
}


def test_build_summary_contains_all_sections_and_values():
    summary = build_summary(FULL_FIELDS)
    assert "Company & Vehicle Details:" in summary
    assert "Banana Hand & Cluster Quantities:" in summary
    assert "Additional Information:" in summary
    assert "ABC Traders" in summary
    assert "Total Quantity: 40" in summary


def test_build_summary_blank_value_shown_as_em_dash():
    # build_summary itself doesn't know which fields are required - it just renders any
    # blank value as an em dash, regardless of field.
    summary = build_summary(FULL_FIELDS)
    blank_line = [line for line in summary.splitlines() if "Cold Storage Supervisor Name" in line][0]
    assert "—" in blank_line


def test_build_summary_raises_on_missing_key():
    incomplete = dict(FULL_FIELDS)
    del incomplete["vehicle_number"]
    with pytest.raises(ValueError):
        build_summary(incomplete)
