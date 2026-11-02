from app.features.validation.calculator import calculate_total


def test_calculate_total():
    assert calculate_total(four_hand=10, five_hand=20, six_hand=5, eight_hand=3, cluster=2) == 40


def test_calculate_total_all_zero():
    assert calculate_total(0, 0, 0, 0, 0) == 0
