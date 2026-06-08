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


class TestFxConversion:
    def _usd_doc(self, total="100.00", fx_rate=None, gst=None):
        return ExtractedDocument(
            doc_type="expense",
            vendor_name="AWS",
            date="2026-04-04",
            total_amount=Decimal(total),
            line_items=[LineItem(description="Cloud", amount=Decimal(total))],
            original_currency="USD",
            currency="USD",
            fx_rate=fx_rate,
            gst=gst,
        )

    def test_inr_doc_unchanged_rate_one(self):
        """INR document: rate=1, no FX trail, amount unchanged."""
        doc = ExtractedDocument(
            doc_type="expense", vendor_name="Local", date="2026-04-04",
            total_amount=Decimal("500.00"),
            line_items=[LineItem(description="x", amount=Decimal("500.00"))],
            original_currency="INR",
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        assert result.amount == Decimal("500.00")
        assert result.original_currency == "INR"
        assert result.original_amount == Decimal("500.00")
        assert result.fx_rate == Decimal("1")
        assert result.rate_source == "inr"
        assert "FX:" not in result.narration

    def test_usd_doc_rate_converts_total(self):
        doc = self._usd_doc(total="100.00", fx_rate=Decimal("83.50"))
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        assert result.original_currency == "USD"
        assert result.original_amount == Decimal("100.00")
        assert result.fx_rate == Decimal("83.50")
        assert result.rate_source == "document"
        # 100 × 83.5 = 8350.00, rounded to 2dp
        assert result.amount == Decimal("8350.00")

    def test_usd_narration_has_fx_trail(self):
        doc = self._usd_doc(total="100.00", fx_rate=Decimal("83.50"))
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        assert "FX: USD 100.00 @ ₹83.50 = ₹8,350.00" in result.narration

    def test_override_arg_wins_over_doc_rate(self):
        doc = self._usd_doc(total="100.00", fx_rate=Decimal("83.50"))
        result = build_payment_voucher_data(
            doc=doc, expense_ledger="E", payment_ledger="Cash",
            override=Decimal("84.5"),
        )
        assert result.fx_rate == Decimal("84.5")
        assert result.rate_source == "override"
        assert result.amount == Decimal("8450.00")

    def test_per_currency_default_used(self):
        doc = self._usd_doc(total="100.00", fx_rate=None)
        result = build_payment_voucher_data(
            doc=doc, expense_ledger="E", payment_ledger="Cash",
            default_rates={"USD": 80.0}, fallback=0.0,
        )
        assert result.fx_rate == Decimal("80.0")
        assert result.rate_source == "default"
        assert result.amount == Decimal("8000.00")

    def test_no_rate_blocked_amount_zero(self):
        """Non-INR, no rate resolvable → rate 0, source 'none'."""
        doc = self._usd_doc(total="100.00", fx_rate=None)
        result = build_payment_voucher_data(
            doc=doc, expense_ledger="E", payment_ledger="Cash",
            default_rates={}, fallback=0.0,
        )
        assert result.rate_source == "none"
        assert result.fx_rate == Decimal("0")
        assert result.amount == Decimal("0.00")

    def test_gst_legs_scaled_by_rate(self):
        gst = GSTBreakdown(
            cgst_rate=Decimal("9"), cgst_amount=Decimal("9.00"),
            sgst_rate=Decimal("9"), sgst_amount=Decimal("9.00"),
        )
        doc = self._usd_doc(total="118.00", fx_rate=Decimal("80.00"), gst=gst)
        result = build_payment_voucher_data(
            doc=doc, expense_ledger="E", payment_ledger="Cash",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        # Each GST leg 9 USD × 80 = 720 INR
        amounts = sorted(e["amount"] for e in result.gst_entries)
        assert amounts == [720.0, 720.0]
        # Total 118 × 80 = 9440
        assert result.amount == Decimal("9440.00")

    def test_original_gst_entries_are_foreign_amounts(self):
        gst = GSTBreakdown(
            cgst_rate=Decimal("9"), cgst_amount=Decimal("9.00"),
            sgst_rate=Decimal("9"), sgst_amount=Decimal("9.00"),
        )
        doc = self._usd_doc(total="118.00", fx_rate=Decimal("80.00"), gst=gst)
        result = build_payment_voucher_data(
            doc=doc, expense_ledger="E", payment_ledger="Cash",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        # original_gst_entries hold the FOREIGN (pre-conversion) amounts, paired
        # to the same ledgers/order as the INR gst_entries.
        assert result.original_gst_entries == [
            {"ledger": "INPUT CGST", "amount": 9.0},
            {"ledger": "INPUT SGST", "amount": 9.0},
        ]
        # ...while gst_entries are INR (9 × 80 = 720)
        assert [e["amount"] for e in result.gst_entries] == [720.0, 720.0]

    def test_original_gst_entries_empty_when_no_gst(self):
        doc = self._usd_doc(total="100.00", fx_rate=Decimal("83.50"))
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        assert result.original_gst_entries == []

    def test_decimal_rounding_to_two_dp(self):
        doc = self._usd_doc(total="33.33", fx_rate=Decimal("83.55"))
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        # 33.33 × 83.55 = 2784.7215 → round half-up to 2dp → 2784.72
        assert result.amount == Decimal("2784.72")
        assert result.amount.as_tuple().exponent == -2  # exactly 2 dp

    def test_rounding_is_half_up(self):
        # 1 × 0.125 = 0.125 → half-up → 0.13
        doc = self._usd_doc(total="1.00", fx_rate=Decimal("0.125"))
        result = build_payment_voucher_data(doc=doc, expense_ledger="E", payment_ledger="Cash")
        assert result.amount == Decimal("0.13")
