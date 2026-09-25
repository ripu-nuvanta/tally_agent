# Code review (retrospective): S0 plan part 2, the probe harness and the company-A probes (2026-09-25)

**Why this exists.** Plan part 2 (`docs/plans/2026-09-22-bi-s0-probes-plan-part2.md`, 13 tasks) shipped without a
`docs/code-review-bi-s0-part2-*.md`. This fills that gap for S0 exit gate item 7
(`docs/bi-s0-exit-gate-2026-09-25.md`).

It is written after the fact. It reviews the part-2 code **as it stands at HEAD** (`9830e97`), not the history.

**Commit range.** `git log -- docs/plans/2026-09-22-bi-s0-probes-plan-part2.md` gives two commits:
- `a0d33e4` (2026-09-23), "S0 live-Tally probe harness + Part 1 design docs". This is the only code commit. Parts 1
  and 2 were built uncommitted in the working tree (per the SDD ruling "no commits") and landed together here: 326
  tests.
- `4a735b8`, a later docs touch.

**The part-2 surface.** Plan tasks 1–12 built these:
- Harness: `actions.py`, `runner.py` (ordered runs, the anchor steps), and the planned-parts / run-mode plumbing in
  `context.py` / `core.py`.
- Write helpers: `setup/writes.py` `TallyWriter`, covering payments, alter/delete by Master ID, ledger
  create/alter/delete/rename, company rename, the popup, report export and licence.
- The automated operator: `operator/{auto,tally_control,company_a,config}.py`, `run --auto`, `reset-a`.
- Probe 1, revised.
- The company-A parts of probes 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23 and 25.

Much of this has since been extended by parts 3–7 (company B, C44, C45, C46, C47). Findings below are limited to
defects in part-2-era code paths that are still in HEAD.

**Suite.** `uv run --project v2 pytest v2/tests -q`: **910 passed**. Everything here was checked offline; nothing was
sent to Tally.

## What the batch reviews at the time found

They are in the untracked `.superpowers/sdd/2026-09-22-bi-s0-probes-plan-part2/` ledger (`progress.md`,
`review-b1..b5.md`, `rereview-b2*.md`, `final-fixes*.md`). The `review-*.md` files are review packages (the code
under review). The verdicts are recorded in `progress.md` and in the tracker's change-log rows for 2026-09-22 and
2026-09-23.

| Review | Scope | Verdict | Findings |
|---|---|---|---|
| B1 | T1–T2: harness actions, write helpers | Approved | Minors deferred: anchor_checks Decimal→str after reload; a context import-order nit; `run_anchor_check`'s catch-all hides tracebacks. |
| B2 | T3–T4: operator, `run --auto`, `reset-a` | **❌ quality, 3 Important**, fixed in 2 rounds + re-reviews | (1) `stop()`'s kill fallback re-listed every `tally.exe` and could SIGKILL a foreign Tally. (2) The backup/restore path was built from an unsanitised tag, so `rmtree`/`copytree` could escape `backups_dir`. (3) Spawn/copy `OSError` wasn't translated into `OperatorError`. Round 2: the `tally.ini` backup `OSError` wasn't wrapped. |
| B3 | T5–T8: probe 1, then 3/4/6/7/8/12/16/17/18 | Approved | p16 uses a ledger-level debtor rollup (ruled acceptable; probe 18 does bill-wise). Minors: p16 FAILED impact lacked the as-on note; `_rule()` hard-coded the date; p17's impact embeds a dict repr; p18 doesn't skip ISPOSTDATED. |
| B4 | T9–T10 | Approved, no issues | — |
| B5 | T11–T12: probes 10, 13 (+19/23/25 A) | Approved | Minors: p13's empty sample passes vacuously; p10's `blind` precedence; p10 parses twice. |
| Final (whole part) | every v2 file | **Ready with fixes** | 3 Important: (I1) FAILED parts blocked ordered runs and the final anchors; (I2) Ctrl-C was swallowed by asyncio; (I3) the post-dated read-back blocked p16. One fix wave, I1–I3 + M1–M12, brought the suite to 316. |
| Scoped re-review of that fix wave (2026-09-23) | `final-fixes.md` against the code, each fix reverted to prove its test | Ready with fixes | 2 Important: p16's M6 guard would be `inconclusive` on every run, because probe 1's throwaway pushes `LastVoucherDate`; the M11 test didn't pin its fix. 4 Minor. All applied, 326 tests (tracker row 2026-09-23). |

**The final review's "stay deferred" list.** Each item was re-checked at HEAD. The ones still live are folded into the
findings below. The ones that are gone or no longer matter are in the last section.

## Critical

None.

## Important

None. The Important findings from B2, the final review and the re-review are all fixed at HEAD:
- the kill fallback now kills only `targets`: `tally_control.py`;
- the backup tag is validated: `company_a.py` `_TAG_RE` + the parent check;
- `OSError` is wrapped;
- FAILED parts are skipped in ordered runs: `runner.py:137-140`;
- the SIGINT handler is in place;
- the post-dated read-back returns LASTVCHID: `writes.py`.

Nothing found in this pass rises above Minor, because each remaining defect needs either a re-run on a changed Tally
or an operator error before it bites. The results already recorded for company A were checked against the
observations that each claim rests on (see M1 and M2).

## Minor

### M1. Probe 7's CONFIRMED summary claims something it never checks

**Where:** `v2/probes/p07_deleted_vouchers.py:82,106-108`

The summary says "…AltVchId moves on the delete". But `counters_moved_on_delete` is only observed. If the counter
didn't move, the probe would still return CONFIRMED with that sentence.

The live record happens to be true: `70 → 71 → 74`, `counters_moved_on_delete: true`. Probe 1 also covers counter
movement on a delete. So nothing recorded is wrong today.

**Fix:** either drop the clause, or return DIFFERENT with a decision-9 impact when the counter didn't move.

### M2. Probe 13 judges "counters fall back" without first checking that they rose

**Where:** `v2/probes/p13_backup_restore.py:61-62,85-88`

`rose` is computed but only observed. If `AltVchId` is missing from the counters read, both sides become 0, so
`back_below` is False, and the probe reports DIFFERENT "counters didn't fall back". That is a false finding about
restore detection. The same happens if the throwaway didn't move the counter.

The live record has `counters_rose_on_throwaway: true`, so the recorded CONFIRMED stands.

**Fix:** BLOCK, or mark it inconclusive, when `not rose` or either counter is missing.

### M3. `replace_company_folder` and `backup_company` delete before they copy

**Where:** `v2/probes/operator/company_a.py:24-25,69-71`

- **`restore_company`:** `rmtree(target)` then `copytree(source, target)`. A copy that fails partway leaves company
  A's live folder half-written, and Tally is then started on it.
- **`backup_company`:** re-using a tag deletes the previous good backup before the new copy has succeeded.
  `backup_company` also leaves Tally stopped if the copy fails (deferred in B2, still true).

Company A is disposable (`reset-a` rebuilds it), so this is Minor. But the same helper is the route for restoring a
labelled backup.

**Fix:** copy to a sibling temporary folder, then swap it in with `os.replace` (or `rename`). Restart Tally in a
`finally`.

### M4. The operator's text still says it "never edits tally.ini", but since C44 it does

**Where:**
- `v2/probes/operator/tally_control.py:275` (the log line in `_backup_ini_once`)
- `v2/README.md:39-40`

Since C44, `_set_ini_load` (`:277-311`) rewrites `Load=` before every labelled start. The log line and the README
tell the person at the machine the opposite. That matters when they are working out why Tally opened a different
company after a manual start. `tally.ini.before-s0` is the original, not the current state.

**Fix:** reword both. For example: "backed up tally.ini (the operator rewrites only its `Load=` line, C44)".

### M5. `_set_ini_load` rewrites only the first `Load=` line

**Where:** `v2/probes/operator/tally_control.py:289` (`count=1`)

`tally.ini` can list several `Load=` lines, one per default company. Any after the first still load, so "only this
company opens" isn't guaranteed.

It fails safe: `wait_for_companies` raises after `WRONG_COMPANY_LIMIT` polls, naming what's open. So the cost is a
confusing stop, not wrong data.

**Fix:** remove every extra `Load=` line, or refuse with a clear message when there is more than one.

### M6. `SystemRunner.list_tally` matches any command line that contains "tally.exe"

**Where:** `v2/probes/operator/tally_control.py:72`

Deferred in B2 and still live. Any process whose command line merely contains the string is treated as a Tally, for
example `tail -f …/tally.exe.log`, or an editor that has the file open. Such a process could:
- make `start()` refuse ("already running");
- count as foreign, so `stop()` refuses without `--stop-any-tally`;
- or, with `--stop-any-tally`, be sent SIGTERM.

**Fix:** match the executable token, i.e. argv[0] or the first `*.exe` token ending in `tally.exe`, not a substring.

### M7. Probe 10's "popup not raised" path leaves a stock group behind with no cleanup note

**Where:**
- `v2/probes/p10_error_shapes.py:57-70`
- `v2/probes/setup/writes.py:737-747`

`raise_duplicate_master_popup` relies on the stock group "Electronics" already existing. If it doesn't, Tally
answers `created=1`, and a new stock group now exists on company A. `popup_note` is resolved at `:70` regardless, and
no `on_abort` note names the new group.

The tracker (2026-09-23) records this as "known, not fixed". It is still live. `reset-a` clears it.

**Fix:** when `popup_raised is False`, keep a cleanup note ("delete stock group 'Electronics' created by probe 10"),
or have `_raise_popup` read the group before sending.

### M8. The auto-operator keeps a voucher ref after a restore has removed the voucher

**Where:** `v2/probes/operator/auto.py:192-196` and `_restore_company`

Probe 13 creates `p13-v4` and then restores over it. The ref stays in `self.vouchers`, so in the same process:
- a second probe-13 run (for example `run --all --auto --rerun` reaching 13 twice, or a scripted retry) BLOCKs with
  "Voucher ref 'p13-v4' is already in use";
- any later lookup by that ref would target a Master ID that no longer exists.

**Fix:** clear `self.vouchers` in `_restore_company` and `_restore_seed`, as `reset_company_a` already does.

### M9. `run_order` marks a company "current" without switching to it

**Where:** `v2/probes/runner.py:143-146`

For a probe with `guard=False`, `current = label` is set although no switch happened. The next guarded probe for
that label then skips `_switch`.

It is caught one step later: `check_company` BLOCKs the part with a wrong-company guard error. So the result is a
spurious BLOCKED, not a write to the wrong company.

**Fix:** set `current` only when a switch actually happened, or when the probe is guarded.

### M10. The B1/B3/B5 minors that were deferred and are still in HEAD (cosmetic or inert)

- **p17's CONFIRMED `spec_impact` embeds a dict repr** of the explode variables (`p17_ledger_level_tb.py:143`). It
  reads as `{'EXPLODEFLAG': 'Yes', …}` in the spec input.
- **p18's `pending_bills` / `stock_verdict` don't skip `ISPOSTDATED`** (`p18_historical_reports.py:104,137`).
  `reads.ledger_movements` does (`reads.py:273`). This is inert for the as-on dates used, but it is a trap if
  post-dated vouchers ever sit before an as-on date.
- **`run_anchor_check` and `run_probe` record `Exception` without a traceback** (`runner.py:70,104`). A harness bug
  reads as "Harness error: KeyError: 'x'", with no location. Log `traceback.format_exc()` to the operator log.

## Deferred items that are gone or don't matter at HEAD

- **p13 empty-sample guard.** Fixed in the fix wave (`p13_backup_restore.py` BLOCKs on an empty sample or read-back).
- **p16's `_rule()` literal date, the FAILED impact's as-on note, and the M6 guard.** Fixed, then reworked by C33/C45
  in parts 4–5.
- **p10 `blind` precedence.** `A and B or C` parses as intended, `(A and B) or C`. It is readability only, so not
  listed.
- **anchor_checks Decimal→str after reload.** Representation only. The comparisons use the stored strings on both
  sides.
- **Duplicate `core` import in `test_cli`, `_own_pids` timing, and `test_isolation`'s transitive check.** These are
  test or cosmetic issues. None changes a verdict.

## Verdict

**Ready.** No Critical or Important defects remain in the part-2 code at HEAD.
- The three B2 safety Importants, the final review's three Importants and the re-review's two Importants are all
  fixed and pinned by tests.
- The ten Minors above are latent. Each needs either a changed Tally or an operator slip to bite.
- None of them changes a recorded company-A result: the observations behind probe 7's and probe 13's claims were
  checked in `results.json`.

Worth doing before any tier-C or licensed re-run of the A batch: M2, M3, M7 and M8, since those are the operator
paths a re-run exercises.
