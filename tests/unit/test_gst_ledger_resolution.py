"""Unit tests — GST ledger resolution from a workspace's Tally ledgers.

The orchestrator's file-upload path must resolve the correct GST ledgers (Input
for Purchase/Debit Note, Output for Sales/Credit Note) from the live ledger list
rather than hardcoding names. Matching is among ledgers under "Duties & Taxes",
case-insensitive, tolerating minor word-order variation ("Input CGST"). A missing
ledger needed by the document yields a warning and no leg (rather than a crash).
"""
import pytest

from backend.agents.orchestrator import _resolve_gst_ledgers


# Seed-company GST ledgers (verified live under "Duties & Taxes").
_SEED_GST_LEDGERS = [
    {"name": "CGST Input", "parent_group": "Duties & Taxes"},
    {"name": "SGST Input", "parent_group": "Duties & Taxes"},
    {"name": "IGST Input", "parent_group": "Duties & Taxes"},
    {"name": "CGST Output", "parent_group": "Duties & Taxes"},
    {"name": "SGST Output", "parent_group": "Duties & Taxes"},
    {"name": "IGST Output", "parent_group": "Duties & Taxes"},
    {"name": "Croma Electronics", "parent_group": "Sundry Creditors"},
]


class _GST:
    def __init__(self, cgst=None, sgst=None, igst=None):
        self.cgst_amount = cgst
        self.sgst_amount = sgst
        self.igst_amount = igst


class _Doc:
    def __init__(self, gst):
        self.gst = gst


def test_resolves_input_gst_for_intrastate_purchase():
    doc = _Doc(_GST(cgst=1171.0, sgst=1171.0))
    ledgers, warnings = _resolve_gst_ledgers(_SEED_GST_LEDGERS, "input", doc)
    assert ledgers["cgst_input"] == "CGST Input"
    assert ledgers["sgst_input"] == "SGST Input"
    assert "igst_input" not in ledgers  # no IGST component on the doc
    assert warnings == []


def test_resolves_input_igst_for_interstate_purchase():
    doc = _Doc(_GST(igst=3600.0))
    ledgers, warnings = _resolve_gst_ledgers(_SEED_GST_LEDGERS, "input", doc)
    assert ledgers["igst_input"] == "IGST Input"
    assert "cgst_input" not in ledgers
    assert warnings == []


def test_resolves_output_gst_for_sales():
    doc = _Doc(_GST(cgst=9000.0, sgst=9000.0))
    ledgers, warnings = _resolve_gst_ledgers(_SEED_GST_LEDGERS, "output", doc)
    assert ledgers["cgst_output"] == "CGST Output"
    assert ledgers["sgst_output"] == "SGST Output"
    assert warnings == []


def test_tolerates_reversed_word_order():
    """'Input CGST' must still map to the cgst_input key."""
    ledgers_list = [
        {"name": "Input CGST", "parent_group": "Duties & Taxes"},
        {"name": "Input SGST", "parent_group": "Duties & Taxes"},
    ]
    doc = _Doc(_GST(cgst=100.0, sgst=100.0))
    ledgers, warnings = _resolve_gst_ledgers(ledgers_list, "input", doc)
    assert ledgers["cgst_input"] == "Input CGST"
    assert ledgers["sgst_input"] == "Input SGST"
    assert warnings == []


def test_only_matches_duties_and_taxes_group():
    """A 'CGST Input' ledger under the wrong group must not be picked up."""
    ledgers_list = [
        {"name": "CGST Input", "parent_group": "Indirect Expenses"},
    ]
    doc = _Doc(_GST(cgst=100.0))
    ledgers, warnings = _resolve_gst_ledgers(ledgers_list, "input", doc)
    assert "cgst_input" not in ledgers
    assert any("CGST Input" in w for w in warnings)


def test_missing_ledger_warns_and_does_not_crash():
    """Doc has CGST but no matching ledger → warning, no key, no exception."""
    ledgers_list = [
        {"name": "SGST Input", "parent_group": "Duties & Taxes"},
    ]
    doc = _Doc(_GST(cgst=100.0, sgst=100.0))
    ledgers, warnings = _resolve_gst_ledgers(ledgers_list, "input", doc)
    assert ledgers["sgst_input"] == "SGST Input"
    assert "cgst_input" not in ledgers
    assert any("CGST Input" in w for w in warnings)


def test_no_gst_on_doc_returns_empty():
    doc = _Doc(None)
    ledgers, warnings = _resolve_gst_ledgers(_SEED_GST_LEDGERS, "input", doc)
    assert ledgers == {}
    assert warnings == []
