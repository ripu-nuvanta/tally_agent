# Tally Bridge Gap Closure — Implementation Plan

> **Status: COMPLETE** — All 9 gaps (H1-H4, M1-M5) implemented and merged to master.
> 8 commits, 670 backend tests (up from 641), 6 new tools (12→18).
> Code review: `docs/code-review-phase11.md` | Test coverage: 95%

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the high and medium priority gaps identified in `docs/tally-bridge-gap-analysis.md` — adding 6 new tools, fixing 1 model, updating 2 tool descriptions, fixing 1 prompt, and wiring up inventory allocation data in vouchers.

**Architecture:** Each gap follows the same pattern: request builder → response parser → query function → tool schema + handler → mock fixture → tests. Changes are additive — no existing APIs change, only new fields/tools are added.

**Tech Stack:** Python (FastAPI), xml.etree.ElementTree, Pydantic, pytest, httpx

**Gap items covered (9 total):**
- **H1**: `list_stock_items` tool (complete orphaned chain)
- **H2**: Inventory allocations in vouchers (`AllInventoryEntries`)
- **H3**: `list_all_ledgers` direct tool
- **H4**: `overdue_days` in `OutstandingBill` model
- **M1**: Dedicated `get_payment_register` / `get_receipt_register` tools
- **M2**: Cash Flow Statement tool
- **M3**: `list_account_groups` tool (complete orphaned chain)
- **M4**: Update receivable/payable tool descriptions for `due_date` / `overdue_days`
- **M5**: Fix P&L month-trend prompt guidance

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `backend/tally_bridge/models.py` | Modify | Add `overdue_days` to `OutstandingBill`, add `StockItem` and `AccountGroup` models |
| `backend/tally_bridge/response_parser.py` | Modify | Add `parse_stock_items()`, `parse_groups()`, `parse_cash_flow()`, add `inventory_entries` to `parse_vouchers()` |
| `backend/tally_bridge/request_builder.py` | Modify | Add `build_cash_flow()`, add `AllInventoryEntries` to `_voucher_native_methods()` |
| `backend/tally_bridge/queries/masters.py` | Modify | Add `list_stock_items()`, `list_groups()` |
| `backend/tally_bridge/queries/reports.py` | Modify | Add `cash_flow()`, fix `bills_receivable`/`bills_payable` to pass `due_date`/`overdue_days` |
| `backend/agents/tools.py` | Modify | Add 5 new tool schemas + handlers, update 2 descriptions |
| `backend/agents/prompts.py` | Modify | Fix Rule 11 for P&L trend, add voucher_type valid values |
| `backend/tally_bridge/mock_handler.py` | Modify | Add entries for stock items, groups, cash flow fixtures |
| `tests/fixtures/generate_fixtures.py` | Modify | Add `generate_stock_items_list()`, `generate_groups_list()`, `generate_cash_flow()`, add inventory entries to voucher fixtures |
| `tests/unit/test_response_parser.py` | Modify | Tests for new parsers |
| `tests/unit/test_request_builder.py` | Modify | Tests for new/modified builders |
| `tests/unit/test_tools.py` | Modify | Tests for new tool handlers |
| `tests/unit/test_models.py` | Modify | Tests for new/modified models |

---

## Chunk 1: Prompt Fixes (M5)

These are low-risk text-only changes. **Get these reviewed before implementation tasks.**

> **Review note (M4 moved):** Tool description updates (M4) are deferred to Task 3 (H4) since they
> claim `overdue_days` in the response — the model must support it first.

### Task 1: Fix P&L month-trend prompt (M5)

**Files:**
- Modify: `backend/agents/prompts.py:151-154` (Rule 11)

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_prompts.py — add to existing file or create
from backend.agents.prompts import build_query_agent_prompt

def test_query_prompt_warns_pnl_not_groupable_by_month():
    """Rule 11 must warn that get_profit_and_loss returns per-account rows, not per-voucher."""
    prompt = build_query_agent_prompt("13-03-2026")
    assert "get_profit_and_loss" in prompt
    assert "cannot be grouped by month" in prompt.lower()
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_prompts.py::test_query_prompt_warns_pnl_not_groupable_by_month -v`
Expected: FAIL — current Rule 11 does not mention P&L limitation

- [x]**Step 3: Update Rule 11 in prompts.py**

Replace the current Rule 11 (lines 151-154) with:

```python
11. **One-call trend queries**: For trend/time-series queries on VOUCHER data \
(day book, sales register, purchase register), fetch the FULL date range in ONE call, \
then use compute_totals with group_by='month' to aggregate by month. Do NOT make \
separate API calls per month — the voucher data includes a 'month' field for grouping. \
**IMPORTANT**: get_profit_and_loss and get_balance_sheet return one row per ACCOUNT, \
not per voucher — they CANNOT be grouped by month. For monthly P&L trends, call \
get_profit_and_loss once per month (up to 12 calls for a full year; note: each call \
internally triggers 2 Tally HTTP requests via the subtraction approach, so 12 months ≈ 23 \
HTTP requests). For a lighter alternative, use get_sales_register + \
get_day_book(voucher_type="Purchase") as a proxy for revenue/cost trends (one call each, \
then group_by='month').
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_prompts.py::test_query_prompt_warns_pnl_not_groupable_by_month -v`
Expected: PASS

- [x]**Step 5: Write test for voucher_type guidance**

```python
def test_query_prompt_lists_valid_voucher_types():
    prompt = build_query_agent_prompt("13-03-2026")
    for vtype in ["Sales", "Purchase", "Payment", "Receipt", "Journal", "Contra", "Credit Note", "Debit Note"]:
        assert vtype in prompt
```

- [x]**Step 6: Add voucher_type valid values to prompt**

Add after Rule 11 in `build_query_agent_prompt`:

```python
12. **Valid voucher_type values for get_day_book**: Use exactly one of: \
"Sales", "Purchase", "Payment", "Receipt", "Journal", "Contra", "Credit Note", \
"Debit Note". The value is case-insensitive (auto-title-cased). Do NOT use plurals \
(e.g. "Payments" is wrong, use "Payment"). Other Tally voucher types exist \
(Delivery Note, Receipt Note, etc.) but are not currently supported by the tool layer.
```

- [x]**Step 7: Run all prompt tests**

Run: `pytest tests/unit/test_prompts.py -v`
Expected: All PASS

- [x]**Step 8: Commit**

```bash
git add backend/agents/prompts.py tests/unit/test_prompts.py
git commit -m "fix: clarify P&L month-trend limitation and valid voucher_type values in query prompt (M5)"
```

---

## Chunk 2: Model & Parser Foundations (H4, partial H1, partial M3)

### Task 3: Add `overdue_days` to OutstandingBill model + fix reports.py + update tool descriptions (H4 + M4)

**Files:**
- Modify: `backend/tally_bridge/models.py:44-50`
- Modify: `backend/tally_bridge/response_parser.py` (overdue_days conversion)
- Modify: `backend/tally_bridge/queries/reports.py:181-211` (pass due_date/overdue_days through)
- Modify: `backend/agents/tools.py:145-178` (tool descriptions)

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_models.py — add
from backend.tally_bridge.models import OutstandingBill
from datetime import date

def test_outstanding_bill_has_overdue_days():
    bill = OutstandingBill(
        party_name="Test", bill_number="B001", bill_date=date(2025, 10, 1),
        amount=10000, pending_amount=10000, overdue_days=45,
    )
    assert bill.overdue_days == 45

def test_outstanding_bill_overdue_days_default_none():
    bill = OutstandingBill(
        party_name="Test", bill_number="B001", bill_date=date(2025, 10, 1),
        amount=10000, pending_amount=10000,
    )
    assert bill.overdue_days is None
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py::test_outstanding_bill_has_overdue_days -v`
Expected: FAIL — `overdue_days` not a field on `OutstandingBill`

- [x]**Step 3: Add overdue_days field**

In `backend/tally_bridge/models.py`, modify `OutstandingBill`:

```python
class OutstandingBill(BaseModel):
    party_name: str
    bill_number: str
    bill_date: date
    due_date: date | None = None
    amount: float
    pending_amount: float
    overdue_days: int | None = None
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

- [x]**Step 5: Update bills handler to pass overdue_days through**

The parser (`parse_bills` in `response_parser.py`) already extracts `overdue_days` as a string. The handler in `tools.py` converts to `OutstandingBill` model which now accepts it. But we need to convert the string to int.

In `backend/tally_bridge/queries/reports.py`, the `bills_receivable` and `bills_payable` functions call `parse_bills()` which returns dicts with `overdue_days` as string. These get passed to `OutstandingBill(**row)`. We need to handle the string-to-int conversion.

Update `parse_bills` in `response_parser.py` to convert overdue_days. Tally may return
plain integers ("45") or suffixed strings ("45 Days"), so strip non-numeric suffixes:

```python
# In parse_bills(), change the overdue_days line in the bills.append() dict:
"overdue_days": _parse_overdue_days(overdue_days),
```

Add this helper near the top of response_parser.py (after `parse_amount`):

```python
def _parse_overdue_days(text: str) -> int | None:
    """Parse overdue days from Tally — handles '45', '-10', '45 Days', etc."""
    if not text or not text.strip():
        return None
    # Take first token (handles "45 Days" → "45")
    num_str = text.strip().split()[0]
    try:
        return int(num_str)
    except ValueError:
        return None
```

- [x]**Step 6: Write parser test for overdue_days conversion**

```python
# tests/unit/test_response_parser.py — add
def test_parse_bills_includes_overdue_days():
    xml = """<ENVELOPE><BODY><DATA><TALLYMESSAGE>
    <BILLFIXED><BILLREF>INV001</BILLREF><BILLPARTY>Test Co</BILLPARTY><BILLDATE>20251001</BILLDATE></BILLFIXED>
    <BILLCL>50000</BILLCL><BILLDUE>15-11-2025</BILLDUE><BILLOVERDUE>45</BILLOVERDUE>
    </TALLYMESSAGE></DATA></BODY></ENVELOPE>"""
    from backend.tally_bridge.response_parser import parse_bills
    bills = parse_bills(xml)
    assert len(bills) == 1
    assert bills[0]["overdue_days"] == 45
    assert bills[0]["due_date"] == "15-11-2025"
```

- [x]**Step 7: Run parser tests**

Run: `pytest tests/unit/test_response_parser.py -v`
Expected: PASS

- [x]**Step 8: Fix reports.py to pass due_date and overdue_days through**

Currently `bills_receivable()` and `bills_payable()` in `backend/tally_bridge/queries/reports.py`
explicitly construct `OutstandingBill` with only 5 fields, dropping `due_date` and `overdue_days`.
Update both functions to pass them through:

```python
# In bills_receivable() and bills_payable(), update the OutstandingBill constructor:
return [
    OutstandingBill(
        party_name=b["party_name"],
        bill_number=b["bill_number"],
        bill_date=_parse_tally_date(b["bill_date"]) or date.today(),
        due_date=_parse_tally_date(b.get("due_date", "")),
        amount=b["amount"],
        pending_amount=b["pending_amount"],
        overdue_days=b.get("overdue_days"),
    )
    for b in parsed
]
```

- [x]**Step 9: Write integration test for full chain (XML → query → model)**

```python
# tests/unit/test_reports_query.py — add or create
import pytest
from unittest.mock import AsyncMock
from backend.tally_bridge.queries.reports import bills_receivable

@pytest.mark.asyncio
async def test_bills_receivable_passes_overdue_days():
    mock_client = AsyncMock()
    mock_client.post_xml.return_value = """<ENVELOPE><BODY><DATA><TALLYMESSAGE>
    <BILLFIXED><BILLREF>INV001</BILLREF><BILLPARTY>Test Co</BILLPARTY><BILLDATE>20251001</BILLDATE></BILLFIXED>
    <BILLCL>50000</BILLCL><BILLDUE>15-11-2025</BILLDUE><BILLOVERDUE>45</BILLOVERDUE>
    </TALLYMESSAGE></DATA></BODY></ENVELOPE>"""
    bills = await bills_receivable(mock_client, "13-03-2026")
    assert len(bills) == 1
    assert bills[0].overdue_days == 45
    assert bills[0].due_date is not None
```

- [x]**Step 10: Update receivable/payable tool descriptions (M4)**

In `backend/agents/tools.py`, update both tool descriptions:

```python
# get_outstanding_receivables
"description": "Fetch all outstanding receivable bills from TallyPrime as on a date. Returns party name, bill number, bill date, due date, overdue days, amount, and pending amount.",

# get_outstanding_payables
"description": "Fetch all outstanding payable bills from TallyPrime as on a date. Returns party name, bill number, bill date, due date, overdue days, amount, and pending amount.",
```

- [x]**Step 11: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [x]**Step 12: Commit**

```bash
git add backend/tally_bridge/models.py backend/tally_bridge/response_parser.py backend/tally_bridge/queries/reports.py backend/agents/tools.py tests/unit/
git commit -m "feat: add overdue_days to OutstandingBill, fix reports.py passthrough, update tool descriptions (H4 + M4)"
```

### Task 4: Add StockItem and AccountGroup models

**Files:**
- Modify: `backend/tally_bridge/models.py`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_models.py — add
from backend.tally_bridge.models import StockItem, AccountGroup

def test_stock_item_model():
    item = StockItem(
        name="HP Laptop 15s", parent_group="Electronics", base_units="Nos",
        closing_balance=10.0, closing_rate=38000.0, closing_value=380000.0,
    )
    assert item.name == "HP Laptop 15s"
    assert item.parent_group == "Electronics"

def test_account_group_model():
    group = AccountGroup(name="Sales Accounts", parent="Revenue")
    assert group.name == "Sales Accounts"
    assert group.parent == "Revenue"
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py::test_stock_item_model -v`
Expected: FAIL — `StockItem` not defined

- [x]**Step 3: Add models**

In `backend/tally_bridge/models.py`, add:

```python
class StockItem(BaseModel):
    name: str
    parent_group: str = ""
    base_units: str = ""
    closing_balance: float = 0.0
    closing_rate: float = 0.0
    closing_value: float = 0.0


class AccountGroup(BaseModel):
    name: str
    parent: str = ""
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

- [x]**Step 5: Commit**

```bash
git add backend/tally_bridge/models.py tests/unit/test_models.py
git commit -m "feat: add StockItem and AccountGroup Pydantic models"
```

### Task 5: Add `parse_stock_items()` and `parse_groups()` parsers

**Files:**
- Modify: `backend/tally_bridge/response_parser.py`

- [x]**Step 1: Write failing test for parse_stock_items**

```python
# tests/unit/test_response_parser.py — add
from backend.tally_bridge.response_parser import parse_stock_items, parse_groups

def test_parse_stock_items_extracts_fields():
    xml = """<ENVELOPE><BODY><DATA><COLLECTION>
    <STOCKITEM NAME="HP Laptop 15s">
        <NAME>HP Laptop 15s</NAME>
        <PARENT>Electronics</PARENT>
        <BASEUNITS>Nos</BASEUNITS>
        <CLOSINGBALANCE>10.0000 Nos</CLOSINGBALANCE>
        <CLOSINGRATE>38000.00/Nos</CLOSINGRATE>
        <CLOSINGVALUE>380000.00</CLOSINGVALUE>
    </STOCKITEM>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    items = parse_stock_items(xml)
    assert len(items) == 1
    assert items[0]["name"] == "HP Laptop 15s"
    assert items[0]["parent_group"] == "Electronics"
    assert items[0]["base_units"] == "Nos"
    assert items[0]["closing_balance"] == 10.0
    assert items[0]["closing_rate"] == 38000.0
    assert items[0]["closing_value"] == 380000.0
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_response_parser.py::test_parse_stock_items_extracts_fields -v`
Expected: FAIL — `parse_stock_items` not defined

- [x]**Step 3: Implement parse_stock_items**

In `backend/tally_bridge/response_parser.py`, add:

```python
def parse_stock_items(raw_xml: str) -> list[dict]:
    """Parse CustomStockItemList collection response.

    CLOSINGBALANCE format: "10.0000 Nos" (number + space + unit) in our fixtures.
    Note: Real Tally TYPE=Collection may return just the numeric value without unit.
    The BASEUNITS fallback handles this — if CLOSINGBALANCE has no unit suffix,
    the unit comes from the dedicated BASEUNITS field.
    CLOSINGRATE format: "38000.00/Nos" (number + slash + unit)
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    items = []
    for item in root.iter("STOCKITEM"):
        name = _get_text(item, "NAME") or item.get("NAME", "")
        if not name:
            continue
        # Parse closing balance: "10.0000 Nos" → qty=10.0, unit="Nos"
        cb_text = _get_text(item, "CLOSINGBALANCE")
        qty = 0.0
        unit = _get_text(item, "BASEUNITS")
        if cb_text:
            parts = cb_text.split()
            if parts:
                try:
                    qty = float(parts[0].replace(",", ""))
                except ValueError:
                    pass
                if len(parts) > 1 and not unit:
                    unit = " ".join(parts[1:])
        # Parse closing rate: "38000.00/Nos" → 38000.0
        rate_text = _get_text(item, "CLOSINGRATE")
        rate = 0.0
        if rate_text:
            rate_num = rate_text.split("/")[0].strip()
            rate = parse_amount(rate_num)
        items.append({
            "name": name,
            "parent_group": _get_text(item, "PARENT"),
            "base_units": unit,
            "closing_balance": qty,
            "closing_rate": rate,
            "closing_value": parse_amount(_get_text(item, "CLOSINGVALUE")),
        })
    return items
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_response_parser.py::test_parse_stock_items_extracts_fields -v`
Expected: PASS

- [x]**Step 5: Write failing test for parse_groups**

```python
def test_parse_groups_extracts_fields():
    xml = """<ENVELOPE><BODY><DATA><COLLECTION>
    <GROUP NAME="Sales Accounts">
        <NAME>Sales Accounts</NAME>
        <PARENT>Revenue</PARENT>
    </GROUP>
    <GROUP NAME="North Zone Debtors">
        <NAME>North Zone Debtors</NAME>
        <PARENT>Sundry Debtors</PARENT>
    </GROUP>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    groups = parse_groups(xml)
    assert len(groups) == 2
    assert groups[0]["name"] == "Sales Accounts"
    assert groups[0]["parent"] == "Revenue"
```

- [x]**Step 6: Implement parse_groups**

In `backend/tally_bridge/response_parser.py`, add:

```python
def parse_groups(raw_xml: str) -> list[dict]:
    """Parse CustomGroupList collection response."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    groups = []
    for group in root.iter("GROUP"):
        name = _get_text(group, "NAME") or group.get("NAME", "")
        if not name:
            continue
        groups.append({
            "name": name,
            "parent": _get_text(group, "PARENT"),
        })
    return groups
```

- [x]**Step 7: Run all parser tests**

Run: `pytest tests/unit/test_response_parser.py -v`
Expected: All PASS

- [x]**Step 8: Commit**

```bash
git add backend/tally_bridge/response_parser.py tests/unit/test_response_parser.py
git commit -m "feat: add parse_stock_items and parse_groups response parsers"
```

---

## Chunk 3: Inventory Allocations in Vouchers (H2)

This is the highest-value change — it unblocks all item-level sales/purchase analysis.

### Task 6: Add AllInventoryEntries to voucher requests

**Files:**
- Modify: `backend/tally_bridge/request_builder.py:56-61`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_request_builder.py — add
def test_voucher_native_methods_include_inventory_entries():
    """All voucher collection queries must fetch AllInventoryEntries for item-level data."""
    from backend.tally_bridge.request_builder import build_day_book
    xml = build_day_book("01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml

def test_sales_register_includes_inventory_entries():
    from backend.tally_bridge.request_builder import build_sales_register
    xml = build_sales_register("01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml

def test_ledger_vouchers_includes_inventory_entries():
    from backend.tally_bridge.request_builder import build_ledger_vouchers
    xml = build_ledger_vouchers("Cash", "01-10-2025", "31-10-2025")
    assert "AllInventoryEntries" in xml
```

- [x]**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_request_builder.py::test_voucher_native_methods_include_inventory_entries -v`
Expected: FAIL — `AllInventoryEntries` not in voucher fields

- [x]**Step 3: Add AllInventoryEntries to _voucher_native_methods()**

In `backend/tally_bridge/request_builder.py`, modify `_voucher_native_methods()`:

```python
def _voucher_native_methods() -> str:
    """Return NATIVEMETHOD elements for the specific voucher fields we need.
    Using * fetches ALL fields and can overload Tally with large datasets.
    """
    fields = ["Date", "VoucherTypeName", "VoucherNumber", "PartyLedgerName",
              "Narration", "AllLedgerEntries", "AllInventoryEntries"]
    return "\n".join(f"<NATIVEMETHOD>{f}</NATIVEMETHOD>" for f in fields)
```

- [x]**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_request_builder.py -v`
Expected: All PASS

- [x]**Step 5: Commit**

```bash
git add backend/tally_bridge/request_builder.py tests/unit/test_request_builder.py
git commit -m "feat: add AllInventoryEntries to voucher TDL queries (H2 part 1)"
```

### Task 7: Parse inventory allocations in parse_vouchers()

**Files:**
- Modify: `backend/tally_bridge/response_parser.py:280-317`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_response_parser.py — add
def test_parse_vouchers_extracts_inventory_entries():
    xml = """<ENVELOPE><BODY><DATA><COLLECTION>
    <VOUCHER>
        <DATE>20251001</DATE>
        <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
        <VOUCHERNUMBER>S001</VOUCHERNUMBER>
        <PARTYLEDGERNAME>Apex Technologies</PARTYLEDGERNAME>
        <NARRATION>Test sale</NARRATION>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Sales - Electronics</LEDGERNAME>
            <AMOUNT>-94000</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        <ALLINVENTORYENTRIES.LIST>
            <STOCKITEMNAME>HP Laptop 15s</STOCKITEMNAME>
            <ACTUALQTY>2 Nos</ACTUALQTY>
            <RATE>45000/Nos</RATE>
            <AMOUNT>-90000</AMOUNT>
        </ALLINVENTORYENTRIES.LIST>
        <ALLINVENTORYENTRIES.LIST>
            <STOCKITEMNAME>Logitech Wireless Mouse</STOCKITEMNAME>
            <ACTUALQTY>5 Nos</ACTUALQTY>
            <RATE>800/Nos</RATE>
            <AMOUNT>-4000</AMOUNT>
        </ALLINVENTORYENTRIES.LIST>
    </VOUCHER>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    from backend.tally_bridge.response_parser import parse_vouchers
    vouchers = parse_vouchers(xml)
    assert len(vouchers) == 1
    v = vouchers[0]
    assert "inventory_entries" in v
    assert len(v["inventory_entries"]) == 2
    assert v["inventory_entries"][0]["item_name"] == "HP Laptop 15s"
    assert v["inventory_entries"][0]["quantity"] == 2.0
    assert v["inventory_entries"][0]["rate"] == 45000.0
    assert v["inventory_entries"][0]["amount"] == -90000.0
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_response_parser.py::test_parse_vouchers_extracts_inventory_entries -v`
Expected: FAIL — `inventory_entries` key missing from voucher dict

- [x]**Step 3: Add inventory entry parsing to parse_vouchers()**

In `backend/tally_bridge/response_parser.py`, inside the `for v in root.iter("VOUCHER"):` loop, after the `ledger_entries` block (before the ghost voucher check), add:

```python
        inventory_entries = []
        for inv_entry in v.findall("ALLINVENTORYENTRIES.LIST"):
            item_name = _get_text(inv_entry, "STOCKITEMNAME")
            if not item_name:
                continue
            # Parse quantity: "2 Nos" → 2.0
            # Note: ACTUALQTY is signed (negative for sales outgoing, positive for purchases).
            # We take abs() because quantity is displayed as a positive number; the sign
            # is already conveyed by the amount field and voucher_type context.
            qty_text = _get_text(inv_entry, "ACTUALQTY")
            qty = 0.0
            if qty_text:
                parts = qty_text.split()
                if parts:
                    try:
                        qty = abs(float(parts[0].replace(",", "")))
                    except ValueError:
                        pass
            # Parse rate: "45000/Nos" → 45000.0
            rate_text = _get_text(inv_entry, "RATE")
            rate = 0.0
            if rate_text:
                rate_num = rate_text.split("/")[0].strip()
                rate = parse_amount(rate_num)
            inventory_entries.append({
                "item_name": item_name,
                "quantity": qty,
                "rate": rate,
                "amount": parse_amount(_get_text(inv_entry, "AMOUNT")),
            })
```

And add `"inventory_entries": inventory_entries,` to the vouchers.append() dict.

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_response_parser.py::test_parse_vouchers_extracts_inventory_entries -v`
Expected: PASS

- [x]**Step 5: Write backwards-compatibility test for vouchers without inventory entries**

```python
def test_parse_vouchers_without_inventory_entries_returns_empty_list():
    """Vouchers without ALLINVENTORYENTRIES should have an empty inventory_entries list."""
    xml = """<ENVELOPE><BODY><DATA><COLLECTION>
    <VOUCHER>
        <DATE>20251001</DATE>
        <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
        <VOUCHERNUMBER>PMT001</VOUCHERNUMBER>
        <PARTYLEDGERNAME>Rent</PARTYLEDGERNAME>
        <NARRATION>Office rent</NARRATION>
        <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Rent</LEDGERNAME>
            <AMOUNT>-75000</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    from backend.tally_bridge.response_parser import parse_vouchers
    vouchers = parse_vouchers(xml)
    assert len(vouchers) == 1
    assert vouchers[0]["inventory_entries"] == []
```

- [x]**Step 6: Run full unit test suite to check for regressions**

Run: `pytest tests/unit/ -v`
Expected: All PASS — existing voucher tests should not break because `inventory_entries` is a new additive field

- [x]**Step 7: Commit**

```bash
git add backend/tally_bridge/response_parser.py tests/unit/test_response_parser.py
git commit -m "feat: parse AllInventoryEntries in voucher responses (H2 part 2)"
```

### Task 8: Add inventory entries to mock voucher fixtures

**Files:**
- Modify: `tests/fixtures/generate_fixtures.py`

- [x]**Step 1: Update generate_fixtures.py to include inventory entries in sales/purchase vouchers**

In the `generate_sales_register()` function, add `ALLINVENTORYENTRIES.LIST` elements for each item in each sales invoice. The data is already available in `SALES_INVOICES` — each tuple has `[(item, qty, rate)]`.

Add this helper function. Build a UOM lookup from STOCK_ITEMS so each item uses
its actual unit (e.g. "Nos" for electronics, "Pcs" for paper):

```python
# Build UOM lookup from STOCK_ITEMS: {item_name: uom}
_ITEM_UOM = {name: uom for name, _group, uom, *_ in STOCK_ITEMS}

def _inventory_entries_xml(items: list[tuple], voucher_type: str) -> str:
    """Generate ALLINVENTORYENTRIES.LIST XML for a list of (item_name, qty, rate) tuples."""
    entries = []
    for item_name, qty, rate in items:
        uom = _ITEM_UOM.get(item_name, "Nos")
        amount = qty * rate
        # Sales = negative amount (outgoing stock), Purchase = positive
        if voucher_type == "Sales":
            amount = -amount
        entries.append(f"""<ALLINVENTORYENTRIES.LIST>
<STOCKITEMNAME>{item_name}</STOCKITEMNAME>
<ACTUALQTY>{qty} {uom}</ACTUALQTY>
<RATE>{rate}/{uom}</RATE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLINVENTORYENTRIES.LIST>""")
    return "\n".join(entries)
```

Then in each `<VOUCHER>` element for sales and purchase, insert the inventory entries XML after the `ALLLEDGERENTRIES.LIST` elements.

- [x]**Step 2: Regenerate fixtures**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && python tests/fixtures/generate_fixtures.py`

- [x]**Step 3: Verify fixtures contain inventory entries**

```bash
grep -c "ALLINVENTORYENTRIES" tests/fixtures/sales_register.xml
grep -c "ALLINVENTORYENTRIES" tests/fixtures/purchase_register.xml
grep -c "ALLINVENTORYENTRIES" tests/fixtures/day_book.xml
```
Expected: Non-zero counts for sales and purchase registers

- [x]**Step 4: Run integration tests to verify mock still works**

Run: `pytest tests/integration/ -v`
Expected: All PASS

- [x]**Step 5: Commit**

```bash
git add tests/fixtures/generate_fixtures.py tests/fixtures/sales_register.xml tests/fixtures/purchase_register.xml tests/fixtures/day_book.xml
git commit -m "feat: add inventory allocation entries to mock voucher fixtures (H2 part 3)"
```

---

## Chunk 4: New Query Functions & Tools (H1, H3, M3)

### Task 9: Add list_stock_items query function (H1)

**Files:**
- Modify: `backend/tally_bridge/queries/masters.py`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_masters_query.py — add or create
import pytest
from unittest.mock import AsyncMock, patch
from backend.tally_bridge.queries.masters import list_stock_items

@pytest.mark.asyncio
async def test_list_stock_items_returns_stock_item_list():
    mock_client = AsyncMock()
    mock_client.post_xml.return_value = """<ENVELOPE><BODY><DATA><COLLECTION>
    <STOCKITEM><NAME>HP Laptop</NAME><PARENT>Electronics</PARENT>
    <BASEUNITS>Nos</BASEUNITS><CLOSINGBALANCE>10 Nos</CLOSINGBALANCE>
    <CLOSINGRATE>38000/Nos</CLOSINGRATE><CLOSINGVALUE>380000</CLOSINGVALUE></STOCKITEM>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    items = await list_stock_items(mock_client)
    assert len(items) == 1
    assert items[0].name == "HP Laptop"
    assert items[0].parent_group == "Electronics"
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_masters_query.py::test_list_stock_items_returns_stock_item_list -v`
Expected: FAIL — `list_stock_items` not defined

- [x]**Step 3: Implement list_stock_items**

In `backend/tally_bridge/queries/masters.py`, add:

```python
from backend.tally_bridge.request_builder import build_list_stock_items, build_list_groups
from backend.tally_bridge.response_parser import parse_stock_items, parse_groups
from backend.tally_bridge.models import StockItem, AccountGroup

async def list_stock_items(client: TallyClient) -> list[StockItem]:
    """Fetch all stock items with parent group, UOM, and closing values."""
    raw = await client.post_xml(build_list_stock_items())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_stock_items(raw)
    return [StockItem(**row) for row in parsed]
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_masters_query.py::test_list_stock_items_returns_stock_item_list -v`
Expected: PASS

- [x]**Step 5: Commit**

```bash
git add backend/tally_bridge/queries/masters.py tests/unit/test_masters_query.py
git commit -m "feat: add list_stock_items query function (H1 part 1)"
```

### Task 10: Add list_groups query function (M3)

**Files:**
- Modify: `backend/tally_bridge/queries/masters.py`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_masters_query.py — add
@pytest.mark.asyncio
async def test_list_groups_returns_group_list():
    mock_client = AsyncMock()
    mock_client.post_xml.return_value = """<ENVELOPE><BODY><DATA><COLLECTION>
    <GROUP><NAME>Sales Accounts</NAME><PARENT>Revenue</PARENT></GROUP>
    </COLLECTION></DATA></BODY></ENVELOPE>"""
    from backend.tally_bridge.queries.masters import list_groups
    groups = await list_groups(mock_client)
    assert len(groups) == 1
    assert groups[0].name == "Sales Accounts"
    assert groups[0].parent == "Revenue"
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_masters_query.py::test_list_groups_returns_group_list -v`
Expected: FAIL

- [x]**Step 3: Implement list_groups**

```python
async def list_groups(client: TallyClient) -> list[AccountGroup]:
    """Fetch all account groups with parent hierarchy."""
    raw = await client.post_xml(build_list_groups())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_groups(raw)
    return [AccountGroup(**row) for row in parsed]
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_masters_query.py -v`
Expected: All PASS

- [x]**Step 5: Commit**

```bash
git add backend/tally_bridge/queries/masters.py tests/unit/test_masters_query.py
git commit -m "feat: add list_groups query function (M3 part 1)"
```

### Task 11: Add tool schemas and handlers for H1, H3, M3

**Files:**
- Modify: `backend/agents/tools.py`

- [x]**Step 1: Write failing tests for new tools**

```python
# tests/unit/test_tools.py — add
from backend.agents.tools import TALLY_TOOLS, TOOL_HANDLERS

def test_list_stock_items_tool_exists():
    names = [t["name"] for t in TALLY_TOOLS]
    assert "list_stock_items" in names

def test_list_all_ledgers_tool_exists():
    names = [t["name"] for t in TALLY_TOOLS]
    assert "list_all_ledgers" in names

def test_list_account_groups_tool_exists():
    names = [t["name"] for t in TALLY_TOOLS]
    assert "list_account_groups" in names

def test_new_tools_have_handlers():
    for name in ["list_stock_items", "list_all_ledgers", "list_account_groups"]:
        assert name in TOOL_HANDLERS, f"Missing handler for {name}"
```

- [x]**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tools.py::test_list_stock_items_tool_exists -v`
Expected: FAIL

- [x]**Step 3: Add tool schemas**

In `backend/agents/tools.py`, add to `TALLY_TOOLS` list:

```python
    {
        "name": "list_all_ledgers",
        "description": "List all ledger accounts in TallyPrime. Returns every ledger with its name, parent group, opening balance, and closing balance. Use this to discover all available ledger names or for top-N-by-balance queries.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_stock_items",
        "description": "List all stock/inventory items in TallyPrime with their stock group, unit of measure (UOM), closing quantity, rate, and value. Use this instead of get_stock_summary when you need stock group or UOM information.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_account_groups",
        "description": "List all account groups in TallyPrime with their parent group. Returns the full chart of accounts group hierarchy (e.g. Sales Accounts → Revenue, Bank Accounts → Current Assets).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
```

- [x]**Step 4: Add handler functions**

```python
async def _handle_list_all_ledgers(client: TallyClient, **kwargs: Any) -> Any:
    result = await masters.list_ledgers(client)
    return [l.model_dump(mode="json") for l in result]


async def _handle_list_stock_items(client: TallyClient, **kwargs: Any) -> Any:
    result = await masters.list_stock_items(client)
    return [s.model_dump(mode="json") for s in result]


async def _handle_list_account_groups(client: TallyClient, **kwargs: Any) -> Any:
    result = await masters.list_groups(client)
    return [g.model_dump(mode="json") for g in result]
```

- [x]**Step 5: Add to TOOL_HANDLERS dict**

```python
"list_all_ledgers": _handle_list_all_ledgers,
"list_stock_items": _handle_list_stock_items,
"list_account_groups": _handle_list_account_groups,
```

- [x]**Step 6: Update EXPECTED_TOOL_NAMES and count assertion in test_tools.py**

The existing test at `tests/unit/test_tools.py:15-28` has `EXPECTED_TOOL_NAMES` (12 items) and
line 88 asserts `len(TALLY_TOOLS) == 12`. These MUST be updated or the test suite will break.

Add `"list_all_ledgers"`, `"list_stock_items"`, `"list_account_groups"` to `EXPECTED_TOOL_NAMES`.
Update the count assertion to match the new total (will be 15 after this task, 18 after Task 12+13).

- [x]**Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_tools.py -v`
Expected: All PASS

- [x]**Step 8: Commit**

```bash
git add backend/agents/tools.py tests/unit/test_tools.py
git commit -m "feat: add list_all_ledgers, list_stock_items, list_account_groups tools (H1, H3, M3)"
```

---

## Chunk 5: Payment/Receipt Register Tools & Cash Flow (M1, M2)

### Task 12: Add dedicated payment and receipt register tools (M1)

**Files:**
- Modify: `backend/agents/tools.py`

- [x]**Step 1: Write the failing test**

```python
# tests/unit/test_tools.py — add
def test_payment_register_tool_exists():
    names = [t["name"] for t in TALLY_TOOLS]
    assert "get_payment_register" in names

def test_receipt_register_tool_exists():
    names = [t["name"] for t in TALLY_TOOLS]
    assert "get_receipt_register" in names
```

- [x]**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tools.py::test_payment_register_tool_exists -v`
Expected: FAIL

- [x]**Step 3: Add tool schemas**

In `backend/agents/tools.py`, add to `TALLY_TOOLS`:

```python
    {
        "name": "get_payment_register",
        "description": "Fetch all Payment vouchers from TallyPrime for a date range. Returns payment entries with payee, bank/cash account, amount, and narration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in DD-MM-YYYY format",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in DD-MM-YYYY format",
                },
                "company": {
                    "type": "string",
                    "description": "Company name in Tally. Optional — uses active company if omitted.",
                },
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_receipt_register",
        "description": "Fetch all Receipt vouchers from TallyPrime for a date range. Returns receipt entries with payer, bank/cash account, amount, and narration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in DD-MM-YYYY format",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in DD-MM-YYYY format",
                },
                "company": {
                    "type": "string",
                    "description": "Company name in Tally. Optional — uses active company if omitted.",
                },
            },
            "required": ["from_date", "to_date"],
        },
    },
```

- [x]**Step 4: Add handler functions**

These reuse the day_book query with a fixed voucher_type:

```python
async def _handle_payment_register(client: TallyClient, **kwargs: Any) -> Any:
    return await vouchers.day_book(
        client, kwargs["from_date"], kwargs["to_date"], "Payment", kwargs.get("company")
    )


async def _handle_receipt_register(client: TallyClient, **kwargs: Any) -> Any:
    return await vouchers.day_book(
        client, kwargs["from_date"], kwargs["to_date"], "Receipt", kwargs.get("company")
    )
```

- [x]**Step 5: Add to TOOL_HANDLERS**

```python
"get_payment_register": _handle_payment_register,
"get_receipt_register": _handle_receipt_register,
```

- [x]**Step 6: Update EXPECTED_TOOL_NAMES, DATE_RANGE_TOOLS, and count assertion**

Add `"get_payment_register"` and `"get_receipt_register"` to `EXPECTED_TOOL_NAMES` and
`DATE_RANGE_TOOLS` in `tests/unit/test_tools.py`. Update the count assertion to 17.

- [x]**Step 7: Run tests**

Run: `pytest tests/unit/test_tools.py -v`
Expected: All PASS

- [x]**Step 8: Commit**

```bash
git add backend/agents/tools.py tests/unit/test_tools.py
git commit -m "feat: add dedicated get_payment_register and get_receipt_register tools (M1)"
```

### Task 13: Add Cash Flow Statement (M2)

**Files:**
- Modify: `backend/tally_bridge/request_builder.py`
- Modify: `backend/tally_bridge/response_parser.py`
- Modify: `backend/tally_bridge/queries/reports.py`
- Modify: `backend/agents/tools.py`

- [x]**Step 1: Write failing test for request builder**

```python
# tests/unit/test_request_builder.py — add
def test_build_cash_flow_has_report_id():
    from backend.tally_bridge.request_builder import build_cash_flow
    xml = build_cash_flow("01-04-2025", "31-03-2026")
    assert "Cash Flow" in xml
    assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
```

- [x]**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_request_builder.py::test_build_cash_flow_has_report_id -v`
Expected: FAIL

- [x]**Step 3: Add build_cash_flow to request_builder.py**

```python
def build_cash_flow(from_date: str, to_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Cash Flow", from_date, to_date, company)
```

- [x]**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_request_builder.py::test_build_cash_flow_has_report_id -v`
Expected: PASS

- [x]**Step 5: Write failing test for parser**

The Cash Flow report from Tally uses the same alternating sibling structure as P&L (DSPACCNAME + DSPACCINFO or similar). We reuse `parse_trial_balance` structure since cash flow has the same DSPACCNAME/DSPACCINFO pattern.

```python
# tests/unit/test_response_parser.py — add
def test_parse_cash_flow_extracts_rows():
    """Cash Flow report uses same sibling-pair structure as Trial Balance."""
    from backend.tally_bridge.response_parser import parse_cash_flow
    xml = """<ENVELOPE><DSPACCNAME><DSPDISPNAME>Cash from Operating Activities</DSPDISPNAME></DSPACCNAME>
    <DSPACCINFO><DSPCLDRAMT><DSPCLDRAMTA>150000</DSPCLDRAMTA></DSPCLDRAMT><DSPCLCRAMT><DSPCLCRAMTA>0</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO></ENVELOPE>"""
    rows = parse_cash_flow(xml)
    assert len(rows) == 1
    assert rows[0]["account_name"] == "Cash from Operating Activities"
```

- [x]**Step 6: Implement parse_cash_flow**

```python
def parse_cash_flow(raw_xml: str) -> list[dict]:
    """Parse Cash Flow report — assumed same sibling-pair structure as Trial Balance.

    TODO: Validate against live Tally instance. The actual Cash Flow XML structure
    may differ from Trial Balance. This is a separate function (not just an alias)
    so it can be adjusted independently after live testing.
    """
    return parse_trial_balance(raw_xml)
```

- [x]**Step 7: Add query function in reports.py**

```python
async def cash_flow(
    client: TallyClient,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> ReportResponse:
    """Fetch Cash Flow statement."""
    raw = await client.post_xml(build_cash_flow(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = parse_cash_flow(raw)
    return ReportResponse(
        report_name="Cash Flow",
        company=company or "",
        from_date=datetime.strptime(from_date, "%d-%m-%Y").date(),
        to_date=datetime.strptime(to_date, "%d-%m-%Y").date(),
        rows=rows,
    )
```

Add necessary imports:
```python
from backend.tally_bridge.request_builder import build_cash_flow
from backend.tally_bridge.response_parser import parse_cash_flow
```

- [x]**Step 8: Add tool schema and handler**

Tool schema:
```python
    {
        "name": "get_cash_flow",
        "description": "Fetch the Cash Flow Statement from TallyPrime for a date range. Returns cash flows from operating, investing, and financing activities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date in DD-MM-YYYY format",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date in DD-MM-YYYY format",
                },
                "company": {
                    "type": "string",
                    "description": "Company name in Tally. Optional — uses active company if omitted.",
                },
            },
            "required": ["from_date", "to_date"],
        },
    },
```

Handler:
```python
async def _handle_cash_flow(client: TallyClient, **kwargs: Any) -> Any:
    result = await reports.cash_flow(
        client, kwargs["from_date"], kwargs["to_date"], kwargs.get("company")
    )
    return result.model_dump(mode="json")
```

Add to TOOL_HANDLERS: `"get_cash_flow": _handle_cash_flow,`

- [x]**Step 9: Update EXPECTED_TOOL_NAMES, DATE_RANGE_TOOLS, and count assertion**

Add `"get_cash_flow"` to `EXPECTED_TOOL_NAMES` and `DATE_RANGE_TOOLS` in `tests/unit/test_tools.py`.
Update the count assertion to **18** (final total).

- [x]**Step 10: Run all tests**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [x]**Step 11: Commit**

```bash
git add backend/tally_bridge/request_builder.py backend/tally_bridge/response_parser.py backend/tally_bridge/queries/reports.py backend/agents/tools.py tests/unit/
git commit -m "feat: add Cash Flow Statement tool (M2)"
```

---

## Chunk 6: Mock Fixtures & Integration Tests

### Task 14: Generate mock fixtures for new query types

**Files:**
- Modify: `tests/fixtures/generate_fixtures.py`
- Modify: `backend/tally_bridge/mock_handler.py`

- [x]**Step 1: Add generate_stock_items_list() to generate_fixtures.py**

Note: This uses opening values from STOCK_ITEMS (not computed closing values like
`generate_stock_summary()` does). This is acceptable because TYPE=Collection master
queries return static master data, not date-dependent summaries. Add a comment noting this.

```python
def generate_stock_items_list() -> str:
    """Generate CustomStockItemList fixture from STOCK_ITEMS opening data.

    Note: Uses opening values (not computed closing). TYPE=Collection master
    queries return static item attributes, not date-dependent balances.
    """
    items_xml = []
    for name, group, uom, _sell_rate, open_qty, open_rate, open_value in STOCK_ITEMS:
        items_xml.append(f"""<STOCKITEM NAME="{name}">
<NAME>{name}</NAME>
<PARENT>{group}</PARENT>
<BASEUNITS>{uom}</BASEUNITS>
<CLOSINGBALANCE>{open_qty} {uom}</CLOSINGBALANCE>
<CLOSINGRATE>{open_rate}/{uom}</CLOSINGRATE>
<CLOSINGVALUE>{open_value:.2f}</CLOSINGVALUE>
</STOCKITEM>""")
    return f"""<ENVELOPE><BODY><DATA><COLLECTION>
{"".join(items_xml)}
</COLLECTION></DATA></BODY></ENVELOPE>"""
```

Call it in `main()` and write to `stock_items_list.xml`.

- [x]**Step 2: Add generate_groups_list() to generate_fixtures.py**

```python
# Unique groups from LEDGERS + stock groups
ACCOUNT_GROUPS = [
    ("North Zone Debtors", "Sundry Debtors"),
    ("South Zone Debtors", "Sundry Debtors"),
    ("Sundry Debtors", "Current Assets"),
    ("National Creditors", "Sundry Creditors"),
    ("Local Creditors", "Sundry Creditors"),
    ("Sundry Creditors", "Current Liabilities"),
    ("Bank Accounts", "Current Assets"),
    ("Cash-in-Hand", "Current Assets"),
    ("Sales Accounts", "Revenue"),
    ("Purchase Accounts", "Expenses"),
    ("Indirect Expenses", "Expenses"),
    ("Direct Expenses", "Expenses"),
    ("Duties & Taxes", "Current Liabilities"),
    ("Capital Account", "Capital Account"),
    ("Current Assets", "Assets"),
    ("Current Liabilities", "Liabilities"),
    ("Revenue", "Income"),
    ("Expenses", "Expenditure"),
    ("Electronics", "Stock-in-Hand"),
    ("Peripherals", "Stock-in-Hand"),
    ("Office Supplies", "Stock-in-Hand"),
    ("Stock-in-Hand", "Current Assets"),
]

def generate_groups_list() -> str:
    groups_xml = []
    for name, parent in ACCOUNT_GROUPS:
        groups_xml.append(f"""<GROUP NAME="{name}">
<NAME>{name}</NAME>
<PARENT>{parent}</PARENT>
</GROUP>""")
    return f"""<ENVELOPE><BODY><DATA><COLLECTION>
{"".join(groups_xml)}
</COLLECTION></DATA></BODY></ENVELOPE>"""
```

Call it in `main()` and write to `groups_list.xml`.

- [x]**Step 3: Regenerate all fixtures**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && python tests/fixtures/generate_fixtures.py`

- [x]**Step 4: Add mock handler entries**

In `backend/tally_bridge/mock_handler.py`, add to `STATIC_FIXTURES`:

```python
"CustomStockItemList": "stock_items_list.xml",
"CustomGroupList": "groups_list.xml",
```

And add `"Cash Flow"` to `DATE_AWARE_REPORTS` or `STATIC_FIXTURES` (static is simpler for now):

```python
"Cash Flow": "cash_flow.xml",  # Will need a fixture
```

Or alternatively, handle Cash Flow in `DATE_AWARE_REPORTS` and add a generation function. Since Cash Flow is date-dependent in real Tally, but for mock purposes a static fixture is fine:

Add `"Cash Flow"` to `STATIC_FIXTURES` with a `cash_flow.xml` fixture generated from fixture data.

- [x]**Step 5: Generate cash_flow.xml fixture**

Add `generate_cash_flow()` to `generate_fixtures.py`:

```python
def generate_cash_flow() -> str:
    """Generate a simple Cash Flow fixture using Trial Balance structure."""
    return """<ENVELOPE>
<DSPACCNAME><DSPDISPNAME>Cash from Operating Activities</DSPDISPNAME></DSPACCNAME>
<DSPACCINFO><DSPCLDRAMT><DSPCLDRAMTA>-450000.00</DSPCLDRAMTA></DSPCLDRAMT><DSPCLCRAMT><DSPCLCRAMTA>0</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO>
<DSPACCNAME><DSPDISPNAME>Cash from Investing Activities</DSPDISPNAME></DSPACCNAME>
<DSPACCINFO><DSPCLDRAMT><DSPCLDRAMTA>0</DSPCLDRAMTA></DSPCLDRAMT><DSPCLCRAMT><DSPCLCRAMTA>0</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO>
<DSPACCNAME><DSPDISPNAME>Cash from Financing Activities</DSPDISPNAME></DSPACCNAME>
<DSPACCINFO><DSPCLDRAMT><DSPCLDRAMTA>0</DSPCLDRAMTA></DSPCLDRAMT><DSPCLCRAMT><DSPCLCRAMTA>750000.00</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO>
</ENVELOPE>"""
```

- [x]**Step 6: Run regeneration and integration tests**

Run: `python tests/fixtures/generate_fixtures.py && pytest tests/integration/ -v`
Expected: All PASS

- [x]**Step 7: Commit**

```bash
git add tests/fixtures/ backend/tally_bridge/mock_handler.py
git commit -m "feat: add mock fixtures for stock items, groups, cash flow, and inventory entries"
```

### Task 15: Run full test suite and fix regressions

- [x]**Step 1: Run full backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/`
Expected: All tests PASS (641+ tests)

- [x]**Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: 111 tests PASS (frontend unchanged)

- [x]**Step 3: Fix any regressions**

If any tests fail due to the new `inventory_entries` field in voucher dicts, update assertions in affected tests to account for the new field.

- [x]**Step 4: Final commit (if regressions were found)**

Stage only the specific files that were fixed — never use `git add -A` (risks staging
`.env`, `.DS_Store`, or other unintended files).

```bash
git add <specific files that were changed to fix regressions>
git commit -m "fix: resolve regressions from gap closure changes"
```

---

## Summary

| Gap | Task(s) | New Tools | Est. Lines Changed |
|-----|---------|-----------|-------------------|
| M5 (P&L prompt) | 1 | 0 | ~20 |
| H4 + M4 (overdue_days + descriptions) | 3 | 0 | ~40 |
| Models (StockItem, AccountGroup) | 4 | 0 | ~15 |
| Parsers (stock_items, groups) | 5 | 0 | ~55 |
| H2 (inventory allocations) | 6, 7, 8 | 0 | ~70 |
| H1 (list_stock_items) | 9, 11 | 1 | ~25 |
| H3 (list_all_ledgers) | 11 | 1 | ~15 |
| M3 (list_account_groups) | 10, 11 | 1 | ~25 |
| M1 (payment/receipt) | 12 | 2 | ~45 |
| M2 (cash flow) | 13 | 1 | ~65 |
| Mock fixtures | 14 | 0 | ~90 |
| Regression check | 15 | 0 | ~10 |
| **Total** | **14 tasks** | **6 new tools** | **~475 lines** |

After completion: **18 Tally tools + 1 date tool = 19 tools** (up from 12+1=13).

---

## Review History

**Chunk 1 review** — Identified: M4 premature (merged into Task 3), voucher type test
incomplete (fixed: all 8 types), P&L HTTP cost not documented (fixed: ~23 requests note),
test assertion hyphen mismatch (fixed), due_date not passed through reports.py (fixed in Task 3).

**Chunks 2-6 review** — Identified: C1 reports.py not passing overdue_days (fixed: Steps 8-10
added to Task 3), C3 git add -A unsafe (fixed: explicit staging), I1 overdue_days edge case
(fixed: _parse_overdue_days helper), I2 CLOSINGBALANCE format (noted in parser docstring),
I3 abs() quantity (documented design decision), I4 Cash Flow format assumption (TODO added),
I5 EXPECTED_TOOL_NAMES count (fixed: update steps in Tasks 11, 12, 13), I6 UOM hardcoding
(fixed: _ITEM_UOM lookup), S1 TDD ordering (fixed: test before implementation), S3 backwards-compat
test (added), S4 opening vs closing values (noted in docstring).

---

## Post-Implementation Notes

### Eval Coverage Gaps
The following new tools are NOT yet covered by mock eval scenarios:
- `list_stock_items` — no eval turn exercises this tool
- `list_account_groups` — no eval turn exercises this tool
- `get_cash_flow` — existing cash flow turns use day_book filtering, not the dedicated tool
- `get_payment_register` / `get_receipt_register` — no dedicated eval turns

**Action**: New eval turns being added to `financial_deep_dive_mock.yaml` to close these gaps.

### Code Review Findings (from `docs/code-review-phase11.md`)
- **I1/I2**: XML-escaping missing in fixture generator for stock item names (test-only, low risk)
- **S1**: Cash flow parser delegates to trial_balance parser — needs live Tally validation
- **S2**: Quantity/rate parsing logic duplicated across 3 parser functions
- **S3**: Master list tools lack optional `company` parameter

### Test Coverage
- Overall: 95% (1764 statements, 91 missed)
- New modules fully covered: models.py (100%), prompts.py (100%)
- Lower coverage areas: masters.py (82%), reports.py (85%) — error paths
