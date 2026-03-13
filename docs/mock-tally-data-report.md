# Mock Tally Data Reference Report

Source of truth: `tests/fixtures/generate_fixtures.py`
Generated fixture files: `tests/fixtures/*.xml`

---

## 1. Company

**Bharat Traders Pvt Ltd**
Electronics & Office Supplies trader, Maharashtra
Financial Year: April 2025 – March 2026
Data coverage: October 2025 – March 2026 (H2 of FY)

---

## 2. Ledgers (34 total)

Opening balances reflect pre-FY positions. All zero-opening ledgers accumulate balances purely from voucher activity.

### Debtors (7)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Apex Technologies Pvt Ltd | North Zone Debtors | 0 |
| Sunrise Electronics Mumbai | South Zone Debtors | 0 |
| Global IT Solutions | North Zone Debtors | 0 |
| Sharma & Sons Traders | South Zone Debtors | 0 |
| Patel Enterprises | North Zone Debtors | 0 |
| Rajesh Computers | South Zone Debtors | 0 |
| Eastern Digital Hub | North Zone Debtors | 0 |

### Creditors (5)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Samsung India Electronics | National Creditors | 0 |
| HP India Sales Pvt Ltd | National Creditors | 0 |
| Logitech India Pvt Ltd | National Creditors | 0 |
| Local Stationery Mart | Local Creditors | 0 |
| Bharat Paper Supplies | Local Creditors | 0 |

### Bank & Cash (3)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| HDFC Bank - Current A/c | Bank Accounts | ₹5,00,000 (debit) |
| SBI Savings A/c | Bank Accounts | ₹2,00,000 (debit) |
| Cash | Cash-in-Hand | ₹50,000 (debit) |

Note: Negative opening balance in Tally convention = debit (asset). The code stores these as `-500000`, `-200000`, `-50000`.

### Revenue Ledgers (2)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Sales - Electronics | Sales Accounts | 0 |
| Sales - Office Supplies | Sales Accounts | 0 |

### Purchase Ledgers (2)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Purchase - Electronics | Purchase Accounts | 0 |
| Purchase - Office Supplies | Purchase Accounts | 0 |

### Expense Ledgers (8)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Rent | Indirect Expenses | 0 |
| Salaries | Indirect Expenses | 0 |
| Electricity | Indirect Expenses | 0 |
| Internet & Phone | Indirect Expenses | 0 |
| Office Maintenance | Indirect Expenses | 0 |
| Travel & Conveyance | Indirect Expenses | 0 |
| Courier & Freight | Direct Expenses | 0 |
| Packing Charges | Direct Expenses | 0 |

Note: Courier & Freight and Packing Charges have no voucher activity in the current dataset (no payments made to them).

### Tax Ledgers (6)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| CGST Output | Duties & Taxes | 0 |
| SGST Output | Duties & Taxes | 0 |
| IGST Output | Duties & Taxes | 0 |
| CGST Input | Duties & Taxes | 0 |
| SGST Input | Duties & Taxes | 0 |
| IGST Input | Duties & Taxes | 0 |

Note: GST ledgers have no voucher activity (invoices use pre-tax totals; GST not separately booked in mock data).

### Capital (1)

| Name | Parent Group | Opening Balance |
|------|-------------|----------------|
| Capital Account | Capital Account | ₹7,50,000 (credit) |

---

## 3. Stock Items (15 total)

Closing quantity = Opening Qty − Sold Qty + Purchased Qty. Closing value uses opening rate as approximation.

### Electronics (5)

| Name | Group | UOM | Selling Rate | Open Qty | Open Rate | Open Value | Sold | Bought | Close Qty | Close Value |
|------|-------|-----|-------------|----------|-----------|------------|------|--------|-----------|-------------|
| Samsung 24 inch Monitor | Electronics | Nos | ₹12,500 | 20 | ₹11,000 | ₹2,20,000 | 23 | 45 | 42 | ₹4,62,000 |
| HP Laptop 15s | Electronics | Nos | ₹45,000 | 10 | ₹38,000 | ₹3,80,000 | 10 | 25 | 25 | ₹9,50,000 |
| Samsung Galaxy Tab A8 | Electronics | Nos | ₹16,000 | 15 | ₹13,500 | ₹2,02,500 | 12 | 35 | 38 | ₹5,13,000 |
| Dell Desktop Optiplex | Electronics | Nos | ₹35,000 | 8 | ₹29,000 | ₹2,32,000 | 8 | 0 | 0 | ₹0 |
| Lenovo Ideapad Slim 3 | Electronics | Nos | ₹42,000 | 12 | ₹36,000 | ₹4,32,000 | 13 | 0 | −1 | −₹36,000 |

Note: Dell Desktop Optiplex closes at zero (8 opening sold exactly). Lenovo shows −1 due to selling 13 (S005: 4 + S010: 3 + S016: 6) against 12 opening with no purchase — likely a data edge case.

### Peripherals (5)

| Name | Group | UOM | Selling Rate | Open Qty | Open Rate | Open Value | Sold | Bought | Close Qty | Close Value |
|------|-------|-----|-------------|----------|-----------|------------|------|--------|-----------|-------------|
| Logitech Wireless Mouse | Peripherals | Nos | ₹800 | 100 | ₹550 | ₹55,000 | 55 | 250 | 295 | ₹1,62,250 |
| Logitech Keyboard K380 | Peripherals | Nos | ₹2,500 | 60 | ₹1,800 | ₹1,08,000 | 25 | 80 | 115 | ₹2,07,000 |
| HP DeskJet Printer 2723 | Peripherals | Nos | ₹5,500 | 10 | ₹4,200 | ₹42,000 | 7 | 18 | 21 | ₹88,200 |
| TP-Link WiFi Router AC750 | Peripherals | Nos | ₹1,800 | 25 | ₹1,300 | ₹32,500 | 13 | 0 | 12 | ₹15,600 |
| USB-C Hub 7-in-1 | Peripherals | Nos | ₹1,500 | 40 | ₹950 | ₹38,000 | 18 | 50 | 72 | ₹68,400 |

Logitech Mouse qty detail: Sold = S001(5) + S007(20) + S014(30) = 55; Bought = P003(150) + P007(100) = 250.

### Office Supplies (5)

| Name | Group | UOM | Selling Rate | Open Qty | Open Rate | Open Value | Sold | Bought | Close Qty | Close Value |
|------|-------|-----|-------------|----------|-----------|------------|------|--------|-----------|-------------|
| A4 Paper Ream 500 sheets | Office Supplies | Pcs | ₹350 | 200 | ₹280 | ₹56,000 | 150 | 500 | 550 | ₹1,54,000 |
| Whiteboard Marker Set | Office Supplies | Pcs | ₹250 | 50 | ₹180 | ₹9,000 | 30 | 100 | 120 | ₹21,600 |
| Stapler Heavy Duty | Office Supplies | Nos | ₹450 | 30 | ₹320 | ₹9,600 | 15 | 50 | 65 | ₹20,800 |
| Box File Pack of 10 | Office Supplies | Pcs | ₹600 | 40 | ₹420 | ₹16,800 | 20 | 60 | 80 | ₹33,600 |
| Pen Drive 32GB | Office Supplies | Nos | ₹400 | 80 | ₹280 | ₹22,400 | 70 | 0 | 10 | ₹2,800 |

A4 Paper: Sold = S004(50) + S015(100) = 150; Bought = P006(300) + P008(200) = 500.

**Total Opening Stock Value: ₹14,35,300**

---

## 4. Sales Invoices (16 total)

All dates in DD-MMM-YYYY. Items listed as (Name, Qty × Rate).

| VNo | Date | Party | Items | Total |
|-----|------|-------|-------|-------|
| S001 | 01-Oct-2025 | Apex Technologies Pvt Ltd | HP Laptop 15s (2 × ₹45,000), Logitech Wireless Mouse (5 × ₹800) | ₹94,000 |
| S002 | 08-Oct-2025 | Sunrise Electronics Mumbai | Samsung 24 inch Monitor (5 × ₹12,500), Samsung Galaxy Tab A8 (3 × ₹16,000) | ₹1,10,500 |
| S003 | 15-Oct-2025 | Global IT Solutions | Dell Desktop Optiplex (3 × ₹35,000), Logitech Keyboard K380 (10 × ₹2,500) | ₹1,30,000 |
| S004 | 22-Oct-2025 | Sharma & Sons Traders | A4 Paper Ream 500 sheets (50 × ₹350), Box File Pack of 10 (20 × ₹600) | ₹29,500 |
| S005 | 30-Oct-2025 | Patel Enterprises | Lenovo Ideapad Slim 3 (4 × ₹42,000), USB-C Hub 7-in-1 (8 × ₹1,500) | ₹1,80,000 |
| S006 | 05-Nov-2025 | Rajesh Computers | HP DeskJet Printer 2723 (3 × ₹5,500), TP-Link WiFi Router AC750 (5 × ₹1,800) | ₹25,500 |
| S007 | 15-Nov-2025 | Eastern Digital Hub | Samsung 24 inch Monitor (8 × ₹12,500), Logitech Wireless Mouse (20 × ₹800) | ₹1,16,000 |
| S008 | 25-Nov-2025 | Apex Technologies Pvt Ltd | Samsung Galaxy Tab A8 (5 × ₹16,000), Pen Drive 32GB (20 × ₹400) | ₹88,000 |
| S009 | 05-Dec-2025 | Global IT Solutions | HP Laptop 15s (5 × ₹45,000), Logitech Keyboard K380 (15 × ₹2,500) | ₹2,62,500 |
| S010 | 15-Dec-2025 | Sunrise Electronics Mumbai | Lenovo Ideapad Slim 3 (3 × ₹42,000), USB-C Hub 7-in-1 (10 × ₹1,500) | ₹1,41,000 |
| S011 | 28-Dec-2025 | Sharma & Sons Traders | Whiteboard Marker Set (30 × ₹250), Stapler Heavy Duty (15 × ₹450) | ₹14,250 |
| S012 | 10-Jan-2026 | Patel Enterprises | Dell Desktop Optiplex (5 × ₹35,000), HP DeskJet Printer 2723 (4 × ₹5,500) | ₹1,97,000 |
| S013 | 20-Jan-2026 | Rajesh Computers | Samsung 24 inch Monitor (10 × ₹12,500), TP-Link WiFi Router AC750 (8 × ₹1,800) | ₹1,39,400 |
| S014 | 05-Feb-2026 | Eastern Digital Hub | HP Laptop 15s (3 × ₹45,000), Logitech Wireless Mouse (30 × ₹800) | ₹1,59,000 |
| S015 | 15-Feb-2026 | Apex Technologies Pvt Ltd | A4 Paper Ream 500 sheets (100 × ₹350), Pen Drive 32GB (50 × ₹400) | ₹55,000 |
| S016 | 01-Mar-2026 | Global IT Solutions | Lenovo Ideapad Slim 3 (6 × ₹42,000), Samsung Galaxy Tab A8 (4 × ₹16,000) | ₹3,16,000 |

**Total Sales: ₹20,57,650**

### Sales by Party

| Party | Invoices | Total |
|-------|----------|-------|
| Global IT Solutions | S003, S009, S016 | ₹7,08,500 |
| Patel Enterprises | S005, S012 | ₹3,77,000 |
| Apex Technologies Pvt Ltd | S001, S008, S015 | ₹2,37,000 |
| Eastern Digital Hub | S007, S014 | ₹2,75,000 |
| Sunrise Electronics Mumbai | S002, S010 | ₹2,51,500 |
| Rajesh Computers | S006, S013 | ₹1,64,900 |
| Sharma & Sons Traders | S004, S011 | ₹43,750 |
| **Total** | **16** | **₹20,57,650** |

### Sales by Month

| Month | Invoices | Total |
|-------|----------|-------|
| Oct-2025 | S001–S005 | ₹5,44,000 |
| Nov-2025 | S006–S008 | ₹2,29,500 |
| Dec-2025 | S009–S011 | ₹4,17,750 |
| Jan-2026 | S012–S013 | ₹3,36,400 |
| Feb-2026 | S014–S015 | ₹2,14,000 |
| Mar-2026 | S016 | ₹3,16,000 |
| **Total** | **16** | **₹20,57,650** |

---

## 5. Purchase Invoices (8 total)

| VNo | Date | Party | Items | Total |
|-----|------|-------|-------|-------|
| P001 | 28-Sep-2025 | Samsung India Electronics | Samsung 24 inch Monitor (25 × ₹11,000), Samsung Galaxy Tab A8 (20 × ₹13,500) | ₹5,45,000 |
| P002 | 20-Oct-2025 | HP India Sales Pvt Ltd | HP Laptop 15s (15 × ₹38,000), HP DeskJet Printer 2723 (10 × ₹4,200) | ₹6,12,000 |
| P003 | 10-Nov-2025 | Logitech India Pvt Ltd | Logitech Wireless Mouse (150 × ₹550), Logitech Keyboard K380 (80 × ₹1,800) | ₹2,26,500 |
| P004 | 28-Nov-2025 | Samsung India Electronics | Samsung 24 inch Monitor (20 × ₹11,000), Samsung Galaxy Tab A8 (15 × ₹13,500) | ₹4,22,500 |
| P005 | 15-Dec-2025 | HP India Sales Pvt Ltd | HP Laptop 15s (10 × ₹38,000), HP DeskJet Printer 2723 (8 × ₹4,200) | ₹4,13,600 |
| P006 | 05-Jan-2026 | Local Stationery Mart | A4 Paper Ream 500 sheets (300 × ₹280), Whiteboard Marker Set (100 × ₹180), Box File Pack of 10 (60 × ₹420) | ₹1,27,200 |
| P007 | 25-Jan-2026 | Logitech India Pvt Ltd | Logitech Wireless Mouse (100 × ₹550), USB-C Hub 7-in-1 (50 × ₹950) | ₹1,02,500 |
| P008 | 10-Feb-2026 | Bharat Paper Supplies | A4 Paper Ream 500 sheets (200 × ₹280), Stapler Heavy Duty (50 × ₹320) | ₹72,000 |

**Total Purchases: ₹25,21,300**

### Purchases by Party

| Party | Invoices | Total |
|-------|----------|-------|
| HP India Sales Pvt Ltd | P002, P005 | ₹10,25,600 |
| Samsung India Electronics | P001, P004 | ₹9,67,500 |
| Logitech India Pvt Ltd | P003, P007 | ₹3,29,000 |
| Local Stationery Mart | P006 | ₹1,27,200 |
| Bharat Paper Supplies | P008 | ₹72,000 |
| **Total** | **8** | **₹25,21,300** |

### Purchases by Month

| Month | Invoices | Total |
|-------|----------|-------|
| Sep-2025 | P001 | ₹5,45,000 |
| Oct-2025 | P002 | ₹6,12,000 |
| Nov-2025 | P003, P004 | ₹6,49,000 |
| Dec-2025 | P005 | ₹4,13,600 |
| Jan-2026 | P006, P007 | ₹2,29,700 |
| Feb-2026 | P008 | ₹72,000 |
| **Total** | **8** | **₹25,21,300** |

---

## 6. Payments (16 total)

| VNo | Date | Payee | Bank/Cash | Amount | Narration |
|-----|------|-------|-----------|--------|-----------|
| PMT001 | 10-Oct-2025 | Samsung India Electronics | HDFC Bank - Current A/c | ₹4,00,000 | Part payment for PO #P001 |
| PMT002 | 05-Nov-2025 | HP India Sales Pvt Ltd | HDFC Bank - Current A/c | ₹5,00,000 | Payment for PO #P002 |
| PMT003 | 30-Nov-2025 | Rent | HDFC Bank - Current A/c | ₹75,000 | Office rent - November |
| PMT004 | 30-Nov-2025 | Salaries | HDFC Bank - Current A/c | ₹2,50,000 | Staff salaries - November |
| PMT005 | 05-Dec-2025 | Logitech India Pvt Ltd | HDFC Bank - Current A/c | ₹1,50,000 | Part payment PO #P003 |
| PMT006 | 31-Dec-2025 | Rent | HDFC Bank - Current A/c | ₹75,000 | Office rent - December |
| PMT007 | 31-Dec-2025 | Salaries | HDFC Bank - Current A/c | ₹2,50,000 | Staff salaries - December |
| PMT008 | 31-Dec-2025 | Electricity | HDFC Bank - Current A/c | ₹12,000 | Electricity bill Q3 |
| PMT009 | 15-Jan-2026 | Local Stationery Mart | HDFC Bank - Current A/c | ₹80,000 | Payment PO #P006 |
| PMT010 | 31-Jan-2026 | Rent | HDFC Bank - Current A/c | ₹75,000 | Office rent - January |
| PMT011 | 31-Jan-2026 | Salaries | HDFC Bank - Current A/c | ₹2,50,000 | Staff salaries - January |
| PMT012 | 31-Jan-2026 | Internet & Phone | HDFC Bank - Current A/c | ₹8,000 | Monthly internet |
| PMT013 | 28-Feb-2026 | Rent | HDFC Bank - Current A/c | ₹75,000 | Office rent - February |
| PMT014 | 28-Feb-2026 | Salaries | HDFC Bank - Current A/c | ₹2,50,000 | Staff salaries - February |
| PMT015 | 15-Feb-2026 | Travel & Conveyance | Cash | ₹15,000 | Sales team travel |
| PMT016 | 20-Feb-2026 | Office Maintenance | Cash | ₹8,000 | AC servicing |

**Total Payments: ₹23,73,000**

### Payments by Category

| Category | Payee(s) | Total |
|----------|----------|-------|
| Supplier payments | Samsung, HP, Logitech, Local Stationery | ₹11,30,000 |
| Salaries | Salaries (4 months) | ₹10,00,000 |
| Rent | Rent (4 months × ₹75,000) | ₹3,00,000 |
| Electricity | Electricity | ₹12,000 |
| Internet & Phone | Internet & Phone | ₹8,000 |
| Travel & Conveyance | Travel & Conveyance | ₹15,000 |
| Office Maintenance | Office Maintenance | ₹8,000 |

---

## 7. Receipts (10 total)

| VNo | Date | From Party | Bank | Amount | Against Invoice |
|-----|------|-----------|------|--------|-----------------|
| RCT001 | 20-Oct-2025 | Apex Technologies Pvt Ltd | HDFC Bank - Current A/c | ₹94,000 | S001 (full) |
| RCT002 | 05-Nov-2025 | Sunrise Electronics Mumbai | HDFC Bank - Current A/c | ₹1,10,500 | S002 (full) |
| RCT003 | 25-Nov-2025 | Global IT Solutions | HDFC Bank - Current A/c | ₹1,30,000 | S003 (part) |
| RCT004 | 10-Dec-2025 | Sharma & Sons Traders | SBI Savings A/c | ₹29,500 | S004 (full) |
| RCT005 | 28-Dec-2025 | Patel Enterprises | HDFC Bank - Current A/c | ₹1,80,000 | S005 (full) |
| RCT006 | 10-Jan-2026 | Rajesh Computers | HDFC Bank - Current A/c | ₹25,500 | S006 (full) |
| RCT007 | 20-Jan-2026 | Eastern Digital Hub | HDFC Bank - Current A/c | ₹1,16,000 | S007 (part) |
| RCT008 | 05-Feb-2026 | Apex Technologies Pvt Ltd | SBI Savings A/c | ₹88,000 | S008 (full) |
| RCT009 | 20-Feb-2026 | Global IT Solutions | HDFC Bank - Current A/c | ₹2,62,500 | S009 (full) |
| RCT010 | 01-Mar-2026 | Patel Enterprises | HDFC Bank - Current A/c | ₹1,97,000 | S012 (full) |

**Total Receipts: ₹12,33,000**

### Receipts by Bank Account

| Bank | Receipts | Total |
|------|----------|-------|
| HDFC Bank - Current A/c | RCT001–003, RCT005–007, RCT009–010 | ₹11,15,500 |
| SBI Savings A/c | RCT004, RCT008 | ₹1,17,500 |
| **Total** | **10** | **₹12,33,000** |

---

## 8. Financial Summary

All figures are cumulative from October 2025 through March 2026 (H2 of FY 2025-26).

### Profit & Loss Account

| Line Item | Amount |
|-----------|--------|
| **Sales Revenue** | **₹20,57,650** |
| Purchase - Electronics | ₹23,22,100 |
| Purchase - Office Supplies | ₹1,99,200 |
| **Total Purchases** | **₹25,21,300** |
| **Gross Profit / (Loss)** | **(₹4,63,650)** |
| Direct Expenses (Courier & Freight, Packing) | ₹0 |
| Rent (4 months × ₹75,000) | ₹3,00,000 |
| Salaries (4 months × ₹2,50,000) | ₹10,00,000 |
| Electricity | ₹12,000 |
| Internet & Phone | ₹8,000 |
| Travel & Conveyance | ₹15,000 |
| Office Maintenance | ₹8,000 |
| **Total Indirect Expenses** | **₹13,43,000** |
| **Net Profit / (Loss)** | **(₹18,06,650)** |

Note: The net loss arises because H2 purchases (large stock restocking) exceed H2 sales revenue. The company started with ₹14,35,300 in opening stock value and ₹7,50,000 capital, reflecting a trading business where stock is an asset on the balance sheet. The P&L figure correctly reflects period activity without closing stock adjustment.

### Sales vs. Purchases by Month

| Month | Sales | Purchases | Net |
|-------|-------|-----------|-----|
| Sep-2025 | — | ₹5,45,000 | (₹5,45,000) |
| Oct-2025 | ₹5,44,000 | ₹6,12,000 | (₹68,000) |
| Nov-2025 | ₹2,29,500 | ₹6,49,000 | (₹4,19,500) |
| Dec-2025 | ₹4,17,750 | ₹4,13,600 | ₹4,150 |
| Jan-2026 | ₹3,36,400 | ₹2,29,700 | ₹1,06,700 |
| Feb-2026 | ₹2,14,000 | ₹72,000 | ₹1,42,000 |
| Mar-2026 | ₹3,16,000 | — | ₹3,16,000 |
| **Total** | **₹20,57,650** | **₹25,21,300** | **(₹4,63,650)** |

---

## 9. Outstanding Bills

### Receivables (Debtors)

Computed as: total invoiced to party − total received from party.

| Party | Invoiced | Received | Outstanding |
|-------|----------|----------|-------------|
| Global IT Solutions | ₹7,08,500 | ₹3,92,500 | ₹3,16,000 |
| Sunrise Electronics Mumbai | ₹2,51,500 | ₹1,10,500 | ₹1,41,000 |
| Eastern Digital Hub | ₹2,75,000 | ₹1,16,000 | ₹1,59,000 |
| Rajesh Computers | ₹1,64,900 | ₹25,500 | ₹1,39,400 |
| Apex Technologies Pvt Ltd | ₹2,37,000 | ₹1,82,000 | ₹55,000 |
| Sharma & Sons Traders | ₹43,750 | ₹29,500 | ₹14,250 |
| Patel Enterprises | ₹3,77,000 | ₹3,77,000 | ₹0 (fully paid) |
| **Total** | **₹20,57,650** | **₹13,32,500** | **₹8,24,650** |

Outstanding invoices detail:
- Global IT Solutions: S016 (₹3,16,000) unpaid
- Eastern Digital Hub: S014 (₹1,59,000) unpaid (S007 partially collected via RCT007 ₹1,16,000)
- Rajesh Computers: S013 (₹1,39,400) unpaid
- Sunrise Electronics Mumbai: S010 (₹1,41,000) unpaid
- Apex Technologies Pvt Ltd: S015 (₹55,000) unpaid
- Sharma & Sons Traders: S011 (₹14,250) unpaid

### Payables (Creditors)

Computed as: total purchased from party − total paid to party.

| Party | Purchased | Paid | Outstanding |
|-------|----------|------|-------------|
| HP India Sales Pvt Ltd | ₹10,25,600 | ₹5,00,000 | ₹5,25,600 |
| Samsung India Electronics | ₹9,67,500 | ₹4,00,000 | ₹5,67,500 |
| Logitech India Pvt Ltd | ₹3,29,000 | ₹1,50,000 | ₹1,79,000 |
| Bharat Paper Supplies | ₹72,000 | ₹0 | ₹72,000 |
| Local Stationery Mart | ₹1,27,200 | ₹80,000 | ₹47,200 |
| **Total** | **₹25,21,300** | **₹11,30,000** | **₹13,91,300** |

---

## 10. Date Range Coverage

| Month | Sales | Purchases | Payments | Receipts |
|-------|-------|-----------|----------|---------|
| Sep-2025 | — | P001 | — | — |
| Oct-2025 | S001, S002, S003, S004, S005 | P002 | PMT001 | RCT001 |
| Nov-2025 | S006, S007, S008 | P003, P004 | PMT002, PMT003, PMT004, PMT005 | RCT002, RCT003 |
| Dec-2025 | S009, S010, S011 | P005 | PMT006, PMT007, PMT008 | RCT004, RCT005 |
| Jan-2026 | S012, S013 | P006, P007 | PMT009, PMT010, PMT011, PMT012 | RCT006, RCT007 |
| Feb-2026 | S014, S015 | P008 | PMT013, PMT014, PMT015, PMT016 | RCT008, RCT009 |
| Mar-2026 | S016 | — | — | RCT010 |

**Voucher count by type:**

| Type | Count |
|------|-------|
| Sales Invoices | 16 |
| Purchase Invoices | 8 |
| Payments | 16 |
| Receipts | 10 |
| **Total vouchers** | **50** |

**Coverage notes:**
- Data covers Oct 2025 – Mar 2026 (Q3 + Q4 of Indian FY 2025-26)
- Q1 (Apr–Jun 2025) and Q2 (Jul–Sep 2025) have no vouchers — only P001 is dated 28-Sep-2025
- For quarter-specific queries, Q3 = Oct–Dec 2025 (invoices S001–S011, P001–P005), Q4 = Jan–Mar 2026 (invoices S012–S016, P006–P008)
- Expense payments cover Nov-2025 through Feb-2026 (4 months of rent and salaries)
- March 2026 has only one sales invoice (S016) and one receipt (RCT010) — no expense payments yet

---

## Appendix: Item-to-Ledger Routing

| Item Category | Sales Ledger | Purchase Ledger |
|---------------|-------------|----------------|
| A4 Paper Ream 500 sheets | Sales - Office Supplies | Purchase - Office Supplies |
| Whiteboard Marker Set | Sales - Office Supplies | Purchase - Office Supplies |
| Stapler Heavy Duty | Sales - Office Supplies | Purchase - Office Supplies |
| Box File Pack of 10 | Sales - Office Supplies | Purchase - Office Supplies |
| Pen Drive 32GB | Sales - Office Supplies | Purchase - Office Supplies |
| All Electronics & Peripherals | Sales - Electronics | Purchase - Electronics |
