"""
Query functions for Tally financial reports.
"""

import logging
from datetime import date, datetime, timedelta

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
from backend.utils.date_utils import get_fy_start, format_for_tally

logger = logging.getLogger(__name__)


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


def _parse_tally_date_str(date_str: str) -> date:
    """Parse DD-MM-YYYY date string into a date object."""
    return datetime.strptime(date_str.strip(), "%d-%m-%Y").date()


def _subtract_pnl_rows(
    cumulative_rows: list[dict], prior_rows: list[dict]
) -> list[dict]:
    """Subtract prior-period P&L rows from cumulative rows to get period-specific values.

    Aligns rows by account_name. For each matching row, subtracts prior closing_balance
    from cumulative closing_balance and recomputes debit/credit.
    """
    prior_map = {r["account_name"]: r["closing_balance"] for r in prior_rows}
    result = []
    for row in cumulative_rows:
        name = row["account_name"]
        cum_bal = row["closing_balance"]
        prior_bal = prior_map.get(name, 0.0)
        period_bal = cum_bal - prior_bal
        result.append({
            "account_name": name,
            "debit_amount": period_bal if period_bal < 0 else 0.0,
            "credit_amount": period_bal if period_bal > 0 else 0.0,
            "closing_balance": period_bal,
        })
    return result


async def profit_and_loss_period(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch period-specific Profit & Loss by subtracting cumulative figures.

    Tally's P&L report (TYPE=Data) may return cumulative figures from the
    Financial Year start, ignoring SVFROMDATE. This function works around
    that by:
    1. If from_date is already FY start (April 1), just fetch normally.
    2. Otherwise, fetch two cumulative P&L reports (FY start→to_date and
       FY start→day-before-from_date) and subtract to get period-specific data.
    """
    from_dt = _parse_tally_date_str(from_date)
    fy_start = get_fy_start(from_dt)
    fy_start_str = format_for_tally(fy_start)

    # If from_date is already FY start, no subtraction needed
    if from_dt == fy_start:
        logger.debug("P&L period: from_date is FY start, fetching directly")
        return await profit_and_loss(client, from_date, to_date, company)

    # Fetch cumulative P&L from FY start to to_date
    logger.debug(
        "P&L period: using subtraction approach (%s to %s via FY start %s)",
        from_date, to_date, fy_start_str,
    )
    cumulative = await profit_and_loss(client, fy_start_str, to_date, company)

    # Fetch cumulative P&L from FY start to the day before from_date
    prior_end = from_dt - timedelta(days=1)
    prior_end_str = format_for_tally(prior_end)
    prior = await profit_and_loss(client, fy_start_str, prior_end_str, company)

    # Subtract to get period-specific values
    period_rows = _subtract_pnl_rows(cumulative.rows, prior.rows)

    return ReportResponse(
        report_name="Profit and Loss",
        company=company or "",
        from_date=from_dt,
        to_date=_parse_tally_date_str(to_date),
        rows=period_rows,
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
