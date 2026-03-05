"""
Query functions for Tally voucher data: day book, registers, ledger transactions.
"""

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.request_builder import (
    build_day_book,
    build_ledger_vouchers,
    build_sales_register,
    build_purchase_register,
)
from backend.tally_bridge.response_parser import detect_error, parse_vouchers
from backend.tally_bridge.exceptions import TallyResponseError


async def day_book(
    client: TallyClient,
    from_date: str,
    to_date: str,
    voucher_type: str | None = None,
    company: str | None = None,
) -> list[dict]:
    """Fetch all voucher entries for a date range."""
    raw = await client.post_xml(build_day_book(from_date, to_date, voucher_type, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def ledger_vouchers(
    client: TallyClient,
    ledger_name: str,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch all vouchers for a specific ledger."""
    raw = await client.post_xml(build_ledger_vouchers(ledger_name, from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def sales_register(
    client: TallyClient,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch sales register."""
    raw = await client.post_xml(build_sales_register(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def purchase_register(
    client: TallyClient,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch purchase register."""
    raw = await client.post_xml(build_purchase_register(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)
