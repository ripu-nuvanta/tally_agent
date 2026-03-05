import pytest

from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.reports import (
    trial_balance,
    profit_and_loss,
    balance_sheet,
    bills_receivable,
    bills_payable,
    stock_summary,
)


@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient(host="localhost", port=server.port)
    return client


@pytest.mark.asyncio
async def test_trial_balance(mock_tally):
    result = await trial_balance(mock_tally, "01-04-2025", "31-03-2026")
    assert result.report_name == "Trial Balance"
    assert len(result.rows) == 7


@pytest.mark.asyncio
async def test_profit_and_loss(mock_tally):
    result = await profit_and_loss(mock_tally, "01-04-2025", "31-03-2026")
    assert result.report_name == "Profit and Loss"
    assert len(result.rows) > 0


@pytest.mark.asyncio
async def test_balance_sheet(mock_tally):
    result = await balance_sheet(mock_tally, "31-03-2026")
    assert result.report_name == "Balance Sheet"


@pytest.mark.asyncio
async def test_bills_receivable(mock_tally):
    bills = await bills_receivable(mock_tally, "31-03-2026")
    assert len(bills) == 2
    assert bills[0].party_name == "HCODE TECHNOLOGIES PRIVATE LIMITED"
    assert bills[0].amount == 200000.0
    assert bills[0].bill_number == "#1"


@pytest.mark.asyncio
async def test_bills_payable(mock_tally):
    bills = await bills_payable(mock_tally, "31-03-2026")
    assert len(bills) == 2
    assert bills[0].bill_number == "#1"
    assert bills[0].amount == 200000.0


@pytest.mark.asyncio
async def test_stock_summary(mock_tally):
    items = await stock_summary(mock_tally, "31-03-2026")
    assert len(items) == 5
    assert items[0]["name"] == "Data Cleaning and Matching Application Software"
    assert items[0]["closing_quantity"] == -1.0
