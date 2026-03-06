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


# ---------------------------------------------------------------------------
# TestResolveDateRange
# ---------------------------------------------------------------------------

from backend.utils.date_utils import resolve_date_range


class TestResolveDateRange:
    def test_q1(self):
        result = resolve_date_range("Q1", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "30-06-2025"
        assert "Q1" in result["description"]

    def test_q2(self):
        result = resolve_date_range("Q2", date(2026, 3, 6))
        assert result["from_date"] == "01-07-2025"
        assert result["to_date"] == "30-09-2025"

    def test_q3(self):
        result = resolve_date_range("Q3", date(2026, 3, 6))
        assert result["from_date"] == "01-10-2025"
        assert result["to_date"] == "31-12-2025"

    def test_q4(self):
        result = resolve_date_range("Q4", date(2026, 3, 6))
        assert result["from_date"] == "01-01-2026"
        assert result["to_date"] == "31-03-2026"

    def test_this_month(self):
        result = resolve_date_range("this month", date(2026, 3, 6))
        assert result["from_date"] == "01-03-2026"
        assert result["to_date"] == "31-03-2026"

    def test_last_month(self):
        result = resolve_date_range("last month", date(2026, 3, 6))
        assert result["from_date"] == "01-02-2026"
        assert result["to_date"] == "28-02-2026"

    def test_this_quarter(self):
        result = resolve_date_range("this quarter", date(2026, 3, 6))
        assert result["from_date"] == "01-01-2026"
        assert result["to_date"] == "31-03-2026"

    def test_last_quarter(self):
        result = resolve_date_range("last quarter", date(2026, 3, 6))
        assert result["from_date"] == "01-10-2025"
        assert result["to_date"] == "31-12-2025"

    def test_current_fy(self):
        result = resolve_date_range("current FY", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "31-03-2026"

    def test_last_fy(self):
        result = resolve_date_range("last FY", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2024"
        assert result["to_date"] == "31-03-2025"

    def test_ytd(self):
        result = resolve_date_range("YTD", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "06-03-2026"

    def test_last_n_months(self):
        result = resolve_date_range("last 3 months", date(2026, 3, 6))
        assert result["from_date"] == "01-12-2025"
        assert result["to_date"] == "06-03-2026"

    def test_q2_explicit_fy(self):
        result = resolve_date_range("Q2 2025-26", date(2026, 3, 6))
        assert result["from_date"] == "01-07-2025"
        assert result["to_date"] == "30-09-2025"

    def test_unknown_returns_error(self):
        result = resolve_date_range("banana", date(2026, 3, 6))
        assert "error" in result
