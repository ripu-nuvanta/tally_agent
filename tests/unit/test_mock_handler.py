"""Tests for the in-process mock Tally handler."""

import pytest
from backend.tally_bridge.mock_handler import mock_tally_request, REPORT_FIXTURES


class TestMockHandler:
    """Test pattern matching and fixture loading."""

    def test_report_fixtures_mapping_exists(self):
        """All expected report types are mapped."""
        expected = [
            "List of Companies", "Trial Balance", "CustomLedgerList",
            "Profit and Loss", "Balance Sheet", "Bills Receivable",
            "Bills Payable", "Stock Summary", "DayBookVchs",
            "SalesVchs", "PurchaseVchs", "LedgerVchs",
        ]
        for name in expected:
            assert name in REPORT_FIXTURES, f"Missing fixture for {name}"

    def test_company_list_request(self):
        xml = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "<COMPANY>" in result
        assert "Bharat Traders" in result

    def test_trial_balance_request(self):
        xml = '<ENVELOPE><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>Trial Balance</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result
        assert len(result) > 100

    def test_profit_and_loss_request(self):
        xml = '<REPORTNAME>Profit and Loss</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_balance_sheet_request(self):
        xml = '<REPORTNAME>Balance Sheet</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_sales_register_request(self):
        xml = '<COLLECTION>SalesVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_purchase_register_request(self):
        xml = '<COLLECTION>PurchaseVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_day_book_request(self):
        xml = '<COLLECTION>DayBookVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_bills_receivable_request(self):
        xml = '<REPORTNAME>Bills Receivable</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_stock_summary_request(self):
        xml = '<REPORTNAME>Stock Summary</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_ledger_list_request(self):
        xml = '<COLLECTION>CustomLedgerList</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_unknown_request_returns_error(self):
        xml = '<ENVELOPE><BODY>Something Unknown</BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "Unknown request" in result

    def test_all_fixtures_return_valid_xml(self):
        """Every fixture response should start with < (valid XML)."""
        for report_name in REPORT_FIXTURES:
            xml = f'<REPORTNAME>{report_name}</REPORTNAME>'
            result = mock_tally_request(xml)
            assert result.strip().startswith("<"), f"Invalid XML for {report_name}"
