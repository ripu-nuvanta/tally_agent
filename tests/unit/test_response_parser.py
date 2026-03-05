import os
import pytest
from backend.tally_bridge.response_parser import (
    parse_amount, parse_trial_balance, parse_ledger_list, detect_error,
    parse_profit_and_loss, parse_balance_sheet, parse_stock_summary,
    parse_bills, sanitize_xml,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")

def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# parse_amount — utility, unchanged
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Trial Balance — real Tally XML (DSPACCNAME + sibling DSPACCINFO)
# ---------------------------------------------------------------------------
class TestParseTrialBalance:
    @pytest.fixture
    def rows(self):
        return parse_trial_balance(_read_fixture("trial_balance.xml"))

    def test_returns_all_rows(self, rows):
        assert len(rows) == 7

    def test_account_names(self, rows):
        names = [r["account_name"] for r in rows]
        assert "Capital Account" in names
        assert "Current Liabilities" in names
        assert "Fixed Assets" in names
        assert "Current Assets" in names
        assert "Sales Accounts" in names
        assert "Purchase Accounts" in names
        assert "Indirect Expenses" in names

    def test_capital_account_credit(self, rows):
        capital = next(r for r in rows if r["account_name"] == "Capital Account")
        assert capital["debit_amount"] == 0.0
        assert capital["credit_amount"] == 100000.0
        assert capital["closing_balance"] == 100000.0

    def test_current_liabilities_both_amounts(self, rows):
        cl = next(r for r in rows if r["account_name"] == "Current Liabilities")
        assert cl["debit_amount"] == -279384.87
        assert cl["credit_amount"] == 55856.21
        assert cl["closing_balance"] == pytest.approx(-223528.66)

    def test_fixed_assets_debit_only(self, rows):
        fa = next(r for r in rows if r["account_name"] == "Fixed Assets")
        assert fa["debit_amount"] == -208496.0
        assert fa["credit_amount"] == 0.0
        assert fa["closing_balance"] == -208496.0

    def test_sales_accounts_credit(self, rows):
        sales = next(r for r in rows if r["account_name"] == "Sales Accounts")
        assert sales["debit_amount"] == 0.0
        assert sales["credit_amount"] == 3764350.0
        assert sales["closing_balance"] == 3764350.0

    def test_purchase_accounts_debit(self, rows):
        purchase = next(r for r in rows if r["account_name"] == "Purchase Accounts")
        assert purchase["debit_amount"] == -32181.61
        assert purchase["credit_amount"] == 0.0
        assert purchase["closing_balance"] == -32181.61

    def test_indirect_expenses_small_credit(self, rows):
        ie = next(r for r in rows if r["account_name"] == "Indirect Expenses")
        assert ie["debit_amount"] == -2351297.74
        assert ie["credit_amount"] == 0.54
        assert ie["closing_balance"] == pytest.approx(-2351297.20)

    def test_closing_balance_is_float(self, rows):
        for row in rows:
            assert isinstance(row["closing_balance"], float)
            assert isinstance(row["debit_amount"], float)
            assert isinstance(row["credit_amount"], float)

    def test_empty_xml_returns_empty(self):
        rows = parse_trial_balance("<ENVELOPE></ENVELOPE>")
        assert rows == []


# ---------------------------------------------------------------------------
# Profit & Loss — real Tally XML (DSPACCNAME + sibling PLAMT)
# ---------------------------------------------------------------------------
class TestParseProfitAndLoss:
    @pytest.fixture
    def rows(self):
        return parse_profit_and_loss(_read_fixture("profit_and_loss.xml"))

    def test_returns_all_rows(self, rows):
        assert len(rows) == 6

    def test_sales_accounts(self, rows):
        sales = next(r for r in rows if r["account_name"] == "Sales Accounts")
        assert sales["closing_balance"] == 3764350.0
        assert sales["credit_amount"] == 3764350.0
        assert sales["debit_amount"] == 0.0

    def test_cost_of_sales(self, rows):
        cos = next(r for r in rows if r["account_name"] == "Cost of Sales :")
        assert cos["closing_balance"] == -32181.61
        assert cos["debit_amount"] == -32181.61
        assert cos["credit_amount"] == 0.0

    def test_opening_stock_empty(self, rows):
        opening = next(r for r in rows if r["account_name"] == "Opening Stock")
        assert opening["closing_balance"] == 0.0
        assert opening["debit_amount"] == 0.0
        assert opening["credit_amount"] == 0.0

    def test_sub_item_uses_plsubamt(self, rows):
        """When BSMAINAMT is empty, parser should fall back to PLSUBAMT."""
        purchase = next(r for r in rows if r["account_name"] == "Add: Purchase Accounts")
        assert purchase["closing_balance"] == -32181.61
        assert purchase["debit_amount"] == -32181.61

    def test_indirect_expenses(self, rows):
        ie = next(r for r in rows if r["account_name"] == "Indirect Expenses")
        assert ie["closing_balance"] == -2351297.20
        assert ie["debit_amount"] == -2351297.20
        assert ie["credit_amount"] == 0.0

    def test_closing_balance_is_float(self, rows):
        for row in rows:
            assert isinstance(row["closing_balance"], float)

    def test_empty_xml_returns_empty(self):
        rows = parse_profit_and_loss("<ENVELOPE></ENVELOPE>")
        assert rows == []


# ---------------------------------------------------------------------------
# Balance Sheet — real Tally XML (BSNAME + sibling BSAMT)
# ---------------------------------------------------------------------------
class TestParseBalanceSheet:
    @pytest.fixture
    def rows(self):
        return parse_balance_sheet(_read_fixture("balance_sheet.xml"))

    def test_returns_all_rows(self, rows):
        assert len(rows) == 7

    def test_capital_account(self, rows):
        capital = next(r for r in rows if r["account_name"] == "Capital Account")
        assert capital["closing_balance"] == 100000.0
        assert capital["credit_amount"] == 100000.0
        assert capital["debit_amount"] == 0.0

    def test_loans_liability_empty(self, rows):
        loans = next(r for r in rows if r["account_name"] == "Loans (Liability)")
        assert loans["closing_balance"] == 0.0

    def test_current_liabilities(self, rows):
        cl = next(r for r in rows if r["account_name"] == "Current Liabilities")
        assert cl["closing_balance"] == -223528.66
        assert cl["debit_amount"] == -223528.66

    def test_profit_and_loss_account(self, rows):
        pnl = next(r for r in rows if r["account_name"] == "Profit & Loss A/c")
        assert pnl["closing_balance"] == 1380871.19
        assert pnl["credit_amount"] == 1380871.19

    def test_fixed_assets(self, rows):
        fa = next(r for r in rows if r["account_name"] == "Fixed Assets")
        assert fa["closing_balance"] == -208496.0
        assert fa["debit_amount"] == -208496.0

    def test_current_assets(self, rows):
        ca = next(r for r in rows if r["account_name"] == "Current Assets")
        assert ca["closing_balance"] == -1048846.53
        assert ca["debit_amount"] == -1048846.53

    def test_closing_balance_is_float(self, rows):
        for row in rows:
            assert isinstance(row["closing_balance"], float)

    def test_empty_xml_returns_empty(self):
        rows = parse_balance_sheet("<ENVELOPE></ENVELOPE>")
        assert rows == []


# ---------------------------------------------------------------------------
# Stock Summary — real Tally XML (DSPACCNAME + sibling DSPSTKINFO)
# ---------------------------------------------------------------------------
class TestParseStockSummary:
    @pytest.fixture
    def items(self):
        return parse_stock_summary(_read_fixture("stock_summary.xml"))

    def test_returns_all_items(self, items):
        assert len(items) == 5

    def test_item_names(self, items):
        names = [i["name"] for i in items]
        assert "Data Cleaning and Matching Application Software" in names
        assert "IT Project Technical Consulting" in names
        assert "IT Project Technical Consulting(WITHOUT GST)" in names
        assert "Smartbike Software Development Technical Services" in names
        assert "Website Design and App Development" in names

    def test_quantity_parsing(self, items):
        first = next(i for i in items if i["name"] == "Data Cleaning and Matching Application Software")
        assert first["closing_quantity"] == -1.0

    def test_quantity_negative_values(self, items):
        consulting = next(i for i in items if i["name"] == "IT Project Technical Consulting")
        assert consulting["closing_quantity"] == -2.0
        no_gst = next(i for i in items if "WITHOUT GST" in i["name"])
        assert no_gst["closing_quantity"] == -154.0

    def test_base_units_parsed(self, items):
        for item in items:
            assert item["base_units"] == "NOS"

    def test_empty_rate_and_value(self, items):
        for item in items:
            assert item["closing_rate"] == 0.0
            assert item["closing_value"] == 0.0

    def test_parent_group_empty_for_data_report(self, items):
        for item in items:
            assert item["parent_group"] == ""

    def test_empty_xml_returns_empty(self):
        items = parse_stock_summary("<ENVELOPE></ENVELOPE>")
        assert items == []


# ---------------------------------------------------------------------------
# Bills Receivable — real Tally XML
# ---------------------------------------------------------------------------
class TestParseBillsReceivable:
    @pytest.fixture
    def bills(self):
        return parse_bills(_read_fixture("bills_receivable_live.xml"))

    def test_returns_all_bills(self, bills):
        assert len(bills) == 12

    def test_first_bill(self, bills):
        first = bills[0]
        assert first["bill_number"] == "#1"
        assert first["party_name"] == "HCODE TECHNOLOGIES PRIVATE LIMITED"
        assert first["amount"] == 200000.0
        assert first["bill_date"] == "2-Jul-25"
        assert first["due_date"] == "2-Jul-25"
        assert first["overdue_days"] == "272"

    def test_smartbike_bill(self, bills):
        sb = next(b for b in bills if b["party_name"] == "SMARTBIKE MOBILITY PRIVATE LIMITED" and b["bill_number"] == "7")
        assert sb["amount"] == 300000.0

    def test_last_bill(self, bills):
        last = bills[-1]
        assert last["bill_number"] == "#12"
        assert last["party_name"] == "SMARTBIKE TECH PRIVATE LIMITED"
        assert last["amount"] == 354000.0


# ---------------------------------------------------------------------------
# Bills Payable — real Tally XML
# ---------------------------------------------------------------------------
class TestParseBillsPayable:
    @pytest.fixture
    def bills(self):
        return parse_bills(_read_fixture("bills_payable_live.xml"))

    def test_returns_one_bill(self, bills):
        assert len(bills) == 1

    def test_anthropic_bill(self, bills):
        bill = bills[0]
        assert bill["bill_number"] == "6ZBO7JXW-0003"
        assert bill["party_name"] == "Anthropic, PBC"
        assert bill["amount"] == 2096.86
        assert bill["due_date"] == "26-Sep-25"
        assert bill["overdue_days"] == "186"


# ---------------------------------------------------------------------------
# Ledger List — unchanged (working correctly)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# detect_error — unchanged (working correctly)
# ---------------------------------------------------------------------------
class TestDetectError:
    def test_detect_error_response(self):
        error = detect_error(_read_fixture("error_response.xml"))
        assert error is not None
        assert "Company not loaded" in error
    def test_no_error_in_valid(self):
        error = detect_error(_read_fixture("trial_balance.xml"))
        assert error is None


# ---------------------------------------------------------------------------
# Inline XML tests — updated to use real Tally structure
# ---------------------------------------------------------------------------
class TestClosingBalanceParsing:
    """Verify closing_balance is parsed correctly from real Tally XML structure."""

    def test_trial_balance_closing_balance_is_float(self):
        xml = """<ENVELOPE>
        <DSPACCNAME>
            <DSPDISPNAME>Cash</DSPDISPNAME>
        </DSPACCNAME>
        <DSPACCINFO>
            <DSPCLDRAMT><DSPCLDRAMTA>-1000.00</DSPCLDRAMTA></DSPCLDRAMT>
            <DSPCLCRAMT><DSPCLCRAMTA></DSPCLCRAMTA></DSPCLCRAMT>
        </DSPACCINFO>
        </ENVELOPE>"""
        rows = parse_trial_balance(xml)
        assert len(rows) == 1
        assert isinstance(rows[0]["closing_balance"], float)
        assert rows[0]["closing_balance"] == -1000.0
        assert rows[0]["debit_amount"] == -1000.0

    def test_trial_balance_credit_only(self):
        xml = """<ENVELOPE>
        <DSPACCNAME>
            <DSPDISPNAME>Sales</DSPDISPNAME>
        </DSPACCNAME>
        <DSPACCINFO>
            <DSPCLDRAMT><DSPCLDRAMTA></DSPCLDRAMTA></DSPCLDRAMT>
            <DSPCLCRAMT><DSPCLCRAMTA>123456.00</DSPCLCRAMTA></DSPCLCRAMT>
        </DSPACCINFO>
        </ENVELOPE>"""
        rows = parse_trial_balance(xml)
        assert rows[0]["closing_balance"] == 123456.0
        assert rows[0]["credit_amount"] == 123456.0
        assert rows[0]["debit_amount"] == 0.0

    def test_trial_balance_empty_returns_zero(self):
        xml = """<ENVELOPE>
        <DSPACCNAME>
            <DSPDISPNAME>Empty Account</DSPDISPNAME>
        </DSPACCNAME>
        <DSPACCINFO>
            <DSPCLDRAMT><DSPCLDRAMTA></DSPCLDRAMTA></DSPCLDRAMT>
            <DSPCLCRAMT><DSPCLCRAMTA></DSPCLCRAMTA></DSPCLCRAMT>
        </DSPACCINFO>
        </ENVELOPE>"""
        rows = parse_trial_balance(xml)
        assert rows[0]["closing_balance"] == 0.0

    def test_profit_and_loss_inline(self):
        xml = """<ENVELOPE>
        <DSPACCNAME>
            <DSPDISPNAME>Revenue</DSPDISPNAME>
        </DSPACCNAME>
        <PLAMT>
            <PLSUBAMT></PLSUBAMT>
            <BSMAINAMT>500000.00</BSMAINAMT>
        </PLAMT>
        </ENVELOPE>"""
        rows = parse_profit_and_loss(xml)
        assert isinstance(rows[0]["closing_balance"], float)
        assert rows[0]["closing_balance"] == 500000.0
        assert rows[0]["credit_amount"] == 500000.0

    def test_balance_sheet_inline(self):
        xml = """<ENVELOPE>
        <BSNAME>
            <DSPACCNAME>
                <DSPDISPNAME>Assets</DSPDISPNAME>
            </DSPACCNAME>
        </BSNAME>
        <BSAMT>
            <BSSUBAMT></BSSUBAMT>
            <BSMAINAMT>-1000000.00</BSMAINAMT>
        </BSAMT>
        </ENVELOPE>"""
        rows = parse_balance_sheet(xml)
        assert isinstance(rows[0]["closing_balance"], float)
        assert rows[0]["closing_balance"] == -1000000.0
        assert rows[0]["debit_amount"] == -1000000.0

    def test_stock_summary_inline(self):
        xml = """<ENVELOPE>
        <DSPACCNAME>
            <DSPDISPNAME>Widget A</DSPDISPNAME>
        </DSPACCNAME>
        <DSPSTKINFO>
            <DSPSTKCL>
                <DSPCLQTY>10.0000 PCS</DSPCLQTY>
                <DSPCLRATE>150.00</DSPCLRATE>
                <DSPCLAMTA>1500.00</DSPCLAMTA>
            </DSPSTKCL>
        </DSPSTKINFO>
        </ENVELOPE>"""
        items = parse_stock_summary(xml)
        assert len(items) == 1
        assert items[0]["name"] == "Widget A"
        assert items[0]["closing_quantity"] == 10.0
        assert items[0]["base_units"] == "PCS"
        assert items[0]["closing_rate"] == 150.0
        assert items[0]["closing_value"] == 1500.0


# ---------------------------------------------------------------------------
# sanitize_xml — unchanged (working correctly)
# ---------------------------------------------------------------------------
class TestSanitizeXml:
    """Verify sanitize_xml is importable as a public function (Issue #13)."""

    def test_strips_control_characters(self):
        raw = '<ROOT><NAME>Test&#4; Value</NAME></ROOT>'
        cleaned = sanitize_xml(raw)
        assert "&#4;" not in cleaned
        assert "<ROOT>" in cleaned

    def test_preserves_valid_xml(self):
        raw = '<ROOT><NAME>Hello World</NAME></ROOT>'
        assert sanitize_xml(raw) == raw
