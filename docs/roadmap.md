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
| **B1b** | Sales / Purchase voucher builders (extends B1a pipeline) | Specced. Blocked on **Group B Task 0** feasibility probe. |
| **B1c** | Debit Note / Credit Note voucher builders | Specced. Part of Group B. |
| **B1d** | Bank statement import + reconciliation | Deferred. Needs its own feasibility probe (BANKALLOCATIONS / BANKDATE / INSTRUMENTNO primitives unvalidated). See [`open-items-parked.md`](open-items-parked.md). |
| **Group A** | UI polish (F4 deferred conversation creation + workspace landing, F5 voucher button disable, F6 responsive drawer) | ✅ Complete 2026-04-12. Spec: `specs/2026-04-12-group-a-ui-enhancements-design.md`. |
| **Group B** | F1 (company dropdown) + F2 (multi-currency) + F3 (Payment vs Purchase) + B1b/B1c + TDS | **In progress, sliced.** Task 0 probes (E1–E8 + TDS + bank-recon) ✅ done 2026-06-08. **F2 (Slice A) ✅ merged.** Building remaining slices B–F (see Active Work). Spec: `specs/2026-04-12-group-b-voucher-types-design.md`. |

### Set C — Sync & Store

| Sub | Scope | Status |
|---|---|---|
| **C1** | Package existing XML bridge as a local connector (tunnel + scheduler) | Not started |
| **C2** | Cloud DB (Postgres + pgvector) with synced Tally data — offline queries | Not started |

Architecture intent: hybrid real-time tunnel + scheduled sync, reusing existing `backend/tally_bridge/`.

---

## Active Work — Next Up

The write-flow (Group B + reconciliation) is being built in **dependency-ordered slices**, one spec→plan→implement→review→merge cycle each:

| Slice | Scope | Status |
|---|---|---|
| **A** | Foreign-currency → INR (F2): extract original currency+amount, code-computed rate, chat-only override, INR-only into Tally, no-rate writes blocked | ✅ **Merged to dev 2026-06-08.** Spec `specs/2026-06-08-fx-inr-conversion-design.md`; review `code-review-fx-inr-2026-06-08.md`. |
| **B** | Supplier Payment against an outstanding bill (Agst Ref) + cheque/instrument details | Next |
| **C** | Purchase invoice + payment + **TDS-deducted journal** | Planned |
| **D** | Sales invoice + receipt + **TDS-receivable journal** | Planned |
| **E** | Credit / Debit Notes (returns) | Planned |
| **F** | Bank-statement reconciliation (mark cleared) | Deferred — see below |

**Group B Task 0 feasibility probes — DONE (2026-06-08).** Results: [`group-b-task0-probe-results-2026-06-08.md`](group-b-task0-probe-results-2026-06-08.md). E1–E8 run live; Debit Note (E5), Credit Note (E6), company list (E7), party-voucher filter (E8) all verified. Two new probes added and verified: **TDS journals persist** (T1a/T1b) and **bank instrument details persist** via `BANKALLOCATIONS.LIST` (B1) — but the **bank-reconciliation date does NOT persist** via voucher import (top-level `BANKDATE` dropped), so reconciliation needs Tally's dedicated mechanism (Slice F / B1d).

**TDS is new scope** (not in the original Group B plan): the Sale and Purchase flows each need three linked vouchers (invoice + settlement + TDS journal). Proven feasible by the probes; needs its own design in Slices C/D.

**In-between UX plan (company picker + chat UX):** before/alongside Slices B–E, scope an intermediate plan for the workspace **company dropdown** (F1, E7 proven) and the chat UX for the multi-voucher review flow. To be specced.

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
