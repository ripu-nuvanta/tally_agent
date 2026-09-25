# BI S0 exit gate audit (2026-09-25)

- **Gate:** `docs/specs/2026-09-22-bi-s0-probes-design.md` §10 (L912–920), items 1–7.
- **Branch:** `feat/bi-s0-probe-harness`, audited at HEAD `a5cafc0`.
- **Scope:** this audit covers items 1, 2, 3, 4, 6 and 7. The controller runs item 5 (company A anchors) live and fills
  in its section below.
- **Method:** read-only. The audit did not contact Tally or `localhost:9000` and ran no
  `python -m v2.probes run|anchors|setup-*|reset-a`. Evidence comes from `python -m v2.probes list`,
  `v2/probes/results/results.json`, the specs, the tracker, git, and the offline suite.

## Verdict summary

> **Superseded 2026-09-25. See "Final verdict (2026-09-25)" at the end.** Items 3, 5 and 7 were closed after this
> audit, by `e8420f1`, `9830e97`, and `bb71f83` + `86df230`/`b92a659`/`da9e7d4`. The table below and the
> "Recommendation" sections keep the audit as written at `a5cafc0`.

| # | Gate item | Verdict |
|---|---|---|
| 1 | Every tier-B probe has an outcome (none PARTIAL or unrun) | **PASS** |
| 2 | Every DIFFERENT / FAILED has its Part 1 spec change | **PASS, with body-text exceptions** (the dated headers carry every change; some §6/§12/R30 body lines still contradict them) |
| 3 | Probes 16, 17, 18 written into Part 1 §6 and §16 | **GAP** (§16 is done; §6 lacks probe 16's as-of/post-dated rule and the C45 correction) |
| 4 | Q22/Q23 answerable from probe 21's storage table | **PASS** (the 240-voucher re-run still supports the 2026-09-24 decisions) |
| 5 | Company A anchors | *controller, live (see the placeholder below)* |
| 6 | Tests pass; only `v2/` + `docs/` changed | **PASS on tests. Exception on paths:** `CLAUDE.md` changed (process doc). `LESSONS.md` is allowed by the plans. |
| 7 | Code review stored for every S0 plan part | **GAP** (no review for plan part 2; C47 commits unreviewed) |

**Recommendation: the gate does not pass yet.** Two gaps block it, and both are cheap to close:

1. **Item 3.** Write probe 16's as-of/post-dated rule and the typed-SVTODATE/C45 correction into Part 1 §6 "Rung 1" and
   "The opening anchor".
2. **Item 7.** Write `docs/code-review-bi-s0-part2-<date>.md`, or get explicit user sign-off to waive it. Review the C47
   commits.

Once those are closed and item 5 is OK, the gate **passes with recorded exceptions**. The exceptions are listed under
"Other open items" below.

---

## Item 1: every tier-B probe has an outcome. **PASS**

`uv run --project v2 python -m v2.probes list` at `a5cafc0`:

```
 0 environment A CONFIRMED            13 backup_restore A CONFIRMED
 1 company_counters A CONFIRMED       14 special_char_company B CONFIRMED
 2 active_company_guid A CONFIRMED    15 unicode_compound_units B CONFIRMED
 3 voucher_ids_flags A+B CONFIRMED    16 ledger_closing_balance A+B FAILED
 4 alterid_filter A CONFIRMED         17 ledger_level_tb A CONFIRMED
 5 voucher_month_bounds B CONFIRMED   18 historical_reports A+B CONFIRMED
 6 nested_lines_ledger_guid A CONF.   19 counter_stability A CONFIRMED
 7 deleted_vouchers A CONFIRMED       20 parity_cost — C ⏭ deferred (Q29)
 8 ledger_rename A CONFIRMED          21 full_history_reach B B+C CONFIRMED
 9 chunk_latency — C ⏭ deferred (Q29) 22 forex B CONFIRMED
10 error_shapes A CONFIRMED           23 gst_due_dates A+B CONFIRMED
11 openings B DIFFERENT               24 secured_company C CONFIRMED
12 current_snapshots A CONFIRMED      25 masters_classification A+B DIFFERENT
```

What `results.json` shows, per part:

- **Every registered part of every probe has a stored outcome.**
  - A+B probes: 3 A/B CONFIRMED, 16 A DIFFERENT / B FAILED, 18 A/B CONFIRMED, 23 A/B CONFIRMED, 25 A/B DIFFERENT.
  - Every `remaining` list is `[]`.
  - No part is `PARTIAL`: `grep PARTIAL results.json` returns nothing.
  - No current part is BLOCKED. Probe 22's C36 BLOCKED is lifted.
  - Probe 21's BLOCKED EOF attempt of 2026-09-25 16:52:49 sits only in `history`. The current probe 21 B result is
    CONFIRMED at 16:53:03.
- **Deferred ⏭ items are allowed by the spec.** §8 "Deferred probes" (spec L897–900) lists exactly these, all tier C
  (Q29):
  - probe 9 (chunk latency);
  - probe 20 (parity cost);
  - the timing half of probe 21;
  - the standard-edition runs of probes 7 and 13.

  §8 also says they "are listed ⏭ in `list`". They are tier C, so they fall outside item 1's "every tier-B probe".
  Probe 21's timing figures are recorded but labelled "Wine — not representative"
  (`probes.21.parts.B.observations.timings_ms.note`).
- **Cosmetic finding.** Probe 11 B's current result carries `ran_at` 2026-09-24T20:57:35. Its log is named
  `logs/p11-rerun-c46-2026-09-25.log`, and the tracker calls it a "Re-run 2026-09-25". The run really happened on
  2026-09-24 evening (the log mtime matches), so the file name and the tracker date are wrong, not the result.

## Item 2: every DIFFERENT / FAILED has its Part 1 spec change. **PASS, with body-text exceptions**

The DIFFERENT and FAILED probes are 11 (B DIFFERENT), 16 (A DIFFERENT, B FAILED) and 25 (A DIFFERENT, B DIFFERENT).
Each has its change written into `docs/specs/2026-09-21-bi-part1-sync-design.md`. File:line references follow.

**Probe 11 (R5, openings, C46)**

| Where | What it says |
|---|---|
| L136–142 | Header "Changed 2026-09-24" point 4. The stock half is FAILED (C46). The ledger half is struck through and pointed at the 2026-09-25 block. |
| L147–154 | "Two inputs": the master `OpeningBalance` is current-period-relative, never books-start. |
| L185–190 | Header "Changed 2026-09-25 (plan part 6)". Probe 11 re-run is DIFFERENT: both ledger and stock master openings are current-period. Books-start anchors come from the TB / Stock Summary as-on books start. |

**Probe 16 (decision 11, R30, C45)**

| Where | What it says |
|---|---|
| L110–124 | Header "Changed 2026-09-24" point 1. A typed SVTODATE is honoured inside the current period. It clamps before the period (C45). |
| L244 | Decision 11 row, "Changed 2026-09-24 (plan part 5)". |
| L1167 | §12 probe 16, "Corrected 2026-09-24". |
| L1265–1281 | §16. |

Probe 16 A's other DIFFERENT half (nominal ledgers have a non-zero ClosingBalance) is already honoured by the design:

- §6 Rung 1 selects ledgers by group `nature` (L660).
- Nominal ledgers are `not_applicable` (L682).
- The TB's `Opening Stock` row is covered at L74–78 and L748–749.

**Probe 25 (R9, R16: nature and base type are derived, not read)**

| Where | What it says |
|---|---|
| L256 | Data contract: `nature` and `base_type` are derived by S1. |
| L603–609 | `tally_groups.nature`: Parent walk + `PRIMARY_NATURE`. |
| L612–617 | `tally_voucher_types.base_type`: Parent-chain walk. |
| L173–178 | Header 2026-09-25: 25 B DIFFERENT (same rule) and R9 duplicate names refused. |

**Exceptions to record.** The dated headers win, but these body lines still state the superseded result:

- **§6 L734–735** says: "Once history is complete, `tally_balance_as_on(...)` is replaced by the ledger's books-start
  `OpeningBalance` (probe 16)". Probes 11 and 16 B showed that ledger `OpeningBalance` is the **current-FY** opening
  (`opening_scope = fy`, L187). This is a live design contradiction, not just stale wording: the formula would
  double-count prior FYs. It must be fixed in S1's parity design.
- **§6 L723–724** says "as-on per-ledger balances are unobtainable from the Ledger collection (live 2026-09-23)". That
  was corrected by the typed probe 16 A for in-period dates (header L115–117).
- **§12 L1162** (probe 11) still reads "Ledger `OpeningBalance` … CONFIRMED against books-start values". Only the header
  (L136–138) was corrected. The tracker row 11 says "Part 1 spec point 4" was corrected, which is true, but §12 was
  missed.
- **R30 Handling L1145** still offers "probe 16 (ledger `OpeningBalance` readable as-on a date)" as a per-ledger route.
- **C47** (a forex ledger at the latest rate, so parity must expect the unrealised difference) is in the header
  (L204–209) and at L627. §6 Rung 1 and Rung 2 do not mention it yet.

## Item 3: probes 16, 17, 18 written into Part 1 §6 and §16. **GAP**

- **§16: done.** L1265–1281 carry all three:
  - probe 16's typed re-measure and C45;
  - probe 17 settled, `ISLEDGERWISE=Yes`;
  - probe 18 settled for TB (2026-09-23) and Bills/Stock (2026-09-24, C43 artefact).
- **§6: probes 17 and 18 done.**
  - Probe 17: "Per-ledger anchors during backfill" L736–746, with both caveats (`Opening Stock` row, EXPLODEFLAG).
  - Probe 18: the opening anchor from a dated TB (L713–736), and Rung 2 adds the `Opening Stock` row (L748–749).
- **§6: probe 16 is missing.** The S0 spec's own outcome rule for probe 16 (S0 spec L772) says: *"The post-dated rule
  and the as-of date are written into Part 1 §6 'Rung 1'."* That has not happened.
  - Part 1 §6 "Post-dated vouchers" (L677–680) still reads "Probe 16 settles both".
  - `grep -n "31-03-2026\|IsPostDated=Yes"` on the Part 1 spec finds no probe-16 result anywhere in it.
  - The measured answer exists: `results.json` `probes.16.parts.A.spec_impact`, and S0 spec L777–779. "ClosingBalance
    is as of the period end (31-03-2026), not Tally's current date; post-dated vouchers are included; IsPostDated
    exported 'Yes'."
  - §6 also has no C45 / typed-SVTODATE correction (C45 appears in the Part 1 spec only at L119 and L1281). The stale
    L723–724 still says "unobtainable".
- **To close:** add a dated "Changed" line to §6 "Rung 1" that does three things:
  1. states the as-of date as the current period's end;
  2. states that post-dated vouchers are counted, so `:as_on` = period end and `is_post_dated` lines are included;
  3. corrects L723–724 and L734–735 per item 2.

## Item 4: Q22/Q23 answerable from probe 21's storage table. **PASS**

- **The questions are decided.** Part 1 spec §15:
  - **L1251 Q22:** "DECIDED 2026-09-24 (user): keep `raw` for the recent 2 FYs only; older backfilled years store the
    structured columns only".
  - **L1252 Q23:** "DECIDED 2026-09-24 (user): no year floor … day chunks plus a per-company storage alert".
  - The tracker change log (L612) matches.
- **The re-run still supports the decision.** `results.json` `probes.21`:

  | | Decided on (2026-09-24, `history`) | Current (2026-09-25 re-run) |
  |---|---|---|
  | Vouchers | 236 | 238 (FY 2022-23 now holds 240 incl. USD 101/102; flagged excluded from sizes) |
  | Columns, B/voucher | 1050.3 | 1047.1 |
  | Raw JSON, B/voucher | 6518.5 | 6493.6 |
  | Raw JSON share | 86.1% | 86.1% (`storage.q22.raw_share_pct`) |
  | 200k/yr × 10 yr, with raw | 15137.5 MB | 15081.4 MB |
  | 200k/yr × 10 yr, without raw | 2100.5 MB | 2094.2 MB |
  | 200k/yr × 10 yr, raw for recent 2 FYs only | 4707.9 MB | 4691.6 MB |
  | 200k/yr month chunk | 626.9 MB, over the chunk cap | 623.9 MB, `over_chunk_cap: true` |
  | 10k and 50k/yr month chunks | under the cap | under the cap |

  Every figure moved by under 0.5%, and in the direction that favours the decision. Adding forex AMOUNT text did not
  grow per-voucher size. The same conclusions follow: raw dominates storage, so drop it past 2 FYs; 200k/yr needs day
  chunks, so Q23's day-chunk auto-split stands.
- **Exceptions to record.**
  - Part 1 §15 L1251–1252 and R27 L1134 still quote the 2026-09-24 numbers (e.g. 15137.5 MB). This is harmless but
    stale.
  - The tracker's Q22/Q23 rows (L459–460) still say **"Decision pending"**, which contradicts its own change log (L612)
    and the spec.

## Item 5: company A anchors (controller, live) — **PASS**

Run 2026-09-25 17:12 by the controller: Tally restarted on company A only via C44 (`Load=100003`, one licence click;
`logs/s0-exit-restart-A-2026-09-25.log`), then `python -m v2.probes anchors --when after_a_batch` →
`--- anchors check (after_a_batch) company A: OK` (`logs/s0-exit-anchors-A-2026-09-25.log`). `results.json`
`anchor_checks` row: `{"when": "after_a_batch", "label": "A", "ok": true, "problems": [], "receivable": "970537.00",
"payable": "1834142.00", "ran_at": "2026-09-25T17:12:28+05:30"}` — the seed residuals (₹9,70,537 / ₹18,34,142)
unchanged since 2026-09-24. Tally then returned to company B (`Load=100000`, `logs/s0-exit-restart-B-2026-09-25.log`).

## Item 6: harness tests and changed paths. **PASS on tests. Exception on paths.**

**Tests**

```
$ uv run --project v2 pytest v2/tests -q            → 910 passed in 226.78s
$ uv run --project v2 pytest v2/tests -q -W error   → 910 passed in 224.85s
```

**`git status --porcelain`**

```
 M v2/probes/results/results.json        ← item 5's anchors row (see above); inside v2/
?? .pgtmp/ .playwright-mcp/ .tmp_eval/ backups/ frontend/.tmp_vitest/ logs/
?? 01-chat-ready.png … 08-both-new-written.png  latest-purchase-card.md
?? scripts/cleanup_mismatched_vouchers.py  scripts/cleanup_waterpump.py
```

- The tracked change is inside `v2/`.
- The untracked paths outside `v2/`+`docs/` are **not S0 work**. They were already untracked at the start of this
  session: earlier write-flow screenshots, production cleanup scripts, scratch directories.
- `logs/` is untracked because `.gitignore:15` ignores `*.log`.
- Taken literally, item 6 fails on these untracked paths. **Judgement:** they are not S0 changes and not a violation,
  but they must **not** be committed on this branch. Record them as an exception, or move them out of the repo root.

**`git diff --stat master...HEAD -- . ':!v2' ':!docs' ':!LESSONS.md'`**

- The raw result is **262 files** (backend/, frontend/, tests/, scripts/, `CLAUDE.md`, `pyproject.toml`, `uv.lock`,
  `.gitignore` …).
- **These are not this branch's changes.** The branch was cut from `dev` at `c04d7d2` (merge-base with `dev`), and
  `dev` is 95 commits ahead of `master`. They are unmerged `dev` features: FX, Group B, GST, dedup, inventory, edit
  history.
- Diffing from the real branch point isolates the branch's own changes:

  ```
  $ git diff --name-only c04d7d2 HEAD -- . ':!v2' ':!docs' ':!LESSONS.md'
  CLAUDE.md
  $ git diff --stat dev...HEAD -- . ':!v2' ':!docs' ':!LESSONS.md'
  CLAUDE.md | 26 +++++++++++++++++++++++++-
  ```
- **`LESSONS.md`: allowed.** It changed by +42 lines vs `dev`. Plan part 5 L52 ("Task 11 may also edit `LESSONS.md`")
  and plan part 7 L73 ("Task 7 may also edit `LESSONS.md`") allow it, and plan part 4 Task 8 set the precedent.
- **`CLAUDE.md`: a technical violation of the letter of item 6, low risk.** It is one commit, `dc9bf02` (2026-09-23),
  "docs: require the tracker to be updated as each part completes". It adds § "Always update the tracker" and
  lifecycle step 7. It is process documentation: no code, no runtime effect, and no plan authorises it. **Recommend:**
  record it as an accepted exception, or cherry-pick it to `dev` separately so the feature branch's diff is pure
  `v2/`+`docs/`+`LESSONS.md`.
- **Nothing under `backend/`, `frontend/`, `tests/` or `scripts/` was changed by this branch.** v2 isolation holds.

## Item 7: code reviews stored as `docs/code-review-bi-s0-*.md`. **GAP**

| S0 plan part | Plan | Review doc(s) | Status |
|---|---|---|---|
| 1 | `plans/2026-09-22-bi-s0-probes-plan.md` | `code-review-bi-s0-part1-2026-09-22.md` | ✅ |
| 2 | `plans/2026-09-22-bi-s0-probes-plan-part2.md` | **none** | ❌ Tracker L293: "Write `docs/code-review-bi-s0-part2-<date>.md` — still missing; plan part 2 shipped without it." Per-batch task reviews exist only in the untracked SDD ledger `.superpowers/sdd/2026-09-22-bi-s0-probes-plan-part2/progress.md` (L30–44), not in `docs/`. |
| 3 (company-B loader) | `plans/2026-09-23-bi-s0-company-b-loader.md` | `code-review-bi-s0-company-b-minors-2026-09-24.md`, `code-review-bi-s0-company-b-live-fixes-2026-09-24.md` | 🟡 These cover the minors round and the C30–C34 live fixes. The loader's **whole-branch final review** ("FINAL whole-branch review (opus, 24 mutations): READY WITH FIXES") is recorded only in the untracked `.superpowers/sdd/2026-09-23-bi-s0-company-b-loader/progress.md` L138. Acceptable if the two docs are taken as covering the part. Better: copy the final review into `docs/`. |
| 4 | `plans/2026-09-24-bi-s0-probes-plan-part4.md` | `code-review-bi-s0-part4-2026-09-24.md` | ✅ |
| 5 | `plans/2026-09-24-bi-s0-probes-plan-part5.md` | `code-review-bi-s0-part5-2026-09-24.md` | ✅ |
| 6 | `plans/2026-09-25-bi-s0-probes-plan-part6.md` | `code-review-bi-s0-part6-2026-09-25.md` | ✅ (range `1043c91..9bd5262`) |
| 7 | `plans/2026-09-25-bi-s0-probes-plan-part7.md` | `code-review-bi-s0-part7-task1-2026-09-25.md`, `code-review-bi-s0-part7-2026-09-25.md` | 🟡 These cover `95941a1..47330a5` and `e3dd9c8..164af9a`. The **post-review C47 code is unreviewed**: `2c568be` (10 files, +197/−50, `company_b.py`, `company_b_data.py`, `FakeBooks`) and `136e5f6` (`p22_forex.py`, +33). It was live-verified (setup-b run 2 clean, probe 22 CONFIRMED) but has no review. |

Other v2 code commits after a review, with no review doc:

- the part-6 review fixes `0ec3653`, `fd42e9c`;
- the part-6 minors `9788d0e`, `0697ad7`, `c81c53c`, `8593761`, `ca5388c`, `3871e86`;
- `95941a1` (`judge_halves`).

All are small. **Recommend** one short catch-up review covering `2c568be`, `136e5f6`, `95941a1` and the part-6 minors,
stored as `docs/code-review-bi-s0-part7-c47-<date>.md`.

## Other open items (not gate criteria; record them as exceptions or carry into S1)

1. **Probes 16 B and 11 cannot be re-run as built.** The USD party's `ClosingBalance`/`OpeningBalance` export as an
   expression (`-$1609.71 @ ? 82.58/$ = -? 132929.85`). `parse_ledger_list` raises `AmountParseError` on it.
   - Sources: tracker "Resume here" step 3; Part 1 L210–213; plan part 7 "Open follow-ups".
   - Their stored verdicts stand, because they were measured before the forex data existed.
   - **The agent-side parser needs the same fix**, so this is an S1/S2 input, not an S0 blocker.
2. **Stale-dataset B verdicts (plan part 7 review M4).** Probes 3/11/14/16/25 B were judged against the pre-part-7
   dataset (958 vouchers, 25 ledgers, no USD party). The tracker notes this on each row. It is a recorded exception: a
   later difference is the dataset change, not a regression.
3. **Tier-C / licensed-Tally confirmation.** Every result is TallyPrime 7.0 Edit Log **Educational** under **Wine
   11.0**.
   - Probe 16 A's result carries "[Educational mode — confirm on a licensed Tally]".
   - The C43 date clamp is Educational-only.
   - R8 (backup/restore UI parity) "stays open" (tracker L325).
   - Timing probes 9/20/21-timing and the standard-edition runs of 7/13 are ⏭ (Q29).
4. **§6 parity contradictions** (item 2 exceptions). L734–735 books-start `OpeningBalance`, and C47 is missing from
   Rungs 1/2. S1's parity design must resolve both.
5. **Evidence durability.** All the probe logs the tracker and specs cite as proof live only on this Mac:
   `logs/p*-live-*.log`, `logs/setup-b-*`, `logs/c44-*`, 49 files in all. `*.log` is gitignored and `logs/` is
   untracked. Fixtures and `results.json` are committed; the logs are not. Accept this, or archive the logs.
6. **Tracker inconsistencies** (for the tracker owner; this audit does not edit the tracker).
   - The Q22/Q23 rows (L459–460) say "Decision pending", but both are decided.
   - "Resume here" step 4 says "Deferred minors M1–M8" from the part-6 review, but M1, M3, M4, M5, M6 and M7 were
     applied (`9788d0e`, `0697ad7`, `c81c53c`, `8593761`, `ca5388c`, `3871e86`). Only M2 and M8 look outstanding.
   - The probe 11 re-run date is wrong: it says 2026-09-25, but the run happened on 2026-09-24 20:57.
7. **Rendered results file name.** `docs/bi-s0-probe-results-2026-09-24.md` holds the 2026-09-25 snapshot (its title
   says 2026-09-25). This is cosmetic.

## Recommendation

**The gate does not pass as of `a5cafc0`.** Items 1, 2, 4 and 6 are PASS, with exceptions to record. Item 5 is pending
the controller's live run. The blockers:

- **Item 3 (GAP):** probe 16's as-of/post-dated rule, and the C45 correction, are not in Part 1 §6. The S0 spec (L772)
  requires them there. This is a small, docs-only fix.
- **Item 7 (GAP):** there is no review doc for plan part 2, and the C47 commits have not been reviewed. Either write
  them or get explicit user sign-off to waive them. CLAUDE.md § Test reality rule 4 says "a flagged gap is a TODO, not a
  footnote".

Once those are closed and item 5 is OK, **the gate passes with recorded exceptions:**

- `CLAUDE.md` `dc9bf02` in the branch diff;
- unrelated untracked root files;
- ⏭ tier-C probes (spec §8);
- stale-dataset B verdicts (M4);
- expression-form parsing (an S1 input);
- §6 L734–735 and C47 parity wording (an S1 input);
- gitignored evidence logs.

---

## Final verdict (2026-09-25)

**S0 exit gate PASSES with recorded exceptions.** This supersedes both "Recommendation" blocks above.

| # | Gate item | Final verdict | Closed by |
|---|---|---|---|
| 1 | Every tier-B probe has an outcome | **PASS** | audit (`f0104e4`) |
| 2 | Every DIFFERENT / FAILED has its Part 1 spec change | **PASS** | audit. The stale body lines were corrected in `e8420f1`. |
| 3 | Probes 16, 17, 18 written into Part 1 §6 and §16 | **PASS** | `e8420f1`: §6 "Rung 1" now has probe 16's as-of and post-dated rule, C45 and C47 |
| 4 | Q22/Q23 answerable from probe 21's storage table | **PASS** | audit |
| 5 | Company A anchors | **PASS** (live 2026-09-25 17:12) | `9830e97` |
| 6 | Tests pass; only `v2/` + `docs/` changed | **PASS**, exception (a) | audit. Suite at the fix commits: 912, then **917 passed**, normal and `-W error`. |
| 7 | A code review is stored for every S0 plan part | **PASS** | `bb71f83` (part-2 retro review + C47 catch-up review); its two Important findings were fixed in `86df230` (I1) and `b92a659` (I2); fix round recorded in `da9e7d4` |

**Recorded exceptions.** None of these blocks S0. Each one is carried forward as stated.

- **(a) `CLAUDE.md` changed on this branch.** Commit `dc9bf02` adds the "Always update the tracker" rule. It is
  process documentation only. **Accepted.**
- **(b) Every result comes from Educational TallyPrime 7.0 running under Wine.** Confirmation on a licensed install is
  deferred to tier C. **R8 stays open.**
- **(c) Probes 9 and 20 are ⏭ tier C (Q29).** S0 spec §8 allows this, along with the timing half of 21 and the
  standard-edition runs of 7 and 13.
- **(d) Probes 11 B and 16 B can't be re-run until an expression-form balance parser exists.** This is an open S1
  decision.
  - The USD party's `OpeningBalance` and `ClosingBalance` both export as `-$1609.71 @ ? 82.58/$ = -? 132929.85`.
  - Since `b92a659`, both tags are pinned offline:
    - FakeBooks matches `p22_B_usd_ledger.xml`;
    - 11 B and 16 B BLOCK with `AmountParseError`.
  - Their stored verdicts stand, because they were measured before the forex data existed.
- **(e) Plan part 7 review M4.** The B verdicts of probes 3, 11, 14, 16 and 25 were judged against the pre-forex
  dataset: 958 vouchers, 25 ledgers, no USD party. A later difference reflects that dataset change, not a regression.
- **(f) The part-2 retro review's 10 latent Minors are deferred to S1 hardening**
  (`docs/code-review-bi-s0-part2-retro-2026-09-25.md`). The retro says to do M2, M3, M7 and M8 before any tier-C or
  licensed re-run of the A batch.
  - **M1:** probe 7's CONFIRMED summary claims something it never checks.
  - **M2:** probe 13 judges "counters fall back" without first checking that they rose.
  - **M3:** `replace_company_folder` and `backup_company` delete before they copy.
  - **M4:** the operator text still says it "never edits tally.ini", but it has done so since C44.
  - **M5:** `_set_ini_load` rewrites only the first `Load=` line.
  - **M6:** `SystemRunner.list_tally` matches any command line that contains "tally.exe".
  - **M7:** probe 10's "popup not raised" path leaves a stock group behind with no cleanup note.
  - **M8:** the auto-operator keeps a voucher ref after a restore has removed the voucher.
  - **M9:** `run_order` marks a company "current" without switching to it.
  - **M10:** deferred B1/B3/B5 minors:
    - p17's `spec_impact` dict repr;
    - p18 doesn't skip `ISPOSTDATED`;
    - `run_probe` / `run_anchor_check` record no traceback.
- **(g) The C47 review's Minors M1–M6 are deferred**
  (`docs/code-review-bi-s0-part7-c47-2026-09-25.md`):
  - M1: latest-dated vs last-entered rate;
  - M2: setup-b's expected C47 gap is printed but not checked;
  - M3: a `no_base` closing leaves probe 22's revaluation empty;
  - M4: probe 22 is silent on other revaluation rules;
  - M5: an inconsistent FakeBooks `bases` + `expression` candidate;
  - M6: probe 23 B's `bill_date_differs` fires on a missing BILLDATE.
- **(h) Probe logs are local only.** `*.log` is gitignored, and `logs/` is untracked on this Mac. The committed
  evidence is the fixtures and `results.json`.

Also carried from the audit, not gate criteria:
- The unrelated untracked root files (write-flow screenshots, cleanup scripts, scratch directories) must not be
  committed on this branch.
- Resolving the §6 parity wording (C47, the books-start anchor) in the S1 parity design is an S1 input.

**Next:** the S1 spec (cloud: tables, device auth, ingest, parity). It needs the user for its design decisions,
including the expression-form balance parser (d) and how parity handles C47's unrealised difference.
