# Enriched Mock Tally & Eval Improvements — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich demo company fixture data to match the full TALLYPRIME_AGENT_PLAN.md seed data spec, make the mock handler date-aware so it returns format-identical responses to live Tally, create mock-specific eval scenarios, and add live-vs-mock format comparison tests.

**Architecture:** Replace thin fixture files (3 ledgers, 2 sales, 2 day-book entries) with complete Bharat Traders data (30+ ledgers, 16 sales, 8 purchases, 16 payments, 10 receipts, 15 stock items). Upgrade `mock_handler.py` from simple string-matching to date-aware XML parsing that computes cumulative P&L/TB from voucher data — matching real Tally's behavior. Create `*_mock.yaml` scenario variants for eval turns that reference live-only entities (HCODE, Q1/Q2 data).

**Tech Stack:** Python, XML (ElementTree), pytest, YAML, existing Tally XML format conventions

---

## File Structure

### Fixtures to Replace (tests/fixtures/)
| File | Current | After |
|------|---------|-------|
| `ledger_list.xml` | 3 ledgers | 30+ ledgers (7 debtors, 5 creditors, 3 bank/cash, 2 sales, 2 purchase, 8 expense, 6 GST, 1 capital) |
| `sales_register.xml` | 2 vouchers (Oct) | 16 invoices (Oct 2025 – Mar 2026, 7 customers) |
| `purchase_register.xml` | 10 vouchers (different vendors) | 8 invoices matching plan (Sep 2025 – Feb 2026, 5 suppliers) |
| `day_book.xml` | 2 vouchers | ~50 vouchers (16 sales + 8 purchases + 16 payments + 10 receipts) |
| `bills_receivable.xml` | 2 HCODE bills | 7+ parties with outstanding amounts |
| `stock_summary.xml` | 5 IT service items | 15 electronics/peripherals/office supply items |
| `profit_and_loss.xml` | Static full-FY | Full-FY P&L consistent with voucher totals |
| `trial_balance.xml` | 7 groups | Expanded with correct totals from voucher data |
| `balance_sheet.xml` | 7 items | Consistent with updated TB and P&L |

### New Files to Create
| File | Purpose |
|------|---------|
| `tests/fixtures/bills_payable.xml` | Separate payable fixture (5 suppliers) |
| `tests/fixtures/generate_fixtures.py` | Script to generate all fixtures from plan data constants |
| `tests/eval/scenarios/manual_test_regression_mock.yaml` | Mock variant of manual_test_regression |
| `tests/eval/scenarios/edge_case_gauntlet_mock.yaml` | Mock variant of edge_case_gauntlet |
| `tests/eval/scenarios/trends_and_breakdowns_mock.yaml` | Mock variant of trends_and_breakdowns |
| `tests/eval/scenarios/financial_deep_dive_mock.yaml` | Mock variant of financial_deep_dive |
| `tests/integration/test_mock_format_parity.py` | Tests that mock responses parse identically to live format |

### Files to Modify
| File | Changes |
|------|---------|
| `backend/tally_bridge/mock_handler.py` | Add date-aware XML parsing, compute cumulative P&L/TB from voucher data |
| `tests/eval/collect.py` | Auto-select `*_mock.yaml` scenario variant when `--tally-mode mock` |
| `tests/mocks/mock_tally_server.py` | Verify it still delegates to mock_handler correctly |

---

## Chunk 1: Fixture Generator Script & Enriched Voucher Data

### Task 1: Create fixture generator with plan data constants

**Files:**
- Create: `tests/fixtures/generate_fixtures.py`

This script is the single source of truth for all fixture data. It contains the exact data from TALLYPRIME_AGENT_PLAN.md and generates all XML fixture files.

- [ ] **Step 1: Write the data constants module**

Create `tests/fixtures/generate_fixtures.py` with all seed data from the plan:

```python
#!/usr/bin/env python3
"""Generate all Tally fixture XML files from TALLYPRIME_AGENT_PLAN.md seed data.

Run: python tests/fixtures/generate_fixtures.py
Outputs: All .xml fixture files in tests/fixtures/

This is the single source of truth. Edit data here, re-run to regenerate.
"""
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

# ── Company ─────────────────────────────────────────────────────────
COMPANY_NAME = "Bharat Traders Pvt Ltd"

# ── Ledgers (30+) ──────────────────────────────────────────────────
# (name, parent_group, opening_balance)
# Negative opening_balance = debit in Tally convention
LEDGERS = [
    # Debtors (7)
    ("Apex Technologies Pvt Ltd", "North Zone Debtors", 0),
    ("Sunrise Electronics Mumbai", "South Zone Debtors", 0),
    ("Global IT Solutions", "North Zone Debtors", 0),
    ("Sharma & Sons Traders", "South Zone Debtors", 0),
    ("Patel Enterprises", "North Zone Debtors", 0),
    ("Rajesh Computers", "South Zone Debtors", 0),
    ("Eastern Digital Hub", "North Zone Debtors", 0),
    # Creditors (5)
    ("Samsung India Electronics", "National Creditors", 0),
    ("HP India Sales Pvt Ltd", "National Creditors", 0),
    ("Logitech India Pvt Ltd", "National Creditors", 0),
    ("Local Stationery Mart", "Local Creditors", 0),
    ("Bharat Paper Supplies", "Local Creditors", 0),
    # Bank & Cash (3)
    ("HDFC Bank - Current A/c", "Bank Accounts", -500000),
    ("SBI Savings A/c", "Bank Accounts", -200000),
    ("Cash", "Cash-in-Hand", -50000),
    # Revenue (2)
    ("Sales - Electronics", "Sales Accounts", 0),
    ("Sales - Office Supplies", "Sales Accounts", 0),
    # Purchase (2)
    ("Purchase - Electronics", "Purchase Accounts", 0),
    ("Purchase - Office Supplies", "Purchase Accounts", 0),
    # Expenses (8)
    ("Rent", "Indirect Expenses", 0),
    ("Salaries", "Indirect Expenses", 0),
    ("Electricity", "Indirect Expenses", 0),
    ("Internet & Phone", "Indirect Expenses", 0),
    ("Office Maintenance", "Indirect Expenses", 0),
    ("Travel & Conveyance", "Indirect Expenses", 0),
    ("Courier & Freight", "Direct Expenses", 0),
    ("Packing Charges", "Direct Expenses", 0),
    # Tax (6)
    ("CGST Output", "Duties & Taxes", 0),
    ("SGST Output", "Duties & Taxes", 0),
    ("IGST Output", "Duties & Taxes", 0),
    ("CGST Input", "Duties & Taxes", 0),
    ("SGST Input", "Duties & Taxes", 0),
    ("IGST Input", "Duties & Taxes", 0),
    # Capital (1)
    ("Capital Account", "Capital Account", 750000),
]

# ── Stock Items (15) ───────────────────────────────────────────────
# (name, group, uom, selling_rate, opening_qty, opening_rate, opening_value)
STOCK_ITEMS = [
    # Electronics (5)
    ("Samsung 24 inch Monitor", "Electronics", "Nos", 12500, 20, 11000, 220000),
    ("HP Laptop 15s", "Electronics", "Nos", 45000, 10, 38000, 380000),
    ("Samsung Galaxy Tab A8", "Electronics", "Nos", 16000, 15, 13500, 202500),
    ("Dell Desktop Optiplex", "Electronics", "Nos", 35000, 8, 29000, 232000),
    ("Lenovo Ideapad Slim 3", "Electronics", "Nos", 42000, 12, 36000, 432000),
    # Peripherals (5)
    ("Logitech Wireless Mouse", "Peripherals", "Nos", 800, 100, 550, 55000),
    ("Logitech Keyboard K380", "Peripherals", "Nos", 2500, 60, 1800, 108000),
    ("HP DeskJet Printer 2723", "Peripherals", "Nos", 5500, 10, 4200, 42000),
    ("TP-Link WiFi Router AC750", "Peripherals", "Nos", 1800, 25, 1300, 32500),
    ("USB-C Hub 7-in-1", "Peripherals", "Nos", 1500, 40, 950, 38000),
    # Office Supplies (5)
    ("A4 Paper Ream 500 sheets", "Office Supplies", "Pcs", 350, 200, 280, 56000),
    ("Whiteboard Marker Set", "Office Supplies", "Pcs", 250, 50, 180, 9000),
    ("Stapler Heavy Duty", "Office Supplies", "Nos", 450, 30, 320, 9600),
    ("Box File Pack of 10", "Office Supplies", "Pcs", 600, 40, 420, 16800),
    ("Pen Drive 32GB", "Office Supplies", "Nos", 400, 80, 280, 22400),
]

# ── Sales Invoices (16) ────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, party, [(item, qty, rate)], total, narration)
# Ledger routing: Office Supplies items → "Sales - Office Supplies", rest → "Sales - Electronics"
OFFICE_SUPPLY_ITEMS = {"A4 Paper Ream 500 sheets", "Whiteboard Marker Set", "Stapler Heavy Duty", "Box File Pack of 10", "Pen Drive 32GB"}

SALES_INVOICES = [
    ("S001", "20251001", "Apex Technologies Pvt Ltd",
     [("HP Laptop 15s", 2, 45000), ("Logitech Wireless Mouse", 5, 800)], 94000,
     "Invoice #S001 - Laptops and peripherals"),
    ("S002", "20251008", "Sunrise Electronics Mumbai",
     [("Samsung 24 inch Monitor", 5, 12500), ("Samsung Galaxy Tab A8", 3, 16000)], 110500,
     "Invoice #S002 - Samsung products"),
    ("S003", "20251015", "Global IT Solutions",
     [("Dell Desktop Optiplex", 3, 35000), ("Logitech Keyboard K380", 10, 2500)], 130000,
     "Invoice #S003 - Desktops and keyboards"),
    ("S004", "20251022", "Sharma & Sons Traders",
     [("A4 Paper Ream 500 sheets", 50, 350), ("Box File Pack of 10", 20, 600)], 29500,
     "Invoice #S004 - Office supplies"),
    ("S005", "20251030", "Patel Enterprises",
     [("Lenovo Ideapad Slim 3", 4, 42000), ("USB-C Hub 7-in-1", 8, 1500)], 180000,
     "Invoice #S005 - Laptops and hubs"),
    ("S006", "20251105", "Rajesh Computers",
     [("HP DeskJet Printer 2723", 3, 5500), ("TP-Link WiFi Router AC750", 5, 1800)], 25500,
     "Invoice #S006 - Printers and routers"),
    ("S007", "20251115", "Eastern Digital Hub",
     [("Samsung 24 inch Monitor", 8, 12500), ("Logitech Wireless Mouse", 20, 800)], 116000,
     "Invoice #S007 - Monitors and mice"),
    ("S008", "20251125", "Apex Technologies Pvt Ltd",
     [("Samsung Galaxy Tab A8", 5, 16000), ("Pen Drive 32GB", 20, 400)], 88000,
     "Invoice #S008 - Tablets and storage"),
    ("S009", "20251205", "Global IT Solutions",
     [("HP Laptop 15s", 5, 45000), ("Logitech Keyboard K380", 15, 2500)], 262500,
     "Invoice #S009 - Laptops and keyboards"),
    ("S010", "20251215", "Sunrise Electronics Mumbai",
     [("Lenovo Ideapad Slim 3", 3, 42000), ("USB-C Hub 7-in-1", 10, 1500)], 141000,
     "Invoice #S010 - Laptops and hubs"),
    ("S011", "20251228", "Sharma & Sons Traders",
     [("Whiteboard Marker Set", 30, 250), ("Stapler Heavy Duty", 15, 450)], 14250,
     "Invoice #S011 - Stationery"),
    ("S012", "20260110", "Patel Enterprises",
     [("Dell Desktop Optiplex", 5, 35000), ("HP DeskJet Printer 2723", 4, 5500)], 197000,
     "Invoice #S012 - Desktops and printers"),
    ("S013", "20260120", "Rajesh Computers",
     [("Samsung 24 inch Monitor", 10, 12500), ("TP-Link WiFi Router AC750", 8, 1800)], 139400,
     "Invoice #S013 - Monitors and routers"),
    ("S014", "20260205", "Eastern Digital Hub",
     [("HP Laptop 15s", 3, 45000), ("Logitech Wireless Mouse", 30, 800)], 159000,
     "Invoice #S014 - Laptops and mice"),
    ("S015", "20260215", "Apex Technologies Pvt Ltd",
     [("A4 Paper Ream 500 sheets", 100, 350), ("Pen Drive 32GB", 50, 400)], 55000,
     "Invoice #S015 - Office supplies"),
    ("S016", "20260301", "Global IT Solutions",
     [("Lenovo Ideapad Slim 3", 6, 42000), ("Samsung Galaxy Tab A8", 4, 16000)], 316000,
     "Invoice #S016 - Laptops and tablets"),
]

# ── Purchase Invoices (8) ──────────────────────────────────────────
PURCHASE_INVOICES = [
    ("P001", "20250928", "Samsung India Electronics",
     [("Samsung 24 inch Monitor", 25, 11000), ("Samsung Galaxy Tab A8", 20, 13500)], 545000,
     "Invoice #P001 - Samsung stock"),
    ("P002", "20251020", "HP India Sales Pvt Ltd",
     [("HP Laptop 15s", 15, 38000), ("HP DeskJet Printer 2723", 10, 4200)], 612000,
     "Invoice #P002 - HP products"),
    ("P003", "20251110", "Logitech India Pvt Ltd",
     [("Logitech Wireless Mouse", 150, 550), ("Logitech Keyboard K380", 80, 1800)], 226500,
     "Invoice #P003 - Logitech peripherals"),
    ("P004", "20251128", "Samsung India Electronics",
     [("Samsung 24 inch Monitor", 20, 11000), ("Samsung Galaxy Tab A8", 15, 13500)], 422500,
     "Invoice #P004 - Samsung restock"),
    ("P005", "20251215", "HP India Sales Pvt Ltd",
     [("HP Laptop 15s", 10, 38000), ("HP DeskJet Printer 2723", 8, 4200)], 413600,
     "Invoice #P005 - HP restock"),
    ("P006", "20260105", "Local Stationery Mart",
     [("A4 Paper Ream 500 sheets", 300, 280), ("Whiteboard Marker Set", 100, 180), ("Box File Pack of 10", 60, 420)], 127200,
     "Invoice #P006 - Stationery bulk"),
    ("P007", "20260125", "Logitech India Pvt Ltd",
     [("Logitech Wireless Mouse", 100, 550), ("USB-C Hub 7-in-1", 50, 950)], 102500,
     "Invoice #P007 - Logitech restock"),
    ("P008", "20260210", "Bharat Paper Supplies",
     [("A4 Paper Ream 500 sheets", 200, 280), ("Stapler Heavy Duty", 50, 320)], 72000,
     "Invoice #P008 - Paper and staplers"),
]

# ── Payments (16) ──────────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, payee_ledger, bank_ledger, amount, narration)
PAYMENTS = [
    ("PMT001", "20251010", "Samsung India Electronics", "HDFC Bank - Current A/c", 400000, "Part payment for PO #P001"),
    ("PMT002", "20251105", "HP India Sales Pvt Ltd", "HDFC Bank - Current A/c", 500000, "Payment for PO #P002"),
    ("PMT003", "20251130", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - November"),
    ("PMT004", "20251130", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - November"),
    ("PMT005", "20251205", "Logitech India Pvt Ltd", "HDFC Bank - Current A/c", 150000, "Part payment PO #P003"),
    ("PMT006", "20251231", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - December"),
    ("PMT007", "20251231", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - December"),
    ("PMT008", "20251231", "Electricity", "HDFC Bank - Current A/c", 12000, "Electricity bill Q3"),
    ("PMT009", "20260115", "Local Stationery Mart", "HDFC Bank - Current A/c", 80000, "Payment PO #P006"),
    ("PMT010", "20260131", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - January"),
    ("PMT011", "20260131", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - January"),
    ("PMT012", "20260131", "Internet & Phone", "HDFC Bank - Current A/c", 8000, "Monthly internet"),
    ("PMT013", "20260228", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - February"),
    ("PMT014", "20260228", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - February"),
    ("PMT015", "20260215", "Travel & Conveyance", "Cash", 15000, "Sales team travel"),
    ("PMT016", "20260220", "Office Maintenance", "Cash", 8000, "AC servicing"),
]

# ── Receipts (10) ──────────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, from_party, bank_ledger, amount, narration)
RECEIPTS = [
    ("RCT001", "20251020", "Apex Technologies Pvt Ltd", "HDFC Bank - Current A/c", 94000, "Receipt against S001"),
    ("RCT002", "20251105", "Sunrise Electronics Mumbai", "HDFC Bank - Current A/c", 110500, "Receipt against S002"),
    ("RCT003", "20251125", "Global IT Solutions", "HDFC Bank - Current A/c", 130000, "Part receipt S003"),
    ("RCT004", "20251210", "Sharma & Sons Traders", "SBI Savings A/c", 29500, "Receipt against S004"),
    ("RCT005", "20251228", "Patel Enterprises", "HDFC Bank - Current A/c", 180000, "Receipt against S005"),
    ("RCT006", "20260110", "Rajesh Computers", "HDFC Bank - Current A/c", 25500, "Receipt against S006"),
    ("RCT007", "20260120", "Eastern Digital Hub", "HDFC Bank - Current A/c", 116000, "Part receipt S007"),
    ("RCT008", "20260205", "Apex Technologies Pvt Ltd", "SBI Savings A/c", 88000, "Receipt against S008"),
    ("RCT009", "20260220", "Global IT Solutions", "HDFC Bank - Current A/c", 262500, "Receipt S009"),
    ("RCT010", "20260301", "Patel Enterprises", "HDFC Bank - Current A/c", 197000, "Receipt against S012"),
]

# ── Outstanding Bills ──────────────────────────────────────────────
# Receivables: invoiced - received per party
EXPECTED_RECEIVABLES = {
    "Apex Technologies Pvt Ltd": 55000,       # 237000 - 182000
    "Sunrise Electronics Mumbai": 141000,      # 251500 - 110500
    "Global IT Solutions": 316000,             # 708500 - 392500
    "Sharma & Sons Traders": 14250,            # 43750 - 29500
    "Rajesh Computers": 139400,                # 164900 - 25500
    "Eastern Digital Hub": 159000,             # 275000 - 116000
}
# Patel Enterprises: 377000 - 377000 = 0 (fully paid)

EXPECTED_PAYABLES = {
    "Samsung India Electronics": 567500,       # 967500 - 400000
    "HP India Sales Pvt Ltd": 525600,          # 1025600 - 500000
    "Logitech India Pvt Ltd": 179000,          # 329000 - 150000
    "Local Stationery Mart": 47200,            # 127200 - 80000
    "Bharat Paper Supplies": 72000,            # 72000 - 0
}


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                     XML GENERATION FUNCTIONS                      ║
# ╚═══════════════════════════════════════════════════════════════════╝

def generate_company_list() -> str:
    """Generate company_list.xml."""
    return f"""<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
<COMPANY>
<NAME>{COMPANY_NAME}</NAME>
</COMPANY>
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>"""


def generate_ledger_list() -> str:
    """Generate ledger_list.xml with all 30+ ledgers and computed closing balances."""
    # Compute closing balances from transactions
    balances = _compute_ledger_balances()
    lines = ["<ENVELOPE>", "<BODY>", "<DATA>", "<COLLECTION>"]
    for name, parent, opening in LEDGERS:
        closing = balances.get(name, opening)
        closing_str = f"{closing:,.2f}" if closing != 0 else ""
        opening_str = f"{opening:,.2f}" if opening != 0 else ""
        lines.append(f"""<LEDGER>
<NAME>{name}</NAME>
<PARENT>{parent}</PARENT>
<CLOSINGBALANCE>{closing_str}</CLOSINGBALANCE>
<OPENINGBALANCE>{opening_str}</OPENINGBALANCE>
</LEDGER>""")
    lines.extend(["</COLLECTION>", "</DATA>", "</BODY>", "</ENVELOPE>"])
    return "\n".join(lines)


def _sales_ledger_for_item(item_name: str) -> str:
    """Route item to correct sales ledger."""
    return "Sales - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Sales - Electronics"


def _purchase_ledger_for_item(item_name: str) -> str:
    """Route item to correct purchase ledger."""
    return "Purchase - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Purchase - Electronics"


def _build_sales_voucher(vnum, date_str, party, items, total, narration) -> str:
    """Build a single sales voucher XML block."""
    ledger_entries = []
    # Party entry (debit = negative in Tally for sales)
    ledger_entries.append(f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{party}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{total:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>""")
    # Sales ledger entries (credit = positive)
    for item_name, qty, rate in items:
        amt = qty * rate
        sales_ledger = _sales_ledger_for_item(item_name)
        ledger_entries.append(f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{sales_ledger}</LEDGERNAME>
<AMOUNT TYPE="Amount">{amt:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>""")

    return f"""<VOUCHER VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
{"".join(ledger_entries)}
</VOUCHER>"""


def _build_purchase_voucher(vnum, date_str, party, items, total, narration) -> str:
    """Build a single purchase voucher XML block."""
    ledger_entries = []
    # Purchase ledger entries (debit = positive for purchases)
    for item_name, qty, rate in items:
        amt = qty * rate
        purchase_ledger = _purchase_ledger_for_item(item_name)
        ledger_entries.append(f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{purchase_ledger}</LEDGERNAME>
<AMOUNT TYPE="Amount">{amt:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>""")
    # Party entry (credit = negative for supplier)
    ledger_entries.append(f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{party}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{total:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>""")

    return f"""<VOUCHER VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
{"".join(ledger_entries)}
</VOUCHER>"""


def _build_payment_voucher(vnum, date_str, payee, bank, amount, narration) -> str:
    """Build a single payment voucher XML block."""
    return f"""<VOUCHER VCHTYPE="Payment">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{payee}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{payee}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{bank}</LEDGERNAME>
<AMOUNT TYPE="Amount">{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>"""


def _build_receipt_voucher(vnum, date_str, party, bank, amount, narration) -> str:
    """Build a single receipt voucher XML block."""
    return f"""<VOUCHER VCHTYPE="Receipt">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{bank}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{party}</LEDGERNAME>
<AMOUNT TYPE="Amount">{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>"""


def generate_sales_register() -> str:
    """Generate sales_register.xml with all 16 invoices."""
    vouchers = []
    for vnum, dt, party, items, total, narr in SALES_INVOICES:
        vouchers.append(_build_sales_voucher(vnum, dt, party, items, total, narr))
    return f"""<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
{"".join(vouchers)}
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>"""


def generate_purchase_register() -> str:
    """Generate purchase_register.xml with all 8 invoices."""
    vouchers = []
    for vnum, dt, party, items, total, narr in PURCHASE_INVOICES:
        vouchers.append(_build_purchase_voucher(vnum, dt, party, items, total, narr))
    return f"""<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
{"".join(vouchers)}
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>"""


def generate_day_book() -> str:
    """Generate day_book.xml with ALL vouchers (sales + purchases + payments + receipts)."""
    vouchers = []
    for vnum, dt, party, items, total, narr in SALES_INVOICES:
        vouchers.append(_build_sales_voucher(vnum, dt, party, items, total, narr))
    for vnum, dt, party, items, total, narr in PURCHASE_INVOICES:
        vouchers.append(_build_purchase_voucher(vnum, dt, party, items, total, narr))
    for vnum, dt, payee, bank, amount, narr in PAYMENTS:
        vouchers.append(_build_payment_voucher(vnum, dt, payee, bank, amount, narr))
    for vnum, dt, party, bank, amount, narr in RECEIPTS:
        vouchers.append(_build_receipt_voucher(vnum, dt, party, bank, amount, narr))
    return f"""<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
{"".join(vouchers)}
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>"""


def generate_stock_summary() -> str:
    """Generate stock_summary.xml with all 15 items."""
    lines = ["<ENVELOPE>"]
    for name, group, uom, sell_rate, open_qty, open_rate, open_val in STOCK_ITEMS:
        # Compute closing: opening - sold + purchased (simplified)
        sold_qty = sum(
            qty for _, _, _, items, _, _ in SALES_INVOICES
            for item_name, qty, _ in items if item_name == name
        )
        bought_qty = sum(
            qty for _, _, _, items, _, _ in PURCHASE_INVOICES
            for item_name, qty, _ in items if item_name == name
        )
        closing_qty = open_qty - sold_qty + bought_qty
        closing_val = closing_qty * open_rate  # Use opening rate as approx
        lines.append(f""" <DSPACCNAME>
  <DSPDISPNAME>{name}</DSPDISPNAME>
</DSPACCNAME>
 <DSPSTKINFO>
  <DSPSTKCL>
   <DSPCLQTY>{closing_qty:.4f} {uom}</DSPCLQTY>
   <DSPCLRATE>{open_rate:.2f}/{uom}</DSPCLRATE>
   <DSPCLAMTA>{closing_val:.2f}</DSPCLAMTA>
</DSPSTKCL>
</DSPSTKINFO>""")
    lines.append("</ENVELOPE>")
    return "\n".join(lines)


def _compute_ledger_balances() -> dict[str, float]:
    """Compute closing balances for all ledgers from opening + transactions.

    Uses Tally sign convention: negative = debit, positive = credit.
    """
    balances: dict[str, float] = {}
    for name, _, opening in LEDGERS:
        balances[name] = opening

    # Sales: debit party (subtract from party), credit sales ledger (add to sales)
    for _, _, party, items, total, _ in SALES_INVOICES:
        balances[party] = balances.get(party, 0) - total  # Party gets debit (negative)
        for item_name, qty, rate in items:
            ledger = _sales_ledger_for_item(item_name)
            balances[ledger] = balances.get(ledger, 0) + (qty * rate)  # Sales credit (positive)

    # Purchases: debit purchase ledger, credit supplier
    for _, _, party, items, total, _ in PURCHASE_INVOICES:
        for item_name, qty, rate in items:
            ledger = _purchase_ledger_for_item(item_name)
            balances[ledger] = balances.get(ledger, 0) - (qty * rate)  # Purchase debit (negative)
        balances[party] = balances.get(party, 0) + total  # Supplier credit (positive)

    # Payments: debit payee (subtract), credit bank (add)
    for _, _, payee, bank, amount, _ in PAYMENTS:
        balances[payee] = balances.get(payee, 0) - amount  # Pay off liability (debit)
        balances[bank] = balances.get(bank, 0) + amount    # Bank outflow (credit/positive = less debit)

    # Receipts: debit bank (subtract), credit party (add)
    for _, _, party, bank, amount, _ in RECEIPTS:
        balances[bank] = balances.get(bank, 0) - amount    # Bank inflow (debit)
        balances[party] = balances.get(party, 0) + amount  # Party pays off (credit)

    return balances


def _compute_cumulative_pnl(up_to_date: str | None = None) -> dict[str, float]:
    """Compute cumulative P&L from FY start up to a given date (YYYYMMDD).

    Returns dict with keys: sales, purchases, direct_expenses, indirect_expenses.
    If up_to_date is None, computes for full FY.
    """
    sales = 0.0
    purchases = 0.0
    direct_expenses = 0.0
    indirect_expenses = 0.0

    direct_expense_ledgers = {"Courier & Freight", "Packing Charges"}
    indirect_expense_ledgers = {"Rent", "Salaries", "Electricity", "Internet & Phone",
                                "Office Maintenance", "Travel & Conveyance"}

    for _, dt, _, items, total, _ in SALES_INVOICES:
        if up_to_date and dt > up_to_date:
            continue
        sales += total

    for _, dt, _, items, total, _ in PURCHASE_INVOICES:
        if up_to_date and dt > up_to_date:
            continue
        purchases += total

    for _, dt, payee, _, amount, _ in PAYMENTS:
        if up_to_date and dt > up_to_date:
            continue
        if payee in indirect_expense_ledgers:
            indirect_expenses += amount
        elif payee in direct_expense_ledgers:
            direct_expenses += amount

    return {
        "sales": sales,
        "purchases": purchases,
        "direct_expenses": direct_expenses,
        "indirect_expenses": indirect_expenses,
    }


def generate_profit_and_loss(up_to_date: str | None = None) -> str:
    """Generate profit_and_loss.xml — cumulative from FY start to up_to_date.

    Matches live Tally format: alternating DSPACCNAME/PLAMT sibling pairs.
    If up_to_date is None, generates full FY P&L.
    """
    pnl = _compute_cumulative_pnl(up_to_date)
    total_purchases = pnl["purchases"] + pnl["direct_expenses"]

    return f"""<ENVELOPE>
 <DSPACCNAME>
  <DSPDISPNAME>Sales Accounts</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT></PLSUBAMT>
  <BSMAINAMT>{pnl['sales']:.2f}</BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Cost of Sales :</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT></PLSUBAMT>
  <BSMAINAMT>-{total_purchases:.2f}</BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Opening Stock</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT></PLSUBAMT>
  <BSMAINAMT></BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Add: Purchase Accounts</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT>-{pnl['purchases']:.2f}</PLSUBAMT>
  <BSMAINAMT></BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Less: Closing Stock</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT></PLSUBAMT>
  <BSMAINAMT></BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Direct Expenses</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT>{f"-{pnl['direct_expenses']:.2f}" if pnl['direct_expenses'] > 0 else ""}</PLSUBAMT>
  <BSMAINAMT></BSMAINAMT>
</PLAMT>
 <DSPACCNAME>
  <DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
</DSPACCNAME>
 <PLAMT>
  <PLSUBAMT></PLSUBAMT>
  <BSMAINAMT>-{pnl['indirect_expenses']:.2f}</BSMAINAMT>
</PLAMT>
</ENVELOPE>
"""


def generate_trial_balance() -> str:
    """Generate trial_balance.xml consistent with voucher data.

    Uses Tally's alternating DSPACCNAME/DSPACCINFO sibling-pair format.
    """
    pnl = _compute_cumulative_pnl()
    balances = _compute_ledger_balances()

    # Aggregate by group
    group_totals: dict[str, float] = {}
    for name, parent, _ in LEDGERS:
        bal = balances.get(name, 0)
        # Map sub-groups to top-level TB groups
        top_group = _map_to_tb_group(parent)
        group_totals[top_group] = group_totals.get(top_group, 0) + bal

    lines = ["<ENVELOPE>"]
    for group_name in ["Capital Account", "Current Liabilities", "Loans (Liability)",
                       "Fixed Assets", "Current Assets", "Sales Accounts",
                       "Purchase Accounts", "Direct Expenses", "Indirect Expenses"]:
        total = group_totals.get(group_name, 0)
        dr = f"{total:.2f}" if total < 0 else ""
        cr = f"{total:.2f}" if total > 0 else ""
        lines.append(f""" <DSPACCNAME>
  <DSPDISPNAME>{group_name}</DSPDISPNAME>
</DSPACCNAME>
 <DSPACCINFO>
  <DSPCLDRAMT>
   <DSPCLDRAMTA>{dr}</DSPCLDRAMTA>
</DSPCLDRAMT>
  <DSPCLCRAMT>
   <DSPCLCRAMTA>{cr}</DSPCLCRAMTA>
</DSPCLCRAMT>
</DSPACCINFO>""")
    lines.append("</ENVELOPE>")
    return "\n".join(lines)


def _map_to_tb_group(parent: str) -> str:
    """Map ledger parent groups to trial balance top-level groups."""
    mapping = {
        "North Zone Debtors": "Current Assets",
        "South Zone Debtors": "Current Assets",
        "National Creditors": "Current Liabilities",
        "Local Creditors": "Current Liabilities",
        "Bank Accounts": "Current Assets",
        "Cash-in-Hand": "Current Assets",
        "Sales Accounts": "Sales Accounts",
        "Purchase Accounts": "Purchase Accounts",
        "Indirect Expenses": "Indirect Expenses",
        "Direct Expenses": "Direct Expenses",
        "Duties & Taxes": "Current Liabilities",
        "Capital Account": "Capital Account",
    }
    return mapping.get(parent, parent)


def generate_balance_sheet() -> str:
    """Generate balance_sheet.xml consistent with TB and P&L.

    Uses Tally's alternating BSNAME/BSAMT sibling-pair format.
    """
    pnl = _compute_cumulative_pnl()
    net_profit = pnl["sales"] - pnl["purchases"] - pnl["direct_expenses"] - pnl["indirect_expenses"]
    balances = _compute_ledger_balances()

    # Aggregate by BS category
    group_totals: dict[str, float] = {}
    for name, parent, _ in LEDGERS:
        bal = balances.get(name, 0)
        bs_group = _map_to_bs_group(parent)
        if bs_group:
            group_totals[bs_group] = group_totals.get(bs_group, 0) + bal

    lines = ["<ENVELOPE>"]
    bs_items = [
        ("Capital Account", group_totals.get("Capital Account", 0)),
        ("Loans (Liability)", 0),
        ("Current Liabilities", group_totals.get("Current Liabilities", 0)),
        ("Suspense A/c", 0),
        ("Profit & Loss A/c", net_profit),
        ("Fixed Assets", 0),
        ("Current Assets", group_totals.get("Current Assets", 0)),
    ]
    for name, amount in bs_items:
        amt_str = f"{amount:.2f}" if amount != 0 else ""
        lines.append(f""" <BSNAME>
  <DSPACCNAME>
   <DSPDISPNAME>{name}</DSPDISPNAME>
</DSPACCNAME>
</BSNAME>
 <BSAMT>
  <BSSUBAMT></BSSUBAMT>
  <BSMAINAMT>{amt_str}</BSMAINAMT>
</BSAMT>""")
    lines.append("</ENVELOPE>")
    return "\n".join(lines)


def _map_to_bs_group(parent: str) -> str | None:
    """Map ledger parent to balance sheet category. Returns None for P&L items."""
    mapping = {
        "North Zone Debtors": "Current Assets",
        "South Zone Debtors": "Current Assets",
        "National Creditors": "Current Liabilities",
        "Local Creditors": "Current Liabilities",
        "Bank Accounts": "Current Assets",
        "Cash-in-Hand": "Current Assets",
        "Duties & Taxes": "Current Liabilities",
        "Capital Account": "Capital Account",
    }
    return mapping.get(parent)


def generate_bills_receivable() -> str:
    """Generate bills_receivable.xml from outstanding receivables."""
    lines = ["<ENVELOPE>", "<BODY>", "<DATA>", "<TALLYMESSAGE>"]
    for party, amount in EXPECTED_RECEIVABLES.items():
        if amount <= 0:
            continue
        # Use last invoice date as bill date
        last_date = _last_invoice_date_for_party(party)
        lines.append(f"""<BILLFIXED>
<BILLDATE>{last_date}</BILLDATE>
<BILLREF>{party[:20]}</BILLREF>
<BILLPARTY>{party}</BILLPARTY>
</BILLFIXED>
<BILLCL>-{amount:.2f}</BILLCL>
<BILLDUE>{last_date}</BILLDUE>
<BILLOVERDUE>30</BILLOVERDUE>""")
    lines.extend(["</TALLYMESSAGE>", "</DATA>", "</BODY>", "</ENVELOPE>"])
    return "\n".join(lines)


def generate_bills_payable() -> str:
    """Generate bills_payable.xml from outstanding payables."""
    lines = ["<ENVELOPE>", "<BODY>", "<DATA>", "<TALLYMESSAGE>"]
    for party, amount in EXPECTED_PAYABLES.items():
        if amount <= 0:
            continue
        last_date = _last_purchase_date_for_party(party)
        lines.append(f"""<BILLFIXED>
<BILLDATE>{last_date}</BILLDATE>
<BILLREF>{party[:20]}</BILLREF>
<BILLPARTY>{party}</BILLPARTY>
</BILLFIXED>
<BILLCL>{amount:.2f}</BILLCL>
<BILLDUE>{last_date}</BILLDUE>
<BILLOVERDUE>30</BILLOVERDUE>""")
    lines.extend(["</TALLYMESSAGE>", "</DATA>", "</BODY>", "</ENVELOPE>"])
    return "\n".join(lines)


def _last_invoice_date_for_party(party: str) -> str:
    """Find last sales invoice date for a party, formatted as D-Mon-YY."""
    dates = [dt for _, dt, p, _, _, _ in SALES_INVOICES if p == party]
    if not dates:
        return "1-Oct-25"
    last = max(dates)
    d = date(int(last[:4]), int(last[4:6]), int(last[6:8]))
    return d.strftime("%-d-%b-%y")


def _last_purchase_date_for_party(party: str) -> str:
    """Find last purchase invoice date for a party, formatted as D-Mon-YY."""
    dates = [dt for _, dt, p, _, _, _ in PURCHASE_INVOICES if p == party]
    if not dates:
        return "1-Oct-25"
    last = max(dates)
    d = date(int(last[:4]), int(last[4:6]), int(last[6:8]))
    return d.strftime("%-d-%b-%y")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                           MAIN                                    ║
# ╚═══════════════════════════════════════════════════════════════════╝

def main():
    files = {
        "company_list.xml": generate_company_list(),
        "ledger_list.xml": generate_ledger_list(),
        "sales_register.xml": generate_sales_register(),
        "purchase_register.xml": generate_purchase_register(),
        "day_book.xml": generate_day_book(),
        "stock_summary.xml": generate_stock_summary(),
        "profit_and_loss.xml": generate_profit_and_loss(),
        "trial_balance.xml": generate_trial_balance(),
        "balance_sheet.xml": generate_balance_sheet(),
        "bills_receivable.xml": generate_bills_receivable(),
        "bills_payable.xml": generate_bills_payable(),
    }

    for filename, content in files.items():
        path = FIXTURES_DIR / filename
        path.write_text(content)
        print(f"  Generated {filename} ({len(content)} bytes)")

    print(f"\nGenerated {len(files)} fixture files in {FIXTURES_DIR}")

    # Print summary stats
    pnl = _compute_cumulative_pnl()
    print(f"\n  Total Sales:       {pnl['sales']:>12,.2f}")
    print(f"  Total Purchases:   {pnl['purchases']:>12,.2f}")
    print(f"  Direct Expenses:   {pnl['direct_expenses']:>12,.2f}")
    print(f"  Indirect Expenses: {pnl['indirect_expenses']:>12,.2f}")
    net = pnl['sales'] - pnl['purchases'] - pnl['direct_expenses'] - pnl['indirect_expenses']
    print(f"  Net Profit:        {net:>12,.2f}")
    print(f"  Receivables:       {sum(EXPECTED_RECEIVABLES.values()):>12,.2f}")
    print(f"  Payables:          {sum(EXPECTED_PAYABLES.values()):>12,.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator and verify output**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && python tests/fixtures/generate_fixtures.py`
Expected: All 11 fixture files generated with correct byte counts and summary stats.

- [ ] **Step 3: Verify generated fixtures parse correctly**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/test_response_parser.py -v`
Expected: All existing parser tests still pass (they test the XML format the fixtures now produce).

- [ ] **Step 4: Run full unit test suite to catch regressions**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ -v --tb=short`
Expected: All ~355 unit tests pass. Some may need fixture data updates if they hardcode old values.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/generate_fixtures.py tests/fixtures/*.xml
git commit -m "feat: add fixture generator with complete Bharat Traders seed data

Generates all XML fixtures from TALLYPRIME_AGENT_PLAN.md spec:
- 30+ ledgers, 16 sales, 8 purchases, 16 payments, 10 receipts
- 15 stock items (electronics/peripherals/office supplies)
- Computed P&L, TB, BS consistent with voucher totals
- Separate bills_receivable and bills_payable fixtures"
```

---

### Task 2: Fix unit tests that depend on old fixture data

**Files:**
- Modify: various `tests/unit/test_*.py` files that reference old fixture content

- [ ] **Step 1: Run unit tests and identify failures**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ -v --tb=short 2>&1 | grep FAILED`

- [ ] **Step 2: Fix each failing test**

Known files that will break (hardcode old fixture values):
- `tests/unit/test_response_parser.py`: `len(ledgers) == 3` → 30+, P&L amounts (3764350 → 2057650), TB amounts, BS amounts
- `tests/unit/test_pnl_period.py`: Hardcoded P&L subtraction math
- `tests/unit/test_tools.py`: Expected tool outputs referencing old fixture data
- `tests/eval/golden/mock_golden.json`: References old fixture amounts — regenerate
- `tests/integration/test_*.py`: Any integration tests hardcoding fixture row counts

For each failure, update the expected values to match the new fixture data.
Do NOT change the fixture format — only update test expectations.

- [ ] **Step 3: Run unit tests again**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/
git commit -m "fix: update unit test expectations for enriched fixture data"
```

---

## Chunk 2: Date-Aware Mock Handler

### Task 3: Upgrade mock_handler.py to parse dates from XML requests

**Files:**
- Modify: `backend/tally_bridge/mock_handler.py`
- Test: `tests/unit/test_mock_handler.py` (create)

The key insight: live Tally returns **cumulative** P&L from FY start to SVTODATE (ignoring SVFROMDATE). The mock must replicate this behavior by computing cumulative P&L from voucher data up to the requested SVTODATE.

For voucher collections (SalesVchs, PurchaseVchs, DayBookVchs, LedgerVchs), the mock returns the full dataset — existing Python-side `_filter_vouchers_by_date()` handles date filtering.

- [ ] **Step 1: Write failing tests for date-aware mock handler**

Create `tests/unit/test_mock_handler.py`:

```python
"""Tests for date-aware mock Tally handler."""
import re
import pytest
from backend.tally_bridge.mock_handler import mock_tally_request


def _build_pnl_request(from_date: str, to_date: str) -> str:
    """Build a P&L request XML with date range."""
    return f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE><ID>Profit and Loss</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
</STATICVARIABLES></DESC></BODY></ENVELOPE>"""


def _build_tb_request(from_date: str, to_date: str) -> str:
    """Build a Trial Balance request XML with date range."""
    return f"""<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE><ID>Trial Balance</ID></HEADER>
<BODY><DESC><STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
</STATICVARIABLES></DESC></BODY></ENVELOPE>"""


class TestDateAwarePnL:
    """P&L mock returns different cumulative amounts based on SVTODATE."""

    def test_full_fy_pnl_has_all_sales(self):
        xml = _build_pnl_request("01-04-2025", "31-03-2026")
        result = mock_tally_request(xml)
        # Full FY should include all 16 sales invoices
        assert "BSMAINAMT" in result
        # Sales should be 2057650.00 (sum of all 16 invoices)
        assert "2057650.00" in result

    def test_q3_cumulative_pnl_has_oct_dec_sales(self):
        """Cumulative to Dec 31 should include Oct+Nov+Dec sales only."""
        xml = _build_pnl_request("01-04-2025", "31-12-2025")
        result = mock_tally_request(xml)
        # Oct: S001(94k)+S002(110.5k)+S003(130k)+S004(29.5k)+S005(180k)=544000
        # Nov: S006(25.5k)+S007(116k)+S008(88k)=229500
        # Dec: S009(262.5k)+S010(141k)+S011(14.25k)=417750
        # Cumulative to Dec = 1191250
        assert "1191250.00" in result

    def test_q2_cumulative_pnl_has_no_sales(self):
        """Cumulative to Sep 30 should have no sales (first sale is Oct 1)."""
        xml = _build_pnl_request("01-04-2025", "30-09-2025")
        result = mock_tally_request(xml)
        # Only P001 purchase (Sep 28) before Oct
        # Sales should be 0
        assert "Sales Accounts" in result

    def test_different_dates_produce_different_pnl(self):
        """Core test: different SVTODATEs must produce different P&L amounts."""
        q2_xml = _build_pnl_request("01-04-2025", "30-09-2025")
        q3_xml = _build_pnl_request("01-04-2025", "31-12-2025")
        q2_result = mock_tally_request(q2_xml)
        q3_result = mock_tally_request(q3_xml)
        assert q2_result != q3_result, "Q2 and Q3 cumulative P&L must differ"

    def test_subtraction_yields_nonzero_for_q3(self):
        """profit_and_loss_period() for Q3 should yield non-zero after subtraction."""
        # This simulates what profit_and_loss_period() does:
        # cumulative(FY start to Dec 31) - cumulative(FY start to Sep 30)
        cum_xml = _build_pnl_request("01-04-2025", "31-12-2025")
        prior_xml = _build_pnl_request("01-04-2025", "30-09-2025")
        cum_result = mock_tally_request(cum_xml)
        prior_result = mock_tally_request(prior_xml)
        # Extract sales amounts
        cum_sales = _extract_bsmainamt(cum_result, "Sales Accounts")
        prior_sales = _extract_bsmainamt(prior_result, "Sales Accounts")
        period_sales = cum_sales - prior_sales
        assert period_sales > 0, f"Q3 sales should be >0, got {period_sales}"


def _extract_bsmainamt(xml_str: str, account_name: str) -> float:
    """Extract BSMAINAMT value for a given account from P&L XML."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_str)
    children = list(root)
    for i, child in enumerate(children):
        if child.tag == "DSPACCNAME":
            disp = child.find("DSPDISPNAME")
            if disp is not None and disp.text == account_name:
                if i + 1 < len(children) and children[i + 1].tag == "PLAMT":
                    main = children[i + 1].find("BSMAINAMT")
                    if main is not None and main.text:
                        return float(main.text)
    return 0.0


class TestVoucherCollectionsReturnFullData:
    """Voucher collections return ALL data regardless of dates — Python filters."""

    def test_sales_register_returns_all_vouchers(self):
        xml = '<ENVELOPE><HEADER><TYPE>Collection</TYPE></HEADER><BODY>SalesVchs</BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        # Should contain all 16 sales vouchers
        assert result.count("VCHTYPE=\"Sales\"") == 16

    def test_purchase_register_returns_all_vouchers(self):
        xml = '<ENVELOPE><HEADER><TYPE>Collection</TYPE></HEADER><BODY>PurchaseVchs</BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert result.count("VCHTYPE=\"Purchase\"") == 8

    def test_day_book_returns_all_vouchers(self):
        xml = '<ENVELOPE><HEADER><TYPE>Collection</TYPE></HEADER><BODY>DayBookVchs</BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        # 16 sales + 8 purchases + 16 payments + 10 receipts = 50
        total_vouchers = result.count("<VOUCHER ")
        assert total_vouchers == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mock_handler.py -v`
Expected: FAIL — current mock_handler doesn't support date-aware P&L.

- [ ] **Step 3: Implement date-aware mock handler**

Modify `backend/tally_bridge/mock_handler.py`:

```python
"""In-process mock Tally handler.

Returns fixture XML data for Bharat Traders Pvt Ltd demo company.
For TYPE=Data reports (P&L, TB), parses SVTODATE from the request
and computes cumulative figures from voucher data — matching real
Tally's behavior of returning cumulative from FY start.

For TYPE=Collection (vouchers), returns the full fixture dataset.
Python-side date filtering handles range selection.
"""
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# Reports that return full fixture regardless of dates
STATIC_FIXTURES: dict[str, str] = {
    "List of Companies": "company_list.xml",
    "CustomLedgerList": "ledger_list.xml",
    "Trial Balance": "trial_balance.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_payable.xml",
    "Stock Summary": "stock_summary.xml",
}

# Voucher collections — return full data, Python filters by date
VOUCHER_FIXTURES: dict[str, str] = {
    "DayBookVchs": "day_book.xml",
    "SalesVchs": "sales_register.xml",
    "PurchaseVchs": "purchase_register.xml",
    "LedgerVchs": "day_book.xml",
}

# Date-aware reports — computed from voucher data
DATE_AWARE_REPORTS = {"Profit and Loss"}

_ERROR_RESPONSE = (
    "<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>"
)


@lru_cache(maxsize=32)
def _load_fixture(filename: str) -> str:
    """Load a fixture file, cached for performance.

    Call ``_load_fixture.cache_clear()`` to invalidate the cache during
    development (e.g. after editing fixture files on disk).
    """
    path = FIXTURES_DIR / filename
    if not path.exists():
        return _ERROR_RESPONSE
    return path.read_text()


def _extract_svtodate(xml_body: str) -> str | None:
    """Extract SVTODATE value from request XML. Returns YYYYMMDD or None."""
    match = re.search(r"<SVTODATE>(\d{2})-(\d{2})-(\d{4})</SVTODATE>", xml_body)
    if match:
        dd, mm, yyyy = match.groups()
        return f"{yyyy}{mm}{dd}"
    return None


def _generate_cumulative_pnl(up_to_yyyymmdd: str | None) -> str:
    """Generate P&L XML with cumulative figures up to the given date."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "generate_fixtures",
        FIXTURES_DIR / "generate_fixtures.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_profit_and_loss(up_to_date=up_to_yyyymmdd)


def mock_tally_request(xml_body: str) -> str:
    """Process an XML request and return mock fixture response."""
    # Check date-aware reports first
    for report_name in DATE_AWARE_REPORTS:
        if report_name in xml_body:
            svtodate = _extract_svtodate(xml_body)
            if report_name == "Profit and Loss":
                return _generate_cumulative_pnl(svtodate)

    # Static fixtures
    for report_name, fixture_file in STATIC_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)

    # Voucher collections
    for report_name, fixture_file in VOUCHER_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)

    return _ERROR_RESPONSE
```

- [ ] **Step 4: Run mock handler tests**

Run: `pytest tests/unit/test_mock_handler.py -v`
Expected: All pass.

- [ ] **Step 5: Run integration tests**

Run: `pytest tests/integration/ -v`
Expected: All pass — mock_tally_server delegates to updated mock_handler.

- [ ] **Step 6: Commit**

```bash
git add backend/tally_bridge/mock_handler.py tests/unit/test_mock_handler.py
git commit -m "feat: date-aware mock handler computes cumulative P&L from voucher data

Mock handler now parses SVTODATE from request XML and generates
P&L with cumulative figures up to that date — matching real Tally's
behavior. Voucher collections still return full dataset for
Python-side date filtering. Fixes Q2 vs Q3 comparison returning
all zeros in mock mode."
```

---

### Task 4: Update mock_tally_server to delegate correctly

**Files:**
- Modify: `tests/mocks/mock_tally_server.py` (if needed)

- [ ] **Step 1: Verify mock_tally_server still works**

Run: `pytest tests/integration/ -v`
Expected: All pass. If `mock_tally_server.py` has its own fixture mapping, sync it with mock_handler.

- [ ] **Step 2: Fix if needed**

If `mock_tally_server.py` has a separate fixture mapping that overrides `mock_handler`, update it to delegate fully.

- [ ] **Step 3: Commit if changes needed**

---

## Chunk 3: Mock-Specific Eval Scenarios

### Task 5: Create mock variant eval scenario files

**Files:**
- Create: `tests/eval/scenarios/manual_test_regression_mock.yaml`
- Create: `tests/eval/scenarios/edge_case_gauntlet_mock.yaml`
- Create: `tests/eval/scenarios/trends_and_breakdowns_mock.yaml`
- Create: `tests/eval/scenarios/financial_deep_dive_mock.yaml`

Changes from live versions:
- Replace HCODE references with plan parties (Apex Technologies, Global IT Solutions, etc.)
- Replace Q1/Q2 queries with Q3/Q4 (data only exists Oct-Mar)
- Replace "full FY cash flow" with "Oct 2025 to Mar 2026 cash flow"
- Adjust expectations for mock data volumes

- [ ] **Step 1: Create manual_test_regression_mock.yaml**

```yaml
name: "Manual Test Regression (Mock)"
description: "Mock-mode variant. Uses parties and date ranges available in demo fixtures."
tags: [regression, date_resolution, trends, comparison, mock]

turns:
  - query: "P&L last month"
    expect:
      has_data: true
      checks:
        - "Returns profit and loss data for the previous calendar month"
        - "Date range is correct for last month (not full year)"
        - "Income and expense categories shown"

  - query: "show me sales trend over 25-26 FY"
    expect:
      query_type: trend
      has_data: true
      has_chart: true
      checks:
        - "Shows monthly or periodic sales data for FY 2025-26"
        - "Trend direction (growing/declining/stable) is mentioned"
        - "Chart shows time-series data"
        - "Total sales amount should be present as a summary row or in prose"

  - query: "compare Q3 and Q4 results"
    expect:
      query_type: comparison
      has_data: true
      has_chart: true
      checks:
        - "Q3 maps to Oct-Dec 2025"
        - "Q4 maps to Jan-Mar 2026"
        - "Shows absolute and/or percentage difference"
        - "Both quarters have distinct data"
        - "Column totals should be present for each quarter"

  - query: "Top 10 customers"
    expect:
      query_type: top_n
      has_data: true
      checks:
        - "Lists up to 10 customers ranked by sales"
        - "Amounts sorted in descending order"
        - "Indian rupee formatting used"
        - "Grand total of listed customers' sales should be present"

  - query: "month-wise trend for Apex Technologies"
    expect:
      has_data: true
      has_chart: true
      checks:
        - "Identifies Apex Technologies as a party/ledger"
        - "Shows monthly breakdown of transactions or sales for Apex Technologies"
        - "Chart shows time on X-axis with monthly data points"
```

- [ ] **Step 2: Create edge_case_gauntlet_mock.yaml**

Copy `edge_case_gauntlet.yaml` with these changes:
- Turn 5: "Compare sales of Q3 vs Q4" instead of "Q1 vs Q2 vs Q3 vs Q4"
- Turn 7: "What was the sales amount for Apex Technologies last month?" instead of HCODE

- [ ] **Step 3: Create trends_and_breakdowns_mock.yaml**

Copy `trends_and_breakdowns.yaml` with these changes:
- Turn 1: "Show me monthly cash flow from October 2025 to March 2026"
- Turn 4: "Show Q3 vs Q4 revenue and expenses"
- Turn 7: "Compare December expenses with January expenses — category-wise"
- Adjust checks for date ranges within Oct-Mar

- [ ] **Step 4: Create financial_deep_dive_mock.yaml**

Copy `financial_deep_dive.yaml` — most turns work with enriched fixtures. Turn 5 may need date range adjustment: "Show me monthly trend for the largest expense from October to March"

- [ ] **Step 5: Commit**

```bash
git add tests/eval/scenarios/*_mock.yaml
git commit -m "feat: add mock-specific eval scenario variants

Replace live-only entities (HCODE → Apex Technologies) and
date ranges (Q1/Q2 → Q3/Q4) for mock mode compatibility.
Scenarios: manual_test_regression, edge_case_gauntlet,
trends_and_breakdowns, financial_deep_dive."
```

---

### Task 6: Update eval collector to auto-select mock scenarios

**Files:**
- Modify: `tests/eval/collect.py`

- [ ] **Step 1: Add mock scenario auto-selection logic**

Modify `load_scenario()` in `tests/eval/collect.py` (line 36) to accept an optional `tally_mode` parameter:

```python
def load_scenario(name: str, tally_mode: str = "live") -> dict:
    """Load a scenario YAML file by name. Prefers *_mock.yaml in mock mode."""
    if tally_mode == "mock":
        mock_path = SCENARIOS_DIR / f"{name}_mock.yaml"
        if mock_path.exists():
            logger.info("Using mock variant: %s", mock_path.name)
            return yaml.safe_load(mock_path.read_text())
    path = SCENARIOS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {path}")
    return yaml.safe_load(path.read_text())
```

Then update the call site at line ~445 to pass `tally_mode`:
```python
scenario = load_scenario(name, tally_mode=args.tally_mode)
```

Also update `list_scenarios()` (if it exists) to exclude `*_mock.yaml` from the `--scenario all` list — mock variants are auto-selected, not listed separately.

- [ ] **Step 2: Verify collector picks mock scenarios**

Run: `PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --tally-mode mock --dry-run` (if dry-run supported) or check logs.

- [ ] **Step 3: Commit**

```bash
git add tests/eval/collect.py
git commit -m "feat: eval collector auto-selects *_mock.yaml scenario variants"
```

---

## Chunk 4: Live-vs-Mock Format Parity Tests

### Task 7: Create format parity test suite

**Files:**
- Create: `tests/integration/test_mock_format_parity.py`

These tests verify that mock handler responses parse identically to the format that live Tally returns. They use the existing response parsers to ensure structural compatibility.

- [ ] **Step 1: Write format parity tests**

```python
"""Tests that mock handler returns responses in the same format as live Tally.

Each test sends a mock request, parses the response using the real parser,
and verifies the parsed output has the expected structure and field names.
"""
import pytest
from backend.tally_bridge.mock_handler import mock_tally_request
from backend.tally_bridge.response_parser import (
    parse_trial_balance,
    parse_profit_and_loss,
    parse_balance_sheet,
    parse_stock_summary,
    parse_vouchers,
    parse_ledger_list,
    parse_bills,
)


def _pnl_request(to_date: str = "31-03-2026") -> str:
    return f"""<ENVELOPE><HEADER><TYPE>Data</TYPE><ID>Profit and Loss</ID></HEADER>
<BODY><DESC><STATICVARIABLES><SVFROMDATE>01-04-2025</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE></STATICVARIABLES></DESC></BODY></ENVELOPE>"""


def _tb_request() -> str:
    return """<ENVELOPE><HEADER><TYPE>Data</TYPE><ID>Trial Balance</ID></HEADER>
<BODY><DESC><STATICVARIABLES><SVFROMDATE>01-04-2025</SVFROMDATE>
<SVTODATE>31-03-2026</SVTODATE></STATICVARIABLES></DESC></BODY></ENVELOPE>"""


class TestPnLFormatParity:
    """P&L responses must parse with parse_profit_and_loss without errors."""

    def test_full_fy_pnl_parses(self):
        raw = mock_tally_request(_pnl_request())
        rows = parse_profit_and_loss(raw)
        assert len(rows) > 0
        for row in rows:
            assert "account_name" in row
            assert "closing_balance" in row
            assert "debit_amount" in row
            assert "credit_amount" in row

    def test_pnl_has_sales_and_expenses(self):
        raw = mock_tally_request(_pnl_request())
        rows = parse_profit_and_loss(raw)
        names = {r["account_name"] for r in rows}
        assert "Sales Accounts" in names
        assert "Indirect Expenses" in names

    def test_period_pnl_parses_same_format(self):
        """Period-specific P&L must have same structure as full-FY."""
        full = parse_profit_and_loss(mock_tally_request(_pnl_request("31-03-2026")))
        q3 = parse_profit_and_loss(mock_tally_request(_pnl_request("31-12-2025")))
        assert len(full) == len(q3), "Period and full-FY P&L must have same row count"
        for f, q in zip(full, q3):
            assert f["account_name"] == q["account_name"]

    def test_cumulative_pnl_increases_over_time(self):
        """Later SVTODATE should have >= sales than earlier."""
        sep = parse_profit_and_loss(mock_tally_request(_pnl_request("30-09-2025")))
        dec = parse_profit_and_loss(mock_tally_request(_pnl_request("31-12-2025")))
        mar = parse_profit_and_loss(mock_tally_request(_pnl_request("31-03-2026")))
        sep_sales = next(r["closing_balance"] for r in sep if r["account_name"] == "Sales Accounts")
        dec_sales = next(r["closing_balance"] for r in dec if r["account_name"] == "Sales Accounts")
        mar_sales = next(r["closing_balance"] for r in mar if r["account_name"] == "Sales Accounts")
        assert sep_sales <= dec_sales <= mar_sales


class TestTBFormatParity:
    def test_tb_parses(self):
        raw = mock_tally_request(_tb_request())
        rows = parse_trial_balance(raw)
        assert len(rows) > 0
        for row in rows:
            assert "account_name" in row
            assert "debit_amount" in row
            assert "credit_amount" in row


class TestVoucherFormatParity:
    def test_sales_vouchers_parse(self):
        raw = mock_tally_request("<BODY>SalesVchs</BODY>")
        vouchers = parse_vouchers(raw)
        assert len(vouchers) == 16
        for v in vouchers:
            assert "date" in v
            assert "party_name" in v or "party" in v
            assert "amount" in v or "total" in v

    def test_purchase_vouchers_parse(self):
        raw = mock_tally_request("<BODY>PurchaseVchs</BODY>")
        vouchers = parse_vouchers(raw)
        assert len(vouchers) == 8

    def test_day_book_vouchers_parse(self):
        raw = mock_tally_request("<BODY>DayBookVchs</BODY>")
        vouchers = parse_vouchers(raw)
        assert len(vouchers) == 50


class TestBillsFormatParity:
    def test_bills_receivable_parses(self):
        raw = mock_tally_request("<BODY>Bills Receivable</BODY>")
        bills = parse_bills(raw)
        assert len(bills) >= 6  # 6 parties with outstanding

    def test_bills_payable_parses(self):
        raw = mock_tally_request("<BODY>Bills Payable</BODY>")
        bills = parse_bills(raw)  # Same parser, different sign
        assert len(bills) >= 5


class TestLedgerFormatParity:
    def test_ledger_list_parses(self):
        raw = mock_tally_request("<BODY>CustomLedgerList</BODY>")
        ledgers = parse_ledger_list(raw)
        assert len(ledgers) >= 30
        for ledger in ledgers:
            assert "name" in ledger
            assert "parent" in ledger


class TestStockFormatParity:
    def test_stock_summary_parses(self):
        raw = mock_tally_request("<BODY>Stock Summary</BODY>")
        items = parse_stock_summary(raw)
        assert len(items) == 15
        for item in items:
            assert "name" in item or "item_name" in item
```

- [ ] **Step 2: Run format parity tests**

Run: `pytest tests/integration/test_mock_format_parity.py -v`
Expected: FAIL initially — adjust parser field names as needed.

- [ ] **Step 3: Fix any parser/fixture mismatches**

If parsers expect slightly different field names or structures, adjust the fixture generator to match (not the parsers — the fixtures should match live Tally format).

- [ ] **Step 4: Run all tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ -v --tb=short`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_mock_format_parity.py
git commit -m "test: add live-vs-mock format parity tests

Verifies mock handler responses parse identically to live Tally
format using existing response parsers. Tests P&L cumulative
behavior, voucher counts, bill structures, ledger list, and
stock summary format."
```

---

## Chunk 5: Integration Verification

### Task 8: Run e2e_live tests in mock mode

- [ ] **Step 1: Run e2e_live mock tests**

Run: `PYTHONPATH=. pytest tests/e2e_live/ -v -s --tally-mode mock 2>&1 | tee docs/e2e-live-mock-enriched-results.log`
Expected: 19/19 pass (requires ANTHROPIC_API_KEY). If key unavailable, 17/19 pass with 2 auth failures.

- [ ] **Step 2: Run eval manual_test_regression in mock mode**

Run with backend + frontend running:
```bash
PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173 --tally-mode mock
PYTHONPATH=. python tests/eval/judge.py
PYTHONPATH=. python tests/eval/report.py
```
Expected: Collector auto-selects `manual_test_regression_mock.yaml`. All turns produce data. Scores improve significantly (target: avg factual >= 4).

- [ ] **Step 3: Compare mock vs live scores**

If live results exist in `tests/eval/results/run_20260311_212338/`, compare score distributions.

- [ ] **Step 4: Commit results**

```bash
git add docs/e2e-live-mock-enriched-results.log
git commit -m "docs: save enriched mock mode test results"
```

---

### Task 9: Run full test suite

- [ ] **Step 1: Run all backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --tb=short`
Expected: All pass.

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: 111 tests pass.

- [ ] **Step 3: Run Playwright visual tests**

Run:
```bash
cd frontend
rm -rf tests/playwright/__screenshots__
npm run test:playwright -- --update-snapshots
```
Expected: 39 tests pass. Visually inspect eval-visual screenshots.

- [ ] **Step 4: Final commit**

```bash
git add tests/ backend/ docs/
git commit -m "chore: final verification — all tests pass with enriched mock data"
```

---

### Task 10: Update CLAUDE.md and memory

- [ ] **Step 1: Update test counts in CLAUDE.md**

Update the test count comments to reflect new totals.

- [ ] **Step 2: Update memory**

Update `memory/MEMORY.md` with Phase 10 status and key decisions.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for enriched mock data phase"
```
