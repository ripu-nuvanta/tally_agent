# Plan — Foreign-currency → INR conversion

Spec: `docs/specs/2026-06-08-fx-inr-conversion-design.md`. Branch: `feat/fx-inr-conversion`.
All tasks TDD (test first). DB mode only. Backend run on port 7000 locally (see `.claude.local.md`).

## Task order (dependencies)

**T1 — Config + rate resolution** (`backend/config.py`, new `backend/services/fx.py`)
- Add `FX_DEFAULT_RATES: str=""`, `FX_DEFAULT_RATE: float=0.0`.
- `parse_default_rates(s) -> dict[str,float]`; `resolve_fx_rate(currency, doc_rate, override) -> (Decimal, source)`.
- Tests: precedence, INR→1, unknown→0, malformed config.

**T2 — Document parser** (`backend/services/document_parser.py`)
- Vision prompt: drop "INR", add `currency` + `fx_rate`, "do not convert".
- `ExtractedDocument`: `original_currency: str="INR"`, `fx_rate: Decimal|None=None`.
- `parse_vision_response`: capture both.
- Tests: present/absent/lowercase currency; fx_rate present/null.

**T3 — Voucher builder** (`backend/services/voucher_builder.py`)
- `VoucherData`: `original_currency`, `original_amount`, `fx_rate`.
- `build_payment_voucher_data`: resolve rate, INR = amount×rate (total + GST legs), narration FX trail, warnings.
- Tests: conversion math, GST scaling, narration, INR regression, no-rate block.

**T4 — Rate-override parser** (`backend/services/fx.py`)
- `parse_rate_override(msg) -> float|None`. Tests: all phrasings + false-positive guards.

**T5 — Chat path override** (`backend/api/models.py`, `backend/api/chat.py`, `backend/agents/orchestrator.py`)
- `ChatRequest.pending_entry: dict|None=None`.
- In DB chat path: if pending_entry + parse_rate_override → recompute from original_amount×rate, return updated voucher_review; else normal.
- Tests: override recompute, non-override passthrough, no pending_entry.

**T6 — Upload wiring** (`backend/agents/orchestrator.py` `process_file_upload`)
- Put `original_currency`/`original_amount`/`fx_rate` into the review entry dict; pass warnings.
- Tests: USD-with-rate, USD-no-rate-default, USD-no-rate-blocked, INR regression (integration, mock Tally).

**T7 — Review card** (`frontend/src/components/VoucherReviewCard.tsx`, types)
- `VoucherEntry` gains `original_currency`, `original_amount`, `fx_rate`.
- FX line + hint when non-INR; hidden for INR. Vitest.

**T8 — Chat pending_entry** (`frontend/src/components/ChatWindow.tsx`, `api/client.ts`, types)
- Track current pending entry; include in chat request; clear on approve/discard. Vitest.

**T9 — Fixtures** (`tests/fixtures/`, FE mocks): the 6 fixtures in the spec.

**T10 — Integration + E2E** (mock Tally + mock Claude): upload USD → review → chat override → approve → write w/ INR + FX narration.

**T11 — Playwright**: 4 card states × 3 viewports; assertions + VISUAL CHECKLIST; main-agent inspects PNGs.

**T12 — Code review** (`superpowers:requesting-code-review` / code-review agent) → fix → merge to `dev`.

## Sequencing
- T1→T2→T3→T4 are backend core, mostly additive, one subagent sequence (shared files: fx.py, voucher_builder).
- T5,T6 depend on T1–T4.
- T7,T8 frontend, independent of BE internals (depend on entry shape from T6).
- T9 parallel-able. T10/T11 after BE+FE. T12 last.

## Verification gates
- `pytest tests/unit/ -v` green after each BE task.
- `cd frontend && npm test` green after FE tasks.
- Full `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/` before review.
- BE logs → `logs/` per run.
