"""
Query functions for Tally master data: companies, ledgers, groups, stock items.
"""

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.models import Company, Ledger, StockItem, AccountGroup
from backend.tally_bridge.request_builder import (
    build_list_companies,
    build_list_ledgers,
    build_list_stock_items,
    build_list_groups,
)
from backend.tally_bridge.response_parser import detect_error, parse_ledger_list, parse_stock_items, parse_groups, sanitize_xml
from backend.tally_bridge.exceptions import TallyResponseError

import xml.etree.ElementTree as ET


async def list_companies(client: TallyClient) -> list[Company]:
    """Fetch all companies loaded in TallyPrime."""
    raw = await client.post_xml(build_list_companies())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)

    root = ET.fromstring(sanitize_xml(raw))
    companies = []
    # Only look inside DATA > COLLECTION, skip CMPINFO section
    collection = root.find(".//DATA/COLLECTION")
    if collection is None:
        return companies
    for comp in collection.iter("COMPANY"):
        name_el = comp.find("NAME")
        if name_el is not None and name_el.text:
            companies.append(Company(name=name_el.text.strip()))
        elif comp.get("NAME"):
            companies.append(Company(name=comp.get("NAME").strip()))
        elif comp.text and comp.text.strip():
            companies.append(Company(name=comp.text.strip()))
    return companies


async def list_ledgers(client: TallyClient) -> list[Ledger]:
    """Fetch all ledgers with parent groups and balances."""
    raw = await client.post_xml(build_list_ledgers())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)

    parsed = parse_ledger_list(raw)
    return [Ledger(**row) for row in parsed]


async def search_ledger(client: TallyClient, search_term: str) -> list[Ledger]:
    """Search ledgers by partial name match (case-insensitive)."""
    all_ledgers = await list_ledgers(client)
    term_lower = search_term.lower()
    return [l for l in all_ledgers if term_lower in l.name.lower()]


async def list_stock_items(client: TallyClient) -> list[StockItem]:
    """Fetch all stock items with parent group, UOM, and closing values."""
    raw = await client.post_xml(build_list_stock_items())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_stock_items(raw)
    return [StockItem(**row) for row in parsed]


async def list_groups(client: TallyClient) -> list[AccountGroup]:
    """Fetch all account groups with parent hierarchy."""
    raw = await client.post_xml(build_list_groups())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_groups(raw)
    return [AccountGroup(**row) for row in parsed]
