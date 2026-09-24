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
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from v2.probes.core import ProbeBlocked
from v2.probes.reads import parse_vouchers, tally_date
from v2.probes.setup.company_b_data import COMPANY_B_BOOKS_FROM, TAG_PREFIX, Dataset, VoucherSpec, generate

B_BOOKS_FROM_DATE = COMPANY_B_BOOKS_FROM
B_BOOKS_FROM = COMPANY_B_BOOKS_FROM.strftime("%d-%m-%Y")        # "01-04-2022"
B_BOOKS_TO = "31-03-2026"                                       # the dataset's last month (COMPANY_B_LAST_MONTH)
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
    result["match"] = (result["bounded"] and not result["untagged"] and not result["missing"]
                       and not result["extra"] and not result["duplicates"])
    return result


def loaded_licence(environment: dict[str, Any]) -> str:
    """The licence company B was loaded under, once setup-b has finished cleanly; otherwise the part can't run."""
    if not environment.get("company_b_loaded_at"):
        raise ProbeBlocked("Company B isn't loaded yet (no company_b_loaded_at in results.json): run "
                           "`uv run --project v2 python -m v2.probes setup-b` to a clean finish first.")
    licence = environment.get("licence")
    if licence not in ("licensed", "educational"):
        raise ProbeBlocked("No licence recorded: run probe 0 first (company B's voucher dates depend on it).")
    return licence
