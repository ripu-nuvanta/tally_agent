"""Canonical Bharat Traders seed dataset for TallyPrime.

Imported by scripts/seed_tally_data.py (seeder) and intended for reuse by
the fixture generator (tests/fixtures/generate_fixtures.py) in a future task.

Tuple shapes (differ from the fixture file):
  LEDGERS:     (name, parent_group, opening_balance, state, gstin, gst_reg_type)
  STOCK_ITEMS: (name, group, uom, selling_rate, opening_qty, opening_rate, opening_value, hsn, gst_rate)
"""

# ── Company ──────────────────────────────────────────────────────────
COMPANY_NAME = "Bharat Traders Private Limited"
COMPANY_STATE = "Maharashtra"
COMPANY_GSTIN = "27AABCB1234F1ZP"

# ── Groups (sub-groups Tally doesn't ship by default) ─────────────────
# (name, parent)
GROUPS = [
    ("North Zone Debtors", "Sundry Debtors"),
    ("South Zone Debtors", "Sundry Debtors"),
    ("National Creditors",  "Sundry Creditors"),
    ("Local Creditors",     "Sundry Creditors"),
]

# ── Units ─────────────────────────────────────────────────────────────
# (name, formal_name) — short ASCII per docs/tally-write-exploration-v4.md Op 1
UNITS = [
    ("Nos", "Numbers"),
    ("Pcs", "Pieces"),
]

# ── Stock Groups ──────────────────────────────────────────────────────
# (name, parent) — empty parent = top-level under Primary
STOCK_GROUPS = [
    ("Electronics",     ""),
    ("Peripherals",     ""),
    ("Office Supplies", ""),
]

# ── GST Tax Ledgers ───────────────────────────────────────────────────
# (name, duty_head) under Duties & Taxes
# Used by seeder via build_create_gst_ledger (which emits TAXTYPE/GSTDUTYHEAD).
GST_LEDGERS = [
    ("CGST Output", "Central Tax"),
    ("SGST Output", "State Tax"),
    ("IGST Output", "Integrated Tax"),
    ("CGST Input",  "Central Tax"),
    ("SGST Input",  "State Tax"),
    ("IGST Input",  "Integrated Tax"),
]

# ── Ledgers (34) ──────────────────────────────────────────────────────
# (name, parent_group, opening_balance, state, gstin, gst_reg_type)
# Negative opening_balance = debit in Tally convention.
# Sundry Debtors/Creditors get Maharashtra GSTINs; all others get None.
# GSTIN scheme: 27AAAAA<4-digit counter>A1Z5, counter assigned in ledger order
#   (debtors first: 0001-0007, creditors next: 0008-0012).
# NOTE: The 6 GST tax ledgers below are kept for fixture-side compatibility.
#   The seeder uses GST_LEDGERS + build_create_gst_ledger instead.
LEDGERS = [
    # Debtors (7) — counter 0001..0007
    ("Apex Technologies Pvt Ltd",   "North Zone Debtors", 0, "Maharashtra", "27AAAAA0001A1Z5", "Regular"),
    ("Sunrise Electronics Mumbai",  "South Zone Debtors", 0, "Maharashtra", "27AAAAA0002A1Z5", "Regular"),
    ("Global IT Solutions",         "North Zone Debtors", 0, "Maharashtra", "27AAAAA0003A1Z5", "Regular"),
    ("Sharma & Sons Traders",       "South Zone Debtors", 0, "Maharashtra", "27AAAAA0004A1Z5", "Regular"),
    ("Patel Enterprises",           "North Zone Debtors", 0, "Maharashtra", "27AAAAA0005A1Z5", "Regular"),
    ("Rajesh Computers",            "South Zone Debtors", 0, "Maharashtra", "27AAAAA0006A1Z5", "Regular"),
    ("Eastern Digital Hub",         "North Zone Debtors", 0, "Maharashtra", "27AAAAA0007A1Z5", "Regular"),
    # Creditors (5) — counter 0008..0012
    ("Samsung India Electronics",   "National Creditors", 0, "Maharashtra", "27AAAAA0008A1Z5", "Regular"),
    ("HP India Sales Pvt Ltd",      "National Creditors", 0, "Maharashtra", "27AAAAA0009A1Z5", "Regular"),
    ("Logitech India Pvt Ltd",      "National Creditors", 0, "Maharashtra", "27AAAAA0010A1Z5", "Regular"),
    ("Local Stationery Mart",       "Local Creditors",    0, "Maharashtra", "27AAAAA0011A1Z5", "Regular"),
    ("Bharat Paper Supplies",       "Local Creditors",    0, "Maharashtra", "27AAAAA0012A1Z5", "Regular"),
    # Bank & Cash (3)
    ("HDFC Bank - Current A/c", "Bank Accounts", -500000, None, None, None),
    ("SBI Savings A/c",         "Bank Accounts", -200000, None, None, None),
    ("Cash",                    "Cash-in-Hand",   -50000, None, None, None),
    # Revenue (2)
    ("Sales - Electronics",    "Sales Accounts",    0, None, None, None),
    ("Sales - Office Supplies", "Sales Accounts",   0, None, None, None),
    # Purchase (2)
    ("Purchase - Electronics",    "Purchase Accounts", 0, None, None, None),
    ("Purchase - Office Supplies", "Purchase Accounts", 0, None, None, None),
    # Expenses (8)
    ("Rent",               "Indirect Expenses", 0, None, None, None),
    ("Salaries",           "Indirect Expenses", 0, None, None, None),
    ("Electricity",        "Indirect Expenses", 0, None, None, None),
    ("Internet & Phone",   "Indirect Expenses", 0, None, None, None),
    ("Office Maintenance", "Indirect Expenses", 0, None, None, None),
    ("Travel & Conveyance","Indirect Expenses", 0, None, None, None),
    ("Courier & Freight",  "Direct Expenses",   0, None, None, None),
    ("Packing Charges",    "Direct Expenses",   0, None, None, None),
    # Tax (6) — kept for fixture compatibility; seeder uses GST_LEDGERS instead
    ("CGST Output", "Duties & Taxes", 0, None, None, None),
    ("SGST Output", "Duties & Taxes", 0, None, None, None),
    ("IGST Output", "Duties & Taxes", 0, None, None, None),
    ("CGST Input",  "Duties & Taxes", 0, None, None, None),
    ("SGST Input",  "Duties & Taxes", 0, None, None, None),
    ("IGST Input",  "Duties & Taxes", 0, None, None, None),
    # Capital (1)
    ("Capital Account", "Capital Account", 750000, None, None, None),
]

# ── Stock Items (15) ──────────────────────────────────────────────────
# (name, group, uom, selling_rate, opening_qty, opening_rate, opening_value, hsn, gst_rate)
STOCK_ITEMS = [
    # Electronics (5)
    ("Samsung 24 inch Monitor",  "Electronics", "Nos", 12500, 20, 11000, 220000, 8528, 18),
    ("HP Laptop 15s",            "Electronics", "Nos", 45000, 10, 38000, 380000, 8471, 18),
    ("Samsung Galaxy Tab A8",    "Electronics", "Nos", 16000, 15, 13500, 202500, 8471, 18),
    ("Dell Desktop Optiplex",    "Electronics", "Nos", 35000,  8, 29000, 232000, 8471, 18),
    ("Lenovo Ideapad Slim 3",    "Electronics", "Nos", 42000, 12, 36000, 432000, 8471, 18),
    # Peripherals (5)
    ("Logitech Wireless Mouse",      "Peripherals", "Nos",  800, 100,  550,  55000, 8471, 18),
    ("Logitech Keyboard K380",       "Peripherals", "Nos", 2500,  60, 1800, 108000, 8471, 18),
    ("HP DeskJet Printer 2723",      "Peripherals", "Nos", 5500,  10, 4200,  42000, 8443, 18),
    ("TP-Link WiFi Router AC750",    "Peripherals", "Nos", 1800,  25, 1300,  32500, 8517, 18),
    ("USB-C Hub 7-in-1",             "Peripherals", "Nos", 1500,  40,  950,  38000, 8471, 18),
    # Office Supplies (5)
    ("A4 Paper Ream 500 sheets", "Office Supplies", "Pcs",  350, 200, 280, 56000, 4802, 12),
    ("Whiteboard Marker Set",    "Office Supplies", "Pcs",  250,  50, 180,  9000, 9608, 12),
    ("Stapler Heavy Duty",       "Office Supplies", "Nos",  450,  30, 320,  9600, 8205, 18),
    ("Box File Pack of 10",      "Office Supplies", "Pcs",  600,  40, 420, 16800, 4820, 12),
    ("Pen Drive 32GB",           "Office Supplies", "Nos",  400,  80, 280, 22400, 8523, 18),
]

# ── Office Supply Items set (for sales ledger routing) ────────────────
OFFICE_SUPPLY_ITEMS = {
    "A4 Paper Ream 500 sheets",
    "Whiteboard Marker Set",
    "Stapler Heavy Duty",
    "Box File Pack of 10",
    "Pen Drive 32GB",
}

# ── Sales Invoices (16) ───────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, party, [(item, qty, rate)], total, narration)
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

# ── Purchase Invoices (8) ─────────────────────────────────────────────
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

# ── Payments (16) ─────────────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, payee_ledger, bank_ledger, amount, narration)
PAYMENTS = [
    ("PMT001", "20251010", "Samsung India Electronics", "HDFC Bank - Current A/c", 400000, "Part payment for PO #P001"),
    ("PMT002", "20251105", "HP India Sales Pvt Ltd",    "HDFC Bank - Current A/c", 500000, "Payment for PO #P002"),
    ("PMT003", "20251130", "Rent",                      "HDFC Bank - Current A/c",  75000, "Office rent - November"),
    ("PMT004", "20251130", "Salaries",                  "HDFC Bank - Current A/c", 250000, "Staff salaries - November"),
    ("PMT005", "20251205", "Logitech India Pvt Ltd",    "HDFC Bank - Current A/c", 150000, "Part payment PO #P003"),
    ("PMT006", "20251231", "Rent",                      "HDFC Bank - Current A/c",  75000, "Office rent - December"),
    ("PMT007", "20251231", "Salaries",                  "HDFC Bank - Current A/c", 250000, "Staff salaries - December"),
    ("PMT008", "20251231", "Electricity",               "HDFC Bank - Current A/c",  12000, "Electricity bill Q3"),
    ("PMT009", "20260115", "Local Stationery Mart",     "HDFC Bank - Current A/c",  80000, "Payment PO #P006"),
    ("PMT010", "20260131", "Rent",                      "HDFC Bank - Current A/c",  75000, "Office rent - January"),
    ("PMT011", "20260131", "Salaries",                  "HDFC Bank - Current A/c", 250000, "Staff salaries - January"),
    ("PMT012", "20260131", "Internet & Phone",          "HDFC Bank - Current A/c",   8000, "Monthly internet"),
    ("PMT013", "20260228", "Rent",                      "HDFC Bank - Current A/c",  75000, "Office rent - February"),
    ("PMT014", "20260228", "Salaries",                  "HDFC Bank - Current A/c", 250000, "Staff salaries - February"),
    ("PMT015", "20260215", "Travel & Conveyance",       "Cash",                     15000, "Sales team travel"),
    ("PMT016", "20260220", "Office Maintenance",        "Cash",                      8000, "AC servicing"),
]

# ── Receipts (10) ─────────────────────────────────────────────────────
# (voucher_number, date_YYYYMMDD, from_party, bank_ledger, amount, narration)
RECEIPTS = [
    ("RCT001", "20251020", "Apex Technologies Pvt Ltd",  "HDFC Bank - Current A/c", 94000,  "Receipt against S001"),
    ("RCT002", "20251105", "Sunrise Electronics Mumbai", "HDFC Bank - Current A/c", 110500, "Receipt against S002"),
    ("RCT003", "20251125", "Global IT Solutions",        "HDFC Bank - Current A/c", 130000, "Part receipt S003"),
    ("RCT004", "20251210", "Sharma & Sons Traders",      "SBI Savings A/c",          29500,  "Receipt against S004"),
    ("RCT005", "20251228", "Patel Enterprises",          "HDFC Bank - Current A/c", 180000, "Receipt against S005"),
    ("RCT006", "20260110", "Rajesh Computers",           "HDFC Bank - Current A/c",  25500, "Receipt against S006"),
    ("RCT007", "20260120", "Eastern Digital Hub",        "HDFC Bank - Current A/c", 116000, "Part receipt S007"),
    ("RCT008", "20260205", "Apex Technologies Pvt Ltd",  "SBI Savings A/c",          88000,  "Receipt against S008"),
    ("RCT009", "20260220", "Global IT Solutions",        "HDFC Bank - Current A/c", 262500, "Receipt S009"),
    ("RCT010", "20260301", "Patel Enterprises",          "HDFC Bank - Current A/c", 197000, "Receipt against S012"),
]

# ── Outstanding Bills ─────────────────────────────────────────────────
# Receivables: invoiced - received per party
EXPECTED_RECEIVABLES = {
    "Apex Technologies Pvt Ltd":  55000,   # 237000 - 182000
    "Sunrise Electronics Mumbai": 141000,  # 251500 - 110500
    "Global IT Solutions":        316000,  # 708500 - 392500
    "Sharma & Sons Traders":       14250,  # 43750 - 29500
    "Rajesh Computers":           139400,  # 164900 - 25500
    "Eastern Digital Hub":        159000,  # 275000 - 116000
}
# Patel Enterprises: 377000 - 377000 = 0 (fully paid)

EXPECTED_PAYABLES = {
    "Samsung India Electronics": 567500,  # 967500 - 400000
    "HP India Sales Pvt Ltd":    525600,  # 1025600 - 500000
    "Logitech India Pvt Ltd":    179000,  # 329000 - 150000
    "Local Stationery Mart":      47200,  # 127200 - 80000
    "Bharat Paper Supplies":      72000,  # 72000 - 0
}
