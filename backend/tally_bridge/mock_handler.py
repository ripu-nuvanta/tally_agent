"""In-process mock Tally handler.

Returns fixture XML data for Bharat Traders Pvt Ltd demo company.
For TYPE=Data reports (P&L, TB), parses SVTODATE from the request
and computes cumulative figures from voucher data — matching real
Tally's behavior of returning cumulative from FY start.

For TYPE=Collection (vouchers), returns the full fixture dataset.
Python-side date filtering handles range selection.
"""
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# Mock write state (for demo/testing — resets on reset_mock_state call)
_mock_vch_counter = 0


def reset_mock_state() -> None:
    """Reset mock state (for test isolation)."""
    global _mock_vch_counter
    _mock_vch_counter = 0


# Reports that return full fixture regardless of dates
STATIC_FIXTURES: dict[str, str] = {
    "List of Companies": "company_list.xml",
    "CustomLedgerList": "ledger_list.xml",
    "Trial Balance": "trial_balance.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_payable.xml",
    "Stock Summary": "stock_summary.xml",
    "CustomStockItemList": "stock_items_list.xml",
    "CustomGroupList": "groups_list.xml",
    "Cash Flow": "cash_flow.xml",
}

# Voucher collections — return full data, Python filters by date
VOUCHER_FIXTURES: dict[str, str] = {
    "DayBookVchs": "day_book.xml",
    "SalesVchs": "sales_register.xml",
    "PurchaseVchs": "purchase_register.xml",
    "LedgerVchs": "day_book.xml",
}

# Date-aware reports — computed from voucher data
DATE_AWARE_REPORTS = {"Profit and Loss"}

_ERROR_RESPONSE = (
    "<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>"
)


@lru_cache(maxsize=32)
def _load_fixture(filename: str) -> str:
    """Load a fixture file, cached for performance.

    Call ``_load_fixture.cache_clear()`` to invalidate the cache during
    development (e.g. after editing fixture files on disk).
    """
    path = FIXTURES_DIR / filename
    if not path.exists():
        return _ERROR_RESPONSE
    return path.read_text()


def _extract_svtodate(xml_body: str) -> str | None:
    """Extract SVTODATE value from request XML. Returns YYYYMMDD or None."""
    match = re.search(r"<SVTODATE>(\d{2})-(\d{2})-(\d{4})</SVTODATE>", xml_body)
    if match:
        dd, mm, yyyy = match.groups()
        return f"{yyyy}{mm}{dd}"
    return None


def _generate_cumulative_pnl(up_to_yyyymmdd: str | None) -> str:
    """Generate P&L XML with cumulative figures up to the given date."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_fixtures",
        FIXTURES_DIR / "generate_fixtures.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_profit_and_loss(up_to_date=up_to_yyyymmdd)


def _handle_import(xml_body: str) -> str:
    """Handle IMPORTDATA requests — simulate create/alter/delete operations.

    Recognizes ACTION attribute on VOUCHER/LEDGER/GROUP elements and returns
    a matching success response. Cancel returns ALTERED=1, Delete returns
    DELETED=1, anything else (including Create) returns CREATED=1 with an
    incrementing LASTVCHID.
    """
    global _mock_vch_counter

    if 'ACTION="Delete"' in xml_body:
        return """<RESPONSE>
<CREATED>0</CREATED><ALTERED>0</ALTERED><DELETED>1</DELETED>
<LASTVCHID>0</LASTVCHID><LASTMID>0</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
<CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>"""

    if 'ACTION="Cancel"' in xml_body:
        return """<RESPONSE>
<CREATED>0</CREATED><ALTERED>1</ALTERED><DELETED>0</DELETED>
<LASTVCHID>0</LASTVCHID><LASTMID>0</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
<CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>"""

    # Default: create
    _mock_vch_counter += 1
    return f"""<RESPONSE>
<CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
<LASTVCHID>{_mock_vch_counter}</LASTVCHID><LASTMID>{_mock_vch_counter}</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
<CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>"""


def mock_tally_request(xml_body: str) -> str:
    """Process an XML request and return mock fixture response."""
    # Handle write/import requests first
    if "Import Data" in xml_body:
        return _handle_import(xml_body)

    # Check date-aware reports first
    for report_name in DATE_AWARE_REPORTS:
        if report_name in xml_body:
            svtodate = _extract_svtodate(xml_body)
            if report_name == "Profit and Loss":
                return _generate_cumulative_pnl(svtodate)

    # Static fixtures
    for report_name, fixture_file in STATIC_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)

    # Voucher collections
    for report_name, fixture_file in VOUCHER_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)

    return _ERROR_RESPONSE
