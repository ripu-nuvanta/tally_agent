# Code review: S0 plan part 4, company-B probes 5 and 21 (whole branch, before the first live run)

- **Date:** 2026-09-24 · **Branch:** `feat/bi-s0-probe-harness` · **Range:** `3dfcfb2..5dc0bdf` (Tasks 1–5 + fix round 1)
- **Plan:** `docs/plans/2026-09-24-bi-s0-probes-plan-part4.md` Task 6. Ledger and rulings P1–P9, R1:
  `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part4/progress.md`.
- **Specs:** `docs/specs/2026-09-22-bi-s0-probes-design.md` (Probe 5 ~L393, Probe 21 ~L518, S0-D7, §10.6);
  `docs/specs/2026-09-21-bi-part1-sync-design.md` §5 "Cloud" minimum columns (L489–495), Q22/Q23, decision 7b.
- **Method:** the `superpowers:requesting-code-review` code-reviewer checklist, done by one reviewer in one pass. I read
  the whole HEAD state of `company_b_view.py`, `p05_voucher_month_bounds.py` and `p21_full_history_reach.py`, plus
  the diff package, the runner, the context, the auto operator and the dataset generator. I also checked live facts
  against the tracker (blocks 0–0g).
- **Read-only:** no code was edited or committed, and nothing was sent to Tally (localhost:9000).

## Verdict: **READY FOR THE LIVE RUN, with fixes**

There are no Critical or Important code defects. One cheap text fix should land before the live run (M5 storage
caveats, below), because its wording is written into results.json and into the Q22/Q23 headline. The rest are
**run-protocol conditions** for Task 7, not code changes (see "Live-run protocol"). Every other minor can wait.

## Checklist results

| Check | Result |
|---|---|
| **Count rule vs spec §7** ("every date in range and the count equals the dataset's") | ✅ Stricter than the spec, which is correct. `compare_tags` (`company_b_view.py:80-106`) compares tag **sets**, not counts: every unflagged tag must come back, with nothing out of the window and nothing untagged, extra or duplicated. `expected_written` excludes `skip_reason` (C36, USD 101/102, 2022-09). Cancelled and optional vouchers count as "written", so if Tally returns them they are never `extra`. Whether they came back is recorded (`flagged_returned`/`flagged_missing`), never judged (S0-D7: probe 3 B owns the flags). I checked the dataset under the **educational** licence: FY 2022-23 has 240 dated vouchers, 2 skipped, 2 cancelled (201/202, Feb 2023), so 236 are judged and sized. June 2023 has 10 vouchers on the 1st and 10 on the 2nd, with no flagged voucher. 31-May and 1-Jul both hold vouchers, so the month window can fail at either edge, and the day window (01-06) is tested against the 2nd. |
| **Untyped evidence can never change a verdict** | ✅ By value. `untyped` feeds only `reproduced` → the `_untyped_evidence` text (`p05:81-85, 101`). Form choice reads `typed["reach_ok"]` (`p05:87`). The TB pair is observation only (`p05:99`). `test_an_untyped_answer_that_is_also_bounded_is_flagged_not_trusted` pins it. ⚠ By **exception** there is one path, a BLOCKED outcome: see m-A. |
| **Three size definitions vs Part 1 §5 minimum columns** | ✅ `column_bytes` (`p21:74-96`) matches L492–495 field for field. Voucher: 14 columns (`is_deleted` sized as "No"; `base_type` sized by `VOUCHERTYPENAME`). Ledger lines: 5 columns. Inventory lines: 5. Bill allocations: 6. Ruling **P5** is applied: `voucher_id` sits first on all three child rows, sized like the voucher GUID. Raw XML = the exact `<VOUCHER>` block bytes. The raw-JSONB stand-in is a compact generic JSON walk. The storage maths was re-checked by the task review and still stands. The caveats are incomplete (M5). |
| **S0-D7** | ✅ Probe 21 reads only `store.confirmed("voucher_month")` (`p21:252-255`). It never builds its own month request. BooksFrom comes from probe 1's confirmed counters request (`ctx.counters`), and the licence from probe 0 (`loaded_licence`). Probe 5 asserts nothing about reports: the TB pair is labelled "Evidence only: probe 18's B part settles…" (`p05:62`). `requires=(0, 1, 5)` (P4) is safe because probe 1 is recorded DIFFERENT and the runner accepts CONFIRMED or DIFFERENT (`runner.py:24`). |
| **Isolation (company_b_view the only bridge)** | ✅ holds today. I grepped every `.py` under `v2/probes` outside `setup/`: only `company_b_view.py` and `operator/{__init__,company_a,auto}.py` import `v2.probes.setup`. The test proves less than its name says (M1, deferred). `company_b_data.py` imports only the stdlib. Git isolation is clean (see below). |
| **I1 / P8b (fix round 1)** | ✅ Both are addressed, as the re-review found. Drift → `ProbeBlocked`; a missing tag or an unbounded window → FAILED. One decode path (`fetch_window`). |

## Findings

### Critical
None.

### Important
None in code. The live-run conditions below are **mandatory for Task 7**, but they belong in the runbook, not in the
code.

### Minor (new in this review)

**m-A. Evidence-only sends can turn probe 5 into BLOCKED.** `p05_voucher_month_bounds.py:81-82` (untyped month) and `:99`
(`_report_pair`, typed + untyped TB) use `ctx.send`, and the results go through `_group_rows`/`primary_group_rows`.
- **Failure scenario:** the untyped TB times out, or a company-B TB row fails `parse_decimal`. The exception becomes
  `ProbeBlocked` or "Harness error" → probe 5 is BLOCKED → nothing is confirmed → probe 21 is BLOCKED by
  `requires`. It never produces a *false* verdict, only a lost run.
- **Why it's unlikely:** C33 already showed that the untyped voucher read answers healthily (current period), and
  probes 17/18 parse this TB shape on company A.
- **Fix (can wait):** wrap the three evidence sends in `try`. Record `{"error": …}` as the observation. Add a test in
  which the untyped send fails and the outcome is still CONFIRMED.

**m-B. `fetch_window` decodes strictly.** `company_b_view.py:135`: `ctx.last_response.raw.decode("utf-8")`. Before P8b,
probe 5 used `ctx.send`'s text, which is httpx `.text` (lenient decode).
- **Failure scenario:** a non-UTF-8 byte in any month raises `UnicodeDecodeError` → "Harness error" → BLOCKED. Every
  company-B month holds the Hindi debtor `शर्मा ट्रेडर्स`.
- **Why it's low risk:** every captured fixture is ASCII (so the responses are 8-bit, not UTF-16). The live logs
  (`logs/live-checks-c38-c40-2026-09-24.log:8,12`) show the Devanagari decoding correctly through httpx.
- **Fix (can wait):** use `ctx.last_response.text` (the same bytes, the same sizes, because `xml_bytes`
  re-encodes to UTF-8 anyway).

**m-C. A "missing" tag is always blamed on the request, but books drift can cause it too.** `p21:299-302`, `p05:87-94`.
I1 separated extra, untagged and duplicate rows as drift. A tagged voucher that was **deleted or re-dated by hand**
is still read as a request failure (FAILED + `REACH_IMPACT` / `FAILED_IMPACT`). If it was re-dated within FY 2022-23,
the drift check catches it first (as `extra` in the other month). If it was re-dated outside FY 2022-23, or deleted,
it does not.
- **Mitigation (protocol, not code):** run from the clean backup, below.
- **Fix (can wait):** on any `missing`, send one books-wide typed read for those tags before blaming the request.

**m-D. Nothing checks that the period lock was undone.** `p21:233-236`.
- **Failure scenario:** after the "Unlock … press Enter" pause, company B may still be locked, because nothing reads
  it back. The later B probes could then fail inside FY 2022-23.
- **Also:** if locking needs **Security Control / users** on this edition, enabling it changes how every later
  XML read on company B authenticates.
- **Fix:** see protocol item 4. A code fix can wait.

### Deferred minors from the ledger: triage

| ID | Item | Triage | Reason |
|---|---|---|---|
| **M5** | Storage caveats (`p21:170-171`) leave out TOAST compression / JSONB binary overhead, and don't say that `voucher_id` is sized as a GUID string rather than a bigint FK. | **Must fix before live (text only)** | The caveats go into `results.json` (`storage.q23.caveats`), and the CONFIRMED `spec_impact` headline (`p21:241-247`) says "S1 decides Q22/Q23 on these". Change `"JSONB stored size ≈ text JSON (not modelled)"` to say JSONB's binary overhead and TOAST (values over ~2 kB are compressed) are both unmodelled, so `raw` is an estimate in either direction. Add `"child-row voucher_id and referenced GUIDs sized as GUID strings — an upper bound if S1 uses bigint FKs"`. Add `"upper bounds"` to the headline. Pin the new caveat strings with the existing storage test. The raw fixtures are captured, so the figures themselves can be recomputed later without Tally, which is why only the text is must-fix. |
| M1 (P8a) | The isolation test proves less than its name says. | Can wait | My grep confirms the invariant holds today. Harden it to "the set of importers outside `setup/`+`operator/` == {company_b_view.py}". |
| M3 | The locked-period DIFFERENT branch has no test. | Can wait | The branch is two lines, and I read it as correct (`p21:238, 307-309`). It only runs if the operator actually locks (see protocol 4). Add the test before any run that *does* lock. |
| M4 | CONFIRMED + `TYPED_IMPACT` still states the C33 claim when C33 was not reproduced. | Can wait | The summary already says "C33 NOT reproduced … Review before trusting". **Fix only the text** (drop the C33 clause from `spec_impact` when `reproduced` is False). Do **not** take the earlier review's alternative, "return DIFFERENT": that would let untyped evidence change the verdict, which breaks this plan's invariant. |
| M6 | `_headline(None)` can crash. | Can wait | This can't happen after P8b (one raw text for compare and sizing, and at least 236 labelled blocks whenever every month is `reach_ok`). If it ever does, the runner turns it into a BLOCKED "Harness error", not a false verdict. |
| M7 | The formula fallback probably can't help when the typed variables are ignored outright. | Can wait | Live C33 already shows typed variables work, so the formula is not expected to be sent (P6). Add a note to the `month_formula` observation later. |
| M8 | The FakeBooks `S0P05MonthFormula` branch is unused. | Can wait | It fails safe (it returns the whole period, which gives FAILED, not a false pass). |
| M9 | Lint: E402 ×9 in `test_p21_full_history_reach.py`, E741 in `seed_company_b`. My ruff run (default rules + line 120) also flagged cosmetic I001/UP037/FURB/RUF059 hits. | Can wait | Cosmetic. |
| M10 | The `day_svdates` step name is used under the formula form too. | Can wait | Spec §11.5 names it that way. Record `form` in the `day` observation later. |
| m-A…m-D | (new, above) | Can wait / protocol | See each finding. |

## Live-run protocol for Task 7 (the answers to "will these behave against the real company B?")

1. **Don't use `--auto`, `--first` or `--all`.** Run `run 5 --company B`, then `run 21 --company B`, manually, with
   TallyPrime already running and **only company B open**.
   - `--auto` calls `open_company` for guarded probes (`__main__.py:112-117`). If anything other than B alone is
     open, it restarts Tally with `/LOAD:100000`, and the `tally.ini` `Default Companies=Yes` + `Load=100003` bug
     (tracker 0a) then opens A and B, so the guard fails fast. That is safe, but the run is lost.
   - `--auto` also **skips spec step 4** (the period lock), because `_period_lock` returns "not attempted (auto
     mode)" (`p21:226-227`).
   - `--first`/`--all` walk company-A anchor steps and switch companies. That means restarts.
2. **Start from a known-clean company B.** The loader's verify is tag-based, and m-C shows that a hand-deleted or
   re-dated tagged voucher would be read as a request failure. Company B has not been touched since the clean verify
   and backup (`s0probe-backups/100000-company-B-loaded-2026-09-24`, tracker 0g). If anything was done in the UI
   since then, restore that backup first. Don't run `setup-b` as a "check": it writes when something is missing.
3. **Someone must be at the keyboard, or pass `--non-interactive`.** Probe 21 asks the lock question through
   `ctx.ask` when interactive, and that call has no timeout. With `--non-interactive`, the lock is recorded as "not
   attempted (non-interactive)" and nothing else in probes 5/21 needs a person, apart from Tally's own licence box
   if Tally is restarted.
4. **Period lock: answer `none` or press Enter unless the lock can be set WITHOUT enabling Security Control or
   users.** Enabling users/passwords on company B changes how every later B probe reads (that is probe 24's
   subject, on company C). If you do lock: unlock afterwards and check it in the UI before any later B probe (m-D).
   Add the M3 test first.
5. **Educational licence (recorded by probe 0; `company_b_loaded_at` = 2026-09-24T13:02):** `loaded_licence`
   returns "educational", and the expectations use the 1st/2nd/31st dataset (checked above). Probe 5's summary gets
   the Educational suffix (`educational_sensitive=True`, P3).
6. **Cancelled 201/202 (FY 2022-23) and optional 301/302 (Jul 2023):** they are handled whether or not Tally lists
   them in a Voucher collection. They are recorded, never judged, and left out of the size mix. The cancelled vouchers
   (ACTION=Cancel, narration kept) keep their tags, so they show up as `flagged_returned`, not as drift.
7. **Hindi party name:** it is in every month. Decoding is fine on the evidence above (m-B).

## Test counts

| Run | Result |
|---|---|
| `uv run --project v2 pytest v2/tests -q` | **588 passed** (159.6 s), exit 0 |
| `uv run --project v2 pytest v2/tests -q -W error` | **588 passed** (145.2 s), exit 0 |

588 = 581 (Tasks 1–5) + 7 (fix round 1), which matches the ledger.

## CLI smoke (plan Task 6 Step 4, no Tally)

Results path: a session scratch directory instead of `/tmp/s0-smoke-p4`.
```
$ uv run --project v2 python -m v2.probes --results <scratch>/s0-smoke-p4/results.json list | grep -E '^ ?(5|21) '
 5  voucher_month_bounds         B     B    not run
21  full_history_reach           B     B+C  not run
$ uv run --project v2 python -m v2.probes --results <scratch>/s0-smoke-p4/results.json run 11; echo "exit=$?"
Probe 11 is not built yet (S0 plan part 2 or 3).
exit=2
```
✅ as expected.

## Isolation check (ruling P7: untracked files included)

```
$ git status --porcelain | grep -v -E ' (v2/|docs/)'
?? .pgtmp/
?? .playwright-mcp/
?? .tmp_eval/
?? 01-chat-ready.png … ?? 08-both-new-written.png   (8 files)
?? backups/
?? frontend/.tmp_vitest/
?? latest-purchase-card.md
?? scripts/cleanup_mismatched_vouchers.py
?? scripts/cleanup_waterpump.py
```
Every entry was already in the session-start git snapshot, before this plan.
- Most are root clutter: pngs, `.pgtmp/` (a local Postgres data dir), `.playwright-mcp/` (June console logs),
  `.tmp_eval/`, `backups/`, `frontend/.tmp_vitest/`.
- The three that are not pngs or temp dirs are also unrelated, pre-existing write-flow artefacts:
  `latest-purchase-card.md` (19 Jun) and `scripts/cleanup_mismatched_vouchers.py` / `scripts/cleanup_waterpump.py`
  (24 Jun).

Nothing from this plan is outside `v2/` or `docs/`. `git status` shows no modified tracked files under `v2/` or
`docs/` either. The diff `3dfcfb2..5dc0bdf` touches only `v2/**` and `docs/plans/2026-09-22-bi-part1-tracker.md`.
✅ Spec §10.6 holds. This review doc is the only new file, and it is uncommitted as instructed.

## Suites NOT run

- **Live Tally.** Probes 5 and 21 against company B are Task 7. No traffic went to localhost:9000.
- **Tier-C timing** (probe 21's timing half, probes 9/20): ⏭ Q29. Wine timings are labelled "not representative".
- **The root `tests/` suite:** it doesn't collect `v2/`, and nothing outside `v2/` changed.
- Per-commit greenness of the intermediate commits (only HEAD was run).

## Declined to judge

- Whether TallyPrime 7.0 Educational has a period lock, or whether it needs Security Control. This is live-only, so
  I turned it into protocol item 4.
- Whether live Tally lists optional vouchers in a Voucher collection. It's live-only, and the design copes either way.
- Whether the `$$Date:"DD-MM-YYYY"` formula form parses live. It's not expected to be sent (P6/M7).
- The byte-faithfulness of FakeBooks exports. It's live-only by design, and the sizes come from live bytes only.
- Pre-existing harness behaviour: a manual run overwrites `environment.run_mode` in results.json
  (`__main__.py:207`). It is outside this diff.

## Fixes applied (2026-09-24)

Text-only fixes for M5 and M4, no behaviour change (commit: see `fix(bi/v2): part 4 pre-live review — storage
caveats say upper bounds (M5), M4 text`):

- **M5** — `v2/probes/p21_full_history_reach.py`: `storage_table()`'s `q23.caveats` now say JSONB binary overhead
  and TOAST compression (values over ~2 kB) are unmodelled, so `raw` is an estimate in either direction; and that
  child-row `voucher_id`/referenced GUIDs are sized as GUID strings, an upper bound if S1 uses bigint FKs. The
  `_headline()` string now calls the Q22/Q23 figures "upper bounds" and points at the caveats. Pinned by two new
  tests in `v2/tests/probes/test_p21_full_history_reach.py`
  (`test_storage_caveats_flag_unmodelled_jsonb_overhead_and_guid_sized_fks`,
  `test_headline_calls_the_storage_figures_upper_bounds`), written first (red) then made to pass.
- **M4** — `v2/probes/p05_voucher_month_bounds.py`: the CONFIRMED `spec_impact` now drops the C33
  silent-untyped-fallback claim when `reproduced` is False (new `TYPED_IMPACT_UNCONFIRMED` constant), instead of
  always asserting `TYPED_IMPACT`. The outcome itself is untouched — `run_b` still returns `Outcome.CONFIRMED`
  regardless of `reproduced`, so untyped evidence never changes the verdict. Pinned by an added assertion in
  `test_an_untyped_answer_that_is_also_bounded_is_flagged_not_trusted`
  (`v2/tests/probes/test_p05_voucher_month_bounds.py`).
