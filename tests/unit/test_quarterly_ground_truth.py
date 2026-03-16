"""Tests that quarterly ground truth in mock_golden.json is consistent with
the fixture generator's voucher data (commit 87773e5).

Validates:
1. Q3/Q4 revenue, purchases, expenses match mock_golden.json
2. Q3+Q4+Q1+Q2 revenue = full-year P&L revenue
"""

import json
from datetime import date
from pathlib import Path

import pytest

from tests.fixtures.generate_fixtures import (
    SALES_INVOICES,
    PURCHASE_INVOICES,
    PAYMENTS,
    OFFICE_SUPPLY_ITEMS,
    _sales_ledger_for_item,
    _purchase_ledger_for_item,
)

GOLDEN_PATH = Path(__file__).parent.parent / "eval" / "golden" / "mock_golden.json"


@pytest.fixture
def golden_data():
    with open(GOLDEN_PATH) as f:
        return json.load(f)


def _compute_quarterly_revenue(start_yyyymmdd: str, end_yyyymmdd: str) -> dict:
    """Compute revenue per sales ledger for a date range."""
    by_ledger: dict[str, float] = {}
    for _, dt, _, items, total, _ in SALES_INVOICES:
        if dt < start_yyyymmdd or dt > end_yyyymmdd:
            continue
        for item_name, qty, rate in items:
            ledger = _sales_ledger_for_item(item_name)
            by_ledger[ledger] = by_ledger.get(ledger, 0) + qty * rate
    return by_ledger


def _compute_quarterly_purchases(start_yyyymmdd: str, end_yyyymmdd: str) -> dict:
    """Compute purchases per purchase ledger for a date range."""
    by_ledger: dict[str, float] = {}
    for _, dt, _, items, total, _ in PURCHASE_INVOICES:
        if dt < start_yyyymmdd or dt > end_yyyymmdd:
            continue
        for item_name, qty, rate in items:
            ledger = _purchase_ledger_for_item(item_name)
            by_ledger[ledger] = by_ledger.get(ledger, 0) + qty * rate
    return by_ledger


def _compute_quarterly_expenses(start_yyyymmdd: str, end_yyyymmdd: str) -> dict:
    """Compute indirect expenses from payments for a date range."""
    indirect_expense_ledgers = {
        "Rent", "Salaries", "Electricity", "Internet & Phone",
        "Office Maintenance", "Travel & Conveyance",
    }
    by_ledger: dict[str, float] = {}
    for _, dt, payee, _, amount, _ in PAYMENTS:
        if dt < start_yyyymmdd or dt > end_yyyymmdd:
            continue
        if payee in indirect_expense_ledgers:
            by_ledger[payee] = by_ledger.get(payee, 0) + amount
    return by_ledger


class TestQuarterlyGroundTruthConsistency:
    """Verify mock_golden.json quarterly_comparison_q3_q4 matches fixture generator data."""

    def test_q3_revenue_matches_golden(self, golden_data):
        """Q3 (Oct-Dec 2025) revenue from vouchers matches golden file."""
        golden_q3 = golden_data["quarterly_comparison_q3_q4"]["q3"]["revenue"]
        computed = _compute_quarterly_revenue("20251001", "20251231")

        assert computed.get("Sales - Electronics", 0) == golden_q3["Sales - Electronics"]
        assert computed.get("Sales - Office Supplies", 0) == golden_q3["Sales - Office Supplies"]
        total = sum(computed.values())
        assert total == golden_q3["total"]

    def test_q4_revenue_matches_golden(self, golden_data):
        """Q4 (Jan-Mar 2026) revenue from vouchers matches golden file."""
        golden_q4 = golden_data["quarterly_comparison_q3_q4"]["q4"]["revenue"]
        computed = _compute_quarterly_revenue("20260101", "20260331")

        assert computed.get("Sales - Electronics", 0) == golden_q4["Sales - Electronics"]
        assert computed.get("Sales - Office Supplies", 0) == golden_q4["Sales - Office Supplies"]
        total = sum(computed.values())
        assert total == golden_q4["total"]

    def test_q3_purchases_matches_golden(self, golden_data):
        """Q3 purchases from vouchers matches golden file."""
        golden_q3 = golden_data["quarterly_comparison_q3_q4"]["q3"]["purchases"]
        computed = _compute_quarterly_purchases("20251001", "20251231")

        assert computed.get("Purchase - Electronics", 0) == golden_q3["Purchase - Electronics"]
        assert computed.get("Purchase - Office Supplies", 0) == golden_q3["Purchase - Office Supplies"]
        total = sum(computed.values())
        assert total == golden_q3["total"]

    def test_q4_purchases_matches_golden(self, golden_data):
        """Q4 purchases from vouchers matches golden file."""
        golden_q4 = golden_data["quarterly_comparison_q3_q4"]["q4"]["purchases"]
        computed = _compute_quarterly_purchases("20260101", "20260331")

        assert computed.get("Purchase - Electronics", 0) == golden_q4["Purchase - Electronics"]
        assert computed.get("Purchase - Office Supplies", 0) == golden_q4["Purchase - Office Supplies"]
        total = sum(computed.values())
        assert total == golden_q4["total"]

    def test_q3_expenses_matches_golden(self, golden_data):
        """Q3 expenses from payments matches golden file."""
        golden_q3 = golden_data["quarterly_comparison_q3_q4"]["q3"]["expenses"]
        computed = _compute_quarterly_expenses("20251001", "20251231")

        for ledger in ["Rent", "Salaries", "Electricity", "Internet & Phone",
                       "Office Maintenance", "Travel & Conveyance"]:
            assert computed.get(ledger, 0) == golden_q3[ledger], f"Q3 {ledger} mismatch"
        total = sum(computed.values())
        assert total == golden_q3["total"]

    def test_q4_expenses_matches_golden(self, golden_data):
        """Q4 expenses from payments matches golden file."""
        golden_q4 = golden_data["quarterly_comparison_q3_q4"]["q4"]["expenses"]
        computed = _compute_quarterly_expenses("20260101", "20260331")

        for ledger in ["Rent", "Salaries", "Electricity", "Internet & Phone",
                       "Office Maintenance", "Travel & Conveyance"]:
            assert computed.get(ledger, 0) == golden_q4[ledger], f"Q4 {ledger} mismatch"
        total = sum(computed.values())
        assert total == golden_q4["total"]

    def test_q3_gross_profit_matches_golden(self, golden_data):
        """Q3 gross profit = revenue - purchases."""
        golden_q3 = golden_data["quarterly_comparison_q3_q4"]["q3"]
        computed_revenue = sum(_compute_quarterly_revenue("20251001", "20251231").values())
        computed_purchases = sum(_compute_quarterly_purchases("20251001", "20251231").values())
        assert computed_revenue - computed_purchases == golden_q3["gross_profit"]

    def test_q4_gross_profit_matches_golden(self, golden_data):
        """Q4 gross profit = revenue - purchases."""
        golden_q4 = golden_data["quarterly_comparison_q3_q4"]["q4"]
        computed_revenue = sum(_compute_quarterly_revenue("20260101", "20260331").values())
        computed_purchases = sum(_compute_quarterly_purchases("20260101", "20260331").values())
        assert computed_revenue - computed_purchases == golden_q4["gross_profit"]

    def test_all_quarters_revenue_equals_full_year_pnl(self, golden_data):
        """Q1+Q2+Q3+Q4 revenue should equal full-year P&L revenue."""
        # Q1: Apr-Jun 2025, Q2: Jul-Sep 2025, Q3: Oct-Dec 2025, Q4: Jan-Mar 2026
        q1_revenue = sum(_compute_quarterly_revenue("20250401", "20250630").values())
        q2_revenue = sum(_compute_quarterly_revenue("20250701", "20250930").values())
        q3_revenue = sum(_compute_quarterly_revenue("20251001", "20251231").values())
        q4_revenue = sum(_compute_quarterly_revenue("20260101", "20260331").values())

        total_quarterly = q1_revenue + q2_revenue + q3_revenue + q4_revenue

        # Full-year P&L revenue from golden file
        pnl_rows = golden_data["profit_and_loss"]["rows"]
        sales_row = next(r for r in pnl_rows if r["account_name"] == "Sales Accounts")
        full_year_revenue = sales_row["credit_amount"]

        assert total_quarterly == full_year_revenue, (
            f"Quarterly sum {total_quarterly} != P&L revenue {full_year_revenue}"
        )

    def test_q3_q4_net_profit_matches_golden(self, golden_data):
        """Net profit = gross_profit - expenses for each quarter."""
        for qkey, start, end in [("q3", "20251001", "20251231"), ("q4", "20260101", "20260331")]:
            golden_q = golden_data["quarterly_comparison_q3_q4"][qkey]
            revenue = sum(_compute_quarterly_revenue(start, end).values())
            purchases = sum(_compute_quarterly_purchases(start, end).values())
            expenses = sum(_compute_quarterly_expenses(start, end).values())
            net_profit = revenue - purchases - expenses
            assert net_profit == golden_q["net_profit"], (
                f"{qkey} net profit: computed {net_profit} != golden {golden_q['net_profit']}"
            )
