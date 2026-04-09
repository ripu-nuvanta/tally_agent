"""Tests for converting ExtractedDocument → Tally voucher payload."""
from decimal import Decimal

from backend.services.document_parser import ExtractedDocument, GSTBreakdown, LineItem
from backend.services.voucher_builder import build_payment_voucher_data, VoucherData


class TestBuildPaymentVoucher:
    def test_simple_expense(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Uber",
            date="2026-04-04",
            total_amount=Decimal("500.00"),
            line_items=[LineItem(description="Ride", amount=Decimal("500.00"))],
            payment_mode="cash",
        )
        result = build_payment_voucher_data(
            doc=doc,
            expense_ledger="Travel Expenses",
            payment_ledger="Cash",
        )
        assert result.voucher_type == "Payment"
        assert result.date == "20260404"
        assert result.amount == Decimal("500.00")
        assert result.debit_ledger == "Travel Expenses"
        assert result.credit_ledger == "Cash"
        assert "Uber" in result.narration
        assert "Ride" in result.narration
        assert result.gst_entries == []

    def test_expense_with_gst(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Stationery Shop",
            date="2026-04-04",
            total_amount=Decimal("1180.00"),
            line_items=[LineItem(description="Paper", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
            payment_mode="cash",
        )
        result = build_payment_voucher_data(
            doc=doc,
            expense_ledger="Office Supplies",
            payment_ledger="Cash",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        assert len(result.gst_entries) == 2
        ledgers = {e["ledger"] for e in result.gst_entries}
        assert "INPUT CGST" in ledgers
        assert "INPUT SGST" in ledgers
        # Each GST entry sums correctly
        assert sum(e["amount"] for e in result.gst_entries) == 180.0

    def test_date_conversion(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            line_items=[LineItem(description="Test", amount=Decimal("100.00"))],
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="Test", payment_ledger="Cash")
        assert result.date == "20260404"

    def test_narration_without_vendor(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name=None,
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            line_items=[LineItem(description="Miscellaneous expense", amount=Decimal("100.00"))],
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="Misc", payment_ledger="Cash")
        assert "Miscellaneous expense" in result.narration

    def test_narration_fallback_when_empty(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name=None,
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            line_items=[],
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="Misc", payment_ledger="Cash")
        assert result.narration  # not empty
