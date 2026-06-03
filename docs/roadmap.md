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
| **Group B** | F1 (workspace pulls company name) + F2 (multi-currency extraction) + F3 (Payment vs Purchase classification) + B1b combined | **Next up.** Spec: `specs/2026-04-12-group-b-voucher-types-design.md`. Plan: `plans/2026-04-12-group-b-voucher-types-plan.md`. Gating step is Task 0 (E1–E8 probes). |

### Set C — Sync & Store

| Sub | Scope | Status |
|---|---|---|
| **C1** | Package existing XML bridge as a local connector (tunnel + scheduler) | Not started |
| **C2** | Cloud DB (Postgres + pgvector) with synced Tally data — offline queries | Not started |

Architecture intent: hybrid real-time tunnel + scheduled sync, reusing existing `backend/tally_bridge/`.

---

## Active Work — Next Up

**Group B (F1 + F2 + F3 + B1b)** is the immediate next batch.

**Gating step:** Group B Task 0 — feasibility probes E1–E8 against live Tally. Must complete before any Group B implementation. See [`plans/2026-04-12-group-b-voucher-types-plan.md`](plans/2026-04-12-group-b-voucher-types-plan.md).

E7 and E8 (added 2026-05-07) are currently unvalidated:
- E7: `get_company_list` envelope
- E8: `get_party_vouchers` TDL filter

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
