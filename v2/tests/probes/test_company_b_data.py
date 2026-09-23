from calendar import monthrange
from datetime import date
from decimal import Decimal

from v2.probes.setup.company_b_data import (
    COMPOUND_UNIT, HINDI_DEBTOR, NON_BILLWISE_DEBTOR, SALES_GST_VOUCHER_TYPE, USD_DEBTOR,
    expected_figures, generate, gstin,
)


def test_the_same_seed_generates_an_identical_dataset():
    assert generate() == generate()          # frozen dataclasses compare by value


def test_every_voucher_balances_to_zero():
    for v in generate().vouchers:
        total = sum((line.amount for line in v.lines), Decimal("0.00"))
        assert total == Decimal("0.00"), f"{v.tag} {v.kind} does not balance: {total}"


def test_the_calendar_covers_four_financial_years_at_twenty_a_month():
    ds = generate()
    assert len(ds.vouchers) == 960
    months = {(v.date.year, v.date.month) for v in ds.vouchers}
    assert len(months) == 48
    assert min(ds.vouchers, key=lambda v: v.date).date >= date(2022, 4, 1)
    assert max(ds.vouchers, key=lambda v: v.date).date <= date(2026, 3, 31)


def test_educational_mode_uses_only_dates_tally_accepts_and_keeps_the_tags_stable():
    licensed, educational = generate(), generate(licence="educational")
    for v in educational.vouchers:
        allowed = {1, 2, 31} if monthrange(v.date.year, v.date.month)[1] == 31 else {1, 2}
        assert v.date.day in allowed
    assert [v.tag for v in licensed.vouchers] == [v.tag for v in educational.vouchers]


def test_the_dataset_carries_the_messy_shapes_the_probes_need():
    ds = generate()
    by_name = {l.name: l for l in ds.ledgers}
    assert by_name[NON_BILLWISE_DEBTOR].bill_wise is False
    assert by_name[HINDI_DEBTOR].bill_wise is True
    assert {g.name for g in ds.groups} >= {"National Creditors", "Local Creditors"}
    assert all(g.parent == "Sundry Creditors" for g in ds.groups)
    assert any(u.name == COMPOUND_UNIT and u.conversion == 10 for u in ds.units)
    assert any(i.unit == COMPOUND_UNIT for i in ds.items)
    assert not any(i.name == "Primary" for i in ds.items)                      # LESSONS §15 r13


def test_the_non_billwise_debtor_never_gets_a_bill():
    for v in generate().vouchers:
        if v.party == NON_BILLWISE_DEBTOR:
            assert v.bills == ()


def test_the_special_vouchers_sit_on_fixed_tags():
    by_tag = {v.tag: v for v in generate().vouchers}
    assert by_tag[101].currency == "USD" and by_tag[101].fx_amount is not None
    assert by_tag[102].currency == "USD"
    assert by_tag[201].cancelled and by_tag[202].cancelled
    assert by_tag[301].optional and by_tag[302].optional
    assert any(v.vch_type == SALES_GST_VOUCHER_TYPE for v in by_tag.values())
    assert any(HINDI_DEBTOR in v.narration or "शर्मा" in v.narration for v in by_tag.values())


def test_every_narration_carries_its_idempotency_tag():
    for v in generate().vouchers:
        assert v.narration.startswith(f"[S0-B:{v.tag}]")


def test_gstin_check_digit_matches_the_official_algorithm():
    # Verified against a known-real GSTIN (27AAPFU0939F1ZV) with the same algorithm; the brief's literal
    # expectation for this specific body ("...1ZV") did not match its own reference implementation's
    # output ("...1ZE") — see task-1-report.md for the cross-check.
    assert gstin("27", "AAAPL1234C") == "27AAAPL1234C1ZE"
    assert gstin("27", "AAPFU0939F") == "27AAPFU0939F1ZV"


def test_month_end_balances_equal_openings_plus_the_running_sum():
    ds = generate()
    exp = expected_figures(ds)
    for ledger in ("Domestic Sales", "Capital Account", USD_DEBTOR):
        for (name, day), value in exp.ledger_month_end.items():
            if name != ledger:
                continue
            opening = next((l.opening or Decimal("0.00") for l in ds.ledgers if l.name == name), Decimal("0.00"))
            moved = sum((line.amount for v in ds.vouchers if v.date <= day and not v.cancelled
                         for line in v.lines if line.ledger == name), Decimal("0.00"))
            assert value == opening + moved


def test_cancelled_vouchers_do_not_move_a_balance_but_are_still_counted():
    ds = generate()
    exp = expected_figures(ds)
    assert sum(exp.voucher_count_by_month.values()) == len(ds.vouchers)
    assert exp.voucher_count_by_fy["2022-23"] == 240


def test_fy_openings_are_the_previous_month_end():
    ds = generate()
    exp = expected_figures(ds)
    assert exp.ledger_fy_opening[("Domestic Sales", date(2023, 4, 1))] == exp.ledger_month_end[("Domestic Sales", date(2023, 3, 31))]
