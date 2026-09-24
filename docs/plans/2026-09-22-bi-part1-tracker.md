# BI Part 1 (Syncing) — Implementation Tracker

Living status for **Part 1 only**: [`specs/2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md).
Parts 2 and 3 are not started and are not tracked here.

**Built as v2 — current code is never changed** (spec §5 "Code isolation (v2)"). All code lives under `v2/`;
v2 copies from current code instead of importing it; the cloud side is a separate app with its own Alembic chain.
A change outside `v2/` and `docs/` is a bug in the work, not progress.

**Legend:** ⬜ not started · 🟡 in progress · ✅ done · ⛔ blocked · ⏭ deferred

**Rules for updating this file**
- Mark an item 🟡 when work on it starts, not after.
- ✅ needs **proof** in the Proof column: a test name, a log in `logs/`, a fixture path, a doc section, or a
  commit. No proof → not ✅.
- ⛔ needs the reason in the Proof column.
- A result that changes the design → update the spec too (dated "Changed" line in its header) and say so here.
- Stage-level changes (a stage starts or closes) also go to [`roadmap.md`](../roadmap.md) Set C.

---

## ▶ Resume here (updated 2026-09-24)

**Where we are:** S0 plan part 2 is **built, reviewed, fix-waved and run live**. Every company-A probe is ✅
(0, 1, 2, 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23, 25); 3, 16, 18, 23 and 25 are A-done with their **B parts
pending**. `v2/` **is committed** (343 files tracked; harness `a0d33e4`, live findings `ef69e30`, results + fixtures
+ doc sync `50d679c`). Results doc: `docs/bi-s0-probe-results-2026-09-23.md`.

**S0 plan part 3 (company-B loader) is now built and unit-tested — offline against `FakeBooks` only, NOT yet run
against live Tally.** Plan: `docs/plans/2026-09-23-bi-s0-company-b-loader.md` (9 TDD tasks). New: `v2/probes/setup/company_b_data.py`
(deterministic dataset + `expected_figures`, independent of Tally) and `v2/probes/setup/company_b.py` (idempotent
loader: list-before-create, read-back, pauses on flags that won't stick). `TallyWriter` (`v2/probes/setup/writes.py`)
gained master and voucher writers. `setup-b` is wired through the CLI (`v2/probes/__main__.py`) and the auto-operator
(`company_numbers["B"]` + `setup_company_b()`). Suite went **351 → 429 tests**, all green
(`uv run --project v2 pytest v2/tests`). Commits `6f1c882..18f98b5` (17 commits).

**Everything still pending needs company B or company C, neither of which exists yet, and none of the loader code
has touched a real Tally instance.**

**Next steps, in order:**
0d. **2026-09-24 (afternoon) — C32–C34 fixed and live-verified; run 3 stopped before any receipt; C35–C40 in a
   fix wave.** C32 `2c7860a`, C33 `7f32848`, C34 `9a6f7b4` (480 green). Live check with the fixed writer
   (`logs/live-check-vch1-fixed-2026-09-24.log`): voucher 1 `created=1`, the loader's reader finds tag 1, bill
   `Inv/1` = −9,861.74 (receivable). Before that the operator deleted the first voucher 1 (bill had landed in
   **Bills Payable** — UI screenshot, the C34 evidence). Opening bill `Op/2022-001` did NOT save via the UI
   (Receivables empty); written instead by XML ALTER on the ledger (`BILLALLOCATIONS.LIST` with BILLDATE/NAME/
   ISADVANCE/OPENINGBALANCE −62500) → read-back `Op/2022-001` −62,500, ledger unchanged (`logs/op-bill-alter-2026-09-24.log`)
   — **a working opening-bill XML shape, not yet in code**. Review `docs/code-review-bi-s0-company-b-live-fixes-2026-09-24.md`
   found **Critical: all 288 Agst Ref receipts/payments name non-existent bills** (`Inv/{own tag}`) → run 3 stopped at
   the opening-bill pause, before any receipt. **Operator decision: skip USD export sales 101/102, probe 22 blocked.**
   Live masters checks (`logs/stock-opening-live-check-2026-09-24.log`): stock OPENINGVALUE needs the sign too
   (+10,200 landed Cr; −10,200 fixed it) and compound-unit quantities must be in the first unit ("15 Box", not
   "15 Box of 10 Nos", which Tally silently drops). Both items corrected live; TB now balances exactly
   (Dr = Cr = 10,09,861.74). Fix wave in flight: C35 Agst Ref against real bills, C36 skip USD, C37 pre-validate all
   vouchers before first send, C38 discriminating +1.00 sign check, C39 stock opening sign, C40 compound qty text.
   C33 report check inconclusive (only one voucher, on day one) — redo after the load. Dataset note: purchases carry
   no inventory, so sales drive stock negative (Wireless Mouse −12 Nos after tag 1).
0c. **2026-09-24 — setup-b run 2 stopped at voucher 1; two more root causes found live (not yet fixed in code).**
   Run 2 created all 31 masters (units incl. `Box of 10 Nos`, stock items, ledgers with **signed openings confirmed in
   the UI**: Pune Digital Solutions 62,500 Dr). Operator entered opening bill `Op/2022-001` and set F2 = 31-03-2026.
   Voucher `[S0-B:1]` then failed `EXCEPTIONS=1` with no LINEERROR. Debugged live (`logs/debug-vch1-*.log`):
   - **C32 (root cause, voucher write):** in invoice mode `create_b_voucher` emits the nominal Sales/Purchase ledger
     BOTH as a `LEDGERENTRIES.LIST` line AND inside each inventory row's `ACCOUNTINGALLOCATIONS.LIST` → Tally sees the
     goods amount twice (imbalance). Production `build_create_sales_voucher` never emits the nominal line. Refuted
     first: bill-amount sign, voucher date. Removing only the nominal line → `CREATED=1`; voucher `[S0-B:1]` now
     exists in company B (Day Book: 1-Apr-22, Sales No. 1, Dr 9,861.74).
   - **C33 (root cause, every dated read):** Tally honours `SVFROMDATE`/`SVTODATE` **only with `TYPE="Date"`** (format
     irrelevant: `01-04-2022`, `20220401`, `1-Apr-2022` all work typed; all return 0 untyped). Untyped, Tally silently
     uses the company's current period (1-Apr-25..31-Mar-26) — so every v2 dated read so far read the *current
     period*, not the requested window. Company A looked right only because its data sits in that period.
     **⚠ Probes 16/17/18 measured period behaviour with untyped variables — their recorded conclusions are suspect
     and must be re-run after the fix.** Nothing in `v2/` or `backend/` emits `TYPE="Date"` (production
     `backend/tally_bridge/request_builder.py` included — flagged, out of scope for v2).
   - Open: bill sign. `Inv/1` (sent `+9861.74` under a −9,861.74 party line) reads back `ClosingBalance 9861.74`;
     production mirrors the party sign (−). The UI-entered opening bill `Op/2022-001` does not appear in the `Bill`
     collection, so there is no known-Dr bill to compare against yet.
0b. **2026-09-24 — setup-b run 1 stopped at the unit stage (before any ledger), two loader bugs fixed, run 2 in
   flight** (`logs/setup-b-live-2026-09-24-run2.log`). (1) **C30 overturns C21:** Tally reads the OPENINGBALANCE
   *sign* (negative = Dr), it does NOT infer the side from the parent group — `abs()` would have landed B's three
   debit openings as credits (company A's HDFC/SBI already did). Wire now signed (`67a67a3`); **live-verified**:
   sent `-1.00` under Sundry Debtors, read back `-1.00`, ledger deleted (`logs/sign-check-live-2026-09-24.log`,
   `v2/probes/setup/sign_check.py` `4f81b1d`). (2) **C31:** compound unit XML sent `Nos`/`Nos` → Tally
   "Next Unit already contains the First unit!" (`logs/setup-b-live-2026-09-24.log`); now simple `Box` + compound
   Box×10=Nos (`47cf175`). Docs `d2b05c1`. Suite **451 green**. Watch in run 2: `A4 Paper Ream` quantities are
   sent as "<n> Box of 10 Nos" — Tally may want "<n> Box".
0a. **2026-09-24 — all UI prep done**: voucher type `Sales - GST` confirmed via API read; current date 31-Mar-2026;
   company A shut by hand so only B is open. Five minors ✅ (440 green). **New harness bug found:** `tally.ini` has
   `Default Companies=Yes` + `Load=100003`, so `TallyControl.start("B")` (`/LOAD:100000`) opens **A and B** and
   `wait_for_companies` fails fast (guard worked, nothing written — `logs/start-tally-company-b-2026-09-24.log`).
   Any `setup-b`/probe path that has to *restart* Tally for B is blocked until `start()` sets `Load=` to the target
   company. Not fixed yet. Next: operator runs `setup-b` in their own terminal (pauses need stdin) →
   `logs/setup-b-live-2026-09-24.log`.
0. **2026-09-24 — company B shell created in the UI** (name, 1-Apr-22 books, Maharashtra, GST Yes, bill-wise Yes,
   inventory Yes). **Tally assigned it number `100000`, not `100004`** (it takes the lowest free number) — config +
   test updated in `907b9d1`, suite 435 green. Still open in the UI: voucher type `Sales - GST`, F2 = 31-03-2026.
1. ~~**Create company B in the Tally UI**~~ (shell ✅ 2026-09-24, see step 0) (spec §4.3, can't be scripted): name exactly
   `Sharma & Sons' Probe Traders` (the `&` and `'` are what probe 14 tests), books from **01-04-2022**, Maharashtra,
   GST enabled like the seed company, **F2 ≥ 31-03-2026**, and one custom voucher type **`Sales - GST`** under Sales
   created in the UI (voucher-type config via XML is unreliable — LESSONS §11 / §15 rule 4). **Its company
   number is 100000** (confirmed 2026-09-24; was wrongly assumed 100004) — `OperatorConfig.company_numbers["B"]` holds it. Since 2026-09-23 a mismatch really does
   stop the run before anything is written: `setup_company_b` now does `ensure_running()` → `_open_company("B")`
   → `check_company(..., mutating=True)` first, so a wrong number opens (or fails to open) the wrong company and
   `TallyControl` fails fast with "Tally has […] open, not […]". Before that fix `company_numbers["B"]` was never
   read by the `setup-b` path at all and the load would have gone into whichever company was already open.
2. **Run `uv run --project v2 python -m v2.probes setup-b` with a person present.** The F2, flag-settle,
   failed-create and opening-bill pauses are action-less by design and prompt for a human — this is not a
   fire-and-forget step.
3. **Batch 5 (company B) — probe 21 FIRST**: its storage numbers gate Q22/Q23, which gate S1's schema. Then
   16, 18 (B parts), 5, 3 (B), 11, 14, 15, 22, 23 (B), 25 (B).
4. **Batch 6:** create company C (`Probe Vault Co`, one ledger + one voucher) → probe 24 (security, then TallyVault).
5. **Write `docs/code-review-bi-s0-part2-<date>.md`** — still missing; plan part 2 shipped without it.
6. Then S1: the S1 spec itself is unwritten and can't be finalised until Q22/Q23 are answered.

**Open questions the live run must settle** (deliberately unresolved — someone must watch for these when `setup-b`
runs for real):
1. Whether Tally accepts the compound unit name `Box of 10 Nos` — Op 1 warns unit names cannot contain spaces
   ("BAD UNIT NAME"). A failed create becomes a pause step, by design, not a guess.
2. The statement-level Dr=Cr netting rule. `setup-b` prints the observed Trial Balance Dr/Cr total as an
   informational **note**, not a problem, because probes 16/17/18 are what settle it (S0-D7 forbids guessing a
   figure another probe must confirm).
3. Whether a plain Voucher collection returns cancelled/optional vouchers — probe 3's job. Until it is known, the
   loader never auto-recreates the four flag-tagged vouchers; it reports and pauses instead.
4. `_verify_balances` compares per-bucket **absolute** magnitudes, so it catches a wrong or missing bucket but
   proves nothing about which side a bucket nets to.
5. The balance check's fake (`FakeBooks`) replays the same line amounts the expectation is built from, so the
   green balance suite is **not** evidence that live Tally will agree.

**Live-run rules** (unchanged, someone must be at the Mac to click Tally's licence box):
```
cd "/Users/nuvanta-mac-3/work/Tally prime"
export PATH="/Applications/Wine Stable.app/Contents/Resources/wine/bin:$PATH"
uv run --project v2 python -m v2.probes reset-a      # fresh seed copy in s0probe → company A (1 click)
uv run --project v2 python -m v2.probes setup-b      # once company B exists in the UI
uv run --project v2 python -m v2.probes run --all --auto
uv run --project v2 python -m v2.probes report
```
No Tally restart between commands; click only "T: Continue In Educational Mode"; leave probe 10's deliberate modal
alone; don't pass `--stop-any-tally`; don't run commands containing "tally.exe"; if interrupted → `reset-a` before
continuing. Logs: `v2/probes/results/logs/` (gitignored by the `*.log` rule — they live on this machine only).

**Still open after the company-A run** (need a human at the keyboard, not the auto operator): UI-edit parity for
probes 1, 7, 8; probe 16's UI balance read; probe 19's UI report view; probe 13 was **file-level restore only**
(Tally's Backup/Restore screens unused) → **R8 stays open**. All of it ran Educational-mode under Wine, so probes
1, 7, 16, 18 carry "confirm on a licensed Tally", and `master_request`'s refusal of period variables on every
master collection is deliberately conservative pending that check.

**Machine state:** TallyPrime under Wine on "Bharat Traders Probe Copy" (`s0probe` folder; original `tally.ini` saved
as `tally.ini.before-s0`); dev app — Postgres :5434 (started with `pg_ctl`, stops at reboot), backend :7000,
frontend :5173. Wine 11.0 at `/Applications/Wine Stable.app` (Homebrew's Wine casks are disabled). Company A was
reset at 2026-09-23T11:06 and its anchors checked OK after the last batch; probe 10's "popup not raised" path can
leave a stock group behind — `reset-a` clears it.

**Progress ledger (every ruling, fix round, deferred minor):** `.superpowers/sdd/2026-09-22-bi-s0-probes-plan-part2/progress.md`
(part 1: `.superpowers/sdd/2026-09-22-bi-s0-probes-plan/progress.md`).


### Status of the company-B loader (updated 2026-09-23, mid-fix-wave)

**Done** — built via 9 TDD tasks, then a whole-branch review and a fix wave. Suite **351 → 434** tests, green apart from
the one test the in-flight fix is currently editing. **Nothing has run against live Tally.**

| Piece | State | Proof |
|---|---|---|
| `v2/probes/setup/company_b_data.py` — deterministic dataset + `expected_figures` | ✅ | `test_company_b_data.py`; commits `6f1c882`, `105672e` |
| `v2/probes/setup/company_b.py` — idempotent loader | ✅ | `test_company_b.py` (9 spec §11.4 cases + more); `abebf2a..4cc20df` |
| `TallyWriter` master + voucher writers | ✅ | `test_setup_writes.py`; `8d00d5f..83981f1` |
| `FakeBooks` support (groups/units/items, flag + import knobs, `ISDEEMEDPOSITIVE` enforcement) | ✅ | `test_fake_books_masters.py`; `651d705`, `027a9ca` |
| Operator wiring (`company_numbers["B"]`, `setup_company_b`, action-less pause fall-through) | ✅ | `test_auto_operator.py`; `e416cd4`, `fd603d8`, `3d1b4e6` |
| `setup-b` command (exit 0 only when `problems` is empty) | ✅ | `test_cli.py`; `b80584f`, `18f98b5` |

**Pending — code (fix wave, 10 of 15 findings landed).** Verified against the repo at `0b1a6b7`, tree clean,
**435 tests green** (435 not 436 because the dead `voucher_by_tag` test was deleted along with the method).

*Landed:* C1 `3d1b4e6` (company guard) · I2 `e4903ce` (per-builder sign arms) · I1 `22df890` (inventory flag drift)
· I4 `5f12217` (duplicate vouchers visible) · I5 `027a9ca` (fake enforces the Op 6/7/8 rule) · I3 `cf271e3`
(polarity test re-anchored to this project's own live company-A captures) · M2 + dead-code deletion + M3 `0b1a6b7`
· M5 (verified present in the tree).

*✅ All five done 2026-09-24 (440 tests green); review: `docs/code-review-bi-s0-company-b-minors-2026-09-24.md` — **changes requested, 1 Critical (opening sign), fixed `67a67a3`**:*
| ID | What | Where |
|---|---|---|
| M1 ✅ 928b638 (`check_opening_side`, raises on contra-natural or unclassifiable-group openings; `test_a_contra_natural_or_unclassifiable_opening_is_refused_before_anything_is_sent`) | `create_party_ledger` sends `abs(opening)` unconditionally — correct for company B, silently wrong for a contra-natural opening (a bank overdraft in `Bank Accounts`). Document the constraint on `LedgerSpec` or raise on violation | `writes.py`, `company_b_data.py` |
| M4 ✅ 06eb2c4 (mutation-checked) | `test_cancelled_vouchers_do_not_move_a_balance_but_are_still_counted` asserts only counts — add the balance half so it is named for what it tests | `test_company_b_data.py` |
| M6 ✅ 9f41d67 | Spec §4.3 still lists the R9 duplicate-ledger-name pause as a loader rule; the plan re-scoped it to probe 25's B part. Add a dated "Changed" note (the `Changed 2026-09-23` header line currently covers §14's GSTIN answer only) | `specs/2026-09-22-bi-s0-probes-design.md:144` |
| M7 ✅ c3761c9 | One sentence saying `Expected.ledger_month_end` / `ledger_fy_opening` exist for probes 16/18, not for the loader — they are computed but never consumed by `_verify` (correct per Ruling C16/S0-D7, but a reader will wonder) | `company_b.py` |
| M9 ✅ fae0a13 (`Created / skipped:` heading, `test_setup_b_loads_company_b_and_reports`) | The created/skipped block prints with no heading, unlike `Pauses:` / `Notes:` / `Problems:` | `__main__.py` |

M8 (the fake-side `_unit_xml` envelope differing from what `create_unit` sends) was reviewed and **deliberately skipped**.

**Two things tomorrow would otherwise rediscover** (from the fix-wave agent's hand-back):
- I5's fake rule enforces flag⇔sign *agreement*, which a mirrored fixture still satisfies — no fake can tell "Cash"
  from a party ledger. So it cannot replace M3-style role fixes; expect no help from it on the remaining minors.
- Clear `__pycache__` when mutating a module between pytest runs; a stale one made a mutation check read misleadingly.

**Only assertion changed in the whole wave:** `Current Assets < 0` was removed from both halves of the polarity test.
It came from the fixture whose own `SOURCE.md` forbids that use, and company A's live capture shows **+2,605,093.00**
because its Bank/Cash rows carry the known-corrupt seed sign. Replaced by `Sundry Debtors < 0`,
`Sundry Creditors > 0`, `Duties & Taxes < 0` — the buckets `_verify_balances` actually compares.

**Pending — operator, before anything runs live:**
1. Create company B in the Tally UI: exactly `Sharma & Sons' Probe Traders`, books from 01-04-2022, Maharashtra,
   GST enabled, F2 ≥ 31-03-2026, and the custom voucher type `Sales - GST` created **in the UI** (LESSONS §15 rule 4).
2. ✅ Company number confirmed **100000** on 2026-09-24 (not 100004 as assumed) — `OperatorConfig.company_numbers["B"]` fixed in `907b9d1`.
3. Run `uv run --project v2 python -m v2.probes setup-b` **with a person at the machine** — the F2, flag-settle,
   failed-create and opening-bill pauses are action-less by design and prompt for a human.
4. Then batch 5, **probe 21 first** (it gates Q22/Q23 and therefore S1's schema).

**What the live run should watch, in order** (from the final review):
1. **Which company is open, before anything is sent.** This is the one failure that can damage company A.
2. The first `Sales - GST` voucher's `IMPORTRESULT`. `CREATED=1, EXCEPTIONS=0` validates the invoice-mode convention
   for ~670 vouchers at once; `EXCEPTIONS=1` means stop, don't grind through 960 failures.
3. The first `Receipt` and the first `Payment` — Op 8/9 shapes that only just got pinned by a test.
4. The compound unit `Box of 10 Nos` (Op 1: unit names cannot contain spaces — "BAD UNIT NAME"). A failed create is a
   pause by design; check that `list_units` then returns the name **byte-identically**, or the second run attempts a
   duplicate CREATE and raises the blocking modal (LESSONS §15 rule 10).
5. The two USD export sales (tags 101/102), and the first sale of the `GSTAPPLICABLE=Not Applicable` item on an
   invoice carrying explicit GST lines (96 vouchers rest on that assumption).
6. Record the printed Trial Balance Dr/Cr **note** — it is the input probes 16/17/18 need to settle the netting rule.

**Known limits of the green suite — do not read 434 passing as "the books are verified":**
- `_verify_balances` compares per-bucket **absolute magnitudes**, so it catches a wrong or missing bucket but proves
  nothing about which side a bucket nets to.
- The balance check is still **circular on voucher lines**: the fake replays the same amounts the expectation is built
  from. It is genuinely non-circular on opening balances and group structure (both mutation-verified).
- Whether Tally accepts `Box of 10 Nos`, whether a plain Voucher collection returns cancelled/optional vouchers
  (probe 3), and the statement-level Dr=Cr netting rule are all **unsettled by design** — S0-D7 forbids guessing a
  figure another probe must confirm.

---

## 0. Stages

| Stage | Scope | Depends on | Spec | Plan | Status |
|---|---|---|---|---|---|
| Design | Part 1 brainstorm design | — | `specs/2026-09-21-bi-part1-sync-design.md` | — | ✅ 2026-09-21 |
| **S0** | `v2/` scaffold + live-Tally probes 0–25 + real fixtures in `v2/tests/fixtures/sync/` | — | `specs/2026-09-22-bi-s0-probes-design.md` | `plans/2026-09-22-bi-s0-probes-plan.md` (part 1 ✅), `plans/2026-09-22-bi-s0-probes-plan-part2.md` (part 2, 13 tasks), `plans/2026-09-23-bi-s0-company-b-loader.md` (part 3, 9 tasks, ✅ built) | 🟡 Plan parts 1+2 built, reviewed and **run live**: **every company-A probe is ✅ as of 2026-09-23** (0, 1, 2, 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23, 25 — 351 tests; results committed in `50d679c`). **Plan part 3 (company-B loader) built and unit-tested 2026-09-23, NOT yet run against live Tally**: 9 TDD tasks, commits `6f1c882..18f98b5` (17 commits); suite 351 → **429 tests**, all green (`uv run --project v2 pytest v2/tests`). **Remaining: everything that needs company B or C** — create company B in the Tally UI, run `setup-b` live, then probes 21, 5, 11, 14, 15, 22 and the B parts of 3, 16, 18, 23, 25; then company C + probe 24. Timing probes 9 / 20 / 21-timing ⏭ (Q29). Open: part-2 code-review doc not written; auto-mode UI-parity gaps (1/7/8, 16, 19) and file-level-only 13 → **R8 stays open** |
| **S1** | Cloud: tables, device auth, ingest API, parity engine | S0 (probes 6, 16, 17, 18, 21, 25; Q22/Q23) | — | — | ⬜ |
| **S2** | Windows agent | S0 (probe 21 for backfill); parallel with S1 | — | — | ⬜ |

---

## 1. Decisions (spec §2)

| # | Decision (short) | Built in | Status | Proof |
|---|---|---|---|---|
| 2 | Python agent reusing `tally_bridge`; PyInstaller `--onedir`, signed installer, service + tray, auto-update; Windows 10+ | S2 | ⬜ | |
| 3 | Single company picked once at setup; GUID saved on workspace | S1 + S2 | ⬜ | |
| 4 | Fetch only when active company GUID = saved GUID | S0 (probe 2) → S2 | ⬜ | S0 part done: probe 2 ✅ — cheap GUID read confirmed (filtered Company collection); build is S2 |
| 5 | Fetch only while connected; otherwise skip quietly | S2 | ⬜ | |
| 6 | Sync masters, vouchers + lines, report snapshots (current + month-end set) | S0 → S1 + S2 | ⬜ | S0 part done (company A): probe 6 ✅ (nested lines, bills, inventory; posting rule `all_only`) and probe 12 ✅ (all six report snapshots parse, bills match anchors). Build is S1+S2 |
| 7 | First sync = current FY + previous FY; new FY auto-added on 1 April | S2 | ⬜ | |
| 7b | Background backfill to `books_from`, lowest priority, never blocks chat | S0 (probe 21) → S1 + S2 | ⬜ | Gated on **probe 21** (company B, not built) — it also gates Q22/Q23 and therefore S1's schema |
| 9 | Change detection via AltVchId / AltMstId + AlterID, plus deletion check | S0 (probes 1, 3, 4, 7) → S2 | ⬜ | S0: probe 1 ✅ (counters move on every real change); probe 3 ✅ (GUID/MasterID unique, AlterID + the three flags export), 4 ✅ (`$AlterID > N` exact on Voucher/Ledger/Group/StockItem, Tally healthy after), 7 ✅ (deleted voucher vanishes, GUID never reused) — all company A, live 2026-09-23. Build is S2 |
| 11 | Parity rungs 0+1+2; rung 1 needs a per-ledger opening anchor | S0 (probes 16, 17, 18, 19) → S1 + S2 | ⬜ | S0 part done (company A): probe 16 — as-on is **impossible** on a Ledger collection (SVTODATE silently ignored, SVFROMDATE wedges Tally); 17 ✅ — `ISLEDGERWISE=Yes` gives 29 ledger rows reconciling to group totals, so rung 2 CAN run at ledger level; 18 — an as-on **TB is valid history** (R30 needs no suspension), while Bills/Stock ignore the date and must be computed from vouchers; 19 ✅ quiescence guard. Rung 1's per-ledger opening anchor therefore depends on probe 17, not 16. B parts of 16/18 pending. Build is S1+S2 |
| 12 | No full resync is ever automatic | S1 + S2 | ⬜ | |
| 14 | Ops signal for integrity alerts carries counts and causes only | S1 | ⬜ | |

---

## 2. Open questions (spec §15)

Product decisions to settle first: Q1, Q4, Q5, Q11 (Part 3, decides setup), Q25, Q28, Q30–Q32.
Q29 before S0's timing probes. Q22/Q23 need probe 21 before S1 commits to a schema.

| Q | Question (short) | Needed before | Answer | Decided on |
|---|---|---|---|---|
| Q1 | Heartbeat on skipped cycles too? | S1 spec | | |
| Q4 | Changing company or PC — how to re-bind? | S1 spec | | |
| Q5 | Synced data on disconnect / uninstall / account deletion | S1 spec | | |
| Q6 | Privacy: encryption at rest, access, keep `raw`? (DPDP Act) | S1 spec | | |
| Q10 | Is §10 out-of-scope list complete? | S1 spec | | |
| Q11 | Where the company is picked (agent or web) — Part 3 | S1/S2 specs | | |
| Q19 | Parity tolerance: flat ₹1 or percentage | S1 spec (after probe 20) | | |
| Q20 | Rung 3 in or out for v1 | S1 spec | | |
| Q21 | Parity retention 90 / 7 / 90 days | S1 spec (after probe 20) | | |
| Q22 | Keep `raw` JSONB for backfilled years? | S1 schema (after probe 21) | | |
| Q23 | Backfill floor / ceiling? | S1 schema (after probe 21) | | |
| Q25 | Re-link trigger on new GUID + same name; password or click? | S2 spec | | |
| Q28 | Who can see a synced workspace? | S3 spec (Part 3) | | |
| Q29 | Tier C machine: cloud VM or physical PC | S0 timing probes 9, 20, 21 | **None yet.** Timing probes deferred; they run before the first installer build (S2). | 2026-09-22 |
| Q30 | Several PCs, one company | S1 spec | | |
| Q31 | Admin rights at install acceptable? | S2 spec | | |
| Q32 | Split companies — link older company later? | v2 | | |

---

## 3. S0 — live-Tally probes (spec §12)

Probe scripts live in `v2/probes/`; every probe saves raw Tally responses under `v2/tests/fixtures/sync/`.
Tier B = Mac + TallyPrime under Wine; tier C = real Windows x64 (timing only).
**Run first:** 16, 17, 18, 21 (they can change the S1 schema).

| Probe | What it settles | Tier | Feeds | Status | Proof |
|---|---|---|---|---|---|
| — | `v2/` scaffold: README (isolation rules), `pyproject.toml`, copied Tally read client, import-isolation test | A | all v2 work | ✅ | Plan part 1 Tasks 1–3: `uv run --project v2 pytest v2/tests` 50 passed; task review approved (2026-09-22) |
| 0 | Environment check: Wine, edition, licence mode, seed restores | B | all | ✅ | **CONFIRMED live 2026-09-22**: Wine 11.0, TallyPrime 7.0 Edit Log, **Educational**; seed anchors ₹9,70,537 / ₹18,34,142 matched; GUID unchanged by rename. `v2/probes/results/results.json`, `v2/tests/fixtures/sync/p00_*`. Note: every Tally start stops on a licence box (gateway unreachable) until someone clicks T |
| 1 | GUID, AltVchId, AltMstId, BooksFrom, LastVoucherDate — which change on what | B | decision 9, R6 | ✅ | **Counters confirmed live 2026-09-22** (recorded DIFFERENT only because the operator's revert — an empty-value XML alter — was a silent no-op in Tally). Company collection exposes GUID, AltVchId, AltMstId, BooksFrom, LastVoucherDate, AlterID; AltVchId moved on voucher create/alter/delete (+3 on delete); AltMstId on ledger alter/create/delete; a voucher entry does **not** move the ledger's AlterID; LastVoucherDate is **not** rolled back after a delete. `p01_*` fixtures. Open: edits were XML imports, not UI (S0-D3 UI parity), Educational mode |
| 2 | Cheap read of open company GUID; response when no company open | B | decision 4, R2 | ✅ | **CONFIRMED live 2026-09-22**: filtered Company collection (`$Name = ##SVCurrentCompany`) returns the GUID in 1,674 bytes (confirmed request stored); with no company open it returns no GUID. `p02_*` fixtures |
| 3 | Voucher GUID / MasterID / AlterID / IsCancelled / IsOptional / IsPostDated / Reference fetchable | B | R6, R16 | 🟡 A ✅, B pending | **Live 2026-09-23 (A): CONFIRMED — 50 vouchers: GUID / MasterID unique, AlterID present, the three flags export everywhere, Reference = invoice number.** Company B part still to run. |
| 4 | `$AlterID > N` filter on Voucher / Ledger / Group / StockItem works and is safe | B | decision 9, R6 | ✅ | **Live 2026-09-23 (A): CONFIRMED — $AlterID > N returns exactly the expected objects for Voucher, Ledger, Group and StockItem, and Tally answers a cheap read afterwards.** |
| 5 | SVFROMDATE / SVTODATE bound a Voucher collection; safe `$Date` filter | B | extractor chunks | ⬜ | |
| 6 | Bill allocations, ISDEEMEDPOSITIVE, inventory lines; can a line export ledger GUID? | B | S1 ingest rules | ✅ | **Live 2026-09-23 (A): CONFIRMED — Nested lines, bills and inventory export; every voucher balances under the 'all_only' rule with debit negative; ledger GUID on lines via a plain fetch field.** Probe 6 is the probe that formally settles the **posting rule**, and it still measures all four candidates — but the 2026-09-23 live evidence already answers it: on company A only **`all_only`** (`ALLLEDGERENTRIES.LIST` alone) balances all 50 vouchers and reproduces Tally's own as-on TB; `default` / `all_plus_alloc` double-count the nominal ledger of all 24 inventory vouchers, `ledger_plus_alloc` loses 26 vouchers entirely. Its own live run confirms this across voucher types (a note to that effect is in `p06_nested_lines_ledger_guid.py`; no behaviour change) |
| 7 | Deleted voucher vanishes; GUID never reused | B (+ C standard edition) | R7 | ✅ | **Live 2026-09-23 (A): CONFIRMED — A deleted voucher vanishes from the collection; the next voucher gets a new GUID and MasterID; AltVchId moves on the delete [Educational mode — confirm on a licensed Tally].** |
| 8 | Ledger rename: old voucher names, AlterID, GUID stability | B | R9 | ✅ | **Live 2026-09-23 (A): CONFIRMED — Same ledger GUID; old vouchers export the new name; their AlterIDs don't move.** |
| 9 | Latency and size per chunk; can the accountant keep typing | **C only** | R3, R27 | ⏭ | No tier C machine yet (Q29); sizes measured under Wine in 21 |
| 10 | Error shapes: Tally closed, company closed, Educational, popup | B | R26, gate | ✅ | **Live 2026-09-23 (A): CONFIRMED — No company, no report and Tally-not-running each have their own shape (popup read: ok); gate table recorded.** |
| 11 | Opening balances / bills; stock opening qty / rate / value | B | R5 | ⬜ | |
| 12 | Report snapshots via SVCurrentCompany at today's date | B | R5 | ✅ | **Live 2026-09-23 (A): CONFIRMED — All six reports parse (6 TB rows with Decimal amounts, 3 stock rows); bills totals match the anchors.** |
| 13 | Backup restore: do GUID / MasterIDs change? | B (+ C standard edition) | R8 | ✅ | **Live 2026-09-23 (A): CONFIRMED — The restore keeps the company GUID and the MasterIDs; the counters fall back below the post-change values; the throwaway voucher is gone [auto: file-level backup/restore — Tally's Backup/Restore screens not exercised].** |
| 14 | Company names with `&` / quotes / apostrophes | B | R13 | ⬜ | |
| 15 | Hindi / Unicode text; compound-unit stock item | B | R14, R15 | ⬜ | |
| 16 | `LEDGER.ClosingBalance` = TB? Nominal = 0? OpeningBalance scope + as-on? ClosingBalance as-of date + post-dated | B | decision 11, R30, Part 2 | 🟡 A ✅, B pending | **Live 2026-09-23 (A): DIFFERENT — per-ledger as-on balances can't be read from the Ledger collection: SVTODATE changed 0 of 22 closing balances; 10 nominal ledger(s) have a non-zero ClosingBalance [Educational mode — confirm on a licensed Tally].** Company B part still to run. **As-on question settled live 2026-09-23** (reproduced twice on a freshly reset company A): on a **Ledger collection** `SVFROMDATE` **wedges Tally** (45 s timeout; an unrelated counters read then times out too — the XML server is blocked behind a modal until Tally is restarted) and `SVTODATE` is **silently ignored** (instant, byte-identical to the control, **0 of 35** closing balances changed → today's balances). Reports and Voucher collections with the same variables are fine, so it is master-collection-specific, not a date-format bug. Probe 16 no longer sends `SVFROMDATE` by default (opt in with `run 16 --company A --rerun --allow-risky`, which records a wedge and tells you to restart Tally) and reports the SVTODATE evidence as a **DIFFERENT**, not a BLOCKED. `master_request` now refuses both variables on any master collection. The rest of the probe (lines / TB / UI / post-dated / as-of) still needs its live run. Logs: `v2/probes/results/logs/s0-ason-discriminator*-2026-09-23.log`; rule: `LESSONS.md` §15 rule 17. **Fixed 2026-09-23 after the live run (expectations were wrong, not Tally):** (a) the 24 `unbalanced_vouchers` were an artifact of the old posting rule — inventory vouchers export the nominal ledger in both `ALLLEDGERENTRIES.LIST` and `ACCOUNTINGALLOCATIONS.LIST`, so the probes now count `all_only` (`reads.PROBE_POSTING_RULE`) and the list comes out empty; (b) `tb_vs_rollup` compared Current Assets against the **Stock Summary closing** total (−₹9,89,462.31) and reported a mismatch — it now reads the **same TB response's own `Opening Stock` row** (the TB read is `EXPLODEFLAG=Yes`, the separate Stock Summary read is gone) and Current Assets reconciles exactly (₹7,49,293 + ₹18,55,800 = ₹26,05,093), so the verdict no longer reports a TB mismatch. Expected on re-run: **DIFFERENT** on the two genuine findings only — SVTODATE ignored, and 10 nominal ledgers with a non-zero ClosingBalance |
| 17 | Exploded (ledger-level) TB via `TYPE=Data` — safe and fast? | B | decision 11, R3 | ✅ | **Live 2026-09-23 (A): CONFIRMED — 'isledgerwise' returns 29 ledger rows whose per-group sums equal the TB group totals (14 ms, 7341 bytes under Wine).** **`ISLEDGERWISE=Yes` works** (live 2026-09-23): 29 ledger rows, ~7.3 KB, ~18 ms, every primary group reconciling exactly. The live run recorded DIFFERENT only because `evaluate()` told group rows from ledger rows **by name**: `ISLEDGERWISE` emits no group rows at all, so company A's LEDGER named "Capital Account" was consumed as its group's total row and never counted — the sole "mismatch", self-inflicted. Fixed 2026-09-23: a response is treated as group-and-ledger only if some row names a group that is **not** also a ledger. Two genuine caveats kept, not massaged into passes: one non-ledger row (`Opening Stock`) rides along, and `EXPLODEFLAG`/`EXPLODEALLLEVELS` stop at the second group level (company A's 5 creditors under `National`/`Local Creditors` never appear; `SVEXPLODEFLAG`/`LEDGERWISE` aren't recognised at all). Expected on re-run: **CONFIRMED**, `working_variable = "isledgerwise"` |
| 18 | TB / Bills / Stock Summary as-on a past date return correct history | B | decision 11, R30, Parts 2+3 | 🟡 A ✅, B pending | **Live 2026-09-23 (A): DIFFERENT — TB as-on 31-10-2025 is correct history; as-on 30-09-2025: bills receivable; bills payable; stock (A4 Paper Ream 500 sheets, Box File Pack of 10, HP DeskJet Printer 2723, HP Laptop 15s, Lenovo Ideapad Slim 3, Logitech Keyboard K380, Logitech Wireless Mouse, Pen Drive 32GB, Samsung 24 inch Monitor, Samsung Galaxy Tab A8, Stapler Heavy Duty, TP-Link WiFi Router AC750, USB-C Hub 7-in-1, Whiteboard Marker Set) — bills receivable, bills payable, stock match the FULL period (31-03-2026) instead, i.e. the report ignored the date it was given [Educational mode — confirm on a licensed Tally].** Company B part still to run. **Split verdict (live 2026-09-23).** **TB: passes** — a TB as-on a past date *is* history; the live FAILED was ours, from the 2× posting rule (Sales/Purchase came out doubled) plus the missing `Opening Stock` row on Current Assets (the gap was exactly ₹18,55,800); the other three groups already matched to the paisa. So **R30 needs no suspension on this ground**. **Bills Receivable / Bills Payable / Stock Summary: a real Tally finding, recorded as DIFFERENT, not FAILED** — they ignore the as-on date and return the books' current position (bills dated after the date appear, totals equal the FY-end anchors ₹9,70,537 / ₹18,34,142, all 14 stock quantities equal opening + the FULL year's movements; the probe now proves this by also comparing against the full-period computation). Side-effect: the `ISDEEMEDPOSITIVE=Yes is inward` direction rule is validated, since it reproduces Tally's FY-end quantities exactly. `spec_impact` rewritten (its first sentence was the opposite of the truth). Expected on re-run: **DIFFERENT** — tb `CONFIRMED`, bills_stock `DIFFERENT` |
| 19 | AltVchId / AltMstId hold still across a multi-call capture | B | quiescence guard | ✅ | **Live 2026-09-23 (A): CONFIRMED — Quiet captures are stable, the report view wasn't exercised (auto mode used an XML export instead), and a mid-capture voucher is detected.** |
| 20 | Parity cost: full ledger list + TB on a large company | **C only** | R27, Q19, Q21 | ⏭ | No tier C machine yet (Q29) |
| 21 | Full-history reach: `books_from`, old-FY fetch, storage extrapolation | B (reach + size) + **C** (timing) | decision 7b, Q22, Q23 | ⬜ | Timing part ⏭ (Q29) |
| 22 | Forex vouchers expose INR base amount | B | decision 15 | ⬜ | |
| 23 | GST classification on ledgers; due date / credit period on bills | B | Part 3 tiles | 🟡 A ✅, B pending | **Live 2026-09-23 (A): CONFIRMED — TaxType identifies the 6 GST ledgers (['GST']); GSTDutyHead doesn't give the duty head.** Company B part still to run. |
| 24 | Secured companies (security / TallyVault) — export works? | B | R2, R26 | ⬜ | |
| 25 | Group nature / IsRevenue / AffectsGrossProfit; VoucherType parent + base type | B | S1 schema, R5, R16 | 🟡 A ✅, B pending | **Live 2026-09-23 (A): DIFFERENT — Nature / revenue / base-type fields don't all export; walking Parent gives 'National Creditors' → Current Liabilities (liabilities).** Company B part still to run. |

**S0 exit gate:** every tier-B probe ✅ or ⛔-with-fallback recorded (tier-C timing ⏭ until Q29 has a machine); probes 16/17/18 outcomes written into the
Part 1 spec; Q22/Q23 answerable from probe 21's numbers.

---

## 4. S1 — Cloud (spec §5 "Cloud", §6) — separate app in `v2/cloud/`

| # | Item | Status | Proof |
|---|---|---|---|
| S1.0 | `v2/cloud/` app skeleton (own port, same Postgres), own Alembic chain (`alembic_version_v2`), copied auth / JWT helpers | ⬜ | |
| S1.1 | v2 migration — bookkeeping: `sync_workspaces` (replaces `workspace.config.*`), `agent_devices`, `sync_runs` (+ `kind`), `sync_batches` | ⬜ | |
| S1.2 | v2 migration — masters: groups (+ `nature`), voucher types (+ `base_type`), ledgers (+ GST fields), stock items, stock groups, units | ⬜ | |
| S1.3 | v2 migration — vouchers, ledger lines, inventory lines, bill allocations; `Numeric(18,2)` everywhere | ⬜ | |
| S1.4 | v2 migration — `tally_report_snapshots`, `sync_fy_coverage`, `parity_runs`, `parity_lines` | ⬜ | |
| S1.5 | Device auth: `/api/agent/auth/login`, `/refresh`, rotating revocable token, `GET/DELETE /api/devices`, `get_current_device` | ⬜ | |
| S1.6 | One active device per workspace + take-over | ⬜ | |
| S1.7 | `POST /api/sync/company` (bind workspace, config) | ⬜ | |
| S1.8 | `POST/PATCH /api/sync/{ws}/runs` with `kind` | ⬜ | |
| S1.9 | `POST /batches`: upsert `alter_id >=`, lines replaced, company-GUID check, `last_synced_at` rules by `kind` | ⬜ | |
| S1.10 | Ingest rules: masters before vouchers, name → GUID resolution, `missing_master`, `balance_captured_at` | ⬜ | |
| S1.11 | Rung 0: double-entry invariant rejects the batch | ⬜ | |
| S1.12 | Ingest limits: 413 oversize, per-device 429 | ⬜ | |
| S1.13 | `PATCH /coverage`: idempotent, two watermark edges, `config.backfill` copy | ⬜ | |
| S1.14 | `POST /reconcile`: soft-delete, return ledgers to re-read | ⬜ | |
| S1.15 | `POST /snapshots`: upsert on `(workspace_id, report_type, as_on_date)` | ⬜ | |
| S1.16 | `POST /heartbeat`: `last_seen_at` only | ⬜ | |
| S1.17 | Cursors on the server (`config.cursors`) | ⬜ | |
| S1.18 | Stored `sync_state` values incl. `restore_detected`; re-link prompt flag | ⬜ | |
| S1.19 | `GET /api/workspaces/{id}/sync-status` | ⬜ | |
| S1.20 | Parity rung 1 + opening anchor (watermark-bounded) | ⬜ | |
| S1.21 | Parity rung 2 + "TB itself balances" check | ⬜ | |
| S1.22 | Cause classifier + escalation ladder + tolerance setting | ⬜ | |
| S1.23 | `POST /parity` (sync, quiescence abort), `last_parity`, retention | ⬜ | |
| S1.24 | Internal ops signal — counts and causes only (decision 14) | ⬜ | |
| S1.25 | DB integration tests (spec §8, §14 "DB integration") | ⬜ | |
| S1.26 | Code review → `docs/code-review-bi-s1-*.md` | ⬜ | |

---

## 5. S2 — Windows agent (spec §5 "Windows agent", §4) — in `v2/agent/`

| # | Item | Status | Proof |
|---|---|---|---|
| S2.1 | v2 copies of the Tally read code in `v2/agent/tally/`, **without** the §13 gaps (escaping R13, company params, float money, `parse_amount` zero) — current builders untouched. S0 makes the first copies (S0 spec §3.1); S2 completes them | 🟡 | First copies done in S0: client, envelopes, xml_utils, exceptions, amounts, reports (`v2/tests/agent/`) |
| S2.2 | `v2/agent/tally/` sync builders (explicit fields, escaping) + parsers (Decimal, missing ≠ zero) | ⬜ | |
| S2.3 | Platform adapters + foreground CLI for Mac dev | ⬜ | |
| S2.4 | `gate.py`: one request at a time, timeouts, backoff, circuit breaker, health + GUID check | ⬜ | |
| S2.5 | `extractor.py`: month chunks ≤ ~5k vouchers, auto-split | ⬜ | |
| S2.6 | `change_detector.py` | ⬜ | |
| S2.7 | `state.py` (SQLite): cursor cache, chunk status, outbox, log | ⬜ | |
| S2.8 | `uploader.py` + outbox (500 objects / 5 MB, `batch_id`, delete on ack) | ⬜ | |
| S2.9 | `auth.py` (keyring / DPAPI; 401 → "Signed out") | ⬜ | |
| S2.10 | `scheduler.py`: tiers 1–7 + cycle budget | ⬜ | |
| S2.11 | First sync: 24 units, resume, snapshots, anchor TB | ⬜ | |
| S2.12 | Incremental cycle + mirrored balance re-read | ⬜ | |
| S2.13 | Deletion compare: daily 2-FY, round-robin older, masters | ⬜ | |
| S2.14 | Month-end snapshots + FY-close capture | ⬜ | |
| S2.15 | New FY rollover | ⬜ | |
| S2.16 | Backfill walker + pre-emption | ⬜ | |
| S2.17 | Company identity changes: skip, re-link prompt, `restore_detected` | ⬜ | |
| S2.18 | Parity capture + quiescence counters + remediation execution | ⬜ | |
| S2.19 | `diagnostics.py` + "Send diagnostics" (no business data) | ⬜ | |
| S2.20 | v2 copy of mock Tally (`v2/tests/mocks/`) + stateful sync mode + latency / hang / error injection | ⬜ | |
| S2.21 | Round-trip E2E (agent in-process vs v2 mock Tally + v2 cloud app) | ⬜ | |
| S2.22 | `service.py` + `tray.py` ("Sync now", sign-out) — tier C | ⬜ | |
| S2.23 | Installer, uninstall revokes device, proxy support — tier C | ⬜ | |
| S2.24 | `updater.py`: signed download, sha256, `--selftest`, rollback — tier C | ⬜ | |
| S2.25 | Windows CI (`windows-latest`): tests, build, selftest, service install | ⬜ | |
| S2.26 | Manual checks (spec §14 "Manual") | ⬜ | |
| S2.27 | Code review → `docs/code-review-bi-s2-*.md` | ⬜ | |

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-09-22 | Tracker created. Design ✅; S0 spec started. |
| 2026-09-22 | Code isolation decided: Part 1 is built as v2 under `v2/` (copy don't import; separate cloud app, same DB, own Alembic chain). Spec §5 "Code isolation (v2)" added; tracker items re-pathed. |
| 2026-09-22 | S0 spec written (`specs/2026-09-22-bi-s0-probes-design.md`): 3 probe companies (A seed copy, B multi-year + edge cases, C secured), hybrid data (setup script + UI steps), one runner + probe modules. Q29 answered: timing probes ⏭. |
| 2026-09-22 | S0 plan part 1 written (`plans/2026-09-22-bi-s0-probes-plan.md`: foundation + probes 0, 2, 1); implementation started. Found: `*_live.xml` fixtures are the NUVANTA company, not the seed — specs corrected; current `parse_company_list` counts CMPINFO's `<COMPANY>0</COMPANY>` as a company (v2 copy fixed; current code untouched). |
| 2026-09-22 | S0 plan part 1 **built and reviewed**: 146 tests (also `-W error`); task reviews + final review (7 Important fixed) → `docs/code-review-bi-s0-part1-2026-09-22.md`. Probes 0, 1, 2 ready for the live run; nothing run against Tally yet. No commits. |
| 2026-09-22 | **Probes 0, 2, 1 run live** (automated operator: company copy + Tally restarts + XML edits; you clicked the licence box). 0 ✅, 2 ✅, 1 ✅ (see row). Results: `docs/bi-s0-probe-results-2026-09-22.md`. Left in company A: ledger Electricity has EMAIL `s0probe@example.com` (empty-value XML alter can't clear it; no effect on figures). Tally config points at `s0probe` (original saved as `tally.ini.before-s0`). |
| 2026-09-22 | Decided: S0 runs **automated** (operator becomes part of `v2/probes/`; Tally edits via XML, open/close/restore via Tally restarts; the person only clicks Tally's licence box). Plan part 2 started. |
| 2026-09-22 | Plan part 2 written (13 tasks; every code block verified on a scratch copy: 284 tests). Rulings: probe 10 order, probe 13 auto-limit note, probe 16 extra throwaway voucher, probe 4 "all changed after N", probe 7 MasterID reuse = DIFFERENT. Provisional finding: company A's TB rows net to ₹33,05,800 (not 0) — Part 1 §6 flagged. Build started. |
| 2026-09-22 | Plan part 2 Tasks 1–12 built and reviewed in 5 batches (297 tests, also `-W error`): harness actions, write helpers, automated operator + `run --auto`/`reset-a` (2 safety fix rounds), probe 1 revision, probes 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23, 25 (company-A parts). Final whole-part review running; then the automated live run. |
| 2026-09-22 | Final review of part 2: "ready with fixes" (3 Important: FAILED parts blocked ordered runs, Ctrl-C swallowed, p16 post-dated read-back). One fix wave applied (I1–I3, M1–M12): **316 tests**. Spec §5.3: ordered runs also skip FAILED unless `--rerun`. Stopped for the day — see "Resume here". |
| 2026-09-23 | **Scoped re-review of the fix wave** (`final-fixes.md` vs the code; each item verified by reverting it and re-running its test). Verdict "ready with fixes": all 15 applied, 13 pinned by tests; 2 Important — (a) probe 16's M6 guard would record `inconclusive` on **every** run because probe 1's throwaway pushes `LastVoucherDate` to 20260331 and it never rolls back, (b) the M11 test didn't pin its fix (deleting the `raise` left all 21 green); 4 Minor — M5 unpinned, p06 discarded evidence on transport errors, p19's DIFFERENT path still claimed a UI report view in auto mode, p10 misattributed a non-popup timeout. |
| 2026-09-23 | **Those 6 fixes applied: 326 tests** (also `-W error`), each proven by revert. Probe 16 now takes its books-reach baseline from a new probe-1 observation recorded *before* probe 1's throwaway (`p01` `LAST_VOUCHER_DATE_BASELINE`), so **it settles the F2-vs-FY-end question in the planned order — no `reset-a` + `--rerun 16` needed**, provided probe 1 is re-run in the same live session (the documented `run 1 --auto` step does this). The "not included" branch is now decided with no guard at all; a genuinely inconclusive result carries a rerun recipe. An absent `LastVoucherDate` records "not available" instead of reading as a safe date. Known, not fixed: on p10's "popup not raised" path a stock group is created on company A with no `ctx.on_abort` cleanup note (an abort there leaves it behind; `reset-a` clears it). |
| 2026-09-23 | **Live finding: period variables on a master collection are unsafe** — `SVFROMDATE` on a Ledger collection freezes Tally's XML server behind a modal until Tally is restarted; `SVTODATE` is silently ignored and returns today's balances with a healthy 200 (the more dangerous of the two, since a byte-count or "200 OK" check confirms the wrong answer). This is what blocked probe 16 in the live run and stopped the ordered run. Fixed in the harness: probe 16 runs the safe SVTODATE-only comparison **by value per ledger** every time, the SVFROMDATE attempt is opt-in (`run … --allow-risky`) and records a wedge instead of dying, and `v2/probes/reads.py` `master_request` refuses both variables on any master collection (probe 16's gated path passes `allow_period_vars=True`). Probe 16 now returns a real verdict (DIFFERENT, naming decision 11) instead of BLOCKED. **339 tests** (also `-W error`), each fix proven by revert. Consequence: rung 1's per-ledger opening anchor during the backfill depends on **probe 17** — the Ledger-collection route is impossible, not merely unattractive; probes 17 and 18 (report route) are unaffected. *Scope caveat:* Ledger collection only, TallyPrime 7.0 Educational under Wine — the guard is deliberately conservative (all master collections); a licensed Tally on real Windows is an open tier-C check. Docs: `LESSONS.md` §15 rule 17, spec header "Changed 2026-09-23". |
| 2026-09-23 | **Live run diagnosed: three probe expectations were wrong, not Tally — and all three reverse in our favour.** (1) *Posting rule:* inventory vouchers export the nominal ledger in BOTH `ALLLEDGERENTRIES.LIST` and `ACCOUNTINGALLOCATIONS.LIST`, so the old "default" rule double-counted Sales/Purchase by exactly 2× and made 24 of 50 vouchers look unbalanced; the probes now count `all_only` (`reads.PROBE_POSTING_RULE`), which leaves 0 unbalanced and matches Tally's as-on TB to the paisa. (2) *Opening Stock:* the TB's stock-bearing group carries a synthetic `Opening Stock` row (₹18,55,800) that no ledger holds and that is **not** the Stock Summary closing total (−₹9,89,462.31); probes 16 and 18 now read it from the **same** (`EXPLODEFLAG=Yes`) TB response, and Current Assets reconciles exactly. (3) *Ledger-level TB:* `ISLEDGERWISE=Yes` works — probe 17's only mismatch came from telling group rows from ledger rows **by name**, which swallowed company A's ledger "Capital Account"; so **decision 11's rung-1 per-ledger anchor is available** and **R30 needs no suspension** (probe 18's TB half passes). What is genuinely different: Bills Receivable/Payable and Stock Summary **ignore** the as-on date (probe 18 now reports that as DIFFERENT with evidence, not FAILED), and `EXPLODEFLAG`/`EXPLODEALLLEVELS` stop at the second group level. **351 tests** (also `-W error`), every fix proven by revert; no probe was run against Tally from here (live re-run is the operator's next step). Docs: spec header "Changed 2026-09-23 (probes 16–18 re-read)", `LESSONS.md` §15 rules 18–20. Also recorded and **deliberately NOT fixed** (out of scope, `backend/` untouched): company A's TB netting to ₹33,05,800 is explained by `backend/tally_bridge/import_builder.py:680` `abs(float(opening_balance))` discarding the debit sign on the two bank openings — a seed-data/write-path defect whose fix needs a re-seed and a new committed backup, so company A is not a clean fixture for a balanced opening position. |
| 2026-09-23 | **Company-A probe batch run live** (auto operator): 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23, 25 — all CONFIRMED on A except the three genuine DIFFERENTs (16 as-on, 18 bills/stock ignore the date, 25 nature/base-type don't export). Company A anchors checked OK before every batch and after. Results: `docs/bi-s0-probe-results-2026-09-23.md`; fixtures `v2/tests/fixtures/sync/p0*`, `p1*`, `p2*`. **Probe 25's consequence is a schema change**: S1 must DERIVE group `nature` (walk `Parent` → reserved primary group) and voucher-type `base_type` (walk the voucher-type `Parent` chain) instead of reading them — written into the Part 1 spec §"Minimum columns" and the Data contract. **Next: the company-B loader** — probes 21, 22, 5, 11, 14, 15 and the B parts of 3, 16, 18, 23, 25 are all blocked on it, and probe 21 gates Q22/Q23 before S1 can commit to a schema. |
| 2026-09-23 | **S0 plan part 3 (company-B loader) written**: `docs/plans/2026-09-23-bi-s0-company-b-loader.md` — 9 tasks, TDD, offline against `FakeBooks`. Covers `company_b_data.py` (deterministic dataset + independently-computed expected figures), `company_b.py` (idempotent loader), new `TallyWriter` master/voucher writers, `FakeBooks` branches for GROUP/UNIT/STOCKITEM, operator `company_numbers["B"]` + `setup_company_b()`, and the `setup-b` command. Spec §14's open GSTIN question answered in the plan (company-level GST stays UI-only; party ledgers carry a check-digit-correct `PARTYGSTIN`). Not in scope: creating company B in the UI, the B probes, company C, the live run. Not yet implemented. |
| 2026-09-23 | **S0 plan part 3 (company-B loader) built via 9 TDD tasks, commits `6f1c882..18f98b5` (17 commits)**: `v2/probes/setup/company_b_data.py` (deterministic dataset + `expected_figures`, independent of Tally) and `v2/probes/setup/company_b.py` (idempotent loader: list-before-create, read-back, pauses on flags that won't stick) are new; `TallyWriter` (`v2/probes/setup/writes.py`) gained master and voucher writers; `setup-b` is wired through the CLI and the auto-operator (`company_numbers["B"]` + `setup_company_b()`). Suite went **351 → 429 tests**, all green (`uv run --project v2 pytest v2/tests`). Built and unit-tested only, **entirely offline against `FakeBooks`** — not run against live Tally. Spec §14's GSTIN question formally answered in the spec (dated "Changed 2026-09-23" line). Next: create company B in the Tally UI, confirm company number 100004, run `setup-b` live with a person present, then batch 5 (probe 21 first). |
| 2026-09-23 | **Company-B loader code review + fix wave (in progress).** Whole-branch review of `6bcb6f4..4e56ca8` (24 mutations run): **ready with fixes** — 11 of 12 behaviour-removing mutations were killed by the test named for that behaviour. Found **1 Critical**: `setup_company_b` wrote ~1,000 objects without checking which company Tally had OPEN (`check_writable` inspects the string literal `COMPANIES["B"]`, not the loaded company; company A's name also contains "Probe", and the realistic sequence is "run the A probes, then load B") — fixed in `3d1b4e6`, which now calls `ensure_running` + `_open_company` + `check_company` first. Also found the **5th and 6th false-passing tests** of this plan: the Op 6/7 convention test excluded the USD export sale and had no Op 8/9 arm, leaving `_build_usd_sale`/`_build_receipt`/`_build_payment` (**290 of 960 vouchers**) replaceable by the `EXCEPTIONS=1` permutation with the suite green (fixed `e4903ce`, mutation-verified by the controller); and the purchase-subtype inventory test asserted only tag presence while emitting the rejected permutation (fixed `22df890`). Landed so far: C1 `3d1b4e6`, I2 `e4903ce`, I1 `22df890`, I4 `5f12217` (duplicate vouchers were invisible to every count — everything keyed by tag), I5 `027a9ca` (the fake now stores `ISDEEMEDPOSITIVE` and enforces the Op 6/7/8 rule instead of echoing). **Still open in the wave:** I3 (polarity test is anchored to a fixture whose own SOURCE.md forbids that use, and asserts a sign the project's live captures contradict), M2 (line-ordering bare `assert` crashes mid-load instead of pausing — the only surviving behavioural mutation), delete dead `voucher_by_tag`, and minors M3/M4/M5/M1/M6/M7/M9. |
| 2026-09-23 | **Session end — fix wave 10/15, tree clean and green at `0b1a6b7` (435 tests).** Landed since the previous row: I3 `cf271e3` (the polarity test was anchored to a fixture whose own SOURCE.md says "parser tests only, never seed-parity anchors", and asserted a sign this project's live captures contradict — now re-anchored to `p16_A_tb_fy_end.xml`/`p17_A_tb_exploded_explodealllevels.xml` and asserting the second-level buckets `_verify_balances` actually compares); M2 + dead-code deletion + M3 `0b1a6b7` (the party-first line-ordering bare `assert` now raises `CompanyBLoadError` so a violation pauses instead of crashing mid-load — it was the only surviving behavioural mutation in the suite; dead `TallyWriter.voucher_by_tag` deleted with its test; two receipt fixtures flipped off the mirror of Op 8). **Five minors not started: M1, M4, M6, M7, M9** — see "Resume here". Stopped deliberately at a committed green tree rather than mid-edit. |
| 2026-09-24 | **Company B shell created in the Tally UI** by the operator: `Sharma & Sons' Probe Traders`, FY/books from 1-Apr-22, Maharashtra, GST Yes (no company GST details), bill-wise Yes, inventory integrated. **Contradicted expectation:** Tally assigned company number **`100000`** (folder `s0probe/100000`), not `100004` — it picks the lowest free number, not "next after A". `company_numbers["B"]` + `test_auto_operator.py` updated, `907b9d1`, 435 green. Remaining UI steps: voucher type `Sales - GST`, F2 = 31-03-2026; then `setup-b` live. |
| 2026-09-24 | **Five minors done** (M1 `928b638`, M4 `06eb2c4`, M6 `9f41d67`, M7 `c3761c9`, M9 `fae0a13`), suite **440 green**. M1 went one step past the brief: it also refuses openings under custom groups whose nature it can't classify (company B has none). UI prep finished (voucher type `Sales - GST` read back via API, current date 31-Mar-2026). **Contradicted expectation:** starting Tally with `/LOAD:100000` also preloads company A because `tally.ini` has `Default Companies=Yes`/`Load=100003` — the harness guard refused (no writes); operator shut A by hand. Harness fix pending. |
| 2026-09-24 | **setup-b live run 1 → stopped deliberately; C30 + C31.** Run 1 created 2 custom groups + `Nos`, then paused on `Box of 10 Nos` (our XML sent `Nos` as both units). Meanwhile review of the minors (`docs/code-review-bi-s0-company-b-minors-2026-09-24.md`) found a **Critical**: the `abs(opening)` wire (Ruling C21/F11, reaffirmed by M1) contradicts company A's live evidence (HDFC/SBI debits stored as credits). Run killed at the unit pause — **no ledger had been written** (read-back: only `Cash`, `Profit & Loss A/c`). Fixed: signed wire `67a67a3` (live-verified −1.00 → −1.00), compound unit `47cf175`, docs `d2b05c1`, sign check `4f81b1d`. 451 green. Run 2 started. |
| 2026-09-24 | **setup-b run 2: masters ✅, vouchers blocked — C32 + C33 found live.** All 31 masters created cleanly; signed openings confirmed in the UI. Voucher 1 `EXCEPTIONS=1`: root cause C32 = nominal ledger emitted twice in invoice mode (fixed by hand for voucher 1 only, `CREATED=1`). Then the loader's own read-back saw 0 vouchers: root cause C33 = period variables need `TYPE="Date"`, otherwise Tally silently uses the current period — **probes 16/17/18 conclusions suspect**. Run stopped cleanly; code fixes next. Logs: `logs/setup-b-live-2026-09-24-run2.log`, `logs/debug-vch1-*.log`. |
| 2026-09-24 | **C32–C34 live-verified; run 3 stopped; C35–C40 found.** Voucher 1 rewritten correctly (receivable bill). Opening bill written by XML ALTER after the UI entry failed to save. Review found every Agst Ref names a non-existent bill (Critical) — run stopped before any receipt. USD sales skipped by operator decision (probe 22 blocked). Stock opening sign + compound qty text found and fixed live on the two affected items; TB balances. Fix wave C35–C40 dispatched. |
