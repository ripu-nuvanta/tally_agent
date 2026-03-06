import calendar
import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta


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


def resolve_date_range(description: str, ref: date | None = None) -> dict:
    """Resolve a natural-language date expression to a from_date/to_date range.

    Args:
        description: Natural language like "Q2", "this month", "last quarter",
                     "last 3 months", "YTD", "current FY", "Q2 2025-26".
        ref: Reference date (defaults to today).

    Returns:
        {"from_date": "DD-MM-YYYY", "to_date": "DD-MM-YYYY", "description": "..."}
        or {"error": "Could not resolve..."} if unrecognized.
    """
    if ref is None:
        ref = date.today()

    desc = description.strip().lower()

    # --- Specific quarter: Q1, Q2, Q3, Q4 (optionally with FY year) ---
    q_match = re.match(r'^q([1-4])(?:\s+(\d{4})[-–](\d{2,4}))?$', desc)
    if q_match:
        q_num = int(q_match.group(1))
        if q_match.group(2):
            fy_start_year = int(q_match.group(2))
        else:
            fy_start_year = get_fy_start(ref).year
        start_month, end_month = _QUARTERS[q_num - 1]
        if q_num <= 3:  # Q1-Q3 are in the FY start year
            year = fy_start_year
        else:  # Q4 is in the FY end year
            year = fy_start_year + 1
        last_day = calendar.monthrange(year, end_month)[1]
        return {
            "from_date": format_for_tally(date(year, start_month, 1)),
            "to_date": format_for_tally(date(year, end_month, last_day)),
            "description": f"Q{q_num} FY {fy_start_year}-{(fy_start_year+1) % 100:02d}",
        }

    # --- This month ---
    if desc in ("this month", "current month"):
        start, end = get_month_range(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": ref.strftime('%B %Y'),
        }

    # --- Last month ---
    if desc == "last month":
        prev = ref.replace(day=1) - timedelta(days=1)
        start, end = get_month_range(prev)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": prev.strftime('%B %Y'),
        }

    # --- This quarter / current quarter ---
    if desc in ("this quarter", "current quarter"):
        start, end = get_current_quarter_range(ref)
        qi = _get_quarter_index(ref.month)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"Q{qi+1} (current quarter)",
        }

    # --- Last quarter ---
    if desc == "last quarter":
        start, end = get_last_quarter_range(ref)
        qi = (_get_quarter_index(ref.month) - 1) % 4
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"Q{qi+1} (previous quarter)",
        }

    # --- Current FY / this year ---
    if desc in ("current fy", "this fy", "this year", "current year", "current financial year"):
        start = get_fy_start(ref)
        end = get_fy_end(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"FY {start.year}-{(start.year+1) % 100:02d}",
        }

    # --- Last FY / last year ---
    if desc in ("last fy", "last year", "previous fy", "previous year", "last financial year"):
        start, end = get_last_fy_range(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"FY {start.year}-{(start.year+1) % 100:02d}",
        }

    # --- YTD (Year to Date — from FY start to today) ---
    if desc in ("ytd", "year to date"):
        start = get_fy_start(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(ref),
            "description": f"YTD ({format_for_tally(start)} to {format_for_tally(ref)})",
        }

    # --- Last N months ---
    last_n = re.match(r'^last\s+(\d+)\s+months?$', desc)
    if last_n:
        n = int(last_n.group(1))
        start = (ref.replace(day=1) - relativedelta(months=n)).replace(day=1)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(ref),
            "description": f"Last {n} months",
        }

    return {"error": f"Could not resolve date range: '{description}'"}
