"""One-shot LIVE shape probe for a forex voucher (plan part 7, Ruling C36's unblocker). Not wired into the CLI —
run by hand against company B (Task 2's runbook), like sign_check.py. Everything it creates is a throwaway, read
back and deleted, EXCEPT the Currency master, which the forex sales need. Every raw read-back is saved to `out_dir`
(the committed evidence folder) with a summary.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable

from v2.agent.tally.amounts import AmountParseError, parse_decimal
from v2.agent.tally.envelopes import wrap_collection
from v2.probes.reads import parse_forex_amount, parse_vouchers
from v2.probes.safety import check_company
from v2.probes.setup.company_b_data import USD_CURRENCY, CurrencySpec
from v2.probes.setup.writes import (ForexLine, TallyWriter, WriteFailed, WriteTimeout, b_day_voucher_request,
                                    currency_request, ledger_detail_request)

DAY = "01-09-2022"                 # C43-safe (day 1), inside B's books, the day tag 101 lands on (Educational)
DATE = "20220901"
DATE_TEXT = "1-Sep-2022"
USD_PARTY = "ZZ Forex Probe USD Debtor"
INR_PARTY = "ZZ Forex Probe INR Debtor"
NOMINAL = "Export Sales"
FX_AMOUNT, RATE = Decimal("448.44"), Decimal("82.99")          # tag 101's own figures
INR = Decimal("37216.04")
NARRATION = "S0-throwaway forex {}"
# Candidate Company fields for "is multi-currency on?" — recorded, never judged (Ruling P7-6).
COMPANY_FEATURE_FIELDS = ["Name", "BaseCurrencySymbol", "BaseCurrencyName", "IsMultiCurrencyOn",
                          "UseMultiCurrency", "MultiCurrencyOn"]
F2_TEXT = ("In TallyPrime check F2 (Current Date) is 31-03-2026 or later — a restart resets it — then press Enter. "
           "Vouchers dated after F2 are silently dropped (LESSONS §15 rule 14).")
POPUP_HINT = "Tally timed out — check it for an open popup/modal, dismiss it (or restart Tally), then restore if needed."


def _console_wait(message: str) -> None:
    input(f"\n>>> {message}\n    Press Enter when done... ")


@dataclass
class VariantResult:
    id: str
    party: str
    form: str | None
    import_error: str = ""
    master_id: str = ""
    lines: list[dict] = field(default_factory=list)       # {"ledger", "amount_raw", "fields", "classification"}
    classification: str = "not_run"                        # the party line's class; "refused" / "dropped" too


@dataclass
class ShapeReport:
    outcome: str = "not_run"
    currency: dict = field(default_factory=dict)
    company_features: list = field(default_factory=list)
    variants: list[VariantResult] = field(default_factory=list)
    chosen: dict | None = None
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {**asdict(self), "variants": [asdict(v) for v in self.variants]}

    def summary(self) -> str:
        rows = ", ".join(f"{v.id}={v.classification}" for v in self.variants)
        return f"outcome={self.outcome} chosen={self.chosen} variants: {rows or '—'}"


def _stored(v: VariantResult) -> bool:
    return v.classification in ("forex_full", "forex_no_base", "plain_with_forex_field")


def classify(line: dict, sent_inr: Decimal) -> str:
    fa = parse_forex_amount(line["amount_raw"])
    if fa is not None:
        return "forex_full" if fa.base is not None else "forex_no_base"
    try:
        value = parse_decimal(line["amount_raw"])
    except AmountParseError:
        return "other"
    if value is None or value != sent_inr:
        return "other"
    forexish = any(("$" in text or "@" in text) for key, text in line["fields"].items() if key != "AMOUNT")
    return "plain_with_forex_field" if forexish else "plain_inr"


def run(writer: TallyWriter, company: str, out_dir: Path, *, currency: CurrencySpec = USD_CURRENCY,
        wait: Callable[[str], None] = _console_wait) -> ShapeReport:
    check_company(writer.company_names(), company, mutating=True)          # one company, B, "Probe" in the name
    out_dir.mkdir(parents=True, exist_ok=True)
    report = ShapeReport()

    def save(step: str, xml: str) -> str:
        text = writer.post(xml)
        (out_dir / f"{step}.xml").write_text(text, encoding="utf-8")
        return text

    def finish() -> ShapeReport:
        (out_dir / "summary.json").write_text(json.dumps(report.to_json(), indent=2, ensure_ascii=False, default=str),
                                              encoding="utf-8")
        return report

    # Leftovers from an aborted run: refuse, never adopt (a leftover could be the wrong shape) — sign_check pattern.
    ledgers = writer.list_ledgers(company)
    day_rows = parse_vouchers(writer.post(b_day_voucher_request(company, DAY)))
    if USD_PARTY in ledgers or INR_PARTY in ledgers or any(
            v["header"].get("NARRATION", "").startswith("S0-throwaway forex") for v in day_rows):
        raise WriteFailed("A leftover from an earlier forex shape run exists — delete it in the UI or restore the "
                          "pre-forex backup first (plan part 7 Task 2).")

    save("company_features", wrap_collection("S0FxCompany", "Company", COMPANY_FEATURE_FIELDS, company))
    save("currencies_before", currency_request(company))
    save("export_sales_ledger", ledger_detail_request(company, NOMINAL))
    try:
        created = writer.create_currency(company, currency)
    except WriteTimeout:
        report.outcome = "popup"
        report.notes.append(POPUP_HINT)
        return finish()
    except WriteFailed as exc:
        report.outcome = "currency_refused"
        report.notes.append(f"Currency {currency.symbol!r}: {exc}")
        return finish()
    save("currencies_after", currency_request(company))
    report.currency = {"symbol": currency.symbol, "created_now": created}
    wait(F2_TEXT)

    made: list[str] = []
    completed = False             # False while an exception propagates: cleanup then must not mask it (deviation D3)
    try:
        for name, cur in ((INR_PARTY, None), (USD_PARTY, currency.symbol)):
            writer.create_party_ledger(company, name, parent="Sundry Debtors", bill_wise=False, currency=cur)
            made.append(name)
        save("ledgers_after_create", ledger_detail_request(company, USD_PARTY))

        def variant(vid: str, party: str, form: str | None) -> VariantResult:
            result = VariantResult(id=vid, party=party, form=form)
            report.variants.append(result)
            forex = None if form is None else ForexLine(currency.symbol, FX_AMOUNT, RATE, form=form)
            narration = NARRATION.format(vid)
            try:
                result.master_id = writer.create_b_voucher(
                    company, vch_type="Sales", date=DATE, narration=narration, party=party,
                    lines=[(party, -INR, True), (NOMINAL, INR, False)], forex=forex)
            except WriteTimeout:
                raise
            except WriteFailed as exc:
                result.import_error, result.classification = str(exc), "refused"
                return result
            raw = save(f"variant_{vid}", b_day_voucher_request(company, DAY))
            found = [v for v in parse_vouchers(raw) if v["header"].get("NARRATION") == narration]
            if not found:
                result.classification = "dropped"          # created=1 but not there: F2 or date (rule 14)
                return result
            for line in found[0]["ledger_lines"]:
                ledger = line["fields"].get("LEDGERNAME", "")
                sent = -INR if ledger == party else INR
                result.lines.append({"ledger": ledger, "amount_raw": line["amount_raw"], "fields": line["fields"],
                                     "classification": classify(line, sent)})
            party_line = next((l for l in result.lines if l["ledger"] == party), None)
            result.classification = party_line["classification"] if party_line else "other"
            writer.delete_b_voucher(company, result.master_id, vch_type="Sales", day=DAY, date_text=DATE_TEXT)
            return result

        v0 = variant("V0", INR_PARTY, None)
        if v0.classification != "plain_inr":
            report.outcome = "control_failed"
            report.notes.append("V0 (plain INR, non-inventory, no-GST Sales) did not post cleanly — the base "
                                "voucher shape is wrong, so no forex result would mean anything.")
            completed = True
            return finish()
        v1 = variant("V1", USD_PARTY, "full")
        if not _stored(v1):
            variant("V2", USD_PARTY, "no_base")
        variant("V3", INR_PARTY, "full")
        completed = True
    except WriteTimeout:
        report.outcome = "popup"
        report.notes.append(POPUP_HINT)
        return finish()                                   # leave the ledgers: Tally is behind a modal
    finally:
        if report.outcome != "popup":
            for name in reversed(made):
                try:
                    writer.delete_ledger(company, name)
                except WriteFailed as exc:
                    if completed:
                        raise
                    # Live Tally refuses to delete a ledger that still has a voucher (a delete that did not
                    # stick): record it and let the FIRST error surface.
                    report.notes.append(f"cleanup: {exc} — restore the pre-forex backup (plan part 7 Task 2 step 7)")

    if any(v.classification == "dropped" for v in report.variants):
        report.notes.append("A throwaway answered created=1 but was not on " + DAY + " — check F2 (" + F2_TEXT + ")")
    usd_ok = [v for v in report.variants if v.party == USD_PARTY and _stored(v)]
    any_ok = usd_ok or [v for v in report.variants if _stored(v)]
    if any_ok:
        best = any_ok[0]
        report.outcome = "stored_forex"
        report.chosen = {"variant": best.id, "party_currency": currency.symbol if best.party == USD_PARTY else None,
                         "form": best.form}
    elif any(v.classification == "plain_inr" for v in report.variants if v.form):
        report.outcome = "forex_dropped"
    else:
        report.outcome = "refused"
    return finish()
