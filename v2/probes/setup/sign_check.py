"""One-shot live check for Ruling C30 (2026-09-24): does Tally read OPENINGBALANCE's SIGN (negative = Dr)?

Not wired into the CLI — the main agent runs `run(writer, company)` by hand against a Probe company. It creates
one throwaway debtor with a -1.00 opening through the real `create_party_ledger`, reads its OpeningBalance back
raw, and deletes it (the v4 "Ledger delete" shape, `TallyWriter.delete_ledger`, with its own read-back — LESSONS
§15). A debit read-back (Tally exports it negative, e.g. "-1.00") confirms C30; a positive "1.00" would mean the
sign was dropped and C21 stands after all.
"""
from __future__ import annotations

from decimal import Decimal

from v2.agent.tally.envelopes import formula_string, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.setup.writes import TallyWriter, WriteFailed

LEDGER = "ZZ Sign Check Debtor"
PARENT = "Sundry Debtors"
OPENING = Decimal("-1.00")
FIELDS = ["Name", "Parent", "OpeningBalance"]


def _read_opening(writer: TallyWriter, company: str) -> str:
    xml = wrap_collection("S0SignCheckOpening", "Ledger", FIELDS, company,
                          filters=[("S0SignCheckOnly", f"$Name = {formula_string(LEDGER)}")])
    rows = [r for r in read_objects(writer.post(xml), "LEDGER", FIELDS) if r["Name"] == LEDGER]
    if not rows:
        raise WriteFailed(f"Ledger {LEDGER!r} not found on read-back")
    return rows[0]["OpeningBalance"]


def run(writer: TallyWriter, company: str) -> str:
    """Create -> read OpeningBalance -> delete. Returns the raw read-back string. The ledger is deleted even if the
    read-back fails; a leftover from an aborted run is refused (create_party_ledger would skip it silently and the
    OLD opening would be read back)."""
    if writer.ledger(company, LEDGER) is not None:
        raise WriteFailed(f"Ledger {LEDGER!r} already exists — delete it first (a leftover from an earlier run)")
    writer.create_party_ledger(company, LEDGER, parent=PARENT, bill_wise=False, opening=OPENING)
    try:
        raw = _read_opening(writer, company)
        writer.say(f"sign check: sent OPENINGBALANCE {OPENING:.2f} under {PARENT}; Tally reads back {raw!r}")
        return raw
    finally:
        writer.delete_ledger(company, LEDGER)
