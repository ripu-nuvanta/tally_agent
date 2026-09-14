# Code review — FX→INR conversion (feat/fx-inr-conversion)

Date: 2026-06-08. Reviewer: code-review skill (high effort, 7 finder angles + verify).
Scope: `git diff dev...HEAD` — backend/services/fx.py, voucher_builder.py, document_parser.py,
orchestrator.py, api/chat.py, api/models.py, config.py; frontend VoucherReviewCard, ChatWindow, types.

## Findings (ranked)

### 1. [CONFIRMED — critical] No-rate state is not write-blocked server-side
`resolve_fx_rate` returns rate 0 / `rate_source="none"` for a foreign doc with no rate → INR
amount becomes 0. The review card shows a warning, but nothing stops the write:
`writer.validate_voucher` (writer.py:99–115) only checks amount is present + entries balance
(0 == 0 balances), and `voucher_action` (chat.py:222–268) passes `entry["amount"]` through with
no magnitude/rate guard. The Approve button is enabled (status stays "draft").
→ A user can write a ₹0 Payment voucher. Violates spec ("write blocked until a rate exists").
**Fix:** reject in `voucher_action` when a foreign entry has no usable rate (amount ≤ 0 or
fx_rate falsy) → return a `voucher_error`; add an `amount > 0` invariant to `validate_voucher`;
disable the FE Approve button for that state.

### 2. [PLAUSIBLE] recompute silently yields 0 / KeyErrors on a partial pending_entry
`recompute_entry_with_rate` uses `entry.get("original_amount", 0)` (silent 0 → ₹0 result) and
`g["ledger"]`/`g["amount"]` on `original_gst_entries` (KeyError). A round-tripped entry from an
older message (pre-FX fields) or malformed payload → wrong amount or crash on the override path.
**Fix:** if `original_amount` missing/0 for a non-INR entry, return a clarification instead of a
silent 0; use `.get` on gst keys and skip malformed legs.

### 3. [PLAUSIBLE] parse_rate_override over-matches bare "at <num>"
The `\bat\s+<num>` pattern matches non-rate sentences ("flat at 84.5 per day", "meet at 5")
while a voucher is pending → false override, mangles the entry instead of answering the user.
**Fix:** require a rate/currency cue near the number; drop the bare-"at" branch or anchor it.

### 4. [PLAUSIBLE — drift] Conversion/format logic duplicated across the two paths
INR conversion is implemented in both `build_payment_voucher_data` (initial) and
`recompute_entry_with_rate` (override); FX-trail string built in two places; `_round_inr` exists
in both fx.py and voucher_builder.py; FE `formatAmount` duplicates `utils/format.ts:formatINR`.
A change to rounding/format/conversion in one path silently diverges from the other (the
override result no longer matches what the builder would produce). 
**Fix:** one shared `apply_fx_rate`/`round_inr`/`fx_trail` used by both; FE reuse `formatINR`.

### 5. [NOTE — altitude, next slice] FX + chat-override are Payment/DB-mode-specific
Conversion lives in the Payment builder and override detection in `_chat_db_mode`. Sales/Purchase
(next slices) will need both. Not a bug now; generalize when those land so logic isn't duplicated.

### 6. [NOTE] currency silently defaults to INR when vision omits it
If the model returns no `currency`, `parse_vision_response` defaults to "INR" → a foreign amount
is treated as INR. Mitigated by the doc-rate/warning path for known-foreign docs, but a missed
currency is a silent mis-post. Consider surfacing a low-confidence warning when currency is absent
but the document hints otherwise. Tracked as follow-up.

## Disposition
Fix 1 (critical), 2, 3, 4 on this branch with tests. 5–6 noted as follow-ups (5 = next slice).
