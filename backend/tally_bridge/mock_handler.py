"""In-process mock Tally handler.

Returns fixture XML data for Bharat Traders Pvt Ltd demo company.
Pattern-matches report names in XML request body and returns
corresponding fixture files. This is the single canonical mock
implementation — tests/mocks/mock_tally_server.py delegates to this.
"""

import os
from functools import lru_cache

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures"
)

# Same mapping as tests/mocks/mock_tally_server.py — kept in sync
REPORT_FIXTURES: dict[str, str] = {
    "List of Companies": "company_list.xml",
    "Trial Balance": "trial_balance.xml",
    "CustomLedgerList": "ledger_list.xml",
    "Profit and Loss": "profit_and_loss.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_receivable.xml",
    "Stock Summary": "stock_summary.xml",
    "DayBookVchs": "day_book.xml",
    "SalesVchs": "sales_register.xml",
    "PurchaseVchs": "sales_register.xml",
    "LedgerVchs": "day_book.xml",
}

_ERROR_RESPONSE = (
    "<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>"
)


@lru_cache(maxsize=32)
def _load_fixture(filename: str) -> str:
    """Load a fixture file, cached for performance."""
    path = os.path.join(FIXTURES_DIR, filename)
    if not os.path.exists(path):
        return _ERROR_RESPONSE
    with open(path) as f:
        return f.read()


def mock_tally_request(xml_body: str) -> str:
    """Process an XML request and return mock fixture response."""
    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)
    return _ERROR_RESPONSE
