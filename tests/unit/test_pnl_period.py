"""Unit tests for period-specific P&L subtraction logic."""
import pytest
from unittest.mock import AsyncMock, patch
from datetime import date

from backend.tally_bridge.queries.reports import (
    _subtract_pnl_rows,
    _parse_tally_date_str,
    profit_and_loss_period,
)
from backend.tally_bridge.models import ReportResponse


# ---------------------------------------------------------------------------
# _parse_tally_date_str
# ---------------------------------------------------------------------------


def test_parse_tally_date_str_normal():
    assert _parse_tally_date_str("01-04-2025") == date(2025, 4, 1)


def test_parse_tally_date_str_end_of_month():
    assert _parse_tally_date_str("31-03-2026") == date(2026, 3, 31)


def test_parse_tally_date_str_with_whitespace():
    assert _parse_tally_date_str(" 15-07-2025 ") == date(2025, 7, 15)


# ---------------------------------------------------------------------------
# _subtract_pnl_rows
# ---------------------------------------------------------------------------


def _make_row(name: str, amount: float) -> dict:
    return {
        "account_name": name,
        "debit_amount": amount if amount < 0 else 0.0,
        "credit_amount": amount if amount > 0 else 0.0,
        "closing_balance": amount,
    }


def test_subtract_pnl_rows_basic():
    """Subtract prior from cumulative to get period-specific values."""
    cumulative = [
        _make_row("Sales Accounts", 3764350.0),
        _make_row("Indirect Expenses", -2351297.20),
    ]
    prior = [
        _make_row("Sales Accounts", 1195000.0),
        _make_row("Indirect Expenses", -1125369.94),
    ]
    result = _subtract_pnl_rows(cumulative, prior)

    assert len(result) == 2
    # Sales: 3764350 - 1195000 = 2569350
    assert result[0]["account_name"] == "Sales Accounts"
    assert abs(result[0]["closing_balance"] - 2569350.0) < 0.01
    assert result[0]["credit_amount"] == result[0]["closing_balance"]
    assert result[0]["debit_amount"] == 0.0

    # Expenses: -2351297.20 - (-1125369.94) = -1225927.26
    assert result[1]["account_name"] == "Indirect Expenses"
    assert abs(result[1]["closing_balance"] - (-1225927.26)) < 0.01
    assert result[1]["debit_amount"] == result[1]["closing_balance"]
    assert result[1]["credit_amount"] == 0.0


def test_subtract_pnl_rows_missing_prior_account():
    """If an account exists in cumulative but not in prior, treat prior as 0."""
    cumulative = [_make_row("Sales Accounts", 500000.0)]
    prior = []
    result = _subtract_pnl_rows(cumulative, prior)

    assert len(result) == 1
    assert result[0]["closing_balance"] == 500000.0


def test_subtract_pnl_rows_zero_result():
    """Subtraction resulting in zero should have zero debit and credit."""
    cumulative = [_make_row("Sales Accounts", 100000.0)]
    prior = [_make_row("Sales Accounts", 100000.0)]
    result = _subtract_pnl_rows(cumulative, prior)

    assert result[0]["closing_balance"] == 0.0
    assert result[0]["debit_amount"] == 0.0
    assert result[0]["credit_amount"] == 0.0


def test_subtract_pnl_rows_preserves_order():
    """Result should preserve the order of cumulative rows."""
    cumulative = [
        _make_row("Sales Accounts", 200.0),
        _make_row("Cost of Sales", -100.0),
        _make_row("Indirect Expenses", -50.0),
    ]
    prior = [
        _make_row("Indirect Expenses", -20.0),
        _make_row("Sales Accounts", 80.0),
        _make_row("Cost of Sales", -40.0),
    ]
    result = _subtract_pnl_rows(cumulative, prior)
    assert [r["account_name"] for r in result] == [
        "Sales Accounts",
        "Cost of Sales",
        "Indirect Expenses",
    ]
    assert result[0]["closing_balance"] == 120.0  # 200 - 80
    assert result[1]["closing_balance"] == -60.0  # -100 - (-40)
    assert result[2]["closing_balance"] == -30.0  # -50 - (-20)


# ---------------------------------------------------------------------------
# profit_and_loss_period (async, mocked)
# ---------------------------------------------------------------------------


def _make_report(rows: list[dict]) -> ReportResponse:
    return ReportResponse(report_name="Profit and Loss", company="", rows=rows)


@pytest.mark.asyncio
async def test_pnl_period_fy_start_no_subtraction():
    """When from_date is FY start (April 1), should fetch directly without subtraction."""
    mock_client = AsyncMock()
    expected = _make_report([_make_row("Sales Accounts", 1000.0)])

    with patch(
        "backend.tally_bridge.queries.reports.profit_and_loss",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_pnl:
        result = await profit_and_loss_period(
            mock_client, "01-04-2025", "30-06-2025"
        )
        # Should call profit_and_loss only once (direct fetch)
        mock_pnl.assert_called_once_with(
            mock_client, "01-04-2025", "30-06-2025", None
        )
        assert result == expected


@pytest.mark.asyncio
async def test_pnl_period_subtraction_for_q2():
    """Q2 (Jul-Sep) should trigger subtraction: cumulative(Apr-Sep) - cumulative(Apr-Jun)."""
    mock_client = AsyncMock()

    cumulative_apr_sep = _make_report([
        _make_row("Sales Accounts", 1195000.0),
        _make_row("Indirect Expenses", -800000.0),
    ])
    prior_apr_jun = _make_report([
        _make_row("Sales Accounts", 0.0),
        _make_row("Indirect Expenses", -50000.0),
    ])

    call_count = 0

    async def mock_pnl(client, from_date, to_date, company=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: FY start to to_date (cumulative Apr-Sep)
            assert from_date == "01-04-2025"
            assert to_date == "30-09-2025"
            return cumulative_apr_sep
        else:
            # Second call: FY start to day-before-from_date (prior Apr-Jun)
            assert from_date == "01-04-2025"
            assert to_date == "30-06-2025"
            return prior_apr_jun

    with patch(
        "backend.tally_bridge.queries.reports.profit_and_loss",
        side_effect=mock_pnl,
    ):
        result = await profit_and_loss_period(
            mock_client, "01-07-2025", "30-09-2025"
        )

    assert call_count == 2
    assert len(result.rows) == 2
    # Sales: 1195000 - 0 = 1195000
    assert result.rows[0]["closing_balance"] == 1195000.0
    # Expenses: -800000 - (-50000) = -750000
    assert result.rows[1]["closing_balance"] == -750000.0
    # Dates should be set
    assert result.from_date == date(2025, 7, 1)
    assert result.to_date == date(2025, 9, 30)


@pytest.mark.asyncio
async def test_pnl_period_subtraction_for_q3():
    """Q3 (Oct-Dec) should trigger subtraction: cumulative(Apr-Dec) - cumulative(Apr-Sep)."""
    mock_client = AsyncMock()

    cumulative_apr_dec = _make_report([
        _make_row("Sales Accounts", 3152500.0),
    ])
    prior_apr_sep = _make_report([
        _make_row("Sales Accounts", 1195000.0),
    ])

    call_count = 0

    async def mock_pnl(client, from_date, to_date, company=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            assert from_date == "01-04-2025"
            assert to_date == "31-12-2025"
            return cumulative_apr_dec
        else:
            assert from_date == "01-04-2025"
            assert to_date == "30-09-2025"
            return prior_apr_sep

    with patch(
        "backend.tally_bridge.queries.reports.profit_and_loss",
        side_effect=mock_pnl,
    ):
        result = await profit_and_loss_period(
            mock_client, "01-10-2025", "31-12-2025"
        )

    assert call_count == 2
    # Sales: 3152500 - 1195000 = 1957500
    assert result.rows[0]["closing_balance"] == 1957500.0


@pytest.mark.asyncio
async def test_pnl_period_with_company():
    """Company parameter should be passed through to both calls."""
    mock_client = AsyncMock()
    report = _make_report([_make_row("Sales", 100.0)])

    with patch(
        "backend.tally_bridge.queries.reports.profit_and_loss",
        new_callable=AsyncMock,
        return_value=report,
    ) as mock_pnl:
        await profit_and_loss_period(
            mock_client, "01-07-2025", "30-09-2025", "TestCo"
        )
        # Both calls should include company
        assert mock_pnl.call_count == 2
        for call in mock_pnl.call_args_list:
            assert call[0][3] == "TestCo" or call.kwargs.get("company") == "TestCo"


@pytest.mark.asyncio
async def test_pnl_period_jan_crosses_calendar_year():
    """January (Q4) should correctly compute FY start as previous year's April."""
    mock_client = AsyncMock()
    report = _make_report([_make_row("Sales", 100.0)])

    call_args = []

    async def mock_pnl(client, from_date, to_date, company=None):
        call_args.append((from_date, to_date))
        return report

    with patch(
        "backend.tally_bridge.queries.reports.profit_and_loss",
        side_effect=mock_pnl,
    ):
        await profit_and_loss_period(
            mock_client, "01-01-2026", "31-03-2026"
        )

    # FY start for Jan 2026 is 01-04-2025
    assert call_args[0] == ("01-04-2025", "31-03-2026")  # cumulative
    assert call_args[1] == ("01-04-2025", "31-12-2025")  # prior
