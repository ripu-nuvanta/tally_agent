# Code review: BI S0 plan part 6, Tasks 1–7 plus the Task 8 pre-live review (2026-09-25)

- **Scope:** `1043c91..9bd5262` on `feat/bi-s0-probe-harness`, 7 commits, `v2/` only. The diff is
  `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part6/review-1043c91..9bd5262.diff`.
- **Inputs:** task briefs 1–11, rulings S1–S11 (`progress.md`), pre-flight F1–F14 (`preflight-scan.md`), the implementer report
  (`tasks-1-7-report.md`), spec `docs/specs/2026-09-22-bi-s0-probes-design.md`, and the live facts
  (`results.json` probes 11/16/21, the `p21_B_fy2022_month_02.xml` capture, and the C46 snapshot).
- **Reviewer rules:** read-only on code. `results.json` was not touched (md5 `9cae5bfc…` before and after the runs). Nothing was
  sent to `localhost:9000`.

## Verdict

**Ready for live Tasks 9 and 10. Task 11 (probe 24) needs two small fixes plus one runbook fix first.**
Tasks 1–7 follow their briefs and every ruling (S1–S11) as written. The suite is green: **747 passed** plain and
**747 passed with `-W error`**. The CLI smoke and the isolation check pass.
There are no Critical findings. Two Important findings affect probe 24's verdict safety, and one affects the spec impact
of probe 3 B. Probe 3 B's finding needs a fix before Task 9 runs 3 B.
The runbook has one must-fix of its own: the Task 11 credential-leak loop is bash syntax, and it breaks under the Mac's
zsh.

## 1. Spec / ruling compliance

| Item | Status | Evidence |
|---|---|---|
| T1: FakeBooks and `company_b_view` (knobs, `bill_terms`, `credit_days`, `r9_candidate`, `stock_opening_at`, `seed_company_c`) | ✅ | `v2/probes/company_b_view.py:239-307`, `v2/tests/probes/fake_books.py:72-78, 211-231, 363-374, 630-664, 719-741` |
| T2: probe 3 B (header read, flagged months on probe 5's request, drift → BLOCKED, wrong flag → FAILED, unlisted → DIFFERENT) | ✅ (see I3) | `v2/probes/p03_voucher_ids_flags.py:125-216` |
| T3: probe 23 B (two sources; one source → DIFFERENT; calendar-day rule; `On Account` ignored; flagged bills recorded, not judged) | ✅ | `v2/probes/p23_gst_due_dates.py:79-197` |
| T4: probe 25 B (R9 by UI only; the read-back decides; cleanup text in the DIFFERENT summary; `mutating=True`) | ✅ | `v2/probes/p25_masters_classification.py:101-183` |
| T5: probe 11 (C46 stock scope; every half named; relabel test reads the snapshot) | ✅ | `v2/probes/p11_openings.py:112-212`; `v2/tests/probes/test_p11_openings.py:75,102-125` |
| T6: `setup-c` plus the operator label guard before `stop()` | ✅ | `v2/probes/setup/company_c.py:27-50`; `v2/probes/operator/tally_control.py:171-175, 240-244`; `v2/probes/__main__.py:182-197` |
| T7: probe 24 (manual only; no credential path; pending reads never BLOCK) | ✅ (see I1, I2) | `v2/probes/p24_secured_company.py` |
| **S1**: drift voucher dated `20240101`; stage named `vault_prompt_pending` | ✅ | `test_p03_b_part.py:97`; `p24_secured_company.py:187,195` |
| **S2**: cancelled voucher exports the live shape; 3 B measures "no ledger lines" and records the party | ✅ | `fake_books.py:72-78, 211-231`; `p03…py:174-187, 206-209`; `test_fake_books_part6.py:143`; `test_p03_b_part.py:43,57,108` |
| **S3**: an unready LOGIN / VAULT_OPEN prompt gives BLOCKED, not FAILED | ✅ for timeout and `[]`, the two shapes the fake models; ⚠ I1 | `p24…py:122-132, 182, 189`; `test_p24…py:145-157` |
| **S4**: offset per bill; "rule differs" is its own DIFFERENT impact; fake knob | ✅ | `p23…py:121-138, 180-187`; `fake_books.py:364,741`; `test_p23_b_part.py:56` |
| **S5**: one working source → DIFFERENT | ✅ in code (`p23…py:188-190`). The dated spec line is Task 12's job. | — |
| **S6**: Parent walk only → DIFFERENT; ReservedName → CONFIRMED | ✅ | `p25…py:150-159`; `test_p25_b_part.py:30,43` |
| **S7**: C's ledger and voucher written by `setup-c`; credentials never recorded | ✅ in code. The spec's Changed line is Task 12(e). | `company_c.py`; `p24…py:24-45` |
| **S8**: the test searches for the actual dummy values in fixtures, results.json, the console, and requests | ✅ | `test_p24…py:15-17, 124-142` |
| **S9**: a same-GUID rename gives DIFFERENT (checked before `ok`) | ✅ | `p24…py:142-148`; `test_p24…py:160-168` |
| **S10**: one implementer, one combined review | ✅ | this document |
| **S11**: `_ready` uses `ctx.company_names()`, not `check_company` | ✅. An unready prompt BLOCKs **when** Tally times out or lists no company. It does not BLOCK when Tally lists C (I1). | `p24…py:122-132` |
| F10: a shared `judge_halves` / `worst_verdict` | ✅ | `v2/probes/core.py:78-96`; `test_core.py` |
| Task 8 brief: `mutating=True` doesn't affect the A part | ✅ Company A's name contains "Probe" (`companies.py:4`), so `check_mutation_allowed` passes. | `safety.py:35-38` |
| Task 8 brief: p05/p21/p11 suites untouched; bill rows without dates byte-identical | ✅ | `test_fake_books_part6.py:95`; the full suite is green |

## 2. Findings

### Critical
None.

### Important

**I1. Probe 24 `_ready`: an unready prompt still gives FAILED if Tally lists company C while the prompt is up. This is S0-D7.**
`p24_secured_company.py:122-132, 149-152`.
`_ready` BLOCKs only when the company list times out or is empty. Those are the two prompt shapes the fake models:
`modal`, where `popup` makes the read time out, and `closed`, where `loaded=False` gives `[]`
(`test_p24_secured_company.py:27-48`). What the gate sees while a login or TallyVault box is open is exactly what
`pending()` is there to *measure* (`gate_shapes`). The code has already assumed the answer.
*Failure scenario:* at step 6 TallyPrime has loaded the vaulted company but is still showing the login box, so the list
answers `['Probe Vault Co']`. The person presses Enter too early. `_ready` passes. The named reads
(ledgers/vouchers/counters) return errors or nothing. `_slip` passes because the list is `[C]`. `_judge` then records
**FAILED "export doesn't work with the company open"** with `FAILED_IMPACT`, which is the "v1 can't sync secured
companies" finding that S3 exists to prevent.
*Fix (test first):* `_ready` takes the stage's measured pending shape (`login_pending` / `vault_pending`). After Enter
it re-reads `company_list` and `active_company` (captured, as `<stage>_ready_*`). If both answers equal the pending shape
(the same transport and the same body), BLOCK with PROMPT_STILL_OPEN ("indistinguishable from the prompt state").
Otherwise judge as now. Add a fake prompt mode `"listed"`: the list answers `[C]` and named reads fail while
`popup_listed` is set. Add two tests: early Enter in `"listed"` mode gives BLOCKED, and a genuine post-login failure
in `"listed"` mode still gives FAILED.

**I2. Probe 24 `_slip`: a vault that changes both the name and the GUID is BLOCKED with no way forward, and the stage data is dropped.**
`p24…py:135-139, 184, 191, 196-197`.
`_slip` BLOCKs whenever the single listed company is not `C` and its GUID differs from the baseline. Ambiguity 16
treats that as an operator slip. But TallyVault *encrypts company data*, and nothing has measured whether it changes the
listed name, the GUID, or both.
*Failure scenario:* after step 6 the list shows one company, the vaulted C, under a different or encrypted name with a
new GUID. The part is BLOCKED "open only company C and re-run". But only C *is* open, so every re-run BLOCKs the same
way. Each re-run also needs a baseline restore and a redo of steps 1–6. `security_on` and `vault_on` are observed only
after both `_slip` calls (`:196-197`), so the BLOCKED record keeps none of the evidence. Only the raw fixtures survive.
*Fix:* call `ctx.observe(stage)` right after each `export`, before `_slip`. When exactly one company is listed and the
tracker/runbook says only C was open, make the BLOCKED text name the "TallyVault renamed + re-keyed?" possibility and
point at `observations.vault_on`. Or do what Ambiguity 16 intends and treat a single listed company whose ledger and
voucher equal the baseline as DIFFERENT (re-link, Q25) rather than as a slip. Minimum before Task 11: the observe-first
change and the message.

**I3. Probe 3 B: an omission by the probe's own header read gets the extractor's impact ("S1 never ingests them"). This is a mislabel.**
`p03_voucher_ids_flags.py:200-205`, `B_NOT_LISTED_IMPACT` at `:91-93`.
`unlisted` joins two different reads: the header collection that 3 B builds for itself, and probe 5's month request,
which is the extractor's. The impact text is about the extractor only. It is plausible that a plain `Voucher` collection
leaves out optional vouchers while the month request includes them, since Tally's Day Book-like reports hide optional
vouchers by default. The fake cannot show this split, because one `_listed` knob drives both routes
(`fake_books.py:303-306, 630-633`).
*Failure scenario:* 301/302 are missing from the header read but present with their flags in July 2023's month request.
The result is DIFFERENT, "optional vouchers are not listed", with the impact "the extractor's request never returns
optional vouchers". That is false, and S1 would drop R16 handling for optional vouchers.
*Fix (test first):* split the reads into `unlisted_month` (the extractor's request, which is the only one that
decides `B_NOT_LISTED_IMPACT`) and `unlisted_header`. The header-only case becomes its own DIFFERENT, with a note that
the probe's header collection omits them and that the extractor's request returns them. Add a fake knob
`header_lists_optional=False`, or a route override in the test.

### Minor
- **M1.** `setup-c`'s guard accepts any "Probe" company when a caller passes `company=` (`company_c.py:27-32`). The CLI
  always uses C, so this is safe today. Pin it with `if company != COMPANIES["C"]: raise CompanyCLoadError`.
- **M2.** `_ready`'s read is not captured (`_post_uncaptured`), so the post-Enter shape isn't in the fixtures. I1's fix
  covers this.
- **M3.** Probe 23 B computes offsets against the dataset's bill date, not the BILLDATE of the report's own row
  (`p23…py:121-124`). Record both, so that a Tally bill date that differs from the voucher date shows up as such.
- **M4.** The FakeBooks default `stock_opening_scope="books"` contradicts the recorded live C46 (`current`)
  (`fake_books.py:363`). The snapshot relabel test covers the live bytes. Flip the default, or document it as a
  deliberate legacy default.
- **M5.** In the `current_period` branch, probe 11's stock half doesn't judge rate or value (`p11…py:160-163`). This is
  record-only; say so in the summary.
- **M6.** R9: an empty answer (Enter only) is recorded as `tally_message ""` with `answer_agrees True`
  (`p25…py:111-131`). Re-ask on empty.
- **M7.** Deferred as ruled: F9 (Agst Ref bills in the fake have no BILLCREDITPERIOD), F14 ("undecided" labelled
  DIFFERENT), and lines of 121–157 characters.
- **M8.** A full voucher export for company C could carry `ENTEREDBY`/`ALTEREDBY` after security is on. Setup-c's
  voucher predates security, so this is unlikely, but it is a path by which the *throwaway username* could land in a
  fixture. Task 11 step 4's value grep is the backstop (see L2).

### Checked and sound
- **Credential paths.** There is no `ctx.ask` in probe 24 (`io.asks == []`). `ConsoleIO.wait` discards what the person
  types (`console.py:27-28`). `pause()` records only the instruction. Every request is built from fixed templates with no
  credential tag. The S8 test uses the actual dummy values across fixtures, results.json, the console and requests.
  Typed input is echoed only by the tty, so `tee` never captures it.
- **Company C is never started or restarted by code.** `_require_number` runs before `stop()` and `start()`
  (`tally_control.py:171-175, 178, 241`). `AutoOperator._open_company` refuses C (`auto.py:178-179`). The ALL_ORDER
  `(24,"C")` switch therefore BLOCKs in auto mode, and `run_c` refuses auto as well. `setup-c` uses plain httpx and
  never builds an operator (`__main__.py:182-197, 230-231`).
- **The setup-c guard.** `check_writable` runs before any request, then the list must equal `["Probe Vault Co"]` before
  any read or write. With A or B open it refuses (`test_company_c.py:36`). It is idempotent and never re-creates a
  master (`:43`).
- **The S9 rename.** The confirmed `active_company` template has no company variable (candidate a, `$Name =
  ##SVCurrentCompany`), so the GUID is still read after a rename. The named reads fail with "Could not find Company", and
  the verdict is DIFFERENT with "named reads failed: …".
- **R9** is only `ctx.ask` plus a read. It is never sent over XML, and auto or non-interactive mode never attempts it.
  The read-back decides. The Task 9 step 4 restore (stop, move aside, copytree the backup, `diff -rq`, `restart("B")`
  rewrites Load=100000) is correct.
- **Probe 11's C46 relabel** reproduces ledgers DIFFERENT (14 as current FY), opening_bill CONFIRMED, and stock
  DIFFERENT (`current_period` 5/5) on the committed snapshot bytes (`test_p11_openings.py:102-125`).
- **Probe 3 B's S2 check** is real. `with_lines` gives DIFFERENT with `B_CANCELLED_LINES_IMPACT`, and a test with
  injected lines covers it.
- **Probe 23 B's S4 branch.** `OTHER_RULE` means every compared bill has a due date, none equals the bill date, and at
  least one differs from bill date + N. It gives DIFFERENT with the offsets per credit period, and the test uses offset −1.

## 3. Live-run readiness

| Live task | Ready? | Notes |
|---|---|---|
| **9: company B** (3 B, 11, 23 B, 25 B) | ✅ once I3 is fixed | The C44 restart (`restart("B")` → `_set_ini_load` → `/LOAD:100000`) is unchanged and guarded. Keep F13's `ps` before and after 25 B's VoucherType read. Probe 11's expected observations match the relabel test. |
| **10: create C** | ✅ with L1 | `setup-c` needs only C open. Tally's default `Cash` and `Indirect Expenses` exist. The 1-Apr-2025 voucher is ≤ any F2 (rule 14) and falls on an Educational day (C43). |
| **11: probe 24 + cleanup** | ❌ until I1, I2 and L2 are fixed | The cleanup (stop → move every C folder → `restart("B")`, which rewrites Load=100000) is correct and never starts Tally into C. |

- **L1 (runbook, Task 10/11):** add `grep -in '^[[:space:]]*load[[:space:]]*=' …/tally.ini` to Task 10 step 1 and to
  Task 11 step 1, and expect `Load=100000`. `start(None)` (used by `close_all_companies` / `ensure_running`) inherits
  whatever Load= says. If TallyPrime ever rewrote it to C's number, an unattended start would stall at C's prompt.
- **L2 (runbook, Task 11 step 4, must-fix):** `read -rs -p "$what: " V` is bash syntax. Under zsh, the macOS default
  shell, it fails with `read: -p: no coprocess` (verified). `V` stays empty, and `grep -rlF -- ""` then matches every
  file. The check can never pass, and a person may learn to ignore it. Use `bash -c '…'`, or zsh's
  `read -rs "V?$what: "`, and add `[ -n "$V" ] || { echo "empty — retype"; continue; }`.

## 4. Must-fix before live

- **Task 9:** I3 (split 3 B's header-only vs month-request omission, and put the extractor impact on the month request
  only).
- **Task 10:** L1 (grep tally.ini Load= before and after creating C; runbook only).
- **Task 11:** I1 (`_ready` compares against the measured pending shape; a `"listed"` fake mode plus 2 tests), I2
  (observe each stage before `_slip`, and a BLOCKED text that names a vault rename with a re-key), and L2 (make the leak
  grep work under zsh and guard against an empty value).

## 5. Commands run (offline)

- `uv run --project v2 pytest v2/tests -q -p no:cacheprovider` gave **747 passed**. The same with `-W error` gave
  **747 passed**.
- CLI smoke (`--results` in the session scratchpad):
  - `list` shows 3/23/25 `A+B`, 11 `B` and 24 `C`, all `not run`.
  - `run 22` prints "Probe 22 is not built yet" and gives `exit=2`.
- Isolation: `git status --porcelain | grep -v -E ' (v2/|docs/)'` shows only the known clutter. `git status v2 docs` was
  clean before this document was written.

## 6. Suites not run
- Live Tally, Tasks 9–11 (the operator runs these at the Mac).
- Tier-C timing (⏭ Q29).
- The root `tests/` suite, which doesn't collect `v2/`. The root Vitest and Playwright suites weren't run either (not
  touched).

## 7. Fix round (minors), 2026-09-25

Test first for every behaviour change (each new test was run red, then green). `v2/` only; `results.json` (md5
`90bc0d86…` before and after) and the recorded `v2/tests/fixtures/sync/*` fixtures untouched; nothing sent to Tally.

| Item | Result | Commit | What |
|---|---|---|---|
| M1 | fixed | `9788d0e` | `load_company_c` raises `CompanyCLoadError` for any `company` other than C, before any request. Test: `test_a_company_other_than_c_is_refused_even_when_named_probe`. |
| M2 | no change | — | Already done by the I1 fix (`0ec3653`): `_ready` reads go through `ctx.try_send` as `<stage>_ready_company_list` / `_active_company` (live: `p24_C_security_on_ready_company_list.xml`, …); asserted in `test_p24_secured_company.py`. |
| M3 | fixed | `0697ad7` | `due_date_check` also records `report_offsets` (due − the report row's own BILLDATE) and `bill_date_differs` (report BILLDATE ≠ dataset bill date). Record-only; verdicts unchanged. Two tests in `test_p23_b_part.py`. |
| M4 | fixed | `c81c53c` | FakeBooks `stock_opening_scope` defaults to `"current"` (live C46). The four probe 11 tests of the books-beginning shape now pass `stock_opening_scope="books"` explicitly. Test: `test_the_default_stock_opening_scope_follows_live_c46`. |
| M5 | fixed | `8593761` | Probe 11's `current_period` stock half says "rate/value recorded, not judged" in its summary. Two tests. |
| M6 | fixed | `ca5388c` | An empty R9 answer is asked once more. Two empty answers: if the read-back shows only the original ledger, R9 is "not measured (no answer typed, twice)" (no verdict, no `tally_message`, no `answer_agrees`), since nothing shows an attempt was made; if it shows a saved duplicate, the verdict is `accepted` with `tally_message None` and `answer_agrees None`. Three tests. |
| M7 | partly (docs only) | `3871e86` | F9: the Agst Ref BILLCREDITPERIOD / original-BILLDATE gap is now noted in `_export_voucher`'s docstring (as ruled: "note it, don't change it"). F14 (`undecided` → DIFFERENT) not changed: it changes a verdict rule in production code, can't occur on B (5/5 telling), and was ruled "accept for now". Long lines not changed (style only). |
| M8 | no change | — | Probe 24 has run live and company C is archived. A byte scan of every file under `v2/` finds no `ENTEREDBY`/`ALTEREDBY`, and the Task 11 value grep was clean. Redacting those tags in `Capture` would change capture semantics for every probe; revisit only if probe 24 is re-run. |

Suite: `uv run --project v2 pytest v2/tests -q` **765 passed** (756 + 9 new); with `-W error` **765 passed**.
