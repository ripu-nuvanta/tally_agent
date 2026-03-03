from datetime import date
from backend.utils.date_utils import (
    get_fy_start, get_fy_end, get_last_fy_range,
    get_current_quarter_range, get_last_quarter_range,
    get_month_range, format_for_tally,
)

def test_fy_start_before_april():
    assert get_fy_start(date(2026, 1, 15)) == date(2025, 4, 1)

def test_fy_start_after_april():
    assert get_fy_start(date(2025, 6, 15)) == date(2025, 4, 1)

def test_fy_start_on_april_1():
    assert get_fy_start(date(2025, 4, 1)) == date(2025, 4, 1)

def test_fy_end_before_april():
    assert get_fy_end(date(2026, 1, 15)) == date(2026, 3, 31)

def test_fy_end_after_april():
    assert get_fy_end(date(2025, 6, 15)) == date(2026, 3, 31)

def test_last_fy_range():
    start, end = get_last_fy_range(date(2026, 1, 15))
    assert start == date(2024, 4, 1)
    assert end == date(2025, 3, 31)

def test_current_quarter_q1():
    start, end = get_current_quarter_range(date(2025, 5, 10))
    assert start == date(2025, 4, 1)
    assert end == date(2025, 6, 30)

def test_current_quarter_q4():
    start, end = get_current_quarter_range(date(2026, 1, 15))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 3, 31)

def test_last_quarter_from_q4():
    start, end = get_last_quarter_range(date(2026, 1, 15))
    assert start == date(2025, 10, 1)
    assert end == date(2025, 12, 31)

def test_last_quarter_from_q1():
    start, end = get_last_quarter_range(date(2025, 5, 10))
    assert start == date(2025, 1, 1)
    assert end == date(2025, 3, 31)

def test_month_range_normal():
    start, end = get_month_range(date(2026, 1, 15))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)

def test_month_range_february_leap():
    start, end = get_month_range(date(2028, 2, 10))
    assert start == date(2028, 2, 1)
    assert end == date(2028, 2, 29)

def test_format_for_tally():
    assert format_for_tally(date(2025, 4, 1)) == "01-04-2025"

def test_format_for_tally_single_digit():
    assert format_for_tally(date(2025, 1, 5)) == "05-01-2025"
