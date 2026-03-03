import calendar
from datetime import date


def get_fy_start(ref: date) -> date:
    """Return April 1 of the current Indian financial year."""
    if ref.month >= 4:
        return date(ref.year, 4, 1)
    return date(ref.year - 1, 4, 1)


def get_fy_end(ref: date) -> date:
    """Return March 31 of the current Indian financial year."""
    if ref.month >= 4:
        return date(ref.year + 1, 3, 31)
    return date(ref.year, 3, 31)


def get_last_fy_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the previous Indian financial year."""
    fy_start = get_fy_start(ref)
    return date(fy_start.year - 1, 4, 1), date(fy_start.year, 3, 31)


# Indian FY quarters: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
_QUARTERS = [(4, 6), (7, 9), (10, 12), (1, 3)]


def _get_quarter_index(month: int) -> int:
    if 4 <= month <= 6: return 0
    elif 7 <= month <= 9: return 1
    elif 10 <= month <= 12: return 2
    else: return 3


def get_current_quarter_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the current Indian FY quarter."""
    qi = _get_quarter_index(ref.month)
    start_month, end_month = _QUARTERS[qi]
    if qi == 3:
        year = ref.year
    elif ref.month >= 4:
        year = ref.year
    else:
        year = ref.year - 1
    if qi == 3:
        start_year = ref.year
    else:
        start_year = year
    last_day = calendar.monthrange(start_year, end_month)[1]
    return date(start_year, start_month, 1), date(start_year, end_month, last_day)


def get_last_quarter_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the previous Indian FY quarter."""
    qi = _get_quarter_index(ref.month)
    prev_qi = (qi - 1) % 4
    start_month, end_month = _QUARTERS[prev_qi]
    if qi == 0:
        year = ref.year
    elif qi == 3:
        year = ref.year - 1
    else:
        year = ref.year
    last_day = calendar.monthrange(year, end_month)[1]
    return date(year, start_month, 1), date(year, end_month, last_day)


def get_month_range(ref: date) -> tuple[date, date]:
    """Return (first day, last day) of the month containing ref."""
    last_day = calendar.monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)


def format_for_tally(d: date) -> str:
    """Format date as DD-MM-YYYY for Tally requests."""
    return d.strftime("%d-%m-%Y")
