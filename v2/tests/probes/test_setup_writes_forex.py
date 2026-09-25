from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES
from v2.probes.reads import parse_forex_amount
from v2.probes.setup.company_b_data import USD_CURRENCY
from v2.probes.setup.writes import (ForexLine, TallyWriter, WriteFailed, WriteTimeout, forex_amount_text,
                                    validate_b_voucher)
from v2.tests.probes.fake_books import FakeBooks, seed_company_b, sync_client

B = COMPANIES["B"]
FX = ForexLine(symbol="$", fx_amount=Decimal("448.44"), rate=Decimal("82.99"))
LINES = [("ZZ Party", Decimal("-37216.04"), True), ("Export Sales", Decimal("37216.04"), False)]


def _writer(books) -> TallyWriter:
    return TallyWriter(sync_client(books.transport()), say=lambda _m: None)


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


def test_forex_text_round_trips_through_the_parser():
    for inr in (Decimal("-37216.04"), Decimal("37216.04")):
        text = forex_amount_text(inr, FX)
        fa = parse_forex_amount(text)
        assert fa.base == inr and fa.fx == (FX.fx_amount if inr > 0 else -FX.fx_amount) and fa.rate == FX.rate
    assert forex_amount_text(Decimal("-37216.04"), FX) == "-$448.44 @ ₹82.99/$ = -₹37216.04"
    no_base = ForexLine("$", Decimal("448.44"), Decimal("82.99"), form="no_base")
    assert parse_forex_amount(forex_amount_text(Decimal("-37216.04"), no_base)).base is None


def test_validate_refuses_forex_with_inventory_or_bills():
    with pytest.raises(ValueError, match="no inventory and no bills"):
        validate_b_voucher(vch_type="Sales", narration="x", party="ZZ Party", lines=LINES, forex=FX,
                           bills=[("B/1", "New Ref", Decimal("37216.04"), None)])


def test_validate_refuses_a_line_that_is_not_face_times_rate():
    bad = [("ZZ Party", Decimal("-37216.05"), True), ("Export Sales", Decimal("37216.05"), False)]
    with pytest.raises(ValueError, match="face × rate"):
        validate_b_voucher(vch_type="Sales", narration="x", party="ZZ Party", lines=bad, forex=FX)


def test_validate_refuses_a_rounding_tie():
    tie = ForexLine("$", Decimal("0.50"), Decimal("0.01"))          # 0.005: HALF_UP 0.01, HALF_EVEN 0.00
    with pytest.raises(ValueError, match="rounding tie"):
        validate_b_voucher(vch_type="Sales", narration="x", party="P",
                           lines=[("P", Decimal("-0.01"), True), ("S", Decimal("0.01"), False)], forex=tie)


def test_create_currency_lists_first_and_reads_back():
    books = _books()
    writer = _writer(books)
    assert "$" not in writer.list_currencies(B)
    assert writer.create_currency(B, USD_CURRENCY) is True
    assert "$" in writer.list_currencies(B)
    creates = len([r for r in books.requests if "<CURRENCY " in r])
    assert writer.create_currency(B, USD_CURRENCY) is False                  # LESSONS §15 rule 10: no second create
    assert len([r for r in books.requests if "<CURRENCY " in r]) == creates


def test_currency_create_refused_raises():
    with pytest.raises(WriteFailed):
        _writer(_books(forex_currency_create="refuse")).create_currency(B, USD_CURRENCY)


def test_currency_create_popup_times_out():
    with pytest.raises(WriteTimeout):
        _writer(_books(forex_currency_create="popup")).create_currency(B, USD_CURRENCY)


def test_party_ledger_currency_is_sent_and_read_back():
    books = _books()
    writer = _writer(books)
    writer.create_currency(B, USD_CURRENCY)
    writer.create_party_ledger(B, "ZZ Forex Probe USD Debtor", parent="Sundry Debtors", bill_wise=False,
                               currency="$")
    assert writer.ledger_details(B, "ZZ Forex Probe USD Debtor")["CurrencyName"] == "$"


def test_forex_sale_goes_out_as_expression_and_books_the_base():
    books = _books()
    writer = _writer(books)
    writer.create_currency(B, USD_CURRENCY)
    writer.create_party_ledger(B, "ZZ Party", parent="Sundry Debtors", bill_wise=False, currency="$")
    mid = writer.create_b_voucher(B, vch_type="Sales", date="20220901", narration="S0-throwaway forex V1",
                                  party="ZZ Party", lines=LINES, forex=FX)
    body = next(r for r in books.requests if "S0-throwaway forex V1" in r and "Import" in r)
    assert "<AMOUNT>-$448.44 @ ₹82.99/$ = -₹37216.04</AMOUNT>" in body
    assert [l["amount"] for l in books.state["vouchers"][mid]["lines"]] == ["-37216.04", "37216.04"]


def test_delete_b_voucher_verifies_in_the_vouchers_own_day():
    books = _books(deletes_stick=False)                 # Tally says deleted=1 but the voucher is still there
    writer = _writer(books)
    writer.create_party_ledger(B, "ZZ Party", parent="Sundry Debtors", bill_wise=False)
    mid = writer.create_b_voucher(B, vch_type="Sales", date="20220901", narration="S0-throwaway forex V0",
                                  party="ZZ Party", lines=LINES)
    with pytest.raises(WriteFailed, match="still there"):
        writer.delete_b_voucher(B, mid, vch_type="Sales", day="01-09-2022", date_text="1-Sep-2022")


@pytest.mark.parametrize("form, amount_raw, extra", [
    ("full", "-$448.44 @ ₹82.99/$ = -₹37216.04", None),
    ("no_base", "-$448.44 @ ₹82.99/$", None),
    ("plain_plus_field", "-37216.04", "-$448.44"),
])
def test_fake_export_forms_and_closing_expression(form, amount_raw, extra):
    # Not in the plan: covers FakeBooks' candidate export knobs (plan part 7 Task 1.2 step 4) before Task 4 uses them.
    from v2.probes.reads import parse_vouchers
    from v2.probes.setup.writes import b_day_voucher_request
    books = _books(forex_export_form=form, forex_ledger_closing="expression")
    writer = _writer(books)
    writer.create_currency(B, USD_CURRENCY)
    writer.create_party_ledger(B, "ZZ Party", parent="Sundry Debtors", bill_wise=False, currency="$")
    writer.create_b_voucher(B, vch_type="Sales", date="20220901", narration="S0-throwaway forex V1",
                            party="ZZ Party", lines=LINES, forex=FX)
    found = [v for v in parse_vouchers(writer.post(b_day_voucher_request(B, "01-09-2022")))
             if v["header"].get("NARRATION") == "S0-throwaway forex V1"]
    party = next(l for l in found[0]["ledger_lines"] if l["fields"]["LEDGERNAME"] == "ZZ Party")
    assert party["amount_raw"] == amount_raw and party["fields"].get("FOREXAMOUNT") == extra
    assert writer.ledger_details(B, "ZZ Party")["ClosingBalance"] == "-$448.44 = -₹37216.04"
