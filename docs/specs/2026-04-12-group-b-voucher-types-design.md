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

#### Backend Unit Tests

**`import_builder.py` — XML builders (4 new × multiple scenarios):**

| Builder | Scenario |
|---------|----------|
| Purchase | Basic: party + expense ledger, correct VCHTYPE/PERSISTEDVIEW/ISINVOICE/ISPARTYLEDGER |
| Purchase | With GST: INPUT CGST/SGST entries, ISDEEMEDPOSITIVE=Yes |
| Purchase | With IGST (interstate) |
| Purchase | With BILLALLOCATIONS.LIST (New Ref) |
| Sales | Basic: party + revenue ledger, reversed polarity from Purchase |
| Sales | With GST: OUTPUT CGST/SGST, ISDEEMEDPOSITIVE=No |
| Sales | With BILLALLOCATIONS.LIST (New Ref) |
| Debit Note | Basic: VCHTYPE="Debit Note", BILLTYPE="Agst Ref" |
| Debit Note | With original invoice reference |
| Credit Note | Basic: VCHTYPE="Credit Note", BILLTYPE="Agst Ref" |
| Credit Note | With original invoice reference |
| All 4 types | Amount balance validation (entries sum to 0) |
| All 4 types | XML escaping of special characters in party/ledger names |
| All 4 types | Required field validation (empty date/ledger/company → ValueError) |

**`voucher_builder.py` — VoucherData construction:**

| Voucher Type | Scenario |
|-------------|----------|
| Payment | Existing tests (no changes expected) |
| Purchase | INR doc → correct party_ledger, is_party_ledger=True, bill_type="New Ref" |
| Purchase | USD doc → inr_amount used (not original_amount), FX fields set |
| Sales | Correct polarity reversal from Purchase |
| Debit Note | bill_reference set, bill_type="Agst Ref" |
| Credit Note | bill_reference set, bill_type="Agst Ref" |
| All types | Narration built from party_name (not vendor_name) |
| All types | GST entries mapped to correct direction (input vs output) |

**`document_parser.py` — extraction + validation:**

| Scenario | What to verify |
|----------|---------------|
| 5-type classification | Each doc_type value parsed correctly from Vision JSON |
| INR document | original_currency="INR", fx_rate=None, inr_amount=total_amount |
| USD document with rate on doc | original_currency="USD", fx_rate extracted, inr_amount=original×rate |
| USD document without rate | fx_rate=None, warning generated |
| EUR document | Non-USD foreign currency handled |
| FX validation pass | original_amount × fx_rate ≈ inr_amount within ₹1 |
| FX validation fail | Warning: amounts don't reconcile |
| DN with invoice ref | original_invoice_ref extracted from Vision JSON |
| CN with invoice ref | original_invoice_ref extracted from Vision JSON |
| party_name field | Parsed correctly, vendor_name backward compat |
| Existing validation | Line items sum, GST rate checks still work |

**`mock_handler.py`:**

| Scenario | What to verify |
|----------|---------------|
| Company list query | Returns `["Bharat Traders Pvt Ltd"]` |
| Party voucher lookup | Returns sample vouchers for known party |
| Party voucher lookup (unknown party) | Returns empty list |
| Write Purchase/Sales/DN/CN | Returns CREATED=1 with incrementing LASTVCHID |

**DB audit trail (`uploaded_files` + `voucher_entries`):**

| Scenario | What to verify |
|----------|---------------|
| File upload | UploadedFile row created with filename, mime_type, size, workspace_id, user_id |
| Duplicate file upload | Same file hash detected, warned/blocked |
| Successful write | VoucherEntry row created with voucher_type, amount, party, master_id, linked to uploaded_file_id |
| Write all 5 types | VoucherEntry.voucher_type correct for each |
| Cancel voucher | VoucherEntry status updated to "cancelled" |
| Delete voucher | VoucherEntry status updated to "deleted" |
| FX write | VoucherEntry stores original_currency, original_amount, fx_rate, inr_amount |
| Query history | Fetch voucher entries by workspace_id returns correct records |

#### Frontend Vitest Tests

**`ConnectCompanyModal` — state matrix:**

| State | Scenario |
|-------|----------|
| Initial | Shows host + port fields, "Connect" button, no dropdown |
| Connecting | Loading spinner while test-connection API in flight |
| Connected | Company dropdown populated, "Create Workspace" enabled after selection |
| Connection failed | Error message, retry possible |
| Mock mode on | Skip connection, auto-fill "Bharat Traders Pvt Ltd", no dropdown |
| Mock mode toggle | Switching mock on/off resets connection state |
| Single company | Dropdown with one option, auto-selected |
| Multiple companies | Dropdown with multiple options, user must pick |

**`VoucherReviewCard` — voucher type × state × currency matrix:**

| Voucher Type | Card State | Currency | Scenario |
|-------------|-----------|----------|----------|
| Payment | Collapsed | INR | Basic: amount, narration, action buttons |
| Payment | Collapsed | — | No party name shown |
| Purchase | Collapsed | INR | Party name, amount, type badge |
| Purchase | Collapsed | USD | Shows both USD + INR amounts |
| Sales | Collapsed | INR | Party name, reversed polarity display |
| Debit Note | Collapsed | INR | Shows "Against: Invoice #X" |
| Credit Note | Collapsed | INR | Shows "Against: Invoice #X" |
| All 5 types | Expanded | INR | Line items, GST breakdown, ledger mappings visible |
| Purchase | Expanded | USD | FX rate + conversion shown |
| Debit Note | Expanded | INR | Original invoice reference visible |
| All 5 types | With warnings | — | Amber warning banner (FX estimate, amount mismatch) |

**`VoucherReviewCard` — user action flow matrix:**

| Flow | Steps | Expected outcome |
|------|-------|-----------------|
| Quick approve | Collapsed → Write to Tally | Write request sent, card shows success state |
| Quick discard | Collapsed → Discard | Card shows discarded state |
| Review then approve | Collapsed → Expand → Write to Tally | Write request sent |
| Review then discard | Collapsed → Expand → Discard | Discarded |
| Edit then approve | Collapsed → Expand → Edit → Save → Write to Tally | Updated values sent |
| Edit then discard | Collapsed → Expand → Edit → Save → Discard | Discarded with edits lost |
| Edit cancel | Collapsed → Expand → Edit → Cancel (back) | Returns to expanded, no changes |
| Edit reclassify | Edit → change voucher type dropdown | Form fields update (party field appears/disappears) |
| FX override | Edit → change INR amount | New INR amount used for write |
| DN/CN ref select | Edit → select from "Against Invoice" dropdown | bill_reference set |
| DN/CN ref manual | Edit → no matches → type manual reference | Free-text reference accepted |
| Buttons disable | Write to Tally clicked | Buttons disable, spinner, no double-submit |
| Write error | Tally returns error | Error shown, buttons re-enable |

**`VoucherEditForm` — responsive + interaction:**

| Scenario | What to verify |
|----------|---------------|
| Mobile (< 768px) | Full-page overlay, "← Back" nav, line items as stacked cards |
| Desktop (≥ 768px) | Modal overlay, line items as table rows |
| Add line item | New empty row/card added |
| Remove line item | Row/card removed, totals recalculated |
| Edit line item | Amount change → total updates, GST recalculates |
| Ledger dropdown per line | Grouped by account group, searchable |
| Party ledger dropdown | Filtered to Sundry Creditors (Purchase/DN) or Sundry Debtors (Sales/CN) |
| Payment type selected | Party ledger field hidden |
| GST breakdown | Editable rates + amounts, auto-recalculate on change |
| FX override field | Shown only when currency ≠ INR, amber highlight |
| Against Invoice dropdown | Shown only for DN/CN, populated from API response |
| Save validation | Required fields check before closing form |

#### Integration Tests (mock Tally)

**Pipeline end-to-end per voucher type:**

| Voucher Type | Currency | Scenario |
|-------------|----------|----------|
| Payment | INR | Existing flow (regression) |
| Purchase | INR | File upload → classify as purchase → party ledger + expense ledger → write |
| Purchase | USD | File upload → FX extraction → INR override → write with INR amount |
| Sales | INR | File upload → classify as sales → party ledger + revenue ledger → write |
| Debit Note | INR | File upload → classify as DN → fetch party vouchers → select ref → write |
| Credit Note | INR | File upload → classify as CN → fetch party vouchers → select ref → write |
| DN (no match) | INR | Party has no existing vouchers → manual ref fallback |

**DB persistence integration:**

| Scenario | What to verify |
|----------|---------------|
| Upload + write | Both UploadedFile and VoucherEntry rows created, linked correctly |
| Upload + discard | UploadedFile created, no VoucherEntry |
| Upload + edit + write | UploadedFile created, VoucherEntry has edited values |
| Cancel after write | VoucherEntry status updated |
| Delete after write | VoucherEntry status updated |

**ConnectCompanyModal integration:**

| Scenario | What to verify |
|----------|---------------|
| Real Tally connection | test-connection returns company list |
| Mock mode | Returns fixture company |
| Connection refused | Error response, frontend shows error |

#### E2E Tests (mock Claude + mock Tally, DB mode)

| Scenario | Flow |
|----------|------|
| Purchase invoice (USD) | Upload → Vision extracts Purchase + USD → FX shown → user edits INR → Write → success + DB row |
| Debit Note with ref | Upload → Vision extracts DN → party vouchers fetched → user selects ref → Write → success |
| Payment (regression) | Existing flow still works unchanged |
| Discard flow | Upload → review → Discard → no Tally write, UploadedFile in DB |
| Edit + reclassify | Upload → Vision says "payment" → user edits to "purchase" in form → adds party → Write |

#### Playwright Visual Tests

**State × viewport matrix (mobile 375px / tablet 768px / desktop 1280px):**

| Component | State | Viewports |
|-----------|-------|-----------|
| VoucherReviewCard | Collapsed — Payment INR | 3 |
| VoucherReviewCard | Collapsed — Purchase USD (dual currency) | 3 |
| VoucherReviewCard | Collapsed — Debit Note with ref | 3 |
| VoucherReviewCard | Collapsed — with warning banner | 3 |
| VoucherReviewCard | Expanded — Purchase with GST + line items | 3 |
| VoucherReviewCard | Expanded — DN with invoice ref | 3 |
| VoucherEditForm | Purchase form — mobile full-page | 1 (mobile) |
| VoucherEditForm | Purchase form — desktop modal | 1 (desktop) |
| VoucherEditForm | DN form with "Against Invoice" dropdown | 1 (desktop) |
| VoucherEditForm | FX override field highlighted | 1 (desktop) |
| VoucherReviewCard | Success state (after write) | 3 |
| VoucherReviewCard | Discarded state | 3 |
| VoucherReviewCard | Error state (write failed) | 3 |
| ConnectCompanyModal | Initial (host + port) | 3 |
| ConnectCompanyModal | Connected — company dropdown | 3 |
| ConnectCompanyModal | Connection error | 3 |
| ConnectCompanyModal | Mock mode | 3 |

Total: ~17 specs × 3 viewports (some mobile/desktop only) ≈ **45-50 Playwright screenshots**

#### Pre-Implementation

| Task | Purpose |
|------|---------|
| Live Tally exploration script | Verify items 1-6 from `docs/tally-write-exploration.md` "Pending Exploration" section before building XML builders |

### 10.3 Fixture Additions

Three categories of test fixtures needed:

#### A. Vision JSON Response Fixtures (`tests/fixtures/vision/`)

These are the JSON responses that Claude Vision returns after analyzing a document. Used by unit tests (document_parser, voucher_builder) and integration tests (mock Claude returns these).

| Fixture | Doc Type | Currency | GST | Special |
|---------|----------|----------|-----|---------|
| `payment_petty_cash_inr.json` | payment | INR | None | Simple single-line expense |
| `payment_with_gst_inr.json` | payment | INR | CGST+SGST | Expense with intra-state GST |
| `purchase_saas_usd.json` | purchase | USD | IGST | FX: rate visible on doc, tests multi-currency flow |
| `purchase_saas_usd_no_rate.json` | purchase | USD | IGST | FX: no rate on doc, agent must estimate |
| `purchase_office_inr.json` | purchase | INR | CGST+SGST | INR purchase, multiple line items |
| `purchase_interstate_inr.json` | purchase | INR | IGST | Interstate purchase (IGST instead of CGST+SGST) |
| `sales_service_inr.json` | sales | INR | CGST+SGST | Service invoice to client |
| `sales_service_eur.json` | sales | EUR | None | Foreign currency sales (export, no GST) |
| `debit_note_return_inr.json` | debit_note | INR | CGST+SGST | Purchase return with original invoice ref |
| `credit_note_return_inr.json` | credit_note | INR | CGST+SGST | Sales return with original invoice ref |
| `debit_note_no_ref.json` | debit_note | INR | None | DN without original invoice reference on document |
| `ambiguous_type.json` | purchase | INR | None | Edge case: could be payment or purchase, tests classification |

#### B. Sample Upload Files (`tests/fixtures/uploads/`)

Actual files used by integration/E2E tests to test the upload endpoint and file type routing. Mock Claude intercepts the Vision call, so file content doesn't need to be real — but file format must be valid.

| File | Format | Purpose |
|------|--------|---------|
| `sample_receipt.jpg` | JPEG image | Tests image upload path, `detect_file_type → "vision"` |
| `sample_receipt.png` | PNG image | Tests PNG handling |
| `sample_invoice.pdf` | PDF (text) | Tests PDF upload path, `detect_file_type → "vision"` |
| `sample_scanned.pdf` | PDF (image) | Tests scanned PDF (same path as image PDF) |
| `sample_statement.csv` | CSV | Tests `detect_file_type → "structured"` (not processed this cycle, but routing must work) |
| `sample_file.xlsx` | Excel | Tests `detect_file_type → "structured"` routing |
| `unsupported.docx` | Word | Tests `detect_file_type → "unsupported"` rejection |
| `large_file.jpg` | JPEG (>10MB) | Tests file size limit rejection |
| `no_extension` | No extension | Tests missing extension handling |

Note: These can be minimal valid files (1×1 pixel image, single-page PDF with "test" text, etc.). They don't need realistic content since Vision is mocked.

#### C. Mock Tally Response Fixtures

| Fixture | Purpose |
|---------|---------|
| Company list response | For F1 ConnectCompanyModal — returns company names |
| Party voucher list (Purchase) | For DN flow — sample Purchase vouchers for a party |
| Party voucher list (Sales) | For CN flow — sample Sales vouchers for a party |
| Party voucher list (empty) | For fallback — no matching vouchers found |
| Write success (Purchase/Sales/DN/CN) | Already covered by generic `_handle_import()` |

#### D. Frontend Mock Data (`frontend/src/__tests__/fixtures/`)

Pre-built review card props for Vitest component tests — one per voucher type × currency × state combination from the Vitest state matrix above. These are TypeScript objects, not JSON files.

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
