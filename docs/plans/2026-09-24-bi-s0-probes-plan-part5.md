# S0 Probes — Part 5: re-run the date-dependent probes (16/17/18) under C33 + C43, and build probes 11, 14, 15 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified**, not at the end (tracker rules).

**Goal:** Make every date the parity probes send one that TallyPrime actually honours, then re-measure probes 16, 17
and 18 on company A and measure the B parts of 16 and 18 on company B for the first time. Before 2026-09-24 those
probes sent **untyped** date variables, which Tally silently replaces with the current period (Ruling C33). Under the
Educational licence, Tally also ignores a date variable whose day isn't 1, 2 or 31 (Ruling C43). Also build and run
probes 11 (openings), 14 (special characters in the company name) and 15 (Unicode + compound units).

**Architecture:** Nothing new in the harness shape. Two changes are cross-cutting. (1) A **central C43 guard** in
`ProbeContext`: under a recorded Educational licence, any request carrying a date variable off day 1/2/31 is refused
before it is sent. The part BLOCKs, so it can never come back as a healthy-looking answer for the wrong period. (2) The
2026-09-23 company-A evidence is **snapshotted** before the re-run overwrites it, and the tests that pin that evidence
are repointed to the snapshot. The new B parts and probes 11/14/15 follow part 4's pattern: B-only
`Probe(parts={"B": run_b})`, dataset read only through `v2/probes/company_b_view.py`, every response captured, verdicts
per S0-D6. `FakeBooks` grows company-B **masters** (groups, units, items, ledgers, opening bill) and the read routes
these probes need. It keeps C33/C43, and "unknown" Tally behaviours are knobs, so each branch of a verdict can be
tested.

**Tech Stack:** Python ≥ 3.12, httpx (`MockTransport` in tests), pytest + pytest-asyncio (`asyncio_mode = "auto"`),
uv. No new dependencies.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md): §7 probes 11,
14, 15, 16, 17, 18 (A and B parts), §6 batches 2 and 5, §4.2 (anchors), §4.5 (guards), §4.6 (Educational-sensitive
probes, Ruling C43), §5.1–§5.8, §11.5 (fixture steps), S0-D6, S0-D7, S0-D8, S0-D9. Parent:
[`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md) decision 11, §6 rung 1/2, §16,
R3, R5, R13, R14, R15, R30.
**Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3 rows 11, 14, 15, 16, 17, 18; §1
decision 11; "Resume here".
**Live findings this plan builds in:** tracker blocks 0a–0g; part 4's SDD ledger
`.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part4/progress.md` (rulings P1–P9, R1–R3, C43); `LESSONS.md` §15
rules 17, 20, 21, 22; C44 (`tally.ini` `Load=`), which another agent is building in
`v2/probes/operator/tally_control.py` (committed as "built, not yet live" at `08b2597`).

**Plan parts:** part 1 [`2026-09-22-bi-s0-probes-plan.md`](2026-09-22-bi-s0-probes-plan.md), part 2
[`2026-09-22-bi-s0-probes-plan-part2.md`](2026-09-22-bi-s0-probes-plan-part2.md), part 3
[`2026-09-23-bi-s0-company-b-loader.md`](2026-09-23-bi-s0-company-b-loader.md), part 4
[`2026-09-24-bi-s0-probes-plan-part4.md`](2026-09-24-bi-s0-probes-plan-part4.md) (probes 5 + 21, ✅ live).
**Part 5 (this file):** the date audit + re-runs of 16/17/18 A, the new B parts of 16/18, and probes 11, 14, 15.
**Not in this part:** probe 22 (BLOCKED — Ruling C36; not planned), the B parts of 3, 23 and 25 (no B code exists;
see "Remaining B parts (3, 23, 25)" below — plan part 6), company C / probe 24.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Nothing outside `v2/` and `docs/` changes** (Task 11 may also edit `LESSONS.md`, as part 4's Task 8 did). v2 never
  imports `backend`, `scripts` or `tests`. `v2/agent/` never imports `v2.probes`. Probe modules (`v2/probes/pNN_*.py`)
  never import `v2.probes.setup` or `v2.probes.operator`. Probe code reads company B's dataset **only** through
  `v2/probes/company_b_view.py` (`test_isolation.py` pins this).
- **Hands off `v2/probes/operator/`** and its tests (`v2/tests/probes/test_tally_control.py`,
  `v2/tests/probes/test_auto_operator.py`). Other agents are editing them concurrently (C44). Never stage them.
  `fake_books.py` keeps importing `OperatorConfig`/`TallyProcess` from there unchanged.
- **Offline tests only.** Tasks 1–9 never talk to a real Tally, never start Wine and never touch `localhost:9000`.
  Tests use `FakeBooks` (`v2/tests/probes/fake_books.py`) or `FakeTally` (`v2/tests/probes/fakes.py`).
- **C33 and C43 stay true in the fakes.** `FakeBooks.requested_period()` honours `SVFROMDATE`/`SVTODATE` only when
  typed. On an educational fake it also honours only days 1/2/31. Otherwise it falls back to `current_period`. No task
  may weaken that. New master routes read the period through the same function.
- **Every date a probe sends is honoured by an Educational Tally.** That means day 1, 2 or 31, in DD-MM-YYYY, typed by
  `envelopes._static_vars`. Task 2's guard enforces it at send time. Month windows on company B come from
  `company_b_view.month_window`. Company A has **no** "loses nothing" clamp, because the seed company holds vouchers on
  any day (20250928, 20251020, …). A company-A date is therefore *chosen* on 1/2/31, never clamped.
- **No hand edits to `v2/probes/results/`** or to the flat fixtures in `v2/tests/fixtures/sync/`. Only the runner
  writes them, in the live tasks (10a, 10b). The **one** exception is Task 1's snapshot folder
  `v2/tests/fixtures/sync/c33_untyped_2026-09-23/`, a byte-for-byte `cp` of existing captures that is never edited
  afterwards.
- **Re-run convention (kept):** re-running a part moves the previous part into `results.json` `history`
  (`ResultsStore.record_part`). Fixture files with the same step name are overwritten. That is why Task 1 snapshots
  them first. Superseded conclusions are *marked* superseded in the tracker, the spec and LESSONS, never deleted.
- **Money is exact.** Amounts are `Decimal` and never float. A missing/empty amount is `None`, compared as `ZERO`
  only where the probe says so explicitly.
- **Request rules** (`safety.check_request` + Task 2's `check_educational_dates`): no `*` as a
  `NATIVEMETHOD`/`FETCH`, no `$$InDateRange`, and no off-day date under Educational. Every read goes through `ctx.send`
  or `ctx.try_send`. One request at a time, no retries. A timeout blocks the part with the popup hint.
- **Period variables on master collections:** only probe 16 may send them (`master_request(allow_period_vars=True)`,
  LESSONS §15 rule 17). `SVTODATE` alone is the default. `SVFROMDATE` on a Ledger collection is sent **only** with
  `--allow-risky`, and this plan does not use `--allow-risky` in its live tasks (see Task 10a's optional step and
  Ambiguity 6).
- **Step names** follow `capture._STEP` (lowercase, digits, `_ . -`), used once per part. Fixtures are
  `pNN_<part>_<step>.xml` (+ `.json`).
- **Verdicts** follow S0-D6 / §5.4. DIFFERENT and FAILED need a `spec_impact`. **Company-B drift** (a ledger, voucher
  or item that the dataset doesn't have, or the reverse) **BLOCKs** with a "re-run `setup-b` verify or restore the
  backup" message. It is never reported as a Tally finding (part 4's Ruling R1 / I1).
- **Company guard for live runs.** Exactly one company is open, and it is the one the part expects: A = `Bharat
  Traders Probe Copy` (100003) or B = `Sharma & Sons' Probe Traders` (100000). **No `--auto`** unless Task 10a step 3
  (C44 live verification) has passed in the same session.
- **Commands** (repo root `/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q` (also once with `-W error` before a commit that ends a task)
  - one file: `uv run --project v2 pytest v2/tests/probes/<file>.py -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **Logs** of every live command go to `logs/` via `2>&1 | tee logs/<name>-$(date +%F).log`.
- **Commits:** one per task, on `feat/bi-s0-probe-harness`. Stage **only the files the task names**. Every message
  ends with the line `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Tracker discipline:** when a task starts, mark its tracker row 🟡; when it finishes, ✅ with proof, plus a dated
  change-log row, in the same turn (CLAUDE.md "Always update the tracker").
- **Code blocks were written against HEAD `08b2597` but not executed while writing.** Before dispatching, run a
  pre-flight scan (paste the plan's code into a scratch copy of `v2/` and run it, as part 4's ledger did). Record any
  correction as a ruling in `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part5/progress.md`. The **tests are the
  contract**. A code block that fails its own test is fixed to pass the test, never the other way round, unless the
  test contradicts this plan's text.

## Review Focus

These five inputs are the ones most likely to hurt a real run. The spec implies them but doesn't spell them out. Each
one has a test in the task that owns the code.

1. **A date variable off day 1/2/31 under Educational**, from an old constant or from a new probe. A person expects
   the probe to refuse to send it (part BLOCKED, named date), **not** to get a healthy answer for the current period.
   This is exactly how probe 18's 30-09-2025 bills read produced a "finding" on 2026-09-23. Tests: Task 2
   `test_an_off_day_date_blocks_the_part_before_anything_is_sent`, Task 3
   `test_every_date_p18_sends_is_one_educational_tally_honours`.
2. **The re-run overwrites the 2026-09-23 captures** that a dozen tests pin as live evidence. The old evidence must
   survive byte-for-byte and those tests must keep passing whatever the re-run captures. Tests: Task 1
   `test_the_2026_09_23_parity_evidence_is_kept_beside_the_live_fixtures`, `test_the_snapshot_really_is_the_untyped_run`.
3. **Company B has drifted** (a ledger typed in by hand, a voucher deleted). Probes 16 B, 18 B and 11 must BLOCK and
   name the drift, not record a Tally FAILED. Tests: Task 5 `test_b_an_extra_ledger_blocks_as_drift`, Task 6
   `test_b_an_extra_ledger_blocks_as_drift`, Task 7 `test_a_missing_ledger_blocks_as_drift`.
4. **The unescaped company-name request wedges Tally** (probe 14 sends deliberately malformed XML). The part must
   BLOCK with the popup hint, send nothing after it, and not crash. Test: Task 8
   `test_a_wedge_after_the_unescaped_request_blocks_with_the_popup_hint`.
5. **Tally sends Hindi as numeric character references** (`&#2358;…`) instead of raw UTF-8 bytes. The parsed text is
   still exact, so probe 15 must record the encoding form and **not** FAIL. Test: Task 9
   `test_hindi_sent_as_character_references_is_still_exact`.

---

## Before you start

- [ ] **Step 0.1: Confirm the base.** Run `git log --oneline -3` and `git status --short -- v2/`.
  Expected: HEAD contains `08b2597` (or later). Changes under `v2/probes/operator/` or its two test files are
  another agent's C44 work: leave them alone and never stage them. Nothing else under `v2/` is modified.
- [ ] **Step 0.2: Record BASE.** Run `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1` and write the number down
  as BASE (618 passed at `08b2597`, including C44 tests in flight). This plan adds about **55** tests. Each task's
  final step records the running count.
- [ ] **Step 0.3: Start the SDD ledger** `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part5/progress.md` (plan path,
  spec path, start HEAD, pre-flight scan result). Mark tracker rows 11, 14, 15, 16, 17, 18 🟡 "plan part 5 in
  progress".

## The date audit (what this plan found; Tasks 2–3 and 5–9 act on it)

Every date variable the affected probes send, checked against C33 (typed?) and C43 (day 1/2/31?). Since `7f32848`
every `SV*DATE` is typed by `envelopes._static_vars`. The **2026-09-23 captures, however, were all untyped** (their
sidecars' `request_xml` shows `<SVTODATE>31-10-2025</SVTODATE>`).

| Probe / step | Dates sent | C33 on 2026-09-23 | C43 | Consequence |
|---|---|---|---|---|
| 16 A `vouchers_fy`, `tb_fy_end`, throwaway reads | 01-04-2025 .. 31-03-2026 | untyped → current period = the same FY | ✓ | Window unchanged; conclusions from these steps stand |
| 16 A `ledgers_asof_2025-10-31` (Ledger collection, SVTODATE) | 31-10-2025 | **untyped → ignored by C33 alone** | ✓ | "SVTODATE is silently ignored on a Ledger collection" (LESSONS rule 17, tracker decision 11 "impossible") is **unproven for the typed form** → re-measure (Task 10a) |
| 16 A `ledgers_svfromdate_2025-10-01` (opt-in) | 01-10-2025 / 31-10-2025 | untyped | ✓ | "SVFROMDATE wedges Tally" was measured untyped. Not re-measured by default (Ambiguity 6) |
| 17 A `tb_exploded_*` | 01-04-2025 .. 31-03-2026 | untyped, but reports honoured it (p05's typed/untyped TB pair was byte-identical) | ✓ | Conclusion stands. The stored `ledger_level_tb` **template is untyped** (confirmed before `7f32848`) → re-run to re-confirm it typed |
| 18 A `tb_asof_2025-10-31` | 01-04-2025 .. 31-10-2025 | untyped (report honoured it) | ✓ | "An as-on TB is history" stands; re-run confirms typed |
| 18 A `vouchers_to_2025-10-31` (Voucher collection) | 01-04-2025 .. 31-10-2025 | **untyped → Tally returned the whole FY** (the fixture holds vouchers to 20260301) | ✓ | The probe's "matches the FULL period" evidence silently relied on C33. Typed, it would compute "full period" from October data → **fetch the full FY explicitly** (Task 3) |
| 18 A `bills_*_asof_2025-09-30`, `stock_summary_asof_2025-09-30` | **30-09-2025** | untyped | **✗ day 30** | "Bills Receivable/Payable/Stock Summary ignore the as-on date" (LESSONS rule 20 second half, tracker row 18 DIFFERENT) is **very likely a C43 artifact**: an ignored 30-09-2025 falls back to the period end, which is exactly what was recorded → move to 31-10-2025 (Task 3) and re-measure |
| 16 B (new) | 31-03-2025, 31-03-2023; opt-in 01-04-2024 | typed | ✓ | — |
| 18 B (new) | 01-04-2022 .. 31-03-2023 | typed | ✓ | — |
| 11 (new) | 01-04-2022 (opening-bills fallback) | typed | ✓ | — |
| 15 (new) | one-day windows on dataset dates (days 1/2/31 by construction); 01-04-2022 .. 31-03-2026 | typed | ✓ | — |
| 14 (new) | none | — | — | — |

Outside this plan's probes, 0/3/4/6/10/12/19 and the anchors check only send 01-04-2025 / 31-03-2026. That is company
A's current period, so C33 didn't change their windows and C43 doesn't apply. They are not re-run here.

## Remaining B parts (3, 23, 25): not runnable yet, so deferred to plan part 6

None of them has B code. `p03`, `p23` and `p25` all declare `parts={"A": run_a}, planned_parts=("A", "B")`. Their
module docstrings still say "added in plan part 3", which never happened. What each one needs:

| Probe | Missing |
|---|---|
| 3 B | `run_b`: a books-wide typed Voucher read (01-04-2022..31-03-2026) with the flag fields. Tags 201/202 `IsCancelled=Yes`, 301/302 `IsOptional=Yes`, every other written tag both `No` (via `company_b_view`). A `FakeBooks` route that exports the flags for that collection. p21's live run already saw the cancelled pair come back (evidence, not a verdict). |
| 23 B | `run_b`: `BillCreditPeriod` / due date on the bills setup gave credit periods (dataset `BillSpec.credit_period`, e.g. `Inv/1` "30 Days"), and the due-date column of Bills Receivable (`BILLDUE`). `FakeBooks` has to store and export credit periods (today `_post_bills` drops them). |
| 25 B | `run_b`: the `Sales - GST` voucher type resolves to Sales by its `Parent` / `ReservedName`. `FakeBooks`' `S0BVoucherTypes` route exports names only, with no parent. |

They go into plan part 6 together with company C / probe 24. None of them has a live-run task here.

## File Structure

| File | Responsibility |
|---|---|
| `v2/tests/fixtures/sync/c33_untyped_2026-09-23/` *(create, copy only)* | Byte-for-byte snapshot of the 2026-09-23 `p16_A_*`, `p17_A_*`, `p18_A_*` captures (xml + sidecar) |
| `v2/tests/probes/test_evidence_snapshot.py` *(create)* | Task 1: the snapshot exists, is the untyped run, and shows C33 |
| `v2/tests/probes/test_{p16,p17,p18}_…py`, `test_reads.py`, `test_company_b.py` *(modify)* | Task 1: live-evidence tests read the snapshot, not the flat names the re-run overwrites |
| `v2/probes/safety.py` *(modify)* | Task 2: `EDUCATIONAL_DATE_VAR_DAYS`, `educational_ignored_dates()`, `check_educational_dates()` |
| `v2/probes/context.py` *(modify)* | Task 2: calls `check_educational_dates` on every send |
| `v2/probes/company_b_view.py` *(modify)* | Task 2: `check_date_vars` uses the shared constant. Task 4: dataset accessors for 11/14/15/16B/18B |
| `v2/probes/__main__.py` *(modify)* | Task 2: `anchors` command (spec §4.2 before and after parity probes in single runs) |
| `v2/probes/p18_historical_reports.py` *(modify)* | Task 3: C43 bills/stock date, full-FY voucher read. Task 6: `run_b` + `compare_group_rows` |
| `v2/probes/p16_ledger_closing_balance.py` *(modify)* | Task 3: honest "untyped" wording. Task 5: `run_b` |
| `v2/tests/probes/fake_books.py` *(modify)* | Task 4: company-B masters, Ledger/Group/StockItem/Stock Summary routes, knobs, malformed/unknown-company answers |
| `v2/tests/probes/test_fake_books_company_b_masters.py` *(create)* | Task 4 tests |
| `v2/tests/probes/test_p16_b_part.py`, `test_p18_b_part.py` *(create)* | Tasks 5, 6 |
| `v2/probes/p11_openings.py`, `p14_special_char_company.py`, `p15_unicode_compound_units.py` *(create)* | Tasks 7, 8, 9 |
| `v2/tests/probes/test_p11_openings.py`, `test_p14_special_char_company.py`, `test_p15_unicode_compound_units.py` *(create)* | Tasks 7, 8, 9 |
| `v2/probes/registry.py` *(modify)* | Tasks 7–9: `module=` for 11, 14, 15 |
| `v2/tests/probes/test_cli.py` *(modify)* | Task 2: anchors test. Task 7: the "unbuilt probe" test moves from 11 to 22 |

---

### Task 1: Snapshot the 2026-09-23 company-A parity evidence and repoint the tests that pin it

**Files:**
- Create: `v2/tests/fixtures/sync/c33_untyped_2026-09-23/` (copies only), `v2/tests/probes/test_evidence_snapshot.py`
- Modify: `v2/tests/probes/test_p16_ledger_closing_balance.py:369`, `v2/tests/probes/test_p17_ledger_level_tb.py:95`,
  `v2/tests/probes/test_p18_historical_reports.py:131`, `v2/tests/probes/test_reads.py` (p16/p17/p18 references
  only), `v2/tests/probes/test_company_b.py:22-24`

**Interfaces:**
- Consumes: nothing new.
- Produces: `SNAPSHOT = <sync>/c33_untyped_2026-09-23`, the folder every "live 2026-09-23" test reads from now on.
  Tasks 10a/10b's re-runs may overwrite the flat `p16_A_*`/`p17_A_*`/`p18_A_*` files freely.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_evidence_snapshot.py`:

```python
"""The 2026-09-23 company-A parity captures, kept beside the live fixtures before plan part 5 re-runs 16/17/18.

They were sent with UNTYPED date variables (Ruling C33), so they are history, not current evidence: the tests that
pin what that run saw read them from here, and the re-run is free to overwrite the flat `p16_A_*` … files.
"""
import json
from datetime import date
from pathlib import Path

from v2.probes.reads import parse_vouchers, tally_date

SYNC = Path(__file__).resolve().parents[1] / "fixtures" / "sync"
SNAPSHOT = SYNC / "c33_untyped_2026-09-23"


def test_the_2026_09_23_parity_evidence_is_kept_beside_the_live_fixtures():
    names = {p.name for p in SNAPSHOT.iterdir()}
    for required in ("p16_A_ledgers_asof_2025-10-31.xml", "p16_A_tb_fy_end.xml", "p17_A_tb_exploded_isledgerwise.xml",
                     "p17_A_tb_exploded_explodealllevels.xml", "p18_A_bills_receivable_asof_2025-09-30.xml",
                     "p18_A_vouchers_to_2025-10-31.xml", "p18_A_stock_summary_asof_2025-09-30.xml"):
        assert required in names and f"{required}.json" in names, required


def test_the_snapshot_really_is_the_untyped_run():
    sidecar = json.loads((SNAPSHOT / "p16_A_ledgers_asof_2025-10-31.xml.json").read_text(encoding="utf-8"))
    assert "<SVTODATE>31-10-2025</SVTODATE>" in sidecar["request_xml"]
    assert 'TYPE="Date"' not in sidecar["request_xml"]


def test_the_untyped_voucher_read_answered_for_the_whole_fy_c33():
    """Why probe 18's 'full period' evidence held on 2026-09-23: the untyped to-date was ignored."""
    vouchers = parse_vouchers((SNAPSHOT / "p18_A_vouchers_to_2025-10-31.xml").read_text(encoding="utf-8"))
    assert max(tally_date(v["header"]["DATE"]) for v in vouchers) > date(2025, 10, 31)
```

- [ ] **Step 2: Run to verify they fail.**
  `uv run --project v2 pytest v2/tests/probes/test_evidence_snapshot.py -q`. Expected: FAIL (`FileNotFoundError` on
  the snapshot folder).
- [ ] **Step 3: Make the snapshot** (a copy, never edited afterwards):

```bash
cd "/Users/nuvanta-mac-3/work/Tally prime"
SNAP=v2/tests/fixtures/sync/c33_untyped_2026-09-23
mkdir -p "$SNAP"
cp -p v2/tests/fixtures/sync/p16_A_* v2/tests/fixtures/sync/p17_A_* v2/tests/fixtures/sync/p18_A_* "$SNAP"/
diff -rq <(cd v2/tests/fixtures/sync && ls p16_A_* p17_A_* p18_A_*) <(ls "$SNAP")   # expect no output
```

- [ ] **Step 4: Repoint the evidence tests.**
  - In `test_p16_ledger_closing_balance.py`, `test_p17_ledger_level_tb.py` and `test_p18_historical_reports.py`,
    replace the `SYNC = …` line (it is used only for p16/p17/p18 captures in those files) with:
    ```python
    # The 2026-09-23 run (untyped dates, C33) — plan part 5 re-runs these probes and overwrites the flat captures.
    SYNC = Path(__file__).resolve().parents[1] / "fixtures" / "sync" / "c33_untyped_2026-09-23"
    ```
  - In `test_reads.py`, keep `SYNC` (it also reads `p00_*`/`p01_*`). Add under it
    `C33_SNAPSHOT = SYNC / "c33_untyped_2026-09-23"   # 2026-09-23 p16/p17/p18 captures (C33)`, then replace every
    `SYNC / "p16_A_`, `SYNC / "p17_A_`, `SYNC / "p18_A_` with `C33_SNAPSHOT / "p16_A_` and so on (seven sites: lines
    62, 78, 80, 98, 101, 108 and any others the grep below finds).
  - In `test_company_b.py` lines 23–24:
    `LIVE_A_TB_FY_END = _SYNC_FIXTURES / "c33_untyped_2026-09-23" / "p16_A_tb_fy_end.xml"` and the same prefix for
    `LIVE_A_TB_EXPLODED`.
  - Check: `grep -rnE 'SYNC(_FIXTURES)? / "p1[678]_A_' v2/tests` prints nothing.
- [ ] **Step 5: Run the whole suite.** `uv run --project v2 pytest v2/tests -q`. Expected: BASE + 3, all green.
- [ ] **Step 6: Commit.**

```bash
git add v2/tests/fixtures/sync/c33_untyped_2026-09-23 v2/tests/probes/test_evidence_snapshot.py \
        v2/tests/probes/test_p16_ledger_closing_balance.py v2/tests/probes/test_p17_ledger_level_tb.py \
        v2/tests/probes/test_p18_historical_reports.py v2/tests/probes/test_reads.py v2/tests/probes/test_company_b.py
git commit -m "test(bi/v2): snapshot the 2026-09-23 (untyped, C33) p16/p17/p18 captures before the part-5 re-run" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The central C43 guard, and an `anchors` command

**Files:**
- Modify: `v2/probes/safety.py`, `v2/probes/context.py` (`try_send`, `_post_uncaptured`), `v2/probes/company_b_view.py`
  (`EDUCATIONAL_DATE_VAR_DAYS` comes from `safety`), `v2/probes/__main__.py` (new `anchors` sub-command, docstring)
- Test: `v2/tests/probes/test_safety.py` (append), `v2/tests/probes/test_c43_guard.py` (create),
  `v2/tests/probes/test_cli.py` (append)

**Interfaces:**
- Consumes: `store.environment["licence"]` (recorded by probe 0), `runner.run_anchor_check`.
- Produces:
  ```python
  # v2/probes/safety.py
  EDUCATIONAL_DATE_VAR_DAYS: tuple[int, ...] = (1, 2, 31)
  def educational_ignored_dates(xml: str) -> list[str]            # ["SVTODATE=30-09-2025", …]
  def check_educational_dates(xml: str, licence: str | None) -> None   # raises GuardError
  # CLI
  python -m v2.probes anchors [--when before_parity|after_a_batch]    # exit 0 = company A intact, 1 = not
  ```

- [ ] **Step 1: Write the failing tests.** Append to `v2/tests/probes/test_safety.py`:

```python
def test_educational_guard_refuses_an_off_day_date_variable_typed_or_not():
    import pytest
    from v2.agent.tally.envelopes import wrap_report
    from v2.probes.reads import untyped_period_vars
    from v2.probes.safety import GuardError, check_educational_dates
    xml = wrap_report("Bills Receivable", "30-09-2025", "30-09-2025", "Co")
    with pytest.raises(GuardError, match="SVFROMDATE=30-09-2025"):
        check_educational_dates(xml, "educational")
    with pytest.raises(GuardError, match="C43"):
        check_educational_dates(untyped_period_vars(xml), "educational")


def test_educational_guard_passes_days_1_2_31_placeholders_licensed_and_unknown():
    from v2.agent.tally.envelopes import wrap_report
    from v2.probes.safety import check_educational_dates
    for day in ("01-04-2025", "02-06-2023", "31-10-2025"):
        check_educational_dates(wrap_report("Trial Balance", day, day, "Co"), "educational")
    check_educational_dates(wrap_report("Trial Balance", "__FROM__", "__TO__", "Co"), "educational")
    check_educational_dates(wrap_report("Trial Balance", "30-09-2025", "30-09-2025", "Co"), "licensed")
    check_educational_dates(wrap_report("Trial Balance", "30-09-2025", "30-09-2025", "Co"), None)


def test_educational_guard_reads_every_date_format_tally_accepts():
    from v2.probes.safety import educational_ignored_dates
    assert educational_ignored_dates('<SVTODATE TYPE="Date">20250930</SVTODATE>') == ["SVTODATE=20250930"]
    assert educational_ignored_dates("<SVFROMDATE>30-Sep-2025</SVFROMDATE>") == ["SVFROMDATE=30-Sep-2025"]
    assert educational_ignored_dates("<SVCURRENTDATE>1-Apr-25</SVCURRENTDATE>") == []
```

Create `v2/tests/probes/test_c43_guard.py`:

```python
"""Task 2: the C43 guard sits in ProbeContext, so no probe (old constant or new code) can send an off-day date to an
Educational Tally and read the silent current-period fallback as data."""
from v2.agent.tally.envelopes import wrap_report
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, ready_store, tb_xml


def _probe() -> Probe:
    async def part(ctx):
        await ctx.send("tb", wrap_report("Trial Balance", "01-04-2025", "30-09-2025", ctx.company_name))
        return PartResult(Outcome.CONFIRMED, "sent")
    return Probe(id=97, name="c43_guard_test", question="?", feeds=("test",), parts={"A": part})


async def _run(tmp_path, licence):
    fake, _ = a_tally()
    fake.route("<ID>Trial Balance</ID>", lambda body: tb_xml([("Capital Account", "", "1.00")]))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, licence=licence)
    await run_probe(_probe(), labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return fake, store.probe_entry(97)["parts"]["A"]


async def test_an_off_day_date_blocks_the_part_before_anything_is_sent(tmp_path):
    fake, part = await _run(tmp_path, "educational")
    assert part["outcome"] == "BLOCKED" and "SVTODATE=30-09-2025" in part["summary"]
    assert not any("<ID>Trial Balance</ID>" in body for body in fake.requests)


async def test_a_licensed_tally_gets_the_same_request(tmp_path):
    fake, part = await _run(tmp_path, "licensed")
    assert part["outcome"] == "CONFIRMED"
    assert any("<ID>Trial Balance</ID>" in body for body in fake.requests)
```

Append to `v2/tests/probes/test_cli.py`:

```python
def test_anchors_command_without_a_baseline_fails_and_is_recorded(tmp_path):
    io = ScriptedIO()
    results = tmp_path / "r.json"
    assert main(["--results", str(results), "anchors"], transport=FakeTally([COMPANIES["A"]]).transport(), io=io) == 1
    assert any("anchors check (before_parity) company A: FAILED" in s and "No TB baseline" in s for s in io.said)
    assert ResultsStore(results).anchor_checks[-1]["when"] == "before_parity"
```

- [ ] **Step 2: Run to verify they fail.**
  `uv run --project v2 pytest v2/tests/probes/test_safety.py v2/tests/probes/test_c43_guard.py v2/tests/probes/test_cli.py -q`.
  Expected: `ImportError` (`check_educational_dates`), and `argparse` "invalid choice: 'anchors'".
- [ ] **Step 3: Implement.** In `v2/probes/safety.py`, add to the imports `from datetime import datetime` and append:

```python
# C43 (live 2026-09-24, LESSONS §15 rule 22): Educational TallyPrime silently ignores a date static variable whose day
# is not one of these — typed or untyped — and answers for the current period instead. Company-B month windows are
# clamped to them (company_b_view.month_window); every other date is chosen on them. This guard refuses the rest.
EDUCATIONAL_DATE_VAR_DAYS = (1, 2, 31)
_DATE_VAR = re.compile(r"<(SV[A-Z0-9]*DATE)\b[^>]*>([^<]*)</\1\s*>", re.IGNORECASE)
_DATE_FORMATS = ("%d-%m-%Y", "%Y%m%d", "%d-%b-%Y", "%d-%b-%y")


def _day(text: str) -> int | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).day
        except ValueError:
            continue
    return None          # a placeholder (__FROM__) or something Tally would not read as a date either


def educational_ignored_dates(xml: str) -> list[str]:
    """`NAME=value` for every date static variable an Educational Tally would silently replace (C43)."""
    bad = []
    for name, value in _DATE_VAR.findall(xml):
        day = _day(value.strip())
        if day is not None and day not in EDUCATIONAL_DATE_VAR_DAYS:
            bad.append(f"{name}={value.strip()}")
    return bad


def check_educational_dates(xml: str, licence: str | None) -> None:
    """Refuse, before sending, a date an Educational Tally would ignore. A licensed (or not-yet-recorded) licence
    passes: a licensed Tally honours any valid date, and probe 0 runs before any licence is known."""
    if licence != "educational":
        return
    bad = educational_ignored_dates(xml)
    if bad:
        raise GuardError(f"Request refused: {', '.join(bad)} — Educational Tally ignores a date variable off day "
                         "1/2/31 and silently answers for the current period (C43, LESSONS §15 rule 22).")
```

In `v2/probes/context.py`: change the safety import to
`from v2.probes.safety import check_educational_dates, check_request`, and in **both** `try_send` and
`_post_uncaptured` add, right after `check_request(xml)`:

```python
        check_educational_dates(xml, self.store.environment.get("licence"))
```

In `v2/probes/company_b_view.py`, replace the local definition `EDUCATIONAL_DATE_VAR_DAYS = (1, 2, 31)` with
`from v2.probes.safety import EDUCATIONAL_DATE_VAR_DAYS` (keep the C43 comment above it). `check_date_vars` is
unchanged.

In `v2/probes/__main__.py`: add `anchors` to the module docstring's command list. Add
`from v2.probes.registry import ANCHORS_AFTER_A, ANCHORS_BEFORE_PARITY` to the registry import and
`run_anchor_check` to the runner import. In `build_parser()`, after the `setup-b` parser:

```python
    anchors = sub.add_parser("anchors", help="is company A intact? (S0 spec §4.2) — read-only, recorded in results.json")
    anchors.add_argument("--when", choices=["before_parity", "after_a_batch"], default="before_parity")
```

Add the coroutine:

```python
async def _anchors(args, store: ResultsStore, transport: httpx.AsyncBaseTransport | None, io: ProbeIO) -> int:
    """Spec §4.2's anchors check on its own, for single `run` sessions (ordered runs already include it)."""
    step = ANCHORS_BEFORE_PARITY if args.when == "before_parity" else ANCHORS_AFTER_A
    client = TallyClient(args.host, args.port, transport=transport)
    try:
        return 0 if await run_anchor_check(step, "A", client=client, store=store, io=io) else 1
    finally:
        await client.close()
```

In `main()`, after the `setup-b` branch:

```python
    if args.command == "anchors":
        return asyncio.run(_anchors(args, store, transport, io or ConsoleIO(interactive=not args.non_interactive)))
```

(`ANCHORS_BEFORE_PARITY == "anchors:before_parity"`, `ANCHORS_AFTER_A == "anchors:after_a_batch"`, so the recorded
`when` values are `before_parity` / `after_a_batch`.)

- [ ] **Step 4: Run the three files, then the whole suite** (also with `-W error`). Expected: all green, BASE + 9.
  If an existing test now BLOCKs because it sends an off-day date under an educational store, the guard found a
  real case. Record it in the ledger and fix the probe's date (don't weaken the guard). The only known cases are
  probe 18's 30-09-2025 constants, which Task 3 fixes, and they only BLOCK under an educational store. The existing
  p18 tests use `licence="licensed"`.
- [ ] **Step 5: Commit** (`v2/probes/safety.py v2/probes/context.py v2/probes/company_b_view.py v2/probes/__main__.py
  v2/tests/probes/test_safety.py v2/tests/probes/test_c43_guard.py v2/tests/probes/test_cli.py`):
  `feat(bi/v2): C43 guard on every probe send + anchors command`.

---

### Task 3: Company-A date fixes in 16, 17 and 18, before their re-run

**Files:**
- Modify: `v2/probes/p18_historical_reports.py` (constants, `run_a`, docstring),
  `v2/probes/p16_ledger_closing_balance.py` (`SVFROMDATE_SKIPPED`, `AS_ON_IMPACT`, `_ledgers_request` signature,
  `_svfromdate_attempt` returns rows too; docstring), `v2/probes/p17_ledger_level_tb.py` (docstring only)
- Test: `v2/tests/probes/test_p18_historical_reports.py`, `test_p16_ledger_closing_balance.py`,
  `test_p17_ledger_level_tb.py` (append; update one fixture name in `test_history_reads_match_the_lines`)

**Interfaces:**
- Consumes: Task 2's guard (`check_educational_dates` through `ctx.send`) and `safety.educational_ignored_dates`.
- Produces (used by Task 5):
  ```python
  # p16
  def _ledgers_request(company: str, static_vars: dict[str, str] | None = None, *, name: str = "S0P16Ledgers") -> str
  async def _svfromdate_attempt(ctx, step: str = SVFROMDATE_STEP, static_vars: dict[str, str] | None = None,
                                collection: str = "S0P16Ledgers") -> tuple[dict, dict[str, dict]]
  # p18
  BILLS_AS_ON = "31-10-2025"; step names bills_receivable_asof_2025-10-31, bills_payable_asof_2025-10-31,
  stock_summary_asof_2025-10-31, vouchers_fy
  ```

- [ ] **Step 1: Write the failing tests.** Append to `test_p18_historical_reports.py`:

```python
async def test_every_date_p18_sends_is_one_educational_tally_honours(tmp_path):
    """C43: 30-09-2025 (the 2026-09-23 bills/stock date) is ignored by an Educational Tally; the guard would block."""
    from v2.probes.safety import educational_ignored_dates
    fake = _fake()
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, licence="educational")
    await run_probe(p18.PROBE, labels=["A"], client=client, store=store, capture=capture, io=ScriptedIO())
    part = store.probe_entry(18)["parts"]["A"]
    assert part["outcome"] != "BLOCKED", part["summary"]
    assert all(educational_ignored_dates(body) == [] for body in fake.probe_requests())
    assert "p18_A_bills_receivable_asof_2025-10-31.xml" in part["fixtures"]


async def test_vouchers_are_read_for_the_whole_fy_typed_and_filtered_in_python(tmp_path):
    """C33: the old `vouchers_to_2025-10-31` read only reached the full FY because Tally ignored its untyped to-date;
    typed, it would stop at October and the 'matches the FULL period' evidence would be computed from October."""
    fake = _fake()
    _, part = await _run(tmp_path, fake)
    body = next(r for r in fake.probe_requests() if "S0P18Vouchers" in r)
    assert '<SVFROMDATE TYPE="Date">01-04-2025</SVFROMDATE>' in body
    assert '<SVTODATE TYPE="Date">31-03-2026</SVTODATE>' in body
    assert "p18_A_vouchers_fy.xml" in part["fixtures"]
```

In `test_history_reads_match_the_lines`, change the fixture name it asserts to
`"p18_A_stock_summary_asof_2025-10-31.xml"`. Leave
`test_the_live_bills_and_stock_reports_ignore_the_as_on_date_and_return_the_current_position` as it is (it now reads
the snapshot), but add a first docstring line:
`"2026-09-23 capture — 30-09-2025 was a C43-ignored date, so this pins what that run SAW, not a Tally rule."`

Append to `test_p16_ledger_closing_balance.py`:

```python
async def test_every_date_p16_sends_is_one_educational_tally_honours(tmp_path):
    from v2.probes.safety import educational_ignored_dates
    fake, on_action = _fake()
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, licence="educational")
    await run_probe(p16.PROBE, labels=["A"], client=client, store=store, capture=capture, io=_io(on_action),
                    allow_risky=True)
    assert store.probe_entry(16)["parts"]["A"]["outcome"] != "BLOCKED"
    assert all(educational_ignored_dates(body) == [] for body in fake.probe_requests())


async def test_the_skipped_svfromdate_note_says_the_wedge_was_measured_untyped(tmp_path):
    fake, on_action = _fake()
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    note = part["observations"]["as_on_svfromdate"]["note"]
    assert "untyped" in note and "not been re-measured" in note
```

Append to `test_p17_ledger_level_tb.py` (a pin: it passes as soon as the harness types dates, and it states why 17 is
re-run):

```python
async def test_every_date_p17_sends_is_honoured_and_the_confirmed_template_is_typed(tmp_path):
    from v2.probes.safety import educational_ignored_dates
    fake = _fake(_explode_on_flag())
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, baseline=BASELINE, licence="educational")
    await run_probe(p17.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    assert store.probe_entry(17)["parts"]["A"]["outcome"] == "CONFIRMED"
    assert all(educational_ignored_dates(body) == [] for body in fake.probe_requests())
    template = store.confirmed("ledger_level_tb")["xml_template"]
    assert '<SVFROMDATE TYPE="Date">01-04-2025</SVFROMDATE>' in template
```

(If `_explode_on_flag()` isn't the CONFIRMED-path handler in that file, use whichever helper
`test_explodeflag_gives_ledger_rows_and_is_confirmed` uses.)

- [ ] **Step 2: Run to verify.** The two p18 tests and the p16 note test FAIL (guard BLOCKs on 30-09-2025; request
  has SVTODATE 31-10-2025; note lacks "untyped"). The p16 educational test and the p17 test pass already. They are
  pins and are named as such in the commit message.
- [ ] **Step 3: Implement p18.** Replace the constants block at the top:

```python
TB_AS_ON = "31-10-2025"
# C43 (LESSONS §15 rule 22): this was 30-09-2025 — a day Educational Tally silently ignores, answering for the current
# period's end instead. That is exactly what the 2026-09-23 run recorded as "Bills/Stock ignore the as-on date"
# (snapshot: v2/tests/fixtures/sync/c33_untyped_2026-09-23/). 31-10-2025 is honoured under either licence and still
# splits company A's year (its vouchers run to 01-03-2026), so bills and stock still differ from the full period.
BILLS_AS_ON = "31-10-2025"
```

In `run_a`, replace the vouchers read with the full FY (defaults of `voucher_request`) and rename the dated steps:

```python
    # C33: the as-on figures filter these in Python (ledger_movements / pending_bills / stock_verdict take `as_on`);
    # the FULL-period comparison needs the whole FY, which the old untyped `vouchers_to_…` read only got by accident.
    vouchers = parse_vouchers(await ctx.send("vouchers_fy", voucher_request("S0P18Vouchers", VOUCHER_FIELDS, company)))
    …
    receivable = await ctx.send("bills_receivable_asof_2025-10-31",
                                wrap_report("Bills Receivable", BILLS_AS_ON, BILLS_AS_ON, company))
    payable = await ctx.send("bills_payable_asof_2025-10-31",
                             wrap_report("Bills Payable", BILLS_AS_ON, BILLS_AS_ON, company))
    …
    stock_text = await ctx.send("stock_summary_asof_2025-10-31",
                                wrap_report("Stock Summary", A_FY_FROM, BILLS_AS_ON, company,
                                            extra_vars=STOCK_EXPLODE_CANDIDATE))
```

Add a docstring paragraph: "Changed 2026-09-24 (plan part 5): dates audited against C33/C43 — bills/stock as-on
moved 30-09-2025 → 31-10-2025; vouchers read for the whole FY."

- [ ] **Step 4: Implement p16** (behaviour unchanged, wording made honest, two signatures widened for Task 5):

```python
SVFROMDATE_SKIPPED = ("not sent: SVFROMDATE on a Ledger collection froze Tally's XML server behind a modal (live "
                      "2026-09-23, twice — sent untyped, before C33 was known; the typed form has not been "
                      f"re-measured) and needed a Tally restart. Opt in with {RISKY_HINT}.")
AS_ON_IMPACT = ("Per-ledger as-on balances are unobtainable from the Ledger collection (a typed SVTODATE is silently "
                "ignored; SVFROMDATE froze Tally when sent untyped on 2026-09-23), so rung 1's per-ledger opening "
                "anchor during the backfill depends on probe 17's exploded ledger-level TB (decision 11) — that route "
                "is impossible, not merely unattractive. Reports (TYPE=Data) are unaffected.")


def _ledgers_request(company: str, static_vars: dict[str, str] | None = None, *, name: str = "S0P16Ledgers") -> str:
    """The Ledger collection. Probe 16 is the one deliberate exception to the master-collection period-variable guard
    in reads.master_request: it is the probe that measures what those variables do (reads.MASTER_PERIOD_VARS_ERROR)."""
    return master_request(name, "Ledger", LEDGER_FIELDS, company, static_vars=static_vars,
                          allow_period_vars=static_vars is not None)


async def _svfromdate_attempt(ctx: ProbeContext, step: str = SVFROMDATE_STEP,
                              static_vars: dict[str, str] | None = None,
                              collection: str = "S0P16Ledgers") -> tuple[dict, dict[str, dict]]:
    """(record, parsed ledgers) — the dangerous half: SVFROMDATE on a Ledger collection, OFF unless --allow-risky.
    (Unchanged docstring text from here on.)"""
    if not ctx.allow_risky:
        return {"attempted": False, "note": SVFROMDATE_SKIPPED}, {}
    variables = static_vars or {"SVFROMDATE": AS_ON_FROM, "SVTODATE": AS_ON_TO}
    text, error = await ctx.try_send(step, _ledgers_request(ctx.company_name, variables, name=collection),
                                     timeout=SVFROMDATE_TIMEOUT_S)
    if error is None:
        rows = _balances(text)
        return ({"attempted": True, "error": None, "wedged": False, "ledgers": len(rows),
                 "elapsed_ms": ctx.last_response.elapsed_ms, "tally_after": "answered (the read didn't hang)"}, rows)
    try:
        names = await ctx.company_names()
    except ProbeBlocked as exc:
        return {"attempted": True, "error": error, "wedged": True, "tally_after": f"no answer: {exc}"}, {}
    return {"attempted": True, "error": error, "wedged": False, "tally_after": f"answered: {names}"}, {}
```

In `run_a`: `svfromdate, _ = await _svfromdate_attempt(ctx)`. In `_as_on`, build the SVTODATE read with
`_ledgers_request(ctx.company_name, {"SVTODATE": AS_ON_TO})` (unchanged call, new signature). In the module docstring,
replace "The B part … comes in plan part 3" with "The B part is `run_b` (plan part 5)". Task 5 adds `run_b`.

- [ ] **Step 5: p17 docstring.** Add: "Its dates are company A's current period, so C33 didn't change the window it
  measured. It is re-run in plan part 5 only so that the stored `ledger_level_tb` template is the typed form (the
  2026-09-23 one predates `7f32848`)."
- [ ] **Step 6: Run the three probe test files, then the whole suite** (also `-W error`). Expected: BASE + 15.
- [ ] **Step 7: Commit** (the three probe modules + the three test files):
  `fix(bi/v2): C43/C33 date audit — p18 bills/stock on 31-10-2025, full-FY voucher read; p16/p17 pins`.

---

### Task 4: `FakeBooks` gets company B's masters, and `company_b_view` exposes what 11/14/15/16B/18B read

**Files:**
- Modify: `v2/tests/probes/fake_books.py`, `v2/probes/company_b_view.py`
- Create: `v2/tests/probes/test_fake_books_company_b_masters.py`
- Test (append): `v2/tests/probes/test_company_b_view.py`

**Interfaces:**
- Consumes: `setup.company_b_data.{generate, expected_figures, quantity_unit, Expected, LedgerSpec, StockItemSpec,
  HINDI_DEBTOR, COMPOUND_UNIT, OPENING_BILL_DATE}` (the view is still the only bridge).
- Produces:
  ```python
  # v2/probes/company_b_view.py
  HINDI_DEBTOR: str; COMPOUND_UNIT: str
  def expected(licence: str) -> Expected                               # lru_cached expected_figures(dataset)
  def ledger_balances_at(licence: str, day: date) -> dict[str, Decimal]    # day = a month end; else ValueError
  def ledger_openings_at(licence: str, fy_start: date) -> dict[str, Decimal]  # 1 April; else ValueError
  def ledger_specs(licence: str) -> dict[str, LedgerSpec]
  def item_specs(licence: str) -> dict[str, StockItemSpec]
  def qty_unit(licence: str, item: str) -> str                        # C40: compound → its first unit ("Box")
  def stock_qty_at(licence: str, item: str, day: date) -> Decimal
  def first_voucher(licence: str, wanted: Callable[[VoucherSpec], bool]) -> VoucherSpec   # written, unflagged
  # v2/tests/probes/fake_books.py
  seed_company_b(books, licence="educational", *, masters: bool = False)
  FakeBooks(..., ledger_svtodate_honoured=False, ledger_opening_scope="books", ledger_svfromdate_wedges=True,
            ledger_opening_bills_exported=True, opening_stock_row=False, honour_company_var=False,
            tolerate_raw_ampersand=False)
  B_PROBE_COLLECTIONS = ("S0P11", "S0P14", "S0P15", "S0P16B", "S0P18B")   # collection-name prefixes routed generically
  MALFORMED_ANSWER: str                                                    # LINEERROR envelope
  ```

- [ ] **Step 1: Write the failing tests.** Append to `v2/tests/probes/test_company_b_view.py`:

```python
def test_dataset_balances_and_openings_come_from_the_dataset_alone():
    from datetime import date
    from decimal import Decimal
    import pytest
    from v2.probes.company_b_view import ledger_balances_at, ledger_openings_at, ledger_specs
    books = ledger_openings_at("educational", date(2022, 4, 1))
    assert books["Pune Digital Solutions"] == Decimal("-62500.00")
    assert books["Capital Account"] == Decimal("1000000.00")
    assert books == {n: (s.opening or Decimal("0.00")) for n, s in ledger_specs("educational").items()}
    assert set(ledger_balances_at("educational", date(2023, 3, 31))) == set(books)
    with pytest.raises(ValueError):
        ledger_balances_at("educational", date(2023, 3, 30))
    with pytest.raises(ValueError):
        ledger_openings_at("educational", date(2023, 5, 1))


def test_first_voucher_units_and_stock_for_probe_15():
    from datetime import date
    from decimal import Decimal
    from v2.probes.company_b_view import COMPOUND_UNIT, HINDI_DEBTOR, first_voucher, item_specs, qty_unit, stock_qty_at
    hindi = first_voucher("educational", lambda v: not v.narration.isascii())
    assert hindi.tag == 2 and HINDI_DEBTOR in hindi.narration
    compound = next(n for n, i in item_specs("educational").items() if i.unit == COMPOUND_UNIT)
    assert compound == "A4 Paper Ream" and qty_unit("educational", compound) == "Box"
    assert stock_qty_at("educational", compound, date(2026, 3, 31)) == Decimal("20")
```

Create `v2/tests/probes/test_fake_books_company_b_masters.py`:

```python
"""Task 4: FakeBooks as a clean setup-b leaves company B, masters included, for probes 11/14/15/16B/18B."""
from datetime import date
from decimal import Decimal

import httpx

from v2.agent.tally.envelopes import formula_string, wrap_report
from v2.agent.tally.reports import parse_ledger_list
from v2.agent.tally.xml_utils import detect_error, read_objects
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import ledger_balances_at
from v2.probes.reads import exploded_tb_rows, master_request, primary_group_rows, stock_rows_any_depth
from v2.tests.probes.fake_books import FakeBooks, MALFORMED_ANSWER, seed_company_b

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


def _ask(books: FakeBooks, xml: str) -> str:
    with httpx.Client(transport=books.transport(), base_url="http://tally") as client:
        return client.post("/", content=xml.encode("utf-8")).text


def _ledgers(books, static_vars=None, name="S0P16BLedgers"):
    xml = master_request(name, "Ledger", ["Name", "Parent", "OpeningBalance", "ClosingBalance"], B,
                         static_vars=static_vars, allow_period_vars=static_vars is not None)
    return {r["name"]: r for r in parse_ledger_list(_ask(books, xml))}


def test_masters_match_the_dataset_and_the_tb_nets_to_zero():
    books = _books(opening_stock_row=True)
    state = books.state
    assert state["ledgers"]["Pune Digital Solutions"]["opening"] == "-62500.00"
    assert state["items"]["A4 Paper Ream"]["opening_qty"] == "15 Box"
    assert state["items"]["USB Cable Type-C"]["opening_value"] == "-10200.00"
    assert state["bills"]["Op/2022-001"] == {"party": "Pune Digital Solutions", "amount": "-62500.00",
                                             "opening": True, "date": "20220331"}
    rows = exploded_tb_rows(_ask(books, wrap_report("Trial Balance", "01-04-2022", "31-03-2023", B,
                                                    extra_vars={"EXPLODEFLAG": "Yes"})))
    primaries = primary_group_rows(rows)
    assert sum((r["closing_balance"] or Decimal(0)) for r in primaries.values()) == Decimal("0.00")
    assert next(r for r in rows if r["account_name"] == "Opening Stock")["closing_balance"] == Decimal("-24450.00")


def test_ledger_collection_ignores_svtodate_unless_the_knob_says_otherwise():
    now = ledger_balances_at("educational", date(2026, 3, 31))
    back = ledger_balances_at("educational", date(2023, 3, 31))
    ignored = _ledgers(_books(), {"SVTODATE": "31-03-2023"})
    assert ignored["HDFC Bank Current A/c"]["closing_balance"] == now["HDFC Bank Current A/c"]
    honoured = _ledgers(_books(ledger_svtodate_honoured=True), {"SVTODATE": "31-03-2023"})
    assert honoured["HDFC Bank Current A/c"]["closing_balance"] == back["HDFC Bank Current A/c"]


def test_opening_scope_books_or_fy():
    fy = ledger_balances_at("educational", date(2025, 3, 31))
    assert _ledgers(_books())["HDFC Bank Current A/c"]["opening_balance"] == Decimal("-868050.00")
    assert _ledgers(_books(ledger_opening_scope="fy"))["HDFC Bank Current A/c"]["opening_balance"] == \
        fy["HDFC Bank Current A/c"]
    assert _ledgers(_books(ledger_opening_scope="fy"))["Domestic Sales"]["opening_balance"] is None   # nominal: 0


def test_svfromdate_on_a_b_ledger_collection_wedges_by_default():
    books = _books()
    try:
        _ledgers(books, {"SVFROMDATE": "01-04-2024", "SVTODATE": "31-03-2025"})
    except httpx.ReadTimeout:
        pass
    else:
        raise AssertionError("expected the wedge")
    assert books.popup is True


def test_filtered_items_opening_bills_and_stock_summary():
    books = _books()
    xml = master_request("S0P11PartyBills", "Ledger", ["Name", "OpeningBalance", "BillAllocations"], B,
                         filters=[("S0P11IsParty", f"$Name = {formula_string('Pune Digital Solutions')}")])
    text = _ask(books, xml)
    assert text.count("<LEDGER ") == 1 and "<NAME>Op/2022-001</NAME>" in text and "-62500.00" in text
    items = read_objects(_ask(books, master_request("S0P15Item", "StockItem", ["Name", "BaseUnits"], B,
                         filters=[("S0P15IsItem", '$Name = "A4 Paper Ream"')])), "STOCKITEM", ["Name", "BaseUnits"])
    assert items == [{"Name": "A4 Paper Ream", "BaseUnits": "Box of 10 Nos"}]
    rows = stock_rows_any_depth(_ask(books, wrap_report("Stock Summary", "01-04-2022", "31-03-2026", B)))
    assert next(r for r in rows if r["name"] == "A4 Paper Ream")["qty"] == Decimal("20")


def test_malformed_and_unknown_company_answers():
    bad = master_request("S0P14Ledgers", "Ledger", ["Name"], B).replace(
        "Sharma &amp; Sons&apos; Probe Traders", "Sharma & Sons' Probe Traders")
    assert _ask(_books(), bad) == MALFORMED_ANSWER and detect_error(MALFORMED_ANSWER)
    assert "<LEDGER " in _ask(_books(tolerate_raw_ampersand=True), bad)
    unknown = master_request("S0P14Ledgers", "Ledger", ["Name"], B + " X")
    assert "<LEDGER " in _ask(_books(), unknown)                                  # default: SVCurrentCompany ignored
    assert detect_error(_ask(_books(honour_company_var=True), unknown))
```

- [ ] **Step 2: Run to verify they fail.** Expected: `ImportError` (`ledger_balances_at`, `MALFORMED_ANSWER`), and
  `TypeError` (`seed_company_b() got an unexpected keyword argument 'masters'`).
- [ ] **Step 3: Implement the view.** In `v2/probes/company_b_view.py`, extend the `company_b_data` import with
  `COMPOUND_UNIT, HINDI_DEBTOR, Expected, LedgerSpec, StockItemSpec, expected_figures, quantity_unit`. Add
  `from decimal import Decimal` and `from typing import Callable` (keep `Any`, `TYPE_CHECKING`). Then append:

```python
@lru_cache(maxsize=2)
def expected(licence: str) -> Expected:
    """expected_figures of the dataset: computed from the dataset alone, never from Tally (spec §4.3). C42: flagged
    vouchers move nothing; C36: skipped ones don't exist."""
    return expected_figures(dataset(licence))


def ledger_balances_at(licence: str, day: date) -> dict[str, Decimal]:
    """Every dataset ledger's balance at the close of `day`, which must be a month end inside the books. Running
    balances from the books start: right for balance-sheet ledgers; a nominal ledger's is cumulative across FYs,
    which Tally resets every April — callers compare balance-sheet ledgers only, or a period starting at books start."""
    rows = {name: value for (name, when), value in expected(licence).ledger_month_end.items() if when == day}
    if not rows:
        raise ValueError(f"{day.isoformat()} is not a month end inside company B's books")
    return rows


def ledger_openings_at(licence: str, fy_start: date) -> dict[str, Decimal]:
    """Every dataset ledger's balance at the start of the FY beginning `fy_start` (1 April); the books-start one is
    the loader's signed opening (C30)."""
    rows = {name: value for (name, when), value in expected(licence).ledger_fy_opening.items() if when == fy_start}
    if not rows:
        raise ValueError(f"{fy_start.isoformat()} is not an FY start inside company B's books")
    return rows


def ledger_specs(licence: str) -> dict[str, LedgerSpec]:
    return {spec.name: spec for spec in dataset(licence).ledgers}


def item_specs(licence: str) -> dict[str, StockItemSpec]:
    return {spec.name: spec for spec in dataset(licence).items}


def qty_unit(licence: str, item: str) -> str:
    """The unit a quantity of `item` is written and read in (C40: a compound unit's FIRST unit, e.g. "Box")."""
    return quantity_unit(dataset(licence).units, item_specs(licence)[item].unit)


def stock_qty_at(licence: str, item: str, day: date) -> Decimal:
    return expected(licence).stock_month_end[(item, day)]


def first_voucher(licence: str, wanted: Callable[[VoucherSpec], bool]) -> VoucherSpec:
    """The earliest (date, then tag) voucher the loader wrote, not flagged, that `wanted` accepts."""
    for v in sorted(dataset(licence).vouchers, key=lambda v: (v.date, v.tag)):
        if not v.skip_reason and not v.cancelled and not v.optional and wanted(v):
            return v
    raise LookupError("no such voucher in company B's dataset")
```

- [ ] **Step 4: Implement `FakeBooks`.** In `v2/tests/probes/fake_books.py`, add `stock_summary_xml` to the `fakes`
  import and add after `RESERVED_GROUP_PARENTS`:

```python
# Every Tally company's reserved groups (name -> parent, "" = primary), for probes that walk Parent to a primary group.
PRIMARY_GROUPS = ("Capital Account", "Loans (Liability)", "Current Liabilities", "Fixed Assets", "Investments",
                  "Current Assets", "Branch / Divisions", "Misc. Expenses (ASSET)", "Suspense A/c", "Sales Accounts",
                  "Purchase Accounts", "Direct Incomes", "Direct Expenses", "Indirect Incomes", "Indirect Expenses")
RESERVED_GROUPS = {**{g: "" for g in PRIMARY_GROUPS}, **RESERVED_GROUP_PARENTS, "Stock-in-Hand": "Current Assets"}
NOMINAL_PRIMARIES = frozenset({"Sales Accounts", "Purchase Accounts", "Direct Incomes", "Direct Expenses",
                               "Indirect Incomes", "Indirect Expenses"})
# Collection-name prefixes answered by the generic company-B master routes below (probes 11, 14, 15, 16 B, 18 B).
B_PROBE_COLLECTIONS = ("S0P11", "S0P14", "S0P15", "S0P16B", "S0P18B")
# The fake's answer to request XML that isn't well-formed (probe 14's deliberately unescaped `&`). The live shape is
# what probe 14 records; this is only a Tally-style LINEERROR so `detect_error` sees a failure.
MALFORMED_ANSWER = ("<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>0</STATUS></HEADER><BODY><DATA>"
                    "<LINEERROR>fake: request XML is not well-formed</LINEERROR></DATA></BODY></ENVELOPE>")
_BARE_AMP = re.compile(r"&(?!(?:amp|lt|gt|apos|quot|#\d+|#x[0-9a-fA-F]+);)")
_COMPANY_VAR = re.compile(r"<SVCurrentCompany>([^<]*)</SVCurrentCompany>")


def _amount_text(value: Decimal) -> str:
    """Tally exports a zero balance as an empty tag (probe 16 A: `empty_closing_for_zero`)."""
    return "" if value == 0 else f"{value:.2f}"


def _fy_start(yyyymmdd: str) -> str:
    year, month = int(yyyymmdd[:4]), int(yyyymmdd[4:6])
    return f"{year if month >= 4 else year - 1}0401"
```

Extend `seed_company_b`:

```python
def seed_company_b(books: "FakeBooks", licence: str = "educational", *, masters: bool = False) -> None:
    """(existing docstring) … With `masters=True` it also puts company B's masters in state the way the loader leaves
    them: custom groups, units, stock items with signed opening values (C39) in their first unit (C40), ledgers with
    signed openings (C30), the opening bill Op/2022-001, and Tally's own Profit & Loss A/c. Company A's seed ledgers
    are replaced."""
    from v2.probes.setup.company_b_data import OPENING_BILL_DATE, generate, quantity_unit
    data = generate(licence)

    def fill(state: dict) -> None:
        state["books_from"] = "20220401"
        for v in data.vouchers:
            ...                                   # the existing voucher loop, unchanged, iterating data.vouchers
        if masters:
            state["groups"] = {g.name: {"parent": g.parent} for g in data.groups}
            state["units"] = {u.name: {"base": u.first_unit, "additional": u.second_unit,
                                       "conversion": str(u.conversion) if u.conversion else None} for u in data.units}
            state["items"] = {}
            for item in data.items:
                unit = quantity_unit(data.units, item.unit)
                has = item.opening_qty is not None and item.opening_rate is not None
                state["items"][item.name] = {
                    "parent": "", "base_units": item.unit, "qty_unit": unit,
                    "opening_qty": f"{item.opening_qty} {unit}" if has else "",
                    "opening_rate": f"{item.opening_rate:.2f}/{unit}" if has else "",
                    "opening_value": f"{-(item.opening_qty * item.opening_rate):.2f}" if has else "0.00"}
            state["ledgers"] = {"Profit & Loss A/c": {"parent": "Primary", "email": "", "alter_id": 100,
                                                      "guid": f"{state['guid']}-b0000000", "opening": "0.00"}}
            for n, led in enumerate(data.ledgers, start=1):
                state["ledgers"][led.name] = {"parent": led.parent, "email": "", "alter_id": 100 + n,
                                              "guid": f"{state['guid']}-b{n:07x}",
                                              "opening": f"{led.opening:.2f}" if led.opening is not None else "0.00"}
                if led.opening_bill and led.opening is not None:
                    state.setdefault("bills", {})[led.opening_bill] = {
                        "party": led.name, "amount": f"{led.opening:.2f}", "opening": True,
                        "date": OPENING_BILL_DATE.strftime("%Y%m%d")}
    books.edit_state(fill)
```

Add the knobs to `FakeBooks.__init__` (keyword-only, stored as same-named attributes, with a one-line comment each
saying which probe measures the real behaviour):
`ledger_svtodate_honoured=False` (probe 16: the 2026-09-23 untyped evidence; the typed form is re-measured live),
`ledger_opening_scope="books"` (probe 16 B), `ledger_svfromdate_wedges=True` (LESSONS §15 rule 17),
`ledger_opening_bills_exported=True` (probe 11), `opening_stock_row=False` (LESSONS §15 rule 19; off so the loader's
existing tests keep their TB shape), `honour_company_var=False`, `tolerate_raw_ampersand=False` (probe 14).

In `_answer`, directly after the `Import Data` branch:

```python
        if "<TALLYREQUEST>Export</TALLYREQUEST>" in body:
            try:
                ET.fromstring(body)
            except ET.ParseError:
                if not self.tolerate_raw_ampersand:
                    return MALFORMED_ANSWER
                body = _BARE_AMP.sub("&amp;", body)
            company = _COMPANY_VAR.search(body)
            wanted_company = html.unescape(company.group(1)) if company else ""
            if self.honour_company_var and wanted_company and wanted_company != self.state["name"]:
                return ("<ENVELOPE><BODY><DATA><LINEERROR>Could not find Company "
                        f"'{esc(wanted_company)}'</LINEERROR></DATA></BODY></ENVELOPE>")
```

Before the final `return "<ENVELOPE></ENVELOPE>"` of `_answer` (after the Bills routes):

```python
        if "<ID>Stock Summary</ID>" in body:
            return self._stock_summary(state, period[1])
        generic = self._b_collection(state, body, period, request)
        if generic is not None:
            return generic
```

In `_trial_balance_rows`, just before the final `return`, add:
`if stock and self.opening_stock_row: rows.append(("Opening Stock", stock))`.
The row is appended to the `(name, value)` list that the `_dr_cr` mapping turns into a TB row.

In `_export_voucher`, inventory rows gain the unit **only when masters are seeded** (so part 4's byte-size tests are
unchanged):

```python
    for inv in v.get("inventory", []):
        unit = state.get("items", {}).get(inv["item"], {}).get("qty_unit", "")
        qty = inv["qty"].lstrip("-") + (f" {unit}" if unit else "")
        body += (f"<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>{esc(inv['item'])}</STOCKITEMNAME>"
                 f"<ACTUALQTY> {qty}</ACTUALQTY></ALLINVENTORYENTRIES.LIST>")
```

New methods on `FakeBooks`:

```python
    def _all_groups(self, state: dict) -> dict[str, str]:
        return {**RESERVED_GROUPS, **{n: g["parent"] for n, g in state["groups"].items()}}

    def _primary_of(self, state: dict, group: str) -> str:
        parents, seen = self._all_groups(state), []
        while parents.get(group, "") not in ("", "Primary") and group not in seen:
            seen.append(group)
            group = parents[group]
        return group

    @staticmethod
    def _ledger_balances(state: dict, *, up_to: str, before: str | None = None) -> dict[str, Decimal]:
        """Opening + unflagged lines dated ≤ up_to (and < before, when given). C42: flagged vouchers post nothing."""
        balances = {n: Decimal(l.get("opening") or "0.00") for n, l in state["ledgers"].items()}
        for v in state["vouchers"].values():
            day = _yyyymmdd(v["date"]) or v["date"]
            if _flagged(v) or day > up_to or (before is not None and day >= before):
                continue
            for line in v.get("lines", []):
                balances[line["ledger"]] = balances.get(line["ledger"], Decimal("0.00")) + Decimal(line["amount"] or "0")
        return balances

    def _b_collection(self, state: dict, body: str, period: tuple[str, str], request: httpx.Request) -> str | None:
        """Probes 11, 14, 15, 16 B, 18 B: Ledger / Group / StockItem collections, fields by NATIVEMETHOD, a
        `$Name = "…"` filter honoured. None = not one of these collections."""
        name = re.search(r"<ID>([^<]+)</ID>", body)
        if name is None or not name.group(1).startswith(B_PROBE_COLLECTIONS):
            return None
        kind = re.search(r"<COLLECTION [^>]*>\s*<TYPE>([^<]+)</TYPE>", body)
        kind = kind.group(1) if kind else ""
        fields = {f.lower() for f in re.findall(r"<NATIVEMETHOD>([^<]+)</NATIVEMETHOD>", body)}
        match = re.search(r'\$Name = "([^"]*)"', body)
        wanted = html.unescape(match.group(1)) if match else None
        if kind == "Ledger":
            if self.ledger_svfromdate_wedges and "<SVFROMDATE" in body:
                self.popup = True                     # LESSONS §15 rule 17 (measured untyped, 2026-09-23)
                raise httpx.ReadTimeout("SVFROMDATE on a master collection", request=request)
            return self._ledger_export(state, fields, period, wanted)
        if kind == "Group":
            return objects_xml("GROUP", [{"Name": n, "Parent": p} for n, p in self._all_groups(state).items()])
        if kind == "StockItem":
            return objects_xml("STOCKITEM", [
                {"Name": n, "Parent": i.get("parent", ""), "BaseUnits": i.get("base_units", ""),
                 "OpeningBalance": i.get("opening_qty", ""), "OpeningRate": i.get("opening_rate", ""),
                 "OpeningValue": i.get("opening_value", "")}
                for n, i in state["items"].items() if wanted in (None, n)])
        return "<ENVELOPE></ENVELOPE>"

    def _ledger_export(self, state: dict, fields: set[str], period: tuple[str, str], wanted: str | None) -> str:
        closing_to = period[1] if self.ledger_svtodate_honoured else self.current_period[1]
        closing = self._ledger_balances(state, up_to=closing_to)
        before_fy = self._ledger_balances(state, up_to="99991231", before=_fy_start(closing_to))
        out = []
        for name, led in state["ledgers"].items():
            if wanted is not None and name != wanted:
                continue
            if self.ledger_opening_scope == "fy":
                nominal = self._primary_of(state, led["parent"]) in NOMINAL_PRIMARIES
                opening = Decimal("0.00") if nominal else before_fy.get(name, Decimal("0.00"))
            else:
                opening = Decimal(led.get("opening") or "0.00")
            parts = [f"<NAME>{esc(name)}</NAME>"]
            if "parent" in fields:
                parts.append(f"<PARENT>{esc(led['parent'])}</PARENT>")
            if "openingbalance" in fields:
                parts.append(f"<OPENINGBALANCE>{_amount_text(opening)}</OPENINGBALANCE>")
            if "closingbalance" in fields:
                parts.append(f"<CLOSINGBALANCE>{_amount_text(closing.get(name, Decimal('0.00')))}</CLOSINGBALANCE>")
            if "billallocations" in fields and self.ledger_opening_bills_exported:
                for bill_name, bill in state.get("bills", {}).items():
                    if bill.get("opening") and bill["party"] == name:
                        parts.append(f"<BILLALLOCATIONS.LIST><NAME>{esc(bill_name)}</NAME><BILLDATE>{bill['date']}"
                                     f"</BILLDATE><OPENINGBALANCE>{bill['amount']}</OPENINGBALANCE>"
                                     "</BILLALLOCATIONS.LIST>")
            out.append(f'<LEDGER NAME="{esc(name)}">{"".join(parts)}</LEDGER>')
        return f"<ENVELOPE><BODY><DATA><COLLECTION>{''.join(out)}</COLLECTION></DATA></BODY></ENVELOPE>"

    @staticmethod
    def _stock_summary(state: dict, as_on: str) -> str:
        """Closing quantity per item as on `as_on` (the fake keeps no valuation, so values are blank)."""
        rows = []
        for name, item in state["items"].items():
            words = (item.get("opening_qty") or "").split()
            qty = Decimal(words[0]) if words else Decimal("0")
            for v in state["vouchers"].values():
                if _flagged(v) or (_yyyymmdd(v["date"]) or v["date"]) > as_on:
                    continue
                qty += sum((Decimal(i["qty"]) for i in v.get("inventory", []) if i["item"] == name), Decimal("0"))
            rows.append((name, f"{qty} {item.get('qty_unit', '')}".strip(), "", ""))
        return stock_summary_xml(rows)
```

- [ ] **Step 5: Run both new test files, then the whole suite** (also `-W error`). Expected: BASE + 23. If the
  `ET.fromstring` check turns up an existing test that sends a malformed Export, that test was already broken
  against a real Tally. Record it as a ruling. Only then restrict the check to `B_PROBE_COLLECTIONS` requests.
- [ ] **Step 6: Commit** (`v2/tests/probes/fake_books.py v2/probes/company_b_view.py
  v2/tests/probes/test_company_b_view.py v2/tests/probes/test_fake_books_company_b_masters.py`):
  `test(bi/v2): FakeBooks company-B masters + read routes; company_b_view dataset accessors`.

---

### Task 5: Probe 16's B part: OpeningBalance scope and as-on reads on company B

**Files:**
- Modify: `v2/probes/p16_ledger_closing_balance.py` (constants, pure helpers, `run_b`, `PROBE.parts`)
- Create: `v2/tests/probes/test_p16_b_part.py`

**Interfaces:**
- Consumes: Task 3's `_ledgers_request(..., name=)` / `_svfromdate_attempt(...) -> (record, rows)`. Task 4's
  `ledger_balances_at`, `ledger_openings_at`, `seed_company_b(masters=True)`, and knobs. Existing `_kinds`,
  `_balances`, `_value`, `WEDGE_SUMMARY`, `WEDGE_IMPACT`, `AS_ON_IMPACT`, `FAILED_IMPACT`.
- Produces:
  ```python
  def opening_scope(opening: dict[str, Decimal | None], books: dict[str, Decimal], fy: dict[str, Decimal]) -> dict
      # {"verdict": "books" | "fy" | "neither" | "undecided", "telling": int, "as_books": int, "as_fy": int,
      #  "mismatched": list[str]}
  def compare_closing(read: dict[str, dict], names: list[str], want: dict[str, Decimal]) -> dict
  def as_on_state(read, control, names, want) -> dict      # {"state": "works"|"ignored"|"wrong", …}
  async def run_b(ctx) -> PartResult
  ```

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p16_b_part.py`:

```python
"""Probe 16's B part: is Ledger.OpeningBalance books- or FY-scoped, and does a typed SVTODATE give as-on closings?"""
from v2.agent.tally.client import TallyClient
from v2.probes import p16_ledger_closing_balance as p16
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.probes.safety import educational_ignored_dates
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, *, allow_risky=False):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p16.PROBE, labels=["B"], client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO(), allow_risky=allow_risky)
    return store.probe_entry(16)["parts"]["B"]


async def test_b_as_on_ignored_is_different_and_the_scope_is_recorded(tmp_path):
    books = _books()
    part = await _run(tmp_path, books)
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]
    assert obs["opening_scope"]["verdict"] == "books" and obs["opening_scope"]["telling"] > 0
    assert obs["closing_now"]["mismatches"] == {}
    assert obs["as_on_2023"]["state"] == "ignored" and obs["as_on_fy2024"]["state"] == "ignored"
    assert part["fixtures"] == ["p16_B_groups.xml", "p16_B_ledgers.xml", "p16_B_ledgers_fy2024.xml",
                                "p16_B_ledgers_asof_2023-03-31.xml"]
    assert not any("<SVFROMDATE" in r for r in books.requests if "S0P16BLedgers" in r)
    assert all(educational_ignored_dates(r) == [] for r in books.requests)


async def test_b_as_on_honoured_with_books_scope_is_confirmed(tmp_path):
    part = await _run(tmp_path, _books(ledger_svtodate_honoured=True))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["as_on_2023"]["state"] == "works"
    assert "books-start opening" in part["spec_impact"] and "without probe 17" in part["spec_impact"]


async def test_b_fy_scoped_opening_is_a_finding_not_a_failure(tmp_path):
    part = await _run(tmp_path, _books(ledger_svtodate_honoured=True, ledger_opening_scope="fy"))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["opening_scope"]["verdict"] == "fy"
    assert "FY holding" in part["spec_impact"]


async def test_b_a_closing_balance_that_is_not_the_datasets_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"]["HDFC Bank Current A/c"].__setitem__("opening", "-868000.00"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "HDFC Bank Current A/c" in part["summary"]


async def test_b_an_extra_ledger_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"].__setitem__("Hand Entered Ltd", {
        "parent": "Sundry Debtors", "email": "", "alter_id": 999, "guid": "x", "opening": "0.00"}))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "Hand Entered Ltd" in part["summary"] and "setup-b" in part["summary"]


async def test_b_opt_in_svfromdate_wedge_is_failed_and_reported(tmp_path):
    part = await _run(tmp_path, _books(), allow_risky=True)
    assert part["outcome"] == "FAILED" and part["summary"] == p16.WEDGE_SUMMARY
    assert part["observations"]["as_on_svfromdate"]["wedged"] is True
```

- [ ] **Step 2: Run to verify they fail.** Expected: part BLOCKED "Probe 16 has no part 'B'" / `ValueError` from
  `run_probe`.
- [ ] **Step 3: Implement.** Add to p16's imports `from datetime import date` and
  `from v2.probes.company_b_view import (B_BOOKS_FROM_DATE, B_CURRENT_PERIOD, ledger_balances_at, ledger_openings_at,
  loaded_licence)`. Then add:

```python
B_LEDGERS = "S0P16BLedgers"
B_FY2024_START = date(2024, 4, 1)
B_FY2024_FROM, B_FY2024_TO = "01-04-2024", "31-03-2025"     # C43: days 1 and 31
B_ASON_2023 = "31-03-2023"                                    # FY 2022-23, the closed first year
SCOPE_IMPACT = {
    "books": ("Ledger OpeningBalance is the books-start opening whatever the period (R5): S1 stores it once per ledger "
              "as the books-start opening, and FY openings are computed from lines."),
    "fy": ("Ledger OpeningBalance is the opening of the FY holding the read's period (R5): a per-FY opening anchor is "
           "readable, the books-start one only with the period in the first FY."),
}
NEITHER_IMPACT = ("Ledger OpeningBalance is neither the books-start nor the FY opening: R5's opening anchor can't come "
                  "from the Ledger collection; S1 takes openings from probe 17's ledger-level TB instead.")
AS_ON_WRONG_IMPACT = ("A dated Ledger-collection read returns neither the as-on balance nor today's: the agent never "
                      "sends a period variable on a master collection (LESSONS §15 rule 17 stands), and per-ledger "
                      "anchors come from probe 17's ledger-level TB (decision 11).")
AS_ON_WORKS_IMPACT = ("A typed SVTODATE on the Ledger collection gives true as-on closing balances on company B, in a "
                      "closed year and in an older FY: per-ledger opening anchors exist during the backfill without "
                      "probe 17 (decision 11, Part 1 §16).")


def opening_scope(opening: dict[str, Decimal | None], books: dict[str, Decimal], fy: dict[str, Decimal]) -> dict:
    """Books- or FY-scoped, judged on the ledgers whose books-start and FY openings differ ("telling"); a ledger whose
    two openings agree must still match them."""
    telling = sorted(n for n in opening if books[n] != fy[n])
    as_books = [n for n in telling if _value(opening[n]) == books[n]]
    as_fy = [n for n in telling if _value(opening[n]) == fy[n]]
    same_bad = sorted(n for n in opening if books[n] == fy[n] and _value(opening[n]) != books[n])
    if not telling:
        verdict = "undecided"
    elif len(as_books) == len(telling) and not same_bad:
        verdict = "books"
    elif len(as_fy) == len(telling) and not same_bad:
        verdict = "fy"
    else:
        verdict = "neither"
    mismatched = sorted(set(telling) - set(as_books) - set(as_fy)) + same_bad
    return {"verdict": verdict, "telling": len(telling), "as_books": len(as_books), "as_fy": len(as_fy),
            "mismatched": mismatched[:10]}


def compare_closing(read: dict[str, dict], names: list[str], want: dict[str, Decimal]) -> dict:
    bad = {n: {"tally": read.get(n, {}).get("closing_balance"), "dataset": want[n]}
           for n in names if _value(read.get(n, {}).get("closing_balance")) != want[n]}
    return {"compared": len(names), "mismatches": bad}


def as_on_state(read: dict[str, dict], control: dict[str, dict], names: list[str], want: dict[str, Decimal]) -> dict:
    """works = every balance-sheet closing equals the dataset as-on; ignored = nothing moved from the control read;
    wrong = moved, but not to the as-on value."""
    mismatches = compare_closing(read, names, want)["mismatches"]
    moved = sum(1 for n in names if read.get(n, {}).get("closing_balance") != control[n]["closing_balance"])
    state = "works" if not mismatches else ("ignored" if moved == 0 else "wrong")
    return {"state": state, "compared": len(names), "moved": moved, "mismatches": dict(list(mismatches.items())[:10])}


async def _b_read(ctx: ProbeContext, step: str, to_date: str) -> dict[str, dict]:
    return _balances(await ctx.send(step, _ledgers_request(ctx.company_name, {"SVTODATE": to_date}, name=B_LEDGERS)))


async def run_b(ctx: ProbeContext) -> PartResult:
    """Spec §7 probe 16 B. The scope question is answered from the no-variable read: its period is the current FY
    (2025-26), which is not the books start (2022-23), so books- and FY-scoped openings differ on every active ledger.
    The as-on reads send a typed SVTODATE only (SVFROMDATE on a Ledger collection is opt-in, LESSONS §15 rule 17)."""
    licence = loaded_licence(ctx.store.environment)
    company = ctx.company_name
    groups = parse_parents(await ctx.send("groups", master_request("S0P16BGroups", "Group", ["Name", "Parent"], company)))
    control = _balances(await ctx.send("ledgers", _ledgers_request(company, name=B_LEDGERS)))
    if not control:
        return PartResult(Outcome.BLOCKED, "The Ledger collection came back empty — is company B open?")
    books = ledger_openings_at(licence, B_BOOKS_FROM_DATE)
    kinds = _kinds(control, groups)
    drift = sorted({n for n, k in kinds.items() if k != "special"} ^ set(books))
    if drift:
        raise ProbeBlocked(f"Company B's ledgers differ from the dataset ({', '.join(drift[:5])}) — re-run `setup-b` "
                           "verify or restore the backup before trusting this probe.")
    bs = sorted(n for n, k in kinds.items() if k == "bs")
    scope = opening_scope({n: control[n]["opening_balance"] for n in bs}, books,
                          ledger_openings_at(licence, B_CURRENT_PERIOD[0]))
    closing_now = compare_closing(control, bs, ledger_balances_at(licence, B_CURRENT_PERIOD[1]))
    fy_read = await _b_read(ctx, "ledgers_fy2024", B_FY2024_TO)
    fy2024 = as_on_state(fy_read, control, bs, ledger_balances_at(licence, dmy(B_FY2024_TO)))
    fy2024["opening_scope"] = opening_scope({n: fy_read.get(n, {}).get("opening_balance") for n in bs}, books,
                                            ledger_openings_at(licence, B_FY2024_START))
    y2023 = as_on_state(await _b_read(ctx, "ledgers_asof_2023-03-31", B_ASON_2023), control, bs,
                        ledger_balances_at(licence, dmy(B_ASON_2023)))
    ctx.observe("ledger_kinds", {k: sum(1 for v in kinds.values() if v == k) for k in ("bs", "pl", "special")})
    ctx.observe("opening_scope", scope)
    ctx.observe("closing_now", closing_now)
    ctx.observe("as_on_fy2024", fy2024)
    ctx.observe("as_on_2023", y2023)
    svfromdate, rows = await _svfromdate_attempt(ctx, "ledgers_fy2024_svfromdate",
                                                 {"SVFROMDATE": B_FY2024_FROM, "SVTODATE": B_FY2024_TO}, B_LEDGERS)
    if rows:
        svfromdate["opening_scope"] = opening_scope({n: rows.get(n, {}).get("opening_balance") for n in bs}, books,
                                                    ledger_openings_at(licence, B_FY2024_START))
    ctx.observe("as_on_svfromdate", svfromdate)
    if svfromdate.get("wedged"):
        return PartResult(Outcome.FAILED, WEDGE_SUMMARY, spec_impact=WEDGE_IMPACT)
    if closing_now["mismatches"]:
        return PartResult(Outcome.FAILED, f"ClosingBalance ≠ the dataset for {len(closing_now['mismatches'])} "
                                          f"balance-sheet ledger(s) ({', '.join(sorted(closing_now['mismatches'])[:5])})",
                          spec_impact=FAILED_IMPACT)
    reads = (("31-03-2025", fy2024), (B_ASON_2023, y2023))
    wrong = [day for day, state in reads if state["state"] == "wrong"]
    if wrong:
        return PartResult(Outcome.FAILED, f"SVTODATE {', '.join(wrong)} moved closing balances, but not to the as-on "
                                          "values", spec_impact=AS_ON_WRONG_IMPACT)
    differences, impacts = [], []
    if scope["verdict"] in ("neither", "undecided"):
        differences.append(f"OpeningBalance scope is {scope['verdict']} ({scope['mismatched'][:5]})")
        impacts.append(NEITHER_IMPACT)
    ignored = [day for day, state in reads if state["state"] == "ignored"]
    if ignored:
        differences.append(f"a typed SVTODATE ({', '.join(ignored)}) is silently ignored on the Ledger collection")
        impacts.append(AS_ON_IMPACT)
    scope_note = SCOPE_IMPACT.get(scope["verdict"], "")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join([*impacts, scope_note]))
    return PartResult(Outcome.CONFIRMED,
                      f"OpeningBalance is {scope['verdict']}-scoped ({scope['telling']} telling ledgers); a typed "
                      f"SVTODATE gives the dataset's as-on closing for all {len(bs)} balance-sheet ledgers at "
                      f"{B_FY2024_TO} and {B_ASON_2023}",
                      spec_impact=f"{scope_note} {AS_ON_WORKS_IMPACT}")
```

Set `parts={"A": run_a, "B": run_b}` in `PROBE`.

- [ ] **Step 4: Run** `test_p16_b_part.py` and `test_p16_ledger_closing_balance.py`, then the whole suite (also
  `-W error`). Expected: BASE + 29.
- [ ] **Step 5: Commit** (`v2/probes/p16_ledger_closing_balance.py v2/tests/probes/test_p16_b_part.py`):
  `feat(bi/v2): probe 16 B — OpeningBalance scope and typed as-on reads on company B`.

---

### Task 6: Probe 18's B part: TB as-on 31-03-2023 against the dataset

**Files:**
- Modify: `v2/probes/p18_historical_reports.py` (extract `compare_group_rows`, add `dataset_rollup`, `run_b`, parts)
- Create: `v2/tests/probes/test_p18_b_part.py`

**Interfaces:**
- Consumes: Task 4 (`ledger_balances_at`, masters, `opening_stock_row=True`), reads helpers.
- Produces:
  ```python
  def compare_group_rows(tb_rows: dict[str, Decimal | None], computed: dict[str, Decimal], groups: dict[str, str],
                         opening_stock: Decimal | None = None) -> dict   # tb_verdict's old body, same keys
  def dataset_rollup(ledger_parents: dict[str, str], groups: dict[str, str], balances: dict[str, Decimal]
                     ) -> tuple[dict[str, Decimal], list[str]]           # (per primary group, unknown ledgers)
  ```

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p18_b_part.py`:

```python
"""Probe 18's B part: a TB as-on a closed year's end (31-03-2023) against company B's dataset."""
from v2.agent.tally.client import TallyClient
from v2.probes import p18_historical_reports as p18
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.probes.safety import educational_ignored_dates
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **{"opening_stock_row": True, **knobs})
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p18.PROBE, labels=["B"], client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store.probe_entry(18)["parts"]["B"]


async def test_b_tb_as_on_a_closed_year_equals_the_dataset(tmp_path):
    books = _books()
    part = await _run(tmp_path, books)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    tb = part["observations"]["tb"]
    assert tb["mismatched"] == [] and tb["stock_bearing"]["Current Assets"]["reconciled"] is True
    assert part["fixtures"] == ["p18_B_tb_asof_2023-03-31.xml", "p18_B_ledger_list.xml", "p18_B_group_list.xml"]
    assert all(educational_ignored_dates(r) == [] for r in books.requests)


async def test_b_without_the_opening_stock_row_the_stock_group_does_not_reconcile(tmp_path):
    part = await _run(tmp_path, _books(opening_stock_row=False))
    assert part["outcome"] == "FAILED" and "Current Assets" in part["summary"]


async def test_b_a_lost_sale_shows_up_in_its_group(tmp_path):
    books = _books()

    def drop_first_fy22_sale(state):
        mid = next(m for m, v in state["vouchers"].items()
                   if v["vch_type"] == "Sales" and v["date"] < "20230331" and v["cancelled"] == "No"
                   and v["optional"] == "No")
        del state["vouchers"][mid]
    books.edit_state(drop_first_fy22_sale)
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "Sales Accounts" in part["summary"]


async def test_b_an_extra_ledger_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"].__setitem__("Hand Entered Ltd", {
        "parent": "Sundry Debtors", "email": "", "alter_id": 999, "guid": "x", "opening": "0.00"}))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "Hand Entered Ltd" in part["summary"]
```

- [ ] **Step 2: Run to verify they fail** (no part B).
- [ ] **Step 3: Implement.** Refactor `tb_verdict` into two functions. The A tests must stay green:

```python
def compare_group_rows(tb_rows: dict[str, Decimal | None], computed: dict[str, Decimal], groups: dict[str, str],
                       opening_stock: Decimal | None = None) -> dict:
    """Each primary group's TB row vs `computed`; the stock-bearing group reconciled against the TB's own `Opening
    Stock` row (LESSONS §15 rule 19) and reported separately."""
    stock_groups = stock_bearing_groups(groups)
    compared: dict[str, dict] = {}
    stock_side: dict[str, dict] = {}
    for group in sorted(set(tb_rows) | {g for g, v in computed.items() if v != ZERO}):
        …  # the loop body moved verbatim from tb_verdict
    mismatched = sorted(group for group, entry in compared.items() if not entry["match"])
    return {"verdict": "FAILED" if mismatched or not compared else "CONFIRMED", "groups": compared,
            "stock_bearing": stock_side, "mismatched": mismatched}


def tb_verdict(tb_rows, ledgers, groups, vouchers, as_on, opening_stock=None) -> dict:
    """(unchanged docstring)"""
    moves = ledger_movements(vouchers, up_to=as_on)
    computed: dict[str, Decimal] = {}
    for name, row in ledgers.items():
        parent = row["parent_group"]
        if parent in ("", "Primary"):
            continue
        top = top_group(parent, groups)
        computed[top] = computed.get(top, ZERO) + (row["opening_balance"] or ZERO) + moves.get(name, ZERO)
    return compare_group_rows(tb_rows, computed, groups, opening_stock)
```

Then add (imports: `ProbeBlocked` from core; `from v2.probes.company_b_view import B_BOOKS_FROM, ledger_balances_at,
loaded_licence`):

```python
B_TB_AS_ON = "31-03-2023"            # FY 2022-23's end — a closed year three FYs back; day 31 (C43)
B_TB_OK_IMPACT = ("A TB as-on a closed year's end is history on company B too — every primary group equals the "
                  "dataset, the stock-bearing one via its own `Opening Stock` row: parity has a valid anchor during "
                  "the backfill, and R30 needs no suspension (decision 11).")


def dataset_rollup(ledger_parents: dict[str, str], groups: dict[str, str],
                   balances: dict[str, Decimal]) -> tuple[dict[str, Decimal], list[str]]:
    """Per-primary-group sums of the dataset's balances, keyed by Tally's own ledger → group tree; ledgers the dataset
    doesn't know are returned, not summed (drift)."""
    computed: dict[str, Decimal] = {}
    unknown: list[str] = []
    for name, parent in ledger_parents.items():
        if parent in ("", "Primary"):
            continue
        if name not in balances:
            unknown.append(name)
            continue
        top = top_group(parent, groups)
        computed[top] = computed.get(top, ZERO) + balances[name]
    return computed, sorted(unknown)


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    company = ctx.company_name
    tb_all = exploded_tb_rows(await ctx.send(
        "tb_asof_2023-03-31", wrap_report("Trial Balance", B_BOOKS_FROM, B_TB_AS_ON, company, extra_vars=TB_EXPLODE_VARS)))
    tb_rows = {name: row["closing_balance"] for name, row in primary_group_rows(tb_all).items()}
    stock_row = opening_stock_row(tb_all)
    opening_stock = stock_row["closing_balance"] if stock_row else None
    ledger_parents = parse_parents(await ctx.send(
        "ledger_list", master_request("S0P18BLedgers", "Ledger", ["Name", "Parent"], company)), "LEDGER")
    groups = parse_parents(await ctx.send("group_list", master_request("S0P18BGroups", "Group", ["Name", "Parent"], company)))
    balances = ledger_balances_at(licence, dmy(B_TB_AS_ON))
    computed, unknown = dataset_rollup(ledger_parents, groups, balances)
    missing = sorted(set(balances) - set(ledger_parents))
    if unknown or missing:
        raise ProbeBlocked(f"Company B's ledgers differ from the dataset (unknown {unknown[:5]}, missing {missing[:5]}) "
                           "— re-run `setup-b` verify or restore the backup before trusting this probe.")
    tb = compare_group_rows(tb_rows, computed, groups, opening_stock)
    unreconciled_stock = sorted(g for g, entry in tb["stock_bearing"].items() if not entry["reconciled"])
    ctx.observe("tb", tb)
    ctx.observe("tb_opening_stock_row", {"present": stock_row is not None, "closing_balance": opening_stock,
                                         "tb_rows": len(tb_all)})
    bad = tb["mismatched"] + unreconciled_stock
    ctx.observe("sub_verdicts", {"tb": "FAILED" if bad or not tb["groups"] else "CONFIRMED"})
    if bad or not tb["groups"]:
        return PartResult(Outcome.FAILED, f"TB as-on {B_TB_AS_ON} ≠ the dataset for {', '.join(bad) or 'every group'}",
                          spec_impact=TB_IMPACT)
    return PartResult(Outcome.CONFIRMED, f"TB as-on {B_TB_AS_ON} equals the dataset for all {len(tb['groups'])} "
                                         "primary groups, and the stock-bearing group reconciles via its Opening Stock row",
                      spec_impact=B_TB_OK_IMPACT)
```

Set `parts={"A": run_a, "B": run_b}`. Module docstring: "The B part is `run_b` (plan part 5)."

- [ ] **Step 4: Run** both p18 test files, then the whole suite (also `-W error`). Expected: BASE + 33.
- [ ] **Step 5: Commit** (`v2/probes/p18_historical_reports.py v2/tests/probes/test_p18_b_part.py`):
  `feat(bi/v2): probe 18 B — TB as-on 31-03-2023 vs company B's dataset`.

---

### Task 7: Probe 11: openings (ledgers, opening bill, stock)

**Files:**
- Create: `v2/probes/p11_openings.py`, `v2/tests/probes/test_p11_openings.py`
- Modify: `v2/probes/registry.py` (`module="v2.probes.p11_openings"`), `v2/tests/probes/test_cli.py`
  (`test_run_unbuilt_probe_returns_2` uses probe **22**)

**Interfaces:**
- Consumes: Task 4's `ledger_specs`, `item_specs`, `qty_unit`, `ledger_openings_at`, `B_CURRENT_PERIOD`, and the
  `FakeBooks` knobs `ledger_opening_scope`, `ledger_opening_bills_exported`.
- Produces: `PROBE` (id 11, parts `{"B": run_b}`, `requires=(0,)`) and the pure helpers `ledger_opening_check`,
  `ledger_bills`, `bill_check`, `stock_check`. Fixtures: `p11_B_ledger_openings`, `p11_B_opening_bills`,
  `p11_B_opening_bills_report` (fallback only), `p11_B_stock_openings`.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p11_openings.py`:

```python
from v2.agent.tally.client import TallyClient
from v2.probes import p11_openings as p11
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p11.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store.probe_entry(11)["parts"]["B"]


async def test_openings_straight_from_the_masters_are_confirmed(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["ledgers"]["mismatched"] == {} and obs["opening_bill"]["candidate"]["magnitude_match"] is True
    assert obs["stock"]["A4 Paper Ream"]["qty_ok"] and obs["stock"]["USB Cable Type-C"]["value_ok"]
    assert part["fixtures"] == ["p11_B_ledger_openings.xml", "p11_B_opening_bills.xml", "p11_B_stock_openings.xml"]


async def test_opening_bill_only_in_the_report_is_different(tmp_path):
    part = await _run(tmp_path, _books(ledger_opening_bills_exported=False))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["opening_bill"]["report"]["found"] is True
    assert "p11_B_opening_bills_report.xml" in part["fixtures"]
    assert "Bills Receivable" in part["spec_impact"]


async def test_fy_scoped_ledger_openings_are_different_and_point_at_probe_16(tmp_path):
    part = await _run(tmp_path, _books(ledger_opening_scope="fy"))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]["ledgers"]
    assert obs["mismatched"] and set(obs["as_current_fy"]) == set(obs["mismatched"])
    assert "probe 16 B" in part["spec_impact"]


async def test_stock_value_exported_positive_is_different(tmp_path):
    books = _books()
    books.edit_state(lambda s: [i.__setitem__("opening_value", i["opening_value"].lstrip("-"))
                                for i in s["items"].values()])
    part = await _run(tmp_path, books)
    assert part["outcome"] == "DIFFERENT" and part["observations"]["stock"]["USB Cable Type-C"]["value_sign_flipped"]


async def test_wrong_stock_quantity_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["items"]["USB Cable Type-C"].__setitem__("opening_qty", "100 Nos"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "USB Cable Type-C" in part["summary"]


async def test_a_missing_ledger_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["ledgers"].pop("Satara Packaging Co"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "Satara Packaging Co" in part["summary"]
```

- [ ] **Step 2: Run to verify they fail** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `v2/probes/p11_openings.py`:

```python
"""Probe 11: ledger opening balances, the opening bill, and stock openings (S0 spec §7 "Probe 11", B). Feeds R5.

All three are checked against what setup-b wrote (the dataset, via company_b_view), never against another Tally read.
Ledger OpeningBalance is judged against the books-start opening; if it instead equals the current FY's opening, that
is recorded as DIFFERENT and the scope question is left to probe 16 B (S0-D7). The opening-bill candidate is the ledger
master's own BillAllocations; the fallback is Bills Receivable as-on the books start (01-04-2022, day 1, C43).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from v2.agent.tally.envelopes import formula_string, wrap_report
from v2.agent.tally.reports import parse_bills, parse_ledger_list
from v2.agent.tally.xml_utils import read_objects, sanitize_xml
from v2.probes.company_b_view import (B_BOOKS_FROM, B_CURRENT_PERIOD, item_specs, ledger_openings_at, ledger_specs,
                                      loaded_licence, qty_unit)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import ZERO, amount, master_request, qty_number

LEDGER_FIELDS = ["Name", "Parent", "OpeningBalance"]
BILL_FIELDS = ["Name", "OpeningBalance", "BillAllocations"]       # candidate: the ledger's own opening bills
STOCK_FIELDS = ["Name", "Parent", "BaseUnits", "OpeningBalance", "OpeningRate", "OpeningValue"]
OPENING_BILLS_AS_ON = B_BOOKS_FROM

CONFIRMED_IMPACT = ("S1's opening anchors (R5) come straight from the masters: Ledger OpeningBalance, the ledger's own "
                    "opening BillAllocations, and StockItem OpeningBalance / OpeningRate / OpeningValue (debit negative).")
LEDGER_FY_IMPACT = ("Ledger OpeningBalance reads as the current FY's opening, not the books-start one: R5's books-start "
                    "anchor is computed or read with the period in the first FY — probe 16 B settles the scope.")
LEDGER_FAILED_IMPACT = ("Ledger OpeningBalance doesn't export the openings setup wrote: R5's opening anchor comes from an "
                        "as-on TB at the books start (probe 18) instead of the ledger master.")
BILL_REPORT_IMPACT = ("Opening bills aren't on the ledger master's export: S1 reads them from Bills Receivable / Payable "
                      "as-on the books start (R5).")
BILL_FAILED_IMPACT = ("The opening bill can't be read over XML: S1 treats a party's opening balance as on-account (no "
                      "bill-wise ageing before the books start) (R5).")
STOCK_FAILED_IMPACT = ("Stock openings don't export setup's quantity / rate / value: stock tiles start from the first "
                       "Stock Summary snapshot, not an opening anchor (R5).")
STOCK_SIGN_IMPACT = ("StockItem OpeningValue exports positive for a debit: S1 negates it on ingest to keep debit "
                     "negative (Part 1 §6).")


def ledger_opening_check(rows: dict[str, dict], specs: dict, current_fy: dict[str, Decimal]) -> dict:
    mismatched: dict[str, dict] = {}
    as_current_fy: list[str] = []
    for name, spec in specs.items():
        got = rows[name]["opening_balance"]
        want = spec.opening if spec.opening is not None else ZERO
        if (got if got is not None else ZERO) == want:
            continue
        mismatched[name] = {"tally": got, "setup": want, "current_fy_opening": current_fy.get(name)}
        if (got if got is not None else ZERO) == current_fy.get(name):
            as_current_fy.append(name)
    return {"compared": len(specs), "mismatched": mismatched, "as_current_fy": sorted(as_current_fy)}


def ledger_bills(raw_xml: str, party: str) -> list[dict]:
    """Opening bills nested under the party's LEDGER element (BILLALLOCATIONS.LIST: NAME, BILLDATE, OPENINGBALANCE)."""
    found = []
    for ledger in ET.fromstring(sanitize_xml(raw_xml)).iter("LEDGER"):
        if (ledger.findtext("NAME") or ledger.get("NAME", "")).strip() != party:
            continue
        for bill in ledger.iter("BILLALLOCATIONS.LIST"):
            name = (bill.findtext("NAME") or "").strip()
            if name:
                found.append({"name": name, "amount": amount(bill.findtext("OPENINGBALANCE") or bill.findtext("AMOUNT")),
                              "date": (bill.findtext("BILLDATE") or "").strip()})
    return found


def bill_check(found: list[dict], name: str, want: Decimal) -> dict:
    """By magnitude: the sign is recorded, not judged (Tally files a bill by its own sign — C34)."""
    hit = next((b for b in found if b["name"] == name), None)
    value = hit["amount"] if hit else None
    return {"found": hit is not None, "amount": value, "date": hit["date"] if hit else "",
            "magnitude_match": value is not None and abs(value) == abs(want),
            "sign": None if value is None else ("negative" if value < 0 else "positive"), "bills_seen": len(found)}


def stock_check(rows: list[dict[str, str]], specs: dict, units: dict[str, str]) -> dict[str, dict]:
    by_name = {row["Name"]: row for row in rows}
    out: dict[str, dict] = {}
    for name, spec in specs.items():
        row = by_name.get(name)
        if row is None:
            out[name] = {"present": False}
            continue
        want_qty, want_rate = spec.opening_qty or ZERO, spec.opening_rate or ZERO
        want_value = -(want_qty * want_rate)
        qty = qty_number(row["OpeningBalance"]) or ZERO
        rate = amount(row["OpeningRate"].split("/")[0]) if row["OpeningRate"] else None
        value = amount(row["OpeningValue"])
        out[name] = {"present": True, "qty_text": row["OpeningBalance"], "rate_text": row["OpeningRate"],
                     "value": value, "base_units": row["BaseUnits"], "qty_unit": units[name],
                     "qty_ok": qty == want_qty, "rate_ok": (rate or ZERO) == want_rate,
                     "value_ok": (value or ZERO) == want_value,
                     "value_sign_flipped": want_value != ZERO and value == -want_value}
    return out


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    company = ctx.company_name
    specs = ledger_specs(licence)
    rows = {row["name"]: row for row in parse_ledger_list(await ctx.send(
        "ledger_openings", master_request("S0P11Ledgers", "Ledger", LEDGER_FIELDS, company)))}
    missing = sorted(set(specs) - set(rows))
    if missing:
        raise ProbeBlocked(f"Company B is missing ledger(s) {missing[:5]} the dataset has — re-run `setup-b` verify or "
                           "restore the backup before trusting this probe.")
    ledgers = ledger_opening_check(rows, specs, ledger_openings_at(licence, B_CURRENT_PERIOD[0]))
    ctx.observe("ledgers", ledgers)

    party, bill, want = next((s.name, s.opening_bill, s.opening) for s in specs.values() if s.opening_bill)
    candidate = await ctx.send("opening_bills", master_request(
        "S0P11PartyBills", "Ledger", BILL_FIELDS, company, filters=[("S0P11IsParty", f"$Name = {formula_string(party)}")]))
    opening_bill = {"party": party, "bill": bill, "expected": want,
                    "candidate": bill_check(ledger_bills(candidate, party), bill, want)}
    if not opening_bill["candidate"]["magnitude_match"]:
        report = await ctx.send("opening_bills_report", wrap_report("Bills Receivable", OPENING_BILLS_AS_ON,
                                                                    OPENING_BILLS_AS_ON, company))
        found = [{"name": b["bill_number"], "amount": b["amount"], "date": b["bill_date"]}
                 for b in parse_bills(report) if b["party_name"] == party]
        opening_bill["report"] = bill_check(found, bill, want)
    ctx.observe("opening_bill", opening_bill)

    items = read_objects(await ctx.send("stock_openings", master_request("S0P11Stock", "StockItem", STOCK_FIELDS,
                                                                         company)), "STOCKITEM", STOCK_FIELDS)
    item_names = item_specs(licence)
    stock = stock_check(items, item_names, {n: qty_unit(licence, n) for n in item_names})
    ctx.observe("stock", stock)
    absent = sorted(n for n, e in stock.items() if not e["present"])
    if absent:
        raise ProbeBlocked(f"Company B is missing stock item(s) {absent} — re-run `setup-b` verify or restore the backup.")

    failures, differences, impacts = [], [], []
    stock_bad = sorted(n for n, e in stock.items()
                       if not (e["qty_ok"] and e["rate_ok"] and (e["value_ok"] or e["value_sign_flipped"])))
    if stock_bad:
        failures.append(f"stock openings ≠ setup for {', '.join(stock_bad)}")
        impacts.append(STOCK_FAILED_IMPACT)
    if ledgers["mismatched"] and set(ledgers["as_current_fy"]) != set(ledgers["mismatched"]):
        failures.append(f"OpeningBalance ≠ setup for {', '.join(sorted(ledgers['mismatched'])[:5])}")
        impacts.append(LEDGER_FAILED_IMPACT)
    bill_ok = opening_bill["candidate"]["magnitude_match"]
    bill_in_report = opening_bill.get("report", {}).get("magnitude_match", False)
    if not bill_ok and not bill_in_report:
        failures.append(f"opening bill {bill!r} found neither on the ledger nor in Bills Receivable")
        impacts.append(BILL_FAILED_IMPACT)
    if failures:
        return PartResult(Outcome.FAILED, "; ".join(failures), spec_impact=" ".join(impacts))
    if ledgers["mismatched"]:
        differences.append(f"OpeningBalance equals the current FY's opening for {len(ledgers['mismatched'])} ledger(s)")
        impacts.append(LEDGER_FY_IMPACT)
    if not bill_ok:
        differences.append(f"opening bill {bill!r} only in Bills Receivable as-on {OPENING_BILLS_AS_ON}")
        impacts.append(BILL_REPORT_IMPACT)
    flipped = sorted(n for n, e in stock.items() if e["value_sign_flipped"] and not e["value_ok"])
    if flipped:
        differences.append(f"stock OpeningValue exported positive for {', '.join(flipped)}")
        impacts.append(STOCK_SIGN_IMPACT)
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, f"{ledgers['compared']} ledger openings, opening bill {bill!r} "
                                         f"(₹{abs(want)}) and {len(stock)} stock openings equal what setup-b wrote",
                      spec_impact=CONFIRMED_IMPACT)


PROBE = Probe(
    id=11,
    name="openings",
    question="Do ledger openings, the opening bill and stock opening qty / rate / value export as setup wrote them?",
    feeds=("R5",),
    parts={"B": run_b},
    requires=(0,),
)
```

Registry: `ProbeInfo(11, "openings", "B", "B", module="v2.probes.p11_openings")`. In `test_cli.py`, change
`test_run_unbuilt_probe_returns_2` to run probe `"22"`.

- [ ] **Step 4: Run** the new file, `test_cli.py`, and the whole suite (also `-W error`). Expected: BASE + 39.
- [ ] **Step 5: Commit** (`v2/probes/p11_openings.py v2/tests/probes/test_p11_openings.py v2/probes/registry.py
  v2/tests/probes/test_cli.py`): `feat(bi/v2): probe 11 — openings (ledgers, opening bill, stock)`.

---

### Task 8: Probe 14: `&` and `'` in the company name

**Files:**
- Create: `v2/probes/p14_special_char_company.py`, `v2/tests/probes/test_p14_special_char_company.py`
- Modify: `v2/probes/registry.py` (`module=` for 14)

**Interfaces:**
- Consumes: `ledger_specs` (Task 4), the `FakeBooks` knobs `honour_company_var` / `tolerate_raw_ampersand`,
  `MALFORMED_ANSWER`, and `FakeBooks.before_request`.
- Produces: `PROBE` (id 14, `{"B": run_b}`, `requires=(0,)`), `unescaped(xml, company)`, `shape(text, error, names)`.
  Fixtures: `p14_B_escaped_request`, `p14_B_unknown_company_request`, `p14_B_unescaped_request`.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p14_special_char_company.py`:

```python
from v2.agent.tally.client import TallyClient
from v2.probes import p14_special_char_company as p14
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p14.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    return store.probe_entry(14)["parts"]["B"]


def test_unescaped_puts_the_raw_name_back_and_nothing_else():
    xml = p14.escaped_request(B)
    raw = p14.unescaped(xml, B)
    assert "<SVCurrentCompany>Sharma & Sons' Probe Traders</SVCurrentCompany>" in raw
    assert raw.replace("Sharma & Sons' Probe Traders", "Sharma &amp; Sons&apos; Probe Traders") == xml


async def test_escaped_works_unescaped_fails_confirmed(tmp_path):
    part = await _run(tmp_path, _books(honour_company_var=True))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["escaped"]["ok"] and obs["escaped"]["has_hindi"] and not obs["unescaped"]["ok"]
    assert obs["unescaped"]["error"] and obs["unknown_company"]["ok"] is False
    assert part["fixtures"] == ["p14_B_escaped_request.xml", "p14_B_unknown_company_request.xml",
                                "p14_B_unescaped_request.xml"]


async def test_a_tally_that_ignores_the_company_variable_is_still_confirmed_with_a_gate_note(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED" and part["observations"]["unknown_company"]["ok"] is True
    assert "probe 2" in part["spec_impact"]


async def test_a_tally_that_tolerates_the_raw_ampersand_is_different(tmp_path):
    part = await _run(tmp_path, _books(honour_company_var=True, tolerate_raw_ampersand=True))
    assert part["outcome"] == "DIFFERENT" and part["observations"]["unescaped"]["ok"] is True


async def test_a_wedge_after_the_unescaped_request_blocks_with_the_popup_hint(tmp_path):
    books = _books(honour_company_var=True)

    def wedge_on_raw_name(body: str) -> None:
        if "<SVCurrentCompany>Sharma & Sons'" in body:
            books.popup = True
    books.before_request = wedge_on_raw_name
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "popup" in part["summary"].lower()
    assert part["observations"]["unescaped"]["kind"] == "timeout"
```

- [ ] **Step 2: Run to verify they fail** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `v2/probes/p14_special_char_company.py`:

```python
"""Probe 14: `&` and `'` in the company name (S0 spec §7 "Probe 14", B). Feeds R13.

Three reads of the same Ledger list: the v2 envelope (company name escaped); the same with SVCurrentCompany naming a
company that isn't loaded (control: does Tally even read the variable with one company open?); and last, a deliberately
UNESCAPED copy (raw `&` — not well-formed XML), with a short timeout, after which Tally must still answer.
"""
from __future__ import annotations

from v2.agent.tally.envelopes import esc
from v2.agent.tally.xml_utils import detect_error, read_objects
from v2.probes.company_b_view import HINDI_DEBTOR, ledger_specs, loaded_licence
from v2.probes.context import POPUP_HINT, ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import master_request

COLLECTION = "S0P14Ledgers"
UNKNOWN_SUFFIX = " (S0 probe 14 — no such company)"
UNESCAPED_TIMEOUT_S = 10.0
ESCAPED_FAILED_IMPACT = ("An escaped company name doesn't reach its company: R13's escaping is not enough, and the agent "
                         "addresses the company another way (the gate's GUID check, probe 2) before S2.")
TOLERATED_IMPACT = ("Tally accepts the raw `&` in SVCurrentCompany: escaping stays mandatory in v2 (a malformed request "
                    "is never sent), but it isn't what makes such names work (R13).")
CONFIRMED_IMPACT = ("R13 holds: the v2 envelope's escaping is what makes `Sharma & Sons' Probe Traders` reachable, and "
                    "the unescaped form fails as recorded.")
IGNORED_VAR_NOTE = ("With one company loaded Tally answered a request naming a company that isn't open: SVCurrentCompany "
                    "can't be the agent's company check — the gate's GUID read (probe 2) is.")


def escaped_request(company: str) -> str:
    return master_request(COLLECTION, "Ledger", ["Name", "Parent"], company)


def unescaped(xml: str, company: str) -> str:
    escaped = f"<SVCurrentCompany>{esc(company)}</SVCurrentCompany>"
    if escaped not in xml:
        raise ValueError("the escaped SVCurrentCompany element isn't in the request")
    return xml.replace(escaped, f"<SVCurrentCompany>{company}</SVCurrentCompany>")


def shape(text: str | None, error: dict | None, expected: set[str], raw: bytes = b"") -> dict:
    if error is not None:
        return {"ok": False, "kind": error["kind"], "message": error["message"]}
    problem = detect_error(text)
    names = [] if problem else [row["Name"] for row in read_objects(text, "LEDGER", ["Name"])]
    return {"ok": problem is None and expected <= set(names), "kind": "answered", "error": problem,
            "ledgers": len(names), "has_hindi": HINDI_DEBTOR in names, "bytes": len(raw)}


async def _read(ctx: ProbeContext, step: str, xml: str, expected: set[str], timeout: float | None = None) -> dict:
    text, error = await ctx.try_send(step, xml, timeout=timeout)
    return shape(text, error, expected, ctx.last_response.raw if ctx.last_response else b"")


async def run_b(ctx: ProbeContext) -> PartResult:
    expected = set(ledger_specs(loaded_licence(ctx.store.environment)))
    company = ctx.company_name
    xml = escaped_request(company)
    escaped = await _read(ctx, "escaped_request", xml, expected)
    unknown = await _read(ctx, "unknown_company_request", escaped_request(company + UNKNOWN_SUFFIX), expected)
    raw = await _read(ctx, "unescaped_request", unescaped(xml, company), expected, timeout=UNESCAPED_TIMEOUT_S)
    ctx.observe("escaped", escaped)
    ctx.observe("unknown_company", unknown)
    ctx.observe("unescaped", raw)
    try:
        ctx.observe("tally_after", await ctx.company_names())
    except ProbeBlocked as exc:
        raise ProbeBlocked(f"Tally stopped answering after the unescaped request ({exc}). {POPUP_HINT}") from exc
    note = f" {IGNORED_VAR_NOTE}" if unknown["ok"] else ""
    if not escaped["ok"]:
        return PartResult(Outcome.FAILED, f"The escaped request didn't return company B's ledgers ({escaped})",
                          spec_impact=ESCAPED_FAILED_IMPACT + note)
    if raw["ok"]:
        return PartResult(Outcome.DIFFERENT, "The unescaped company name worked too", spec_impact=TOLERATED_IMPACT + note)
    failure = raw.get("error") or raw.get("kind")
    return PartResult(Outcome.CONFIRMED, f"Escaped: {escaped['ledgers']} ledgers incl. the Hindi one; unescaped: "
                                         f"{failure!r}; Tally answered afterwards",
                      spec_impact=CONFIRMED_IMPACT + note)


PROBE = Probe(
    id=14,
    name="special_char_company",
    question="Does the escaped envelope reach a company named with `&` and `'`, and how does an unescaped one fail?",
    feeds=("R13",),
    parts={"B": run_b},
    requires=(0,),
)
```

(`ctx.try_send` returns the sanitized text, and `detect_error` parses it. A transport timeout comes back as
`kind == "timeout"`, and the follow-up `company_names()` then BLOCKs with the popup hint.)

- [ ] **Step 4: Run** the file and the whole suite (also `-W error`). Expected: BASE + 44.
- [ ] **Step 5: Commit** (`v2/probes/p14_special_char_company.py v2/tests/probes/test_p14_special_char_company.py
  v2/probes/registry.py`): `feat(bi/v2): probe 14 — special characters in the company name`.

---

### Task 9: Probe 15: Hindi text and a compound-unit item

**Files:**
- Create: `v2/probes/p15_unicode_compound_units.py`, `v2/tests/probes/test_p15_unicode_compound_units.py`
- Modify: `v2/probes/registry.py` (`module=` for 15)

**Interfaces:**
- Consumes: probe 5's confirmed `voucher_month` template (S0-D7, `requires=(0, 5)`), `fetch_window`,
  `drift_message`, `tag_of`, and Task 4's `first_voucher`, `item_specs`, `stock_qty_at`, `HINDI_DEBTOR`,
  `COMPOUND_UNIT`.
- Produces: `PROBE` (id 15), the pure `text_check(parsed: str | None, expected: str, raw: bytes) -> dict`.
  Fixtures: `p15_B_hindi_ledger`, `p15_B_hindi_narration`, `p15_B_compound_unit_item`, `p15_B_compound_unit_voucher`,
  `p15_B_stock_summary`.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p15_unicode_compound_units.py`:

```python
from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p15_unicode_compound_units as p15
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import HINDI_DEBTOR
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books() -> FakeBooks:
    books = FakeBooks(name=B, educational=True)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    await run_probe(p15.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(15)["parts"]["B"]


async def test_hindi_and_compound_units_round_trip(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["hindi_ledger"]["exact"] and obs["hindi_narration"]["exact"] and obs["hindi_narration"]["tag"] == 2
    assert obs["compound_item"]["base_units"] == "Box of 10 Nos"
    assert obs["compound_voucher"]["qty_ok"] and obs["compound_voucher"]["tag"] != 2
    assert obs["stock_summary"]["qty_ok"] and obs["tally_after"] == [B]
    assert part["fixtures"][-5:] == ["p15_B_hindi_ledger.xml", "p15_B_hindi_narration.xml",
                                     "p15_B_compound_unit_item.xml", "p15_B_compound_unit_voucher.xml",
                                     "p15_B_stock_summary.xml"]


def test_hindi_sent_as_character_references_is_still_exact():
    refs = "".join(f"&#{ord(c)};" for c in HINDI_DEBTOR).encode("ascii")
    check = p15.text_check(HINDI_DEBTOR, HINDI_DEBTOR, b"<NAME>" + refs + b"</NAME>")
    assert check == {"exact": True, "utf8_bytes_in_raw": False, "encoding": "character references"}


def test_mangled_hindi_is_not_exact():
    assert p15.text_check("?????", HINDI_DEBTOR, b"?????")["exact"] is False


async def test_without_probe_5_the_part_blocks(tmp_path):
    part = await _run(tmp_path, _books(), with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "5" in part["summary"]


async def test_a_compound_quantity_that_reads_back_wrong_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["items"]["A4 Paper Ream"].__setitem__("opening_qty", "150 Box"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "stock summary" in part["summary"]
```

- [ ] **Step 2: Run to verify they fail** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `v2/probes/p15_unicode_compound_units.py`:

```python
"""Probe 15: Hindi text and a compound-unit stock item (S0 spec §7 "Probe 15", B). Feeds R14, R15.

"Byte-exact" is judged on the PARSED text (code-point equality with the dataset); whether the raw response carried
the Hindi as UTF-8 bytes or as numeric character references is recorded, not judged — both parse to the same text.
Vouchers are fetched with probe 5's confirmed month request as one-day windows (S0-D7); dataset dates sit on days
1/2/31, so no C43 clamp is needed. The Stock Summary is read at the books' end (31-03-2026): it asks for the current
position, not an as-on one (that question is probe 18's).
"""
from __future__ import annotations

from v2.agent.tally.envelopes import formula_string, wrap_report
from v2.agent.tally.xml_utils import read_objects
from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_TO, COMPOUND_UNIT, HINDI_DEBTOR, drift_message,
                                      fetch_window, first_voucher, item_specs, loaded_licence, stock_qty_at, tag_of)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import dmy, master_request, parse_vouchers, qty_number, stock_rows_any_depth

LEDGER_FIELDS = ["Name", "Parent"]
ITEM_FIELDS = ["Name", "Parent", "BaseUnits", "OpeningBalance"]
OK_IMPACT = ("Hindi names and narrations round-trip exactly through the XML export and a compound-unit item's "
             "quantities read back in its first unit (C40): S1 stores text as UTF-8 unchanged and parses quantities by "
             "their leading number (R14, R15).")
TEXT_FAILED_IMPACT = ("Hindi text doesn't round-trip exactly: S1's text columns and the agent's parser are revisited "
                      "before S1 (R14).")
QTY_FAILED_IMPACT = ("A compound-unit quantity doesn't read back as written: the agent can't take compound quantities by "
                     "their leading number; S1 stores the raw quantity text and R15 is revisited.")
UNIT_IMPACT = ("The compound unit's name doesn't export as created ('Box of 10 Nos'): S1 stores units by the exported "
               "string and never re-derives it (R15).")


def text_check(parsed: str | None, expected: str, raw: bytes) -> dict:
    in_raw = expected.encode("utf-8") in raw
    return {"exact": parsed == expected, "utf8_bytes_in_raw": in_raw,
            "encoding": "utf-8 bytes" if in_raw else "character references"}


async def _one_voucher(ctx: ProbeContext, step: str, template: str, licence: str, spec) -> dict:
    day = spec.date.strftime("%d-%m-%Y")
    result, raw = await fetch_window(ctx, step, template, licence, day, day)
    if result["drifted"]:
        raise ProbeBlocked(drift_message(step, result))
    found = [v for v in parse_vouchers(raw) if tag_of(v["header"].get("NARRATION", "")) == spec.tag]
    if not found:
        raise ProbeBlocked(f"{step}: probe 5's request returned no voucher tagged {spec.tag} on {day} — company B "
                           "differs from the dataset, or the request stopped bounding a day (re-run probe 5).")
    return found[0]


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    confirmed = ctx.store.confirmed("voucher_month")
    if confirmed is None:
        raise ProbeBlocked("No confirmed month request: run probe 5 first.")
    template, company = confirmed["xml_template"], ctx.company_name
    compound = next(name for name, spec in item_specs(licence).items() if spec.unit == COMPOUND_UNIT)

    text = await ctx.send("hindi_ledger", master_request("S0P15Ledger", "Ledger", LEDGER_FIELDS, company, filters=[
        ("S0P15IsHindi", f"$Name = {formula_string(HINDI_DEBTOR)}")]))
    names = [row["Name"] for row in read_objects(text, "LEDGER", LEDGER_FIELDS)]
    hindi_ledger = {"names": names, **text_check(names[0] if len(names) == 1 else None, HINDI_DEBTOR,
                                                 ctx.last_response.raw)}

    hindi_spec = first_voucher(licence, lambda v: not v.narration.isascii())
    got = await _one_voucher(ctx, "hindi_narration", template, licence, hindi_spec)
    hindi_narration = {"tag": hindi_spec.tag, "got": got["header"].get("NARRATION"),
                       **text_check(got["header"].get("NARRATION"), hindi_spec.narration, ctx.last_response.raw)}

    item_rows = read_objects(await ctx.send("compound_unit_item", master_request(
        "S0P15Item", "StockItem", ITEM_FIELDS, company, filters=[("S0P15IsItem", f"$Name = {formula_string(compound)}")])),
        "STOCKITEM", ITEM_FIELDS)
    base_units = item_rows[0]["BaseUnits"] if item_rows else None
    compound_item = {"name": compound, "base_units": base_units, "expected": COMPOUND_UNIT,
                     "opening_text": item_rows[0]["OpeningBalance"] if item_rows else None,
                     "unit_exact": base_units == COMPOUND_UNIT}

    unit_spec = first_voucher(licence, lambda v: v.tag != hindi_spec.tag and any(i.item == compound for i in v.inventory))
    want = next(i.qty for i in unit_spec.inventory if i.item == compound)
    voucher = await _one_voucher(ctx, "compound_unit_voucher", template, licence, unit_spec)
    line = next((inv["fields"] for inv in voucher["inventory"] if inv["fields"].get("STOCKITEMNAME") == compound), {})
    read_qty = qty_number(line.get("ACTUALQTY", ""))
    compound_voucher = {"tag": unit_spec.tag, "actual_qty_text": line.get("ACTUALQTY"),
                        "billed_qty_text": line.get("BILLEDQTY"), "rate_text": line.get("RATE"), "expected_qty": want,
                        "qty_ok": read_qty is not None and abs(read_qty) == want}

    rows = stock_rows_any_depth(await ctx.send("stock_summary", wrap_report("Stock Summary", B_BOOKS_FROM, B_BOOKS_TO,
                                                                            company)))
    row = next((r for r in rows if r["name"] == compound), None)
    want_stock = stock_qty_at(licence, compound, dmy(B_BOOKS_TO))
    stock_summary = {"qty_text": row["qty_text"] if row else None, "expected_qty": want_stock,
                     "qty_ok": row is not None and row["qty"] == want_stock}

    for key, value in (("hindi_ledger", hindi_ledger), ("hindi_narration", hindi_narration),
                       ("compound_item", compound_item), ("compound_voucher", compound_voucher),
                       ("stock_summary", stock_summary)):
        ctx.observe(key, value)
    ctx.observe("tally_after", await ctx.company_names())       # "no crash, Tally answers a cheap read after"

    if not (hindi_ledger["exact"] and hindi_narration["exact"]):
        return PartResult(Outcome.FAILED, f"Hindi text isn't exact (ledger {hindi_ledger['names']}, narration "
                                          f"{hindi_narration['got']!r})", spec_impact=TEXT_FAILED_IMPACT)
    bad_qty = [what for what, ok in (("voucher", compound_voucher["qty_ok"]), ("stock summary", stock_summary["qty_ok"]))
               if not ok]
    if bad_qty:
        return PartResult(Outcome.FAILED, f"{compound} quantity reads back wrong in the {' and '.join(bad_qty)}",
                          spec_impact=QTY_FAILED_IMPACT)
    if not compound_item["unit_exact"]:
        return PartResult(Outcome.DIFFERENT, f"{compound}'s unit exports as {base_units!r}, not {COMPOUND_UNIT!r}",
                          spec_impact=UNIT_IMPACT)
    return PartResult(Outcome.CONFIRMED, f"Hindi ledger and narration (tag {hindi_spec.tag}) exact "
                                         f"({hindi_ledger['encoding']}); {compound} ({COMPOUND_UNIT}) reads "
                                         f"{compound_voucher['actual_qty_text']!r} on tag {unit_spec.tag} and "
                                         f"{stock_summary['qty_text']!r} in the Stock Summary; Tally answered after",
                      spec_impact=OK_IMPACT)


PROBE = Probe(
    id=15,
    name="unicode_compound_units",
    question="Do Hindi names/narrations and a compound-unit item round-trip exactly, without upsetting Tally?",
    feeds=("R14", "R15"),
    parts={"B": run_b},
    requires=(0, 5),
)
```

- [ ] **Step 4: Run** the file and the whole suite (also `-W error`). Expected: BASE + 49 (±, per the pre-flight
  count). Then run `git status --porcelain | grep -v -E '^\?\? ' | grep -v -E ' (v2/|docs/)'`. Expected: empty.
- [ ] **Step 5: Commit** (`v2/probes/p15_unicode_compound_units.py v2/tests/probes/test_p15_unicode_compound_units.py
  v2/probes/registry.py`): `feat(bi/v2): probe 15 — Hindi text and compound units`.

---

### Task 9b: Code review (before any live run)

**Files:** Create `docs/code-review-bi-s0-part5-<YYYY-MM-DD>.md`.

- [ ] **Step 1:** Run the `superpowers:requesting-code-review` skill (or the `code-review` agent) on
  `git diff 08b2597..HEAD -- v2/`. Excluding `v2/probes/operator/` is fine, since that is not this plan's work. Ask the
  reviewer to check at least:
  - the date audit table against every constant in 16/17/18. The C43 guard must cover `_post_uncaptured` too, and must
    not break placeholders or probe 0 (no licence yet).
  - that the snapshot is byte-identical and every "live 2026-09-23" test reads it.
  - p16 B: the drift check is symmetric; `opening_scope` "undecided" can't be CONFIRMED; the opt-in SVFROMDATE stays
    last.
  - p18 B: stricter stock-bearing rule vs A's.
  - p11's magnitude-only bill rule. p14's step order (unescaped last, short timeout). p15's text rule vs spec's
    "byte-exact".
  - that the FakeBooks knobs' defaults model the **recorded** live behaviour, not the hoped-for one.
  - isolation: only `company_b_view` reaches `company_b_data`, and nothing is staged from `v2/probes/operator/`.
  - the Review Focus items.
- [ ] **Step 2:** Store the findings. Fix the confirmed ones test-first. Re-run the suite (with and without `-W error`)
  and record the count. The doc lists the suites **not** run: live Tally (Tasks 10a/10b), tier-C timing (⏭ Q29), the
  root `tests/` suite (it doesn't collect `v2/`).
- [ ] **Step 3: CLI smoke (no Tally needed).**
  ```bash
  mkdir -p /tmp/s0-smoke-p5
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p5/results.json list | grep -E '^ ?(11|14|15|16|18) '
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p5/results.json run 22; echo "exit=$?"
  ```
  Expected: 11/14/15 listed `not run`, 16/18 companies `A+B`; `run 22` prints "not built yet", `exit=2`.
- [ ] **Step 4: Commit** the review doc and fixes (only the files named), plus a tracker change-log row with the
  review path.

---

### Task 10a: Live session 1, company A: anchors, then 16, 17, 18 A re-runs (operator at the Mac)

**Files (written by the runner, then committed):** `v2/probes/results/results.json`, `v2/tests/fixtures/sync/p16_A_*`,
`p17_A_*`, `p18_A_*`, `docs/bi-s0-probe-results-<date>.md` (generated). Logs go to `logs/`.

Probes 17 and 18 only read. Probe 16 A **writes** two throwaway vouchers (future-dated, then post-dated) and deletes
each one (spec §7). Manual mode: the person makes them in the Tally UI when the pause asks. Auto mode: only after
step 3 passes.

- [ ] **Step 1: Pre-flight (read-only).**
  ```bash
  cd "/Users/nuvanta-mac-3/work/Tally prime"
  git log --oneline -3 -- v2/probes/operator/tally_control.py; git status --short -- v2/probes/operator/
  grep -in '^[[:space:]]*load[[:space:]]*=' "$HOME/.wine/drive_c/Program Files/TallyPrimeEditLog/tally.ini"
  grep -n '"licence"\|"company_b_loaded_at"' v2/probes/results/results.json | head
  python3 -c "import json;d=json.load(open('v2/probes/results/results.json'));print(sorted(d['environment']['company_a_tb_baseline']))"
  ps -axo pid,command | grep -i 'tally.exe' | grep -v grep
  curl -s --max-time 3 http://localhost:9000
  ls -d seed_data/100003 ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe-backups/100000-company-B-loaded-2026-09-24
  ```
  Expected:
  - `licence` is `educational`, and the TB baseline has its group keys.
  - There is exactly one `tally.exe`, with `s0probe` in its command line, and the server answers.
  - Both backups exist: `seed_data/100003` is company A's pristine source for `reset-a`, and the `100000-…` folder is
    company B's.
  - Record the `Load=` value, because it decides the next step.
- [ ] **Step 2: Put company A (only) on screen.** In the TallyPrime window: if company B is open, shut it (Company →
  Shut, or `Ctrl+F3`) and select `Bharat Traders Probe Copy` (F3). **Don't restart Tally to do this.** If Tally isn't
  running at all, starting it is safe for A only when the step-1 `Load=` is `100003` (or C44 is verified in step 3). A
  `Load=100000` start opens B as well.
- [ ] **Step 3 (only if you want `--auto` for probe 16's throwaways): verify C44 live.** This needs the licence box
  clicked twice ("CLICK NEEDED").
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/c44-verify-$(date +%F).log
  from v2.probes.companies import COMPANIES
  from v2.probes.operator.auto import build_auto_operator
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      print("B ->", auto.control.restart("B", [COMPANIES["B"]]))
      print("A ->", auto.control.restart("A", [COMPANIES["A"]]))
  finally:
      auto.close()
  EOF
  grep -in '^[[:space:]]*load[[:space:]]*=' "$HOME/.wine/drive_c/Program Files/TallyPrimeEditLog/tally.ini"
  ```
  Expected: `B -> ["Sharma & Sons' Probe Traders"]`, then `A -> ['Bharat Traders Probe Copy']`, with `Load=100003`
  at the end. **Any** "Tally has [...] open, not [...]" means C44 is not working live. Record that in the tracker
  (C44 row) and use manual mode for the rest of this plan. Skip this step entirely to stay manual.
- [ ] **Step 4: Anchors before parity** (spec §4.2):
  `uv run --project v2 python -m v2.probes anchors 2>&1 | tee logs/s0-p5-anchors-before-$(date +%F).log`.
  Expected: `anchors check (before_parity) company A: OK`. If FAILED: company A has drifted. Run
  `uv run --project v2 python -m v2.probes reset-a --stop-any-tally 2>&1 | tee logs/reset-a-$(date +%F).log`
  (it restarts Tally with `/LOAD:100003`, which is safe per step 2's `Load=` rule; click the licence box), then rerun
  anchors. Probe 1's recorded LastVoucherDate baseline stays valid after `reset-a`, because it is the same seed.
- [ ] **Step 5: Probe 16 A** (throwaway vouchers, UI balances asked, **no `--allow-risky`**):
  ```bash
  uv run --project v2 python -m v2.probes run 16 --company A 2>&1 | tee logs/p16A-rerun-typed-$(date +%F).log
  # or, only if step 3 passed:  … run 16 --company A --auto
  ```
  Manual: create each voucher exactly as the pause says (31-Mar-2026, Cash → Electricity, ₹1, the given narration;
  the second one post-dated with Ctrl+T), then delete it when asked. At the UI-balance asks, type the balance Tally
  shows or press Enter to skip. Read the result: `observations.as_on.closing_follows_svtodate`. `true` means **a typed
  SVTODATE IS honoured on a Ledger collection**. That overturns tracker decision 11's "impossible" and LESSONS rule
  17's SVTODATE half. `false` confirms that half for the typed form. Either way it's a finding: record it, and don't
  re-run to change it.
- [ ] **Step 6: Probe 17 A:**
  `uv run --project v2 python -m v2.probes run 17 --company A 2>&1 | tee logs/p17A-rerun-typed-$(date +%F).log`.
  Expected: CONFIRMED on `isledgerwise`, and `results.json` `confirmed_requests.ledger_level_tb.xml_template` now
  contains `TYPE="Date"`.
- [ ] **Step 7: Probe 18 A:**
  `uv run --project v2 python -m v2.probes run 18 --company A 2>&1 | tee logs/p18A-rerun-typed-$(date +%F).log`.
  Read `sub_verdicts.bills_stock` and each `bills.*.match` / `stock.verdict`. Matching the as-on 31-10-2025
  position means **the 2026-09-23 "Bills/Stock ignore the date" was a C43 artifact**, and LESSONS rule 20's second
  half is overturned. Still matching the full period means the finding stands, now on a valid day and typed.
- [ ] **Step 8: Anchors after the A batch:**
  `uv run --project v2 python -m v2.probes anchors --when after_a_batch 2>&1 | tee logs/s0-p5-anchors-after-$(date +%F).log`.
  Expected OK. A FAILED here means probe 16's throwaway cleanup failed: follow its "CLEANUP NEEDED" notes, then
  rerun anchors.
- [ ] **Step 9 (OPTIONAL — only with the user's explicit go-ahead in this session): re-measure SVFROMDATE on a Ledger
  collection, typed.** Justification: rule 17's "SVFROMDATE freezes Tally" was measured untyped. The design doesn't
  need it, because an as-on closing via SVTODATE (step 5) is the anchor route. So this only refines a LESSONS rule, at
  the cost of a likely Tally wedge. Protocol:
  1. Company A only is open, and anchors are OK.
  2. `uv run --project v2 python -m v2.probes run 16 --company A --allow-risky 2>&1 | tee logs/p16A-risky-typed-$(date +%F).log`.
     This repeats the throwaways. SVFROMDATE is sent **last**, with a 20 s timeout.
  3. If the part reports `WEDGE_SUMMARY`: quit Tally from the Mac. Use the operator (`auto.control.stop()` via the
     step-3 snippet), or `kill` the `tally.exe` PID from step 1's `ps`. Restart Tally with A only and click the
     licence box. Nothing was written by the read, so company A needs no reset.
  4. Rerun anchors. The previous clean 16 A result moves to `history` automatically, and both runs are cited in the
     tracker.
  If the user doesn't approve, record "typed SVFROMDATE-on-master not re-measured (risk > value); guard stays" in the
  tracker and in LESSONS rule 17.
- [ ] **Step 10: List, report, commit the evidence.**
  ```bash
  uv run --project v2 python -m v2.probes list | grep -E '^ ?(16|17|18) '
  uv run --project v2 python -m v2.probes report
  git diff --stat v2/probes/results/results.json     # only probes 16/17/18, anchor_checks, confirmed_requests.ledger_level_tb, run_mode
  git add v2/probes/results/results.json v2/tests/fixtures/sync/p16_A_* v2/tests/fixtures/sync/p17_A_* \
          v2/tests/fixtures/sync/p18_A_* docs/bi-s0-probe-results-$(date +%F).md
  git commit -m "data(bi/v2): probes 16/17/18 A re-run with typed, C43-valid dates (company A)" \
             -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
  ```
  (`git add` on `p1[678]_A_*` also stages any new step names, e.g. `p18_A_vouchers_fy.xml`. The old
  `p18_A_*_2025-09-30.*` and `p18_A_vouchers_to_2025-10-31.*` flat files are now stale duplicates of the snapshot:
  `git rm` them in the same commit, and say so in the message.)

---

### Task 10b: Live session 2, company B: 16 B, 18 B, 11, 14, 15 (operator at the Mac)

**Files (runner-written, then committed):** `results.json`, `v2/tests/fixtures/sync/p16_B_*`, `p18_B_*`, `p11_B_*`,
`p14_B_*`, `p15_B_*`, and the regenerated results doc. None of these probes writes to Tally.

- [ ] **Step 1: Pre-flight (read-only):** same commands as Task 10a step 1. Also confirm the company-B backup folder
  exists (`…/s0probe-backups/100000-company-B-loaded-2026-09-24`) and that `results.json` has
  `environment.company_b_loaded_at` and `confirmed_requests.voucher_month` (probe 15 needs it).
- [ ] **Step 2: Switch to company B only.** In the UI: shut `Bharat Traders Probe Copy`, then select
  `Sharma & Sons' Probe Traders` (100000). If step 10a.3 passed, `auto.control.restart("B", [COMPANIES["B"]])` may do
  it instead. **Never** start Tally with a `Load=100003` ini and `/LOAD:100000` by hand (tracker 0a: both open).
- [ ] **Step 3: Run, in spec §6 batch-5 order, one probe per log:**
  ```bash
  uv run --project v2 python -m v2.probes run 16 --company B 2>&1 | tee logs/p16B-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 18 --company B 2>&1 | tee logs/p18B-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 11 2>&1 | tee logs/p11-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 15 2>&1 | tee logs/p15-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 14 2>&1 | tee logs/p14-live-$(date +%F).log
  ```
  Probe 14 runs **last** because it sends malformed XML on purpose. If it BLOCKs with the popup hint, dismiss the
  Tally popup (or restart Tally with B only) before anything else. A BLOCKED "Company B … differs from the dataset" on
  any of them means drift. Stop, and restore the backup (stop Tally, copy the backup folder back into `s0probe/100000`,
  restart with B only). **Don't** re-run to "get CONFIRMED". DIFFERENT and FAILED are findings: record them.
- [ ] **Step 4: Read the numbers out** (for the tracker and spec):
  ```bash
  uv run --project v2 python -c "import json; p=json.load(open('v2/probes/results/results.json'))['probes']; \
  [print(k, p[k]['parts']['B']['outcome'], '—', p[k]['parts']['B']['summary']) for k in ('16','18','11','14','15')]; \
  print(json.dumps({k:p['16']['parts']['B']['observations'][k] for k in ('opening_scope','as_on_fy2024','as_on_2023')}, indent=1, ensure_ascii=False, default=str))" \
  2>&1 | tee logs/s0-p5-b-numbers-$(date +%F).log
  ```
- [ ] **Step 5: List, report, commit the evidence** (as in 10a step 10, with B fixture globs; the message
  `data(bi/v2): probes 16/18 B, 11, 14, 15 live on company B`).

---

### Task 11: Spec, tracker, roadmap, LESSONS and Part 1 spec updates (same session as the live tasks)

**Files:** `docs/specs/2026-09-22-bi-s0-probes-design.md`, `docs/specs/2026-09-21-bi-part1-sync-design.md`,
`docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md`, `LESSONS.md`, and this plan (tick the boxes).

- [ ] **Step 1: S0 spec.** Add a header line `**Changed <date> (plan part 5):**` covering:
  (a) §7 probe 18 A: bills/stock as-on moved 30-09-2025 → 31-10-2025 (C43); vouchers read for the whole FY (C33).
  (b) §7 probe 16 B as built: scope decided from the current-period read; typed SVTODATE-only as-on reads; SVFROMDATE
  opt-in.
  (c) §7 probe 18 B: the stock-bearing group must reconcile via its Opening Stock row.
  (d) probes 11/14/15 as built (the candidate bill field; the unknown-company control; parsed-text exactness).
  (e) §4.5 gains the C43 send-time guard.
  (f) §11.5 rows: 11 + `opening_bills_report`; 14 + `unknown_company_request`; 16 B `B_groups`, `B_ledgers`,
  `B_ledgers_fy2024`, `B_ledgers_asof_2023-03-31` (+ opt-in `B_ledgers_fy2024_svfromdate`); 18 A
  `A_bills_*_asof_2025-10-31`, `A_stock_summary_asof_2025-10-31`, `A_vouchers_fy`; 18 B + `B_ledger_list`,
  `B_group_list`.
  (g) Every superseded 2026-09-23 conclusion, named as superseded (not deleted), with where its evidence now lives
  (`v2/tests/fixtures/sync/c33_untyped_2026-09-23/`).
  Update the header status line.
- [ ] **Step 2: Tracker.**
  - Rows 16, 17, 18: the re-run outcome and proof (summary, fixtures, `results.json` keys, logs). Put the old result
    in the row as "superseded (untyped, C33 / C43)". Rows 16 and 18 become ✅ when both parts are run.
  - Rows 11, 14, 15: ✅ with proof, or the real outcome.
  - §1 decision 11: rewrite the S0 sentence from the new 16/17/18 results.
  - §0 S0 row: part 5 done.
  - Plan part 6 is next (B parts of 3/23/25, then company C / probe 24). Record C44's live status from Task 10a
    step 3.
  - Rewrite "Resume here" to the state actually left behind.
  - Add a dated change-log row with every contradicted expectation.
- [ ] **Step 3: LESSONS.md §15.** Rule 17: qualify it by what step 5 (and optional step 9) showed about the *typed*
  forms. Rule 20: keep the TB half. The Bills/Stock half is either overturned ("was C43: 30-09-2025 is an ignored day")
  or re-confirmed on a valid day. Rule 22: add that the v2 probes now refuse off-day dates at send time. Keep each
  rule's scope caveat.
- [ ] **Step 4: Part 1 spec.** One dated "Changed" line. Decision 11 / §6 rung 1 / §16: the per-ledger opening anchor
  route per probes 16 A/B. R30: probe 18 B. R5: probe 11. R13: probe 14. R14/R15: probe 15.
- [ ] **Step 5: Roadmap.** Set C S0 row: one line — part 5 done, and what remains (part 6: 3/23/25 B, company C).
- [ ] **Step 6: Commit** docs only: `docs(bi/v2): plan part 5 results into specs, tracker, LESSONS, roadmap`.

---

## Self-review (done while writing)

- **Spec coverage (requirement → task):**
  - §7 probe 16 A (re-measure as-on under typed dates) → T3 (text + seams) + T10a step 5. Opt-in SVFROMDATE →
    T10a step 9 (gated).
  - Probe 16 B (scope FY vs books, period inside FY 2024-25, as-on 31-03-2023) → T5 + T10b.
  - Probe 17 (typed confirmation) → T3 pin + T10a step 6.
  - Probe 18 A (TB 31-10-2025; bills/stock as-on on a C43-valid day) → T3 + T10a step 7. Probe 18 B (TB 31-03-2023 vs
    dataset) → T6 + T10b.
  - Probe 11 (ledger openings, the opening bill via a candidate else Bills Receivable at books start, stock opening
    qty/rate/value) → T7. Probe 14 (escaped works, unescaped fails, error shape) → T8. Probe 15 (Hindi ledger,
    Hindi narration, compound item, voucher, Stock Summary, cheap read after) → T9.
  - §4.2 anchors before/after the parity probes → T2 (`anchors` command) + T10a steps 4 and 8.
  - §4.5 guards (+C43) → T2. §4.6 Educational tag → the existing `educational_sensitive` on 16/18; 11/14/15 aren't
    date-sensitive. §5.7 history on re-run → the existing `record_part` + T1 snapshot. §6 batch order → T10a/T10b
    ordering (14 last within B for safety — Ambiguity 12).
  - §10 exit-gate items 3 (16/17/18 into Part 1 §6/§16) → T11 step 4. Item 6 (isolation) → T9 step 4 + T9b.
    Item 7 (code review) → T9b.
- **Placeholders:** no TBD. `<date>`, `<YYYY-MM-DD>` and `08b2597..HEAD` are run-time values. The "(±, per the
  pre-flight count)" test totals are advisory, as in part 4's Ruling P2.
- **Names used across tasks (checked):** `check_educational_dates`, `educational_ignored_dates`,
  `EDUCATIONAL_DATE_VAR_DAYS` (T2 → T3, T5, T6); `_ledgers_request(..., name=)`, `_svfromdate_attempt → (record, rows)`
  (T3 → T5); `ledger_balances_at`, `ledger_openings_at`, `ledger_specs`, `item_specs`, `qty_unit`, `stock_qty_at`,
  `first_voucher`, `HINDI_DEBTOR`, `COMPOUND_UNIT` (T4 → T5–T9); `seed_company_b(masters=True)`, the knobs,
  `MALFORMED_ANSWER`, `B_PROBE_COLLECTIONS` (T4 → T5–T9); collection names `S0P16BLedgers`, `S0P16BGroups`,
  `S0P18BLedgers`, `S0P18BGroups`, `S0P11Ledgers`, `S0P11PartyBills`, `S0P11Stock`, `S0P14Ledgers`, `S0P15Ledger`,
  `S0P15Item` all start with a `B_PROBE_COLLECTIONS` prefix; `compare_group_rows`, `dataset_rollup` (T6).
- **Review Focus → tests:** 1 → T2/T3; 2 → T1; 3 → T5/T6/T7; 4 → T8; 5 → T9.

## Ambiguities in the spec, and how this plan resolves them

1. **"Re-run" the B parts of 16 and 18, though they were never built.** Both modules have only `run_a`. **Resolution:**
   build them (Tasks 5, 6). Their first live run is the B measurement. "Re-run" applies to the A parts only.
2. **Probe 18 A's as-on 30-09-2025 is a day Educational Tally ignores (C43).** **Resolution:** move bills/stock to
   31-10-2025 (the TB's date). It is honoured under both licences and still splits company A's year. The step names
   and spec §11.5 change, and the 2026-09-23 captures stay in the snapshot.
3. **Probe 18 A's "full period" evidence relied on C33** (its untyped to-October voucher read returned the whole FY).
   **Resolution:** read the whole FY explicitly (`vouchers_fy`) and filter in Python for as-on figures.
4. **Probe 17's dates were never wrong** (current period = FY either way). **Resolution:** re-run anyway, so that the
   stored `ledger_level_tb` template is the typed one S2 will reuse. Its conclusion is not expected to change.
5. **C43 enforcement: clamp or refuse?** **Resolution:** refuse at send time, centrally, in `ProbeContext` (BLOCKED,
   nothing sent). Clamping stays only in `company_b_view.month_window`, where it provably loses nothing. Company A
   holds vouchers on any day, so a silent clamp there would change the question asked.
6. **Re-measure SVFROMDATE on a Ledger collection (typed)?** **Resolution:** not by default. The design question
   (per-ledger as-on anchors) is answered by the typed SVTODATE read. A wedge costs a Tally restart and a licence
   click. It is an optional, user-approved step (Task 10a step 9), run last. The master-collection guard stays either
   way.
7. **Probe 16 B "with the period set inside FY 2024-25" on a Ledger collection**, where SVFROMDATE is the risky
   variable. **Resolution:** the scope question is answered from the no-variable read. Its period (current FY 2025-26)
   isn't the books start, so books- and FY-scoped openings differ on every active ledger. The FY 2024-25 read sends a
   typed SVTODATE (31-03-2025) only, and SVFROMDATE 01-04-2024 is added only under `--allow-risky`.
8. **Which ledgers probe 16 B compares.** The dataset's running balances are cumulative across FYs, and Tally resets
   nominal ledgers every April. **Resolution:** balance-sheet ledgers only (kind from Tally's own group tree, as in
   A). Nominal ledgers are counted, not compared.
9. **Probe 16 B's verdict when scope is FY-based.** **Resolution:** books or FY scope is a *finding* recorded in
   `spec_impact`, not a failure. Only "neither" or "undecided" is DIFFERENT. Closing ≠ dataset is FAILED. An ignored
   as-on read is DIFFERENT (consistent with A), and a moved-but-wrong one is FAILED.
10. **Probe 18 B's stock-bearing group.** A reports it separately. **Resolution:** in B it must reconcile via the TB's
    own `Opening Stock` row (LESSONS rule 19), or the part is FAILED. Company B's dataset knows its opening stock
    exactly (−24,450), so there is no reason to exempt it.
11. **Probe 11's "candidate opening-bills field".** **Resolution:** `BillAllocations` on a Ledger collection filtered to
    the party (the live-written opening-bill shape is `BILLALLOCATIONS.LIST` under the ledger). The fallback is Bills
    Receivable as-on the books start, 01-04-2022 (the loader's own verify read). Amounts are compared by magnitude,
    with the sign recorded (C34: Tally files bills by their own sign).
12. **Probe 11 vs probe 16 B both touch OpeningBalance.** **Resolution:** 11 judges against setup's books-start values.
    If they instead equal the current FY's openings, 11 is DIFFERENT and names probe 16 B as the owner of the scope
    question (S0-D7).
13. **Probe 11's stock value sign.** **Resolution:** expected debit-negative (Part 1 §6; C39's wire). A
    positive-magnitude match is DIFFERENT (S1 negates on ingest), and anything else is FAILED.
14. **Probe 14 with one company loaded.** Tally may ignore SVCurrentCompany entirely, which would make the unescaped
    test prove nothing. **Resolution:** add an `unknown_company_request` control step. "Fails" means a transport error,
    a Tally error envelope, or not the full ledger list. The unescaped request is sent last, with a 10 s timeout, and
    a wedge BLOCKs with the popup hint. Probe 14 also runs last in the B session.
15. **Probe 15's "a Hindi narration".** The dataset has no Hindi-only narration. **Resolution:** the first written,
    unflagged voucher whose narration isn't ASCII (tag 2, "Sale to शर्मा ट्रेडर्स"). The compound-unit voucher is the
    first *other* A4 Paper Ream voucher, so the two steps are independent evidence.
16. **Probe 15's "text byte-exact".** **Resolution:** parsed text equals the dataset string (code points). Whether the
    raw bytes carry UTF-8 or character references is recorded, not judged, because both parse identically.
17. **Probe 15's unit string / Stock Summary date.** **Resolution:** the unit name is recorded, and a mismatch with
    `Box of 10 Nos` is DIFFERENT. Quantities are judged numerically on the leading number (C40: first unit). The Stock
    Summary is read at 31-03-2026 (the current position), because the as-on question belongs to probe 18.
18. **Probe 15 vouchers without probe 5.** **Resolution:** `requires=(0, 5)`. They use probe 5's confirmed
    `voucher_month` template as one-day windows (S0-D7), never a probe-15-built request.
19. **The B parts of 3, 23, 25** have no B code. **Resolution:** not run here. What each needs is listed above, and
    they go to plan part 6.
20. **`--auto` and C44.** **Resolution:** manual mode by default. `--auto` only after the live C44 check in Task 10a
    step 3. A start that loads company A is safe even without C44 when `tally.ini` still has `Load=100003`. That is why
    the pre-flight reads it.
21. **Anchors in single-probe sessions.** Spec §4.2 requires anchors before 16–19 and after the A batch, but only
    ordered runs did them. **Resolution:** a read-only `anchors` command (Task 2), used in Task 10a steps 4 and 8.
    `reset-a` is used only when anchors fail.
22. **Keeping superseded evidence.** `results.json` keeps old parts in `history` automatically, but fixture files are
    overwritten by name. **Resolution:** Task 1's byte-for-byte snapshot, with the evidence tests repointed to it. The
    stale renamed flat files are `git rm`'d in Task 10a's evidence commit, and the snapshot keeps them.
