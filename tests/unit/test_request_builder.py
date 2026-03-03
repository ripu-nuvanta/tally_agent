from backend.tally_bridge.request_builder import (
    build_list_companies, build_list_ledgers, build_list_groups, build_list_stock_items,
    build_trial_balance, build_profit_and_loss, build_balance_sheet,
    build_bills_receivable, build_bills_payable, build_stock_summary,
    build_day_book, build_ledger_vouchers, build_sales_register, build_purchase_register,
)


class TestMasterBuilders:
    def test_list_companies_has_envelope(self):
        xml = build_list_companies()
        assert "<ENVELOPE>" in xml and "</ENVELOPE>" in xml

    def test_list_companies_has_export_request(self):
        xml = build_list_companies()
        assert "<TALLYREQUEST>Export</TALLYREQUEST>" in xml

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

    def test_day_book_report_id(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "Day Book" in xml

    def test_day_book_with_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="Sales")
        assert "Sales" in xml

    def test_day_book_without_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "VOUCHERTYPENAME" not in xml

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
