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
