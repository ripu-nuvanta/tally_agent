# Open Items — Parked (2026-04-02)

Items from Phases 1–16 that are deferred while we focus on SaaS and compliance features.

**Sources:**
- Architecture explorations (F1–F4, Company Selector): [`docs/plans/2026-03-12-agent-architecture-exploration.md`](plans/2026-03-12-agent-architecture-exploration.md)
- Phase 8 backlog (conversation memory, cached ledger list, GST reports, export, WhatsApp, cross-agent context): [`TALLYPRIME_AGENT_PLAN.md` §9](../TALLYPRIME_AGENT_PLAN.md) (lines 966–984)

## Eval Status (Final — Run 31, stock_reorder_mock)

| Turn | Query | Scores (F/Q/C/Ch) | Notes |
|------|-------|--------------------|-------|
| 1 | Stock reorder | Pass | — |
| 2 | Top customers | Pass | Chart 4/5 |
| 3 | MoM growth | Pass | Chart 5/5 |
| 4 | Q3 vs Q4 | Pass | Clarification question (expected) |
| 5 | Expense % | Pass | Fixed by streaming (34k tokens) |
| 6 | Top 5 change | Pass | Passed with 480s timeout |
| 7 | Avg monthly | Pass | — |

**7/7 turns pass.** All eval scenarios green.

## Parked Architecture Items

### F1: Merge QueryAgent + AnalysisAgent
- Would eliminate handover gaps, reduce token waste from two agent histories
- Risk: 18+ tools in one agent may confuse model
- Status: Open — revisit if handover bugs resurface

### F2-B/C: Session Data Cache
- Option A (pass last N messages) implemented in Phase 14
- Cleaner options: shared session cache (B) or merged agents (C) deferred
- Status: Open — current approach works for 5–7 turn sessions

### F3: Frontend Streaming (SSE/WebSocket)
- Backend streaming done (AnalysisAgent uses `messages.stream()`)
- Frontend still waits for full response; 480s timeout is workaround
- Progressive UI ("Fetching... Analyzing... Charting...") not built
- Status: Open — biggest UX win remaining

### F4: XML-Tagged Structured Output
- Replace `STRUCTURED_RESULT:` prefix with XML tags for robust parsing
- Status: Open — current approach works, XML would be more robust

### Company Selector End-to-End
- Dropdown exists but is display-only
- `<SVCurrentCompany>` plumbing exists in request_builder but is never wired
- Medium-high priority for multi-company deployments
- Status: Open — required before real deployment

### Latency Optimization
- Turns with 76k–106k input context take 240s+
- Frontend streaming would help perceived latency
- Context pruning or summarization not explored
- Status: Open — addressed partially by 480s timeout

## Parked Phase 8 Backlog Items

From [`TALLYPRIME_AGENT_PLAN.md` §9](../TALLYPRIME_AGENT_PLAN.md):

| Item | Status | Notes |
|------|--------|-------|
| Conversation memory (last 10 messages) | Partial | Session history exists, but in-memory only (no persistence) |
| Cached ledger list | Open | Would speed up fuzzy matching / suggestions |
| GST reports (GSTR-1, GSTR-3B, tax liability) | Open | Superseded by compliance feature set |
| Date-relative intelligence | Done | Implemented in Phase 7 |
| Export (PDF/Excel) | Open | — |
| WhatsApp integration | Open | Twilio/Meta webhook, text-only responses |
| Agent architecture refinement | Done | C1 implemented in Phase 12 |
| Cross-agent context preservation | Partial | F2-A done (last N messages), longer sessions untested |

## Parked Tally Write-Agent Items

### Per-voucher-type external-doc-date toggles (Sales/Receipt/Payment)

Purchase has a "Use supplier invoice date" toggle (Voucher Type → Configuration) that gates `<REFERENCE>`/`<REFERENCEDATE>` writes. When OFF, REFERENCEDATE writes are silently overwritten with the voucher's main `<DATE>` field (no error, `altered=1`, readback looks healthy — most insidious silent-failure mode encountered). When ON, the same XML envelope sticks correctly.

Sales (customer PO date), Receipt and Payment (cheque date for post-dated cheques) likely have analogous per-voucher-type toggles, since REFERENCE/REFERENCEDATE have natural meaning on those types too — but the toggle locations and exact behavior have not yet been probed. Required before write-agent supports these fields on those voucher types.

- Owner: write-agent design phase.
- Cross-ref: `LESSONS.md` §14, `docs/tally-write-exploration-v4.md` § "REFERENCEDATE — supplier invoice date (toggle-gated)".
- Status: Open.

### Set B1d feasibility probe — bank reconciliation primitives

Set B1d (bank statement import + reconciliation) is deferred per Group B design but will need its own feasibility probe before implementation, similar to Group B Task 0. Several primitives are currently unvalidated against live Tally:

- `BANKALLOCATIONS.LIST` block structure inside Receipt/Payment bank LEDGERENTRY
- `BANKDATE` field — sets reconciled-with-bank date on a voucher (silent-failure risk per LESSONS §14 if there's a toggle gate)
- `INSTRUMENTNO` and `INSTRUMENTDATE` fields — cheque/UTR no + cheque date
- Whether `BANKDATE` can be set via ALTER on existing Receipt/Payment vouchers (similar to REFERENCEDATE pattern), or only on Create
- Tally's "Bank Statement" import envelope (separate from voucher import) — does it exist as a documented import flavor, or is the right approach to ALTER bank-side fields directly?

- Owner: Set B1d design phase.
- Cross-ref: `LESSONS.md` §14 (silent-overwrite warning), `docs/tally-write-exploration-v4.md` (general write findings).
- Status: Open.
