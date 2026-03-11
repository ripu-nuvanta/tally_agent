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


class TestResolveDateRangeNewPatterns:
    """Test new date resolution patterns: month+year, FY, month ranges."""

    def test_resolve_april_2025(self):
        result = resolve_date_range("April 2025")
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "30-04-2025"

    def test_resolve_march_2026(self):
        result = resolve_date_range("March 2026")
        assert result["from_date"] == "01-03-2026"
        assert result["to_date"] == "31-03-2026"

    def test_resolve_jan_2026_abbreviated(self):
        result = resolve_date_range("jan 2026")
        assert result["from_date"] == "01-01-2026"
        assert result["to_date"] == "31-01-2026"

    def test_resolve_september_2025_sept_abbrev(self):
        result = resolve_date_range("sept 2025")
        assert result["from_date"] == "01-09-2025"
        assert result["to_date"] == "30-09-2025"

    def test_resolve_case_insensitive(self):
        result = resolve_date_range("APRIL 2025")
        assert result["from_date"] == "01-04-2025"

    def test_resolve_fy_2025_26(self):
        result = resolve_date_range("FY 2025-26")
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "31-03-2026"

    def test_resolve_fy_short_years(self):
        result = resolve_date_range("fy 25-26")
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "31-03-2026"

    def test_resolve_fy_full_years(self):
        result = resolve_date_range("FY 2025-2026")
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "31-03-2026"

    def test_resolve_april_to_june_2025(self):
        result = resolve_date_range("April to June 2025")
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "30-06-2025"


import pytest
from backend.utils.date_utils import validate_tally_date


class TestValidateTallyDate:
    def test_valid_date(self):
        assert validate_tally_date("01-04-2025") == "01-04-2025"

    def test_valid_date_end_of_month(self):
        assert validate_tally_date("31-03-2026") == "31-03-2026"

    def test_valid_date_leap_year(self):
        assert validate_tally_date("29-02-2028") == "29-02-2028"

    def test_iso_format_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("2025-04-01")

    def test_slash_format_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("01/04/2025")

    def test_garbage_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("not-a-date")

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("")

    def test_invalid_day_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("30-02-2025")

    def test_iso_autofix(self):
        assert validate_tally_date("2025-04-01", autofix=True) == "01-04-2025"

    def test_iso_autofix_validates_result(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date("2025-13-01", autofix=True)

    def test_none_rejected(self):
        with pytest.raises(ValueError, match="DD-MM-YYYY"):
            validate_tally_date(None)
