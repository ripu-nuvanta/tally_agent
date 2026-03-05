"""
Query functions for Tally financial reports.
"""

from datetime import date, datetime

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.models import ReportResponse, OutstandingBill
from backend.tally_bridge.request_builder import (
    build_trial_balance,
    build_profit_and_loss,
    build_balance_sheet,
    build_bills_receivable,
    build_bills_payable,
    build_stock_summary,
)
from backend.tally_bridge.response_parser import (
    detect_error,
    parse_trial_balance as _parse_tb,
    parse_profit_and_loss as _parse_pnl,
    parse_balance_sheet as _parse_bs,
    parse_bills,
    parse_stock_summary as _parse_stock,
)
from backend.tally_bridge.exceptions import TallyResponseError


def _parse_tally_date(date_str: str) -> date | None:
    """Parse Tally date formats into date object.

    Tally uses multiple formats:
    - YYYYMMDD (voucher exports)
    - D-Mon-YY (bills: 2-Jul-25)
    - DD-MM-YYYY (request format)
    """
    if not date_str:
        return None
    for fmt in ("%Y%m%d", "%d-%b-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


async def trial_balance(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Trial Balance for a date range."""
    raw = await client.post_xml(build_trial_balance(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_tb(raw)
    return ReportResponse(
        report_name="Trial Balance",
        company=company or "",
        rows=rows,
    )


async def profit_and_loss(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Profit & Loss statement."""
    raw = await client.post_xml(build_profit_and_loss(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_pnl(raw)
    return ReportResponse(
        report_name="Profit and Loss",
        company=company or "",
        rows=rows,
    )


async def balance_sheet(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Balance Sheet as on a date."""
    raw = await client.post_xml(build_balance_sheet(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_bs(raw)
    return ReportResponse(
        report_name="Balance Sheet",
        company=company or "",
        rows=rows,
    )


async def bills_receivable(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> list[OutstandingBill]:
    """Fetch outstanding receivables."""
    raw = await client.post_xml(build_bills_receivable(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_bills(raw)
    return [
        OutstandingBill(
            party_name=b["party_name"],
            bill_number=b["bill_number"],
            bill_date=_parse_tally_date(b["bill_date"]) or date.today(),
            amount=b["amount"],
            pending_amount=b["pending_amount"],
        )
        for b in parsed
    ]


async def bills_payable(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> list[OutstandingBill]:
    """Fetch outstanding payables."""
    raw = await client.post_xml(build_bills_payable(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_bills(raw)
    return [
        OutstandingBill(
            party_name=b["party_name"],
            bill_number=b["bill_number"],
            bill_date=_parse_tally_date(b["bill_date"]) or date.today(),
            amount=b["amount"],
            pending_amount=b["pending_amount"],
        )
        for b in parsed
    ]


async def stock_summary(
    client: TallyClient, as_on_date: str, stock_group: str | None = None, company: str | None = None
) -> list[dict]:
    """Fetch stock/inventory summary."""
    raw = await client.post_xml(build_stock_summary(as_on_date, stock_group, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return _parse_stock(raw)
