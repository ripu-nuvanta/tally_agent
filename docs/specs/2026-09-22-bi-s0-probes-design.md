# S0 — Live-Tally probes (BI Part 1, v2)

> **Design spec; Part 1 of the plan implemented 2026-09-22** (harness + probes 0, 2, 1 — tier A tested, not yet run live).
> **Plan part 4 (2026-09-24):** probes 5 and 21 built, tested and run live on company B — both CONFIRMED.
> Brainstormed and approved section by section on 2026-09-22. **Changed 2026-09-22 (final review):** probe 0 checks anchors
> before the rename and records the data folder; probe 1 uses the first Indirect Expenses ledger and reverts its change;
> ordered runs stop/skip/`--rerun`; context gains `last_response`, `check_company`, cleanup notes; §10 uses `git status`.
> **Changed 2026-09-23:** §14's open GSTIN question answered — company-level GST registration stays UI-only (the
> loader never writes it); party ledgers carry a check-digit-correct `PARTYGSTIN`. See §14.
> **Changed 2026-09-24:** §4.3's duplicate-ledger-name pause (R9) is no longer a loader rule — it is a probe
> observation, re-scoped to probe 25's B part by [`plans/2026-09-23-bi-s0-company-b-loader.md`](../plans/2026-09-23-bi-s0-company-b-loader.md);
> `setup-b` never runs it. See §4.3.
> **Changed 2026-09-24 (Ruling C36):** **probe 22 is BLOCKED.** The 2 USD export sales (tags 101/102) were being written
> as plain INR sales (no Currency master, no ledger CURRENCYNAME, no forex AMOUNT), so probe 22 would have measured no
> forex. `setup-b` now skips them (tags kept, nothing renumbers), leaves them out of the expected figures, and reports
> one note. Unblocking needs a live-probed forex write shape first (review `code-review-bi-s0-company-b-live-fixes-2026-09-24.md` #2).
> **Changed 2026-09-24 (plan part 4):** probes 5 and 21 built, reviewed and **run live — both CONFIRMED** (company B).
> (a) §6 batch 5 now runs **5 immediately before 21** (21 fetches with probe 5's confirmed request, S0-D7; `requires=(5,)`
> in addition to (0, 1)), and §5.3's `--first` includes probe 5 in that position. (b) §7 probe 5 records the untyped
> form and one Trial Balance pair (typed vs untyped as-on) as **evidence only**, never judged against the dataset; the
> **typed** form (`SVFROMDATE`/`SVTODATE TYPE="Date"`) is the one confirmed via `confirm_request("voucher_month")`.
> (c) The count rule reads: compare **tag sets**, not raw counts — flagged (cancelled/optional) vouchers are recorded
> if returned, never judged (probe 3 B owns the flags); skipped (C36) vouchers are never expected. (d) §7 probe 21
> defines its three size measures (raw XML bytes, parsed-JSON bytes as a `raw` JSONB stand-in, minimum-column bytes)
> and adds one current-FY sample month (`fy2025_month_03`, sizes only, no verdict); the period-lock step is asked only
> when interactive and not in auto mode (an action-less `ask`; Educational Tally here answered "no period lock in this
> edition"). (e) §11.5 rows 5 and 21 gain `month_svdates_untyped`, `report_tb_typed`, `report_tb_untyped` (row 5) and
> `fy2025_month_03` (row 21). (f) Probe modules read company B's dataset only through the new `company_b_view.py`
> bridge (S0-D8 isolation), never `v2.probes.setup` directly. **New finding (Ruling C43):** Educational TallyPrime
> silently ignores a date **static variable** (`SVFROMDATE`/`SVTODATE`) whose day is not 1, 2 or 31 — same rule as
> voucher dates (§4.6) — and falls back to the current period's end; §4.6's educational-sensitive list gains probe 5.
> Full detail: `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part4/progress.md`, `docs/bi-s0-probe-results-2026-09-24.md`,
> `docs/code-review-bi-s0-part4-2026-09-24.md`.
> **Changed 2026-09-24 (plan part 5, Ruling Q6):** §6 batch 5 runs **probe 14 last** in company B (after 15, 22, 23,
> 25): it deliberately sends an unescaped, malformed request that may leave Tally behind a popup, so no other B probe
> runs after it. `registry.ALL_ORDER` matches.
> **Changed 2026-09-24 (plan part 5, Ruling Q8):** §7 probe 15's "byte-exact" means the characters survive: the verdict
> is code-point equality of the **parsed** text with the dataset; the transport form (UTF-8 bytes or numeric character
> references) is recorded, not judged. The raw response bytes are kept in the fixture, so it can be re-judged.
> **Changed 2026-09-24 (plan part 5, live run — Task 10a/10b):** probes 16/17/18 A re-run **typed**; 11/14/15 built
> and run live on B; 18 B built and run live. Outcomes: 17 **CONFIRMED**, 18 (A + B) **CONFIRMED**, 14 **CONFIRMED**,
> 15 **CONFIRMED**, 16 **FAILED** (A part DIFFERENT, B part FAILED), 11 **FAILED** (stock only).
> (a) §7 probe 18 A: bills/stock as-on moved **30-09-2025 → 31-10-2025** (Ruling C43 — 30-09-2025 is an
> Educational-ignored day) and vouchers are now read for the **whole FY** (`vouchers_fy`, reproducing C33
> explicitly rather than relying on it) and filtered in Python for the as-on figures. Live: Bills + Stock as-on
> 31-10-2025 **match that date exactly (CONFIRMED)** — the 2026-09-23 "Bills/Stock ignore the as-on date" finding
> is **superseded**: it was a C43 artefact (an ignored 30-09-2025 silently answering with the period-end position),
> not a Tally behaviour. LESSONS rule 20's second half is overturned; see LESSONS.md §15.
> (b) §7 probe 16 A: a **typed** SVTODATE on a Ledger collection, **inside the current period**, IS honoured
> (`closing_follows_svtodate=true`; SVTODATE moved 19 of 22 balance-sheet ledgers to match the as-on lines). This
> **overturns** the 2026-09-23 untyped finding and LESSONS rule 17's SVTODATE half — that finding was measured
> **untyped**. Typed SVFROMDATE-on-a-master-collection was **not** re-measured live (risk > value; a wedge costs a
> Tally restart); the freeze guard stays (§4.5). §7 probe 16 B (**new finding, Ruling C45**): a typed SVTODATE
> **earlier than the current period's start** silently **clamps to the current period's first day** — 31-03-2025
> and 31-03-2023 both answered with balances as of 01-04-2025, on all 10 balance-sheet ledgers checked — **FAILED**.
> So the Ledger-collection as-on route works only **inside** the current period; for a date in a past period, the
> as-on route is the TB report (probe 18 B), not a Ledger collection.
> (c) §7 probe 18 B: TB as-on 31-03-2023 **CONFIRMED** — matches the dataset for all 5 primary groups, the
> stock-bearing group via its own `Opening Stock` row (resolution 10).
> (d) §7 probe 11: **CONFIRMED** for ledger openings and the debtor's opening bill; **FAILED for stock only** —
> **new finding, Ruling C46**: `StockItem.OpeningBalance`/`OpeningRate`/`OpeningValue` are the **current period's**
> opening, not books-start — live, all 5 items' "opening" equalled the dataset's stock **at 31-03-2025**, not
> 01-04-2022. The stock-openings verdict rule (resolution 11) predates C46 and is recorded as measured, not
> re-run to relabel; a follow-up should teach the rule about C46 (tracker "Resume here").
> Probe 14: **CONFIRMED** — the escaped request works (26 ledgers incl. the Hindi one); an `unknown_company_request`
> control and the unescaped request both fail as expected; Tally answers a cheap read afterwards (resolution 14).
> Probe 15: **CONFIRMED** — the Hindi ledger and narration (tag 7) round-trip exact (UTF-8 bytes); the compound-unit
> item reads "10 Box 0 Nos" on its voucher and "20 Box" in Stock Summary; Tally answers a cheap read after.
> (e) §4.5 gains a **C43 send-time guard**: `ProbeContext` refuses (BLOCKED, nothing sent) any request whose typed
> date static variable's day is not 1, 2 or 31 under the Educational licence — one implementation (`v2/probes/safety.py`),
> shared by `send`/`try_send`, `_post_uncaptured`, the `anchors` command, and `company_b_view.check_date_vars`.
> (f) §11.5 gains steps: probe 11 `opening_bills_report` (the Bills Receivable fallback); probe 14
> `unknown_company_request`; probe 16 B `groups`, `ledgers`, `ledgers_fy2024`, `ledgers_fy2024_svfromdate` (opt-in);
> probe 18 A `…_asof_2025-10-31` (bills/stock/TB) + `vouchers_fy`; probe 18 B `ledger_list`, `group_list`,
> `tb_asof_2023-03-31` — see the updated §11.5 table below.
> (g) Every 2026-09-23 conclusion this overturns is marked **superseded**, not deleted; its untyped evidence is kept
> byte-for-byte at [`v2/tests/fixtures/sync/c33_untyped_2026-09-23/`](../../v2/tests/fixtures/sync/c33_untyped_2026-09-23/)
> (`git mv`, 50 files, byte-identical) — see LESSONS.md §15 and the tracker's change log.
> Full detail: `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part5/progress.md`, `docs/bi-s0-probe-results-2026-09-24.md`,
> `docs/code-review-bi-s0-part5-2026-09-24.md`.
> **Changed 2026-09-25 (plan part 6):** B parts of probes 3, 23, 25 built and run live on company B; probe 11 re-run
> under the C46 rule; company C built; probe 24 built and run live on company C. Outcomes: 3 **CONFIRMED** (A+B),
> 23 **CONFIRMED** (A+B), 25 **DIFFERENT** (A DIFFERENT, B DIFFERENT with its R9 sub-verdict CONFIRMED), 11
> **DIFFERENT**, 24 **CONFIRMED**. Evidence commits `ced8171` (3 B, 11, 23 B, 25 B with R9 skipped), `a282544` (R9
> measured), `84b37c9` (company C + probe 24); results `docs/bi-s0-probe-results-2026-09-24.md` (regenerated
> 2026-09-25), `v2/probes/results/results.json`.
> (a) §7 **probe 3 B as built:** probe 21 had already seen the cancelled pair 201/202 in probe 5's month export, so B
> does not re-ask "are cancelled vouchers returned". It judges the flags on the **extractor's own request** (probe 5's
> `voucher_month`) for Feb 2023 (201/202) and Jul 2023 (301/302, the optional pair nobody had seen), and runs one
> header-only books-wide read (01-04-2022..31-03-2026) to check that the other 954 vouchers carry no flag. Verdicts: a
> returned flagged voucher without its flag → FAILED; a flagged voucher not listed → DIFFERENT (R16 has less to filter);
> a flag on a voucher the dataset did not flag → BLOCKED as drift. **Live: CONFIRMED** — 201/202 `IsCancelled=Yes`,
> 301/302 `IsOptional=Yes` on both reads; the cancelled pair exports **no ledger lines and an empty
> `PartyLedgerName`**; the other 954 carry no flag.
> (b) §7 **probe 23 B as built:** voucher credit periods from **June 2023 via probe 5's request** (the New Ref bills'
> `BILLCREDITPERIOD`), and the due-date column of **Bills Receivable as-on 31-03-2026**. The two sources answer one
> question (can Part 3's overdue split be built?), so: both work → CONFIRMED, one → DIFFERENT (the impact names the
> source), neither → FAILED. Due = bill date + credit period in calendar days; `BILLOVERDUE`, the opening bill (no
> credit period) and `On Account` rows are recorded, not judged. **Live: CONFIRMED** — 12/12 June-2023 New Ref bills
> carry their credit period ("30 Days"/"45 Days"); 202/202 Bills Receivable due dates = bill date + credit period.
> (c) §7 **probe 25 B as built:** voucher types only (group nature was settled by A's Parent walk). `Sales - GST` →
> Sales counts as resolved when reached by the Parent walk (`resolved_by` recorded). **R9 is a UI-only, action-less ask
> inside 25 B**, never XML (LESSONS §15 rule 10), offered only when interactive and not in auto mode; the read-back
> (`B_ledgers_after_duplicate_attempt`) decides, not the typed answer; "saved" → DIFFERENT + a restore of B. **Live:
> DIFFERENT** for the voucher-type half ('Sales - GST' has no base type of its own; it resolves to Sales only via the
> Parent walk). **R9 CONFIRMED (2026-09-25, `a282544`):** TallyPrime **refused** a second ledger `Delhi Metal Traders`
> under Sundry Debtors (the existing one is under National Creditors) with "Oops! Name already exists. Enter a
> different name." — raised at the **Name** field, before Under/Accept; read-back: one ledger, parent unchanged, B
> untouched (no restore). **R9 spec impact (written here by hand — the probe's combined `spec_impact` carries only the
> voucher-type half):** ledger names are unique within a company, across groups, so S1 may treat a ledger name as
> unique per company, but it still keys ledgers by GUID (renames, probe 8). The 2026-09-24 run of 25 B (R9 "skipped
> by the operator") is kept in `results.json` `history`.
> (d) §7 **probe 11 — correction of the 2026-09-24 text.** The recorded evidence shows ledger `OpeningBalance` = the
> **current-FY** opening for 14 of 25 ledgers (all 14 mismatches equal `current_fy_opening`; the other 11 read the same at both dates, so they do not
> tell), consistent with probe 16 B's `opening_scope.verdict = "fy"` (14 as FY, 0 as books). The
> 2026-09-24 "ledger openings **CONFIRMED** against books-start" is **superseded**: the stock FAILED was checked first
> and returned early, so the summary never showed the ledger half. Re-run 2026-09-25 under the C46 rule (every half
> named, `sub_verdicts`): **DIFFERENT** — ledgers DIFFERENT (current FY), opening bill `Op/2022-001` ₹62,500 on the
> ledger master CONFIRMED, stock DIFFERENT (current period, 5/5). The re-run reproduced the offline relabel of the
> 2026-09-24 snapshot (`v2/tests/fixtures/sync/c46_p11_live_2026-09-24/`), so company B had not changed.
> (e) §4.4 **company C as built** — see §4.4. Books 01-04-2025, content from `setup-c`, folder **100001**, manual
> only, and **credentials are never recorded anywhere** (overrides "throwaway passwords recorded in the results").
> (f) §7 **probe 24 as built:** five reads per stage (company list, active GUID via probe 2's request, counters via
> probe 1's, ledger list, vouchers via probe 5's, 01-04-2025..31-03-2026) at baseline, security on, vault on; plus two
> gate reads (company list + active company) while the login / TallyVault prompt is open (`*_pending_*`) and after it
> is answered (`*_ready_*`). **Live: CONFIRMED** — security on and TallyVault on both leave the export unchanged (same
> GUID, ledgers, narration). **Gate shape:** while either prompt is open Tally **answers** (transport ok) with an
> **empty** company list and no active-company rows — "as if no company were open" — so S2's gate treats it as
> "company not open" (skip quietly, retry). No timeout, no new error envelope.
> (g) §6 batch 6 is **manual only** (never `--auto`); §11.5 rows 3, 23, 24, 25 updated to the as-built step names.
> Full detail: `docs/plans/2026-09-25-bi-s0-probes-plan-part6.md`, `.superpowers/sdd/2026-09-25-bi-s0-probes-plan-part6/progress.md`,
> `docs/code-review-bi-s0-part6-2026-09-25.md`, tracker rows 3/11/23/24/25.
> **Parent:** [`2026-09-21-bi-part1-sync-design.md`](2026-09-21-bi-part1-sync-design.md) §12 (probe list), §7 (test tiers),
> §5 "Code isolation (v2)". **Status:** [`plans/2026-09-22-bi-part1-tracker.md`](../plans/2026-09-22-bi-part1-tracker.md) §3.
>
> S0 answers the questions the Part 1 design can't settle on paper: what TallyPrime actually returns, what
> changes its counters, and whether its balances can anchor parity. It builds the first `v2/` code: a probe
> harness plus the copied Tally read code that S2 later grows into the agent. **It changes no current code.**

## 1. Purpose and scope

**In S0 (tier B: Mac + TallyPrime under Wine):**
- The `v2/` scaffold S0 needs: README, `pyproject.toml`, copied Tally read code, probe harness, isolation test.
- Probes **0–8, 10–19, 21 (reach + payload size), 22–25**, each with an outcome, raw fixtures and a spec consequence.
- A data-setup script for probe company B.

**Deferred (⏭, blocked on Q29: no tier C machine yet):** probe 9, probe 20, the timing half of probe 21, and the
standard-edition cross-checks of probes 7 and 13. They run before the first installer build (S2).

**Not in S0:** any S1 cloud code, any S2 agent logic beyond the copied read code, any change to current code.

## 2. Decisions made in this spec

| # | Decision | Why |
|---|---|---|
| S0-D1 | All S0 code lives under `v2/`; nothing outside `v2/` and `docs/` changes | Part 1 §5 "Code isolation (v2)" |
| S0-D2 | **Three probe companies** (A seed copy, B multi-year + edge cases, C secured). Bharat Traders itself is never touched | The seed company's books begin 1-Apr-2025, so older years can't be added to a copy of it; probe 21 and the backfill need several FYs |
| S0-D3 | **Hybrid data:** B's data is loaded by a v2 setup script via XML import; edit-behaviour probes (1, 7, 8, 13, and the post-dated / rename / backup steps) are done **by hand in the Tally UI** when the probe pauses | UI edits are what customers make and what probes 1, 7, 8 measure; an XML-import edit may not move counters the same way |
| S0-D4 | **One runner + probe modules** (`python -m v2.probes …`), not 25 standalone scripts, not pytest | Shared counter/GUID reads, pause steps and evidence format written once; probes are open questions, not assertions |
| S0-D5 | Tier C timing deferred (Q29 answered "none yet"); payload **sizes** are still measured under Wine | Tally's XML output is the same under Wine; only latency is unrepresentative (Part 1 §7) |
| S0-D6 | Outcomes are **CONFIRMED / DIFFERENT / FAILED / BLOCKED** (plus PARTIAL while a multi-company probe has parts left) | Every probe ends with a decision the spec can act on |
| S0-D7 | Probes never guess a request another probe must confirm: the active-company and counter reads come from probes 2 and 1 | Stops later probes resting on an unproven read |
| S0-D8 | The copied **write** code lives only in `v2/probes/setup/`; `v2/agent/` must never import `v2.probes` | The agent ships with no write code at all (Part 1 decision 2, §5) |
| S0-D9 | **Automated mode** (decided 2026-09-22, supersedes the "by hand in the Tally UI" half of S0-D3): `run --auto` plays the person at Tally — edits via XML import, open/close/restore via Tally restarts; the person only clicks Tally's licence box after a restart that loads a company (§5.8) | The user wants S0 hands-off; the live run of probes 0–2 proved it works. Cost: UI-edit parity (S0-D3) becomes a later manual check, Tally's own backup/restore UI isn't exercised |

## 3. What S0 adds under `v2/`

```
v2/
  README.md              isolation rules (Part 1 §5) + how to run probes and harness tests
  pyproject.toml         v2's own deps for S0: httpx, pytest, pytest-asyncio
  agent/
    tally/               COPIED read code — S2 builds on it
      client.py          from backend/tally_bridge/client.py
      envelopes.py       from backend/tally_bridge/request_builder.py (envelope wrappers + build_company_list)
      xml_utils.py       from backend/tally_bridge/response_parser.py (sanitize_xml, detect_error)
      amounts.py         NEW: Decimal amount parser (missing ≠ zero)
      reports.py         from response_parser.py (TB, bills, stock summary, ledger list parsers) — Decimal
      exceptions.py      from backend/tally_bridge/exceptions.py
  probes/
    __main__.py          runner CLI (§5.3)
    core.py              Probe, ProbeContext, Outcome
    capture.py           fixture + sidecar writer (§5.6)
    results.py           results.json + results-doc generator (§5.7)
    safety.py            company guard + request guards (§5.5)
    anchors.py           "company A is intact" check (§4.2)
    p00_environment.py … p25_masters_classification.py
    setup/
      import_xml.py      COPIED write envelope (_wrap_import, _esc) from backend/tally_bridge/import_builder.py
      company_b_data.py  deterministic dataset for company B + its expected figures
      company_b.py       idempotent loader (§4.3)
    results/
      results.json       committed
      logs/              run transcripts (local only — root .gitignore drops *.log)
  tests/
    fixtures/sync/       S0 captures (committed; input for S1/S2 unit tests)
    fixtures/harness/    canned responses for harness tests
    test_isolation.py
    probes/              harness tests (§11)
```

- `v2` is a package run from the repo root: `PYTHONPATH=. uv run --project v2 python -m v2.probes …`.
  Harness tests: `PYTHONPATH=. uv run --project v2 pytest v2/tests -q`. The root `pytest` only collects
  `tests/` (`testpaths` in the root `pyproject.toml`), so v2 tests never mix into current runs.
- Every copied file starts with a comment: source path + the commit it was copied from.

### 3.1 What the copies change

| Copy | Change from the source | Why |
|---|---|---|
| `client.py` | `mock_mode` and the `mock_handler` import removed. Per-request timeout argument (default 30 s, max 90 s). `post_xml` returns text **plus** elapsed ms and response bytes. `health_check` uses the copied `build_company_list` | No mock or write code in `v2/agent/`; probes record timing and size |
| `envelopes.py` | The company name is **always** XML-escaped in every wrapper (the current `_wrap_voucher_collection`, `_wrap_report_envelope`, `build_ledger_vouchers` don't — Part 1 R13). Every wrapper takes a company argument. Only the wrappers + `build_company_list` are copied; no `build_*` catalogue | Part 1 §13 gaps must not cross over |
| `amounts.py` (new) | `parse_decimal(text) -> Decimal \| None` (deliberately not named `parse_amount`): plain numbers → `Decimal`; empty / missing → `None`; anything else (e.g. a forex expression) raises `AmountParseError` carrying the raw text | The current `parse_amount` returns `0.0` on failure (Part 1 §13) — a false zero is a false parity match |
| `reports.py` | `parse_trial_balance`, `parse_bills`, `parse_stock_summary`, `parse_ledger_list` copied with Decimal amounts via `amounts.py` | Probes 12, 16, 18 compare at paise resolution |
| `xml_utils.py` | `sanitize_xml`, `detect_error`, `_get_text` (as `get_text`) copied as-is. `parse_company_list` copied **with a fix**: only `COMPANY` elements with a `NAME` child or attribute count | The current one returns `['0', …]` on a live response (§4.5) |
| `exceptions.py` | Copied, plus `TallyTimeoutError(TallyConnectionError)` so a timeout is told apart from a refusal | Harness records `timeout` vs `refused` (§5.6) |

The float `parse_amount`, `writer.py`, `import_builder.py` (except the two helpers in `probes/setup/`) and
`mock_handler.py` are never copied into `v2/agent/`.

## 4. Probe environment

### 4.1 Tally on the Mac
- TallyPrime 7 Edit Log under Wine, XML server "Both" on port 9000 (`README.md` "Installing TallyPrime on macOS").
- **One company open at a time** (Part 1 decision 4). Pause steps say which company to open and which to close.
- Each probe company lives in its **own Tally data folder** under Wine, so Bharat Traders' folder is never touched.
- Before loading any vouchers, F2 (working date) is set to a date on or after the latest voucher date (LESSONS §15 rule 14).

### 4.2 Company A — "Bharat Traders Probe Copy"
- **Made by probe 0:** restore `seed_data/TDBK1800_100003.001` into a separate data folder, open it, rename it to
  "Bharat Traders Probe Copy" (the GUID is read before and after the rename).
- **Why:** known figures. Bills Receivable ₹9,70,537 and Bills Payable ₹18,34,142 as on 31-03-2026
  (`docs/seed-data-setup.md`); 50 vouchers, 35 ledgers, 15 stock items, custom creditor sub-groups.
  Note: `tests/fixtures/trial_balance_live.xml` and the other `*_live.xml` fixtures are **not** from the seed
  company (they come from the NUVANTA company, e.g. party "HCODE TECHNOLOGIES"), so they are never used as
  company A's figures. Company A's TB baseline is **captured by probe 0** right after the restore.
- **Used by:** probes 0–4, 6–8, 10, 12, 13, 16–19, 23, 25 (A parts).
- **Kept intact:** probes that change A create **throwaway** vouchers (narration starts `S0-throwaway`) and delete
  them, or rename and rename back. `anchors.py` re-checks both bills totals (against the doc) and the TB group rows
  (against probe 0's baseline) **before** the parity probes (16–19) and **after** the A batch. If they don't match,
  the runner stops and asks for A to be re-restored from the seed backup.

### 4.3 Company B — "Sharma & Sons' Probe Traders"
- **Created by you in the UI:** that exact name (the `&` and `'` serve probe 14), books beginning **01-04-2022**,
  Maharashtra, GST enabled like the seed company. Then F2 set to 31-03-2026 or later, and one custom voucher type
  **"Sales - GST"** under Sales created in the UI (voucher-type config via XML is unreliable, LESSONS §11 / §15 rule 4).
- **Loaded by `python -m v2.probes setup-b`** from `company_b_data.py`, which generates the data deterministically
  from a fixed seed and also exports the **expected** figures (per-ledger balance at every month-end and FY
  opening, per-month voucher counts). That gives probes 16 and 18 an expected value that doesn't come from Tally.

| Area | Content |
|---|---|
| Groups | Custom sub-groups "National Creditors" and "Local Creditors" under Sundry Creditors |
| Ledgers | 6 debtors (one Hindi name "शर्मा ट्रेडर्स", one USD export customer, one **not** bill-wise), 4 creditors under the custom sub-groups, 1 bank, cash, sales, purchase, 3 expense ledgers, CGST / SGST / IGST input and output, capital |
| Openings (probe 11) | Opening balances on capital, bank and 2 debtors; one debtor with an opening **bill**; opening stock on 2 items |
| Stock (probe 15) | Units "Nos" and compound unit "Box of 10 Nos"; 5 items, one using the compound unit |
| Vouchers | FY 2022-23 → 2025-26, about 20 per month (~960): sales (some with inventory lines, some on "Sales - GST"), purchases, receipts and payments with bill allocations (New Ref / Agst Ref), credit periods on some bills (probe 23), Hindi narrations, 2 USD export sales (probe 22), 2 cancelled and 2 optional vouchers (probe 3) |
| Tag | Every voucher's narration starts `[S0-B:<n>]`, so re-runs can find what already exists |

**Loader rules** (LESSONS §15):
- Lists existing masters first and creates **only missing ones** (rule 10: a duplicate create freezes Tally).
  Vouchers already present (by tag) are skipped. A second run sends no creates.
- Reads back every write (rules 2, 3). Goods go through the stock grid, services through ledger lines (rule 15).
  Parties are bill-wise except the one deliberate exception (rule 16).
- A flag that doesn't stick on import (e.g. cancelled, optional) turns into a **pause step**: the loader names the
  voucher and asks you to set it in the UI, then reads it back.
- Ends by checking per-FY voucher counts and closing balances against the expected figures.
- ~~**Duplicate ledger names (R9):** never attempted via XML (rule 10). A pause step asks you to try creating a
  ledger with an existing name under another parent in the UI and record what Tally says.~~ **Moved 2026-09-24:**
  not a loader rule — this UI pause belongs to probe 25's B part, and `setup-b` does not run it (still never
  attempted via XML, rule 10).

### 4.4 Company C — "Probe Vault Co"
~~Created by you in the UI with one ledger and one voucher. Probe 24 turns on security (username + password), then
TallyVault, with throwaway passwords recorded in the results (the company holds no real data).~~
**Superseded 2026-09-25 (plan part 6) — as built:**
- **Shell created in the TallyPrime UI** (K: Company → Create): name `Probe Vault Co`, financial year and books
  beginning **01-04-2025**, State Maharashtra, no security at creation. The Company Features screen defaulted GST and
  inventory to **Yes** and was accepted unchanged (the plan's "(no GST)" note was a guess). Tally gave it folder
  **100001** — the lowest free number (B has 100000, A 100003), observed, not assumed.
- **Content loaded by `python -m v2.probes setup-c`** (`v2/probes/setup/company_c.py`, expected content in
  `v2/probes/companies.py` `COMPANY_C_*`): one ledger `S0 Vault Expense` under Indirect Expenses and one ₹100 Payment
  dated 01-04-2025, narration `[S0-C:1] Probe Vault voucher`. Idempotent live: run 1 `Created: ledger, voucher`, run 2
  `Created: nothing; already there: ledger, voucher` (`logs/setup-c-live-2026-09-25.log`).
- **Manual only.** C is **not** in `OperatorConfig.company_numbers`; the operator never starts Tally on it (a start
  with `Load=<C>` would stop at a login/vault prompt no licence click clears); tally.ini stays `Load=100000`.
- **Unsecured baseline backup:** `s0probe-backups/100001-company-C-baseline-2026-09-25`. After probe 24 the secured +
  vaulted folder was archived to `s0probe-backups/100001-company-C-secured-vaulted-2026-09-25` (out of git, deletable).
- **Credentials are never recorded anywhere** — not in `results.json`, fixtures, sidecars, logs, docs or commits.
  The harness never asks for or sends one; the person types them into TallyPrime only. A leak grep over
  `v2 docs logs LESSONS.md` ran before the evidence commit and was clean.

### 4.5 Safety rules
- **Company guard.** Before any request, the probe checks that exactly **one** company is loaded and it is the one
  the probe expects (by name). The guard always uses the copied `build_company_list`, because only a list shows
  how many companies are loaded. Probe 2's cheap active-company read is for the S2 agent's per-cycle gate, not
  for this guard. The v2 `parse_company_list` skips the `<COMPANY>0</COMPANY>` counters inside `CMPINFO`;
  the current parser counts them as a company named "0" (seen on `tests/fixtures/company_list_live.xml`).
- **Mutation guard.** Setup, and any probe step that asks for a change, also requires "Probe" in the company name.
- **Request guards.** `ctx.send` refuses, without sending, any request with `*` as a `NATIVEMETHOD` / `FETCH`
  value (LESSONS §5) or containing `$$InDateRange` (LESSONS §3).
- **One request at a time, no automatic retries.** A timeout stops the probe as BLOCKED with the hint "check Tally
  for an open popup or modal" (LESSONS §15 rule 10).
- **C43 date guard (added plan part 5, 2026-09-24).** Before sending, `ProbeContext` refuses — BLOCKED, nothing
  sent — any request whose typed date static variable's day is not 1, 2 or 31, when the licence is Educational
  (LESSONS §15 rule 22). One implementation (`v2/probes/safety.py`), one exception type (`GuardError`), one date
  parser (`reads.tally_date`); shared by `send`/`try_send`, `_post_uncaptured`, the read-only `anchors` command,
  and `company_b_view.check_date_vars` (so the company-B setup dataset's own date reads can't silently clamp
  either). A placeholder like `__FROM__` (not yet a real date) passes through untouched.

### 4.6 Licence mode
Probe 0 records licensed vs Educational. In Educational mode, setup-b uses only the voucher dates Educational
allows, and results of probes 1, 7, 16, 18 and **5** are tagged "Educational" (Part 1 R26). A result that looks odd
under Wine or Educational is flagged "confirm on tier C" rather than designed around (Part 1 §7).
**Changed 2026-09-24 (Ruling P3 / C43):** probe 5 added to this list. Educational TallyPrime silently ignores a
**date static variable** (`SVFROMDATE`/`SVTODATE`) whose day is not 1, 2 or 31 — the same rule already known for
voucher dates — and falls back to the current period's end instead of erroring; see §7 probe 5 and LESSONS.md.

## 5. Harness

### 5.1 Probe module contract
```python
PROBE = Probe(
    id=16,
    name="ledger_closing_balance",
    question="Does LEDGER.ClosingBalance equal Tally's TB? …",
    feeds=["decision 11", "R30", "Part 2 Rule 1"],
    parts={"A": run_a, "B": run_b},     # one entry per company label
    requires=[2, 1],                    # probes whose confirmed requests this one uses
)
async def run_a(ctx: ProbeContext) -> PartResult: ...
```
A `PartResult` carries an outcome, a one-line summary, observations and a `spec_impact` sentence. The probe's
outcome is combined from its parts with this precedence, first match wins:
**PARTIAL** (any part not yet run) → **BLOCKED** (any part blocked) → **FAILED** → **DIFFERENT** → **CONFIRMED**.
Probes with two independent questions in one part (18: TB vs bills/stock; 23: GST fields vs due dates) record
both sub-verdicts in observations, and the part outcome is the worse of the two.

### 5.2 Context API (`ctx`)
| Call | Does |
|---|---|
| `send(step, xml, timeout=30)` | Guards (§4.5) → POST → saves the raw response + sidecar (§5.6) → returns sanitized text |
| `counters()` | Reads GUID / AltVchId / AltMstId etc. with the request **probe 1 confirmed**; refuses if it isn't confirmed yet |
| `company_names()` | Names of the loaded companies via the copied company list (used by the guard; not captured as a fixture) |
| `pause(instruction)` | Prints a numbered instruction, waits for Enter, logs it with a timestamp. Non-interactive → part BLOCKED |
| `ask(prompt)` | Pause that also records typed input (e.g. a balance read from the Tally UI, the Tally version) |
| `observe(key, value)` | Records a finding into the part's observations |
| `confirm_request(name, xml_template)` | Stores a working request in `results.json` for other probes (probes 1, 2, 5) |
| `try_send(step, xml)` | Like `send`, but returns `(text, error)` instead of blocking — for probes that expect a failure (10, 14, 2's no-company step) |
| `last_response` | The last `TallyResponse` (raw bytes, elapsed ms) — for byte/timing measurements (probes 2, 17, 21) |
| `check_company()` | Re-runs the company guard; call it after any pause that closes/reopens/restores a company |
| `on_abort(note)` / `resolve_abort(note)` | Cleanup notes for UI changes in flight; if the part ends BLOCKED or crashes, the runner prints them as "CLEANUP NEEDED in Tally" and stores them |

A part that raises anything unexpected is **recorded as BLOCKED** ("Harness error: …") with its fixtures and manual
steps kept; Ctrl-C records the part, then stops the run. A step name may be used only once per part.

### 5.3 Runner CLI
| Command | Does |
|---|---|
| `list` | Every probe: id, name, companies, tier, last outcome (deferred ones shown ⏭) |
| `run <id> [--company A\|B\|C]` | Runs that probe's parts (or one part). Between parts it pauses for the company switch |
| `run --first [--rerun]` | 0 → 2 → 1 → 16, 17, 18 (A parts); B parts of 16 / 18, then **5, then 21**, once B is set up (Changed 2026-09-24: 21 requires 5's confirmed request, S0-D7) |
| `run --all [--rerun]` | All tier-B probes, batched by company in the §6 order |
| `setup-b` | Loads company B (§4.3) |
| `report` | Regenerates `docs/bi-s0-probe-results-<date>.md` from `results.json` |

Common flags: `--host` / `--port` (default `localhost:9000`), `--non-interactive`.

**Ordered runs (`--first`, `--all`)** skip a part that is already CONFIRMED, DIFFERENT or FAILED (unless `--rerun`; FAILED added 2026-09-22 so a known failure doesn't block the rest of the order), and
**stop at the first part that ends otherwise** (BLOCKED, FAILED): after a timeout or an anchors failure nothing more is
sent to a Tally that may be stuck. Probes 1 and 2 require probe 0. A single `run <id>` always runs.

### 5.4 Outcomes
| Outcome | Meaning | Required with it |
|---|---|---|
| CONFIRMED | The Part 1 assumption holds | Proof: fixtures + observations |
| DIFFERENT | It works, but not the way Part 1 assumed | The spec change needed, as `spec_impact` |
| FAILED | Not possible | Which Part 1 fallback applies, as `spec_impact` |
| BLOCKED | Couldn't run | The reason (timeout, Tally unreachable, guard, non-interactive, missing prerequisite) |
| PARTIAL | Some company parts not run yet | Which parts remain (stored as `remaining`; `list` and the report show `PARTIAL (remaining: B)`) |

### 5.5 Guards
See §4.5. Guards run **before** a request is sent; a guard failure makes the part BLOCKED and sends nothing.

### 5.6 Capture format
- Raw response saved **exactly as received** (bytes, UTF-8), never sanitized, to
  `v2/tests/fixtures/sync/p{NN}_{company}_{step}.xml`, e.g. `p16_A_ledgers_asof_2025-10-31.xml`.
- Sidecar `…xml.json`:

```json
{
  "probe": 16, "part": "A", "step": "ledgers_asof_2025-10-31",
  "company_name": "Bharat Traders Probe Copy", "company_guid": "…",
  "sent_at": "2026-09-23T10:12:03+05:30", "elapsed_ms": 412, "response_bytes": 18234,
  "timing_note": "Wine — not representative",
  "request_xml": "<ENVELOPE>…</ENVELOPE>",
  "environment": {"tally_version": "…", "edition": "Edit Log", "licence": "licensed", "wine": "…"}
}
```

- A transport failure (refused, timeout) writes the sidecar only, with `"error": {"kind": "timeout", "message": …}`.

### 5.7 Results
`v2/probes/results/results.json` (committed):

```json
{
  "environment": {"tally_version": "…", "edition": "…", "licence": "…", "wine": "…", "recorded_by_probe": 0},
  "confirmed_requests": {
    "active_company":   {"probe": 2, "xml_template": "…"},
    "company_counters": {"probe": 1, "xml_template": "…", "fields": ["GUID", "AltVchId", "AltMstId", "…"]},
    "voucher_month":    {"probe": 5, "xml_template": "…"}
  },
  "probes": {
    "16": {
      "outcome": "PARTIAL",
      "parts": {"A": {"outcome": "CONFIRMED", "ran_at": "…", "summary": "…", "observations": {}, "fixtures": ["…"],
                      "manual_steps": [{"n": 1, "instruction": "…", "done_at": "…", "input": "…"}],
                      "spec_impact": "…"}},
      "history": []
    }
  }
}
```

- Re-running a part replaces it and moves the old one into `history`.
- `report` writes the readable doc in the style of `docs/group-b-task0-probe-results-2026-06-08.md`: environment,
  then one table row per probe (outcome, what it tested, finding, design impact), then deferred probes. The doc is
  **generated only**. Design consequences are written into the Part 1 spec, and the tracker row is updated by hand
  with its proof (tracker rules).

### 5.8 Automated operator (`run --auto`, S0-D9)
Implemented in `v2/probes/operator/` (write helpers stay in `v2/probes/setup/`, S0-D8). It implements the `ProbeIO`
interface: each `pause` is performed, each `ask` is answered, and every action is logged.

- **Tally control.** TallyPrime is stopped and started under Wine with `/DATA:<s0probe folder>` and, when a company is
  wanted, `/LOAD:<company number>` (tally.ini `Load=` is ignored by this build). After every start Tally shows a
  **licence box** (Educational mode, gateway unreachable): a start that loads a company waits — up to 15 minutes —
  for the person to click "T: Continue In Educational Mode" and prints `CLICK NEEDED`. A start with no company needs no
  click. Company loading can block the XML server for over 30 s; the operator keeps waiting through timeouts.
- **Company A lifecycle.** `reset-a`: with Tally stopped, copy the pristine `seed_data/100003` into `s0probe/100003`,
  start with `/LOAD`, rename to "Bharat Traders Probe Copy" via XML (`<COMPANY NAME="…" ACTION="Alter"><NAME>…</NAME>`,
  verified live 2026-09-22). This also undoes anything a probe could not revert.
- **XML writes** use only verified shapes (`docs/tally-write-exploration-v4.md`), the live-verified company rename, and
  header-field voucher alters by Master ID. An **empty-value alter is silently ignored** (live 2026-09-22), so there are
  no "clear a field" steps: reverts delete throwaway objects, or use `reset-a`.
- **Safety.** Writes only to companies with "Probe" in the name (the one exception is renaming the fresh seed copy
  inside `s0probe`); Tally's data path is always `s0probe`; tally.ini is backed up once (`tally.ini.before-s0`).
- **Limits (recorded in results as `run_mode`).** UI-edit parity for probes 1, 7, 8 is a later manual check.
  A popup is simulated with a deliberate duplicate-master create on the probe copy (LESSONS §15 rule 10 — it raises a
  blocking modal), then cleared by a restart. Probe 13 restores at file level (a copy of the company folder taken
  before the change) — Tally's own Backup/Restore screens are not exercised; probe 13 keeps its normal outcome and
  records this limit in its observations and summary (PARTIAL stays reserved for company parts not yet run).
- **Probe 1 revision.** Master steps run on the throwaway ledger (create → alter → alter again → delete), so company A
  is left exactly as it was; probe 1 is re-run with `--rerun`.

## 6. Run order

| Batch | Company | Probes | Notes |
|---|---|---|---|
| 1 | A | **0** → **2** → **1** | Environment; then the active-company and counter reads everything else uses |
| 2 | A | anchors check → **16, 17, 18, 19** (A parts) | Parity-critical first (Part 1 §16) |
| 3 | A | 3, 4, 6, 12, 23, 25 (A parts) | Non-mutating reads |
| 4 | A | 7, 8, 10, then **13 last** → anchors check | Mutating; 13 restores A, so it goes last. In auto mode probe 10 runs popup → no company → quit, then reopens A so 13 can run (ruling 2026-09-22) |
| — | B | `setup-b` | Loader + its pause steps |
| 5 | B | 16, 18 (B parts), **5, then 21**, 3, 11, 15, 22 (BLOCKED — C36), 23, 25 (B parts), then **14 last** | Changed 2026-09-24: 5 runs immediately before 21 — 21 fetches with 5's confirmed `voucher_month` request (S0-D7); "21 first" is read as "first after the request it depends on". Changed 2026-09-24 (plan part 5, Ruling Q6): 14 runs last — its deliberately malformed request may upset Tally |
| 6 | C | 24 | Security, then Vault. Changed 2026-09-25 (plan part 6): **manual only** — never `--auto` (every step is a person at the TallyPrime UI); `--all --auto` reaching 24 BLOCKs cleanly |

## 7. Probe methods

Field names marked *candidate* are guesses the probe tests; the probe records which ones come back. Every step
saves its fixture per §5.6.

### Foundations

**Probe 0 — Environment** · A · feeds all
1. Run `wine --version`; POST a company-list request to `:9000` → answers.
2. Pause: restore the seed backup into a separate data folder and open it. Company list shows exactly
   "Bharat Traders Private Limited". Read its GUID.
3. Anchors (read-only, **before** anything is changed): Bills Receivable ₹9,70,537 and Payable ₹18,34,142 as on
   31-03-2026, and capture the TB baseline.
4. Ask: the Tally data-folder path shown for this company (recorded; it must not be Bharat Traders' usual folder).
5. Pause: rename it to "Bharat Traders Probe Copy" (Company menu, Alt+K → Alter). Read the GUID again → record whether a
   rename changes it.
6. Ask: Tally version (Help → About), edition (`Edit Log` / `standard`), licence (`licensed` / `educational`) —
   re-asked until the answer is one of those.
- **CONFIRMED** if all pass. **FAILED** only if Tally refuses the connection on port 9000 → S0 is blocked on Q29
  (a timeout or HTTP error at the first request is BLOCKED with the popup hint).
  A wrong company open after the restore, or figures that don't match the anchors, is **BLOCKED** (redo the
  restore): the harness can't tell an operator slip from Wine being unable to restore. If the restore itself
  can't be done under Wine, the operator records that in the tracker and S0 is blocked on Q29.

**Probe 2 — Cheap active-company GUID read** · A · feeds decision 4, R2
1. Send each candidate:
   - (a) a Company collection with FETCH Name, GUID filtered to `##SVCurrentCompany`
   - (b) `TYPE=Object SUBTYPE=Company` for the current company
   - (c) the full company list with GUID, as the heavy baseline
2. Record for each: correct?, bytes. The cheapest correct one → `confirm_request("active_company")`.
3. Pause: close all companies → send each candidate → record the response shape. Pause: reopen A.
- **CONFIRMED** if a cheap read works and "no company open" is distinguishable from "our company".
  **DIFFERENT** if only (c) works → the gate uses the company list every cycle (heavier).

**Probe 1 — Company counters** · A · feeds decision 9, R6
1. Company collection with *candidate* fields GUID, AltVchId, AltMstId, BooksFrom, LastVoucherDate, AlterID.
   Record which come back non-empty → `confirm_request("company_counters")`.
2. Pick the test ledger: "Bank Charges" if it exists, else the first Indirect Expenses ledger (the seed company has no
   "Bank Charges", so on company A this is "Rent"), else ask. Baseline read, plus that ledger's AlterID.
3. Pause steps (each names the company), with a counter read after each:
   1. Create a ₹1 Payment Cash → <ledger>, narration "S0-throwaway 1".
   2. Alter its amount.
   3. Delete it.
   4. Alter ledger <ledger> (set a mailing name).
   5. Clear that mailing name again (leaves company A as it was).
   6. Create ledger "S0 Probe Ledger".
   7. Delete it.
4. Record the matrix action × {AltVchId, AltMstId, LastVoucherDate} moved?, and whether the voucher entry moved the
   ledger's AlterID. Result tagged "Educational" when the licence is educational (§4.6).
- **CONFIRMED** if AltVchId moves on every voucher action, AltMstId on every master action, and a voucher entry does
  **not** move the ledger's AlterID (Part 1 "Why the re-read"). **DIFFERENT** otherwise → the matrix goes into
  Part 1 §4 and decision 9 gains the rolling re-pull fallback (R6).

**Probe 3 — Voucher IDs and flags** · A + B · feeds R6, R16
- A: all 50 vouchers with explicit *candidate* fields GUID, MasterID, AlterID, Date, VoucherTypeName, VoucherNumber,
  Reference, PartyLedgerName, Narration, IsCancelled, IsOptional, IsPostDated. IDs non-empty and unique; Reference
  equals the invoice numbers on Sales / Purchase.
- B: the 2 cancelled and 2 optional vouchers carry their flags; all others don't. (IsPostDated is checked on
  probe 16's post-dated voucher.)
- **FAILED** for a missing flag → R16 filtering is redesigned before S1.
- **Changed 2026-09-25 (plan part 6) — B as built and run live: CONFIRMED.** Flags judged on probe 5's
  `voucher_month` request for Feb 2023 (201/202) and Jul 2023 (301/302), plus a header-only books-wide read for "no
  other voucher is flagged" (probe 21 had already seen 201/202; that evidence is re-judged offline, not re-asked).
  Flagged-but-unlisted → DIFFERENT; flag on an unflagged voucher → BLOCKED (drift). Live: both pairs carry their
  flags on both reads; the cancelled pair exports no ledger lines and an empty `PartyLedgerName`; the other 954 carry
  no flag. Impact (R16): the extractor's month request returns cancelled and optional vouchers **with** their flags; S1
  ingests them and keeps both out of balances by `IsCancelled`/`IsOptional`, as Tally does (C42). Fixtures
  `p03_B_vouchers_flags.xml`, `p03_B_flagged_month_2023_02.xml`, `p03_B_flagged_month_2023_07.xml`.

**Probe 4 — `$AlterID > N` filter** · A · feeds decision 9, R6
- For Voucher, Ledger, Group, StockItem: full fetch → max AlterID M. Filter `$AlterID > M-5` → exactly the 5
  highest (compared by GUID); `> M` → empty; `> 0` → all. Tally still answers a cheap read afterwards.
- **FAILED** if wrong or Tally hangs → rolling re-pull fallback (R6).

**Probe 5 — Month bounds on a Voucher collection** · B · feeds the extractor
1. SVFROMDATE / SVTODATE, **typed** (`TYPE="Date"`) = 01-06-2023 … 30-06-2023 → every unflagged tag comes back, in
   window, and nothing untagged/extra/duplicated (count rule = compare tag sets, not a raw count — Changed
   2026-09-24 (c)). The **untyped** form of the same request is also sent and recorded as **evidence only**
   (`month_svdates_untyped`), never judged against the dataset (S0-D7); it is C33's reproduction check.
2. If not bounded: a *candidate* `$Date` formula filter (never `$$InDateRange`), run inside a typed books-wide
   period (a formula alone inside an untyped/current period can never reach 2023). Also a one-day request (for
   auto-split).
3. The working (typed) form → `confirm_request("voucher_month")`.
4. One Trial Balance pair, as-on the window's last date, typed vs untyped `SVFROMDATE`/`SVTODATE` — **evidence
   only** (`report_tb_typed`, `report_tb_untyped`), byte-identical or not; probe 18's B part settles whether an
   as-on report is history, not probe 5.
- **DIFFERENT** if only the formula works; **FAILED** if neither → the extractor filters in Python and the chunk
  cap is re-sized.
- **Changed 2026-09-24 (plan part 4, live run):** CONFIRMED. Typed form bounds June 2023 exactly (20 vouchers) and
  a one-day window returns exactly 01-06-2023's 10. Under the Educational licence a `SVTODATE` whose day is not
  1/2/31 is silently ignored and Tally falls back to the current period's end (**Ruling C43**, §4.6) — the
  extractor's typed request therefore clamps a month's to-date under Educational to the 2nd (or the 31st when the
  month has one). The untyped evidence reproduced C33 (240 vouchers, current-period window, 2025-04-01..2026-03-31).
  `spec_impact`: the extractor types its period variables (`TYPE="Date"`); an untyped chunk under Educational looks
  healthy and is silently wrong (Part 1 §5 extractor). Run 1 failed against this exact bug before the clamp was
  built — see `.superpowers/sdd/2026-09-24-bi-s0-probes-plan-part4/progress.md` (Ruling R3).

### Data shape

**Probe 6 — Nested lines and ledger GUID on lines** · A · feeds S1 ingest rules, R5, R9
1. Vouchers with AllLedgerEntries.{LedgerName, Amount, IsDeemedPositive, BillAllocations.{Name, BillType, Amount,
   BillCreditPeriod}} and AllInventoryEntries.{StockItemName, ActualQty, BilledQty, Rate, Amount,
   BatchAllocations.{GodownName, BatchName, Amount}}. Check them against the seed structure (Sales = New Ref,
   Receipts = Agst Ref, 4 party Payments = Agst Ref).
2. Every voucher's Σ line Amount = 0.00 (Decimal) and debit is negative (Part 1 §6).
3. Ledger GUID on a line: (a) a *candidate* fetch field; (b) an inline-TDL computed field (e.g.
   `$GUID:Ledger:$LedgerName`). Record which works and whether it needs inline TDL.
- No GUID on lines → **DIFFERENT**: server name resolution stays (already designed). A nested list missing →
  **FAILED** → S1 schema change.

**Probe 11 — Openings** · B · feeds R5
- Ledger OpeningBalance, the debtor's opening bill (*candidate* opening-bills field, else Bills Receivable as-on
  books start), stock OpeningBalance / OpeningRate / OpeningValue — all against setup's values.
- **Changed 2026-09-25 (plan part 6) — correction, re-run under C46: DIFFERENT.** Ledger `OpeningBalance` is the
  **current-FY** opening, not books-start: 14 of 25 ledgers differ from setup's books-start value and all 14 equal
  the current FY's opening (`as_current_fy`), matching probe 16 B's `opening_scope.verdict = "fy"`. The opening bill
  `Op/2022-001` (₹62,500, dated 31-03-2022, on the ledger master via `BillAllocations`) CONFIRMED. Stock openings are
  the current period's (as at 01-04-2025) for 5/5 items (C46). Sub-verdicts: ledgers DIFFERENT, opening bill
  CONFIRMED, stock DIFFERENT; every half is now named in the summary. Impact (R5): **both** ledger and stock master
  openings are current-period-relative; a books-start anchor comes from a TB / Stock Summary as-on the books start
  (probe 18's route), never a master's `OpeningBalance`. Log `logs/p11-rerun-c46-2026-09-25.log`; the 2026-09-24
  captures are kept byte-for-byte in `v2/tests/fixtures/sync/c46_p11_live_2026-09-24/`. **The 2026-09-24 text below
  is superseded where it says ledger openings were CONFIRMED against books-start** — it misread a summary that
  showed only the stock half.
- ~~**Changed 2026-09-24 (plan part 5, live run):**~~ *(superseded 2026-09-25 for the ledger half, see above)* **FAILED (stock only).** Ledger OpeningBalance and the debtor's
  opening bill (via `BillAllocations` on the Ledger collection, filtered to the party) **CONFIRMED** against
  setup's books-start values. Stock OpeningBalance / OpeningRate / OpeningValue for all 5 items **FAILED** — **new
  finding, Ruling C46**: `StockItem.OpeningBalance` is the **current period's** opening, not the books-start one;
  live, all 5 items' exported "opening" equalled the dataset's stock **at 31-03-2025** (the current FY's start),
  not 01-04-2022. `spec_impact`: stock tiles must start from the first Stock Summary snapshot, not an opening
  anchor (R5); a books-start stock opening has to come from a historical report (probe 18's route), not the
  StockItem master. Fixtures: `p11_B_ledger_openings.xml`, `p11_B_opening_bills.xml`, `p11_B_stock_openings.xml`.

**Probe 12 — Current report snapshots** · A · feeds R5, the S1 snapshot fixtures
- TB, BS, full-FY P&L 2025-26, Stock Summary, Bills Receivable, Bills Payable at today's date. Bills totals equal
  the anchors; TB group rows parse to Decimal.
- These fixtures become the S1 snapshot-ingest fixtures.

**Probe 15 — Unicode and compound units** · B · feeds R14, R15
- The Hindi ledger, a Hindi narration, the compound-unit item, a voucher using it, and a Stock Summary including
  it. Text byte-exact against the dataset; the unit string recorded; no crash, and Tally answers a cheap read after.
  Changed 2026-09-24 (plan part 5, Ruling Q8): "byte-exact" is judged on the parsed text (code-point equality); whether
  the response carried it as UTF-8 bytes or as character references is recorded, not judged.
- **Changed 2026-09-24 (plan part 5, live run):** **CONFIRMED.** The Hindi debtor ledger and its narration (tag 7)
  round-trip exact (UTF-8 bytes, code-point equality); the compound-unit item (A4 Paper Ream, "Box of 10 Nos")
  reads back `10 Box 0 Nos` on its voucher and `20 Box` in the Stock Summary; Tally answered a cheap read after.
  Fixtures: `p15_B_hindi_ledger.xml`, `p15_B_hindi_narration.xml`, `p15_B_compound_unit_item.xml`,
  `p15_B_compound_unit_voucher.xml`, `p15_B_stock_summary.xml`.

**Probe 22 — Forex** · B · feeds decision 15 · **BLOCKED 2026-09-24 (C36)** — `setup-b` skips the 2 USD export
sales until a forex write shape is live-verified; see the header's "Changed 2026-09-24 (Ruling C36)".
- The 2 USD export sales: record each line's raw AMOUNT text (it may be an expression like `$… @ ₹…/$ = ₹…`) and
  any *candidate* forex fields. `amounts.parse_decimal` raising on the expression is expected; the probe records
  the raw text.
- **CONFIRMED** if the INR base amount comes from a field, or from one unambiguous parse rule, and balances to
  0.00 per voucher. **FAILED** → decision 15 is revisited.

**Probe 23 — GST classification and due dates** · A + B · feeds Part 3 tiles
- A: *candidate* fields (TaxType, GSTDutyHead, TypeOfDutyTax) on the CGST / SGST / IGST ledgers; empty on non-tax
  ledgers.
- B: BillCreditPeriod / due date on the bills setup gave credit periods; the due-date column of Bills Receivable.
- Missing → **FAILED** for that half → the GST tile or the overdue split is dropped from v1 (Part 1 probe 23).
- **Changed 2026-09-25 (plan part 6) — B as built and run live: CONFIRMED.** Credit periods from June 2023 via probe
  5's `voucher_month` request; due dates from Bills Receivable as-on 31-03-2026. Both sources work → CONFIRMED, one →
  DIFFERENT, neither → FAILED (one question: can the overdue split be built). Due = bill date + credit period in
  calendar days; `BILLOVERDUE`, the opening bill and `On Account` rows recorded, not judged. Live: 12/12 June-2023
  New Ref bills carry `BILLCREDITPERIOD` ("30 Days"/"45 Days"); Bills Receivable `BILLDUE` = bill date + credit period
  for 202/202 bills. Impact (Part 3 overdue split): two agreeing sources — S1 stores the credit period on the bill
  row and reads due dates from the Bills snapshot. Fixtures `p23_B_bills_credit_period.xml`,
  `p23_B_bills_receivable_due.xml`.

**Probe 25 — Masters classification** · A + B · feeds the S1 schema, R5, R16
- Groups: *candidate* fields Parent, PrimaryGroup / _PrimaryGroup, Nature, IsRevenue, AffectsGrossProfit,
  IsDeemedPositive, ReservedName. "National Creditors" must resolve to liabilities.
- Voucher types: Parent, ReservedName. B's "Sales - GST" must resolve to Sales.
- Missing → **DIFFERENT**: nature is derived by walking Parent to a reserved primary group, and base type by the
  parent chain (the mapping goes in the S1 spec).
- **Changed 2026-09-25 (plan part 6) — B as built and run live: DIFFERENT, with R9 CONFIRMED.** Voucher types:
  `Sales - GST` exports Parent `Sales` and an empty ReservedName, so it resolves to Sales only by the Parent walk
  (DIFFERENT, same rule as A). **R9 (duplicate ledger names)** is asked here as a UI-only, action-less step (never
  XML — LESSONS §15 rule 10), only when interactive and not auto; the read-back decides. Live 2026-09-25: TallyPrime
  **refused** a second `Delhi Metal Traders` under Sundry Debtors (existing under National Creditors) — "Oops! Name
  already exists. Enter a different name." at the Name field; read-back one ledger, parent unchanged. **R9 impact:**
  ledger names are unique within a company across groups; S1 may treat a ledger name as unique per company but keys
  ledgers by GUID. Fixtures `p25_B_voucher_types.xml`, `p25_B_ledgers_after_duplicate_attempt.xml`; logs
  `logs/p25B-live-2026-09-25.log`, `logs/p25B-r9-2026-09-25.log`.

### Change and identity

**Probe 7 — Deleted vouchers** · A · feeds R7
1. Pause: create throwaway voucher 2. Record its GUID, MasterID, AlterID and the counters.
2. Pause: delete it. It's gone from the collection? A tombstone (*candidate* IsDeleted)? Counters moved?
3. Pause: create throwaway voucher 3 → its GUID and MasterID differ from voucher 2's. Pause: delete it.
- **FAILED** if a GUID is reused or the voucher lingers → the deletion compare is redesigned.

**Probe 8 — Ledger rename** · A · feeds R9
1. Before: GUID and AlterID of "Rajesh Computers"; its vouchers' AlterIDs and exported names.
2. Pause: rename it to "Rajesh Computers S0". Record: which name the old vouchers export, whether voucher AlterIDs
   changed, same ledger GUID?, ledger AlterID bumped?, AltMstId / AltVchId moved?
3. Pause: rename it back. Verify.
- Outcome confirms or changes R9's server-side rename cascade by GUID.

**Probe 13 — Backup restore** · A · feeds R8 (last in batch 4)
1. Read the GUID, 5 MasterIDs and the counters.
2. Pause: back up A. Pause: create throwaway voucher 4 → counters rise.
3. Pause: close A, restore the backup over A's folder, open A. Read again.
- Record: same GUID? Counters back **below** the post-voucher values? Throwaway voucher gone?
- GUID changes on restore → **DIFFERENT**: a restore shows up as "new GUID, same name" (the re-link path, Q25), not
  `restore_detected`. Part 1 §4 "Company identity changes" is updated.

**Probe 19 — Counter stability** · A · feeds the quiescence guard
1. A capture (counters → ledger list → TB → counters), 3 times with no activity → counters equal each time.
2. Pause: open Balance Sheet in the UI and close it → counters unchanged? (Viewing must not move them.)
3. One capture with a pause between ledger list and TB: "enter a ₹1 voucher now" → counters differ. Pause: delete it.
- **CONFIRMED** if quiet captures are stable and a mid-capture entry is detected.

### Parity (decides whether decision 11 holds)

**Probe 16 — Ledger balances** · A + B · feeds decision 11, R30, Part 2 Rule 1
- A part:
  1. Ledger collection (Name, Parent, OpeningBalance, ClosingBalance).
  2. Nominal (P&L) ledgers → all ClosingBalance 0?
  3. Balance-sheet ledgers rolled up the group tree vs the TB group rows.
  4. Σ bill-wise debtors vs ₹9,70,537; Σ creditors vs ₹18,34,142.
  5. Ask: you read the closing balance of "Apex Technologies Pvt Ltd", "HP India Sales Pvt Ltd" and the main bank
     ledger from the Tally UI → compare.
  6. As-of date: ClosingBalance vs opening + Σ lines up to (i) the F2 date, (ii) the FY end.
  7. As-on: the same collection with SVTODATE = 31-10-2025 (and SVFROMDATE = 01-10-2025) → do the balances change
     to the as-on values computed from the lines?
  8. Pause: create a **post-dated** voucher in the UI (marked post-dated at entry) → is it in ClosingBalance?
     Does it export IsPostDated = Yes? Pause: delete it.
- B part: is OpeningBalance **FY-scoped or books-scoped**? With the period set inside FY 2024-25, compare against
  the dataset's FY opening and books-start opening. As-on reading at 31-03-2023 vs the dataset.
- Outcomes (Part 1 §16):
  - ClosingBalance ≠ TB / UI → **FAILED**: rung 1 collapses to group level.
  - As-on works → per-ledger opening anchors exist during the backfill without probe 17.
  - The post-dated rule and the as-of date are written into Part 1 §6 "Rung 1".
- **Changed 2026-09-24 (plan part 5, live run):** as built, bills/stock dates in the A part moved to 31-10-2025
  (Ruling C43, see header); the B part sends only a **typed** SVTODATE (01/02/31-only days: 31-03-2025 and
  31-03-2023), SVFROMDATE opt-in only under `--allow-risky`. **Outcome: FAILED** (worse of A DIFFERENT + B FAILED).
  **A part: DIFFERENT.** 10 nominal ledgers still have a non-zero ClosingBalance (rung 1 must pick balance-sheet
  ledgers by group nature, never by "ClosingBalance = 0"); the throwaway post-dated voucher was counted in
  ClosingBalance and exported `IsPostDated=Yes` (Tally's own current date had not yet reached the FY end). But
  **as-on closing DOES follow a typed SVTODATE inside the current period** — 19 of 22 balance-sheet ledgers moved to
  match the as-on lines — so per-ledger anchors are available this way **for dates inside the current period**.
  SVFROMDATE on the Ledger collection was **not** re-sent (the untyped form wedged Tally twice on 2026-09-23; the
  typed form is an open, opt-in check). **B part: FAILED — new finding, Ruling C45.** A typed SVTODATE **earlier
  than the current period's start** silently **clamps to the current period's first day**: 31-03-2025 and
  31-03-2023 both answered with the 01-04-2025 balances, on all 10 balance-sheet ledgers checked. So a dated
  Ledger-collection read never returns the as-on balance nor today's for a date before the current period — the
  agent must never send a period variable on a master collection for such a date (LESSONS rule 17 stands, now for
  the typed case too); per-ledger anchors for a past period come from probe 17's ledger-level TB (rung 2/decision
  11), or from a TB read per date the way probe 18 B does it. Fixtures: `p16_A_ledgers.xml`, `p16_A_groups.xml`,
  `p16_A_vouchers_fy.xml`, `p16_A_tb_fy_end.xml`, `p16_A_ledgers_asof_2025-10-31.xml`, `p16_A_future_voucher.xml`,
  `p16_A_ledgers_with_future_voucher.xml`, `p16_A_post_dated_voucher.xml`, `p16_A_ledgers_with_post_dated.xml`,
  `p16_B_groups.xml`, `p16_B_ledgers.xml`, `p16_B_ledgers_fy2024.xml`, `p16_B_ledgers_asof_2023-03-31.xml`. Debug
  log: `logs/p16B-debug-asof-2026-09-24.log`.

**Probe 17 — Ledger-level TB** · A · feeds decision 11, R3
- TB `TYPE=Data` with *candidate* explode / ledger-wise static variables (EXPLODEFLAG and others the plan lists).
  Ledger rows present? Their per-group sums equal the group rows? It completes within the timeout, and Tally
  answers a cheap read after? Record which variable works.
- **CONFIRMED** → rung 2 works at ledger level and month-bisect gets cheaper.
- **Changed 2026-09-24 (plan part 5, live run):** **CONFIRMED**, on the now-typed `ledger_level_tb` request
  template (no date change; probe 17's dates were never wrong, re-run so the stored template is the typed one S2
  will reuse). `isledgerwise` returns 29 ledger rows whose per-group sums equal the TB group totals; one non-ledger
  row (`Opening Stock`) rides along; `EXPLODEFLAG`/`EXPLODEALLLEVELS` stop at the second group level and miss
  ledgers under a custom sub-group. Fixtures: `p17_A_ledger_list.xml`, `p17_A_group_list.xml`,
  `p17_A_tb_exploded_explodeflag.xml`, `p17_A_tb_exploded_svexplodeflag.xml`, `p17_A_tb_exploded_isledgerwise.xml`,
  `p17_A_tb_exploded_ledgerwise.xml`, `p17_A_tb_exploded_explodealllevels.xml`.

**Probe 18 — Historical reports** · A + B · feeds decision 11, R30, Parts 2 + 3
- A:
  - TB as-on 31-10-2025 vs the group rollup of opening + lines ≤ that date.
  - Bills Receivable / Payable as-on 30-09-2025 vs bills pending on that date from the bill allocations.
  - Stock Summary as-on 30-09-2025: quantities exact vs opening + inventory lines; values recorded (valuation
    method may differ).
- B: TB as-on 31-03-2023 vs the dataset.
- Two sub-results:
  - TB part FAILED → **parity is suspended during the backfill** (R30).
  - Bills / stock part FAILED → those tiles lose their month-end comparison.
- **Changed 2026-09-24 (plan part 5, live run):** **CONFIRMED, both A and B.** A's bills/stock date moved to
  31-10-2025 (Ruling C43; a C43-valid day), and vouchers are read for the whole FY (`vouchers_fy`) instead of
  relying on an untyped to-date request (C33). **A: TB as-on 31-10-2025, Bills Receivable/Payable, and Stock
  Summary all as-on 31-10-2025 match that date exactly** — the 2026-09-23 "Bills/Stock ignore the as-on date"
  finding is **superseded**: 30-09-2025 was an Educational-ignored day (C43), and the report silently fell back
  to the FY-end position, which is exactly what looked like "ignoring the date". LESSONS rule 20's second half is
  overturned. **B: TB as-on 31-03-2023 equals the dataset for all 5 primary groups**, the stock-bearing group via
  its own `Opening Stock` TB row (resolution 10). Fixtures: `p18_A_tb_asof_2025-10-31.xml`, `p18_A_vouchers_fy.xml`,
  `p18_A_ledger_list.xml`, `p18_A_group_list.xml`, `p18_A_bills_receivable_asof_2025-10-31.xml`,
  `p18_A_bills_payable_asof_2025-10-31.xml`, `p18_A_stock_summary_asof_2025-10-31.xml`,
  `p18_A_stock_item_openings.xml`, `p18_B_tb_asof_2023-03-31.xml`, `p18_B_ledger_list.xml`, `p18_B_group_list.xml`.

### Reach and robustness

**Probe 21 — Full-history reach and size** · B · feeds decision 7b, Q22, Q23 · `requires=(0, 1, 5)`
1. BooksFrom = 01-04-2022. Fetch FY 2022-23 month by month with **probe 5's confirmed `voucher_month` request**
   (S0-D7 — probe 21 never builds its own); counts equal the dataset's (tag-set rule, Changed 2026-09-24 (c)). Also
   one current-FY sample month (`fy2025_month_03`) fetched for size comparison only, no verdict (closed- vs
   open-year behaviour).
2. Bytes per voucher by kind (with / without inventory lines, with bill allocations), in three measures: raw XML
   bytes, parsed-JSON bytes (a stand-in for the `raw` JSONB), and minimum-column bytes (Part 1 §5's columns,
   including `voucher_id` on every child row).
3. Storage table: 10k / 50k / 200k vouchers a year × 2 / 5 / 10 years, with and without `raw`; feeds Q22 (per-FY
   cost, share of `raw`, saving from dropping `raw` beyond the recent 2 FYs) and Q23 (per-extra-FY increment,
   month-chunk XML size against the ~5k-row cap).
4. If the edition has a period lock, lock FY 2022-23 (pause) and confirm reads still work. **The period-lock ask is
   an action-less pause, asked only when the run is interactive and not in auto mode** — locking a period cannot be
   done over XML and a blocked pause would sink the whole batch (Changed 2026-09-24 (d)). Otherwise recorded "not
   attempted".
- Timings recorded but labelled "Wine — not representative"; the tier-C timing part stays ⏭.
- **Changed 2026-09-24 (plan part 4, live run):** CONFIRMED. BooksFrom = 01-04-2022 (exact match). 12/12 FY 2022-23
  months reached exactly (238 tagged vouchers by count of written+unflagged tags; the cancelled pair — 201/202,
  Feb 2023 — was reported back, recorded, not judged per S0-D7). Size stats are computed over the 236 unflagged
  vouchers only (flagged vouchers excluded from size stats per plan resolution #10) — this is why the storage
  table's `mix_vouchers` reads 236, not 238; not a discrepancy. This edition reported "no period lock" — step 4
  recorded "not attempted"/none per Ruling R2 (locking would require reconfiguring the shared Educational Tally
  mid-S0). Numbers: `logs/p21-numbers-2026-09-24.log`, `v2/probes/results/results.json` `probes.21`, rendered in
  `docs/bi-s0-probe-results-2026-09-24.md`. These numbers are the Q22/Q23 **inputs**; the Q22/Q23 decisions
  themselves stay with the user (Part 1 spec §15).

**Probe 10 — Error shapes** · A · feeds the gate
1. No company open (pause) → response for a collection and for a report.
2. Popup: pause "open a voucher entry screen and leave it unsaved" → cheap read with a 10 s timeout → record
   timeout or response → pause "dismiss it" → Tally recovers?
3. Pause: quit Tally → the client error kind (refused).
4. Educational: only if probe 0 recorded Educational; otherwise "not applicable".
- Output: a table condition → transport result → body shape → gate action, for the S2 gate.

**Probe 14 — Special characters in the company name** · B · feeds R13
- The v2 envelope (escaped) with SVCURRENTCOMPANY = "Sharma & Sons' Probe Traders" → works. A deliberately
  unescaped copy of the same request → fails; record the error shape.
- **Changed 2026-09-24 (plan part 5, live run):** **CONFIRMED.** As built (resolution 14), an `unknown_company_request`
  control (naming a company that isn't loaded) is sent first: it "answered" rather than erroring — one company
  loaded, so the variable's own selectivity is unmeasured, but the request still gets a well-formed answer. The
  **escaped** request then returns 26 ledgers including the Hindi one; the **unescaped** request fails as recorded
  (kept 10 s and last in the B session, per resolution 14 / Ruling Q6); Tally answers a cheap read afterwards.
  `spec_impact`: the v2 envelope's escaping is what makes `Sharma & Sons' Probe Traders` reachable; the unescaped
  form fails as recorded (R13 holds). Fixtures: `p14_B_escaped_request.xml`, `p14_B_unknown_company_request.xml`,
  `p14_B_unescaped_request.xml`.

**Probe 24 — Secured companies** · C · feeds R2, R26
- Baseline export. Pause: enable security (username / password), reopen and log in → export. Pause: enable
  TallyVault, reopen with the vault password → export. Record each response.
- Needs credentials → onboarding note + a new error shape for the gate.
- **Changed 2026-09-25 (plan part 6) — as built and run live on company C (100001): CONFIRMED.** Manual only,
  `requires=(0, 1, 2, 5)`; "export" = five reads per stage (company list, active GUID with probe 2's request, counters
  with probe 1's, ledger list, vouchers with probe 5's for 01-04-2025..31-03-2026) at `baseline`, `security_on`,
  `vault_on`; plus the two gate reads (company list, active company) while the prompt is open (`security_login_pending`,
  `vault_prompt_pending`, via `try_send`) and once it is answered (`security_on_ready`, `vault_on_ready`). The probe
  never asks for or sends a credential. Verdict mapping: export unchanged after log-in/unlock → CONFIRMED; export works
  but GUID/content changed → DIFFERENT (re-link, Q25); export fails with the company open → FAILED; another company
  open → BLOCKED. Live: security on and TallyVault on both left the export unchanged (GUID
  `9d87f8c7-…`, ledgers, narration). **Gate shape:** with a login or TallyVault prompt open, both reads were
  **answered** with an empty company list and no active-company rows (as if no company were open) — no timeout, no
  error envelope → S2's gate treats it as "company not open" (skip quietly, retry). **Impact (R2, R26):** no
  credentials in the agent; onboarding says "open the company in TallyPrime as usual". Observed in the UI (TallyPrime
  7 EDU): security is K: Company → **Security** ("Security And User Access"); TallyVault is K: Company → TallyVault
  and offers "create a copy of <company> (<number>)?" — **No** encrypts in place (same folder); a vaulted company's
  name shows as asterisks in Select Company. Fixtures `p24_C_*` (23 files); log `logs/p24-live-2026-09-25.log`.

## 8. Deferred probes (⏭)
Probe 9 (latency per chunk; can the accountant keep typing), probe 20 (parity cost on a large company), the timing
half of probe 21, and the standard-edition runs of probes 7 and 13. All need tier C (Q29). The harness supports
them unchanged; they are listed ⏭ in `list` and in the results doc.

## 9. Outputs and where they go

| Output | Location | Consumed by |
|---|---|---|
| Raw fixtures + sidecars | `v2/tests/fixtures/sync/` | S1 ingest tests, S2 parser tests |
| Machine results + confirmed requests | `v2/probes/results/results.json` | S2 (the confirmed requests become the agent's requests) |
| Readable results | `docs/bi-s0-probe-results-<date>.md` (generated) | Team, spec updates |
| Tracker rows | `docs/plans/2026-09-22-bi-part1-tracker.md` §3 | Status |
| Spec changes | Part 1 spec (dated "Changed" line) | S1 / S2 specs |

## 10. Exit gate
1. Every tier-B probe is CONFIRMED, DIFFERENT, FAILED or BLOCKED-with-reason (none PARTIAL or unrun).
2. Every DIFFERENT / FAILED has its Part 1 spec change written.
3. Probes 16, 17, 18 outcomes are written into Part 1 §6 and §16.
4. Q22 and Q23 are answerable from probe 21's storage table.
5. Company A passes the anchors check at the end.
6. Harness tests pass, and `git status --porcelain` shows new or changed paths only under `v2/` and `docs/` (`git diff --stat`
   can't see untracked files).
7. Code review stored in `docs/code-review-bi-s0-*.md` (CLAUDE.md process).

## 11. Testing (tier A, no Tally)

The harness is tested with a fake transport (`httpx.MockTransport`) serving canned responses from
`v2/tests/fixtures/harness/`. **S0 writes no DB**, so there are no DB persistence scenarios. **Regression:** S0
changes no current code (isolation test + `git status --porcelain`), and the root suite doesn't collect `v2/tests`.

### 11.1 Harness state matrix

| Component | State / input | Expected |
|---|---|---|
| Part run | completes CONFIRMED / DIFFERENT / FAILED | Part written with summary, observations, fixtures, `spec_impact` (required for DIFFERENT / FAILED) |
| Part run | `pause` + Enter | Continues; manual step logged with timestamp |
| Part run | `pause` with `--non-interactive` | Part BLOCKED "needs manual step"; no further requests |
| Part run | `ask` | Typed input stored in `manual_steps[].input` |
| Part run | timeout | Part BLOCKED with the popup hint; sidecar with `error.kind = timeout`; no retry sent |
| Part run | connection refused | Part BLOCKED "Tally not reachable"; sidecar with `error.kind = refused` |
| Part run | missing prerequisite (`requires`) | Part BLOCKED naming the probe to run first; no request sent |
| Probe outcome | parts A done, B not run | PARTIAL, listing B |
| Probe outcome | A CONFIRMED + B DIFFERENT | DIFFERENT |
| Probe outcome | A CONFIRMED + B FAILED | FAILED |
| Probe outcome | all parts run, one BLOCKED and one FAILED | BLOCKED (precedence §5.1) |
| Probe outcome | A FAILED, B not run | PARTIAL |
| Part outcome | probe 18 with TB sub-verdict CONFIRMED and bills/stock FAILED | FAILED, both sub-verdicts in observations |
| Probe outcome | all parts CONFIRMED | CONFIRMED |
| Re-run | same part run twice | Latest replaces; previous moves to `history` |
| Company guard | 0 companies loaded | BLOCKED "no company open" |
| Company guard | 1 company, the expected one | Proceeds |
| Company guard | 1 company, a different one | BLOCKED naming both |
| Company guard | 2 companies loaded | BLOCKED "close all but …" |
| Mutation guard | expected company without "Probe" in its name | BLOCKED before any pause or request |
| Request guard | `<NATIVEMETHOD>*</NATIVEMETHOD>` / FETCH `*` | Refused, nothing sent |
| Request guard | `$$InDateRange` anywhere | Refused, nothing sent |
| Request guard | clean request | Sent |
| `counters()` | before probe 1 confirmed | Refuses, naming probe 1 |
| `counters()` | after | Uses the stored template |
| `company_names()` | `company_list_live.xml` (has `CMPINFO` counters) | Exactly one name: "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED" (no "0") |
| Capture | normal response | `.xml` byte-identical to what the transport returned (incl. `&#4;` and Hindi); sidecar has every §5.6 field |
| Report | results with every outcome + ⏭ probes | Deterministic doc: probes in id order, deferred listed, environment block present |
| `list` | mixed results | Each probe's latest outcome; ⏭ for deferred |

### 11.2 Copied-code tests

| Unit | Cases |
|---|---|
| `envelopes.py` escaping | Company names `A & B`, `Sharma & Sons' Probe Traders`, `He said "x"`, `a<b>c`, a Hindi name → every wrapper yields XML that `ElementTree` parses, and the parsed value equals the input |
| `envelopes.py` company argument | Every wrapper places SVCURRENTCOMPANY when given, omits it when `None` |
| `amounts.py` (`parse_decimal`) | `"-1048846.53"` → `Decimal("-1048846.53")`; `"0"` → `Decimal("0")`; `""` / missing tag → `None`; a forex expression → `AmountParseError` with the raw text; no float anywhere |
| `xml_utils.py` | `parse_company_list` on `company_list_live.xml` → exactly one company, no "0"; on a response with a `<NAME>` child, a `NAME` attribute, and two companies → both names |
| `reports.py` | Copied into `v2/tests/fixtures/` from `tests/fixtures/` (NUVANTA company data — parser tests only): `trial_balance_live.xml` → 7 group rows, Decimal amounts, debit negative; `bills_receivable_live.xml` / `bills_payable_live.xml` → Decimal totals; `stock_summary_live.xml` → Decimal values; `ledger_list.xml` → Decimal opening / closing |
| `client.py` | Returns (text, ms, bytes); timeout / refused raise the copied exceptions; no attribute or import referring to mock mode |

### 11.3 Isolation tests (`test_isolation.py`)

| Case | Expected |
|---|---|
| Real scan of every `.py` under `v2/` | No import whose top-level module is `backend`, `scripts` or `tests` |
| Real scan of `v2/agent/` | No import of `v2.probes` (so no write code reaches the agent) |
| Scanner self-test on a temp tree: `import backend.x`, `from scripts import y`, `from tests.z import w`, and `v2/agent` importing `v2.probes.setup` | Each one flagged |
| Every copied file | Starts with the source-path + commit header |

### 11.4 Company B loader tests

| Case | Expected |
|---|---|
| Dataset generated twice with the same seed | Identical vouchers and expected figures |
| Every generated voucher | Σ amounts = 0.00 |
| Educational mode on | Only allowed voucher dates are used |
| Expected-figures function | Month-end balances equal the running sum of the generated lines + openings |
| First load on an empty company (fake transport) | Lists masters before any create; creates everything; reads back each write |
| Second load | Sends **zero** creates |
| A master that already exists | Not re-created (LESSONS §15 rule 10) |
| Company without "Probe" in its name | Refused before any request |
| A read-back that doesn't match (e.g. cancelled flag dropped) | Turns into a pause step naming the voucher |

### 11.5 Fixture matrix

**Harness fixtures** (`v2/tests/fixtures/harness/`): company list with 0 / 1 / 2 companies; a collection response;
a report response; a Tally error envelope; a response containing `&#4;` control characters; a Hindi response;
transport-level refused and timeout (simulated by the fake transport, no file).

**S0 captures** (`v2/tests/fixtures/sync/`, one `.xml` + `.json` per step; `{C}` = company letter). The exact step
names per probe are fixed by the implementation plans (part 2 adds steps, e.g. probe 1's `alter_ledger_again` replaces
`revert_ledger`); the list below is the minimum:

| Probe | Steps captured |
|---|---|
| 0 | `company_list`, `guid_before_rename`, `guid_after_rename`, `anchors_bills_receivable`, `anchors_bills_payable`, `anchors_tb` |
| 1 | `counters_candidates`, `ledger_list`, `counters_baseline`, `ledger_before`, `counters_after_{create,alter,delete}_voucher`, `ledger_after_voucher`, `counters_after_{alter,create,delete}_ledger` |
| 2 | `active_{a,b,c}`, `active_{a,b,c}_no_company` |
| 3 | `A_vouchers_ids_flags`, `B_vouchers_flags` (as built, plan part 6: adds `B_flagged_month_2023_02`, `B_flagged_month_2023_07` — probe 5's month request for the cancelled and the optional pair) |
| 4 | `{voucher,ledger,group,stockitem}_full`, `…_gt_m_minus_5`, `…_gt_m`, `…_gt_0` |
| 5 | `month_svdates`, `month_svdates_untyped` (evidence only), `month_formula` (if needed), `day_svdates`, `report_tb_typed`, `report_tb_untyped` (evidence only) |
| 6 | `vouchers_nested`, `line_guid_fetch`, `line_guid_tdl` |
| 7 | `throwaway_created`, `after_delete`, `second_throwaway` |
| 8 | `rename_before`, `rename_after`, `rename_restored` |
| 10 | `no_company_collection`, `no_company_report`, `popup_read` (sidecar only if timeout), `after_popup`, `tally_quit` (sidecar only) |
| 11 | `ledger_openings`, `opening_bills`, `stock_openings` (as built, adds `opening_bills_report`, the Bills Receivable books-start fallback) |
| 12 | `tb_today`, `bs_today`, `pl_fy2025`, `stock_summary_today`, `bills_receivable_today`, `bills_payable_today` |
| 13 | `before_backup`, `after_throwaway`, `after_restore` |
| 14 | `escaped_request`, `unescaped_request` (as built, adds `unknown_company_request`, the SVCurrentCompany control, sent first) |
| 15 | `hindi_ledger`, `hindi_narration`, `compound_unit_item`, `compound_unit_voucher`, `stock_summary` |
| 16 | `A_ledgers`, `A_ledgers_asof_2025-10-31`, `A_ledgers_from_2025-10-01`, `A_post_dated_voucher`, `A_ledgers_with_post_dated`, `B_ledgers_fy2024`, `B_ledgers_asof_2023-03-31` (as built: `A_groups`, `A_vouchers_fy`, `A_tb_fy_end`, `A_future_voucher`, `A_ledgers_with_future_voucher` also captured; B part uses only typed SVTODATE steps — `B_groups`, `B_ledgers`, `B_ledgers_fy2024`, `B_ledgers_asof_2023-03-31`, plus opt-in `B_ledgers_fy2024_svfromdate`) |
| 17 | `tb_exploded_{variable}` (one per candidate) |
| 18 | `A_tb_asof_2025-10-31`, `A_bills_receivable_asof_2025-09-30`, `A_bills_payable_asof_2025-09-30`, `A_stock_summary_asof_2025-09-30`, `A_vouchers_to_2025-10-31`, `B_tb_asof_2023-03-31` — **as built (plan part 5, C43/C33):** the 30-09-2025 bills/stock dates moved to **31-10-2025** and the untyped `vouchers_to_2025-10-31` read is replaced by an explicit `A_vouchers_fy` (whole-FY) fetch: `A_tb_asof_2025-10-31`, `A_bills_receivable_asof_2025-10-31`, `A_bills_payable_asof_2025-10-31`, `A_stock_summary_asof_2025-10-31`, `A_stock_item_openings`, `A_vouchers_fy`, `A_ledger_list`, `A_group_list`; B adds `B_ledger_list`, `B_group_list` alongside `B_tb_asof_2023-03-31`. The superseded 2025-09-30 / untyped `vouchers_to_2025-10-31` captures are kept byte-for-byte at [`v2/tests/fixtures/sync/c33_untyped_2026-09-23/`](../../v2/tests/fixtures/sync/c33_untyped_2026-09-23/), not deleted. |
| 19 | `capture_quiet_{1,2,3}_{counters_start,ledgers,tb,counters_end}`, `after_ui_view`, `capture_moving_*` |
| 21 | `books_from`, `fy2022_month_{04..03}`, `fy2025_month_03` (current-FY sample, sizes only), `period_locked_read` (if lockable) |
| 22 | `forex_sales` |
| 23 | `A_gst_ledgers`, `B_bills_credit_period`, `B_bills_receivable_due` (as built, plan part 6: unchanged — `B_bills_credit_period` is June 2023 via probe 5's request, `B_bills_receivable_due` is Bills Receivable as-on 31-03-2026) |
| 24 | `baseline`, `security_on`, `vault_on` — **as built (plan part 6), part C:** each of `C_baseline`, `C_security_on`, `C_vault_on` is five reads, `…_{company_list,active_company,counters,ledgers,vouchers}`; plus the gate reads `C_security_login_pending_{company_list,active_company}`, `C_security_on_ready_{company_list,active_company}`, `C_vault_prompt_pending_{company_list,active_company}`, `C_vault_on_ready_{company_list,active_company}` (23 fixtures; the plan's `vault_password_pending` was built as `vault_prompt_pending`) |
| 25 | `A_groups`, `A_voucher_types`, `B_voucher_types` (as built, plan part 6: adds `B_ledgers_after_duplicate_attempt`, the R9 read-back) |

## 12. Risks (S0-specific)

| Risk | Handling |
|---|---|
| setup-b freezes Tally (duplicate-master modal) | List before create, skip by tag, timeout stops the loader with the popup hint (LESSONS §15 rule 10) |
| Company A's figures drift after a failed cleanup | Anchors check before parity probes and after the A batch; recovery = re-restore A from the seed backup |
| Probe 10's popup or probe 13's restore leaves Tally stuck | The pause text includes the recovery step (dismiss the modal / restart Tally); both run late in batch 4 |
| Wine behaviour differs from Windows | Odd results are flagged "confirm on tier C" and not designed around (Part 1 §7) |
| Educational mode distorts date-based probes | Probe 0 records the mode; affected results tagged (§4.6) |
| A candidate field name is wrong and every candidate fails | The probe outcome is FAILED with the fallback, not a guess; the plan lists candidates per probe |
| Timings under Wine taken as real | Every sidecar says "Wine — not representative"; no decision uses Wine timings |

## 13. Out of scope
- Tier C timing probes (9, 20, 21-timing) and standard-edition cross-checks (§8).
- Any S1 cloud code, and any S2 agent code beyond the copied read code in §3.
- Any change outside `v2/` and `docs/`.

## 14. Left for the implementation plan
- The exact Wine data-folder paths for companies A, B, C.
- ~~How company B's GST registration is filled in (Tally may validate the GSTIN format).~~ **Answered
  2026-09-23** (`docs/plans/2026-09-23-bi-s0-company-b-loader.md`, built): company-level GST registration
  stays **UI-only** — the loader never writes it (spec §4.3's UI setup step covers "GST enabled", not the
  GSTIN itself). Party ledgers that need one carry a `PARTYGSTIN` whose check digit is computed with the
  standard base-36 alternating-weight algorithm (`gstin()` in `v2/probes/setup/company_b_data.py`), verified
  against the real-world GSTIN `27AAPFU0939F1ZV`. Parties without a GSTIN are written
  `GSTREGISTRATIONTYPE=Unregistered` (`v2/probes/setup/writes.py`).
- The full candidate request list for probes 2, 6, 16 (as-on variables), 17 and 25.