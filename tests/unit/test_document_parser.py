"""Tests for document parser — file routing, extraction, validation."""
import json
from decimal import Decimal

import pytest

from backend.services.document_parser import (
    ExtractedDocument,
    GSTBreakdown,
    LineItem,
    detect_file_type,
    validate_extracted_amounts,
    build_vision_prompt,
    parse_vision_response,
)


class TestFileTypeDetection:
    def test_csv(self):
        assert detect_file_type("statement.csv", "text/csv") == "structured"

    def test_xlsx(self):
        assert detect_file_type(
            "report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ) == "structured"

    def test_jpg(self):
        assert detect_file_type("receipt.jpg", "image/jpeg") == "vision"

    def test_png(self):
        assert detect_file_type("receipt.png", "image/png") == "vision"

    def test_pdf(self):
        assert detect_file_type("invoice.pdf", "application/pdf") == "vision"

    def test_unknown(self):
        assert detect_file_type("doc.docx", "application/msword") == "unsupported"


class TestVisionPrompt:
    def test_prompt_includes_instructions(self):
        prompt = build_vision_prompt()
        assert "vendor" in prompt.lower()
        assert "amount" in prompt.lower()
        assert "date" in prompt.lower()
        assert "json" in prompt.lower()
        assert "GST" in prompt or "gst" in prompt

    def test_prompt_drops_inr_mandate(self):
        """Prompt must no longer force amounts into INR."""
        prompt = build_vision_prompt()
        assert "All amounts in INR" not in prompt

    def test_prompt_asks_for_currency_and_fx_rate(self):
        prompt = build_vision_prompt()
        assert "currency" in prompt.lower()
        assert "fx_rate" in prompt.lower()

    def test_prompt_says_do_not_convert(self):
        prompt = build_vision_prompt()
        lower = prompt.lower()
        assert "original currency" in lower
        assert "not convert" in lower or "do not convert" in lower

    def test_prompt_asks_for_line_item_unit(self):
        """Per-line schema must include a unit field (inventory Phase 2)."""
        prompt = build_vision_prompt()
        assert '"unit"' in prompt


class TestParseVisionResponse:
    def test_basic_expense(self):
        response_json = json.dumps({
            "doc_type": "expense",
            "vendor_name": "Uber",
            "date": "2026-04-04",
            "total_amount": 500.00,
            "line_items": [{"description": "Ride", "amount": 500.00}],
            "gst": None,
            "payment_mode": "upi",
        })
        doc = parse_vision_response(response_json)
        assert doc.vendor_name == "Uber"
        assert doc.total_amount == Decimal("500.00")
        assert doc.doc_type == "expense"
        assert len(doc.line_items) == 1

    def test_expense_with_gst(self):
        response_json = json.dumps({
            "doc_type": "expense",
            "vendor_name": "Stationery Shop",
            "date": "2026-04-04",
            "total_amount": 1180.00,
            "line_items": [{"description": "Paper and pens", "amount": 1000.00}],
            "gst": {
                "cgst_rate": 9.0, "cgst_amount": 90.0,
                "sgst_rate": 9.0, "sgst_amount": 90.0,
            },
            "payment_mode": "cash",
        })
        doc = parse_vision_response(response_json)
        assert doc.gst is not None
        assert doc.gst.cgst_amount == Decimal("90.00")

    def test_line_item_unit_captured(self):
        """A line item's printed unit is captured onto LineItem.unit."""
        response_json = json.dumps({
            "doc_type": "purchase", "party_name": "Acme", "date": "2026-04-04",
            "total_amount": 1000.00,
            "line_items": [
                {"description": "Pens", "amount": 1000.00,
                 "quantity": 10, "rate": 100, "unit": "Pcs"},
            ],
            "gst": None, "payment_mode": None,
        })
        doc = parse_vision_response(response_json)
        assert doc.line_items[0].unit == "Pcs"

    def test_line_item_unit_null_becomes_none(self):
        """A null/absent unit parses to None (default applied later at build time)."""
        response_json = json.dumps({
            "doc_type": "purchase", "party_name": "Acme", "date": "2026-04-04",
            "total_amount": 1000.00,
            "line_items": [
                {"description": "Widget", "amount": 1000.00,
                 "quantity": 5, "rate": 200, "unit": None},
                {"description": "Gadget", "amount": 50.00, "quantity": 1, "rate": 50},
            ],
            "gst": None, "payment_mode": None,
        })
        doc = parse_vision_response(response_json)
        assert doc.line_items[0].unit is None
        assert doc.line_items[1].unit is None

    def test_strips_markdown_code_fences(self):
        """Claude sometimes wraps JSON in ```json ... ``` even when told not to."""
        response = """```json
{"doc_type":"expense","vendor_name":"Test","date":"2026-04-04","total_amount":100.00,"line_items":[{"description":"x","amount":100.00}],"gst":null,"payment_mode":null}
```"""
        doc = parse_vision_response(response)
        assert doc.vendor_name == "Test"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_vision_response("not json at all")

    def test_currency_present_captured_as_original_currency(self):
        response_json = json.dumps({
            "doc_type": "expense", "vendor_name": "AWS", "date": "2026-04-04",
            "total_amount": 100.00, "currency": "USD", "fx_rate": 83.5,
            "line_items": [{"description": "Cloud", "amount": 100.00}],
            "gst": None, "payment_mode": "card",
        })
        doc = parse_vision_response(response_json)
        assert doc.original_currency == "USD"
        assert doc.fx_rate == Decimal("83.5")

    def test_currency_absent_defaults_to_inr(self):
        response_json = json.dumps({
            "doc_type": "expense", "vendor_name": "Local", "date": "2026-04-04",
            "total_amount": 500.00,
            "line_items": [{"description": "x", "amount": 500.00}],
            "gst": None, "payment_mode": "cash",
        })
        doc = parse_vision_response(response_json)
        assert doc.original_currency == "INR"
        assert doc.fx_rate is None

    def test_lowercase_currency_uppercased(self):
        response_json = json.dumps({
            "doc_type": "expense", "vendor_name": "X", "date": "2026-04-04",
            "total_amount": 50.0, "currency": "eur", "fx_rate": None,
            "line_items": [], "gst": None, "payment_mode": None,
        })
        doc = parse_vision_response(response_json)
        assert doc.original_currency == "EUR"
        assert doc.fx_rate is None

    def test_fx_rate_null_yields_none(self):
        response_json = json.dumps({
            "doc_type": "expense", "vendor_name": "X", "date": "2026-04-04",
            "total_amount": 100.0, "currency": "USD", "fx_rate": None,
            "line_items": [], "gst": None, "payment_mode": None,
        })
        doc = parse_vision_response(response_json)
        assert doc.original_currency == "USD"
        assert doc.fx_rate is None

    def test_currency_back_compat_alias_set(self):
        """Legacy `currency` field stays populated for back-compat."""
        response_json = json.dumps({
            "doc_type": "expense", "vendor_name": "X", "date": "2026-04-04",
            "total_amount": 100.0, "currency": "usd", "fx_rate": None,
            "line_items": [], "gst": None, "payment_mode": None,
        })
        doc = parse_vision_response(response_json)
        assert doc.currency == "USD"


class TestAmountValidation:
    def test_valid_amounts(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("1180.00"),
            line_items=[LineItem(description="Item", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
        )
        warnings = validate_extracted_amounts(doc)
        assert warnings == []

    def test_mismatched_total(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("1500.00"),  # Wrong total
            line_items=[LineItem(description="Item", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
        )
        warnings = validate_extracted_amounts(doc)
        assert len(warnings) > 0
        assert any("total" in w.lower() or "sum" in w.lower() for w in warnings)

    def test_zero_amount_warning(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("0"),
            line_items=[LineItem(description="Free item", amount=Decimal("0"))],
        )
        warnings = validate_extracted_amounts(doc)
        assert any("zero" in w.lower() for w in warnings)

    def test_no_gst_no_items_match(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("500.00"),
            line_items=[LineItem(description="Item", amount=Decimal("500.00"))],
        )
        warnings = validate_extracted_amounts(doc)
        assert warnings == []

    def test_never_raises_on_float_amounts(self):
        """Hand-constructed docs with float (not Decimal) amounts must not crash."""
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=1180.0,  # float, not Decimal
            line_items=[LineItem(description="Item", amount=1000.0)],  # float
            gst=GSTBreakdown(cgst_rate=9.0, cgst_amount=90.0, sgst_rate=9.0, sgst_amount=90.0),
        )
        # Must not raise
        warnings = validate_extracted_amounts(doc)
        assert isinstance(warnings, list)

    def test_never_raises_on_none_line_items(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("100"),
            line_items=None,  # type: ignore
        )
        warnings = validate_extracted_amounts(doc)
        assert isinstance(warnings, list)

    def test_sgst_mismatch_warning(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("1180.00"),
            line_items=[LineItem(description="Item", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("50"),  # Wrong
            ),
        )
        warnings = validate_extracted_amounts(doc)
        assert any("sgst" in w.lower() for w in warnings)
