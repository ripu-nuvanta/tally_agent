# Code review — BI S0 company-B loader, minors round (2026-09-24)

**Scope:** `907b9d1` (company B number) and `928b638..fae0a13` (M1, M4, M6, M7, M9) on `feat/bi-s0-probe-harness`.
**Mode:** read-only. Nothing was run against Tally (a live load was in progress).
**Offline suite:** `uv run --project v2 pytest v2/tests -q` gave **`440 passed in 67.86s`**.

## Verdict

**Changes requested: one Critical finding.** It sits in M1's premise, not its code. M4, M6, M7, M9 and `907b9d1`
are correct.

M1's group-to-primary map is right for Tally's default chart. Its sign test is consistent with the project's
convention. It refuses **none** of company B's openings. But the fix rests on the claim from
`tally-write-exploration-v4.md` Op 5 that "Tally infers OPENINGBALANCE's side from the parent group." The project's
own settled spec says that claim is false. So M1 does not protect the load that is running now. It passes the three
debit openings that will land on the wrong side, and its docstring hardens the wrong belief.

---

## Critical

### C1 — M1 relies on a disproven wire rule, so company B's three debit openings will land as credits

- **Where:** `v2/probes/setup/writes.py`
  - the `check_opening_side` docstring and the `_RESERVED_SUBGROUP_PRIMARY` comment (~L48–82)
  - the `create_party_ledger` docstring (~L456–462)
  - the wire line `<OPENINGBALANCE>{abs(opening):.2f}</OPENINGBALANCE>`
  - this was introduced by F11 / Ruling C21. M1 reaffirms it.
- **Evidence:**
  - `docs/specs/2026-09-21-bi-part1-sync-design.md` L37–46 ("Settled 2026-09-23") says
    `backend/tally_bridge/import_builder.py:680` `abs(float(opening_balance))` "discards the debit sign the seeder
    sets (`HDFC -500000`, `SBI -200000`) … landing both bank openings as **credits**".
  - The live fixture `v2/tests/fixtures/sync/p18_A_ledger_list.xml` shows `HDFC Bank - Current A/c | Bank Accounts |
    500000.00` and `SBI Savings A/c | Bank Accounts | 200000.00`. These are positive, the same sign as `Capital
    Account 750000.00`.
  - Company A's TB nets to 7,50,000 + 5,00,000 + 2,00,000 + 18,55,800 = **₹33,05,800**. That total is only possible
    if the two unsigned bank openings were stored as credits.
  - Op 5 never verified the side: `scripts/explore_tally_write_v4.py` L571–589 only checks that the Capital ledger
    exists ("We accept this as success if ledger exists"). The "positive with Cash-in-Hand = debit" gotcha was never
    tested. Only Capital Account, which is naturally a credit, was ever consistent with it.
  - The live evidence therefore says Tally reads the sign of `OPENINGBALANCE` directly: negative means Dr, positive
    means Cr, whatever the group. That is also how Tally exports it.
- **Failure scenario (today's load):** `company_b_data.py` has 4 nonzero openings:

  | Ledger | Parent | Dataset | `check_opening_side` | Sent on the wire | Tally will store |
  |---|---|---|---|---|---|
  | Kolhapur (NON_BILLWISE_DEBTOR) | Sundry Debtors | −45,000.00 | pass | 45000.00 | **Cr 45,000** (wrong) |
  | Pune Digital Solutions | Sundry Debtors | −62,500.00 | pass | 62500.00 | **Cr 62,500** (wrong) |
  | HDFC Bank Current A/c | Bank Accounts | −8,68,050.00 | pass | 868050.00 | **Cr 8,68,050** (wrong) |
  | Capital Account | Capital Account | +10,00,000.00 | pass | 1000000.00 | Cr 10,00,000 (right) |

  - Company B's opening balance sheet will be inverted: Dr = only the ₹24,450 of opening stock, and Cr = ₹19,75,550.
  - Every per-ledger anchor that probes 16/18 measure against will be off by 2 × |opening| for these three ledgers.
  - `_verify_balances` compares magnitudes only. It should still flag Sundry Debtors and Bank Accounts as
    "balance magnitude mismatch", because the error is 2×1,07,500 and 2×8,68,050. The operator may read those lines
    as posting problems rather than an opening-side flip.
  - A re-run will **not** repair it. `create_party_ledger` skips any ledger that already exists ("already exists —
    not re-created"), so the wrong openings persist.
- **Suggested fix:**
  1. Do not trust company B's openings from today's run. Read back the three ledgers' `OPENINGBALANCE` (or the TB's
     Sundry Debtors / Bank Accounts rows) once the load finishes. If they are credits, correct them in the UI or with
     an ALTER plus readback, per LESSONS §15.
  2. Send the signed value on the wire (`{opening:.2f}`, negative means Dr), matching the dataset convention and
     C19/C22. Before relying on it, confirm with one throwaway ledger read-back: one debit opening under Bank Accounts
     and one under Sundry Debtors.
  3. Once the wire is signed, a contra-natural opening can be represented. `check_opening_side` then becomes
     unnecessary; drop it or keep it only as a warning.
  4. Correct Op 5's gotcha in `docs/tally-write-exploration-v4.md`, and add a dated "Changed" line on C21 / F11.
  5. The test `test_a_negative_dataset_opening_emits_a_positive_openingbalance_on_the_wire` pins the defect. Invert
     it.
  - This contradicts Rulings C21 and F13, so the controller needs to make a ruling before the fix. If the operator
    wants certainty first, the throwaway read-back in step 2 settles it in one request pair.

---

## Important

None. (The custom-group refusal is judged Minor below: it cannot affect today's load.)

---

## Minor

### m1 — The reserved-subgroup map is correct but applies the rule too strictly to Duties & Taxes

- **Where:** `writes.py` `_RESERVED_SUBGROUP_PRIMARY`.
- **The map is correct:** all 13 reserved sub-groups sit under the right primary.
  - Bank Accounts, Cash-in-Hand, Deposits (Asset), Loans & Advances (Asset), Stock-in-Hand and Sundry Debtors map to
    Current Assets.
  - Duties & Taxes, Provisions and Sundry Creditors map to Current Liabilities.
  - Bank OD A/c, Secured Loans and Unsecured Loans map to Loans (Liability).
  - Reserves & Surplus maps to Capital Account.
  - All 15 primaries appear in `reads.PRIMARY_NATURE`.
  - Under debit-negative, `(opening < 0) != debit_group` is the right test.
- **Scenario:** an Input GST ledger under Duties & Taxes naturally carries a **debit** opening (ITC carried forward).
  M1 refuses it as contra-natural. Company B has no Duties & Taxes openings, so this is harmless today. It goes away
  once C1 is fixed.

### m2 — Refusing custom groups goes further than needed, but it does not block today's load

- **Where:** `check_opening_side`, the `nature is None` branch.
- **Scenario:** none today. Company B's only custom groups are National Creditors and Local Creditors, and all four
  creditors have `opening=None`, so the check returns early. A future dataset with, say, `North Zone Debtors`
  openings (company A's shape) would be refused.
  - A group's nature could be resolved by walking `GroupSpec.parent` in the dataset. `_groups()` already carries
    that, with no Tally read.
  - Moot once the wire is signed (C1).

### m3 — The parametrized refusal test does not isolate the custom-group branch

- **Where:** `v2/tests/probes/test_setup_writes.py`, case `("Pune Traders", "Local Creditors", Decimal("-1.00"))`
  with `match="opening"`.
- **Scenario:** −1.00 is a *debit* under a creditors group. If `Local Creditors` were ever added to the map (or
  resolved via the parent), the contra-natural branch would raise instead, and the test would stay green. The
  `nature is None` branch is therefore not really pinned.
- **Fix:** use `Decimal("1.00")` (a natural credit) and `match="nature is unknown"`. Likewise, match `"contra-natural"`
  for the other three cases.

### m4 — The guard runs before the "already exists" skip

- **Where:** `writes.py` `create_party_ledger` (the `check_opening_side` call precedes `self.ledger(...)`).
- **Scenario:** a re-run against an existing ledger raises even though nothing would be sent.
  - This is arguably the right place: fail loud on bad data.
  - Worth one sentence in the docstring so it isn't "fixed" to run after the skip.

### m5 — The superseded plan still says 100004

- **Where:** `docs/plans/2026-09-23-bi-s0-company-b-loader.md` L958, L983.
- **Issue:** it states "`100004` is the number Tally assigns the second company". The tracker (L49/55/158/374) records
  the correction, but the plan's explanation reads as fact.
- **Fix:** add an inline "Superseded 2026-09-24: Tally assigned 100000 (lowest free)" note.
- `907b9d1` itself is correct. Config and test agree, and the explanatory comment is accurate.

---

## Commits judged correct (no findings)

- **`06eb2c4` M4:** the test does check the balance half, and it cannot pass vacuously.
  - It rebuilds each touched ledger's balance independently: opening plus non-cancelled lines. It checks this both
    at the FY end and at each cancelled voucher's own month-end, then compares the result with
    `expected.ledger_month_end`.
  - The `live != with_cancelled` check guarantees that counting a cancelled line would change the figure. Removing
    the `if v.cancelled: continue` in `expected_figures` (company_b_data.py ~L428) makes the test fail.
  - A missing key raises `KeyError`, so the test fails rather than passing silently.
  - The re-derivation repeats the same "opening + Σlines" arithmetic, so it only independently checks the
    cancelled-voucher filter. That is exactly what the test claims to check.
- **`9f41d67` M6:** accurate.
  - The dated header line and the struck §4.3 bullet match the plan (L1111: R9 re-scoped to probe 25's B part).
  - The note keeps "never attempted via XML (rule 10)".
- **`c3761c9` M7:** accurate.
  - `_verify` uses only `voucher_count_by_fy`.
  - `_verify_balances` uses its own `_posted_group_balances`.
  - `ledger_month_end` / `ledger_fy_opening` are consumed nowhere in `company_b.py`.
  - Ruling C16 (progress.md L98) and S0-D7 (spec L41) say what the comment claims.
- **`fae0a13` M9:** correct.
  - `report.created` is always seeded with all five `_MASTER_KINDS`, so the heading is never printed without rows
    under it.
  - The test asserts the heading and that the next line is an indented "created" row.
