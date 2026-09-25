# Code review — BI S0 plan part 7, Tasks 3–4 (pre-live), 2026-09-25

**Scope:** `e3dd9c8..164af9a` on `feat/bi-s0-probe-harness` — `d4be5fc` (3.9 fake pinned to live), `28e34fe` (Task 3
loader, lifts C36), `da9bada` (Task 4 probe 22), `164af9a` (plan doc). Reviewed against
`docs/plans/2026-09-25-bi-s0-probes-plan-part7.md` (Tasks 3/4/5, Global Constraints, Review Focus, "Task 2 result",
D8–D14) and `LESSONS.md` §15, with the live evidence `v2/tests/fixtures/sync/forex_shape_2026-09-25_run2/`.
**Mode:** offline only (no Tally, no localhost:9000). Real defects only, not style.
**Suite:** `uv run --project v2 pytest v2/tests -q` → **888 passed** (189 s) at `164af9a`.

## Verdict

**Safe to run live: yes after fixes.** Both fixes are small. Nothing found can make `setup-b` write anything other
than the USD ledger and vouchers 101/102 on the current company B, or alter `Gulf Office Supplies LLC`, and no path sends
a Currency create. The one Important gap: `setup-b` cannot tell a forex store from a plain-INR store (C36) and still
re-stamps `company_b_loaded_at`. Probe 22 would catch it one step later, so this is not a blocker. It is cheap to close,
though, and it changes how you recover. Close it in code (I1), or at least make Task 6 Step 4 a pass/fail check before
the backup in Step 5.

## Critical

None.

## Important

### I1 — `setup-b` has no forex read-back, so a plain-INR store (C36) or a slightly wrong base passes it clean

- **Where:** `v2/probes/setup/company_b.py:468-478` (`_load_vouchers` create call), `v2/probes/setup/writes.py:476-479`
  (`create_b_voucher` checks only `created==1`, `clean` and `last_vch_id`), `company_b.py:584-620`
  (`_verify_balances`: group magnitudes, tolerance ₹1.00).
- **Failure scenario:** Tally answers `created=1` for 101/102 but keeps a plain `-37216.04` (the C36 failure, Review
  Focus 1). Or it keeps the forex text with a base a few paise off (Review Focus 5). In both cases the per-FY count is
  240 and every group magnitude matches within ₹1.00, because a plain-INR store has exactly the same INR postings. So
  `setup-b` prints no problems and exits 0, **re-stamps `company_b_loaded_at`**, and the operator then takes the
  "loaded-forex" backup in Task 6 Step 5 of a wrong company. Probe 22 does BLOCK afterwards (`p22_forex.py:81-84`,
  `:91-94`). But `setup-b` is keyed by tag, so it can never repair 101/102: the only way back is restoring
  `100000-pre-forex-with-usd-2026-09-25`, and a bad backup has already been taken by then. This also falls short of
  the Global Constraint "Read back every write (rules 2, 3): `created=1` is not proof". The only read-back for these
  two writes is Task 6 Step 4, which prints and asserts nothing.
- **Fix (preferred, test-first):** after each forex create in `_load_vouchers`, read that voucher's own day with
  `writer.post(b_day_voucher_request(company, v.date.strftime("%d-%m-%Y")))` (C43-safe: 01-09 / 02-09). Find the tag,
  and for every `reads.primary_lines` line require all of the following:
  - `parse_forex_amount(...)` is not None;
  - `.currency == v.currency_symbol`;
  - `|.fx| == v.fx_amount` and `.rate == v.fx_rate`;
  - `forex_base(...)[0] == the line's INR amount`.

  Anything else appends a `problems` line ("[S0-B:101] stored as plain INR / base … ≠ … — restore
  `…pre-forex-with-usd…`"), so `setup-b` exits 1 and does not stamp. Tests: the fake with `forex_storage="plain"`, and an
  edited `amount_text` with a different base. **Minimum procedural fix:** make Task 6 Step 4 assert those same
  conditions (exit non-zero), and make it a gate before Step 5's backup.

## Minor

### M1 — Probe 22 judges the base only, not face value, rate or currency

- **Where:** `v2/probes/p22_forex.py:58-76` (`judge_voucher`).
- **Scenario:** Tally keeps `$448.44 @ ? 83.00/$ = ? 37216.04` (an inconsistent rate), or the right base in another
  currency's symbol. Probe 22 reports CONFIRMED. This is unlikely given V1b, but the plan's `forex_mismatch` class
  exists for exactly this case.
- **Fix:** record `fx_matches` / `rate_matches` / `currency_matches` per line against `spec`. Treat a mismatch like
  row 4 (BLOCKED drift), or at least put it in `summary`.

### M2 — Only one of the two exported line lists is judged

- **Where:** `p22_forex.py:67` (`primary_lines`, which prefers ALLLEDGERENTRIES), per D14.
- **Scenario:** a live voucher exports both ALLLEDGERENTRIES and LEDGERENTRIES. If the two ever disagree (for example,
  LEDGERENTRIES keeps a plain INR amount), the probe never sees it. D14's de-duplication is right. Nothing double-counts,
  and an empty or one-sided list can't CONFIRM, because `known` needs ≥1 line and Σ must be 0.
- **Fix:** observe `lists_agree`: the `(ledger, amount_raw)` multiset of LEDGERENTRIES equals that of ALLLEDGERENTRIES
  when both are present. Recorded, not judged.

### M3 — An extra line Tally adds would be reported with the wrong cause

- **Where:** `p22_forex.py:81-84`.
- **Scenario:** Tally adds a third, plain-amount line to a forex voucher (a rounding or exchange line). That line
  routes `plain_no_forex`, and the BLOCKED text says "written as plain INR (the C36 failure)". The real finding would
  then be misdiagnosed as loader drift.
- **Fix:** before the verdict, compare the primary lines' ledger set with `spec.lines`. Report "unexpected line(s) …"
  separately from the C36 text.

### M4 — The blast-radius list leaves out stale B results

- **Where:** plan Task 6 Step 7 re-runs only 21 and 18 B.
- **What goes stale:** the recorded B results of 3 (`others` 954→956), 11, 14 (ledger count 26→27), 16 (the USD party
  is a balance-sheet ledger; its Ledger `ClosingBalance` may export as an expression, Review Focus 4, and would then
  show up as a closing mismatch on a re-run) and 25 all predate the dataset change.
- **Fix:** no need to re-run them now, but the Task 6 results doc and the tracker should name them as "judged against
  the pre-part-7 dataset". Otherwise a later re-run of 16 B will look like a regression.

### M5 — The plan's Task 6 Step 3 text still gives the pre-D8 expectation

- **Where:** plan Task 6 Step 3.
- **Scenario:** it still says "`created 1` if B was restored". Under D8, a B without `$` makes `setup-b` stop with exit
  1 and the UI instruction, and nothing is written. D8 records this, but the step itself wasn't edited, so an operator
  reading only Step 3 could misread the stop as a failure.
- **Fix:** edit the step.

## Focus questions — answers

1. **Can `setup-b` write or alter anything other than 1 ledger + 2 vouchers on live B (958 vouchers)?** No.
   - **Currency:** `_require_currencies` only lists (`company_b.py:148-164`) and raises before any write if `$` is
     missing.
   - **Masters are list-before-create.** An existing ledger is never sent (`_load_masters` skips it; `create_party_ledger`
     re-checks with `ledger()`). The INR `Gulf Office Supplies LLC` has `currency=None`, so nothing about it is even
     read (`company_b_data.py`, pinned by `test_usd_export_party_and_currency`). Its 87 vouchers are untouched.
   - **Vouchers** are created only for tags not in the pre-run read (`company_b.py:449-451`). The sha pin
     (`test_every_other_voucher_is_byte_identical_to_p7_base`, hashes = the P7_BASE values in the plan) covers every
     non-101/102 voucher's tag, kind, type, date, party, narration, lines, inventory, bills, flags and currency in both
     licences. Excluding the USD party from the rotation keeps it green.
   - **D11** (`company_b.py:357-363`) turns the gap into a note only when the missing tags ⊆ {101, 102} **and**
     `pre_count + len(missing) == expected`. So a duplicate or extra voucher in FY 2022-23, or a third missing tag,
     still gives the problem line (tests `test_any_other_gap_in_that_fy_is_still_a_problem` and the D11 cases).
   - **Numbering:** checked against the live evidence, no renumbering. In `variant_V0/V1b/V3.xml` the throwaways took
     Sales numbers 73/74/75, i.e. max + 1 (FY 2022-23 ends at 72 in `numbers_before.xml`), and the deleted numbers
     were not reused. So inserting a voucher dated 01-09-2022 does not renumber the later Sales vouchers. 101/102 will
     just take the next numbers.
2. **Is a Currency create sent anywhere?** Not by `setup-b` or any probe. The only caller of `create_currency` is the
   one-shot `forex_shape.run` (`forex_shape.py:286`). It isn't wired into the CLI and isn't part of the next live step.
   The fake's default is now `forex_currency_create="refuse"`, so an accidental create would fail loudly in tests too.
3. **Is the forex write the exact V1b form?** Yes.
   - `_forex_of` passes `FOREX_FORM="full"` and `FOREX_BASE_SYMBOL=""`, and `forex_amount_text` renders
     `-$448.44 @ 82.99/$ = -37216.04`. That is the same `create_b_voucher` path, vch_type `Sales`, date format, and
     LEDGERENTRIES/Invoice-view header that the shape runner used for V1b, with the same party-ledger shape
     (`create_party_ledger(..., bill_wise=False, currency="$")`, CURRENCYNAME read back as `$`, as in
     `ledgers_after_create.xml`). `test_the_forex_write_shape_is_the_live_one` pins this to `summary.json`.
   - **Read-back:** `create_party_ledger` verifies CURRENCYNAME. **Nothing verifies the voucher's forex storage or
     base** (I1). Probe 22 does (plain → BLOCKED, base ≠ dataset → BLOCKED), and so does the live V0 capture test
     `test_judge_on_the_live_plain_control_is_the_c36_block`.
4. **Probe 22 verdict logic.**
   - The order matches the plan's table: plain → BLOCKED, unparsed → FAILED, unbalanced → FAILED, base ≠ dataset →
     BLOCKED, stated/field → CONFIRMED, computed → DIFFERENT. Missing tags, untagged or drift, and no probe 5 are all
     BLOCKED.
   - Primary lines only (D14) can't double-count. See M2 and M3 for what it can't see.
   - The `field` route can't fire vacuously on today's exports: no non-AMOUNT line field in any committed
     `v2/tests/fixtures/sync/**` capture contains `$` or `@`.
   - C43: the window is `month_window(2022, 9, "educational")` = 01..02-09-2022 (`test_educational_window_is_c43_safe`),
     and the master reads carry no period variables.
5. **Probe 21 / 18 B re-run figures.**
   - Consistent: Sep-2022 = 20 (educational puts every Sep voucher on day 1/2), FY 2022-23 = 240, and the p21
     kind-count total is 238.
   - D12: 37,216.04 + 95,897.68 = **1,33,113.72**, added to the magnitudes of both Sundry Debtors (debit) and Sales
     Accounts (credit), which is correct for a debit sale. Probe 18 B takes its expectations from `ledger_balances_at`,
     which now includes 101/102 once.
   - Probe 21's and `_verify`'s amount parsing (`reads.amount`) returns None on a forex expression and never raises,
     so neither can crash on the forex text. The TB group rows are INR.
6. **Is FakeBooks pinned to live (not ideal)?** Yes, for everything live settled:
   - V1 `?`-rate refused, V1b and V3 kept, the XML Currency create refused, the `? ` export layout byte-for-byte
     against the capture, the `$` row, and no extra leaf fields.
   - The remaining candidates are labelled: `no_base`, `plain`/`refuse` storage, `plain_plus_field` and
     `forex_ledger_closing`.
   - No test found that hides wrong behaviour. The one blind spot is shared by the fake and the loader: the fake's
     `forex_storage="plain"` load still verifies clean in `setup-b`, and no test asserts that it shouldn't (I1).

## Not run

- Live Tally: Task 6 (`setup-b`, probe 22, the 21/18 B re-runs).
- Tier-C timing (⏭ Q29).
- The root `tests/` suite (it doesn't collect `v2/`).
- `-W error` was not re-run by this review (the implementer recorded it green per commit).
