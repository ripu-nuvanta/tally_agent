# S0 Probes — Part 7: unblock and run probe 22 (forex vouchers expose the INR base amount) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified**, not at the end (tracker rules).

**Goal:** Find, on live company B, a write shape that makes TallyPrime store a USD export sale as a real forex
voucher. Then load the two skipped USD export sales (tags 101/102, Ruling C36) with that shape, and build and run
probe 22: "does a forex voucher line expose the INR base amount?" (decision 15).

**Architecture:** Five steps, and each one is gated on the one before.
1. **Offline candidate (Task 1).** Build the forex writer pieces with tests: a Currency master create, `CURRENCYNAME`
   on a party ledger, and a forex `AMOUNT` expression renderer/parser. Also a one-shot shape runner,
   `v2/probes/setup/forex_shape.py`, in the pattern of `sign_check.py`: not wired into the CLI, run by hand.
2. **Live shape run (Task 2).** Take a fresh backup of B. Run the shape runner **on throwaway objects only**
   (`ZZ Forex Probe …` ledgers and `S0-throwaway forex` vouchers, each read back, then deleted). It keeps the
   Currency master and saves every raw read-back.
3. **Loader (Task 3).** Only if the live run stored forex: remove C36's skip, write 101/102 with the proven shape, and
   teach `FakeBooks` the shape **as it was read back live**, pinned by a test on the committed capture.
4. **Probe 22 (Task 4).** Reads the forex sales with probe 5's confirmed request (the extractor's own request) and
   judges them against the dataset.
5. **Review, then live (Tasks 5–6).** A code review, a live `setup-b` that writes only the 2 vouchers (plus the new
   currency and ledger), a new backup, probe 22 live, and a blast-radius re-run of 21 and 18 B. Docs are Task 7.

**Tech Stack:** Python ≥ 3.12, httpx (`MockTransport` in tests), pytest + pytest-asyncio (`asyncio_mode = "auto"`),
uv. No new dependencies.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md): header
"Changed 2026-09-24 (Ruling C36)", §4.3 (company B: "one USD export customer", "2 USD export sales (probe 22)"), §4.5
(guards incl. C43), §4.6 (Educational dates 1/2/31), §5 (harness), §6 batch 5 (22 before 23/25, **14 last**, Ruling
Q6), §7 probe 22, §11.4, §11.5 row 22. Parent:
[`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md) decision 15 (INR base amount in
every amount column, face value + rate in `raw`, "no conversion at read time"), §12 item 22.
**Why forex was blocked:** [`docs/code-review-bi-s0-company-b-live-fixes-2026-09-24.md`](../code-review-bi-s0-company-b-live-fixes-2026-09-24.md)
finding #2 and "(5) USD export path". The ruling is C36 in `.superpowers/sdd/2026-09-23-bi-s0-company-b-loader/progress.md`.
Its neighbours matter here: C30 (sign on the wire), C32 (invoice nominal line), C34 (bill sign), C35 (settlement
pool), C41 (purchases' own RNG stream), C42 (flagged vouchers post nothing).
**Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3 row 22, "Resume here" step 2.
**Plan parts:** 1–3 (see part 6's header), 4 [`2026-09-24-bi-s0-probes-plan-part4.md`](2026-09-24-bi-s0-probes-plan-part4.md),
5 [`2026-09-24-bi-s0-probes-plan-part5.md`](2026-09-24-bi-s0-probes-plan-part5.md), 6
[`2026-09-25-bi-s0-probes-plan-part6.md`](2026-09-25-bi-s0-probes-plan-part6.md). **Part 7 (this file).**
**Not in this part:** the S0 exit-gate check, tier-C timing (⏭ Q29), any company-A work, and the part-6 review minors
M1–M8 (another agent is doing those in `v2/` right now; see Step 0.1).

---

## Four facts found while writing this plan (they shape Tasks 1–3)

1. **The "USD export customer" is also an ordinary INR customer.** In both licences, `Gulf Office Supplies LLC`
   (`USD_DEBTOR`) carries **87 live vouchers**: 55 domestic GST sales with `New Ref` bills and 32 receipts
   (`Agst Ref` / `On Account`). This is a side effect of the debtor rotation. **Changing Gulf's currency would re-cast
   87 live vouchers**, so this plan never alters Gulf. The forex sales go to a new, dedicated USD ledger
   (Ruling P7-2, **a human decision, H1**).
2. **Un-skipping 101/102 trips the loader's own drift alarm.** `setup-b` computes `_latest_complete_fy`. FY 2023-24 to
   2025-26 are complete, so FY 2022-23 at 238 of 240 would be reported as "Tally was missing 2 — investigate why they
   went missing". That is a `problems` line, so `setup-b` exits 1 and never stamps `company_b_loaded_at`. Task 3 turns
   exactly that gap into a note (Ruling P7-9).
3. **`TallyWriter.delete_voucher` checks a delete with the wrong window.** `voucher()` → `list_vouchers()` reads
   `READBACK_FROM..READBACK_TO` = company A's FY 2025-26. A 2022 throwaway voucher would **always** look deleted, so a
   failed delete would pass silently. The shape runner deletes and verifies inside the voucher's own day
   (`delete_b_voucher`, Task 1.2). This is Review Focus item 2.
4. **The USD sales have no rounding tie.** Base = face × rate: 448.44 × 82.99 = 37216.0**356** and
   1161.27 × 82.58 = 95897.6**766**. Both round the same under HALF_UP and HALF_EVEN, so the dataset's ₹37,216.04 /
   ₹95,897.68 hold whichever rule Tally uses. A test pins this (Task 3), because a tie would make "base matches
   dataset" depend on Tally's unmeasured rounding.
   Dates: under Educational, 101 is **01-09-2022** and 102 is **02-09-2022**. Both are C43-safe days (1 and 2), and
   the Sep-2022 month window is 01..02-09-2022. Under a licensed Tally they fall on the 2nd and the 5th.

## Global Constraints

Every task's requirements implicitly include this section.

- **Nothing outside `v2/` and `docs/` changes.** Task 7 may also edit `LESSONS.md`. v2 never imports `backend`,
  `scripts` or `tests`. `v2/agent/` never imports `v2.probes`. Probe modules (`v2/probes/pNN_*.py`) never import
  `v2.probes.setup` or `v2.probes.operator`. They read company B's dataset **only** through
  `v2/probes/company_b_view.py` (`test_isolation.py` pins both). `v2/probes/setup/forex_shape.py` may import
  `v2.probes.reads` and `v2.probes.safety` (setup already does).
- **Offline tests only in Tasks 1, 3 and 4.** They never talk to a real Tally, never start Wine and never touch
  `localhost:9000`. They use `FakeBooks` (`v2/tests/probes/fake_books.py`).
- **C33 and C43 stay true in the fakes.** `FakeBooks.requested_period()` honours only typed `SVFROMDATE`/`SVTODATE`,
  and on an educational fake only days 1/2/31. No task may weaken this.
- **Every date this part sends or writes is Educational-safe:** throwaway vouchers **01-09-2022**, voucher read-back
  window 01-09-2022..01-09-2022, tags 101/102 on 01-09-2022 / 02-09-2022, and probe 22's window from
  `company_b_view.month_window(2022, 9, licence)` (educational → 01..02-09-2022). The central C43 guard
  (`safety.check_educational_dates`) refuses anything else. **F2 must be ≥ 31-03-2026 before any voucher write.**
  Tally resets F2 on a restart (operator gotcha, tracker "Resume here"), and a voucher dated after F2 is silently
  dropped (LESSONS §15 rule 14). The read-back catches that.
- **Write safety (LESSONS §15):** list before every create (rule 10: a duplicate master create raises a blocking
  modal). Read back every write (rules 2, 3): `created=1` is not proof. Treat `altered=1` on a master create as
  "already exists" (rule 11). Company-level features (multi-currency) are **UI-only** (the rule 4 analogue): never
  sent over XML.
- **`Gulf Office Supplies LLC` is never altered** (fact 1). No existing company-B voucher is altered, re-created or
  deleted. The only company-B writes in this part are: the Currency master, one new ledger, tags 101/102, and the
  shape runner's throwaways, which are deleted with a read-back.
- **No hand edits to `v2/probes/results/`** or to the flat `v2/tests/fixtures/sync/pNN_*` fixtures. Only the runner
  writes them (Task 6). **One exception:** the shape runner writes its own evidence folder
  `v2/tests/fixtures/sync/forex_shape_<YYYY-MM-DD>/` (Task 2). It is committed once and never edited afterwards (the
  same pattern as `c46_p11_live_2026-09-24/`).
- **Money is exact** (`Decimal`, never float). A missing amount is `None`. Rounding to paise is `ROUND_HALF_UP`, and
  only where this plan says so.
- **Request rules** (`safety.check_request` + `check_educational_dates`): no `*` as `NATIVEMETHOD`/`FETCH`, no
  `$$InDateRange`, no off-day dates under Educational. One request at a time, no retries. A timeout stops with the
  popup hint.
- **Verdicts** follow S0-D6 / §5.4. DIFFERENT and FAILED need a `spec_impact`. **Company-B drift** (an untagged,
  extra or duplicated voucher; a forex sale missing; a stored base that differs from the dataset) **BLOCKs** with
  "re-run `setup-b` verify or restore the backup". It is never reported as a Tally finding.
- **Company guard for live runs:** exactly one company open, `Sharma & Sons' Probe Traders` (folder 100000).
  `--auto` is never used for probe runs. Restarts, backups and restores go through the C44 operator helpers
  (`build_auto_operator`, `backup_company`, `restore_company`).
- **Commands** (repo root `/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q` (also once with `-W error` before a commit that ends a task)
  - one file: `uv run --project v2 pytest v2/tests/probes/<file>.py -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **Logs** of every live command go to `logs/` via `2>&1 | tee logs/<name>-$(date +%F).log`.
- **Commits:** one per sub-task, on `feat/bi-s0-probe-harness`. Stage **only the files the task names**. Every message
  ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tracker discipline** (CLAUDE.md "Always update the tracker"): row 22 goes 🟡 when Task 1 starts. Every finished
  task adds its proof and a dated change-log row **in the same turn**, and rewrites "Resume here".
- **Code blocks were written against HEAD `3da09d7` but not executed.** Step 0.3's pre-flight scan runs them in a
  scratch copy first. **The tests are the contract.** If a code block fails its own test, fix the code, not the test,
  unless the test contradicts this plan's text. Record each correction as a ruling in the SDD ledger.
- **Candidate names are guesses until Task 2 measures them.** This covers the XML tags `CURRENCY`, `MAILINGNAME`,
  `EXPANDEDSYMBOL`, `DECIMALSYMBOL`, `ISSUFFIX`, `HASSPACE`, `DECIMALPLACES`, `CURRENCYNAME`, the company feature
  fields, and the AMOUNT expression grammar. Task 2 step 3 compares them with the base currency's own export **before**
  the first create. Task 3 re-pins the fake to what came back.

## Review Focus

These five inputs are the ones most likely to hurt a real run. The spec implies them but doesn't spell them out. Each
one has a test in the task that owns the code.

1. **Tally accepts the forex voucher but stores plain INR** (`created=1`, and the read-back shows `-37216.04`). This is
   the C36 failure again. The shape runner must classify it `forex_dropped`, not success. Probe 22 must BLOCK ("not a
   forex voucher"), never CONFIRM vacuously. Tests: Task 1.3 `test_forex_dropped_when_tally_stores_plain_inr`, Task 4
   `test_plain_inr_without_forex_blocks_as_c36_recurrence`.
2. **A throwaway delete that silently fails** (fact 3). Tally answers `deleted=1`, but the 2022 voucher is still
   there. The runner must raise, not report success. Test: Task 1.3 `test_a_delete_that_does_not_stick_is_caught_in_the_2022_window`.
3. **The loader's drift alarm on the formerly skipped tags** (fact 2). A person expects `setup-b` to write 2 vouchers
   and exit 0 with a note, and a genuine gap in another tag to still be a problem. Tests: Task 3
   `test_formerly_skipped_gap_is_a_note_not_a_problem`, `test_any_other_gap_in_that_fy_is_still_a_problem`.
4. **The forex party's ledger balance exports as an expression, not a number.** That would break S1 parity parsing
   (decision 11) even while the voucher lines are fine. Probe 22 records it (not judged) and says so in the summary
   and `spec_impact`. Test: Task 4 `test_usd_ledger_closing_expression_is_recorded_not_judged`.
5. **Tally stores a different base than the dataset** (its own rounding or rate): balanced, but ≠ ₹37,216.04. Every
   expected figure that probes 16/18/21 use would then be wrong, so this is drift (BLOCKED), not CONFIRMED. Test: Task
   4 `test_base_differs_from_dataset_blocks_as_drift`. The no-tie precondition is pinned by Task 3
   `test_usd_sale_bases_have_no_rounding_tie`.

---

## Before you start

- [x] **Step 0.1: Confirm the base and wait for the other agent.** Another agent is editing `v2/` for the part-6 review
  minors. `git log --oneline -5` must show its commit(s), **and** `git status --short -- v2/` must be empty. If it isn't
  empty, **wait**. Do not stash, reset or touch another agent's files. Record the HEAD you start from as `P7_BASE`.
- [x] **Step 0.2: Record BASE.** `uv run --project v2 pytest v2/tests -q 2>&1 | tail -1`. It was 756 green after part
  6; record whatever it is now. This part adds **about 45** tests (advisory). Each sub-task's last step records the
  running count.
- [x] **Step 0.3: Pre-flight scratch scan.** Same pattern as part 6's Step 0.3, on the offline Tasks 1, 3 and 4 only:
  ```bash
  SCRATCH="$TMPDIR/p7-scratch"
  git worktree add --detach "$SCRATCH" HEAD
  cd "$SCRATCH"
  # For each of 1.1, 1.2, 1.3, 3, 4: paste the task's code and tests as written, then
  uv run --project v2 pytest v2/tests -q 2>&1 | tee "$SCRATCH/runs/task-N.log" | tail -3
  git add -A && git commit -qm "scratch task N"
  ```
  Task 3 depends on Task 2's live shape. For the scan, use the **default candidate shape** (F1 text,
  `forex_export_form="full"`) and mark any failure that is due only to the missing live capture as "expected: pinned in
  Task 3 step 3.9". Write failures and corrections to
  `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part7/preflight-scan.md`, one ruling each in `progress.md`, then
  `cd` back and `git worktree remove --force "$SCRATCH"`.
- [ ] **Step 0.4: Start the SDD ledger** `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part7/progress.md`: plan path,
  spec path, `P7_BASE`, BASE count, pre-flight result, and **the answers to H1 and H2** (see "Rulings"). Mark tracker
  row 22 🟡 "plan part 7 in progress" and add a change-log row.

## File Structure

| File | Responsibility |
|---|---|
| `v2/probes/reads.py` *(modify)* | Task 1.1: `ForexAmount`, `parse_forex_amount`, `forex_base` (probe-side parser; setup and the fake reuse it) |
| `v2/probes/setup/company_b_data.py` *(modify)* | Task 1.1: `CurrencySpec`, `USD_CURRENCY`. Task 3: `LedgerSpec.currency`, `VoucherSpec.currency_symbol` / `fx_rate`, `Dataset.currencies`, `USD_EXPORT_PARTY` ledger, 101/102 un-skipped, `FORMERLY_SKIPPED_TAGS`; `USD_SKIP_REASON` removed |
| `v2/probes/setup/writes.py` *(modify)* | Task 1.2: `ForexLine`, `forex_amount_text`, `validate_b_voucher(forex=)`, `create_b_voucher(forex=)`, `currency_request`, `list_currencies`, `create_currency`, `create_party_ledger(currency=)`, `ledger_detail_request` / `ledger_details`, `b_day_voucher_request`, `delete_b_voucher` |
| `v2/probes/setup/forex_shape.py` *(create)* | Task 1.3: the one-shot live shape runner (`run`, `classify`, `ShapeReport`) |
| `v2/tests/probes/fake_books.py` *(modify)* | Task 1.2/1.3: Currency masters + route, ledger `CURRENCYNAME`, forex AMOUNT on import/export, knobs. Task 3: default shape = live; `seed_company_b` writes 101/102 |
| `v2/tests/probes/test_forex_amount.py` *(create)* | Task 1.1 |
| `v2/tests/probes/test_setup_writes_forex.py` *(create)* | Task 1.2 |
| `v2/tests/probes/test_forex_shape.py` *(create)* | Task 1.3 |
| `v2/tests/fixtures/sync/forex_shape_<date>/` *(runner-written, committed)* | Task 2 evidence |
| `v2/probes/setup/company_b.py` *(modify)* | Task 3: `_load_currencies`, ledger currency, forex vouchers, the formerly-skipped exemption, `_MASTER_KINDS` |
| `v2/tests/probes/test_company_b_data.py`, `test_company_b.py`, `test_company_b_view.py`, `test_fake_books_vouchers.py`, `test_fake_books_part6.py`, `test_cli.py`, `test_p21_full_history_reach.py`, `test_setup_writes.py` *(modify)* | Task 3: the C36 expectations (958, 238, `skipped == {101, 102}`) become the part-7 ones, each with its reason |
| `v2/tests/probes/test_fake_books_forex.py` *(create)* | Task 3: the fake pinned to the live capture |
| `v2/probes/company_b_view.py` *(modify)* | Task 4: `USD_EXPORT_PARTY`, `USD_CURRENCY_SYMBOL`, `forex_vouchers` |
| `v2/probes/p22_forex.py` *(create)*, `v2/tests/probes/test_p22_forex.py` *(create)*, `v2/probes/registry.py` *(modify)* | Task 4 |
| `docs/code-review-bi-s0-part7-<date>.md` *(create)* | Task 5 |
| runner-written evidence + `docs/bi-s0-probe-results-<date>.md` | Task 6 |
| specs, tracker, roadmap, `LESSONS.md` | Task 7 |

---

### Task 1: The offline forex write-shape candidate (three sub-tasks, one commit each)

#### Task 1.1: The AMOUNT expression — render and parse

**Files:**
- Modify: `v2/probes/reads.py` (append after `signed_ui_amount`)
- Modify: `v2/probes/setup/company_b_data.py` (add `CurrencySpec`, `USD_CURRENCY` next to `UnitSpec`)
- Test: `v2/tests/probes/test_forex_amount.py`

**Interfaces:**
- Produces: `reads.ForexAmount(currency: str, fx: Decimal, rate: Decimal, rate_symbol: str, base: Decimal | None,
  raw: str)`; `reads.parse_forex_amount(text: str | None) -> ForexAmount | None`;
  `reads.forex_base(fa: ForexAmount) -> tuple[Decimal, str]` (the route is `"stated"` or `"computed"`);
  `company_b_data.CurrencySpec(symbol, formal_name, decimal_symbol="cent", decimal_places=2)`,
  `company_b_data.USD_CURRENCY = CurrencySpec("$", "USD")`.

The grammar is the candidate from the 2026-09-24 review (`-$448.44 @ ₹82.99/$ = -₹37216.04`). It is widened to
tolerate spaces, a missing base part, a `Rs.` base symbol and a symbol word (`USD`), because Tally's own export form
is still unmeasured.

- [x] **Step 1: Write the failing tests** (`v2/tests/probes/test_forex_amount.py`):

```python
from decimal import Decimal

import pytest

from v2.agent.tally.amounts import AmountParseError, parse_decimal
from v2.probes.reads import ForexAmount, forex_base, parse_forex_amount


@pytest.mark.parametrize("text, fx, rate, base", [
    ("-$448.44 @ ₹82.99/$ = -₹37216.04", "-448.44", "82.99", "-37216.04"),       # review 2026-09-24's form
    ("$448.44 @ ₹ 82.99/$ = ₹ 37216.04", "448.44", "82.99", "37216.04"),         # spaces after the symbols
    ("$1,161.27 @ ₹82.58/$ = ₹95,897.68", "1161.27", "82.58", "95897.68"),       # Indian/Western commas
    ("-$448.44@₹82.99/$=-₹37216.04", "-448.44", "82.99", "-37216.04"),           # no spaces at all
    ("USD 10 @ 80/USD = 800", "10", "80", "800"),                                # a symbol word, no base symbol
])
def test_full_expression_parses(text, fx, rate, base):
    fa = parse_forex_amount(text)
    assert fa == ForexAmount(currency=fa.currency, fx=Decimal(fx), rate=Decimal(rate), rate_symbol=fa.rate_symbol,
                             base=Decimal(base), raw=text)
    assert forex_base(fa) == (Decimal(base), "stated")


def test_expression_without_base_computes_half_up():
    fa = parse_forex_amount("-$ 448.44 @ Rs. 82.99/$")
    assert (fa.currency, fa.rate_symbol, fa.base) == ("$", "Rs.", None)
    assert forex_base(fa) == (Decimal("-37216.04"), "computed")          # 448.44 × 82.99 = 37216.0356


@pytest.mark.parametrize("text", ["-37216.04", "", None, "37,216.04", "$448.44", "@ 82.99/$", "abc"])
def test_non_expressions_are_none(text):
    assert parse_forex_amount(text) is None


def test_parse_decimal_still_raises_on_the_expression():
    # spec §11.2: amounts.parse_decimal raising on a forex expression is expected, and carries the raw text
    with pytest.raises(AmountParseError) as err:
        parse_decimal("-$448.44 @ ₹82.99/$ = -₹37216.04")
    assert err.value.raw == "-$448.44 @ ₹82.99/$ = -₹37216.04"
```

- [x] **Step 2: Run:** `uv run --project v2 pytest v2/tests/probes/test_forex_amount.py -q` → FAIL (`ImportError: ForexAmount`).
- [x] **Step 3: Implement** (`v2/probes/reads.py`, plus `import re`, `from dataclasses import dataclass`,
  `from decimal import ROUND_HALF_UP` if not already imported):

```python
# --- forex amounts (probe 22, plan part 7) --------------------------------------------------------------------------
# Candidate grammar (review 2026-09-24 #2): "<sign><sym><fx> @ <base sym><rate>/<sym> [= <sign><base sym><base>]".
# Widened for the unmeasured export form: optional spaces, a missing "= base" part, "Rs." or no base symbol, a
# symbol word ("USD"). Task 2 of plan part 7 measures Tally's own form; tests pin it to that capture.
_FX_NUM = r"\d[\d,]*(?:\.\d+)?"
_FOREX_RE = re.compile(
    rf"^\s*(?P<s1>-?)\s*(?P<sym>[^\d\s@=/-]+)\s*(?P<s2>-?)\s*(?P<fx>{_FX_NUM})"
    rf"\s*@\s*(?P<rsym>[^\d\s@=/-]*)\s*(?P<rate>{_FX_NUM})\s*/\s*(?P<per>[^\s=]+)"
    rf"(?:\s*=\s*(?P<b1>-?)\s*(?P<bsym>[^\d\s=-]*)\s*(?P<b2>-?)\s*(?P<base>{_FX_NUM}))?\s*$")
_PAISA = Decimal("0.01")


@dataclass(frozen=True)
class ForexAmount:
    currency: str            # the foreign symbol as written ("$")
    fx: Decimal              # signed foreign face value
    rate: Decimal            # base-currency units per foreign unit
    rate_symbol: str         # the base symbol as written ("₹", "Rs.", "")
    base: Decimal | None     # signed base amount when the text states it ("= -₹37216.04"), else None
    raw: str


def _fx_number(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def parse_forex_amount(text: str | None) -> ForexAmount | None:
    """A Tally forex AMOUNT expression → its parts; anything else (a plain number, empty, junk) → None."""
    match = _FOREX_RE.match(text or "")
    if match is None:
        return None
    fx = _fx_number(match["fx"]) * (-1 if "-" in match["s1"] + match["s2"] else 1)
    base = None
    if match["base"] is not None:
        base = _fx_number(match["base"]) * (-1 if "-" in (match["b1"] or "") + (match["b2"] or "") else 1)
    return ForexAmount(currency=match["sym"], fx=fx, rate=_fx_number(match["rate"]),
                       rate_symbol=match["rsym"] or "", base=base, raw=text)


def forex_base(fa: ForexAmount) -> tuple[Decimal, str]:
    """The INR base of one forex line: the stated "= ₹…" part when present ("stated"), else face × rate rounded
    ROUND_HALF_UP to paise ("computed" — Tally's own rounding is unmeasured, so a computed base is a DIFFERENT)."""
    if fa.base is not None:
        return fa.base, "stated"
    return (fa.fx * fa.rate).quantize(_PAISA, rounding=ROUND_HALF_UP), "computed"
```

  In `company_b_data.py`, after `UnitSpec`:

```python
@dataclass(frozen=True)
class CurrencySpec:
    """A Tally Currency master (plan part 7). `symbol` is the master's NAME and what a forex AMOUNT is written in;
    `formal_name` is its expanded name. Field names on the wire are candidates until Task 2 measures them."""
    symbol: str
    formal_name: str
    decimal_symbol: str = "cent"
    decimal_places: int = 2


USD_CURRENCY = CurrencySpec(symbol="$", formal_name="USD")
```

- [x] **Step 4: Run** the file → PASS. Then the full suite, and record the count.
- [x] **Step 5: Commit** `v2/probes/reads.py v2/probes/setup/company_b_data.py v2/tests/probes/test_forex_amount.py`:
  `feat(bi/v2): forex AMOUNT expression parser + USD currency spec (plan part 7 task 1.1)`.

#### Task 1.2: Writer pieces — currency, ledger currency, forex voucher lines, a day-window delete

**Files:**
- Modify: `v2/probes/setup/writes.py`
- Modify: `v2/tests/probes/fake_books.py` (Currency masters + route, ledger `CURRENCYNAME`, forex import/export, knobs)
- Test: `v2/tests/probes/test_setup_writes_forex.py`

**Interfaces:**
- Consumes: `CurrencySpec`, `parse_forex_amount`, `forex_base` (1.1).
- Produces (all in `writes.py`):
  - `ForexLine(symbol: str, fx_amount: Decimal, rate: Decimal, base_symbol: str = "₹", form: str = "full")`, where
    `fx_amount` is a **magnitude**;
  - `forex_amount_text(inr: Decimal, forex: ForexLine) -> str`;
  - `validate_b_voucher(..., forex: ForexLine | None = None) -> CheckedVoucher`, where `CheckedVoucher.forex` is added;
  - `TallyWriter.create_b_voucher(..., forex: ForexLine | None = None) -> str`;
  - `CURRENCY_FIELDS`, `currency_request(company) -> str`, `TallyWriter.list_currencies(company) -> dict[str, dict[str, str]]`,
    `TallyWriter.create_currency(company, spec) -> bool` (True = created now, False = already there);
  - `TallyWriter.create_party_ledger(..., currency: str | None = None)`;
  - `LEDGER_DETAIL_FIELDS`, `ledger_detail_request(company, name) -> str`,
    `TallyWriter.ledger_details(company, name) -> dict[str, str] | None`;
  - `b_day_voucher_request(company, day: str) -> str` (a DD-MM-YYYY day, typed, `VOUCHER_MONTH_FIELDS`, collection
    `S0FxDay`);
  - `TallyWriter.delete_b_voucher(company, master_id, *, vch_type, day: str, date_text: str) -> None`.
- `FakeBooks` gains these knobs (defaults are **candidates**; Task 3 re-pins them to the live capture):
  - `forex_currency_create="ok"`, one of `"ok" | "refuse" | "popup"`;
  - `forex_storage="expression"`, one of `"expression" | "plain" | "refuse"`;
  - `forex_forms_accepted=("full", "no_base")`;
  - `forex_on_base_party="same"`, one of `"same" | "refuse" | "plain"`;
  - `forex_export_form="full"`, one of `"full" | "no_base" | "plain_plus_field"`;
  - `forex_ledger_closing="plain"`, one of `"plain" | "expression"`;
  - `deletes_stick=True`;
  - `refuse_narrations=()`: a voucher whose narration contains one of these gets `import_result(exceptions=1)`. This
    is a test seam for "this voucher shape is refused", used by the V0-control test.

- [x] **Step 1: Write the failing tests** (`v2/tests/probes/test_setup_writes_forex.py`):

```python
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
```

- [x] **Step 2: Run** → FAIL (`ImportError: ForexLine`).
- [x] **Step 3: Implement `writes.py`.** Add near `CheckedVoucher`:

```python
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP

from v2.probes.reads import VOUCHER_MONTH_FIELDS, voucher_request
from v2.probes.setup.company_b_data import CurrencySpec

_PAISA = Decimal("0.01")


@dataclass(frozen=True)
class ForexLine:
    """How a forex voucher's lines go on the wire (plan part 7). `fx_amount` is the voucher's face value as a
    MAGNITUDE — every line of a 2-line export sale carries it, signed like that line's INR amount. `form` "full"
    states the base ("… = ₹37216.04", candidate F1); "no_base" leaves Tally to compute it (F2)."""
    symbol: str
    fx_amount: Decimal
    rate: Decimal
    base_symbol: str = "₹"
    form: str = "full"


def forex_amount_text(inr: Decimal, forex: ForexLine) -> str:
    sign = "-" if inr < 0 else ""
    text = f"{sign}{forex.symbol}{forex.fx_amount:.2f} @ {forex.base_symbol}{forex.rate:.2f}/{forex.symbol}"
    if forex.form == "full":
        text += f" = {sign}{forex.base_symbol}{abs(inr):.2f}"
    return text
```

  Add `forex: ForexLine | None = None` to `CheckedVoucher` (last field, default `None`) and to `validate_b_voucher`'s
  keyword-only arguments. Add these checks after the balance check, **before** the inventory checks:

```python
    if forex is not None:
        if inventory or bills:
            raise ValueError(f"Voucher {narration!r}: a forex voucher here carries no inventory and no bills "
                             "(plan part 7 Ruling P7-3: forex bill allocations are unverified)")
        if forex.form not in ("full", "no_base"):
            raise ValueError(f"Voucher {narration!r}: unknown forex form {forex.form!r}")
        product = forex.fx_amount * forex.rate
        base = product.quantize(_PAISA, rounding=ROUND_HALF_UP)
        if base != product.quantize(_PAISA, rounding=ROUND_HALF_EVEN):
            raise ValueError(f"Voucher {narration!r}: {forex.fx_amount} × {forex.rate} = {product} is a rounding tie "
                             "— the stored base would depend on Tally's unmeasured rounding rule")
        wrong = [ledger for ledger, amount, _ in lines if abs(amount) != base]
        if wrong:
            raise ValueError(f"Voucher {narration!r}: lines {wrong} are not face × rate = {base}")
```

  Return `CheckedVoucher(..., forex=forex)`. In `create_b_voucher`, add `forex: ForexLine | None = None`, pass it to
  `validate_b_voucher`, and render each ledger block's amount as
  `amount_text = forex_amount_text(amount, checked.forex) if checked.forex else f"{amount:.2f}"`, i.e.
  `<AMOUNT>{esc(amount_text)}</AMOUNT>`. (`esc` leaves `$ @ / = ₹` alone. It is there for safety only.)

  Currency, ledger details, day read and delete, next to the other read-backs:

```python
CURRENCY_FIELDS = ["Name", "MailingName", "ExpandedSymbol", "DecimalSymbol", "OriginalName", "IsSuffix",
                   "HasSpace", "DecimalPlaces"]                     # candidates — Task 2 step 3 compares them
LEDGER_DETAIL_FIELDS = ["Name", "Parent", "CurrencyName", "IsBillWiseOn", "OpeningBalance", "ClosingBalance"]


def currency_request(company: str) -> str:
    return wrap_collection("S0BCurrencies", "Currency", CURRENCY_FIELDS, company)


def ledger_detail_request(company: str, name: str) -> str:
    return wrap_collection("S0BLedgerDetail", "Ledger", LEDGER_DETAIL_FIELDS, company,
                           filters=[("S0BLedgerDetailOnly", f"$Name = {formula_string(name)}")])


def b_day_voucher_request(company: str, day: str) -> str:
    """Company B's vouchers on ONE day (DD-MM-YYYY, typed — C33; the day must be 1/2/31 under Educational — C43),
    fetched whole like probe 5's month request, so a forex line comes back exactly as the extractor would see it."""
    return voucher_request("S0FxDay", VOUCHER_MONTH_FIELDS, company, from_date=day, to_date=day)
```

  In `TallyWriter`:

```python
    def list_currencies(self, company: str) -> dict[str, dict[str, str]]:
        return {row["Name"]: row for row in read_objects(self.post(currency_request(company)), "CURRENCY",
                                                          CURRENCY_FIELDS)}

    def create_currency(self, company: str, spec: CurrencySpec) -> bool:
        """List first (LESSONS §15 rule 10), create, read back. No verified op exists — the tags are candidates
        (plan part 7 Task 2 step 3). Returns False when it was already there (nothing sent)."""
        check_writable(company)
        if spec.symbol in self.list_currencies(company):
            self.say(f"currency {spec.symbol!r} already exists — not re-created")
            return False
        inner = (f'<CURRENCY NAME="{esc(spec.symbol)}" ACTION="Create">\n'
                 f"  <NAME>{esc(spec.symbol)}</NAME>\n"
                 f"  <MAILINGNAME>{esc(spec.formal_name)}</MAILINGNAME>\n"
                 f"  <EXPANDEDSYMBOL>{esc(spec.formal_name)}</EXPANDEDSYMBOL>\n"
                 f"  <DECIMALSYMBOL>{esc(spec.decimal_symbol)}</DECIMALSYMBOL>\n"
                 f"  <DECIMALPLACES>{spec.decimal_places}</DECIMALPLACES>\n"
                 "  <ISSUFFIX>No</ISSUFFIX>\n  <HASSPACE>No</HASSPACE>\n</CURRENCY>")
        result = self.import_("All Masters", company, inner)
        if not ((result.created == 1 or result.altered == 1) and result.clean):          # rule 11
            raise WriteFailed(f"Currency {spec.symbol!r} not created: {result}")
        if spec.symbol not in self.list_currencies(company):
            raise WriteFailed(f"Currency {spec.symbol!r} not found on read-back")
        return True

    def ledger_details(self, company: str, name: str) -> dict[str, str] | None:
        rows = [r for r in read_objects(self.post(ledger_detail_request(company, name)), "LEDGER",
                                        LEDGER_DETAIL_FIELDS) if r["Name"] == name]
        return rows[0] if rows else None

    def delete_b_voucher(self, company: str, master_id: str, *, vch_type: str, day: str, date_text: str) -> None:
        """Delete by Master ID and verify in the voucher's OWN day. `delete_voucher` verifies through
        `list_vouchers`, i.e. company A's FY 2025-26 window, where a 2022 voucher is never listed — a delete that
        did not stick would pass there (plan part 7, fact 3)."""
        check_writable(company)
        inner = (f'<VOUCHER DATE="{esc(date_text)}" VCHTYPE="{esc(vch_type)}" TAGNAME="Master ID" '
                 f'TAGVALUE="{esc(master_id)}" ACTION="Delete"></VOUCHER>')
        result = self.import_("Vouchers", company, inner)
        if result.deleted != 1 or not result.clean:
            raise WriteFailed(f"Voucher {master_id} not deleted: {result}")
        still = [r for r in read_objects(self.post(b_day_voucher_request(company, day)), "VOUCHER", ["MasterID"])
                 if r.get("MasterID") == master_id]
        if still:
            raise WriteFailed(f"Voucher {master_id} still there on {day} after the delete")
```

  `create_party_ledger` gets `currency: str | None = None`. When it's set, add `\n  <CURRENCYNAME>{esc(currency)}</CURRENCYNAME>`
  to `extra`. After the existing read-back, check
  `self.ledger_details(company, name)["CurrencyName"] == currency`, else raise
  `WriteFailed(f"Party ledger {name!r}: CURRENCYNAME {currency!r} did not stick on read-back")`.

- [x] **Step 4: Teach `FakeBooks`** (`fake_books.py`). Put each rule in a comment that names its source:
  "candidate — plan part 7, pinned by Task 3" or "live — forex_shape_<date>".
  - `seed_state`: `"currencies": {"₹": {"MailingName": "INR", "ExpandedSymbol": "INR", "DecimalSymbol": "paise",
    "DecimalPlaces": "2"}}` (base currency).
  - `_import`: `element.tag == "CURRENCY"` and `Create`:
    - `refuse` → `import_result(exceptions=1, line_error="fake: currency refused")`;
    - `popup` → `self.popup = True; raise httpx.ReadTimeout(...)`;
    - otherwise `_create_master(state, "currencies", element, request, lambda el: {"MailingName": el.findtext("MAILINGNAME", ""), ...})`,
      whose duplicate → popup behaviour already follows rule 10.
  - `_answer`: `"S0BCurrencies" in body or "S0P22Currencies" in body` → `objects_xml("CURRENCY", [{"Name": n, **c} for n, c in state["currencies"].items()])`.
  - `_ledger` Create: store `"currency": element.findtext("CURRENCYNAME") or ""`. The fake returns
    `exceptions=1, line_error="fake: unknown currency"` when that currency isn't in `state["currencies"]`.
  - `_answer`: `"S0BLedgerDetail" in body` → the `$Name` filter plus `Name, Parent, CurrencyName, IsBillWiseOn,
    OpeningBalance, ClosingBalance`. Closing comes from `_ledger_balances`. When `forex_ledger_closing == "expression"`
    and the ledger has a currency, closing is written `f"{sign}{sym}{fx_total:.2f} = {sign}₹{abs(base):.2f}"`
    (a **hypothesis**, never measured). `_ledger_export` (probe collections) gains a `currencyname` field and the same
    closing rule.
  - `_voucher` Create, before `_signs_agree`: for every `LEDGERENTRIES.LIST`/`ALLLEDGERENTRIES.LIST` entry whose
    `AMOUNT` parses with `parse_forex_amount`:
    - `forex_storage == "refuse"`, or its form (`"full" if fa.base is not None else "no_base"`) not in
      `forex_forms_accepted` → `import_result(exceptions=1)`;
    - the entry's ledger has no currency and `forex_on_base_party == "refuse"` → `import_result(exceptions=1)`;
    - otherwise set the entry's `AMOUNT` text (on the parsed element, before `_posted_lines`) to
      `f"{forex_base(fa)[0]:.2f}"`, so balance and sign checks see the INR base;
    - remember `forex_text[ledger] = fa` unless `forex_storage == "plain"` or (`forex_on_base_party == "plain"` and
      the ledger has no currency).

    After `_posted_lines`, each line whose ledger is in `forex_text` gets
    `line["amount_text"] = _fake_forex_export(line["amount"], fa, self.forex_export_form)`, where:
    - `"full"` → `forex_amount_text`-shaped text with the stored base;
    - `"no_base"` → the same without `= …`;
    - `"plain_plus_field"` → `amount_text` stays unset and `line["extra"] = {"FOREXAMOUNT": f"{sign}{sym}{fx}"}`
      (a hypothesis field name, used only to cover probe 22's "field" route).
  - `_export_voucher`: `<AMOUNT>{line.get('amount_text') or line['amount']}</AMOUNT>`, plus
    `"".join(f"<{k}>{esc(v)}</{k}>" for k, v in line.get("extra", {}).items())`. With no forex, the bytes are exactly as
    before (the p05/p21/p03 suites must not move).
  - `_answer`: add `"S0FxDay"` to the full-export condition next to `"S0VoucherMonth"`.
  - `_voucher` Delete: if `not self.deletes_stick`, answer `import_result(deleted=1, last_vch_id=mid)` and keep the voucher.
  - `_voucher` Create, first line: if any of `refuse_narrations` is in the NARRATION, return `import_result(exceptions=1)`.
  - Put the text-building in **one** method, `FakeBooks._forex_line_text(base: Decimal, fa: ForexAmount) -> dict`, which
    returns `{"amount_text": …}`, `{"extra": {…}}` or `{}` according to the knobs. Task 3.8's `seed_company_b` calls
    it too, so seeded and imported forex lines honour the same knobs and can't drift apart.
- [x] **Step 5: Run** the new file → PASS. Then run the full suite: **the old byte-identity tests (p05, p21, p03 B,
  p23 B) must stay green without edits.** Record the count.
- [x] **Step 6: Commit** `v2/probes/setup/writes.py v2/tests/probes/fake_books.py v2/tests/probes/test_setup_writes_forex.py`:
  `feat(bi/v2): forex writer pieces — currency, ledger currency, forex lines, day-window delete (plan part 7 task 1.2)`.

#### Task 1.3: The shape runner `forex_shape.py`

**Files:**
- Create: `v2/probes/setup/forex_shape.py`
- Test: `v2/tests/probes/test_forex_shape.py`

**Interfaces:**
- Consumes: everything from 1.1 and 1.2; `safety.check_company`; `reads.parse_vouchers`, `amounts.parse_decimal`.
- Produces:
  - `run(writer: TallyWriter, company: str, out_dir: Path, *, currency: CurrencySpec = USD_CURRENCY,
    wait: Callable[[str], None] = _console_wait) -> ShapeReport`;
  - `classify(line: dict, sent_inr: Decimal) -> str`, one of `"forex_full" | "forex_no_base" | "plain_with_forex_field" |
    "plain_inr" | "other"`;
  - `ShapeReport.outcome`, one of `"stored_forex" | "forex_dropped" | "refused" | "currency_refused" | "control_failed" | "popup"`;
  - `ShapeReport.chosen` = `{"variant", "party_currency", "form"}` or `None`;
  - `ShapeReport.to_json() -> dict`; `out_dir/summary.json`.

**Variants** (all Sales, dated **01-09-2022**, narration `S0-throwaway forex <id>`, lines
`party −₹37,216.04 (Yes) / Export Sales +₹37,216.04 (No)`, tag 101's own figures `$448.44 @ ₹82.99`):

| id | party | forex | why |
|---|---|---|---|
| V0 | `ZZ Forex Probe INR Debtor` (no currency) | none | **control**: company B has never had a non-inventory, no-GST Sales invoice live. If V0 fails, the forex result means nothing |
| V1 | `ZZ Forex Probe USD Debtor` (`CURRENCYNAME` `$`) | F1 `full` | the recommended shape (S-B + F1) |
| V2 | USD debtor | F2 `no_base` | **only if V1 did not store forex** |
| V3 | INR debtor | F1 `full` | S-A evidence for H1: can a base-currency party carry forex? |

Both throwaway ledgers go under Sundry Debtors, **not** bill-wise (Ruling P7-3), with no GSTIN. After each variant:
read back the day, save the raw XML, classify both lines, delete the voucher, and verify the delete in the same day.
At the end, delete both ledgers (only the ones this run created, after their vouchers are gone). **Keep the Currency
master.**

- [x] **Step 1: Write the failing tests** (`v2/tests/probes/test_forex_shape.py`):

```python
import json
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES
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
    ("-$448.44 @ ₹82.99/$ = -₹37216.04", {}, "forex_full"),
    ("-$448.44 @ ₹82.99/$", {}, "forex_no_base"),
    ("-37216.04", {"FOREXAMOUNT": "-$448.44"}, "plain_with_forex_field"),
    ("-37216.04", {}, "plain_inr"),
    ("-37216.05", {}, "other"),
])
def test_classify(amount, fields, expected):
    line = {"amount_raw": amount, "fields": {"AMOUNT": amount, **fields}}
    assert forex_shape.classify(line, Decimal("-37216.04")) == expected
```

- [x] **Step 2: Run** → FAIL (`ModuleNotFoundError: forex_shape`).
- [x] **Step 3: Implement** `v2/probes/setup/forex_shape.py`:

```python
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
            return finish()
        v1 = variant("V1", USD_PARTY, "full")
        if not _stored(v1):
            variant("V2", USD_PARTY, "no_base")
        variant("V3", INR_PARTY, "full")
    except WriteTimeout:
        report.outcome = "popup"
        report.notes.append(POPUP_HINT)
        return finish()                                   # leave the ledgers: Tally is behind a modal
    finally:
        if report.outcome != "popup":
            for name in reversed(made):
                writer.delete_ledger(company, name)

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
```

  Note: `delete_ledger` uses the existing `writer.ledger()` (a name filter with no date), so its read-back is valid
  for any year.

- [x] **Step 4: Run** the file → PASS; full suite → green; record the count.
- [x] **Step 5: Commit** `v2/probes/setup/forex_shape.py v2/tests/probes/test_forex_shape.py` (plus any fake edits):
  `feat(bi/v2): forex shape runner — throwaway-only, read back, saved (plan part 7 task 1.3)`.
- [ ] **Step 6: Task-1 review before anything goes live.** Run the SDD spec-compliance review and the code-quality
  review on `git diff P7_BASE..HEAD -- v2/`. It must check:
  - the runner writes only throwaways plus the currency;
  - every write has a read-back;
  - deletes are verified in the 2022 day;
  - a timeout stops with no further writes;
  - list-before-create holds for the currency and both ledgers;
  - the fake's candidate knobs are commented as candidates.

  Fix the confirmed findings test-first, record them in `progress.md`, and add a tracker change-log row.

---

### Task 2: Live write-shape run on company B (operator at the Mac; read-mostly; throwaways only)

**Files (committed):** `v2/tests/fixtures/sync/forex_shape_<YYYY-MM-DD>/` (runner-written: `*.xml`, `summary.json`).
Logs go to `logs/` (not committed; cited by path).

The restore point for this task is a **fresh** backup taken in step 2. `100000-company-B-loaded-2026-09-24` stays as
the older one.

- [ ] **Step 1: Pre-flight (read-only).** Same as part 6 Task 9 step 1:
  ```bash
  cd "/Users/nuvanta-mac-3/work/Tally prime"
  git log --oneline -1; uv run --project v2 pytest v2/tests -q 2>&1 | tail -1
  grep -in '^[[:space:]]*load[[:space:]]*=' "$HOME/.wine/drive_c/Program Files/TallyPrimeEditLog/tally.ini"
  ls ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe ~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe-backups
  ps -axo pid,command | grep -i 'tally.exe' | grep -v grep
  uv run --project v2 python - <<'EOF'
  import httpx
  from v2.agent.tally.envelopes import build_company_list
  from v2.agent.tally.xml_utils import parse_company_list
  print(parse_company_list(httpx.post("http://localhost:9000", content=build_company_list().encode(), timeout=30, trust_env=False).text))
  EOF
  ```
  Expected: the suite is green, `Load=100000`, one `tally.exe` with `s0probe`, and the list is exactly
  `["Sharma & Sons' Probe Traders"]`. If the list is anything else, restart through C44 (part 6 Task 9 step 2's
  snippet, `auto.control.restart("B", [COMPANIES["B"]])`).
- [ ] **Step 2: Fresh backup of B** (Tally stops, the folder is copied, Tally starts; click "T: Continue In Educational
  Mode" when `CLICK NEEDED` shows):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p7-backup-B-pre-forex-$(date +%F).log
  import datetime
  from v2.probes.operator.auto import build_auto_operator
  from v2.probes.operator.company_a import backup_company
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      print(backup_company(auto.control, auto.config, "B", f"pre-forex-{datetime.date.today()}"))
  finally:
      auto.close()
  EOF
  ```
  Expected: `…/s0probe-backups/100000-pre-forex-<date>`. Record it in `progress.md`.
- [ ] **Step 3: Discovery reads, before any write** (read-only; the runner does these first as well, but look before
  you let it write):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p7-forex-discovery-$(date +%F).log
  import httpx
  from v2.probes.companies import COMPANIES
  from v2.probes.setup.writes import TallyWriter, currency_request
  B = COMPANIES["B"]
  with httpx.Client(base_url="http://localhost:9000", trust_env=False) as http:
      w = TallyWriter(http, print)
      print(w.post(currency_request(B)))
      print(w.ledger_details(B, "Export Sales"))
      print(w.ledger_details(B, "Gulf Office Supplies LLC"))
  EOF
  ```
  Decide from the base currency's (₹) row:
  - **If `CURRENCY_FIELDS` come back empty for ₹** (Tally names them differently, e.g. `FORMALNAME`): STOP. Change
    `create_currency`'s tags to the names that did come back, re-run Task 1's tests (add a test pinning the new tags),
    commit that with a ruling, then continue.
  - **If `$` already exists:** fine. The runner skips the create (`created_now=false`).
  - Record the base symbol exactly as exported. **Done 2026-09-25 (Ruling R-SYM):** company B's base currency NAME
    is a literal `?` (`logs/p7-forex-discovery-2026-09-25.log`). The runner now reads it itself
    (`forex_shape.base_currency`) and never hard-codes `₹`, so no code change is needed here.
- [ ] **Step 4: F2.** In TallyPrime, check "Current Date" (top bar). If it is before 31-03-2026, press **F2** and set
  31-03-2026. If the operator is away, the controller may drive it with **guarded** `osascript` keystrokes (LESSONS
  §15 rule 27: pid-guard every keystroke, no pause mid-sequence, screenshot before re-pressing anything, since the
  screen lags about 5 s). Under Ruling R-F2 the controller sets F2 **before** step 5 and passes
  `f2_confirm=lambda: None`. The runner's default confirmation asks on the console, and it refuses to start without
  a terminal.
- [x] **Step 5: Run the shape runner** from a script file (R-F2 / D6: a heredoc is stdin, so it can't carry a
  console prompt). F2 must already be ≥ 31-03-2026. The evidence folder must not exist yet; the runner refuses to
  overwrite a `summary.json`.
  ```bash
  cd "/Users/nuvanta-mac-3/work/Tally prime"
  cat > "$TMPDIR/p7_forex_shape.py" <<'EOF'
  import datetime, httpx
  from pathlib import Path
  from v2.probes.companies import COMPANIES
  from v2.probes.setup import forex_shape
  from v2.probes.setup.writes import TallyWriter
  out = Path(f"v2/tests/fixtures/sync/forex_shape_{datetime.date.today()}")
  with httpx.Client(base_url="http://localhost:9000", trust_env=False) as http:
      report = forex_shape.run(TallyWriter(http, print), COMPANIES["B"], out,
                               f2_confirm=lambda: None)        # R-F2: F2 was set before this run
      print(report.summary())
  EOF
  PYTHONPATH=. uv run --project v2 python "$TMPDIR/p7_forex_shape.py" 2>&1 | tee logs/p7-forex-shape-live-$(date +%F).log
  ```
- [ ] **Step 6: Decide by outcome** (write the decision into `progress.md` as a ruling, and into the tracker):

  | `summary.json` outcome | Meaning | Next |
  |---|---|---|
  | `stored_forex`, `chosen.variant` = `V1` (`base_symbol` `?`) | F1 on a USD party works, with the discovered base symbol | Task 3 with the recommended H1 (S-B, F1) and `base_symbol="?"` |
  | `stored_forex`, `chosen.variant` = `V1b` (`base_symbol` `""`) | F1 works only with the rate written without a base symbol (R-SYM) | Task 3 with F1 and `base_symbol=""` |
  | `stored_forex`, `chosen.variant` = `V2` | Only F2 works (Tally computes base) | Task 3 with `form="no_base"` (Ruling P7-5); probe 22 will likely say DIFFERENT |
  | `stored_forex`, `chosen.party_currency` = `null` (only V3) | A USD-currency ledger is refused; forex on an INR party works | **Ask the human (H1 fallback):** S-A = 101/102 stay on `Gulf Office Supplies LLC` (never altered) with forex lines. Task 3 drops the new ledger |
  | `forex_dropped` | Tally accepts, but stores plain INR | **UI fallback (Ruling P7-5):** the person enters one USD sale by hand on a throwaway party (Gateway → Vouchers → F8 Sales, type `$448.44`, rate `82.99`), the controller exports that day with `b_day_voucher_request`, saves it as `ui_entered.xml` in the evidence folder, and the voucher is deleted in the UI. If the UI stores forex, re-code the renderer to the exported text (a ruling + test) and re-run step 5. If the UI can't either → last row |
  | `currency_refused` | XML can't create the currency | **UI fallback:** Gateway → Create → Currency (`$`, formal name `USD`, 2 decimals, "cent"). If Tally asks to enable multi-currency (F11), accept it in the UI — never over XML. Read back with step 3's snippet, then re-run step 5 (it will skip the create) |
  | `forex_mismatch` | Tally kept a forex-looking amount, but not the sent values (I1; `notes` name what differs, e.g. face, rate or base) | **Not** stored. Read `variant_V*.xml`: `systematic-debugging` on how Tally rewrote the line before any re-run. Probably a restore |
  | `currency_unverified` | `created=1`, but no listed currency carries `$`/`USD` (I5) | **Do NOT re-run** (it would be a duplicate create, and the rule-10 modal). Inspect `currencies_after.xml` and the UI's Currency list, fix `currency_matches`/`CURRENCY_FIELDS` test-first, then re-run (the create is then skipped) |
  | `ledger_currency_refused` | The USD ledger was refused, or its `CURRENCYNAME` didn't stick (I3). The throwaway ledgers were deleted | UI: enable multi-currency (F11) / set the ledger's currency, then re-run. Otherwise it is the H1 fallback S-A (ask the human) |
  | `ledger_refused` | The plain INR throwaway ledger itself failed | `systematic-debugging` (the same create shape works in `sign_check`) |
  | `f2_or_date_dropped` | `created=1`, but a voucher is not on 01-09-2022 (I2), which is F2 below the date | Set F2 ≥ 31-03-2026, **restore** (a dropped voucher may have landed elsewhere), re-run |
  | `unrecognised` | A read-back line matches no known form | Read `variant_V*.xml` by hand, then decide |
  | `base_currency_unknown` | No single INR base row in the Currency list; nothing was written | Check `currencies_before.xml` / `base_currency` |
  | `aborted` (+ a traceback) | An error stopped the run: a delete that didn't stick ("still there"), a read-back MasterID ≠ LASTVCHID ("not deleting", I4) or a leftover ("leftover_found" in `notes`). `summary.json` is still written | **Restore** (step 7) unless `notes` say `leftover_found` and nothing was written |
  | any outcome with `numbering.changed = true` | Real company-B voucher numbers or AlterIDs in 01-09-2022..31-03-2023 changed (M6) | **Restore** (step 7), even if the forex result is good |
  | `control_failed` | V0 itself failed | The non-inventory, no-GST Sales shape is wrong on B: `superpowers:systematic-debugging` on the V0 `LINEERROR`/read-back **before** anything forex. It may need `Sales` without `ISINVOICE`; record a ruling |
  | `popup` | A modal is up | Dismiss it (or restart Tally, C44). Then **restore** (step 7), because throwaway ledgers may be left behind |
  | Edition refuses forex at every route (XML and UI) | Educational/Wine limit | **Stop the part here:** restore (step 7), probe 22 stays **BLOCKED** with this reason, C36 stays, go to **Task 7** (docs only, "confirm on tier C") |

- [ ] **Step 7: Restore path** (only for `popup`, the "edition refuses" row, or any sign that company B changed beyond
  the currency master):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p7-restore-B-$(date +%F).log
  import datetime
  from v2.probes.operator.auto import build_auto_operator
  from v2.probes.operator.company_a import restore_company
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      restore_company(auto.control, auto.config, "B", "pre-forex-<the date used in step 2>")
  finally:
      auto.close()
  EOF
  ```
  (One licence click.) Then check with step 1's company-list read and
  `uv run --project v2 python -m v2.probes setup-b` (verify only: it must create 0 and report no problems **under the
  old C36 code**, because Task 3 isn't merged yet).
- [ ] **Step 8: B is unchanged apart from the currency.** Re-run the setup-b verify:
  `uv run --project v2 python -m v2.probes setup-b 2>&1 | tee logs/p7-setup-b-verify-after-shape-$(date +%F).log`.
  Expected: every master and voucher skipped, 0 created, the C36 note, no problems. That proves the throwaways are
  gone and the balances haven't moved.
- [x] **Step 9: Commit the evidence** (the folder only):
  ```bash
  git add v2/tests/fixtures/sync/forex_shape_$(date +%F)/
  git commit -m "data(bi/v2): forex write-shape evidence on company B (plan part 7 task 2)" \
             -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```
  Tracker: row 22 notes the shape outcome and `chosen`; change-log row; "Resume here". If the shape result changes the
  design (H1 fallback, F2 only, UI-only currency), add a dated "Changed" line to the S0 spec **now** (§4.3 or §7 probe
  22) and say so in the tracker.

**Task 2 result (recorded 2026-09-25, Tasks 3–4 implementation session; evidence committed in `271ff01`):**
- **Outcome `stored_forex`**, `chosen` = `{"variant": "V1b", "party_currency": "$", "form": "full", "base_symbol": ""}`
  (`v2/tests/fixtures/sync/forex_shape_2026-09-25_run2/summary.json`).
- **Import side.** The forex line is written with the rate **without** a base symbol (V1b:
  `-$448.44 @ 82.99/$ = -37216.04`). V1 (the rate with company B's base symbol, `@ ?82.99/$ = -?37216.04`) was
  **refused**: EXCEPTIONS=1, no LINEERROR. V3 (the same forex form on an INR party) was **stored** too.
- **Read-back side** (`variant_V1b.xml`): party line `<AMOUNT>-$448.44 @ ? 82.99/$ = -? 37216.04</AMOUNT>`,
  ISDEEMEDPOSITIVE Yes; `Export Sales` line `<AMOUNT>$448.44 @ ? 82.99/$ = ? 37216.04</AMOUNT>`, ISDEEMEDPOSITIVE No.
  Tally rewrites the rate and the base in the base currency's own prefix, **`?` followed by a space**, whatever was
  sent (the base currency ₹ shows correctly in the UI; it exports as `?`, and its `HasSpace` is Yes). A forex line
  carries no extra leaf field compared with the plain V0 line. A live voucher exports both ALLLEDGERENTRIES.LIST and
  LEDGERENTRIES.LIST for the same postings.
- **The `$` Currency master cannot be created over XML** on this TallyPrime 7 Educational: run 1
  (`forex_shape_2026-09-25_run1_currency_refused/`) got EXCEPTIONS=1, and Tally kept `$` as an import-**exception**
  master, after which the UI refused to create `$`. Company B was restored; `$` was then created **in the UI**
  (Formal name USD) and B backed up as `s0probe-backups/100000-pre-forex-with-usd-2026-09-25`. B has `$` now.
  Consequence for Task 3: **setup-b never sends a Currency create** — it requires `$` to exist and otherwise stops
  before any write, naming the UI steps (deviation D8).
- **A ledger that ever had a voucher can't be deleted** ("Cannot be deleted!", `summary.json` notes), even after its
  voucher was deleted: the throwaway `ZZ Forex Probe USD Debtor` stayed, so B was restored again (to the backup
  above). Nothing in Task 3 creates and then deletes a ledger.
- **Numbering** 01-09-2022..31-03-2023 unchanged across the run (138 vouchers before and after, nothing renumbered).
- Steps 5 and 9 are ticked on that evidence; steps 1–4 and 6–8 were run by the controller at the Mac (see the
  tracker and `logs/p7-*-2026-09-25.log`).

---

### Task 3: Loader — write 101/102 with the proven shape (TDD against FakeBooks pinned to the live read-back)

**Gate:** `summary.json` outcome is `stored_forex`. Otherwise skip to Task 7.

**Files:**
- Modify: `v2/probes/setup/company_b_data.py`, `v2/probes/setup/company_b.py`, `v2/tests/probes/fake_books.py`
- Create: `v2/tests/probes/test_fake_books_forex.py`
- Modify tests (expectations only, each with its reason in a comment): `test_company_b_data.py` (lines ~60, 170, 207–208,
  373–386, 417), `test_company_b.py` (~85, 111–128), `test_company_b_view.py` (~42, 53), `test_fake_books_vouchers.py`
  (~28–29), `test_fake_books_part6.py` (~39, 69), `test_cli.py` (~239), `test_p21_full_history_reach.py` (~166, 169),
  `test_setup_writes.py` (~570, docstring only).

**Interfaces:**
- Consumes: `CurrencySpec`, `USD_CURRENCY`, `ForexLine`, `create_currency`, `create_party_ledger(currency=)`,
  `create_b_voucher(forex=)`, the live `summary.json` (`chosen.form`, the exported AMOUNT text).
- Produces:
  - `company_b_data.USD_EXPORT_PARTY = "Gulf Office Supplies LLC (USD)"` (H1 = S-B; under S-A it is `USD_DEBTOR`
    and no new ledger is added);
  - `LedgerSpec.currency: str | None = None`;
  - `VoucherSpec.currency_symbol: str | None = None` and `VoucherSpec.fx_rate: Decimal | None = None`;
  - `Dataset.currencies: tuple[CurrencySpec, ...] = ()`;
  - `FOREX_FORM: str` (`"full"` or `"no_base"`, from the live run);
  - `FORMERLY_SKIPPED_TAGS = frozenset({101, 102})`;
  - `company_b._load_currencies(writer, io, company, dataset, report)`, with `_MASTER_KINDS` gaining `"currencies"`
    (first).
  - `USD_SKIP_REASON` is **removed**. `VoucherSpec.skip_reason` stays as a general mechanism: no voucher uses it, and
    `_skip_notes` / the fake keep honouring it.

- [x] **Step 3.1: Pin the untouched dataset first.** At `P7_BASE`, compute and paste the hashes into the new test
  below (both licences):
  ```bash
  uv run --project v2 python - <<'EOF'
  import hashlib
  from v2.probes.setup.company_b_data import generate
  for lic in ("educational", "licensed"):
      rows = [repr((v.tag, v.kind, v.vch_type, v.date, v.party, v.narration, v.lines, v.inventory, v.bills,
                    v.cancelled, v.optional, v.currency, v.fx_amount)) for v in generate(lic).vouchers if v.tag not in (101, 102)]
      print(lic, hashlib.sha256("\n".join(rows).encode()).hexdigest())
  EOF
  ```
- [x] **Step 3.2: Write the failing dataset tests** (append to `test_company_b_data.py`; this replaces the "C36"
  block's assertions):

```python
import hashlib
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP

from v2.probes.setup.company_b_data import (FORMERLY_SKIPPED_TAGS, FOREX_FORM, USD_CURRENCY, USD_EXPORT_PARTY,
                                            expected_figures, generate)

UNTOUCHED_SHA = {"educational": "<paste from step 3.1>", "licensed": "<paste from step 3.1>"}


@pytest.mark.parametrize("licence", ["educational", "licensed"])
def test_every_other_voucher_is_byte_identical_to_p7_base(licence):
    rows = [repr((v.tag, v.kind, v.vch_type, v.date, v.party, v.narration, v.lines, v.inventory, v.bills,
                  v.cancelled, v.optional, v.currency, v.fx_amount))
            for v in generate(licence).vouchers if v.tag not in (101, 102)]
    assert hashlib.sha256("\n".join(rows).encode()).hexdigest() == UNTOUCHED_SHA[licence]   # C35/C41 pools unmoved


@pytest.mark.parametrize("licence, days", [("educational", (1, 2)), ("licensed", (2, 5))])
def test_usd_sales_are_written_with_forex(licence, days):
    by_tag = {v.tag: v for v in generate(licence).vouchers}
    for tag, day, fx, rate, inr in ((101, days[0], "448.44", "82.99", "37216.04"),
                                    (102, days[1], "1161.27", "82.58", "95897.68")):
        v = by_tag[tag]
        assert (v.skip_reason, v.currency, v.currency_symbol) == (None, "USD", USD_CURRENCY.symbol)
        assert (v.fx_amount, v.fx_rate, v.date) == (Decimal(fx), Decimal(rate), date(2022, 9, day))
        assert v.party == USD_EXPORT_PARTY and v.bills == () and v.inventory == ()
        assert [(l.ledger, l.amount, l.deemed_positive) for l in v.lines] == [
            (USD_EXPORT_PARTY, -Decimal(inr), True), ("Export Sales", Decimal(inr), False)]


def test_usd_sale_bases_have_no_rounding_tie():
    for v in generate("educational").vouchers:
        if v.fx_rate is not None:
            product = v.fx_amount * v.fx_rate
            assert product.quantize(Decimal("0.01"), ROUND_HALF_UP) == product.quantize(Decimal("0.01"), ROUND_HALF_EVEN)


def test_usd_export_party_and_currency():
    ds = generate("educational")
    assert ds.currencies == (USD_CURRENCY,)
    party = next(l for l in ds.ledgers if l.name == USD_EXPORT_PARTY)
    assert (party.parent, party.bill_wise, party.currency, party.opening, party.gstin) == (
        "Sundry Debtors", False, USD_CURRENCY.symbol, None, None)
    gulf = next(l for l in ds.ledgers if l.name == USD_DEBTOR)
    assert gulf.currency is None                                 # fact 1: Gulf's 87 live vouchers stay INR


def test_expected_counts_include_the_usd_sales():
    ds = generate("educational")
    exp = expected_figures(ds)
    assert not any(v.skip_reason for v in ds.vouchers) and FORMERLY_SKIPPED_TAGS == {101, 102}
    assert sum(exp.voucher_count_by_month.values()) == len(ds.vouchers) == 960
    assert exp.voucher_count_by_fy["2022-23"] == 240
    last = max(day for _, day in exp.ledger_month_end)
    assert exp.ledger_month_end[(USD_EXPORT_PARTY, last)] == Decimal("-133113.72")   # both sales, never settled
    assert FOREX_FORM in ("full", "no_base")
```

- [x] **Step 3.3: Run** → FAIL. **Implement the dataset:**
  - Add `currency: str | None = None` to `LedgerSpec` (last, with a default) and `currency_symbol` / `fx_rate` to
    `VoucherSpec`, after `fx_amount`.
  - Add `currencies: tuple[CurrencySpec, ...] = ()` to `Dataset` (last).
  - Add `USD_EXPORT_PARTY` and append it to `debtors` in `_ledgers()` (the **last** debtor, so `debtor_names`
    rotation indices for the existing six **don't move**).

  **Careful:** `_vouchers` builds `debtor_names` from every Sundry Debtors ledger, and adding a 7th changes
  `% len(debtor_names)` for every sale and receipt. So `_vouchers` must exclude the forex-only party from the rotation:
  `debtor_names = [l.name for l in ledgers if l.parent == "Sundry Debtors" and l.currency is None]`. The sha test in
  3.2 catches it if you forget.

  `_build_usd_sale` takes the **same draws in the same order** (qty, rate_usd, fx_rate) and returns
  `party=USD_EXPORT_PARTY`, `currency="USD"`, `currency_symbol=USD_CURRENCY.symbol`, `fx_amount=fx_amount`,
  `fx_rate=fx_rate`, and no `skip_reason`. `generate()` passes `currencies=(USD_CURRENCY,)`. Delete
  `USD_SKIP_REASON`. Replace the C36 comment with a "plan part 7" one naming `FORMERLY_SKIPPED_TAGS`, and add
  `FOREX_FORM = "<chosen.form from summary.json>"` with a comment naming the evidence folder.
- [x] **Step 3.4: Run** the dataset tests → PASS. **Then fix the C36-era expectations** in the listed test files. Each
  gets a one-line comment `# plan part 7: 101/102 written with forex (was C36-skipped)`:
  - 958 → 960 and 238 → 240;
  - `sep.skipped == {101, 102}` → `sep.skipped == frozenset()` and `len(sep.written) == 20`;
  - p21's `expected_written` for `fy2022_month_09` → 20, and its kind-count total 236 → 238 (the two USD sales are
    kind `sales`, unflagged);
  - `test_company_b.py`'s C36 tests become Step 3.6's tests.

  Never change an expectation without its reason.
- [x] **Step 3.5: Write the failing loader tests** (`test_company_b.py`, new section "plan part 7"). Follow that file's
  existing helpers for building a `FakeBooks` company B shell and running `load_company_b` with a scripted IO:

```python
def test_load_creates_the_currency_before_the_usd_ledger(tmp_path):
    books, report = _full_load(tmp_path)                        # existing helper: empty B shell → load
    bodies = [r for r in books.requests if "Import" in r]
    currency_at = next(i for i, r in enumerate(bodies) if "<CURRENCY " in r)
    ledger_at = next(i for i, r in enumerate(bodies) if f'NAME="{esc(USD_EXPORT_PARTY)}"' in r)
    assert currency_at < ledger_at and report.created["currencies"] == 1 and not report.problems


def test_second_load_sends_no_currency_create(tmp_path):
    books, _ = _full_load(tmp_path)
    before = len(books.requests)
    report = load_company_b(_writer(books), ScriptedIO(), licence="educational")
    assert report.created["currencies"] == 0 and report.skipped["currencies"] == 1
    assert not any("<CURRENCY " in r for r in books.requests[before:])


def test_usd_sales_go_out_with_forex_amounts(tmp_path):
    books, _ = _full_load(tmp_path)
    for tag in (101, 102):
        body = next(r for r in books.requests if f"[S0-B:{tag}]" in r and "Import" in r)
        amounts = re.findall(r"<AMOUNT>([^<]*)</AMOUNT>", body)
        assert amounts and all(parse_forex_amount(html.unescape(a)) is not None for a in amounts)


def test_a_foreign_voucher_without_fx_fields_stops_the_load(tmp_path, monkeypatch):
    ds = generate("educational")
    broken = replace(ds, vouchers=tuple(replace(v, fx_rate=None) if v.tag == 101 else v for v in ds.vouchers))
    monkeypatch.setattr(company_b, "generate", lambda licence="licensed": broken)
    books = _empty_b(tmp_path)
    with pytest.raises(CompanyBLoadError, match=r"\[S0-B:101\].*fx"):
        load_company_b(_writer(books), ScriptedIO(), licence="educational")
    assert not any("[S0-B:" in r and "Import" in r for r in books.requests)       # before any voucher is sent


def test_formerly_skipped_gap_is_a_note_not_a_problem(tmp_path):
    books = _loaded_b(tmp_path)                                  # seed_company_b(masters=True) = the part-7 dataset
    books.edit_state(_drop_tags(101, 102))                       # = live B after C36: 958 vouchers, no currency
    books.edit_state(lambda s: s["currencies"].pop("$", None))
    books.edit_state(lambda s: s["ledgers"].pop(USD_EXPORT_PARTY, None))
    report = load_company_b(_writer(books), ScriptedIO(), licence="educational")
    assert report.created["vouchers"] == 2 and report.created["ledgers"] == 1 and report.created["currencies"] == 1
    assert not report.problems, report.problems
    assert any("[S0-B:101, 102]" in n and "plan part 7" in n for n in report.notes)


def test_any_other_gap_in_that_fy_is_still_a_problem(tmp_path):
    books = _loaded_b(tmp_path)
    books.edit_state(_drop_tags(101, 102, 103))
    report = load_company_b(_writer(books), ScriptedIO(), licence="educational")
    assert any("FY 2022-23" in p and "missing" in p for p in report.problems)


def test_existing_usd_party_without_its_currency_is_a_problem(tmp_path):
    books = _loaded_b(tmp_path)
    books.edit_state(lambda s: s["ledgers"][USD_EXPORT_PARTY].__setitem__("currency", ""))
    report = load_company_b(_writer(books), ScriptedIO(), licence="educational")
    assert any(USD_EXPORT_PARTY in p and "currency" in p for p in report.problems)


def test_full_load_with_forex_verifies_clean(tmp_path):
    _, report = _full_load(tmp_path)
    assert report.created["vouchers"] == 960 and not report.problems            # TB magnitudes incl. the base
```

  (Add small helpers `_drop_tags(*tags)` and `_loaded_b` in the test file if they don't already exist. `_drop_tags`
  removes the vouchers whose narration starts `[S0-B:<tag>]`.)
- [x] **Step 3.6: Implement the loader** (`company_b.py`):
  - `_MASTER_KINDS = ("currencies", "groups", "units", "items", "ledgers", "vouchers")`.
  - `load_company_b`: call `_load_currencies(...)` right after `_require_voucher_type` and before `_load_masters`.
  - Currencies are created with the same `_create_or_pause` UI fallback as every other master:

```python
def _load_currencies(writer: TallyWriter, io: ProbeIO, company: str, dataset: Dataset, report: LoadReport) -> None:
    """Plan part 7: the Currency masters the forex sales need, list-before-create (rule 10). No verified XML op
    before part 7's live shape run; a refusal becomes a UI pause like any other master (C11)."""
    existing = writer.list_currencies(company)
    for c in dataset.currencies:
        if c.symbol in existing:
            report.skipped["currencies"] += 1
            continue
        if _create_or_pause(writer, io, report, "currency", c.symbol,
                            lambda c=c: writer.create_currency(company, c),
                            lambda c=c: c.symbol in writer.list_currencies(company)):
            report.created["currencies"] += 1
        else:
            report.skipped["currencies"] += 1
```

  - `_load_masters`, ledgers:
    - pass `currency=l.currency` to `create_party_ledger`;
    - for an **existing** ledger with `l.currency`, read `writer.ledger_details(company, l.name)`; if its
      `CurrencyName != l.currency`, append the problem
      `f"ledger {l.name!r}: currency is {got!r} in Tally, expected {l.currency!r} — never altered by the loader (a
      currency change re-casts the ledger's vouchers); fix it in the UI or restore"`.
  - `_load_vouchers`: replace the C36 currency stop with:

```python
    for v in dataset.vouchers:
        if v.currency != "INR" and not v.skip_reason and (v.currency_symbol is None or v.fx_amount is None
                                                          or v.fx_rate is None):
            raise CompanyBLoadError(f"[S0-B:{v.tag}] {v.narration}: currency {v.currency} without its fx fields "
                                    "(currency_symbol, fx_amount, fx_rate) — it would go out as a plain INR voucher.")
```

    `validate_dataset` passes `forex=_forex_of(v)` to `validate_b_voucher`, and the create call passes the same, where

```python
def _forex_of(v: VoucherSpec) -> ForexLine | None:
    if v.currency == "INR":
        return None
    return ForexLine(symbol=v.currency_symbol, fx_amount=v.fx_amount, rate=v.fx_rate, form=FOREX_FORM)
```

  - `_flag_predated_drift` gains the exemption. Pass it `existing.by_tag` and `dataset`, compute the missing written
    tags per FY, and:

```python
        missing = sorted(t for t, v in written.items() if fy_label(v.date) == fy and t not in present)
        if missing and set(missing) <= FORMERLY_SKIPPED_TAGS:
            report.notes.append(f"[S0-B:{', '.join(map(str, missing))}] written now — skipped under C36 until "
                                "plan part 7 proved a forex write shape; not drift.")
            continue
```

    Here `written = {v.tag: v for v in dataset.vouchers if not v.skip_reason}` and `present = set(existing.by_tag)`.
    Every other gap keeps its problem line exactly as before.
- [x] **Step 3.7: Run** the loader tests → PASS.
- [x] **Step 3.8: `seed_company_b` writes the forex sales.** `fill()` stores:
  - lines with the INR `amount`, updated with `books._forex_line_text(amount, parse_forex_amount(forex_amount_text(amount,
    ForexLine(...))))`. That is the same helper `_voucher` uses, so the `forex_storage` / `forex_export_form` knobs
    apply to seeded vouchers too. Probe 22's knob tests depend on this;
  - `state["currencies"]["$"]`;
  - the new ledger with `"currency": "$"`.

  `test_fake_books_vouchers.py`'s 960 and the p21 counts now pass.
- [x] **Step 3.9: Pin the fake to the live capture** (`v2/tests/probes/test_fake_books_forex.py`, create):

```python
from pathlib import Path

from v2.probes.reads import parse_forex_amount, parse_vouchers
from v2.tests.probes.fake_books import FakeBooks, _export_voucher, seed_company_b

SHAPE = sorted(Path("v2/tests/fixtures/sync").glob("forex_shape_*"))[-1]        # the committed live evidence
CHOSEN = __import__("json").loads((SHAPE / "summary.json").read_text())["chosen"]


def _live_forex_line() -> dict:
    raw = (SHAPE / f"variant_{CHOSEN['variant']}.xml").read_text(encoding="utf-8")
    voucher = next(v for v in parse_vouchers(raw) if v["header"]["NARRATION"].startswith("S0-throwaway forex"))
    return next(l for l in voucher["ledger_lines"] if parse_forex_amount(l["amount_raw"]) or l["fields"].get("AMOUNT"))


def test_fake_default_export_matches_the_live_amount_shape():
    live = parse_forex_amount(_live_forex_line()["amount_raw"])
    books = FakeBooks(name="Sharma & Sons' Probe Traders", educational=True)
    seed_company_b(books, "educational", masters=True)
    state = books.state
    mid, v = next((m, v) for m, v in state["vouchers"].items() if v["narration"].startswith("[S0-B:101]"))
    fake = parse_vouchers(f"<ENVELOPE><BODY><DATA><COLLECTION>{_export_voucher(state, mid, v)}</COLLECTION></DATA></BODY></ENVELOPE>")
    fake_fa = parse_forex_amount(fake[0]["ledger_lines"][0]["amount_raw"])
    assert (fake_fa is None) == (live is None)
    if live is not None:                              # same grammar: base stated or not, same symbols as live
        assert (fake_fa.base is None, fake_fa.currency, fake_fa.rate_symbol) == (live.base is None, live.currency,
                                                                                 live.rate_symbol)
        assert fake_fa.fx == live.fx and fake_fa.rate == live.rate          # tag 101 = the throwaway's figures


def test_fake_forex_line_carries_the_live_extra_fields():
    """The forex-only leaf fields live exported (V1 line vs V0 line) — the fake must export the same names."""
    v0 = parse_vouchers((SHAPE / "variant_V0.xml").read_text(encoding="utf-8"))
    control = next(v for v in v0 if v["header"]["NARRATION"] == "S0-throwaway forex V0")["ledger_lines"][0]["fields"]
    extra_live = set(_live_forex_line()["fields"]) - set(control)
    books = FakeBooks(name="Sharma & Sons' Probe Traders", educational=True)
    seed_company_b(books, "educational", masters=True)
    state = books.state
    mid, v = next((m, v) for m, v in state["vouchers"].items() if v["narration"].startswith("[S0-B:101]"))
    fake = parse_vouchers(f"<ENVELOPE><BODY><DATA><COLLECTION>{_export_voucher(state, mid, v)}</COLLECTION></DATA></BODY></ENVELOPE>")
    assert extra_live <= set(fake[0]["ledger_lines"][0]["fields"])
```

  Then set the `FakeBooks` defaults to the live answer:
  - `forex_export_form` = what live exported;
  - `forex_forms_accepted` = the forms that stored;
  - `forex_on_base_party` = V3's result;
  - the exact text layout (spaces, symbols) of `_fake_forex_export`;
  - any extra forex-only leaf fields live exported (add them to the fake's forex line, with the live values' shape).

  Update every knob's comment from "candidate" to "live — forex_shape_<date>". The knobs stay only for the
  hypotheses that live didn't settle.
- [x] **Step 3.10: The refresh round-trip analogue** (CLAUDE.md "Test reality" rule 7, S0 edition): load → read back
  through the **extractor's** request (probe 5's template via `fill_month_request`) → the forex text survives and
  parses to the dataset base. Add to `test_company_b.py`:

```python
async def test_forex_sale_round_trips_through_the_extractors_request(tmp_path):
    books, _ = _full_load(tmp_path)
    xml = fill_month_request(VOUCHER_MONTH_TEMPLATE, B, "01-09-2022", "02-09-2022")   # p05's confirmed shape
    raw = _writer(books).post(xml)
    by_tag = {tag_of(v["header"]["NARRATION"]): v for v in parse_vouchers(raw)}
    for tag, inr in ((101, Decimal("37216.04")), (102, Decimal("95897.68"))):
        bases = [forex_base(parse_forex_amount(l["amount_raw"]))[0] for l in by_tag[tag]["ledger_lines"]]
        assert sorted(bases) == [-inr, inr] and sum(bases) == 0
```

  (`VOUCHER_MONTH_TEMPLATE`: build it the way `test_p05_voucher_month_bounds.py` builds probe 5's confirmed template,
  and reuse that helper rather than copying XML. If the live form is `no_base`, `forex_base` computes the base, and
  this test still holds because there is no tie, fact 4.)
- [x] **Step 3.11: Run the whole suite** (and once with `-W error`); record the count. Commit the dataset, loader,
  fake and tests together, only the files named:
  `feat(bi/v2): company B writes the USD export sales as forex (plan part 7 task 3; lifts C36)`.

---

### Task 4: Probe 22 — forex vouchers expose the INR base amount

**Files:**
- Modify: `v2/probes/company_b_view.py`
- Create: `v2/probes/p22_forex.py`
- Modify: `v2/probes/registry.py`
- Test: `v2/tests/probes/test_p22_forex.py`
- Modify: `v2/tests/probes/fake_books.py` (`B_PROBE_COLLECTIONS` += `"S0P22"`; the Currency kind in `_b_collection`)

**Interfaces:**
- Consumes:
  - from the view: `loaded_licence`, `month_window`, `fetch_window`, `drift_message`, `tag_of`;
  - from `reads`: `parse_vouchers`, `parse_forex_amount`, `forex_base`, `master_request`;
  - `amounts.parse_decimal`.
- Produces:
  - `company_b_view.USD_EXPORT_PARTY` and `company_b_view.USD_CURRENCY_SYMBOL` (re-exported from the dataset);
  - `company_b_view.forex_vouchers(licence) -> dict[int, VoucherSpec]` (written, non-INR);
  - `p22_forex.judge_voucher(voucher: dict, spec: VoucherSpec, *, party_alias: str | None = None) -> dict`;
  - `p22_forex.verdict(judged: list[dict]) -> tuple[Outcome, str, str]` (outcome, summary, spec_impact; it raises
    `ProbeBlocked` for the BLOCKED rows);
  - `p22_forex.PROBE` (`id=22`, `parts={"B": run_b}`, `requires=(0, 5)`, `educational_sensitive=True`).

**Steps captured (§11.5 row 22):**
- `forex_sales`: probe 5's `voucher_month` for `month_window(2022, 9, licence)`, i.e. educational 01..02-09-2022;
- `usd_ledger`: a Ledger collection filtered to `USD_EXPORT_PARTY` with `Name, Parent, CurrencyName, OpeningBalance, ClosingBalance`;
- `currencies`: a Currency collection with `Name, MailingName, ExpandedSymbol, DecimalPlaces`.

No period variables on the master reads (rule 17).

**How a line is read (`judge_voucher`):**

| AMOUNT text | other leaf fields | route | base |
|---|---|---|---|
| expression with `= base` | any | `stated` | the stated base |
| expression without base | any | `computed` | face × rate, HALF_UP |
| plain decimal | a field mentioning `$` or `@` | `field` | the plain decimal (recorded field names) |
| plain decimal | none | `plain_no_forex` | the plain decimal |
| anything else | — | `unparsed` | `None` |

Per voucher it records:
- `balanced`: Σ base == 0.00 with every base known;
- `base_matches_dataset`: each line's |base| == |the dataset line's INR amount|, matched by ledger name;
- `parse_decimal_raises`, per line;
- `extra_fields`: leaf names on the forex lines that the unflagged INR sales in the same response don't carry.

**Verdict (`verdict`), first match wins:**

| # | Condition | Outcome | Summary / impact |
|---|---|---|---|
| 1 | any line `plain_no_forex` | **BLOCKED** | "tag N has no forex in the export: it was written as plain INR (the C36 failure). Re-run the shape probe / `setup-b`" |
| 2 | any line `unparsed` | **FAILED** | `FAILED_IMPACT` |
| 3 | any voucher not `balanced` | **FAILED** | `FAILED_IMPACT` (names the voucher and Σ) |
| 4 | any voucher not `base_matches_dataset` | **BLOCKED** | drift: "Tally's stored base differs from the dataset: the expected figures probes 16/18/21 use are wrong. Fix the dataset, don't trust this run" |
| 5 | routes ⊆ {`stated`, `field`} | **CONFIRMED** | `OK_IMPACT` |
| 6 | `computed` among the routes | **DIFFERENT** | `COMPUTED_IMPACT` |

In every outcome, `usd_ledger`'s `closing_form` (`"plain"`, or `"expression"` when `parse_decimal` raises) is
observed. When it is `"expression"`, the summary says "the forex party's ClosingBalance exports as an expression", and
`LEDGER_EXPRESSION_NOTE` is appended to `spec_impact` (Review Focus 4). It is recorded, not judged.

- [x] **Step 1: Write the failing tests** (`v2/tests/probes/test_p22_forex.py`; harness helpers as in
  `test_p15_unicode_compound_units.py`):

```python
from decimal import Decimal

from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p22_forex as p22
from v2.probes import registry
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import USD_EXPORT_PARTY, forex_vouchers
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books(**knobs) -> FakeBooks:
    books = FakeBooks(name=B, educational=True, **knobs)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-25T12:00:00+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    await run_probe(p22.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(22)["parts"]["B"]


def _edit_line(books, tag, ledger, **changes):
    def mutate(state):
        v = next(v for v in state["vouchers"].values() if v["narration"].startswith(f"[S0-B:{tag}]"))
        line = next(l for l in v["lines"] if l["ledger"] == ledger)
        line.update(changes)
    books.edit_state(mutate)


async def test_forex_sales_confirmed_when_the_amount_states_the_base(tmp_path):
    part = await _run(tmp_path, _books(forex_export_form="full"))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert sorted(obs["vouchers"]) == ["101", "102"]
    assert all(j["balanced"] and j["base_matches_dataset"] for j in obs["vouchers"].values())
    assert {l["route"] for j in obs["vouchers"].values() for l in j["lines"]} == {"stated"}
    assert all(l["parse_decimal_raises"] for j in obs["vouchers"].values() for l in j["lines"])   # expected (§11.2)
    assert part["fixtures"][-3:] == ["p22_B_forex_sales.xml", "p22_B_usd_ledger.xml", "p22_B_currencies.xml"]


async def test_base_only_by_rate_is_different(tmp_path):
    part = await _run(tmp_path, _books(forex_export_form="no_base"))
    assert part["outcome"] == "DIFFERENT" and "face × rate" in part["spec_impact"]


async def test_plain_amount_with_a_forex_field_is_confirmed(tmp_path):
    part = await _run(tmp_path, _books(forex_export_form="plain_plus_field"))
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["vouchers"]["101"]["lines"][0]["route"] == "field"


async def test_plain_inr_without_forex_blocks_as_c36_recurrence(tmp_path):
    part = await _run(tmp_path, _books(forex_storage="plain"))
    assert part["outcome"] == "BLOCKED" and "plain INR" in part["summary"]


async def test_unbalanced_forex_voucher_fails(tmp_path):
    books = _books()
    _edit_line(books, 101, "Export Sales", amount_text="$448.44 @ ₹82.99/$ = ₹37216.05")
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "101" in part["summary"]


async def test_unparsed_amount_fails(tmp_path):
    books = _books()
    _edit_line(books, 102, USD_EXPORT_PARTY, amount_text="-$ ??? @ ₹82.58")
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED"


async def test_base_differs_from_dataset_blocks_as_drift(tmp_path):
    books = _books()
    _edit_line(books, 101, USD_EXPORT_PARTY, amount_text="-$448.44 @ ₹83.00/$ = -₹37220.52")
    _edit_line(books, 101, "Export Sales", amount_text="$448.44 @ ₹83.00/$ = ₹37220.52")
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "differs from the dataset" in part["summary"]


async def test_missing_usd_sale_blocks(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["vouchers"].pop(next(m for m, v in s["vouchers"].items()
                                                      if v["narration"].startswith("[S0-B:102]"))))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "102" in part["summary"] and "setup-b" in part["summary"]


async def test_untagged_voucher_in_the_window_blocks_as_drift(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["vouchers"].__setitem__("99999", {**next(iter(s["vouchers"].values())),
                                                                   "narration": "stray", "date": "20220901"}))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "BLOCKED" and "untagged" in part["summary"]


async def test_needs_probe_5(tmp_path):
    part = await _run(tmp_path, _books(), with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "probe 5" in part["summary"]


async def test_educational_window_is_c43_safe(tmp_path):
    books = _books()
    await _run(tmp_path, books)
    sent = next(r for r in books.requests if "S0VoucherMonth" in r and "01-09-2022" in r)
    assert '<SVTODATE TYPE="Date">02-09-2022</SVTODATE>' in sent


async def test_usd_ledger_closing_expression_is_recorded_not_judged(tmp_path):
    part = await _run(tmp_path, _books(forex_ledger_closing="expression"))
    assert part["outcome"] == "CONFIRMED"
    led = part["observations"]["usd_ledger"]
    assert led["closing_form"] == "expression" and led["currency_name"] == "$"
    assert "ClosingBalance exports as an expression" in part["summary"] and "parity" in part["spec_impact"]


def test_forex_vouchers_view():
    assert sorted(forex_vouchers("educational")) == [101, 102]


def test_registry_wires_probe_22_and_14_stays_last():
    assert registry.info(22).module == "v2.probes.p22_forex" and registry.load_probe(22) is p22.PROBE
    b = [step for step, label in registry.ALL_ORDER if label == "B"]
    assert b.index(22) < b.index(23) < b.index(25) < b.index(14) and b[-1] == 14


def test_judge_on_the_live_shape_capture():
    """The live throwaway (Task 2) judged by the probe's own code: its stated/computed base is the sent ₹37,216.04."""
    from pathlib import Path
    import json
    from v2.probes.reads import parse_vouchers
    shape = sorted(Path("v2/tests/fixtures/sync").glob("forex_shape_*"))[-1]
    chosen = json.loads((shape / "summary.json").read_text())["chosen"]
    raw = (shape / f"variant_{chosen['variant']}.xml").read_text(encoding="utf-8")
    voucher = next(v for v in parse_vouchers(raw) if v["header"]["NARRATION"].startswith("S0-throwaway forex"))
    spec = forex_vouchers("educational")[101]                    # same figures as the throwaway
    judged = p22.judge_voucher(voucher, spec, party_alias=voucher["header"].get("PARTYLEDGERNAME"))
    assert judged["balanced"] and judged["base_matches_dataset"]
```

- [x] **Step 2: Run** → FAIL (`ImportError: p22_forex`).
- [x] **Step 3: Implement.** `company_b_view.py` (imports from `company_b_data` only):

```python
from v2.probes.setup.company_b_data import USD_CURRENCY, USD_EXPORT_PARTY   # add to the existing import

USD_CURRENCY_SYMBOL = USD_CURRENCY.symbol


def forex_vouchers(licence: str) -> dict[int, VoucherSpec]:
    """tag → voucher for every written foreign-currency voucher (company B: the USD export sales 101/102)."""
    return {t: v for t, v in written_vouchers(licence).items() if v.currency != "INR"}
```

  `v2/probes/p22_forex.py`:

```python
"""Probe 22: do forex vouchers expose the INR base amount? (S0 spec §7 "Probe 22", B). Feeds decision 15.

Reads the USD export sales (101/102) with probe 5's confirmed month request — the extractor's own request (S0-D7) —
for the Sep-2022 window (C43-safe: educational 01..02-09-2022). Records every line's raw AMOUNT and any forex-only
fields; `amounts.parse_decimal` raising on an expression is expected (§11.2) and recorded. The forex party's ledger
and the Currency masters are recorded, not judged (plan part 7 Rulings P7-13, P7-14)."""
from __future__ import annotations

from decimal import Decimal

from v2.agent.tally.amounts import AmountParseError, parse_decimal
from v2.agent.tally.envelopes import formula_string
from v2.agent.tally.xml_utils import read_objects
from v2.probes.company_b_view import (USD_EXPORT_PARTY, drift_message, fetch_window, forex_vouchers, loaded_licence,
                                      month_window, tag_of)
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import forex_base, master_request, parse_forex_amount, parse_vouchers

LEDGER_FIELDS = ["Name", "Parent", "CurrencyName", "OpeningBalance", "ClosingBalance"]
CURRENCY_FIELDS = ["Name", "MailingName", "ExpandedSymbol", "DecimalPlaces"]
OK_IMPACT = ("Forex voucher lines carry the INR base amount in the export (the AMOUNT's stated base, or a plain field): "
             "S1 stores the base in every amount column and keeps face value + rate in raw — decision 15 holds, no "
             "conversion at read time.")
COMPUTED_IMPACT = ("The export gives only the forex face value and rate: S2 computes base = face × rate (ROUND_HALF_UP to "
                   "paise) at extract time and stores it; decision 15 holds with one documented computation, and "
                   "parity must tolerate Tally's own rounding of that product.")
FAILED_IMPACT = ("The INR base can't be read from a forex voucher line unambiguously, or it doesn't balance: decision 15 "
                 "is revisited before S1 (Part 1 probe 22).")
LEDGER_EXPRESSION_NOTE = (" The forex party's ClosingBalance exports as an expression, not a number: S1 parity (decision "
                          "11) must parse its base part the same way, or read that ledger's balance from the TB.")


def _route(line: dict) -> tuple[str, Decimal | None, bool, list[str]]:
    text = line["amount_raw"]
    try:
        plain, raises = parse_decimal(text), False
    except AmountParseError:
        plain, raises = None, True
    hints = sorted(k for k, v in line["fields"].items() if k != "AMOUNT" and ("$" in v or "@" in v))
    fa = parse_forex_amount(text)
    if fa is not None:
        base, how = forex_base(fa)
        return how, base, raises, hints
    if plain is not None:
        return ("field" if hints else "plain_no_forex"), plain, raises, hints
    return "unparsed", None, raises, hints


def judge_voucher(voucher: dict, spec, *, party_alias: str | None = None) -> dict:
    expected = {l.ledger: abs(l.amount) for l in spec.lines}
    if party_alias and party_alias not in expected:          # the live throwaway's party stands in for the dataset's
        expected[party_alias] = expected.pop(spec.party)
    lines = []
    for line in voucher["ledger_lines"]:
        route, base, raises, hints = _route(line)
        lines.append({"ledger": line["fields"].get("LEDGERNAME", ""), "amount_raw": line["amount_raw"],
                      "route": route, "base": None if base is None else f"{base:.2f}",
                      "parse_decimal_raises": raises, "forex_fields": hints})
    bases = [Decimal(l["base"]) for l in lines if l["base"] is not None]
    known = len(bases) == len(lines) and lines
    return {"tag": spec.tag, "lines": lines, "routes": sorted({l["route"] for l in lines}),
            "balanced": bool(known) and sum(bases, Decimal("0.00")) == 0,
            "base_matches_dataset": bool(known) and all(
                abs(Decimal(l["base"])) == expected.get(l["ledger"]) for l in lines)}


def verdict(judged: list[dict]) -> tuple[Outcome, str, str]:
    for j in judged:
        if "plain_no_forex" in j["routes"]:
            raise ProbeBlocked(f"forex_sales: tag {j['tag']} has no forex in the export — it was written as plain INR "
                               "(the C36 failure). Re-run plan part 7's shape probe / setup-b before judging.")
    bad = [j["tag"] for j in judged if "unparsed" in j["routes"]]
    if bad:
        return Outcome.FAILED, f"forex line(s) of {bad} parse to no base", FAILED_IMPACT
    bad = [j["tag"] for j in judged if not j["balanced"]]
    if bad:
        return Outcome.FAILED, f"forex voucher(s) {bad} don't balance to 0.00 in INR", FAILED_IMPACT
    bad = [j["tag"] for j in judged if not j["base_matches_dataset"]]
    if bad:
        raise ProbeBlocked(f"forex_sales: Tally's stored base for {bad} differs from the dataset — the expected "
                           "figures probes 16/18/21 use are wrong; re-run `setup-b` verify or restore the backup.")
    routes = {r for j in judged for r in j["routes"]}
    if routes <= {"stated", "field"}:
        return Outcome.CONFIRMED, f"INR base read from the export ({', '.join(sorted(routes))})", OK_IMPACT
    return Outcome.DIFFERENT, "INR base only computable as face × rate", COMPUTED_IMPACT


async def run_b(ctx: ProbeContext) -> PartResult:
    licence = loaded_licence(ctx.store.environment)
    confirmed = ctx.store.confirmed("voucher_month")
    if confirmed is None:
        raise ProbeBlocked("No confirmed month request: run probe 5 first.")
    specs = forex_vouchers(licence)
    months = sorted({(v.date.year, v.date.month) for v in specs.values()})
    found: dict[int, dict] = {}
    inr_fields: set[str] = set()
    for year, month in months:
        start, end = month_window(year, month, licence)
        step = "forex_sales" if len(months) == 1 else f"forex_sales_{year}_{month:02d}"
        result, raw = await fetch_window(ctx, step, confirmed["xml_template"], licence,
                                         start.strftime("%d-%m-%Y"), end.strftime("%d-%m-%Y"))
        if result["drifted"]:
            raise ProbeBlocked(drift_message(step, result))
        for v in parse_vouchers(raw):
            tag = tag_of(v["header"].get("NARRATION", ""))
            if tag in specs:
                found[tag] = v
            elif v["header"].get("VOUCHERTYPENAME", "").startswith("Sales"):
                inr_fields |= {k for line in v["ledger_lines"] for k in line["fields"]}
    missing = sorted(set(specs) - set(found))
    if missing:
        raise ProbeBlocked(f"forex_sales: USD export sale(s) {missing} not in Tally — run `setup-b` with the plan "
                           "part 7 loader (Task 6) first.")
    judged = [judge_voucher(found[t], specs[t]) for t in sorted(specs)]
    ctx.observe("vouchers", {str(j["tag"]): j for j in judged})
    ctx.observe("extra_fields", sorted({k for t in found for line in found[t]["ledger_lines"]
                                        for k in line["fields"]} - inr_fields))

    rows = read_objects(await ctx.send("usd_ledger", master_request("S0P22Ledger", "Ledger", LEDGER_FIELDS,
                        ctx.company_name, filters=[("S0P22IsParty", f"$Name = {formula_string(USD_EXPORT_PARTY)}")])),
                        "LEDGER", LEDGER_FIELDS)
    closing = rows[0]["ClosingBalance"] if rows else None
    try:
        closing_form = "plain" if parse_decimal(closing) is not None else "missing"
    except AmountParseError:
        closing_form = "expression"
    ctx.observe("usd_ledger", {"found": bool(rows), "currency_name": rows[0]["CurrencyName"] if rows else None,
                               "closing_text": closing, "closing_form": closing_form})
    currencies = read_objects(await ctx.send("currencies", master_request("S0P22Currencies", "Currency",
                              CURRENCY_FIELDS, ctx.company_name)), "CURRENCY", CURRENCY_FIELDS)
    ctx.observe("currencies", currencies)

    outcome, summary, impact = verdict(judged)
    if closing_form == "expression":
        summary += "; the forex party's ClosingBalance exports as an expression"
        impact += LEDGER_EXPRESSION_NOTE
    return PartResult(outcome, f"{summary} — tags {sorted(specs)}", spec_impact=impact)


PROBE = Probe(
    id=22,
    name="forex",
    question="Does a forex voucher's ledger line expose the INR base amount, and does it balance to 0.00?",
    feeds=("decision 15",),
    parts={"B": run_b},
    requires=(0, 5),
    educational_sensitive=True,
)
```

  `registry.py`: replace the probe 22 row with
  `ProbeInfo(22, "forex", "B", "B", module="v2.probes.p22_forex"),   # plan part 7 (C36 lifted)`.
  `ALL_ORDER` stays unchanged (22 before 23, 25; 14 last, Ruling Q6). `FIRST_ORDER` stays unchanged.

  `fake_books.py`:
  - add `"S0P22"` to `B_PROBE_COLLECTIONS`;
  - in `_b_collection`, `kind == "Currency"` returns the currencies;
  - `_ledger_export` honours `currencyname` and the closing knob.

  Check that `master_request` refuses nothing here (no period vars).
- [x] **Step 4: Run** → PASS. Run the full suite plus `-W error`. Also check `test_isolation.py` stays green (the probe
  imports only the view and reads). Record the count.
- [x] **Step 5: Commit** `v2/probes/company_b_view.py v2/probes/p22_forex.py v2/probes/registry.py
  v2/tests/probes/fake_books.py v2/tests/probes/test_p22_forex.py`:
  `feat(bi/v2): probe 22 — forex INR base on the extractor's request (plan part 7 task 4)`.

---

### Task 5: Code review before the live run

**Files:** Create `docs/code-review-bi-s0-part7-<YYYY-MM-DD>.md`.

- [ ] **Step 1:** Run `superpowers:requesting-code-review` (or the `code-review` agent, opus) on
  `git diff P7_BASE..HEAD -- v2/`. Ask the reviewer to check at least:
  - **write safety:**
    - list-before-create for the currency and ledger;
    - read-back after every write;
    - `delete_b_voucher` verifies in the voucher's own day;
    - Gulf is never altered;
    - no existing voucher is touched;
    - a forex voucher is refused with inventory/bills or a rounding tie.
  - **dataset:**
    - the sha pin covers every non-USD voucher in both licences;
    - the new ledger is excluded from the debtor rotation;
    - `expected_figures` / `_expected_group_balances` include 101/102 exactly once;
    - C41's purchase plan and C35's pool are unmoved.
  - **loader:**
    - the formerly-skipped exemption can't hide any other gap;
    - the currency pause fallback;
    - the problem text for a wrong currency on an existing ledger.
  - **FakeBooks:**
    - defaults equal the live capture (Task 3.9);
    - candidate knobs are labelled;
    - no forex → byte-identical exports (the p05/p21/p03/p23 suites untouched);
    - C33/C43 intact.
  - **probe 22:**
    - the verdict table (esp. "plain INR" BLOCKED, never CONFIRMED; base ≠ dataset BLOCKED);
    - dates C43-safe;
    - `requires=(0, 5)`;
    - 14 still last;
    - isolation (the probe never imports `setup`).
  - **Review Focus items 1–5**, one test each.
- [ ] **Step 2:** Store the findings. Fix the confirmed ones test-first (`superpowers:receiving-code-review`). Re-run the
  suite, with and without `-W error`, and record the count. The doc lists the suites **not** run: live Tally (Task 6),
  tier-C timing (⏭ Q29), and the root `tests/` suite (it doesn't collect `v2/`).
- [ ] **Step 3: CLI smoke (no Tally):**
  ```bash
  mkdir -p /tmp/s0-smoke-p7
  uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p7/results.json list | grep -E '^ ?22 '
  ```
  Expected: `22 forex B … not run` (no longer "not built").
- [ ] **Step 4: Commit** the review doc and fixes (only the files named), plus a tracker change-log row with the
  review path.

---

### Task 6: Live run — load 101/102, back up, probe 22, blast-radius re-runs (operator at the Mac)

**Files (written by the runner, then committed):** `v2/probes/results/results.json`,
`v2/tests/fixtures/sync/p22_B_*` (+ `p21_B_*`, `p18_B_*` if the H2 re-runs happen),
`docs/bi-s0-probe-results-<date>.md`. Logs go to `logs/`.

- [ ] **Step 1: Pre-flight** (Task 2 step 1's commands). Also expect `$` in the currency list, no `ZZ Forex Probe`
  ledger, and 958 tagged vouchers (Task 2 step 8's state).
- [ ] **Step 2: F2 ≥ 31-03-2026** (Task 2 step 4). `setup-b` also pauses for it.
- [ ] **Step 3: Load** (the company-B loader; it writes only what is missing):
  ```bash
  uv run --project v2 python -m v2.probes setup-b 2>&1 | tee logs/setup-b-forex-live-$(date +%F).log
  ```
  Expected (changed 2026-09-25, D8 + review I1):
  - `currencies: created 0, skipped 1` — always 0 created: setup-b never creates a currency (D8). `$` was made in the
    UI and is in `100000-pre-forex-with-usd-2026-09-25`. **If B has no `$`** (e.g. restored from an older backup),
    setup-b stops before any write with exit 1 and `setup-b failed: … create `$` (Formal name USD, ISO USD) in the
    UI: Create → Currency … Nothing was written.` That is the designed stop, not a loader bug: create `$` in the UI
    (or restore `…pre-forex-with-usd…`) and re-run;
  - `groups: created 0, skipped 2`, `units: created 0, skipped 3`, `items: created 0, skipped 5`;
  - `ledgers: created 1, skipped 25` (the USD party);
  - `vouchers: created 2, skipped 958`;
  - Notes: `[S0-B:101, 102] written now — skipped under C36 until plan part 7…`, **and** `[S0-B:101, 102] read back
    as forex: currency, face, rate and INR base as sent (plan part 7 review I1).` (plus the TB total note);
  - **no Problems**, and `Company B loaded`, which re-stamps `company_b_loaded_at`.

  **If Problems name `[S0-B:101]`/`[S0-B:102]` "not stored as the forex voucher that was sent"** (plain INR = C36, or a
  different base/face/rate/currency) or "forex read-back … failed": setup-b exits 1 and does **not** stamp. Do **not**
  take Step 5's backup. Restore `100000-pre-forex-with-usd-2026-09-25` (setup-b never re-writes an existing tag) and
  debug offline.

  If there is a voucher-create pause: **don't** type the voucher by hand. Stop, restore (Task 2 step 7, but using the
  **pre-forex** backup), and debug offline (`superpowers:systematic-debugging`): the live shape and the loader
  disagree.
- [ ] **Step 4: Read-back sanity** (read-only):
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p7-forex-readback-$(date +%F).log
  import httpx
  from v2.probes.companies import COMPANIES
  from v2.probes.reads import parse_forex_amount, parse_vouchers
  from v2.probes.setup.company_b_data import USD_EXPORT_PARTY
  from v2.probes.setup.writes import TallyWriter, b_day_voucher_request
  B = COMPANIES["B"]
  with httpx.Client(base_url="http://localhost:9000", trust_env=False) as http:
      w = TallyWriter(http, print)
      for day in ("01-09-2022", "02-09-2022"):
          for v in parse_vouchers(w.post(b_day_voucher_request(B, day))):
              if v["header"]["NARRATION"].startswith(("[S0-B:101]", "[S0-B:102]")):
                  print(day, v["header"]["NARRATION"], [(l["fields"].get("LEDGERNAME"), l["amount_raw"]) for l in v["ledger_lines"]])
      print(w.ledger_details(B, USD_EXPORT_PARTY))
      print(w.ledger_details(B, "Gulf Office Supplies LLC"))       # unchanged: no CurrencyName
  EOF
  ```
  (Under Educational, 101 is on 01-09 and 102 on 02-09. Under a licensed Tally, read 02-09 and 05-09.)
- [ ] **Step 5: New restore point:**
  ```bash
  uv run --project v2 python - <<'EOF' 2>&1 | tee logs/p7-backup-B-loaded-forex-$(date +%F).log
  import datetime
  from v2.probes.operator.auto import build_auto_operator
  from v2.probes.operator.company_a import backup_company
  auto = build_auto_operator(stop_any_tally=True, echo=print)
  try:
      print(backup_company(auto.control, auto.config, "B", f"company-B-loaded-forex-{datetime.date.today()}"))
  finally:
      auto.close()
  EOF
  ```
  (One licence click. Tally resets F2 on this restart. Probe reads don't care about F2.)
- [ ] **Step 6: Probe 22** (manual mode, never `--auto`):
  ```bash
  uv run --project v2 python -m v2.probes run 22 --company B 2>&1 | tee logs/p22-live-$(date +%F).log
  ```
  CONFIRMED, DIFFERENT and FAILED are findings: record them and **don't re-run**. A BLOCKED "no forex" or "differs
  from the dataset" means stop: restore `…-loaded-forex-<date>` only if something changed, and debug offline.
- [ ] **Step 7: Blast-radius re-runs (H2; recommended yes).** The dataset these two probes judge has changed. Sep 2022
  now holds 20 vouchers, and FY 2022-23's TB includes the forex base. So re-run them on the live B, in this order,
  with 14 **not** re-run (it stays last in any session that runs it):
  ```bash
  uv run --project v2 python -m v2.probes run 21 --company B 2>&1 | tee logs/p21-rerun-forex-$(date +%F).log
  uv run --project v2 python -m v2.probes run 18 --company B 2>&1 | tee logs/p18B-rerun-forex-$(date +%F).log
  ```
  Expected: both still CONFIRMED. 21 now reports 240 FY 2022-23 vouchers with `fy2022_month_09` at 20, and its
  size stats include the forex text. If 21's month parse or size maths chokes on the forex AMOUNT, that is a **real
  extractor finding**: record it, don't fix it live. The previous parts move to `history` automatically.
- [ ] **Step 8: Read the numbers out:**
  ```bash
  uv run --project v2 python -c "import json; p=json.load(open('v2/probes/results/results.json'))['probes']; \
  [print(k, p[k]['parts']['B']['outcome'], '—', p[k]['parts']['B']['summary']) for k in ('22','21','18')]; \
  print(json.dumps(p['22']['parts']['B']['observations'], ensure_ascii=False, indent=1))" 2>&1 | tee logs/s0-p7-numbers-$(date +%F).log
  ```
- [ ] **Step 9: List, report, commit the evidence:**
  ```bash
  uv run --project v2 python -m v2.probes list | grep -E '^ ?(18|21|22) '
  uv run --project v2 python -m v2.probes report
  git diff --stat v2/probes/results/results.json           # only probes 22 (+21, 18), environment.company_b_loaded_at
  git add v2/probes/results/results.json v2/tests/fixtures/sync/p22_B_* v2/tests/fixtures/sync/p21_B_* \
          v2/tests/fixtures/sync/p18_B_* docs/bi-s0-probe-results-$(date +%F).md
  git commit -m "data(bi/v2): USD export sales 101/102 loaded as forex; probe 22 live on company B" \
             -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
  ```
  Then update tracker row 22 (outcome, proof, logs, backup name), rows 21/18 (the re-run line), and "Resume here", with
  a change-log row, **in the same turn**.

---

### Task 7: Spec, tracker, LESSONS, Part 1 spec, roadmap (same session)

**Files:** `docs/specs/2026-09-22-bi-s0-probes-design.md`, `docs/specs/2026-09-21-bi-part1-sync-design.md`,
`docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md`, `LESSONS.md`, and this plan (tick the boxes).

- [ ] **Step 1: S0 spec.** Add a header line `**Changed <date> (plan part 7):**` covering:
  - (a) C36 lifted: how 101/102 are written (currency master, party, AMOUNT form, no bills), with the evidence folder.
    Mark the "Changed 2026-09-24 (Ruling C36)" line **superseded** (keep its text).
  - (b) §4.3: the Ledgers row gains the USD export party (or notes S-A), Groups/Ledgers mention the Currency master,
    and §4.3's loader rules gain "currencies: list-before-create; a party's currency is never altered by the loader".
  - (c) §7 probe 22 as built: steps, verdict table, outcome.
  - (d) §6 batch 5: drop "(BLOCKED — C36)".
  - (e) §11.4: the formerly-skipped exemption.
  - (f) §11.5 row 22: `forex_sales`, `usd_ledger`, `currencies`.
  - If the edition refused forex, record instead: "probe 22 BLOCKED — Educational/Wine can't store forex (evidence …);
    confirm on tier C".
- [ ] **Step 2: Tracker.**
  - Row 22 ✅ with its real outcome and proof (commit SHAs, logs, fixtures, backups `100000-pre-forex-<date>` and
    `100000-company-B-loaded-forex-<date>`).
  - Rows 21/18 get their re-run line.
  - Update the §0 S0 row, and §1 decision 15 (if it changes).
  - Rewrite "Resume here": the S0 exit-gate check (§10) is next, with the B restore point `…-loaded-forex-<date>`.
  - Add a change-log row naming every contradicted expectation (e.g. the tag names, F2-only, UI-only currency, a ledger
    closing expression).
- [ ] **Step 3: LESSONS.md §15, new rule 28** (and 29 if needed):
  - how a forex voucher must be written over XML (the proven AMOUNT form, currency master and ledger currency, what
    failed);
  - how it exports (stated base or not, extra fields, ledger closing form);
  - "never alter a ledger's currency once it has vouchers" (fact 1's reasoning, if measured);
  - the delete-verification window trap (fact 3).

  Each rule carries the scope caveat: TallyPrime 7.0 Edit Log, **Educational**, Wine 11.0.
- [ ] **Step 4: Part 1 spec.** One dated "Changed" line on decision 15 / §5 "Cloud" amount columns: CONFIRMED (base in
  the export), DIFFERENT (S2 computes face × rate, and the rounding rule), or FAILED (decision 15 reopened). Add the
  ledger-closing note for decision 11 parity if it was an expression.
- [ ] **Step 5: Roadmap.** Set C S0 row: probe 22 done (outcome); what remains (the §10 exit gate, then the S1 spec).
- [ ] **Step 6: Commit** docs only: `docs(bi/v2): plan part 7 results into specs, tracker, LESSONS, roadmap`.

---

## State matrix (CLAUDE.md "Spec & test plan thoroughness")

S0 writes **no DB**, so there are no DB-persistence scenarios. The "refresh round-trip" analogue is Task 3.10
(write → read back through the extractor's request → the same base).

### Shape runner (`forex_shape.run`) × Tally behaviour

| Tally behaviour (FakeBooks knob) | Expected outcome | Throwaways left | Currency kept | Test |
|---|---|---|---|---|
| stores the F1 expression (default) | `stored_forex`, V1, V2 not run | none | yes | `test_run_stores_forex_on_both_parties_and_cleans_up` |
| stores plain INR (`forex_storage="plain"`) | `forex_dropped`, V2 run | none | yes | `test_forex_dropped_when_tally_stores_plain_inr` |
| accepts only F2 (`forex_forms_accepted=("no_base",)`) | `stored_forex`, V2 | none | yes | `test_only_the_no_base_form_accepted_picks_v2` |
| refuses a currency create | `currency_refused`, no ledger sent | none | — | `test_currency_refused_stops_before_any_throwaway` |
| currency create raises a modal | `popup` + hint | none | — | `test_a_currency_popup_stops_with_the_hint` |
| V0 can't post | `control_failed`, only V0 | none | yes | `test_control_failure_is_reported_first` |
| forex refused on a base-currency party | `stored_forex`, V3 `refused` | none | yes | `test_base_party_refusal_is_evidence_not_failure` |
| delete answers 1 but keeps the voucher | raises "still there" | (restore) | yes | `test_a_delete_that_does_not_stick_is_caught_in_the_2022_window` |
| leftover from an aborted run | raises "leftover" before any write | — | — | `test_leftover_throwaway_refuses_to_run` |
| company A open | `GuardError`, no import sent | — | — | `test_wrong_company_is_refused_before_any_write` |

### Writer (`validate_b_voucher` / `create_b_voucher` / masters) × input

| Input | Expected | Test |
|---|---|---|
| forex + bills or inventory | ValueError before sending | `test_validate_refuses_forex_with_inventory_or_bills` |
| a line ≠ face × rate | ValueError | `test_validate_refuses_a_line_that_is_not_face_times_rate` |
| face × rate is a rounding tie | ValueError | `test_validate_refuses_a_rounding_tie` |
| forex sale, F1 | expression on the wire, base booked | `test_forex_sale_goes_out_as_expression_and_books_the_base` |
| text ↔ parser, both signs, both forms | round-trips | `test_forex_text_round_trips_through_the_parser` |
| currency absent / present / refused / modal | create+read-back / nothing sent / WriteFailed / WriteTimeout | `test_create_currency_lists_first_and_reads_back`, `…_refused_raises`, `…_popup_times_out` |
| party ledger with a currency | `CURRENCYNAME` sent + read back | `test_party_ledger_currency_is_sent_and_read_back` |
| delete not sticking (2022) | WriteFailed | `test_delete_b_voucher_verifies_in_the_vouchers_own_day` |

### Loader (`setup-b`) × company-B state × licence

| Company B state | Licence | Expected | Test |
|---|---|---|---|
| empty shell | educational | 960 vouchers, currency before USD ledger, verify clean | `test_load_creates_the_currency_before_the_usd_ledger`, `test_full_load_with_forex_verifies_clean` |
| fully loaded (part 7) | educational | 0 creates incl. currency | `test_second_load_sends_no_currency_create` |
| live B after C36 (958, no `$`, no USD party) | educational | +1 currency, +1 ledger, +2 vouchers, **note** not problem | `test_formerly_skipped_gap_is_a_note_not_a_problem` |
| as above + 103 missing | educational | FY 2022-23 problem stays | `test_any_other_gap_in_that_fy_is_still_a_problem` |
| USD party exists without its currency | educational | problem, never altered | `test_existing_usd_party_without_its_currency_is_a_problem` |
| a USD voucher without fx fields | any | CompanyBLoadError before any voucher | `test_a_foreign_voucher_without_fx_fields_stops_the_load` |
| forex sale re-read via the extractor's request | educational | bases ±₹37,216.04 / ±₹95,897.68, Σ 0 | `test_forex_sale_round_trips_through_the_extractors_request` |
| both licences | educational + licensed | 101/102 dates (1, 2) / (2, 5); every other voucher byte-identical | `test_usd_sales_are_written_with_forex`, `test_every_other_voucher_is_byte_identical_to_p7_base` |

### Probe 22 × export shape

| Export shape (knob / state edit) | Outcome | Test |
|---|---|---|
| AMOUNT states the base | CONFIRMED | `test_forex_sales_confirmed_when_the_amount_states_the_base` |
| plain AMOUNT + a forex field | CONFIRMED (`field`) | `test_plain_amount_with_a_forex_field_is_confirmed` |
| expression without base | DIFFERENT | `test_base_only_by_rate_is_different` |
| plain INR, no forex anywhere | BLOCKED (C36 recurrence) | `test_plain_inr_without_forex_blocks_as_c36_recurrence` |
| a line unparseable | FAILED | `test_unparsed_amount_fails` |
| voucher off by ₹0.01 | FAILED | `test_unbalanced_forex_voucher_fails` |
| balanced but a different base | BLOCKED (drift) | `test_base_differs_from_dataset_blocks_as_drift` |
| 102 missing | BLOCKED (run setup-b) | `test_missing_usd_sale_blocks` |
| untagged voucher on 01-09-2022 | BLOCKED (drift) | `test_untagged_voucher_in_the_window_blocks_as_drift` |
| probe 5 not confirmed | BLOCKED | `test_needs_probe_5` |
| ledger closing is an expression | outcome unchanged + note | `test_usd_ledger_closing_expression_is_recorded_not_judged` |
| the live throwaway capture | balanced, base = sent | `test_judge_on_the_live_shape_capture` |

## Fixture matrix

| Category | Fixture | Source | Used by |
|---|---|---|---|
| Offline strings | the F1 form with and without spaces, with commas, a symbol word, F2 with `Rs.`, 7 non-expressions | hand-written (candidates) | `test_forex_amount.py` |
| Fake Tally answers | Currency list (₹ + `$`), ledger detail with `CurrencyName`, forex AMOUNT per knob, a closing expression | `FakeBooks` knobs (candidate → live-pinned in 3.9) | Tasks 1.2, 1.3, 3, 4 |
| Live evidence (Task 2) | `forex_shape_<date>/company_features.xml`, `currencies_before.xml`, `export_sales_ledger.xml`, `currencies_after.xml`, `ledgers_after_create.xml`, `variant_V0.xml`, `variant_V1.xml` (+`V2`), `variant_V3.xml`, (`ui_entered.xml` if the UI fallback ran), `summary.json` | `forex_shape.run`, live company B | `test_fake_books_forex.py`, `test_judge_on_the_live_shape_capture` |
| Live captures (Task 6) | `p22_B_forex_sales.xml`, `p22_B_usd_ledger.xml`, `p22_B_currencies.xml` (+ `.json` sidecars); re-run `p21_B_*`, `p18_B_*` | the runner | results doc, future S2 extractor tests |
| Regression (unchanged bytes) | `p21_B_fy2022_month_02.xml` (p03 B, p23 B tests), p05/p21 fake exports without forex | committed | must stay green untouched |

The messy real shapes are modelled on purpose (Test reality rule 2):
- a forex party that is a **separate** ledger next to an INR customer with the "same" name root;
- a bill-wise INR customer (Gulf) with 87 vouchers that must not move;
- a GST-enabled company selling zero-rated with no GST lines;
- a non-bill-wise forex party;
- Educational day 1/2 dates.

---

## Rulings / ambiguities (decisions made while writing, with the recommendation)

**Needs a human (answer in Step 0.4, before Task 1):** both **decided 2026-09-25 by the controller, on the user's
standing instruction to proceed**: **H1 = S-B** (new ledger `Gulf Office Supplies LLC (USD)`, the recommendation) and
**H2 = yes** (re-run 21 and 18 B after the load).

- **H1 = Ruling P7-2: which ledger carries the USD sales.** — **Decided 2026-09-25 (controller, on the user's
  standing instruction to proceed): S-B**, the new ledger `Gulf Office Supplies LLC (USD)`.
  - **Recommend S-B:** a new ledger `Gulf Office Supplies LLC (USD)` under Sundry Debtors, `CURRENCYNAME` `$`, not
    bill-wise, no GSTIN, used only by 101/102. It is excluded from the debtor rotation, so no other voucher moves.
  - **Why not alter Gulf:** it has 87 live INR vouchers (fact 1). A currency change could re-cast them, and the
    loader's rule is "never alter".
  - **Alternative S-A:** 101/102 stay on Gulf (INR ledger) with forex amounts, and no new ledger. It is simpler, but
    it doesn't model a real exporter's USD ledger, and it can't measure a forex ledger's closing balance.
  - Task 2 measures both (V1 vs V3). If only S-A works, the plan falls back to it automatically, after asking.
- **H2 = Ruling P7-16: re-run probes 21 and 18 B after loading.** — **Decided 2026-09-25 (controller, on the
  user's standing instruction to proceed): yes**, re-run 21 and 18 B after the load.
  - **Recommend yes.** The dataset they judge changed (Sep 2022: 18 → 20 vouchers; FY 2022-23 TB includes ₹1,33,113.72
    more in Sundry Debtors/Sales). This is the blast-radius check on the extractor's month read and the TB anchor, and
    the re-run rule allows it: the judged expectation changed.
  - Probe 16 B is not re-run (its FAILED is C45, unrelated). 14 is not re-run.
  - Cost: two cheap reads, plus `history` entries.

**Decided by the controller, 2026-09-25 (review fix round):**

- **R-SYM (live discovery, `logs/p7-forex-discovery-2026-09-25.log`):** company B's base currency exports `NAME` =
  a literal `?` (byte 0x3F), with MAILINGNAME `INR` and EXPANDEDSYMBOL `INR`. Every ledger's `CurrencyName` is `?`
  too. Hindi text round-trips fine (probe 15), so this is how B stores its base symbol (lost at UI creation under
  Wine), not a transport bug. What changed:
  - `ForexLine.base_symbol` has no default. The runner reads it from the Currency list (`forex_shape.base_currency`)
    and never hard-codes `₹`.
  - The classifier accepts the discovered symbol or none.
  - The runner tries the variants in this order: V1 = the full form with the discovered symbol (`@ ?82.99/$ =
    -?37216.04`); V1b = the rate with no base symbol (`@ 82.99/$ = -37216.04`), if V1 isn't stored; V2 = no stated
    base; V3 = the INR party with the chosen form.
  - Each variant is judged only on its read-back values (I1).
  - `FakeBooks`' base currency is `?`. **Task 3 must pass the chosen `base_symbol` into `_forex_of` / the seed.**
- **R-F2 (replaces the `input()` pause; review M2 / D6):** `run(..., f2_confirm: Callable[[], None])`, called once,
  after the currency step and before the first throwaway. The default asks on the console, and it refuses
  (`WriteRefused`, before any request) unless stdin is a tty. The controller sets F2 itself and passes
  `f2_confirm=lambda: None`. Step 5 shows the script-file form.

**Decided here:**

- **P7-1:** discover the shape on **throwaways** (`ZZ Forex Probe …` ledgers, `S0-throwaway forex` vouchers on
  01-09-2022), never on tags 101/102 directly. A wrong real voucher would be permanent (the loader is idempotent by
  tag, C17) and would need a restore.
- **P7-3:** the USD sales carry **no bill allocations** (a forex bill's AMOUNT form is another unverified shape), and
  the new party is **not bill-wise**, so its bill-wise total can't disagree with its balance (review #2's secondary
  point).
- **P7-4:** currency symbol `$` with formal name `USD`, 2 decimals, "cent". If `$` is refused as a master name, retry
  with symbol `USD` (a ruling + test). The Currency master is **kept** after the shape run.
- **P7-5:** AMOUNT form order:
  1. F1 `-$448.44 @ ₹82.99/$ = -₹37216.04`, the review's form;
  2. F2 without the base;
  3. a UI-entered voucher whose export becomes the shape;
  4. otherwise BLOCKED.
  The base symbol is whatever B's base currency exports (step 3).
- **P7-6:** "Enable multi-currency" / company features are **discovered** (candidate Company fields, recorded not
  judged) and, if needed, toggled **in the UI only** (the LESSONS rule 4 analogue). The Currency master create is
  tried over XML first (no verified op), with a UI pause as the fallback, like every other master (C11).
- **P7-7:** if the Educational edition refuses forex by every route: restore the pre-forex backup, keep C36, and
  leave probe 22 **BLOCKED** with the reason and "confirm on tier C". Not FAILED: the question wasn't answerable
  here, and decision 15 isn't disproved.
- **P7-8:** dates. Throwaways on 01-09-2022; 101/102 on 01/02-09-2022 (Educational), both C43-safe. The probe window
  is `month_window(2022, 9)` (educational 01..02). F2 is set ≥ 31-03-2026 before every voucher write, because Tally
  resets it on restart.
- **P7-9:** the loader's pre-run drift check treats a gap made **only** of `FORMERLY_SKIPPED_TAGS` as a note. Any other
  gap stays a problem (fact 2).
- **P7-10:** `VoucherSpec` gains `currency_symbol` and `fx_rate`, and `_build_usd_sale` keeps its three draws in order.
  Every other voucher is pinned byte-identical to `P7_BASE` by sha (both licences), the C41 pattern.
- **P7-11:** FakeBooks defaults become the **live** read-back (Task 3.9, pinned to the committed capture). Unmeasured
  alternatives stay as labelled knobs so every probe-22 branch has a test (the part-6 pattern).
- **P7-12:** `forex_shape` verifies deletes in the voucher's own day (`delete_b_voucher`). `delete_voucher`'s
  FY 2025-26 window is left as is for company A (fact 3). Changing it is out of scope, and it is noted in the review.
- **P7-13:** probe 22's verdict:
  - base stated or in a plain field → CONFIRMED;
  - only face × rate → DIFFERENT (S2 computes, with a documented rounding rule);
  - unparseable or unbalanced → FAILED;
  - no forex at all, a missing voucher, or a base ≠ dataset → BLOCKED.

  "One unambiguous parse rule" (spec §7) is read as "the stated `= base` part". Multiplying face × rate is a
  computation, so it is DIFFERENT, not CONFIRMED. The Part 1 wording is "no conversion at read time".
- **P7-14:** the forex party's `ClosingBalance` form and the Currency list are **recorded, not judged**. An expression
  closing adds a parity note to `spec_impact` (Review Focus 4).
- **P7-15:** `requires=(0, 5)` (like probe 15). `ALL_ORDER` is unchanged: 22 already sits after 15 and before 23/25,
  and 14 stays last (Q6).
- **P7-17:** after the load, a new backup `100000-company-B-loaded-forex-<date>` becomes B's restore point.
  `…-loaded-2026-09-24` and `…-pre-forex-<date>` are kept.
- **P7-18:** expected-figure changes, all derived rather than hand-set:
  - FY 2022-23: 238 → 240 vouchers;
  - total: 958 → 960 written;
  - the USD party: −₹1,33,113.72 at the books' end;
  - Export Sales: +₹1,33,113.72 (reset each FY in Tally, so it isn't compared across FYs).
- **P7-19:** the shape evidence lives in its own dated subfolder `forex_shape_<date>/`, written by the runner and
  committed once. Probe 22's steps are `forex_sales`, `usd_ledger`, `currencies` (§11.5 row 22 gains the last two).
- **P7-20:** the multi-currency Company field names are candidates, recorded only. The definitive answer is whether
  the currency create and the V1 read-back worked.

## Self-review (done while writing)

- **Spec coverage:**

  | Spec item | Where |
  |---|---|
  | §7 probe 22 (raw AMOUNT text, candidate fields, `parse_decimal` raising recorded, CONFIRMED/FAILED rule, balance 0.00 per voucher) | Task 4 + Task 6 |
  | §4.3 "one USD export customer", "2 USD export sales" | Task 3 (+ H1) |
  | C36 lift | Tasks 2, 3, 7 |
  | §4.5 guards (company, mutation, request, C43) | Global Constraints, Tasks 1.3, 4 |
  | §4.6 Educational tagging | `educational_sensitive=True` |
  | §6 batch-5 order | P7-15 |
  | §10 item 6 (isolation) | T4 step 4, T5 |
  | §10 item 7 (review) | T5 |
  | §10 item 2 (spec changes) | T7 |
  | §11.4 loader cases | T3 matrix |
  | §11.5 row 22 | P7-19 |

- **Placeholders:** none in the steps. These are run-time values, each produced by a named command:
  - `<date>`, `<YYYY-MM-DD>`;
  - `P7_BASE`;
  - the two sha hashes (Step 3.1);
  - `FOREX_FORM` and the fake's live text layout (Task 2's `summary.json`).
- **Names used across tasks:**
  - 1.1 → 1.2/1.3/3/4: `ForexAmount`, `parse_forex_amount`, `forex_base`, `CurrencySpec`, `USD_CURRENCY`.
  - 1.2 → 1.3/3: `ForexLine`, `forex_amount_text`, `create_currency`, `list_currencies`, `currency_request`,
    `create_party_ledger(currency=)`, `ledger_details`, `ledger_detail_request`, `b_day_voucher_request`,
    `delete_b_voucher`.
  - 1.3 → 2/3/4: `forex_shape.run`, `USD_PARTY`, `INR_PARTY`, `summary.json` keys `outcome`, `chosen.variant`,
    `chosen.form`, `chosen.party_currency`.
  - 3 → 4: `USD_EXPORT_PARTY`, `FOREX_FORM`, `FORMERLY_SKIPPED_TAGS`, `VoucherSpec.currency_symbol` / `fx_rate`,
    `Dataset.currencies`.
  - 4: `forex_vouchers`, `USD_CURRENCY_SYMBOL`, `judge_voucher`, `verdict`.
  - Collection names: `S0BCurrencies`, `S0BLedgerDetail`, `S0FxDay`, `S0FxCompany`, `S0P22Ledger`, `S0P22Currencies`.
- **Review Focus → tests:**
  1. → T1.3 + T4;
  2. → T1.2 + T1.3;
  3. → T3;
  4. → T4;
  5. → T4 + T3.
- **Biggest risk:** Educational TallyPrime under Wine may not store forex at all (no multi-currency, or the import
  silently drops the forex part). The plan contains it: a throwaway-only probe, a fresh backup, a UI fallback, and a
  clean "BLOCKED — confirm on tier C" exit, with nothing permanent written to B.

## Deviations (implementation of Steps 0.1–0.3 and Task 1, 2026-09-25)

Run record: `P7_BASE` = `95941a1`, BASE = **766** passed. After 1.1 (`4aed355`) **780**, after 1.2 (`d4cda98`)
**793**, after 1.3 (`47330a5`) **810**, all green normally and with `-W error`. Step 0.4 (SDD ledger, tracker row 22)
was left to the controller: this run changed only `v2/` and this file, so there are no `.superpowers/` or tracker
edits. For the same reason the pre-flight findings are recorded here and not in `preflight-scan.md`. Task 1.3 Step 6
(the Task-1 review) is not ticked: the controller runs it.

**Task 1: code blocks run in the real tree (Step 0.3 for Task 1):**
- **D1 (fake).** The 1.2 bullet "the entry's ledger has no currency and `forex_on_base_party == "refuse"`" was
  implemented literally, and it failed `test_base_party_refusal_is_evidence_not_failure`. The nominal `Export Sales`
  line never has a currency and carries the forex text on every variant, so V1 was refused too. Fixed in the fake
  (the test is the contract): the rule keys on the **voucher's party** (`PARTYLEDGERNAME`), not on each line's own
  ledger. The same applies to `"plain"`.
- **D2 (writer, minor).** `create_party_ledger`'s currency read-back also raises `WriteFailed` when
  `ledger_details` returns `None`. The plan's form would have been a `TypeError`.
- **D3 (runner, added).** When a delete did not stick, the `finally` ledger cleanup fails on live Tally, because a
  ledger that still has a voucher can't be deleted. That `WriteFailed` would have hidden the original "still there"
  error. Now a cleanup failure is added to `notes`, and the first error is the one raised. It still re-raises when
  the run itself completed. Test: `test_cleanup_failure_does_not_mask_the_first_error`.
- **D4 (runner, added).** A variant classified `dropped` (answered `created=1`, but not on 01-09-2022) now adds an
  F2 note. Before, the outcome could read `refused` with no hint. Test: `test_a_dropped_voucher_leaves_an_f2_note`.
- **D5 (test, added).** `test_fake_export_forms_and_closing_expression` (3 cases) covers the fake's
  `forex_export_form` and `forex_ledger_closing` branches. Otherwise nothing would test them before Task 4.
- **D6 (Task 2 Step 5 command).** The runner's F2 pause (`_console_wait` → `input()`) raises `EOFError` under
  `uv run … python - <<'EOF'`, because the heredoc *is* stdin (checked offline). Step 5 as written would stop right
  after the currency create. Run the snippet from a script file instead, with `PYTHONPATH=.` (a file outside the
  repo root can't otherwise import `v2`). The live-run notes in the controller's hand-off give the exact command.
- Otherwise every Task-1 code block and test ran as written. All the 1.1 grammar cases passed first time.

**Step 0.3: scratch scan of Tasks 3 and 4.** Run at `47330a5` in a throwaway worktree (since removed). It used a
minimal Task 3 (dataset 3.3 + seed 3.8 at the default candidate shape `FOREX_FORM="full"`) and Task 4's code and
tests pasted as written. The loader (3.5–3.7) was only checked statically.
- **Step 3.1 hashes** (the dataset is unchanged since `P7_BASE`): educational
  `dd7f6d44ba52a5a42637edf441213533ba1b163750364bc69392800b8558d5be`, licensed
  `546acc0609f63330c6d6c6d1bd9eddf3a6b95102c3914c913cd6e2c462b0da23`. All 7 of the Task 3.2 dataset tests passed
  against the minimal 3.3. That includes the sha with the forex-only party left out of `debtor_names`, 960/240, and
  −₹1,33,113.72. The 3.2 block also needs `date`, `Decimal`, `pytest` and `USD_DEBTOR` in scope.
- **F1 (Task 3.4: its list of files to fix is incomplete).** These also break and are **not** listed:
  - `test_company_b_data.py::test_every_sale_receipt_and_expense_payment_is_byte_identical_to_before_c41`
    (~line 449). `_digest` hashes `repr(v)`, and the new `VoucherSpec` fields change every voucher's repr. Update
    `_HEAD_DIGESTS` with a reason, or hash the pre-part-7 fields only.
  - `test_p03_b_part.py::test_flags_on_both_reads_are_confirmed`: `others` 954 → 956.
  - `test_p11_openings.py::test_the_2026_09_24_live_capture_relabels_to_different_under_c46`: the committed live
    capture has no `Gulf Office Supplies LLC (USD)`, so probe 11's missing-ledger drift check BLOCKs. Any probe that
    compares the dataset's ledgers with a **pre-part-7 live capture** will do the same.
  - `test_cli.py::test_run_unbuilt_probe_returns_2` uses probe 22 as "the unbuilt probe". Task 4's registry change
    breaks it, so pick another unbuilt probe.
- **F2 (Task 3.8 breaks Task 1 tests).** Once `seed_company_b(masters=True)` seeds `$`, these tests fail: 3 in
  `test_setup_writes_forex.py` (currency create / refused / popup) and 2 in `test_forex_shape.py` (currency refused /
  popup). They assume `$` is absent from a freshly seeded B. 3.8 must have those tests drop `$` first (e.g.
  `books.edit_state(lambda s: s["currencies"].pop("$"))`) or seed it behind a flag.
- **F3 (Task 3.8).** Seeded forex lines go through `_forex_line_text`, so that method must honour
  `forex_storage="plain"` (return `{}`). Otherwise Task 4's `test_plain_inr_without_forex_blocks_as_c36_recurrence`
  gets expression text from the seed. The Task-1 fake applies `plain` only on import (`_forex_entries`). The scan
  added it to `_forex_line_text`, and that test then passed.
- **F4 (Task 3.5 helpers).** `test_company_b.py` has `_loader(books, **io_kwargs)` and `_empty_b()` (no `tmp_path`).
  `_full_load`, `_loaded_b`, `_writer` and `_drop_tags` do not exist, so they must be written, and
  `_empty_b(tmp_path)` must be `_empty_b()`. `VOUCHER_MONTH_TEMPLATE` (3.10) is not a helper in
  `test_p05_voucher_month_bounds.py`. Take it from a probe-5 run's `store.confirmed("voucher_month")["xml_template"]`.
- **F5 (Task 4 test).** `test_needs_probe_5` fails as written. `requires=(0, 5)` makes the runner block **before**
  `run_b`, with its own wording "Run probe(s) 5 first.", so `"probe 5"` never appears. Assert
  `"probe(s) 5" in part["summary"]` (or keep `requires=(0,)` and let `run_b`'s own message fire).
- **Expected failures only:** `test_judge_on_the_live_shape_capture` and 3.9's `test_fake_books_forex.py` need Task
  2's `forex_shape_<date>/` folder. With F3 applied, the other 20 of Task 4's 22 tests passed against the candidate
  fake.
- Narration note (not a failure): with S-B, 101/102's narration reads `Export sale to Gulf Office Supplies LLC (USD)`.
  101/102 are outside the sha pin, so nothing else moves.

**Review fix round (2026-09-25, `docs/code-review-bi-s0-part7-task1-2026-09-25.md`):** I1–I5, M1, M6, R-SYM and
R-F2 are fixed test-first (`634f93b`, `d6644f2`, `4229c9a`; 810 → 846 passed, green normally and with `-W error`).
The details are in the review's "Fix round" section. One addition: **D7** — the runner refuses an `out_dir` that
already holds a `summary.json`, so a re-run can't overwrite a failed run's evidence.

## Deviations (implementation of Tasks 3 and 4, 2026-09-25)

Run record: start `271ff01` at **846** passed. After `d4be5fc` (3.9, the fake pinned to live) **853**, after `28e34fe`
(Task 3) **870**, after `da9bada` (Task 4) **888**; every commit green normally and with `-W error`. Offline only:
no Tally, no `setup-*`, no `run`. Only `v2/` and this file changed; no `.superpowers/`, tracker or spec edits (the
controller owns those).

**Applied from the pre-flight scan:** F1 (all four extra files: `_HEAD_DIGESTS` re-based at `271ff01` onto the
pre-part-7 fields with 101/102 left out; `test_p03_b_part` 954 → 956; the p11 2026-09-24 capture judged against the
ledgers B had then, via a monkeypatched `ledger_specs` without the USD party; `test_run_unbuilt_probe_returns_2` uses
the deferred probe 9), F2 (Task 1's `_books` helpers drop the seeded `$`), F3 (`_forex_line_text` returns `{}` under
`forex_storage="plain"`), F4 (`_full_load` / `_loaded_b` / `_drop_tags` / `_load` / `_imports` written;
`_empty_b()` without `tmp_path`), F5 (`test_needs_probe_5` asserts `"probe(s) 5"`).

- **D8 (loader: the currency is never created).** Task 2 showed the XML create is refused *and* leaves an
  import-exception master behind. So `_load_currencies` + `_create_or_pause` became `_require_currencies`: list, and
  if a dataset currency is missing (`currency_matches` on symbol or formal name), raise `CompanyBLoadError` before any
  write with "create `$` (Formal name USD, ISO USD) in the UI: Create → Currency". `report.created["currencies"]` is
  therefore always 0 (the `currencies` row stays in the report). Tests renamed/adapted:
  `test_load_creates_the_currency_before_the_usd_ledger` → `test_the_loader_never_creates_the_currency_and_stops_before_any_write_without_it`
  + `test_load_uses_the_ui_created_currency_for_the_usd_ledger`; `test_second_load_sends_no_currency_create` →
  `…_and_no_voucher`; `test_formerly_skipped_gap_is_a_note_not_a_problem` expects currencies created 0 / skipped 1
  (live B has `$`). Added `test_a_currency_listed_under_its_formal_name_satisfies_the_currency_check` and the CLI
  test `test_setup_b_without_the_usd_currency_names_the_ui_step_and_writes_nothing`. `_empty_b()` and the CLI
  setup-b fakes carry the UI-made `$` (`fake_books.USD_CURRENCY_ROW`, the live row). Task 6 Step 3's "`created 1` if B was restored" no longer applies: a B without `$` makes setup-b stop (exit 1) with the UI instruction.
- **D9 (dataset).** Besides `FOREX_FORM = "full"`, `FOREX_BASE_SYMBOL = ""` (V1b) — `_forex_of` needs both
  (`ForexLine.base_symbol` has no default, R-SYM). `test_the_forex_write_shape_is_the_live_one` pins both to
  `summary.json`. The USD sales' narration reads `Export sale to Gulf Office Supplies LLC (USD)`.
- **D10 (FakeBooks pinned, 3.9).** Defaults now: `forex_currency_create="refuse"` (run 1),
  `forex_rate_symbols_refused=("?",)` (V1), `forex_on_base_party="same"` (V3), `forex_export_form="full"` in the live
  layout — the base currency's NAME plus a space when its HasSpace is Yes (`_base_prefix`), whatever was sent;
  `_forex_line_text` takes `state` for that. Still candidates, labelled: `no_base` accepted, `plain`/`refuse`
  storage, `plain_plus_field`, and `forex_ledger_closing` (live never read a currency ledger's closing with a voucher
  on it). Task 1's tests pass `CANDIDATE_FOREX_KNOBS` (XML create ok, `?` rate accepted) so they keep testing the
  branches live didn't take; `test_fake_export_forms_and_closing_expression`'s layout moved to the live `? `.
  `test_fake_books_forex.py` compares the fake with the capture itself, byte for byte on the AMOUNT text (primary
  lines), instead of the plan's grammar-only comparison.
- **D11 (drift exemption, stricter).** `_flag_predated_drift` turns the gap into the note only when the missing tags
  are ⊆ `FORMERLY_SKIPPED_TAGS` **and** `pre_count + len(missing) == expected` — so an extra/duplicated voucher in the
  same FY can't hide behind it.
- **D12 (loader test fixture).** The run-4 educational group figures (`LIVE_RUN4_EDUCATIONAL`) predate 101/102; the
  two tests compare with `EDUCATIONAL_WITH_FOREX` = run 4 + ₹1,33,113.72 on Sundry Debtors and Sales Accounts
  (derived, not hand-set).
- **D13 (round trip, 3.10).** Uses `p05.svdates_template()` — the `svdates_typed` form live probe 5 confirmed —
  instead of a `VOUCHER_MONTH_TEMPLATE` helper (none exists), and also asserts the live `? ` layout survives.
- **D14 (probe 22 judges primary lines).** The plan's `judge_voucher` iterated every `ledger_lines` entry; a live
  voucher exports ALLLEDGERENTRIES and LEDGERENTRIES for the same postings, so each would count twice. It uses
  `reads.primary_lines` (as does `extra_fields`), and the `usd_ledger` rows are filtered to the party's name. Tests
  added: `test_judge_on_the_live_plain_control_is_the_c36_block` (live V0 → BLOCKED), `test_judge_keys_the_base_match_by_ledger`,
  `test_master_reads_carry_no_period_variables`; the plan's `₹` strings in the edit tests use the live `? ` layout.
- `FakeBooks` needed only `"S0P22"` in `B_PROBE_COLLECTIONS`: its Currency list and ledger `CurrencyName` routes
  already existed from Task 1.
- Task 5 step 3's CLI smoke was checked offline: `list` shows `22  forex  B  B  not run`.

## Deviations (review fix round, 2026-09-25 — `docs/code-review-bi-s0-part7-2026-09-25.md`)

- **I1 (`3b07c9e`).** `setup-b` now reads back every forex voucher of the dataset — created in this run or already
  there — in its own day (`b_day_voucher_request`, educational 01-09 / 02-09-2022, licensed 02-09 / 05-09) and checks
  each primary line's ledger, currency symbol, face, rate and INR base against the dataset (`forex_line_problems`).
  A mismatch, a missing/duplicated voucher on that day or a failed read is a `problems` line naming the
  `…pre-forex-with-usd…` backup → exit 1, no stamp. Checked for all forex vouchers (not only those just created) so a
  re-run after a bad load can't exit 0. Done in the verify stage (`_verify_forex`, after the TB check), not inside
  the create loop: same reads, and it also covers the re-run. The loader tests' fakes now follow the load's licence
  (`_empty_b(educational=…)`, the CLI fakes `educational=False`): the licensed 102 is on 05-09-2022, a day an
  educational fake (C43) doesn't honour. `test_a_forex_readback_that_times_out_is_a_problem_not_a_crash` passed on
  first run (the I7-style wrap was written with the check).
- **M1 (`5cd161a`).** Probe 22 compares each forex line's currency, face and rate with the dataset
  (`currency_matches`/`fx_matches`/`rate_matches`, `forex_mismatch`). A mismatch maps to the table's row 4 — **BLOCKED
  (drift)**, after the base check: the stored voucher isn't the one setup-b wrote, so it is company-B drift (Global
  Constraints), not a Tally finding. Never CONFIRMED.
- **M3 (`5cd161a`).** The C36 row (plain INR → BLOCKED) now looks only at the dataset voucher's own ledgers. A ledger
  the dataset voucher doesn't have is recorded (`unexpected_ledgers`) and gives **FAILED "unexpected line(s) …"** with
  its own `UNEXPECTED_IMPACT` (checked after C36, before unparsed/unbalanced): a line Tally adds to a forex voucher is
  a finding about Tally, not loader drift. A dataset ledger that is missing makes `base_matches_dataset` false
  (BLOCKED drift).
- **M5.** Task 6 Step 3's expected output rewritten above (D8's stop, the I1 note and problems, and the full
  created/skipped block).
- **M2 (recorded, no code).** Probe 22 judges `reads.primary_lines` only (ALLLEDGERENTRIES when present, D14); whether
  LEDGERENTRIES carries the same `(ledger, AMOUNT)` multiset is not observed. In the live capture
  (`variant_V1b.xml`) both lists carry identical AMOUNT text. If a later capture ever disagrees, add a recorded
  `lists_agree` observation.
- **M4 (recorded, no code).** The recorded B results of probes **3** (`others` 954→956), **11**, **14** (ledger count
  26→27), **16** (the USD party is a balance-sheet ledger; its ClosingBalance may export as an expression, Review
  Focus 4) and **25** were judged against the pre-part-7 dataset. Task 6 re-runs only 21 and 18 B (H2). The Task 6
  results doc and the tracker must name 3/11/14/16/25 B as "judged against the pre-part-7 dataset", so a later re-run
  (esp. 16 B) isn't read as a regression.

