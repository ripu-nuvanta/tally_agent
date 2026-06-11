"""Tests for multi-currency + 5-type classification in document parser."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.services.document_parser import (
    ExtractedDocument,
    build_vision_prompt,
    parse_vision_response,
    validate_extracted_amounts,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "vision"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParseMultiType:
    """parse_vision_response handles all 5 doc types + multi-currency."""

    def test_payment_inr(self):
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        assert doc.doc_type == "payment"
        assert doc.party_name == "Uber"
        assert doc.original_currency == "INR"
        assert doc.fx_rate is None
        assert doc.inr_amount == doc.total_amount

    def test_purchase_usd_with_rate(self):
        doc = parse_vision_response(_load("purchase_saas_usd.json"))
        assert doc.doc_type == "purchase"
        assert doc.party_name == "Anthropic PBC"
        assert doc.original_currency == "USD"
        assert doc.fx_rate == Decimal("83.46")
        expected_inr = Decimal("1730.00") * Decimal("83.46")
        assert abs(doc.inr_amount - expected_inr) < Decimal("1.00")

    def test_purchase_usd_no_rate(self):
        doc = parse_vision_response(_load("purchase_saas_usd_no_rate.json"))
        assert doc.doc_type == "purchase"
        assert doc.original_currency == "USD"
        assert doc.fx_rate is None
        # inr_amount should equal total_amount when no rate (no conversion possible)
        assert doc.inr_amount == doc.total_amount

    def test_purchase_inr_multiline(self):
        doc = parse_vision_response(_load("purchase_office_inr.json"))
        assert doc.doc_type == "purchase"
        assert len(doc.line_items) == 2
        assert doc.original_currency == "INR"

    def test_purchase_interstate_igst(self):
        doc = parse_vision_response(_load("purchase_interstate_inr.json"))
        assert doc.gst is not None
        assert doc.gst.igst_amount == Decimal("3600.00")
        assert doc.gst.cgst_amount is None

    def test_sales_inr(self):
        doc = parse_vision_response(_load("sales_service_inr.json"))
        assert doc.doc_type == "sales"
        assert doc.party_name == "Infosys Ltd"

    def test_sales_eur_export(self):
        doc = parse_vision_response(_load("sales_service_eur.json"))
        assert doc.doc_type == "sales"
        assert doc.original_currency == "EUR"
        assert doc.fx_rate == Decimal("90.25")
        assert doc.gst is None

    def test_debit_note_with_ref(self):
        doc = parse_vision_response(_load("debit_note_return_inr.json"))
        assert doc.doc_type == "debit_note"
        assert doc.original_invoice_ref == "CRO-2026-5678"

    def test_credit_note_with_ref(self):
        doc = parse_vision_response(_load("credit_note_return_inr.json"))
        assert doc.doc_type == "credit_note"
        assert doc.original_invoice_ref == "INV-2026-FEB-001"

    def test_debit_note_no_ref(self):
        doc = parse_vision_response(_load("debit_note_no_ref.json"))
        assert doc.doc_type == "debit_note"
        assert doc.original_invoice_ref is None

    def test_party_name_backward_compat(self):
        """vendor_name still works as alias for party_name."""
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        assert doc.vendor_name == doc.party_name

    def test_invoice_number_captured(self):
        """A plain invoice's OWN number is captured into invoice_number."""
        doc = parse_vision_response(_load("purchase_office_inr.json"))
        assert doc.invoice_number == "CRO-2026-5678"

    def test_invoice_number_distinct_from_original_ref(self):
        """invoice_number (doc's own no) is separate from original_invoice_ref."""
        resp = json.dumps({
            "doc_type": "purchase",
            "party_name": "Acme",
            "date": "2026-02-10",
            "total_amount": 100,
            "invoice_number": "OWN-123",
            "original_invoice_ref": "AGAINST-999",
        })
        doc = parse_vision_response(resp)
        assert doc.invoice_number == "OWN-123"
        assert doc.original_invoice_ref == "AGAINST-999"

    def test_invoice_number_defaults_none_when_absent(self):
        resp = json.dumps({
            "doc_type": "payment", "party_name": "X", "date": "2026-01-01",
            "total_amount": 10,
        })
        doc = parse_vision_response(resp)
        assert doc.invoice_number is None


class TestVisionPromptMultiType:
    """Updated Vision prompt includes multi-currency + 5-type classification."""

    def test_prompt_includes_all_doc_types(self):
        prompt = build_vision_prompt()
        for t in ["payment", "purchase", "sales", "debit_note", "credit_note"]:
            assert t in prompt

    def test_prompt_includes_currency_fields(self):
        prompt = build_vision_prompt()
        assert "original_currency" in prompt
        assert "fx_rate" in prompt

    def test_prompt_includes_invoice_ref(self):
        prompt = build_vision_prompt()
        assert "original_invoice_ref" in prompt

    def test_prompt_includes_invoice_number(self):
        """Prompt asks for the document's OWN invoice number distinctly."""
        prompt = build_vision_prompt()
        assert "invoice_number" in prompt

    def test_prompt_original_invoice_ref_scoped_to_dn_cn(self):
        """original_invoice_ref description tightened to DN/CN only, not own number."""
        prompt = build_vision_prompt()
        # The schema line for original_invoice_ref must scope it to debit/credit
        # notes and explicitly say it is NOT this document's own number.
        assert "NOT this document's own number" in prompt


class TestValidateFX:
    """validate_extracted_amounts handles FX scenarios."""

    def test_inr_no_warnings(self):
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        warnings = validate_extracted_amounts(doc)
        assert len(warnings) == 0

    def test_usd_with_rate_no_warnings(self):
        doc = parse_vision_response(_load("purchase_saas_usd.json"))
        warnings = validate_extracted_amounts(doc)
        # GST math may not perfectly reconcile due to the fixture being USD
        # but no FX-specific warning expected since rate is present
        fx_warnings = [w for w in warnings if "estimated" in w.lower() or "fx" in w.lower()]
        assert len(fx_warnings) == 0

    def test_usd_no_rate_warns(self):
        doc = parse_vision_response(_load("purchase_saas_usd_no_rate.json"))
        warnings = validate_extracted_amounts(doc)
        fx_warnings = [w for w in warnings if "rate" in w.lower() or "verify" in w.lower()]
        assert len(fx_warnings) >= 1
