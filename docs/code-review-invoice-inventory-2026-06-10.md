# Code review — invoice-entry Phase 2 (inventory line items)

Date: 2026-06-10. Branch `feat/invoice-inventory-items`. (Live-verify pending — Tally was unreachable.)

## Findings

### 1. [CRITICAL] Bill-allocation gross ≠ builder party total → imbalanced voucher
`_write_inventory_voucher` (chat.py:257–260) sets the `New Ref` bill allocation amount to
`float(entry["amount"])` (Vision's extracted total), but `create_purchase/sales_voucher` computes the
party total from the item tuples (Σ qty×rate + per-bucket GST). If Vision's total ≠ Σ(qty×rate)+GST
(rounding, extraction noise) — or after the user **edits qty/rate** — the bill allocation won't match
the party leg → Tally imbalance / "cannot allocate" / wrong bill amount.
**Fix:** compute the gross from the SAME line items the builder uses (reuse the seeder's `_compute_gross`
over the item tuples + gst_mode) for BOTH the bill allocation and the entry's posted amount; never use
Vision's total for the inventory party leg. Add a test asserting bill-alloc gross == builder party total.

### 2. [HIGH] qty<=0 / silent qty fallback posts zero-qty stock lines
`_write_inventory_voucher` uses `float(line.get("qty") or 0)` / `rate or 0` — a missing qty silently
posts a 0-qty (or 0-rate) stock line. **Fix:** block the write if any inventory line has qty<=0 or
rate<=0 → `voucher_error` "Line '<item>' is missing quantity/rate — fix it before writing."

### 3. [HIGH] Mixed invoice: qty-null lines silently dropped
Goods detection = "any line has qty"; but `resolve_line_items` drops qty-null lines. A mixed invoice
(some lines with qty, some without) posts only the qty lines → gross < full invoice, silent under-post.
**Fix:** if the invoice routed to inventory but NOT all line items have a positive qty, block the write
with a clear message listing the lines needing qty (user fixes them in the card). No silent drop.

### 4. [MEDIUM] `_idempotent` swallows too much
The create_unit/group/item "already exists" guard catches any error containing "exist"/"duplicate",
hiding real failures (bad group, Tally down, perms) → confusing downstream "not found". **Fix:** narrow
to the specific already-exists Tally response; log + re-raise anything else.

### 5. [MEDIUM] Frontend create_new/matched state hole
Toggling "Create new" off clears `matched_item` but keeps the typed `stock_name`, allowing
`create_new=false && matched_item=null`. **Fix:** enforce matched XOR create_new — toggling off requires
re-selecting an existing item (or the row is invalid and Write is blocked).

## Confirmed safe
Unit→group→item creation order; matched dropdown prepopulated; qty×rate recompute on edit; Phase-1 dedup
re-derive + FX/party guards still run before the inventory write; line table hidden for accounting-only.

## Disposition
Fix 1 (critical), 2, 3, 4, 5 on this branch with tests, then live-verify (items in stock grid +
balanced voucher) once Tally is reachable, then merge.
