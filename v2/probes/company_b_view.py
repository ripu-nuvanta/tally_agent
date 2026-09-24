"""Read-side view of company B's dataset for the company-B probes (S0 spec §4.3, §7).

Probe modules may not import `v2.probes.setup` (the write code, S0-D8; test_isolation). The dataset generator
`setup/company_b_data.py` is pure (no I/O, no v2 imports), so this module is the one bridge. It imports nothing else
from `setup/`, and test_isolation pins both facts.

The count rule (S0 plan part 4, Global Constraints): a window's expected tags are every dataset voucher dated in it
without `skip_reason` (C36: never written). Cancelled and optional vouchers are included, because they are vouchers
that exist in Tally, even though Tally leaves them out of balances (C42). A window is exact when no unflagged tag is
missing and nothing unexpected, untagged, duplicated or out of the window came back. Whether the flagged tags came
back is recorded, never judged: probe 3's B part owns the flags (S0-D7).
"""
from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from v2.probes.core import ProbeBlocked
from v2.probes.reads import dmy, fill_month_request, parse_vouchers, tally_date, untyped_period_vars
from v2.probes.setup.company_b_data import (COMPANY_B_BOOKS_FROM, COMPANY_B_LAST_MONTH, TAG_PREFIX, Dataset,
                                            VoucherSpec, _educational_days, generate)

if TYPE_CHECKING:
    from v2.probes.context import ProbeContext

B_BOOKS_FROM_DATE = COMPANY_B_BOOKS_FROM
B_BOOKS_FROM = COMPANY_B_BOOKS_FROM.strftime("%d-%m-%Y")        # "01-04-2022"
# The dataset's last month (COMPANY_B_LAST_MONTH), end-of-month — was hard-coded "31-03-2026" (review M2/P8b).
_B_BOOKS_TO_DATE = date(COMPANY_B_LAST_MONTH.year, COMPANY_B_LAST_MONTH.month,
                        monthrange(COMPANY_B_LAST_MONTH.year, COMPANY_B_LAST_MONTH.month)[1])
B_BOOKS_TO = _B_BOOKS_TO_DATE.strftime("%d-%m-%Y")
# The company's current period: the FY that holds its last month (live: 1-Apr-2025..31-Mar-2026). C33: an untyped
# period variable silently answers for this period; C43: so does an educational one off day 1/2/31.
B_CURRENT_PERIOD = (date(_B_BOOKS_TO_DATE.year - (1 if _B_BOOKS_TO_DATE.month < 4 else 0), 4, 1), _B_BOOKS_TO_DATE)
# C43 (live 2026-09-24): Educational TallyPrime silently ignores a date static variable (SVFROMDATE/SVTODATE, typed)
# whose day is not one of these — the same rule it applies to voucher dates — and falls back to the current period.
EDUCATIONAL_DATE_VAR_DAYS = (1, 2, 31)
_TAG = re.compile(rf"^\[{re.escape(TAG_PREFIX)}:(\d+)\]")


def tag_of(narration: str) -> int | None:
    """The loader's tag at the start of a narration ('[S0-B:281] …' → 281); anything else → None."""
    match = _TAG.match((narration or "").strip())
    return int(match.group(1)) if match else None


def kind_label(v: VoucherSpec) -> str:
    """The storage kind probe 21 sizes by: base kind, then '+inventory' and '+bills' when the voucher has them."""
    return v.kind + ("+inventory" if v.inventory else "") + ("+bills" if v.bills else "")


@lru_cache(maxsize=2)
def dataset(licence: str) -> Dataset:
    return generate(licence)


@dataclass(frozen=True)
class WindowExpectation:
    written: dict[int, VoucherSpec]      # tag -> voucher, for every tag the loader wrote in the window
    flagged: frozenset[int]              # cancelled or optional among `written`
    skipped: frozenset[int]              # skip_reason: dated in the window, never written

    @property
    def unflagged(self) -> frozenset[int]:
        return frozenset(self.written) - self.flagged


def month_window(year: int, month: int, licence: str) -> tuple[date, date]:
    """The (from, to) window every company-B probe asks Tally for when it means "this calendar month" (C43, Ruling R3).

    Licensed: the 1st to the month's last day. Educational: the 1st to the last day ≤ month-end whose day is 1, 2 or 31
    — the 31st in a 31-day month, else the 2nd. Educational TallyPrime silently ignores a date variable on any other
    day and answers for the current period instead (C43: typed 01-06-2023..30-06-2023 returned 680 vouchers running to
    2026-03-31). The clamp loses nothing: an educational company cannot hold a voucher on any other day either
    (`_educational_days`, the loader's own rule), so 1st..2nd or 1st..31st still bounds the whole month exactly.
    [Educational mode — confirm on a licensed Tally.]
    """
    if licence not in ("licensed", "educational"):
        raise ValueError(f"unknown licence {licence!r}")
    last = monthrange(year, month)[1]
    if licence == "educational":
        last = max(day for day in _educational_days(year, month) if day in EDUCATIONAL_DATE_VAR_DAYS)
    return date(year, month, 1), date(year, month, last)


def check_date_vars(licence: str, *dates: str) -> None:
    """Refuse a DD-MM-YYYY request date an educational Tally would silently ignore (C43): sending it reads as a
    healthy answer for the wrong period, which is worse than not asking."""
    if licence != "educational":
        return
    bad = [d for d in dates if dmy(d).day not in EDUCATIONAL_DATE_VAR_DAYS]
    if bad:
        raise ValueError(f"C43: educational Tally ignores date variables off day 1/2/31 and answers for the current "
                         f"period instead — {', '.join(bad)} would be silently replaced; use month_window().")


def expect_window(licence: str, start: date, end: date) -> WindowExpectation:
    in_window = [v for v in dataset(licence).vouchers if start <= v.date <= end]
    written = {v.tag: v for v in in_window if not v.skip_reason}
    return WindowExpectation(written=written,
                             flagged=frozenset(t for t, v in written.items() if v.cancelled or v.optional),
                             skipped=frozenset(v.tag for v in in_window if v.skip_reason))


def voucher_rows(text: str) -> list[dict[str, Any]]:
    """[{"tag", "date"}] for every voucher in a collection response (CMPINFO's counter skipped by parse_vouchers)."""
    return [{"tag": tag_of(v["header"].get("NARRATION", "")), "date": tally_date(v["header"].get("DATE", ""))}
            for v in parse_vouchers(text)]


def compare_tags(rows: list[dict[str, Any]], expected: WindowExpectation, start: date, end: date) -> dict[str, Any]:
    dates = [row["date"] for row in rows if row["date"] is not None]
    out_of_window = sum(1 for row in rows if row["date"] is None or not start <= row["date"] <= end)
    tags = [row["tag"] for row in rows if row["tag"] is not None]
    got = set(tags)
    result = {
        "returned": len(rows),
        "expected_written": len(expected.written),
        "expected_unflagged": len(expected.unflagged),
        "bounded": out_of_window == 0,
        "out_of_window": out_of_window,
        "date_span": [min(dates).isoformat(), max(dates).isoformat()] if dates else None,
        "untagged": len(rows) - len(tags),
        "missing": sorted(expected.unflagged - got),
        "extra": sorted(got - set(expected.written)),
        "duplicates": sorted(t for t in got if tags.count(t) > 1),
        "flagged_returned": sorted(expected.flagged & got),
        "flagged_missing": sorted(expected.flagged - got),
    }
    # I1: split "the request doesn't bound the window" (reach_ok False — a real request/reach failure) from "the
    # request bounded and returned every expected tag, but the books hold something the dataset doesn't" (drifted —
    # company B no longer matches its generated dataset; never a request failure). `match` keeps its original,
    # stricter meaning (reach_ok and not drifted) so every existing exactness check is unchanged.
    result["reach_ok"] = result["bounded"] and not result["missing"]
    result["drifted"] = result["reach_ok"] and bool(result["untagged"] or result["extra"] or result["duplicates"])
    result["match"] = result["reach_ok"] and not result["drifted"]
    return result


def drift_message(step: str, result: dict[str, Any]) -> str:
    """I1: the window bounded and every expected tag came back, but something extra came with it — an untagged
    row, an unexpected tag, or a duplicate. That means company B has drifted from its generated dataset (a hand
    edit, a partial reseed, …), not that the request under test failed to bound or fetch the window."""
    bits = []
    if result["untagged"]:
        bits.append(f"untagged {result['untagged']}")
    if result["extra"]:
        bits.append(f"extra {result['extra']}")
    if result["duplicates"]:
        bits.append(f"duplicates {result['duplicates']}")
    return (f"Company B differs from the dataset in {step}: {', '.join(bits)} — re-run `setup-b` verify or "
            "restore the backup before trusting this probe again.")


async def fetch_window(ctx: "ProbeContext", step: str, template: str, licence: str, start: str, end: str, *,
                       untyped: bool = False) -> tuple[dict[str, Any], str]:
    """Fetch and decode one Voucher-collection month/day window through the ONE shared path probe 5 and probe 21
    both call (review M2/P8b — they used to decode the same kind of response two different ways: probe 5 read
    `ctx.send`'s sanitized text, probe 21 separately re-decoded `ctx.last_response.raw`). `start`/`end` are
    DD-MM-YYYY. Returns (compare_tags result, the raw response text) — `parse_vouchers` sanitizes internally, so
    the same raw text is safe both for tag comparison (`voucher_rows`) and for probe 21's byte-accurate size
    measurement (`voucher_blocks`), which is why this hands back the raw text rather than `ctx.send`'s return value.
    C43: under an educational licence a date off day 1/2/31 is refused before anything is sent (`check_date_vars`);
    callers build month windows with `month_window`.
    """
    check_date_vars(licence, start, end)
    xml = fill_month_request(template, ctx.company_name, start, end)
    await ctx.send(step, untyped_period_vars(xml) if untyped else xml)
    raw_text = ctx.last_response.raw.decode("utf-8")
    result = compare_tags(voucher_rows(raw_text), expect_window(licence, dmy(start), dmy(end)), dmy(start), dmy(end))
    return result, raw_text


def loaded_licence(environment: dict[str, Any]) -> str:
    """The licence company B was loaded under, once setup-b has finished cleanly; otherwise the part can't run."""
    if not environment.get("company_b_loaded_at"):
        raise ProbeBlocked("Company B isn't loaded yet (no company_b_loaded_at in results.json): run "
                           "`uv run --project v2 python -m v2.probes setup-b` to a clean finish first.")
    licence = environment.get("licence")
    if licence not in ("licensed", "educational"):
        raise ProbeBlocked("No licence recorded: run probe 0 first (company B's voucher dates depend on it).")
    return licence
