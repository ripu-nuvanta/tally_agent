"""
Lightweight HTTP server mimicking TallyPrime's behavior.
Receives XML POST requests, pattern-matches the report type,
and returns corresponding fixture data.
"""

import os

from aiohttp import web

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")

REPORT_FIXTURES = {
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


async def handle_tally_request(request: web.Request) -> web.Response:
    body = await request.text()

    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in body:
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            if os.path.exists(fixture_path):
                with open(fixture_path) as f:
                    return web.Response(text=f.read(), content_type="text/xml")

    return web.Response(
        text="<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>",
        content_type="text/xml",
    )


def create_mock_tally_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/", handle_tally_request)
    return app
