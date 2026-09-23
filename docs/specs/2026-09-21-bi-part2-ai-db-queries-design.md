# Part 2 — AI queries from our DB

> **Brainstorm design, not yet implemented.** Docs only; no code changes have been made for this.
> Split from `2026-09-15-bi-sync-agent-design.md` on 2026-09-21. The original is kept unchanged.
>
> This part covers how the AI chat answers from our DB instead of live Tally: where every figure
> comes from, which rules the tool handlers enforce, and which caveats answers carry. The same
> query layer serves Part 3's report/dashboard API.
>
> The other two parts:
> - **Part 1** (`2026-09-21-bi-part1-sync-design.md`): syncing. It also holds the shared context,
>   out of scope, R20 and the cross-cutting questions.
> - **Part 3** (`2026-09-21-bi-part3-ui-dashboard-api-design.md`): the UI and the report/dashboard API.
>
> IDs are the same as in the original (decision N, Rn, Qn, probe n).

## 1. Scope
- Rewriting the 18 data-tool handlers in `backend/agents/tools.py` so that, on sync-agent
  workspaces, they read our DB (§4).
- The query rules they enforce: snapshot-only reports, backwards balance computation, "still
  loading" and the other refusals (§4, Rules 1 and 2).
- The caveats answers carry (§5).
- Context and what is out of scope: Part 1, "Context" and "Out of scope (v1)".

## 2. Decisions this part implements
| # | Decision |
|---|---|
| 8 | During first sync the web shows progress and chat is locked. After that, every query is answered from our DB with "last synced X ago". **On sync-agent workspaces we never query live Tally.** Chat tool handlers branch on `workspace.config.source`: `sync_agent` → our DB (§4); live-connected workspaces (with `tally_host`) and demo mode keep today's live/mock query path unchanged (decision 1). Retiring the live path is Q27. |
| 13 | **An integrity alert never blocks chat or dashboards.** Affected answers carry a caveat and the dashboard shows a scoped ribbon. Blocking is reserved for the first sync. |
| 15 | **India-only, INR-only.** Indian companies, Indian FY (1 Apr – 31 Mar), GST, Indian number formatting. **Every BI and chat figure is the INR base amount.** An Indian company can still hold forex vouchers (export sales, import purchases — the reason the FX write flow exists), but Tally records those with an INR base amount alongside the foreign face value: we aggregate **only** the INR base amount, and the original currency/face value is preserved in `raw` JSONB for drill-down, never summed. No multi-currency reporting, no rate tables, no conversion at read time. |

Decision 7b ("still loading", never a partial total) is defined in Part 1; Rule 2 below is how the
query side honours it.

## 3. Depends on / provides
**Depends on Part 1:**
- **Data contract** (Part 1, "Depends on / provides"): tables, voucher flags, INR base amounts,
  coverage states and the two watermark edges, snapshots, mirrored-balance freshness,
  `last_synced_at`.
- **Integrity contract:** parity states, `parity_lines` verdicts, and the surfacing rules.

**Provides to Part 3:**
- **The query layer:** the sources and Rules 1–2 below, as one backend implementation. Both the
  chat tool handlers and Part 3's report/dashboard API call it; neither re-implements a figure. That
  is what keeps a dashboard tile and its chat click-through in agreement.
- **The answer contract:** every result declares its `source` (`computed | mirrored | snapshot`; none
  for `resolve_date_range`) and an `as_of` time, carries `warnings: string[]` (integrity and restore
  caveats, §5), and uses the refusal wording of Rules 1–2. A structured status for refusals is an
  open design item (§6).

## 4. Where every answer comes from

### Sources
Three sources. Every tool result **must declare which one it used and an "as of" time**. Today no
tool result carries any freshness metadata at all — `ReportResponse` has `from_date`/`to_date` but
TB/P&L/BS never populate them (`reports.py:61,77,124`); only `cash_flow` does (`:203-204`).

| Source | Meaning | Freshness label shown to the user |
|---|---|---|
| **Computed** | SQL over `tally_voucher_ledger_lines` / `tally_vouchers` | "as of last sync, 8 min ago" |
| **Mirrored** | A Tally field copied verbatim at sync time (`LEDGER.ClosingBalance`, `STOCKITEM.ClosingValue`). Kept fresh by Part 1's re-read of every ledger and stock item a synced voucher touches (Part 1, "Every cycle") | "as of last sync, 8 min ago" — true only because of that re-read |
| **Snapshot** | A whole `TYPE=Data` report captured and stored | "Tally's own figure as of 18 Sep, 9:12 pm" |

### Routing for the 19 tools
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

### Rule 1 — snapshot tools and computed balances
1. **A snapshot tool only answers at its snapshot's own date.** "TB as on 30 June" cannot be served
   from a snapshot taken today. The handler picks a matching snapshot — the routine month-end set
   (Part 1, "Month-end snapshots") or one left by month-bisect (Part 1, "Month-bisect") — or, **only
   where a computed answer can match Tally**, computes and labels the result *computed*.
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
     rung 1, Part 1 "Rung 1"). Our lines only start at the available edge, so a forward sum would
     miss all earlier history (R30's problem, in chat). The backwards sum needs only the lines
     *after* D, and those are all held whenever D is on or after the available edge. So it needs no
     opening anchor, and works at ledger level during the backfill and in `resyncing` years. A
     computed TB is the group rollup of these.
   - Nominal (P&L) ledgers read `ClosingBalance = 0` and reset each FY: Σ lines from FY start to
     the date, valid when that FY start is on or after the available edge; otherwise rule 2.
   - **Depends on probe 16** (mirrored balance = Tally's TB). If probe 16 fails, computed balances
     fall back to the forward formula from a stored month-end TB (Part 1, "The opening anchor"),
     group level only, and ledger-level past balances answer "still loading" (rule 2).
   - Opening anchors are **for parity only**. A backwards-computed balance cannot check anything,
     because at today's date it equals Tally's figure by construction. Parity has to compare an
     independent forward sum (Part 1, "Integrity (parity) system").
   - The Cash & bank tile's month-end baseline uses this same rule (Part 3, "Dashboard"), so the
     tile and its chat click-through always agree.

### Rule 2 — dates outside the loaded history
2. **Out-of-window dates fail loudly — and the two kinds of "out of window" say different things**
   (decision 7b). Handlers check the **`sync_fy_coverage`** watermark (Part 1, "Background history
   backfill" and "What a full resync does…"), not just the requested date:
   - **On or after the available edge** → answer normally.
   - **Not yet backfilled** (inside the books, behind the *available* edge — `pending`/`running`) →
     *"I'm still loading data from before Apr 2024 — about 60% done. Ask me again shortly."* Never a
     partial total; a figure that silently grows later is worse than no figure.
   - **`resyncing`** (already loaded, being refreshed after a restore or a parity resync) is **not**
     "out of window": answer normally with the restore or integrity caveat (§5). A resync must never
     turn loaded data into "still loading".
   - **Before `books_from`** (data that does not exist in Tally at all) → *"This company's books
     start in Apr 2019."*
   - A range **straddling** the available edge is treated as not-yet-available, never silently truncated.
   - Neither case ever returns a silently wrong zero.

The existing full-FY-only restriction on P&L stays exactly as it is (LESSONS §1;
`reports.py:99-112` raises for partial periods and points at the voucher registers).

## 5. Caveats in chat
How each integrity state shows in AI Chat. The rules every surface follows (`suspect` is invisible,
chat is never blocked, the wording never implies their books are wrong) are defined in Part 1,
"Surfacing rules". The Settings card and dashboard ribbon are in Part 3, "Integrity surfacing in the
UI".

| Integrity state | AI Chat |
|---|---|
| `ok` | nothing |
| `suspect` | nothing |
| `alert` | tools touching an affected ledger return a `warning`; the answer carries a one-line caveat |
| `hard_alert` | same caveat |

**Restore caveats.** While `sync_state = restore_detected`, answers carry "Tally was restored from a
backup — our copy may include entries that no longer exist" (Part 1, "Company identity changes").
While a year is `resyncing` after a restore, answers for it carry "Tally was restored from a backup —
we're refreshing our copy" (Part 1, "What a full resync does…"). Whether a restore should instead
block chat is Q26 (default: caveat, don't block).

**Locking.** Chat is locked only during the first sync (decision 8). No integrity state, restore state
or resync ever locks it (decision 13).

Implementation note: the chat caveat reuses the existing `warnings: string[]` pattern from
`VoucherReviewCard.tsx:37` rather than inventing a new mechanism.

## 6. Open design items
Not designed in the original spec. Only the known requirements are listed here; the S4 spec settles
them.

1. **Structured answer status.** Refusals exist only as text today ("still loading", "I have Tally's
   own figures for these dates", "This company's books start in …"). Chat can render text, but Part 3's
   dashboard tiles cannot render a "still loading" state without a machine-readable status, e.g.
   `status: ok | still_loading | not_held | before_books`. The status belongs in the answer contract
   (§3). Chat keeps rendering the wording.
2. **"Touches an affected ledger."** §5 says tools touching an affected ledger get the integrity
   caveat, but the rule for "touches" isn't defined. It has to say which parity verdicts count (Part 1,
   "Storage": `mismatch`, `missing_in_db`, `missing_in_tally`), from which run (the latest
   non-`aborted_moving` one), and whether a group-level mismatch taints every ledger under it. Part 3's
   ribbon scoping must use the same rule.

## 7. Code gaps (verified 2026-09-18)
The sync-side gaps (escaping, `parse_amount`, parser and client gaps) are in Part 1, "Code gaps".

- **No freshness metadata on any tool result.** `ReportResponse.from_date/to_date` are populated only by `cash_flow` (`reports.py:203-204`); TB/P&L/BS leave them `None` (`:61,77,124`) and `raw_response` is never set. §4 requires `source` + `as_of` on every result.
- **`bills_receivable` / `bills_payable` fall back to `date.today()`** on an unparseable bill date (`reports.py:144,167`) — makes rung-3 bill parity non-deterministic.
- **`parse_stock_summary` returns `closing_quantity` while `StockItem` declares `closing_balance`** (`response_parser.py:257-264` vs `models.py:54-60`) — the two stock paths disagree on the key name; the sync schema must pick one.
- **Money is float throughout.** Queries need `Decimal` end to end; Part 1 stores `Numeric(18,2)`.

## 8. Verification (when built, later)
- **Watermark query behaviour:** a date behind the available edge returns "still loading" (never a partial total); a date before `books_from` returns the out-of-window refusal; a range **straddling** the available edge is refused, not truncated. One test per case.
- **`resyncing` never answers "still loading":** a single-FY resync of the **current** FY keeps answering normally with the integrity caveat (assert no "still loading" and no chat lock); after a restore, every `resyncing` year answers with the restore caveat. Assert queries read the *available* edge, not the verified one. (The state transitions themselves are tested in Part 1.)
- **Computed historical balances (Rule 1):** a balance-sheet ledger's balance on a past date on/after the available edge equals mirrored `ClosingBalance` minus later lines — at ledger level, mid-backfill and in a `resyncing` year alike (assert no "still loading"); a date behind the available edge answers "still loading"; a nominal ledger sums from its FY start; with the probe-16 fallback switched on, only group-level answers computed forward from a stored month-end TB are given. **Cash flow** is computed from Cash / Bank ledger movements and labelled *computed*. **No computed fallback:** Stock Summary / P&L / BS / Bills for a date with no snapshot return the held-dates message, never a recomputed figure.
- **Mirrored labels:** master-list tools are labelled *mirrored*, and a mirrored balance reflects a synced voucher in the same cycle (via Part 1's re-read).
- **Caveats:** tools touching an affected ledger return the `warning`; `suspect` adds nothing; restore caveats appear in `restore_detected` and `resyncing` states; no integrity or restore state locks chat.
- **Dual path (decision 8):** live-connected and demo workspaces still use today's live / mock query path.
- **Chat regression:** existing eval scenarios run against the synced seed company (R25), with `get_cash_flow` checked against Tally's own report.

## 9. Risks
R5, R16 and R25 live here. The rest are in Part 1 (shared ones included) and Part 3.

| ID | Risk | Likelihood | Impact | Status |
|---|---|---|---|---|
| R5 | Our numbers differ from Tally | High | **Critical** | Mitigated (snapshots + parity) |
| R16 | Cancelled / optional vouchers counted | Medium | High | Filter + test |
| R25 | Chat answers regress after moving to our DB | Medium | High | Parity + eval |

**R5: Our numbers differ from Tally**
- *What:* Tally doesn't store closing stock or ledger closing balances; they're computed when a report opens. Our recomputation (stock valuation method, opening balances, cancelled/optional vouchers) can differ.
- *Impact:* critical. One wrong number on the dashboard costs trust.
- *Evidence:* no closing-stock voucher exists; tally-database-loader recomputes WA/FIFO itself.
- *Handling:* show Tally's own report snapshots (Stock Summary, Bills Receivable/Payable, full-FY TB/P&L/BS) with an "as of" time (§4). The parity ladder (Part 1, "Integrity (parity) system") proves our computed numbers still agree: **rung 0** double-entry invariant on every ingest, **rung 1** per-ledger vs Tally's own mirrored `ClosingBalance`, **rung 2** group rollup vs the TB snapshot. Mismatches are classified to a cause and remediated before anything is shown to the user. Sync opening balances/bills/stock (probe 11).
- *Prove:* seed residuals ₹9,70,537 receivable / ₹18,34,142 payable; computed TB = `tests/fixtures/trial_balance_live.xml`.
- *Note:* rung 1 cannot see revenue/expense ledgers (nominal accounts always read `ClosingBalance = 0`, LESSONS §4) — that is precisely why rung 2 is in v1 scope and not deferred.

**R16: Cancelled / optional vouchers counted**
- *What:* cancelled or optional (memo) vouchers get included in sales/profit totals.
- *Handling:* sync the `IsCancelled`/`IsOptional` flags (probe 3, Part 1) and exclude them in every computed number. Fixtures include both.

**R25: Chat answers regress after moving to our DB**
- *What:* rewriting the 18 data-tool handlers in `backend/agents/tools.py` (all except the `resolve_date_range` helper) changes answers that are correct today.
- *Handling:* the parity check vs Tally snapshots; run the existing eval scenarios against a synced seed company; tool-by-tool mapping (Q7). `get_cash_flow` needs particular attention: it moves from Tally's own report to a computed figure (§4).

## 10. Open questions
| # | Question | Linked risk | Options / notes |
|---|---|---|---|
| Q7 | ~~**Chat tools mapping**~~ | R25 | **Answered in §4** (routing table for all 19 tools; out-of-window dates fail loudly). Confirm the split when the S4 spec is written. |
| Q8 | **Previous FY reports:** the routine month-end set (Part 1, "Month-end snapshots") already captures TB, Bills Receivable/Payable and Stock Summary as-on 31 March. Remaining question: also capture the **full-FY P&L and a Balance Sheet** at each FY close (and a BS at each month-end)? Rule 1 gives P&L/BS no computed fallback (R5), so without these snapshots a past year's P&L or BS cannot be answered at all. | R5, Q20 | Leaning yes — a few extra calls a year |
| Q26 | **During a backup-restore state:** is chat-with-caveat right (decision 13), or should a restore be the one case that blocks chat until the user decides? Our copy may contain vouchers that no longer exist in Tally. | R8, decision 13 | Default: caveat, don't block |
| Q27 | **Live-connected workspaces long-term:** keep the dual path (live Tally for `tally_host` workspaces, DB for sync-agent ones) indefinitely, or migrate live-connected customers to the agent and retire live chat queries? The dual path doubles the S4 tool test matrix. | R25, R28 | Decide before the S4 spec |

Q8, Q26 and Q27 are product decisions to settle first. Q7 is answered in §4. Q8's answer also feeds
Part 1's snapshot capture and Q20.

## 11. Sub-project
| # | Scope | Depends on |
|---|---|---|
| S4 | AI chat on our DB — tool routing per §4, **watermark-aware "still loading" behaviour** (decision 7b), integrity caveats per §5 | S1 (Part 1) |

## 12. Next step
Brainstorm only so far. When approved: settle Q8, Q26 and Q27 → resolve the open design items in §6
→ S4 spec → implementation plan. S4 builds on S1 (Part 1). The S0 results of probes 16, 18 and 22
(Part 1, "S0 probe list") may change Rule 1 and decision 15.
