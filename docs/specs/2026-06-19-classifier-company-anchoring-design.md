# Spec: Anchor Vision doc-type classifier to the company (purchase-vs-sales direction)

**Date:** 2026-06-19
**Status:** Design → implement
**Branch:** feat/connect-modal-improvements (current)

## Problem

The Vision document classifier (`backend/services/document_parser.py::build_vision_prompt`)
has **no knowledge of the user's own company**. It decides `doc_type`
(payment/purchase/sales/debit_note/credit_note) purely from the document's
framing. A realistic **supplier invoice** — issued *by* the vendor, with
`Bill To: <our company>` — reads, from the document issuer's perspective, as a
*sales* invoice to the customer (us). So Vision returns `doc_type=sales` with
`party_name = <our company>`, and the orchestrator (`orchestrator.py:289`)
routes it as a Sales voucher with our own company as the Sundry-Creditors party.
That is backwards: from *our* books it is a **purchase**.

**Live-reproduced (2026-06-19):** `purchase_existinggroup.pdf` (supplier "Aqua
Pipes & Fittings Co", `Bill To: Bharat Traders Private Limited`) classified as
**Sales**, party **Bharat Traders Private Limited** → discarded, not written.

**Why it wasn't caught earlier:** prior purchase test PDFs (`gen_hp_laptop_bills.py`)
label the counterparty `Supplier: <name>` and omit a `Bill To:` line, biasing
Vision to "purchase". The realistic supplier-invoice shape was never exercised.

## Fix

Pass the **company name** into the Vision prompt so Claude can orient direction
from *our* perspective:

- If the document is **issued by** `<company>` (we are the seller / "from" party)
  → `sales` (or `credit_note` for a sales return).
- If the document is **billed to** `<company>` (we are the buyer / "Bill To")
  → `purchase` (or `debit_note` for a purchase return; `payment` for an
  immediately-paid expense).
- `party_name` is always the **counterparty**, never `<company>` itself.

When no company is supplied (legacy/tests), the prompt falls back to the current
framing-based rules (no regression).

## Changes

1. **`backend/services/document_parser.py`**
   - `build_vision_prompt(company_name: str | None = None) -> str`.
   - When `company_name` is truthy, inject a "Perspective" block near the
     Classification rules: state the books belong to `<company_name>`, give the
     issued-by → sales / billed-to → purchase rule, and require `party_name` to be
     the counterparty (never `<company_name>`).
   - When falsy, emit the prompt unchanged (back-compat).

2. **`backend/agents/orchestrator.py`**
   - `process_file_upload(...)` gains a `company: str | None = None` parameter.
   - Pass it to `build_vision_prompt(company)` at the call site (~line 229).

3. **`backend/api/chat.py`** (`/chat/upload` handler)
   - Capture the workspace returned by `_verify_workspace_ownership` and derive
     `company = ws_config.get("tally_company") or workspace.name or "Default"`
     (mirror `voucher_action` at chat.py:437). In legacy mode, `request`-level
     company / None.
   - Pass `company=company` into `orchestrator.process_file_upload(...)`.

## Tests (TDD — write first)

Unit (`tests/unit/test_document_parser.py` or new):
- `build_vision_prompt("Bharat Traders Private Limited")` contains the company
  name AND a perspective instruction (issued-by→sales, billed-to→purchase, party
  is the counterparty).
- `build_vision_prompt()` and `build_vision_prompt("")`/`None` == the original
  prompt string (byte-for-byte back-compat — guard against accidental drift).
- The perspective block names the exact company string passed (escaping not
  needed; it's a plain prompt).

Unit (orchestrator plumbing): assert `process_file_upload` forwards `company`
to `build_vision_prompt` (monkeypatch `build_vision_prompt` to capture its arg;
the anthropic client is already mocked in existing upload tests — follow their
pattern).

Integration (if an upload integration test exists with a mock Claude): assert the
company is threaded end-to-end (prompt text seen by the mock contains the company).

## Live validation (after merge-ready)

Re-run the Playwright upload of `purchase_existinggroup.pdf` (realistic supplier
framing, `Bill To: Bharat Traders`) and confirm it now classifies as **Purchase**,
party **Aqua Pipes & Fittings Co**, new ledger under **Sundry Creditors**.
Cross-check a genuine **sales** invoice (issued by Bharat Traders) still → Sales.

## Out of scope

- Receipt voucher, TDS journals, bank reconciliation (separate future slices).
- Changing the orchestrator routing logic itself (only the classification input
  changes).
