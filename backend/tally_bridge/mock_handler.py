"""In-process mock Tally handler.

Returns fixture XML data for Bharat Traders Pvt Ltd demo company.
Pattern-matches report names in XML request body and returns
corresponding fixture files. This is the single canonical mock
implementation — tests/mocks/mock_tally_server.py delegates to this.
"""

from functools import lru_cache
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# Same mapping as tests/mocks/mock_tally_server.py — kept in sync
REPORT_FIXTURES: dict[str, str] = {
    "List of Companies": "company_list.xml",
    "Trial Balance": "trial_balance.xml",
    "CustomLedgerList": "ledger_list.xml",
    "Profit and Loss": "profit_and_loss.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_receivable.xml",  # Intentional: demo company uses same fixture format for both receivable and payable
    "Stock Summary": "stock_summary.xml",
    "DayBookVchs": "day_book.xml",
    "SalesVchs": "sales_register.xml",
    "PurchaseVchs": "purchase_register.xml",
    "LedgerVchs": "day_book.xml",
}

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


def mock_tally_request(xml_body: str) -> str:
    """Process an XML request and return mock fixture response."""
    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)
    return _ERROR_RESPONSE
