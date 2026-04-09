# B1a: Expense Receipt Entry — Implementation Plan

> **Status: ✅ COMPLETE — merged to master on 2026-04-09.**
> All 15 tasks implemented, all code review issues (C1-C4, I1-I5) resolved.
> Test totals: 858 backend unit + 133 integration + 9 e2e + 181 frontend ≈ **1181 tests**, zero regressions.
>
> **Code review:** `docs/code-review-set-b1a.md`
> **Known gaps (intentional, deferred):**
> - DB persistence of uploaded_files/voucher_entries rows (models exist, orchestrator doesn't populate)
> - LedgerMapping DB persistence (in-memory only)
> - Frontend DB-mode workspace_id propagation to voucher-action endpoint
> - Sales/Purchase voucher builders (Set B1b/B1c)
> - Bulk upload for bank statements (Set B1d)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload an expense receipt in the chat, AI extracts data via Claude Vision, maps to Tally ledgers, shows a review card, and on approval writes a Payment voucher to Tally.

**Architecture:** Extends existing orchestrator with data entry capability. New modules: `writer.py` (Tally import XML), `document_parser.py` (file → structured data), `ledger_mapper.py` (vendor → ledger). New DB tables: `uploaded_files`, `voucher_entries`, `ledger_mappings`. Frontend: file attach button + `VoucherReviewCard` component.

**Tech Stack:** Python (FastAPI, httpx, xml.etree, Anthropic SDK vision), PostgreSQL (SQLAlchemy, Alembic), React (TypeScript, Tailwind, lucide-react)

**Spec:** `docs/specs/2026-04-04-set-b1-file-upload-tally-write-design.md`
**Exploration results:** `docs/tally-write-exploration.md` — MUST READ before implementing Tasks 1-3.

### Critical Findings from Live Tally Exploration (Task 0 — COMPLETED)

These override any XML examples in the tasks below:

1. **`NAME.LIST` is REQUIRED** for all master operations (create AND delete). Without it, Tally crashes with memory violation.
2. **`PERSISTEDVIEW`** tag is required for Sales/Purchase vouchers (not Payment).
3. **Voucher delete/cancel** uses `TAGNAME="Master ID" TAGVALUE="<LASTVCHID>"` + `DATE` + `VCHTYPE` — NOT `VCHKEY` or `REMOTEID`.
4. **`ACTION="Cancel"`** returns `ALTERED=1` (cancel is internally an alter). Preferred for undo.
5. **`ALLLEDGERENTRIES.LIST`** works for all voucher types (Payment, Sales, Purchase).
6. **GST ledgers** in live company: `INPUT CGST`, `INPUT SGST`, `INPUT IGST`, `OUTPUT CGST`, `OUTPUTSGST`, `OUTPUT IGST` — all under `Duties & Taxes`.
7. **Response fields**: `CREATED`, `ALTERED`, `DELETED`, `ERRORS`, `EXCEPTIONS`, `LASTVCHID`, `LINEERROR`, `CANCELLED`.
8. **`EXCEPTIONS=1`** means silent failure (bad XML format). `ERRORS` + `LINEERROR` means explicit error.

---

## File Structure

### New Files (Backend)
| File | Responsibility |
|------|---------------|
| `backend/tally_bridge/writer.py` | Build import XML for vouchers, ledgers, groups. Parse import responses. |
| `backend/tally_bridge/import_builder.py` | Pure functions: build IMPORTDATA XML envelopes for each entity type. |
| `backend/services/document_parser.py` | Route files by type, extract structured data via Claude Vision or CSV parser. |
| `backend/services/ledger_mapper.py` | 3-tier mapping: stored rules → fuzzy match → AI suggestion. Learning loop. |
| `backend/services/voucher_builder.py` | Convert ExtractedDocument + mappings → Tally voucher XML payload. Dry-run validation. |
| `backend/db/migrations/versions/002_data_entry.py` | Alembic migration for uploaded_files, voucher_entries, ledger_mappings tables. |

### New Files (Frontend)
| File | Responsibility |
|------|---------------|
| `frontend/src/components/VoucherReviewCard.tsx` | Inline review card with editable fields and action buttons. |
| `frontend/src/components/FileAttachButton.tsx` | Paperclip icon, file picker, drag-drop zone. |

### Modified Files
| File | Change |
|------|--------|
| `backend/db/models.py` | Add `UploadedFile`, `VoucherEntry`, `LedgerMapping` ORM models. |
| `backend/config.py` | Add `FILE_STORAGE_PATH`, `FILE_MAX_SIZE_MB`, `TALLY_WRITE_ENABLED`, `TALLY_DRY_RUN`. |
| `backend/api/chat.py` | Add multipart form data handling, file save, pass file_id to orchestrator. |
| `backend/api/models.py` | Add `VoucherReviewData`, `VoucherEntryResponse` models. |
| `backend/agents/orchestrator.py` | Detect file attachment → route to data entry pipeline. |
| `backend/agents/tools.py` | Add write tools: `create_payment_voucher`, `create_ledger`, `create_group`. |
| `backend/tally_bridge/response_parser.py` | Add `parse_import_response()` for Tally write responses. |
| `backend/tally_bridge/mock_handler.py` | Add `handle_import()` for mock write operations. |
| `frontend/src/components/ChatInput.tsx` | Add file attach button, file preview, multipart send. |
| `frontend/src/components/MessageBubble.tsx` | Detect `data.type === "voucher_review"` → render `VoucherReviewCard`. |
| `frontend/src/api/client.ts` | Add `sendChatWithFile()` using FormData. |

### New Test Files
| File | Tests |
|------|-------|
| `tests/unit/test_import_builder.py` | XML generation for vouchers, ledgers, groups. |
| `tests/unit/test_writer.py` | Import response parsing, dry-run validation. |
| `tests/unit/test_document_parser.py` | Vision prompt building, structured extraction, arithmetic validation. |
| `tests/unit/test_ledger_mapper.py` | 3-tier mapping, learning loop, fuzzy matching. |
| `tests/unit/test_voucher_builder.py` | ExtractedDocument → voucher payload conversion, balance check. |
| `tests/integration/test_tally_write.py` | Full write cycle with mock Tally server. |
| `tests/e2e/test_data_entry.py` | End-to-end: file upload → parse → map → review → write. |
| `frontend/src/__tests__/VoucherReviewCard.test.tsx` | Review card rendering, edit, approve, discard actions. |
| `frontend/src/__tests__/FileAttachButton.test.tsx` | File selection, drag-drop, preview. |

---

## Task 0: Tally Write Exploration (Live Tally) — COMPLETED

> **Status:** DONE. Results documented in `docs/tally-write-exploration.md`.
> The code block below is the ORIGINAL pre-exploration script. For the ACTUAL verified scripts, see:
> - `scripts/explore_tally_write.py` — v1 (initial attempt, discovered NAME.LIST requirement)
> - `scripts/explore_tally_write_v2.py` — v2 (format testing, verified ledger + payment creation)
> - `scripts/explore_tally_write_v3.py` — v3 (sales, purchase, cancel, delete verification)
> - `scripts/cleanup_tally_test.py` — cleanup utility for test entities
>
> **Do NOT use the code block below** — it contains pre-exploration XML formats that crash Tally. Refer to the scripts above and `docs/tally-write-exploration.md` for correct formats.

<details>
<summary>Original pre-exploration script (STALE — click to expand)</summary>

**Files:**
- Create: `scripts/explore_tally_write.py`
- Create: `docs/tally-write-exploration.md`

- [x] **Step 1: Write exploration script**

```python
"""Explore Tally write operations against live instance.

Usage:
    PYTHONPATH=. python scripts/explore_tally_write.py --host 172.26.104.48 --port 9000
"""
import argparse
import asyncio
import xml.etree.ElementTree as ET

from backend.tally_bridge.client import TallyClient


def build_create_ledger_xml(name: str, parent: str, company: str) -> str:
    return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<LEDGER NAME="{name}" ACTION="Create">
<PARENT>{parent}</PARENT>
</LEDGER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


def build_create_payment_xml(
    date: str, debit_ledger: str, credit_ledger: str,
    amount: float, narration: str, company: str,
) -> str:
    return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>{date}</DATE>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{debit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{credit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


def build_delete_voucher_xml(
    date: str, voucher_type: str, voucher_number: str, company: str,
) -> str:
    return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER VCHTYPE="{voucher_type}" ACTION="Delete" VCHKEY="{voucher_number}">
<DATE>{date}</DATE>
</VOUCHER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


def build_delete_ledger_xml(name: str, company: str) -> str:
    return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<LEDGER NAME="{name}" ACTION="Delete"/>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


async def run_exploration(host: str, port: int):
    client = TallyClient(host=host, port=port)
    company = "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED"

    print("=" * 60)
    print("TALLY WRITE EXPLORATION")
    print("=" * 60)

    # 1. Create a test ledger
    print("\n--- Test 1: Create Ledger ---")
    xml = build_create_ledger_xml("_Test Expense Ledger", "Indirect Expenses", company)
    resp = await client.post_xml(xml)
    print(f"Response:\n{resp}")

    # 2. Create a payment voucher using the test ledger
    print("\n--- Test 2: Create Payment Voucher ---")
    xml = build_create_payment_xml(
        date="20260404",
        debit_ledger="_Test Expense Ledger",
        credit_ledger="Cash",
        amount=500.00,
        narration="Test expense - exploration script",
        company=company,
    )
    resp = await client.post_xml(xml)
    print(f"Response:\n{resp}")

    # 3. Verify by fetching day book
    print("\n--- Test 3: Verify via Day Book ---")
    from backend.tally_bridge.request_builder import build_day_book
    xml = build_day_book("04-04-2026", "04-04-2026", company=company)
    resp = await client.post_xml(xml)
    root = ET.fromstring(resp)
    for v in root.iter("VOUCHER"):
        narration = v.findtext("NARRATION", "")
        if "Test expense" in narration:
            vnum = v.findtext("VOUCHERNUMBER", "")
            print(f"Found test voucher: {vnum} — {narration}")

    # 4. Delete the test voucher (cleanup)
    print("\n--- Test 4: Delete Voucher (cleanup) ---")
    # Note: we need the voucher number from step 3
    # For now, print instructions
    print("TODO: Parse voucher number from step 3, delete it")

    # 5. Delete the test ledger (cleanup)
    print("\n--- Test 5: Delete Ledger (cleanup) ---")
    xml = build_delete_ledger_xml("_Test Expense Ledger", company)
    resp = await client.post_xml(xml)
    print(f"Response:\n{resp}")

    # 6. Inspect existing voucher patterns
    print("\n--- Test 6: Sample existing Payment vouchers ---")
    from backend.tally_bridge.request_builder import build_day_book
    xml = build_day_book("01-04-2025", "04-04-2026", voucher_type="Payment", company=company)
    resp = await client.post_xml(xml)
    from backend.tally_bridge.response_parser import parse_vouchers
    vouchers = parse_vouchers(resp)
    for v in vouchers[:3]:
        print(f"  {v['date']} | {v['voucher_type']} | {v['narration']}")
        for le in v.get("ledger_entries", []):
            print(f"    {le['ledger_name']}: {le['amount']}")

    # 7. Inspect GST ledger structure
    print("\n--- Test 7: GST Ledger Detection ---")
    from backend.tally_bridge.request_builder import build_list_ledgers
    xml = build_list_ledgers(company=company)
    resp = await client.post_xml(xml)
    from backend.tally_bridge.response_parser import parse_ledger_list
    ledgers = parse_ledger_list(resp)
    gst_ledgers = [l for l in ledgers if any(k in l["name"].upper() for k in ["GST", "CGST", "SGST", "IGST", "TAX"])]
    print(f"GST-related ledgers ({len(gst_ledgers)}):")
    for l in gst_ledgers:
        print(f"  {l['name']} (under {l['parent_group']})")

    # 8. Inspect group hierarchy
    print("\n--- Test 8: Account Group Hierarchy ---")
    from backend.tally_bridge.request_builder import build_list_groups
    xml = build_list_groups(company=company)
    resp = await client.post_xml(xml)
    from backend.tally_bridge.response_parser import parse_groups
    groups = parse_groups(resp)
    print(f"Total groups: {len(groups)}")
    for g in groups:
        print(f"  {g['name']} → parent: {g['parent']}")

    await client.close()
    print("\n" + "=" * 60)
    print("EXPLORATION COMPLETE — document results in docs/tally-write-exploration.md")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="172.26.104.48")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    asyncio.run(run_exploration(args.host, args.port))
```

- [ ] **Step 2: Run against live Tally**

Run: `PYTHONPATH=. python scripts/explore_tally_write.py --host 172.26.104.48 --port 9000 2>&1 | tee docs/tally-write-exploration.log`

**Capture:**
- Exact XML response format for successful creates (CREATED count? voucher number returned?)
- Error response format for invalid data (missing ledger, bad date, etc.)
- Delete response format
- GST ledger organization in the live company
- Existing payment voucher patterns (ledger entry structure)
- Group hierarchy

- [ ] **Step 3: Document results**

Write `docs/tally-write-exploration.md` with:
- Working XML templates (verified against live Tally)
- Response formats (success + error)
- GST structure findings
- Any date format differences (YYYYMMDD in import vs DD-MM-YYYY in queries)
- Voucher number handling (auto-generated vs specified)

- [ ] **Step 4: Commit**

```bash
git add scripts/explore_tally_write.py docs/tally-write-exploration.md docs/tally-write-exploration.log
git commit -m "explore: test Tally write operations against live instance"
```

</details>

---

## Task 1: Import XML Builder

**Files:**
- Create: `backend/tally_bridge/import_builder.py`
- Create: `tests/unit/test_import_builder.py`

- [ ] **Step 1: Write failing tests for import XML generation**

```python
"""Tests for Tally import XML builder — vouchers, ledgers, groups.

IMPORTANT: XML formats verified against live Tally in docs/tally-write-exploration.md.
Key requirements: NAME.LIST for masters, TAGNAME/TAGVALUE for voucher delete/cancel.
"""
import xml.etree.ElementTree as ET

from backend.tally_bridge.import_builder import (
    build_create_group,
    build_create_ledger,
    build_create_payment_voucher,
    build_cancel_voucher,
    build_delete_ledger,
    build_delete_group,
    build_delete_voucher,
)


def _parse(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


class TestCreatePaymentVoucher:
    def test_basic_payment_structure(self):
        xml = build_create_payment_voucher(
            date="20260404",
            debit_ledger="Travel Expenses",
            credit_ledger="Cash",
            amount=500.00,
            narration="Uber ride",
            company="Test Co",
        )
        root = _parse(xml)
        assert root.findtext(".//TALLYREQUEST") == "Import Data"
        assert root.findtext(".//REPORTNAME") == "Vouchers"
        assert root.findtext(".//SVCURRENTCOMPANY") == "Test Co"

        voucher = root.find(".//VOUCHER")
        assert voucher is not None
        assert voucher.get("VCHTYPE") == "Payment"
        assert voucher.get("ACTION") == "Create"
        assert voucher.findtext("DATE") == "20260404"
        assert voucher.findtext("NARRATION") == "Uber ride"

    def test_ledger_entries_balance(self):
        xml = build_create_payment_voucher(
            date="20260404",
            debit_ledger="Travel Expenses",
            credit_ledger="Cash",
            amount=500.00,
            narration="Test",
            company="Test Co",
        )
        root = _parse(xml)
        entries = root.findall(".//ALLLEDGERENTRIES.LIST")
        assert len(entries) == 2

        # Debit entry (expense): negative amount, ISDEEMEDPOSITIVE=Yes
        debit = entries[0]
        assert debit.findtext("LEDGERNAME") == "Travel Expenses"
        assert debit.findtext("ISDEEMEDPOSITIVE") == "Yes"
        assert float(debit.findtext("AMOUNT")) == -500.00

        # Credit entry (cash): positive amount, ISDEEMEDPOSITIVE=No
        credit = entries[1]
        assert credit.findtext("LEDGERNAME") == "Cash"
        assert credit.findtext("ISDEEMEDPOSITIVE") == "No"
        assert float(credit.findtext("AMOUNT")) == 500.00

    def test_payment_with_gst_entries(self):
        xml = build_create_payment_voucher(
            date="20260404",
            debit_ledger="Office Supplies",
            credit_ledger="Cash",
            amount=1180.00,
            narration="Stationery with GST",
            company="Test Co",
            gst_entries=[
                {"ledger": "CGST Input 9%", "amount": 90.00},
                {"ledger": "SGST Input 9%", "amount": 90.00},
            ],
        )
        root = _parse(xml)
        entries = root.findall(".//ALLLEDGERENTRIES.LIST")
        # 1 debit (expense base: 1000) + 2 GST + 1 credit (cash: 1180)
        assert len(entries) == 4

        # Verify amounts balance: sum of all amounts should be 0
        total = sum(float(e.findtext("AMOUNT")) for e in entries)
        assert abs(total) < 0.01


class TestCreateLedger:
    def test_basic_ledger(self):
        xml = build_create_ledger(
            name="Uber",
            parent="Indirect Expenses",
            company="Test Co",
        )
        root = _parse(xml)
        assert root.findtext(".//REPORTNAME") == "All Masters"
        ledger = root.find(".//LEDGER")
        assert ledger is not None
        assert ledger.get("NAME") == "Uber"
        assert ledger.get("ACTION") == "Create"
        assert ledger.findtext("PARENT") == "Indirect Expenses"

    def test_ledger_has_name_list(self):
        """NAME.LIST is REQUIRED — without it Tally crashes with memory violation."""
        xml = build_create_ledger(name="Test", parent="Indirect Expenses", company="Test Co")
        root = _parse(xml)
        ledger = root.find(".//LEDGER")
        name_list = ledger.find("NAME.LIST")
        assert name_list is not None
        assert name_list.findtext("NAME") == "Test"

    def test_ledger_with_gstin(self):
        xml = build_create_ledger(
            name="Supplier ABC",
            parent="Sundry Creditors",
            company="Test Co",
            gstin="29XXXXX1234Z",
        )
        root = _parse(xml)
        ledger = root.find(".//LEDGER")
        assert ledger.findtext("PARTYGSTIN") == "29XXXXX1234Z"


class TestCreateGroup:
    def test_basic_group(self):
        xml = build_create_group(
            name="SaaS Subscriptions",
            parent="Indirect Expenses",
            company="Test Co",
        )
        root = _parse(xml)
        group = root.find(".//GROUP")
        assert group is not None
        assert group.get("NAME") == "SaaS Subscriptions"
        assert group.get("ACTION") == "Create"
        assert group.findtext("PARENT") == "Indirect Expenses"

    def test_group_has_name_list(self):
        """NAME.LIST is REQUIRED for group operations too."""
        xml = build_create_group(name="Test Group", parent="Indirect Expenses", company="Test Co")
        root = _parse(xml)
        group = root.find(".//GROUP")
        name_list = group.find("NAME.LIST")
        assert name_list is not None
        assert name_list.findtext("NAME") == "Test Group"


class TestDeleteOperations:
    def test_delete_voucher_uses_tagname(self):
        """Voucher delete uses TAGNAME='Master ID' + TAGVALUE (not VCHKEY)."""
        xml = build_delete_voucher(
            voucher_type="Payment",
            master_id="301",
            date="20260405",
            company="Test Co",
        )
        root = _parse(xml)
        voucher = root.find(".//VOUCHER")
        assert voucher.get("ACTION") == "Delete"
        assert voucher.get("VCHTYPE") == "Payment"
        assert voucher.get("TAGNAME") == "Master ID"
        assert voucher.get("TAGVALUE") == "301"
        assert voucher.get("DATE") == "20260405"

    def test_cancel_voucher(self):
        """Cancel sets ACTION='Cancel', returns ALTERED=1 from Tally."""
        xml = build_cancel_voucher(
            voucher_type="Payment",
            master_id="301",
            date="20260405",
            company="Test Co",
            narration="Cancelled by user",
        )
        root = _parse(xml)
        voucher = root.find(".//VOUCHER")
        assert voucher.get("ACTION") == "Cancel"
        assert voucher.get("TAGNAME") == "Master ID"
        assert voucher.findtext("NARRATION") == "Cancelled by user"

    def test_delete_ledger_has_name_list(self):
        """Ledger delete REQUIRES NAME.LIST — without it Tally crashes."""
        xml = build_delete_ledger(name="Old Ledger", company="Test Co")
        root = _parse(xml)
        ledger = root.find(".//LEDGER")
        assert ledger.get("ACTION") == "Delete"
        assert ledger.get("NAME") == "Old Ledger"
        name_list = ledger.find("NAME.LIST")
        assert name_list is not None

    def test_delete_group_has_name_list(self):
        xml = build_delete_group(name="Old Group", company="Test Co")
        root = _parse(xml)
        group = root.find(".//GROUP")
        assert group.get("ACTION") == "Delete"
        name_list = group.find("NAME.LIST")
        assert name_list is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_import_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.tally_bridge.import_builder'`

- [ ] **Step 3: Implement import_builder.py**

```python
"""Build Tally IMPORTDATA XML payloads for creating/cancelling/deleting vouchers, ledgers, groups.

All functions are pure — no I/O, no side effects. Each returns an XML string.
Tally import date format: YYYYMMDD (different from query format DD-MM-YYYY).

CRITICAL (from live Tally exploration — docs/tally-write-exploration.md):
- NAME.LIST is REQUIRED for all master operations (create AND delete). Without it, Tally crashes.
- Voucher delete/cancel uses TAGNAME="Master ID" + TAGVALUE=LASTVCHID (not VCHKEY).
- PERSISTEDVIEW is required for Sales/Purchase vouchers.
"""


def _wrap_import(report_name: str, company: str, inner_xml: str) -> str:
    """Wrap entity XML in the standard IMPORTDATA envelope."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>{report_name}</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
{inner_xml}
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>"""


def build_create_payment_voucher(
    date: str,
    debit_ledger: str,
    credit_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
) -> str:
    """Build XML to create a Payment voucher in Tally.

    Args:
        date: YYYYMMDD format.
        debit_ledger: Expense ledger name (e.g., "Travel Expenses").
        credit_ledger: Cash/Bank ledger name (e.g., "Cash").
        amount: Total payment amount (positive number).
        narration: Description of the expense.
        company: Tally company name.
        gst_entries: Optional list of {"ledger": str, "amount": float} for GST components.
    """
    gst_total = sum(e["amount"] for e in (gst_entries or []))
    base_amount = amount - gst_total

    entries = []
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{debit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{base_amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )
    for gst in gst_entries or []:
        entries.append(
            f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{gst["ledger"]}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{gst["amount"]:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
        )
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{credit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )

    entries_xml = "\n".join(entries)
    voucher_xml = f"""<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>{date}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<NARRATION>{narration}</NARRATION>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
{entries_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_create_ledger(
    name: str,
    parent: str,
    company: str,
    gstin: str | None = None,
) -> str:
    """Build XML to create a ledger master in Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    gstin_xml = f"\n<PARTYGSTIN>{gstin}</PARTYGSTIN>" if gstin else ""
    ledger_xml = f"""<LEDGER NAME="{name}" ACTION="Create">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
<PARENT>{parent}</PARENT>{gstin_xml}
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_create_group(name: str, parent: str, company: str) -> str:
    """Build XML to create an account group in Tally."""
    group_xml = f"""<GROUP NAME="{name}" ACTION="Create">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
<PARENT>{parent}</PARENT>
</GROUP>"""
    return _wrap_import("All Masters", company, group_xml)


def build_delete_voucher(
    voucher_type: str,
    master_id: str,
    date: str,
    company: str,
) -> str:
    """Build XML to delete a voucher from Tally.

    Uses TAGNAME="Master ID" + TAGVALUE (the LASTVCHID from creation response).
    """
    voucher_xml = f"""<VOUCHER DATE="{date}" TAGNAME="Master ID" TAGVALUE="{master_id}" VCHTYPE="{voucher_type}" ACTION="Delete">
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_cancel_voucher(
    voucher_type: str,
    master_id: str,
    date: str,
    company: str,
    narration: str = "",
) -> str:
    """Build XML to cancel a voucher in Tally (preserves audit trail).

    Cancel returns ALTERED=1 from Tally (cancel is internally an alter).
    Preferred over delete for undo operations.
    """
    narration_xml = f"\n<NARRATION>{narration}</NARRATION>" if narration else ""
    voucher_xml = f"""<VOUCHER DATE="{date}" TAGNAME="Master ID" TAGVALUE="{master_id}" VCHTYPE="{voucher_type}" ACTION="Cancel">{narration_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_delete_ledger(name: str, company: str) -> str:
    """Build XML to delete a ledger master from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    ledger_xml = f"""<LEDGER NAME="{name}" ACTION="Delete">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_delete_group(name: str, company: str) -> str:
    """Build XML to delete an account group from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    group_xml = f"""<GROUP NAME="{name}" ACTION="Delete">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
</GROUP>"""
    return _wrap_import("All Masters", company, group_xml)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_import_builder.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/import_builder.py tests/unit/test_import_builder.py
git commit -m "feat(B1a): add Tally import XML builder for vouchers, ledgers, groups"
```

---

## Task 2: Import Response Parser

**Files:**
- Modify: `backend/tally_bridge/response_parser.py`
- Create: `tests/unit/test_import_response.py`

- [ ] **Step 1: Write failing tests for import response parsing**

```python
"""Tests for Tally import response parsing."""
from backend.tally_bridge.response_parser import parse_import_response


class TestParseImportResponse:
    def test_successful_create(self):
        xml = """<RESPONSE>
<CREATED>1</CREATED>
<ALTERED>0</ALTERED>
<DELETED>0</DELETED>
<LASTVCHID>12345</LASTVCHID>
<LASTMID>67890</LASTMID>
<COMBINED>0</COMBINED>
<IGNORED>0</IGNORED>
<ERRORS>0</ERRORS>
</RESPONSE>"""
        result = parse_import_response(xml)
        assert result["success"] is True
        assert result["created"] == 1
        assert result["errors"] == 0
        assert result["last_vch_id"] == "12345"

    def test_error_response(self):
        xml = """<RESPONSE>
<CREATED>0</CREATED>
<ALTERED>0</ALTERED>
<DELETED>0</DELETED>
<LASTVCHID>0</LASTVCHID>
<LASTMID>0</LASTMID>
<COMBINED>0</COMBINED>
<IGNORED>0</IGNORED>
<ERRORS>1</ERRORS>
<LINEERROR>Ledger "Nonexistent" not found</LINEERROR>
</RESPONSE>"""
        result = parse_import_response(xml)
        assert result["success"] is False
        assert result["errors"] == 1
        assert "not found" in result["error_message"]

    def test_successful_delete(self):
        xml = """<RESPONSE>
<CREATED>0</CREATED>
<ALTERED>0</ALTERED>
<DELETED>1</DELETED>
<LASTVCHID>0</LASTVCHID>
<LASTMID>0</LASTMID>
<COMBINED>0</COMBINED>
<IGNORED>0</IGNORED>
<ERRORS>0</ERRORS>
</RESPONSE>"""
        result = parse_import_response(xml)
        assert result["success"] is True
        assert result["deleted"] == 1

    def test_malformed_xml(self):
        result = parse_import_response("<not valid xml>>>")
        assert result["success"] is False
        assert "parse" in result["error_message"].lower() or "invalid" in result["error_message"].lower()

    def test_empty_response(self):
        result = parse_import_response("")
        assert result["success"] is False

    def test_exceptions_response(self):
        """EXCEPTIONS=1 means silent failure (e.g., missing NAME.LIST in master XML)."""
        xml = """<RESPONSE>
<CREATED>0</CREATED>
<ALTERED>0</ALTERED>
<DELETED>0</DELETED>
<LASTVCHID>0</LASTVCHID>
<LASTMID>0</LASTMID>
<COMBINED>0</COMBINED>
<IGNORED>0</IGNORED>
<ERRORS>0</ERRORS>
<CANCELLED>0</CANCELLED>
<EXCEPTIONS>1</EXCEPTIONS>
</RESPONSE>"""
        result = parse_import_response(xml)
        assert result["success"] is False
        assert result["exceptions"] == 1
        assert "exception" in result["error_message"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_import_response.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_import_response'`

- [ ] **Step 3: Add parse_import_response to response_parser.py**

Add at the end of `backend/tally_bridge/response_parser.py` (after `parse_cash_flow`):

```python
def parse_import_response(raw_xml: str) -> dict:
    """Parse Tally's IMPORTDATA response.

    Returns:
        {
            "success": bool,
            "created": int,
            "altered": int,
            "deleted": int,
            "errors": int,
            "last_vch_id": str | None,
            "error_message": str | None,
        }
    """
    if not raw_xml or not raw_xml.strip():
        return {"success": False, "error_message": "Empty response from Tally",
                "created": 0, "altered": 0, "deleted": 0, "errors": 0, "last_vch_id": None}
    try:
        root = ET.fromstring(sanitize_xml(raw_xml))
    except ET.ParseError:
        return {"success": False, "error_message": "Invalid XML in Tally response",
                "created": 0, "altered": 0, "deleted": 0, "errors": 0, "last_vch_id": None}

    def _find_int(tag: str) -> int:
        el = root.find(tag)
        if el is None:
            el = root.find(f".//{tag}")
        return int(el.text.strip()) if el is not None and el.text else 0

    created = _find_int("CREATED")
    altered = _find_int("ALTERED")
    deleted = _find_int("DELETED")
    errors = _find_int("ERRORS")
    exceptions = _find_int("EXCEPTIONS")
    last_vch_id = root.findtext("LASTVCHID") or root.findtext(".//LASTVCHID")
    if last_vch_id == "0":
        last_vch_id = None

    error_message = None
    if errors > 0:
        line_error = root.findtext("LINEERROR") or root.findtext(".//LINEERROR")
        error_message = line_error or f"Tally reported {errors} error(s)"
    elif exceptions > 0:
        error_message = f"Tally reported {exceptions} exception(s) — likely malformed XML"

    success = errors == 0 and exceptions == 0 and (created > 0 or altered > 0 or deleted > 0)
    return {
        "success": success,
        "created": created,
        "altered": altered,
        "deleted": deleted,
        "errors": errors,
        "exceptions": exceptions,
        "last_vch_id": last_vch_id,
        "error_message": error_message,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_import_response.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/response_parser.py tests/unit/test_import_response.py
git commit -m "feat(B1a): add Tally import response parser"
```

---

## Task 3: Tally Writer Module

**Files:**
- Create: `backend/tally_bridge/writer.py`
- Create: `tests/unit/test_writer.py`

- [ ] **Step 1: Write failing tests for writer (dry-run validation + write orchestration)**

```python
"""Tests for Tally writer — validation and write orchestration."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.tally_bridge.writer import TallyWriter, ValidationError


class TestDryRunValidation:
    def test_valid_payment_passes(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test expense",
            "ledger_entries": [
                {"ledger": "Travel Expenses", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel Expenses", "Cash"])
        assert errors == []

    def test_unbalanced_amounts_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Bad entry",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 400.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("balance" in e.lower() for e in errors)

    def test_unknown_ledger_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Unknown Ledger", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Cash"])
        assert any("Unknown Ledger" in e for e in errors)

    def test_missing_narration_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("narration" in e.lower() for e in errors)

    def test_fewer_than_two_entries_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "20260404",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel"])
        assert any("two" in e.lower() or "entries" in e.lower() for e in errors)

    def test_missing_date_fails(self):
        writer = TallyWriter.__new__(TallyWriter)
        voucher = {
            "voucher_type": "Payment",
            "date": "",
            "narration": "Test",
            "ledger_entries": [
                {"ledger": "Travel", "amount": -500.00, "is_debit": True},
                {"ledger": "Cash", "amount": 500.00, "is_debit": False},
            ],
        }
        errors = writer.validate_voucher(voucher, known_ledgers=["Travel", "Cash"])
        assert any("date" in e.lower() for e in errors)


class TestWriteVoucher:
    @pytest.mark.asyncio
    async def test_successful_write(self):
        mock_client = AsyncMock()
        mock_client.post_xml.return_value = """<RESPONSE>
<CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
<LASTVCHID>12345</LASTVCHID><LASTMID>0</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
</RESPONSE>"""
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_payment_voucher(
            date="20260404",
            debit_ledger="Travel Expenses",
            credit_ledger="Cash",
            amount=500.00,
            narration="Test",
        )
        assert result["success"] is True
        assert result["created"] == 1
        mock_client.post_xml.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_with_validation_error(self):
        mock_client = AsyncMock()
        writer = TallyWriter(client=mock_client, company="Test Co")
        # Unknown ledger should fail validation before calling Tally
        with pytest.raises(ValidationError, match="not found"):
            await writer.create_payment_voucher(
                date="20260404",
                debit_ledger="Nonexistent",
                credit_ledger="Cash",
                amount=500.00,
                narration="Test",
                known_ledgers=["Cash"],
            )
        mock_client.post_xml.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.tally_bridge.writer'`

- [ ] **Step 3: Implement writer.py**

```python
"""Tally write operations — validates and submits import XML.

Wraps import_builder (XML generation) and response_parser (response parsing)
with validation and error handling.
"""
from __future__ import annotations

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.import_builder import (
    build_cancel_voucher,
    build_create_group,
    build_create_ledger,
    build_create_payment_voucher,
    build_delete_group,
    build_delete_ledger,
    build_delete_voucher,
)
from backend.tally_bridge.response_parser import parse_import_response


class ValidationError(Exception):
    """Raised when voucher data fails dry-run validation."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


class TallyWriter:
    """Validates and writes vouchers/masters to Tally."""

    def __init__(self, client: TallyClient, company: str):
        self.client = client
        self.company = company

    def validate_voucher(
        self, voucher: dict, known_ledgers: list[str] | None = None,
    ) -> list[str]:
        """Dry-run validation. Returns list of error strings (empty = valid)."""
        errors = []

        if not voucher.get("date"):
            errors.append("Date is required")

        if not voucher.get("narration", "").strip():
            errors.append("Narration is required")

        entries = voucher.get("ledger_entries", [])
        if len(entries) < 2:
            errors.append("At least two ledger entries required")

        # Balance check
        total = sum(e["amount"] for e in entries)
        if abs(total) > 0.01:
            errors.append(f"Ledger entries do not balance (sum={total:.2f})")

        # Ledger existence check
        if known_ledgers is not None:
            known_set = {l.lower() for l in known_ledgers}
            for e in entries:
                if e["ledger"].lower() not in known_set:
                    errors.append(f"Ledger \"{e['ledger']}\" not found in Tally")

        return errors

    async def create_payment_voucher(
        self,
        date: str,
        debit_ledger: str,
        credit_ledger: str,
        amount: float,
        narration: str,
        gst_entries: list[dict] | None = None,
        known_ledgers: list[str] | None = None,
    ) -> dict:
        """Create a Payment voucher in Tally with validation."""
        # Build voucher dict for validation
        gst_total = sum(e["amount"] for e in (gst_entries or []))
        base_amount = amount - gst_total
        entries = [
            {"ledger": debit_ledger, "amount": -base_amount, "is_debit": True},
        ]
        for gst in gst_entries or []:
            entries.append({"ledger": gst["ledger"], "amount": -gst["amount"], "is_debit": True})
        entries.append({"ledger": credit_ledger, "amount": amount, "is_debit": False})

        voucher = {
            "voucher_type": "Payment",
            "date": date,
            "narration": narration,
            "ledger_entries": entries,
        }
        errors = self.validate_voucher(voucher, known_ledgers)
        if errors:
            raise ValidationError(errors)

        xml = build_create_payment_voucher(
            date=date,
            debit_ledger=debit_ledger,
            credit_ledger=credit_ledger,
            amount=amount,
            narration=narration,
            company=self.company,
            gst_entries=gst_entries,
        )
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_ledger(
        self, name: str, parent: str, gstin: str | None = None,
    ) -> dict:
        """Create a ledger master in Tally."""
        xml = build_create_ledger(name, parent, self.company, gstin)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def create_group(self, name: str, parent: str) -> dict:
        """Create an account group in Tally."""
        xml = build_create_group(name, parent, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def cancel_voucher(
        self, voucher_type: str, master_id: str, date: str, narration: str = "",
    ) -> dict:
        """Cancel a voucher in Tally (preferred for undo — preserves audit trail)."""
        xml = build_cancel_voucher(voucher_type, master_id, date, self.company, narration)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_voucher(self, voucher_type: str, master_id: str, date: str) -> dict:
        """Delete a voucher from Tally."""
        xml = build_delete_voucher(voucher_type, master_id, date, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_ledger(self, name: str) -> dict:
        """Delete a ledger master from Tally."""
        xml = build_delete_ledger(name, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)

    async def delete_group(self, name: str) -> dict:
        """Delete an account group from Tally."""
        xml = build_delete_group(name, self.company)
        response_xml = await self.client.post_xml(xml)
        return parse_import_response(response_xml)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_writer.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/writer.py tests/unit/test_writer.py
git commit -m "feat(B1a): add Tally writer with dry-run validation"
```

---

## Task 4: Database Schema — New Tables

**Files:**
- Modify: `backend/db/models.py`
- Create: `backend/db/migrations/versions/002_data_entry.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Add new ORM models to backend/db/models.py**

Add after the `UsageLog` class (line 94):

```python
class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int]
    storage_path: Mapped[str] = mapped_column(String(500))
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VoucherEntry(Base):
    __tablename__ = "voucher_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploaded_files.id"), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    voucher_type: Mapped[str] = mapped_column(String(30))
    voucher_data: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    tally_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tally_voucher_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow,
    )


class LedgerMapping(Base):
    __tablename__ = "ledger_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    vendor_pattern: Mapped[str] = mapped_column(String(255))
    ledger_name: Mapped[str] = mapped_column(String(255))
    voucher_type: Mapped[str] = mapped_column(String(30))
    gst_treatment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.8)
    use_count: Mapped[int] = mapped_column(default=0)
    created_from: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Add new config settings to backend/config.py**

Add after existing settings (before `db_mode` property):

```python
    # File upload
    FILE_STORAGE_PATH: str = "./uploads"
    FILE_MAX_SIZE_MB: int = 10

    # Tally write
    TALLY_WRITE_ENABLED: bool = True
    TALLY_DRY_RUN: bool = False
```

- [ ] **Step 3: Create Alembic migration**

Run: `DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent PYTHONPATH=. python -m alembic revision --autogenerate -m "add data entry tables"`

Verify the generated migration creates `uploaded_files`, `voucher_entries`, and `ledger_mappings` tables with correct columns, FKs, and indexes. Edit if needed.

- [ ] **Step 4: Run migration against test DB**

Run: `DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent_test PYTHONPATH=. python -m alembic upgrade head`
Expected: Migration applies cleanly

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py backend/config.py backend/db/migrations/versions/002_data_entry.py
git commit -m "feat(B1a): add DB models and migration for uploaded_files, voucher_entries, ledger_mappings"
```

---

## Task 5: Document Parser — Claude Vision Extraction

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/document_parser.py`
- Create: `tests/unit/test_document_parser.py`

- [ ] **Step 1: Create services package**

```bash
touch backend/services/__init__.py
```

- [ ] **Step 2: Write failing tests**

```python
"""Tests for document parser — file routing, extraction, validation."""
import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.document_parser import (
    ExtractedDocument,
    GSTBreakdown,
    LineItem,
    detect_file_type,
    validate_extracted_amounts,
    build_vision_prompt,
    parse_vision_response,
)


class TestFileTypeDetection:
    def test_csv(self):
        assert detect_file_type("statement.csv", "text/csv") == "structured"

    def test_xlsx(self):
        assert detect_file_type("report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "structured"

    def test_jpg(self):
        assert detect_file_type("receipt.jpg", "image/jpeg") == "vision"

    def test_png(self):
        assert detect_file_type("receipt.png", "image/png") == "vision"

    def test_pdf(self):
        assert detect_file_type("invoice.pdf", "application/pdf") == "vision"

    def test_unknown(self):
        assert detect_file_type("doc.docx", "application/msword") == "unsupported"


class TestVisionPrompt:
    def test_prompt_includes_instructions(self):
        prompt = build_vision_prompt()
        assert "vendor" in prompt.lower()
        assert "amount" in prompt.lower()
        assert "date" in prompt.lower()
        assert "json" in prompt.lower()
        assert "GST" in prompt or "gst" in prompt


class TestParseVisionResponse:
    def test_basic_expense(self):
        response_json = json.dumps({
            "doc_type": "expense",
            "vendor_name": "Uber",
            "date": "2026-04-04",
            "total_amount": 500.00,
            "line_items": [{"description": "Ride", "amount": 500.00}],
            "gst": None,
            "payment_mode": "upi",
        })
        doc = parse_vision_response(response_json)
        assert doc.vendor_name == "Uber"
        assert doc.total_amount == Decimal("500.00")
        assert doc.doc_type == "expense"
        assert len(doc.line_items) == 1

    def test_expense_with_gst(self):
        response_json = json.dumps({
            "doc_type": "expense",
            "vendor_name": "Stationery Shop",
            "date": "2026-04-04",
            "total_amount": 1180.00,
            "line_items": [{"description": "Paper and pens", "amount": 1000.00}],
            "gst": {
                "cgst_rate": 9.0, "cgst_amount": 90.0,
                "sgst_rate": 9.0, "sgst_amount": 90.0,
            },
            "payment_mode": "cash",
        })
        doc = parse_vision_response(response_json)
        assert doc.gst is not None
        assert doc.gst.cgst_amount == Decimal("90.00")


class TestAmountValidation:
    def test_valid_amounts(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("1180.00"),
            line_items=[LineItem(description="Item", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
        )
        warnings = validate_extracted_amounts(doc)
        assert warnings == []

    def test_mismatched_total(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("1500.00"),  # Wrong total
            line_items=[LineItem(description="Item", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
        )
        warnings = validate_extracted_amounts(doc)
        assert len(warnings) > 0
        assert any("total" in w.lower() or "sum" in w.lower() for w in warnings)

    def test_zero_amount_warning(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("0"),
            line_items=[LineItem(description="Free item", amount=Decimal("0"))],
        )
        warnings = validate_extracted_amounts(doc)
        assert any("zero" in w.lower() for w in warnings)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_document_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.document_parser'`

- [ ] **Step 4: Implement document_parser.py**

```python
"""Parse uploaded documents into structured ExtractedDocument data.

Routes by file type: CSV/Excel → structured parser, images/PDF → Claude Vision.
Post-extraction arithmetic validation in Python (no LLM math).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass
class LineItem:
    description: str
    amount: Decimal
    quantity: Decimal | None = None
    rate: Decimal | None = None
    gst_rate: Decimal | None = None
    gst_amount: Decimal | None = None


@dataclass
class GSTBreakdown:
    cgst_rate: Decimal | None = None
    cgst_amount: Decimal | None = None
    sgst_rate: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_rate: Decimal | None = None
    igst_amount: Decimal | None = None
    gstin: str | None = None


@dataclass
class ExtractedDocument:
    doc_type: str
    vendor_name: str | None
    date: str
    total_amount: Decimal
    line_items: list[LineItem] = field(default_factory=list)
    gst: GSTBreakdown | None = None
    payment_mode: str | None = None
    raw_text: str | None = None
    confidence: float = 0.0
    currency: str = "INR"


_STRUCTURED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ofx"}
_VISION_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".pdf"}


def detect_file_type(filename: str, mime_type: str) -> str:
    """Determine parsing strategy from filename/MIME type.

    Returns: "structured", "vision", or "unsupported".
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _STRUCTURED_EXTENSIONS:
        return "structured"
    if ext in _VISION_EXTENSIONS:
        return "vision"
    return "unsupported"


def build_vision_prompt() -> str:
    """Build the Claude Vision extraction prompt."""
    return """Analyze this document (expense receipt, invoice, or bill) and extract structured data.

Return ONLY valid JSON with this exact structure:
{
    "doc_type": "expense" | "purchase" | "sale",
    "vendor_name": "string or null",
    "date": "YYYY-MM-DD",
    "total_amount": number,
    "line_items": [
        {
            "description": "string",
            "amount": number,
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
        "gstin": "string or null"
    } or null,
    "payment_mode": "cash" | "bank" | "upi" | "card" | null
}

Rules:
- All amounts in INR as positive numbers.
- Date in YYYY-MM-DD format.
- If GST is not mentioned or not applicable, set gst to null.
- If unsure about a field, set it to null rather than guessing.
- For expenses, doc_type is always "expense".
- Return ONLY the JSON, no markdown formatting or explanation."""


def _to_decimal(value) -> Decimal:
    """Convert a value to Decimal, handling None and string inputs."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def parse_vision_response(response_text: str) -> ExtractedDocument:
    """Parse Claude Vision's JSON response into ExtractedDocument."""
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)

    line_items = []
    for item in data.get("line_items", []):
        line_items.append(LineItem(
            description=item.get("description", ""),
            amount=_to_decimal(item.get("amount")),
            quantity=_to_decimal(item["quantity"]) if item.get("quantity") is not None else None,
            rate=_to_decimal(item["rate"]) if item.get("rate") is not None else None,
            gst_rate=_to_decimal(item["gst_rate"]) if item.get("gst_rate") is not None else None,
            gst_amount=_to_decimal(item["gst_amount"]) if item.get("gst_amount") is not None else None,
        ))

    gst = None
    if data.get("gst"):
        g = data["gst"]
        gst = GSTBreakdown(
            cgst_rate=_to_decimal(g["cgst_rate"]) if g.get("cgst_rate") is not None else None,
            cgst_amount=_to_decimal(g["cgst_amount"]) if g.get("cgst_amount") is not None else None,
            sgst_rate=_to_decimal(g["sgst_rate"]) if g.get("sgst_rate") is not None else None,
            sgst_amount=_to_decimal(g["sgst_amount"]) if g.get("sgst_amount") is not None else None,
            igst_rate=_to_decimal(g["igst_rate"]) if g.get("igst_rate") is not None else None,
            igst_amount=_to_decimal(g["igst_amount"]) if g.get("igst_amount") is not None else None,
            gstin=g.get("gstin"),
        )

    return ExtractedDocument(
        doc_type=data.get("doc_type", "expense"),
        vendor_name=data.get("vendor_name"),
        date=data.get("date", ""),
        total_amount=_to_decimal(data.get("total_amount")),
        line_items=line_items,
        gst=gst,
        payment_mode=data.get("payment_mode"),
        confidence=0.85,
    )


def validate_extracted_amounts(doc: ExtractedDocument) -> list[str]:
    """Post-extraction arithmetic validation. Returns list of warnings."""
    warnings = []

    if doc.total_amount == 0:
        warnings.append("Total amount is zero — please verify")

    # Check line items + GST = total
    items_sum = sum(item.amount for item in doc.line_items)
    gst_sum = Decimal("0")
    if doc.gst:
        gst_sum += doc.gst.cgst_amount or Decimal("0")
        gst_sum += doc.gst.sgst_amount or Decimal("0")
        gst_sum += doc.gst.igst_amount or Decimal("0")

    expected_total = items_sum + gst_sum
    if abs(expected_total - doc.total_amount) > Decimal("1.00"):
        warnings.append(
            f"Line items ({items_sum}) + GST ({gst_sum}) = {expected_total}, "
            f"but document total is {doc.total_amount} — please verify"
        )

    # Check GST rates match amounts (if both present)
    if doc.gst and doc.line_items:
        base = items_sum
        if doc.gst.cgst_rate and doc.gst.cgst_amount:
            expected_cgst = base * doc.gst.cgst_rate / Decimal("100")
            if abs(expected_cgst - doc.gst.cgst_amount) > Decimal("1.00"):
                warnings.append(
                    f"CGST {doc.gst.cgst_rate}% of {base} should be {expected_cgst}, "
                    f"but extracted {doc.gst.cgst_amount}"
                )

    return warnings
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_document_parser.py -v`
Expected: All 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/__init__.py backend/services/document_parser.py tests/unit/test_document_parser.py
git commit -m "feat(B1a): add document parser with Claude Vision extraction and amount validation"
```

---

## Task 6: Ledger Mapper

**Files:**
- Create: `backend/services/ledger_mapper.py`
- Create: `tests/unit/test_ledger_mapper.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for 3-tier ledger mapping: stored rules → fuzzy → AI."""
import pytest
from unittest.mock import AsyncMock

from backend.services.ledger_mapper import LedgerMapper, MappingResult


class TestStoredRuleMapping:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = [
            {"vendor_pattern": "uber", "ledger_name": "Travel Expenses",
             "voucher_type": "Payment", "confidence": 1.0, "use_count": 5},
        ]
        result = await mapper.find_mapping("Uber", "Payment", tally_ledgers=[])
        assert result.ledger_name == "Travel Expenses"
        assert result.source == "stored_rule"
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_no_stored_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        result = await mapper.find_mapping("Unknown Vendor", "Payment", tally_ledgers=["Cash"])
        assert result.source != "stored_rule"


class TestFuzzyMapping:
    @pytest.mark.asyncio
    async def test_fuzzy_ledger_match(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        result = await mapper.find_mapping(
            "Reliance Jio Infocomm Ltd",
            "Payment",
            tally_ledgers=["Reliance Jio", "Cash", "Bank Account"],
        )
        assert result.ledger_name == "Reliance Jio"
        assert result.source == "fuzzy_match"

    @pytest.mark.asyncio
    async def test_no_fuzzy_match_falls_through(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = []
        mapper._ai_suggest = AsyncMock(return_value=MappingResult(
            ledger_name="Office Supplies",
            source="ai_suggestion",
            confidence=0.7,
        ))
        result = await mapper.find_mapping(
            "Random Shop XYZ",
            "Payment",
            tally_ledgers=["Cash", "Bank Account"],
        )
        assert result.source == "ai_suggestion"


class TestLearning:
    def test_store_user_correction(self):
        mapper = LedgerMapper()
        mapper.learn_mapping(
            vendor="Swiggy",
            ledger_name="Staff Welfare",
            voucher_type="Payment",
            source="user_correction",
        )
        assert len(mapper._stored_mappings) == 1
        assert mapper._stored_mappings[0]["vendor_pattern"] == "swiggy"
        assert mapper._stored_mappings[0]["confidence"] == 1.0

    def test_correction_overrides_existing(self):
        mapper = LedgerMapper()
        mapper._stored_mappings = [
            {"vendor_pattern": "swiggy", "ledger_name": "Food Expenses",
             "voucher_type": "Payment", "confidence": 0.8, "use_count": 3},
        ]
        mapper.learn_mapping(
            vendor="Swiggy",
            ledger_name="Staff Welfare",
            voucher_type="Payment",
            source="user_correction",
        )
        assert len(mapper._stored_mappings) == 1
        assert mapper._stored_mappings[0]["ledger_name"] == "Staff Welfare"
        assert mapper._stored_mappings[0]["confidence"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ledger_mapper.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ledger_mapper.py**

```python
"""Three-tier ledger mapping: stored rules → fuzzy match → AI suggestion.

Learns from user corrections to improve over time.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class MappingResult:
    ledger_name: str
    source: str  # "stored_rule", "fuzzy_match", "ai_suggestion"
    confidence: float
    is_new_ledger: bool = False
    suggested_parent: str | None = None


class LedgerMapper:
    """Maps vendor names to Tally ledgers using a 3-tier strategy."""

    def __init__(self):
        self._stored_mappings: list[dict] = []

    async def find_mapping(
        self,
        vendor_name: str,
        voucher_type: str,
        tally_ledgers: list[str],
        tally_groups: list[dict] | None = None,
    ) -> MappingResult:
        """Find the best ledger mapping for a vendor.

        Tries: stored rules → fuzzy match against Tally ledgers → AI suggestion.
        """
        vendor_lower = vendor_name.lower().strip()

        # Tier 1: Stored rules
        for mapping in sorted(self._stored_mappings, key=lambda m: -m["use_count"]):
            if mapping["vendor_pattern"] == vendor_lower and mapping["voucher_type"] == voucher_type:
                return MappingResult(
                    ledger_name=mapping["ledger_name"],
                    source="stored_rule",
                    confidence=mapping["confidence"],
                )

        # Tier 2: Fuzzy match against Tally ledger names
        best_match = None
        best_ratio = 0.0
        for ledger in tally_ledgers:
            ratio = SequenceMatcher(None, vendor_lower, ledger.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = ledger
        if best_match and best_ratio >= 0.6:
            return MappingResult(
                ledger_name=best_match,
                source="fuzzy_match",
                confidence=best_ratio,
            )

        # Tier 3: AI suggestion (delegated to caller or mock)
        return await self._ai_suggest(vendor_name, voucher_type, tally_ledgers, tally_groups)

    async def _ai_suggest(
        self,
        vendor_name: str,
        voucher_type: str,
        tally_ledgers: list[str],
        tally_groups: list[dict] | None = None,
    ) -> MappingResult:
        """Default AI suggestion — returns a generic mapping.

        Override this or inject a real AI client for production use.
        """
        # Default: suggest creating a new ledger under a reasonable parent
        parent = "Indirect Expenses" if voucher_type == "Payment" else "Sundry Creditors"
        return MappingResult(
            ledger_name=vendor_name,
            source="ai_suggestion",
            confidence=0.5,
            is_new_ledger=True,
            suggested_parent=parent,
        )

    def learn_mapping(
        self,
        vendor: str,
        ledger_name: str,
        voucher_type: str,
        source: str = "user_correction",
    ) -> None:
        """Store a mapping from user correction or approved AI suggestion."""
        vendor_lower = vendor.lower().strip()
        confidence = 1.0 if source == "user_correction" else 0.8

        # Update existing or add new
        for mapping in self._stored_mappings:
            if mapping["vendor_pattern"] == vendor_lower and mapping["voucher_type"] == voucher_type:
                mapping["ledger_name"] = ledger_name
                mapping["confidence"] = confidence
                mapping["created_from"] = source
                return

        self._stored_mappings.append({
            "vendor_pattern": vendor_lower,
            "ledger_name": ledger_name,
            "voucher_type": voucher_type,
            "confidence": confidence,
            "use_count": 0,
            "created_from": source,
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_ledger_mapper.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/ledger_mapper.py tests/unit/test_ledger_mapper.py
git commit -m "feat(B1a): add 3-tier ledger mapper with learning loop"
```

---

## Task 7: Voucher Builder — ExtractedDocument to Tally Payload

**Files:**
- Create: `backend/services/voucher_builder.py`
- Create: `tests/unit/test_voucher_builder.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for converting ExtractedDocument → Tally voucher payload."""
from decimal import Decimal

import pytest

from backend.services.document_parser import ExtractedDocument, GSTBreakdown, LineItem
from backend.services.voucher_builder import build_payment_voucher_data, VoucherData


class TestBuildPaymentVoucher:
    def test_simple_expense(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Uber",
            date="2026-04-04",
            total_amount=Decimal("500.00"),
            line_items=[LineItem(description="Ride", amount=Decimal("500.00"))],
            payment_mode="cash",
        )
        result = build_payment_voucher_data(
            doc=doc,
            expense_ledger="Travel Expenses",
            payment_ledger="Cash",
        )
        assert result.voucher_type == "Payment"
        assert result.date == "20260404"
        assert result.amount == Decimal("500.00")
        assert result.debit_ledger == "Travel Expenses"
        assert result.credit_ledger == "Cash"
        assert result.narration == "Uber — Ride"
        assert result.gst_entries == []

    def test_expense_with_gst(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Stationery Shop",
            date="2026-04-04",
            total_amount=Decimal("1180.00"),
            line_items=[LineItem(description="Paper", amount=Decimal("1000.00"))],
            gst=GSTBreakdown(
                cgst_rate=Decimal("9"), cgst_amount=Decimal("90"),
                sgst_rate=Decimal("9"), sgst_amount=Decimal("90"),
            ),
            payment_mode="cash",
        )
        result = build_payment_voucher_data(
            doc=doc,
            expense_ledger="Office Supplies",
            payment_ledger="Cash",
            gst_ledgers={"cgst_input": "CGST Input 9%", "sgst_input": "SGST Input 9%"},
        )
        assert len(result.gst_entries) == 2
        assert result.gst_entries[0]["ledger"] == "CGST Input 9%"
        assert result.gst_entries[0]["amount"] == 90.0

    def test_date_conversion(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name="Test",
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            line_items=[LineItem(description="Test", amount=Decimal("100.00"))],
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="Test", payment_ledger="Cash")
        assert result.date == "20260404"  # YYYYMMDD format for Tally import

    def test_narration_without_vendor(self):
        doc = ExtractedDocument(
            doc_type="expense",
            vendor_name=None,
            date="2026-04-04",
            total_amount=Decimal("100.00"),
            line_items=[LineItem(description="Miscellaneous expense", amount=Decimal("100.00"))],
        )
        result = build_payment_voucher_data(doc=doc, expense_ledger="Misc", payment_ledger="Cash")
        assert result.narration == "Miscellaneous expense"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_voucher_builder.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement voucher_builder.py**

```python
"""Convert ExtractedDocument into Tally voucher payload data.

Handles date format conversion (YYYY-MM-DD → YYYYMMDD), narration building,
and GST entry construction.
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


def _convert_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for Tally import."""
    return date_str.replace("-", "")


def _build_narration(doc: ExtractedDocument) -> str:
    """Build narration from vendor name and line item descriptions."""
    parts = []
    if doc.vendor_name:
        parts.append(doc.vendor_name)
    descriptions = [item.description for item in doc.line_items if item.description]
    if descriptions:
        parts.append(", ".join(descriptions[:3]))  # Max 3 items in narration
    return " — ".join(parts) if parts else "Expense entry"


def build_payment_voucher_data(
    doc: ExtractedDocument,
    expense_ledger: str,
    payment_ledger: str,
    gst_ledgers: dict[str, str] | None = None,
) -> VoucherData:
    """Convert an ExtractedDocument into VoucherData for a Payment voucher.

    Args:
        doc: Parsed document data.
        expense_ledger: Tally ledger for the expense (debit side).
        payment_ledger: Cash/Bank ledger (credit side).
        gst_ledgers: Optional dict mapping GST type to ledger name,
            e.g. {"cgst_input": "CGST Input 9%", "sgst_input": "SGST Input 9%"}.
    """
    gst_entries = []
    if doc.gst and gst_ledgers:
        if doc.gst.cgst_amount and "cgst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["cgst_input"],
                "amount": float(doc.gst.cgst_amount),
            })
        if doc.gst.sgst_amount and "sgst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["sgst_input"],
                "amount": float(doc.gst.sgst_amount),
            })
        if doc.gst.igst_amount and "igst_input" in gst_ledgers:
            gst_entries.append({
                "ledger": gst_ledgers["igst_input"],
                "amount": float(doc.gst.igst_amount),
            })

    return VoucherData(
        voucher_type="Payment",
        date=_convert_date(doc.date),
        debit_ledger=expense_ledger,
        credit_ledger=payment_ledger,
        amount=doc.total_amount,
        narration=_build_narration(doc),
        gst_entries=gst_entries,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_voucher_builder.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/voucher_builder.py tests/unit/test_voucher_builder.py
git commit -m "feat(B1a): add voucher builder — ExtractedDocument to Tally payload conversion"
```

---

## Task 8: Mock Handler — Write Support

**Files:**
- Modify: `backend/tally_bridge/mock_handler.py`
- Create: `tests/unit/test_mock_write.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for mock handler write operations."""
from backend.tally_bridge.mock_handler import mock_tally_request, reset_mock_state


class TestMockImport:
    def setup_method(self):
        reset_mock_state()

    def test_create_voucher_returns_success(self):
        xml = """<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>
<REQUESTDATA><TALLYMESSAGE><VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>20260404</DATE><NARRATION>Test</NARRATION>
</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""
        resp = mock_tally_request(xml)
        assert "CREATED" in resp
        assert ">1<" in resp or "<CREATED>1</CREATED>" in resp

    def test_create_ledger_returns_success(self):
        xml = """<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
<REQUESTDATA><TALLYMESSAGE><LEDGER NAME="Test" ACTION="Create">
<PARENT>Indirect Expenses</PARENT></LEDGER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""
        resp = mock_tally_request(xml)
        assert "<CREATED>1</CREATED>" in resp

    def test_delete_returns_success(self):
        xml = """<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>
<REQUESTDATA><TALLYMESSAGE><VOUCHER VCHTYPE="Payment" ACTION="Delete" VCHKEY="1">
</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""
        resp = mock_tally_request(xml)
        assert "<DELETED>1</DELETED>" in resp
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mock_write.py -v`
Expected: FAIL — `ImportError: cannot import name 'reset_mock_state'` or assertion errors

- [ ] **Step 3: Add import handling to mock_handler.py**

Add at the top of `mock_tally_request` function, before the existing dispatch logic. Also add a `reset_mock_state` function and a module-level counter:

```python
# Add at module level
_mock_vch_counter = 0
_mock_created_vouchers: list[dict] = []
_mock_created_ledgers: list[str] = []


def reset_mock_state():
    """Reset mock state for testing."""
    global _mock_vch_counter, _mock_created_vouchers, _mock_created_ledgers
    _mock_vch_counter = 0
    _mock_created_vouchers = []
    _mock_created_ledgers = []


def _handle_import(xml_body: str) -> str:
    """Handle IMPORTDATA requests — create/delete mocks."""
    global _mock_vch_counter

    if 'ACTION="Delete"' in xml_body:
        return """<RESPONSE>
<CREATED>0</CREATED><ALTERED>0</ALTERED><DELETED>1</DELETED>
<LASTVCHID>0</LASTVCHID><LASTMID>0</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
</RESPONSE>"""

    _mock_vch_counter += 1
    return f"""<RESPONSE>
<CREATED>1</CREATED><ALTERED>0</ALTERED><DELETED>0</DELETED>
<LASTVCHID>{_mock_vch_counter}</LASTVCHID><LASTMID>{_mock_vch_counter}</LASTMID>
<COMBINED>0</COMBINED><IGNORED>0</IGNORED><ERRORS>0</ERRORS>
</RESPONSE>"""
```

Add to the top of `mock_tally_request`, before existing dispatch:

```python
    # Handle import/write requests
    if "Import Data" in xml_body:
        return _handle_import(xml_body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_mock_write.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `pytest tests/unit/ -v --tb=short -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add backend/tally_bridge/mock_handler.py tests/unit/test_mock_write.py
git commit -m "feat(B1a): add write support to mock handler for demo and testing"
```

---

## Task 9: API Endpoint — Multipart File Upload

**Files:**
- Modify: `backend/api/chat.py`
- Modify: `backend/api/models.py`
- Create: `tests/unit/test_file_upload_endpoint.py`

- [ ] **Step 1: Add VoucherReviewData model to backend/api/models.py**

Add after `ConversationDetailResponse` (end of file):

```python
# --- Data Entry models (Set B1) ---

class VoucherReviewEntry(BaseModel):
    """A single voucher entry for review."""
    id: str
    voucher_type: str
    date: str
    vendor_name: str | None = None
    amount: float
    debit_ledger: str
    credit_ledger: str
    narration: str
    gst_entries: list[dict[str, Any]] = []
    status: str = "draft"
    warnings: list[str] = []
    is_new_ledger: bool = False
    suggested_parent: str | None = None


class VoucherReviewData(BaseModel):
    """Review card data sent as message.data for data entry."""
    type: Literal["voucher_review"] = "voucher_review"
    file_id: str | None = None
    entries: list[VoucherReviewEntry]
    available_ledgers: list[str] = []
    available_payment_ledgers: list[str] = []
```

- [ ] **Step 2: Add file upload endpoint to backend/api/chat.py**

Add a new endpoint alongside the existing `/chat` endpoint:

```python
from fastapi import UploadFile, File, Form

@router.post("/chat/upload")
async def chat_with_file(
    file: UploadFile = File(...),
    message: str = Form(default=""),
    workspace_id: str = Form(default=""),
    conversation_id: str = Form(default=""),
    client: TallyClient = Depends(get_client),
    user_id: str = Depends(get_current_user),
    db: AsyncSession | None = Depends(_get_optional_db),
) -> ChatResponse:
    """Handle file upload for data entry. Parses document and returns review card."""
    import os
    from backend.config import settings
    from backend.services.document_parser import detect_file_type

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_type = detect_file_type(file.filename, file.content_type or "")
    if file_type == "unsupported":
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

    file_size = 0
    contents = await file.read()
    file_size = len(contents)
    max_bytes = settings.FILE_MAX_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({file_size} bytes). Max: {settings.FILE_MAX_SIZE_MB}MB",
        )

    # Save file to disk
    os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)
    import uuid as uuid_mod
    file_id = str(uuid_mod.uuid4())
    ext = os.path.splitext(file.filename)[1]
    storage_path = os.path.join(settings.FILE_STORAGE_PATH, f"{file_id}{ext}")
    with open(storage_path, "wb") as f:
        f.write(contents)

    # TODO: In Task 11, this will call the data entry pipeline.
    # For now, return a placeholder acknowledging the upload.
    return ChatResponse(
        message=f"File '{file.filename}' uploaded successfully ({file_size} bytes). Processing...",
        data={"type": "file_uploaded", "file_id": file_id, "filename": file.filename},
        session_id=conversation_id or "upload",
    )
```

- [ ] **Step 3: Write tests for the upload endpoint**

```python
"""Tests for file upload endpoint."""
import io
import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


class TestFileUploadEndpoint:
    def test_upload_jpg(self, client, tmp_path):
        with patch("backend.config.settings") as mock_settings:
            mock_settings.FILE_STORAGE_PATH = str(tmp_path)
            mock_settings.FILE_MAX_SIZE_MB = 10
            mock_settings.db_mode = False
            # Create a fake image file
            file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
            response = client.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"message": "lunch expense"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "uploaded" in data["message"].lower()

    def test_upload_unsupported_type(self, client):
        response = client.post(
            "/api/chat/upload",
            files={"file": ("doc.docx", io.BytesIO(b"content"), "application/msword")},
        )
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_upload_too_large(self, client):
        with patch("backend.config.settings") as mock_settings:
            mock_settings.FILE_MAX_SIZE_MB = 0  # 0 MB = reject everything
            mock_settings.db_mode = False
            response = client.post(
                "/api/chat/upload",
                files={"file": ("big.jpg", io.BytesIO(b"\x00" * 100), "image/jpeg")},
            )
            assert response.status_code == 400
            assert "large" in response.json()["detail"].lower()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_file_upload_endpoint.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/chat.py backend/api/models.py tests/unit/test_file_upload_endpoint.py
git commit -m "feat(B1a): add file upload endpoint with validation"
```

---

## Task 10: Frontend — File Attach Button

**Files:**
- Create: `frontend/src/components/FileAttachButton.tsx`
- Modify: `frontend/src/components/ChatInput.tsx`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/__tests__/FileAttachButton.test.tsx`

- [ ] **Step 1: Create FileAttachButton component**

```tsx
import { useRef } from "react";
import { Paperclip } from "lucide-react";

const ACCEPTED_TYPES = ".jpg,.jpeg,.png,.heic,.pdf,.csv,.xlsx,.xls";

interface FileAttachButtonProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export default function FileAttachButton({ onFileSelect, disabled }: FileAttachButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleClick() {
    inputRef.current?.click();
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
      // Reset input so same file can be selected again
      e.target.value = "";
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={handleChange}
        className="hidden"
        data-testid="file-input"
      />
      <button
        onClick={handleClick}
        disabled={disabled}
        aria-label="Attach file"
        title="Attach expense receipt, invoice, or statement"
        className="rounded-xl p-2.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        <Paperclip className="w-5 h-5" />
      </button>
    </>
  );
}
```

- [ ] **Step 2: Update ChatInput to include file attach + preview**

Replace `frontend/src/components/ChatInput.tsx` with:

```tsx
import { useState, useRef, type KeyboardEvent } from "react";
import { SendHorizontal, X } from "lucide-react";
import FileAttachButton from "./FileAttachButton";

interface ChatInputProps {
  onSend: (message: string, file?: File) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed && !attachedFile) return;
    if (disabled) return;
    onSend(trimmed, attachedFile || undefined);
    setInput("");
    setAttachedFile(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
    }
  }

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {attachedFile && (
        <div className="max-w-3xl mx-auto mb-2">
          <div className="inline-flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-1.5 text-sm text-blue-700">
            <span className="truncate max-w-[200px]">{attachedFile.name}</span>
            <span className="text-blue-400">({(attachedFile.size / 1024).toFixed(0)} KB)</span>
            <button
              onClick={() => setAttachedFile(null)}
              className="text-blue-400 hover:text-blue-600"
              aria-label="Remove file"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <FileAttachButton
          onFileSelect={setAttachedFile}
          disabled={disabled}
        />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={attachedFile ? "Add a note (optional)..." : "Ask about your Tally data..."}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          onClick={handleSend}
          disabled={disabled || (!input.trim() && !attachedFile)}
          aria-label="Send message"
          className="rounded-xl bg-blue-600 p-2.5 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <SendHorizontal className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add sendChatWithFile to frontend/src/api/client.ts**

Add after the `sendChat` function:

```typescript
export async function sendChatWithFile(
  file: File,
  message: string,
  workspaceId?: string,
  conversationId?: string,
): Promise<ChatResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("message", message);
  if (workspaceId) form.append("workspace_id", workspaceId);
  if (conversationId) form.append("conversation_id", conversationId);

  const resp = await apiClient.post<ChatResponse>("/chat/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data;
}
```

- [ ] **Step 4: Write tests for FileAttachButton**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import FileAttachButton from "../components/FileAttachButton";

describe("FileAttachButton", () => {
  it("renders attach button", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} />);
    expect(screen.getByLabelText("Attach file")).toBeInTheDocument();
  });

  it("opens file picker on click", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} />);
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");
    fireEvent.click(screen.getByLabelText("Attach file"));
    expect(clickSpy).toHaveBeenCalled();
  });

  it("calls onFileSelect when file chosen", () => {
    const onFileSelect = vi.fn();
    render(<FileAttachButton onFileSelect={onFileSelect} />);
    const input = screen.getByTestId("file-input");
    const file = new File(["test"], "receipt.jpg", { type: "image/jpeg" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it("is disabled when disabled prop is true", () => {
    render(<FileAttachButton onFileSelect={vi.fn()} disabled />);
    expect(screen.getByLabelText("Attach file")).toBeDisabled();
  });
});
```

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: New tests pass, existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FileAttachButton.tsx frontend/src/components/ChatInput.tsx frontend/src/api/client.ts frontend/src/__tests__/FileAttachButton.test.tsx
git commit -m "feat(B1a): add file attach button and upload API client"
```

---

## Task 11: Frontend — VoucherReviewCard Component

**Files:**
- Create: `frontend/src/components/VoucherReviewCard.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Create: `frontend/src/__tests__/VoucherReviewCard.test.tsx`

- [ ] **Step 1: Create VoucherReviewCard component**

```tsx
import { useState } from "react";

interface VoucherEntry {
  id: string;
  voucher_type: string;
  date: string;
  vendor_name: string | null;
  amount: number;
  debit_ledger: string;
  credit_ledger: string;
  narration: string;
  gst_entries: Array<{ ledger: string; amount: number }>;
  status: string;
  warnings: string[];
  is_new_ledger: boolean;
  suggested_parent: string | null;
}

interface VoucherReviewCardProps {
  entries: VoucherEntry[];
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  onApprove: (entryId: string) => void;
  onDiscard: (entryId: string) => void;
  onEdit: (entryId: string, updates: Partial<VoucherEntry>) => void;
}

function formatDate(dateStr: string): string {
  // YYYYMMDD → DD-MMM-YYYY
  if (dateStr.length === 8) {
    const y = dateStr.slice(0, 4);
    const m = dateStr.slice(4, 6);
    const d = dateStr.slice(6, 8);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${d}-${months[parseInt(m) - 1]}-${y}`;
  }
  return dateStr;
}

function formatAmount(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(amount);
}

export default function VoucherReviewCard({
  entries,
  availableLedgers,
  availablePaymentLedgers,
  onApprove,
  onDiscard,
  onEdit,
}: VoucherReviewCardProps) {
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`rounded-lg border p-4 ${
            entry.status === "written"
              ? "border-green-200 bg-green-50"
              : entry.status === "deleted"
              ? "border-gray-200 bg-gray-50 opacity-60"
              : "border-blue-200 bg-blue-50"
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-700">
              Expense Entry — {entry.status === "written" ? "Written" : entry.status === "deleted" ? "Discarded" : "Draft"}
            </span>
            {entry.status === "written" && entry.id && (
              <span className="text-xs text-green-600">Voucher #{entry.id}</span>
            )}
          </div>

          {editingId === entry.id ? (
            <EditForm
              entry={entry}
              availableLedgers={availableLedgers}
              availablePaymentLedgers={availablePaymentLedgers}
              onSave={(updates) => {
                onEdit(entry.id, updates);
                setEditingId(null);
              }}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                <Field label="Vendor" value={entry.vendor_name || "—"} />
                <Field label="Date" value={formatDate(entry.date)} />
                <Field label="Amount" value={formatAmount(entry.amount)} />
                <Field label="Expense Ledger" value={entry.debit_ledger} />
                <Field label="Paid via" value={entry.credit_ledger} />
                <Field label="Narration" value={entry.narration} />
              </div>

              {entry.is_new_ledger && (
                <div className="text-xs text-amber-600 mb-2">
                  New ledger "{entry.debit_ledger}" will be created under "{entry.suggested_parent}"
                </div>
              )}

              {entry.warnings.length > 0 && (
                <div className="text-xs text-amber-600 mb-2">
                  {entry.warnings.map((w, i) => <div key={i}>{w}</div>)}
                </div>
              )}

              {entry.gst_entries.length > 0 && (
                <div className="text-xs text-gray-500 mb-2">
                  GST: {entry.gst_entries.map(g => `${g.ledger}: ${formatAmount(g.amount)}`).join(", ")}
                </div>
              )}

              {entry.status === "draft" && (
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => onApprove(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700 transition-colors"
                  >
                    Write to Tally
                  </button>
                  <button
                    onClick={() => setEditingId(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 text-sm hover:bg-gray-50 transition-colors"
                  >
                    Edit Entry
                  </button>
                  <button
                    onClick={() => onDiscard(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-600 text-sm hover:bg-red-50 transition-colors"
                  >
                    Discard
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}:</span>{" "}
      <span className="text-gray-900">{value}</span>
    </div>
  );
}

interface EditFormProps {
  entry: VoucherEntry;
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  onSave: (updates: Partial<VoucherEntry>) => void;
  onCancel: () => void;
}

function EditForm({ entry, availableLedgers, availablePaymentLedgers, onSave, onCancel }: EditFormProps) {
  const [vendor, setVendor] = useState(entry.vendor_name || "");
  const [amount, setAmount] = useState(String(entry.amount));
  const [debitLedger, setDebitLedger] = useState(entry.debit_ledger);
  const [creditLedger, setCreditLedger] = useState(entry.credit_ledger);
  const [narration, setNarration] = useState(entry.narration);

  return (
    <div className="space-y-2">
      <input value={vendor} onChange={(e) => setVendor(e.target.value)}
        placeholder="Vendor" className="w-full rounded border px-2 py-1 text-sm" />
      <input value={amount} onChange={(e) => setAmount(e.target.value)} type="number"
        placeholder="Amount" className="w-full rounded border px-2 py-1 text-sm" />
      <select value={debitLedger} onChange={(e) => setDebitLedger(e.target.value)}
        className="w-full rounded border px-2 py-1 text-sm">
        {availableLedgers.map(l => <option key={l} value={l}>{l}</option>)}
        {!availableLedgers.includes(debitLedger) && (
          <option value={debitLedger}>{debitLedger} (new)</option>
        )}
      </select>
      <select value={creditLedger} onChange={(e) => setCreditLedger(e.target.value)}
        className="w-full rounded border px-2 py-1 text-sm">
        {availablePaymentLedgers.map(l => <option key={l} value={l}>{l}</option>)}
      </select>
      <input value={narration} onChange={(e) => setNarration(e.target.value)}
        placeholder="Narration" className="w-full rounded border px-2 py-1 text-sm" />
      <div className="flex gap-2">
        <button onClick={() => onSave({
          vendor_name: vendor, amount: parseFloat(amount),
          debit_ledger: debitLedger, credit_ledger: creditLedger, narration,
        })}
          className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700">
          Confirm & Write to Tally
        </button>
        <button onClick={onCancel}
          className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 text-sm hover:bg-gray-50">
          Edit Again
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update MessageBubble to render VoucherReviewCard**

In `frontend/src/components/MessageBubble.tsx`, add detection for `data.type === "voucher_review"` in the assistant message rendering. After the existing chart/table rendering logic, add:

```tsx
import VoucherReviewCard from "./VoucherReviewCard";

// Inside the assistant message rendering, after chart/table detection:
{message.data && typeof message.data === "object" && !Array.isArray(message.data)
  && (message.data as Record<string, unknown>).type === "voucher_review" && (
  <VoucherReviewCard
    entries={(message.data as any).entries || []}
    availableLedgers={(message.data as any).available_ledgers || []}
    availablePaymentLedgers={(message.data as any).available_payment_ledgers || []}
    onApprove={(id) => {
      // Send approval message back to chat
      // This will be wired up in Task 12
    }}
    onDiscard={(id) => {
      // Send discard message
    }}
    onEdit={(id, updates) => {
      // Send edit message
    }}
  />
)}
```

- [ ] **Step 3: Write tests for VoucherReviewCard**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoucherReviewCard from "../components/VoucherReviewCard";

const mockEntry = {
  id: "test-1",
  voucher_type: "Payment",
  date: "20260404",
  vendor_name: "Uber",
  amount: 500,
  debit_ledger: "Travel Expenses",
  credit_ledger: "Cash",
  narration: "Uber — Ride",
  gst_entries: [],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

describe("VoucherReviewCard", () => {
  it("renders entry fields", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={["Travel Expenses", "Office Supplies"]}
        availablePaymentLedgers={["Cash", "Bank Account"]}
        onApprove={vi.fn()}
        onDiscard={vi.fn()}
        onEdit={vi.fn()}
      />
    );
    expect(screen.getByText(/Uber/)).toBeInTheDocument();
    expect(screen.getByText(/Travel Expenses/)).toBeInTheDocument();
    expect(screen.getByText("Write to Tally")).toBeInTheDocument();
    expect(screen.getByText("Edit Entry")).toBeInTheDocument();
    expect(screen.getByText("Discard")).toBeInTheDocument();
  });

  it("calls onApprove when Write to Tally clicked", () => {
    const onApprove = vi.fn();
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={onApprove}
        onDiscard={vi.fn()}
        onEdit={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText("Write to Tally"));
    expect(onApprove).toHaveBeenCalledWith("test-1");
  });

  it("shows warning for new ledger", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, is_new_ledger: true, suggested_parent: "Indirect Expenses" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={vi.fn()}
        onDiscard={vi.fn()}
        onEdit={vi.fn()}
      />
    );
    expect(screen.getByText(/will be created/)).toBeInTheDocument();
  });

  it("shows written state", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "written" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={vi.fn()}
        onDiscard={vi.fn()}
        onEdit={vi.fn()}
      />
    );
    expect(screen.getByText(/Written/)).toBeInTheDocument();
    expect(screen.queryByText("Write to Tally")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VoucherReviewCard.tsx frontend/src/components/MessageBubble.tsx frontend/src/__tests__/VoucherReviewCard.test.tsx
git commit -m "feat(B1a): add VoucherReviewCard component with approve/edit/discard actions"
```

---

## Task 12: Data Entry Pipeline — Orchestrator Integration

> This is the integration task that wires everything together.

**Files:**
- Modify: `backend/agents/orchestrator.py`
- Modify: `backend/api/chat.py`
- Create: `tests/e2e/test_data_entry.py`

- [ ] **Step 1: Add data entry handler to orchestrator**

Add a new method to the `Orchestrator` class in `backend/agents/orchestrator.py`:

```python
async def process_file_upload(
    self,
    file_path: str,
    filename: str,
    mime_type: str,
    user_message: str,
    client: TallyClient,
    session: SessionContext,
    file_id: str,
) -> dict:
    """Process an uploaded file for data entry.

    Returns a ChatResponse-compatible dict with voucher review data.
    """
    from backend.services.document_parser import (
        detect_file_type, build_vision_prompt, parse_vision_response,
        validate_extracted_amounts,
    )
    from backend.services.ledger_mapper import LedgerMapper, MappingResult
    from backend.services.voucher_builder import build_payment_voucher_data

    # 1. Parse the document
    file_type = detect_file_type(filename, mime_type)
    if file_type == "vision":
        # Read file as base64 for Claude Vision
        import base64
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine media type for Claude
        media_type = mime_type
        if mime_type == "application/pdf":
            media_type = "application/pdf"
        elif mime_type in ("image/heic",):
            media_type = "image/jpeg"  # Claude doesn't support HEIC directly

        import anthropic
        from backend.config import settings
        ai_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = ai_client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": build_vision_prompt()},
                ],
            }],
        )
        extracted = parse_vision_response(response.content[0].text)
    else:
        return {
            "message": f"Structured file parsing ({filename}) not yet supported in B1a. Upload an image or PDF.",
            "data": None,
        }

    # 2. Validate amounts
    warnings = validate_extracted_amounts(extracted)

    # 3. Fetch Tally ledger list for mapping
    from backend.tally_bridge.request_builder import build_list_ledgers
    from backend.tally_bridge.response_parser import parse_ledger_list
    ledger_xml = await client.post_xml(build_list_ledgers())
    tally_ledgers = parse_ledger_list(ledger_xml)
    ledger_names = [l["name"] for l in tally_ledgers]

    # Identify payment ledgers (Cash, Bank accounts)
    payment_groups = {"cash-in-hand", "bank accounts", "bank occ a/c"}
    payment_ledgers = [
        l["name"] for l in tally_ledgers
        if l["parent_group"].lower() in payment_groups
    ]
    if not payment_ledgers:
        payment_ledgers = ["Cash"]

    # 4. Map to ledger
    mapper = LedgerMapper()
    # TODO: Load stored mappings from DB in future
    mapping = await mapper.find_mapping(
        extracted.vendor_name or "Expense",
        "Payment",
        tally_ledgers=ledger_names,
    )

    # 5. Build voucher data
    voucher = build_payment_voucher_data(
        doc=extracted,
        expense_ledger=mapping.ledger_name,
        payment_ledger=payment_ledgers[0],
    )

    # 6. Build review card response
    import uuid as uuid_mod
    entry_id = str(uuid_mod.uuid4())
    review_data = {
        "type": "voucher_review",
        "file_id": file_id,
        "entries": [{
            "id": entry_id,
            "voucher_type": voucher.voucher_type,
            "date": voucher.date,
            "vendor_name": extracted.vendor_name,
            "amount": float(voucher.amount),
            "debit_ledger": voucher.debit_ledger,
            "credit_ledger": voucher.credit_ledger,
            "narration": voucher.narration,
            "gst_entries": voucher.gst_entries,
            "status": "draft",
            "warnings": warnings,
            "is_new_ledger": mapping.is_new_ledger,
            "suggested_parent": mapping.suggested_parent,
        }],
        "available_ledgers": ledger_names,
        "available_payment_ledgers": payment_ledgers,
    }

    vendor_display = extracted.vendor_name or "Unknown vendor"
    amount_display = f"₹{float(voucher.amount):,.2f}"
    message = f"I've extracted the expense details from your receipt:\n\n**{vendor_display}** — {amount_display} on {extracted.date}\n\nPlease review the entry below and click **Write to Tally** to create the payment voucher, or **Edit Entry** to make corrections."

    if warnings:
        message += "\n\n⚠️ " + " | ".join(warnings)

    return {"message": message, "data": review_data}
```

- [ ] **Step 2: Wire file upload endpoint to orchestrator pipeline**

Update the `chat_with_file` endpoint in `backend/api/chat.py` to call `process_file_upload`:

Replace the TODO placeholder at the end of `chat_with_file` with:

```python
    # Run data entry pipeline
    from backend.agents.orchestrator import Orchestrator
    from backend.agents.context import SessionContext

    orchestrator = Orchestrator()
    session = SessionContext(session_id=conversation_id or file_id)

    result = await orchestrator.process_file_upload(
        file_path=storage_path,
        filename=file.filename,
        mime_type=file.content_type or "",
        user_message=message,
        client=client,
        session=session,
        file_id=file_id,
    )

    return ChatResponse(
        message=result["message"],
        data=result.get("data"),
        session_id=conversation_id or file_id,
    )
```

- [ ] **Step 3: Add approval handling to chat endpoint**

Add a new endpoint for voucher actions (approve/discard/edit):

```python
@router.post("/chat/voucher-action")
async def voucher_action(
    request: dict,
    client: TallyClient = Depends(get_client),
    user_id: str = Depends(get_current_user),
) -> ChatResponse:
    """Handle voucher approve/discard/edit actions."""
    from backend.config import settings
    from backend.tally_bridge.writer import TallyWriter

    action = request.get("action")  # "approve", "discard", "edit"
    entry = request.get("entry", {})
    company = request.get("company", "")

    if action == "approve":
        if not settings.TALLY_WRITE_ENABLED:
            return ChatResponse(
                message="Tally write is disabled. Enable TALLY_WRITE_ENABLED to create vouchers.",
                session_id=request.get("session_id", ""),
            )

        writer = TallyWriter(client=client, company=company)
        try:
            result = await writer.create_payment_voucher(
                date=entry["date"],
                debit_ledger=entry["debit_ledger"],
                credit_ledger=entry["credit_ledger"],
                amount=entry["amount"],
                narration=entry["narration"],
                gst_entries=entry.get("gst_entries"),
            )
            if result["success"]:
                vch_id = result.get("last_vch_id", "")
                return ChatResponse(
                    message=f"Payment voucher written to Tally successfully (Voucher #{vch_id}).",
                    data={"type": "voucher_written", "entry_id": entry["id"], "tally_voucher_id": vch_id},
                    session_id=request.get("session_id", ""),
                )
            else:
                return ChatResponse(
                    message=f"Failed to write to Tally: {result.get('error_message', 'Unknown error')}",
                    data={"type": "voucher_error", "entry_id": entry["id"]},
                    session_id=request.get("session_id", ""),
                )
        except Exception as e:
            return ChatResponse(
                message=f"Error writing to Tally: {str(e)}",
                data={"type": "voucher_error", "entry_id": entry["id"]},
                session_id=request.get("session_id", ""),
            )

    elif action == "discard":
        return ChatResponse(
            message="Entry discarded.",
            data={"type": "voucher_discarded", "entry_id": entry.get("id")},
            session_id=request.get("session_id", ""),
        )

    return ChatResponse(
        message="Unknown action.",
        session_id=request.get("session_id", ""),
    )
```

- [ ] **Step 4: Write E2E test for the data entry pipeline**

```python
"""E2E test for expense data entry pipeline (mock mode)."""
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.main import app
    return TestClient(app)


class TestDataEntryE2E:
    @patch("backend.agents.orchestrator.anthropic")
    def test_upload_receipt_returns_review_card(self, mock_anthropic, client, tmp_path):
        """Upload a receipt image → get back a voucher review card."""
        # Mock Claude Vision response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"doc_type":"expense","vendor_name":"Uber","date":"2026-04-04","total_amount":500.0,"line_items":[{"description":"Ride","amount":500.0}],"gst":null,"payment_mode":"upi"}')]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        with patch("backend.config.settings") as mock_settings:
            mock_settings.FILE_STORAGE_PATH = str(tmp_path)
            mock_settings.FILE_MAX_SIZE_MB = 10
            mock_settings.db_mode = False
            mock_settings.ANTHROPIC_API_KEY = "test-key"
            mock_settings.CLAUDE_MODEL = "claude-sonnet-4-6"
            mock_settings.TALLY_MODE = "mock"

            file_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
            response = client.post(
                "/api/chat/upload",
                files={"file": ("receipt.jpg", io.BytesIO(file_content), "image/jpeg")},
                data={"message": "lunch expense"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "Uber" in data["message"]
            assert data["data"]["type"] == "voucher_review"
            assert len(data["data"]["entries"]) == 1
            assert data["data"]["entries"][0]["status"] == "draft"
```

- [ ] **Step 5: Run E2E test**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/e2e/test_data_entry.py -v`
Expected: Test passes

- [ ] **Step 6: Commit**

```bash
git add backend/agents/orchestrator.py backend/api/chat.py tests/e2e/test_data_entry.py
git commit -m "feat(B1a): wire data entry pipeline — file upload → parse → map → review card"
```

---

## Task 13: Integration Test — Full Write Cycle

**Files:**
- Create: `tests/integration/test_tally_write.py`

- [ ] **Step 1: Write integration test for create + verify + delete cycle**

```python
"""Integration tests for Tally write operations using mock handler."""
import pytest

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.writer import TallyWriter
from backend.tally_bridge.mock_handler import reset_mock_state


@pytest.fixture
def mock_client():
    reset_mock_state()
    return TallyClient(host="localhost", port=9000, mock_mode=True)


class TestTallyWriteIntegration:
    @pytest.mark.asyncio
    async def test_create_payment_voucher(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_payment_voucher(
            date="20260404",
            debit_ledger="Travel Expenses",
            credit_ledger="Cash",
            amount=500.00,
            narration="Integration test expense",
        )
        assert result["success"] is True
        assert result["created"] == 1

    @pytest.mark.asyncio
    async def test_create_ledger(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_ledger(name="Test Ledger", parent="Indirect Expenses")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_group(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.create_group(name="Test Group", parent="Indirect Expenses")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_voucher(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        result = await writer.delete_voucher(voucher_type="Payment", voucher_number="1")
        assert result["success"] is True
        assert result["deleted"] == 1

    @pytest.mark.asyncio
    async def test_create_then_delete_ledger(self, mock_client):
        writer = TallyWriter(client=mock_client, company="Test Co")
        create_result = await writer.create_ledger(name="Temp Ledger", parent="Indirect Expenses")
        assert create_result["success"] is True
        delete_result = await writer.delete_ledger(name="Temp Ledger")
        assert delete_result["success"] is True
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/integration/test_tally_write.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ -q`
Expected: All existing + new tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_tally_write.py
git commit -m "test(B1a): add integration tests for Tally write operations"
```

---

## Task 14: Frontend — Wire Approve/Discard Actions

**Files:**
- Modify: `frontend/src/components/ChatWindow.tsx`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add voucherAction API call to client.ts**

Add after `sendChatWithFile`:

```typescript
export async function voucherAction(
  action: "approve" | "discard" | "edit",
  entry: Record<string, unknown>,
  company: string,
  sessionId: string,
): Promise<ChatResponse> {
  const resp = await apiClient.post<ChatResponse>("/chat/voucher-action", {
    action,
    entry,
    company,
    session_id: sessionId,
  });
  return resp.data;
}
```

- [ ] **Step 2: Update ChatWindow to handle file sends and voucher actions**

In `ChatWindow.tsx`, update `handleSend` to support file uploads:

```typescript
// Update the handleSend signature and body to support files:
async function handleSend(message: string, file?: File) {
  // ... existing message handling ...

  if (file) {
    // Use file upload endpoint
    const response = await sendChatWithFile(
      file,
      message,
      workspaceId,
      conversationId,
    );
    // Handle response same as regular chat
    // ...
  } else {
    // Existing sendChat logic
    // ...
  }
}
```

Add a `handleVoucherAction` callback and pass it down to `MessageBubble`:

```typescript
async function handleVoucherAction(
  action: "approve" | "discard",
  entry: Record<string, unknown>,
) {
  setLoading(true);
  try {
    const response = await voucherAction(action, entry, company || "", sessionId);
    setMessages(prev => [...prev, {
      role: "assistant",
      content: response.message,
      data: response.data,
    }]);
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 3: Wire VoucherReviewCard actions in MessageBubble**

Update the `VoucherReviewCard` rendering in `MessageBubble.tsx` to wire the callbacks:

```tsx
onApprove={(id) => {
  const entry = (message.data as any).entries.find((e: any) => e.id === id);
  if (entry && onVoucherAction) {
    onVoucherAction("approve", entry);
  }
}}
onDiscard={(id) => {
  const entry = (message.data as any).entries.find((e: any) => e.id === id);
  if (entry && onVoucherAction) {
    onVoucherAction("discard", entry);
  }
}}
```

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatWindow.tsx frontend/src/components/MessageBubble.tsx frontend/src/api/client.ts
git commit -m "feat(B1a): wire voucher approve/discard actions in frontend"
```

---

## Task 15: Smoke Test & Manual Verification

- [ ] **Step 1: Run full backend test suite**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ -q`
Expected: All tests pass

- [ ] **Step 2: Run frontend test suite**

Run: `cd frontend && npm test -- --run`
Expected: All tests pass

- [ ] **Step 3: Manual smoke test in mock mode**

Start backend and frontend:
```bash
# Terminal 1
TALLY_MODE=mock ANTHROPIC_API_KEY=<key> uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend && npm run dev
```

Manual test:
1. Open http://localhost:5173
2. Click paperclip icon → select an expense receipt image
3. Verify review card appears with extracted data
4. Click "Edit Entry" → change ledger → click "Confirm & Write to Tally"
5. Verify success message

- [ ] **Step 4: Commit final integration**

```bash
git add -A
git commit -m "feat(B1a): complete expense receipt data entry pipeline"
```

---

## Summary

| Task | Description | Key Files | Tests |
|------|-------------|-----------|-------|
| 0 | Tally write exploration | `scripts/explore_tally_write*.py` | Manual (DONE) |
| 1 | Import XML builder | `import_builder.py` | 11 |
| 2 | Import response parser | `response_parser.py` | 6 |
| 3 | Tally writer + validation | `writer.py` | 8 |
| 4 | DB schema + config | `models.py`, `config.py`, migration | — |
| 5 | Document parser | `document_parser.py` | 10 |
| 6 | Ledger mapper | `ledger_mapper.py` | 5 |
| 7 | Voucher builder | `voucher_builder.py` | 4 |
| 8 | Mock handler writes | `mock_handler.py` | 3 |
| 9 | File upload endpoint | `chat.py`, `models.py` | 3 |
| 10 | Frontend file attach | `FileAttachButton.tsx`, `ChatInput.tsx` | 4 |
| 11 | VoucherReviewCard | `VoucherReviewCard.tsx`, `MessageBubble.tsx` | 4 |
| 12 | Pipeline integration | `orchestrator.py`, `chat.py` | 1 |
| 13 | Write integration tests | `test_tally_write.py` | 5 |
| 14 | Frontend action wiring | `ChatWindow.tsx`, `client.ts` | — |
| 15 | Smoke test | — | Manual |

**Total new tests: ~64**
**Estimated new test count after B1a: ~1039**
