# S0 Probes — Part 4: company-B probes 5 and 21 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified**, not at the end (tracker rules).

**Goal:** Build and run live probe 5 (do typed `SVFROMDATE`/`SVTODATE` bound a Voucher collection to a month and a
day?) and probe 21 (can FY 2022-23 be fetched month by month, and what do vouchers cost to store over 2/5/10 years
with and without `raw`?). Together they produce the confirmed `voucher_month` request S2's extractor will use, and the
storage numbers that Q22/Q23 need before S1 commits to a schema.

**Architecture:** Both probes are B-only modules that follow the existing pattern (`Probe(parts={"B": run_b})`, reads
only through `ProbeContext`, every response captured). A new read-side module, `v2/probes/company_b_view.py`, is the
one place probe code reads company B's dataset. It turns `setup/company_b_data.generate(licence)` into per-window tag
expectations and a tag comparison, so probe modules still import no write code. Probe 5 stores its working request as
a template with `__COMPANY__` / `__FROM__` / `__TO__` placeholders (`reads.fill_month_request`), and probe 21 reuses it
(S0-D7). Probe 21's size maths are pure functions in its own module and are unit-tested with hand numbers. `FakeBooks`
gains a full Voucher export that keeps its typed-dates-only behaviour (C33), plus a fast `seed_company_b()` that puts
it in the state a finished `setup-b` leaves.

**Tech Stack:** Python ≥ 3.12, httpx (`MockTransport` in tests), pytest + pytest-asyncio (`asyncio_mode = "auto"`),
uv. No new dependencies.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md): §7 "Probe 5"
and "Probe 21", §6 batch 5, §5.1–§5.7 (probe contract, context, CLI, outcomes, capture, results), S0-D6 (verdicts),
S0-D7 (never guess what another probe must confirm), §4.3 (company B), §4.6 (licence), §11.5 (fixture steps). Parent:
[`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md) decision 7b, §5 "Windows agent"
(extractor), §5 "Cloud" (minimum columns, `raw` JSONB), R27, R29, Q22, Q23, §12 probe 21.
**Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3 rows 5 and 21, §2 rows Q22 and Q23.
**Live findings this plan builds in:** tracker blocks 0c–0g and the SDD ledger
`.superpowers/sdd/2026-09-23-bi-s0-company-b-loader/progress.md` rulings C30–C42 (especially C33, C36 and C42).

**Plan parts:** part 1 [`2026-09-22-bi-s0-probes-plan.md`](2026-09-22-bi-s0-probes-plan.md) (harness, probes 0/2/1),
part 2 [`2026-09-22-bi-s0-probes-plan-part2.md`](2026-09-22-bi-s0-probes-plan-part2.md) (operator, company-A probes),
part 3 [`2026-09-23-bi-s0-company-b-loader.md`](2026-09-23-bi-s0-company-b-loader.md) (company-B loader, ✅ loaded
live). **Part 4 (this file):** probes 5 and 21 only. Probes 11, 14, 15, 22, 24 and the B parts of 3, 16, 18, 23 and
25 come in later parts.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Nothing outside `v2/` and `docs/` changes.** v2 never imports `backend`, `scripts` or `tests`. `v2/agent/` never
  imports `v2.probes`. Probe modules (`v2/probes/pNN_*.py`) never import `v2.probes.setup` or `v2.probes.operator`
  (`v2/tests/test_isolation.py::test_probe_modules_never_import_write_code`). Probe code reads the dataset **only**
  through `v2/probes/company_b_view.py`, which imports nothing from `setup/` except the pure
  `setup/company_b_data.py` (Task 1 pins both facts in `test_isolation.py`).
- **Offline tests only.** Tasks 1–6 never talk to a real Tally, never start Wine, never touch `localhost:9000`. Tests
  use `FakeBooks` (stateful, `v2/tests/probes/fake_books.py`) or `FakeTally` (canned routes,
  `v2/tests/probes/fakes.py`) over `httpx.MockTransport`.
- **C33 stays true in the fake.** `FakeBooks` honours `SVFROMDATE`/`SVTODATE` **only** with `TYPE="Date"` and
  otherwise answers for `current_period` (default 1-Apr-2025..31-Mar-2026), through the existing `requested_period()`.
  No task may weaken that. The new Voucher export route (Task 2) filters through the same `in_period`.
- **No hand edits to `v2/probes/results/`.** Only the runner writes `results.json`, and only in Task 7 (live).
  Fixtures in `v2/tests/fixtures/sync/` are also written only by the runner in Task 7.
- **Money and bytes are exact.** Amounts are `Decimal`, never float. Byte counts are `int` (UTF-8 bytes, never
  characters). Means and MB figures use `Decimal` with `ROUND_HALF_UP`, and MB means 10⁶ bytes.
- **Request rules** (`safety.check_request`): no `*` as a `NATIVEMETHOD`/`FETCH`, no `$$InDateRange`. Every read goes
  through `ctx.send`, so it is guarded and captured. One request at a time, no retries. A timeout blocks the part with
  the popup hint.
- **Step names** follow `capture._STEP` (lowercase, digits, `_ . -`). Each name is used once per part. Fixture files are
  `p05_B_<step>.xml` / `p21_B_<step>.xml` (+ `.json` sidecar).
- **Verdicts** follow S0-D6 / §5.4: CONFIRMED / DIFFERENT / FAILED / BLOCKED. DIFFERENT and FAILED need a
  `spec_impact`. A CONFIRMED part may carry one too, when the spec needs to state what was confirmed.
- **The flagged-voucher count rule (this plan's resolution; see Ambiguities).** "Counts equal the dataset's" compares
  **tag sets**. The expected set for a window is every dataset voucher dated in it **without `skip_reason`** (the USD
  sales 101/102 were never written, C36). That set includes cancelled 201/202 and optional 301/302, because they are
  vouchers and they exist in Tally (C42 only showed that Tally leaves them out of *balances*). A window is **exact**
  when it holds no out-of-window date, no untagged voucher, no duplicate tag, no tag outside the expected set, and
  every **unflagged** expected tag. Whether flagged tags come back is recorded (`flagged_returned` /
  `flagged_missing`) but is never a verdict here. Probe 3's B part owns that (S0-D7).
- **Company B guard for live runs.** Only company B, `Sharma & Sons' Probe Traders`, is loaded in Tally. It is company
  number **100000** (`s0probe/100000`, `OperatorConfig.company_numbers["B"]`). The runner's guard refuses any other
  state before sending anything. `results.json` must hold `environment.company_b_loaded_at`, which only a clean
  `setup-b` writes. Both probes BLOCK without it.
- **Timings are Wine, not representative.** Every sidecar already says so (`capture.TIMING_NOTE`). Probe 21 records
  `elapsed_ms` per step under that label. No verdict uses a timing. The tier-C timing half of probe 21 stays ⏭ (Q29).
- **Commands** (repo root `/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q`
  - one file: `uv run --project v2 pytest v2/tests/probes/<file>.py -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **Commits:** one per task, on `feat/bi-s0-probe-harness`. Stage only the files the task names (another agent may be
  working elsewhere in `v2/`). Every message ends with the session's `Co-Authored-By:` trailer line.
- **Tracker discipline:** when a task finishes, flip its tracker row (⬜ → 🟡 → ✅ with proof) and add a dated
  change-log row in the same turn (CLAUDE.md "Always update the tracker").

## Review Focus

These are the five inputs most likely to hurt a real run that the spec implies but does not spell out. Each has a
test in the task that owns the code.

1. **A voucher in the window with no `[S0-B:n]` tag** (someone typed a voucher into company B by hand, or a
   throwaway was left behind). The month must count as **not exact**, with `untagged` = 1, and probe 21 names the
   month rather than passing. Tests: Task 1 `test_compare_reports_missing_extra_untagged_and_duplicates`, Task 5
   `test_a_hand_entered_voucher_makes_its_month_inexact_and_fails`.
2. **The cancelled pair in Feb 2023, returned or not.** Either way the month is exact, and the flags are recorded but
   not judged. Tests: Task 1 `test_flagged_tags_are_recorded_but_never_decide_the_match`, Task 5
   `test_fy2022_is_reached_month_by_month_and_sizes_are_measured` (Feb shows `flagged_returned == [201, 202]`).
3. **Multi-byte text and control characters in a response** (Hindi party names and narrations, Tally's `&#4;`).
   Byte counts must be UTF-8 bytes of the block exactly as sent, and the JSON stand-in must survive `&#4;`. Tests:
   Task 4 `test_voucher_blocks_skip_the_cmpinfo_counter_and_count_utf8_bytes`,
   `test_element_json_drops_placeholders_keeps_lists_and_survives_control_chars`.
4. **Tally stops answering mid-year** (a popup appears at month 7). The part must BLOCK with the popup hint, keep the
   fixtures of the months already read, and send **no** retry. Test: Task 5
   `test_a_timeout_mid_year_blocks_with_the_popup_hint_and_is_not_retried`.
5. **Nobody is at the Tally UI** (auto mode or `--non-interactive`) when probe 21 reaches the period lock. The lock
   step must be recorded as "not attempted", **not** BLOCK the whole part. Test: Task 5
   `test_period_lock_is_not_attempted_without_a_person` (parametrized: non-interactive and auto).

---

## Before you start

- [ ] **Step 0.1: Confirm the base.** Run `git log --oneline -3` and `git status --short -- v2/`.
  Expected: HEAD contains `1391e67` (C42) and `c7151b3`, and there are no modified files under `v2/probes/setup/` or
  `v2/tests/` (another agent's C42 work must be committed first; `v2/probes/results/results.json` may show as modified
  because of `company_b_loaded_at`. Leave it alone.)
- [ ] **Step 0.2: Record BASE.** Run `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1`.
  Expected: `539 passed` (as of `1391e67`). Write the number down as BASE. This plan adds **41** tests, so the target
  is BASE + 41.

## File Structure

| File | Responsibility |
|---|---|
| `v2/probes/reads.py` *(modify)* | Add `VOUCHER_MONTH_FIELDS`, `FROM_PLACEHOLDER`, `TO_PLACEHOLDER`, `fill_month_request()` and `untyped_period_vars()`. These are shared by probes 5 and 21 now, and by S2 later. |
| `v2/probes/company_b_view.py` *(create)* | The read-side view of company B's dataset: `tag_of`, `kind_label`, `expect_window`, `voucher_rows`, `compare_tags`, `loaded_licence`, and the books-window constants. Its only link to `setup/` is `company_b_data`. |
| `v2/probes/p05_voucher_month_bounds.py` *(create)* | Probe 5: typed month, untyped month (evidence), the formula candidate if needed, the day window, and a TB typed/untyped pair (evidence). Confirms `voucher_month`. |
| `v2/probes/p21_full_history_reach.py` *(create)* | Probe 21: BooksFrom, 12 months of FY 2022-23, one current-FY sample month, pure size and storage maths, and the optional period lock. |
| `v2/probes/registry.py` *(modify)* | `module=` for probes 5 and 21. In `ALL_ORDER` and `FIRST_ORDER`, (5, "B") runs immediately before (21, "B"). |
| `v2/tests/probes/fake_books.py` *(modify)* | A full Voucher export for `S0VoucherMonth` / `S0P05MonthFormula` (typed-dates-only via `in_period`), `BooksFrom` from state, and `seed_company_b(books, licence)`. |
| `v2/tests/probes/test_company_b_view.py` *(create)* | Task 1 tests. |
| `v2/tests/probes/test_reads.py` *(modify)* | Task 1 tests for the two new read helpers. |
| `v2/tests/test_isolation.py` *(modify)* | Task 1: `company_b_view` is the only bridge, and `company_b_data` is pure. |
| `v2/tests/probes/test_fake_books_vouchers.py` *(create)* | Task 2 tests. It is a new file so that it doesn't collide with other agents' edits to `test_fake_books_masters.py`. |
| `v2/tests/probes/test_p05_voucher_month_bounds.py` *(create)* | Task 3 tests. |
| `v2/tests/probes/test_cli.py` *(modify)* | `test_run_unbuilt_probe_returns_2` moves from probe 5 (now built) to probe 11. |
| `v2/tests/probes/test_p21_full_history_reach.py` *(create)* | Task 4 and Task 5 tests. |

---

### Task 1: Month-request helpers and the company-B dataset view

**Files:**
- Modify: `v2/probes/reads.py` (imports at the top; new block after `voucher_request`)
- Create: `v2/probes/company_b_view.py`
- Test: `v2/tests/probes/test_reads.py` (append), `v2/tests/probes/test_company_b_view.py` (create),
  `v2/tests/test_isolation.py` (append)

**Interfaces:**
- Consumes: `envelopes.COMPANY_PLACEHOLDER`, `envelopes.esc`, `reads.voucher_request`, `reads.parse_vouchers`,
  `reads.tally_date`, `core.ProbeBlocked`, and `setup.company_b_data.{COMPANY_B_BOOKS_FROM, TAG_PREFIX, Dataset,
  VoucherSpec, generate}`.
- Produces (used by Tasks 2–5):
  ```python
  # v2/probes/reads.py
  VOUCHER_MONTH_FIELDS: list[str]      # GUID … IsPostDated, AllLedgerEntries, AllInventoryEntries
  FROM_PLACEHOLDER = "__FROM__"
  TO_PLACEHOLDER = "__TO__"
  def fill_month_request(template: str, company: str, from_date: str, to_date: str) -> str
  def untyped_period_vars(xml: str) -> str
  # v2/probes/company_b_view.py
  B_BOOKS_FROM: str            # "01-04-2022"
  B_BOOKS_FROM_DATE: date      # date(2022, 4, 1)
  B_BOOKS_TO: str              # "31-03-2026"
  def tag_of(narration: str) -> int | None
  def kind_label(v: VoucherSpec) -> str                     # e.g. "sales+inventory+bills", "payment"
  def dataset(licence: str) -> Dataset                      # lru_cached generate()
  @dataclass(frozen=True) class WindowExpectation: written: dict[int, VoucherSpec]; flagged: frozenset[int];
                                                   skipped: frozenset[int]; unflagged (property)
  def expect_window(licence: str, start: date, end: date) -> WindowExpectation
  def voucher_rows(text: str) -> list[dict]                 # [{"tag": int | None, "date": date | None}]
  def compare_tags(rows: list[dict], expected: WindowExpectation, start: date, end: date) -> dict
  def loaded_licence(environment: dict) -> str              # raises ProbeBlocked
  ```

- [ ] **Step 1: Write the failing tests**

Append to `v2/tests/probes/test_reads.py`:

```python
def test_fill_month_request_escapes_the_company_and_fills_typed_dates():
    import xml.etree.ElementTree as ET
    from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER
    from v2.probes.reads import (FROM_PLACEHOLDER, TO_PLACEHOLDER, VOUCHER_MONTH_FIELDS, fill_month_request,
                                 voucher_request)
    template = voucher_request("S0VoucherMonth", VOUCHER_MONTH_FIELDS, COMPANY_PLACEHOLDER,
                               from_date=FROM_PLACEHOLDER, to_date=TO_PLACEHOLDER)
    xml = fill_month_request(template, "Sharma & Sons' Probe Traders", "01-06-2023", "30-06-2023")
    assert "<SVCurrentCompany>Sharma &amp; Sons&apos; Probe Traders</SVCurrentCompany>" in xml
    assert '<SVFROMDATE TYPE="Date">01-06-2023</SVFROMDATE>' in xml
    assert '<SVTODATE TYPE="Date">30-06-2023</SVTODATE>' in xml
    assert "__" not in xml
    assert ET.fromstring(xml).find(".//SVCurrentCompany").text == "Sharma & Sons' Probe Traders"


def test_untyped_period_vars_strips_only_the_date_type():
    from v2.agent.tally.envelopes import wrap_report
    from v2.probes.reads import untyped_period_vars
    typed = wrap_report("Trial Balance", "01-04-2022", "30-06-2023", "B", extra_vars={"EXPLODEFLAG": "Yes"})
    untyped = untyped_period_vars(typed)
    assert "<SVFROMDATE>01-04-2022</SVFROMDATE>" in untyped
    assert "<SVTODATE>30-06-2023</SVTODATE>" in untyped
    assert 'TYPE="Date"' not in untyped
    assert untyped.replace("<SVFROMDATE>", '<SVFROMDATE TYPE="Date">').replace(
        "<SVTODATE>", '<SVTODATE TYPE="Date">') == typed
```

Create `v2/tests/probes/test_company_b_view.py`:

```python
from collections import Counter
from datetime import date

import pytest

from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_FROM_DATE, B_BOOKS_TO, compare_tags, dataset,
                                      expect_window, kind_label, loaded_licence, tag_of, voucher_rows)
from v2.probes.core import ProbeBlocked
from v2.tests.probes.fakes import vch, vouchers_xml

JUNE = (date(2023, 6, 1), date(2023, 6, 30))


def _rows(tags_and_days):
    return [{"tag": tag, "date": day} for tag, day in tags_and_days]


def test_tag_of_reads_the_loader_tag_and_nothing_else():
    assert tag_of("[S0-B:281] Sale to शर्मा ट्रेडर्स") == 281
    assert tag_of("  [S0-B:7] Receipt") == 7
    assert tag_of("S0-throwaway 1") is None
    assert tag_of("Paid [S0-B:9] later") is None
    assert tag_of("") is None
    assert (B_BOOKS_FROM, B_BOOKS_FROM_DATE, B_BOOKS_TO) == ("01-04-2022", date(2022, 4, 1), "31-03-2026")


def test_windows_follow_the_written_dataset():
    june = expect_window("educational", *JUNE)
    assert len(june.written) == 20 and not june.flagged and not june.skipped
    sep = expect_window("educational", date(2022, 9, 1), date(2022, 9, 30))
    assert len(sep.written) == 18 and sep.skipped == {101, 102}          # C36: the USD sales were never written
    feb = expect_window("educational", date(2023, 2, 1), date(2023, 2, 28))
    assert len(feb.written) == 20 and feb.flagged == {201, 202}         # cancelled: written, flagged
    assert feb.unflagged == frozenset(feb.written) - {201, 202}
    day = expect_window("educational", date(2023, 6, 1), date(2023, 6, 1))
    assert len(day.written) == 10                                        # Educational: the 1st and the 2nd only
    assert len(expect_window("licensed", date(2023, 6, 1), date(2023, 6, 1)).written) == 1


def test_fy2022_kind_mix_is_what_probe_21_weights_storage_by():
    fy = expect_window("educational", date(2022, 4, 1), date(2023, 3, 31))
    assert len(fy.written) == 238
    assert Counter(kind_label(v) for v in fy.written.values()) == Counter({
        "sales+inventory+bills": 81, "purchase+inventory+bills": 60, "receipt+bills": 40, "payment+bills": 24,
        "sales+inventory": 13, "payment": 12, "receipt": 8})
    assert dataset("educational") is dataset("educational")            # cached, generated once


def test_voucher_rows_read_tag_and_date_and_skip_the_cmpinfo_counter():
    text = vouchers_xml([vch({"DATE": "20230601", "NARRATION": "[S0-B:281] Sale"}),
                         vch({"DATE": "20230602", "NARRATION": "hand entry"})])
    assert voucher_rows(text) == [{"tag": 281, "date": date(2023, 6, 1)}, {"tag": None, "date": date(2023, 6, 2)}]


def test_an_exact_window_matches():
    june = expect_window("educational", *JUNE)
    result = compare_tags(_rows((t, v.date) for t, v in june.written.items()), june, *JUNE)
    assert result["match"] and result["bounded"]
    assert (result["returned"], result["expected_written"], result["expected_unflagged"]) == (20, 20, 20)
    assert result["date_span"] == ["2023-06-01", "2023-06-02"]


def test_compare_reports_missing_extra_untagged_and_duplicates():
    june = expect_window("educational", *JUNE)
    tags = sorted(june.written)
    rows = _rows([(t, date(2023, 6, 1)) for t in tags[1:]] + [(tags[1], date(2023, 6, 1)), (101, date(2023, 6, 1)),
                                                              (None, date(2023, 6, 2))])
    result = compare_tags(rows, june, *JUNE)
    assert not result["match"]
    assert result["missing"] == [tags[0]]
    assert result["extra"] == [101]                         # a skipped tag showing up is extra, never expected
    assert result["duplicates"] == [tags[1]]
    assert result["untagged"] == 1


def test_a_date_outside_the_window_is_not_bounded():
    june = expect_window("educational", *JUNE)
    rows = _rows([(t, v.date) for t, v in june.written.items()] + [(301, date(2023, 7, 1))])
    result = compare_tags(rows, june, *JUNE)
    assert not result["bounded"] and result["out_of_window"] == 1 and not result["match"]
    assert result["date_span"] == ["2023-06-01", "2023-07-01"]


def test_flagged_tags_are_recorded_but_never_decide_the_match():
    feb_window = (date(2023, 2, 1), date(2023, 2, 28))
    feb = expect_window("educational", *feb_window)
    with_flags = compare_tags(_rows((t, v.date) for t, v in feb.written.items()), feb, *feb_window)
    without_flags = compare_tags(_rows((t, feb.written[t].date) for t in feb.unflagged), feb, *feb_window)
    assert with_flags["match"] and with_flags["flagged_returned"] == [201, 202] and not with_flags["flagged_missing"]
    assert without_flags["match"] and without_flags["flagged_missing"] == [201, 202]


def test_loaded_licence_needs_a_clean_setup_b_and_a_recorded_licence():
    with pytest.raises(ProbeBlocked, match="setup-b"):
        loaded_licence({"licence": "educational"})
    with pytest.raises(ProbeBlocked, match="probe 0"):
        loaded_licence({"company_b_loaded_at": "2026-09-24T13:02:33+05:30"})
    assert loaded_licence({"licence": "educational", "company_b_loaded_at": "x"}) == "educational"
```

Append to `v2/tests/test_isolation.py`:

```python
def test_company_b_view_is_the_only_bridge_from_probes_to_the_dataset():
    modules = imported_modules((V2_ROOT / "probes" / "company_b_view.py").read_text(encoding="utf-8"))
    reached = [m for m in modules if m.startswith(("v2.probes.setup", "v2.probes.operator"))]
    assert reached, "company_b_view should read the dataset"
    assert all(m.startswith("v2.probes.setup.company_b_data") for m in reached), reached


def test_the_dataset_module_is_pure():
    modules = imported_modules((V2_ROOT / "probes" / "setup" / "company_b_data.py").read_text(encoding="utf-8"))
    assert [m for m in modules if m.split(".")[0] in {"v2", "httpx"}] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_reads.py v2/tests/probes/test_company_b_view.py v2/tests/test_isolation.py -q`
Expected: FAIL with `ImportError: cannot import name 'fill_month_request'` and
`ModuleNotFoundError: No module named 'v2.probes.company_b_view'`.

- [ ] **Step 3: Implement the read helpers**

In `v2/probes/reads.py`, add `import re` to the imports, and change the envelopes import to
`from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, esc, wrap_collection`. Then add this block directly after
`voucher_request`:

```python
# --- the month request (probe 5 confirms it, probe 21 and S2's extractor reuse it) --------------------------------
FROM_PLACEHOLDER = "__FROM__"
TO_PLACEHOLDER = "__TO__"
# Everything S1 stores for a voucher (Part 1 §5 "Cloud" minimum columns) plus the nested lists (probe 6: fetched whole).
VOUCHER_MONTH_FIELDS = ["GUID", "MasterID", "AlterID", "Date", "VoucherTypeName", "VoucherNumber", "Reference",
                        "PartyLedgerName", "Narration", "IsCancelled", "IsOptional", "IsPostDated",
                        "AllLedgerEntries", "AllInventoryEntries"]
_TYPED_DATE_VAR = re.compile(r'<(SV[A-Z0-9]*DATE) TYPE="Date">', re.IGNORECASE)


def fill_month_request(template: str, company: str, from_date: str, to_date: str) -> str:
    """A confirmed month template (placeholders __COMPANY__ / __FROM__ / __TO__) for one company and window.

    The company is XML-escaped here; dates are DD-MM-YYYY. Works for both forms probe 5 can confirm: typed period
    variables, or a `$Date` formula whose bounds carry the placeholders.
    """
    return (template.replace(COMPANY_PLACEHOLDER, esc(company))
            .replace(FROM_PLACEHOLDER, from_date).replace(TO_PLACEHOLDER, to_date))


def untyped_period_vars(xml: str) -> str:
    """The same request with TYPE="Date" stripped from every SV*DATE variable. Evidence only (C33): probe 5 sends
    it once to record Tally's silent current-period fallback. Nothing may use it for data."""
    return _TYPED_DATE_VAR.sub(r"<\1>", xml)
```

- [ ] **Step 4: Implement `company_b_view.py`**

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_reads.py v2/tests/probes/test_company_b_view.py v2/tests/test_isolation.py -q`
Expected: PASS (12 new tests). Then run the full suite: `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1` →
`BASE + 12 passed`.

- [ ] **Step 6: Commit**

```bash
git add v2/probes/reads.py v2/probes/company_b_view.py v2/tests/probes/test_reads.py \
        v2/tests/probes/test_company_b_view.py v2/tests/test_isolation.py
git commit -m "feat(bi/v2): month-request helpers + company-B dataset view for probes 5/21" \
           -m "Co-Authored-By: <session trailer>"
```

- [ ] **Step 7: Tracker.** Tracker §3 row 5 → 🟡 ("plan part 4 Task 1 ✅ `<sha>`"), and add a change-log row.

---

### Task 2: `FakeBooks` exports full vouchers for the month request, and can be seeded as company B

**Files:**
- Modify: `v2/tests/probes/fake_books.py` (imports; the counters branch in `_answer`; a new Voucher-export branch in
  `_answer` just after `in_period` is computed; a module-level `_export_voucher()`; a module-level `seed_company_b()`)
- Test: `v2/tests/probes/test_fake_books_vouchers.py` (create)

**Interfaces:**
- Consumes: Task 1 (`reads.VOUCHER_MONTH_FIELDS`, `FROM_PLACEHOLDER`, `TO_PLACEHOLDER`, `fill_month_request`,
  `untyped_period_vars`) and `setup.company_b_data.generate` (test code may import it).
- Produces (used by Tasks 3 and 5):
  ```python
  def seed_company_b(books: FakeBooks, licence: str = "educational") -> None
  # FakeBooks: a Voucher collection whose body names S0VoucherMonth or S0P05MonthFormula is answered with full
  # <VOUCHER> exports (header + ALLLEDGERENTRIES.LIST with the party line's BILLALLOCATIONS + ALLINVENTORYENTRIES.LIST)
  # for the vouchers inside requested_period() — the typed window, or current_period when untyped (C33).
  # Counters answer BooksFrom = state["books_from"] (default "20250401").
  ```

- [ ] **Step 1: Write the failing tests**

```python
# v2/tests/probes/test_fake_books_vouchers.py
from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER
from v2.probes.companies import COMPANIES
from v2.probes.p01_company_counters import COUNTERS_REQUEST
from v2.probes.reads import (FROM_PLACEHOLDER, TO_PLACEHOLDER, VOUCHER_MONTH_FIELDS, fill_month_request,
                             parse_vouchers, untyped_period_vars, voucher_request)
from v2.agent.tally.xml_utils import read_objects
from v2.tests.probes.fake_books import FakeBooks, seed_company_b, sync_client

B = COMPANIES["B"]
TEMPLATE = voucher_request("S0VoucherMonth", VOUCHER_MONTH_FIELDS, COMPANY_PLACEHOLDER,
                           from_date=FROM_PLACEHOLDER, to_date=TO_PLACEHOLDER)


def _post(books: FakeBooks, xml: str) -> str:
    with sync_client(books.transport()) as client:
        return client.post("/", content=xml.encode("utf-8")).text


def _seeded(licence="educational") -> FakeBooks:
    books = FakeBooks(name=B)
    seed_company_b(books, licence)
    return books


def test_seeded_company_b_holds_every_written_voucher_with_its_flags():
    state = _seeded().state
    by_tag = {v["narration"].split("]")[0] + "]": v for v in state["vouchers"].values()}
    assert len(state["vouchers"]) == 958                              # 960 minus the skipped USD sales (C36)
    assert "[S0-B:101]" not in by_tag and "[S0-B:102]" not in by_tag
    assert by_tag["[S0-B:201]"]["cancelled"] == "Yes" and by_tag["[S0-B:302]"]["optional"] == "Yes"
    assert by_tag["[S0-B:1]"]["cancelled"] == by_tag["[S0-B:1]"]["optional"] == "No"
    assert state["books_from"] == "20220401"


def test_a_typed_month_returns_exactly_that_month_in_full():
    vouchers = parse_vouchers(_post(_seeded(), fill_month_request(TEMPLATE, B, "01-06-2023", "30-06-2023")))
    assert len(vouchers) == 20
    assert {v["header"]["DATE"][:6] for v in vouchers} == {"202306"}
    sale = next(v for v in vouchers if v["header"]["NARRATION"].startswith("[S0-B:281]"))
    assert sale["header"]["VOUCHERTYPENAME"] in ("Sales", "Sales - GST") and sale["header"]["GUID"]
    assert sale["ledger_lines"][0]["bills"][0]["BILLTYPE"] == "New Ref"
    assert len(sale["inventory"]) == 1


def test_an_untyped_window_silently_answers_for_the_current_period():
    xml = untyped_period_vars(fill_month_request(TEMPLATE, B, "01-06-2023", "30-06-2023"))
    dates = sorted(v["header"]["DATE"] for v in parse_vouchers(_post(_seeded(), xml)))
    assert len(dates) == 240 and (dates[0], dates[-1]) == ("20250401", "20260331")


def test_counters_report_books_from_from_state():
    def books_from(books):
        return read_objects(_post(books, COUNTERS_REQUEST), "COMPANY", ["BooksFrom"])[0]["BooksFrom"]
    assert books_from(FakeBooks()) == "20250401"
    assert books_from(_seeded()) == "20220401"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_fake_books_vouchers.py -q`
Expected: FAIL with `ImportError: cannot import name 'seed_company_b'`.

- [ ] **Step 3: Implement**

In `fake_books.py`, add `from v2.agent.tally.envelopes import esc` and add `vouchers_xml` to the existing `fakes`
import. In `_answer`'s `S0CompanyCounters` branch, replace `"BooksFrom": "20250401"` with
`"BooksFrom": state.get("books_from", "20250401")`. Right after the `in_period = {…}` line, add:

```python
        if "<TYPE>Voucher</TYPE>" in body and ("S0VoucherMonth" in body or "S0P05MonthFormula" in body):
            # Probe 5's month request and its formula candidate: full exports, bounded ONLY by the typed period
            # (C33: an untyped one reads current_period). The fake does not evaluate the formula; typed dates always
            # bound here, so probe 5 never needs it against FakeBooks (its formula path is tested with FakeTally).
            return vouchers_xml([_export_voucher(state, mid, v)
                                 for mid, v in sorted(in_period.items(), key=lambda kv: int(kv[0]))])
```

Add these module-level functions (below `_effective_bills`):

```python
def _export_voucher(state: dict, mid: str, v: dict) -> str:
    """One stored voucher the way probe 5's month request gets it back: header, ledger lines (the voucher's bill
    postings on its first line, the party line), and inventory rows. It is shaped for the probes' parsers (reads.
    parse_vouchers), not a byte-for-byte copy of live Tally. Probe 21's live byte counts come from live Tally only."""
    lines = v.get("lines", [])
    header = {"DATE": v["date"], "GUID": f"{state['guid']}-{int(mid):08x}", "MASTERID": mid, "ALTERID": mid,
              "VOUCHERTYPENAME": v.get("vch_type", ""), "VOUCHERNUMBER": mid, "REFERENCE": "",
              "PARTYLEDGERNAME": lines[0]["ledger"] if lines else "", "NARRATION": v["narration"],
              "ISCANCELLED": v["cancelled"], "ISOPTIONAL": v["optional"], "ISPOSTDATED": v["post_dated"]}
    body = "".join(f"<{k}>{esc(str(value))}</{k}>" for k, value in header.items())
    for i, line in enumerate(lines):
        bills = "".join(f"<BILLALLOCATIONS.LIST><NAME>{esc(b['name'])}</NAME><BILLTYPE>{esc(b['type'])}</BILLTYPE>"
                        f"<AMOUNT>{b['amount']}</AMOUNT></BILLALLOCATIONS.LIST>"
                        for b in (v.get("bills", []) if i == 0 else []))
        body += (f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{esc(line['ledger'])}</LEDGERNAME>"
                 f"<ISDEEMEDPOSITIVE>{line['deemed_positive']}</ISDEEMEDPOSITIVE><AMOUNT>{line['amount']}</AMOUNT>"
                 f"{bills or '<BILLALLOCATIONS.LIST>  </BILLALLOCATIONS.LIST>'}</ALLLEDGERENTRIES.LIST>")
    for inv in v.get("inventory", []):
        body += (f"<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>{esc(inv['item'])}</STOCKITEMNAME>"
                 f"<ACTUALQTY> {inv['qty'].lstrip('-')}</ACTUALQTY></ALLINVENTORYENTRIES.LIST>")
    return f'<VOUCHER VCHTYPE="{esc(header["VOUCHERTYPENAME"])}">{body}</VOUCHER>'


def seed_company_b(books: "FakeBooks", licence: str = "educational") -> None:
    """Company B as a clean `setup-b` leaves it: every written voucher on record with its flags, BooksFrom
    1-Apr-2022. It goes straight into state, NOT through the loader (read-probe tests only; the loader has its own
    tests). Skipped vouchers (C36) are absent. A cancelled voucher keeps no bill postings, as `_voucher` does."""
    from v2.probes.setup.company_b_data import generate

    def fill(state: dict) -> None:
        state["books_from"] = "20220401"
        for v in generate(licence).vouchers:
            if v.skip_reason:
                continue
            mid = str(state["next_master_id"])
            state["next_master_id"] += 1
            state["vouchers"][mid] = {
                "narration": v.narration, "date": v.date.strftime("%Y%m%d"), "post_dated": "No",
                "cancelled": "Yes" if v.cancelled else "No", "optional": "Yes" if v.optional else "No",
                "vch_type": v.vch_type,
                "lines": [{"ledger": l.ledger, "amount": f"{l.amount:.2f}",
                           "deemed_positive": "Yes" if l.deemed_positive else "No"} for l in v.lines],
                "inventory": [{"item": i.item, "qty": f"{i.qty if v.kind == 'purchase' else -i.qty}"}
                              for i in v.inventory],
                "bills": [] if v.cancelled else [{"name": b.name, "type": b.bill_type, "amount": f"{b.amount:.2f}"}
                                                 for b in v.bills]}
    books.edit_state(fill)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_fake_books_vouchers.py -q` → 4 passed. Then run the full suite
→ `BASE + 16 passed`. The existing loader tests must stay green, because the counters change keeps the old default.

- [ ] **Step 5: Commit**

```bash
git add v2/tests/probes/fake_books.py v2/tests/probes/test_fake_books_vouchers.py
git commit -m "test(bi/v2): FakeBooks exports full vouchers for the month request; seed_company_b" \
           -m "Co-Authored-By: <session trailer>"
```

- [ ] **Step 6: Tracker.** Add a change-log row ("part 4 Task 2 `<sha>`").

---

### Task 3: Probe 5, month bounds on a Voucher collection

**Files:**
- Create: `v2/probes/p05_voucher_month_bounds.py`
- Modify: `v2/probes/registry.py` (probe 5's `ProbeInfo` gains `module=`; `FIRST_ORDER` and `ALL_ORDER` put (5, "B")
  immediately before (21, "B"))
- Modify: `v2/tests/probes/test_cli.py::test_run_unbuilt_probe_returns_2` (use probe **11**, not 5)
- Test: `v2/tests/probes/test_p05_voucher_month_bounds.py` (create)

**Interfaces:**
- Consumes: Task 1 (`reads.*` month helpers, `company_b_view.*`), Task 2 (`seed_company_b`, the FakeBooks export),
  `reads.dmy`, `reads.exploded_tb_rows`, `reads.primary_group_rows`, `envelopes.wrap_report`, `COMPANY_PLACEHOLDER`.
- Produces (used by Task 5, and later by S2):
  ```python
  # results.json → confirmed_requests["voucher_month"] =
  #   {"probe": 5, "xml_template": <template>, "form": "svdates_typed" | "formula",
  #    "fields": VOUCHER_MONTH_FIELDS, "day_window_exact": bool,
  #    "placeholders": ["__COMPANY__", "__FROM__", "__TO__"]}
  # filled with reads.fill_month_request(template, company, "DD-MM-YYYY", "DD-MM-YYYY")
  MONTH_COLLECTION = "S0VoucherMonth"; FORMULA_COLLECTION = "S0P05MonthFormula"
  PROBE: Probe   # id=5, name="voucher_month_bounds", parts={"B": run_b}, requires=(0,), educational_sensitive=True
  ```
- Steps captured, in order: `month_svdates`, `month_svdates_untyped`, `month_formula` (only when the typed form isn't
  exact), `day_svdates` (only when a form works), `report_tb_typed`, `report_tb_untyped`.

**Why June 2023:** it is FY 2023-24, so it lies outside the company's current period (1-Apr-2025..31-Mar-2026), and an
untyped request is guaranteed to answer something different. It holds no flagged, skipped or boundary voucher. Under
Educational its 20 vouchers fall on the 1st and 2nd only (June has 30 days, and `_educational_days` gives
`(1, 2)`), so the one-day window 01-06-2023 holds exactly 10. Under licensed it holds 1 (slot 8). Every expected
figure comes from `expect_window(licence, …)`, never from these comments.

- [ ] **Step 1: Write the failing tests**

```python
# v2/tests/probes/test_p05_voucher_month_bounds.py
from datetime import date

from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import expect_window
from v2.probes.registry import ALL_ORDER, FIRST_ORDER
from v2.probes.results import ResultsStore
from v2.probes.runner import EDUCATIONAL_SUFFIX, run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, objects_xml, ready_store, vch, vouchers_xml

B = COMPANIES["B"]
JUNE = (date(2023, 6, 1), date(2023, 6, 30))
JUNE_1 = (date(2023, 6, 1), date(2023, 6, 1))
LOADED_AT = "2026-09-24T13:02:33+05:30"


def _store(tmp_path, licence="educational", loaded=True) -> ResultsStore:
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence=licence)
    if loaded:
        store.update_environment(company_b_loaded_at=LOADED_AT)
    return store


async def _run_books(tmp_path, books, **store_kwargs):
    store = _store(tmp_path, **store_kwargs)
    await run_probe(p05.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store, store.probe_entry(5)["parts"]["B"]


def _books(licence="educational") -> FakeBooks:
    books = FakeBooks(name=B)
    seed_company_b(books, licence)
    return books


def _vouchers(window, *, extra=()):
    exp = expect_window("educational", *window)
    return vouchers_xml([vch({"DATE": v.date.strftime("%Y%m%d"), "VOUCHERTYPENAME": v.vch_type,
                              "NARRATION": v.narration}) for v in exp.written.values()] + list(extra))


JULY_STRAY = vch({"DATE": "20230701", "VOUCHERTYPENAME": "Sales", "NARRATION": "[S0-B:301] Sale"})


def _b_tally(month_route, formula_route=None) -> FakeTally:
    fake = FakeTally([B])
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{
        "Name": B, "GUID": "g-b", "AltVchId": "958", "AltMstId": "40", "BooksFrom": "20220401",
        "LastVoucherDate": "20260331", "AlterID": "40"}]))
    fake.route("S0P05MonthFormula", formula_route or (lambda body: vouchers_xml([])))
    fake.route("S0VoucherMonth", month_route)
    return fake


async def _run_fake(tmp_path, fake):
    client, _, capture = make_harness(tmp_path, fake)
    store = _store(tmp_path)
    await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store, store.probe_entry(5)["parts"]["B"]


async def test_typed_svdates_bound_june_2023_and_the_request_is_confirmed(tmp_path):
    store, part = await _run_books(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["month_typed"]["match"] and obs["month_typed"]["returned"] == 20
    assert obs["month_untyped"]["returned"] == 240 and not obs["month_untyped"]["bounded"]
    assert obs["month_untyped"]["date_span"] == ["2025-04-01", "2026-03-31"]
    assert obs["c33_reproduced"] is True
    assert obs["day"]["match"] and obs["day"]["returned"] == 10
    assert obs["report_period_vars"]["identical_bytes"] is False
    assert "C33 reproduced" in part["summary"] and part["summary"].endswith(EDUCATIONAL_SUFFIX)
    assert 'TYPE="Date"' in part["spec_impact"]
    assert part["fixtures"] == ["p05_B_month_svdates.xml", "p05_B_month_svdates_untyped.xml",
                                "p05_B_day_svdates.xml", "p05_B_report_tb_typed.xml", "p05_B_report_tb_untyped.xml"]
    confirmed = store.confirmed("voucher_month")
    assert confirmed["probe"] == 5 and confirmed["form"] == "svdates_typed" and confirmed["day_window_exact"]
    assert '<SVFROMDATE TYPE="Date">__FROM__</SVFROMDATE>' in confirmed["xml_template"]
    assert "<SVCurrentCompany>__COMPANY__</SVCurrentCompany>" in confirmed["xml_template"]


async def test_licensed_books_put_one_voucher_on_the_first(tmp_path):
    _, part = await _run_books(tmp_path, _books("licensed"), licence="licensed")
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["day"]["returned"] == 1


async def test_a_licence_that_does_not_match_the_books_shows_in_the_day_window(tmp_path):
    _, part = await _run_books(tmp_path, _books("educational"), licence="licensed")
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["month_typed"]["match"]                  # same 20 tags, all inside June either way
    assert not part["observations"]["day"]["match"] and "half-month" in part["spec_impact"]


async def test_company_b_not_loaded_blocks_before_any_voucher_request(tmp_path):
    books = _books()
    _, part = await _run_books(tmp_path, books, loaded=False)
    assert part["outcome"] == "BLOCKED" and "setup-b" in part["summary"]
    assert not any("<TYPE>Voucher</TYPE>" in r for r in books.requests)


async def test_the_formula_is_confirmed_when_typed_svdates_do_not_bound(tmp_path):
    fake = _b_tally(lambda body: _vouchers(JUNE, extra=[JULY_STRAY]),
                    lambda body: _vouchers(JUNE if '"30-06-2023"' in body else JUNE_1))
    store, part = await _run_fake(tmp_path, fake)
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["month_formula"]["match"] and "$Date formula" in part["spec_impact"]
    confirmed = store.confirmed("voucher_month")
    assert confirmed["form"] == "formula" and "S0P05InWindow" in confirmed["xml_template"]
    assert "__FROM__" in confirmed["xml_template"]
    assert "p05_B_month_formula.xml" in part["fixtures"]


async def test_neither_form_bounding_fails_and_confirms_nothing(tmp_path):
    stray = lambda body: _vouchers(JUNE, extra=[JULY_STRAY])       # noqa: E731
    store, part = await _run_fake(tmp_path, _b_tally(stray, stray))
    assert part["outcome"] == "FAILED"
    assert "filters by date in Python" in part["spec_impact"]
    assert store.confirmed("voucher_month") is None
    assert "p05_B_day_svdates.xml" not in part["fixtures"] and "p05_B_report_tb_typed.xml" in part["fixtures"]


async def test_an_untyped_answer_that_is_also_bounded_is_flagged_not_trusted(tmp_path):
    fake = _b_tally(lambda body: _vouchers(JUNE_1 if "01-06-2023</SVTODATE>" in body else JUNE))
    _, part = await _run_fake(tmp_path, fake)
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["c33_reproduced"] is False
    assert "C33 NOT reproduced" in part["summary"]


def test_ordered_runs_put_probe_5_right_before_probe_21():
    for order in (ALL_ORDER, FIRST_ORDER):
        assert order.index((5, "B")) == order.index((21, "B")) - 1
```

In `v2/tests/probes/test_cli.py`, change `test_run_unbuilt_probe_returns_2` to run `"11"` instead of `"5"`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p05_voucher_month_bounds.py -q`
Expected: FAIL with `ImportError: cannot import name 'p05_voucher_month_bounds'`.

- [ ] **Step 3: Implement the probe**

```python
# v2/probes/p05_voucher_month_bounds.py
"""Probe 5: do SVFROMDATE / SVTODATE bound a Voucher collection to a month and a day? (S0 spec §7 "Probe 5", B)

Feeds the S2 extractor's month chunks. C33 (live 2026-09-24): Tally honours the period variables only with
TYPE="Date". Untyped, it silently answers for the company's current period. v2's envelope renderer always types them,
so the typed form is the one under test. The untyped form is sent once as recorded evidence of the silent fallback,
and it never decides the outcome. One Trial Balance pair (typed / untyped) is recorded the same way. Whether an as-on
report is history is probe 18's B part to settle, not this probe's (S0-D7).
"""
from __future__ import annotations

from typing import Any

from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, wrap_report
from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_TO, compare_tags, expect_window, loaded_licence,
                                      voucher_rows)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import (FROM_PLACEHOLDER, TO_PLACEHOLDER, VOUCHER_MONTH_FIELDS, dmy, exploded_tb_rows,
                             fill_month_request, primary_group_rows, untyped_period_vars, voucher_request)

MONTH_FROM, MONTH_TO = "01-06-2023", "30-06-2023"   # FY 2023-24: outside the current period; no flagged voucher
DAY = "01-06-2023"
REPORT_AS_ON = MONTH_TO
MONTH_COLLECTION = "S0VoucherMonth"
FORMULA_COLLECTION = "S0P05MonthFormula"
FORMULA_FILTER = "S0P05InWindow"
# Candidate only (spec §7 step 2; never $$InDateRange, LESSONS §3). A collection's scope is its period, so the formula
# runs inside a typed books-wide period, and the placeholders carry the window.
FORMULA_CANDIDATE = f'$Date >= $$Date:"{FROM_PLACEHOLDER}" AND $Date <= $$Date:"{TO_PLACEHOLDER}"'

TYPED_IMPACT = ('The extractor\'s month request types its period variables (TYPE="Date", C33): untyped, Tally '
                "silently answers for the company's current period, so an untyped chunk looks healthy and is wrong "
                "(Part 1 §5 extractor).")
FORMULA_IMPACT = ("Typed SVFROMDATE/SVTODATE don't bound a Voucher collection: the extractor bounds month chunks with "
                  "the $Date formula filter inside a books-wide typed period (Part 1 §5 extractor).")
DAY_IMPACT = ("A one-day window doesn't return exactly that day's vouchers, so month chunks can't auto-split to days: "
              "the extractor splits to half-months at most and the ~5k-voucher chunk cap is re-sized (Part 1 §5, R3).")
FAILED_IMPACT = ("Neither form bounds a Voucher collection: the extractor fetches wider windows and filters by date in "
                 "Python, and the chunk cap is re-sized (Part 1 §5 extractor, R3).")


def svdates_template() -> str:
    return voucher_request(MONTH_COLLECTION, VOUCHER_MONTH_FIELDS, COMPANY_PLACEHOLDER,
                           from_date=FROM_PLACEHOLDER, to_date=TO_PLACEHOLDER)


def formula_template() -> str:
    return voucher_request(FORMULA_COLLECTION, VOUCHER_MONTH_FIELDS, COMPANY_PLACEHOLDER, from_date=B_BOOKS_FROM,
                           to_date=B_BOOKS_TO, filters=[(FORMULA_FILTER, FORMULA_CANDIDATE)])


async def _window(ctx: ProbeContext, step: str, template: str, licence: str, start: str, end: str, *,
                  untyped: bool = False) -> dict[str, Any]:
    xml = fill_month_request(template, ctx.company_name, start, end)
    text = await ctx.send(step, untyped_period_vars(xml) if untyped else xml)
    return compare_tags(voucher_rows(text), expect_window(licence, dmy(start), dmy(end)), dmy(start), dmy(end))


def _group_rows(text: str) -> dict[str, str]:
    return {name: str(row["closing_balance"]) for name, row in primary_group_rows(exploded_tb_rows(text)).items()}


async def _report_pair(ctx: ProbeContext) -> dict[str, Any]:
    typed_xml = wrap_report("Trial Balance", B_BOOKS_FROM, REPORT_AS_ON, ctx.company_name)
    typed_text = await ctx.send("report_tb_typed", typed_xml)
    typed_raw = ctx.last_response.raw
    untyped_text = await ctx.send("report_tb_untyped", untyped_period_vars(typed_xml))
    return {"as_on": REPORT_AS_ON, "identical_bytes": typed_raw == ctx.last_response.raw,
            "typed": _group_rows(typed_text), "untyped": _group_rows(untyped_text),
            "note": "Evidence only: probe 18's B part settles whether an as-on report is history (S0-D7)."}


def _untyped_evidence(untyped: dict[str, Any], reproduced: bool) -> str:
    span = untyped["date_span"]
    seen = f"untyped, Tally answered {untyped['returned']} voucher(s)" + (f" dated {span[0]}..{span[1]}" if span else "")
    return (f"C33 reproduced: {seen}." if reproduced
            else f"C33 NOT reproduced: {seen}. Review before trusting either form.")


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    typed_template = svdates_template()
    typed = await _window(ctx, "month_svdates", typed_template, licence, MONTH_FROM, MONTH_TO)
    untyped = await _window(ctx, "month_svdates_untyped", typed_template, licence, MONTH_FROM, MONTH_TO, untyped=True)
    reproduced = typed["match"] and not untyped["match"]
    ctx.observe("month_typed", typed)
    ctx.observe("month_untyped", untyped)
    ctx.observe("c33_reproduced", reproduced)

    form, template = ("svdates_typed", typed_template) if typed["match"] else (None, None)
    if form is None:
        formula = await _window(ctx, "month_formula", formula_template(), licence, MONTH_FROM, MONTH_TO)
        ctx.observe("month_formula", formula)
        if formula["match"]:
            form, template = "formula", formula_template()
    day = None
    if form is not None:
        day = await _window(ctx, "day_svdates", template, licence, DAY, DAY)
        ctx.observe("day", day)
    ctx.observe("report_period_vars", await _report_pair(ctx))

    evidence = _untyped_evidence(untyped, reproduced)
    if form is None:
        return PartResult(Outcome.FAILED, "Neither typed SVFROMDATE/SVTODATE nor the $Date formula candidate bounds a "
                                          f"Voucher collection to June 2023. {evidence}", spec_impact=FAILED_IMPACT)
    ctx.confirm_request("voucher_month", template, form=form, fields=list(VOUCHER_MONTH_FIELDS),
                        day_window_exact=day["match"],
                        placeholders=[COMPANY_PLACEHOLDER, FROM_PLACEHOLDER, TO_PLACEHOLDER])
    notes, impacts = [], []
    if form == "formula":
        notes.append("only the $Date formula bounds June 2023")
        impacts.append(FORMULA_IMPACT)
    if not day["match"]:
        notes.append(f"a one-day window isn't exact (missing {day['missing']}, extra {day['extra']}, "
                     f"out of window {day['out_of_window']})")
        impacts.append(DAY_IMPACT)
    if impacts:
        return PartResult(Outcome.DIFFERENT, "; ".join(notes) + f". {evidence}", spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, f"Typed SVFROMDATE/SVTODATE bound June 2023 exactly ({typed['returned']} "
                                         f"vouchers) and a one-day window returns exactly {DAY}'s {day['returned']}. "
                                         f"{evidence}", spec_impact=TYPED_IMPACT)


PROBE = Probe(
    id=5,
    name="voucher_month_bounds",
    question="Do SVFROMDATE / SVTODATE bound a Voucher collection to a month and to a day, and in which form?",
    feeds=("extractor chunks", "C33"),
    parts={"B": run_b},
    requires=(0,),
    educational_sensitive=True,
)
```

In `v2/probes/registry.py`:
- `ProbeInfo(5, "voucher_month_bounds", "B", "B", module="v2.probes.p05_voucher_month_bounds"),`
- `FIRST_ORDER`'s tail becomes `(5, "B"), (21, "B"), (16, "B"), (18, "B"),`
- In `ALL_ORDER`, `(21, "B"), (16, "B"), (18, "B"), (5, "B"), (3, "B"), …` becomes
  `(5, "B"), (21, "B"), (16, "B"), (18, "B"), (3, "B"), …`. Add a comment:
  `# 5 before 21: probe 21 fetches with probe 5's confirmed request (S0-D7); spec §6 "21 first" = first after 5.`

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_p05_voucher_month_bounds.py v2/tests/probes/test_cli.py -q`
→ PASS (8 new tests). Then run the full suite → `BASE + 24 passed`. `test_registry_matches_built_modules` now also
checks probe 5.

- [ ] **Step 5: Commit**

```bash
git add v2/probes/p05_voucher_month_bounds.py v2/probes/registry.py \
        v2/tests/probes/test_p05_voucher_month_bounds.py v2/tests/probes/test_cli.py
git commit -m "feat(bi/v2): probe 5 — typed month/day bounds on a Voucher collection, untyped as C33 evidence" \
           -m "Co-Authored-By: <session trailer>"
```

- [ ] **Step 6: Tracker.** Row 5: "🟡 built (part 4 Task 3 `<sha>`), not run live", plus a change-log row.

---

### Task 4: Probe 21's size and storage maths (pure functions)

**Files:**
- Create: `v2/probes/p21_full_history_reach.py` (this task adds only the constants and pure functions; the part and
  `PROBE` come in Task 5)
- Test: `v2/tests/probes/test_p21_full_history_reach.py` (create)

**Interfaces:**
- Consumes: `reads.parse_vouchers`, `reads.primary_lines`, `xml_utils.sanitize_xml`.
- Produces (used by Task 5):
  ```python
  PG_ROW_OVERHEAD_BYTES = 28; VOLUMES = (10_000, 50_000, 200_000); YEARS = (2, 5, 10)
  RECENT_FYS_WITH_RAW = 2; CHUNK_CAP_VOUCHERS = 5_000
  def voucher_blocks(raw_text: str) -> list[str]
  def xml_bytes(block: str) -> int
  def element_json(element: ET.Element) -> Any
  def raw_json_bytes(block: str) -> int
  def column_bytes(voucher: dict) -> tuple[int, int]                 # (bytes incl. row overhead, rows)
  def measure(blocks: dict[int, str], labels: dict[int, str]) -> dict[str, dict]
  def mean_block_bytes(blocks: list[str], list_tag: str) -> int
  def storage_table(stats: dict[str, dict]) -> dict[str, Any]       # keys: per_voucher_bytes, mix_vouchers, table,
                                                                    #       q22, q23
  ```

**What each size means** (the spec says "raw XML and parsed JSON (a stand-in for the `raw` JSONB)". This plan pins the
three measures down as follows):
- **raw XML**: the UTF-8 bytes of one `<VOUCHER>…</VOUCHER>` block, exactly as Tally sent it. It is used for
  month-chunk sizing.
- **raw JSON** (the stand-in for S1's `raw` JSONB): the whole voucher block turned into compact JSON by a generic
  XML→JSON walk. `.LIST` children become arrays, attributes go under `"@"`, empty placeholder lists and empty scalars
  are dropped, and `&#4;`-style control references are stripped (`sanitize_xml`). Postgres JSONB is binary, and its
  size is close to (usually a little above) the text JSON. That is recorded as a caveat and not modelled.
- **columns** (the stand-in for S1's typed rows, "without raw"): compact JSON of the Part 1 §5 minimum column values
  for the voucher row, each ledger line, inventory line and bill allocation, **plus 28 bytes per row**. That is the
  PostgreSQL heap tuple header (23 B, aligned to 24) plus a 4-byte line pointer. Referenced GUID columns
  (`voucher_type_guid`, `party_ledger_guid`, each `ledger_guid` / `stock_item_guid`) are sized like the voucher's own
  exported GUID, because it is the same Tally GUID format. **Indexes are excluded**, and the table says so.

- [ ] **Step 1: Write the failing tests**

```python
# v2/tests/probes/test_p21_full_history_reach.py  (Task 4 part; Task 5 appends)
import json
import xml.etree.ElementTree as ET

from v2.probes import p21_full_history_reach as p21
from v2.probes.reads import parse_vouchers

HINDI_BLOCK = ('<VOUCHER VCHTYPE="Sales"><DATE>20230601</DATE><GUID>g-0001</GUID>'
               "<NARRATION>[S0-B:281] Sale to शर्मा ट्रेडर्स&#4;</NARRATION>"
               "<ALLLEDGERENTRIES.LIST><LEDGERNAME>शर्मा ट्रेडर्स</LEDGERNAME><AMOUNT>-11.80</AMOUNT>"
               "<BILLALLOCATIONS.LIST><NAME>Inv/281</NAME><BILLTYPE>New Ref</BILLTYPE><AMOUNT>-11.80</AMOUNT>"
               "</BILLALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST>"
               "<ALLLEDGERENTRIES.LIST><LEDGERNAME>Domestic Sales</LEDGERNAME><AMOUNT>10.00</AMOUNT>"
               "<BILLALLOCATIONS.LIST>  </BILLALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST>"
               "<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>USB Cable</STOCKITEMNAME><ACTUALQTY> 1 Nos</ACTUALQTY>"
               "<RATE>10.00/Nos</RATE><AMOUNT>10.00</AMOUNT></ALLINVENTORYENTRIES.LIST>"
               "<REFERENCE></REFERENCE></VOUCHER>")


def _response(*blocks: str) -> str:
    return ("<ENVELOPE><BODY><DESC><CMPINFO><VOUCHER>0</VOUCHER></CMPINFO></DESC><DATA><COLLECTION>"
            + "".join(blocks) + "</COLLECTION></DATA></BODY></ENVELOPE>")


def test_voucher_blocks_skip_the_cmpinfo_counter_and_count_utf8_bytes():
    blocks = p21.voucher_blocks(_response(HINDI_BLOCK, HINDI_BLOCK.replace("281", "282")))
    assert len(blocks) == 2 and blocks[0] == HINDI_BLOCK
    assert p21.xml_bytes(HINDI_BLOCK) == len(HINDI_BLOCK.encode("utf-8")) > len(HINDI_BLOCK)


def test_element_json_drops_placeholders_keeps_lists_and_survives_control_chars():
    from v2.agent.tally.xml_utils import sanitize_xml
    doc = p21.element_json(ET.fromstring(sanitize_xml(HINDI_BLOCK)))
    assert doc["@"] == {"VCHTYPE": "Sales"}
    assert doc["NARRATION"] == "[S0-B:281] Sale to शर्मा ट्रेडर्स"
    assert "REFERENCE" not in doc                                                  # empty scalar dropped
    assert len(doc["ALLLEDGERENTRIES.LIST"]) == 2
    assert "BILLALLOCATIONS.LIST" not in doc["ALLLEDGERENTRIES.LIST"][1]           # empty placeholder dropped
    assert doc["ALLLEDGERENTRIES.LIST"][0]["BILLALLOCATIONS.LIST"][0]["NAME"] == "Inv/281"


def test_raw_json_bytes_is_the_compact_utf8_json():
    from v2.agent.tally.xml_utils import sanitize_xml
    expected = json.dumps(p21.element_json(ET.fromstring(sanitize_xml(HINDI_BLOCK))), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")
    assert p21.raw_json_bytes(HINDI_BLOCK) == len(expected)


def test_column_bytes_counts_rows_and_sizes_referenced_guids_like_the_vouchers_own():
    short = parse_vouchers(HINDI_BLOCK)[0]
    longer = parse_vouchers(HINDI_BLOCK.replace("<GUID>g-0001</GUID>", "<GUID>g-0001-0123456789</GUID>"))[0]
    (short_bytes, rows), (long_bytes, _) = p21.column_bytes(short), p21.column_bytes(longer)
    assert rows == 5                                  # voucher + 2 ledger lines + 1 inventory line + 1 bill
    assert short_bytes > rows * p21.PG_ROW_OVERHEAD_BYTES
    # +11 chars on the own GUID and on each of 6 references: voucher type, party, 2 line ledgers, item, bill ledger
    assert long_bytes - short_bytes == 11 * 7


def test_measure_groups_by_kind_rounds_half_up_and_ignores_unlabelled_tags():
    blocks = {281: HINDI_BLOCK, 282: HINDI_BLOCK.replace("281", "282"), 999: HINDI_BLOCK}
    stats = p21.measure(blocks, {281: "sales+inventory+bills", 282: "sales+inventory+bills"})
    s = stats["sales+inventory+bills"]
    assert list(stats) == ["sales+inventory+bills"] and s["count"] == 2
    assert s["xml_bytes"] == 2 * p21.xml_bytes(HINDI_BLOCK)          # 281 and 282 have the same length
    assert s["xml_per_voucher"] == p21.xml_bytes(HINDI_BLOCK)
    assert s["rows_per_voucher"] == "5.00"


def test_storage_table_from_hand_numbers():
    stats = {"k": {"count": 2, "xml_bytes": 2000, "json_bytes": 1200, "column_bytes": 800, "rows": 10}}
    out = p21.storage_table(stats)
    assert out["per_voucher_bytes"] == {"xml": "1000.0", "raw": "600.0", "columns": "400.0"}
    rows = {(r["vouchers_per_year"], r["years"]): r for r in out["table"]}
    assert len(rows) == 9
    assert rows[(10_000, 2)] == {"vouchers_per_year": 10_000, "years": 2, "vouchers": 20_000, "with_raw_mb": "20.0",
                                 "without_raw_mb": "8.0", "raw_recent_2_fy_only_mb": "20.0"}
    assert rows[(10_000, 5)]["raw_recent_2_fy_only_mb"] == "32.0"          # 50k×400 + 20k×600
    assert rows[(200_000, 10)]["with_raw_mb"] == "2000.0"
    assert out["q22"]["raw_share_pct"] == "60.0"
    assert out["q22"]["per_fy_mb"]["50000"] == {"with_raw": "50.0", "without_raw": "20.0"}
    assert out["q22"]["saving_if_raw_dropped_beyond_2_fy_mb"]["10000"] == {"5": "18.0", "10": "48.0"}


def test_month_chunks_flag_volumes_over_the_chunk_cap():
    stats = {"k": {"count": 1, "xml_bytes": 1000, "json_bytes": 600, "column_bytes": 400, "rows": 5}}
    chunks = {c["vouchers_per_year"]: c for c in p21.storage_table(stats)["q23"]["month_chunks"]}
    assert chunks[10_000] == {"vouchers_per_year": 10_000, "vouchers_per_month": 834, "month_xml_mb": "0.8",
                              "over_chunk_cap": False}
    assert chunks[50_000]["vouchers_per_month"] == 4167 and not chunks[50_000]["over_chunk_cap"]
    assert chunks[200_000]["vouchers_per_month"] == 16667 and chunks[200_000]["over_chunk_cap"]


def test_mean_block_bytes_ignores_empty_placeholders():
    blocks = [HINDI_BLOCK]
    bill = ("<BILLALLOCATIONS.LIST><NAME>Inv/281</NAME><BILLTYPE>New Ref</BILLTYPE><AMOUNT>-11.80</AMOUNT>"
            "</BILLALLOCATIONS.LIST>")
    assert p21.mean_block_bytes(blocks, "BILLALLOCATIONS.LIST") == len(bill.encode("utf-8"))
    assert p21.mean_block_bytes([], "BILLALLOCATIONS.LIST") == 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p21_full_history_reach.py -q`
Expected: FAIL with `ImportError: cannot import name 'p21_full_history_reach'`.

- [ ] **Step 3: Implement (module head + pure functions)**

```python
# v2/probes/p21_full_history_reach.py
"""Probe 21: full-history reach and size (S0 spec §7 "Probe 21", B part). Feeds decision 7b, Q22, Q23, R27.

Reach: fetch FY 2022-23 (company B's first year, three FYs behind the current one) month by month with probe 5's
confirmed request. Every month's tags must equal the dataset's (company_b_view.compare_tags; the cancelled pair is
reported, not judged, because probe 3's B part owns the flags, S0-D7).
Size: measure bytes per voucher by kind in three forms. Raw XML; a generic JSON of the whole voucher (the stand-in for
S1's `raw` JSONB); and the Part 1 §5 minimum columns plus a per-row overhead (the stand-in for S1's typed rows). Then
extrapolate to 10k/50k/200k vouchers a year × 2/5/10 years, with and without `raw`. Those are the numbers Q22 and Q23
wait on.
Timings are recorded and labelled "Wine — not representative". The tier-C timing half stays ⏭ (Q29).
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

from v2.agent.tally.xml_utils import sanitize_xml
from v2.probes.reads import parse_vouchers, primary_lines

PG_ROW_OVERHEAD_BYTES = 28      # PostgreSQL heap tuple header (23 B, aligned to 24) + 4-byte line pointer
VOLUMES = (10_000, 50_000, 200_000)
YEARS = (2, 5, 10)
RECENT_FYS_WITH_RAW = 2         # Q22's option: keep `raw` only for the 2-FY window
CHUNK_CAP_VOUCHERS = 5_000      # Part 1 §5 extractor: day/month chunks capped at about 5k vouchers
BLOCK_TAGS = ("ALLLEDGERENTRIES.LIST", "ALLINVENTORYENTRIES.LIST", "BILLALLOCATIONS.LIST")
_MB = Decimal(10) ** 6
_BLOCK = re.compile(r"<VOUCHER\b[^>]*>(.*?)</VOUCHER>", re.S)


def voucher_blocks(raw_text: str) -> list[str]:
    """Each <VOUCHER>…</VOUCHER> exactly as sent. CMPINFO's childless <VOUCHER>0</VOUCHER> counter is skipped."""
    return [m.group(0) for m in _BLOCK.finditer(raw_text) if "<" in m.group(1)]


def xml_bytes(block: str) -> int:
    return len(block.encode("utf-8"))


def element_json(element: ET.Element) -> Any:
    """A generic XML → JSON walk: `.LIST` children become arrays, attributes go under "@", and empty placeholders and
    empty scalars are dropped. This is the stand-in for S1's `raw` JSONB."""
    children = [c for c in element if len(c) or (c.text or "").strip()]
    text = (element.text or "").strip()
    if not children:
        return {"@": dict(element.attrib), "#": text} if element.attrib else text
    out: dict[str, Any] = {"@": dict(element.attrib)} if element.attrib else {}
    for child in children:
        value = element_json(child)
        if child.tag.endswith(".LIST"):
            out.setdefault(child.tag, []).append(value)
        else:
            out[child.tag] = value
    return out


def _compact(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def raw_json_bytes(block: str) -> int:
    return _compact(element_json(ET.fromstring(sanitize_xml(block))))


def column_bytes(voucher: dict) -> tuple[int, int]:
    """(bytes, rows) of the Part 1 §5 minimum columns for one voucher: compact JSON of the values, plus
    PG_ROW_OVERHEAD_BYTES per row. Referenced GUIDs are sized like the voucher's own. Indexes are excluded."""
    h = voucher["header"]
    ref = "g" * len(h.get("GUID", ""))
    lines = primary_lines(voucher)
    rows: list[list[str]] = [[h.get("GUID", ""), h.get("MASTERID", ""), h.get("ALTERID", ""), h.get("DATE", ""),
                              ref, h.get("VOUCHERTYPENAME", ""), h.get("VOUCHERNUMBER", ""), h.get("REFERENCE", ""),
                              ref, h.get("NARRATION", ""), h.get("ISCANCELLED", ""), h.get("ISOPTIONAL", ""),
                              h.get("ISPOSTDATED", ""), "No"]]
    rows += [[ref, ln["fields"].get("LEDGERNAME", ""), ln["fields"].get("AMOUNT", ""),
              ln["fields"].get("ISDEEMEDPOSITIVE", "")] for ln in lines]
    rows += [[ref, inv["fields"].get("ACTUALQTY", ""), inv["fields"].get("RATE", ""),
              inv["fields"].get("AMOUNT", "")] for inv in voucher["inventory"]]
    rows += [[ref, bill.get("NAME", ""), bill.get("BILLTYPE", ""), bill.get("AMOUNT", ""),
              bill.get("BILLCREDITPERIOD", "")] for ln in lines for bill in ln["bills"]]
    return sum(_compact(row) for row in rows) + PG_ROW_OVERHEAD_BYTES * len(rows), len(rows)


def _mean(total: int, count: int) -> int:
    return int((Decimal(total) / count).quantize(Decimal("1"), ROUND_HALF_UP)) if count else 0


def measure(blocks: dict[int, str], labels: dict[int, str]) -> dict[str, dict[str, Any]]:
    """Per kind label: totals and per-voucher means. Tags without a label (flagged, untagged, outside the window)
    are left out."""
    stats: dict[str, dict[str, Any]] = {}
    for tag, block in sorted(blocks.items()):
        label = labels.get(tag)
        if label is None:
            continue
        cols, rows = column_bytes(parse_vouchers(block)[0])
        s = stats.setdefault(label, {"count": 0, "xml_bytes": 0, "json_bytes": 0, "column_bytes": 0, "rows": 0})
        s["count"] += 1
        s["xml_bytes"] += xml_bytes(block)
        s["json_bytes"] += raw_json_bytes(block)
        s["column_bytes"] += cols
        s["rows"] += rows
    for s in stats.values():
        s["xml_per_voucher"] = _mean(s["xml_bytes"], s["count"])
        s["json_per_voucher"] = _mean(s["json_bytes"], s["count"])
        s["column_per_voucher"] = _mean(s["column_bytes"], s["count"])
        s["rows_per_voucher"] = str((Decimal(s["rows"]) / s["count"]).quantize(Decimal("0.01"), ROUND_HALF_UP))
    return stats


def mean_block_bytes(blocks: list[str], list_tag: str) -> int:
    """Mean bytes of one non-empty `list_tag` block. It lets S1 scale to invoices with more lines than company B's
    (every company-B invoice carries exactly one stock line)."""
    pattern = re.compile(rf"<{re.escape(list_tag)}>(.*?)</{re.escape(list_tag)}>", re.S)
    found = [m.group(0) for block in blocks for m in pattern.finditer(block) if m.group(1).strip()]
    return _mean(sum(xml_bytes(f) for f in found), len(found))


def _mb(n: Decimal) -> str:
    return str((n / _MB).quantize(Decimal("0.1"), ROUND_HALF_UP))


def storage_table(stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Q22/Q23 inputs from the measured mix. Weights = the measured kinds' counts (company B's FY 2022-23)."""
    n = sum(s["count"] for s in stats.values())
    per = {key: Decimal(sum(s[total] for s in stats.values())) / n
           for key, total in (("xml", "xml_bytes"), ("raw", "json_bytes"), ("columns", "column_bytes"))}
    with_raw = per["columns"] + per["raw"]
    table = []
    for volume in VOLUMES:
        for years in YEARS:
            vouchers = Decimal(volume * years)
            recent = Decimal(volume * min(years, RECENT_FYS_WITH_RAW))
            table.append({"vouchers_per_year": volume, "years": years, "vouchers": volume * years,
                          "with_raw_mb": _mb(vouchers * with_raw), "without_raw_mb": _mb(vouchers * per["columns"]),
                          "raw_recent_2_fy_only_mb": _mb(vouchers * per["columns"] + recent * per["raw"])})
    chunks = []
    for volume in VOLUMES:
        per_month = int((Decimal(volume) / 12).quantize(Decimal("1"), ROUND_CEILING))
        chunks.append({"vouchers_per_year": volume, "vouchers_per_month": per_month,
                       "month_xml_mb": _mb(per_month * per["xml"]), "over_chunk_cap": per_month > CHUNK_CAP_VOUCHERS})
    return {
        "per_voucher_bytes": {k: str(v.quantize(Decimal("0.1"), ROUND_HALF_UP)) for k, v in per.items()},
        "mix_vouchers": n,
        "table": table,
        "q22": {"raw_share_pct": str((per["raw"] / with_raw * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)),
                "per_fy_mb": {str(v): {"with_raw": _mb(v * with_raw), "without_raw": _mb(v * per["columns"])}
                              for v in VOLUMES},
                "saving_if_raw_dropped_beyond_2_fy_mb": {
                    str(v): {str(y): _mb(Decimal(v * (y - RECENT_FYS_WITH_RAW)) * per["raw"])
                             for y in YEARS if y > RECENT_FYS_WITH_RAW} for v in VOLUMES}},
        "q23": {"per_extra_fy_with_raw_mb": {str(v): _mb(v * with_raw) for v in VOLUMES},
                "per_extra_fy_without_raw_mb": {str(v): _mb(v * per["columns"]) for v in VOLUMES},
                "month_chunks": chunks,
                "caveats": ["indexes excluded", "JSONB stored size ≈ text JSON (not modelled)",
                            "company B's mix: one stock line per invoice — scale with block_bytes"]},
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_p21_full_history_reach.py -q` → 8 passed. Then run the full
suite → `BASE + 32 passed`. Probe 21 isn't in the registry yet, so nothing else changes.

- [ ] **Step 5: Commit**

```bash
git add v2/probes/p21_full_history_reach.py v2/tests/probes/test_p21_full_history_reach.py
git commit -m "feat(bi/v2): probe 21 size + storage maths (raw XML / JSON stand-in / columns)" \
           -m "Co-Authored-By: <session trailer>"
```

- [ ] **Step 6: Tracker.** Row 21 → 🟡 ("part 4 Task 4 `<sha>`"), plus a change-log row.

---

### Task 5: Probe 21's B part: reach, sizes, the optional period lock, and the registry

**Files:**
- Modify: `v2/probes/p21_full_history_reach.py` (add the imports below, `run_b`, helpers, `PROBE`)
- Modify: `v2/probes/registry.py` (`ProbeInfo(21, "full_history_reach", "B", "B+C", module="v2.probes.p21_full_history_reach")`)
- Test: `v2/tests/probes/test_p21_full_history_reach.py` (append)

**Interfaces:**
- Consumes: Task 1 (`company_b_view.*`, `fill_month_request`), Task 2 (`seed_company_b`), Task 3 (the confirmed
  `voucher_month` request; tests run probe 5 first), Task 4 (the pure functions), `capture.TIMING_NOTE`,
  `ctx.counters(step)` (probe 1's confirmed request, which exports `BooksFrom`).
- Produces: `PROBE` (id=21, `parts={"B": run_b}`, `requires=(5,)`). Observations: `books_from`, `months` (per step:
  the `compare_tags` dict + `bytes`), `kinds` (from `measure`), `block_bytes`, `storage` (from `storage_table`),
  `current_fy_sample`, `timings_ms` (with `note`), `period_lock`.
- Steps captured, in order: `books_from`, `fy2022_month_04` … `fy2022_month_12`, `fy2022_month_01` … `fy2022_month_03`,
  `fy2025_month_03`, and `period_locked_read` (only when the operator locked the period).

**Verdict rules:** FAILED if any FY 2022-23 month isn't exact (reach is the question decision 7b depends on). Else
DIFFERENT if BooksFrom ≠ 01-04-2022, or a locked period no longer reads back exactly. Else CONFIRMED, and the
`spec_impact` carries the storage headline so the Part 1 spec update has one sentence to paste. The period lock is
asked **only** when a person is there: `--non-interactive` and auto mode record "not attempted" without asking (the
operator can't lock a period through XML). The ask has no `Action`, like the UI-only pauses (ruling C18). Size stats
use unflagged tagged vouchers only.

- [ ] **Step 1: Write the failing tests** (append to `v2/tests/probes/test_p21_full_history_reach.py`)

```python
import pytest

from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes.capture import TIMING_NOTE, Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]
KINDS = {"sales+inventory+bills", "purchase+inventory+bills", "receipt+bills", "payment+bills", "sales+inventory",
         "payment", "receipt"}


def _books() -> FakeBooks:
    books = FakeBooks(name=B)
    seed_company_b(books, "educational")
    return books


async def _run(tmp_path, books, io=None, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    io = io or ScriptedIO(answers=[""])
    await run_probe(p21.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(21)["parts"]["B"], io


async def test_fy2022_is_reached_month_by_month_and_sizes_are_measured(tmp_path):
    part, _ = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["books_from"] == {"exported": "20220401", "expected": "01-04-2022", "match": True}
    assert len(obs["months"]) == 12 and all(m["match"] for m in obs["months"].values())
    assert obs["months"]["fy2022_month_09"]["expected_written"] == 18                     # 101/102 never written
    assert obs["months"]["fy2022_month_02"]["flagged_returned"] == [201, 202]
    assert set(obs["kinds"]) == KINDS
    assert sum(k["count"] for k in obs["kinds"].values()) == 236                          # 238 minus the cancelled pair
    assert set(obs["block_bytes"]) == {"ALLLEDGERENTRIES.LIST", "ALLINVENTORYENTRIES.LIST", "BILLALLOCATIONS.LIST"}
    assert len(obs["storage"]["table"]) == 9 and obs["storage"]["mix_vouchers"] == 236
    assert set(obs["storage"]["q22"]) == {"raw_share_pct", "per_fy_mb", "saving_if_raw_dropped_beyond_2_fy_mb"}
    assert obs["timings_ms"]["note"] == TIMING_NOTE and "fy2022_month_04" in obs["timings_ms"]
    assert obs["current_fy_sample"]["month"]["match"]
    assert obs["period_lock"] == {"status": "not attempted", "answer": ""}
    assert "⏭" in part["summary"] and "Q22" in part["spec_impact"]
    assert part["fixtures"][:2] == ["p21_B_books_from.xml", "p21_B_fy2022_month_04.xml"]
    assert "p21_B_fy2022_month_03.xml" in part["fixtures"] and "p21_B_fy2025_month_03.xml" in part["fixtures"]


async def test_a_hand_entered_voucher_makes_its_month_inexact_and_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["vouchers"].__setitem__("99999", {
        "narration": "typed in by hand", "date": "20220815", "post_dated": "No", "cancelled": "No",
        "optional": "No", "vch_type": "Journal", "lines": [], "inventory": [], "bills": []}))
    part, _ = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED"
    assert part["observations"]["months"]["fy2022_month_08"]["untagged"] == 1
    assert "fy2022_month_08" in part["summary"] and "decision 7b" in part["spec_impact"]


async def test_books_from_other_than_2022_is_different(tmp_path):
    books = _books()
    books.edit_state(lambda s: s.update(books_from="20230401"))
    part, _ = await _run(tmp_path, books)
    assert part["outcome"] == "DIFFERENT"
    assert "BooksFrom" in part["summary"] and "books-beginning" in part["spec_impact"]


async def test_a_timeout_mid_year_blocks_with_the_popup_hint_and_is_not_retried(tmp_path):
    books = _books()
    books.before_request = lambda body: setattr(books, "popup", True) if ">01-10-2022<" in body else None
    part, _ = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "popup" in part["summary"]
    assert "p21_B_fy2022_month_09.xml" in part["fixtures"]
    assert "p21_B_fy2022_month_10.xml.json" in part["fixtures"]
    assert sum(">01-10-2022<" in body for body in books.requests) == 1


async def test_a_locked_period_is_read_again_and_then_unlocked(tmp_path):
    part, io = await _run(tmp_path, _books(), ScriptedIO(answers=["locked"]))
    lock = part["observations"]["period_lock"]
    assert lock["status"] == "locked" and lock["read"]["match"] and lock["same_as_unlocked"]
    assert "p21_B_period_locked_read.xml" in part["fixtures"]
    assert any("Unlock" in w for w in io.waits)
    assert "cleanup_needed" not in part["observations"]


async def test_an_edition_without_a_period_lock_is_recorded(tmp_path):
    part, _ = await _run(tmp_path, _books(), ScriptedIO(answers=["none"]))
    assert part["observations"]["period_lock"] == {"status": "no period lock in this edition"}
    assert part["outcome"] == "CONFIRMED"


@pytest.mark.parametrize("io, status", [
    (ScriptedIO(interactive=False), "not attempted (non-interactive)"),
    (ScriptedIO(run_mode="auto"), "not attempted (auto mode: a person must lock the period in the Tally UI)"),
])
async def test_period_lock_is_not_attempted_without_a_person(tmp_path, io, status):
    part, used = await _run(tmp_path, _books(), io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["period_lock"] == {"status": status}
    assert used.asks == []


async def test_probe_21_blocks_until_probe_5_has_confirmed_the_month_request(tmp_path):
    books = _books()
    part, _ = await _run(tmp_path, books, with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "probe(s) 5" in part["summary"]
    assert not any("<TYPE>Voucher</TYPE>" in body for body in books.requests)
```

(The `ScriptedIO(interactive=False)` case: `run_probe` doesn't switch companies for the first part, and probe 5 runs
with its own `ScriptedIO()`, so non-interactive mode only affects probe 21.)

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p21_full_history_reach.py -q`
Expected: the Task 4 tests pass, and the new ones fail with `AttributeError: module … has no attribute 'PROBE'`.

- [ ] **Step 3: Implement**

Add these imports to `p21_full_history_reach.py`:

```python
from calendar import monthrange
from datetime import date

from v2.probes.capture import TIMING_NOTE
from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_FROM_DATE, compare_tags, expect_window, kind_label,
                                      loaded_licence, tag_of, voucher_rows)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import fill_month_request, tally_date
```

Then add:

```python
FY2022_MONTHS = [(2022, m) for m in range(4, 13)] + [(2023, m) for m in range(1, 4)]
FY2022 = (date(2022, 4, 1), date(2023, 3, 31))
CURRENT_FY_SAMPLE = (2026, 3)             # one month of the current FY: "do closed years behave differently?"
LOCK_FROM, LOCK_TO = "01-04-2022", "31-03-2023"
LOCK_PROMPT = ("Probe 21 step 4, period lock: if this TallyPrime can lock a period for company B, lock "
               f"{LOCK_FROM} to {LOCK_TO} now and type 'locked'. Type 'none' if it has no period lock, or just press "
               "Enter to skip.")
LOCK_NOTE = "Company B: unlock FY 2022-23 again (probe 21 locked it)."
REACH_IMPACT = ("Decision 7b: probe 5's month request can't fetch FY 2022-23 exactly, so the backfill can't walk back "
                "to books_from with it; the extractor needs another route before S1 (R27, R29).")
BOOKS_FROM_IMPACT = ("The Company collection's BooksFrom isn't the books-beginning date, so the backfill's floor "
                     "(decision 7b, Part 1 §4 'Where history starts') needs another source before S2.")
LOCK_IMPACT = ("A locked period doesn't read back the same: the backfill must treat locked years as unreadable and "
               "say so on the History card (decision 7b, R29).")
TIMING_TAIL = f"Timings recorded ({TIMING_NOTE}); the tier-C timing half stays ⏭ (Q29)."


def month_window(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _dmy(day: date) -> str:
    return day.strftime("%d-%m-%Y")


def _blocks_by_tag(raw_text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for block in voucher_blocks(raw_text):
        tag = tag_of(parse_vouchers(block)[0]["header"].get("NARRATION", ""))
        if tag is not None:
            out[tag] = block
    return out


def _labels(licence: str, start: date, end: date) -> dict[int, str]:
    window = expect_window(licence, start, end)
    return {tag: kind_label(v) for tag, v in window.written.items() if tag not in window.flagged}


async def _month(ctx: ProbeContext, template: str, licence: str, step: str, start: date,
                 end: date) -> tuple[dict[str, Any], dict[int, str]]:
    text = await ctx.send(step, fill_month_request(template, ctx.company_name, _dmy(start), _dmy(end)))
    result = compare_tags(voucher_rows(text), expect_window(licence, start, end), start, end)
    result["bytes"] = ctx.last_response.response_bytes
    return result, _blocks_by_tag(ctx.last_response.raw.decode("utf-8"))


async def _period_lock(ctx: ProbeContext, template: str, licence: str, unlocked: dict[str, Any]) -> dict[str, Any]:
    if not ctx.io.interactive:
        return {"status": "not attempted (non-interactive)"}
    if ctx.run_mode == "auto":
        return {"status": "not attempted (auto mode: a person must lock the period in the Tally UI)"}
    answer = ctx.ask(LOCK_PROMPT).strip().lower()
    if answer == "none":
        return {"status": "no period lock in this edition"}
    if answer != "locked":
        return {"status": "not attempted", "answer": answer}
    ctx.on_abort(LOCK_NOTE)
    read, _ = await _month(ctx, template, licence, "period_locked_read", *month_window(2022, 4))
    ctx.pause(f"Unlock {LOCK_FROM} to {LOCK_TO} for company B again, then press Enter.")
    ctx.resolve_abort(LOCK_NOTE)
    return {"status": "locked", "read": read,
            "same_as_unlocked": read["match"] and read["returned"] == unlocked["returned"]}


def _headline(storage: dict[str, Any]) -> str:
    row = next(r for r in storage["table"] if (r["vouchers_per_year"], r["years"]) == (200_000, 10))
    per = storage["per_voucher_bytes"]
    return (f"Q22/Q23 inputs (company B's mix, sizes under Wine): {per['columns']} B/voucher without raw, raw JSON "
            f"{per['raw']} B more ({storage['q22']['raw_share_pct']}% of the total); 200k vouchers/yr × 10 yr = "
            f"{row['with_raw_mb']} MB with raw, {row['without_raw_mb']} MB without, {row['raw_recent_2_fy_only_mb']} MB "
            "keeping raw for the recent 2 FYs only (indexes excluded). S1 decides Q22/Q23 on these.")


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    confirmed = ctx.store.confirmed("voucher_month")
    if confirmed is None:
        raise ProbeBlocked("No confirmed month request: run probe 5 first.")
    template = confirmed["xml_template"]

    exported = (await ctx.counters("books_from")).get("BooksFrom", "")
    books_from_ok = tally_date(exported) == B_BOOKS_FROM_DATE
    ctx.observe("books_from", {"exported": exported, "expected": B_BOOKS_FROM, "match": books_from_ok})

    months: dict[str, dict[str, Any]] = {}
    timings: dict[str, Any] = {"note": TIMING_NOTE}
    blocks: dict[int, str] = {}
    for year, month in FY2022_MONTHS:
        step = f"fy2022_month_{month:02d}"
        months[step], found = await _month(ctx, template, licence, step, *month_window(year, month))
        timings[step] = ctx.last_response.elapsed_ms
        blocks.update(found)
    ctx.observe("months", months)

    labels = _labels(licence, *FY2022)
    stats = measure(blocks, labels)
    sized = [block for tag, block in blocks.items() if tag in labels]
    ctx.observe("kinds", stats)
    ctx.observe("block_bytes", {tag: mean_block_bytes(sized, tag) for tag in BLOCK_TAGS})
    storage = storage_table(stats) if stats else None
    ctx.observe("storage", storage)

    sample_window = month_window(*CURRENT_FY_SAMPLE)
    sample, sample_blocks = await _month(ctx, template, licence, "fy2025_month_03", *sample_window)
    timings["fy2025_month_03"] = ctx.last_response.elapsed_ms
    ctx.observe("current_fy_sample", {
        "month": sample,
        "kinds": {label: {"xml_per_voucher": s["xml_per_voucher"], "json_per_voucher": s["json_per_voucher"]}
                  for label, s in measure(sample_blocks, _labels(licence, *sample_window)).items()},
        "note": "Part 1 probe 21's 'do closed years behave differently?': compare with `kinds`; no verdict."})
    ctx.observe("timings_ms", timings)

    lock = await _period_lock(ctx, template, licence, months["fy2022_month_04"])
    ctx.observe("period_lock", lock)

    inexact = [step for step, result in months.items() if not result["match"]]
    if inexact:
        return PartResult(Outcome.FAILED, f"FY 2022-23 not reached exactly: {', '.join(inexact)} differ from the "
                                          f"dataset (see observations.months). {TIMING_TAIL}", spec_impact=REACH_IMPACT)
    notes, impacts = [], []
    if not books_from_ok:
        notes.append(f"BooksFrom exported {exported!r}, not {B_BOOKS_FROM}")
        impacts.append(BOOKS_FROM_IMPACT)
    if lock["status"] == "locked" and not lock["same_as_unlocked"]:
        notes.append("the locked FY 2022-23 no longer reads back the same")
        impacts.append(LOCK_IMPACT)
    if notes:
        return PartResult(Outcome.DIFFERENT, "; ".join(notes) + f". {TIMING_TAIL}", spec_impact=" ".join(impacts))
    total = sum(result["returned"] for result in months.values())
    return PartResult(Outcome.CONFIRMED, f"FY 2022-23 reached month by month: 12/12 months exact ({total} vouchers; "
                                         f"the cancelled pair reported, not judged); BooksFrom {B_BOOKS_FROM}; sizes "
                                         f"for {len(stats)} voucher kinds. {TIMING_TAIL}",
                      spec_impact=_headline(storage))


PROBE = Probe(
    id=21,
    name="full_history_reach",
    question="Can every month of an FY three years back be fetched exactly, and what do vouchers cost to store "
             "over 2/5/10 years with and without raw?",
    feeds=("decision 7b", "Q22", "Q23", "R27"),
    parts={"B": run_b},
    requires=(5,),
)
```

In `v2/probes/registry.py` set `ProbeInfo(21, "full_history_reach", "B", "B+C", module="v2.probes.p21_full_history_reach")`.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_p21_full_history_reach.py -q` → 17 passed (8 + 9). Then run the
full suite: `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1` → `BASE + 41 passed` (580 if BASE was 539).
Also run it with `-W error` → same count.

- [ ] **Step 5: Commit**

```bash
git add v2/probes/p21_full_history_reach.py v2/probes/registry.py v2/tests/probes/test_p21_full_history_reach.py
git commit -m "feat(bi/v2): probe 21 — FY 2022-23 reach, bytes per voucher by kind, Q22/Q23 storage table" \
           -m "Co-Authored-By: <session trailer>"
```

- [ ] **Step 6: Tracker.** Row 21: "🟡 built (part 4 Task 5 `<sha>`), not run live", plus a change-log row.

---

### Task 6: Code review (before the live run)

**Files:**
- Create: `docs/code-review-bi-s0-part4-<YYYY-MM-DD>.md`

- [ ] **Step 1:** Run the `superpowers:requesting-code-review` skill (or the `code-review` agent) on
  `git diff c7151b3..HEAD -- v2/`. Ask the reviewer to check at least these: this plan's count rule against spec §7
  "counts equal the dataset's"; whether the untyped evidence can ever change a verdict (it must not); the three size
  definitions against Part 1 §5 "Cloud" minimum columns; S0-D7 (probe 21 reads only probe 5's confirmed request, and
  probe 5 asserts nothing about reports); the Review Focus items; and isolation (`company_b_view` is the only bridge).
- [ ] **Step 2:** Store the findings in `docs/code-review-bi-s0-part4-<date>.md`, and fix the confirmed ones with a
  failing test first (TDD). Re-run the full suite (with and without `-W error`) and record the count. The doc must list
  the suites **not** run: live Tally (Task 7 does that), tier-C timing (⏭ Q29), and the root `tests/` suite (it
  doesn't collect `v2/`).
- [ ] **Step 3: Isolation check against git.** Run `git status --porcelain | grep -v -E '^\?\? ' | grep -v -E ' (v2/|docs/)'`.
  Expected: empty.
- [ ] **Step 4: CLI smoke (no Tally needed).**
  ```bash
  mkdir -p /tmp/s0-smoke-p4
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p4/results.json list | grep -E '^ ?(5|21) '
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p4/results.json run 11; echo "exit=$?"
  ```
  Expected: `5  voucher_month_bounds … not run` and `21  full_history_reach … not run`; `run 11` prints "not built yet",
  `exit=2`.
- [ ] **Step 5: Commit** the review doc and any fixes, staging only the files named. Add a tracker change-log row with
  the review doc path.

---

### Task 7: Live run: probes 5 then 21 on company B (operator at the Mac)

**Files (written by the runner, then committed):** `v2/probes/results/results.json`, `v2/tests/fixtures/sync/p05_B_*`,
`v2/tests/fixtures/sync/p21_B_*`, `docs/bi-s0-probe-results-<date>.md` (generated). Logs go to `logs/` (gitignored
`*.log`).

Neither probe writes to Tally. The only change is the optional period lock in step 4 of probe 21, which a person makes
by hand and undoes by hand. **Do not use `--auto`**. Probe 5 has no pauses. Probe 21's period lock needs a person. An
auto `open_company` that decides to restart Tally hits the known `tally.ini` `Load=100003` bug (tracker 0a) and would
open company A as well.

- [ ] **Step 1: Pre-flight (read-only).**
  ```bash
  cd "/Users/nuvanta-mac-3/work/Tally prime"
  grep -n '"company_b_loaded_at"\|"licence"' v2/probes/results/results.json
  ps -axo pid,command | grep -i 'tally.exe' | grep -v grep
  curl -s --max-time 3 http://localhost:9000
  ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe-backups/100000-company-B-loaded-2026-09-24
  ```
  Expected: `company_b_loaded_at` is present and `licence` is `educational`. There is exactly one
  `tally.exe`, whose command line shows the `s0probe` data folder (and `/LOAD:100000` if the operator started it).
  `<RESPONSE>TallyPrime Server is Running</RESPONSE>`. The backup folder exists. In the TallyPrime window, **only**
  `Sharma & Sons' Probe Traders` is open (company 100000). If company A is also open, close it by hand in the Tally UI.
  Don't restart Tally to fix it.
- [ ] **Step 2: Probe 5.**
  ```bash
  uv run --project v2 python -m v2.probes run 5 --company B 2>&1 | tee logs/p05-live-$(date +%F).log
  ```
  Expected: `part B: CONFIRMED — Typed SVFROMDATE/SVTODATE bound June 2023 exactly (20 vouchers) and a one-day window
  returns exactly 01-06-2023's 10. C33 reproduced: untyped, Tally answered N voucher(s) dated 2025-04-01..… [Educational
  mode — confirm on a licensed Tally]`. `results.json` gains `confirmed_requests.voucher_month` with
  `"form": "svdates_typed"`. If the guard BLOCKs ("close all but …" / a different company): fix what's open in the UI,
  then re-run. **If it is DIFFERENT or FAILED, that is a finding.** Record it and don't re-run to "get CONFIRMED". A
  FAILED probe 5 means probe 21 BLOCKs by design. Stop and take it to the tracker and spec (Part 1 §5 extractor
  fallback).
- [ ] **Step 3: Probe 21.**
  ```bash
  uv run --project v2 python -m v2.probes run 21 --company B 2>&1 | tee logs/p21-live-$(date +%F).log
  ```
  At the period-lock question: look in this TallyPrime build for a way to lock a period for company B. If one exists,
  lock 01-04-2022..31-03-2023 and type `locked`. At the next pause, unlock it again and press Enter. If there is none,
  type `none`. If you'd rather not touch the UI, press Enter (recorded as "not attempted"). Expected:
  `part B: CONFIRMED — FY 2022-23 reached month by month: 12/12 months exact (238 vouchers; the cancelled pair
  reported, not judged); BooksFrom 01-04-2022; sizes for 7 voucher kinds. Timings recorded (Wine — not
  representative); the tier-C timing half stays ⏭ (Q29).` The 238 assumes Tally returns the cancelled pair. If it
  omits them, the month is still exact and the count reads 236. Record which one happened, because it is evidence for
  probe 3's B part.
  If `CLEANUP NEEDED in Tally` prints (the part blocked while the period was locked), unlock FY 2022-23 by hand first.
- [ ] **Step 4: Read the numbers out** (for the tracker and spec):
  ```bash
  uv run --project v2 python -c "import json; p=json.load(open('v2/probes/results/results.json'))['probes']; \
  o=p['21']['parts']['B']['observations']; print(json.dumps({k:o[k] for k in ('books_from','kinds','block_bytes','storage','period_lock')}, indent=1, ensure_ascii=False)); \
  print(json.dumps(p['5']['parts']['B']['observations']['report_period_vars'], indent=1, ensure_ascii=False))" \
  2>&1 | tee logs/p21-numbers-$(date +%F).log
  ```
- [ ] **Step 5: List + report.**
  `uv run --project v2 python -m v2.probes list | grep -E '^ ?(5|21) '` should show both CONFIRMED (or the outcome
  that actually happened). Then `uv run --project v2 python -m v2.probes report`, which writes
  `docs/bi-s0-probe-results-<today>.md`.
- [ ] **Step 6: Commit the evidence.** First check that `git diff v2/probes/results/results.json` touches only
  probes 5 and 21, `confirmed_requests.voucher_month`, and `environment.run_mode` (the manual run records
  `MANUAL_RUN_MODE`). Then:
  ```bash
  git add v2/probes/results/results.json v2/tests/fixtures/sync/p05_B_* v2/tests/fixtures/sync/p21_B_* \
          docs/bi-s0-probe-results-$(date +%F).md
  git commit -m "data(bi/v2): probes 5 + 21 live on company B — confirmed month request, FY 2022-23 reach, storage table" \
             -m "Co-Authored-By: <session trailer>"
  ```

---

### Task 8: Spec, tracker and roadmap updates (same session as Task 7)

**Files:** `docs/specs/2026-09-22-bi-s0-probes-design.md`, `docs/specs/2026-09-21-bi-part1-sync-design.md`,
`docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md`, and this plan (tick the boxes).

- [ ] **Step 1: S0 spec.** Add a header line `**Changed <date> (plan part 4):**` covering all of the following.
  (a) §6 batch 5 now runs 5 → 21 (21 fetches with probe 5's request, S0-D7), and §5.3's `--first` includes 5.
  (b) §7 probe 5 records the untyped form and one TB pair as evidence only, and the typed form is the one confirmed.
  (c) The count rule (tag sets; flagged recorded, not judged; skipped never expected).
  (d) §7 probe 21 defines its three size measures and the current-FY sample month, and the period lock is asked only
  when a person is present.
  (e) §11.5 rows 5 and 21 gain the extra steps (`month_svdates_untyped`, `report_tb_typed`, `report_tb_untyped`;
  `fy2025_month_03`).
  (f) Probe modules read the dataset only through `company_b_view`.
  Update the header status line.
- [ ] **Step 2: Part 1 spec.** Add one dated "Changed" line. In §5 "Windows agent" `extractor.py`: month chunks use
  probe 5's confirmed request with typed period variables (C33), and add the day-split finding. In §15, add to the
  **Q22** and **Q23** rows `Numbers (probe 21, <date>): …`, copying `storage.q22` / `storage.q23` and the 200k × 10
  row. These are numbers, not a decision; the decision stays open for the user. In R27 "Residual", add the headline
  sentence (`spec_impact`). Record the probe 5 `report_period_vars` evidence as an open note on the C33 report
  question. It is not a conclusion.
- [ ] **Step 3: Tracker.** §3 row 5 and row 21 get status (✅, or the real outcome) with proof: the outcome sentence,
  the fixture names, the `results.json` keys, and the log paths from Task 7. Row 21's timing half stays ⏭ (Q29). The
  §2 Q22/Q23 rows get the numbers in the "Answer" column, marked "numbers in; decision pending". §0 S0 row: part 4
  done. Rewrite the "Resume here" block so it describes the state actually left behind, with the next step being the
  B parts of 16 and 18, then 3, 11, 14, 15, 23, 25 (22 is still BLOCKED by C36). Add a dated change-log row that
  includes anything that contradicted this plan's expectations (e.g. 236 instead of 238).
- [ ] **Step 4: Roadmap.** Set C S0 row: one line with probes 5 + 21 done and Q22/Q23 numbers in.
- [ ] **Step 5: Commit** these docs only:
  `git commit -m "docs(bi/v2): probes 5 + 21 results into specs, tracker, roadmap" -m "Co-Authored-By: <session trailer>"`.

---

## Self-review (done while writing)

- **Spec coverage (requirement → task):**
  - Probe 5 step 1 (typed SV dates, June 2023, dates in range, count equals the dataset's) → T3 (`month_svdates` +
    `compare_tags`, T1). Step 2 (formula candidate, never `$$InDateRange`; one-day request) → T3 (`month_formula`,
    `day_svdates`). Step 3 (`confirm_request("voucher_month")`) → T3. DIFFERENT/FAILED rules → T3 tests 3, 5, 6.
    C33 evidence (untyped, recorded, verdict-neutral) → T3 tests 1, 7. One report-level comparison, evidence only →
    T3 `_report_pair`.
  - Probe 21 step 1 (BooksFrom = 01-04-2022; FY 2022-23 month by month with probe 5's request; counts equal) → T5.
    Step 2 (bytes per voucher by kind, raw XML and parsed JSON) → T4 + T5. Step 3 (10k/50k/200k × 2/5/10, with and
    without raw) → T4 `storage_table`. Step 4 (period lock, a pause, edition permitting) → T5 `_period_lock`. Timing ⏭,
    labelled → T5 `timings_ms` + summary. Decision 7b / Q22 / Q23 / R27 outputs → T4 `q22`/`q23` + T5 `_headline`.
  - §5.1 probe contract and §5.2 context use → T3/T5. §5.6 capture names → T3/T5 fixture assertions. §5.4 verdicts
    with `spec_impact` → every DIFFERENT/FAILED path. §4.5 guards → the runner (unchanged) + BLOCKED tests. §4.6
    Educational tag → probe 5 `educational_sensitive`. S0-D7 → `requires=(5,)` + the flag rule + report evidence only.
    §10 exit gate item 4 (Q22/Q23 answerable) → T7 step 4 + T8 step 2. Item 6 (isolation) → T1 + T6 step 3. Item 7
    (code review) → T6.
- **Placeholders:** none in code steps. `<sha>`, `<date>` and `<session trailer>` are run-time values the executor
  fills in.
- **Names used across tasks (checked):** `VOUCHER_MONTH_FIELDS`, `FROM_PLACEHOLDER`, `TO_PLACEHOLDER`,
  `fill_month_request`, `untyped_period_vars` (T1 → T2, T3, T5); `B_BOOKS_FROM`, `B_BOOKS_FROM_DATE`, `B_BOOKS_TO`,
  `tag_of`, `kind_label`, `dataset`, `WindowExpectation`, `expect_window`, `voucher_rows`, `compare_tags`,
  `loaded_licence` (T1 → T3, T5); `seed_company_b`, collection markers `S0VoucherMonth` / `S0P05MonthFormula`
  (T2 ↔ T3); `voucher_month` keys `form` / `fields` / `day_window_exact` / `placeholders` (T3 → T5);
  `voucher_blocks`, `xml_bytes`, `element_json`, `raw_json_bytes`, `column_bytes`, `measure`, `mean_block_bytes`,
  `storage_table`, `BLOCK_TAGS`, `PG_ROW_OVERHEAD_BYTES` (T4 → T5).
- **Test count:** T1 12 (2 reads + 8 view + 2 isolation), T2 4, T3 8, T4 8, T5 9 (one parametrized ×2) = **41**.

## Ambiguities in the spec, and how this plan resolves them

1. **Run order vs S0-D7.** §6 says "21 first", but probe 21 step 1 fetches "with probe 5's request", and S0-D7 forbids
   guessing a request another probe must confirm. **Resolution:** probe 5 runs immediately before probe 21 in both
   ordered runs, and `requires=(5,)`. "21 first" is read as "first after the request it depends on". Spec §6/§5.3 get
   a Changed line (T8).
2. **"Counts equal the dataset's" when the dataset has flagged and skipped vouchers.** **Resolution:** compare tag
   sets. Skipped (C36) vouchers are never expected. Cancelled and optional vouchers are expected to *exist* (they are
   vouchers; C42 is about balances), but their presence or absence is recorded, never judged, because probe 3's B part
   owns the flags. The expected FY 2022-23 set is 238 (Sep 2022 = 18), taken from `generate("educational")` minus
   `skip_reason`, never hard-coded in the probe.
3. **Where a probe gets the dataset.** Probe modules may not import `v2.probes.setup` (test_isolation, S0-D8).
   **Resolution:** the new `company_b_view.py` is the single bridge and imports only the pure `company_b_data`. Two
   isolation tests pin this. Probes 16B/18B can reuse it later.
4. **The verdict with the typed/untyped split (C33).** The spec's DIFFERENT is "only the formula works". **Resolution:**
   the typed form is the form v2 always sends, so typed-exact is CONFIRMED. The `spec_impact` states the TYPE="Date"
   requirement. The untyped result is evidence only. If it is *also* exact (C33 not reproduced), the summary flags it
   for review, but the verdict doesn't change.
5. **Reports and untyped dates (the review's open point).** **Resolution:** probe 5 records one TB pair (typed vs
   untyped as-on 30-06-2023: byte-identical?, group rows) as evidence with an explicit "probe 18 B settles this" note.
   No verdict is taken from it, and it is not compared against the dataset (S0-D7).
6. **What "a one-day request (for auto-split)" decides.** **Resolution:** it runs with the working form. A month that
   works while a day doesn't gives DIFFERENT, with the half-month / chunk-cap impact.
7. **The formula candidate's scope.** A collection is scoped to its period, so a formula alone inside an untyped
   (current) period can never reach 2023. **Resolution:** the candidate runs inside a typed books-wide period, and the
   `$$Date:"…"` form is recorded as a guess. It is only sent if the typed form fails.
8. **Probe 21's period-lock step.** It is "a pause if the edition has one", but the operator can't lock a period over
   XML, and a blocked pause would sink the whole part. **Resolution:** an action-less `ask` (ruling C18 style), only
   when interactive and not in auto mode. Otherwise it is recorded "not attempted". A locked period that reads back
   differently gives DIFFERENT.
9. **"Parsed JSON (a stand-in for `raw` JSONB)" and "without `raw`".** **Resolution:** raw JSON = a generic XML→JSON
   of the whole voucher (placeholders dropped). "Without raw" = the Part 1 §5 minimum columns as compact JSON plus
   28 B/row Postgres tuple overhead. Referenced GUIDs are sized like the voucher's own. Indexes are excluded and
   stated. The JSONB binary overhead is a stated caveat, not a model.
10. **Kinds and mix.** Company B's kinds are `sales+inventory+bills`, `sales+inventory` (the non-bill-wise debtor),
    `purchase+inventory+bills`, `receipt+bills`, `receipt` (non-bill-wise), `payment+bills` and `payment` (expenses,
    no bills). Every invoice carries exactly one stock line. **Resolution:** the storage table is weighted by FY
    2022-23's measured mix, and flagged vouchers are left out of size stats. Mean block sizes (ledger line, inventory
    line, bill allocation) are recorded so S1 can scale to fatter invoices.
11. **What settles Q22/Q23.** **Resolution:** probe 21 outputs, per 10k/50k/200k: storage per FY with and without raw,
    raw's share, the saving from dropping raw beyond the 2-FY window at 5 and 10 years (Q22), the full-span table
    2/5/10 years with, without and recent-2-FY-only, the per-extra-FY increment, and month-chunk counts and XML size
    against the ~5k cap (Q23). It also proves reach 3 FYs back (decision 7b). The decisions themselves stay with the
    user.
12. **BooksFrom mismatch.** The spec states the expected value but no verdict for a mismatch. **Resolution:**
    DIFFERENT, with the impact on the backfill's floor.
13. **Preconditions.** **Resolution:** both probes BLOCK unless `environment.company_b_loaded_at` exists (written only
    by a clean `setup-b`) and a licence is recorded. That stops them measuring a half-loaded company.
14. **"Do closed years behave differently?"** (Part 1 §12 probe 21). **Resolution:** one current-FY sample month
    (`fy2025_month_03`), sizes only, recorded for comparison with no verdict.
