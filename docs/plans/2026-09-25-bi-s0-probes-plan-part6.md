# S0 Probes — Part 6: B parts of probes 3, 23, 25; company C + probe 24; probe 11 learns C46 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified**, not at the end (tracker rules).

**Goal:** Close the last open company-B parts of S0 (probes 3 B, 23 B, 25 B, including 25 B's R9 duplicate-name UI
attempt), create company C and run probe 24 (security, then TallyVault), and teach probe 11's stock verdict about
Ruling C46.

**Architecture:** Same harness and patterns as part 5. B parts are added to the existing A-only modules
(`parts={"A": run_a, "B": run_b}`). They read company B's dataset only through `v2/probes/company_b_view.py`, judge
against the dataset, and BLOCK on drift. `FakeBooks` grows the read routes these parts need. Each route has a knob for
every Tally behaviour we haven't measured yet, so every verdict branch gets a test. Where a live capture already shows
the real shape (the probe 21 month exports, the probe 11 captures), a test runs the new code against those exact
bytes. Company C gets a tiny idempotent XML loader (`setup-c`: one ledger and one voucher, following the
`TallyWriter` pattern). Its company shell, security and TallyVault are set up by hand in the UI, and probe 24 runs in
manual mode only.

**Tech Stack:** Python ≥ 3.12, httpx (`MockTransport` in tests), pytest + pytest-asyncio (`asyncio_mode = "auto"`),
uv. No new dependencies.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md): §7 probes 3,
11, 23, 24, 25 (B/C parts), §4.3 (company B, the R9 note moved to probe 25 B), §4.4 (company C), §4.5 (guards incl.
C43), §4.6, §5.1–§5.8, §6 batches 5 and 6, §11.5, S0-D6, S0-D7, S0-D8, S0-D9; every "Changed" line through
2026-09-24. Parent: [`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md) R2, R5, R9,
R16, R26, probe 23/24 (§12 list item 24: "Does XML export still work without extra credentials, and do the error
shapes differ?"), Part 3 tiles.
**Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3 rows 3, 11, 23, 24, 25; "Resume
here"; §0 S0 row.
**Live findings this plan builds in:** part 5's ledger `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part5/progress.md`
(rulings Q1–Q18, C45, C46), part 4's ledger (C43, R1–R3), `LESSONS.md` §15 rules 17–22 (+20b), C44 (live-verified
both directions: `TallyControl.restart(label)` rewrites `tally.ini` `Load=`).

**Plan parts:** 1 [`2026-09-22-bi-s0-probes-plan.md`](2026-09-22-bi-s0-probes-plan.md), 2
[`…-part2.md`](2026-09-22-bi-s0-probes-plan-part2.md), 3 [`2026-09-23-bi-s0-company-b-loader.md`](2026-09-23-bi-s0-company-b-loader.md),
4 [`2026-09-24-bi-s0-probes-plan-part4.md`](2026-09-24-bi-s0-probes-plan-part4.md), 5
[`2026-09-24-bi-s0-probes-plan-part5.md`](2026-09-24-bi-s0-probes-plan-part5.md). **Part 6 (this file).**
**Not in this part:** probe 22 (BLOCKED, Ruling C36; do not plan it), tier-C timing (⏭ Q29), any company-A re-run.

---

## Two facts found while writing this plan (they shape Tasks 2, 5 and 12)

1. **Probe 3 B's question is half-answered already.** Probe 21's live month exports (`p21_B_fy2022_month_02.xml`,
   probe 5's confirmed request) contain the cancelled pair 201/202 with `ISCANCELLED` = `Yes`, and **zero ledger
   lines** each. They are recorded, not judged (S0-D7: probe 3 B owns the flags). No probe has read July 2023 yet, so
   **the optional pair 301/302 has never been observed**. Task 2 therefore re-uses p21's evidence (an offline test
   runs 3 B's judging code on p21's committed bytes). Live, it measures only what is still open: the flags judged on
   the extractor's own request, the optional pair, and "no other voucher is flagged" across all 958.
2. **The recorded probe-11 evidence contradicts three documents.** Tracker row 11, spec §7 probe 11 and LESSONS rule
   20b say ledger `OpeningBalance` "correctly held the books-start values". `results.json` `probes.11.parts.B.observations.ledgers`
   says otherwise: **14 of 25 ledgers mismatched, and all 14 equal the current FY's opening** (`as_current_fy`). That
   agrees with probe 16 B's `opening_scope.verdict = "fy"` (14 as FY, 0 as books). The stock FAILED was checked first
   and returned early, so the summary never mentioned the ledger half, and the docs misread the summary. Ledger
   `OpeningBalance` is **current-period-relative, just like stock** (C46 generalises). Task 5 stops a worse half from
   hiding another half. Task 12 corrects the three documents; nothing is deleted, the wrong text is marked superseded.

## Global Constraints

Every task's requirements implicitly include this section.

- **Nothing outside `v2/` and `docs/` changes** (Task 12 may also edit `LESSONS.md`). v2 never imports `backend`,
  `scripts` or `tests`. `v2/agent/` never imports `v2.probes`. Probe modules (`v2/probes/pNN_*.py`) never import
  `v2.probes.setup` or `v2.probes.operator`. They read company B's dataset **only** through
  `v2/probes/company_b_view.py`, which imports only `v2.probes.setup.company_b_data` (`test_isolation.py` pins both).
  Company C's expected content lives in `v2/probes/companies.py` (probe-side constants), never in `setup/`.
- **`v2/probes/operator/`** is touched by exactly one change: Task 6's label guard in `tally_control.py` (plus its
  test). C44 is finished and committed, so no other agent is editing it. Leave everything else in `operator/` alone.
- **Offline tests only in Tasks 1–7.** They never talk to a real Tally, never start Wine and never touch
  `localhost:9000`. Tests use `FakeBooks` (`v2/tests/probes/fake_books.py`) or `FakeTally` (`v2/tests/probes/fakes.py`).
- **C33 and C43 stay true in the fakes.** `FakeBooks.requested_period()` honours only typed `SVFROMDATE`/`SVTODATE`.
  On an educational fake it also honours only days 1/2/31. No task may weaken this. New routes read the period
  through the same function.
- **Every date a probe sends is honoured by an Educational Tally** (day 1, 2 or 31, typed). This part's dates:
  01-04-2022 / 31-03-2026 (3 B books-wide read, 23 B report), month windows from `company_b_view.month_window`
  (Feb 2023 → 01..02, Jun 2023 → 01..02, Jul 2023 → 01..31), 01-04-2025 / 31-03-2026 (company C). The central C43
  guard (`safety.check_educational_dates`) refuses anything else.
- **No hand edits to `v2/probes/results/`** or to the flat fixtures in `v2/tests/fixtures/sync/`. Only the runner
  writes them, in the live tasks (9, 11). **One exception:** Task 5's snapshot folder
  `v2/tests/fixtures/sync/c46_p11_live_2026-09-24/`, a byte-for-byte `cp` of the three `p11_B_*` captures and their
  sidecars, made **before** probe 11 is re-run. It is never edited afterwards.
- **Re-run rule (probe 11, stated once):** a live re-run is allowed **only when the code that judges has changed**.
  It is never allowed to get a different outcome out of unchanged code. The earlier part moves to `results.json`
  `history` automatically. Before the re-run, the new rule is applied offline to the snapshot of the captures it
  judged before (Task 5's relabel test). The live re-run must then reproduce the same observations. A difference
  means company B changed, so **stop** (treat it as drift). Why re-run rather than "relabel in place": only the runner
  may write `results.json`. So a relabel *is* a run, and company B is open in Task 9 anyway (three cheap reads).
- **Money is exact** (`Decimal`, never float). A missing amount is `None`.
- **Request rules** (`safety.check_request` + `check_educational_dates`): no `*` as `NATIVEMETHOD`/`FETCH`, no
  `$$InDateRange`, no off-day date under Educational. Every read goes through `ctx.send` / `ctx.try_send`. One request
  at a time, no retries. A timeout BLOCKs the part with the popup hint, **except** in probe 24's two deliberate
  "prompt open" reads, which use `try_send` and record the timeout as the finding.
- **No period variables on master collections** in this part (none of 3 B / 23 B / 25 B / 24 needs one).
- **Step names** follow `capture._STEP` and are used once per part. Fixtures are `pNN_<part>_<step>.xml` (+ `.json`).
- **Verdicts** follow S0-D6 / §5.4. DIFFERENT and FAILED need a `spec_impact`. **Company-B drift** (an untagged,
  extra, duplicated or wrongly flagged voucher; a bill or ledger the dataset doesn't have) **BLOCKs** with "re-run
  `setup-b` verify or restore the backup". It is never reported as a Tally finding (part 4 Ruling R1 / I1). A part
  that answers two sub-questions records `sub_verdicts` in its observations and names **every** half in its summary.
- **`requires` stays probe-wide.** Probes 3/23/25 keep `requires=(0,)` so that an ordered run's company-A batch never
  BLOCKs on B-only probe 5. A B part that needs probe 5's `voucher_month` checks `ctx.store.confirmed("voucher_month")`
  itself and BLOCKs with "run probe 5 first", as probe 21 does.
- **Credentials (company C) are never written anywhere.** The harness never asks for a username or password and never
  sends one. None appears in any request, sidecar, `results.json`, log, doc or commit. The person types them into
  TallyPrime only. This overrides spec §4.4's "throwaway passwords recorded in the results" (Task 12 records the
  change). Task 11 greps for them before its commit.
- **Company guard for live runs.** Exactly one company is open, and it is the one the part expects: B =
  `Sharma & Sons' Probe Traders` (100000), C = `Probe Vault Co` (number recorded in Task 10; **not** added to
  `OperatorConfig.company_numbers`). Company A is not opened in this part. `--auto` is **never** used (probe 25 B's R9
  step and all of probe 24 are human UI steps). Restarts go through C44 (`auto.control.restart("B", …)`) only.
- **Commands** (repo root `/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q` (also once with `-W error` before a commit that ends a task)
  - one file: `uv run --project v2 pytest v2/tests/probes/<file>.py -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **Logs** of every live command go to `logs/` via `2>&1 | tee logs/<name>-$(date +%F).log`.
- **Commits:** one per task, on `feat/bi-s0-probe-harness`. Stage **only the files the task names**. Every message ends
  with the line `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Tracker discipline** (CLAUDE.md "Always update the tracker"): when a task starts, mark its row 🟡. When it
  finishes, add the proof (test names / commit SHA / log) and a dated change-log row **in the same turn**.
- **Code blocks were written against HEAD `4a735b8` (684 green) but not executed while writing.** Step 0.3's
  pre-flight scan runs them in a scratch copy before any dispatch. The **tests are the contract**. If a code block
  fails its own test, fix the code to pass the test, never the other way round, unless the test contradicts this
  plan's text. Every correction is recorded as a ruling in the SDD ledger.

## Review Focus

These five inputs are the ones most likely to hurt a real run. The spec implies them but doesn't spell them out. Each
one has a test in the task that owns the code.

1. **Optional vouchers are simply not listed** by a Voucher collection (the extractor's request included). A person
   expects probe 3 B to say DIFFERENT and name the extractor consequence, not CONFIRMED because "no flag was wrong",
   and not a crash. Test: Task 2 `test_optional_vouchers_missing_from_the_month_request_is_different`.
2. **A login or TallyVault prompt left open wedges the XML server** (probe 10's popup family). Probe 24 must record the
   timeout as the gate shape, carry on once the person has logged in, and never BLOCK on those two reads. Test: Task 7
   `test_security_and_vault_leave_export_unchanged` (the prompts time out) and
   `test_a_prompt_that_answers_with_no_company_is_recorded`.
3. **A throwaway credential leaks into a committed file.** Test: Task 7
   `test_probe_24_never_asks_for_or_sends_a_credential`, plus Task 11 step 4's grep before the evidence commit.
4. **A worse half hides another half** (the probe-11 misreading above). Every half must be named in the summary, with
   `sub_verdicts` in the observations. Tests: Task 5 `test_every_half_is_named_in_the_summary` and
   `test_the_2026_09_24_live_capture_relabels_to_different_under_c46`.
5. **TallyPrime accepts the R9 duplicate ledger name** (or the person's typed answer disagrees with what Tally did).
   The read-back decides, the part is DIFFERENT, and the cleanup is spelled out in the summary, because a DIFFERENT
   part prints no "CLEANUP NEEDED". Tests: Task 4 `test_a_saved_duplicate_is_different_and_names_the_cleanup` and
   `test_the_read_back_wins_over_the_operators_answer`.

---

## Before you start

- [ ] **Step 0.1: Confirm the base.** `git log --oneline -3` shows `4a735b8` (or later docs-only commits).
  `git status --short -- v2/` is empty.
- [ ] **Step 0.2: Record BASE.** `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1` → expect `684 passed`. This
  plan adds about **55** tests (advisory, as in part 4's Ruling P2). Each task's last step records the running count.
- [ ] **Step 0.3: Pre-flight scratch scan (before any dispatch).** Run the plan's code in a throwaway copy, one commit
  per task, exactly as part 5's `preflight-scan.md` did:
  ```bash
  SCRATCH="$TMPDIR/p6-scratch"      # or the session scratchpad; never inside the repo
  git worktree add --detach "$SCRATCH" HEAD
  cd "$SCRATCH"
  # For Task N = 1..7: paste the task's code and tests as written, then
  uv run --project v2 pytest v2/tests -q 2>&1 | tee "$SCRATCH/runs/task-N.log" | tail -3
  git add -A && git commit -qm "scratch task N"
  ```
  For every failure, write a row in `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part6/preflight-scan.md`: task,
  failing test, cause, the minimal correction (the tests are the contract). Then add one ruling per correction to
  `progress.md` in the same folder. Finally `cd` back and `git worktree remove --force "$SCRATCH"`. The implementer
  ports the **corrected** scratch commits (part 5 Ruling Q1 pattern).
- [ ] **Step 0.4: Start the SDD ledger** `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part6/progress.md` (plan
  path, spec path, start HEAD, BASE, pre-flight result). Mark tracker rows 3, 11, 23, 24, 25 🟡 "plan part 6 in
  progress", with a change-log row.

## File Structure

| File | Responsibility |
|---|---|
| `v2/probes/companies.py` *(modify)* | Task 1: company C's expected content (`COMPANY_C_*` constants) |
| `v2/probes/company_b_view.py` *(modify)* | Task 1: `credit_days`, `written_vouchers`, `flagged_tags`, `BillTerm` + `bill_terms`, `stock_opening_at`, `r9_candidate`, `B_CUSTOM_VOUCHER_TYPE(_BASE)` |
| `v2/tests/probes/fake_books.py` *(modify)* | Task 1: header-only Voucher route, VoucherType route, active-company route, bill dates / credit periods / due dates, duplicate-ledger rows, current-period stock openings, `seed_company_b(bills=)`, `seed_company_c` |
| `v2/tests/probes/test_fake_books_part6.py` *(create)* | Task 1 tests |
| `v2/probes/p03_voucher_ids_flags.py` *(modify)*, `v2/tests/probes/test_p03_b_part.py` *(create)*, `test_p03_voucher_ids_flags.py` *(modify: `labels=["A"]`)* | Task 2 |
| `v2/probes/p23_gst_due_dates.py` *(modify)*, `v2/tests/probes/test_p23_b_part.py` *(create)*, `test_p23_gst_due_dates.py` *(modify)* | Task 3 |
| `v2/probes/p25_masters_classification.py` *(modify)*, `v2/tests/probes/test_p25_b_part.py` *(create)*, `test_p25_masters_classification.py` *(modify)* | Task 4 |
| `v2/probes/p11_openings.py`, `v2/tests/probes/test_p11_openings.py` *(modify)*; `v2/tests/fixtures/sync/c46_p11_live_2026-09-24/` *(create, copy only)* | Task 5 |
| `v2/probes/setup/company_c.py` *(create)*, `v2/probes/setup/writes.py` *(modify: `list_vouchers`)*, `v2/probes/__main__.py` *(modify: `setup-c`)*, `v2/probes/operator/tally_control.py` *(modify: label guard)*, `v2/tests/probes/test_company_c.py` *(create)*, `test_cli.py`, `test_tally_control.py` *(modify)* | Task 6 |
| `v2/probes/p24_secured_company.py` *(create)*, `v2/tests/probes/test_p24_secured_company.py` *(create)*, `v2/probes/registry.py` *(modify)* | Task 7 |
| `docs/code-review-bi-s0-part6-<date>.md` *(create)* | Task 8 |
| runner-written evidence + `docs/bi-s0-probe-results-<date>.md` | Tasks 9, 11 |
| specs, tracker, roadmap, `LESSONS.md` | Task 12 |

---

### Task 1: Dataset accessors, company C constants, and the `FakeBooks` routes for 3 B / 23 B / 25 B / 24 / C46

**Files:**
- Modify: `v2/probes/companies.py`, `v2/probes/company_b_view.py`, `v2/tests/probes/fake_books.py`
- Create: `v2/tests/probes/test_fake_books_part6.py`

**Interfaces:**
- Produces (company_b_view): `credit_days(text) -> int | None`; `written_vouchers(licence) -> dict[int, VoucherSpec]`;
  `flagged_tags(licence) -> tuple[frozenset[int], frozenset[int]]` (cancelled, optional); `BillTerm(name, party,
  bill_date, credit_period, flagged)` with `.credit_days`, `.due`; `bill_terms(licence) -> dict[str, BillTerm]`;
  `stock_opening_at(licence, item, fy_start: date) -> Decimal`; `r9_candidate(licence) -> (name, parent, other_parent)`;
  `B_CUSTOM_VOUCHER_TYPE = "Sales - GST"`, `B_CUSTOM_VOUCHER_TYPE_BASE = "Sales"`.
- Produces (companies): `COMPANY_C_BOOKS_FROM`, `COMPANY_C_BOOKS_TO`, `COMPANY_C_LEDGER`, `COMPANY_C_LEDGER_PARENT`,
  `COMPANY_C_VOUCHER_DATE`, `COMPANY_C_VOUCHER_NARRATION`, `COMPANY_C_VOUCHER_AMOUNT`.
- Produces (FakeBooks): knobs `cancelled_vouchers_listed=True`, `optional_vouchers_listed=True`,
  `bill_credit_period_exported=True`, `bill_due_from_credit_period=True`, `voucher_type_parent_exported=True`,
  `stock_opening_scope="books"`. Collection prefixes `S0P03B`, `S0P24`, `S0P25B` are answered. Also `S0ActiveCompany`,
  `seed_company_b(…, bills=False)`, `seed_company_c(books)`, `FAKE_STOCK_RATE`, and state key `duplicate_ledgers`.

Knob defaults: `cancelled_vouchers_listed` and `bill_credit_period_exported` model **recorded** live behaviour (p21's
captures). `optional_vouchers_listed`, `bill_due_from_credit_period` and `voucher_type_parent_exported` are
**unmeasured hypotheses** that this part settles live. `stock_opening_scope` stays `"books"` even though C46 recorded
`"current"`: five existing suites seed on it, and Task 5 pins the live shape with the real bytes, which is stronger
evidence than a knob default (Ambiguity 21).

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_fake_books_part6.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills
from v2.agent.tally.xml_utils import read_objects
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_TO, B_CUSTOM_VOUCHER_TYPE, bill_terms, credit_days,
                                      flagged_tags, item_specs, r9_candidate, stock_opening_at, written_vouchers)
from v2.probes.companies import (COMPANIES, COMPANY_C_BOOKS_FROM, COMPANY_C_BOOKS_TO, COMPANY_C_LEDGER,
                                 COMPANY_C_VOUCHER_NARRATION)
from v2.probes.reads import fill_month_request, master_request, parse_vouchers, qty_number, tally_date, voucher_request
from v2.tests.probes.fake_books import FakeBooks, seed_company_b, seed_company_c, sync_client
from v2.tests.probes.fakes import bills_xml

B, C = COMPANIES["B"], COMPANIES["C"]


def _post(books: FakeBooks, xml: str) -> str:
    with sync_client(books.transport()) as http:
        return http.post("/", content=xml.encode("utf-8")).text


def _b(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True, bills=True)
    return books


def test_credit_days_reads_tallys_text():
    assert credit_days("30 Days") == 30 and credit_days(" 45 Days ") == 45 and credit_days("1 Day") == 1
    assert credit_days("") is None and credit_days(None) is None and credit_days("30") is None


def test_the_flagged_pairs_and_the_skipped_usd_sales():
    cancelled, optional = flagged_tags("educational")
    assert cancelled == {201, 202} and optional == {301, 302}
    written = written_vouchers("educational")
    assert len(written) == 958 and 101 not in written and 102 not in written


def test_bill_terms_carry_bill_date_credit_period_and_due():
    terms = bill_terms("educational")
    inv = terms["Inv/203"]                       # live: p21_B_fy2022_month_02.xml, BILLDATE 20230201, "30 Days"
    assert inv.bill_date == date(2023, 2, 1) and inv.credit_days == 30 and inv.due == date(2023, 3, 3)
    opening = terms["Op/2022-001"]
    assert opening.credit_period is None and opening.due == opening.bill_date and not opening.flagged
    assert terms["Inv/301"].flagged                  # opened by optional voucher 301


def test_stock_opening_at_the_current_fy_is_the_31_march_2025_stock():
    # C46, live 2026-09-24 (p11_B_stock_openings.xml): 11 / 47 / 19 / 9 / 4.
    want = {"USB Cable Type-C": 11, "Wireless Mouse": 47, "A4 Paper Ream": 19, "Office Stapler": 9,
            "Whiteboard Marker Set": 4}
    for item, qty in want.items():
        assert stock_opening_at("educational", item, date(2025, 4, 1)) == Decimal(qty)
    assert stock_opening_at("educational", "USB Cable Type-C", date(2022, 4, 1)) == Decimal("120")


def test_r9_candidate_is_a_creditor_under_a_custom_group():
    name, parent, other = r9_candidate("educational")
    assert parent in ("National Creditors", "Local Creditors") and other == "Sundry Debtors" and name


def test_header_collection_lists_flags_and_honours_the_listed_knobs():
    xml = voucher_request("S0P03BVouchers", ["Narration", "IsCancelled", "IsOptional"], B,
                          from_date=B_BOOKS_FROM, to_date=B_BOOKS_TO)
    rows = read_objects(_post(_b(), xml), "VOUCHER", ["Narration", "IsCancelled", "IsOptional"])
    assert len(rows) == 958
    assert sum(r["IsCancelled"] == "Yes" for r in rows) == 2 and sum(r["IsOptional"] == "Yes" for r in rows) == 2
    hidden = read_objects(_post(_b(optional_vouchers_listed=False), xml), "VOUCHER", ["Narration"])
    assert len(hidden) == 956


def test_month_export_carries_bill_date_and_credit_period():
    xml = fill_month_request(p05.svdates_template(), B, "01-06-2023", "02-06-2023")
    periods = {b.get("BILLCREDITPERIOD") for v in parse_vouchers(_post(_b(), xml)) for line in v["ledger_lines"]
               for b in line["bills"] if b.get("BILLTYPE") == "New Ref"}
    assert periods == {"30 Days", "45 Days"}
    silent = {b.get("BILLCREDITPERIOD") for v in parse_vouchers(_post(_b(bill_credit_period_exported=False), xml))
              for line in v["ledger_lines"] for b in line["bills"]}
    assert silent == {None}


def test_bills_receivable_due_is_bill_date_plus_credit_period():
    terms = bill_terms("educational")
    report = wrap_report("Bills Receivable", B_BOOKS_FROM, B_BOOKS_TO, B)
    bills = [b for b in parse_bills(_post(_b(), report)) if terms[b["bill_number"]].credit_days]
    assert bills and all(tally_date(b["due_date"]) == terms[b["bill_number"]].due for b in bills)
    flat = [b for b in parse_bills(_post(_b(bill_due_from_credit_period=False), report))
            if terms[b["bill_number"]].credit_days]
    assert flat and all(b["due_date"] == b["bill_date"] for b in flat)


def test_bill_rows_without_dates_stay_byte_identical():
    books = FakeBooks(name=B)
    books.edit_state(lambda s: s["bills"].__setitem__("X/1", {"party": "P", "amount": "-5.00"}))
    report = wrap_report("Bills Receivable", "01-04-2025", "31-03-2026", B)
    assert _post(books, report) == bills_xml([("X/1", "P", "-5.00")])


def test_voucher_types_export_parent_and_reserved_name():
    fields = ["Name", "Parent", "ReservedName"]
    xml = master_request("S0P25BVoucherTypes", "VoucherType", fields, B)
    rows = {r["Name"]: r for r in read_objects(_post(_b(), xml), "VOUCHERTYPE", fields)}
    assert rows[B_CUSTOM_VOUCHER_TYPE]["Parent"] == "Sales" and rows[B_CUSTOM_VOUCHER_TYPE]["ReservedName"] == ""
    assert rows["Sales"]["Parent"] == "Sales" and rows["Sales"]["ReservedName"] == "Sales"   # live p25 A shape
    hidden = {r["Name"]: r for r in read_objects(_post(_b(voucher_type_parent_exported=False), xml),
                                                   "VOUCHERTYPE", fields)}
    assert hidden[B_CUSTOM_VOUCHER_TYPE]["Parent"] == ""


def test_duplicate_ledger_rows_are_exported():
    name, _parent, other = r9_candidate("educational")
    books = _b()
    books.edit_state(lambda s: s.setdefault("duplicate_ledgers", []).append({"name": name, "parent": other}))
    xml = master_request("S0P25BLedgers", "Ledger", ["Name", "Parent"], B)
    parents = sorted(r["Parent"] for r in read_objects(_post(books, xml), "LEDGER", ["Name", "Parent"])
                     if r["Name"] == name)
    assert len(parents) == 2 and other in parents


def test_current_period_stock_openings_replay_to_the_dataset():
    xml = master_request("S0P11Stock", "StockItem", ["Name", "OpeningBalance"], B)
    rows = read_objects(_post(_b(stock_opening_scope="current"), xml), "STOCKITEM", ["Name", "OpeningBalance"])
    assert {r["Name"] for r in rows} == set(item_specs("educational"))
    for row in rows:
        assert qty_number(row["OpeningBalance"]) == stock_opening_at("educational", row["Name"], date(2025, 4, 1))


def test_company_c_seed_answers_every_probe_24_read():
    books = FakeBooks(name=C, educational=True)
    seed_company_c(books)
    active = read_objects(_post(books, "<ENVELOPE><HEADER><ID>S0ActiveCompany</ID></HEADER></ENVELOPE>"),
                          "COMPANY", ["Name", "GUID"])
    assert [r["Name"] for r in active] == [C] and active[0]["GUID"]
    ledgers = read_objects(_post(books, master_request("S0P24Ledgers", "Ledger", ["Name"], C)), "LEDGER", ["Name"])
    assert COMPANY_C_LEDGER in {r["Name"] for r in ledgers}
    month = fill_month_request(p05.svdates_template(), C, COMPANY_C_BOOKS_FROM, COMPANY_C_BOOKS_TO)
    assert [v["header"]["NARRATION"] for v in parse_vouchers(_post(books, month))] == [COMPANY_C_VOUCHER_NARRATION]
```

- [ ] **Step 2: Run to verify they fail** (`ImportError` on the new names).
- [ ] **Step 3a: `v2/probes/companies.py`** — append:

```python
# Company C (S0 spec §4.4; plan part 6). The company shell, its security and its TallyVault are made by hand in the
# UI; `setup-c` writes exactly this one ledger and one voucher. Books begin 1-Apr-2025 so the voucher's date is the
# books-start day: never after F2 (LESSONS §15 rule 14) and a day Educational TallyPrime accepts (1/2/31, C43).
COMPANY_C_BOOKS_FROM = "01-04-2025"
COMPANY_C_BOOKS_TO = "31-03-2026"
COMPANY_C_LEDGER = "S0 Vault Expense"
COMPANY_C_LEDGER_PARENT = "Indirect Expenses"
COMPANY_C_VOUCHER_DATE = "20250401"
COMPANY_C_VOUCHER_NARRATION = "[S0-C:1] Probe Vault voucher"
COMPANY_C_VOUCHER_AMOUNT = "100.00"
```

- [ ] **Step 3b: `v2/probes/company_b_view.py`**. Add `from datetime import date, timedelta` (replacing the bare
  `date` import), add `OPENING_BILL_DATE, SALES_GST_VOUCHER_TYPE` to the `company_b_data` import, and append:

```python
B_CUSTOM_VOUCHER_TYPE = SALES_GST_VOUCHER_TYPE     # made in the UI under Sales before setup-b (spec §4.3)
B_CUSTOM_VOUCHER_TYPE_BASE = "Sales"
_CREDIT_DAYS = re.compile(r"^\s*(\d+)\s*Days?\s*$", re.IGNORECASE)


def credit_days(text: str | None) -> int | None:
    """'30 Days' → 30: Tally's BILLCREDITPERIOD text (live: `<BILLCREDITPERIOD JD=… P="30 Days">30 Days`) and the
    dataset's `credit_period`. Anything else → None."""
    match = _CREDIT_DAYS.match(text or "")
    return int(match.group(1)) if match else None


def written_vouchers(licence: str) -> dict[int, VoucherSpec]:
    """tag → voucher for every voucher the loader wrote (C36: skipped ones never exist in Tally)."""
    return {v.tag: v for v in dataset(licence).vouchers if not v.skip_reason}


def flagged_tags(licence: str) -> tuple[frozenset[int], frozenset[int]]:
    """(cancelled, optional) among the written vouchers — company B's 201/202 and 301/302 (probe 3 B)."""
    written = written_vouchers(licence).values()
    return frozenset(v.tag for v in written if v.cancelled), frozenset(v.tag for v in written if v.optional)


@dataclass(frozen=True)
class BillTerm:
    name: str
    party: str
    bill_date: date                # its voucher's date; the opening bill's is OPENING_BILL_DATE
    credit_period: str | None      # the dataset's text ("30 Days"); None = none (the opening bill)
    flagged: bool                  # opened by a cancelled/optional voucher — Tally keeps it out of bills (C42)

    @property
    def credit_days(self) -> int | None:
        return credit_days(self.credit_period)

    @property
    def due(self) -> date:
        """Bill date + credit period in calendar days (the rule probe 23 B checks Tally's BILLDUE against)."""
        return self.bill_date + timedelta(days=self.credit_days or 0)


def bill_terms(licence: str) -> dict[str, BillTerm]:
    """Every bill the loader opened, by name: each ledger's opening bill, and each New Ref on a written voucher."""
    terms: dict[str, BillTerm] = {}
    for spec in dataset(licence).ledgers:
        if spec.opening_bill:
            terms[spec.opening_bill] = BillTerm(spec.opening_bill, spec.name, OPENING_BILL_DATE, None, False)
    for v in written_vouchers(licence).values():
        for bill in v.bills:
            if bill.bill_type == "New Ref":
                terms[bill.name] = BillTerm(bill.name, v.party, v.date, bill.credit_period, v.cancelled or v.optional)
    return terms


def stock_opening_at(licence: str, item: str, fy_start: date) -> Decimal:
    """The item's quantity at the start of the FY beginning `fy_start`: setup's opening at the books start, else the
    close of the day before (a month end). C46: for the current FY this, not the books-start figure, is what
    StockItem.OpeningBalance exports."""
    if fy_start == B_BOOKS_FROM_DATE:
        return item_specs(licence)[item].opening_qty or Decimal("0")
    return stock_qty_at(licence, item, fy_start - timedelta(days=1))


def r9_candidate(licence: str) -> tuple[str, str, str]:
    """(ledger, its parent, the parent to try it under) for probe 25 B's duplicate-name attempt (R9; spec §4.3 note,
    moved to probe 25 B on 2026-09-24): the first creditor under a custom sub-group, tried under Sundry Debtors."""
    custom = {group.name for group in dataset(licence).groups}
    spec = next(s for s in dataset(licence).ledgers if s.parent in custom)
    return spec.name, spec.parent, "Sundry Debtors"
```

- [ ] **Step 3c: `v2/tests/probes/fake_books.py`.** Make these edits.

  1. Replace the `B_PROBE_COLLECTIONS` line, and add these module helpers under `_COMPANY_VAR`:

```python
# Collection-name prefixes answered by the generic probe master routes below (probes 3 B, 11, 14, 15, 16 B, 18 B, 24,
# 25 B).
B_PROBE_COLLECTIONS = ("S0P03B", "S0P11", "S0P14", "S0P15", "S0P16B", "S0P18B", "S0P24", "S0P25B")
# The fake keeps no stock valuation: a current-period opening (C46 knob) is priced at this placeholder rate. Probe 11
# records, never judges, the rate/value of a current-period opening.
FAKE_STOCK_RATE = Decimal("100.00")
_CREDIT_DAYS = re.compile(r"^\s*(\d+)\s*Days?\s*$", re.IGNORECASE)


def _short_date(day) -> str:
    """Tally's report date text: 1-Feb-23."""
    return f"{day.day}-{day:%b}-{day:%y}"


def _bill_row(ref: str, party: str, amount: str, bill_date: str = "1-Apr-25", due: str = "1-Apr-25",
              overdue: str = "10") -> str:
    """One Bills Receivable/Payable row — byte-identical to fakes.bills_xml when no date is known."""
    return (f"<BILLFIXED><BILLDATE>{bill_date}</BILLDATE><BILLREF>{esc(ref)}</BILLREF><BILLPARTY>{esc(party)}"
            f"</BILLPARTY></BILLFIXED><BILLCL>{amount}</BILLCL><BILLDUE>{due}</BILLDUE><BILLOVERDUE>{overdue}"
            "</BILLOVERDUE>")


def _voucher_header(state: dict, mid: str, v: dict) -> dict[str, str]:
    lines = v.get("lines", [])
    return {"DATE": v["date"], "GUID": f"{state['guid']}-{int(mid):08x}", "MASTERID": mid, "ALTERID": mid,
            "VOUCHERTYPENAME": v.get("vch_type", ""), "VOUCHERNUMBER": mid, "REFERENCE": "",
            "PARTYLEDGERNAME": lines[0]["ledger"] if lines else "", "NARRATION": v["narration"],
            "ISCANCELLED": v["cancelled"], "ISOPTIONAL": v["optional"], "ISPOSTDATED": v["post_dated"]}
```

  2. Replace `_export_voucher` with:

```python
def _export_voucher(state: dict, mid: str, v: dict, *, credit_periods: bool = True) -> str:
    """One stored voucher the way probe 5's month request gets it back: header, ledger lines (the voucher's bill
    postings on its first line, the party line), and inventory rows. It is shaped for the probes' parsers (reads.
    parse_vouchers), not a byte-for-byte copy of live Tally. Probe 21's live byte counts come from live Tally only.
    A posting that knows its bill date / credit period (seed_company_b(bills=True)) exports them as BILLDATE and
    BILLCREDITPERIOD (live shape: p21_B_fy2022_month_02.xml); without them the bytes are exactly as before."""
    lines = v.get("lines", [])
    header = _voucher_header(state, mid, v)
    body = "".join(f"<{k}>{esc(str(value))}</{k}>" for k, value in header.items())
    for i, line in enumerate(lines):
        bills = "".join(
            "<BILLALLOCATIONS.LIST>"
            + (f"<BILLDATE>{b['date']}</BILLDATE>" if b.get("date") else "")
            + f"<NAME>{esc(b['name'])}</NAME>"
            + (f"<BILLCREDITPERIOD>{esc(b['credit_period'])}</BILLCREDITPERIOD>"
               if credit_periods and b.get("credit_period") else "")
            + f"<BILLTYPE>{esc(b['type'])}</BILLTYPE><AMOUNT>{b['amount']}</AMOUNT></BILLALLOCATIONS.LIST>"
            for b in (v.get("bills", []) if i == 0 else []))
        body += (f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{esc(line['ledger'])}</LEDGERNAME>"
                 f"<ISDEEMEDPOSITIVE>{line['deemed_positive']}</ISDEEMEDPOSITIVE><AMOUNT>{line['amount']}</AMOUNT>"
                 f"{bills or '<BILLALLOCATIONS.LIST>  </BILLALLOCATIONS.LIST>'}</ALLLEDGERENTRIES.LIST>")
    for inv in v.get("inventory", []):
        unit = state.get("items", {}).get(inv["item"], {}).get("qty_unit", "")
        qty = inv["qty"].lstrip("-") + (f" {unit}" if unit else "")
        body += (f"<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>{esc(inv['item'])}</STOCKITEMNAME>"
                 f"<ACTUALQTY> {qty}</ACTUALQTY></ALLINVENTORYENTRIES.LIST>")
    return f'<VOUCHER VCHTYPE="{esc(header["VOUCHERTYPENAME"])}">{body}</VOUCHER>'
```

  3. In `seed_company_b`, change the signature to `(books, licence="educational", *, masters=False, bills=False)` and
     extend its docstring with one paragraph: "With `bills=True` (probe 23 B) every bill is on record the way Tally
     keeps it: each New Ref opened by a written, unflagged voucher with its signed amount (the party line's sign;
     C34: − = receivable), its bill date and credit period; each Agst Ref added to its bill; the opening bill. The
     vouchers' postings then carry the bill date and credit period too." Import
     `OPENING_BILL_DATE, SALES_GST_VOUCHER_TYPE, generate, quantity_unit` in its local import, add this helper
     inside the function:

```python
    def posting(v, b) -> dict[str, str]:
        entry = {"name": b.name, "type": b.bill_type, "amount": f"{b.amount:.2f}"}
        if bills and b.credit_period:
            entry.update(date=v.date.strftime("%Y%m%d"), credit_period=b.credit_period)
        return entry
```

     replace the voucher's `"bills": …` value with `[] if v.cancelled else [posting(v, b) for b in v.bills]`, add at
     the end of the `if masters:` block:

```python
            if SALES_GST_VOUCHER_TYPE not in state["voucherTypes"]:
                state["voucherTypes"].append(SALES_GST_VOUCHER_TYPE)
            state["voucher_type_parents"] = {SALES_GST_VOUCHER_TYPE: "Sales"}
```

     and add after it, still inside `fill`:

```python
        if bills:
            book = state.setdefault("bills", {})
            for led in data.ledgers:
                if led.opening_bill and led.opening is not None:
                    book.setdefault(led.opening_bill, {"party": led.name, "amount": f"{led.opening:.2f}",
                                                       "opening": True,
                                                       "date": OPENING_BILL_DATE.strftime("%Y%m%d")})
            for v in sorted(data.vouchers, key=lambda v: (v.date, v.tag)):
                if v.skip_reason or v.cancelled or v.optional:           # C42: flagged vouchers post no bill
                    continue
                party = next((line for line in v.lines if line.ledger == v.party), None)
                sign = Decimal("1") if party is None or party.amount > 0 else Decimal("-1")
                for b in v.bills:
                    if b.bill_type == "New Ref":
                        book[b.name] = {"party": v.party, "amount": f"{sign * b.amount:.2f}",
                                        "date": v.date.strftime("%Y%m%d"), "credit_period": b.credit_period or ""}
                    elif b.bill_type == "Agst Ref":
                        target = book.setdefault(b.name, {"party": v.party, "amount": "0.00"})
                        target["amount"] = f"{Decimal(target['amount']) + sign * b.amount:.2f}"
```

  4. Add below `seed_company_b`:

```python
def seed_company_c(books: "FakeBooks") -> None:
    """Company C as `setup-c` leaves it (plan part 6): Tally's own Cash and Profit & Loss A/c, the one expense
    ledger and the one Payment voucher, books from 1-Apr-2025. Straight into state (read-probe tests only)."""
    from v2.probes.companies import (COMPANY_C_LEDGER, COMPANY_C_LEDGER_PARENT, COMPANY_C_VOUCHER_AMOUNT,
                                     COMPANY_C_VOUCHER_DATE, COMPANY_C_VOUCHER_NARRATION)

    def fill(state: dict) -> None:
        guid = state["guid"]
        state["books_from"] = COMPANY_C_VOUCHER_DATE
        state["last_voucher_date"] = COMPANY_C_VOUCHER_DATE
        state["ledgers"] = {
            "Cash": {"parent": "Cash-in-Hand", "email": "", "alter_id": 10, "guid": f"{guid}-c000000a", "opening": "0.00"},
            "Profit & Loss A/c": {"parent": "Primary", "email": "", "alter_id": 11, "guid": f"{guid}-c000000b",
                                  "opening": "0.00"},
            COMPANY_C_LEDGER: {"parent": COMPANY_C_LEDGER_PARENT, "email": "", "alter_id": 12,
                               "guid": f"{guid}-c000000c", "opening": "0.00"}}
        state["vouchers"] = {"1": {
            "narration": COMPANY_C_VOUCHER_NARRATION, "date": COMPANY_C_VOUCHER_DATE, "post_dated": "No",
            "cancelled": "No", "optional": "No", "vch_type": "Payment",
            "lines": [{"ledger": COMPANY_C_LEDGER, "amount": f"-{COMPANY_C_VOUCHER_AMOUNT}", "deemed_positive": "Yes"},
                      {"ledger": "Cash", "amount": COMPANY_C_VOUCHER_AMOUNT, "deemed_positive": "No"}],
            "inventory": []}}
    books.edit_state(fill)
```

  5. `FakeBooks.__init__`: add keyword arguments and attributes (keep every existing one):

```python
                 cancelled_vouchers_listed: bool = True, optional_vouchers_listed: bool = True,
                 bill_credit_period_exported: bool = True, bill_due_from_credit_period: bool = True,
                 voucher_type_parent_exported: bool = True, stock_opening_scope: str = "books"):
        ...
        # plan part 6. Recorded live: cancelled vouchers are listed with ISCANCELLED=Yes and New Ref bills export
        # BILLCREDITPERIOD (p21_B_fy2022_month_02.xml). Hypotheses measured live by probes 3 B / 23 B / 25 B:
        # optional vouchers listed, BILLDUE = bill date + credit period, a custom voucher type exports its Parent.
        self.cancelled_vouchers_listed = cancelled_vouchers_listed
        self.optional_vouchers_listed = optional_vouchers_listed
        self.bill_credit_period_exported = bill_credit_period_exported
        self.bill_due_from_credit_period = bill_due_from_credit_period
        self.voucher_type_parent_exported = voucher_type_parent_exported
        # probe 11 / C46 (live 2026-09-24): "current" = StockItem opening fields are the current period's opening.
        self.stock_opening_scope = stock_opening_scope
```

  6. In `_answer`: right after the `S0CompanyCounters` branch add

```python
        if "S0ActiveCompany" in body:
            # Probe 2's confirmed active-company read (candidate a): Company collection filtered to ##SVCurrentCompany.
            return objects_xml("COMPANY", [{"Name": state["name"], "GUID": state["guid"]}])
```

     in the month-request branch, list only `self._listed(v)` vouchers and pass the knob:

```python
            return vouchers_xml([_export_voucher(state, mid, v, credit_periods=self.bill_credit_period_exported)
                                 for mid, v in sorted(in_period.items(), key=lambda kv: int(kv[0]))
                                 if self._listed(v)])
```

     and replace the two bills branches with

```python
        if "<ID>Bills Receivable</ID>" in body:
            return self._bills_report(state, receivable=True, as_on=period[1])
        if "<ID>Bills Payable</ID>" in body:
            return self._bills_report(state, receivable=False, as_on=period[1])
```

  7. In `_b_collection`, before `if kind == "Ledger":`, add:

```python
        if kind == "Voucher":                              # probe 3 B: header fields only, typed period, knobs
            rows = [_voucher_header(state, mid, v)
                    for mid, v in sorted(state["vouchers"].items(), key=lambda kv: int(kv[0]))
                    if period[0] <= (_yyyymmdd(v["date"]) or v["date"]) <= period[1] and self._listed(v)]
            return objects_xml("VOUCHER", rows)
        if kind == "VoucherType":                          # probe 25 B
            parents = state.get("voucher_type_parents", {})
            rows = []
            for vtype in state["voucherTypes"]:
                if vtype in parents:                       # a custom type: Parent = its base type, no ReservedName
                    rows.append({"Name": vtype, "Parent": parents[vtype] if self.voucher_type_parent_exported else "",
                                 "ReservedName": ""})
                else:                                      # live p25 A: a reserved type is its own Parent and ReservedName
                    rows.append({"Name": vtype, "Parent": vtype, "ReservedName": vtype})
            return objects_xml("VOUCHERTYPE", rows)
```

     and replace the `StockItem` branch with:

```python
        if kind == "StockItem":
            rows = []
            for n, i in state["items"].items():
                if wanted not in (None, n):
                    continue
                row = {"Name": n, "Parent": i.get("parent", ""), "BaseUnits": i.get("base_units", ""),
                       "OpeningBalance": i.get("opening_qty", ""), "OpeningRate": i.get("opening_rate", ""),
                       "OpeningValue": i.get("opening_value", "")}
                if self.stock_opening_scope == "current":          # C46: the current period's opening
                    qty, unit = self._stock_level(state, n, before=self.current_period[0]), i.get("qty_unit", "")
                    row.update(OpeningBalance=f"{qty} {unit}".strip(), OpeningRate=f"{FAKE_STOCK_RATE:.2f}/{unit}",
                               OpeningValue=f"{-(qty * FAKE_STOCK_RATE):.2f}")
                rows.append(row)
            return objects_xml("STOCKITEM", rows)
```

  8. At the end of `_ledger_export`'s loop (before the `return`), emit hand-made duplicates:

```python
        for dup in state.get("duplicate_ledgers", []):     # probe 25 B / R9: a second ledger with the same name
            if wanted is None or dup["name"] == wanted:
                parent = f"<PARENT>{esc(dup['parent'])}</PARENT>" if "parent" in fields else ""
                out.append(f'<LEDGER NAME="{esc(dup["name"])}"><NAME>{esc(dup["name"])}</NAME>{parent}</LEDGER>')
```

  9. Add these methods to `FakeBooks` (next to `_stock_summary`):

```python
    def _listed(self, v: dict) -> bool:
        if v.get("cancelled") == "Yes" and not self.cancelled_vouchers_listed:
            return False
        return not (v.get("optional") == "Yes" and not self.optional_vouchers_listed)

    @staticmethod
    def _stock_level(state: dict, name: str, *, before: str) -> Decimal:
        """Opening quantity + unflagged inventory moves dated before `before` (YYYYMMDD). C42: flagged move nothing."""
        words = (state["items"][name].get("opening_qty") or "").split()
        qty = Decimal(words[0]) if words else Decimal("0")
        for v in state["vouchers"].values():
            if _flagged(v) or (_yyyymmdd(v["date"]) or v["date"]) >= before:
                continue
            qty += sum((Decimal(i["qty"]) for i in v.get("inventory", []) if i["item"] == name), Decimal("0"))
        return qty

    def _bills_report(self, state: dict, *, receivable: bool, as_on: str) -> str:
        """Bills Receivable/Payable (C34: the bill's sign files it). A bill that knows its date shows it; BILLDUE is
        date + credit period when `bill_due_from_credit_period`, else the bill date. Rows of bills without a date are
        byte-identical to the old fakes.bills_xml output."""
        from datetime import datetime, timedelta
        rows = [_bill_row(ref, party, amount) for ref, party, amount in
                (state.get("bills_receivable", []) if receivable else [])]
        as_on_day = datetime.strptime(as_on, "%Y%m%d").date()
        for name, bill in _effective_bills(state).items():
            amount = Decimal(bill["amount"])
            if amount == 0 or (amount < 0) != receivable:
                continue
            if not bill.get("date"):
                rows.append(_bill_row(name, bill["party"], bill["amount"]))
                continue
            start = datetime.strptime(bill["date"], "%Y%m%d").date()
            match = _CREDIT_DAYS.match(bill.get("credit_period") or "")
            days = int(match.group(1)) if match and self.bill_due_from_credit_period else 0
            due = start + timedelta(days=days)
            rows.append(_bill_row(name, bill["party"], bill["amount"], _short_date(start), _short_date(due),
                                  str(max((as_on_day - due).days, 0))))
        return "<ENVELOPE>" + "".join(rows) + "</ENVELOPE>"
```

- [ ] **Step 4: Run** the new file, then the whole suite (also `-W error`). Expected BASE + 13, all green. If an
  existing suite changes, the byte-identity promise (step 3c.6 bills, step 3c.2 vouchers) is broken. Fix the fake,
  never the old test.
- [ ] **Step 5: Commit** (`v2/probes/companies.py v2/probes/company_b_view.py v2/tests/probes/fake_books.py
  v2/tests/probes/test_fake_books_part6.py`):
  `test(bi/v2): FakeBooks + company_b_view for 3 B / 23 B / 25 B / 24 / C46`. Add a tracker change-log row.

---

### Task 2: Probe 3's B part — flags on the extractor's request, the optional pair, and "nothing else is flagged"

**Files:**
- Modify: `v2/probes/p03_voucher_ids_flags.py`, `v2/tests/probes/test_p03_voucher_ids_flags.py` (every
  `run_probe(p03.PROBE, labels=None, …)` → `labels=["A"]`, as part 5's F6/F8 did; `remaining == ["B"]` stays true)
- Create: `v2/tests/probes/test_p03_b_part.py`

**Interfaces:**
- Consumes: Task 1's `written_vouchers`, `flagged_tags`, the knobs `optional_vouchers_listed` /
  `cancelled_vouchers_listed`; existing `fetch_window`, `month_window`, `tag_of`, `loaded_licence`, `B_BOOKS_FROM`,
  `B_BOOKS_TO`.
- Produces: `PROBE.parts = {"A": run_a, "B": run_b}`; pure helpers `month_flag_rows(raw) -> dict[int, dict]`,
  `flag_readings(rows: dict[int, dict], tags, cancelled) -> dict[str, dict]`. Fixtures `p03_B_vouchers_flags`,
  `p03_B_flagged_month_2023_02`, `p03_B_flagged_month_2023_07`.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p03_b_part.py`:

```python
from pathlib import Path

from v2.agent.tally.client import TallyClient
from v2.probes import p03_voucher_ids_flags as p03
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes.capture import Capture
from v2.probes.company_b_view import first_voucher
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]
SYNC = Path(__file__).resolve().parents[1] / "fixtures" / "sync"


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational")
    return books


def _set(books: FakeBooks, tag: int, key: str, value: str) -> None:
    def edit(state):
        for v in state["vouchers"].values():
            if v["narration"].startswith(f"[S0-B:{tag}]"):
                v[key] = value
    books.edit_state(edit)


async def _run(tmp_path, books, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    await run_probe(p03.PROBE, labels=["B"], client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(3)["parts"]["B"]


async def test_flags_on_both_reads_are_confirmed(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["header_flagged"]["201"]["flags_ok"] and obs["header_flagged"]["302"]["flags_ok"]
    assert obs["months"]["2023-07"]["flags"]["301"]["IsOptional"] == "Yes" and obs["others"] == 954
    assert part["fixtures"] == ["p03_B_vouchers_flags.xml", "p03_B_flagged_month_2023_02.xml",
                                "p03_B_flagged_month_2023_07.xml"]


async def test_optional_vouchers_missing_from_the_month_request_is_different(tmp_path):
    part = await _run(tmp_path, _books(optional_vouchers_listed=False))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert "optional" in part["summary"] and "extractor" in part["spec_impact"]
    assert part["observations"]["months"]["2023-07"]["flags"]["301"]["returned"] is False


async def test_a_flag_that_did_not_stick_fails(tmp_path):
    books = _books()
    _set(books, 301, "optional", "No")
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "301" in part["summary"] and "R16" in part["spec_impact"]


async def test_a_flag_the_dataset_does_not_set_blocks_as_drift(tmp_path):
    books = _books()
    _set(books, first_voucher("educational", lambda v: True).tag, "cancelled", "Yes")
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "drifted" in part["summary"]


async def test_an_untagged_voucher_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["vouchers"].__setitem__("99999", {
        "narration": "typed by hand", "date": "20230601", "post_dated": "No", "cancelled": "No", "optional": "No",
        "vch_type": "Journal", "lines": [], "inventory": [], "bills": []}))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "untagged 1" in part["summary"]


async def test_without_probe_5_the_b_part_blocks(tmp_path):
    part = await _run(tmp_path, _books(), with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "probe 5" in part["summary"]


def test_probe_21s_capture_already_shows_the_cancelled_pair_flagged():
    """S0-D7: probe 21 saw 201/202 come back (recorded, not judged). 3 B's judging code on those exact live bytes."""
    rows = p03.month_flag_rows((SYNC / "p21_B_fy2022_month_02.xml").read_text(encoding="utf-8"))
    readings = p03.flag_readings(rows, {201, 202}, frozenset({201, 202}))
    assert readings["201"]["flags_ok"] and readings["202"]["flags_ok"]
    assert rows[201]["ledger_lines"] == 0          # live: a cancelled voucher exports no ledger lines
```

- [ ] **Step 2: Run to verify they fail** (`KeyError: 'B'` / missing helpers).
- [ ] **Step 3: Implement.** In `p03_voucher_ids_flags.py`, replace the docstring's last line with the B paragraph
  below, add the imports, and append the B code. Then set `parts={"A": run_a, "B": run_b}` (keep
  `planned_parts=("A", "B")`, `requires=(0,)`).

```python
"""…
The B part (plan part 6) judges the cancelled / optional flags on company B. What B still measures (S0-D7): probe
21's live run already saw the cancelled pair 201/202 come back from probe 5's confirmed month request (recorded, not
judged), so B does not re-ask "are cancelled vouchers returned?". It judges the flags on the extractor's own request
for the two months that hold flagged vouchers (Feb 2023: 201/202; Jul 2023: 301/302 — no probe has read July 2023),
and books-wide on this probe's header collection for everything else.
"""
from collections import Counter
from typing import Any, Iterable

from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_TO, fetch_window, flagged_tags, loaded_licence,
                                      month_window, tag_of, written_vouchers)
from v2.probes.core import ProbeBlocked
from v2.probes.reads import parse_vouchers

FLAGGED_MONTHS = ((2023, 2), (2023, 7))       # the dataset's cancelled 201/202 and optional 301/302
HEADER_TIMEOUT = 60.0                          # ~958 headers at ~1.6 KB (probe 3 A: 78,911 bytes for 50)
B_CONFIRMED_IMPACT = ("R16: the extractor's month request returns cancelled and optional vouchers WITH their flags "
                      "(a cancelled one exports no ledger lines); S1 ingests them and keeps both out of balances by "
                      "IsCancelled / IsOptional, as Tally does (C42). No other voucher carries a flag.")
B_WRONG_FLAG_IMPACT = ("R16 filtering is redesigned before S1: a flagged voucher comes back without its flag, so "
                       "ingest can't tell it from a posting voucher.")
B_NOT_LISTED_IMPACT = ("The extractor's request never returns {kinds} vouchers: S1 never ingests them, and when a person "
                       "turns one into a regular voucher it arrives as a new voucher (AltVchId moves). R16's filter "
                       "only has to handle what is listed.")


def _wanted(tag: int, cancelled: frozenset[int]) -> tuple[str, str]:
    return ("Yes", "No") if tag in cancelled else ("No", "Yes")        # (IsCancelled, IsOptional)


def month_flag_rows(raw: str) -> dict[int, dict[str, Any]]:
    """tag → flags and line counts from a full voucher export (probe 5's month request)."""
    out: dict[int, dict[str, Any]] = {}
    for v in parse_vouchers(raw):
        tag = tag_of(v["header"].get("NARRATION", ""))
        if tag is not None:
            out[tag] = {"IsCancelled": v["header"].get("ISCANCELLED", ""), "IsOptional": v["header"].get("ISOPTIONAL", ""),
                        "ledger_lines": len(v["ledger_lines"]),
                        "amounts": sum(1 for line in v["ledger_lines"] if line["amount"] is not None)}
    return out


def flag_readings(rows: dict[int, dict], tags: Iterable[int], cancelled: frozenset[int]) -> dict[str, dict]:
    """str(tag) → returned? its two flags, and whether they are the ones the dataset set."""
    out: dict[str, dict] = {}
    for tag in sorted(tags):
        row = rows.get(tag)
        if row is None:
            out[str(tag)] = {"returned": False}
            continue
        got = (row.get("IsCancelled", ""), row.get("IsOptional", ""))
        out[str(tag)] = {"returned": True, "IsCancelled": got[0], "IsOptional": got[1],
                         "flags_ok": got == _wanted(tag, cancelled)}
    return out


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    confirmed = ctx.store.confirmed("voucher_month")
    if confirmed is None:
        raise ProbeBlocked("No confirmed month request: run probe 5 first — 3 B judges the flags on the extractor's "
                           "own request (S0-D7).")
    written = written_vouchers(licence)
    cancelled, optional = flagged_tags(licence)
    flagged = cancelled | optional
    rows = read_objects(await ctx.send("vouchers_flags", voucher_request(
        "S0P03BVouchers", FIELDS, ctx.company_name, from_date=B_BOOKS_FROM, to_date=B_BOOKS_TO),
        timeout=HEADER_TIMEOUT), "VOUCHER", FIELDS)
    tags = [tag_of(row["Narration"]) for row in rows]
    counts = Counter(tag for tag in tags if tag is not None)
    untagged, extra = tags.count(None), sorted(set(counts) - set(written))
    duplicates = sorted(tag for tag, n in counts.items() if n > 1)
    if untagged or extra or duplicates:
        raise ProbeBlocked(f"Company B differs from the dataset in vouchers_flags: untagged {untagged}, extra "
                           f"{extra[:5]}, duplicates {duplicates[:5]} — re-run `setup-b` verify or restore the backup.")
    by_tag = {tag: row for tag, row in zip(tags, rows)}
    missing = sorted(set(written) - flagged - set(by_tag))
    if missing:
        raise ProbeBlocked(f"The books-wide read ({B_BOOKS_FROM}..{B_BOOKS_TO}) didn't return {len(missing)} written "
                           f"voucher(s) {missing[:5]} — company B drifted or the request didn't reach them; re-run "
                           "`setup-b` verify.")
    false_flags = sorted(tag for tag, row in by_tag.items() if tag not in flagged
                         and "Yes" in (row["IsCancelled"], row["IsOptional"], row["IsPostDated"]))
    if false_flags:
        raise ProbeBlocked(f"Voucher(s) {false_flags[:5]} carry a flag the dataset doesn't set — company B drifted "
                           "(a UI edit?); re-run `setup-b` verify or restore the backup.")
    empty = [flag for flag in FLAG_CANDIDATES if any(not row[flag] for row in rows)]
    header = flag_readings(by_tag, flagged, cancelled)

    months: dict[str, dict] = {}
    for year, month in FLAGGED_MONTHS:
        start, end = month_window(year, month, licence)
        step = f"flagged_month_{year}_{month:02d}"
        result, raw = await fetch_window(ctx, step, confirmed["xml_template"], licence,
                                         start.strftime("%d-%m-%Y"), end.strftime("%d-%m-%Y"))
        if not result["reach_ok"] or result["drifted"]:
            raise ProbeBlocked(f"{step}: probe 5's confirmed request didn't return that window exactly (missing "
                               f"{result['missing'][:5]}, extra {result['extra'][:5]}, untagged {result['untagged']}) — "
                               "re-run `setup-b` verify / probe 5.")
        found = month_flag_rows(raw)
        in_month = {tag for tag in flagged if start <= written[tag].date <= end}
        months[f"{year}-{month:02d}"] = {
            "returned": result["returned"], "flags": flag_readings(found, in_month, cancelled),
            "lines": {str(tag): {k: found[tag][k] for k in ("ledger_lines", "amounts")} for tag in in_month
                      if tag in found}}
    month_flags = {tag: reading for m in months.values() for tag, reading in m["flags"].items()}

    ctx.observe("count", len(rows))
    ctx.observe("flags", {flag: {"empty": sum(1 for r in rows if not r[flag]), "yes": sum(1 for r in rows if r[flag] == "Yes")}
                          for flag in FLAG_CANDIDATES})
    ctx.observe("header_flagged", header)
    ctx.observe("months", months)
    ctx.observe("others", len(by_tag) - len(flagged & set(by_tag)))
    ctx.observe("prior_evidence", "probe 21 (2026-09-24): 201/202 returned by probe 5's month request, "
                                  "p21_B_fy2022_month_02.xml — recorded there, judged here")

    if empty or not rows:
        return PartResult(Outcome.FAILED, f"flag(s) {', '.join(empty) or 'all'} don't export on every voucher",
                          spec_impact=B_WRONG_FLAG_IMPACT)
    keys = sorted(str(tag) for tag in flagged)
    wrong = [k for k in keys if (header[k]["returned"] and not header[k]["flags_ok"])
             or (month_flags.get(k, {}).get("returned") and not month_flags[k]["flags_ok"])]
    if wrong:
        return PartResult(Outcome.FAILED, f"flagged voucher(s) {', '.join(wrong)} came back without their flag",
                          spec_impact=B_WRONG_FLAG_IMPACT)
    unlisted = [k for k in keys if not header[k]["returned"] or not month_flags.get(k, {}).get("returned")]
    if unlisted:
        kinds = " and ".join(sorted({"cancelled" if int(k) in cancelled else "optional" for k in unlisted}))
        return PartResult(Outcome.DIFFERENT, f"{kinds} voucher(s) {', '.join(unlisted)} are not listed "
                                             "(header read and/or probe 5's month request)",
                          spec_impact=B_NOT_LISTED_IMPACT.format(kinds=kinds))
    return PartResult(Outcome.CONFIRMED, f"cancelled {sorted(cancelled)} and optional {sorted(optional)} carry their "
                                         f"flags on both reads; the other {len(by_tag) - len(flagged)} vouchers "
                                         "carry none", spec_impact=B_CONFIRMED_IMPACT)
```

- [ ] **Step 4: Run** both p03 test files and the whole suite (also `-W error`). Expected ≈ BASE + 20.
- [ ] **Step 5: Commit** (`v2/probes/p03_voucher_ids_flags.py v2/tests/probes/test_p03_b_part.py
  v2/tests/probes/test_p03_voucher_ids_flags.py`): `feat(bi/v2): probe 3 B — cancelled/optional flags on company B`.
  Tracker row 3: "B built (<sha>), not live".

---

### Task 3: Probe 23's B part — credit periods on vouchers and the due-date column of Bills Receivable

**Files:**
- Modify: `v2/probes/p23_gst_due_dates.py`, `v2/tests/probes/test_p23_gst_due_dates.py` (`labels=["A"]` everywhere)
- Create: `v2/tests/probes/test_p23_b_part.py`

**Interfaces:**
- Consumes: Task 1's `bill_terms`, `BillTerm`, `credit_days`, knobs `bill_credit_period_exported`,
  `bill_due_from_credit_period`, `seed_company_b(bills=True)`.
- Produces: `PROBE.parts = {"A": run_a, "B": run_b}`; pure helpers `voucher_credit_periods(raw)`,
  `credit_period_check(found, expected)`, `due_date_check(bills, terms)`. Fixtures `p23_B_bills_credit_period`,
  `p23_B_bills_receivable_due`.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p23_b_part.py`:

```python
from datetime import date
from pathlib import Path

from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p23_gst_due_dates as p23
from v2.probes.capture import Capture
from v2.probes.company_b_view import bill_terms
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]
SYNC = Path(__file__).resolve().parents[1] / "fixtures" / "sync"


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True, bills=True)
    return books


async def _run(tmp_path, books, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    await run_probe(p23.PROBE, labels=["B"], client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(23)["parts"]["B"]


async def test_credit_periods_and_due_dates_agree_with_the_dataset(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["sub_verdicts"] == {"voucher_credit_period": "CONFIRMED", "report_due_date": "CONFIRMED"}
    assert obs["credit_period"]["compared"] >= 2 and obs["credit_period"]["values"] == ["30 Days", "45 Days"]
    assert obs["due_dates"]["compared"] >= 1
    assert part["fixtures"] == ["p23_B_bills_credit_period.xml", "p23_B_bills_receivable_due.xml"]


async def test_a_due_column_that_ignores_the_credit_period_is_different(tmp_path):
    part = await _run(tmp_path, _books(bill_due_from_credit_period=False))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["due_dates"]["as_bill_date"] and "BILLCREDITPERIOD" in part["spec_impact"]


async def test_vouchers_without_credit_periods_are_different(tmp_path):
    part = await _run(tmp_path, _books(bill_credit_period_exported=False))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["credit_period"]["missing"] and "Bills Receivable snapshot" in part["spec_impact"]


async def test_neither_source_fails_and_drops_the_overdue_split(tmp_path):
    part = await _run(tmp_path, _books(bill_credit_period_exported=False, bill_due_from_credit_period=False))
    assert part["outcome"] == "FAILED" and "dropped from v1" in part["spec_impact"]


async def test_a_bill_the_dataset_never_opened_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["bills"].__setitem__("Hand/1", {"party": "Nagpur Wholesale Traders",
                                                                  "amount": "-10.00"}))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "Hand/1" in part["summary"]


async def test_without_probe_5_the_b_part_blocks(tmp_path):
    part = await _run(tmp_path, _books(), with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "probe 5" in part["summary"]


def test_the_live_month_export_carries_credit_periods_that_match_the_dataset():
    """Live shape (p21_B_fy2022_month_02.xml, probe 5's request, window 01..02-02-2023)."""
    found = p23.voucher_credit_periods((SYNC / "p21_B_fy2022_month_02.xml").read_text(encoding="utf-8"))
    assert found["Inv/203"]["credit_period"] == "30 Days" and found["Pur/209"]["credit_period"] == "45 Days"
    expected = {n: t for n, t in bill_terms("educational").items()
                if t.credit_period and not t.flagged and date(2023, 2, 1) <= t.bill_date <= date(2023, 2, 2)}
    assert p23.credit_period_check(found, expected)["verdict"] == "CONFIRMED"
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement.** In `p23_gst_due_dates.py`, replace the docstring's second paragraph with "The B part
  (plan part 6): BillCreditPeriod on the vouchers' New Ref bills, and Bills Receivable's due-date column, both
  against the dataset." Then add:

```python
from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills
from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_TO, BillTerm, bill_terms, credit_days, drift_message,
                                      fetch_window, loaded_licence, month_window, tag_of)
from v2.probes.core import ProbeBlocked
from v2.probes.reads import parse_vouchers, tally_date

CREDIT_MONTH = (2023, 6)             # probe 5's own month: 30-day sales and 45-day purchase New Ref bills
DUE_AS_ON = B_BOOKS_TO               # 31-03-2026, company B's current position (day 31, C43-safe)
IGNORED_BILL_REFS = frozenset({"On Account"})
BOTH_IMPACT = ("Part 3's overdue split has two agreeing sources: each New Ref bill's BILLCREDITPERIOD on the voucher, "
               "and Bills Receivable's due-date column (BILLDUE = bill date + credit period). S1 stores the credit "
               "period on the bill row and reads due dates from the Bills snapshot.")
VOUCHER_ONLY_IMPACT = ("Bills Receivable's due column doesn't carry the credit period: S1 computes due = bill date + "
                       "BILLCREDITPERIOD from the voucher's bill allocation (Part 3 overdue split).")
REPORT_ONLY_IMPACT = ("Voucher bill allocations don't export the credit period: the overdue split reads due dates from "
                      "the Bills Receivable snapshot only (no due date for bills settled before a snapshot).")
NEITHER_IMPACT = ("Neither a credit period nor a due date is readable: the overdue split is dropped from v1, never "
                  "approximated (Part 1 probe 23, Part 3).")


def voucher_credit_periods(raw: str) -> dict[str, dict]:
    """New Ref bill name → {tag, credit_period, bill_date} from a full voucher export (probe 5's month request)."""
    out: dict[str, dict] = {}
    for v in parse_vouchers(raw):
        tag = tag_of(v["header"].get("NARRATION", ""))
        for line in v["ledger_lines"]:
            for bill in line["bills"]:
                if bill.get("BILLTYPE") == "New Ref" and bill.get("NAME"):
                    out[bill["NAME"]] = {"tag": tag, "credit_period": bill.get("BILLCREDITPERIOD", ""),
                                         "bill_date": bill.get("BILLDATE", "")}
    return out


def credit_period_check(found: dict[str, dict], expected: dict[str, BillTerm]) -> dict:
    names = sorted(expected)
    missing = [n for n in names if not found.get(n, {}).get("credit_period")]
    wrong = {n: {"tally": found[n]["credit_period"], "setup": expected[n].credit_period} for n in names
             if n not in missing and credit_days(found[n]["credit_period"]) != expected[n].credit_days}
    values = sorted({found[n]["credit_period"] for n in names if n not in missing})
    ok = bool(names) and not missing and not wrong
    return {"compared": len(names), "missing": missing, "wrong": wrong, "values": values,
            "verdict": "CONFIRMED" if ok else "FAILED"}


def due_date_check(bills: list[dict], terms: dict[str, BillTerm]) -> dict:
    ok, as_bill_date, no_due, unknown, flagged_listed = [], [], [], [], []
    wrong: dict[str, dict] = {}
    opening: dict[str, dict] = {}
    for bill in bills:
        name = bill["bill_number"]
        if name in IGNORED_BILL_REFS:
            continue
        term = terms.get(name)
        if term is None:
            unknown.append(name)
            continue
        if term.flagged:
            flagged_listed.append(name)
            continue
        if term.credit_days is None:                      # the opening bill: recorded, not judged
            opening[name] = {"due": bill["due_date"], "bill_date": bill["bill_date"]}
            continue
        due = tally_date(bill["due_date"])
        if due is None:
            no_due.append(name)
        elif due == term.due:
            ok.append(name)
        elif due == term.bill_date:
            as_bill_date.append(name)
        else:
            wrong[name] = {"tally": bill["due_date"], "setup": term.due.isoformat()}
    compared = len(ok) + len(as_bill_date) + len(no_due) + len(wrong)
    return {"compared": compared, "ok": len(ok), "as_bill_date": sorted(as_bill_date), "no_due": sorted(no_due),
            "wrong": wrong, "unknown": sorted(unknown), "flagged_listed": sorted(flagged_listed), "opening": opening,
            "verdict": "CONFIRMED" if compared and len(ok) == compared else "FAILED"}


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    confirmed = ctx.store.confirmed("voucher_month")
    if confirmed is None:
        raise ProbeBlocked("No confirmed month request: run probe 5 first (S0-D7 — 23 B reads bills with it).")
    terms = bill_terms(licence)
    start, end = month_window(*CREDIT_MONTH, licence)
    result, raw = await fetch_window(ctx, "bills_credit_period", confirmed["xml_template"], licence,
                                     start.strftime("%d-%m-%Y"), end.strftime("%d-%m-%Y"))
    if result["drifted"]:
        raise ProbeBlocked(drift_message("bills_credit_period", result))
    if not result["reach_ok"]:
        raise ProbeBlocked(f"bills_credit_period: probe 5's request didn't return {start}..{end} exactly "
                           f"(missing {result['missing'][:5]}) — re-run probe 5 / `setup-b` verify.")
    expected = {n: t for n, t in terms.items() if t.credit_period and not t.flagged and start <= t.bill_date <= end}
    voucher = credit_period_check(voucher_credit_periods(raw), expected)
    report = await ctx.send("bills_receivable_due", wrap_report("Bills Receivable", B_BOOKS_FROM, DUE_AS_ON,
                                                                ctx.company_name))
    due = due_date_check(parse_bills(report), terms)
    if due["unknown"]:
        raise ProbeBlocked(f"Bills Receivable lists bill(s) {due['unknown'][:5]} the dataset never opened — company B "
                           "drifted; re-run `setup-b` verify or restore the backup.")
    if not due["compared"]:
        raise ProbeBlocked(f"Bills Receivable as-on {DUE_AS_ON} has no open bill with a credit period — nothing to "
                           "compare; re-run `setup-b` verify.")
    subs = {"voucher_credit_period": voucher["verdict"], "report_due_date": due["verdict"]}
    ctx.observe("credit_period", voucher)
    ctx.observe("due_dates", due)
    ctx.observe("sub_verdicts", subs)
    summary = (f"voucher credit periods: {voucher['compared']} New Ref bill(s) in {start:%b %Y} "
               f"({voucher['verdict']}); Bills Receivable due dates: {due['ok']}/{due['compared']} = bill date + "
               f"credit period ({due['verdict']})")
    if subs == {"voucher_credit_period": "CONFIRMED", "report_due_date": "CONFIRMED"}:
        return PartResult(Outcome.CONFIRMED, summary, spec_impact=BOTH_IMPACT)
    if "CONFIRMED" in subs.values():
        impact = VOUCHER_ONLY_IMPACT if voucher["verdict"] == "CONFIRMED" else REPORT_ONLY_IMPACT
        return PartResult(Outcome.DIFFERENT, summary, spec_impact=impact)
    return PartResult(Outcome.FAILED, summary, spec_impact=NEITHER_IMPACT)
```

  Set `parts={"A": run_a, "B": run_b}` (keep `requires=(0,)`).
- [ ] **Step 4: Run** both p23 test files and the suite (also `-W error`). Expected ≈ BASE + 27.
- [ ] **Step 5: Commit** (`v2/probes/p23_gst_due_dates.py v2/tests/probes/test_p23_b_part.py
  v2/tests/probes/test_p23_gst_due_dates.py`): `feat(bi/v2): probe 23 B — credit periods and due dates on company B`.
  Tracker row 23: "B built, not live".

---

### Task 4: Probe 25's B part — `Sales - GST` resolves to Sales, and the R9 duplicate-name UI attempt

**Files:**
- Modify: `v2/probes/p25_masters_classification.py`, `v2/tests/probes/test_p25_masters_classification.py`
  (`labels=["A"]` everywhere)
- Create: `v2/tests/probes/test_p25_b_part.py`

**Interfaces:**
- Consumes: Task 1's `B_CUSTOM_VOUCHER_TYPE(_BASE)`, `r9_candidate`, the knob `voucher_type_parent_exported`, the
  state key `duplicate_ledgers`.
- Produces: `PROBE.parts = {"A": run_a, "B": run_b}`, `mutating=True` (the R9 step asks for a UI create on a
  "Probe" company). Helpers `r9_prompt(name, parent, other)` and `duplicate_name_attempt(ctx, licence) -> dict`.
  Fixtures `p25_B_voucher_types`, `p25_B_ledgers_after_duplicate_attempt`.

R9 is **never** sent over XML (a duplicate create raises a blocking modal, LESSONS §15 rule 10). It is one action-less
`ask`, offered only when the run is interactive and not in auto mode (probe 21's period-lock pattern). What Tally did
is decided by the **read-back**, not by the typed answer.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p25_b_part.py`:

```python
from v2.agent.tally.client import TallyClient
from v2.probes import p25_masters_classification as p25
from v2.probes.capture import Capture
from v2.probes.company_b_view import B_CUSTOM_VOUCHER_TYPE, r9_candidate
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]
NAME, PARENT, OTHER = r9_candidate("educational")


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, io):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p25.PROBE, labels=["B"], client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=io)
    return store.probe_entry(25)["parts"]["B"]


async def test_custom_type_walks_to_sales_and_the_duplicate_is_refused(tmp_path):
    io = ScriptedIO(answers=["Duplicate Entry!"])
    part = await _run(tmp_path, _books(), io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["voucher_type"]["resolved_by"] == "Parent walk" and obs["r9"]["verdict"] == "refused"
    assert NAME in io.asks[0] and OTHER in io.asks[0]
    assert part["fixtures"] == ["p25_B_voucher_types.xml", "p25_B_ledgers_after_duplicate_attempt.xml"]


async def test_a_custom_type_without_a_parent_fails(tmp_path):
    part = await _run(tmp_path, _books(voucher_type_parent_exported=False), ScriptedIO(answers=["Duplicate Entry!"]))
    assert part["outcome"] == "FAILED" and "R16" in part["spec_impact"]


async def test_a_saved_duplicate_is_different_and_names_the_cleanup(tmp_path):
    books = _books()
    books.edit_state(lambda s: s.setdefault("duplicate_ledgers", []).append({"name": NAME, "parent": OTHER}))
    part = await _run(tmp_path, books, ScriptedIO(answers=["saved"]))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert "CLEANUP" in part["summary"] and part["observations"]["r9"]["answer_agrees"] is True
    assert "GUID" in part["spec_impact"]


async def test_the_read_back_wins_over_the_operators_answer(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(answers=["saved"]))
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["r9"]["verdict"] == "refused" and part["observations"]["r9"]["answer_agrees"] is False


async def test_non_interactive_leaves_r9_unmeasured(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(interactive=False))
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["r9"]["status"].startswith("not attempted")
    assert part["fixtures"] == ["p25_B_voucher_types.xml"]


async def test_auto_mode_never_attempts_the_duplicate(tmp_path):
    io = ScriptedIO(run_mode="auto")
    part = await _run(tmp_path, _books(), io)
    assert "auto mode" in part["observations"]["r9"]["status"] and io.asks == []


async def test_skip_leaves_r9_unmeasured(tmp_path):
    part = await _run(tmp_path, _books(), ScriptedIO(answers=["skip"]))
    assert part["outcome"] == "CONFIRMED" and part["observations"]["r9"]["status"] == "skipped by the operator"


async def test_a_missing_custom_voucher_type_blocks(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["voucherTypes"].remove(B_CUSTOM_VOUCHER_TYPE))
    part = await _run(tmp_path, books, ScriptedIO(answers=["Duplicate Entry!"]))
    assert part["outcome"] == "BLOCKED" and B_CUSTOM_VOUCHER_TYPE in part["summary"]
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement.** In `p25_masters_classification.py`, replace the docstring's last sentence with "The B
  part (plan part 6): the custom voucher type 'Sales - GST' must resolve to Sales, plus the R9 duplicate-ledger-name
  UI attempt moved here from the company-B loader (spec §4.3 note, 2026-09-24)." Then add:

```python
from v2.probes.company_b_view import B_CUSTOM_VOUCHER_TYPE, B_CUSTOM_VOUCHER_TYPE_BASE, loaded_licence, r9_candidate
from v2.probes.core import ProbeBlocked

LEDGER_CHECK_FIELDS = ["Name", "Parent"]
RANK = {"CONFIRMED": 0, "DIFFERENT": 1, "FAILED": 2}
B_TYPE_IMPACT = ("S1 derives a custom voucher type's base type by {by} (R16): 'Sales - GST' → Sales — the same "
                 "Parent-chain rule probe 25 A put into the S1 spec.")
B_TYPE_FAILED_IMPACT = ("A custom voucher type's base type can't be read or derived from the export: S1 can't classify "
                        "custom types (R16) and needs another source before their vouchers reach typed tiles.")
R9_REFUSED_IMPACT = ("R9: ledger names are unique within a company (TallyPrime refused the duplicate), so S1's "
                     "name → GUID resolution on ingest is unambiguous.")
R9_ACCEPTED_IMPACT = ("R9: TallyPrime allows two ledgers with one name under different groups: S1 keys ledgers by GUID "
                      "only and resolves a line's ledger name with its parent, or by the GUID on lines (probe 6).")
R9_NOTE = ("Company B: if TallyPrime saved a second ledger {name!r} under {other!r}, delete it (Gateway of Tally → "
           "Alter → Ledger → the one under {other!r} → D: Delete) or restore company B's backup "
           "(s0probe-backups/100000-company-B-loaded-2026-09-24).")


def r9_prompt(name: str, parent: str, other: str) -> str:
    return (f"Probe 25 B, duplicate ledger name (R9). In TallyPrime: Gateway of Tally → Create → Ledger. Name: {name}   "
            f"Under: {other}   (it already exists under {parent}). Try to save it (A: Accept on the right-hand "
            "button bar). Then press Esc until you are back at the Gateway of Tally, answering Yes if TallyPrime "
            "asks to quit without saving. Type TallyPrime's message word for word, or 'saved' if it saved the "
            "ledger, or 'skip' to leave R9 unmeasured.")


async def duplicate_name_attempt(ctx: ProbeContext, licence: str) -> dict:
    if not ctx.io.interactive:
        return {"status": "not attempted (non-interactive)"}
    if ctx.run_mode == "auto":
        return {"status": "not attempted (auto mode: a duplicate create is never sent over XML — it raises a "
                          "blocking modal, LESSONS §15 rule 10)"}
    name, parent, other = r9_candidate(licence)
    note = R9_NOTE.format(name=name, other=other)
    ctx.on_abort(note)
    answer = ctx.ask(r9_prompt(name, parent, other)).strip()
    if answer.lower() == "skip":
        ctx.resolve_abort(note)
        return {"status": "skipped by the operator"}
    rows = read_objects(await ctx.send("ledgers_after_duplicate_attempt", master_request(
        "S0P25BLedgers", "Ledger", LEDGER_CHECK_FIELDS, ctx.company_name)), "LEDGER", LEDGER_CHECK_FIELDS)
    parents = sorted(row["Parent"] for row in rows if row["Name"] == name)
    out = {"status": "attempted", "ledger": name, "existing_parent": parent, "tried_parent": other,
           "tally_message": answer, "parents_after": parents}
    if parents == [parent]:
        out["verdict"] = "refused"
        ctx.resolve_abort(note)
    elif len(parents) > 1 and parent in parents:
        out["verdict"] = "accepted"
        out["cleanup_needed"] = note
    else:
        raise ProbeBlocked(f"Ledger {name!r} now reads under {parents or 'nothing'}, not {parent!r} — company B "
                           f"changed during the R9 attempt. {note}")
    out["answer_agrees"] = (answer.lower() == "saved") == (out["verdict"] == "accepted")
    return out


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    vtypes = read_objects(await ctx.send("voucher_types", master_request(
        "S0P25BVoucherTypes", "VoucherType", VOUCHER_TYPE_FIELDS, ctx.company_name)), "VOUCHERTYPE", VOUCHER_TYPE_FIELDS)
    row = next((r for r in vtypes if r["Name"] == B_CUSTOM_VOUCHER_TYPE), None)
    if row is None:
        raise ProbeBlocked(f"Company B has no voucher type {B_CUSTOM_VOUCHER_TYPE!r} (made in the UI before setup-b, "
                           "spec §4.3) — company B drifted or isn't loaded.")
    walk = ancestors(B_CUSTOM_VOUCHER_TYPE, {r["Name"]: r["Parent"] for r in vtypes if r["Name"]})
    resolved_by = ("ReservedName" if row["ReservedName"] == B_CUSTOM_VOUCHER_TYPE_BASE
                   else "Parent walk" if len(walk) > 1 and walk[-1] == B_CUSTOM_VOUCHER_TYPE_BASE else None)
    ctx.observe("voucher_type", {"name": B_CUSTOM_VOUCHER_TYPE, "parent": row["Parent"],
                                 "reserved_name": row["ReservedName"], "walk": walk, "resolved_by": resolved_by})
    r9 = await duplicate_name_attempt(ctx, licence)
    ctx.observe("r9", r9)

    halves: dict[str, tuple[str, str, str]] = {}
    if resolved_by:
        halves["voucher_type"] = ("CONFIRMED", f"{B_CUSTOM_VOUCHER_TYPE!r} resolves to {B_CUSTOM_VOUCHER_TYPE_BASE} "
                                               f"by {resolved_by}", B_TYPE_IMPACT.format(by=resolved_by))
    else:
        halves["voucher_type"] = ("FAILED", f"{B_CUSTOM_VOUCHER_TYPE!r} doesn't resolve to {B_CUSTOM_VOUCHER_TYPE_BASE} "
                                            f"(Parent {row['Parent']!r}, ReservedName {row['ReservedName']!r})",
                                  B_TYPE_FAILED_IMPACT)
    if r9.get("verdict") == "refused":
        halves["duplicate_name"] = ("CONFIRMED", f"TallyPrime refused a second {r9['ledger']!r} "
                                                 f"({r9['tally_message']!r})", R9_REFUSED_IMPACT)
    elif r9.get("verdict") == "accepted":
        halves["duplicate_name"] = ("DIFFERENT", f"TallyPrime SAVED a second {r9['ledger']!r} under "
                                                 f"{r9['tried_parent']!r} — CLEANUP: {r9['cleanup_needed']}",
                                    R9_ACCEPTED_IMPACT)
    ctx.observe("sub_verdicts", {k: v[0] for k, v in halves.items()} | ({} if "duplicate_name" in halves
                                                                       else {"duplicate_name": r9["status"]}))
    worst = max((v[0] for v in halves.values()), key=RANK.__getitem__)
    summary = "; ".join(f"{k.replace('_', ' ')}: {text} ({verdict})" for k, (verdict, text, _) in halves.items())
    if "duplicate_name" not in halves:
        summary += f"; duplicate name (R9): {r9['status']}"
    impacts = [impact for verdict, _, impact in halves.values() if verdict != "CONFIRMED" or worst == "CONFIRMED"]
    return PartResult(Outcome[worst], summary, spec_impact=" ".join(impacts))
```

  Set `parts={"A": run_a, "B": run_b}` and `mutating=True` (keep `requires=(0,)`).
- [ ] **Step 4: Run** both p25 test files and the suite (also `-W error`). Expected ≈ BASE + 35.
- [ ] **Step 5: Commit** (`v2/probes/p25_masters_classification.py v2/tests/probes/test_p25_b_part.py
  v2/tests/probes/test_p25_masters_classification.py`): `feat(bi/v2): probe 25 B — custom voucher type + R9 attempt`.
  Tracker row 25: "B built, not live".

---

### Task 5: Probe 11 learns C46 — every half judged and named; stock openings scoped like ledger openings

**Files:**
- Create (copy only): `v2/tests/fixtures/sync/c46_p11_live_2026-09-24/` ← `cp -p` of
  `p11_B_ledger_openings.xml(.json)`, `p11_B_opening_bills.xml(.json)`, `p11_B_stock_openings.xml(.json)`
- Modify: `v2/probes/p11_openings.py`, `v2/tests/probes/test_p11_openings.py`

**Interfaces:**
- Consumes: Task 1's `stock_opening_at`, the knob `stock_opening_scope`.
- Produces: `stock_check(rows, specs, units, current_qty)`, `stock_scope(stock) -> dict` (`scope` ∈ `books` /
  `current_period` / `undecided` / `mixed` / `neither`), observations `sub_verdicts`, `stock_scope`. Summary format
  `"ledgers: … (V); opening bill: … (V); stock: … (V)"`.

The rule for the stock half mirrors the ledger half. The books-start opening gives CONFIRMED (the old checks, sign
flip → DIFFERENT). An opening that equals the **current period's** opening, on every item where the two differ, gives
DIFFERENT with the C46 impact: quantity is judged, and rate and value are recorded, not judged (the dataset has no
valuation). Anything else is FAILED. The part outcome is the worst half, and every half is in the summary.

- [ ] **Step 1: Snapshot the live evidence first:**
  `mkdir -p v2/tests/fixtures/sync/c46_p11_live_2026-09-24 && cp -p v2/tests/fixtures/sync/p11_B_{ledger_openings,opening_bills,stock_openings}.xml{,.json} v2/tests/fixtures/sync/c46_p11_live_2026-09-24/`,
  then `cmp` each copy against its original (no output = identical).
- [ ] **Step 2: Write the failing tests.** Append to `v2/tests/probes/test_p11_openings.py` (add `from pathlib
  import Path`, `from v2.tests.probes.fakes import FakeTally, objects_xml`):

```python
SNAPSHOT = Path(__file__).resolve().parents[1] / "fixtures" / "sync" / "c46_p11_live_2026-09-24"


async def test_stock_openings_of_the_current_period_are_different_under_c46(tmp_path):
    part = await _run(tmp_path, _books(stock_opening_scope="current"))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]
    assert obs["stock_scope"]["scope"] == "current_period" and obs["sub_verdicts"]["stock"] == "DIFFERENT"
    assert obs["sub_verdicts"]["ledgers"] == "CONFIRMED" and "C46" in part["spec_impact"]


async def test_every_half_is_named_in_the_summary(tmp_path):
    part = await _run(tmp_path, _books(ledger_opening_scope="fy", stock_opening_scope="current"))
    assert part["outcome"] == "DIFFERENT"
    assert all(label in part["summary"] for label in ("ledgers:", "opening bill:", "stock:"))
    assert "probe 16 B" in part["spec_impact"] and "C46" in part["spec_impact"]


async def test_a_mixed_stock_scope_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["items"]["USB Cable Type-C"].__setitem__("opening_qty", "11 Nos"))  # its 31-03-2025 qty
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and part["observations"]["stock_scope"]["scope"] == "mixed"


async def test_the_2026_09_24_live_capture_relabels_to_different_under_c46(tmp_path):
    """Plan part 6 re-run rule: the new rule on the exact bytes the old rule judged FAILED (stock only)."""
    fake = FakeTally([B])
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{
        "Name": B, "GUID": "g-b", "AltVchId": "1", "AltMstId": "1", "BooksFrom": "20220401",
        "LastVoucherDate": "20260331", "AlterID": "1"}]))
    for marker, name in (("S0P11PartyBills", "p11_B_opening_bills.xml"), ("S0P11Ledgers", "p11_B_ledger_openings.xml"),
                         ("S0P11Stock", "p11_B_stock_openings.xml")):
        data = (SNAPSHOT / name).read_bytes()
        fake.route(marker, lambda body, data=data: data)
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    await run_probe(p11.PROBE, labels=None, client=TallyClient(transport=fake.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=ScriptedIO())
    part = store.probe_entry(11)["parts"]["B"]
    assert part["outcome"] == "DIFFERENT", part["summary"]
    obs = part["observations"]
    assert obs["sub_verdicts"] == {"ledgers": "DIFFERENT", "opening_bill": "CONFIRMED", "stock": "DIFFERENT"}
    assert len(obs["ledgers"]["as_current_fy"]) == 14
    assert obs["stock_scope"]["scope"] == "current_period" and len(obs["stock_scope"]["as_current_period"]) == 5
```

  The six existing tests stay unchanged and must keep passing: the default fake is books-scoped, `100 Nos` is
  "neither" (FAILED), and the sign flip stays DIFFERENT.
- [ ] **Step 3: Run to verify the four new tests fail.**
- [ ] **Step 4: Implement** in `p11_openings.py`. Add `stock_opening_at` to the
  `company_b_view` import, add the two impacts, and replace `stock_check` and the verdict tail of `run_b` (everything
  from `items = read_objects(…)` down) with:

```python
STOCK_CURRENT_IMPACT = ("C46: StockItem OpeningBalance / OpeningRate / OpeningValue are the CURRENT period's opening, "
                        "not the books-start one — S1 may use them only as the current FY's stock opening; a "
                        "books-start stock opening comes from a Stock Summary as-on the books start (probe 18's route), "
                        "never the StockItem master (R5).")
STOCK_UNDECIDED_IMPACT = ("No stock item moved before the current period, so books-start and current-period openings "
                          "can't be told apart here: the StockItem opening's scope stays unmeasured (R5).")
RANK = {"CONFIRMED": 0, "DIFFERENT": 1, "FAILED": 2}


def stock_check(rows: list[dict[str, str]], specs: dict, units: dict[str, str],
                current_qty: dict[str, Decimal]) -> dict[str, dict]:
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
                     "books_qty": want_qty, "current_period_qty": current_qty[name],
                     "qty_ok": qty == want_qty, "qty_current_ok": qty == current_qty[name],
                     "rate_ok": (rate or ZERO) == want_rate, "value_ok": (value or ZERO) == want_value,
                     "value_sign_flipped": want_value != ZERO and value == -want_value}
    return out


def stock_scope(stock: dict[str, dict]) -> dict:
    """Which opening StockItem exports, judged on the items whose books-start and current-period openings differ."""
    telling = sorted(n for n, e in stock.items() if e["books_qty"] != e["current_period_qty"])
    as_books = [n for n in telling if stock[n]["qty_ok"]]
    as_current = [n for n in telling if stock[n]["qty_current_ok"]]
    neither = sorted(n for n, e in stock.items() if not e["qty_ok"] and not e["qty_current_ok"])
    if neither:
        scope = "neither"
    elif not telling:
        scope = "undecided"
    elif len(as_books) == len(telling):
        scope = "books"
    elif len(as_current) == len(telling):
        scope = "current_period"
    else:
        scope = "mixed"
    return {"scope": scope, "telling": len(telling), "as_books": as_books, "as_current_period": as_current,
            "neither": neither}


def _ledger_half(ledgers: dict) -> tuple[str, str, str]:
    if not ledgers["mismatched"]:
        return "CONFIRMED", f"{ledgers['compared']} openings equal setup's books-start openings", ""
    if set(ledgers["as_current_fy"]) == set(ledgers["mismatched"]):
        return ("DIFFERENT", f"OpeningBalance equals the current FY's opening for {len(ledgers['mismatched'])} "
                             "ledger(s)", LEDGER_FY_IMPACT)
    return "FAILED", f"OpeningBalance ≠ setup for {', '.join(sorted(ledgers['mismatched'])[:5])}", LEDGER_FAILED_IMPACT


def _bill_half(opening_bill: dict) -> tuple[str, str, str]:
    bill = opening_bill["bill"]
    if opening_bill["candidate"]["magnitude_match"]:
        return "CONFIRMED", f"{bill!r} (₹{abs(opening_bill['expected'])}) on the ledger master", ""
    if opening_bill.get("report", {}).get("magnitude_match"):
        return "DIFFERENT", f"{bill!r} only in Bills Receivable as-on {OPENING_BILLS_AS_ON}", BILL_REPORT_IMPACT
    return "FAILED", f"{bill!r} found neither on the ledger nor in Bills Receivable", BILL_FAILED_IMPACT


def _stock_half(stock: dict[str, dict], scope: dict) -> tuple[str, str, str]:
    if scope["scope"] == "books":
        bad = sorted(n for n, e in stock.items() if not (e["rate_ok"] and (e["value_ok"] or e["value_sign_flipped"])))
        flipped = sorted(n for n, e in stock.items() if e["value_sign_flipped"] and not e["value_ok"])
        if bad:
            return "FAILED", f"openings ≠ setup's rate/value for {', '.join(bad)}", STOCK_FAILED_IMPACT
        if flipped:
            return "DIFFERENT", f"OpeningValue exported positive for {', '.join(flipped)}", STOCK_SIGN_IMPACT
        return "CONFIRMED", f"{len(stock)} openings equal what setup-b wrote", ""
    if scope["scope"] == "current_period":
        return ("DIFFERENT", f"openings are the current period's (as at {B_CURRENT_PERIOD[0]}) for "
                             f"{len(scope['as_current_period'])} item(s), not the books-start ones (C46)",
                STOCK_CURRENT_IMPACT)
    if scope["scope"] == "undecided":
        return "DIFFERENT", "books-start and current-period openings are equal on every item", STOCK_UNDECIDED_IMPACT
    names = scope["neither"] or sorted(scope["as_books"] + scope["as_current_period"])
    return ("FAILED", f"openings ≠ setup for {', '.join(names)}" if scope["neither"]
            else f"openings mix books-start and current-period values ({', '.join(names)})", STOCK_FAILED_IMPACT)
```

  and the new tail of `run_b`:

```python
    items = read_objects(await ctx.send("stock_openings", master_request("S0P11Stock", "StockItem", STOCK_FIELDS,
                                                                         company)), "STOCKITEM", STOCK_FIELDS)
    item_names = item_specs(licence)
    current = {n: stock_opening_at(licence, n, B_CURRENT_PERIOD[0]) for n in item_names}
    stock = stock_check(items, item_names, {n: qty_unit(licence, n) for n in item_names}, current)
    ctx.observe("stock", stock)
    absent = sorted(n for n, e in stock.items() if not e["present"])
    if absent:
        raise ProbeBlocked(f"Company B is missing stock item(s) {absent} — re-run `setup-b` verify or restore the backup.")
    scope = stock_scope(stock)
    ctx.observe("stock_scope", scope)

    halves = {"ledgers": _ledger_half(ledgers), "opening_bill": _bill_half(opening_bill),
              "stock": _stock_half(stock, scope)}
    ctx.observe("sub_verdicts", {k: v[0] for k, v in halves.items()})
    worst = max((v[0] for v in halves.values()), key=RANK.__getitem__)
    summary = "; ".join(f"{k.replace('_', ' ')}: {text} ({verdict})" for k, (verdict, text, _) in halves.items())
    impacts = " ".join(impact for verdict, _, impact in halves.values() if verdict != "CONFIRMED" and impact)
    return PartResult(Outcome[worst], summary, spec_impact=impacts or CONFIRMED_IMPACT)
```

  Also update the module docstring. Add one sentence: "C46 (live 2026-09-24): StockItem opening fields are the current
  period's opening. The stock half judges that scope the way the ledger half judges OpeningBalance's, and every half
  is named in the summary (the 2026-09-24 run's FAILED stock half hid a DIFFERENT ledger half)."
- [ ] **Step 5: Run** `test_p11_openings.py` and the suite (also `-W error`). Expected ≈ BASE + 39.
- [ ] **Step 6: Commit** (`v2/probes/p11_openings.py v2/tests/probes/test_p11_openings.py
  v2/tests/fixtures/sync/c46_p11_live_2026-09-24/`): `feat(bi/v2): probe 11 learns C46 — every half judged and named`.
  Tracker row 11: "rule updated (<sha>); relabel test: live evidence → DIFFERENT; live re-run in Task 9".

---

### Task 6: Company C's tiny loader (`setup-c`) and the operator's label guard

**Files:**
- Create: `v2/probes/setup/company_c.py`, `v2/tests/probes/test_company_c.py`
- Modify: `v2/probes/setup/writes.py` (`list_vouchers`; `voucher` uses it), `v2/probes/__main__.py` (`setup-c`),
  `v2/probes/operator/tally_control.py` (label guard), `v2/tests/probes/test_cli.py`,
  `v2/tests/probes/test_tally_control.py`

**Interfaces:**
- Consumes: Task 1's `COMPANY_C_*` constants; existing `TallyWriter.create_ledger`, `create_payment`, `ledger`,
  `company_names`, `check_writable`.
- Produces: `load_company_c(writer, company=COMPANIES["C"]) -> CReport(created: list[str], skipped: list[str])`,
  `CompanyCLoadError`; CLI `python -m v2.probes setup-c` (exit 0 only on a clean load, records
  `environment.company_c_loaded_at`); `TallyWriter.list_vouchers(company) -> list[dict[str, str]]`;
  `TallyControl.start/restart` refuse a label with no configured company number **before** stopping or starting
  anything.

Company C is **not** added to `OperatorConfig.company_numbers`. It is opened by hand only. With security or TallyVault
on, a `/LOAD` start stops at the login/vault prompt, and `wait_for_companies` would wait out its 15-minute window
against a modal that no licence click clears. Today `restart("C")` stops Tally first and only then fails with a
`KeyError`. The guard makes it refuse up front.

- [ ] **Step 1: Write the failing tests.** `v2/tests/probes/test_company_c.py`:

```python
import pytest

from v2.probes.companies import COMPANIES, COMPANY_C_LEDGER, COMPANY_C_LEDGER_PARENT, COMPANY_C_VOUCHER_NARRATION
from v2.probes.setup.company_c import CompanyCLoadError, load_company_c
from v2.probes.setup.writes import TallyWriter
from v2.tests.probes.fake_books import FakeBooks, sync_client

C = COMPANIES["C"]


def _writer(books: FakeBooks) -> TallyWriter:
    return TallyWriter(sync_client(books.transport()), say=lambda message: None)


def _imports(books: FakeBooks, since: int = 0) -> list[str]:
    return [r for r in books.requests[since:] if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in r]


def test_first_load_creates_the_ledger_and_the_voucher():
    books = FakeBooks(name=C, educational=True)
    report = load_company_c(_writer(books))
    assert report.created == ["ledger", "voucher"] and report.skipped == []
    state = books.state
    assert state["ledgers"][COMPANY_C_LEDGER]["parent"] == COMPANY_C_LEDGER_PARENT
    assert [v["narration"] for v in state["vouchers"].values()] == [COMPANY_C_VOUCHER_NARRATION]


def test_a_second_load_writes_nothing():
    books = FakeBooks(name=C, educational=True)
    load_company_c(_writer(books))
    before = len(books.requests)
    report = load_company_c(_writer(books))
    assert report.created == [] and report.skipped == ["ledger", "voucher"] and _imports(books, before) == []


def test_another_open_company_is_refused_before_any_write():
    books = FakeBooks(name=COMPANIES["B"])
    with pytest.raises(CompanyCLoadError, match="open"):
        load_company_c(_writer(books))
    assert _imports(books) == []


def test_the_ledger_under_another_group_is_a_problem_not_a_second_create():
    books = FakeBooks(name=C)
    books.edit_state(lambda s: s["ledgers"].__setitem__(COMPANY_C_LEDGER, {
        "parent": "Sundry Debtors", "email": "", "alter_id": 1, "guid": "g", "opening": "0.00"}))
    with pytest.raises(CompanyCLoadError, match="Sundry Debtors"):
        load_company_c(_writer(books))
    assert _imports(books) == []
```

  Append to `test_cli.py` (add imports `from v2.probes.companies import COMPANIES` and
  `from v2.tests.probes.fake_books import FakeBooks` if missing):

```python
def test_setup_c_loads_company_c(tmp_path, capsys):
    books = FakeBooks(name=COMPANIES["C"], educational=True)
    assert main(["--results", str(tmp_path / "r.json"), "setup-c"], transport=books.transport()) == 0
    assert "Company C loaded" in capsys.readouterr().out
    assert ResultsStore(tmp_path / "r.json").environment["company_c_loaded_at"]


def test_setup_c_refuses_when_another_company_is_open(tmp_path, capsys):
    books = FakeBooks(name=COMPANIES["B"])
    assert main(["--results", str(tmp_path / "r.json"), "setup-c"], transport=books.transport()) == 1
    assert "setup-c failed" in capsys.readouterr().out
```

  Append to `test_tally_control.py`:

```python
def test_restart_refuses_a_company_with_no_number_before_stopping_tally(tmp_path):
    books = FakeBooks(name=A)
    control, runner, _ = _control(tmp_path, books, [TallyProcess(7, OWN_COMMAND)])
    ini = tmp_config(tmp_path).tally_dir / "tally.ini"
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_bytes(b"Default Companies=Yes\r\nLoad=100000\r\n")
    with pytest.raises(OperatorError, match="opened by hand only"):
        control.restart("C", [COMPANIES["C"]])
    assert runner.terminated == [] and runner.spawned == [] and books.running
    assert ini.read_bytes() == b"Default Companies=Yes\r\nLoad=100000\r\n"
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement.**

  `v2/probes/setup/company_c.py`:

```python
"""Company C's tiny, idempotent loader (S0 spec §4.4; plan part 6): one expense ledger and one Payment voucher.

The company shell is created by hand in the TallyPrime UI (company creation can't be scripted), security and TallyVault
are switched on by hand during probe 24, and no credential ever passes through here. Writes use only verified shapes
(`TallyWriter.create_ledger`, `create_payment`, docs/tally-write-exploration-v4.md) and read each one back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from v2.probes.companies import (COMPANIES, COMPANY_C_LEDGER, COMPANY_C_LEDGER_PARENT, COMPANY_C_VOUCHER_AMOUNT,
                                 COMPANY_C_VOUCHER_DATE, COMPANY_C_VOUCHER_NARRATION)
from v2.probes.setup.writes import TallyWriter, check_writable


class CompanyCLoadError(Exception):
    """setup-c refused or found company C in a state it won't write over."""


@dataclass
class CReport:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def load_company_c(writer: TallyWriter, company: str = COMPANIES["C"]) -> CReport:
    check_writable(company)                                   # before any request at all
    loaded = writer.company_names()
    if loaded != [company]:
        raise CompanyCLoadError(f"Tally has {loaded} open; open only {company!r} (K: Company → Select) and shut every "
                                "other company first.")
    report = CReport()
    ledger = writer.ledger(company, COMPANY_C_LEDGER)
    if ledger is None:
        writer.create_ledger(company, COMPANY_C_LEDGER, COMPANY_C_LEDGER_PARENT)
        report.created.append("ledger")
    elif ledger["Parent"] != COMPANY_C_LEDGER_PARENT:
        raise CompanyCLoadError(f"Ledger {COMPANY_C_LEDGER!r} exists under {ledger['Parent']!r}, not "
                                f"{COMPANY_C_LEDGER_PARENT!r} — fix it in the UI; setup-c never re-creates a master "
                                "(LESSONS §15 rule 10).")
    else:
        report.skipped.append("ledger")
    if any(row["Narration"] == COMPANY_C_VOUCHER_NARRATION for row in writer.list_vouchers(company)):
        report.skipped.append("voucher")
    else:
        writer.create_payment(company, ledger=COMPANY_C_LEDGER, amount=Decimal(COMPANY_C_VOUCHER_AMOUNT),
                              narration=COMPANY_C_VOUCHER_NARRATION, date=COMPANY_C_VOUCHER_DATE)
        report.created.append("voucher")
    return report
```

  `writes.py`: replace `voucher()` with:

```python
    def list_vouchers(self, company: str) -> list[dict[str, str]]:
        """Every voucher in the read-back window (READBACK_FROM..READBACK_TO, typed — C33), header fields only."""
        xml = wrap_collection("S0OpVouchers", "Voucher", VOUCHER_FIELDS, company,
                              static_vars={"SVFROMDATE": READBACK_FROM, "SVTODATE": READBACK_TO},
                              extra_collection_xml="<CHILDOF>$$VchTypeAllVouchers</CHILDOF>")
        return read_objects(self.post(xml), "VOUCHER", VOUCHER_FIELDS)

    def voucher(self, company: str, master_id: str) -> dict[str, str] | None:
        return next((row for row in self.list_vouchers(company) if row["MasterId"] == master_id), None)
```

  `__main__.py`: add `setup-c` to the docstring's command list. Add
  `sub.add_parser("setup-c", help="company C's one ledger + one voucher (S0 spec §4.4) — open only company C first")`
  in `build_parser`, `if args.command == "setup-c": return _setup_c(args, store, transport)` in `main` (next to
  `setup-b`), and:

```python
def _setup_c(args, store: ResultsStore, transport) -> int:
    from v2.probes.safety import GuardError
    from v2.probes.setup.company_c import CompanyCLoadError, load_company_c
    from v2.probes.setup.writes import TallyWriter, WriteFailed, WriteRefused
    http = httpx.Client(base_url=f"http://{args.host}:{args.port}", transport=transport, trust_env=False)
    try:
        report = load_company_c(TallyWriter(http, say=print))
    except (CompanyCLoadError, WriteFailed, WriteRefused, GuardError) as exc:
        print(f"setup-c failed: {exc}")
        return 1
    finally:
        http.close()
    print(f"Created: {', '.join(report.created) or 'nothing'}; already there: {', '.join(report.skipped) or 'nothing'}")
    store.update_environment(company_c_loaded_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    print(f"Company C loaded: {COMPANIES['C']!r} is ready.")
    return 0
```

  `tally_control.py`: add a method and call it first in `start()` and in `restart()` (before `self.stop()`):

```python
    def _require_number(self, load_label: str | None) -> None:
        if load_label is not None and load_label not in self.config.company_numbers:
            raise OperatorError(f"No company number configured for company {load_label}: it is opened by hand only "
                                "(company C — a security login or TallyVault prompt would block an unattended start; "
                                "S0 plan part 6).")
```

- [ ] **Step 4: Run** the three test files and the suite (also `-W error`). Expected ≈ BASE + 46. Also run
  `test_isolation.py`: `company_c.py` lives in `setup/`, so probe modules must not import it.
- [ ] **Step 5: Commit** (`v2/probes/setup/company_c.py v2/probes/setup/writes.py v2/probes/__main__.py
  v2/probes/operator/tally_control.py v2/tests/probes/test_company_c.py v2/tests/probes/test_cli.py
  v2/tests/probes/test_tally_control.py`): `feat(bi/v2): setup-c (company C) + operator refuses unnumbered labels`.
  Tracker change-log row.

---

### Task 7: Probe 24 — secured companies (security, then TallyVault), manual only

**Files:**
- Create: `v2/probes/p24_secured_company.py`, `v2/tests/probes/test_p24_secured_company.py`
- Modify: `v2/probes/registry.py` (`ProbeInfo(24, "secured_company", "C", "B", module="v2.probes.p24_secured_company")`)

**Interfaces:**
- Consumes: probe 2's `active_company`, probe 1's `company_counters`, probe 5's `voucher_month` (S0-D7: probe 24 never
  builds its own identity/voucher request); `COMPANY_C_*`; Task 1's `seed_company_c` and `S0ActiveCompany` route.
- Produces: `PROBE` (id 24, parts `{"C": run_c}`, `requires=(0, 1, 2, 5)`, `mutating=True`); pause constants
  `SECURITY_ON`, `SECURITY_RESELECT`, `LOGIN`, `VAULT_ON`, `VAULT_RESELECT`, `VAULT_OPEN`; helpers `export(ctx,
  stage)`, `pending(ctx, stage)`. Fixtures `p24_C_{baseline,security_on,vault_on}_{company_list,active_company,
  counters,ledgers,vouchers}` and `p24_C_{security_login_pending,vault_password_pending}_{company_list,active_company}`.

**Export** (spec §7 "export") means five reads per stage, all through `try_send` so that a refusal is recorded as a
shape: the company list, the active-company GUID (probe 2's request), the counters (probe 1's request), the ledger
list, and the vouchers (probe 5's request, 01-04-2025..31-03-2026). **Pending** means the two cheap gate reads (company
list and active company) sent with a 10-second timeout while TallyPrime shows the login or TallyVault prompt. That is
the new gate error shape the spec asks for.

- [ ] **Step 1: Write the failing tests** in `v2/tests/probes/test_p24_secured_company.py`:

```python
from v2.agent.tally.client import TallyClient
from v2.probes import p02_active_company_guid as p02
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p24_secured_company as p24
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_c
from v2.tests.probes.fakes import ScriptedIO, mark_done, ready_store

C = COMPANIES["C"]
ALL_PAUSES = [p24.SECURITY_ON, p24.SECURITY_RESELECT, p24.LOGIN, p24.VAULT_ON, p24.VAULT_RESELECT, p24.VAULT_OPEN]


def _books() -> FakeBooks:
    books = FakeBooks(name=C, educational=True)
    seed_company_c(books)
    return books


def operator(books: FakeBooks, *, prompt: str = "modal", after_vault=None, after_login=None):
    """Plays the person at TallyPrime: a prompt either blocks the XML server (modal) or leaves no company open."""
    def act(text: str) -> None:
        if text in (p24.SECURITY_RESELECT, p24.VAULT_RESELECT):
            if prompt == "modal":
                books.popup = True
            else:
                books.loaded = False
        elif text in (p24.LOGIN, p24.VAULT_OPEN):
            books.popup, books.loaded = False, True
            hook = after_vault if text == p24.VAULT_OPEN else after_login
            if hook:
                hook(books)
    return act


async def _run(tmp_path, books, io, *, confirm_active=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    if confirm_active:
        store.confirm_request("active_company", 2, p02.CANDIDATES["a"], candidate="a")
    mark_done(store, 5, part="B")
    store.confirm_request("voucher_month", 5, p05.svdates_template(), form="svdates_typed")
    await run_probe(p24.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=io)
    return store.probe_entry(24)["parts"]["C"]


async def test_security_and_vault_leave_export_unchanged(tmp_path):
    books = _books()
    io = ScriptedIO(on_wait=operator(books))
    part = await _run(tmp_path, books, io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert io.waits == ALL_PAUSES
    shapes = part["observations"]["gate_shapes"]
    assert shapes["security_login_pending"]["company_list"]["transport"] == "timeout"
    assert shapes["vault_password_pending"]["active_company"]["transport"] == "timeout"
    assert "No credentials" in part["spec_impact"]
    assert "p24_C_baseline_vouchers.xml" in part["fixtures"]
    assert any(f.startswith("p24_C_security_login_pending_company_list") for f in part["fixtures"])


async def test_a_prompt_that_answers_with_no_company_is_recorded(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, prompt="closed")))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    shape = part["observations"]["gate_shapes"]["security_login_pending"]["company_list"]
    assert shape == {"transport": "answered", "body": {"companies": []}}


async def test_a_new_guid_after_the_vault_is_different_and_points_at_relink(tmp_path):
    books = _books()
    rekey = lambda b: b.edit_state(lambda s: s.__setitem__("guid", "vaulted-guid"))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_vault=rekey)))
    assert part["outcome"] == "DIFFERENT" and "Q25" in part["spec_impact"]


async def test_an_empty_export_after_the_vault_fails(tmp_path):
    books = _books()
    empty = lambda b: b.edit_state(lambda s: (s["ledgers"].clear(), s["vouchers"].clear()))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_vault=empty)))
    assert part["outcome"] == "FAILED" and "tallyvault" in part["summary"].lower()


async def test_another_company_open_after_login_blocks(tmp_path):
    books = _books()
    other = lambda b: b.edit_state(lambda s: (s.__setitem__("name", "Other Co"), s.__setitem__("guid", "other")))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_login=other)))
    assert part["outcome"] == "BLOCKED" and "Other Co" in part["summary"]


async def test_company_c_without_setup_c_blocks(tmp_path):
    books = FakeBooks(name=C, educational=True)         # no seed_company_c: no S0 ledger, no voucher
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books)))
    assert part["outcome"] == "BLOCKED" and "setup-c" in part["summary"]


async def test_auto_mode_is_refused(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(run_mode="auto"))
    assert part["outcome"] == "BLOCKED" and "manual" in part["summary"]


async def test_without_probe_2s_request_it_blocks(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books)), confirm_active=False)
    assert part["outcome"] == "BLOCKED" and "probe 2" in part["summary"]


async def test_probe_24_never_asks_for_or_sends_a_credential(tmp_path):
    books = _books()
    io = ScriptedIO(on_wait=operator(books))
    await _run(tmp_path, books, io)
    assert io.asks == []
    for sidecar in (tmp_path / "fixtures").glob("p24_C_*.json"):
        text = sidecar.read_text(encoding="utf-8").lower()
        assert "password" not in text and "username" not in text, sidecar.name
```

- [ ] **Step 2: Run to verify they fail** (`ModuleNotFoundError`).
- [ ] **Step 3: Implement** `v2/probes/p24_secured_company.py`:

```python
"""Probe 24 — secured companies (S0 spec §7 "Probe 24", company C). Feeds R2, R26 (Part 1 §12 item 24: does XML
export still work without extra credentials once the company is open, and do the error shapes differ?).

Manual only. Security and TallyVault are switched on in the TallyPrime UI, and a secured company's login / TallyVault
prompt would stop an unattended start (C44's Load= would reopen company C at the prompt), so `--auto` is refused. The
harness never asks for, stores or sends a username or password: the person types them into TallyPrime only.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, build_company_list, esc
from v2.agent.tally.xml_utils import detect_error, parse_company_list, read_objects
from v2.probes.companies import (COMPANIES, COMPANY_C_BOOKS_FROM, COMPANY_C_BOOKS_TO, COMPANY_C_LEDGER,
                                 COMPANY_C_VOUCHER_NARRATION)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import fill_month_request, master_request, parse_vouchers

C = COMPANIES["C"]
PENDING_TIMEOUT = 10.0
RANK = {"CONFIRMED": 0, "DIFFERENT": 1, "FAILED": 2}
NEEDED = (("active_company", 2), ("company_counters", 1), ("voucher_month", 5))
AUTO_REFUSED = ("Probe 24 is manual only: security and TallyVault are switched on in the TallyPrime UI, and their "
                "prompts block an unattended start. Run `run 24` without --auto, at the Mac.")
BASELINE_DRIFT = ("Company C isn't as `setup-c` leaves it (ledgers {ledgers}, vouchers {narrations}, errors {errors}) — "
                  "run `python -m v2.probes setup-c` with only {company!r} open.")
SECURITY_ON = (f"Probe 24, step 1 — turn on security for {C!r}. In TallyPrime: K: Company → Alter → {C}. Set "
               "'Control user access to company data' to Yes, type a THROWAWAY username and password (never a real one; "
               "do not type them here or anywhere in the repo), repeat the password, and accept the screen (A: Accept). "
               "Log in if TallyPrime asks. Press Enter here once company C is open and you are at the Gateway of Tally.")
SECURITY_RESELECT = (f"Probe 24, step 2 — K: Company → Shut → {C}. Then K: Company → Select → {C}. STOP at the login "
                     "box: leave it open (do not log in yet) and press Enter here.")
LOGIN = "Probe 24, step 3 — log in to company C now, wait for the Gateway of Tally, then press Enter here."
VAULT_ON = (f"Probe 24, step 4 — turn on TallyVault for {C!r}: K: Company → Change TallyVault → {C}. Type a THROWAWAY "
            "TallyVault password twice (again: never here, never in the repo) and accept. If TallyPrime shuts or "
            "reopens the company, open it again (TallyVault password, then your login). Press Enter here once company "
            "C is open at the Gateway of Tally.")
VAULT_RESELECT = (f"Probe 24, step 5 — K: Company → Shut → {C}. Then K: Company → Select → {C}. STOP at the "
                  "TallyVault password box: leave it open and press Enter here.")
VAULT_OPEN = ("Probe 24, step 6 — type the TallyVault password (and your login when asked), wait for the Gateway of "
              "Tally, then press Enter here.")
UNDO_NOTE = ("Company C has security and/or TallyVault on (the throwaway credentials you chose). Nothing to undo in "
             "Tally: plan part 6 Task 11 archives company C's folder; to redo probe 24 restore "
             "s0probe-backups/<C number>-company-C-baseline-<date> first.")


def _parse(read: str, text: str | None) -> Any:
    if text is None:
        return None
    try:
        if read == "company_list":
            return parse_company_list(text)
        if read in ("active_company", "counters"):
            return [r for r in read_objects(text, "COMPANY", ["Name", "GUID"]) if r["Name"] or r["GUID"]]
        if read == "ledgers":
            return sorted(r["Name"] for r in read_objects(text, "LEDGER", ["Name"]) if r["Name"])
        return sorted(v["header"].get("NARRATION", "") for v in parse_vouchers(text))
    except ET.ParseError:
        return {"unparseable": text[:200]}


def _requests(ctx: ProbeContext) -> dict[str, str]:
    template = lambda name: ctx.store.confirmed(name)["xml_template"].replace(COMPANY_PLACEHOLDER, esc(C))
    return {"company_list": build_company_list(), "active_company": template("active_company"),
            "counters": template("company_counters"),
            "ledgers": master_request("S0P24Ledgers", "Ledger", ["Name", "Parent"], C),
            "vouchers": fill_month_request(ctx.store.confirmed("voucher_month")["xml_template"], C,
                                           COMPANY_C_BOOKS_FROM, COMPANY_C_BOOKS_TO)}


async def export(ctx: ProbeContext, stage: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    errors: dict[str, dict] = {}
    for read, xml in _requests(ctx).items():
        text, error = await ctx.try_send(f"{stage}_{read}", xml)
        if error:
            errors[read] = error
        elif detect_error(text):
            errors[read] = {"kind": "tally_error", "message": detect_error(text)}
        parsed[read] = _parse(read, text)
    active = parsed["active_company"] if isinstance(parsed["active_company"], list) else []
    counters = [r for r in (parsed["counters"] if isinstance(parsed["counters"], list) else []) if r["Name"] == C]
    out = {"stage": stage, "companies": parsed["company_list"], "errors": errors,
           "active_guid": active[0]["GUID"] if len(active) == 1 else "",
           "counters_guid": counters[0]["GUID"] if counters else "",
           "ledgers": parsed["ledgers"] if isinstance(parsed["ledgers"], list) else [],
           "narrations": parsed["vouchers"] if isinstance(parsed["vouchers"], list) else []}
    out["ok"] = (not errors and out["companies"] == [C] and bool(out["active_guid"])
                 and out["active_guid"] == out["counters_guid"] and COMPANY_C_LEDGER in out["ledgers"]
                 and COMPANY_C_VOUCHER_NARRATION in out["narrations"])
    return out


async def pending(ctx: ProbeContext, stage: str) -> dict[str, Any]:
    """The gate's two cheap reads while a login / TallyVault prompt is on screen (a new gate shape, spec §7)."""
    shapes: dict[str, Any] = {}
    requests = _requests(ctx)
    for read in ("company_list", "active_company"):
        text, error = await ctx.try_send(f"{stage}_{read}", requests[read], timeout=PENDING_TIMEOUT)
        if error:
            shapes[read] = {"transport": error["kind"], "body": None}
        else:
            body = _parse(read, text)
            shapes[read] = {"transport": "answered",
                            "body": {"companies": body} if read == "company_list" else {"rows": body}}
    return shapes


def _slip(stage: dict[str, Any], baseline_guid: str) -> None:
    names = stage["companies"] or []
    if len(names) > 1 or (names and names != [C] and stage["active_guid"] != baseline_guid):
        raise ProbeBlocked(f"{stage['stage']}: Tally has {names} open, not only {C!r} — open only company C and re-run "
                           "probe 24 (restore the company-C baseline backup first if security/TallyVault is on).")


def _judge(stage: dict[str, Any], baseline: dict[str, Any]) -> tuple[str, str]:
    if not stage["ok"]:
        why = ", ".join(f"{k}: {v['kind']}" for k, v in stage["errors"].items()) or (
            f"listed as {stage['companies']}, ledgers {stage['ledgers'][:3]}, vouchers {stage['narrations'][:2]}")
        return "FAILED", f"export doesn't work with the company open ({why})"
    changed = [k for k in ("active_guid", "ledgers", "narrations") if stage[k] != baseline[k]]
    return ("DIFFERENT", f"export works but {', '.join(changed)} changed") if changed else ("CONFIRMED", "export unchanged")


def _shape_text(shapes: dict[str, Any]) -> str:
    listing = shapes["company_list"]
    if listing["transport"] != "answered":
        return f"a {listing['transport']} (the prompt blocks the XML server)"
    return f"an answer listing {listing['body']['companies']} (as if no company were open)"


async def run_c(ctx: ProbeContext) -> PartResult:
    for name, probe_id in NEEDED:
        if ctx.store.confirmed(name) is None:
            raise ProbeBlocked(f"No confirmed {name} request: run probe {probe_id} first (S0-D7).")
    if ctx.run_mode == "auto":
        raise ProbeBlocked(AUTO_REFUSED)
    baseline = await export(ctx, "baseline")
    ctx.observe("baseline", baseline)
    if not baseline["ok"]:
        raise ProbeBlocked(BASELINE_DRIFT.format(ledgers=baseline["ledgers"], narrations=baseline["narrations"],
                                                 errors=baseline["errors"], company=C))
    ctx.on_abort(UNDO_NOTE)
    ctx.pause(SECURITY_ON)
    ctx.pause(SECURITY_RESELECT)
    login_pending = await pending(ctx, "security_login_pending")
    ctx.pause(LOGIN)
    security = await export(ctx, "security_on")
    _slip(security, baseline["active_guid"])
    ctx.pause(VAULT_ON)
    ctx.pause(VAULT_RESELECT)
    vault_pending = await pending(ctx, "vault_password_pending")
    ctx.pause(VAULT_OPEN)
    vault = await export(ctx, "vault_on")
    _slip(vault, baseline["active_guid"])

    halves = {"security": _judge(security, baseline), "TallyVault": _judge(vault, baseline)}
    shapes = {"security_login_pending": login_pending, "vault_password_pending": vault_pending}
    ctx.observe("security_on", security)
    ctx.observe("vault_on", vault)
    ctx.observe("gate_shapes", shapes)
    ctx.observe("sub_verdicts", {k: v[0] for k, v in halves.items()})
    worst = max((v[0] for v in halves.values()), key=RANK.__getitem__)
    login, vault_shape = _shape_text(login_pending), _shape_text(vault_pending)
    summary = (f"security on: {halves['security'][1]} ({halves['security'][0]}); TallyVault on: "
               f"{halves['TallyVault'][1]} ({halves['TallyVault'][0]}); login prompt → {login}; TallyVault prompt → "
               f"{vault_shape}")
    gate = (f"While a login prompt is open the gate sees {login}; while a TallyVault prompt is open, {vault_shape}. "
            "S2's gate treats both as 'company not open' (skip quietly, retry next cycle).")
    if worst == "CONFIRMED":
        impact = ("No credentials in the agent (R2, R26): once the person has logged in / entered the TallyVault "
                  "password in TallyPrime, XML export of a secured or vaulted company is unchanged (same GUID, same "
                  f"data). {gate} Onboarding: open the company in TallyPrime as usual.")
    elif worst == "DIFFERENT":
        impact = ("Export works once the company is open, but its identity/content changed: a new GUID with the same "
                  f"name takes the re-link path (Q25), never a new company. {gate}")
    else:
        failed = " and ".join(k for k, v in halves.items() if v[0] == "FAILED")
        impact = (f"XML export of a company with {failed} fails even with it open in TallyPrime: v1 can't sync such "
                  f"companies — onboarding says so, and the gate reports it as its own condition (R26). {gate}")
    return PartResult(Outcome[worst], summary, spec_impact=impact)


PROBE = Probe(
    id=24,
    name="secured_company",
    question="Does XML export still work for a company with security and then TallyVault, once it is open, and what "
             "does the gate see while TallyPrime waits for the login / vault password?",
    feeds=("R2", "R26"),
    parts={"C": run_c},
    requires=(0, 1, 2, 5),
    mutating=True,
)
```

- [ ] **Step 4: Run** the new file, `test_cli.py` (`list` now shows 24 as `not run`) and the suite (also `-W error`).
  Expected ≈ BASE + 55.
- [ ] **Step 5: Commit** (`v2/probes/p24_secured_company.py v2/tests/probes/test_p24_secured_company.py
  v2/probes/registry.py`): `feat(bi/v2): probe 24 — secured companies (security, TallyVault), manual only`. Tracker
  row 24: "built, not live".

---

### Task 8: Code review (before any live run)

**Files:** Create `docs/code-review-bi-s0-part6-<YYYY-MM-DD>.md`.

- [ ] **Step 1:** Run `superpowers:requesting-code-review` (or the `code-review` agent, opus) on
  `git diff 4a735b8..HEAD -- v2/`. Ask the reviewer to check at least:
  - each knob default against **recorded** live behaviour vs **hypothesis** (Task 1's table), and that nothing
    weakens C33/C43 in `FakeBooks`;
  - byte-identity of the old bill and voucher exports (the p05/p21/p11 suites must be untouched);
  - 3 B: what counts as drift vs finding (false flags BLOCK, unlisted flagged → DIFFERENT, wrong flag → FAILED);
  - 23 B: the two-source verdict (one source → DIFFERENT), the due rule (calendar days), the handling of
    `On Account` / flagged bills;
  - 25 B: R9 is never sent over XML; the read-back decides; cleanup text reaches a DIFFERENT summary;
    `mutating=True` doesn't change the A part;
  - 11: the relabel test reads the **snapshot**, not the flat names the re-run overwrites; every half is named;
  - 24: no credential path exists (no `ask`, nothing in requests); `_slip` can't mistake a vault rename for a slip
    when the GUID matches; pending reads never BLOCK;
  - `setup-c`: guard before any write, idempotent, never re-creates a master; the operator label guard runs before
    `stop()`;
  - isolation (`test_isolation.py`), and the Review Focus items.
- [ ] **Step 2:** Store the findings. Fix the confirmed ones test-first. Re-run the suite (with and without
  `-W error`) and record the count. The doc lists the suites **not** run: live Tally (Tasks 9–11), tier-C timing (⏭
  Q29), and the root `tests/` suite (it doesn't collect `v2/`).
- [ ] **Step 3: CLI smoke (no Tally):**
  ```bash
  mkdir -p /tmp/s0-smoke-p6
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p6/results.json list | grep -E '^ ?(3|11|23|24|25) '
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p6/results.json run 22; echo "exit=$?"
  ```
  Expected: 3/23/25 `A+B`, 24 `C` `not run`, and `run 22` prints "not built yet" with `exit=2`.
- [ ] **Step 4: Commit** the review doc and fixes (only the files named), plus a tracker change-log row with the
  review path.

---

### Task 9: Live session B — 3 B, 11 (C46 re-run), 23 B, 25 B with the R9 attempt (operator at the Mac)

**Files (written by the runner, then committed):** `v2/probes/results/results.json`,
`v2/tests/fixtures/sync/p03_B_*`, `p11_B_*`, `p23_B_*`, `p25_B_*`, `docs/bi-s0-probe-results-<date>.md`. Logs go to
`logs/`.

Only probe 25 B's R9 step can change company B, and only if TallyPrime accepts the duplicate. That is why it runs last.
The pristine restore point is `s0probe-backups/100000-company-B-loaded-2026-09-24`.

- [x] **Step 1: Pre-flight (read-only).**
  ```bash
  cd "/Users/nuvanta-mac-3/work/Tally prime"
  git log --oneline -1; uv run --project v2 pytest v2/tests -q 2>&1 | tail -1
  grep -in '^[[:space:]]*load[[:space:]]*=' "$HOME/.wine/drive_c/Program Files/TallyPrimeEditLog/tally.ini"
  ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe-backups
  ps -axo pid,command | grep -i 'tally.exe' | grep -v grep
  python3 -c "import json;d=json.load(open('v2/probes/results/results.json'));e=d['environment'];print(e.get('licence'),e.get('company_b_loaded_at'));print(sorted(d['confirmed_requests']))"
  uv run --project v2 python - <<'EOF'
  import httpx
  from v2.agent.tally.envelopes import build_company_list
  from v2.agent.tally.xml_utils import parse_company_list
  print(parse_company_list(httpx.post("http://localhost:9000", content=build_company_list().encode(), timeout=30, trust_env=False).text))
  EOF
  ```
  Expected: the suite is green. `Load=100000`. `s0probe` holds `100000 100003`. The backups include
  `100000-company-B-loaded-2026-09-24`. There is one `tally.exe` with `s0probe` in its command line. The licence is
  `educational` and `company_b_loaded_at` is set. The confirmed requests are `active_company, company_counters,
  ledger_level_tb, voucher_month`. The company list is exactly `["Sharma & Sons' Probe Traders"]`.
- [x] **Step 2: B only.** If the list is anything else, restart through C44 (click "T: Continue In Educational Mode"
  when `CLICK NEEDED` shows):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p6-restart-B-$(date +%F).log
  from v2.probes.companies import COMPANIES
  from v2.probes.operator.auto import build_auto_operator
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      print("B ->", auto.control.restart("B", [COMPANIES["B"]]))
  finally:
      auto.close()
  EOF
  ```
- [x] **Step 3: Run, one probe per log, in this order (manual mode, never `--auto`):**
  ```bash
  uv run --project v2 python -m v2.probes run 3 --company B 2>&1 | tee logs/p03B-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 11 2>&1 | tee logs/p11-rerun-c46-$(date +%F).log
  uv run --project v2 python -m v2.probes run 23 --company B 2>&1 | tee logs/p23B-live-$(date +%F).log
  uv run --project v2 python -m v2.probes run 25 --company B 2>&1 | tee logs/p25B-live-$(date +%F).log
  ```
  - **Probe 11:** its observations must equal the relabel test's: 14 ledgers as current FY, bill on the ledger, stock
    scope `current_period` 5/5. If they differ, company B changed: **stop**, restore the backup, and investigate
    before anything else. Never re-run to "fix" a number.
  - **Probe 25 B (you, at TallyPrime):** when it asks, go to Gateway of Tally → Create → Ledger. Type the name it
    shows and put it under **Sundry Debtors**. Try to save (click **A: Accept**), then press Esc back to the Gateway
    (answer Yes to quit without saving if asked). Type TallyPrime's message **word for word** (or `saved` if it
    saved).
  - Any BLOCKED "Company B differs from the dataset…" or "drifted": stop, and restore (step 4). DIFFERENT and FAILED
    are findings: record them and don't re-run.
- [x] **Step 4: Only if probe 25 B's `r9.verdict` is `accepted`, or a drift BLOCK happened: restore company B.** *(Not needed 2026-09-25: R9 was refused and no drift BLOCK happened; B unchanged.)*
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p6-restore-B-$(date +%F).log
  import datetime, shutil, subprocess
  from v2.probes.companies import COMPANIES
  from v2.probes.operator.auto import build_auto_operator
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      auto.control.stop()
      live, backups = auto.config.data_dir / "100000", auto.config.backups_dir
      aside = backups / f"100000-after-part6-{datetime.date.today()}"
      shutil.move(str(live), str(aside)); shutil.copytree(backups / "100000-company-B-loaded-2026-09-24", live)
      print(subprocess.run(["diff", "-rq", str(backups / "100000-company-B-loaded-2026-09-24"), str(live)],
                           capture_output=True, text=True).stdout or "restored: identical")
      print("B ->", auto.control.restart("B", [COMPANIES["B"]]))
  finally:
      auto.close()
  EOF
  ```
  (One licence click is needed.) The moved-aside folder is the evidence of what TallyPrime saved. Keep it.
- [x] **Step 5: Read the numbers out** (for the tracker and specs):
  ```bash
  uv run --project v2 python -c "import json; p=json.load(open('v2/probes/results/results.json'))['probes']; \
  [print(k, p[k]['parts']['B']['outcome'], '—', p[k]['parts']['B']['summary']) for k in ('3','11','23','25')]; \
  print(json.dumps({k: p[k]['parts']['B']['observations'].get('sub_verdicts') for k in ('11','23','25')}, ensure_ascii=False)); \
  print(json.dumps(p['25']['parts']['B']['observations']['r9'], ensure_ascii=False))" 2>&1 | tee logs/s0-p6-b-numbers-$(date +%F).log
  ```
- [x] **Step 6: List, report, commit the evidence.**
  ```bash
  uv run --project v2 python -m v2.probes list | grep -E '^ ?(3|11|23|25) '
  uv run --project v2 python -m v2.probes report
  git diff --stat v2/probes/results/results.json     # only probes 3/11/23/25 and run_mode
  git add v2/probes/results/results.json v2/tests/fixtures/sync/p03_B_* v2/tests/fixtures/sync/p11_B_* \
          v2/tests/fixtures/sync/p23_B_* v2/tests/fixtures/sync/p25_B_* docs/bi-s0-probe-results-$(date +%F).md
  git commit -m "data(bi/v2): probes 3/23/25 B and 11 (C46 re-run) live on company B" \
             -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
  ```
  Then update tracker rows 3, 11, 23, 25 (outcome, proof, logs) and add a change-log row, in the same turn.

---

### Task 10: Company C — create it in the UI, record its number, load it, back it up (operator at the Mac)

**Files:** none committed here. `setup-c` writes `environment.company_c_loaded_at` into `results.json`, which Task 11
commits. Logs go to `logs/`.

- [x] **Step 1: Pre-flight.** Only B is open (Task 9 step 1's company-list snippet). Record
  `ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe | tee logs/company-c-before-$(date +%F).log` (expect
  `100000 100003`).
- [x] **Step 2: Create company C (you, in TallyPrime; mouse / menu wording as TallyPrime 7 shows it).**
  1. Top menu bar → **K: Company** → **Create**.
  2. **Company Name:** `Probe Vault Co`, exactly. The mailing name fills itself.
  3. **State:** Maharashtra, **Country:** India (keep the defaults if already set).
  4. **Financial year beginning from:** `1-4-2025`. **Books beginning from:** `1-4-2025`.
  5. Security fields, if shown on this screen ("Control user access to company data", "Use TallyVault password to
     encrypt company data" or similar): **No** and blank. The baseline must be unsecured; probe 24 turns them on
     later.
  6. Leave everything else (base currency ₹ / INR, etc.) at its default. Accept the screen: click **A: Accept** on the
     right-hand button bar, or answer **Yes** to "Accept?".
  7. If a Company Features screen appears, accept it unchanged (no GST).
  8. TallyPrime now has B and C open. Shut B: **K: Company** → **Shut** → `Sharma & Sons' Probe Traders`. The Gateway
     of Tally must show only `Probe Vault Co`.
  If a menu item's wording differs from the above, use the nearest item and write the exact wording into the log
  (step 3).
- [x] **Step 3: Record C's company number.** Tally assigns the lowest free number: B got 100000. Given `100000` and
  `100003`, expect `100001`, but **don't assume it**.
  ```bash
  ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe | tee logs/company-c-created-$(date +%F).log
  ```
  The one new folder is company C's number. Write it into the tracker row 24 proof and into the log. It is
  **not** added to `OperatorConfig.company_numbers` (Task 6: manual-only).
- [x] **Step 4: Load it.**
  `uv run --project v2 python -m v2.probes setup-c 2>&1 | tee logs/setup-c-live-$(date +%F).log` → `Created:
  ledger, voucher` and `Company C loaded`. Run it a second time into the same log (`tee -a`) → `Created: nothing;
  already there: ledger, voucher` (live idempotence). Optional UI check: Gateway → Day Book shows the ₹100 Payment
  dated 1-Apr-2025.
- [x] **Step 5: Back up the unsecured baseline** (Tally idle, company C open is fine, as with B's backup):
  ```bash
  C=100001   # ← the number from step 3
  D=~/.wine/drive_c/users/Public/TallyPrimeEditLog
  cp -Rp "$D/s0probe/$C" "$D/s0probe-backups/$C-company-C-baseline-$(date +%F)"
  diff -rq "$D/s0probe/$C" "$D/s0probe-backups/$C-company-C-baseline-$(date +%F)" && echo identical
  ```
  Tracker: row 24 🟡 "company C created (number …), loaded, backed up". Add a change-log row.

---

### Task 11: Live probe 24 on company C, then clean up (operator at the Mac)

**Files (written by the runner, then committed):** `results.json`, `v2/tests/fixtures/sync/p24_C_*`, the regenerated
results doc. Logs go to `logs/`.

- [x] **Step 1: Pre-flight.** The company list (Task 9 step 1 snippet) is exactly `['Probe Vault Co']`, and
  `results.json` has `company_c_loaded_at` plus the four confirmed requests.
- [x] **Step 2: Run** (manual, never `--auto`):
  `uv run --project v2 python -m v2.probes run 24 2>&1 | tee logs/p24-live-$(date +%F).log`.
  Do each pause exactly as printed:
  (1) turn on security with **throwaway** credentials and stay logged in → (2) Shut and Select company C, stop at
  the login box → (3) log in → (4) Change TallyVault with a **throwaway** password, reopen if TallyPrime closes it →
  (5) Shut and Select, stop at the TallyVault box → (6) enter the vault password and log in. The probe never asks
  you to type a credential into the terminal. If you ever find yourself doing that, stop.
- [x] **Step 3: Record what TallyVault did to the folder:**
  `ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe | tee logs/company-c-after-vault-$(date +%F).log`
  (a new number or a renamed folder is itself a finding for Q25 / probe 13's restore story).
- [x] **Step 4: Credential leak check (before any `git add`).** Type each throwaway value at a hidden prompt; nothing
  lands in shell history:
  ```bash
  for what in username password vault-password; do
    read -rs -p "$what: " V; echo
    grep -rlF -- "$V" v2 docs logs LESSONS.md && echo "LEAK: $what — stop, remove it, do not commit"
  done; unset V
  ```
  Expected: no `LEAK` line.
- [x] **Step 5: Clean up.** In TallyPrime: **K: Company** → **Shut** → `Probe Vault Co`, so that nothing reopens it at
  a prompt. Then archive its folder(s) and return to company B through C44 (one licence click):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/company-c-archive-$(date +%F).log
  import datetime, shutil
  from v2.probes.companies import COMPANIES
  from v2.probes.operator.auto import build_auto_operator
  C_FOLDERS = ["100001"]   # ← every company-C folder from Task 10 step 3 and step 3 above; edit before running
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      auto.control.stop()
      for number in C_FOLDERS:
          src = auto.config.data_dir / number
          dst = auto.config.backups_dir / f"{number}-company-C-secured-vaulted-{datetime.date.today()}"
          assert src.is_dir() and not dst.exists(), (src, dst)
          shutil.move(str(src), str(dst))
          print("archived", src, "→", dst)
      print("B ->", auto.control.restart("B", [COMPANIES["B"]]))
  finally:
      auto.close()
  EOF
  ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe
  grep -in '^[[:space:]]*load[[:space:]]*=' "$HOME/.wine/drive_c/Program Files/TallyPrimeEditLog/tally.ini"
  ```
  Expected: `s0probe` holds `100000 100003`, `Load=100000`, and `B -> ["Sharma & Sons' Probe Traders"]`. The archive
  stays out of git. It can be deleted any time, since nothing depends on it and its credentials are throwaway.
- [x] **Step 6: List, report, commit the evidence.**
  ```bash
  uv run --project v2 python -m v2.probes list | grep -E '^ ?24 '
  uv run --project v2 python -m v2.probes report
  git add v2/probes/results/results.json v2/tests/fixtures/sync/p24_C_* docs/bi-s0-probe-results-$(date +%F).md
  git commit -m "data(bi/v2): company C + probe 24 live (security, TallyVault)" \
             -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
  ```
  Tracker row 24: the outcome, proof, logs and the company number. Add a change-log row.

---

### Task 12: Spec, tracker, roadmap, LESSONS and Part 1 spec updates (same session as the live tasks)

**Files:** `docs/specs/2026-09-22-bi-s0-probes-design.md`, `docs/specs/2026-09-21-bi-part1-sync-design.md`,
`docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md`, `LESSONS.md`, and this plan (tick the boxes).

- [x] **Step 1: S0 spec.** Add a header line `**Changed <date> (plan part 6):**` covering:
  (a) §7 probe 3 B as built (what B measures given probe 21's evidence; the verdict mapping; outcome).
  (b) §7 probe 23 B as built (June 2023 via probe 5's request, Bills Receivable as-on 31-03-2026, the two-source
  verdict; outcome).
  (c) §7 probe 25 B as built (voucher types; R9 as a UI-only ask in 25 B, never XML; outcome).
  (d) §7 probe 11: correct the 2026-09-24 text. The recorded evidence shows ledger OpeningBalance =
  **current-FY** opening for 14/25 (consistent with 16 B's `fy`). The old "ledger openings CONFIRMED" is marked
  superseded, with the relabel from the re-run.
  (e) §4.4 company C as built: books 01-04-2025, `setup-c` content, company number, manual-only, and **credentials
  never recorded** (overrides "throwaway passwords recorded in the results").
  (f) §7 probe 24 as built: five-read export, pending-prompt gate shapes, outcome.
  (g) §6 batch 6: manual only. §11.5 rows 3 (+ `B_flagged_month_2023_02/07`), 23, 24 (+ the `*_pending_*` steps, the
  per-read names), 25 (+ `B_ledgers_after_duplicate_attempt`).
- [x] **Step 2: Tracker.** Rows 3, 11, 23, 24, 25 get ✅ with proof (or their real outcome). Row 11 also gets the
  correction of its 2026-09-24 "ledger openings CONFIRMED" text (superseded, not deleted). Update the §0 S0 row and
  §1 decisions 9 (probe 3) and 11 (probe 11 if it changes the anchor story). Rewrite "Resume here" to the state
  actually left behind. Next steps: probe 22 still blocked on the forex write shape; the S0 exit-gate check (§10); S1
  spec. Add a dated change-log row with every contradicted expectation (including the probe-11 misreading).
- [x] **Step 3: LESSONS.md §15.** Rule 20b: its "Ledger OpeningBalance … did **not** have this problem" is wrong.
  Correct it (current-period-relative for ledgers too, citing p11's observations and 16 B's `opening_scope`), keeping
  the old text in a superseded note. Add a rule for any new finding: optional/cancelled listing and flags, due-date
  column, R9, secured/vault export and gate shapes. Each carries its scope caveat (Educational, Wine 11.0, TallyPrime
  7.0).
- [x] **Step 4: Part 1 spec.** One dated "Changed" line: R16 (3 B), Part 3 overdue split (23 B), R9 (25 B), R2/R26 +
  onboarding + gate shape (24), R5 (11 under C46: both ledger and stock openings are current-period; books-start
  anchors come from the TB / Stock Summary as-on the books start).
- [x] **Step 5: Roadmap.** Set C S0 row: part 6 done; what remains (probe 22 blocked on forex write shape; exit
  gate; S1 spec).
- [x] **Step 6: Commit** docs only: `docs(bi/v2): plan part 6 results into specs, tracker, LESSONS, roadmap`.

---

## Self-review (done while writing)

- **Spec coverage:**
  - §7 probe 3 B → T2 + T9.
  - Probe 23 B → T3 + T9.
  - Probe 25 B (+ the §4.3 R9 note) → T4 + T9.
  - §4.4 company C → T6 (loader), T10 (UI + load + backup).
  - Probe 24 → T7 + T11.
  - Probe 11 / C46 follow-up (tracker "Resume here" item 3) → T5 + T9.
  - §6 batch 5 order (3, 11, 23, 25; 14 isn't re-run) and batch 6 → T9, T11.
  - §4.5 guards: the C43 dates are listed in Global Constraints; the drift BLOCKs are in T2–T5.
  - §10 exit gate: item 6 (isolation) → T6 step 4 + T8; item 7 (code review) → T8; item 2 (spec changes for every
    DIFFERENT/FAILED) → T12.
- **Placeholders:** none. `<date>`, `<YYYY-MM-DD>`, `<sha>` and company C's number are run-time values. The number is
  deliberately observed, not assumed (T10 step 3).
- **Names used across tasks:**
  - Task 1 → Tasks 2–7: `written_vouchers`, `flagged_tags`, `bill_terms` / `BillTerm.bill_date/.credit_days/.due/.flagged`,
    `credit_days`, `stock_opening_at`, `r9_candidate`, `B_CUSTOM_VOUCHER_TYPE(_BASE)`.
  - `COMPANY_C_*` → Tasks 6, 7.
  - FakeBooks knobs and `seed_company_b(bills=)` / `seed_company_c` → Tasks 2–5, 7.
  - Collection names `S0P03BVouchers`, `S0P25BVoucherTypes`, `S0P25BLedgers`, `S0P24Ledgers` all start with a
    `B_PROBE_COLLECTIONS` prefix. `S0ActiveCompany` is probe 2's candidate (a) ID.
- **Review Focus → tests:** 1 → T2; 2 → T7; 3 → T7 + T11 step 4; 4 → T5; 5 → T4.

## Ambiguities in the spec, and how this plan resolves them

1. **What probe 3 B still measures, given probe 21's evidence (S0-D7).** B does not re-ask whether cancelled vouchers
   are returned (probe 21 saw 201/202, and an offline test re-judges those bytes). It judges the flags on the
   extractor's own request for Feb and Jul 2023, measures the never-seen optional pair 301/302, and checks books-wide
   that the 954 others carry no flag.
2. **Probe 3 B: a flagged voucher that isn't listed.** DIFFERENT (the extractor never sees it, so R16 has less to
   filter), not FAILED. The spec's FAILED is for a *missing flag* on a returned voucher.
3. **Probe 3 B: a flag on a voucher the dataset didn't flag.** BLOCKED as drift (someone edited B), not a Tally
   finding.
4. **Probe 5 as a prerequisite for B parts only.** `requires` stays `(0,)`, so an ordered run's A batch never blocks
   on a B-only probe. Each B part checks `voucher_month` itself, as probe 21 does.
5. **Probe 23 B: which bills and which date.** Voucher credit periods come from June 2023 via probe 5's request
   (probe 5's own month, holding both 30- and 45-day bills). Due dates come from Bills Receivable as-on 31-03-2026,
   the current position. The opening bill (no credit period) is recorded, not judged. `On Account` rows are ignored.
   Bills of flagged vouchers are recorded if listed.
6. **Probe 23 B: "worse of two sub-verdicts" (§5.1).** That clause pairs GST fields with due dates, which the A/B
   split already separates. B's two halves answer **one** question (can the overdue split be built?). So one working
   source gives DIFFERENT (the impact names the source), neither gives FAILED, and both give CONFIRMED.
7. **Probe 23 B: the due rule.** Due = bill date + credit period in calendar days. `BILLOVERDUE` is recorded, not
   judged. A due equal to the bill date is classed separately ("credit period ignored").
8. **Probe 25 B's scope.** Voucher types only (§11.5 lists `B_voucher_types`) plus R9. Group nature isn't re-read on
   B: A settled it by walking Parent.
9. **Probe 25 B: resolving by the Parent walk counts as CONFIRMED** for B's question ("must resolve to Sales"). How it
   resolved is recorded (`resolved_by`).
10. **R9: how it's asked.** It is a UI-only, action-less ask (never XML, rule 10), offered only when the run is
    interactive and not in auto mode. The name is the first creditor under a custom sub-group, tried under Sundry
    Debtors. The read-back beats the typed answer. "Accepted" means DIFFERENT, with the cleanup in the summary, and
    Task 9 step 4 restores B from backup.
11. **Probe 25 becomes `mutating=True`.** The R9 step asks for a create. Both A and B contain "Probe", so the guard
    changes nothing for A.
12. **Company C's content.** The spec says "created by you in the UI with one ledger and one voucher". The company
    shell is made in the UI because it can't be scripted. Its content comes from a tiny idempotent `setup-c`, which
    gives read-back and a deterministic baseline for probe 24's drift check. Books begin 01-04-2025, and the ₹100
    Payment is dated on that day (never after F2; C43-safe).
13. **Company C's number.** It is observed after creation (lowest free number, expected 100001, never assumed) and
    recorded in the tracker. It is **not** added to `OperatorConfig.company_numbers`, because C is manual-only.
    `TallyControl` now refuses an unnumbered label before stopping Tally.
14. **Credentials.** Spec §4.4 says "throwaway passwords recorded in the results". Overridden: `results.json`,
    fixtures and logs are committed or kept, so credentials are never recorded anywhere. The probe never asks for
    them. Task 11 greps before committing. Task 12 adds a dated spec line.
15. **What "export" means in probe 24.** Five reads per stage, all using other probes' confirmed requests (S0-D7):
    company list, active GUID (2), counters (1), ledgers, vouchers (5). "Record each response" also covers the two
    **pending-prompt** reads, because the spec asks for "a new error shape for the gate" and the prompt is exactly when
    the gate runs into one.
16. **Probe 24's verdict.** Unchanged export after log-in/unlock gives CONFIRMED (no credentials in the agent).
    Export works but GUID or content changed gives DIFFERENT (the re-link path, Q25). Export fails with the company
    open gives FAILED (v1 can't sync it; onboarding says so). A different company open is BLOCKED (operator slip),
    unless the GUID matches (then it is a vault rename, and it is recorded).
17. **C44 and a vaulted company.** A start with `Load=<C>` would stop at the login/vault prompt that no licence click
    clears, so C is never started by the operator. The person shuts C before quitting. Cleanup stops Tally, archives
    C's folder(s), and restarts B through C44, which rewrites `Load=100000`.
18. **Cleanup: archive, not delete.** The vaulted company goes to `s0probe-backups/…-secured-vaulted-<date>`
    (evidence; deletable any time). The unsecured baseline backup lets probe 24 be redone.
19. **Probe 11: re-run or relabel.** Re-run, under the stated rule: allowed only when the judging code changed, never
    to change an outcome. The live re-run must reproduce the offline relabel of the snapshot. Only the runner may
    write `results.json`, so a relabel is a run anyway.
20. **Probe 11's stock rule under C46.** The quantity decides the scope, judged on the items where the books-start
    and current-period openings differ. Rate and value are recorded, not judged, in the current-period case (the
    dataset has no valuation). "Mixed" and "neither" are FAILED. "Undecided" is DIFFERENT.
21. **`FakeBooks.stock_opening_scope` default stays `"books"`,** although live is `"current"` (C46). Five suites
    seed on it. The live shape is pinned by the relabel test on the real bytes.
22. **Probe 11's hidden ledger half.** The recorded 2026-09-24 evidence shows ledger OpeningBalance is FY-scoped (14
    as current FY). The docs that said "CONFIRMED" misread a summary that only showed the worst half. Fixed in code
    (every half named) and in the docs (Task 12), which mark the old text as superseded.
23. **Batch-5 order in this session:** 3, 11, 23, 25. 25 goes last because its R9 step may change B. 14 isn't re-run
    (it must stay last in any B session that does run it). The order in `ALL_ORDER` is unchanged.
24. **Probe 24 in `ALL_ORDER`.** It stays last. `--all --auto` reaching it BLOCKs (manual only), so the ordered run
    stops there cleanly.
25. **Probe 22.** Not planned (BLOCKED, C36).
