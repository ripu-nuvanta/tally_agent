"""Tests for Debit Note / Credit Note XML builders (Group B Task 3).

Sales/Purchase invoice builders already exist (inventory-based) and are covered
by ``tests/unit/test_import_builder.py``. This file covers only the NEW
ledger-only Debit Note / Credit Note builders, whose verified XML shape comes
from the Task 0 live probes E5/E6 (``docs/group-b-task0-probe-results-2026-06-08.md``):

  - Debit Note mirrors Purchase: party ISDEEMEDPOSITIVE=No / +amount,
    contra (purchase) ISDEEMEDPOSITIVE=Yes / -amount.
  - Credit Note mirrors Sales:   party ISDEEMEDPOSITIVE=Yes / -amount,
    contra (sales)    ISDEEMEDPOSITIVE=No / +amount.
  - Both use LEDGERENTRIES.LIST + Invoice Voucher View + ISPARTYLEDGER + Agst Ref.
"""
import xml.etree.ElementTree as ET

import pytest

from backend.tally_bridge.import_builder import (
    build_create_credit_note,
    build_create_debit_note,
)


def _parse(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


def _voucher(xml_str: str) -> ET.Element:
    root = _parse(xml_str)
    return root.find(".//VOUCHER")


def _party_entry(v: ET.Element) -> ET.Element:
    return [
        e for e in v.findall("LEDGERENTRIES.LIST")
        if e.find("ISPARTYLEDGER") is not None
        and e.find("ISPARTYLEDGER").text == "Yes"
    ][0]


class TestCreateDebitNote:
    def test_basic_structure(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=4718.0,
            narration="Return", company="Test Co",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Debit Note"
        assert v.get("ACTION") == "Create"
        assert v.find("VOUCHERTYPENAME").text == "Debit Note"
        assert v.find("DATE").text == "20260305"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"
        assert v.find("ISINVOICE").text == "Yes"

    def test_party_ledger_has_ispartyledger(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=1000.0,
            narration="Return", company="Test Co",
        )
        v = _voucher(xml)
        party = _party_entry(v)
        assert party.find("LEDGERNAME").text == "Croma"

    def test_debit_note_sign_mirrors_purchase(self):
        """DN party = credit side (No / +amount); contra = debit (Yes / -amount)."""
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=1000.0,
            narration="Return", company="Test Co",
        )
        v = _voucher(xml)
        party = _party_entry(v)
        assert party.find("ISDEEMEDPOSITIVE").text == "No"
        assert float(party.find("AMOUNT").text) > 0
        contra = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is None
            and "Purchases" in (e.find("LEDGERNAME").text or "")
        ][0]
        assert contra.find("ISDEEMEDPOSITIVE").text == "Yes"
        assert float(contra.find("AMOUNT").text) < 0

    def test_debit_note_agst_ref(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=1000.0,
            narration="Return", company="Test Co",
            bill_ref="CRO-2026-5678",
        )
        v = _voucher(xml)
        bill = _party_entry(v).find("BILLALLOCATIONS.LIST")
        assert bill is not None
        assert bill.find("BILLTYPE").text == "Agst Ref"
        assert bill.find("NAME").text == "CRO-2026-5678"
        # Bill alloc amount mirrors the party-line sign (positive for DN).
        assert float(bill.find("AMOUNT").text) > 0

    def test_debit_note_gst_input(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Supplier",
            purchase_ledger="Purchases", amount=11800.0,
            narration="Return", company="Test Co",
            gst_entries=[
                {"ledger": "INPUT CGST", "amount": 900.0},
                {"ledger": "INPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        gst = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if "INPUT" in (e.find("LEDGERNAME").text or "")
        ]
        assert len(gst) == 2
        for e in gst:
            # GST input on a DN sits on the debit side (Yes / negative).
            assert e.find("ISDEEMEDPOSITIVE").text == "Yes"
            assert float(e.find("AMOUNT").text) < 0

    def test_debit_note_entries_balance(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Supplier",
            purchase_ledger="Purchases", amount=11800.0,
            narration="Return", company="Test Co",
            gst_entries=[
                {"ledger": "INPUT CGST", "amount": 900.0},
                {"ledger": "INPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        amounts = [float(e.find("AMOUNT").text) for e in v.findall("LEDGERENTRIES.LIST")]
        assert abs(sum(amounts)) < 0.01

    def test_required_fields_validation(self):
        with pytest.raises(ValueError, match="date"):
            build_create_debit_note(
                date="", party_ledger="S", purchase_ledger="P",
                amount=100.0, narration="t", company="C",
            )

    def test_amount_must_be_positive(self):
        with pytest.raises(ValueError, match="amount"):
            build_create_debit_note(
                date="20260305", party_ledger="S", purchase_ledger="P",
                amount=0.0, narration="t", company="C",
            )

    def test_xml_escaping(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Smith & Sons",
            purchase_ledger="Office <Supplies>",
            amount=100.0, narration='Test "quote"', company="Test Co",
        )
        assert "Smith &amp; Sons" in xml
        assert "Office &lt;Supplies&gt;" in xml


class TestCreateCreditNote:
    def test_basic_structure(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=11800.0,
            narration="Discount", company="Test Co",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Credit Note"
        assert v.find("VOUCHERTYPENAME").text == "Credit Note"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"
        assert v.find("ISINVOICE").text == "Yes"

    def test_credit_note_sign_mirrors_sales(self):
        """CN party = debit side (Yes / -amount); contra = credit (No / +amount)."""
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=1000.0,
            narration="Discount", company="Test Co",
        )
        v = _voucher(xml)
        party = _party_entry(v)
        assert party.find("ISDEEMEDPOSITIVE").text == "Yes"
        assert float(party.find("AMOUNT").text) < 0
        contra = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is None
            and "Sales" in (e.find("LEDGERNAME").text or "")
        ][0]
        assert contra.find("ISDEEMEDPOSITIVE").text == "No"
        assert float(contra.find("AMOUNT").text) > 0

    def test_credit_note_agst_ref(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=1000.0,
            narration="Discount", company="Test Co",
            bill_ref="INV-2026-FEB-001",
        )
        v = _voucher(xml)
        bill = _party_entry(v).find("BILLALLOCATIONS.LIST")
        assert bill.find("BILLTYPE").text == "Agst Ref"
        assert bill.find("NAME").text == "INV-2026-FEB-001"
        # Bill alloc amount mirrors the party-line sign (negative for CN).
        assert float(bill.find("AMOUNT").text) < 0

    def test_credit_note_gst_output(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=11800.0,
            narration="Discount", company="Test Co",
            gst_entries=[
                {"ledger": "OUTPUT CGST", "amount": 900.0},
                {"ledger": "OUTPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        gst = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if "OUTPUT" in (e.find("LEDGERNAME").text or "")
        ]
        assert len(gst) == 2
        for e in gst:
            # GST output on a CN sits on the credit side (No / positive).
            assert e.find("ISDEEMEDPOSITIVE").text == "No"
            assert float(e.find("AMOUNT").text) > 0

    def test_credit_note_entries_balance(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=11800.0,
            narration="Discount", company="Test Co",
            gst_entries=[
                {"ledger": "OUTPUT CGST", "amount": 900.0},
                {"ledger": "OUTPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        amounts = [float(e.find("AMOUNT").text) for e in v.findall("LEDGERENTRIES.LIST")]
        assert abs(sum(amounts)) < 0.01
