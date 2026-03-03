import os
import pytest
from backend.tally_bridge.response_parser import (
    parse_amount, parse_trial_balance, parse_ledger_list, detect_error,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")

def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


class TestParseAmount:
    def test_normal_amount(self):
        assert parse_amount("1,23,456.78") == 123456.78
    def test_empty_string(self):
        assert parse_amount("") == 0.0
    def test_none_value(self):
        assert parse_amount(None) == 0.0
    def test_negative_amount(self):
        assert parse_amount("-1,23,456.78") == -123456.78
    def test_plain_number(self):
        assert parse_amount("50000.00") == 50000.0
    def test_whitespace(self):
        assert parse_amount("  1,000.00  ") == 1000.0


class TestParseTrialBalance:
    def test_returns_rows(self):
        rows = parse_trial_balance(_read_fixture("trial_balance.xml"))
        assert len(rows) == 3
    def test_has_account_name(self):
        rows = parse_trial_balance(_read_fixture("trial_balance.xml"))
        names = [r["account_name"] for r in rows]
        assert "Capital Account" in names
    def test_debit_credit(self):
        rows = parse_trial_balance(_read_fixture("trial_balance.xml"))
        purchase = next(r for r in rows if r["account_name"] == "Purchase Accounts")
        assert purchase["debit_amount"] == 1020000.0
        assert purchase["credit_amount"] == 0.0
    def test_empty_amount_is_zero(self):
        rows = parse_trial_balance(_read_fixture("trial_balance.xml"))
        capital = next(r for r in rows if r["account_name"] == "Capital Account")
        assert capital["debit_amount"] == 0.0


class TestParseLedgerList:
    def test_returns_list(self):
        ledgers = parse_ledger_list(_read_fixture("ledger_list.xml"))
        assert len(ledgers) == 3
    def test_fields(self):
        ledgers = parse_ledger_list(_read_fixture("ledger_list.xml"))
        hdfc = next(l for l in ledgers if "HDFC" in l["name"])
        assert hdfc["parent_group"] == "Bank Accounts"
        assert hdfc["closing_balance"] == -500000.0
    def test_empty_opening(self):
        ledgers = parse_ledger_list(_read_fixture("ledger_list.xml"))
        apex = next(l for l in ledgers if "Apex" in l["name"])
        assert apex["opening_balance"] == 0.0


class TestDetectError:
    def test_detect_error_response(self):
        error = detect_error(_read_fixture("error_response.xml"))
        assert error is not None
        assert "Company not loaded" in error
    def test_no_error_in_valid(self):
        error = detect_error(_read_fixture("trial_balance.xml"))
        assert error is None
