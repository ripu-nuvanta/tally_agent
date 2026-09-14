# Spec — Foreign-currency → INR conversion (Slice A of write-flow Group B)

**Date:** 2026-06-08
**Branch:** `feat/fx-inr-conversion`
**Scope:** the document-upload → Payment-voucher flow only (Set B1a path). No Sales/Purchase/DN/CN here.
**Goal:** stop the model from converting foreign currency to INR. Extract the original currency + amount, apply an explicit conversion rate (code-computed), show it, and let the user override the rate **in chat**.

## Decisions (from brainstorming)

1. **Rate source:** doc-if-present, else configured per-currency default, else global fallback. User can override in chat. The model never multiplies — Python does `amount × rate`.
2. **Override UX:** **chat message only** (e.g. "use rate 84.5"). No rate field on the card.
3. **Tally storage:** INR-only. Post the computed INR amount; keep `original_currency` / `original_amount` / `fx_rate` in the entry and in the voucher narration. No Tally native forex fields.
4. **Currency scope:** any non-INR currency, generic. Per-currency default rates with a global fallback.
5. **Override intent parsing:** deterministic regex (no LLM, no LLM math).

## Architecture & data flow

```
upload → vision extract (original currency + amount, NO conversion)
       → build_payment_voucher_data (resolve rate; INR = amount × rate; warn if default used)
       → voucher_review card (shows "USD 100.00 @ ₹83.50 = ₹8,350.00")
       → [user types "use rate 84.5"] → chat path detects pending_entry + rate override
                                       → recompute from original_amount × new rate → updated card
       → approve → Tally Payment voucher (INR amount; FX trail in narration)
```

### Section 1 — Data model & single conversion point

- `backend/services/document_parser.py`
  - `build_vision_prompt()`: replace "All amounts in INR" with: *report amounts in the document's original currency exactly as printed; add `currency` (ISO code, default "INR" if none shown); add `fx_rate` only if the document prints one, else null; DO NOT convert.*
  - `ExtractedDocument`: add `original_currency: str = "INR"` (keep existing `currency` as alias/back-compat) and `fx_rate: Decimal | None = None`. Amounts remain in original currency.
  - `parse_vision_response()`: capture `currency` → `original_currency`, and `fx_rate`.
- **Conversion happens only in** `backend/services/voucher_builder.py` → `build_payment_voucher_data()`:
  - resolve rate (Section 2), compute `inr_total = original_total × rate`, convert each GST entry amount likewise.
  - `VoucherData` gains `original_currency: str`, `original_amount: Decimal`, `fx_rate: Decimal`. `amount` becomes INR.
  - `_build_narration()` appends FX trail when `original_currency != "INR"`: `" | FX: USD 100.00 @ ₹83.50 = ₹8,350.00"`.

### Section 2 — Rate resolution (precedence)

1. chat override for this entry (Section 3)
2. `doc.fx_rate` (printed on doc)
3. configured per-currency default — `FX_DEFAULT_RATES` (`"USD:83.5,EUR:90"`), parsed to dict
4. global fallback `FX_DEFAULT_RATE` (default 0.0 = unknown)

- New `backend/config.py` settings: `FX_DEFAULT_RATES: str = ""`, `FX_DEFAULT_RATE: float = 0.0`. Small helper `resolve_fx_rate(currency, doc_rate, override) -> (rate, source)`.
- Warning rules:
  - rate came from a **default/fallback** → warning: `Used default <CUR>→INR rate <r> — verify or reply 'use rate <n>'.`
  - non-INR and **no rate resolvable** (fallback 0) → loud warning + INR amount left 0/flagged; **write blocked** until a rate is set: `No conversion rate for <CUR> — reply 'use rate <n>' to set it.`
  - INR doc → rate 1, no warning, identical to today.

### Section 3 — Chat-only rate override (frontend-mediated, backend-authoritative)

- Frontend `ChatWindow` tracks the current **pending** `voucher_review` entry (last one not approved/discarded).
- `ChatRequest` (BE model + FE type) gains optional `pending_entry: dict | None`.
- `frontend/src/api/client.ts` / `ChatWindow`: when a voucher is pending and the user sends a chat message, include `pending_entry`.
- Backend chat path (`_chat_db_mode` / orchestrator entry): **before** the query agent — if `pending_entry` present AND message parses as a rate override (`parse_rate_override(message) -> float | None`):
  - recompute `inr = original_amount × new_rate` (total + each GST leg) from the entry's `original_*` fields (never from already-converted INR), set `fx_rate`, clear the default-rate warning, return an updated `voucher_review` card. Do NOT run the Tally query agent.
  - else → normal query path; `pending_entry` ignored.
- `parse_rate_override()` regex matches: `use rate 84.5`, `convert at 84.5`, `rate = 84.5`, `@ 84.5`, `84.50 per usd`. Single number extracted. Rate-ish words but no number → reply asking for the number.
- YAGNI: only the **rate** is chat-overridable; amount/ledger/date stay in the existing Edit form. One pending voucher at a time (most recent).

### Section 4 — UI (review card)

- `VoucherEntry` (TS) + entry dict (BE) gain `original_currency`, `original_amount`, `fx_rate`.
- `VoucherReviewCard.tsx`: when `original_currency !== "INR"`, render an FX line under Amount: `USD 100.00 @ ₹83.50 = ₹8,350.00`, and a hint: `Wrong rate? Reply "use rate <n>" in chat.` `formatAmount` keeps showing the posted INR amount. INR docs render exactly as today (no FX line).
- Default-rate warning surfaces in the existing `warnings` strip.

### Section 5 — Testing

**Backend unit** (`tests/unit/`):
- vision prompt no longer says "INR"; asks for currency + fx_rate.
- `parse_vision_response` captures `currency`/`fx_rate` (present, absent, lowercase code).
- `resolve_fx_rate` precedence: override > doc > per-currency default > fallback; INR→1.
- conversion math: total + GST legs scaled; Decimal precision; rounding to 2dp.
- `parse_rate_override` regex: all accepted phrasings + negative cases (no number, plain text, "rate of return" false-positive guard).
- narration FX trail present for non-INR, absent for INR.
- warnings: default-used warning; no-rate block warning.

**Backend integration** (`tests/integration/`, mock Tally):
- upload USD doc (with doc rate) → review card has INR amount + FX fields.
- upload USD doc (no rate, default configured) → default-used warning.
- upload USD doc (no rate, no default) → write-blocked warning, amount flagged.
- chat override recompute: pending_entry + "use rate 90" → updated card, amounts = original×90, warning cleared.
- regression: INR doc unchanged end-to-end.

**Frontend unit** (Vitest):
- review card renders FX line for USD entry; hides it for INR entry.
- ChatWindow includes `pending_entry` when a voucher is pending; omits it otherwise and after approve/discard.

**E2E (mock Tally + mock Claude)** (`tests/e2e/`):
- upload USD doc → review → "use rate 84.5" in chat → card updates → approve → Payment written with INR amount + FX narration.

**Playwright** (per § Playwright discipline): review-card states = {INR, foreign-with-doc-rate, foreign-default-rate-warning, foreign-no-rate-blocked} × 3 viewports. Assertions before screenshots; VISUAL CHECKLIST blocks; main-agent inspects PNGs.

**Eval:** write-flow eval still out of scope (tracked separately).

## Fixture matrix

- `expense_usd_with_rate.json` — USD, fx_rate printed.
- `expense_usd_no_rate.json` — USD, fx_rate null.
- `expense_eur_no_rate.json` — EUR, fx_rate null (per-currency default).
- `expense_inr.json` — INR regression (no FX line, unchanged).
- `expense_usd_with_gst.json` — USD + GST legs (verify each leg scaled).
- FE mock prop objects mirroring the four card states.

## State matrix (review card × state)

| State | currency | rate source | FX line | warning | write allowed |
|---|---|---|---|---|---|
| INR | INR | n/a (1) | hidden | none | yes |
| foreign + doc rate | USD | doc | shown | none | yes |
| foreign + default | USD | config default | shown | "used default rate" | yes |
| foreign + no rate | USD | none (0) | shown (rate ?) | "no rate — set it" | **no** (blocked) |
| foreign + chat override | USD | chat | shown (new rate) | cleared | yes |

## Out of scope (this slice)

Tally native forex fields; multi-currency line items in different currencies; live FX API; a dedicated FX audit DB table (FX trail lives in narration + entry/history); Sales/Purchase/DN/CN; bank reconciliation.
