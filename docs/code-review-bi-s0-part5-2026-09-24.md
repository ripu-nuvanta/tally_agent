# Code review: BI S0 plan part 5 (Tasks 1–9), task review and pre-live whole-part review (Ruling Q17)

- **Date:** 2026-09-24. **Branch:** `feat/bi-s0-probe-harness`. **Range:** `879dfb7..0f7c553` (9 commits, Q10 base).
- **Reviewer:** one opus review (`superpowers:requesting-code-review`, code-reviewer checklist). It was read-only on
  code: no edits, no commits, nothing sent to `localhost:9000`, and no subagents.
- **Inputs:** task briefs 1–9 and 9b, `progress.md` (Q1–Q17), `preflight-scan.md` (F1–F9, X*, D1–D12, C1–C12),
  `tasks-1-9-report.md`, the review diff, spec `docs/specs/2026-09-22-bi-s0-probes-design.md`, tracker blocks
  0a–0g, LESSONS §15 rules 17–22.

## Verdict: **ready for live with fixes**

Company A (Task 10a) is **ready now**. Probes 16 A, 17 A and 18 A, the C43 guard and the `anchors` command have no
blocking finding. Company B (Task 10b) needs **three small fixes first** (I1–I3 below). Each one is a place where a
live run would record a FAILED, or an over-claiming `spec_impact`, for a reason the probe never measured. The plan's
rule is that findings are recorded, not re-run ("DIFFERENT and FAILED are findings"), so a wrong verdict here would
be hard to undo. No Critical findings.

## Verification run by this review

| Check | Result |
|---|---|
| `uv run --project v2 pytest v2/tests -q` | **679 passed** (178 s) |
| `uv run --project v2 pytest v2/tests -q -W error` | **679 passed** (153 s) |
| CLI smoke `list` (fresh results file in the scratchpad, not `/tmp`) | `11 openings B B not run`, `14 … not run`, `15 … not run`, `16 … A+B B not run`, `18 … A+B B not run` ✅ |
| CLI smoke `run 22` | "Probe 22 is not built yet (S0 plan part 2 or 3)." `exit=2` ✅ |
| Snapshot byte-identity | `git diff -M --summary 879dfb7..HEAD -- v2/tests/fixtures/sync` shows **50 renames at 100%** ✅ |
| Isolation `git status --porcelain \| grep -v -E ' (v2/\|docs/)'` | Only pre-existing untracked clutter: the 8 root PNGs, `.pgtmp/`, `.playwright-mcp/`, `.tmp_eval/`, `backups/`, `frontend/.tmp_vitest/`, `latest-purchase-card.md`, `scripts/cleanup_mismatched_vouchers.py`, `scripts/cleanup_waterpump.py`, **plus `logs/`** (untracked, already in the session-start snapshot, and not produced by this part). Nothing else. `v2/`/`docs/` clean. `v2/probes/operator/` is untouched in the range ✅ |
| Off-day date literals in `v2/probes/*.py`, `v2/probes/setup/*.py` | None: every `"DD-MM-YYYY"` literal is on day 01/02/31, and no probe uses `today()` ✅ |

## Spec / ruling compliance per task

| Task | Verdict | Evidence (file:line at HEAD) |
|---|---|---|
| 1 Snapshot (Q1 F1/F2, Q2, Q13) | ✅ | `git mv`, 50 files at 100%. `test_evidence_snapshot.py:17-34`. p17 reads `p00_A_anchors_tb.xml` via `SNAPSHOT.parent` (`test_p17_ledger_level_tb.py:103-104`, F1). Variables are renamed `SNAPSHOT` in 16/17/18 (F2), and `test_reads.py` has 6 `C33_SNAPSHOT` sites plus the definition. Q2: `SNAPSHOT_AS_ON = p18.dmy("30-09-2025")` (`test_p18_historical_reports.py:197`). Every "live 2026-09-23" test reads the snapshot (`_live` in p17:99, p18:172; `SNAPSHOT` in p16:370). |
| 2 C43 guard + `anchors` (Q4, Q5, F3) | ✅ | One implementation: `safety.py:44-86`, one parser (`reads.tally_date`), one `GuardError`. `company_b_view.check_date_vars` delegates (`company_b_view.py:~98`). Guard sites: `context.py:83` (`try_send`), `context.py:116` (`_post_uncaptured`), `anchors.py:74` (`_post`), and all three reports are pre-checked before the company list goes out (`anchors.py` `check_anchors_direct`). `licence=None` passes, so probe 0 and placeholders (`__FROM__`) work (`_ignored_by_educational` returns False for non-dates). `runner.py:65` catches `GuardError` → BLOCKED (was "Harness error" for the old `ValueError`). One switch: `test_one_switch_turns_off_both_call_sites`. |
| 3 p16/p17/p18 A dates (Q3, Q14) | ✅ | `BILLS_AS_ON = "31-10-2025"`, whole-FY `vouchers_fy` (`p18_historical_reports.py:~28, ~190`). The Q3 post-31-10 fake voucher and the 3 tests are in place. The impact is chosen from evidence (`BILLS_STOCK_IMPACT` only when `full`, `BILLS_STOCK_WRONG_IMPACT` otherwise). The p16 `SVFROMDATE_SKIPPED` / `AS_ON_IMPACT` wording says "untyped". |
| 4 FakeBooks B masters (F5) | ✅ (knob defaults noted, see §Knobs) | `fake_books.py` `seed_company_b(masters=True)` and the `_b_collection` / `_ledger_export` / `_stock_summary` routes. `hindi.tag == 7`. |
| 5 p16 B (Q9, Q15, F6, F7) | ✅ | `judged_scope` (`p16_ledger_closing_balance.py:~470`): the typed FY 2024-25 read decides; the current-FY read supports it, and stands in with `source="current_fy_read"` + `why` only when SVTODATE is ignored or wrong. A disagreement with the FY 2024-25 read honoured → DIFFERENT. Drift check is symmetric (`^`). `undecided`/`neither` → DIFFERENT, never CONFIRMED. The opt-in SVFROMDATE is sent last, after every observation is recorded. The typed `<SVTODATE TYPE="Date">31-03-2025</SVTODATE>` is pinned by a test. |
| 6 p18 B (F8, plan Ambiguity 10) | ✅ (see I2) | `run_b` uses `compare_group_rows`, `dataset_rollup` and a drift BLOCK. The stricter rule (the stock-bearing group must reconcile via the `Opening Stock` row, else FAILED) is applied as Ambiguity 10 rules. |
| 7 p11 | ✅ (see M7) | Candidate = Ledger `BillAllocations` filtered to the party. Fallback = Bills Receivable as-on 01-04-2022. That fallback is live-backed: setup-b's clean verify (`setup/company_b.py:232-246`) reads exactly that report and found `Op/2022-001`. Magnitude-only, sign recorded. Stock sign flip → DIFFERENT. Missing ledger/item → BLOCKED. |
| 8 p14 + Q6/Q16 | ✅ (see M1, M2) | `ALL_ORDER` B run ends `…, 25, 14` (`registry.py:~61`). Spec §6 row and header "Changed 2026-09-24 (plan part 5, Ruling Q6)". Step order: escaped → unknown-company → unescaped (10 s) → cheap read. Tested by `test_probe_14_runs_last_in_company_b`. |
| 9 p15 + Q8 | ✅ (see I1) | `text_check` judges parsed text and records the encoding from evidence (utf-8 bytes / character references / not in the response). Spec header and §7 probe 15 dated Changed lines. F9 tag asserts are in place. |
| Q7 (10a/10b text lives in the ledger) | ✅ n/a to code | See §Live readiness. |
| Q11/Q12/Q17 | ✅ | 679 (= 666 + 13 Q-ruling tests). One implementer, nine commits, one review doc. |

## Findings

### Critical

None.

### Important (fix before Task 10b; none blocks Task 10a)

**I1. Probe 15 can record a false R14 "Hindi text doesn't round-trip" FAILED because of a TDL filter nobody has
measured.** `p15_unicode_compound_units.py:941-945`. The Hindi ledger is fetched with a
`$Name = "शर्मा ट्रेडर्स"` formula filter, and the part judges `names[0] if len(names) == 1 else None`.
- **Why it matters:** no live read has ever sent a non-ASCII literal inside a TDL formula. If Tally's formula compare
  mishandles it (encoding, normalisation), the collection comes back empty. `exact` is then False, and the part
  returns **FAILED with `TEXT_FAILED_IMPACT`**, blaming the text round-trip when it was the filter that failed.
  That breaks S0-D7: the verdict rests on an assumption the probe never measures.
- **Fix:** read the Ledger collection unfiltered (about 31 ledgers; probe 14 already does exactly that read and
  checks `has_hindi`) and judge `HINDI_DEBTOR in names`. Or keep the filter, but when it returns no rows, fall back
  to the unfiltered read and record `filter_matched: false`. Test: a FakeBooks knob that makes the Hindi filter
  return nothing must still give CONFIRMED (or a distinct DIFFERENT), never the text FAILED.

**I2. Probe 18 B's stock-only failure carries the "parity is suspended" impact.** `p18_historical_reports.py:~1631-1635`
(`bad = tb["mismatched"] + unreconciled_stock` → `spec_impact=TB_IMPACT`).
- **Why it matters:** when every non-stock primary group matches and only the stock-bearing group fails to
  reconcile via `Opening Stock` (a valuation or row-shape question), the part still writes "A TB as-on a past date
  isn't history … parity is suspended during the backfill (R30)". That is the same kind of over-claim Q14 removed
  from p18 A. Ambiguity 10's FAILED is kept; only the claim attached to it is wrong. It feeds R30 directly.
- **Fix:** when `tb["mismatched"]` is empty and only `unreconciled_stock` is non-empty, use a separate
  `B_STOCK_UNRECONCILED_IMPACT` (for example: "the stock-bearing group doesn't reconcile via its Opening Stock row;
  non-stock groups are history; R30 holds for them; stock parity is revisited"). Test: extend
  `test_b_without_the_opening_stock_row_the_stock_group_does_not_reconcile` to assert that the impact is not
  `TB_IMPACT`.

**I3. Probe 14 keeps sending after an earlier step timed out, then blames the unescaped request.**
`p14_special_char_company.py:826-839`.
- **Why it matters:** the unknown-company control (`SVCurrentCompany` naming a company that isn't loaded) is itself
  unmeasured live behaviour. If Tally answers it with a popup or a hang, `_read` records `kind: timeout`, and the part
  still sends the malformed request into a Tally that isn't responding. The final `ProbeBlocked` then says "Tally
  stopped answering **after the unescaped request**". The observations would contradict that, but the summary, which
  the tracker and spec quote, names the wrong step. It also sends a deliberately malformed request into a Tally
  that is already stuck.
- **Fix:** after `escaped` and after `unknown`, if `kind == "timeout"`, call `ctx.company_names()` at once, and
  BLOCK naming that step with `POPUP_HINT` without sending the unescaped copy. Test: `before_request` wedges on
  the unknown-company body → BLOCKED naming `unknown_company_request`, and no `unescaped_request` fixture.

### Minor (fix when convenient; don't hold the live run)

- **M1 p14 `CONFIRMED_IMPACT` over-claims when the company variable is ignored.** At `p14…py:840-849`, when
  `unknown["ok"]` is true, the impact still says escaping "is what makes `Sharma & Sons' …` reachable", and then
  appends `IGNORED_VAR_NOTE`, which says the variable doesn't select the company. The two sentences contradict each
  other. Pick the wording from `unknown["ok"]`: "escaping keeps the request well-formed; with one company loaded the
  name doesn't select the company (gate = probe 2)".
- **M2 p14 wedge: `tally_after` is not observed, and the hint is doubled.** On the `ProbeBlocked` path
  (`p14…py:836-839`), record `ctx.observe("tally_after", {"answered": False, "error": str(exc)})` before raising.
  `exc` already carries `POPUP_HINT` (from `context._post_uncaptured`), so the re-wrap prints it twice (scan D6).
- **M3 p16 B disagreement test (Q15).** `test_b_scope_reads_that_disagree_are_different` (`test_p16_b_part.py:111-120`)
  is **not order-fragile in outcome**. Flipping either the first or the second `opening_scope` call produces a
  disagreement, and so a DIFFERENT, and monkeypatch is per-test. It is weak, though. It would still pass if `run_b`
  swapped which read is the judged source, and the flipped dict has an inconsistent `as_books`/`as_fy`. Better: a
  FakeBooks knob that scopes openings differently for a typed-SVTODATE read than for a no-variable read, then
  assert `source == "fy2024_read"`, the verdict, and "disagree".
- **M4 p16 B `wrong` branch is untested.** `AS_ON_WRONG_IMPACT` / FAILED "moved … but not to the as-on values"
  (`p16…py:~1305-1309`) has no test. That is the "untested branch" pattern that hid C43. Add a knob (for example
  `ledger_svtodate_to=<other date>`).
- **M5 `_post_uncaptured`'s C43 call has no test.** `context.py:116` is there, and its callers (company list,
  counters) carry no dates today. Task 9b asked for coverage: add one test that sends an off-day date through
  `counters()`'s uncaptured path.
- **M6 The fake's compound ACTUALQTY isn't the live shape.** Live (tracker 0e) reads `" 10 Box 0 Nos"`, but
  `fake_books.py:2117-2121` emits `" 10 Box"`. `qty_number` takes the leading number, so the verdict is unaffected.
  Still, per CLAUDE.md "fixtures mirror reality", make the fake emit the live form.
- **M7 p11 conflates the ledger opening with the bill amount.** At `p11_openings.py:704`, `want = s.opening`, which
  is right for the one dataset bill (−62,500 = full opening, live-read as −62,500.00). It would silently mis-judge a
  partial opening bill. Document the assumption, or carry the bill amount in `LedgerSpec`.
- **M8 Setup-path sends skip the C43 guard.** `setup/writes.py:206` `TallyWriter.post` isn't guarded. Its dated
  reads (`B_READBACK_FROM/TO` 01-04-2022/31-03-2026, `BILLS_RECEIVABLE_AS_ON` 01-04-2022) are all on valid days,
  so nothing is wrong today. Q4's scope is probe sends, so this is noted only.
- **M9 p15 / p16 B observations are lost when a mid-part BLOCK fires.** `observe` runs after all reads
  (`p15…py:976-979`). A drift BLOCK on the compound voucher discards the Hindi-ledger evidence already gathered.
  Observe each item as soon as it's measured.
- **M10 Dangling references after the `git mv` (Q13, Task 11).** `results.json` `fixtures` lists for 16/17/18 A
  (lines ~1175-1184, ~1398-1403, and p18's) name flat files that no longer exist. After 10a these entries move to
  `history`. The `2025-09-30` / `vouchers_to_2025-10-31` names are never re-created. Docs citing flat paths:
  `docs/plans/2026-09-22-bi-part1-tracker.md:488`, `docs/code-review-bi-s0-company-b-minors-2026-09-24.md:33`,
  `docs/tally-write-exploration-v4.md:154`, spec `:272`, plan-part2 `:81, :4059-4062, :5228`, plan `:1222`. Nothing
  in code reads the `fixtures` lists (`results.py` only loads JSON), so this is docs only. Task 11 points them at
  `c33_untyped_2026-09-23/`.
- **M11 Task 11 text now contradicts Q9.** Plan Task 11 step 1(b) says "scope decided from the current-period
  read", but under Q9 the typed FY 2024-25 read decides and the current-FY read stands in. Task 11 must write Q9's
  version. Spec §11.5 also needs: 14 `unknown_company_request`; 16 B `groups`/`ledgers`/`ledgers_fy2024_svfromdate`;
  18 A `…_2025-10-31`/`vouchers_fy`; 11 `opening_bills_report`.

### FakeBooks knobs vs S0-D7 (asked explicitly)

- **`ledger_svtodate_honoured=False`:** a hypothesis, taken from the 2026-09-23 *untyped* evidence. No verdict
  silently depends on it. p16 B measures `as_on_state` (works/ignored/wrong) from Tally's own answer, and both
  default paths are tested (`test_b_as_on_ignored…` and `…honoured…`, plus the Q9 tests). The fake can fail:
  closing ≠ dataset → FAILED, and drift → BLOCKED. The `wrong` state has no knob (M4). 10a step 5 (typed SVTODATE on
  company A) settles it live before 10b.
- **`honour_company_var=False`:** a hypothesis. The verdict doesn't depend on it: CONFIRMED either way, with only the
  note changing. With `honour_company_var=True` the fake can fail a badly escaped name, because the variable is
  `html.unescape`d and compared. The only issue is the impact wording (M1).
- **Other defaults:** `ledger_svfromdate_wedges=True` is the recorded untyped behaviour.
  `ledger_opening_bills_exported=True` has both paths tested. `opening_stock_row=False` has both paths tested, and
  live A had the row.

## Live readiness (Tasks 10a / 10b, C44 live, `tally.ini` `Load=100000`)

- **What changes for the operator (Q7):**
  - A hand start of Tally now opens **B**. Company A is opened only via `restart("A")` (C44 rewrites
    `Load=100003`) or `reset-a`.
  - C44 is live-verified for **B only**. So 10a's first live action is the 10a step-3 snippet trimmed to
    `restart("A")`. Expect `['Bharat Traders Probe Copy']` and `Load=100003` afterwards.
  - If that fails, record it in the C44 row and switch by hand in the UI: shut B, then F3 select A. Don't restart.
  - The plan's `Load=` warnings (10a step 2, 10b step 2) are obsolete. Follow the ledger's Q7 text.
- **Company A:** `anchors` (read-only, guarded, dates 01-04-2025/31-03-2026) → 16 A (no `--allow-risky`) → 17 A →
  18 A → `anchors --when after_a_batch`. The CLI works: `--non-interactive` is a top-level flag, so the `anchors`
  branch's `args.non_interactive` resolves. Only the no-baseline path is unit-tested.
- **Company B:** `restart("B")` or a hand start. Run 16 B → 18 B → 11 → 15 → 14, one log each.
  - Every B request's dates are on days 1/2/31, and the p16 B test asserts it
    (`educational_ignored_dates(r) == []` for all requests).
  - Probe 5's `voucher_month` is confirmed in `results.json`, which 15 needs.
  - 16 B `requires=(0,1,2)`: all CONFIRMED.
  - Apply I1–I3 first.
- **Probe 14 recovery:** if it BLOCKs with the popup hint, dismiss the popup (or `restart("B")`). It is last in B,
  and an ordered `--all` then only reaches probe 24, which is not built.

## Must-fix before live

1. **I1** p15: judge the Hindi ledger from an unfiltered (or fallback) Ledger read, so a filter miss can't become an
   R14 text FAILED (before 10b).
2. **I2** p18 B: a stock-only unreconciled failure gets its own impact, not `TB_IMPACT`'s "parity suspended"
   (before 10b).
3. **I3** p14: stop and BLOCK, naming the step, when the escaped or unknown-company read times out, before sending
   the malformed request (before 10b).
4. **Operational (10a):** verify `restart("A")` live (A only, `Load=100003`) before any A-batch command. Otherwise
   switch A in the UI by hand.

Re-run the suite after the fixes, with and without `-W error`. Expected: 679 + the new tests.

## Declined to judge

- **LESSONS/spec wording updates (Task 11):** out of this range. M10/M11 only list what Task 11 must carry.
- **`v2/probes/operator/` (C44 code):** not this plan's work, and unchanged in the range.
- **Whether live Tally honours a typed SVTODATE on a Ledger collection, or exports `BillAllocations` on a Ledger
  collection:** those are the probes' questions. They were judged only for whether the code measures them.
- **Plan-supplied lines over 120 characters:** no linter enforces the limit, and they match repo style.
- **The advisory test counts in the plan (Q11).**

## Suites not run

- Live Tally (Tasks 10a/10b): by design, not before this review.
- Tier-C timing probes (⏭ Q29).
- The root `tests/` suite (it doesn't collect `v2/`) and the frontend suites: S0 changes nothing outside `v2/` and
  `docs/`.
- The eval and `e2e_live` suites: not applicable.
