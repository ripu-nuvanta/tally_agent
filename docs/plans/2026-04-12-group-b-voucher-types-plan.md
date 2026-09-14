# Group B: Multi-Voucher Types Implementation Plan

> **✅ STATUS: COMPLETE — merged to `dev` 2026-06-09.** All tasks (0–16) implemented and shipped; the
> unticked `- [ ]` checkboxes below are a historical planning artifact (not re-ticked individually).
> Live-verified end-to-end (real Vision → live Tally → read-back). See `docs/code-review-group-b-2026-06-09.md`,
> `docs/group-b-task0-probe-results-2026-06-08.md`, and the roadmap. Follow-on slices (GST-on-invoices,
> DN/CN direction fix, invoice no. + dedup, inventory line items) shipped separately — see roadmap.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the data entry pipeline from Payment-only to 5 voucher types (Payment, Purchase, Sales, Debit Note, Credit Note), add multi-currency extraction, auto-populate workspace company name from Tally, upgrade the review card UI with progressive disclosure, and persist audit trail to DB.

## Why combined (F1 + F2 + F3 + B1b)

These four items all modify the same vertical pipeline — `document_parser → voucher_builder → import_builder → writer → orchestrator` — and shipping them together avoids multiple passes through the same code:

- **F1** (workspace creation pulls company name from Tally): `ConnectCompanyModal` should query Tally's company list and present exact names as a dropdown stored in `workspace.config.tally_company`. Prevents the `SVCurrentCompany` mismatch errors hit during the B1a smoke test.
- **F2** (USD→INR multi-currency extraction): Claude Vision prompt needs explicit multi-currency handling. Extract `line_items_currency`, `total_currency`, `fx_rate`, `inr_total` separately; validator checks `line_items × fx_rate ≈ inr_total` instead of naive sum. Non-deterministic amounts across runs on the same PDF (1682.6 vs 1730.0 on Anthropic invoice) drove this.
- **F3** (Payment vs Purchase voucher classification): blocks on B1b — needs the Purchase builder to exist. Extraction classifies receipt type (expense receipt vs vendor invoice); orchestrator routes to the appropriate voucher builder.
- **B1b** (Sales/Purchase voucher builders): extends `import_builder.py` for Sales/Purchase. `PERSISTEDVIEW`, `ISPARTYLEDGER`, `LEDGERENTRIES.LIST` differ from Payment. GST: OUTPUT CGST/SGST for Sales, INPUT CGST/SGST for Purchase. XML format verified in `docs/tally-write-exploration-v4.md`.

F1 also touches workspace config, which F2 may need (currency settings per workspace).

**Architecture:** Widen existing B1a pipeline at every layer: document_parser (multi-currency + 5-type classification) → voucher_builder (4 new builder functions) → import_builder (4 new XML builders) → writer (4 new write methods) → orchestrator (routing by doc_type) → chat API (dispatch by voucher_type) → frontend (3-state review card + edit form). New tally_bridge query for company list (F1) and party voucher lookup (DN/CN). DB audit via existing UploadedFile/VoucherEntry models.

**Tech Stack:** Python (FastAPI, httpx, xml.etree), React (Vite, Tailwind), Claude Vision API, PostgreSQL (SQLAlchemy async), Playwright

**Spec:** `docs/specs/2026-04-12-group-b-voucher-types-design.md`

**BLOCKING PRE-REQUISITE:** Task 0 (Live Tally Exploration) MUST complete before Task 3 (Import Builders). Tasks 1-2 can run in parallel with Task 0.

---

## File Map

### New Files
| File | Responsibility |
| `scripts/explore_tally_invoice_formats.py` | Live exploration script — tests Purchase/Sales/DN/CN XML against real Tally |
|------|---------------|
| `tests/fixtures/vision/payment_petty_cash_inr.json` | Vision fixture: simple INR payment |
| `tests/fixtures/vision/payment_with_gst_inr.json` | Vision fixture: payment with CGST+SGST |
| `tests/fixtures/vision/purchase_saas_usd.json` | Vision fixture: USD purchase with FX rate |
| `tests/fixtures/vision/purchase_saas_usd_no_rate.json` | Vision fixture: USD purchase, no FX rate |
| `tests/fixtures/vision/purchase_office_inr.json` | Vision fixture: INR purchase, multi-line |
| `tests/fixtures/vision/purchase_interstate_inr.json` | Vision fixture: IGST purchase |
| `tests/fixtures/vision/sales_service_inr.json` | Vision fixture: INR sales invoice |
| `tests/fixtures/vision/sales_service_eur.json` | Vision fixture: EUR export, no GST |
| `tests/fixtures/vision/debit_note_return_inr.json` | Vision fixture: DN with invoice ref |
| `tests/fixtures/vision/credit_note_return_inr.json` | Vision fixture: CN with invoice ref |
| `tests/fixtures/vision/debit_note_no_ref.json` | Vision fixture: DN without ref |
| `tests/fixtures/uploads/sample_receipt.jpg` | Minimal JPEG for upload path tests |
| `tests/fixtures/uploads/sample_receipt.png` | Minimal PNG for upload path tests |
| `tests/fixtures/uploads/sample_invoice.pdf` | Minimal PDF for upload path tests |
| `tests/fixtures/uploads/unsupported.docx` | Invalid format for rejection tests |
| `tests/unit/test_import_builder_invoice.py` | Unit tests for Purchase/Sales/DN/CN XML builders |
| `tests/unit/test_voucher_builder_multi.py` | Unit tests for 4 new voucher builder functions |
| `tests/unit/test_document_parser_multi.py` | Unit tests for multi-currency + 5-type parsing |
| `tests/unit/test_mock_handler_group_b.py` | Unit tests for company list + party voucher mock |
| `tests/unit/test_writer_multi.py` | Unit tests for TallyWriter Purchase/Sales/DN/CN methods |
| `tests/unit/test_audit_trail.py` | Unit tests for UploadedFile/VoucherEntry DB persistence |
| `backend/api/tally.py` | New router: `POST /api/tally/test-connection` |
| `frontend/src/components/VoucherReviewExpanded.tsx` | Read-only expanded detail view |
| `frontend/src/components/VoucherEditForm.tsx` | Full edit form (mobile full-page / desktop modal) |
| `frontend/src/components/LineItemEditor.tsx` | Editable line items (stacked cards on mobile, table on desktop) |
| `frontend/src/components/VoucherRefSelect.tsx` | "Against Invoice" dropdown for DN/CN |
| `frontend/src/__tests__/VoucherReviewCard.test.tsx` | Tests for redesigned 3-state review card |
| `frontend/src/__tests__/VoucherEditForm.test.tsx` | Tests for edit form |
| `frontend/src/__tests__/ConnectCompanyModal.test.tsx` | Tests for company lookup modal |
| `frontend/src/__tests__/fixtures/voucherMockData.ts` | TypeScript mock data for all voucher type × state combos |

### Modified Files
| File | What Changes |
|------|-------------|
| `backend/services/document_parser.py` | Add `party_name`, `original_currency`, `original_amount`, `fx_rate`, `inr_amount`, `original_invoice_ref` to ExtractedDocument. Update Vision prompt for 5-type + multi-currency. Update `parse_vision_response()` and `validate_extracted_amounts()`. |
| `backend/services/voucher_builder.py` | Add `party_ledger`, `is_party_ledger`, `bill_reference`, `bill_type` to VoucherData. Add `build_purchase_voucher_data()`, `build_sales_voucher_data()`, `build_debit_note_data()`, `build_credit_note_data()`. |
| `backend/tally_bridge/import_builder.py` | Add `build_create_purchase_voucher()`, `build_create_sales_voucher()`, `build_create_debit_note()`, `build_create_credit_note()`. |
| `backend/tally_bridge/writer.py` | Add `create_purchase_voucher()`, `create_sales_voucher()`, `create_debit_note()`, `create_credit_note()` methods. Import new builder functions. |
| `backend/tally_bridge/mock_handler.py` | Add company list query response, party voucher lookup response to `mock_tally_request()`. |
| `backend/tally_bridge/queries/masters.py` | Add `get_company_list(host, port)` for arbitrary Tally host:port. |
| `backend/tally_bridge/queries/vouchers.py` | Add `get_party_vouchers(party_name, voucher_types, company)`. |
| `backend/agents/orchestrator.py` | Route by `doc_type` (5 types), fetch party vouchers for DN/CN, build correct VoucherData, persist UploadedFile row. |
| `backend/api/chat.py` | Dispatch voucher-action to correct writer method by `voucher_type`. Persist VoucherEntry row on write/cancel/delete. |
| `backend/api/models.py` | Add `party_ledger`, `original_currency`, `fx_rate`, `inr_amount`, `bill_reference`, `party_vouchers` to VoucherReviewEntry/Data. |
| `backend/api/__init__.py` | Register new tally router. |
| `frontend/src/components/VoucherReviewCard.tsx` | Rewrite: collapsed card with type badge, progressive disclosure, delegates to VoucherReviewExpanded and VoucherEditForm. |
| `frontend/src/components/ConnectCompanyModal.tsx` | Replace free-text name with Tally company dropdown. Add test-connection flow. |
| `frontend/src/api/client.ts` | Add `testTallyConnection(host, port)` function. |

---

### Task 0: Live Tally Exploration — Verify Purchase/Sales/DN/CN XML Formats

**Files:**
- Create: `scripts/explore_tally_invoice_formats.py`
- Modify: `docs/tally-write-exploration.md` (update "Pending Exploration" section + "Verified Operations Summary" table)

**Purpose:** The plan's XML builders (Task 3) assume specific XML tag names, attribute values, and structures based on official Tally docs — but several of these have **never been tested against live TallyPrime 7.0+**. This task runs a controlled exploration against your live Tally (localhost:9000) to verify or correct these assumptions BEFORE writing production code.

**Company:** NUVANTA AI TECHNOLOGIES PRIVATE LIMITED (localhost:9000)

**What to test (6 experiments):**

Each experiment creates a test voucher/entity, inspects the Tally response, and cleans up. All test entities use `_GroupB_Test_` prefix in names and Rs 1.00 amounts for safety.

| # | Experiment | What we're verifying | Success = | Current assumption |
|---|-----------|---------------------|-----------|-------------------|
| E1 | Purchase voucher with `LEDGERENTRIES.LIST` | Does `LEDGERENTRIES.LIST` work for Purchase (vs `ALLLEDGERENTRIES.LIST`)? | CREATED=1, ERRORS=0 | Plan uses `LEDGERENTRIES.LIST` |
| E2 | Purchase voucher with `ALLLEDGERENTRIES.LIST` | Fallback: does the B1a-verified format still work? | CREATED=1, ERRORS=0 | Known to work |
| E3 | Purchase voucher with `PERSISTEDVIEW=Invoice Voucher View` | Does this PERSISTEDVIEW value work? | CREATED=1, ERRORS=0 | Plan uses `Invoice Voucher View` |
| E4 | Purchase voucher with `ISPARTYLEDGER=Yes` + `BILLALLOCATIONS.LIST` | Do these tags work together? | CREATED=1, ERRORS=0 | Plan uses both |
| E5 | Debit Note (`VCHTYPE="Debit Note"`) | Does DN creation work at all? With `Agst Ref` bill type? | CREATED=1, ERRORS=0 | Never tested |
| E6 | Credit Note (`VCHTYPE="Credit Note"`) | Does CN creation work at all? With `Agst Ref` bill type? | CREATED=1, ERRORS=0 | Never tested |

E7 and E8 added 2026-05-07 to cover read-side query primitives the write-agent UI depends on (gap analysis).

**E7 — `get_company_list()` envelope**

- **Goal:** Verify Tally exposes a way to list all loaded companies via XML export, so the write-agent's ConnectCompanyModal (Group B feature F1) can populate a dropdown of available companies on a given Tally host:port without requiring the user to type the company name.
- **Status before probe:** No documented envelope in `docs/tally-write-exploration-v4.md`. Tally's export API is object-oriented (TYPE=Object/Collection/Data with explicit ID), and "list of companies" may not be a first-class endpoint. Possible candidates to test: `TYPE=Collection ID="List of Companies"`, `TYPE=Function NAME="$$CmpName"`, scraping from `TYPE=Data REPORT="..."`, or a bare `<ENVELOPE>` with no `SVCURRENTCOMPANY` returning an introspection response.
- **Probe approach:** Try 3-4 candidate envelopes against live Tally. For each: log full response. Look for any response that returns a structured list of company names. Note: Tally is currently running on localhost:9000 with three companies present (`Bharat Traders Private Limited`, `Bharat Traders V0`, `Bharat Traders V1` per recent verifier output) — clear ground truth.
- **Pass criteria:** At least one envelope returns all three company names parseable from XML.
- **Fallback if no envelope works:** ConnectCompanyModal accepts a freeform text input instead of dropdown. Document this as a UX degradation in the design and flag in `docs/open-items-parked.md`.

**E8 — `get_party_vouchers(party, voucher_types)` TDL collection**

- **Goal:** Verify a TDL Collection envelope can return recent Purchase/Sales vouchers filtered by both party ledger name AND voucher type, for the DN/CN "against invoice" dropdown (Group B features F2/F3).
- **Status before probe:** TDL collections with `CHILDOF=$$VchTypeAllVouchers` are known-working (used by `scripts/delete_seeded_vouchers.py`). Filter-by-party-name within voucher type is the unproven dimension. Tally TDL supports `FILTER` clauses but the exact syntax for cross-referencing the party ledger inside a voucher is non-trivial.
- **Probe approach:** Build a TDL Collection with `TYPE=Voucher`, `CHILDOF=$$VchTypeSales` (or Purchase), and a FILTER comparing `$PartyLedgerName` to a passed parameter. Test against `Bharat Traders Private Limited` (which has 16 sales / 8 purchase vouchers spread across multiple parties — good filter test surface). Run twice: once with `Apex Technologies Pvt Ltd` (should return 3 sales), once with `Samsung India Electronics` (should return 2 purchases).
- **Pass criteria:** Filtered collection returns ONLY vouchers for the requested party + type combination, with VOUCHERNUMBER, DATE, REFERENCE, and total amount accessible.
- **Fallback if filter syntax doesn't work:** Fetch all vouchers of the type and filter client-side in Python. Document acceptable for low voucher counts (< few hundred); flag in parked items if filter is needed for scale.

**Pre-requisites for running:**
- Tally running on localhost:9000 with NUVANTA company loaded
- Tally license activated (see `docs/tally-write-exploration.md` license section)
- Existing ledgers: `Cash` (or any Cash-in-Hand ledger), any expense ledger under `Indirect Expenses`, any party ledger under `Sundry Creditors`

- [ ] **Step 1: Write the exploration script**

Create `scripts/explore_tally_invoice_formats.py`. Follow the pattern from `scripts/explore_tally_write_v2.py`:

```python
"""Tally Invoice Format Exploration — verify Purchase/Sales/DN/CN XML before Group B.

Tests 6 specific XML format questions against live Tally.
All test entities use _GroupB_Test_ prefix and Rs 1.00 amounts.
Cleans up after each test (delete created vouchers).

Usage:
    PYTHONPATH=. python scripts/explore_tally_invoice_formats.py --host localhost --port 9000

Output: prints results table + updates docs/tally-write-exploration.md
"""
import argparse
import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.import_builder import (
    _esc,
    _wrap_import,
    build_delete_voucher,
)
from backend.tally_bridge.response_parser import parse_import_response, sanitize_xml

COMPANY = "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED"
# Use existing ledgers from NUVANTA company — check with list_ledgers first
# Fallbacks: Cash, Bank Charges (Indirect Expenses), any Sundry Creditor
TEST_DATE = datetime.now().strftime("%Y%m%d")
RESULTS: list[dict] = []


def parse_response(xml_text: str) -> dict:
    try:
        root = ET.fromstring(sanitize_xml(xml_text))
    except ET.ParseError:
        return {"raw": xml_text, "parse_error": True}
    result = {}
    for tag in ["CREATED", "ALTERED", "DELETED", "ERRORS", "LASTVCHID", "LASTMID",
                "COMBINED", "IGNORED", "LINEERROR", "CANCELLED", "EXCEPTIONS"]:
        el = root.find(tag) if root.find(tag) is not None else root.find(f".//{tag}")
        if el is not None and el.text:
            result[tag] = el.text.strip()
    return result


async def post_and_report(client: TallyClient, xml: str, label: str) -> dict:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    # Print the XML being sent (truncated for readability)
    xml_preview = xml[:500].replace("\n", " ")
    print(f"  Sending: {xml_preview}...")
    try:
        resp = await client.post_xml(xml)
        result = parse_response(resp)
        print(f"  Result: {json.dumps(result, indent=4)}")
        success = result.get("CREATED") == "1" or result.get("ALTERED") == "1"
        print(f"  {'✅ SUCCESS' if success else '❌ FAILED'}")
        return result
    except Exception as e:
        print(f"  ❌ ERROR: {type(e).__name__}: {e}")
        return {"error": str(e)}


async def cleanup_voucher(client: TallyClient, vch_type: str, master_id: str, label: str):
    """Delete a test voucher by master_id."""
    if not master_id or master_id == "0":
        print(f"  [skip cleanup — no master_id for {label}]")
        return
    xml = build_delete_voucher(vch_type, master_id, TEST_DATE, COMPANY)
    result = await post_and_report(client, xml, f"CLEANUP: Delete {label}")
    if result.get("DELETED") != "1":
        print(f"  ⚠️ WARNING: cleanup failed for {label} (master_id={master_id})")


def record(experiment: str, description: str, result: dict, success: bool):
    RESULTS.append({
        "experiment": experiment,
        "description": description,
        "success": success,
        "created": result.get("CREATED", "0"),
        "errors": result.get("ERRORS", "0"),
        "exceptions": result.get("EXCEPTIONS", "0"),
        "lineerror": result.get("LINEERROR", ""),
        "last_vch_id": result.get("LASTVCHID", ""),
    })


async def run(host: str, port: int):
    client = TallyClient(host=host, port=port)
    print(f"Group B Tally Exploration — {datetime.now().isoformat()}")
    print(f"Target: {host}:{port} / {COMPANY}")
    print(f"Test date: {TEST_DATE}")

    # First, verify connectivity + find usable ledgers
    from backend.tally_bridge.request_builder import build_list_ledgers
    from backend.tally_bridge.response_parser import parse_ledger_list
    ledger_xml = await client.post_xml(build_list_ledgers())
    ledgers = parse_ledger_list(ledger_xml)
    ledger_names = {l["name"] for l in ledgers}
    print(f"Found {len(ledgers)} ledgers")

    # Find test ledgers
    cash_ledger = "Cash" if "Cash" in ledger_names else next(
        (l["name"] for l in ledgers if l.get("parent_group", "").lower() == "cash-in-hand"), "Cash"
    )
    expense_ledger = "Bank Charges" if "Bank Charges" in ledger_names else next(
        (l["name"] for l in ledgers if l.get("parent_group", "").lower() == "indirect expenses"), "Misc Expenses"
    )
    # Find a Sundry Creditor for party ledger tests
    creditor_ledger = next(
        (l["name"] for l in ledgers if l.get("parent_group", "").lower() == "sundry creditors"), None
    )
    if not creditor_ledger:
        print("⚠️ No Sundry Creditor ledger found — will create _GroupB_Test_Supplier")
        # Create a test creditor
        from backend.tally_bridge.import_builder import build_create_ledger
        xml = build_create_ledger("_GroupB_Test_Supplier", "Sundry Creditors", COMPANY)
        await post_and_report(client, xml, "CREATE test supplier ledger")
        creditor_ledger = "_GroupB_Test_Supplier"

    # Find a Sundry Debtor for sales tests
    debtor_ledger = next(
        (l["name"] for l in ledgers if l.get("parent_group", "").lower() == "sundry debtors"), None
    )
    if not debtor_ledger:
        from backend.tally_bridge.import_builder import build_create_ledger
        xml = build_create_ledger("_GroupB_Test_Customer", "Sundry Debtors", COMPANY)
        await post_and_report(client, xml, "CREATE test customer ledger")
        debtor_ledger = "_GroupB_Test_Customer"

    print(f"\nUsing ledgers: Cash={cash_ledger}, Expense={expense_ledger}")
    print(f"  Creditor={creditor_ledger}, Debtor={debtor_ledger}")

    # ─── E1: Purchase with LEDGERENTRIES.LIST ───
    xml_e1 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Purchase" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E1: LEDGERENTRIES.LIST</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(creditor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>1.00</AMOUNT>
</LEDGERENTRIES.LIST>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</LEDGERENTRIES.LIST>
</VOUCHER>""")
    r1 = await post_and_report(client, xml_e1, "E1: Purchase with LEDGERENTRIES.LIST")
    record("E1", "Purchase with LEDGERENTRIES.LIST + Invoice Voucher View + ISPARTYLEDGER", r1, r1.get("CREATED") == "1")
    await cleanup_voucher(client, "Purchase", r1.get("LASTVCHID", ""), "E1 Purchase")

    # ─── E2: Purchase with ALLLEDGERENTRIES.LIST (fallback — known to work) ───
    xml_e2 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Purchase" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E2: ALLLEDGERENTRIES.LIST</NARRATION>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(creditor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>""")
    r2 = await post_and_report(client, xml_e2, "E2: Purchase with ALLLEDGERENTRIES.LIST (control)")
    record("E2", "Purchase with ALLLEDGERENTRIES.LIST + Accounting Voucher View (control)", r2, r2.get("CREATED") == "1")
    await cleanup_voucher(client, "Purchase", r2.get("LASTVCHID", ""), "E2 Purchase")

    # ─── E3: Purchase with Invoice Voucher View but ALLLEDGERENTRIES ───
    # Isolates the PERSISTEDVIEW question from the entry tag question
    xml_e3 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Purchase" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E3: ALLLEDGER + Invoice View</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(creditor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>""")
    r3 = await post_and_report(client, xml_e3, "E3: ALLLEDGERENTRIES + Invoice Voucher View")
    record("E3", "ALLLEDGERENTRIES.LIST + Invoice Voucher View (isolate PERSISTEDVIEW)", r3, r3.get("CREATED") == "1")
    await cleanup_voucher(client, "Purchase", r3.get("LASTVCHID", ""), "E3 Purchase")

    # ─── E4: Purchase with BILLALLOCATIONS.LIST ───
    xml_e4 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Purchase" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E4: BILLALLOCATIONS</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(creditor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>1.00</AMOUNT>
<BILLALLOCATIONS.LIST>
<NAME>TEST-INV-001</NAME>
<BILLTYPE>New Ref</BILLTYPE>
<AMOUNT>1.00</AMOUNT>
</BILLALLOCATIONS.LIST>
</LEDGERENTRIES.LIST>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</LEDGERENTRIES.LIST>
</VOUCHER>""")
    r4 = await post_and_report(client, xml_e4, "E4: Purchase with BILLALLOCATIONS.LIST")
    record("E4", "Purchase with ISPARTYLEDGER + BILLALLOCATIONS.LIST (New Ref)", r4, r4.get("CREATED") == "1")
    await cleanup_voucher(client, "Purchase", r4.get("LASTVCHID", ""), "E4 Purchase")

    # ─── E5: Debit Note ───
    xml_e5 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Debit Note" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Debit Note</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E5: Debit Note</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(creditor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>1.00</AMOUNT>
<BILLALLOCATIONS.LIST>
<NAME>TEST-INV-001</NAME>
<BILLTYPE>Agst Ref</BILLTYPE>
<AMOUNT>1.00</AMOUNT>
</BILLALLOCATIONS.LIST>
</LEDGERENTRIES.LIST>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</LEDGERENTRIES.LIST>
</VOUCHER>""")
    r5 = await post_and_report(client, xml_e5, "E5: Debit Note creation")
    record("E5", "Debit Note with LEDGERENTRIES.LIST + Agst Ref BILLALLOCATIONS", r5, r5.get("CREATED") == "1")
    await cleanup_voucher(client, "Debit Note", r5.get("LASTVCHID", ""), "E5 Debit Note")

    # ─── E6: Credit Note ───
    xml_e6 = _wrap_import("Vouchers", COMPANY, f"""<VOUCHER VCHTYPE="Credit Note" ACTION="Create">
<DATE>{TEST_DATE}</DATE>
<VOUCHERTYPENAME>Credit Note</VOUCHERTYPENAME>
<NARRATION>_GroupB_Test E6: Credit Note</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(debtor_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>-1.00</AMOUNT>
<BILLALLOCATIONS.LIST>
<NAME>TEST-SALE-001</NAME>
<BILLTYPE>Agst Ref</BILLTYPE>
<AMOUNT>-1.00</AMOUNT>
</BILLALLOCATIONS.LIST>
</LEDGERENTRIES.LIST>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(expense_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>1.00</AMOUNT>
</LEDGERENTRIES.LIST>
</VOUCHER>""")
    r6 = await post_and_report(client, xml_e6, "E6: Credit Note creation")
    record("E6", "Credit Note with LEDGERENTRIES.LIST + Agst Ref BILLALLOCATIONS", r6, r6.get("CREATED") == "1")
    await cleanup_voucher(client, "Credit Note", r6.get("LASTVCHID", ""), "E6 Credit Note")

    # ─── Cleanup test ledgers if we created them ───
    if "_GroupB_Test_Supplier" in creditor_ledger:
        from backend.tally_bridge.import_builder import build_delete_ledger
        xml = build_delete_ledger("_GroupB_Test_Supplier", COMPANY)
        await post_and_report(client, xml, "CLEANUP: Delete _GroupB_Test_Supplier")
    if "_GroupB_Test_Customer" in debtor_ledger:
        from backend.tally_bridge.import_builder import build_delete_ledger
        xml = build_delete_ledger("_GroupB_Test_Customer", COMPANY)
        await post_and_report(client, xml, "CLEANUP: Delete _GroupB_Test_Customer")

    # ─── Summary ───
    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Exp':<5} {'Success':<8} {'Crt':<4} {'Err':<4} {'Exc':<4} {'Description'}")
    print("-" * 80)
    for r in RESULTS:
        status = "✅" if r["success"] else "❌"
        print(f"{r['experiment']:<5} {status:<8} {r['created']:<4} {r['errors']:<4} {r['exceptions']:<4} {r['description']}")

    # Check for failures
    failures = [r for r in RESULTS if not r["success"]]
    if failures:
        print(f"\n⚠️ {len(failures)} EXPERIMENT(S) FAILED — review results above.")
        print("Plan adjustments needed in Task 3 (Import Builders):")
        for f in failures:
            print(f"  - {f['experiment']}: {f['description']}")
            if f.get("lineerror"):
                print(f"    LINEERROR: {f['lineerror']}")
    else:
        print(f"\n✅ ALL {len(RESULTS)} EXPERIMENTS PASSED — plan assumptions confirmed.")

    print("\nNext steps:")
    print("1. Update docs/tally-write-exploration.md 'Pending Exploration' → 'Verified' with results")
    print("2. Update 'Verified Operations Summary' table with new entries")
    print("3. If any experiment failed, adjust Task 3 XML builders before implementing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tally Invoice Format Exploration for Group B")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    asyncio.run(run(args.host, args.port))
```

- [ ] **Step 2: Verify Tally is running**

```bash
curl -s http://localhost:9000 | head -5
```

Expected: Tally HTTP response (any HTML/XML). If connection refused, start Tally first.

- [ ] **Step 3: Run the exploration script**

```bash
PYTHONPATH=. python scripts/explore_tally_invoice_formats.py --host localhost --port 9000 2>&1 | tee docs/group-b-exploration-results.log
```

**⚠️ Save the full output.** If any experiment fails, stop and investigate before proceeding.

Expected output: 6 experiments, each showing CREATED=1 + successful cleanup.

- [ ] **Step 4: Update `docs/tally-write-exploration.md`**

Based on results, update three sections:

**a) Replace "Pending Exploration" section** with verified results. For each of the 6 items, record:
- The exact XML that was tested
- The Tally response (CREATED/ERRORS/EXCEPTIONS)
- Whether it passed or failed
- If failed: what XML format DID work (from fallback experiments)

**b) Update "Verified Operations Summary" table** — add rows:

```markdown
| Create Purchase (LEDGERENTRIES.LIST) | [result] | [key requirement] |
| Create Purchase (Invoice Voucher View) | [result] | [key requirement] |
| Create Purchase (BILLALLOCATIONS.LIST) | [result] | [key requirement] |
| Create Debit Note | [result] | [key requirement] |
| Create Credit Note | [result] | [key requirement] |
```

**c) Update "Sales/Purchase: Key Differences from Payment" section** with corrected information if any assumptions were wrong.

- [ ] **Step 5: If any experiment failed — adjust the plan**

If E1 fails (LEDGERENTRIES.LIST doesn't work): Task 3 must use `ALLLEDGERENTRIES.LIST` instead. Update the `_build_invoice_voucher` function and all tests.

If E3 fails (Invoice Voucher View doesn't work): Task 3 must use `Accounting Voucher View`. Update the constant.

If E5/E6 fail (DN/CN don't work): Investigate the error, try alternative XML formats, and adjust. Document findings.

- [ ] **Step 6: Commit exploration script + updated docs**

```bash
git add scripts/explore_tally_invoice_formats.py docs/tally-write-exploration.md docs/group-b-exploration-results.log
git commit -m "feat: live Tally exploration for Group B — verify Purchase/Sales/DN/CN XML"
```

---

### Task 1: Vision JSON Fixtures

**Files:**
- Create: `tests/fixtures/vision/payment_petty_cash_inr.json`
- Create: `tests/fixtures/vision/payment_with_gst_inr.json`
- Create: `tests/fixtures/vision/purchase_saas_usd.json`
- Create: `tests/fixtures/vision/purchase_saas_usd_no_rate.json`
- Create: `tests/fixtures/vision/purchase_office_inr.json`
- Create: `tests/fixtures/vision/purchase_interstate_inr.json`
- Create: `tests/fixtures/vision/sales_service_inr.json`
- Create: `tests/fixtures/vision/sales_service_eur.json`
- Create: `tests/fixtures/vision/debit_note_return_inr.json`
- Create: `tests/fixtures/vision/credit_note_return_inr.json`
- Create: `tests/fixtures/vision/debit_note_no_ref.json`

These fixtures are the JSON that Claude Vision would return. Every subsequent task depends on these.

- [ ] **Step 1: Create fixture directory**

```bash
mkdir -p tests/fixtures/vision tests/fixtures/uploads
```

- [ ] **Step 2: Write payment_petty_cash_inr.json**

```json
{
  "doc_type": "payment",
  "party_name": "Uber",
  "date": "2026-03-15",
  "total_amount": 350.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Uber ride - client meeting", "amount": 350.00, "quantity": null, "rate": null}
  ],
  "gst": null,
  "payment_mode": "upi",
  "original_invoice_ref": null
}
```

- [ ] **Step 3: Write payment_with_gst_inr.json**

```json
{
  "doc_type": "payment",
  "party_name": "Cafe Coffee Day",
  "date": "2026-03-20",
  "total_amount": 590.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Team lunch", "amount": 500.00, "quantity": null, "rate": null}
  ],
  "gst": {
    "cgst_rate": 9.0, "cgst_amount": 45.00,
    "sgst_rate": 9.0, "sgst_amount": 45.00,
    "igst_rate": null, "igst_amount": null,
    "gstin": null
  },
  "payment_mode": "card",
  "original_invoice_ref": null
}
```

- [ ] **Step 4: Write purchase_saas_usd.json**

```json
{
  "doc_type": "purchase",
  "party_name": "Anthropic PBC",
  "date": "2026-03-15",
  "total_amount": 1730.00,
  "original_currency": "USD",
  "fx_rate": 83.46,
  "line_items": [
    {"description": "Claude API Usage - March 2026", "amount": 1730.00, "quantity": null, "rate": null}
  ],
  "gst": {
    "cgst_rate": null, "cgst_amount": null,
    "sgst_rate": null, "sgst_amount": null,
    "igst_rate": 18.0, "igst_amount": 311.40,
    "gstin": null
  },
  "payment_mode": "bank",
  "original_invoice_ref": "INV-2026-0315"
}
```

- [ ] **Step 5: Write purchase_saas_usd_no_rate.json** (same as above but `fx_rate: null`)

```json
{
  "doc_type": "purchase",
  "party_name": "Anthropic PBC",
  "date": "2026-03-15",
  "total_amount": 1730.00,
  "original_currency": "USD",
  "fx_rate": null,
  "line_items": [
    {"description": "Claude API Usage - March 2026", "amount": 1730.00, "quantity": null, "rate": null}
  ],
  "gst": null,
  "payment_mode": "bank",
  "original_invoice_ref": null
}
```

- [ ] **Step 6: Write purchase_office_inr.json** (multi-line, intra-state)

```json
{
  "doc_type": "purchase",
  "party_name": "Croma Electronics",
  "date": "2026-02-10",
  "total_amount": 15340.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Logitech MX Keys keyboard", "amount": 8999.00, "quantity": 1, "rate": 8999.00},
    {"description": "USB-C Hub", "amount": 3999.00, "quantity": 1, "rate": 3999.00}
  ],
  "gst": {
    "cgst_rate": 9.0, "cgst_amount": 1171.00,
    "sgst_rate": 9.0, "sgst_amount": 1171.00,
    "igst_rate": null, "igst_amount": null,
    "gstin": "27AABCC1234D1Z5"
  },
  "payment_mode": "bank",
  "original_invoice_ref": "CRO-2026-5678"
}
```

- [ ] **Step 7: Write purchase_interstate_inr.json**

```json
{
  "doc_type": "purchase",
  "party_name": "AWS India",
  "date": "2026-03-31",
  "total_amount": 23600.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "AWS Cloud Services - March", "amount": 20000.00, "quantity": null, "rate": null}
  ],
  "gst": {
    "cgst_rate": null, "cgst_amount": null,
    "sgst_rate": null, "sgst_amount": null,
    "igst_rate": 18.0, "igst_amount": 3600.00,
    "gstin": "29AABCA1234E1ZP"
  },
  "payment_mode": "bank",
  "original_invoice_ref": null
}
```

- [ ] **Step 8: Write sales_service_inr.json**

```json
{
  "doc_type": "sales",
  "party_name": "Infosys Ltd",
  "date": "2026-03-01",
  "total_amount": 118000.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "AI Consulting Services - February", "amount": 100000.00, "quantity": null, "rate": null}
  ],
  "gst": {
    "cgst_rate": 9.0, "cgst_amount": 9000.00,
    "sgst_rate": 9.0, "sgst_amount": 9000.00,
    "igst_rate": null, "igst_amount": null,
    "gstin": "27AABCI1234F1G5"
  },
  "payment_mode": null,
  "original_invoice_ref": null
}
```

- [ ] **Step 9: Write sales_service_eur.json** (export, no GST)

```json
{
  "doc_type": "sales",
  "party_name": "Acme GmbH",
  "date": "2026-03-10",
  "total_amount": 5000.00,
  "original_currency": "EUR",
  "fx_rate": 90.25,
  "line_items": [
    {"description": "Software Development Services", "amount": 5000.00, "quantity": null, "rate": null}
  ],
  "gst": null,
  "payment_mode": null,
  "original_invoice_ref": null
}
```

- [ ] **Step 10: Write debit_note_return_inr.json**

```json
{
  "doc_type": "debit_note",
  "party_name": "Croma Electronics",
  "date": "2026-03-05",
  "total_amount": 4718.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Return: USB-C Hub (defective)", "amount": 3999.00, "quantity": 1, "rate": 3999.00}
  ],
  "gst": {
    "cgst_rate": 9.0, "cgst_amount": 359.91,
    "sgst_rate": 9.0, "sgst_amount": 359.91,
    "igst_rate": null, "igst_amount": null,
    "gstin": "27AABCC1234D1Z5"
  },
  "payment_mode": null,
  "original_invoice_ref": "CRO-2026-5678"
}
```

- [ ] **Step 11: Write credit_note_return_inr.json**

```json
{
  "doc_type": "credit_note",
  "party_name": "Infosys Ltd",
  "date": "2026-03-15",
  "total_amount": 11800.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Discount on Feb services", "amount": 10000.00, "quantity": null, "rate": null}
  ],
  "gst": {
    "cgst_rate": 9.0, "cgst_amount": 900.00,
    "sgst_rate": 9.0, "sgst_amount": 900.00,
    "igst_rate": null, "igst_amount": null,
    "gstin": "27AABCI1234F1G5"
  },
  "payment_mode": null,
  "original_invoice_ref": "INV-2026-FEB-001"
}
```

- [ ] **Step 12: Write debit_note_no_ref.json**

```json
{
  "doc_type": "debit_note",
  "party_name": "Unknown Supplier",
  "date": "2026-03-20",
  "total_amount": 1000.00,
  "original_currency": "INR",
  "fx_rate": null,
  "line_items": [
    {"description": "Damaged goods return", "amount": 1000.00, "quantity": null, "rate": null}
  ],
  "gst": null,
  "payment_mode": null,
  "original_invoice_ref": null
}
```

- [ ] **Step 13: Create minimal sample upload files**

```bash
# 1x1 red pixel JPEG
python3 -c "
from PIL import Image
img = Image.new('RGB', (1, 1), (255, 0, 0))
img.save('tests/fixtures/uploads/sample_receipt.jpg')
img.save('tests/fixtures/uploads/sample_receipt.png')
"

# Minimal PDF (text)
python3 -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/uploads/sample_invoice.pdf')
c.drawString(100, 750, 'Sample Invoice')
c.save()
"

# If those libraries not available, create minimal binary files:
# JPEG: ff d8 ff e0 header
python3 -c "
import struct
# Minimal JPEG
data = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xD9])
with open('tests/fixtures/uploads/sample_receipt.jpg', 'wb') as f: f.write(data)
# Minimal PNG
import zlib
def minimal_png():
    sig = b'\x89PNG\r\n\x1a\n'
    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    # IDAT
    raw = zlib.compress(b'\x00\xff\x00\x00')
    idat_crc = zlib.crc32(b'IDAT' + raw) & 0xffffffff
    idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
    # IEND
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    return sig + ihdr + idat + iend
with open('tests/fixtures/uploads/sample_receipt.png', 'wb') as f: f.write(minimal_png())
# Minimal PDF
pdf = b'%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF'
with open('tests/fixtures/uploads/sample_invoice.pdf', 'wb') as f: f.write(pdf)
# Unsupported file
with open('tests/fixtures/uploads/unsupported.docx', 'wb') as f: f.write(b'PK\x03\x04fake docx')
"
```

- [ ] **Step 14: Commit**

```bash
git add tests/fixtures/vision/ tests/fixtures/uploads/
git commit -m "feat: add vision JSON + upload file fixtures for Group B"
```

---

### Task 2: Document Parser — Multi-Currency + 5-Type Classification

**Files:**
- Modify: `backend/services/document_parser.py`
- Create: `tests/unit/test_document_parser_multi.py`

- [ ] **Step 1: Write failing tests for new ExtractedDocument fields**

Create `tests/unit/test_document_parser_multi.py`:

```python
"""Tests for multi-currency + 5-type classification in document parser."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.services.document_parser import (
    ExtractedDocument,
    build_vision_prompt,
    parse_vision_response,
    validate_extracted_amounts,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "vision"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParseMultiType:
    """parse_vision_response handles all 5 doc types + multi-currency."""

    def test_payment_inr(self):
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        assert doc.doc_type == "payment"
        assert doc.party_name == "Uber"
        assert doc.original_currency == "INR"
        assert doc.fx_rate is None
        assert doc.inr_amount == doc.total_amount

    def test_purchase_usd_with_rate(self):
        doc = parse_vision_response(_load("purchase_saas_usd.json"))
        assert doc.doc_type == "purchase"
        assert doc.party_name == "Anthropic PBC"
        assert doc.original_currency == "USD"
        assert doc.fx_rate == Decimal("83.46")
        expected_inr = Decimal("1730.00") * Decimal("83.46")
        assert abs(doc.inr_amount - expected_inr) < Decimal("1.00")

    def test_purchase_usd_no_rate(self):
        doc = parse_vision_response(_load("purchase_saas_usd_no_rate.json"))
        assert doc.doc_type == "purchase"
        assert doc.original_currency == "USD"
        assert doc.fx_rate is None
        # inr_amount should equal total_amount when no rate (no conversion possible)
        assert doc.inr_amount == doc.total_amount

    def test_purchase_inr_multiline(self):
        doc = parse_vision_response(_load("purchase_office_inr.json"))
        assert doc.doc_type == "purchase"
        assert len(doc.line_items) == 2
        assert doc.original_currency == "INR"

    def test_purchase_interstate_igst(self):
        doc = parse_vision_response(_load("purchase_interstate_inr.json"))
        assert doc.gst is not None
        assert doc.gst.igst_amount == Decimal("3600.00")
        assert doc.gst.cgst_amount is None

    def test_sales_inr(self):
        doc = parse_vision_response(_load("sales_service_inr.json"))
        assert doc.doc_type == "sales"
        assert doc.party_name == "Infosys Ltd"

    def test_sales_eur_export(self):
        doc = parse_vision_response(_load("sales_service_eur.json"))
        assert doc.doc_type == "sales"
        assert doc.original_currency == "EUR"
        assert doc.fx_rate == Decimal("90.25")
        assert doc.gst is None

    def test_debit_note_with_ref(self):
        doc = parse_vision_response(_load("debit_note_return_inr.json"))
        assert doc.doc_type == "debit_note"
        assert doc.original_invoice_ref == "CRO-2026-5678"

    def test_credit_note_with_ref(self):
        doc = parse_vision_response(_load("credit_note_return_inr.json"))
        assert doc.doc_type == "credit_note"
        assert doc.original_invoice_ref == "INV-2026-FEB-001"

    def test_debit_note_no_ref(self):
        doc = parse_vision_response(_load("debit_note_no_ref.json"))
        assert doc.doc_type == "debit_note"
        assert doc.original_invoice_ref is None

    def test_party_name_backward_compat(self):
        """vendor_name still works as alias for party_name."""
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        assert doc.vendor_name == doc.party_name


class TestVisionPromptMultiType:
    """Updated Vision prompt includes multi-currency + 5-type classification."""

    def test_prompt_includes_all_doc_types(self):
        prompt = build_vision_prompt()
        for t in ["payment", "purchase", "sales", "debit_note", "credit_note"]:
            assert t in prompt

    def test_prompt_includes_currency_fields(self):
        prompt = build_vision_prompt()
        assert "original_currency" in prompt
        assert "fx_rate" in prompt

    def test_prompt_includes_invoice_ref(self):
        prompt = build_vision_prompt()
        assert "original_invoice_ref" in prompt


class TestValidateFX:
    """validate_extracted_amounts handles FX scenarios."""

    def test_inr_no_warnings(self):
        doc = parse_vision_response(_load("payment_petty_cash_inr.json"))
        warnings = validate_extracted_amounts(doc)
        assert len(warnings) == 0

    def test_usd_with_rate_no_warnings(self):
        doc = parse_vision_response(_load("purchase_saas_usd.json"))
        warnings = validate_extracted_amounts(doc)
        # GST math may not perfectly reconcile due to the fixture being USD
        # but no FX-specific warning expected since rate is present
        fx_warnings = [w for w in warnings if "estimated" in w.lower() or "fx" in w.lower()]
        assert len(fx_warnings) == 0

    def test_usd_no_rate_warns(self):
        doc = parse_vision_response(_load("purchase_saas_usd_no_rate.json"))
        warnings = validate_extracted_amounts(doc)
        fx_warnings = [w for w in warnings if "rate" in w.lower() or "verify" in w.lower()]
        assert len(fx_warnings) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_document_parser_multi.py -v
```

Expected: FAIL — `party_name`, `original_currency`, `fx_rate`, `inr_amount`, `original_invoice_ref` not on ExtractedDocument.

- [ ] **Step 3: Update ExtractedDocument dataclass**

Modify `backend/services/document_parser.py`. Add new fields to `ExtractedDocument`:

```python
@dataclass
class ExtractedDocument:
    doc_type: str                    # "payment" | "purchase" | "sales" | "debit_note" | "credit_note"
    vendor_name: str | None          # backward compat alias
    date: str
    total_amount: Decimal
    line_items: list[LineItem] = field(default_factory=list)
    gst: GSTBreakdown | None = None
    payment_mode: str | None = None
    raw_text: str | None = None
    confidence: float = 0.0
    currency: str = "INR"            # DEPRECATED: use original_currency
    # --- Group B additions ---
    party_name: str | None = None    # canonical: vendor or customer
    original_currency: str = "INR"   # "INR", "USD", "EUR", etc.
    original_amount: Decimal = Decimal("0")
    fx_rate: Decimal | None = None
    inr_amount: Decimal = Decimal("0")
    original_invoice_ref: str | None = None
```

- [ ] **Step 4: Update build_vision_prompt()**

Replace the prompt in `build_vision_prompt()` with the 5-type, multi-currency version:

```python
def build_vision_prompt() -> str:
    """Build the Claude Vision extraction prompt for all document types."""
    return """Analyze this document (expense receipt, purchase invoice, sales invoice, debit note, or credit note) and extract structured data.

Return ONLY valid JSON with this exact structure:
{
    "doc_type": "payment" | "purchase" | "sales" | "debit_note" | "credit_note",
    "party_name": "vendor or customer name, string or null",
    "date": "YYYY-MM-DD",
    "total_amount": number (in the document's original currency),
    "original_currency": "INR" | "USD" | "EUR" | other ISO 4217 code,
    "fx_rate": number or null (exchange rate if visible on document, or your best estimate for foreign currency),
    "line_items": [
        {
            "description": "string",
            "amount": number (in original currency),
            "quantity": number or null,
            "rate": number or null
        }
    ],
    "gst": {
        "cgst_rate": number or null,
        "cgst_amount": number or null,
        "sgst_rate": number or null,
        "sgst_amount": number or null,
        "igst_rate": number or null,
        "igst_amount": number or null,
        "gstin": "vendor/supplier GSTIN or null"
    } or null,
    "payment_mode": "cash" | "bank" | "upi" | "card" | null,
    "original_invoice_ref": "string or null (original invoice number for debit/credit notes)"
}

Classification rules:
- "payment": Direct expense paid immediately (petty cash, reimbursement, taxi, food)
- "purchase": Vendor invoice for goods or services on credit (supplier invoice, SaaS subscription)
- "sales": Invoice issued to a customer for goods or services
- "debit_note": Return or adjustment against a purchase (reduces amount owed to supplier)
- "credit_note": Return or adjustment against a sale (reduces amount owed by customer)

Currency rules:
- Set original_currency to the currency shown on the document
- All amounts (total_amount, line_items) should be in the original currency
- If the document shows an exchange rate, set fx_rate to that number
- If the document is in a foreign currency but no rate is shown, estimate a reasonable fx_rate
- For INR documents, set original_currency to "INR" and fx_rate to null

If GST is not mentioned or not applicable, set gst to null.
If unsure about a field, set it to null rather than guessing.
Return ONLY the JSON, no markdown formatting or explanation."""
```

- [ ] **Step 5: Update parse_vision_response()**

After the existing field parsing, add:

```python
    # Multi-currency + party_name (Group B)
    party_name = data.get("party_name") or data.get("vendor_name")
    original_currency = data.get("original_currency", "INR")
    fx_rate_raw = data.get("fx_rate")
    fx_rate = _to_decimal(fx_rate_raw) if fx_rate_raw is not None else None
    total = _to_decimal(data.get("total_amount"))

    if fx_rate and original_currency != "INR":
        inr_amount = total * fx_rate
    else:
        inr_amount = total

    return ExtractedDocument(
        doc_type=data.get("doc_type", "expense"),
        vendor_name=party_name,     # backward compat
        party_name=party_name,
        date=data.get("date", ""),
        total_amount=total,
        line_items=line_items,
        gst=gst,
        payment_mode=data.get("payment_mode"),
        confidence=0.85,
        original_currency=original_currency,
        original_amount=total,
        fx_rate=fx_rate,
        inr_amount=inr_amount,
        original_invoice_ref=data.get("original_invoice_ref"),
    )
```

- [ ] **Step 6: Update validate_extracted_amounts()**

Add FX validation after existing checks:

```python
        # FX validation (Group B)
        if doc.original_currency != "INR":
            if doc.fx_rate is None:
                warnings.append(
                    f"Foreign currency ({doc.original_currency}) with no exchange rate — "
                    "please verify INR amount"
                )
            elif doc.fx_rate > 0:
                expected_inr = doc.original_amount * doc.fx_rate
                if abs(expected_inr - doc.inr_amount) > Decimal("1.00"):
                    warnings.append(
                        f"{doc.original_currency} {doc.original_amount} × {doc.fx_rate} = "
                        f"{expected_inr}, but INR amount is {doc.inr_amount} — please verify"
                    )
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/unit/test_document_parser_multi.py -v
```

Expected: ALL PASS

- [ ] **Step 8: Run existing parser tests (regression)**

```bash
pytest tests/unit/test_document_parser.py -v
```

Expected: ALL PASS (backward compat via `vendor_name` alias, default `original_currency="INR"`)

- [ ] **Step 9: Commit**

```bash
git add backend/services/document_parser.py tests/unit/test_document_parser_multi.py
git commit -m "feat: multi-currency + 5-type classification in document parser"
```

---

### Task 3: Import Builder — Purchase/Sales/DN/CN XML

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Create: `tests/unit/test_import_builder_invoice.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_import_builder_invoice.py`:

```python
"""Tests for Purchase/Sales/Debit Note/Credit Note XML builders."""
import xml.etree.ElementTree as ET

import pytest

from backend.tally_bridge.import_builder import (
    build_create_credit_note,
    build_create_debit_note,
    build_create_purchase_voucher,
    build_create_sales_voucher,
)


def _parse(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


def _voucher(xml_str: str) -> ET.Element:
    root = _parse(xml_str)
    return root.find(".//VOUCHER")


class TestCreatePurchaseVoucher:
    def test_basic_structure(self):
        xml = build_create_purchase_voucher(
            date="20260210",
            party_ledger="Croma Electronics",
            purchase_ledger="Office Equipment",
            amount=15340.0,
            narration="Office supplies purchase",
            company="Bharat Traders Pvt Ltd",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Purchase"
        assert v.get("ACTION") == "Create"
        assert v.find("VOUCHERTYPENAME").text == "Purchase"
        assert v.find("DATE").text == "20260210"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"
        assert v.find("ISINVOICE").text == "Yes"

    def test_party_ledger_has_ispartyledger(self):
        xml = build_create_purchase_voucher(
            date="20260210", party_ledger="Croma", purchase_ledger="Purchases",
            amount=1000.0, narration="test", company="Test Co",
        )
        v = _voucher(xml)
        party_entries = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is not None and e.find("ISPARTYLEDGER").text == "Yes"
        ]
        assert len(party_entries) == 1
        assert party_entries[0].find("LEDGERNAME").text == "Croma"

    def test_purchase_with_gst_input(self):
        xml = build_create_purchase_voucher(
            date="20260210", party_ledger="Supplier", purchase_ledger="Purchases",
            amount=11800.0, narration="test", company="Test Co",
            gst_entries=[
                {"ledger": "INPUT CGST", "amount": 900.0},
                {"ledger": "INPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        gst_entries = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if "INPUT" in (e.find("LEDGERNAME").text or "")
        ]
        assert len(gst_entries) == 2
        # GST input: ISDEEMEDPOSITIVE=Yes (debit side)
        for e in gst_entries:
            assert e.find("ISDEEMEDPOSITIVE").text == "Yes"

    def test_purchase_with_bill_ref(self):
        xml = build_create_purchase_voucher(
            date="20260210", party_ledger="Supplier", purchase_ledger="Purchases",
            amount=1000.0, narration="test", company="Test Co",
            bill_ref="INV-001",
        )
        v = _voucher(xml)
        party_entry = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is not None
        ][0]
        bill = party_entry.find("BILLALLOCATIONS.LIST")
        assert bill is not None
        assert bill.find("NAME").text == "INV-001"
        assert bill.find("BILLTYPE").text == "New Ref"

    def test_purchase_entries_balance(self):
        xml = build_create_purchase_voucher(
            date="20260210", party_ledger="Supplier", purchase_ledger="Purchases",
            amount=1000.0, narration="test", company="Test Co",
        )
        v = _voucher(xml)
        amounts = [float(e.find("AMOUNT").text) for e in v.findall("LEDGERENTRIES.LIST")]
        assert abs(sum(amounts)) < 0.01

    def test_required_fields_validation(self):
        with pytest.raises(ValueError, match="date"):
            build_create_purchase_voucher(
                date="", party_ledger="S", purchase_ledger="P",
                amount=100.0, narration="t", company="C",
            )

    def test_xml_escaping(self):
        xml = build_create_purchase_voucher(
            date="20260210", party_ledger="Smith & Sons",
            purchase_ledger="Office <Supplies>",
            amount=100.0, narration='Test "quote"', company="Test Co",
        )
        assert "Smith &amp; Sons" in xml
        assert "Office &lt;Supplies&gt;" in xml


class TestCreateSalesVoucher:
    def test_basic_structure(self):
        xml = build_create_sales_voucher(
            date="20260301", party_ledger="Infosys Ltd",
            sales_ledger="Sales", amount=118000.0,
            narration="Consulting services", company="Test Co",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Sales"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"
        assert v.find("ISINVOICE").text == "Yes"

    def test_sales_polarity_reversed_from_purchase(self):
        """Sales: party (debit) is negative, sales (credit) is positive."""
        xml = build_create_sales_voucher(
            date="20260301", party_ledger="Customer",
            sales_ledger="Sales", amount=1000.0,
            narration="test", company="Test Co",
        )
        v = _voucher(xml)
        party_entry = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is not None
        ][0]
        # Sales party: ISDEEMEDPOSITIVE=Yes, amount negative (debit)
        assert party_entry.find("ISDEEMEDPOSITIVE").text == "Yes"
        assert float(party_entry.find("AMOUNT").text) < 0

    def test_sales_gst_output(self):
        xml = build_create_sales_voucher(
            date="20260301", party_ledger="Customer",
            sales_ledger="Sales", amount=11800.0,
            narration="test", company="Test Co",
            gst_entries=[
                {"ledger": "OUTPUT CGST", "amount": 900.0},
                {"ledger": "OUTPUT SGST", "amount": 900.0},
            ],
        )
        v = _voucher(xml)
        gst_entries = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if "OUTPUT" in (e.find("LEDGERNAME").text or "")
        ]
        # Sales GST output: ISDEEMEDPOSITIVE=No (credit side)
        for e in gst_entries:
            assert e.find("ISDEEMEDPOSITIVE").text == "No"

    def test_sales_entries_balance(self):
        xml = build_create_sales_voucher(
            date="20260301", party_ledger="Customer",
            sales_ledger="Sales", amount=1000.0,
            narration="test", company="Test Co",
        )
        v = _voucher(xml)
        amounts = [float(e.find("AMOUNT").text) for e in v.findall("LEDGERENTRIES.LIST")]
        assert abs(sum(amounts)) < 0.01


class TestCreateDebitNote:
    def test_basic_structure(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=4718.0,
            narration="Return", company="Test Co",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Debit Note"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"

    def test_debit_note_agst_ref(self):
        xml = build_create_debit_note(
            date="20260305", party_ledger="Croma",
            purchase_ledger="Purchases", amount=1000.0,
            narration="Return", company="Test Co",
            bill_ref="CRO-2026-5678",
        )
        v = _voucher(xml)
        party_entry = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is not None
        ][0]
        bill = party_entry.find("BILLALLOCATIONS.LIST")
        assert bill.find("BILLTYPE").text == "Agst Ref"
        assert bill.find("NAME").text == "CRO-2026-5678"


class TestCreateCreditNote:
    def test_basic_structure(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=11800.0,
            narration="Discount", company="Test Co",
        )
        v = _voucher(xml)
        assert v.get("VCHTYPE") == "Credit Note"
        assert v.find("PERSISTEDVIEW").text == "Invoice Voucher View"

    def test_credit_note_agst_ref(self):
        xml = build_create_credit_note(
            date="20260315", party_ledger="Infosys",
            sales_ledger="Sales", amount=1000.0,
            narration="Discount", company="Test Co",
            bill_ref="INV-2026-FEB-001",
        )
        v = _voucher(xml)
        party_entry = [
            e for e in v.findall("LEDGERENTRIES.LIST")
            if e.find("ISPARTYLEDGER") is not None
        ][0]
        bill = party_entry.find("BILLALLOCATIONS.LIST")
        assert bill.find("BILLTYPE").text == "Agst Ref"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_import_builder_invoice.py -v
```

Expected: FAIL — `build_create_purchase_voucher` etc. not defined.

- [ ] **Step 3: Implement the 4 new builder functions**

Add to `backend/tally_bridge/import_builder.py` after `build_create_payment_voucher`:

```python
def _build_invoice_voucher(
    vch_type: str,
    date: str,
    party_ledger: str,
    contra_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
    bill_ref: str | None = None,
    bill_type: str = "New Ref",
    is_purchase_side: bool = True,
) -> str:
    """Build XML for invoice-style vouchers (Purchase/Sales/DN/CN).

    Args:
        is_purchase_side: True for Purchase/DN (party=credit, expense=debit).
                         False for Sales/CN (party=debit, revenue=credit).
    """
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    _require(date, "date")
    _require(party_ledger, "party_ledger")
    _require(contra_ledger, "contra_ledger")
    _require(narration, "narration")
    _require(company, "company")

    gst_total = sum(e["amount"] for e in (gst_entries or []))
    base_amount = amount - gst_total

    entries = []

    # Party ledger entry
    if is_purchase_side:
        # Purchase/DN: party is credit side (positive amount, ISDEEMEDPOSITIVE=No)
        party_amount = f"{amount:.2f}"
        party_deemed = "No"
    else:
        # Sales/CN: party is debit side (negative amount, ISDEEMEDPOSITIVE=Yes)
        party_amount = f"-{amount:.2f}"
        party_deemed = "Yes"

    bill_xml = ""
    if bill_ref:
        bill_xml = f"""
<BILLALLOCATIONS.LIST>
<NAME>{_esc(bill_ref)}</NAME>
<BILLTYPE>{_esc(bill_type)}</BILLTYPE>
<AMOUNT>{party_amount}</AMOUNT>
</BILLALLOCATIONS.LIST>"""

    entries.append(
        f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(party_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{party_deemed}</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>{party_amount}</AMOUNT>{bill_xml}
</LEDGERENTRIES.LIST>"""
    )

    # GST entries
    for gst in gst_entries or []:
        if is_purchase_side:
            # Purchase/DN GST: input credit, debit side (negative, ISDEEMEDPOSITIVE=Yes)
            gst_amount = f"-{gst['amount']:.2f}"
            gst_deemed = "Yes"
        else:
            # Sales/CN GST: output, credit side (positive, ISDEEMEDPOSITIVE=No)
            gst_amount = f"{gst['amount']:.2f}"
            gst_deemed = "No"
        entries.append(
            f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(gst['ledger'])}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{gst_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{gst_amount}</AMOUNT>
</LEDGERENTRIES.LIST>"""
        )

    # Contra ledger (expense/revenue)
    if is_purchase_side:
        # Purchase/DN: expense is debit side (negative, ISDEEMEDPOSITIVE=Yes)
        contra_amount = f"-{base_amount:.2f}"
        contra_deemed = "Yes"
    else:
        # Sales/CN: revenue is credit side (positive, ISDEEMEDPOSITIVE=No)
        contra_amount = f"{base_amount:.2f}"
        contra_deemed = "No"

    entries.append(
        f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(contra_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{contra_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{contra_amount}</AMOUNT>
</LEDGERENTRIES.LIST>"""
    )

    entries_xml = "\n".join(entries)
    voucher_xml = f"""<VOUCHER VCHTYPE="{_esc(vch_type)}" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<VOUCHERTYPENAME>{_esc(vch_type)}</VOUCHERTYPENAME>
<NARRATION>{_esc(narration)}</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
{entries_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_create_purchase_voucher(
    date: str,
    party_ledger: str,
    purchase_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
    bill_ref: str | None = None,
) -> str:
    """Build XML to create a Purchase voucher in Tally."""
    return _build_invoice_voucher(
        vch_type="Purchase", date=date, party_ledger=party_ledger,
        contra_ledger=purchase_ledger, amount=amount, narration=narration,
        company=company, gst_entries=gst_entries, bill_ref=bill_ref,
        bill_type="New Ref", is_purchase_side=True,
    )


def build_create_sales_voucher(
    date: str,
    party_ledger: str,
    sales_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
    bill_ref: str | None = None,
) -> str:
    """Build XML to create a Sales voucher in Tally."""
    return _build_invoice_voucher(
        vch_type="Sales", date=date, party_ledger=party_ledger,
        contra_ledger=sales_ledger, amount=amount, narration=narration,
        company=company, gst_entries=gst_entries, bill_ref=bill_ref,
        bill_type="New Ref", is_purchase_side=False,
    )


def build_create_debit_note(
    date: str,
    party_ledger: str,
    purchase_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
    bill_ref: str | None = None,
) -> str:
    """Build XML to create a Debit Note in Tally."""
    return _build_invoice_voucher(
        vch_type="Debit Note", date=date, party_ledger=party_ledger,
        contra_ledger=purchase_ledger, amount=amount, narration=narration,
        company=company, gst_entries=gst_entries, bill_ref=bill_ref,
        bill_type="Agst Ref", is_purchase_side=True,
    )


def build_create_credit_note(
    date: str,
    party_ledger: str,
    sales_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
    bill_ref: str | None = None,
) -> str:
    """Build XML to create a Credit Note in Tally."""
    return _build_invoice_voucher(
        vch_type="Credit Note", date=date, party_ledger=party_ledger,
        contra_ledger=sales_ledger, amount=amount, narration=narration,
        company=company, gst_entries=gst_entries, bill_ref=bill_ref,
        bill_type="Agst Ref", is_purchase_side=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_import_builder_invoice.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Run existing import builder tests (regression)**

```bash
pytest tests/unit/test_import_builder.py -v
```

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tally_bridge/import_builder.py tests/unit/test_import_builder_invoice.py
git commit -m "feat: add Purchase/Sales/Debit Note/Credit Note XML builders"
```

---

### Task 4: Voucher Builder — 4 New Builder Functions

**Files:**
- Modify: `backend/services/voucher_builder.py`
- Create: `tests/unit/test_voucher_builder_multi.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_voucher_builder_multi.py`:

```python
"""Tests for Purchase/Sales/DN/CN voucher builder functions."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.services.document_parser import parse_vision_response
from backend.services.voucher_builder import (
    VoucherData,
    build_credit_note_data,
    build_debit_note_data,
    build_purchase_voucher_data,
    build_sales_voucher_data,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "vision"


def _load_doc(name: str):
    return parse_vision_response((FIXTURES / name).read_text())


class TestBuildPurchaseVoucher:
    def test_inr_purchase(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Office Equipment",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        assert vd.voucher_type == "Purchase"
        assert vd.party_ledger == "Croma Electronics"
        assert vd.is_party_ledger is True
        assert vd.bill_type == "New Ref"
        assert vd.amount == doc.inr_amount

    def test_usd_purchase_uses_inr_amount(self):
        doc = _load_doc("purchase_saas_usd.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Anthropic PBC",
            purchase_ledger="SaaS Subscriptions",
        )
        # Should use inr_amount, not total_amount (which is in USD)
        assert vd.amount == doc.inr_amount

    def test_purchase_gst_entries_input(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma",
            purchase_ledger="Purchases",
            gst_ledgers={"cgst_input": "INPUT CGST", "sgst_input": "INPUT SGST"},
        )
        assert len(vd.gst_entries) == 2
        ledger_names = [e["ledger"] for e in vd.gst_entries]
        assert "INPUT CGST" in ledger_names


class TestBuildSalesVoucher:
    def test_inr_sales(self):
        doc = _load_doc("sales_service_inr.json")
        vd = build_sales_voucher_data(
            doc, party_ledger="Infosys Ltd",
            sales_ledger="Sales",
            gst_ledgers={"cgst_output": "OUTPUT CGST", "sgst_output": "OUTPUT SGST"},
        )
        assert vd.voucher_type == "Sales"
        assert vd.party_ledger == "Infosys Ltd"
        assert vd.is_party_ledger is True
        assert len(vd.gst_entries) == 2

    def test_eur_sales_uses_inr(self):
        doc = _load_doc("sales_service_eur.json")
        vd = build_sales_voucher_data(
            doc, party_ledger="Acme GmbH",
            sales_ledger="Export Sales",
        )
        assert vd.amount == doc.inr_amount


class TestBuildDebitNote:
    def test_with_ref(self):
        doc = _load_doc("debit_note_return_inr.json")
        vd = build_debit_note_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Purchases",
            original_ref="CRO-2026-5678",
        )
        assert vd.voucher_type == "Debit Note"
        assert vd.bill_reference == "CRO-2026-5678"
        assert vd.bill_type == "Agst Ref"

    def test_without_ref(self):
        doc = _load_doc("debit_note_no_ref.json")
        vd = build_debit_note_data(
            doc, party_ledger="Unknown Supplier",
            purchase_ledger="Purchases",
        )
        assert vd.bill_reference is None


class TestBuildCreditNote:
    def test_with_ref(self):
        doc = _load_doc("credit_note_return_inr.json")
        vd = build_credit_note_data(
            doc, party_ledger="Infosys Ltd",
            sales_ledger="Sales",
            original_ref="INV-2026-FEB-001",
        )
        assert vd.voucher_type == "Credit Note"
        assert vd.bill_reference == "INV-2026-FEB-001"
        assert vd.bill_type == "Agst Ref"


class TestNarrationUsesPartyName:
    def test_party_name_in_narration(self):
        doc = _load_doc("purchase_office_inr.json")
        vd = build_purchase_voucher_data(
            doc, party_ledger="Croma Electronics",
            purchase_ledger="Purchases",
        )
        assert "Croma Electronics" in vd.narration
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_voucher_builder_multi.py -v
```

Expected: FAIL — `build_purchase_voucher_data` etc. not defined.

- [ ] **Step 3: Update VoucherData and add builder functions**

Modify `backend/services/voucher_builder.py`:

```python
"""Convert ExtractedDocument into Tally voucher payload data.

Handles date format conversion (YYYY-MM-DD → YYYYMMDD), narration building,
and GST entry construction. Output is consumed by TallyWriter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from backend.services.document_parser import ExtractedDocument


@dataclass
class VoucherData:
    voucher_type: str
    date: str  # YYYYMMDD
    debit_ledger: str
    credit_ledger: str
    amount: Decimal
    narration: str
    gst_entries: list[dict] = field(default_factory=list)
    # Group B additions
    party_ledger: str | None = None
    is_party_ledger: bool = False
    bill_reference: str | None = None
    bill_type: str = "New Ref"


def _convert_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Tally import."""
    return date_str.replace("-", "")


def _build_narration(doc: ExtractedDocument) -> str:
    """Build narration from party name and line item descriptions."""
    parts = []
    name = doc.party_name or doc.vendor_name
    if name:
        parts.append(name)
    descriptions = [item.description for item in doc.line_items if item.description]
    if descriptions:
        parts.append(", ".join(descriptions[:3]))
    return " — ".join(parts) if parts else "Entry"


def _extract_gst_entries(
    doc: ExtractedDocument,
    gst_ledgers: dict[str, str] | None,
    direction: str,
) -> list[dict]:
    """Extract GST entries from document.

    direction: "input" for Purchase/DN, "output" for Sales/CN.
    """
    entries: list[dict] = []
    if not doc.gst or not gst_ledgers:
        return entries

    prefix = f"cgst_{direction}"
    if doc.gst.cgst_amount and prefix in gst_ledgers:
        entries.append({"ledger": gst_ledgers[prefix], "amount": float(doc.gst.cgst_amount)})

    prefix = f"sgst_{direction}"
    if doc.gst.sgst_amount and prefix in gst_ledgers:
        entries.append({"ledger": gst_ledgers[prefix], "amount": float(doc.gst.sgst_amount)})

    prefix = f"igst_{direction}"
    if doc.gst.igst_amount and prefix in gst_ledgers:
        entries.append({"ledger": gst_ledgers[prefix], "amount": float(doc.gst.igst_amount)})

    return entries


def _get_amount(doc: ExtractedDocument) -> Decimal:
    """Get the INR amount to use for the voucher."""
    if hasattr(doc, "inr_amount") and doc.inr_amount:
        return doc.inr_amount
    return doc.total_amount


def build_payment_voucher_data(
    doc: ExtractedDocument,
    expense_ledger: str,
    payment_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Payment voucher."""
    gst_entries = _extract_gst_entries(doc, gst_ledgers, "input")
    return VoucherData(
        voucher_type="Payment",
        date=_convert_date(doc.date),
        debit_ledger=expense_ledger,
        credit_ledger=payment_ledger,
        amount=_get_amount(doc),
        narration=_build_narration(doc),
        gst_entries=gst_entries,
    )


def build_purchase_voucher_data(
    doc: ExtractedDocument,
    party_ledger: str,
    purchase_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Purchase voucher."""
    gst_entries = _extract_gst_entries(doc, gst_ledgers, "input")
    return VoucherData(
        voucher_type="Purchase",
        date=_convert_date(doc.date),
        debit_ledger=purchase_ledger,
        credit_ledger=party_ledger,
        amount=_get_amount(doc),
        narration=_build_narration(doc),
        gst_entries=gst_entries,
        party_ledger=party_ledger,
        is_party_ledger=True,
        bill_type="New Ref",
    )


def build_sales_voucher_data(
    doc: ExtractedDocument,
    party_ledger: str,
    sales_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Sales voucher."""
    gst_entries = _extract_gst_entries(doc, gst_ledgers, "output")
    return VoucherData(
        voucher_type="Sales",
        date=_convert_date(doc.date),
        debit_ledger=party_ledger,
        credit_ledger=sales_ledger,
        amount=_get_amount(doc),
        narration=_build_narration(doc),
        gst_entries=gst_entries,
        party_ledger=party_ledger,
        is_party_ledger=True,
        bill_type="New Ref",
    )


def build_debit_note_data(
    doc: ExtractedDocument,
    party_ledger: str,
    purchase_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    original_ref: str | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Debit Note."""
    gst_entries = _extract_gst_entries(doc, gst_ledgers, "input")
    return VoucherData(
        voucher_type="Debit Note",
        date=_convert_date(doc.date),
        debit_ledger=purchase_ledger,
        credit_ledger=party_ledger,
        amount=_get_amount(doc),
        narration=_build_narration(doc),
        gst_entries=gst_entries,
        party_ledger=party_ledger,
        is_party_ledger=True,
        bill_reference=original_ref,
        bill_type="Agst Ref",
    )


def build_credit_note_data(
    doc: ExtractedDocument,
    party_ledger: str,
    sales_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
    original_ref: str | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Credit Note."""
    gst_entries = _extract_gst_entries(doc, gst_ledgers, "output")
    return VoucherData(
        voucher_type="Credit Note",
        date=_convert_date(doc.date),
        debit_ledger=party_ledger,
        credit_ledger=sales_ledger,
        amount=_get_amount(doc),
        narration=_build_narration(doc),
        gst_entries=gst_entries,
        party_ledger=party_ledger,
        is_party_ledger=True,
        bill_reference=original_ref,
        bill_type="Agst Ref",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_voucher_builder_multi.py -v
```

- [ ] **Step 5: Run existing voucher builder tests (regression)**

```bash
pytest tests/unit/test_voucher_builder.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/services/voucher_builder.py tests/unit/test_voucher_builder_multi.py
git commit -m "feat: add Purchase/Sales/DN/CN voucher builder functions"
```

---

### Task 5: TallyWriter — 4 New Write Methods

**Files:**
- Modify: `backend/tally_bridge/writer.py`
- Create: `tests/unit/test_writer_multi.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_writer_multi.py` testing that TallyWriter has `create_purchase_voucher`, `create_sales_voucher`, `create_debit_note`, `create_credit_note` methods that call the correct import_builder functions, validate, and return results. Use a mock TallyClient that returns success XML.

```python
"""Tests for TallyWriter Purchase/Sales/DN/CN write methods."""
from unittest.mock import AsyncMock

import pytest

from backend.tally_bridge.writer import TallyWriter, ValidationError


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.post_xml.return_value = """<RESPONSE>
<CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
<LASTVCHID>100</LASTVCHID><LASTMID>100</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
<CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>"""
    return client


@pytest.mark.asyncio
class TestCreatePurchaseVoucher:
    async def test_success(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_purchase_voucher(
            date="20260210", party_ledger="Supplier",
            purchase_ledger="Purchases", amount=1000.0,
            narration="test purchase",
        )
        assert result["success"] is True
        assert result["last_vch_id"] == "100"
        mock_client.post_xml.assert_called_once()
        xml = mock_client.post_xml.call_args[0][0]
        assert 'VCHTYPE="Purchase"' in xml

    async def test_validation_error(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        with pytest.raises(ValidationError):
            await writer.create_purchase_voucher(
                date="", party_ledger="S", purchase_ledger="P",
                amount=1000.0, narration="",
            )

    async def test_with_gst_and_bill_ref(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_purchase_voucher(
            date="20260210", party_ledger="Supplier",
            purchase_ledger="Purchases", amount=11800.0,
            narration="test", gst_entries=[{"ledger": "INPUT CGST", "amount": 900.0}],
            bill_ref="INV-001",
        )
        assert result["success"] is True


@pytest.mark.asyncio
class TestCreateSalesVoucher:
    async def test_success(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_sales_voucher(
            date="20260301", party_ledger="Customer",
            sales_ledger="Sales", amount=1000.0,
            narration="test sale",
        )
        assert result["success"] is True
        xml = mock_client.post_xml.call_args[0][0]
        assert 'VCHTYPE="Sales"' in xml


@pytest.mark.asyncio
class TestCreateDebitNote:
    async def test_success(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_debit_note(
            date="20260305", party_ledger="Supplier",
            purchase_ledger="Purchases", amount=1000.0,
            narration="return", bill_ref="INV-001",
        )
        assert result["success"] is True
        xml = mock_client.post_xml.call_args[0][0]
        assert 'VCHTYPE="Debit Note"' in xml


@pytest.mark.asyncio
class TestCreateCreditNote:
    async def test_success(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_credit_note(
            date="20260315", party_ledger="Customer",
            sales_ledger="Sales", amount=1000.0,
            narration="discount", bill_ref="INV-FEB-001",
        )
        assert result["success"] is True
        xml = mock_client.post_xml.call_args[0][0]
        assert 'VCHTYPE="Credit Note"' in xml
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_writer_multi.py -v
```

- [ ] **Step 3: Add write methods to TallyWriter**

Add to `backend/tally_bridge/writer.py`. Import the new builder functions and add 4 methods following the same pattern as `create_payment_voucher`:

```python
from backend.tally_bridge.import_builder import (
    build_cancel_voucher,
    build_create_credit_note,
    build_create_debit_note,
    build_create_group,
    build_create_ledger,
    build_create_payment_voucher,
    build_create_purchase_voucher,
    build_create_sales_voucher,
    build_delete_group,
    build_delete_ledger,
    build_delete_voucher,
)

# ... existing class ...

    async def create_purchase_voucher(
        self, date: str, party_ledger: str, purchase_ledger: str,
        amount: float, narration: str,
        gst_entries: list[dict] | None = None,
        bill_ref: str | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Purchase voucher in Tally with validation."""
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": purchase_ledger, "amount": -base_amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": -gst["amount"], "is_debit": True})
        entries.append({"ledger": party_ledger, "amount": amount, "is_debit": False})

        errors = self.validate_voucher(
            {"voucher_type": "Purchase", "date": date, "narration": narration, "ledger_entries": entries},
            known_ledgers,
        )
        if errors:
            raise ValidationError(errors)

        xml = build_create_purchase_voucher(
            date=date, party_ledger=party_ledger, purchase_ledger=purchase_ledger,
            amount=amount, narration=narration, company=self.company,
            gst_entries=gst_entries, bill_ref=bill_ref,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_sales_voucher(
        self, date: str, party_ledger: str, sales_ledger: str,
        amount: float, narration: str,
        gst_entries: list[dict] | None = None,
        bill_ref: str | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Sales voucher in Tally with validation."""
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": party_ledger, "amount": -amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": gst["amount"], "is_debit": False})
        entries.append({"ledger": sales_ledger, "amount": base_amount, "is_debit": False})

        errors = self.validate_voucher(
            {"voucher_type": "Sales", "date": date, "narration": narration, "ledger_entries": entries},
            known_ledgers,
        )
        if errors:
            raise ValidationError(errors)

        xml = build_create_sales_voucher(
            date=date, party_ledger=party_ledger, sales_ledger=sales_ledger,
            amount=amount, narration=narration, company=self.company,
            gst_entries=gst_entries, bill_ref=bill_ref,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_debit_note(
        self, date: str, party_ledger: str, purchase_ledger: str,
        amount: float, narration: str,
        gst_entries: list[dict] | None = None,
        bill_ref: str | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Debit Note in Tally with validation."""
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": purchase_ledger, "amount": -base_amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": -gst["amount"], "is_debit": True})
        entries.append({"ledger": party_ledger, "amount": amount, "is_debit": False})

        errors = self.validate_voucher(
            {"voucher_type": "Debit Note", "date": date, "narration": narration, "ledger_entries": entries},
            known_ledgers,
        )
        if errors:
            raise ValidationError(errors)

        xml = build_create_debit_note(
            date=date, party_ledger=party_ledger, purchase_ledger=purchase_ledger,
            amount=amount, narration=narration, company=self.company,
            gst_entries=gst_entries, bill_ref=bill_ref,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_credit_note(
        self, date: str, party_ledger: str, sales_ledger: str,
        amount: float, narration: str,
        gst_entries: list[dict] | None = None,
        bill_ref: str | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Credit Note in Tally with validation."""
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": party_ledger, "amount": -amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": gst["amount"], "is_debit": False})
        entries.append({"ledger": sales_ledger, "amount": base_amount, "is_debit": False})

        errors = self.validate_voucher(
            {"voucher_type": "Credit Note", "date": date, "narration": narration, "ledger_entries": entries},
            known_ledgers,
        )
        if errors:
            raise ValidationError(errors)

        xml = build_create_credit_note(
            date=date, party_ledger=party_ledger, sales_ledger=sales_ledger,
            amount=amount, narration=narration, company=self.company,
            gst_entries=gst_entries, bill_ref=bill_ref,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_writer_multi.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/writer.py tests/unit/test_writer_multi.py
git commit -m "feat: add Purchase/Sales/DN/CN write methods to TallyWriter"
```

---

### Task 6: Mock Handler — Company List + Party Voucher Lookup

**Files:**
- Modify: `backend/tally_bridge/mock_handler.py`
- Create: `tests/unit/test_mock_handler_group_b.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_mock_handler_group_b.py`:

```python
"""Tests for mock handler Group B additions: company list + party voucher lookup."""
import xml.etree.ElementTree as ET

from backend.tally_bridge.mock_handler import mock_tally_request


class TestCompanyListMock:
    def test_company_list_returns_fixture_company(self):
        # This is the XML query for listing companies (LISTOFCOMPANIES collection)
        xml = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "Bharat Traders Pvt Ltd" in result


class TestPartyVoucherLookupMock:
    def test_party_voucher_lookup_returns_sample_vouchers(self):
        # Query with LEDGERNAME filter for party vouchers
        xml = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><LEDGERNAME>Croma Electronics</LEDGERNAME></STATICVARIABLES></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        root = ET.fromstring(result)
        vouchers = root.findall(".//VOUCHER")
        assert len(vouchers) >= 1

    def test_unknown_party_returns_empty(self):
        xml = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><LEDGERNAME>Nonexistent Party</LEDGERNAME></STATICVARIABLES></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        root = ET.fromstring(result)
        vouchers = root.findall(".//VOUCHER")
        assert len(vouchers) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_mock_handler_group_b.py -v
```

- [ ] **Step 3: Add company list + party voucher lookup to mock_handler.py**

Add to `mock_tally_request()` before the existing fixture-based routing:

```python
    # Company list query
    if "List of Companies" in xml_body:
        return """<ENVELOPE><BODY><DATA><COLLECTION>
<COMPANY><NAME>Bharat Traders Pvt Ltd</NAME></COMPANY>
</COLLECTION></DATA></BODY></ENVELOPE>"""

    # Party voucher lookup (for DN/CN reference matching)
    if "<LEDGERNAME>" in xml_body and "Vouchers" in xml_body:
        import re
        match = re.search(r"<LEDGERNAME>(.*?)</LEDGERNAME>", xml_body)
        party = match.group(1) if match else ""
        known_parties = {"Croma Electronics", "Infosys Ltd", "Anthropic PBC"}
        if party in known_parties:
            return f"""<ENVELOPE><BODY><DATA><COLLECTION>
<VOUCHER><VOUCHERNUMBER>PUR-001</VOUCHERNUMBER><DATE>20260210</DATE>
<AMOUNT>15340.00</AMOUNT><VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<PARTYLEDGERNAME>{party}</PARTYLEDGERNAME></VOUCHER>
<VOUCHER><VOUCHERNUMBER>PUR-002</VOUCHERNUMBER><DATE>20260115</DATE>
<AMOUNT>8500.00</AMOUNT><VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<PARTYLEDGERNAME>{party}</PARTYLEDGERNAME></VOUCHER>
</COLLECTION></DATA></BODY></ENVELOPE>"""
        return """<ENVELOPE><BODY><DATA><COLLECTION></COLLECTION></DATA></BODY></ENVELOPE>"""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_mock_handler_group_b.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/mock_handler.py tests/unit/test_mock_handler_group_b.py
git commit -m "feat: add company list + party voucher mock responses"
```

---

### Task 7: Tally Bridge Queries — Company List + Party Vouchers

**Files:**
- Modify: `backend/tally_bridge/queries/masters.py`
- Modify: `backend/tally_bridge/queries/vouchers.py`

- [ ] **Step 1: Add `get_company_list_from_host()` to masters.py**

Add after existing `list_companies()`:

```python
async def get_company_list_from_host(host: str, port: int) -> list[str]:
    """Fetch company list from an arbitrary Tally host:port.

    Used by ConnectCompanyModal to discover company names.
    Creates a temporary TallyClient for the given host.
    """
    from backend.tally_bridge.client import TallyClient
    temp_client = TallyClient(host, port)
    xml = build_list_companies()
    response = await temp_client.post_xml(xml)
    companies = parse_company_list(response)
    return [c["name"] for c in companies]
```

- [ ] **Step 2: Add `get_party_vouchers()` to vouchers.py**

```python
async def get_party_vouchers(
    client,
    party_name: str,
    voucher_types: list[str],
    company: str | None = None,
) -> list[dict]:
    """Fetch recent vouchers for a party, filtered by type.

    Used by DN/CN flow to find matching original invoices.
    Returns list of {voucher_number, date, amount, voucher_type}.
    """
    # Build TDL query for party vouchers
    type_filter = " OR ".join(f'$VOUCHERTYPENAME = "{vt}"' for vt in voucher_types)
    xml = f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY><EXPORTDATA><REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES>
<LEDGERNAME>{party_name}</LEDGERNAME>
</STATICVARIABLES>
</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"""

    response = await client.post_xml(xml)

    import xml.etree.ElementTree as ET
    root = ET.fromstring(response)
    results = []
    for v in root.findall(".//VOUCHER"):
        vtype = v.findtext("VOUCHERTYPENAME", "")
        if vtype in voucher_types:
            results.append({
                "voucher_number": v.findtext("VOUCHERNUMBER", ""),
                "date": v.findtext("DATE", ""),
                "amount": float(v.findtext("AMOUNT", "0")),
                "voucher_type": vtype,
            })
    return results
```

- [ ] **Step 3: Run all unit tests (regression)**

```bash
pytest tests/unit/ -v --timeout=30
```

- [ ] **Step 4: Commit**

```bash
git add backend/tally_bridge/queries/masters.py backend/tally_bridge/queries/vouchers.py
git commit -m "feat: add company list from host + party voucher lookup queries"
```

---

### Task 8: Backend API — Test Connection Endpoint + Voucher Action Dispatch

**Files:**
- Create: `backend/api/tally.py`
- Modify: `backend/api/chat.py` (lines 260-270)
- Modify: `backend/api/models.py`
- Modify: `backend/api/__init__.py` or `backend/main.py` (register router)

- [ ] **Step 1: Create test-connection endpoint**

Create `backend/api/tally.py`:

```python
"""Tally connectivity endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/tally", tags=["tally"])


class TestConnectionRequest(BaseModel):
    host: str = "localhost"
    port: int = 9000


class TestConnectionResponse(BaseModel):
    connected: bool
    companies: list[str] = []
    error: str | None = None


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    req: TestConnectionRequest,
    user_id: str = Depends(get_current_user),
) -> TestConnectionResponse:
    """Test connectivity to a Tally instance and return available companies."""
    from backend.tally_bridge.queries.masters import get_company_list_from_host

    try:
        companies = await get_company_list_from_host(req.host, req.port)
        return TestConnectionResponse(connected=True, companies=companies)
    except Exception as e:
        return TestConnectionResponse(connected=False, error=str(e))
```

- [ ] **Step 2: Register the router in main.py**

Find where other routers are included in `backend/main.py` and add:

```python
from backend.api.tally import router as tally_router
app.include_router(tally_router)
```

- [ ] **Step 3: Update VoucherReviewEntry model**

Add to `backend/api/models.py` VoucherReviewEntry class:

```python
class VoucherReviewEntry(BaseModel):
    """A single voucher entry for review."""
    id: str
    voucher_type: str
    date: str
    vendor_name: str | None = None
    party_name: str | None = None       # NEW: canonical party name
    amount: float
    debit_ledger: str
    credit_ledger: str
    narration: str
    gst_entries: list[dict[str, Any]] = []
    status: str = "draft"
    warnings: list[str] = []
    is_new_ledger: bool = False
    suggested_parent: str | None = None
    # Group B additions
    party_ledger: str | None = None
    is_party_ledger: bool = False
    original_currency: str = "INR"
    original_amount: float | None = None
    fx_rate: float | None = None
    inr_amount: float | None = None
    bill_reference: str | None = None
    bill_type: str = "New Ref"
    party_vouchers: list[dict[str, Any]] = []  # for DN/CN reference dropdown
```

- [ ] **Step 4: Update voucher_action endpoint for multi-type dispatch**

In `backend/api/chat.py`, replace the hardcoded `writer.create_payment_voucher(...)` call (lines 261-270) with type-based dispatch:

```python
        # Create the voucher — dispatch by type
        voucher_type = entry.get("voucher_type", "Payment")
        try:
            gst_entries = entry.get("gst_entries") or None
            if voucher_type == "Payment":
                result = await writer.create_payment_voucher(
                    date=entry["date"], debit_ledger=entry["debit_ledger"],
                    credit_ledger=entry["credit_ledger"], amount=entry["amount"],
                    narration=entry["narration"], gst_entries=gst_entries,
                )
            elif voucher_type == "Purchase":
                result = await writer.create_purchase_voucher(
                    date=entry["date"], party_ledger=entry["party_ledger"],
                    purchase_ledger=entry["debit_ledger"], amount=entry["amount"],
                    narration=entry["narration"], gst_entries=gst_entries,
                    bill_ref=entry.get("bill_reference"),
                )
            elif voucher_type == "Sales":
                result = await writer.create_sales_voucher(
                    date=entry["date"], party_ledger=entry["party_ledger"],
                    sales_ledger=entry["credit_ledger"], amount=entry["amount"],
                    narration=entry["narration"], gst_entries=gst_entries,
                    bill_ref=entry.get("bill_reference"),
                )
            elif voucher_type == "Debit Note":
                result = await writer.create_debit_note(
                    date=entry["date"], party_ledger=entry["party_ledger"],
                    purchase_ledger=entry["debit_ledger"], amount=entry["amount"],
                    narration=entry["narration"], gst_entries=gst_entries,
                    bill_ref=entry.get("bill_reference"),
                )
            elif voucher_type == "Credit Note":
                result = await writer.create_credit_note(
                    date=entry["date"], party_ledger=entry["party_ledger"],
                    sales_ledger=entry["credit_ledger"], amount=entry["amount"],
                    narration=entry["narration"], gst_entries=gst_entries,
                    bill_ref=entry.get("bill_reference"),
                )
            else:
                return ChatResponse(
                    message=f"Unknown voucher type: {voucher_type}",
                    data={"type": "voucher_error", "entry_id": entry.get("id")},
                    session_id=session_id,
                )
```

Also update the success message from `"Payment voucher written"` to `f"{voucher_type} voucher written"`.

- [ ] **Step 5: Run tests (regression)**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v --timeout=60
```

- [ ] **Step 6: Commit**

```bash
git add backend/api/tally.py backend/api/chat.py backend/api/models.py backend/main.py
git commit -m "feat: test-connection endpoint + multi-type voucher action dispatch"
```

---

### Task 9: Orchestrator — Route by Doc Type + DB Audit

**Files:**
- Modify: `backend/agents/orchestrator.py` (lines 131-291)

This is the most complex backend task. The orchestrator's `process_file_upload` currently hardcodes Payment flow. We need to:
1. Route by `doc_type` from extraction
2. Fetch party vouchers for DN/CN
3. Use correct voucher builder
4. Include multi-currency fields in review card
5. Persist UploadedFile row

- [ ] **Step 1: Update imports in orchestrator.py**

Add imports for new builder functions:

```python
from backend.services.voucher_builder import (
    build_credit_note_data,
    build_debit_note_data,
    build_payment_voucher_data,
    build_purchase_voucher_data,
    build_sales_voucher_data,
)
from backend.tally_bridge.queries.vouchers import get_party_vouchers
```

- [ ] **Step 2: Add routing logic by doc_type**

Replace the section from "4. Map vendor to ledger" through "6. Assemble review card" (lines 240-291) with routing that:
- For `payment`: use existing flow (expense ledger + payment ledger)
- For `purchase`: map party to Sundry Creditors, expense to appropriate purchase ledger
- For `sales`: map party to Sundry Debtors, revenue to Sales ledger
- For `debit_note`: same as purchase mapping + fetch party Purchase vouchers
- For `credit_note`: same as sales mapping + fetch party Sales vouchers

Build correct VoucherData, include `party_ledger`, `original_currency`, `fx_rate`, `inr_amount`, `bill_reference`, and `party_vouchers` (for DN/CN) in the review card response.

The full implementation should follow this pattern:

```python
        # 4. Route by doc_type
        doc_type = extracted.doc_type
        party_vouchers_list = []

        if doc_type == "payment":
            mapping = await mapper.find_mapping(
                extracted.party_name or "Expense", "Payment",
                tally_ledgers=ledger_names,
            )
            voucher = build_payment_voucher_data(
                doc=extracted, expense_ledger=mapping.ledger_name,
                payment_ledger=payment_ledgers[0],
            )
        elif doc_type in ("purchase", "debit_note"):
            # Party under Sundry Creditors
            party_name = extracted.party_name or "Unknown Supplier"
            mapping = await mapper.find_mapping(
                party_name, doc_type, tally_ledgers=ledger_names,
            )
            purchase_ledger = mapping.ledger_name

            if doc_type == "debit_note":
                party_vouchers_list = await get_party_vouchers(
                    client, party_name, ["Purchase"], company=None,
                )
                voucher = build_debit_note_data(
                    doc=extracted, party_ledger=party_name,
                    purchase_ledger=purchase_ledger,
                    original_ref=extracted.original_invoice_ref,
                )
            else:
                voucher = build_purchase_voucher_data(
                    doc=extracted, party_ledger=party_name,
                    purchase_ledger=purchase_ledger,
                )
        elif doc_type in ("sales", "credit_note"):
            party_name = extracted.party_name or "Unknown Customer"
            mapping = await mapper.find_mapping(
                party_name, doc_type, tally_ledgers=ledger_names,
            )
            sales_ledger = mapping.ledger_name

            if doc_type == "credit_note":
                party_vouchers_list = await get_party_vouchers(
                    client, party_name, ["Sales"], company=None,
                )
                voucher = build_credit_note_data(
                    doc=extracted, party_ledger=party_name,
                    sales_ledger=sales_ledger,
                    original_ref=extracted.original_invoice_ref,
                )
            else:
                voucher = build_sales_voucher_data(
                    doc=extracted, party_ledger=party_name,
                    sales_ledger=sales_ledger,
                )
        else:
            # Fallback to payment
            mapping = await mapper.find_mapping(
                extracted.party_name or "Expense", "Payment",
                tally_ledgers=ledger_names,
            )
            voucher = build_payment_voucher_data(
                doc=extracted, expense_ledger=mapping.ledger_name,
                payment_ledger=payment_ledgers[0],
            )
```

- [ ] **Step 3: Update review card assembly with Group B fields**

```python
        review_data = {
            "type": "voucher_review",
            "file_id": file_id,
            "entries": [{
                "id": entry_id,
                "voucher_type": voucher.voucher_type,
                "date": voucher.date,
                "vendor_name": extracted.party_name,
                "party_name": extracted.party_name,
                "amount": float(voucher.amount),
                "debit_ledger": voucher.debit_ledger,
                "credit_ledger": voucher.credit_ledger,
                "narration": voucher.narration,
                "gst_entries": voucher.gst_entries,
                "status": "draft",
                "warnings": warnings,
                "is_new_ledger": mapping.is_new_ledger,
                "suggested_parent": mapping.suggested_parent,
                # Group B additions
                "party_ledger": voucher.party_ledger,
                "is_party_ledger": voucher.is_party_ledger,
                "original_currency": extracted.original_currency,
                "original_amount": float(extracted.original_amount),
                "fx_rate": float(extracted.fx_rate) if extracted.fx_rate else None,
                "inr_amount": float(extracted.inr_amount),
                "bill_reference": voucher.bill_reference,
                "bill_type": voucher.bill_type,
                "party_vouchers": party_vouchers_list,
            }],
            "available_ledgers": ledger_names,
            "available_payment_ledgers": payment_ledgers,
        }
```

- [ ] **Step 4: Update the response message to be type-aware**

```python
        type_labels = {
            "Payment": "payment", "Purchase": "purchase invoice",
            "Sales": "sales invoice", "Debit Note": "debit note",
            "Credit Note": "credit note",
        }
        type_label = type_labels.get(voucher.voucher_type, "entry")
        party_display = extracted.party_name or "Unknown"

        if extracted.original_currency != "INR" and extracted.fx_rate:
            amount_display = (
                f"{extracted.original_currency} {float(extracted.original_amount):,.2f} "
                f"(≈ ₹{float(voucher.amount):,.2f} @ {float(extracted.fx_rate):.2f})"
            )
        else:
            amount_display = f"₹{float(voucher.amount):,.2f}"

        message = (
            f"I've extracted the {type_label} details:\n\n"
            f"**{party_display}** — {amount_display} on {extracted.date}\n\n"
            f"Please review the entry below and click **Write to Tally** to create "
            f"the {voucher.voucher_type.lower()} voucher, or **Edit Entry** to make corrections."
        )
```

- [ ] **Step 5: Run regression tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v --timeout=60
pytest tests/unit/ -v --timeout=30
```

- [ ] **Step 6: Commit**

```bash
git add backend/agents/orchestrator.py
git commit -m "feat: orchestrator routes by doc_type, multi-currency, DN/CN voucher lookup"
```

---

### Task 10: Frontend API Client — Test Connection Function

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add testTallyConnection function**

```typescript
export interface TestConnectionResponse {
  connected: boolean;
  companies: string[];
  error?: string;
}

export async function testTallyConnection(
  host: string,
  port: number,
): Promise<TestConnectionResponse> {
  const { data } = await api.post<TestConnectionResponse>("/tally/test-connection", {
    host,
    port,
  });
  return data;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add testTallyConnection API function"
```

---

### Task 11: ConnectCompanyModal — Tally Company Dropdown

**Files:**
- Modify: `frontend/src/components/ConnectCompanyModal.tsx`
- Create: `frontend/src/__tests__/ConnectCompanyModal.test.tsx`

- [ ] **Step 1: Write failing Vitest tests**

Create `frontend/src/__tests__/ConnectCompanyModal.test.tsx` with tests for all 8 states from the spec matrix:
- Initial state (host + port fields, no dropdown)
- Connecting state (loading spinner)
- Connected state (dropdown populated)
- Connection failed (error message)
- Mock mode on (auto-fill, no dropdown)
- Mock mode toggle resets state
- Single company auto-selected
- Multiple companies require selection

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test -- --run ConnectCompanyModal
```

- [ ] **Step 3: Rewrite ConnectCompanyModal**

Replace the current free-text name field with:
1. Host + port fields (unchanged)
2. "Test Connection" button
3. On success: company dropdown populated from API response
4. Selected company → workspace name AND config.tally_company
5. Mock mode: skip connection, auto-fill "Bharat Traders Pvt Ltd"

```tsx
import { useState } from "react";
import { createWorkspace, testTallyConnection } from "../api/client";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: () => void;
}

type ConnectionState = "idle" | "connecting" | "connected" | "error";

export default function ConnectCompanyModal({ onClose, onCreated }: ConnectCompanyModalProps) {
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [mockMode, setMockMode] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [companies, setCompanies] = useState<string[]>([]);
  const [selectedCompany, setSelectedCompany] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  const handleTestConnection = async () => {
    setConnectionState("connecting");
    setError("");
    try {
      const result = await testTallyConnection(tallyHost, parseInt(tallyPort, 10));
      if (result.connected && result.companies.length > 0) {
        setCompanies(result.companies);
        setSelectedCompany(result.companies.length === 1 ? result.companies[0] : "");
        setConnectionState("connected");
      } else {
        setError(result.error || "No companies found");
        setConnectionState("error");
      }
    } catch {
      setError("Could not reach Tally. Check host and port.");
      setConnectionState("error");
    }
  };

  const handleMockToggle = (checked: boolean) => {
    setMockMode(checked);
    if (checked) {
      setCompanies(["Bharat Traders Pvt Ltd"]);
      setSelectedCompany("Bharat Traders Pvt Ltd");
      setConnectionState("connected");
      setError("");
    } else {
      setCompanies([]);
      setSelectedCompany("");
      setConnectionState("idle");
    }
  };

  const handleCreate = async () => {
    if (!selectedCompany) return;
    setCreating(true);
    setError("");
    try {
      await createWorkspace({
        name: selectedCompany,
        config: {
          tally_host: tallyHost,
          tally_port: parseInt(tallyPort, 10),
          tally_company: selectedCompany,
          mock_mode: mockMode,
        },
      });
      onCreated();
    } catch {
      setError("Failed to create workspace.");
    } finally {
      setCreating(false);
    }
  };

  const canCreate = connectionState === "connected" && selectedCompany !== "";

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Connect Tally Company</h2>
        <div className="space-y-4">
          {error && <div className="bg-red-50 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700">Tally Host</label>
            <input type="text" value={tallyHost} onChange={(e) => setTallyHost(e.target.value)}
              disabled={connectionState === "connected" && !mockMode}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Tally Port</label>
            <input type="number" value={tallyPort} onChange={(e) => setTallyPort(e.target.value)}
              disabled={connectionState === "connected" && !mockMode}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100" />
          </div>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <span className="text-sm font-medium text-gray-700">Demo Mode</span>
            <div className="relative">
              <input type="checkbox" className="sr-only peer" checked={mockMode}
                onChange={(e) => handleMockToggle(e.target.checked)} />
              <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="text-xs text-gray-500">{mockMode ? "Uses sample data" : "Connects to live Tally"}</span>
          </label>

          {!mockMode && connectionState !== "connected" && (
            <button type="button" onClick={handleTestConnection}
              disabled={connectionState === "connecting"}
              className="w-full px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50">
              {connectionState === "connecting" ? "Connecting..." : "Test Connection"}
            </button>
          )}

          {connectionState === "connected" && companies.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Company</label>
              {companies.length === 1 ? (
                <div className="mt-1 px-3 py-2 bg-green-50 border border-green-200 rounded-md text-sm text-green-800">
                  {companies[0]}
                </div>
              ) : (
                <select value={selectedCompany} onChange={(e) => setSelectedCompany(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500">
                  <option value="">Select a company...</option>
                  {companies.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              )}
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md">Cancel</button>
            <button type="button" onClick={handleCreate} disabled={!canCreate || creating}
              className="px-4 py-2 text-sm text-white bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50">
              {creating ? "Creating..." : "Create Workspace"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm test -- --run ConnectCompanyModal
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ConnectCompanyModal.tsx frontend/src/__tests__/ConnectCompanyModal.test.tsx frontend/src/api/client.ts
git commit -m "feat: ConnectCompanyModal queries Tally for company dropdown"
```

---

### Task 12: Frontend — VoucherReviewCard Redesign (Collapsed + Expanded)

**Files:**
- Modify: `frontend/src/components/VoucherReviewCard.tsx`
- Create: `frontend/src/components/VoucherReviewExpanded.tsx`
- Create: `frontend/src/__tests__/fixtures/voucherMockData.ts`
- Create: `frontend/src/__tests__/VoucherReviewCard.test.tsx`

This task implements the collapsed and expanded states. Task 13 handles the edit form.

- [ ] **Step 1: Create mock data fixtures**

Create `frontend/src/__tests__/fixtures/voucherMockData.ts` with pre-built VoucherEntry objects for all type × state × currency combinations from the spec matrix.

- [ ] **Step 2: Write Vitest tests for collapsed + expanded states**

Test all 11 combinations from the spec matrix (Payment collapsed INR, Purchase collapsed USD, etc.) plus the toggle behavior.

- [ ] **Step 3: Implement VoucherReviewExpanded component**

Read-only detail view showing line items, GST breakdown, FX rate, bill reference. Takes a VoucherEntry and renders it.

- [ ] **Step 4: Rewrite VoucherReviewCard with type badges and progressive disclosure**

The collapsed card shows: type badge (color-coded), party name, date, amount (dual currency if FX), warning banners, "Show details" toggle, action buttons. Toggle opens VoucherReviewExpanded inline. "Edit" button (shown in expanded) will be wired in Task 13.

- [ ] **Step 5: Update VoucherEntry interface**

Add `party_name`, `party_ledger`, `is_party_ledger`, `original_currency`, `original_amount`, `fx_rate`, `inr_amount`, `bill_reference`, `bill_type`, `party_vouchers` to the TypeScript interface.

- [ ] **Step 6: Run tests**

```bash
cd frontend && npm test -- --run VoucherReviewCard
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/VoucherReviewCard.tsx frontend/src/components/VoucherReviewExpanded.tsx frontend/src/__tests__/
git commit -m "feat: redesigned VoucherReviewCard with type badges and progressive disclosure"
```

---

### Task 13: Frontend — VoucherEditForm (Full-Page Mobile / Modal Desktop)

**Files:**
- Create: `frontend/src/components/VoucherEditForm.tsx`
- Create: `frontend/src/components/LineItemEditor.tsx`
- Create: `frontend/src/components/VoucherRefSelect.tsx`
- Create: `frontend/src/__tests__/VoucherEditForm.test.tsx`

- [ ] **Step 1: Write Vitest tests for edit form**

Cover all scenarios from the spec matrix: responsive layout, line item add/remove, ledger dropdowns, party ledger visibility by type, FX override, "Against Invoice" dropdown for DN/CN, save validation.

- [ ] **Step 2: Implement LineItemEditor**

Stacked cards on mobile (< 768px), table rows on desktop. Each line has: description, amount, ledger dropdown (grouped by account group). Add/remove rows.

- [ ] **Step 3: Implement VoucherRefSelect**

Dropdown for DN/CN "Against Invoice" reference. Options from `party_vouchers` array: `#{number} — {date} — ₹{amount}`. Fallback to free-text when empty.

- [ ] **Step 4: Implement VoucherEditForm**

Mobile: full-page overlay with "← Back" / "Save" header. Desktop: modal. Fields: voucher type dropdown, party ledger dropdown (hidden for Payment), date, line items, GST, FX override (shown when currency ≠ INR), VoucherRefSelect (shown for DN/CN). Save validates required fields and calls `onSave` with updated entry.

- [ ] **Step 5: Wire edit form into VoucherReviewCard**

The "Edit" button in expanded state opens VoucherEditForm. Save returns to collapsed state with updated values.

- [ ] **Step 6: Remove old EditForm**

Delete the inline `EditForm` component from VoucherReviewCard.tsx (lines 210-317 in current file).

- [ ] **Step 7: Run tests**

```bash
cd frontend && npm test -- --run VoucherEditForm
cd frontend && npm test -- --run VoucherReviewCard
```

- [ ] **Step 8: Run all frontend tests (regression)**

```bash
cd frontend && npm test
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ frontend/src/__tests__/
git commit -m "feat: VoucherEditForm with responsive layout, line items, FX override, DN/CN refs"
```

---

### Task 14: DB Audit Trail — UploadedFile + VoucherEntry Persistence

**Files:**
- Modify: `backend/agents/orchestrator.py` (add UploadedFile insert)
- Modify: `backend/api/chat.py` (add VoucherEntry insert on write/cancel/delete)
- Create: `tests/unit/test_audit_trail.py`

- [ ] **Step 1: Write tests for DB persistence**

Test that:
- File upload creates UploadedFile row
- Successful write creates VoucherEntry row linked to file
- Discard creates no VoucherEntry
- Cancel updates VoucherEntry status
- VoucherEntry stores FX fields for foreign currency writes

- [ ] **Step 2: Add UploadedFile persistence to orchestrator**

In `process_file_upload`, after extraction, persist:

```python
        # Persist uploaded file record (DB mode only)
        if db:
            from backend.db.models import UploadedFile
            import hashlib
            file_hash = hashlib.sha256(open(file_path, "rb").read()).hexdigest()
            uploaded = UploadedFile(
                user_id=user_id, workspace_id=workspace_id,
                conversation_id=conversation_id, filename=filename,
                mime_type=mime_type, file_size=os.path.getsize(file_path),
                storage_path=file_path, extracted_data=extracted.__dict__,
                status="extracted",
            )
            db.add(uploaded)
            await db.flush()
            file_id = str(uploaded.id)
```

Note: the `db`, `user_id`, `workspace_id`, `conversation_id` need to be threaded through from chat.py. This requires adding these as parameters to `process_file_upload`.

- [ ] **Step 3: Add VoucherEntry persistence to voucher_action**

In the success branch of voucher_action (after `result["success"]`):

```python
            if result["success"] and db and settings.db_mode:
                from backend.db.models import VoucherEntry as VoucherEntryDB
                ve = VoucherEntryDB(
                    file_id=entry.get("file_id"),
                    user_id=user_id, workspace_id=request.workspace_id,
                    conversation_id=entry.get("conversation_id"),
                    voucher_type=voucher_type,
                    voucher_data=entry,
                    status="written",
                    tally_response=result,
                    tally_voucher_number=str(result.get("last_vch_id", "")),
                )
                db.add(ve)
                await db.commit()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_audit_trail.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/agents/orchestrator.py backend/api/chat.py tests/unit/test_audit_trail.py
git commit -m "feat: persist UploadedFile + VoucherEntry to DB for audit trail"
```

---

### Task 15: Full Regression + E2E Tests

**Files:**
- Existing test suites

- [ ] **Step 1: Run all backend tests**

```bash
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --timeout=60
```

Expected: ALL PASS (existing + new tests)

- [ ] **Step 2: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: ALL PASS

- [ ] **Step 3: Fix any failures**

If there are regressions, fix them. Commit fixes individually.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: full regression pass after Group B implementation"
```

---

### Task 16: Playwright Visual Tests

**Files:**
- New Playwright specs under `frontend/tests/playwright/`

This task creates Playwright visual tests for the new components per the spec's visual matrix (~45-50 screenshots). Requires backend running.

**IMPORTANT:** After running, the main agent must visually inspect ALL screenshots in `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/`.

- [ ] **Step 1: Write Playwright specs for VoucherReviewCard states**

Enumerate: collapsed (Payment INR, Purchase USD, DN with ref, with warning), expanded (Purchase with GST, DN with ref), success, discarded, error — each × 3 viewports.

- [ ] **Step 2: Write Playwright specs for VoucherEditForm**

Purchase form mobile full-page, desktop modal, DN with Against Invoice, FX override.

- [ ] **Step 3: Write Playwright specs for ConnectCompanyModal**

Initial, connected with dropdown, error, mock mode — each × 3 viewports.

- [ ] **Step 4: Run Playwright tests and generate screenshots**

```bash
cd frontend && npm run test:playwright -- --update-snapshots
```

- [ ] **Step 5: Main agent visually inspects all screenshots**

- [ ] **Step 6: Commit**

```bash
git add frontend/tests/playwright/
git commit -m "test: Playwright visual tests for Group B review card + modal states"
```
