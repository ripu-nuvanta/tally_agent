import json
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES
from v2.probes.reads import parse_forex_amount
from v2.probes.safety import GuardError
from v2.probes.setup import forex_shape
from v2.probes.setup.writes import TallyWriter, WriteFailed
from v2.tests.probes.fake_books import FakeBooks, seed_company_b, sync_client

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


def _run(books, tmp_path):
    writer = TallyWriter(sync_client(books.transport()), say=lambda _m: None)
    return forex_shape.run(writer, B, tmp_path / "shape", wait=lambda _msg: None)


def _throwaways_gone(books) -> bool:
    ledgers = set(books.state["ledgers"])
    return (forex_shape.USD_PARTY not in ledgers and forex_shape.INR_PARTY not in ledgers
            and not any(v["narration"].startswith("S0-throwaway forex") for v in books.state["vouchers"].values()))


def test_run_stores_forex_on_both_parties_and_cleans_up(tmp_path):
    books = _books()
    report = _run(books, tmp_path)
    assert report.outcome == "stored_forex"
    assert report.chosen == {"variant": "V1", "party_currency": "$", "form": "full"}
    assert [v.id for v in report.variants] == ["V0", "V1", "V3"]                   # V2 only when V1 fails
    assert {v.id: v.classification for v in report.variants} == {"V0": "plain_inr", "V1": "forex_full",
                                                                  "V3": "forex_full"}
    assert _throwaways_gone(books) and "$" in books.state["currencies"]            # the currency is kept
    files = {p.name for p in (tmp_path / "shape").iterdir()}
    assert {"company_features.xml", "currencies_before.xml", "currencies_after.xml", "ledgers_after_create.xml",
            "variant_V0.xml", "variant_V1.xml", "variant_V3.xml", "summary.json"} <= files
    assert json.loads((tmp_path / "shape" / "summary.json").read_text())["outcome"] == "stored_forex"


def test_forex_dropped_when_tally_stores_plain_inr(tmp_path):
    books = _books(forex_storage="plain")
    report = _run(books, tmp_path)
    assert report.outcome == "forex_dropped" and report.chosen is None
    assert [v.id for v in report.variants] == ["V0", "V1", "V2", "V3"]
    assert all(v.classification == "plain_inr" for v in report.variants)
    assert _throwaways_gone(books)


def test_only_the_no_base_form_accepted_picks_v2(tmp_path):
    report = _run(_books(forex_forms_accepted=("no_base",), forex_export_form="no_base"), tmp_path)
    assert report.outcome == "stored_forex"
    assert report.chosen == {"variant": "V2", "party_currency": "$", "form": "no_base"}
    assert {v.id: v.classification for v in report.variants}["V1"] == "refused"


def test_currency_refused_stops_before_any_throwaway(tmp_path):
    books = _books(forex_currency_create="refuse")
    report = _run(books, tmp_path)
    assert report.outcome == "currency_refused" and report.variants == []
    assert not any("ZZ Forex Probe" in r for r in books.requests)


def test_a_currency_popup_stops_with_the_hint(tmp_path):
    report = _run(_books(forex_currency_create="popup"), tmp_path)
    assert report.outcome == "popup" and "popup" in report.notes[-1].lower()


def test_control_failure_is_reported_first(tmp_path):
    books = _books(refuse_narrations=("S0-throwaway forex V0",))                   # V0 cannot post
    report = _run(books, tmp_path)
    assert report.outcome == "control_failed" and [v.id for v in report.variants] == ["V0"]


def test_base_party_refusal_is_evidence_not_failure(tmp_path):
    report = _run(_books(forex_on_base_party="refuse"), tmp_path)
    assert report.outcome == "stored_forex"
    assert {v.id: v.classification for v in report.variants}["V3"] == "refused"


def test_a_delete_that_does_not_stick_is_caught_in_the_2022_window(tmp_path):
    with pytest.raises(WriteFailed, match="still there"):
        _run(_books(deletes_stick=False), tmp_path)


def test_leftover_throwaway_refuses_to_run(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"].__setitem__(forex_shape.USD_PARTY, dict(s["ledgers"]["Cash"])))
    with pytest.raises(WriteFailed, match="leftover"):
        _run(books, tmp_path)


def test_wrong_company_is_refused_before_any_write(tmp_path):
    books = FakeBooks(name=COMPANIES["A"], educational=True)
    with pytest.raises(GuardError):
        _run(books, tmp_path)
    assert not any("Import" in r for r in books.requests)


@pytest.mark.parametrize("amount, fields, expected", [
    ("-$448.44 @ ?82.99/$ = -?37216.04", {}, "forex_full"),
    ("-$448.44 @ 82.99/$ = -37216.04", {}, "forex_full"),                 # R-SYM: the rate without a base symbol
    ("-$448.44 @ ?82.99/$", {}, "forex_no_base"),
    ("-37216.04", {"FOREXAMOUNT": "-$448.44"}, "plain_with_forex_field"),
    ("-37216.04", {}, "plain_inr"),
    ("-37216.05", {}, "other"),
    # I1: values that parse but are not what was sent — never "stored"
    ("-$37216.04 @ ?82.99/$ = -?3088558.16", {}, "forex_mismatch"),      # Tally reinterpreted the amount
    ("-?37216.04 @ ?1.00/? = -?37216.04", {}, "forex_mismatch"),          # a base-currency line in expression form
    ("-$448.44 @ ?83.00/$ = -?37220.52", {}, "forex_mismatch"),           # another rate
    ("$448.44 @ ?82.99/$ = ?37216.04", {}, "forex_mismatch"),             # the sign flipped
    ("-$448.44 @ ?82.99/$ = -?37216.05", {}, "forex_mismatch"),           # a stated base ≠ the INR sent
    ("-$448.44 @ ₹82.99/$ = -₹37216.04", {}, "forex_mismatch"),           # a base symbol that isn't the discovered one
    # I1: the field route is strict — a stray "$" or "@" is not a forex value
    ("-37216.04", {"LEDGERCURRENCY": "$"}, "plain_inr"),
    ("-37216.04", {"NOTE": "@ desk"}, "plain_inr"),
    ("-37216.04", {"FOREXAMOUNT": "448.44"}, "plain_inr"),                 # the face without the currency symbol
])
def test_classify(amount, fields, expected):
    line = {"amount_raw": amount, "fields": {"AMOUNT": amount, **fields}}
    assert forex_shape.classify(line, Decimal("-37216.04"), base_symbol="?") == expected


def test_forex_problems_name_what_differs():
    problems = forex_shape.forex_problems(parse_forex_amount("-$37216.04 @ ?82.99/$ = -?3088558.16"),
                                          Decimal("-37216.04"), base_symbol="?")
    assert any("448.44" in p for p in problems) and any("base" in p for p in problems)


def test_cleanup_failure_does_not_mask_the_first_error(tmp_path):
    # Not in the plan (deviation D3): live Tally refuses to delete a ledger that still has a voucher, so after a
    # delete that did not stick the ledger cleanup fails too — the "still there" error must be the one raised.
    books = _books(deletes_stick=False)
    writer = TallyWriter(sync_client(books.transport()), say=lambda _m: None)

    def refuse(_company, name):
        raise WriteFailed(f"Ledger {name!r} not deleted: in use")
    writer.delete_ledger = refuse
    with pytest.raises(WriteFailed, match="still there"):
        forex_shape.run(writer, B, tmp_path / "shape", wait=lambda _msg: None)


def test_a_dropped_voucher_leaves_an_f2_note(tmp_path):
    # Not in the plan (deviation D4): created=1 but absent from the day (F2 before the date, LESSONS §15 rule 14).
    books = _books()
    writer = TallyWriter(sync_client(books.transport()), say=lambda _m: None)
    real_create = writer.create_b_voucher

    def create_then_vanish(company, **kw):
        mid = real_create(company, **kw)
        if kw["narration"].endswith("V1"):
            books.edit_state(lambda s: s["vouchers"].pop(mid))
        return mid
    writer.create_b_voucher = create_then_vanish
    report = forex_shape.run(writer, B, tmp_path / "shape", wait=lambda _msg: None)
    assert {v.id: v.classification for v in report.variants}["V1"] == "dropped"
    assert any("F2" in note for note in report.notes)
