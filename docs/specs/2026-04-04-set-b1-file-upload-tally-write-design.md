# Set B1: File Upload + Tally Write — Design Spec

**Date:** 2026-04-04
**Status:** Draft
**Depends on:** Set A1 (Auth + Persistence) — merged

## 1. Overview

Add data entry capability to TallyPrime AI Agent. Users upload expense receipts, purchase invoices, or sales invoices in the chat. The AI extracts structured data, maps to Tally ledgers, presents a review card for human approval/correction, and writes vouchers to Tally.

**Core principle:** Human-in-the-loop. The AI suggests, the user confirms. Every write to Tally requires explicit approval.

### Priority Order (Set B overall)
1. **B1: File Upload + Tally Write** (this spec) — data entry pipeline
2. **B2: Bank Reconciliation** — match bank statements to Tally vouchers
3. **B3: GST Reconciliation** — GSTR-1/3B compliance from Tally data
4. **B4: Purchase Invoice Matching** — verify supplier invoices against Tally

### B1 Sub-phases
- **B1a:** Expense receipts only (first ship — proves full pipeline)
- **B1b:** Purchase invoices (multi-line, stock items, modal review)
- **B1c:** Sales invoices (customer ledgers, GST handling)
- **B1d:** Bulk upload (CSV/Excel bank statements, batch review UI)

## 2. Architecture

### Pipeline Flow

```
User uploads file in chat
  → Frontend sends multipart POST /api/chat (file + optional message)
  → Orchestrator detects file attachment → routes to data entry flow
  → DataEntry pipeline:
      1. PARSE:    file-type router → CSV parser or Claude Vision
      2. VALIDATE: Python arithmetic checks on extracted amounts
      3. INFER:    fetch company's ledger list + group hierarchy + recent voucher patterns
      4. MAP:      match extracted data to Tally ledgers (3-tier: stored rules → fuzzy → AI)
      5. PRESENT:  return structured review card to user in chat
      6. CORRECT:  (optional) user edits fields, system shows updated preview
      7. APPROVE:  user confirms → Tally write (create masters first, then voucher)
      8. LEARN:    store successful mapping for future use
```

### Integration Points

- **Orchestrator** (`backend/agents/orchestrator.py`): Classifies file-attached messages as data entry and routes to the data entry flow. No new agent type — extends existing orchestrator with new tools.
- **Agent Registry**: Same `agent_type: "tally"` — data entry is a capability, not a separate agent.
- **Langfuse/OTEL**: Existing tracing carries through. Data entry spans get additional attributes:
  - `langfuse.trace.name`: `"data_entry"`
  - `document.type`: `"expense"` / `"purchase"` / `"sale"`
  - `document.parse_method`: `"claude_vision"` / `"csv_parser"` / `"text_pdf_parser"`
  - `tally.write_action`: `"create_voucher"` / `"create_ledger"` / `"create_group"`
  - `tally.write_status`: `"success"` / `"failed"`

## 3. Document Parsing Layer

### New Module: `backend/services/document_parser.py`

**Router logic (by file type, no AI classification needed):**
- `.csv`, `.xlsx`, `.xls` → `StructuredParser` (pandas/openpyxl)
- `.jpg`, `.png`, `.heic` → `ClaudeVisionParser`
- `.pdf` (text-extractable) → `TextPDFParser`, fallback to `ClaudeVisionParser`
- `.pdf` (scanned/image) → `ClaudeVisionParser`

### ClaudeVisionParser

Sends image to Claude Sonnet with a structured extraction prompt. Prompt requests:
- Vendor/party name
- Date
- Total amount
- Line items (description, qty, rate, amount)
- GST breakdown (CGST/SGST/IGST rates + amounts)
- Payment mode (cash, bank, UPI)

Returns structured JSON. **No math tools** — Claude extracts, Python validates.

### Post-Extraction Validation (Python)

Deterministic arithmetic checks after extraction:
- Line items sum to subtotal
- GST amounts match (rate × base amount)
- Total = subtotal + GST
- No zero-amount entries
- Date is parseable and within open financial year

If math doesn't add up, flag to user in review card (e.g., "Line items sum to ₹1,450 but document total says ₹1,500 — please verify").

### Data Models

```python
@dataclass
class LineItem:
    description: str
    quantity: Decimal | None
    rate: Decimal | None
    amount: Decimal
    gst_rate: Decimal | None       # e.g., 18.0
    gst_amount: Decimal | None

@dataclass
class GSTBreakdown:
    cgst_rate: Decimal | None
    cgst_amount: Decimal | None
    sgst_rate: Decimal | None
    sgst_amount: Decimal | None
    igst_rate: Decimal | None
    igst_amount: Decimal | None
    gstin: str | None              # vendor's GSTIN

@dataclass
class ExtractedDocument:
    doc_type: str                  # "expense", "purchase", "sale"
    vendor_name: str | None
    date: date
    total_amount: Decimal
    currency: str                  # default "INR"
    line_items: list[LineItem]
    gst: GSTBreakdown | None
    payment_mode: str | None       # "cash", "bank", "upi"
    raw_text: str | None           # OCR'd text for reference
    confidence: float              # 0-1
```

## 4. Ledger Mapping & Learning

### New Module: `backend/services/ledger_mapper.py`

**Three-tier strategy (in order):**

1. **Stored rules** (fastest, free) — check workspace's `ledger_mappings` table
2. **Fuzzy match** (fast, free) — fuzzy-match vendor name against Tally ledger names
3. **AI suggestion** (slowest, costs tokens) — Claude picks best ledger from chart of accounts given document context

### Inference from Existing Tally Data

Before suggesting mappings or creating masters, the system inspects the company's existing structure:
- Fetch ledger list + group hierarchy
- Detect GST ledger organization (separate CGST/SGST/IGST ledgers per rate slab, or combined)
- Fetch recent voucher patterns (sample purchase/sales/payment vouchers to understand line item structure)
- Mirror existing patterns when creating new vouchers
- If company is fresh (empty), fall back to standard Tally GST best practices

### Master Auto-Creation

When a document references entities that don't exist in Tally, the system suggests creating them:

**Three levels (created in dependency order):**

| Level | Example | Tally XML ACTION |
|-------|---------|------------------|
| Group | "SaaS Subscriptions" under Indirect Expenses | `<GROUP ACTION="Create">` |
| Ledger | "Zomato" under Sundry Creditors | `<LEDGER ACTION="Create">` |
| Stock Item | "Dell Monitor 24inch" | `<STOCKITEM ACTION="Create">` (B1b+) |

**Order of operations:** Create missing groups → Create missing ledgers → Create voucher.

All master creation is shown in the review card and requires user approval.

### Learning Loop

- User approves AI suggestion as-is → store mapping with `confidence: 0.8`, `created_from: "ai_suggestion"`
- User corrects a mapping → store with `confidence: 1.0`, `created_from: "user_correction"` (overrides existing)
- Same vendor appears again → stored rule kicks in, no AI call needed
- `use_count` increments on each use for ranking

## 5. Tally Write Layer

### New Module: `backend/tally_bridge/writer.py`

**Responsibilities:**
- Build import XML payloads (`IMPORTDATA` action, various `ACTION` types)
- Submit via existing `TallyClient` (same HTTP POST, different payload)
- Parse Tally's import response (success/error/duplicate)
- Local dry-run validation before submission

### Supported Operations

| Entity | Create | Update (Alter) | Delete |
|--------|--------|----------------|--------|
| Group | ✓ | ✓ | ✓ |
| Ledger | ✓ | ✓ | ✓ |
| Voucher | ✓ | ✓ | ✓ |
| Stock Item | ✓ (B1b+) | ✓ (B1b+) | ✓ (B1b+) |

All operations gated behind user approval flow.

### Import XML Structure

```xml
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>Company Name</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="Payment" ACTION="Create">
            <DATE>20260404</DATE>
            <NARRATION>Uber ride - client meeting</NARRATION>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Travel Expenses</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
              <AMOUNT>-500.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Cash</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>500.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

### Dry-Run Validation (Local Pre-flight)

Before sending XML to Tally:
1. **Balance check** — sum of all ledger entry amounts = 0
2. **Ledger existence** — every ledger name exists in company (from cached list)
3. **Date validation** — valid date, within open financial year
4. **Required fields** — voucher type, ≥2 ledger entries, narration present
5. **GST consistency** — if GST ledgers referenced, rates × base = GST amounts
6. **Amount sanity** — no zero amounts, no unreasonably large amounts (configurable)

Validation failures shown to user before approval step.

### Safety Measures

- **Kill switch** — `TALLY_WRITE_ENABLED` env var (default: true)
- **Dry-run mode** — `TALLY_DRY_RUN` env var validates without sending
- **Duplicate detection** — check for existing voucher with same date + amount + party before creating
- **Audit log** — every write attempt logged to `usage_logs` with full payload
- **Undo capability** — successful writes show "Undo (delete from Tally)" option

### Mock Mode Support

`mock_handler.py` gets a new `handle_import()` method:
- Accepts voucher/ledger/group creation payloads
- Stores in memory
- Updates mock fixture data so subsequent reads reflect new entries
- Enables full end-to-end testing and demo mode without real Tally

## 6. Database Schema

### New Table: `uploaded_files`

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| workspace_id | UUID | FK → workspaces |
| conversation_id | UUID | FK → conversations |
| filename | VARCHAR | original filename |
| mime_type | VARCHAR | detected MIME type |
| file_size | INT | bytes |
| storage_path | VARCHAR | local path (S3 key later) |
| extracted_data | JSONB | parsed ExtractedDocument |
| status | VARCHAR | "uploaded", "parsed", "partially_approved", "fully_approved", "failed" |
| created_at | TIMESTAMP | |

### New Table: `voucher_entries`

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | PK |
| file_id | UUID | FK → uploaded_files (nullable — manual entries have no file) |
| user_id | UUID | FK → users |
| workspace_id | UUID | FK → workspaces |
| conversation_id | UUID | FK → conversations |
| message_id | UUID | FK → messages (the review card message) |
| voucher_type | VARCHAR | Payment / Purchase / Sales |
| voucher_data | JSONB | full voucher payload |
| status | VARCHAR | "draft", "approved", "written", "failed", "deleted" |
| tally_response | JSONB | Tally's import response |
| tally_voucher_number | VARCHAR | returned by Tally on success |
| error_message | VARCHAR | if failed |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

Per-item tracking: one `uploaded_files` row per document, one `voucher_entries` row per voucher. Enables partial approval, individual retry, and per-item audit trail.

### New Table: `ledger_mappings`

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | PK |
| workspace_id | UUID | FK → workspaces |
| vendor_pattern | VARCHAR | normalized vendor name or pattern |
| ledger_name | VARCHAR | Tally ledger to map to |
| voucher_type | VARCHAR | Payment / Purchase / Sales |
| gst_treatment | VARCHAR | nullable, e.g., "GST 18%" |
| confidence | FLOAT | reliability score |
| use_count | INT | times used, for ranking |
| created_from | VARCHAR | "user_correction" or "ai_suggestion" |
| created_at | TIMESTAMP | |

### Migration

New Alembic migration adding all three tables. FKs reference existing `users`, `workspaces`, `conversations`, `messages` tables from Set A1.

## 7. API Changes

### Modified: `POST /api/chat`

Extends to accept `multipart/form-data` when a file is attached:

```
Content-Type: multipart/form-data
Fields:
  - message: string (optional — user context like "office lunch expense")
  - file: binary (uploaded document)
  - conversation_id: string
  - workspace_id: string
```

The chat endpoint detects multipart form data, saves the file, and passes a `file_id` reference to the orchestrator. The orchestrator sees the file reference and routes to the data entry flow instead of the query flow.

### Chat Message Flow

1. **User sends file** → message with `role: "user"`, file reference stored
2. **System parses & maps** → responds with `role: "assistant"`, `data: { type: "voucher_review", entries: [...] }` — the review card
3. **User approves/corrects** → `role: "user"`, approval or correction text
4. **System writes to Tally** → `role: "assistant"`, confirmation with voucher number or error

Full audit trail in conversation history.

## 8. Frontend Changes

### Chat Input — File Attach

- Paperclip/attach icon next to send button
- Click opens file picker (accept: `.jpg,.png,.heic,.pdf,.csv,.xlsx,.xls`)
- Drag-drop onto chat window supported
- File thumbnail/name preview before sending
- File + optional text message sent together

### New Component: `VoucherReviewCard.tsx`

**Single item (B1a — expense receipts):**

Renders inline in chat with editable fields:
- Vendor, Date, Amount, Ledger (dropdown), Paid via (dropdown), Narration
- Each field has inline edit capability
- Ledger dropdown populated from Tally's ledger list

**Button labels (clear action descriptions):**
- **"Write to Tally"** — creates voucher
- **"Edit Entry"** — opens fields for correction
- **"Discard"** — rejects this entry

After edit/correction:
- **"Confirm & Write to Tally"** — writes corrected version
- **"Edit Again"** — back to editing
- **"Discard"** — reject

After successful write:
- Shows "Written to Tally — Voucher #1234"
- **"Undo (delete from Tally)"** link

**Multi-item (B1d — bank statements, future):**

Batch list with per-row Write/Skip/Edit and bulk actions:
- **"Write All to Tally (47)"** — bulk approve mapped items
- **"Review Unmapped (3)"** — items needing attention
- **"Discard All"** — reject entire batch

### New Component: Modal Review (B1b+ — complex invoices)

For multi-line purchase/sales invoices, clicking "Edit Entry" opens a modal with:
- Full form with all fields
- Line items table (add/remove/edit rows)
- GST breakdown
- Ledger dropdowns per line item
- Submit returns to chat with updated review card

## 9. Configuration

### New Environment Variables

```
# File storage
FILE_STORAGE_PATH=./uploads          # local directory (default)
FILE_MAX_SIZE_MB=10                  # per-file limit

# Tally write
TALLY_WRITE_ENABLED=true             # kill switch for all writes
TALLY_DRY_RUN=false                  # validate without sending to Tally
```

### Workspace Config (JSONB in `workspaces.config`)

```json
{
  "tally_host": "172.26.104.48",
  "tally_port": 9000,
  "write_enabled": true,
  "default_payment_ledger": "Cash",
  "auto_approve_threshold": null
}
```

`auto_approve_threshold` reserved for future — auto-write expenses below a threshold without approval. Null = always require approval (B1 default).

## 10. Mock Mode & Demo

- `mock_handler.py` extended with `handle_import()` for voucher/ledger/group writes
- Writes stored in memory, reflected in subsequent read queries
- Same code path as live mode — only the transport differs
- Demo Tally stays consistent: create an expense → "show today's expenses" → it appears

## 11. Exploration Phase (Pre-Implementation)

Before building B1, conduct live Tally exploration to:

1. **Test import XML format** — send a test Payment voucher to real Tally, verify it appears correctly
2. **Inspect GST ledger structure** — how is the company's GST organized?
3. **Fetch sample voucher patterns** — existing payment/purchase/sales vouchers to understand expected format
4. **Test master creation** — create a test ledger and group, verify hierarchy
5. **Test update and delete** — alter and delete the test entries to verify CRUD
6. **Document Tally's error responses** — what comes back for invalid data, duplicates, missing ledgers?
7. **Verify date format** — confirm YYYYMMDD in import XML (different from DD-MM-YYYY in queries)

Results feed back into implementation details (XML field names, error handling, etc.).

## 12. What's NOT in B1

- S3 file storage (local disk is sufficient)
- Auto-approval rules (threshold-based auto-write)
- Email/WhatsApp document ingestion
- Observability improvements (separate effort)
- Bank reconciliation (B2)
- GST reconciliation (B3)
- Purchase invoice matching (B4)
- Payment/billing (Set A2)
