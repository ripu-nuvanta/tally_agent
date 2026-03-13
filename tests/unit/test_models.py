from datetime import date
from backend.tally_bridge.models import (Company, Ledger, TrialBalanceRow, VoucherEntry, ReportResponse, OutstandingBill)

def test_company_minimal():
    c = Company(name="Bharat Traders Pvt Ltd")
    assert c.name == "Bharat Traders Pvt Ltd"
    assert c.fy_start is None

def test_company_with_fy():
    c = Company(name="Test Co", fy_start=date(2025, 4, 1), fy_end=date(2026, 3, 31))
    assert c.fy_start == date(2025, 4, 1)

def test_ledger_defaults():
    l = Ledger(name="Cash", parent_group="Cash-in-Hand")
    assert l.closing_balance == 0.0
    assert l.opening_balance == 0.0

def test_ledger_with_balances():
    l = Ledger(name="HDFC Bank", parent_group="Bank Accounts", closing_balance=-500000.0, opening_balance=-200000.0)
    assert l.closing_balance == -500000.0

def test_trial_balance_row_defaults():
    r = TrialBalanceRow(account_name="Sales Accounts")
    assert r.debit_amount == 0.0
    assert r.credit_amount == 0.0
    assert r.closing_balance == 0.0

def test_voucher_entry():
    v = VoucherEntry(date=date(2025, 10, 1), voucher_type="Sales", voucher_number="S001", ledger_name="Sales - Electronics", amount=94000.0, party_name="Apex Technologies Pvt Ltd")
    assert v.party_name == "Apex Technologies Pvt Ltd"
    assert v.narration is None

def test_report_response():
    r = ReportResponse(report_name="Trial Balance", company="Bharat Traders", rows=[{"account_name": "Cash", "closing_balance": 50000}])
    assert len(r.rows) == 1
    assert r.from_date is None

def test_outstanding_bill():
    b = OutstandingBill(party_name="Apex Technologies Pvt Ltd", bill_number="S001", bill_date=date(2025, 10, 1), amount=94000.0, pending_amount=40000.0)
    assert b.due_date is None
    assert b.pending_amount == 40000.0

def test_outstanding_bill_has_overdue_days():
    bill = OutstandingBill(
        party_name="Test", bill_number="B001", bill_date=date(2025, 10, 1),
        amount=10000, pending_amount=10000, overdue_days=45,
    )
    assert bill.overdue_days == 45

def test_outstanding_bill_overdue_days_default_none():
    bill = OutstandingBill(
        party_name="Test", bill_number="B001", bill_date=date(2025, 10, 1),
        amount=10000, pending_amount=10000,
    )
    assert bill.overdue_days is None
