# Code review — Group B (feat/group-b-voucher-types)

Date: 2026-06-09. Reviewer: code-review skill (high effort, finder angles + verify).
Scope: `git diff dev...HEAD` — 5-voucher-type upload→classify→review→write (~2.8k LOC prod).

## Findings (ranked)

### 1. [CONFIRMED — critical] Editing a Debit/Credit Note collapses both legs onto the party ledger
Backend is self-consistent: orchestrator/`_build_invoice_voucher_data` emits DN→`debit=purchase-contra, credit=party`; CN→`debit=party, credit=sales-contra`, and `chat.py` dispatch reads `purchase_ledger=entry["debit_ledger"]` / `sales_ledger=entry["credit_ledger"]`. A NON-edited DN/CN writes correctly.
But `VoucherEditForm` (save handler, lines 129–146) uses the OPPOSITE mapping for DN/CN (DN: `debit=party, credit=primary`; CN: `debit=primary, credit=party`). After an edit+save, `entry["debit_ledger"]` holds the party ledger, so dispatch passes party as `purchase_ledger` AND `party_ledger` → both voucher legs land on the party ledger. Balances but is meaningless; corrupts the books.
**Fix:** make the edit form's DN mapping match Purchase (`debit=primary, credit=party`) and CN match Sales (`debit=party, credit=primary`), so edit-form output equals the orchestrator convention the dispatch expects. Align `voucherMockData.ts` DN/CN fixtures to the same (orchestrator) convention. Add a test asserting edit→save of a DN/CN preserves distinct debit/credit (purchase-returns vs party).

### 2. [PLAUSIBLE] Reclassify leaves stale party / bill fields on the entry
`VoucherEditForm.handleSave` only sets `party_*` when `showParty` and `bill_reference`/`bill_type` when `showRef`, and `onSave` does a PARTIAL merge. Reclassifying DN→Purchase (or →Payment) leaves the old `bill_type="Agst Ref"`/`bill_reference` (and party fields for →Payment) on the merged entry → Purchase posts with `Agst Ref` instead of `New Ref`; Payment carries a stale party.
**Fix:** when `!showRef`, explicitly clear `bill_reference`/`bill_type` (or set `bill_type` appropriately); when `!showParty`, clear `party_ledger`/`party_name`/`is_party_ledger`. Test reclassify clears them.

### 3. [PLAUSIBLE] No guard when party ledger is empty/missing for party vouchers
If the company has no Sundry Creditors/Debtors group, `available_supplier_ledgers`/`customer_ledgers` are empty and `party_ledger` may be blank; `chat.py` then writes a party voucher with an empty/duplicate party (or KeyErrors → generic error). Mirrors the Slice A no-rate guard gap.
**Fix:** in `voucher_action`, for purchase/sales/DN/CN, if `party_ledger` is empty → return a `voucher_error` ("select a party ledger before writing"). Test it.

## Follow-ups (NOT fixed in this pass — noted)

- **[functional gap] GST ledgers not passed to purchase/sales/DN/CN builders** (orchestrator passes `gst_ledgers=None`). Same as the legacy payment path, so not a regression, but an invoice with GST won't post Input/Output GST ledger legs. Needs per-workspace GST-ledger-name resolution → its own slice/design. Flag to user.
- **[correctness — verify on live Tally] DN/CN posting direction.** The builder convention (DN: party on credit; CN: party on debit) was probe-accepted (E5/E6 CREATED=1) but NOT read-back-verified for *direction* (does the DN actually REDUCE the payable?). Add a read-back probe before relying on it in production.
- **[cleanup] Payment mapper** still calls `resolve_fx_rate` inline while the 4 new mappers use shared `_resolve_fx` — minor drift risk.
- **[cleanup] Dual Purchase/Sales builder families** (stock-based seeder vs new ledger-based) — document which path is canonical for the agent.

## Disposition
Fix 1 (critical), 2, 3 on this branch with tests. Follow-ups tracked for later slices.
