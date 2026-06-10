# Roadmap

Single source of truth for what's planned next. Closed phases live in [`CLAUDE.md` § Implementation Phases](../CLAUDE.md). Parked / deferred items live in [`open-items-parked.md`](open-items-parked.md).

---

## Operating Mode

**SaaS + DB mode is the default and only maintained mode.** All new work targets DB mode (Postgres + JWT auth + per-workspace conversations). Legacy mode (in-memory sessions, no auth) is frozen — bug fixes only, no new features.

- Enable DB mode: set `DATABASE_URL` and `JWT_SECRET` in `.env`, run `alembic upgrade head`, and run frontend with `VITE_DB_MODE=true`. See [`README.md`](../README.md#running-with-auth--persistence-db-mode).

---

## Feature Sets

The product evolves along three feature sets. Set A is foundational; B and C can proceed in parallel once A is in place.

### Set A — SaaS Platform

| Sub | Scope | Status |
|---|---|---|
| **A1** | Auth (signup/login), workspaces (one per Tally company), persistent conversation history | ✅ Complete — merged. Spec: `specs/2026-04-02-set-a1-auth-persistence-design.md`. |
| **A2** | Billing (Razorpay — India), team management, Tally connection config UI | Not started |

### Set B — Compliance & Automation

| Sub | Scope | Status |
|---|---|---|
| **B1a** | Expense receipt entry (file upload → Vision extract → Tally write — Payment voucher only) | ✅ Complete — merged. Spec: `specs/2026-04-04-set-b1a-expense-entry-plan.md`. |
| **B1b** | Sales / Purchase voucher builders (extends B1a pipeline) | ✅ Complete — merged 2026-06-09 (Group B). |
| **B1c** | Debit Note / Credit Note voucher builders | ✅ Complete — merged 2026-06-09 (Group B). |
| **B1d** | Bank statement import + reconciliation | Deferred. Needs its own feasibility probe (BANKALLOCATIONS / BANKDATE / INSTRUMENTNO primitives unvalidated). See [`open-items-parked.md`](open-items-parked.md). |
| **Group A** | UI polish (F4 deferred conversation creation + workspace landing, F5 voucher button disable, F6 responsive drawer) | ✅ Complete 2026-04-12. Spec: `specs/2026-04-12-group-a-ui-enhancements-design.md`. |
| **Group B** | F1 (company dropdown) + F2 (multi-currency) + F3 (5-type classification) + B1b (Purchase/Sales) + B1c (DN/CN) + DB audit | ✅ **Complete — merged 2026-06-09.** Tasks 0–16. Spec: `specs/2026-04-12-group-b-voucher-types-design.md`; review: `code-review-group-b-2026-06-09.md`. (GST-on-invoices + DN/CN-direction now done — see Active Work.) |

### Set C — Sync & Store

| Sub | Scope | Status |
|---|---|---|
| **C1** | Package existing XML bridge as a local connector (tunnel + scheduler) | Not started |
| **C2** | Cloud DB (Postgres + pgvector) with synced Tally data — offline queries | Not started |

Architecture intent: hybrid real-time tunnel + scheduled sync, reusing existing `backend/tally_bridge/`.

---

## Active Work — Next Up

The documented **Group B** (`specs/2026-04-12-group-b-voucher-types-design.md`) is now built and merged. We implemented exactly the doc (upload-driven, 5-type classification) — not the earlier A–F slice reframing.

| Item | Scope | Status |
|---|---|---|
| **F2 (Slice A)** | Foreign-currency → INR: original currency+amount, code-computed rate, chat-only override, INR-only into Tally, no-rate writes blocked | ✅ **Merged 2026-06-08.** Spec `specs/2026-06-08-fx-inr-conversion-design.md`; review `code-review-fx-inr-2026-06-08.md`. |
| **Group B (F1+F3+B1b/B1c)** | Upload → Vision classifies `payment/purchase/sales/debit_note/credit_note` → route to builder → party + GST + bill allocation → write; company-name dropdown (test-connection); DB audit (UploadedFile + VoucherEntry) | ✅ **Merged 2026-06-09.** Plan `plans/2026-04-12-group-b-voucher-types-plan.md` Tasks 0–16; review `code-review-group-b-2026-06-09.md`. |
| **GST on invoices** | Map extracted GST line items → Input (Purchase/DN) / Output (Sales/CN) GST ledgers, resolved from the workspace's Duties & Taxes ledgers | ✅ **Merged 2026-06-09.** Live-verified (CGST/SGST Input/Output post correctly). |
| **DN/CN posting direction** | Verify a Debit Note reduces the payable and a Credit Note reduces the receivable | ✅ **Fixed + live-verified 2026-06-09** (was inverted; caught by live manual test). `code-review-group-b-2026-06-09.md`. |
| **Write-flow eval** | Eval framework extended for upload→review→write (upload/action turns, `voucher_correctness` rubric, DB-mode login) | ✅ **Merged 2026-06-09.** `docs/eval-write-flow-2026-06-09.md`. |
| **End-to-end live verification** | Real document/PDF → real Claude Vision → classify → live Tally write → read-back → cleanup, all 5 types | ✅ **Verified 2026-06-09** (`logs/manual_test_*_live.log`). |

**Group B Task 0 feasibility probes — DONE (2026-06-08).** Results: [`group-b-task0-probe-results-2026-06-08.md`](group-b-task0-probe-results-2026-06-08.md). E1–E8 verified (DN/CN creation, company list, party-voucher filter). Two extra probes: **TDS journals persist** (T1a/T1b) and **bank instrument details persist** via `BANKALLOCATIONS.LIST` (B1) — but the **bank-reconciliation date does NOT persist** via voucher import, so reconciliation needs Tally's dedicated mechanism.

### Next up — from the write-flow code analysis (`docs/code-analysis-write-flow-2026-06-09.md`)

Correctness is proven live; these are hardening/quality items:
- **SSRF (security, HIGH):** `tally_host`/`tally_port` are user-set with no validation — add an allowlist / block private+link-local ranges.
- **Entry-dict typing + sign-convention single-source** — wire up the `VoucherReviewEntry` Pydantic model in `voucher_action`; extract the per-type debit/credit polarity to one config.
- **Cheap correctness warnings:** DN/CN with no reference (silent On-Account), Vision currency missing → defaults INR, GST ledger missing → warn-not-block.
- **Eval mock GST ledgers** — add CGST/SGST/IGST Input+Output to the mock Tally handler so mock-mode eval scores GST.

### Future work (beyond the current doc — need their own spec)

- **Supplier payment against an outstanding bill** (Agst Ref settlement of an existing payable), **TDS journals** (sale/purchase each need invoice + settlement + TDS journal), and **bank-statement reconciliation** (the reconciliation *date* needs Tally's dedicated mechanism — probe-confirmed it doesn't persist via voucher import).

---

## Test Data

Group B work uses the `Bharat Traders Private Limited` demo company. Backup committed at `seed_data/TDBK1800_100003.001`. Restore + reseed procedures in [`seed-data-setup.md`](seed-data-setup.md).

---

## Key Decisions (Locked)

- **Postgres + pgvector** for cloud DB (covers chat history, agent memory, future Tally data sync)
- **Razorpay** for billing (India market — not Stripe)
- **Existing HTTP XML bridge** reused as local connector (not ODBC)
- **DB mode is default**; legacy mode is frozen

---

## Maintenance Convention

This file is the single source of truth for "what's planned next." Update it when:
- A feature set closes (move from active → ✅ Complete, then summarize in `CLAUDE.md § Implementation Phases`)
- A new feature set is added
- Priority changes (re-order Active Work section)
- A probe / gating step is added or resolved

Don't track active roadmap in `CLAUDE.md` (status only) or in individual spec/plan docs (those are per-feature).
