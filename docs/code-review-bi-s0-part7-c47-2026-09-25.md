# Code review: S0 plan part 7, the C47 commits and the part-6 minors (2026-09-25)

**Scope.** These commits had not been reviewed. This closes S0 exit gate item 7 for them
(`docs/bi-s0-exit-gate-2026-09-25.md`).

| Commit | What it does |
|---|---|
| `2c568be` | C47. A forex ledger is valued at its latest voucher rate: `expected_figures` gains `forex_revaluation`, FakeBooks revalues currency ledgers and exports the closing as an expression, and setup-b's TB note states the expected gap. |
| `136e5f6` | Probe 22 B records the forex party's revaluation. It is recorded only, never judged. |
| `95941a1` | `judge_halves` keeps every half's spec impact, worst verdict first. |
| `9788d0e` | Part 6 minor M1: setup-c refuses any company other than C. |
| `0697ad7` | Part 6 minor M3: probe 23 B records `report_offsets` and `bill_date_differs`. |
| `c81c53c` | Part 6 minor M4: FakeBooks' stock opening defaults to the current period (C46). |
| `8593761` | Part 6 minor M5: probe 11 says current-period stock rate/value are recorded only. |
| `ca5388c` | Part 6 minor M6: probe 25 B asks again after an empty R9 answer. |
| `3871e86` | Part 6 minor M7: FakeBooks' Agst Ref credit-period gap (F9) is noted in a docstring. |

**Checked against the live evidence.** Everything was checked offline; nothing was sent to Tally.
- `logs/setup-b-forex-live-2026-09-25.log`: TB total 183.87; Sundry Debtors `|-2590148.41|` against an expected
  `|-2590332.28|`.
- `logs/setup-b-forex-live-2026-09-25-rerun.log`: "observed 183.87; expected 183.87", with no problems.
- `v2/probes/results/results.json` probe 22 B: `closing_base -132929.85`, `bases_total -133113.72`,
  `revalued_at_latest_rate true`, `revaluation_difference 183.87`.
- `v2/tests/fixtures/sync/p22_B_usd_ledger.xml`.
- `v2/tests/fixtures/sync/forex_shape_2026-09-25_run2/`.
- `v2/tests/fixtures/sync/p18` B result at 31-03-2023: every primary group equals the dataset.

**The arithmetic reproduces.** 1609.71 × 82.58 = 132929.85 (HALF_UP). 132929.85 − 133113.72 = −183.87 on the debit
side, so the TB is out by +183.87. Both are right.

**Suite.** `uv run --project v2 pytest v2/tests -q`: **910 passed**, 227 s.

## Critical

None.

## Important

### I1. `judge_halves` now contradicts itself when probe 24's halves disagree (`95941a1`)

**Where:**
- `v2/probes/core.py:95-96`
- `v2/probes/p24_secured_company.py:46` (`CONFIRMED_IMPACT`)
- `v2/probes/p24_secured_company.py:238-244`

**What goes wrong.** The ruling behind this change was aimed at probe 25 B's R9 half, and there it holds. But
`judge_halves` has three callers, and probe 24's CONFIRMED-half impact is not scoped to its half. The text says: "XML
export of a secured **or vaulted** company is unchanged (same GUID, same data)". That is a claim about the whole
probe.

**Reproduced offline.** Pass `judge_halves` a CONFIRMED security half and a DIFFERENT TallyVault half with
`REKEY_IMPACT`. It returns two impacts:

1. `[REKEY_IMPACT]`: "…new name AND a new GUID… re-link path (Q25)"
2. `CONFIRMED_IMPACT`: "…vaulted company is unchanged (same GUID, same data)"

These two sentences contradict each other, and both are written into one `spec_impact`. A FAILED vault half gives
the same result: `FAILED_IMPACT` says "fails even with it open", next to "unchanged".

`test_p24_secured_company.py:133-143` exercises exactly this case (security CONFIRMED, TallyVault DIFFERENT). It only
asserts `"Q25" in spec_impact`, so it passes.

**Impact today:** none on recorded results. Probe 24 C is CONFIRMED on both halves (`results.json`
`sub_verdicts`). The bug is latent. A re-run on another TallyPrime build, or on tier C, where one half differs would
write a self-contradicting spec input, and spec edits are made from `spec_impact`.

**Fix (either):**
- Give probe 24 per-half CONFIRMED impacts, e.g. "Security on: export unchanged…" and "TallyVault on: export
  unchanged…".
- Or let a caller opt out, as probe 24 does, by passing `""` as the CONFIRMED half's impact and appending the
  whole-probe sentence only when `outcome` is CONFIRMED.

Also add `assert CONFIRMED_IMPACT not in part["spec_impact"]` to the mixed-halves test at
`test_p24_secured_company.py:133`.

### I2. FakeBooks exports the forex party's OpeningBalance as a plain number, but live exports an expression (`2c568be`)

**Where:**
- `v2/tests/probes/fake_books.py:814` (`<OPENINGBALANCE>{_amount_text(opening)}`)
- `v2/probes/p11_openings.py:175` (`parse_ledger_list`)
- `v2/agent/tally/reports.py:65`

**What goes wrong.** The live capture taken the same afternoon shows both balances as expressions.
`v2/tests/fixtures/sync/p22_B_usd_ledger.xml:51-52`:

```
<CLOSINGBALANCE TYPE="Amount">-$1609.71 @ ? 82.58/$ = -? 132929.85</CLOSINGBALANCE>
<OPENINGBALANCE TYPE="Amount">-$1609.71 @ ? 82.58/$ = -? 132929.85</OPENINGBALANCE>
```

The Part 1 spec (Changed 2026-09-25) records this too. `2c568be` modelled only the closing half:
`forex_ledger_closing` / `_closing_text`. The opening is always rendered plain.

**Consequences:**
- **Probe 11 B.** It reads `OpeningBalance` through `parse_ledger_list` → `parse_decimal`. Live, it will raise
  `AmountParseError` and BLOCK with a harness error, because the USD party now exists. Against FakeBooks it stays
  green. Unlike 16 B, nothing pins this. The only pin is `test_p16_b_part.py:123`, and it covers the ClosingBalance
  path.
- **Probe 16 B.** Its opening comparisons (`p16_ledger_closing_balance.py:511-537`) have the same blind spot. For now
  the closing expression masks it, because it BLOCKs first.
- **Tracker.** The tracker already says "probes 16 B / 11 need expression-form balance parsing before any re-run".
  But the fake that such a fix would be tested against cannot reproduce the opening half of the problem. A parser
  fix could therefore pass offline and still BLOCK live.

**Fix.**
1. Add the opening half to the fake. When `forex_ledger_closing == "expression"` and the ledger has a currency and
   forex lines, render OPENINGBALANCE through the same expression builder, using the as-at-period-start face total
   and rate.
2. Add a pinned test for probe 11 matching 16 B's: BLOCKED, `AmountParseError`, `132929.85`.
3. Add a FakeBooks-vs-fixture test that compares both tags with `p22_B_usd_ledger.xml`.

## Minor

### M1. "Latest-dated" and "last-entered" can't be told apart from the live data

**Where:**
- `v2/probes/setup/company_b_data.py:646,660`
- `v2/tests/probes/fake_books.py:739,850`
- `v2/probes/p22_forex.py` `revaluation()`

C47 is written as "the rate of its **latest-dated** forex voucher". The live books have exactly two forex vouchers:
101 (02-09-2022, 82.99) and 102 (05-09-2022, 82.58). They sort the same way by date, by tag and by entry (MasterID)
order. So the evidence cannot separate these rules:
- latest date;
- last entered;
- last altered.

The code also breaks same-date ties three different ways:
- `expected_figures` uses `(date, tag)`;
- FakeBooks uses `max((day, master_id, fx, rate))`;
- Tally's rule is unknown.

This is harmless for company B. It becomes a trap when S1 relies on the wording: an older-dated voucher entered
last, or two forex vouchers on one day.

**Fix:** the evidence cannot distinguish the rules, so either label it (spec + LESSONS) "latest by date (entry order
not separated)", or add an out-of-order forex voucher to a future probe. One more reason for caution: Tally's own
Rates of Exchange table, when it is filled in, may override the voucher rate, and that was not exercised either.

### M2. setup-b's C47 "expected" figure is written into a note but never checked

**Where:** `v2/probes/setup/company_b.py:677-683`

The note prints the observed total and the expected total side by side. A mismatch, say a third forex voucher or a
different revaluation rule, still produces no `report.problems` entry. The balances check at `:641-646` catches a
Sundry Debtors drift, but not a gap that lands elsewhere, e.g. a forex creditor.

This is consistent with S0-D7's "not asserted here", but the two figures now sit next to each other, so a reader
will take the line as a check.

**Fix:** either add a problem when `total != forex_gap`, or reword the note: "expected … (not checked)".

### M3. A `no_base` closing leaves probe 22's revaluation fields empty

**Where:** `v2/probes/p22_forex.py:58`

`value = fa.base if fa is not None else parse_decimal(closing)`. A forex expression without an `= ₹…` part gives
`fa.base is None`, so `closing_base`, `revalued_at_latest_rate` and `revaluation_difference` all come back `None`.
They could have been computed with `forex_base(fa)`, the "computed" route this module already uses for voucher
lines.

This is not live-relevant: live states the base. It only matters on the candidate path.

### M4. Probe 22 says nothing when the party is revalued by some other rule

**Where:** `v2/probes/p22_forex.py:209-212`

The summary and impact change only when `revalued_at_latest_rate` is true. Suppose `closing_base` differs from
`bases_total` but is not face × latest rate, for example a Rates-of-Exchange rate. The summary then says nothing, and
the only trace is in the observations.

This is by design ("not judged"). One sentence for "valued at neither the bases nor the latest voucher rate" would
stop a future re-run from looking like "nothing to see".

### M5. The FakeBooks candidate `forex_ledger_revaluation="bases"` + `forex_ledger_closing="expression"` renders an inconsistent expression

**Where:** `v2/tests/probes/fake_books.py:850`

The rate printed is the latest voucher rate, but the base is the sum of the bases. So face × rate ≠ base inside one
string, and nothing live has ever produced that. It is a test-only candidate combination, and no test uses it.

**Fix:** refuse the combination, or print a blended rate.

### M6. Probe 23 B's `bill_date_differs` also fires when BILLDATE is missing (`0697ad7`)

**Where:** `v2/probes/p23_gst_due_dates.py:130-131`

When `tally_date(bill["bill_date"])` is `None` (an empty BILLDATE), `None != term.bill_date` records a "differs"
entry with `"tally": ""`. That is not a date difference. Recording only, so no verdict is affected.

**Fix:** guard with `row_date is not None`, or add a separate `bill_date_missing` list.

## The rest, reviewed: no defects

- **`136e5f6` `revaluation()`.**
  - The face sign follows the party line's INR sign.
  - The latest rate comes from the `(date, tag)` order, which matches `expected_figures`.
  - The rounding is HALF_UP to paise.
  - The observation matches the live record exactly (183.87).
  - The verdict is left untouched as intended.
- **`2c568be` `expected_figures`.**
  - `value()` adds the revaluation only to currency ledgers.
  - `forex_bases` sums only the currency lines, so a currency ledger's INR opening (none today) wouldn't be
    double-counted.
  - The FY-opening values carry the revaluation. That is confirmed live indirectly: 18 B, re-run after the forex
    load, matched every primary group at 31-03-2023, including Sundry Debtors revalued at 82.58.
- **FakeBooks `_ledger_balances`.** It is now an instance method, and every caller was updated (`:618`, `:689`,
  `:796-797`). The `before=` path (the FY opening) revalues at the latest rate before the FY start, consistent with
  `expected_figures`.
- **`95941a1` for probes 25 and 11.** Probe 11's CONFIRMED halves carry `""`, so nothing changes there. In 25 B, R9
  now shows after the Parent-chain impact, as ruled.
- **`9788d0e` (M1).** The guard runs before `check_writable` and before any request.
- **`c81c53c` (M4).** The default follows live C46, and the four books-scope tests opt in explicitly.
- **`8593761` (M5).** Wording only; correct.
- **`ca5388c` (M6).**
  - Enter-then-`skip` still skips.
  - Two empty answers with one ledger read back give "not measured". The `duplicate_name` half is then left out of
    the halves, and its status is appended to the summary.
  - Two empty answers with a saved duplicate give "accepted", with `answer_agrees None`.
  - All paths are tested.
- **`3871e86` (M7).** Docstring only; the note is accurate: `p21` 217 → Inv/45.

## Verdict

**Ready, with two Important follow-ups. Neither changes a recorded result.**
- **I1** is a latent contradiction in probe 24's `spec_impact` that any mixed-halves re-run would produce.
- **I2** is a gap in the fake's fidelity. It hides the fact that probe 11 B, like 16 B, would BLOCK live on the USD
  party's expression-form OpeningBalance.

Fix both before any probe 11 / 16 B / 24 re-run, or before the S1 expression-balance parser is written against
FakeBooks. The C47 numbers themselves (expected figures, FakeBooks TB, setup-b note, probe 22 record) agree with the
live evidence to the paisa.
