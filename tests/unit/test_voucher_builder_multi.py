"""Tests for Purchase/Sales/DN/CN voucher data-mappers (Group B Task 4).

These mappers convert an ``ExtractedDocument`` into ``VoucherData``. They inherit
the same FX-conversion behaviour as ``build_payment_voucher_data`` — the posted
``amount`` (and every GST leg) is always in INR.
"""
from decimal import Decimal
from pathlib import Path

from backend.services.document_parser import parse_vision_response
from backend.services.voucher_builder import (
    VoucherData,
    build_credit_note_data,
    build_debit_note_data,
    build_purchase_voucher_data,
    build_sales_voucher_data,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "vision"


def _load_doc(name: str):
    return parse_vision_response((FIXTURES / name).read_text())


class TestBuildPurchaseVoucher:
    def test_inr_purchase(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Office Equipment",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        assert vd.voucher_type == "Purchase"
        assert vd.party_ledger == "Croma Electronics"
        assert vd.is_party_ledger is True
        assert vd.bill_type == "New Ref"
        assert vd.amount == doc.inr_amount

    def test_usd_purchase_uses_inr_amount(self):
        doc = _load_doc("purchase_saas_usd.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Anthropic PBC",
            purchase_ledger="SaaS Subscriptions",
        )
        # Uses INR-converted amount, not the USD total.
        assert vd.original_currency.upper() == "USD"
        assert vd.amount == doc.inr_amount
        assert vd.amount != doc.total_amount
        assert vd.fx_rate == doc.fx_rate
        # FX trail appended to narration for foreign-currency docs.
        assert "USD" in vd.narration

    def test_purchase_gst_entries_input(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma",
            purchase_ledger="Purchases",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        assert len(vd.gst_entries) == 2
        ledger_names = [e["ledger"] for e in vd.gst_entries]
        assert "INPUT CGST" in ledger_names
        assert "INPUT SGST" in ledger_names


class TestBuildSalesVoucher:
    def test_inr_sales(self):
        doc = _load_doc("sales_service_inr.json")
        vd = build_sales_voucher_data(
            doc, party_ledger="Infosys Ltd",
            sales_ledger="Sales",
            gst_ledgers={"cgst_output": "OUTPUT CGST", "sgst_output": "OUTPUT SGST"},
        )
        assert vd.voucher_type == "Sales"
        assert vd.party_ledger == "Infosys Ltd"
        assert vd.is_party_ledger is True
        assert vd.bill_type == "New Ref"
        assert len(vd.gst_entries) == 2

    def test_eur_sales_uses_inr(self):
        doc = _load_doc("sales_service_eur.json")
        vd = build_sales_voucher_data(
            doc, party_ledger="Acme GmbH",
            sales_ledger="Export Sales",
        )
        assert vd.original_currency.upper() == "EUR"
        assert vd.amount == doc.inr_amount


class TestBuildDebitNote:
    def test_with_ref(self):
        doc = _load_doc("debit_note_return_inr.json")
        vd = build_debit_note_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Purchases",
            original_ref="CRO-2026-5678",
        )
        assert vd.voucher_type == "Debit Note"
        assert vd.bill_reference == "CRO-2026-5678"
        assert vd.bill_type == "Agst Ref"
        assert vd.party_ledger == "Croma Electronics"
        assert vd.is_party_ledger is True

    def test_falls_back_to_doc_invoice_ref(self):
        """When original_ref is not passed, fall back to doc.original_invoice_ref."""
        doc = _load_doc("debit_note_return_inr.json")
        vd = build_debit_note_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Purchases",
        )
        assert vd.bill_reference == "CRO-2026-5678"

    def test_without_ref(self):
        doc = _load_doc("debit_note_no_ref.json")
        vd = build_debit_note_data(
            doc, party_ledger="Unknown Supplier",
            purchase_ledger="Purchases",
        )
        assert vd.bill_reference is None


class TestBuildCreditNote:
    def test_with_ref(self):
        doc = _load_doc("credit_note_return_inr.json")
        vd = build_credit_note_data(
            doc, party_ledger="Infosys Ltd",
            sales_ledger="Sales",
            original_ref="INV-2026-FEB-001",
        )
        assert vd.voucher_type == "Credit Note"
        assert vd.bill_reference == "INV-2026-FEB-001"
        assert vd.bill_type == "Agst Ref"
        assert vd.party_ledger == "Infosys Ltd"


class TestNarrationUsesPartyName:
    def test_party_name_in_narration(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Purchases",
        )
        assert "Croma Electronics" in vd.narration
