# Pre-live code review — S0 plan part 7, Task 1 (forex write-shape candidate)

**Date:** 2026-09-25 · **Branch:** `feat/bi-s0-probe-harness` · **Range:** `95941a1..47330a5`
(`4aed355` 1.1 AMOUNT parser, `d4cda98` 1.2 writer pieces, `47330a5` 1.3 shape runner)
**Against:** `docs/plans/2026-09-25-bi-s0-probes-plan-part7.md` (Task 1, Global Constraints, Review Focus,
Deviations D1–D6), `LESSONS.md` §15.
**Scope of the question:** is `v2/probes/setup/forex_shape.run` safe to run LIVE on company B (Task 2 step 5)? It
writes a USD Currency master (kept), two `ZZ Forex Probe …` ledgers and up to four `S0-throwaway forex V*` Sales
vouchers dated 01-09-2022 (read back, then deleted).

**Offline checks run:** `uv run --project v2 pytest v2/tests -q` → **810 passed** (matches the D-block count). Four
throwaway scratch tests (not committed, file removed) confirmed findings I1, I2 and I3 against `FakeBooks` — see
"Evidence" under each.

## Verdict

**Safe to run live: yes after fixes.**

No finding lets the runner alter or delete a non-throwaway object as the code stands: `Gulf Office Supplies LLC` is
never sent, every ledger create is preceded by a books-wide ledger list (leftover guard) plus the per-name
`ledger()` check, only names the run itself created are deleted, and the company guard (`check_company(...,
mutating=True)` + `check_writable`) runs before the first request. **No Critical findings.**

But three Important findings can give a **false or misleading result** on exactly the live failure modes this run
exists to measure (I1 C36-style false `stored_forex`, I2 F2 misdiagnosed as a broken voucher shape, I3 a candidate
`CURRENCYNAME` that doesn't stick leaves a throwaway behind and no `summary.json`). Fix I1–I4 before step 5; I5 is
cheap and should go in the same commit. Minors can wait.

---

## Critical

None.

---

## Important

### I1 — `classify` trusts any forex-*looking* read-back; the values are never checked (false `stored_forex`)

**Where:** `v2/probes/setup/forex_shape.py:74-85` (`classify`), used at `:156-162`; decides `outcome` at `:196-202`.

**Failure scenario.** `classify` returns `forex_full` / `forex_no_base` as soon as `parse_forex_amount` matches the
read-back text. It never checks that the parsed currency is `$`, that `|fx| == 448.44`, that `rate == 82.99`, or that
the stated/computed base equals the INR that was sent. The grammar is deliberately wide (`sym` = any non-digit run),
so these all classify as "stored forex":
- Tally reinterprets the amount (e.g. `-$37216.04 @ ₹82.99/$ = -₹3088558.16`) — confirmed `forex_full` by scratch test;
- Tally renders a base-currency line in expression form (`-₹37216.04 @ ₹1.00/₹ = -₹37216.04`) — confirmed
  `forex_full`;
- the `plain_with_forex_field` branch (`:84`) fires on **any** non-AMOUNT leaf field containing `$` or `@`. A plain-INR
  line on the USD party that merely carries the ledger's currency symbol in some field (e.g. a hypothetical
  `<LEDGERCURRENCY>$`) is classified `plain_with_forex_field` → `_stored` → `stored_forex` — confirmed by scratch
  test. That is the C36 failure (Review Focus 1) reported as success.

`outcome == "stored_forex"` is the gate into Task 3 (it un-skips 101/102 permanently), so a false positive here writes
real vouchers with a wrong shape.

**Fix.** Pass the expected `ForexLine` + sent INR into `classify` and require, for `forex_*`:
`fa.currency == symbol`, `abs(fa.fx) == FX_AMOUNT`, `fa.rate == RATE`, sign of `fa.fx` == sign of sent INR, and
`forex_base(fa)[0] == sent` (for `forex_full`). Anything else → a new class `forex_mismatch` (never `_stored`, surfaced
in `notes`). For `plain_with_forex_field`, require a field whose text contains the face value (`448.44`) **and**
parses/contains the currency symbol, not just a `$`/`@` character. Add tests for the three texts above.

### I2 — a V0 dropped by F2 is reported as "the base voucher shape is wrong", with no F2 hint

**Where:** `forex_shape.py:166-172` (control-failed early `return finish()` inside the `try`) vs the D4 F2 note at
`:194-195` (after the `try`, never reached on that path).

**Failure scenario.** The most likely live mistake is F2 reset by a Tally restart (LESSONS §15 rule 14; the plan's own
operator gotcha). Then every voucher answers `created=1` but is absent from 01-09-2022, so V0 is `dropped`.
`v0.classification != "plain_inr"` → `outcome = "control_failed"` with the note "the base voucher shape is wrong" and
**no F2 note** (confirmed by scratch test: notes = only the shape message). Task 2 step 6's table then sends the
operator to `superpowers:systematic-debugging` on the V0 shape ("may need Sales without ISINVOICE") — debugging a
correct shape, possibly changing it.

**Fix.** On V0 (and generally), if `classification == "dropped"` set a distinct outcome, e.g. `f2_or_date_dropped`,
with the F2 text, and add that row to Task 2 step 6. At minimum, move the D4 note into the V0 branch too. Test:
V0 vanishes after create → outcome/notes name F2.

### I3 — a party-ledger create that half-succeeds leaves a throwaway in B and writes no `summary.json`

**Where:** `forex_shape.py:132-134` (`made.append(name)` only after `create_party_ledger` returns);
`writes.py:696-699` (the `CURRENCYNAME` read-back raises after the ledger was created); `forex_shape.py:178-181`
(only `WriteTimeout` is caught).

**Failure scenario.** `CURRENCYNAME` is an unmeasured candidate tag, and a ledger's currency field is normally only
available once multi-currency is on. Likely live outcome: Tally creates `ZZ Forex Probe USD Debtor` (`created=1`) but
ignores/coerces the currency (LESSONS §15 rule 3), so the read-back raises `WriteFailed("… did not stick")`. The ledger
exists but isn't in `made`, so the `finally` deletes only the INR ledger; the exception propagates past `finish()`, so
**no `summary.json`** and no outcome row; the next run refuses with "leftover", pushing the operator to a full restore.
Confirmed by scratch test (USD ledger left, INR ledger deleted, no summary). The same applies to an EXCEPTIONS=1
refusal of the ledger (no leftover then, but still no summary/outcome). The plan's state matrix has no row for
"ledger currency refused", yet it's the most plausible Educational failure after the currency create.

**Fix.** Append the name to `made` as soon as the create import returns clean (or: on any exception from
`create_party_ledger`, re-check `writer.ledger(company, name)` and add it to `made` if present). Catch `WriteFailed`
from the ledger step and finish with `outcome = "ledger_currency_refused"` (+ the error, + `ledgers_after_create.xml`
saved anyway) so the evidence is written; add the row to Task 2 step 6 (next step: UI fallback for multi-currency /
the ledger's currency, or H1 fallback S-A via V3 — which the run could still execute on the INR party). Test with a
`ledger_details` that returns `CurrencyName=""`.

### I4 — the delete uses `LASTVCHID` without cross-checking it against the voucher that was read back

**Where:** `forex_shape.py:143-163` (`result.master_id` from `create_b_voucher`; `found` is matched by narration only;
`delete_b_voucher(company, result.master_id, …)`), `writes.py:563-576`.

**Failure scenario.** This is the only path in the run that can destroy a non-throwaway object. The voucher is
*identified* by narration, but *deleted* by the `LASTVCHID` from the import response. If those ever disagree (an import
answer whose `LASTVCHID` is not this voucher's MasterID, an empty/`0` guarded elsewhere but not a stale one), the
`ACTION="Delete"` by Master ID removes a **real** company-B voucher (01-09-2022 carries real vouchers: the Sep-2022
window holds 18), and `delete_b_voucher`'s verification only proves that *that* ID is gone — it passes. `LASTVCHID` =
MasterID was verified on company A, so this is unlikely, but it's a one-line guard on an irreversible action.

**Fix.** Before deleting, require `found[0]["header"].get("MASTERID") == result.master_id` (the day read fetches
`MasterID`; stripped by `_leaf_fields`), else raise `WriteFailed("read-back MasterID ≠ LASTVCHID — not deleting")`.
Optionally also pass the narration into `delete_b_voucher` and check the listed row's narration before sending the
delete. Test: fake returns a different `last_vch_id`.

### I5 — currency list-before-create keys only on `Name`; a read-back miss is reported as "refused"

**Where:** `writes.py:533-556` (`list_currencies` keyed by `row["Name"]`; `create_currency` raises
`WriteFailed("… not found on read-back")` after `created=1`); `forex_shape.py:121-124` (any `WriteFailed` →
`currency_refused`).

**Failure scenario.** If Tally names the Currency master differently from what we sent (e.g. keys it by formal name
`USD`, or `NAME` comes back under another tag — all candidates until step 3), the create answers `created=1`, the
read-back misses it, and the run reports `currency_refused`. Step 6 then says "XML can't create the currency" and
sends the operator to create `$` in the UI (a duplicate). Worse, the **next** run of step 5 again finds no `$` by
`Name` and sends a second `ACTION="Create"` for a master that exists → LESSONS §15 rule 10 blocking modal.
`currencies_after.xml` is also not saved on this path (it's saved only after success), so the evidence to diagnose it
is missing.

**Fix.** In `create_currency`, treat the currency as present if the symbol **or** the formal name appears in any of
`Name`/`OriginalName`/`MailingName`/`ExpandedSymbol`; on a read-back miss after `created/altered == 1` raise a distinct
error (e.g. `WriteUnverified`) that the runner maps to `outcome = "currency_unverified"` ("created=1 but not listed —
do NOT re-run; inspect `currencies_after.xml`"), and always save `currencies_after` in a `finally`.

---

## Minor

- **M1 — no `summary.json` when the run completes but cleanup raises.** `forex_shape.py:182-193, 207`: `finish()` is
  called after the `finally`; with `completed=True` a ledger-delete failure re-raises from the `finally`, so a fully
  measured run loses its summary. Write the summary before re-raising (or in the `finally`).
- **M2 — the F2 pause (D6).** `forex_shape.py:38-39, 127`. From a script file in an interactive terminal it is safe:
  `input()` flushes the prompt, stdin is still the tty even with `2>&1 | tee` (stdout is the pipe). It fails
  (`EOFError`) under the heredoc as D6 found, **and** whenever the controller agent runs it through a non-tty tool
  shell. Harmless (the currency is the intended permanent write and no throwaway exists yet) but it ends without a
  summary. Check `sys.stdin.isatty()` at the top of `run` when `wait is _console_wait` and refuse before the first
  write; and update Task 2 **Step 5's code block itself** — it still shows the heredoc, D6 lives only in Deviations.
- **M3 — no runtime C43 guard on the writer path.** `writes.py:262-263`: `TallyWriter.post` runs `check_request` only,
  not `check_educational_dates`. All dates are hard-coded day 1 today (`DAY`, `DATE`, `DATE_TEXT`), so it's safe as
  written, but nothing stops an edit to e.g. `05-09-2022`. Add a test asserting every request the fake saw passes
  `check_educational_dates(req, "educational")`, or call it in `b_day_voucher_request`.
- **M4 — an unrecognised read-back is reported as `refused`.** `forex_shape.py:203-206`: a party line classified
  `other` (Tally stored something we can't parse) yields `outcome = "refused"`, which step 6 has no row for and reads
  like "Tally rejected it". Use `unrecognised` (human reads `variant_V*.xml`).
- **M5 — `dropped` vouchers are never located.** `forex_shape.py:153-155`: if a `created=1` voucher landed on another
  date (not silently discarded), it stays in B; the ledger cleanup then fails loudly (good), but the message doesn't
  say where the voucher is. A books-wide header read by MasterID would name it.
- **M6 — Sales auto-numbering side effect (LESSONS §15 rule 8, unmeasured).** Inserting and deleting throwaway Sales
  vouchers on 01-09-2022 may renumber (and possibly bump AlterIDs of) every later real Sales voucher under
  "Automatic" numbering. Nothing in the runner checks it; step 8's `setup-b` verify doesn't compare voucher numbers.
  Cheap check: save the Sep-2022 window (`month_window`) before and after the run and diff `VOUCHERNUMBER`/`ALTERID`
  of non-throwaway vouchers; a diff means restore.
- **M7 — `forex_amount_text` renders the rate with `:.2f`.** `writes.py:141-148`: `validate_b_voucher` checks
  `fx × rate` at full precision, but a 3+-decimal rate would go on the wire rounded, so the text's own `fx × rate ≠
  base`. Not reachable with 82.99/82.58; validate `rate == rate.quantize(0.01)` or render it exactly.
- **M8 — leftover-guard test covers only the USD ledger.** `test_forex_shape.py:92-96`: no case for a leftover INR
  ledger or a leftover `S0-throwaway forex` voucher on the day (both branches exist at `forex_shape.py:107-110`).

## Tests — do they mock only the network, and model messy shapes?

- **Network-only mocking: yes.** `FakeBooks` is an `httpx.MockTransport`; the runner, writer and parser are real.
  Two tests monkeypatch `writer.create_b_voucher` / `writer.delete_ledger` to inject a vanish/refusal — acceptable
  seams for failure injection, not stubs of the code under test.
- **Circularity (accepted by the plan, worth saying):** the fake's forex export (`_forex_line_text`) is built from the
  same candidate grammar the writer sends and the parser reads, so the happy path is self-confirming until Task 3
  re-pins the fake to `forex_shape_<date>/`. The knobs cover refuse / plain / F2-only / base-party / popup / sticky
  delete, which is good. Missing shapes, per the findings: values that parse but differ (I1), a currency tag that
  doesn't stick on the ledger (I3), `LASTVCHID` ≠ read-back MasterID (I4), a currency listed under another name (I5),
  V0 dropped by F2 (I2).
- **Messy real shapes:** the seeded B (`seed_company_b(..., masters=True)`) is used, so real B ledgers (including Gulf
  and `Export Sales`) and real 01-09-2022 vouchers are present in the day read — the narration match and leftover
  guard are exercised against real neighbours. There is no test asserting that Gulf / real vouchers on 01-09-2022 are
  byte-unchanged after a run; add one (snapshot `books.state["ledgers"][USD_DEBTOR]` and the day's non-throwaway
  vouchers before/after) — it's the direct test of Global Constraint "Gulf is never altered".

## Review-focus checklist (as asked)

| # | Question | Answer |
|---|---|---|
| 1 | Could a write touch a non-throwaway object? | Not by name: creates are `ZZ Forex Probe …` only, list-first twice, never ALTER, Gulf never sent. Only residual path: delete by an unchecked `LASTVCHID` (I4). Currency `$` is the one intended permanent master. |
| 2 | Deletes verified in the right window; failed delete stops loudly? | Yes — `delete_b_voucher` re-reads 01-09-2022 by MasterID (fact 3 fixed); a sticky delete raises "still there", and D3 keeps that error first. Gap: the ID itself isn't cross-checked (I4). |
| 3 | Plain INR mis-classified as forex (C36)? | Forex is taken only from the read-back (good), but the classification checks *form*, not *values*, and the field heuristic is loose (I1). |
| 4 | Popup / modal risk? | Ledger + currency creates are list-first; a timeout ends in `popup` without further writes (good). Residual: a Name-only currency list can lead a re-run into a duplicate create (I5). |
| 5 | C43 dates; F2-dropped detection? | All dates are day 1 (safe), but no runtime guard on the writer path (M3). F2 drop is detected for V1–V3 but misreported for V0 (I2). |
| 6 | `input()` F2 pause from a script file with a tty? | Safe from an interactive terminal even with `| tee`; fails without a tty (heredoc, agent shell). Refuse up front (M2). |
| 7 | Tests mock only the network, messy shapes? | Yes, network-only; missing the adversarial shapes listed above. |

---

## Fix round (2026-09-25)

The fixes were made test-first, offline only (FakeBooks), with no change to `results.json` or the fixtures.
Commits:
- `634f93b` (I5 + R-SYM writer and fake);
- `d6644f2` (I1);
- `4229c9a` (I2–I4, I5 in the runner, M1, M6, R-SYM variants, R-F2).

The suite went from **810 to 846 passed**, green normally and with `-W error`.

| Finding | Fix | Tests (`v2/tests/probes/…`) |
|---|---|---|
| I1 | `classify(line, sent, *, base_symbol, symbol, fx, rate)` returns forex only when **every value is the sent value**: currency `$`, face 448.44, rate 82.99, the face's sign = the sent INR's sign, the stated (or face × rate) base = the sent INR, and a base symbol that is the discovered one or none. Anything else is the new class `forex_mismatch` (never stored). `forex_problems` names each difference in `notes`. A mismatch on any line makes the whole variant `forex_mismatch`. The field route is strict: a non-AMOUNT field must carry both the face value and the currency symbol. New outcome `forex_mismatch` | `test_forex_shape.py::test_classify` (the review's three texts, plus rate, sign, base, wrong base symbol, loose `$`/`@` fields, face without symbol), `test_forex_problems_name_what_differs`, `test_a_mismatched_v1_is_not_stored_and_the_bare_rate_is_tried`, `test_every_variant_mismatched_is_its_own_outcome` |
| I2 | V0 `dropped` gives the outcome `f2_or_date_dropped` with the F2 text, never `control_failed`. A later variant that is dropped still adds an F2 note, and if nothing is stored the outcome is `f2_or_date_dropped` | `test_v0_dropped_by_f2_is_named_as_f2_not_a_broken_shape` |
| I3 | `create_ledger` adds the name to `made` as soon as Tally has the ledger, even when the create's own read-back then raises (it re-checks `writer.ledger`). A ledger `WriteFailed` finishes with `ledger_currency_refused` (USD) or `ledger_refused` (INR), saves `ledgers_after_create.xml`, and cleans up. `summary.json` is written on every path past the guards | `test_a_ledger_currency_that_does_not_stick_is_cleaned_up_and_reported` (FakeBooks `ledger_currency_sticks=False`) |
| I4 | Before a delete, exactly one voucher must be read back by its narration, and its `MASTERID` must equal LASTVCHID. Otherwise a `WriteFailed` ("… not deleting anything") is raised **without sending a delete**, the outcome is `aborted`, and the summary is written | `test_a_lastvchid_that_is_not_the_read_back_voucher_is_never_deleted` (a LASTVCHID naming a real 01-09-2022 voucher: no delete is sent, and the voucher survives) |
| I5 | `writes.currency_matches` treats the currency as present if its symbol or formal name appears in **any** `CURRENCY_FIELDS` value. This applies to list-before-create and to the read-back. A confirmed create that the read-back can't see raises the new `WriteUnverified` ("do NOT re-run"), and the runner gives the outcome `currency_unverified`. `currencies_after.xml` is saved on every non-modal path (refused, unverified or ok) | `test_setup_writes_forex.py::test_currency_matches_on_name_symbol_or_formal_name`, `…_listed_under_its_formal_name_counts_as_present`, `…_created_currency_that_is_not_listed_is_unverified_not_refused`; `test_forex_shape.py::test_an_unverified_currency_create_stops_with_do_not_rerun`, `test_a_refused_currency_still_saves_currencies_after` |
| M1 | `summary.json` is written before the cleanup and rewritten after it. The first error is re-raised after both writes | `test_summary_is_written_when_a_completed_run_fails_its_cleanup` |
| M6 | A header-only read (`S0FxNumbers`: MasterID, VoucherNumber, AlterID; 01-09-2022..31-03-2023, both C43-safe) runs before any write and after the cleanup (`numbers_before.xml`, `numbers_after.xml`). `summary.numbering` lists `number_changed`, `alter_id_changed`, `missing` and `added` for the real vouchers, and sets `changed`. Any change adds a "restore" note. The window runs from Sep 2022 **to FY end**, a superset of what was asked, because automatic Sales numbering renumbers every later voucher in the FY | `test_a_renumbered_voucher_is_flagged`; the happy path asserts `changed is False` |

**Controller rulings (recorded in the plan's rulings, dated 2026-09-25):**
- **R-SYM.** The base symbol is discovered from the Currency list (`base_currency`: the INR row's `Name`, which is
  `?` on live B) and is never hard-coded. `ForexLine.base_symbol` has no default. Variant order:
  - V1: `@ ?82.99/$ = -?37216.04`;
  - V1b: `@ 82.99/$ = -37216.04`, if V1 isn't stored;
  - V2: no stated base;
  - V3: the INR party with the chosen form.

  `FakeBooks`' base currency is `?` (as live) and gets a new knob, `forex_rate_symbols_refused`. Tests:
  - `test_run_stores_forex_on_both_parties_and_cleans_up` checks the `?` on the wire and that Gulf and the real
    vouchers are byte-identical afterwards;
  - `test_a_refused_base_symbol_falls_back_to_the_bare_rate`;
  - `test_unknown_base_currency_stops_before_any_write`;
  - `test_the_fakes_base_currency_is_named_like_live_b`.
- **R-F2.** `f2_confirm: Callable[[], None]` replaces `wait`. The default refuses with `WriteRefused` before any
  request unless stdin is a tty. Plan Task 2 Step 5 now shows the script-file form with `f2_confirm=lambda: None`.
  Tests: `test_the_default_f2_confirm_refuses_without_a_terminal`,
  `test_f2_confirm_is_called_once_after_the_currency_and_before_the_ledgers`.

**Also done:**
- M8 (the leftover INR ledger and leftover voucher cases): `test_other_leftovers_refuse_too`.
- D7: the runner refuses an `out_dir` that already has a `summary.json`, so a re-run can't overwrite evidence
  (`test_an_existing_evidence_folder_is_never_overwritten`).
- M4 in part: a read-back line matching no known form is now the outcome `unrecognised`, not `refused`.

**Not done (minors left open):**
- M3: no runtime C43 guard on the writer path. The dates are still hard-coded day 1 / 31.
- M5: a dropped voucher is not located.
- M7: the rate's precision.

