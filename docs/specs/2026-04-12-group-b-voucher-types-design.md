# Group B: Multi-Voucher Types + Company Lookup + Multi-Currency — Design Spec

**Date:** 2026-04-12
**Status:** Draft
**Depends on:** Set B1a (Expense Entry) — merged, Group A (UI Enhancements) — merged

## 1. Overview

Extend the data entry pipeline from Payment-only to 5 voucher types (Payment, Purchase, Sales, Debit Note, Credit Note), add multi-currency extraction with INR override, auto-populate workspace company name from Tally, and upgrade the review card UI with progressive disclosure and a full edit form.

**Combines:** F1 (company name), F2 (multi-currency), F3 (voucher classification), B1b (Purchase/Sales/DN/CN builders).

**Not in scope:** Stock items (needs live Tally exploration first — see Appendix A), Receipt voucher (deferred to B1d/bank statements), FX rate API lookup (user overrides manually for now).

## 2. Decisions

| Item | Decision |
|------|----------|
| Voucher types | 5: Payment, Purchase, Sales, Debit Note, Credit Note |
| Stock items | Deferred — ledger-only vouchers this cycle |
| Company name (F1) | ConnectCompanyModal queries Tally for company list → dropdown. Workspace name = Tally company name (not editable separately) |
| Multi-currency (F2) | Extract in original currency. Agent estimates INR conversion. User overrides with actual bank-debited INR amount in review card. No FX API — added later. |
| Classification (F3) | Vision prompt classifies into 5 doc types → routes to appropriate builder |
| Review card UI | 3-state progressive disclosure: Collapsed → Expanded (read-only) → Edit form (full-page mobile / modal desktop) |
| DN/CN references | Voucher lookup — fetch recent party vouchers from Tally, dropdown to match original invoice. Fallback to free-text if no matches. |
| DB audit trail | Populate `uploaded_files` and `voucher_entries` tables during pipeline (models already exist) |
| Mock writes | Already generic in `_handle_import()`. Add company list + party voucher lookup mock responses. |

## 3. Document Parser Changes

**File:** `backend/services/document_parser.py`

### 3.1 ExtractedDocument Model Additions

```python
@dataclass
class ExtractedDocument:
    doc_type: str                    # "payment" | "purchase" | "sales" | "debit_note" | "credit_note"
    vendor_name: str | None          # RENAMED: party_name in new code
    party_name: str | None           # vendor or customer name (type-neutral)
    date: str
    total_amount: Decimal            # total in original currency
    original_currency: str           # "INR", "USD", "EUR", etc.
    original_amount: Decimal         # same as total_amount (explicit original)
    fx_rate: Decimal | None          # rate from document or agent estimate
    inr_amount: Decimal              # converted INR amount (= original × fx_rate if foreign, else = total_amount)
    line_items: list[LineItem]
    gst: GSTBreakdown | None
    payment_mode: str | None
    raw_text: str | None
    confidence: float
    currency: str                    # DEPRECATED: use original_currency
    original_invoice_ref: str | None # for DN/CN: reference from document text
```

Note: `vendor_name` kept temporarily for backward compat, `party_name` is the canonical field going forward. Remove `vendor_name` after migration.

### 3.2 Vision Prompt Update

Replace current prompt with one that:
- Classifies into 5 types: `payment | purchase | sales | debit_note | credit_note`
- Extracts currency code + amounts in original currency (not forced to INR)
- Extracts FX rate if visible on document
- Extracts party GSTIN separately
- For DN/CN: extracts original invoice reference if mentioned on document
- Returns new JSON schema with `original_currency`, `fx_rate`, `original_invoice_ref` fields

### 3.3 Validation Update

`validate_extracted_amounts()` adds:
- Foreign currency check: `original_amount × fx_rate ≈ inr_amount` (within ₹1 tolerance)
- Warning if currency ≠ INR and no FX rate found: "Using estimated rate — please verify INR amount"

**FX rate estimation (no API):** When the document shows an FX rate, use it. When the document shows both original currency and INR amounts, derive the rate. When neither is available, the Vision prompt instructs Claude to estimate a reasonable rate based on its training data. This is explicitly flagged as "estimated" in the review card — the user is expected to override with the actual bank-debited amount.

## 4. Voucher Builder + Import Builder

### 4.1 VoucherData Model Additions

**File:** `backend/services/voucher_builder.py`

```python
@dataclass
class VoucherData:
    voucher_type: str          # "Payment" | "Purchase" | "Sales" | "Debit Note" | "Credit Note"
    date: str                  # YYYYMMDD
    debit_ledger: str
    credit_ledger: str
    amount: Decimal
    narration: str
    gst_entries: list[dict]
    party_ledger: str | None   # NEW: for Purchase/Sales/DN/CN
    is_party_ledger: bool      # NEW: flag for ISPARTYLEDGER XML tag
    bill_reference: str | None # NEW: for DN/CN, original invoice ref
    bill_type: str             # NEW: "New Ref" for Purchase/Sales, "Agst Ref" for DN/CN
```

### 4.2 New Builder Functions

**`voucher_builder.py`** — add alongside existing `build_payment_voucher_data()`:
- `build_purchase_voucher_data(doc, party_ledger, purchase_ledger, gst_ledgers)` → VoucherData
- `build_sales_voucher_data(doc, party_ledger, sales_ledger, gst_ledgers)` → VoucherData
- `build_debit_note_data(doc, party_ledger, purchase_ledger, gst_ledgers, original_ref)` → VoucherData
- `build_credit_note_data(doc, party_ledger, sales_ledger, gst_ledgers, original_ref)` → VoucherData

### 4.3 XML Import Builders

**File:** `backend/tally_bridge/import_builder.py`

Add 4 new functions alongside existing `build_create_payment_voucher()`:
- `build_create_purchase_voucher(...)`
- `build_create_sales_voucher(...)`
- `build_create_debit_note(...)`
- `build_create_credit_note(...)`

### 4.4 XML Differences by Type

| Field | Payment | Purchase | Sales | Debit Note | Credit Note |
|-------|---------|----------|-------|------------|-------------|
| VCHTYPE | Payment | Purchase | Sales | Debit Note | Credit Note |
| PERSISTEDVIEW | Accounting Voucher View | Invoice Voucher View | Invoice Voucher View | Invoice Voucher View | Invoice Voucher View |
| ISINVOICE | — | Yes | Yes | Yes | Yes |
| Party ledger | No | Yes (credit) | Yes (debit) | Yes (credit) | Yes (debit) |
| ISPARTYLEDGER | — | Yes | Yes | Yes | Yes |
| GST direction | Input | Input | Output | Input (reversal) | Output (reversal) |
| BILLALLOCATIONS | — | New Ref | New Ref | Agst Ref | Agst Ref |
| Entry tag | ALLLEDGERENTRIES.LIST | LEDGERENTRIES.LIST | LEDGERENTRIES.LIST | LEDGERENTRIES.LIST | LEDGERENTRIES.LIST |

### 4.5 Live Exploration Required

The verified operations summary in `docs/tally-write-exploration.md` confirms Sales and Purchase creation works, but with `ALLLEDGERENTRIES.LIST` and `PERSISTEDVIEW="Accounting Voucher View"`. The following are **unverified against live Tally**:

1. `LEDGERENTRIES.LIST` vs `ALLLEDGERENTRIES.LIST` for Purchase/Sales — does it matter?
2. `Invoice Voucher View` vs `Accounting Voucher View` as PERSISTEDVIEW value
3. `BILLALLOCATIONS.LIST` — does it work? Is it required?
4. `ISPARTYLEDGER` — does Tally reject without it?
5. Debit Note / Credit Note creation — not tested at all
6. Stock item creation XML format (for future B1b-phase-2)

**Action:** Write a live exploration script as the first implementation task. Test these combinations against real Tally before building the final XML builders. Update `docs/tally-write-exploration.md` with findings.

## 5. F1 — ConnectCompanyModal + Company Lookup

### 5.1 Backend

**New query:** `get_company_list(host, port)` in `backend/tally_bridge/queries/masters.py` — XML request to fetch loaded company names from an arbitrary Tally host:port.

**New endpoint:** `POST /api/tally/test-connection` — accepts `{ host, port }`, calls target Tally, returns `{ connected: bool, companies: ["Company A", "Company B"] }`. Requires JWT auth.

### 5.2 Frontend

**`ConnectCompanyModal.tsx` new flow:**
1. User enters host + port
2. Clicks "Connect" (or auto-triggers on port blur)
3. Frontend calls `POST /api/tally/test-connection`
4. On success: company dropdown populated with returned names
5. User selects company → becomes `workspace.name` AND `workspace.config.tally_company`
6. "Create Workspace" enabled only after company selected
7. Mock mode toggle: skip Tally query, auto-fill "Bharat Traders Pvt Ltd"

### 5.3 Mock Handler

Add company list response to `mock_tally_request()` → returns `["Bharat Traders Pvt Ltd"]`.

## 6. Voucher Lookup for DN/CN

### 6.1 Backend

**New query:** `get_party_vouchers(party_name, voucher_types, company)` in `backend/tally_bridge/queries/vouchers.py` — TDL collection query filtered by party ledger name and voucher type. Returns list of `{ voucher_number, date, amount, voucher_type, ref }`.

**Pipeline integration:** When orchestrator classifies as DN/CN:
1. Identify party name from extracted document
2. Call `get_party_vouchers()` — Purchase vouchers for DN, Sales vouchers for CN
3. Include voucher list in review card response for frontend dropdown

### 6.2 Frontend

Edit form (state ③) for DN/CN gets "Against Invoice" dropdown. Options: `#{number} — {date} — ₹{amount}`. Selected reference → `bill_reference` on VoucherData.

### 6.3 Fallback

If party doesn't exist in Tally or no matching vouchers found, dropdown is empty → falls back to free-text field for manual reference entry.

### 6.4 Mock Handler

Returns 2-3 sample vouchers for the fixture company when it detects the party voucher query.

## 7. Frontend Review Card Redesign

### 7.1 Component Structure

```
VoucherReviewCard (collapsed state — all types)
├── VoucherReviewExpanded (read-only detail view)
└── VoucherEditForm (full-page mobile / modal desktop)
    ├── PartyLedgerSelect
    ├── LineItemEditor (add/remove/edit rows as cards)
    ├── GSTBreakdown
    ├── FXOverride (shown when currency ≠ INR)
    └── VoucherRefSelect (shown for DN/CN only)
```

### 7.2 Three-State Progressive Disclosure

**① Collapsed (default in chat):**
- Type badge with color coding (Payment=blue, Purchase=orange, Sales=green, DN=red, CN=amber)
- Party name, date, total in INR (+ original currency if foreign)
- "Show details" toggle
- Action buttons: Write to Tally / Discard
- Validation warnings as amber banners

**② Expanded (read-only, still inline):**
- Line items with ledger mappings
- GST breakdown
- FX rate and conversion (if applicable)
- Bill reference (if DN/CN)
- "Edit" button opens form
- "Hide details" toggle

**③ Edit form:**
- **Mobile (< 768px):** Full-page overlay with "← Back to chat" / "Save" header nav. Line items as stacked editable cards.
- **Desktop (≥ 768px):** Modal overlay. Line items as compact table with editable cells.
- Fields: voucher type dropdown (can reclassify), party ledger dropdown, date picker, line items (description, amount, ledger dropdown per row, add/remove), GST breakdown, INR override (for FX), "Against Invoice" dropdown (DN/CN only).
- Save → closes form → updates collapsed card with new values.

**User flows:**
- Quick approve: ① → "Write to Tally"
- Review then approve: ① → ② → "Write to Tally"
- Edit then approve: ① → ② → ③ → Save → ① → "Write to Tally"

### 7.3 Ledger Dropdowns

Populated from workspace's cached ledger list (already fetched by agent pipeline). Grouped by Tally account group (Sundry Creditors, Sundry Debtors, Indirect Expenses, etc.).

## 8. Orchestrator Pipeline Changes

### 8.1 Current Flow (Payment only)

```
File upload → detect_file_type → Vision extraction → validate →
build_payment_voucher_data → present review card → write Payment
```

### 8.2 New Flow (5 types)

```
File upload → detect_file_type → Vision extraction (with classification) → validate
  → route by doc_type:
    ├── "payment"     → build_payment_voucher_data → review card
    ├── "purchase"    → build_purchase_voucher_data → review card
    ├── "sales"       → build_sales_voucher_data → review card
    ├── "debit_note"  → fetch party Purchase vouchers → build_debit_note_data → review card (with ref dropdown)
    └── "credit_note" → fetch party Sales vouchers → build_credit_note_data → review card (with ref dropdown)
  → user reviews/edits → write to Tally (appropriate builder)
```

### 8.3 Key Changes

- Classification comes from Vision extraction (`doc_type` field), not a separate step
- New routing logic after extraction picks correct voucher builder
- DN/CN: extra Tally query to fetch matching vouchers before presenting review card
- `voucher-action` endpoint accepts `voucher_type` in request payload and dispatches to correct `import_builder` function (currently hardcoded to Payment)

## 9. DB Audit Trail

### 9.1 Existing Models (already in `backend/db/models.py`)

- `UploadedFile` — filename, mime_type, size, storage_path, workspace_id, user_id
- `VoucherEntry` — voucher_type, amount, party, tally_response, master_id, linked to uploaded_file_id

### 9.2 Pipeline Integration

- **On file upload:** Create `UploadedFile` row with file metadata, linked to workspace
- **On successful Tally write:** Create `VoucherEntry` row with voucher details + Tally response (LASTVCHID, CREATED count), linked to the uploaded_file
- **On cancel/delete:** Update `VoucherEntry` with cancel/delete status

This enables:
- Audit trail: which files produced which Tally vouchers
- Duplicate detection: don't re-process same file (hash-based check)
- History: "show all vouchers written by this workspace"

## 10. Mock Handler + Testing Strategy

### 10.1 Mock Handler Additions

| Query | Response |
|-------|----------|
| Company list | `["Bharat Traders Pvt Ltd"]` |
| Party voucher lookup | 2-3 sample vouchers per party |
| Write (any type) | Already generic — works for all voucher types |

### 10.2 Test Plan

| Layer | What | Type |
|-------|------|------|
| `import_builder.py` | XML correctness for 4 new builders — tags, polarity, PERSISTEDVIEW, BILLALLOCATIONS | Unit |
| `voucher_builder.py` | Routing logic, VoucherData construction for each type, FX fields | Unit |
| `document_parser.py` | Updated Vision prompt parsing, multi-currency fields, 5-type classification, FX validation | Unit |
| `mock_handler.py` | Company list + party voucher lookup responses | Unit |
| `ConnectCompanyModal` | Connection flow, dropdown population, mock mode fallback | Frontend Vitest |
| `VoucherReviewCard` | Collapsed/expanded/edit states for all 5 types, FX override, DN/CN ref dropdown | Frontend Vitest |
| `VoucherEditForm` | Mobile full-page vs desktop modal, line item add/remove, save round-trip | Frontend Vitest |
| Orchestrator pipeline | File upload → extraction → correct builder → review card → write, for each type | Integration (mock Tally) |
| Full E2E | DB mode: upload → review → write → verify, Purchase + DN scenarios minimum | E2E (mock Claude + mock Tally) |
| Playwright visual | Review card states × 3 viewports, ConnectCompanyModal with dropdown × 3 viewports | Playwright |
| Live exploration | Verify Purchase/Sales/DN/CN XML against real Tally before building final builders | Pre-implementation script |

### 10.3 Fixture Additions

Sample Vision responses for each of 5 doc types:
- Payment: petty cash receipt (INR)
- Purchase: SaaS vendor invoice (USD — tests FX flow)
- Sales: service invoice to client (INR)
- Debit Note: purchase return referencing an existing invoice
- Credit Note: sales return referencing an existing invoice

## Appendix A: Stock Item Support (Deferred — B1b Phase 2)

The official Tally docs show Sales/Purchase vouchers with `ALLINVENTORYENTRIES.LIST` for stock items. This includes:
- `STOCKITEMNAME`, `RATE` (format: "15000.00/nos"), `ACTUALQTY`, `BILLEDQTY`
- `BATCHALLOCATIONS.LIST` with `GODOWNNAME`, `BATCHNAME`
- `ACCOUNTINGALLOCATIONS.LIST` for the accounting entry per stock item

This format is **copied from official docs but never live-tested** on TallyPrime 7.0+. Before implementing:
1. Live exploration script must verify: stock item creation XML (NAME.LIST requirement likely applies), inventory entries in vouchers, UOM handling, godown references
2. Update `docs/tally-write-exploration.md` with findings
3. Then build stock item support as B1b-phase-2

This is needed for distributor (Bharat Traders) and manufacturing use cases where Purchase/Sales involve physical goods.
