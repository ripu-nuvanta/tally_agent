from backend.tally_bridge.request_builder import (
    build_list_companies, build_list_ledgers, build_list_groups, build_list_stock_items,
    build_trial_balance, build_profit_and_loss, build_balance_sheet,
    build_bills_receivable, build_bills_payable, build_stock_summary,
    build_day_book, build_ledger_vouchers, build_sales_register, build_purchase_register,
    build_cash_flow,
)


# ---------------------------------------------------------------------------
# H2: AllInventoryEntries in voucher collection queries
# ---------------------------------------------------------------------------
def test_voucher_native_methods_include_inventory_entries():
    """All voucher collection queries must fetch AllInventoryEntries for item-level data."""
    xml = build_day_book("01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml


def test_sales_register_includes_inventory_entries():
    xml = build_sales_register("01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml


def test_ledger_vouchers_includes_inventory_entries():
    xml = build_ledger_vouchers("Cash", "01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml


class TestMasterBuilders:
    def test_list_companies_has_envelope(self):
        xml = build_list_companies()
        assert "<ENVELOPE>" in xml and "</ENVELOPE>" in xml

    def test_list_companies_has_export_request(self):
        xml = build_list_companies()
        assert "<TALLYREQUEST>EXPORT</TALLYREQUEST>" in xml

    def test_list_companies_has_company_collection(self):
        xml = build_list_companies()
        assert "List of Companies" in xml

    def test_list_ledgers_has_collection_type(self):
        xml = build_list_ledgers()
        assert "<TYPE>Ledger</TYPE>" in xml

    def test_list_ledgers_has_native_methods(self):
        xml = build_list_ledgers()
        assert "<NATIVEMETHOD>Name</NATIVEMETHOD>" in xml
        assert "<NATIVEMETHOD>Parent</NATIVEMETHOD>" in xml
        assert "<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>" in xml

    def test_list_groups_has_group_type(self):
        xml = build_list_groups()
        assert "<TYPE>Group</TYPE>" in xml

    def test_list_stock_items_has_stock_type(self):
        xml = build_list_stock_items()
        assert "<TYPE>StockItem</TYPE>" in xml


class TestReportBuilders:
    def test_trial_balance_dates(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_trial_balance_export_format(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "$$SysName:XML" in xml

    def test_trial_balance_report_id(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "Trial Balance" in xml

    def test_trial_balance_with_company(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026", company="ABC Pvt Ltd")
        assert "<SVCurrentCompany>ABC Pvt Ltd</SVCurrentCompany>" in xml

    def test_trial_balance_without_company(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "SVCurrentCompany" not in xml

    def test_profit_and_loss_report_id(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "Profit and Loss" in xml

    def test_profit_and_loss_dates(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_balance_sheet_date(self):
        xml = build_balance_sheet("31-03-2026")
        assert "Balance Sheet" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_bills_receivable(self):
        xml = build_bills_receivable("31-03-2026")
        assert "Bills Receivable" in xml

    def test_bills_payable(self):
        xml = build_bills_payable("31-03-2026")
        assert "Bills Payable" in xml

    def test_stock_summary(self):
        xml = build_stock_summary("31-03-2026")
        assert "Stock Summary" in xml

    def test_stock_summary_with_group(self):
        xml = build_stock_summary("31-03-2026", stock_group="Electronics")
        assert "Electronics" in xml


class TestVoucherBuilders:
    def test_day_book_dates(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>30-04-2025</SVTODATE>" in xml

    def test_day_book_collection_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "<TYPE>Collection</TYPE>" in xml
        assert "<TYPE>Voucher</TYPE>" in xml

    def test_day_book_with_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="Sales")
        assert "Sales" in xml
        assert "VchTypeFilter" in xml

    def test_day_book_without_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "VchTypeFilter" not in xml

    def test_ledger_vouchers_includes_ledger_name(self):
        xml = build_ledger_vouchers("HDFC Bank", "01-04-2025", "31-03-2026")
        assert "HDFC Bank" in xml

    def test_ledger_vouchers_dates(self):
        xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_sales_register(self):
        xml = build_sales_register("01-04-2025", "31-03-2026")
        assert "Sales" in xml
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_purchase_register(self):
        xml = build_purchase_register("01-04-2025", "31-03-2026")
        assert "Purchase" in xml


class TestXmlEscaping:
    """Issue #6: XML injection — special chars in names must be escaped."""

    def test_ledger_vouchers_escapes_ampersand(self):
        xml = build_ledger_vouchers("M/s Sharma & Sons", "01-04-2025", "31-03-2026")
        assert "&amp;" in xml
        assert "& Sons" not in xml  # raw & should not appear

    def test_ledger_vouchers_escapes_quotes(self):
        xml = build_ledger_vouchers('He said "hello"', "01-04-2025", "31-03-2026")
        assert "&quot;" in xml

    def test_ledger_vouchers_escapes_angle_brackets(self):
        xml = build_ledger_vouchers("A <B> C", "01-04-2025", "31-03-2026")
        assert "&lt;" in xml
        assert "&gt;" in xml

    def test_day_book_voucher_type_escapes_ampersand(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="Sales & Returns")
        assert "&amp;" in xml

    def test_stock_summary_group_escapes_ampersand(self):
        xml = build_stock_summary("31-03-2026", stock_group="Oil & Gas")
        assert "&amp;" in xml


class TestVoucherTypeTitleCase:
    """Issue #16: voucher_type_filter must be title-cased for Tally matching."""

    def test_day_book_voucher_type_title_cased(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="sales")
        assert '"Sales"' in xml
        assert '"sales"' not in xml

    def test_day_book_voucher_type_uppercase_normalized(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="PURCHASE")
        assert '"Purchase"' in xml
        assert '"PURCHASE"' not in xml

    def test_day_book_voucher_type_already_correct(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="Sales")
        assert '"Sales"' in xml


class TestNoInDateRange:
    """$$InDateRange is NOT a valid TDL function — must not appear in XML.
    Date filtering relies on SVFROMDATE/SVTODATE + Python-side _filter_vouchers_by_date()."""

    def test_sales_register_no_indaterange(self):
        xml = build_sales_register("01-07-2025", "31-07-2025")
        assert "InDateRange" not in xml
        assert "VchTypeFilter" in xml

    def test_day_book_no_indaterange(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "InDateRange" not in xml

    def test_sales_register_has_svfromdate(self):
        xml = build_sales_register("01-07-2025", "31-07-2025")
        assert "<SVFROMDATE>01-07-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-07-2025</SVTODATE>" in xml

    def test_day_book_no_type_no_vchfilter(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "VchTypeFilter" not in xml

    def test_ledger_vouchers_no_indaterange(self):
        xml = build_ledger_vouchers("Cash", "01-07-2025", "31-07-2025")
        assert "InDateRange" not in xml

    def test_ledger_vouchers_has_ledger_filter(self):
        xml = build_ledger_vouchers("HDFC Bank", "01-04-2025", "31-03-2026")
        assert "LedgerFilter" in xml
        assert "HDFC Bank" in xml

    def test_ledger_vouchers_has_svdates(self):
        xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml


class TestFullFYDateRange:
    """Verify all report/voucher builders handle full FY date ranges correctly."""

    def test_trial_balance_full_fy(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_profit_and_loss_full_fy(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_sales_register_full_fy(self):
        xml = build_sales_register("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "InDateRange" not in xml

    def test_purchase_register_full_fy(self):
        xml = build_purchase_register("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "InDateRange" not in xml

    def test_day_book_full_fy(self):
        xml = build_day_book("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "InDateRange" not in xml

    def test_ledger_vouchers_full_fy(self):
        xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "InDateRange" not in xml

    def test_balance_sheet_single_date(self):
        xml = build_balance_sheet("31-03-2026")
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml


def test_build_cash_flow_has_report_id():
    from backend.tally_bridge.request_builder import build_cash_flow
    xml = build_cash_flow("01-04-2025", "31-03-2026")
    assert "Cash Flow" in xml
    assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
