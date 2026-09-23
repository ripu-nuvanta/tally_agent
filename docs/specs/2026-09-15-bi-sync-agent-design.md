# Design (brainstorm): Read-only BI layer, single-company Windows Sync Agent

> **Brainstorm design (2026-09-15), not yet implemented.** No code changes have been made for this.
> Replaces an earlier multi-company draft with the v1 scope confirmed on 2026-09-15.
> Research sources (2026-09-15): Tally help docs, tally-database-loader source/docs, Biz Analyst/Suvit help, Microsoft Learn.
>
> **Updated 2026-09-18:** §4 Chat & BI expanded into §4.A–4.E (data-source routing for all 18 tools,
> the rung 0/1/2 integrity ladder, quiescence guard, cause classifier, escalation ladder, schema,
> surfacing, tests). Decisions 11–14, probes 16–20, five new code gaps in §9, and questions Q19–Q21
> added; Q7 answered. Code references verified against the repo on that date. Still docs-only.
>
> **Also 2026-09-18 — scope change:** the first sync still copies 2 FYs (that is what unlocks chat),
> but a **background backfill now walks history back to the company's books-start date**
> (decision 7b, §3 "Background history backfill"). Consequences: R27 impact raised, new risks
> **R29** (backfill may never complete — accepted) and **R30** (all-time ledger balances are not a
> valid parity anchor mid-backfill — parity is watermark-bounded, gated on probe 18), new probe 21,
> questions Q22–Q24.
>
> **Scope confirmed 2026-09-18:** **India-only, INR-only** (decision 15). Every BI and chat figure is
> the INR base amount; forex vouchers (export/import) keep their foreign face value in `raw` for
> drill-down but are never aggregated. No multi-currency reporting. New probe 22 confirms the INR
> base amount is exposed on forex voucher lines.
>
> **Updated 2026-09-21 — contradictions resolved:** GUID mismatch vs "GUID changed → full resync"
> (§3 "After a gap", R8), automatic full resync vs decision 12 (decision 12 now covers R8 too),
> chat on live-connected workspaces vs "never query live Tally" (decision 8, §6), stale §12.12
> item 8, and the rung-1 mid-backfill anchor (§4.B). New questions Q25–Q27.
> Second pass the same day: routine **month-end snapshots** (§3) replace the false claim that
> month-bisect stores them; computed historical balances share parity's **opening anchor** (§4.A
> rule 1, §4.B); decision 11 now states rung 1's dependency on probe 16/17 during backfill; probes
> 16 and 18 widened; tool count corrected to 19 (`resolve_date_range`); two line refs corrected;
> `restore_detected` and Re-link added to the web states, Settings and §12.9.
> Third pass: new coverage state **`resyncing`** (§3, §4 Cloud) so no resync — whole-company or
> single-FY — ever locks chat or turns loaded years into "still loading"; queries read the
> *available* edge, parity the *verified* edge.
> Fourth pass: no computed fallback for stock/bill-dependent reports (§4.A rule 1, R5); mirrored
> balances re-read for voucher-touched ledgers each cycle; Cash & bank month-end baseline computed
> backwards; computed balances use the nearest stored anchor; "Re-sync this year" only after two
> failed heals; backfill order in the cycle table; R6/R7 backstop during backfill; S1 probe deps;
> Q8 narrowed; §13 counts and question list; `oldest_available_fy`; half-loaded FY at restore;
> restore state in the status card and selector dot; probe lists in §5/§13 brought up to 1–22.
> Fifth pass (full consistency sweep): chat computes balances **backwards from mirrored balances**
> (§4.A rule 1), so the Cash & bank tile and chat agree and opening anchors are parity-only; master
> tools routed as *mirrored* and `get_cash_flow` as *computed*; one **work-priority** table for all
> agent work (§3); deletion check scoped (daily 2-FY, round-robin older); dates and clocks; month-end
> section aligned with the no-fallback rule; FY-close captures for backfilled years; mirrored
> re-read on outbox and reconcile paths; gross margin, GST and overdue definitions (probe 23);
> diagnostics, ingest limits, GUID index, extra masters out of scope, Q28; `hard_alert` column;
> R28 reordered. This supersedes the anchor-based computed balances of the second and fourth
> passes. Sweep follow-ups: coverage rows for the 2-FY window and each new FY start `complete`;
> both edges counted back from the current FY; masters re-fetched first in a whole-company resync;
> single-FY resync at tier 2; §12.9 `resyncing` row limited to the whole-company case.

## 1. Context
New product direction:
- **BI layer.** The owner sees their business (sales, profit, who owes money, top customers, stock) and asks the AI chat. Everything is answered from **our DB**.
- **Read-only.** This layer never writes to Tally.
- **Windows sync agent.** A small program on the customer's Tally PC copies Tally data into our cloud Postgres.
- The existing write flow (upload → Vision → voucher card → Write to Tally) stays untouched.
- This realizes roadmap **Set C** (`docs/roadmap.md`, never started). Sync-only replaces the old real-time tunnel idea.

## 2. Confirmed decisions
| # | Decision |
|---|---|
| 1 | Existing write features untouched. **Existing live-connected workspaces (with `tally_host`) keep the write flow exactly as today.** |
| 2 | Agent in **Python**, reusing `backend/tally_bridge/` read code. Ships as a PyInstaller `--onedir` build + signed installer, runs as a Windows service + tray app (status, last sync, "Sync now"), with silent auto-update. Minimum **Windows 10**. |
| 3 | **Single company, picked once at setup.** The user logs in inside the agent with website email/password, picks **one** company, and we save its **GUID** on the workspace. One company = one workspace. |
| 4 | **Single company open in Tally.** v1 assumes only our company is open. We fetch only when the active company's GUID matches the saved one. Multi-company, several loaded companies, and loaded-but-not-active are **out of scope**. |
| 5 | **Fetch only while connected.** When Tally is reachable and our company is open, fetch. Otherwise **skip quietly** (no error, no alert) and retry next cycle. |
| 6 | Sync masters (groups, ledgers, stock items), all vouchers with lines, and Tally report snapshots (TB, BS, P&L full-FY, Stock Summary, Bills Receivable/Payable) — **current ones on every refresh, plus a routine month-end set** (§3 "Month-end snapshots"). Eventually for **all** financial years (decision 7b), starting with the most recent two. |
| 7 | First sync copies the **current FY + previous FY** — that is what unlocks chat. A **new FY is added automatically** when the date crosses 1 April. |
| 7b | **After the first sync, a background backfill walks history backwards to the company's books-start date** (§3 "Background history backfill"). It is the lowest-priority loading work (§3 "Work priority"), always pre-empted by incremental sync, and never blocks chat. Dates it hasn't reached yet report "still loading", never a partial total. |
| 8 | During first sync the web shows progress and chat is locked. After that, every query is answered from our DB with "last synced X ago". **On sync-agent workspaces we never query live Tally.** Chat tool handlers branch on `workspace.config.source`: `sync_agent` → our DB (§4.A); live-connected workspaces (with `tally_host`) and demo mode keep today's live/mock query path unchanged (decision 1). Retiring the live path is Q27. |
| 9 | Change detection uses Tally's change counters (AltVchId/AltMstId + AlterID), plus a deletion check (daily for the 2-FY window, round-robin for older years — §3 "After a gap"). Must be proven on live Tally first (S0). |
| 10 | Sync-agent workspaces have no `tally_host`, so **the write flow is not available on them in v1**. The UI says so ("Writing to Tally isn't available for synced companies yet") instead of hiding it silently. |
| 11 | **Parity scope v1 = rungs 0+1+2** (§4.B): double-entry invariant on ingest, ledger-level vs mirrored `LEDGER.ClosingBalance`, group-level vs TB snapshot. Rung 3 (P&L / BS / stock / bills totals) is deferred. **Rung 1 needs a per-ledger opening anchor**: it always runs once history is complete, but *during the backfill* only if probe 16 or probe 17 provides per-ledger openings (§4.B "The opening anchor"); otherwise rung 2 carries the check at group level. Since the backfill can take weeks or never finish (R29), **probes 16 and 17 must be settled before S1** — without either, rung 1 may never run for some customers. |
| 12 | **No full resync is ever automatic — whatever triggers it.** When targeted remediation fails twice (§4.B), or counters go backwards after a backup restore (R8), or the user confirms a re-link (§3 "Company identity changes"), we *offer* it and wait for the user. A full resync is hours of Tally load (R3, R22); running it unannounced while the accountant works is how we get uninstalled. |
| 13 | **An integrity alert never blocks chat or dashboards.** Affected answers carry a caveat and the dashboard shows a scoped ribbon. Blocking is reserved for the first sync. |
| 14 | **The internal ops signal for integrity alerts carries counts and causes only** — no ledger names, party names, or amounts tied to identifiable accounts (respects Q6 / R20). |
| 15 | **India-only, INR-only.** Indian companies, Indian FY (1 Apr – 31 Mar), GST, Indian number formatting. **Every BI and chat figure is the INR base amount.** An Indian company can still hold forex vouchers (export sales, import purchases — the reason the FX write flow exists), but Tally records those with an INR base amount alongside the foreign face value: we aggregate **only** the INR base amount, and the original currency/face value is preserved in `raw` JSONB for drill-down, never summed. No multi-currency reporting, no rate tables, no conversion at read time. |

## 3. Sync behaviour

### Setup (once)
1. Install the agent → log in → the agent lists companies from Tally (`build_company_list`, `request_builder.py:153`).
2. The user picks one → the cloud creates/reuses a workspace with `config = {source:"sync_agent", tally_company, tally_company_guid, device_id, sync_state, books_from, last_synced_at}`.
3. Re-picking the same GUID is a no-op.

### Every cycle (~10 min + jitter)
| Tally state | Internet | Action |
|---|---|---|
| Tally closed / unreachable | any | Skip quietly |
| Tally running, but the XML port is closed or a popup is blocking the XML server | any | Skip + backoff. Tray shows "Turn on Tally connectivity" when the port is closed (R10); nothing for a popup, which clears on its own (R26) |
| Tally open, no company open | any | Skip quietly |
| Tally open, different company (GUID mismatch) | any | Skip quietly, never fetch or upload. If the name matches ours, also show the Re-link prompt (§3 "Company identity changes") |
| Tally open, **our company**, nothing changed | up | Lower-tier work, top-down (§3 "Work priority"): user-confirmed work, parity remediation, the daily pass, month-end captures — and only if none of those, **one backfill / re-walk chunk** (the newest FY not yet loaded, newest month first), then the older-year deletion compare. Nothing pending → heartbeat only. Heartbeat after |
| Tally open, **our company**, nothing changed | **down** | Nothing. Lower-tier work needs server acks (coverage, reconcile, parity), so it waits for the internet |
| Tally open, **our company**, changes found | up | Fetch AlterID > cursor → upload → **re-read `ClosingBalance` / `ClosingValue` for the ledgers and stock items those vouchers touch** → refresh snapshots → advance cursor after server ack. **Nothing lower-tier runs this cycle** — fresh data always wins |
| Tally open, **our company**, changes found | **down** | Fetch → re-read the touched balances → store both as gzipped batches in the local **outbox** → **cursor not advanced on the server yet** → upload the outbox automatically when internet returns (oldest first, `batch_id` makes re-sends safe) |

### First sync (the 2-FY window — this is what unlocks chat)
- Record counters **before** starting → masters → vouchers month by month for 2 FYs (**24 progress units**) → report snapshots → `ready`. At `ready`, both window FYs' `sync_fy_coverage` rows are `complete`.
- The web shows progress text: "Connecting to Tally…" → "Syncing your data… 60%" → "Ready".
- The first incremental starts from the recorded counters, so edits made during the first sync are caught.
- **Interrupted by disconnect → resume** from saved chunk status on the next connection, not from zero.
- Chat stays locked until the first sync completes — **and only until then**. The history backfill below never re-locks it.

### Background history backfill (decision 7b)
Once the 2-FY window is `ready`, the agent keeps walking **backwards** through the company's earlier
financial years until it reaches `books_from`, then stops for good.

**Order.** Newest-first, both between FYs and within one: FY−2 before FY−3, and March before April
inside each. The most recently-closed year is the one people actually ask about, so it lands first.

**Pacing (R3 — the top "customers uninstall" risk).** The lowest-priority loading work, strictly pre-empted:
- At most **one chunk per cycle**, and only on a cycle where incremental found nothing to do.
- Anything in tiers 1–5 (§3 "Work priority") — a pending incremental change, a non-empty outbox,
  a parity remediation, the daily pass, a month-end capture — **cancels** the backfill chunk for
  that cycle.
- The same `gate.py` rules apply — one request at a time, chunk auto-split when slow, circuit breaker
  after a timeout. A backfill chunk that trips the breaker is retried next cycle, never immediately.
- Consequence: a ten-year company may take days or weeks to complete. That is the intended trade —
  it is invisible to the accountant, and the data nobody is waiting on arrives when it arrives.

**Watermark.** The authoritative record is the **`sync_fy_coverage`** table (§4 Cloud) — one row per
FY with `state`, `months_complete`, `months_total`. The agent reports each finished chunk via
`PATCH /api/sync/{ws}/coverage`; `workspace.config.backfill = {oldest_available_fy,
oldest_complete_fy, books_from, percent, state}` is a denormalised copy for cheap status reads.
`oldest_available_fy` is the *available* edge (chat, the History card's available-from date);
`oldest_complete_fy` is the *verified* edge (parity, "Checked against … onwards"). They differ only
while FYs are `resyncing` (§3 "What a full resync does…"). `backfill.state` is `running |
resyncing | complete`; "stalled" is a UI label derived from no progress for N days (R29), not a
stored state. A month chunk is only marked
complete **after the server acks it**, so an interrupted backfill resumes rather than restarts (same
rule as the first sync). Backfill runs are recorded with `kind = backfill` and **do not advance
`last_synced_at`** — "last synced X ago" must mean fresh data, not old data.

**Query behaviour before a year lands (decision 7b).** Tools check the watermark, not just the
requested date:
- Date inside the synced window → answer normally.
- Date in an FY **not yet backfilled** (`pending`/`running`) → *"I'm still loading data from before
  Apr 2024 — about 60% done. Ask me again shortly."* **Never a partial total**, because a figure that
  silently grows later is worse than no figure.
- Date in an FY that is **`resyncing`** (already loaded, being refreshed after a restore or a parity
  resync) → answer normally, with the caveat that applies (§3 "What a full resync does…").
- Date before `books_from` → the ordinary out-of-window refusal (§4.A rule 2).
- A range **straddling** the available edge is treated as not-yet-available, not silently truncated.

**Edits that land in a year not yet loaded.** Incremental sync fetches by AlterID, not by date, so
a back-dated edit can bring in a voucher dated in a `pending` FY. It is stored as usual (upsert,
`alter_id >=`). That FY still answers "still loading" and is not parity-checked until the backfill
completes it, and when the backfill reaches that month the upsert keeps whichever copy is newer.
Not a bug and not a mismatch.

**Interaction with parity.** Parity (§4.B) runs against the **synced window only**, bounded by the
watermark. Un-backfilled years are not a mismatch — they are simply out of scope for the check until
their FY completes. When an FY completes, it becomes eligible and gets one parity run.

**Completion.** When `oldest_complete_fy == books_from`'s FY, state becomes `complete`; the backfill
never runs again unless a full resync is triggered. Settings shows "Full history loaded".

### After a gap
- Tally not opened for days → the next connection fetches everything with AlterID > cursor (natural catch-up).
- **Deletion check** (GUID + AlterID list compare, one month per unit):
  - **2-FY window:** every day, as part of the daily pass (§3 "Work priority", tier 4).
  - **Older years:** round-robin at tier 7, one FY at a time. Each is re-checked once per sweep
    (days to weeks, depending on depth), so the daily cost stays bounded however much history is
    loaded (R3).
  - Anything missing is soft-deleted via `/reconcile`. Its response lists the ledgers those vouchers
    touched, and the agent re-reads their mirrored balances in the same cycle (§4.A "Mirrored").

### Company identity changes (backup restore, re-created company)
The agent cannot tell "a restored or re-created copy of our company" apart from "a different
company" by GUID alone, so **a GUID mismatch is always a skip** (cycle table above). Nothing is
ever fetched, uploaded or resynced automatically on a GUID mismatch (R2 outranks R8).

| Situation | What the agent sees | Action |
|---|---|---|
| Different company open | GUID ≠ saved, name ≠ saved | Skip quietly (cycle table) |
| Possibly our company, re-created or restored with a new GUID | GUID ≠ saved, **name = saved** | Skip, **and** the tray + Sync / Settings show "This looks like a new copy of *Bharat Traders* in Tally. Re-link?" Only on the user's confirm: save the new GUID and *offer* a full resync (decision 12). Q25 |
| Backup restored, same GUID | GUID = saved, `AltVchId`/`AltMstId` **below** our cursor | **Stop incremental** (our cursors are meaningless now), set `sync_state = restore_detected`, and *offer* a full resync (decision 12). Chat and dashboards stay available with a caveat ("Tally was restored from a backup — our copy may include entries that no longer exist"), per decision 13. Q26 |

Whether a Tally restore keeps the GUID is what probe 13 settles; both rows are designed so the
answer changes nothing unsafe.

### What a full resync does to the window and the backfill
A resync **never locks chat and never makes loaded data answer "still loading"**. The data is
already there and is refreshed in place, so every FY it touches goes to the coverage state
**`resyncing`**, not back to `pending`/`running`:

- **Backup-restore / re-link resync (whole company):** every `complete` coverage row — the 2-FY
  window and all backfilled years — goes to `resyncing`. **Masters, with their mirrored balances,
  are re-fetched first** (a restore can change ledgers, groups and every balance), then the 2-FY
  window (tier 2, §3 "Work priority"), chunk by chunk, **without** the first-sync chat lock
  (decision 13). The walker
  then re-walks the older `resyncing` years newest-first, at backfill priority (tier 6). Each FY
  returns to `complete` when its last chunk is acked. Rows not re-seen are soft-deleted by the
  per-chunk reconcile. Throughout, every `resyncing` year answers normally with the restore caveat
  ("Tally was restored from a backup — we're refreshing our copy"). Years that were still `pending`
  before the restore stay `pending` and load as normal backfill. A year that was **half-loaded
  (`running`)** at the time of the restore goes back to `pending` with `months_complete = 0`. Its
  months came from the pre-restore copy, and it was never answerable anyway.
- **Single-FY resync (parity remediation, §4.B):** only that FY goes `complete` → `resyncing` →
  `complete`. The rest of the window and the backfill watermark are untouched. Answers for that FY
  keep the integrity caveat they already carry (the FY is in `alert`), never "still loading" — even
  when it is the current FY.
- **Two watermark edges.** Both are counted back from the current FY. Queries read the *available*
  edge: the oldest FY reached, going back without a gap, whose rows are all `complete` **or**
  `resyncing`. Parity reads the *verified* edge: the same, counting only `complete` rows. A `resyncing` year is answerable but is not parity-checked until it returns to
  `complete`, then gets one run (for a parity-triggered resync, that run is escalation step 4, §4.B).
  Where this spec says "the watermark" without qualifying it, **query rules mean the available edge
  and parity rules mean the verified edge**.
- **Whole-company resync only:** `workspace.config.backfill.state` becomes `resyncing` and the
  History card shows "Refreshing history after a restore — 40%" (§12.4, §12.9). A single-FY parity
  resync leaves `backfill.state` alone and shows only on the Data integrity card.
- Both are recorded as `sync_runs.kind = full_resync`. **Unlike backfill** (which never advances
  `last_synced_at`), a full resync advances it — but only for chunks inside the current 2-FY window,
  since those are the ones that bring the data up to date.

### New financial year
- On the first connected cycle on/after 1 April, add the new FY to the sync range (masters unchanged, vouchers for the new FY from its start). Its `sync_fy_coverage` row is created `complete`: it starts empty and incremental sync keeps it current, so the available edge never breaks at the forward end.
- The previous FY is kept. **No year is ever deleted automatically** — the backfill's whole purpose is to accumulate full history (decision 7b).
- A rollover does not restart the backfill; it only extends the *forward* edge of the window.

### Month-end snapshots
Current snapshots answer "as of now"; §4.A rule 1 and the dashboard's "vs last month-end" tiles
(§4.C) also need Tally's own figures **at each month-end**, so they are captured routinely rather
than only when month-bisect happens to run.
- **When:** on the first connected cycle on/after the 1st of each month, capture the month-end set
  **as-on the last day of the previous month** (not as-on today, so a late capture is still correct).
- **What:** TB, Bills Receivable, Bills Payable, Stock Summary — four `TYPE=Data` calls, one at a
  time through `gate.py`, at tier 5 (§3 "Work priority") — above the backfill, so a long backfill
  never starves it — spread across cycles if needed.
- **First sync:** also captures the most recent completed month-end **and the previous FY's close
  (31 March)** if that is a different date, so the dashboard has a month-end baseline and a
  year-start stock value on day one.
- **Older month-ends are not captured retroactively.** A TB for such a date is computed (§4.A
  rule 1). Bills Receivable/Payable and Stock Summary have no computed fallback, so those dates get
  the "I have Tally's own figures for these dates: …" answer.
- **Backfilled years:** every backfill chunk's anchor TB (§4.B "The opening anchor") is itself a
  month-end TB, so TB month-ends exist for every backfilled month. When a backfilled FY completes,
  its FY-close Stock Summary and Bills Receivable/Payable (as-on 31 March) are captured once at tier
  5, plus P&L / BS if Q8 says yes.
- **Storage:** `tally_report_snapshots` keyed by `(workspace_id, report_type, as_on_date)`, plus
  `captured_at`, so a re-capture replaces rather than duplicates.
- **Missed month:** if Tally was never open in the month after a month-end, that month-end is captured
  late (the as-on date makes that safe). A tile whose baseline has no snapshot says "no month-end
  figure yet", never a wrong or zero baseline.
- Depends on probe 18 (does an as-on-past-date report return correct historical values), which now
  covers Bills Receivable/Payable and Stock Summary as well as TB.

### Dates and clocks
- Tally dates are calendar dates with no time zone. Every FY, month and "as-on" boundary is worked
  out on those dates, never on timestamps.
- The agent's schedule (local midnight, the 1st of the month, 1 April) runs on the Tally PC's local
  clock. The product is India-only (decision 15), so that is IST in practice.
- The server stores timestamps as UTC (`timestamptz`) and shows "last synced X ago" and "as of
  18 Sep, 9:12 pm" in IST (`Asia/Kolkata`).
- Each heartbeat carries the PC's clock. A skew of more than a few minutes shows up in diagnostics
  (§4 Windows agent); the schedule still follows the PC clock.

### Work priority (never slow the accountant)
One request at a time, small chunks, explicit field lists, no imports ever, back off after any
timeout. Every piece of agent work has a tier, and each cycle works top-down:

| Tier | Work | Rule |
|---|---|---|
| 1 | Incremental fetch + mirrored re-read; outbox drain | Always first. If tier 1 had work this cycle, nothing below runs this cycle |
| 2 | User-confirmed work: "Re-check now", a confirmed resync (a whole-company resync's masters and 2-FY pass, or a single-FY resync) | Tiers 2–5 share the cycle budget, top-down |
| 3 | Parity remediation: targeted refetch, month-bisect calls, and the follow-up parity run after a completed resync or a reconcile that soft-deleted rows (§4.B) | Cycle budget |
| 4 | Daily pass: the 2-FY deletion compare, then the parity capture. Starts on the first connected cycle after local midnight | Cycle budget |
| 5 | Month-end snapshot capture; FY-close capture for a completed backfilled year | Cycle budget |
| 6 | One backfill or re-walk chunk, with its anchor TB | Only on a cycle where tiers 1–5 had nothing to do; at most one per cycle |
| 7 | Older-year deletion compare, round-robin (§3 "After a gap") | Same rule as tier 6, after it |

- The **cycle budget** (request count and seconds, sized from probe 9) is shared by tiers 2–5. Any
  timeout ends that cycle's work (circuit breaker in `gate.py`).
- **Internet down:** only tier 1's fetch and mirrored re-read run, into the outbox. Tiers 2–7 need
  server acks, so they wait.
- The history backfill is the lowest-priority loading work (decision 7b), because nobody is waiting
  on a 2019 voucher. Only the older-year deletion compare ranks below it.

## 4. Architecture

### Windows agent (Python)
- Reuses `backend/tally_bridge/{client,request_builder,response_parser,exceptions,models}.py` + helpers `sanitize_xml`, `parse_amount`, `detect_error` (`response_parser.py`). New pure module `backend/tally_bridge/sync/` for sync builders/parsers. The build excludes `writer.py`, `import_builder.py`, `mock_handler.py`.
- `gate.py`: one request at a time, per-request timeouts, backoff, circuit breaker, a cheap health + company-GUID check before any heavy call (LESSONS §15 popup-freeze).
- `extractor.py`: explicit fields (no `*`, LESSONS §5; no `$$InDateRange`, §3). Day/month chunks capped at about 5k vouchers (never more than 10k).
- `change_detector.py`: compare company counters with saved cursors.
- `scheduler.py`: the work-priority tiers and the per-cycle budget (§3 "Work priority").
- `diagnostics.py`: every heartbeat carries the agent version, TallyPrime version, last error code, circuit-breaker state, outbox depth and PC clock, and no business data. A tray action, "Send diagnostics", uploads a redacted log bundle for support: request timings and error shapes, with no voucher, ledger or party content (decision 14, R20).
- `state.py` (SQLite): company, cursors, first-sync chunk status, outbox of gzipped batches, sync log.
- `uploader.py`: batches of at most 500 objects / 5 MB gzipped (the server's ingest limit), with a `batch_id` idempotency key. The cursor advances only after the server acks.
- `auth.py`: device token stored via Windows DPAPI (`keyring`).
- `service.py` (pywin32) + `tray.py` (pystray), talking over localhost / named pipe. A service in session 0 can still reach `localhost:9000`, but Tally itself needs a logged-in Windows session (see R11).
- `updater.py`: version check, signed download, sha256 check, `--selftest` after update, rollback on failed self-test.

### Cloud (FastAPI + Postgres)
- `backend/api/agent_auth.py`: `POST /api/agent/auth/login` (reuse `verify_password` from `backend/utils/auth.py` and `_check_rate_limit` from `backend/api/auth.py`) and `/refresh` with a rotating, revocable device token (hash stored). Plus `GET/DELETE /api/devices`.
- `backend/api/sync.py`:
  - `POST /api/sync/company` (bind one workspace)
  - `POST/PATCH /api/sync/{ws}/runs` (progress). Carries `kind` = `first_sync | incremental | backfill | full_resync`, so a slow history backfill is never mistaken for live sync progress.
  - `POST /api/sync/{ws}/batches` (upsert on `(workspace_id, guid)`, only when `alter_id >=` the stored one; voucher lines replaced in the same transaction). Batches are tagged with their run's `kind`; a **`backfill` batch must not advance `last_synced_at`** (decision 7b) — otherwise the UI would claim "synced 2 min ago" while no fresh data arrived. A `full_resync` batch advances it only for chunks inside the current 2-FY window (§3).
  - `PATCH /api/sync/{ws}/coverage` (the agent reports a completed FY/month chunk; the server advances the backfill watermark in `sync_fy_coverage`)
  - `POST /api/sync/{ws}/reconcile` (soft-delete missing records, return mismatches to refetch, and return the ledgers whose mirrored balances the agent must re-read)
  - `POST /api/sync/{ws}/parity` (agent posts snapshots + before/after counters; the server runs the
    comparison synchronously and returns the remediation list — §4.B)
  - `GET /api/workspaces/{id}/sync-status` (UI polling; carries the sync state, the **integrity** state (§4.B) and the **backfill** state — `{oldest_available_fy, oldest_complete_fy, books_from, percent, state}` — for the History card and the Data integrity card's verified span in §12.4)
- `get_current_device` dependency beside `get_current_user` (`backend/api/dependencies.py`). A device may only post to its own workspace.
- **Ingest limits:** `/batches` rejects a body over the agent's own cap (5 MB gzipped / 500 objects) with 413. Each device has a request rate limit, and a 429 makes the agent back off as it would after a Tally timeout. Both limits are `config.py` settings.
- **Migration 006** (after `005_voucher_revision_file_id.py`) tables:
  - Agent and sync bookkeeping: `agent_devices`, `sync_runs`, `sync_batches`
  - Masters: `tally_groups`, `tally_ledgers`, `tally_stock_items` (+ stock groups/units/voucher types). `tally_ledgers` also stores Tally's own GST classification (`tax_type`, `gst_duty_head` — probe 23) so the GST tile never matches ledgers by name
  - Vouchers: `tally_vouchers`, `tally_voucher_ledger_lines`, `tally_voucher_inventory_lines`, `tally_bill_allocations`
  - Snapshots: `tally_report_snapshots`
  - Integrity: `parity_runs`, `parity_lines` (§4.B)
  - Coverage / backfill watermark: **`sync_fy_coverage`** — one row per `(workspace_id, fy_start, fy_end)` with `state` (`pending | running | resyncing | complete`), `months_complete`, `months_total`, `completed_at`. `pending`/`running` = never fully loaded (queries answer "still loading"); **`resyncing` = already loaded, being refreshed in place** (queries answer normally with a caveat, parity skips it); `complete` = loaded and eligible for parity. This is the **authoritative watermark** that §4.A's "still loading" rule and §4.B's watermark-bounded parity both read — through two different edges (§3 "What a full resync does…"); `workspace.config.backfill` is only a denormalised copy for cheap status reads. `sync_runs` gains a `kind` column (`first_sync | incremental | backfill | full_resync`).
  - Every row has `guid`, `alter_id`, `is_deleted`, `raw` JSONB, with indexes on `(workspace_id, date)`, `(workspace_id, ledger_guid)` (every join is on GUID, R9) and `(workspace_id, ledger_name)` (name search only).
  - If probe 9 / 21 volumes make computed chat queries slow, add a per-ledger monthly totals table maintained on ingest. Decided in the S1 spec.
  - **All money columns are `Numeric(18,2)`, never Float** (§4.B storage).
  - **All amount columns hold the INR base amount** (decision 15). Voucher lines carry no currency column; where a voucher is in foreign currency, the original currency code, face value and Tally's own rate stay in `raw` JSONB for drill-down and are never aggregated. A probe must confirm the INR base amount is present on forex voucher lines (probe 22).

### Web (S3)
- States: **connecting** (waiting for the first connection) / **syncing %** / **error** / **Tally offline** / **ready** / **stale** / **restore detected** (§3 "Company identity changes"), each combined with chat locked or unlocked. A pending **Re-link** prompt (same name, new GUID) is shown alongside whichever state applies.
- "Last synced X ago" is always visible once ready; a stale badge appears when the last sync is old (threshold: open question Q3).
- Synced workspaces show the "writing not available yet" note (decision 10).
- Integrity state (§4.B) overlays these as an independent dimension — see §12.9.
- Backfill state (decision 7b) is a third dimension — History card in §12.4, matrix in §12.9.
- Navigation and page layout: see §12.

###

This is the largest part of §4, so it is broken into four sections which follow immediately below:

| Section | Covers |
|---|---|
| **§4.A** | Where every answer comes from — the three sources (computed / mirrored / snapshot), the routing table for all 19 tools (18 data tools + the `resolve_date_range` helper), freshness labelling, and the rules for dates outside the synced window |
| **§4.B** | The integrity (parity) system — rungs 0–3, the quiescence guard, cause classifier, month-bisect, escalation ladder, schedule, schema, surfacing |
| **§4.C** | Dashboard & Insights (S5) — the KPI tiles, and the demands / reconciliation / alerts pillars |
| **§4.D** | Code gaps this depends on |
| **§4.E** | Testing |

In brief: every answer comes from one of three sources, each labelled with its freshness, and an
integrity ladder proves our computed numbers still agree with Tally's own.

---

## 4.A Where every answer comes from (S4)

Three sources. Every tool result **must declare which one it used and an "as of" time**. Today no
tool result carries any freshness metadata at all — `ReportResponse` has `from_date`/`to_date` but
TB/P&L/BS never populate them (`reports.py:61,77,124`); only `cash_flow` does (`:203-204`).

| Source | Meaning | Freshness label shown to the user |
|---|---|---|
| **Computed** | SQL over `tally_voucher_ledger_lines` / `tally_vouchers` | "as of last sync, 8 min ago" |
| **Mirrored** | A Tally field copied verbatim at sync time (`LEDGER.ClosingBalance`, `STOCKITEM.ClosingValue`). Entering a voucher does not bump the ledger's own AlterID, so an `AlterID > cursor` masters fetch would never refresh these. Instead, every cycle that syncs vouchers re-reads them for the ledgers and stock items those vouchers touch (§3 cycle table): one collection call filtered to those names. That includes vouchers queued in the outbox while offline, and vouchers soft-deleted by the deletion check (§3 "After a gap"). Probes 1/4 confirm the AlterID behaviour | "as of last sync, 8 min ago" — true only because of that re-read |
| **Snapshot** | A whole `TYPE=Data` report captured and stored | "Tally's own figure as of 18 Sep, 9:12 pm" |

Routing for the 19 tools in `backend/agents/tools.py` (18 data tools + one date helper):

| Source | Tools |
|---|---|
| **None** (pure date math, no data read) | `resolve_date_range` — unchanged; carries no source or `as_of` label |
| **Mirrored** | `search_ledger`, `list_all_ledgers`, `list_account_groups`, `list_stock_items`, `list_companies` — masters and balances copied from Tally |
| **Computed** | `get_day_book`, `get_ledger_transactions`, `get_sales_register`, `get_purchase_register`, `get_payment_register`, `get_receipt_register`, `get_cash_flow` |
| **Snapshot** | `get_balance_sheet`, `get_profit_and_loss`, `get_stock_summary`, `get_outstanding_receivables`, `get_outstanding_payables` (snapshot only, rule 1); `get_trial_balance` (snapshot, or computed where rule 1 allows) |

`get_cash_flow` is **computed**: movements on the Cash-in-Hand and Bank Accounts ledgers over the
period, grouped by the other ledger's top-level group. It has no stock or bill-ageing dependency, so
a computed figure can match Tally's, and no Cash Flow snapshot is taken. Its layout may differ from
Tally's own Cash Flow report; R25's eval run checks this.

Two rules the rewritten handlers must enforce:

1. **A snapshot tool only answers at its snapshot's own date.** "TB as on 30 June" cannot be served
   from a snapshot taken today. The handler picks a matching snapshot — the routine month-end set
   (§3 "Month-end snapshots") or one left by month-bisect (§4.B) — or, **only where a computed
   answer can match Tally**, computes and labels the result *computed*.
   - **No computed fallback for anything that depends on stock valuation or bill ageing.** Tally
     values closing stock when the report opens and our recomputation can differ (R5), and no
     computed bill ageing is designed. So `get_stock_summary`, `get_profit_and_loss`,
     `get_balance_sheet`, `get_outstanding_receivables` and `get_outstanding_payables` answer **only
     from a snapshot**. No snapshot for the requested date → *"I have Tally's own figures for these
     dates: …"* (the snapshot dates held), never a recomputed figure. Which past dates are held for
     P&L / BS is Q8.
   - `get_trial_balance` may be computed (ledger balances only). If probe 16/18 show Tally's TB
     carries a closing-stock line, that line comes from the Stock Summary snapshot for the same
     date, and with no such snapshot the TB is not computed either.
   - **Computed balances are worked backwards from Tally's current balance.** For a balance-sheet
     ledger, balance(D) = mirrored `ClosingBalance` − Σ our lines dated after D (same filters as
     rung 1). Our lines only start at the available edge, so a forward sum would miss all earlier
     history (R30's problem, in chat). The backwards sum needs only the lines *after* D, and those
     are all held whenever D is on or after the available edge. So it needs no opening anchor, and
     works at ledger level during the backfill and in `resyncing` years. A computed TB is the group
     rollup of these.
   - Nominal (P&L) ledgers read `ClosingBalance = 0` and reset each FY: Σ lines from FY start to
     the date, valid when that FY start is on or after the available edge; otherwise rule 2.
   - **Depends on probe 16** (mirrored balance = Tally's TB). If probe 16 fails, computed balances
     fall back to the forward formula from a stored month-end TB (§4.B "The opening anchor"), group
     level only, and ledger-level past balances answer "still loading" (rule 2).
   - Opening anchors are **for parity only**. A backwards-computed balance cannot check anything,
     because at today's date it equals Tally's figure by construction. Parity has to compare an
     independent forward sum (§4.B).
   - The Cash & bank tile's month-end baseline uses this same rule (§4.C), so the tile and its chat
     click-through always agree.
2. **Out-of-window dates fail loudly — and the two kinds of "out of window" say different things**
   (decision 7b). Handlers check the **`sync_fy_coverage`** watermark (§4 Cloud), not just the date:
   - **Not yet backfilled** (inside the books, behind the *available* edge — `pending`/`running`) →
     *"I'm still loading data from before Apr 2024 — about 60% done."* Never a partial total; a
     figure that silently grows later is worse than no figure.
   - **`resyncing`** (loaded, being refreshed) is **not** "out of window": answer normally with the
     restore or integrity caveat. A resync must never turn loaded data into "still loading".
   - **Before `books_from`** (data that does not exist in Tally at all) → *"This company's books
     start in Apr 2019."*
   - A range **straddling** the available edge is treated as not-yet-available, never silently truncated.
   - Neither case ever returns a silently wrong zero.

The existing full-FY-only restriction on P&L stays exactly as it is (LESSONS §1;
`reports.py:99-112` raises for partial periods and points at the voucher registers).

---

## 4.B The integrity (parity) system

### Why it is not optional
Tally stores no closing balances — it computes them when a report opens (R5). We recompute from
vouchers. Divergence is **silent**: a dashboard shows ₹9,70,537 receivable with full confidence
while the real figure is ₹10,40,000. Parity is the only thing between a sync bug and a wrong number
the owner acts on. It is the primary mitigation for R5 and a partial one for R4, R6, R7, R8, R16, R25.

### What the code already gives us (verified 2026-09-18)
- `build_list_ledgers` (`request_builder.py:220`) already fetches `ClosingBalance` **and**
  `OpeningBalance` per ledger, parsed at `response_parser.py:95-110`. Every masters sync therefore
  yields **Tally's own per-ledger closing balance for free**. This is the best anchor we have, and
  it is why parity is a ladder rather than a single check.
- The TB report is **group-level only**: `tests/fixtures/trial_balance_live.xml` holds 7 top-level
  group rows (Capital Account, Current Liabilities, Fixed Assets, Current Assets, Sales Accounts,
  Purchase Accounts, Indirect Expenses), and `_wrap_report_envelope` (`request_builder.py:111`)
  sets no explode flag. TB alone can never localise a mismatch to a ledger.
- Nominal (P&L) ledgers always read `ClosingBalance = 0` (LESSONS §4 — auto-closed to P&L A/c).
  So rung 1 covers balance-sheet ledgers only, and rung 2 is *required* for Sales / Purchase /
  Expenses. The two rungs are complementary, not redundant.
- **Sign convention is already consistent end to end: debit = negative, credit = positive** — in the
  live TB export (`-1048846.53` in the debit column) and on the write path
  (`import_builder.py:242-243`). No conversion needed, but counter-intuitive enough that it needs an
  explicit test assertion.

### Rung 0 — double-entry invariant (no Tally call, every ingest)
For every voucher in every batch, `SUM(line.amount)` must equal `0.00`. Catches truncated payloads,
a dropped leg, a chunk that split mid-voucher. On failure the **batch is rejected, not stored** —
a half-voucher in the DB is worse than a missing one. Runs continuously, not daily.

### Rung 1 — ledger-level (free, highest resolution)
For each balance-sheet ledger:

```
computed = opening_balance_at_window_start
         + Σ line.amount from tally_voucher_ledger_lines
           where ledger_guid       = :guid
             and voucher.date     <= :as_on
             and voucher.is_cancelled = false
             and voucher.is_optional  = false
             and voucher.is_deleted   = false
             and line.is_deleted      = false
```

compared against the **mirrored** `tally_ledgers.closing_balance` captured in the same sync cycle.
Join on **GUID, never name** (R9 — renames and duplicate names under different parents).

Nominal ledgers are marked `not_applicable`, **never** `match` — otherwise a future bug hides
behind a false green.

### Rung 2 — group-level (covers what rung 1 cannot)
Roll our ledger balances up the `tally_groups` parent chain to the top-level groups and compare
against the stored TB snapshot. This is the only rung that covers Sales / Purchase / Indirect
Expenses.

It also asserts **the snapshot itself balances** (Σ debit + Σ credit ≈ 0). If Tally's own TB does
not balance, Tally is serving stale data (R4) and the whole run is discarded — not reported as our
error.

### Rung 3 — statement-level (deferred, decision 11)
Computed P&L net vs the full-FY P&L snapshot; computed asset/liability totals vs the BS snapshot;
Σ `tally_stock_items.closing_value` vs the Stock Summary snapshot; Σ pending bills vs the Bills
Receivable/Payable snapshots. Seed-company anchors kept for when this lands:
**₹9,70,537 receivable / ₹18,34,142 payable**.

### The quiescence guard — how we avoid crying wolf
Vouchers and the snapshot come from **separate** Tally calls. A voucher entered between them
produces a real numeric difference that is not a bug.

> Read the company's `AltVchId` / `AltMstId` **immediately before** the parity capture and **again
> immediately after**. If either moved, **discard the run** (`aborted_moving`) and retry next cycle.
> No alert, no remediation.

Parity also only runs when **the outbox is empty and the cursor is caught up** — otherwise we would
be comparing a knowingly-incomplete DB against a current Tally.

**Parity is bounded by the backfill watermark** (decision 7b). A half-backfilled company is
*expected* to disagree with Tally's all-time ledger closing balances, so:
- **The opening anchor** (parity only; chat computes backwards instead, §4.A rule 1). Our DB has no vouchers
  before the watermark, so what is missing is the **opening** balance, not the closing one. While
  `backfill.state != complete`:

  ```
  computed = tally_balance_as_on(watermark_date − 1)       ← from a TB snapshot as-on that date
           + Σ our lines where watermark_date <= voucher.date <= :as_on   (same filters as rung 1)
  compare against  current mirrored LEDGER.ClosingBalance (rung 1)  /  current TB (rung 2)
  ```

  - **Capture:** the anchor TB is taken as-on the day before the window starts at the end of the
    first sync (and again at the end of a whole-company resync's 2-FY pass), and with **each backfill
    or re-walk chunk** as-on the day before that chunk's month, so the anchor moves with the verified
    edge (one extra `TYPE=Data` call per chunk, same gate rules).
  - **Every anchor is kept** in `tally_report_snapshots`, not just the latest. Parity uses the one
    at the verified edge. Each anchor is a genuine month-end TB, so §4.A rule 1 can also serve "TB
    as on <that month-end>" from it as a snapshot. It is also what the probe-16 fallback computes
    forward from.
  - Once history is complete, `tally_balance_as_on(...)` is replaced by the ledger's books-start
    `OpeningBalance` (probe 16) and the comparison is the plain all-time one.
- **Per-ledger anchors during backfill depend on probe 16 or 17.** The TB is group-level only today
  (above), so the anchor exists only per **group**. Per-ledger anchors become available if **either**
  probe 16 shows `LEDGER.OpeningBalance` can be read as-on an arbitrary date, **or** probe 17 proves
  an exploded (ledger-level) TB is safe. Until one of them does:
  - Rung 1 is **suspended** while the backfill runs (ledgers marked `not_applicable`, never `match`).
  - Rung 2 carries the check at group level, and month-bisect does the localising.
  - Chat is unaffected: it computes ledger balances backwards from mirrored balances, which needs
    no anchor (§4.A rule 1).
  - Once either probe succeeds, rung 1 runs mid-backfill at ledger level using those openings.
- Rung 2 compares group rollups with the same opening-anchored formula.
- An FY becomes parity-eligible when its backfill completes, and gets one run at that point.
- **`resyncing` FYs are skipped.** Parity reads the *verified* edge (oldest contiguous `complete`
  FY, §3 "What a full resync does…"). A year being refreshed in place is half old copy, half new, so
  checking it would manufacture mismatches. It gets one run when it returns to `complete`.
- The Settings card says "Checked against Apr 2024 onwards" until the backfill finishes, so a green
  tick never overstates what was actually verified.

### Cause classifier — mismatch shape → likely cause → action
This is what turns a number into something actionable.

| Signature | Likely cause | Automatic action |
|---|---|---|
| Ledger in Tally, absent in our DB | masters sync gap (R6) | refetch masters |
| Ledger in our DB, absent in Tally | ledger deleted | run `/reconcile` soft-delete |
| One ledger differs | a missed voucher or edit on that ledger | targeted refetch of that ledger's vouchers for the FY |
| Two ledgers differ by equal-and-opposite amounts | one whole voucher missed or duplicated | month-bisect, then refetch that month |
| Many ledgers differ by a constant | opening balances wrong | refetch masters + openings (probe 11) |
| Difference equals an exactly cancelled/optional voucher | our filter is inverted (R16) | engineering flag — code bug, not a sync gap |
| Every ledger matches but our rollup total does not | our group-tree walk is wrong | engineering flag |
| Tally's own TB does not balance | stale long-running Tally (R4) | discard run; tray says "Restart TallyPrime" |

### Month-bisect — locating a mismatch cheaply
Request a TB as-on each month-end of the affected FY (12 cheap `TYPE=Data` calls at tier 3, spread
across cycles, one at a time through `gate.py`) and compare against our computed balances at the same
dates. The first month where they diverge is the month to refetch. Bounded cost: month-ends already
held by the routine month-end set (§3 "Month-end snapshots") are reused, so only missing ones cost a
call, and every TB it fetches is stored in `tally_report_snapshots` for §4.A rule 1 to reuse.

### Escalation ladder — confirm before you alarm
1. **First mismatch** → state `suspect`. **Invisible to the user.** Enqueue remediation, re-check
   next cycle.
2. **Still mismatched after remediation** → state `alert`. Now the user sees it.
3. **Two consecutive failed heals** → *offer* a full resync of the affected FY. **The user decides**
   (decision 12) — it is hours of Tally load.
4. **Mismatch survives a full resync** → `hard_alert` + internal engineering flag. This is a real
   bug or a Tally quirk; no amount of refetching will fix it.

Any successful re-check drops the state straight back to `ok`.

### Schedule and trigger — there is no scheduler
Confirmed 2026-09-18: there is **no** Celery / APScheduler / cron / BackgroundTasks anywhere in the
backend. The only lifecycle hook is the FastAPI lifespan (`backend/main.py:24-69`). So parity is
**agent-triggered, server-executed**:

- As the second half of the daily pass (§3 "Work priority", tier 4), after the 2-FY deletion
  compare, the agent captures the snapshots plus the before/after counters and posts them to
  `POST /api/sync/{ws}/parity`. The daily pass starts on the first connected cycle after local
  midnight.
- The server runs the comparison **synchronously inside that request** and returns the remediation
  list, which the agent then executes.
- No new infrastructure, and it naturally cannot run while Tally is closed — which is correct,
  because parity is meaningless then.
- Also triggered by: a completed full resync or a reconcile that soft-deleted rows (tier 3), and a
  "Re-check now" button in Sync / Settings (tier 2).

### Storage (migration 006 additions)

**`parity_runs`** — `id` UUID pk, `workspace_id` FK+index, `sync_run_id`, `as_on_date`, `rung`,
`status` (`ok|suspect|alert|hard_alert|aborted_moving`), `lines_compared`, `mismatch_count`,
`max_abs_diff`, `net_diff`, `counters_before` JSONB, `counters_after` JSONB, `remediation` JSONB,
`started_at`, `finished_at`, `created_at`.

**`parity_lines`** — `id`, `run_id`, `workspace_id`, `scope` (`ledger|group|statement`), `guid`,
`name`, `our_amount`, `tally_amount`, `diff`, `verdict`
(`match|mismatch|missing_in_db|missing_in_tally|not_applicable`), `cause`, `remediation_status`.

Both follow the 004/005 conventions exactly: UUID pk, `workspace_id` FK + index, `created_at` with
`server_default=sa.func.now()`, compound indexes via `__table_args__`, bare FKs with no
`relationship()`.

- **Money columns are `Numeric(18,2)`, never Float.** Everything in the codebase today is a Python
  float (`parse_amount`, `response_parser.py:19`); comparing floats at paise resolution across
  hundreds of thousands of voucher lines manufactures phantom mismatches.
- `workspace.config` gains `last_parity: {state, checked_at, as_on, mismatch_count}` for a cheap read
  on the status endpoint (matches the existing `sync_state` pattern).
- **Retention:** runs kept 90 days; matching lines pruned after 7 days (a daily ledger-level run on a
  large company is thousands of rows); mismatching lines kept the full 90.
- **Tolerance:** `PARITY_TOLERANCE_PAISE` setting, default `100` (₹1.00), applied per line **and** to
  the grand total. Follows the `config.py` convention (new labelled section, inline comment).

### Surfacing

| Surface | `ok` | `suspect` | `alert` | `hard_alert` |
|---|---|---|---|---|
| Sync / Settings "Data integrity" card | green "Matches Tally as of 18 Sep, 9:12 pm" | amber "Re-checking a difference with Tally" | red "3 ledgers don't match Tally" + affected list + "Re-check now"; **"Re-sync this year" only after two failed heals** (escalation step 3, decision 12) | red card + affected list + "Contact support"; internal engineering flag raised |
| Dashboard / Insights | nothing | nothing | amber ribbon, scoped: "Receivables may be off — we're re-checking with Tally" | same ribbon, stronger wording |
| AI Chat | nothing | nothing | tools touching an affected ledger return a `warning`; the answer carries a one-line caveat | same caveat |
| Tray | — | — | only for the stale-Tally cause: "Restart TallyPrime to refresh" | — |

Three rules:
- **`suspect` is invisible.** Showing it means an alarm every time someone posts a voucher mid-capture.
- **Chat is never blocked** by an integrity alert (decision 13). A caveated answer beats no answer;
  blocking is reserved for the first sync.
- **The wording never implies their books are wrong.** The suspicion is always on *our copy*.

Implementation note: there is no notification system today — the only backend→frontend state channel
is the 30s health poll in `TallyStatusBadge.tsx:10`. Integrity state rides on
`GET /api/workspaces/{id}/sync-status`, and the chat caveat reuses the existing
`warnings: string[]` pattern from `VoucherReviewCard.tsx:37` rather than inventing a new mechanism.

### Internal ops signal
Per decision 14: workspace id, rung, cause, mismatch count and magnitude only. **No ledger names, no
party names, no amounts tied to identifiable accounts.** Enough to spot a systemic sync bug across
customers without reading anyone's books (R20, Q6).

---

## 4.C Dashboard & Insights (S5)

Answers Q13. Two distinct pages, two distinct jobs:

| Page | Job | Character |
|---|---|---|
| **Dashboard** | **KPIs** — what the numbers are right now | Fixed, always the same tiles, glanceable |
| **Insights** | **Demands, reconciliation, alerts** — what needs attention | Variable, a ranked list of things to act on; empty when all is well |

The distinction: Dashboard tells you *how the business is doing*; Insights tells you *what to do
today*. A number belongs on the Dashboard; a number that implies an action belongs in Insights.

### Dashboard — the KPI set
Every tile names its source per §4.A (computed / mirrored / snapshot) and carries the freshness
label. All figures are INR base amounts (decision 15). Cancelled and optional vouchers are excluded
from every computed tile (R16) — that exclusion is a property of the query layer, not of each tile.

| Tile | Definition | Source | Comparison |
|---|---|---|---|
| Sales | Sum of sales vouchers, MTD and YTD | computed | vs same period last FY |
| Purchases | Sum of purchase vouchers, MTD and YTD | computed | vs same period last FY |
| Gross margin | Sales − cost of goods sold, as ₹ and %. COGS = opening stock + purchases − closing stock, with the stock values taken from Tally's Stock Summary snapshots at the period's start and end | computed (sales, purchases) + snapshot (stock values) | vs same period last FY, only when stock snapshots exist for all four dates; otherwise "no comparison yet" |
| Cash & bank | Closing balance of the ledgers under Cash-in-Hand + Bank Accounts | mirrored (current); computed (month-end baseline — see notes) | vs last month-end |
| Receivables | Total outstanding, split current vs overdue (overdue = past the due date Tally reports on each bill — probe 23) | snapshot (Bills Receivable) | vs last month-end |
| Payables | Total outstanding, split current vs overdue (same due-date rule) | snapshot (Bills Payable) | vs last month-end |
| Stock value | Closing stock value | snapshot (Stock Summary) | vs last month-end |
| GST position | Output tax − input tax for the period, by duty head (IGST / CGST / SGST / cess). Output = GST-ledger lines on sales-side vouchers (sales, credit notes); input = those on purchase-side vouchers (purchases, debit notes); tax payments and set-off journals excluded. GST ledgers are identified by Tally's own classification (probe 23), never by name. Indicative, not a GSTR-3B figure | computed | current period |
| Top customers | Top N by sales for the period | computed | — |
| Top items | Top N by value sold for the period | computed | — |
| Sales trend | Monthly sales, last 12–24 months | computed | — |

Notes:
- **Period selector** (this month / this FY / last FY / custom) applies to the period-scoped tiles;
  balance tiles are always "as on" the latest available date.
- **Multi-year comparisons become possible as the backfill fills in** (decision 7b). A comparison
  whose baseline period is behind the watermark shows the "still loading" treatment rather than a
  wrong or absent baseline (§4.A rule 2).
- **"vs last month-end" baselines** come from the routine month-end snapshots (§3 "Month-end
  snapshots"). No snapshot for that month-end → "no month-end figure yet", never a zero baseline.
- **Exception — Cash & bank.** The month-end TB holds only the top-level groups (Cash-in-Hand and
  Bank Accounts sit inside Current Assets, §4.B), so it cannot supply this baseline. The baseline
  is **computed backwards** by §4.A rule 1: the current mirrored balance minus our lines dated after
  the month-end, labelled *computed*. It is the same rule chat uses, so the tile and its chat
  click-through give the same figure.
- **Gross margin stock values:** MTD uses the last month-end Stock Summary and the current one; YTD
  uses the 31 March snapshot the first sync captures (§3 "Month-end snapshots"). A boundary with no
  stock snapshot → "no figure yet". Sales − purchases is never shown as margin. A company with no
  inventory has zero stock, so its margin is sales − purchases by definition.
- Every tile is **clickable through to AI Chat** with the equivalent question pre-filled, so the
  dashboard is an entry point to the chat rather than a dead end.

### Insights — three pillars
A ranked list of items needing attention, each with a plain-language statement, the evidence, and a
link that opens it in AI Chat. **Insights is empty when nothing needs attention** — it must never
manufacture findings to look busy.

1. **Demands** — money to chase or to pay: overdue receivables by party and age, overdue payables,
   large bills approaching due date, parties who have stopped buying. *(Scope needs confirming —
   see Q13a below.)*
2. **Reconciliation** — items that don't tie out **within the Tally data we hold**: party ledger
   balance vs the sum of its open bills, stock ledger movement vs Stock Summary value, a voucher
   with no bill allocation against a bill-wise party, suspense/unclassified ledger activity.
   *(External-source reconciliation is a different feature — see Q13b.)*
3. **Alerts** — anomalies and exceptions: unusual transaction size for a party, a sudden margin
   drop, negative stock, a ledger that changed after being reconciled, duplicate-looking vouchers.
   The **data-integrity alert** (§4.B) also surfaces here, alongside its dashboard ribbon.

Each item carries a severity, a first-seen date, and a dismiss action; a dismissed item does not
return unless its underlying condition changes.

### What Insights is not (v1)
- **Not** bank reconciliation against a bank statement — that needs an external file and Tally's own
  reconciliation mechanism, which probe work showed does not persist via voucher import (B1d,
  deferred, `docs/roadmap.md`).
- **Not** GST return reconciliation (GSTR-2B vs purchase register) — that needs GSTN data we do not
  sync. A candidate for a later slice, not v1.
- **Not** predictive forecasting.

Both exclusions matter because "reconciliation" usually means one of those two in Indian practice;
v1's reconciliation is strictly *internal consistency within the synced books*.

---

## 4.D Code gaps this section depends on
(Also listed in §9.)

1. **`parse_amount` turns anything unparseable into `0.0`** (`response_parser.py:19-26`). A parse
   failure becomes a legitimate-looking zero — which can produce a **false parity match** or a
   silently wrong balance. The sync parsers must distinguish missing from zero and reject the batch.
2. **No freshness metadata on any tool result.** `ReportResponse.from_date/to_date` are set only by
   `cash_flow` (`reports.py:203-204`); `raw_response` is never populated. §4.A needs `source` +
   `as_of` on every result.
3. **Money is float throughout.** Sync tables and parity need `Decimal` / `Numeric`.
4. **`bills_receivable` / `bills_payable` silently fall back to `date.today()`** on an unparseable
   bill date (`reports.py:144,167`) — makes rung-3 bill parity non-deterministic.
5. **`parse_stock_summary` returns `closing_quantity` while `StockItem` declares `closing_balance`**
   — the two stock paths disagree on the key name; the sync schema must pick one.

---

## 4.E Testing (per CLAUDE.md "test reality, not an ideal")

- **Unit — one fixture per cause signature**, not one happy path: missing ledger, extra ledger,
  single-ledger diff, offsetting pair, constant opening shift, unbalanced Tally TB, all-zero nominal
  ledgers. Tolerance boundaries at ₹0.99 / ₹1.00 / ₹1.01. An explicit **debit-is-negative** assertion.
- **Fixtures mirror the seed company:** custom sub-groups (`National Creditors` / `Local Creditors`),
  duplicate ledger names under different parents, non-bill-wise parties, cancelled **and** optional
  vouchers.
- **Mock Tally:** stateful sync mode returns a deliberately disagreeing TB → assert detect →
  classify → targeted refetch issued → heal → back to `ok`. Plus a counters-moved run asserting
  `aborted_moving` and **no** alert.
- **Mid-backfill parity (R30) — the regression this design exists to prevent:** with
  `backfill.state = running`, a mock company whose all-time `LEDGER.ClosingBalance` is deliberately
  far from the watermark-bounded computed balance must produce **`ok`**, not an alert. Assert the
  comparison used the watermark-dated TB snapshot as the opening and not the all-time figure, and
  that rung-1 lines are `not_applicable` (not `match`) while neither probe 16's as-on reading nor
  probe 17 is proven. Then complete the
  backfill and assert the all-time anchor switches on.
- **Identity changes (§3):** GUID mismatch with a different name → skip, nothing uploaded; same name
  with a new GUID → skip + Re-link prompt, no resync until confirmed; counters below the cursor with
  the same GUID → `restore_detected`, incremental stopped, resync *offered*, never started.
- **DB integration** (`TEST_DATABASE_URL`): parity rows written, retention pruning, cross-tenant
  isolation, `Numeric` round-trip. Plus coverage: `PATCH /coverage` advances `sync_fy_coverage`
  idempotently (a replayed chunk ack doesn't double-count), a `kind = backfill` batch **does not**
  move `last_synced_at` while an `incremental` one does, and the watermark a tool reads matches the
  table after a partial FY.
- **Round-trip E2E:** first sync → `ok` → delete a voucher in mock Tally *without* reconcile →
  parity detects it → reconcile → `ok`.
- **Refresh round-trip** (CLAUDE.md rule 7): act → reload → the Settings card and the dashboard
  ribbon show the same state, rehydrated from the DB.
- **Real-data parity:** computed TB vs `tests/fixtures/trial_balance_live.xml`; seed residuals
  ₹9,70,537 receivable / ₹18,34,142 payable.
- **Playwright:** integrity card × {ok, suspect, alert, hard_alert, never-run} × 3 viewports, each with a
  `// VISUAL CHECKLIST:` block and content assertions before the screenshot; main agent reviews
  every PNG.

## 5. Sub-projects (each: spec → plan → build, later)
| # | Scope | Depends on |
|---|---|---|
| S0 | Live-Tally probe + capture real fixtures (probes 1–23, incl. parity probes 16–20, full-history 21, forex 22, GST / due dates 23) | none |
| S1 | Cloud: sync tables, device auth, ingest API + ingest limits, sync runs, **parity tables + comparison engine + `/parity` endpoint** (§4.B) | S0 (batch format; probes 16, 17, 18 for parity — decision 11) |
| S2 | Windows agent (extractor, change detector, outbox, service/tray, updater, **work-priority scheduler**, diagnostics, **parity capture + quiescence counters + remediation execution**, **history backfill walker + pre-emption**) | S0 (parallel with S1; probe 21 for backfill) |
| S3 | Web shell with the new navigation (§12) + onboarding + sync status + **Data integrity card + History card** (§12.4) | S1 |
| S4 | AI chat on our DB — tool routing per §4.A, **watermark-aware "still loading" behaviour** (decision 7b), integrity caveats per §4.B | S1 |
| S5 | BI dashboards (incl. the integrity ribbon) | S4 query layer |

Parity (§4.B) is deliberately **not** its own sub-project: rung 0 belongs to the S1 ingest path, the
comparison engine is S1, the capture and remediation are S2, and the surfacing is S3/S4/S5. Building
it as a separate slice would mean shipping an ingest path we cannot yet verify.

## 6. Out of scope (v1)
- More than one company per PC or per workspace; syncing a company that's loaded but not active.
- Any write to Tally from sync-agent workspaces.
- Live Tally queries from chat **on sync-agent workspaces** (everything comes from our DB). Live-connected and demo workspaces keep today's path (decision 8).
- Real-time tunnel (replaced by sync).
- Billing / pricing for the BI layer.
- Mac/Linux agent; Tally versions older than TallyPrime 7.
- Cost-centre reporting, godown-wise stock and batch-wise stock. Those allocations are kept in `raw` for drill-down but not modelled or aggregated; the Stock Summary snapshot is company-level.
- **Non-Indian companies, and any multi-currency reporting** (decision 15). India-only: Indian FY, GST, Indian number formatting, INR-only figures. Forex vouchers are reported at their INR base amount; the foreign face value is drill-down detail in `raw`, never aggregated. No rate tables, no conversion at read time.

## 7. Risks (detailed)

### 7.1 Summary
| ID | Risk | Likelihood | Impact | Status |
|---|---|---|---|---|
| R1 | Tally must be open to sync | Certain | Medium | **Accepted** |
| R2 | Wrong company's data mixed into workspace | Medium | **Critical** | Handled (GUID check) |
| R3 | Agent slows or freezes Tally | High | **Critical** | Mitigated, prove in S0 |
| R4 | Long-running Tally returns stale data | Medium | High | Mitigated |
| R5 | Our numbers differ from Tally | High | **Critical** | Mitigated (snapshots + parity) |
| R6 | Incremental change detection misses changes | Medium | High | Mitigated, prove in S0 |
| R7 | Deleted vouchers stay in our DB | High | High | Mitigated (daily compare) |
| R8 | Backup restore / counters reset | Medium | High | Mitigated (full resync offered, never automatic) |
| R9 | Ledger renames and duplicate names | Medium | Medium | Unknown, prove in S0 |
| R10 | Tally setup friction (XML server off) | High | Medium | Onboarding |
| R11 | Tally needs a logged-in Windows session | High | Medium | Onboarding + accepted |
| R12 | Two Tally instances → port conflict | Low | Medium | Detect + message |
| R13 | Company names with `&` / quotes break requests | Medium | High | Code fix + probe |
| R14 | Hindi / Unicode text garbled | Medium | Medium | Test in S0 |
| R15 | Compound units crash export | Low | High | Test in S0 |
| R16 | Cancelled / optional vouchers counted | Medium | High | Filter + test |
| R17 | Antivirus / SmartScreen blocks installer | High | High | Signing |
| R18 | Auto-update breaks or is hijacked | Low | **Critical** | Signed + rollback |
| R19 | Device credential stolen / cross-tenant post | Low | **Critical** | Revocable tokens + isolation |
| R20 | Full books stored in our cloud (privacy) | Certain | High | Open question Q6 |
| R21 | Internet down / duplicate or lost uploads | High | High | Outbox + idempotency |
| R22 | First sync very long or never finishes | Medium | High | Resume + chunks |
| R23 | New FY never synced | Medium | High | Auto-add on 1 April |
| R24 | Web can't tell agent offline from Tally closed | High | Medium | Open question Q1 |
| R25 | Chat answers regress after moving to our DB | Medium | High | Parity + eval |
| R26 | Tally popups / Educational mode / version differences | Medium | Medium | Error shapes in S0 |
| R27 | Data volume and DB cost for big companies | Medium | **High** (raised by decision 7b) | Measure full books span in S0 (probe 21) |
| R28 | No write flow on synced workspaces | Certain | Medium | **Accepted** for v1 |
| R29 | Background backfill never completes | Medium | Medium | **Accepted** — honest progress, degrades gracefully |
| R30 | All-time ledger balances invalid as a parity anchor mid-backfill | **Certain** | High | Watermark-bounded parity; gated on probes 16–18 |

### 7.2 Detail

**R1: Tally must be open to sync (accepted)**
- *What:* all tools need the company open in Tally. If the accountant closes Tally at 6pm, nothing syncs until it's opened again.
- *Evidence:* every Tally sync tool requires the company open (tally-database-loader, Biz Analyst, Suvit help).
- *Handling:* by design (decision 5) we skip quietly. "Last synced X ago" tells the owner how fresh the data is.
- *Residual:* data can be hours or days old. Acceptable for v1.

**R2: Wrong company's data mixed into the workspace**
- *What:* the accountant opens a different company, and the agent uploads its vouchers into our workspace, mixing two sets of books.
- *Impact:* critical. Wrong numbers, and one client's data shown in another's workspace.
- *Handling:* before every fetch, read the open company's GUID and compare it with `tally_company_guid`. On mismatch, skip. The server also rejects batches whose company GUID doesn't match the workspace.
- *Prove in S0:* probe 2 (cheap GUID read, response when no company is open).

**R3: Agent slows or freezes Tally**
- *What:* heavy XML requests freeze Tally's UI while the accountant is typing. Customers uninstall.
- *Evidence:* Tally's XML server handles one request at a time. tally-database-loader batches day-wise, defaults to 5,000 vouchers, and warns "never >10,000 or export may hang". LESSONS §15: popups freeze the XML server.
- *Handling:* `gate.py` sends one request at a time with per-request timeouts, a cheap health check first, and backoff/circuit breaker after any timeout. Chunks are capped at ~5k vouchers and auto-split to half-month/day when slow. Explicit field lists only; no imports.
- *Prove in S0:* probe 9 (latency/size per chunk, can the accountant keep typing).

**R4: Long-running Tally returns stale data**
- *What:* Tally left open for days can return old data through XML until it's restarted.
- *Evidence:* tally-database-loader notes.
- *Handling:* parity **rung 2** (§4.B) asserts that Tally's own TB snapshot balances. If it doesn't, Tally is serving stale data: the run is discarded rather than blamed on us, and the tray says "Restart TallyPrime to refresh".
- *Residual:* can't be fully detected — a stale Tally can still return an internally consistent but outdated TB. Document it in onboarding and support notes.

**R5: Our numbers differ from Tally**
- *What:* Tally doesn't store closing stock or ledger closing balances; they're computed when a report opens. Our recomputation (stock valuation method, opening balances, cancelled/optional vouchers) can differ.
- *Impact:* critical. One wrong number on the dashboard costs trust.
- *Evidence:* no closing-stock voucher exists; tally-database-loader recomputes WA/FIFO itself.
- *Handling:* show Tally's own report snapshots (Stock Summary, Bills Receivable/Payable, full-FY TB/P&L/BS) with an "as of" time (§4.A). The parity ladder (§4.B) proves our computed numbers still agree: **rung 0** double-entry invariant on every ingest, **rung 1** per-ledger vs Tally's own mirrored `ClosingBalance`, **rung 2** group rollup vs the TB snapshot. Mismatches are classified to a cause and remediated before anything is shown to the user. Sync opening balances/bills/stock (probe 11).
- *Prove:* seed residuals ₹9,70,537 receivable / ₹18,34,142 payable; computed TB = `tests/fixtures/trial_balance_live.xml`.
- *Note:* rung 1 cannot see revenue/expense ledgers (nominal accounts always read `ClosingBalance = 0`, LESSONS §4) — that is precisely why rung 2 is in v1 scope and not deferred.

**R6: Incremental change detection misses changes**
- *What:* we use company counters + `$AlterID > cursor`, and some edits don't come through.
- *Evidence:* tally-database-loader uses the same method, but its own notes call incremental "**not stable**" and it later fixed **missed master changes**.
- *Handling:* the GUID + AlterID compare (daily for the 2-FY window, round-robin for older years — §3 "After a gap") catches misses and refetches mismatches. Parity **rung 1** is the backstop that proves it worked: a missed voucher shows up as a single-ledger (or offsetting-pair) difference, which the cause classifier turns into a targeted refetch, and month-bisect localises it (§4.B). **During the backfill**, unless probe 16 or 17 gives per-ledger openings, rung 1 is suspended (decision 11); the backstop is then rung 2 at group level, with month-bisect doing the localising. Fallback if AlterID filtering fails: rolling re-pull of recent months + daily compare.
- *Prove in S0:* probes 1, 3, 4.

**R7: Deleted vouchers stay in our DB**
- *What:* a deleted voucher simply disappears from Tally, and no change counter tells us which one.
- *Handling:* the GUID list compare per month/master type (daily for the 2-FY window, round-robin for older years — §3 "After a gap") → `/reconcile` soft-deletes anything missing and returns the ledgers whose mirrored balances must be re-read. Parity **rung 1** independently catches a deletion the compare missed (the ledger's computed balance stays high while Tally's mirrored `ClosingBalance` drops), and its classifier routes the fix back through `/reconcile`. During the backfill, while rung 1 is suspended (decision 11), the same deletion shows up at group level in rung 2 and is localised by month-bisect.
- *Residual:* deletions show up within a day in the 2-FY window, and within one round-robin sweep for older years (§3 "After a gap") — not within 10 minutes.
- *Prove in S0:* probe 7 (vanishes, GUID never reused).

**R8: Backup restore / counters reset**
- *What:* the customer restores an older backup, counters go backwards, and our cursors are ahead of Tally.
- *Handling:* §3 "Company identity changes". Counters below our cursor with the same GUID → stop incremental, caveat the data, and **offer** a full resync (decision 12 — never automatic). A changed GUID is always a skip; a same-name, new-GUID company is only re-linked on the user's confirm (Q25), because a GUID mismatch must never be treated as "our company" (R2).
- *Prove in S0:* probe 13 (do GUID/MasterIDs change on restore).

**R9: Ledger renames and duplicate names**
- *What:* vouchers reference ledgers by name. After a rename, old vouchers may export the new name without their AlterID changing, so our copy keeps the old name.
- *Evidence:* tally-database-loader cascades renames into its voucher tables.
- *Handling:* store ledger GUID; on rename, cascade on the server by GUID. Fixtures must include duplicate names under different parents (CLAUDE.md "fixtures mirror the seed company").
- *Prove in S0:* probe 8.

**R10: Tally setup friction**
- *What:* Tally's XML server is **off by default** (F1 > Settings > Connectivity → "Acts as Server/Both", port 9000). Without it the agent sees nothing.
- *Handling:* an onboarding checklist in the agent (checks the port, shows step-by-step screenshots); the tray shows "Turn on Tally connectivity" when the port is closed but Tally is running.

**R11: Tally needs a logged-in Windows session**
- *What:* Tally is a desktop app. If the user logs off Windows, Tally closes. A Windows service (session 0) can still reach `localhost:9000` while Tally runs in the user's session.
- *Handling:* the onboarding note says to "disconnect, don't log off" for remote/RDP setups. Otherwise accepted under R1.

**R12: Two Tally instances → port conflict**
- *What:* two Tally instances (e.g. two versions) on one PC fight over port 9000, and the agent talks to the wrong one.
- *Handling:* the GUID check (R2) prevents wrong data. The tray shows "Tally port busy / wrong company" and lets the user set the port.

**R13: Company names with `&` or quotes break requests**
- *What:* the company name isn't XML-escaped in `_wrap_voucher_collection` (`request_builder.py:69`), `_wrap_report_envelope` (`:112`) and `build_ledger_vouchers` (`:270`), so a name like "A & B Traders" produces invalid XML.
- *Handling:* new sync builders always escape (as `:31`, `:179` already do). Also fix the existing builders.
- *Prove in S0:* probe 14.

**R14: Hindi / Unicode text garbled**
- *What:* party names, narrations and item names in Hindi or other scripts get corrupted by encoding.
- *Handling:* UTF-8 end to end, with Unicode fixtures.
- *Prove in S0:* probe 15.

**R15: Compound units crash export**
- *What:* stock items with compound units (e.g. Box of 10 Nos) have crashed Tally exports in other tools.
- *Handling:* explicit unit field lists; test on an item with compound units; skip and log if a single item fails.
- *Prove in S0:* probe 15.

**R16: Cancelled / optional vouchers counted**
- *What:* cancelled or optional (memo) vouchers get included in sales/profit totals.
- *Handling:* sync the `IsCancelled`/`IsOptional` flags (probe 3) and exclude them in every computed number. Fixtures include both.

**R17: Antivirus / SmartScreen blocks the installer**
- *What:* PyInstaller/Nuitka `--onefile` builds are commonly flagged, and unsigned installers get the SmartScreen "unknown publisher" warning.
- *Evidence:* since Aug 2024 an **EV certificate no longer skips SmartScreen**; reputation builds over weeks; Microsoft Artifact Signing is recommended (Microsoft Learn).
- *Handling:* `--onedir` build, code signing (Microsoft Artifact Signing), a consistent publisher name, and a support note for early customers.
- *Residual:* install friction for the first few weeks of customers.

**R18: Auto-update breaks or is hijacked**
- *What:* a bad update bricks every agent, or an attacker pushes a malicious update to PCs holding full books.
- *Handling:* signed updates, sha256 check, `--selftest` after update, automatic rollback, staged rollout.

**R19: Device credential stolen / cross-tenant post**
- *What:* the long-lived device token can read the full books. A bug could let one device post into another customer's workspace.
- *Handling:* the token is stored with DPAPI and the refresh token is rotating and revocable (hash stored). `get_current_device` allows posts only to the device's own workspace. DB tests cover the cross-tenant block and a revoked device getting 401.

**R20: Full books stored in our cloud (privacy)**
- *What:* we hold complete accounting data plus `raw` JSONB, including party names, amounts and narrations.
- *Handling:* TLS everywhere; encryption at rest and access policy to decide (Q6).

**R21: Internet down / duplicate or lost uploads**
- *What:* the upload fails mid-batch, is retried and duplicates data, or batches are lost.
- *Handling:* local outbox, a `batch_id` idempotency key, the cursor advances only after server ack, and upsert with the `alter_id >=` rule. The round-trip E2E restarts the agent and asserts no duplicates.

**R22: First sync very long or never finishes**
- *What:* a big company takes hours, and Tally closes midway, again and again.
- *Handling:* resume from saved chunk status, month chunks auto-split, and a progress screen. What the web shows before and during this is open question Q2.

**R23: New FY never synced**
- *What:* the sync range stays fixed to the first two FYs, so April onwards is missing.
- *Handling:* auto-add the new FY on the first connected cycle on/after 1 April (§3). Unit test with a fake clock.

**R24: Web can't tell agent offline from Tally closed**
- *What:* skips are quiet and the heartbeat is sent only when connected, so "PC off / agent uninstalled" looks the same as "Tally closed".
- *Handling:* open question Q1.

**R25: Chat answers regress after moving to our DB**
- *What:* rewriting the 18 data-tool handlers in `backend/agents/tools.py` (all except the `resolve_date_range` helper) changes answers that are correct today.
- *Handling:* the parity check vs Tally snapshots; run the existing eval scenarios against a synced seed company; tool-by-tool mapping (Q7). `get_cash_flow` needs particular attention: it moves from Tally's own report to a computed figure (§4.A).

**R26: Tally popups / Educational mode / version differences**
- *What:* an open popup blocks XML (LESSONS §15), Educational mode limits dates, and older Tally versions return different shapes.
- *Handling:* the gate treats these as "skip + backoff". Record the error shapes in S0 (probe 10). v1 supports TallyPrime 7+ only.

**R27: Data volume and DB cost**
- *What:* a large trader has hundreds of thousands of vouchers, and `raw` JSONB doubles storage. **Decision 7b (backfill all history to books start) makes this materially worse** — a twelve-year-old company is roughly 6× the two-FY estimate, and it is unbounded by design.
- *Handling:* measure bytes per month chunk in S0 (probe 9) and extrapolate to the **full books span** (probe 21), not just 2 FYs, before S1. Decide whether `raw` is kept permanently — and specifically whether it is kept for backfilled (older) years, where it is least likely to be needed. Q22 tracks this.
- *Residual:* an unusually old or high-volume company may need a per-customer storage ceiling. Not designed for v1; revisit once probe 21 gives real numbers.

**R28: No write flow on synced workspaces (accepted)**
- *What:* customers who sync can't use upload → Write to Tally on that workspace in v1.
- *Handling:* a clear UI note (decision 10). Revisit writes after the BI layer.

**R29: Background backfill never completes**
- *What:* the backfill only advances on cycles where nothing else needs doing and Tally is open. A customer who opens Tally for twenty minutes a day, or whose books go back fifteen years, may never reach `books_from`. The UI would sit at "still loading" indefinitely.
- *Likelihood:* Medium. *Impact:* Medium — chat and dashboards work throughout; only deep history is missing.
- *Handling:* it is a deliberate consequence of decision 7b's pacing (fresh data always wins, R3 is the bigger risk). Settings shows honest progress ("2019-20 onwards still loading, 60%") and an estimated remaining span rather than a false ETA. If progress stalls for N days with the agent otherwise healthy, Settings suggests leaving Tally open longer.
- *Residual:* accepted. A never-finished backfill degrades gracefully; a frozen Tally does not.

**R30: All-time ledger balances are not a valid parity anchor mid-backfill**
- *What:* Tally's `LEDGER.ClosingBalance` is an **all-time** figure. Our computed balance only covers the synced window. While the backfill is incomplete these legitimately differ, and a naive rung-1 comparison would raise an integrity alert on every ledger of every customer, every day.
- *Impact:* High — it would make the integrity system worse than useless during the period it is most needed.
- *Handling:* §4.B — while `backfill.state != complete`, the opening balance at the watermark comes from a TB snapshot as-on the day before the watermark. Our lines from the watermark onward are added to it, and the result is compared with Tally's current balance. The TB is group-level, so this runs at group level (rung 2) and rung 1 is suspended, unless per-ledger openings come from probe 16 (ledger `OpeningBalance` readable as-on a date) or probe 17 (a ledger-level TB). Once history is complete, the books-start opening balance replaces the watermark anchor. The Settings card states the verified span.
- *Prove in S0:* probe 18 (does a TB as-on a past date return correct historical values?). **If probe 18 fails, there is no valid parity anchor during backfill** and parity must be suspended until the backfill completes — a real possibility that must be settled before S1.

## 8. S0 probe list (on restored seed backup `seed_data/TDBK1800_100003.001`)
Every probe **saves the raw Tally responses as fixtures** under `tests/fixtures/sync/` for the unit tests.

1. Company GUID, AltVchId, AltMstId, BooksFrom, LastVoucherDate: do they change on voucher create/alter/delete and master alter? (R6)
2. **Cheap read of the open company's GUID; the response when no company is open.** (R2)
3. Voucher GUID/MasterID/AlterID/IsCancelled/IsOptional/Reference can be fetched. (R6, R16)
4. The `$AlterID > N` filter on Voucher/Ledger/Group/StockItem works, doesn't crash Tally, and is fast enough. (R6)
5. SVFROMDATE/SVTODATE bound a Voucher collection? Safe `$Date` filter alternative.
6. Nested BILLALLOCATIONS, ISDEEMEDPOSITIVE, inventory/batch lines are returned. (R5)
7. A deleted voucher vanishes; GUID never reused. (R7)
8. Ledger rename: do old vouchers' names change? Is AlterID bumped? Does the GUID stay stable? (R9)
9. Latency and size per chunk; can the accountant keep typing during a heavy query? (R3, R27)
10. Error shapes: Tally closed, company closed, Educational mode, popup open. (R26)
11. Opening balances/bills, stock opening qty/rate/value. (R5)
12. Report snapshots via SVCurrentCompany at today's date. (R5)
13. Backup restore: do the company GUID and MasterIDs change? (R8)
14. **Company names with `&` / quotes / apostrophes:** escaped requests work, and unescaped ones fail as expected. (R13)
15. **Hindi/Unicode names and narrations + a stock item with compound units:** export intact, no crash. (R14, R15)
16. **Ledger closing balances (parity rung 1, and the base of every computed balance in chat — §4.A rule 1):** does `LEDGER.ClosingBalance` from `TYPE=Collection` equal Tally's TB screen? Is it `0` for *all* nominal ledgers? Is `OpeningBalance` FY-scoped or books-scoped — and **can it be read as-on an arbitrary date** (e.g. via `SVFROMDATE`)? If yes, that gives per-ledger opening anchors during the backfill without probe 17 (decision 11, §4.B "The opening anchor"). (§4.B, R5, R30)
17. **Ledger-level TB:** can an exploded (ledger-level) TB be exported via `TYPE=Data` safely and fast? If yes, rung 2 gains ledger resolution and month-bisect gets cheaper. (§4.B, R3)
18. **Historical reports (now load-bearing):** does a TB as-on a *past* month-end return correct historical values — and do **Bills Receivable/Payable and Stock Summary** as-on a past date too? Required for month-bisect, for the routine month-end snapshots (§3) and the dashboard's "vs last month-end" baselines, for answering historical dates from snapshots, **and — since decision 7b — as the only valid parity anchor while the backfill is incomplete** (and the base of the probe-16 fallback for chat). If the TB part fails, parity must be suspended until history completes; if the bills/stock part fails, those tiles lose their month-end comparison. (§3, §4.A, §4.B, §4.C, **R30**)
19. **Counter stability:** do `AltVchId` / `AltMstId` hold still across a multi-call capture window? This is the quiescence guard that prevents false parity alerts. (§4.B, R6)
20. **Parity cost:** latency and payload size of a full ledger list + TB on a large company. (R27)
21. **Full-history reach (decision 7b):** read `books_from` / the oldest available FY; can vouchers be fetched for an FY several years back, at what latency and payload size, and do closed/audited years behave differently? Extrapolate total storage across the whole books span. (R27, R29)
22. **Forex vouchers (decision 15):** on a foreign-currency sale/purchase (export/import — an Indian company can still have these), does the voucher's ledger line expose the **INR base amount** alongside the foreign face value, and in which fields? Confirms that aggregating the base amount is safe and nothing needs conversion at read time. **If the base amount is not exposed, decision 15 must be revisited.** (§4.A, decision 15)
23. **GST classification and due dates (§4.C):** do ledger masters expose Tally's GST classification (`TaxType`, `GSTDutyHead` or equivalent), so tax ledgers can be identified without name matching? Do Bills Receivable/Payable exports (and bill allocations) carry a due date or credit period, so overdue can be split without guessing? If either is missing, the GST tile or the overdue split is dropped from v1, never approximated.

## 9. Code gaps found (verified 2026-09-15)
- Company name not XML-escaped in `_wrap_voucher_collection` (`request_builder.py:69`), `_wrap_report_envelope` (`:112`), `build_ledger_vouchers` (`:270`). Escaped correctly at `:31` and `:179`.
- `build_list_groups` (`:223`), `build_list_stock_items` (`:226`), `build_list_stock_groups` (`:230`) and `masters.list_groups/list_stock_items/list_stock_groups` take no company param.
- `parse_vouchers` (`response_parser.py:291`) drops IDs, bill allocations, cancelled/optional flags.
- `TallyClient` has a single 90s timeout (`client.py:14`) and no retries. No ALTERID/MASTERID/GUID is fetched anywhere today.

Found while detailing §4 (2026-09-18) — these block the parity design specifically:
- **`parse_amount` returns `0.0` for anything unparseable** (`response_parser.py:19-26`), turning a parse failure into a legitimate-looking zero. That can produce a **false parity match** or a silently wrong balance. Sync parsers must distinguish missing from zero and reject the batch.
- **No freshness metadata on any tool result.** `ReportResponse.from_date/to_date` are populated only by `cash_flow` (`reports.py:203-204`); TB/P&L/BS leave them `None` (`:61,77,124`) and `raw_response` is never set. §4.A requires `source` + `as_of` on every result.
- **Money is float everywhere.** Sync tables and parity comparisons need `Decimal` / `Numeric(18,2)`.
- **`bills_receivable` / `bills_payable` fall back to `date.today()`** on an unparseable bill date (`reports.py:144,167`) — makes rung-3 bill parity non-deterministic.
- **`parse_stock_summary` returns `closing_quantity` while `StockItem` declares `closing_balance`** (`response_parser.py:257-264` vs `models.py:54-60`) — the two stock paths disagree on the key name; the sync schema must pick one.
- The TB report is **group-level only** and `_wrap_report_envelope` (`request_builder.py:111`) sets no explode flag — see probe 17.

## 10. Verification (when built, later)
- **Unit:** sync builders (escaping, no `*`, no `$$InDateRange`) and parsers on S0 fixtures from `tests/fixtures/sync/` (custom creditor sub-groups, non-bill-wise parties, duplicate names, cancelled/optional, Unicode, compound units); chunk splitter; change detector; outbox; gate (fake clock); new-FY rollover (fake clock); **work priority** (§3): a cycle with tier-1 work runs nothing else, tiers 2–5 consume the budget top-down, tiers 6–7 run only on an otherwise idle cycle, a timeout ends the cycle's work, and internet-down runs only tier 1's fetch; deletion compare covers the 2-FY window daily and rotates through older FYs; dates and FY boundaries come from Tally dates, never from UTC timestamps.
- **Backfill (decision 7b):** newest-first ordering across FYs and within an FY; **pre-emption** — a cycle with pending incremental work, a non-empty outbox, a parity remediation, the daily pass or a month-end capture runs **no** backfill chunk; watermark advances only after server ack; interrupted backfill resumes rather than restarts; terminates exactly at `books_from` and never runs again once `complete`, unless a whole-company resync re-walks it; a back-dated voucher landing in a `pending` FY is stored but that FY still answers "still loading"; an FY rollover extends the forward edge without restarting the backfill. Fake clock throughout.
- **Watermark query behaviour:** a date behind the available edge returns "still loading" (never a partial total); a date before `books_from` returns the out-of-window refusal; a range **straddling** the available edge is refused, not truncated. One test per case.
- **`resyncing` never locks (§3):** a single-FY resync of the **current** FY keeps answering normally with the integrity caveat (assert no "still loading" and no chat lock); after a restore, every previously `complete` year goes `resyncing` (not `pending`), answers with the restore caveat, is skipped by parity, returns to `complete` per FY on the last acked chunk, and then gets exactly one parity run; years still `pending` before the restore stay `pending`. Assert queries read the *available* edge and parity the *verified* edge.
- **Computed historical balances (§4.A rule 1):** a balance-sheet ledger's balance on a past date on/after the available edge equals mirrored `ClosingBalance` minus later lines — at ledger level, mid-backfill and in a `resyncing` year alike (assert no "still loading"); a date behind the available edge answers "still loading"; a nominal ledger sums from its FY start; with the probe-16 fallback switched on, only group-level answers computed forward from a stored month-end TB are given. **Cash flow** is computed from Cash / Bank ledger movements and labelled *computed*. **No computed fallback:** Stock Summary / P&L / BS / Bills for a date with no snapshot return the held-dates message, never a recomputed figure.
- **Mirrored freshness:** a cycle that syncs a voucher re-reads `ClosingBalance` for exactly the ledgers it touches (and `ClosingValue` for touched stock items), so the Cash & bank tile moves in the same cycle. The same holds for vouchers drained from the outbox and for vouchers soft-deleted by the deletion check. The Cash & bank month-end baseline equals current mirrored minus lines after the month-end, and equals chat's answer to the same question. Master-list tools are labelled *mirrored*.
- **Dashboard definitions:** gross margin uses COGS from stock snapshots and shows "no figure yet" when a boundary snapshot is missing (never sales − purchases); GST position reads only ledgers Tally classifies as GST, excludes tax payments and set-offs, and splits by duty head; the overdue split uses Tally's due dates.
- **Month-end snapshots (§3):** captured as-on the month-end date even when captured late (fake clock); a re-capture replaces rather than duplicates; a dashboard baseline with no snapshot shows "no month-end figure yet", never zero; month-bisect reuses an existing month-end snapshot instead of re-fetching it.
- **Mock Tally:**
  - Stateful sync mode in `backend/tally_bridge/mock_handler.py` (counters, AlterID/date filters, mutate/delete hooks).
  - **Latency / hang / error injection** in `tests/mocks/mock_tally_server.py`.
  - Skip cases: Tally offline, no company open, GUID mismatch.
  - Resume after an interrupted first sync.
- **DB integration (`TEST_DATABASE_URL`):** idempotent batch replay, older alter_id never overwrites, lines replaced not duplicated, reconcile soft-deletes (and returns the ledgers to re-read), cross-tenant post blocked, revoked device 401, run progress, batch with wrong company GUID rejected, oversize batch 413, per-device rate limit 429.
- **Round-trip E2E:** agent in-process vs mock Tally + FastAPI (ASGITransport): first sync → assert whole DB state = mock company → mutate → incremental → re-assert → delete → reconcile → re-assert → internet down mid-upload → outbox drains → restart agent → no duplicate uploads.
- **Parity:** see §4.E for the full plan (one unit fixture per cause signature, tolerance boundaries, debit-is-negative assertion, mock-Tally detect→classify→heal cycle, counters-moved `aborted_moving` run, retention + cross-tenant DB tests, reload round-trip, Playwright state matrix). Anchors: DB-computed TB vs `tests/fixtures/trial_balance_live.xml`; seed residuals ₹9,70,537 receivable / ₹18,34,142 payable.
- **Chat regression:** existing eval scenarios run against the synced seed company (R25).
- **Frontend:** state matrix (connecting / syncing % / error / Tally offline / ready / stale / restore detected / re-link offered × chat lock) with Vitest + Playwright screenshots, including a reload mid-sync.
- **Windows CI:** `windows-latest` runs agent tests, PyInstaller `--onedir` build, `--selftest`, service install/uninstall.
- **Windows manual:** Win10/11 VM + TallyPrime 7 + seed backup, covering:
  - Non-admin user
  - Antivirus / SmartScreen
  - Sleep/resume
  - Tally restarted mid-sync
  - Updater rollback
  - Log off vs disconnect (R11)
  - Two Tally instances (R12)

## 11. Open questions (decide before specs)
| # | Question | Linked risk | Options / notes |
|---|---|---|---|
| Q1 | **Agent offline vs Tally closed:** should the agent send a lightweight heartbeat on skipped cycles too (e.g. "alive, Tally closed")? | R24 | Yes → web can show "Tally closed" vs "Agent offline"; costs one tiny request per cycle |
| Q2 | **Before the first sync ever runs:** what does the web show if Tally hasn't been opened since install? | R22 | e.g. locked chat + "Waiting for Tally: open Bharat Traders in TallyPrime" |
| Q3 | **Stale threshold:** after how long is the stale badge shown? | R1 | e.g. >1 hour amber, >24 hours red |
| Q4 | **Changing company or PC:** the user picked the wrong company, moves to a new PC or reinstalls. How is the saved company re-bound? | R2, R19 | e.g. "Change company" in agent → new workspace, or re-bind with a confirm; old device revoked |
| Q5 | **Removing data:** what happens to synced data on disconnect, uninstall or account deletion? | R20 | Keep read-only / delete after N days / delete immediately |
| Q6 | **Data privacy:** encryption at rest, who at our side can see the books, keep `raw` JSONB or not? | R20, R27 | |
| Q7 | ~~**Chat tools mapping**~~ | R25 | **Answered in §4.A** (routing table for all 19 tools; out-of-window dates fail loudly). Confirm the split when the S4 spec is written. |
| Q8 | **Previous FY reports:** the routine month-end set (§3) already captures TB, Bills Receivable/Payable and Stock Summary as-on 31 March. Remaining question: also capture the **full-FY P&L and a Balance Sheet** at each FY close (and a BS at each month-end)? §4.A rule 1 gives P&L/BS no computed fallback (R5), so without these snapshots a past year's P&L or BS cannot be answered at all. | R5, Q20 | Leaning yes — a few extra calls a year |
| Q9 | **Tally offline state on web:** full set of UI states and messages | R24 | Decide in S3 spec (see §4 Web states) |
| Q10 | **Out-of-scope confirmation:** is §6 complete (multi-company, writes, live queries, billing, Mac/Linux, older Tally)? | — | |
| Q11 | **Where the company is picked:** decision 3 says inside the Windows agent; the new Sync / Settings page "picks up companies automatically". Does the web show the agent's company list and the user picks there, or does the agent pick and the web only display it? | R2 | A: pick in web Settings (agent reports list) · B: pick in agent, web displays · C: both |
| Q12 | **Two company selectors:** is the top bar for **switching** between connected companies and Sync / Settings for **connecting** a new one? | R2 | Assumed yes in §12.5 |
| Q13 | ~~**Dashboard vs Insights**~~ | R25 | **Answered (§4.C):** Dashboard = **KPIs** (fixed tiles, glanceable); Insights = **demands, reconciliation, alerts** (ranked list of things to act on). Two sub-questions remain: Q13a, Q13b. |
| Q13a | **"Demands" — which meaning?** Collections/dunning (overdue receivables to chase, payables to pay) is the reading assumed in §4.C. It could instead mean statutory **tax demands** (GST/TDS notices), which we hold no data for. | — | Confirm before S5 |
| Q13b | **"Reconciliation" — internal only?** §4.C assumes *internal consistency within the synced books* (party ledger vs open bills, stock ledger vs Stock Summary, unallocated bill-wise vouchers). Bank-statement and GSTR-2B reconciliation both need external data we don't sync and are excluded from v1. | B1d | Confirm the v1 line |
| Q14 | **Upload → Write to Tally:** does the existing write flow stay inside AI Chat, for live-connected workspaces only? | R28 | Assumed yes in §12.4 |
| Q15 | **Landing page:** after login, does the user land on Dashboard or AI Chat? | — | Assumed Dashboard in §12.6 |
| Q16 | **Existing live-connected companies:** keep manual host/port connect (today's `ConnectCompanyModal`) somewhere in Settings, or hide it? | — | |
| Q17 | **Demo mode toggle + Live/Demo badge** (today in `Header.tsx` / `TallyStatusBadge.tsx`): move to Sync / Settings, or remove? | — | Assumed moved to Settings in §12.3 |
| Q18 | **Mobile and tablet:** left menu as a drawer (like today's sidebar)? Collapsed icon rail on tablet? | — | Assumed drawer on mobile in §12.8 |
| Q19 | **Parity tolerance:** flat ₹1.00 per line (`PARITY_TOLERANCE_PAISE=100`), or percentage-based for large balances? A ₹1 tolerance on a ₹4 crore ledger is effectively exact; on a ₹500 ledger it is 0.2%. | R5 | Flat is simpler and catches more; decide after probe 20 shows real diff magnitudes |
| Q20 | **Rung 3 in or out for v1?** Decision 11 defers it. Does Q8 (previous-FY closing snapshot) change that — i.e. do we need statement-level parity to trust a stored FY close? | R5, Q8 | Revisit when Q8 is settled |
| Q21 | **Parity retention:** proposed 90 days for runs, 7 days for matching lines, 90 for mismatching. Enough history to debug a recurring drift without storing a daily full ledger dump forever? | R20, R27 | Size it against probe 20's ledger counts |
| Q22 | **Is `raw` JSONB kept for backfilled years?** Decision 7b makes storage unbounded. Keeping `raw` for the recent 2 FYs but dropping it for older backfilled years would roughly halve the marginal cost of deep history. | R27, R29 | Decide after probe 21 |
| Q23 | **Does the backfill need a floor?** Decision 7b says all history to books start. Do we want a safety ceiling (e.g. stop at 10 FYs, or at a storage budget) for pathological companies, and what does the UI say when it stops early? | R27, R29 | Revisit after probe 21 gives real numbers |
| Q24 | **What does the web show while history loads?** A progress line in Settings only, or a subtle indicator on Dashboard/Insights too? Chat already answers "still loading" for un-backfilled dates (decision 7b). | R29, Q2 | Decide in S3 spec |
| Q25 | **Re-link on a new GUID:** is "same company name, different GUID → offer Re-link" (§3 "Company identity changes") the right trigger? Name matching can be fooled by two companies with the same name (e.g. one per FY split). Should re-link need the website password, or just a tray click? | R2, R8 | Default: tray + web prompt, website password required, never automatic |
| Q26 | **During a backup-restore state:** is chat-with-caveat right (decision 13), or should a restore be the one case that blocks chat until the user decides? Our copy may contain vouchers that no longer exist in Tally. | R8, decision 13 | Default: caveat, don't block |
| Q27 | **Live-connected workspaces long-term:** keep the dual path (live Tally for `tally_host` workspaces, DB for sync-agent ones) indefinitely, or migrate live-connected customers to the agent and retire live chat queries? The dual path doubles the S4 tool test matrix. | R25, R28 | Decide before the S4 spec |
| Q28 | **Who can see a synced workspace?** v1 assumes the existing workspace ownership model: the account that bound the company. Owners often want their accountant on the same workspace, or the other way round. Share with other logins, and with what roles? | R19, R20 | Decide before the S3 spec |

Q1–Q5, Q8, Q11–Q17 and Q25–Q28 are product decisions to settle first. Q6, Q9, Q10 and Q18–Q24 can be settled in the S1–S5 specs, though **Q22/Q23 need probe 21's numbers before S1 commits to a schema**. Q7 is answered in §4.A.

## 12. Navigation & page layout (new design, 2026-09-15)

> Source: design input shared on 2026-09-15. Items marked **(given)** come directly from that input. Items marked **(assumed)** are interpretations to confirm via Q11–Q18.

### 12.1 The change as given
| Area | What it holds |
|---|---|
| **Top bar** | Logo, Company selector, User **(given)** |
| **Page titles** | Move out of the top bar into the main right section **(given)** |
| **High-level menu** | Dashboard, Insights, AI Chat, Sync / Settings **(given)** |
| **AI Chat** | Chats become a submenu under it **(given)** |
| **Sync / Settings** | Connect Tally status and company selector; picks up companies automatically **(given)** |

### 12.2 Layout (desktop)
```
┌──────────────────────────────────────────────────────────────────┐
│ TOP BAR:  [Logo]            [Company selector ▾]        [User ▾] │
├───────────────────┬──────────────────────────────────────────────┤
│ LEFT MENU         │  MAIN SECTION                                │
│                   │  ┌────────────────────────────────────────┐  │
│ ▸ Dashboard       │  │ Page title          [page actions]     │  │
│ ▸ Insights        │  │ Last synced 8 min ago                  │  │
│ ▾ AI Chat         │  └────────────────────────────────────────┘  │
│     + New chat    │                                              │
│     Chat 1   ⋯    │  …page content…                              │
│     Chat 2   ⋯    │                                              │
│ ▸ Sync / Settings │                                              │
└───────────────────┴──────────────────────────────────────────────┘
```

### 12.3 Top bar
| Element | Behaviour |
|---|---|
| **Logo** | Click → Dashboard of the selected company **(assumed)** |
| **Company selector** | Dropdown of the user's connected companies (one workspace each). Selecting one switches the whole app to that workspace and stays on the same menu page (e.g. Dashboard → Dashboard) **(assumed, Q12)**. Each entry shows a small sync-state dot (ready / syncing / stale / offline / restore detected) **(assumed)**. A footer link "Connect a company" goes to Sync / Settings **(assumed)** |
| **User menu** | Existing `UserMenu.tsx` (profile, logout) **(given: "user")** |
| **Removed from top bar** | Page/chat title (moves to main section, **given**); Live/Demo badge and demo toggle (move to Sync / Settings, **assumed, Q17**) |

### 12.4 Left menu
**Dashboard**
- Purpose: the **KPI** overview for the selected company (S5) — sales, purchases, gross margin, cash & bank, receivables/payables, stock value, GST position, top customers/items, sales trend. Full tile definitions in **§4.C**.
- Period selector on period-scoped tiles; balance tiles are always "as on" the latest available date. Every tile links through to AI Chat with the equivalent question pre-filled.
- Data: our DB + Tally report snapshots with "as of" time (§4 Chat & BI).
- Page title: "Dashboard". Header shows "Last synced X ago" and the stale badge.
- First sync not finished → progress panel instead of tiles; nothing synced yet → "Waiting for Tally" panel (Q2).

**Insights**
- Purpose: **demands, reconciliation, alerts** — a ranked list of things needing attention (§4.C). Not a second dashboard.
- Each item: plain-language statement + evidence + severity + first-seen date + dismiss, with a link that opens it in AI Chat.
- **Empty state is a success state** ("Nothing needs your attention") — Insights must never manufacture findings to look busy.
- The data-integrity alert (§4.B) surfaces here as well as in the dashboard ribbon.
- Same freshness header and first-sync states as Dashboard.

**AI Chat** (expandable)
- Submenu = today's conversation list for the **selected company only** (`ConversationList.tsx`), with the existing rename/delete kebab (⋯) and "+ New chat" at the top.
- The active chat is highlighted. The submenu expands automatically when a chat is open.
- Main section title = conversation title (inline rename could move here later), or "New chat" for a new conversation.
- On sync-agent workspaces, answers come from our DB (S4); live-connected and demo workspaces keep today's path (decision 8). Chat is locked during the first sync with the progress message.
- Upload → Write to Tally stays inside AI Chat **for live-connected workspaces only**. Synced workspaces show the "writing not available yet" note (decision 10, Q14).

**Sync / Settings**
- **Connection status card:** agent online/offline (Q1), Tally reachable, our company open, sync state (connecting / syncing % / ready / stale / error / restore detected), last synced time, last error in plain words.
- **Company identity prompts** (§3 "Company identity changes"): "This looks like a new copy of *Bharat Traders* in Tally. Re-link?" (Q25), and the backup-restore card "Tally was restored from a backup — our copy may include entries that no longer exist" with **"Re-sync now"**. Both are offers the user acts on; nothing starts automatically (decision 12).
- **Companies:** list picked up **automatically** from the agent (given). The user connects one → a workspace is created (binding rules: Q11). Already-connected companies show their status.
- **History card** (decision 7b): "Full history loaded (Apr 2019 onwards)" when complete; after a restore or re-link, "Refreshing history after a restore — 40%" (all years stay available, §3 `resyncing`); otherwise "Loading history — 2019-20 onwards, 60%" with the span already available. Shows an available-from date, not a false ETA (R29). If progress has stalled for several days while the agent is healthy, adds "Leave TallyPrime open longer to finish loading". Detail level: Q24.
- **Data integrity card** (§4.B surfacing): green "Matches Tally as of 18 Sep, 9:12 pm" / amber "Re-checking a difference with Tally" / red "3 ledgers don't match Tally" with the affected list. Actions: **"Re-check now"** and, only after two failed heals, **"Re-sync this year"** (decision 12 — never automatic). `hard_alert` keeps the red card and adds "Contact support" (§4.B surfacing). The `suspect` state renders as the amber "re-checking" wording, never as an alarm. While the backfill is incomplete the card states the verified span ("Checked against Apr 2024 onwards") so a green tick never overstates what was proven (R30).
- **Devices:** the PCs running the agent for this account, with "Remove device" (uses `GET/DELETE /api/devices`) **(assumed)**.
- **Setup help:** onboarding checklist (turn on Tally XML server, port 9000, keep Tally open, don't log off) linked to R10/R11 **(assumed)**.
- **Demo mode** toggle and **live-connected manual connect** (today's `ConnectCompanyModal.tsx`), if kept (Q16, Q17).
- "Sync now" is **not** on the web in v1; it stays in the agent tray **(assumed)**.

### 12.5 Two company selectors: roles
| Where | Role |
|---|---|
| Top bar | **Switch** between companies already connected (**assumed, Q12**) |
| Sync / Settings | **Connect** a new company from the automatically found list, and see each company's sync status (**given + assumed**) |

### 12.6 Routes (proposal)
| Route | Page |
|---|---|
| `/w/:workspaceId/dashboard` | Dashboard |
| `/w/:workspaceId/insights` | Insights |
| `/w/:workspaceId/chat` | AI Chat, new chat |
| `/w/:workspaceId/chat/:conversationId` | AI Chat, open conversation |
| `/w/:workspaceId/settings` | Sync / Settings |
| `/` after login | Redirect to the last used workspace's Dashboard (Q15) |
| Existing `/c/:conversationId`, `/w/:workspaceId` (`App.tsx:26-27`) | Redirect to the new chat / dashboard routes so old links keep working |

The workspace lives in the URL so a reload or shared link opens the same company and page.

### 12.7 Mapping from today's frontend
| Today (`frontend/src/`) | New |
|---|---|
| `components/Header.tsx`: brand, `CompanySelector`, chat title, demo toggle | Top bar with logo + company selector + user only. Chat title → main section header. Demo toggle → Settings (Q17) |
| `components/CompanySelector.tsx` | Reused in the top bar (switch) |
| `components/TallyStatusBadge.tsx` (Live/Demo) | Status card in Sync / Settings; small status dot in the company selector |
| `components/Sidebar.tsx`: workspace groups, conversations, "+ Connect Company" | Becomes the left menu with 4 items. Conversations → AI Chat submenu. "+ Connect Company" → Sync / Settings |
| `components/ConversationList.tsx` (rename/delete kebab) | Reused as the AI Chat submenu |
| `components/ConnectCompanyModal.tsx` (manual host/port, Check Connection, setup steps) | Replaced by Sync / Settings company list; kept only for live-connected mode if Q16 says so |
| `components/UserMenu.tsx` | Unchanged, in the top bar |
| `ChatApp.tsx` + `components/ChatWindow.tsx` | AI Chat page content |
| `App.tsx` routes | New routes (§12.6) with redirects |
| Nothing | New pages: Dashboard, Insights, Sync / Settings, plus a shared page header (title + freshness) |

### 12.8 Responsive
| Viewport | Behaviour |
|---|---|
| Desktop | Left menu always visible; AI Chat submenu expandable |
| Tablet | Left menu collapses to an icon rail; expands on tap **(assumed, Q18)** |
| Mobile | Top bar: menu button + logo + compact company selector + user avatar. Left menu opens as a drawer (like today's responsive drawer, Group A F6) and closes after navigation **(assumed, Q18)** |

Page titles stay in the main section on all viewports. Long company names and chat titles truncate with a tooltip.

### 12.9 Page × sync state matrix
| Sync state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| Connecting (never synced) | "Waiting for Tally" panel | Same | Locked, "Waiting for Tally" | Checklist + status "Waiting for Tally" |
| Syncing (first sync) | Progress panel (%) | Same | Locked, progress message | Progress bar + current step |
| Error | Last good data + error banner (or panel if no data) | Same | Unlocked if a first sync ever completed | Plain-language error + fix steps |
| Tally offline (after first sync) | Data + "last synced X ago" | Same | Unlocked | "Tally closed / company not open" (Q1) |
| Ready | Data | Data | Unlocked | "Up to date" |
| Stale | Data + stale badge | Same | Unlocked + stale note | Stale warning + likely cause |
| Restore detected (R8) | Data + restore caveat banner | Same | Unlocked; answers carry the restore caveat (Q26) | Restore card + "Re-sync now" (offer only, decision 12) |
| Re-link offered (same name, new GUID) | Data + "last synced X ago" (sync is paused) | Same | Unlocked | Re-link prompt (Q25); on confirm, new GUID saved + full resync offered |

**History backfill is a third, independent dimension** (decision 7b). Like integrity, it only ever
adds to the page and never locks anything — the 2-FY window is already `ready` by the time it runs:

| Backfill state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| `running` | data for the synced span; no banner (Q24) | same | unlocked; pre-watermark dates answer "still loading, 60% done" | "Loading history — 2019-20 onwards, 60%" |
| `complete` | no change | no change | all dates answer normally | "Full history loaded (Apr 2019 onwards)" |
| stalled (R29) | no change | no change | same "still loading" wording | progress + "Leave TallyPrime open longer to finish loading" |
| `resyncing` (whole-company resync after a restore / re-link) | data for every loaded year + restore caveat banner | same | unlocked; `resyncing` years answer **normally** with the restore caveat — never "still loading" | "Refreshing history after a restore — 40%" |

A single-FY parity resync does not change `backfill.state` (§3). It shows only in the integrity
dimension below, and that year keeps answering normally with its integrity caveat.

**Integrity is a second, independent dimension** (§4.B) — it overlays whatever sync state applies,
and only ever adds to the page; it never removes data or locks anything (decision 13):

| Integrity state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| `ok` | no change | no change | no change | green "Matches Tally as of …" |
| `suspect` | no change (invisible to the user) | no change | no change | amber "Re-checking a difference with Tally" |
| `alert` | scoped amber ribbon ("Receivables may be off — we're re-checking with Tally") | same | unlocked; affected answers carry a one-line caveat | red card + affected ledgers + "Re-check now" (+ "Re-sync this year" only after two failed heals) |
| `hard_alert` | same ribbon, stronger wording | same | same caveat | red card + "Contact support" + internal engineering flag raised |

Plus, per workspace type: **live-connected** workspaces keep today's chat + write flow; Dashboard/Insights behaviour for them is open (not synced → no BI data) **(assumed: show "Connect via sync agent to see dashboards")**.

### 12.10 Accessibility
- Top bar = `header`, left menu = `nav` with `aria-label="Main"`, main section = `main` with the page title as its `h1`.
- Active menu item uses `aria-current="page"`. The AI Chat submenu is a disclosure button with `aria-expanded`.
- Company selector and user menu keyboard-operable (arrow keys, Esc closes), matching the existing kebab menu roles.

### 12.11 Testing (per CLAUDE.md rules)
- **Vitest, top-level container:** render the app shell, click each menu item, assert the main section title and content change; switch company in the top bar and assert chat submenu + page data switch; open a chat from the submenu and assert the title shows in the main section, not the top bar. Mock only the HTTP API.
- **Refresh round trip:** on each page, reload → same company, same page, same open chat, submenu state restored (URL-driven).
- **Route redirects:** old `/c/:id` and `/w/:id` links land on the new pages.
- **Sync-state matrix:** each cell in §12.9 has a mock data variant and a test.
- **Playwright:** page × sync state × viewport (mobile/tablet/desktop) screenshots, each with a `// VISUAL CHECKLIST:` block and content assertions first; main agent reviews every PNG. Includes long company name / long chat title truncation and mobile drawer open/closed.
- **Regression:** existing chat, upload → voucher card → write, rename/delete conversation all still work from the AI Chat page.

### 12.12 Assumptions to confirm
1. Top bar selector switches; Settings connects (Q12).
2. Upload → write stays in AI Chat for live-connected workspaces (Q14).
3. Landing page is Dashboard (Q15).
4. Demo toggle and Live/Demo badge move to Settings (Q17).
5. Mobile drawer, tablet icon rail (Q18).
6. Workspace in the URL; old routes redirect.
7. "Sync now" stays in the agent tray only.
8. ~~Insights = AI-generated findings (Q13).~~ Superseded by §4.C: Insights is a rule-based ranked list of demands / reconciliation / alerts, never AI-invented. Remaining sub-questions: Q13a, Q13b.

## 13. Next step
Brainstorm only so far. When approved: settle open questions Q1–Q5, Q8, Q11–Q17 and Q25–Q28 → write the S0 live-Tally probe spec (all probes 1–23, including parity probes 16–20, full-history probe 21, forex probe 22 and GST / due-date probe 23) → S1–S5 specs → implementation plans.

The §4.B integrity design rests on four probe results (16, 17, 18, 19). Three are load-bearing enough
to run first:

- **Probe 16** — if `LEDGER.ClosingBalance` does **not** agree with Tally's own TB, rung 1 collapses
  and parity falls back to group level only, making month-bisect the primary localisation tool and
  changing the cost profile materially. Chat's computed balances also lose their base and fall back
  to group-level forward computation from stored month-end TBs (§4.A rule 1).
- **Probe 18** — if a TB as-on a past date is unreliable, there is **no valid parity anchor while
  the backfill is incomplete** (R30), and parity would have to be suspended until full history
  lands. Since decision 7b means most customers are mid-backfill for weeks, that would gut the
  integrity system exactly when it matters most.
- **Probe 17, or probe 16's as-on reading** — decides whether rung 1 runs at all during the
  backfill (decision 11). If neither gives per-ledger openings, ledger-level parity waits for full
  history, and some customers (R29) may never get it.

**Probe 21** should also run early: decision 7b makes storage unbounded, and Q22/Q23 (drop `raw` for
backfilled years? cap the depth?) must be settled before S1 commits to a schema.
