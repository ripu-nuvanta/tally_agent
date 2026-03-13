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
        closing_str = f"{closing:.2f}" if closing != 0 else ""
        opening_str = f"{opening:.2f}" if opening != 0 else ""
        # Escape XML special characters in name and parent
        safe_name = name.replace("&", "&amp;")
        safe_parent = parent.replace("&", "&amp;")
        lines.append(f"""<LEDGER>
<NAME>{safe_name}</NAME>
<PARENT>{safe_parent}</PARENT>
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


def _xml_escape(text: str) -> str:
    """Escape XML special characters in text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_sales_voucher(vnum, date_str, party, items, total, narration) -> str:
    """Build a single sales voucher XML block."""
    ledger_entries = []
    safe_party = _xml_escape(party)
    # Party entry (debit = negative in Tally for sales)
    ledger_entries.append(f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{safe_party}</LEDGERNAME>
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
<PARTYLEDGERNAME TYPE="String">{safe_party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
{"".join(ledger_entries)}
</VOUCHER>"""


def _build_purchase_voucher(vnum, date_str, party, items, total, narration) -> str:
    """Build a single purchase voucher XML block."""
    ledger_entries = []
    safe_party = _xml_escape(party)
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
<LEDGERNAME>{safe_party}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{total:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>""")

    return f"""<VOUCHER VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{safe_party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
{"".join(ledger_entries)}
</VOUCHER>"""


def _build_payment_voucher(vnum, date_str, payee, bank, amount, narration) -> str:
    """Build a single payment voucher XML block."""
    safe_payee = _xml_escape(payee)
    safe_bank = _xml_escape(bank)
    return f"""<VOUCHER VCHTYPE="Payment">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{safe_payee}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{safe_payee}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{safe_bank}</LEDGERNAME>
<AMOUNT TYPE="Amount">{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>"""


def _build_receipt_voucher(vnum, date_str, party, bank, amount, narration) -> str:
    """Build a single receipt voucher XML block."""
    safe_party = _xml_escape(party)
    safe_bank = _xml_escape(bank)
    return f"""<VOUCHER VCHTYPE="Receipt">
<DATE TYPE="Date">{date_str}</DATE>
<VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
<VOUCHERNUMBER>{vnum}</VOUCHERNUMBER>
<PARTYLEDGERNAME TYPE="String">{safe_party}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{safe_bank}</LEDGERNAME>
<AMOUNT TYPE="Amount">-{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{safe_party}</LEDGERNAME>
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
        ("Profit &amp; Loss A/c", net_profit),
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
        safe_party = _xml_escape(party)
        safe_ref = _xml_escape(party[:20])
        lines.append(f"""<BILLFIXED>
<BILLDATE>{last_date}</BILLDATE>
<BILLREF>{safe_ref}</BILLREF>
<BILLPARTY>{safe_party}</BILLPARTY>
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
        safe_party = _xml_escape(party)
        safe_ref = _xml_escape(party[:20])
        lines.append(f"""<BILLFIXED>
<BILLDATE>{last_date}</BILLDATE>
<BILLREF>{safe_ref}</BILLREF>
<BILLPARTY>{safe_party}</BILLPARTY>
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
