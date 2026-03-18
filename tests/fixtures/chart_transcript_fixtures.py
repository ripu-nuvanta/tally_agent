"""Chart pipeline E2E test fixtures.

Extracted from eval run_20260316_160527 transcript:
  tests/eval/results/run_20260316_160527/transcripts/stock_reorder_mock_20260316_161719.json

Each fixture contains:
  - query: The user query string
  - query_type: One of top_n, trend, comparison, aggregation
  - chart_suggestion: Suggested chart type
  - message: Response text with pipe-formatted markdown table (for parse_markdown_table_for_chart)

Note: The transcript stores tables in tab-separated format (as rendered by the LLM).
These fixtures convert them to pipe-separated markdown so parse_markdown_table_for_chart()
can extract the structured data. The data values are identical to the transcript's
response_data field.
"""

# ---------------------------------------------------------------------------
# Turn 2 (turn_index=1): Top 10 customers by sales amount
# query_type: top_n  |  chart_suggestion: bar
# ---------------------------------------------------------------------------

TURN_2_TOP_CUSTOMERS = {
    "query": "Top 10 customers by sales amount",
    "query_type": "top_n",
    "chart_suggestion": "bar",
    "message": (
        "🏆 Top 10 Customers by Sales Amount — FY 2025-26\n\n"
        "Global IT Solutions dominates with ₹7,08,500 across 3 invoices — "
        "nearly 1 in 3 rupees earned comes from this single customer. "
        "The data has only 7 unique customers in total, so the full ranked list "
        "is presented below (base values excl. GST).\n\n"
        "Customer Rankings\n"
        "| Rank | Customer | Invoices | Total Sales Amount | % of Total |\n"
        "|------|----------|----------|--------------------|------------|\n"
        "| 🥇 1 | Global IT Solutions | 3 | ₹7,08,500.00 | 34.4% |\n"
        "| 🥈 2 | Patel Enterprises | 2 | ₹3,77,000.00 | 18.3% |\n"
        "| 🥉 3 | Eastern Digital Hub | 2 | ₹2,75,000.00 | 13.4% |\n"
        "| 4 | Sunrise Electronics Mumbai | 2 | ₹2,51,500.00 | 12.2% |\n"
        "| 5 | Apex Technologies Pvt Ltd | 3 | ₹2,37,000.00 | 11.5% |\n"
        "| 6 | Rajesh Computers | 2 | ₹1,64,900.00 | 8.0% |\n"
        "| 7 | Sharma & Sons Traders | 2 | ₹43,750.00 | 2.1% |\n"
        "| Total | Total | 16 | ₹20,57,650.00 | 100.0% |\n\n"
        "ℹ️ Only 7 unique customers exist in FY 2025-26 sales data — "
        "full list shown rather than a truncated Top 10.\n\n"
        "🥇 Global IT Solutions is the undisputed #1 at ₹7,08,500 (34.4% share) "
        "across high-value orders: Desktops, HP Laptops, Lenovo Ideapads & Tablets.\n"
        "Top 3 customers (Global IT, Patel Enterprises, Eastern Digital Hub) "
        "collectively account for 66.1% of total sales — significant revenue concentration risk.\n"
        "Apex Technologies Pvt Ltd had the most invoices (3) but ranks only 5th at ₹2,37,000, "
        "indicating a mix of high-value electronics and lower-value office supply orders.\n"
        "Sharma & Sons Traders is the smallest customer at just ₹43,750 (2.1%), "
        "purchasing only office supplies (A4 paper, box files, stationery).\n"
        "The bottom 4 customers (Apex, Rajesh, Sharma) together contribute just 21.6% of revenue "
        "— the business is heavily dependent on its top 3 accounts."
    ),
}

# ---------------------------------------------------------------------------
# Turn 3 (turn_index=2): Month-over-month growth in sales
# query_type: trend  |  chart_suggestion: composed
# ---------------------------------------------------------------------------

TURN_3_MOM_GROWTH = {
    "query": "What's the month-over-month growth in sales for this FY?",
    "query_type": "trend",
    "chart_suggestion": "composed",
    "message": (
        "📈 Month-over-Month Sales Growth — FY 2025-26\n\n"
        "Note: No sales vouchers exist for Apr–Sep 2025. The trend starts from "
        "October 2025 (the first recorded transaction of the FY). "
        "All figures are base values (excl. GST).\n\n"
        "Monthly Sales Summary\n"
        "| Month | Vouchers | Sales Amount | Change | Change % |\n"
        "|-------|----------|--------------|--------|----------|\n"
        "| Oct 2025 | 5 | ₹5,44,000.00 | — | — (base) |\n"
        "| Nov 2025 | 3 | ₹2,29,500.00 | ▼ −₹3,14,500.00 | 🔴 −57.8% |\n"
        "| Dec 2025 | 3 | ₹4,17,750.00 | ▲ +₹1,88,250.00 | 🟢 +82.0% |\n"
        "| Jan 2026 | 2 | ₹3,36,400.00 | ▼ −₹81,350.00 | 🔴 −19.5% |\n"
        "| Feb 2026 | 2 | ₹2,14,000.00 | ▼ −₹1,22,400.00 | 🔴 −36.4% |\n"
        "| Mar 2026 | 1 | ₹3,16,000.00 | ▲ +₹1,02,000.00 | 🟢 +47.7% |\n"
        "| Total | 16 | ₹20,57,650.00 | — | — |\n\n"
        "Sales peaked at ₹5,44,000 in Oct 2025 and have been on a broadly declining "
        "trajectory since, averaging ₹2,62,730/month over Nov–Mar. "
        "The overall trend is volatile and declining from peak, though March shows a mild recovery.\n\n"
        "🏆 Oct 2025 was the peak month at ₹5,44,000 — driven by 5 invoices including "
        "high-value Lenovo Ideapads (₹1,68,000), Dell Desktops (₹1,05,000), and HP Laptops (₹90,000).\n"
        "📉 Nov 2025 saw the steepest drop — a 57.8% fall to ₹2,29,500 as no big-ticket "
        "laptop/desktop orders were recorded; only printers, routers, monitors, and tablets.\n"
        "💪 Dec 2025 bounced back +82.0% to ₹4,17,750, the second-best month, fuelled by "
        "Global IT Solutions' HP Laptop + Keyboard order (₹2,62,500) and Sunrise Electronics' "
        "Lenovo order (₹1,41,000).\n"
        "📉 Sustained weakness in Jan–Feb 2026 — two consecutive declines bringing sales to "
        "₹2,14,000 in Feb, the lowest month of the FY (only 2 vouchers each).\n"
        "🔄 Mar 2026 recovery is modest — +47.7% to ₹3,16,000 (only 1 large voucher from "
        "Global IT Solutions), but still 42% below the Oct peak; with Q4 (Jan–Mar) averaging "
        "₹2,89,000/month vs Q2 (Oct–Dec) avg of ₹3,97,083/month."
    ),
}

# ---------------------------------------------------------------------------
# Turn 4 (turn_index=3): Q3 vs Q4 revenue and expenses
# query_type: comparison  |  chart_suggestion: grouped_bar
# ---------------------------------------------------------------------------

TURN_4_Q3_VS_Q4 = {
    "query": "Compare Q3 and Q4 revenue and expenses",
    "query_type": "comparison",
    "chart_suggestion": "grouped_bar",
    "message": (
        "⚖️ Q3 vs Q4 Revenue & Expenses — FY 2025-26\n\n"
        "Q3 = Oct–Dec 2025 | Q4 = Jan–Mar 2026 | All values base (excl. GST)\n\n"
        "📊 Revenue Comparison\n"
        "| Ledger | Q3 (Oct–Dec 2025) | Q4 (Jan–Mar 2026) | Change | Change % |\n"
        "|--------|------------------|------------------|--------|----------|\n"
        "| Sales - Electronics | ₹11,39,500.00 | ₹8,11,400.00 | ▼ −₹3,28,100.00 | 🔴 −28.8% |\n"
        "| Sales - Office Supplies | ₹51,750.00 | ₹55,000.00 | ▲ +₹3,250.00 | 🟢 +6.3% |\n"
        "| Total Revenue | ₹11,91,250.00 | ₹8,66,400.00 | ▼ −₹3,24,850.00 | 🔴 −27.3% |\n\n"
        "💸 Operating Expenses Comparison\n"
        "| Ledger | Q3 (Oct–Dec 2025) | Q4 (Jan–Mar 2026) | Change | Change % |\n"
        "|--------|------------------|------------------|--------|----------|\n"
        "| Salaries | ₹5,00,000.00 | ₹5,00,000.00 | — | ➡️ Flat |\n"
        "| Rent | ₹1,50,000.00 | ₹1,50,000.00 | — | ➡️ Flat |\n"
        "| Electricity | ₹12,000.00 | ₹0.00 | ▼ −₹12,000.00 | (Q3 lump-sum; Q4 bill pending) |\n"
        "| Internet & Phone | ₹0.00 | ₹8,000.00 | ▲ +₹8,000.00 | New in Q4 |\n"
        "| Office Maintenance | ₹0.00 | ₹8,000.00 | ▲ +₹8,000.00 | New in Q4 |\n"
        "| Travel & Conveyance | ₹0.00 | ₹15,000.00 | ▲ +₹15,000.00 | New in Q4 |\n"
        "| Total OpEx | ₹6,62,000.00 | ₹6,81,000.00 | ▲ +₹19,000.00 | 🔴 +2.9% |\n\n"
        "📋 P&L Summary\n"
        "| Metric | Q3 (Oct–Dec 2025) | Q4 (Jan–Mar 2026) | Change | Change % |\n"
        "|--------|------------------|------------------|--------|----------|\n"
        "| Total Revenue | ₹11,91,250.00 | ₹8,66,400.00 | ▼ −₹3,24,850.00 | 🔴 −27.3% |\n"
        "| Total OpEx | ₹6,62,000.00 | ₹6,81,000.00 | ▲ +₹19,000.00 | 🔴 +2.9% |\n"
        "| Operating Profit | ₹5,29,250.00 | ₹1,85,400.00 | ▼ −₹3,43,850.00 | 🔴 −65.0% |\n"
        "| Operating Profit Margin | 44.4% | 21.4% | — | −23.0 pp |\n\n"
        "📉 Revenue fell sharply by ₹3,24,850 (−27.3%) from Q3 to Q4 — driven almost entirely "
        "by Electronics sales declining ₹3,28,100 (−28.8%); Q3 benefited from high-value "
        "Laptop/Desktop bulk orders (HP, Lenovo, Dell) while Q4 had fewer such orders.\n"
        "💥 Operating Profit collapsed 65.0% — from ₹5,29,250 in Q3 to just ₹1,85,400 in Q4 "
        "— as fixed costs (Salaries + Rent = ₹6,50,000/qtr) remained unchanged while revenue "
        "dropped; margin compressed from 44.4% → 21.4% (a 23 percentage point drop).\n"
        "OpEx crept up ₹19,000 (+2.9%) in Q4 due to three new expense categories — "
        "Travel & Conveyance (₹15K), Internet & Phone (₹8K), and Office Maintenance (₹8K) "
        "— partially offset by no electricity bill yet recorded.\n"
        "Office Supplies held steady and even grew marginally (+6.3%), "
        "showing stable stationery demand from Apex Technologies and Sharma & Sons."
    ),
}

# ---------------------------------------------------------------------------
# Turn 5 (turn_index=4): Expense ledger breakdown (% of total)
# query_type: aggregation  |  chart_suggestion: pie
# ---------------------------------------------------------------------------

TURN_5_EXPENSE_BREAKDOWN = {
    "query": "What percentage of total expenses does each expense ledger represent?",
    "query_type": "aggregation",
    "chart_suggestion": "pie",
    "message": (
        "💸 Expense Ledger Breakdown — FY 2025-26\n\n"
        "All figures are operating expenses only (excl. stock purchases/vendor payments). "
        "Sourced from Payment vouchers posted to date. Oct 2025 and Mar 2026 Rent & Salaries "
        "are not yet recorded — actuals reflect Nov 2025 through Feb 2026 "
        "(4 months each for fixed costs).\n\n"
        "Expense Ledger % Share\n"
        "| # | Expense Ledger | Amount (₹) | % of Total | Months Recorded |\n"
        "|---|----------------|------------|------------|------------------|\n"
        "| 🥇 | Salaries | ₹10,00,000.00 | 74.5% | Nov 2025, Dec 2025, Jan 2026, Feb 2026 |\n"
        "| 🥈 | Rent | ₹3,00,000.00 | 22.3% | Nov 2025, Dec 2025, Jan 2026, Feb 2026 |\n"
        "| 🥉 | Travel & Conveyance | ₹15,000.00 | 1.1% | Feb 2026 only |\n"
        "| 4 | Electricity | ₹12,000.00 | 0.9% | Dec 2025 (Q3 lump-sum) |\n"
        "| 5 | Internet & Phone | ₹8,000.00 | 0.6% | Jan 2026 only |\n"
        "| 6 | Office Maintenance | ₹8,000.00 | 0.6% | Feb 2026 only |\n"
        "| — | Grand Total | ₹13,43,000.00 | 100% | — |\n\n"
        "🏦 Salaries dominate at 74.5% (₹10,00,000) — at ₹2,50,000/month for 4 months, "
        "this is the single largest cost driver; fully fixed and predictable.\n"
        "🏢 Rent is the #2 cost at 22.3% (₹3,00,000) — at ₹75,000/month, "
        "Salaries + Rent together account for 96.8% of all operating expenses, "
        "leaving very little room for discretionary spend.\n"
        "🔌 Variable expenses are negligible — Electricity (₹12,000), Internet & Phone (₹8,000), "
        "Office Maintenance (₹8,000), and Travel & Conveyance (₹15,000) together make up "
        "only 3.2% (₹43,000) of total expenses.\n"
        "⚠️ Data gap note: Oct 2025 and Mar 2026 salaries/rent are not yet recorded in Tally. "
        "When added (2 × ₹3,25,000 = ₹6,50,000), the full-year total will rise to ~₹19,93,000, "
        "with Salaries and Rent maintaining similar proportions (~74–75% and ~22–23% respectively)."
    ),
}

# ---------------------------------------------------------------------------
# Turn 7 (turn_index=6): Average monthly sales amount
# query_type: trend  |  chart_suggestion: composed
# ---------------------------------------------------------------------------

TURN_7_AVG_MONTHLY = {
    "query": "What is the average monthly sales amount for this FY and which months were above/below average?",
    "query_type": "trend",
    "chart_suggestion": "composed",
    "message": (
        "📊 Average Monthly Sales — FY 2025-26\n\n"
        "No sales were recorded from Apr–Sep 2025 — the business began operations "
        "in Oct 2025. The 6-active-month average (₹3,42,942) is used as the benchmark "
        "for above/below comparisons.\n\n"
        "Key figures:\n\n"
        "🗓️ 12-Month FY Average: ₹1,71,471 (diluted by 6 zero months)\n"
        "📈 6-Active-Month Average: ₹3,42,942 ← primary benchmark\n"
        "💰 Total FY Sales: ₹20,57,650\n\n"
        "Monthly Sales vs Average (6-Month Avg: ₹3,42,942)\n"
        "| Month | Sales Amount | vs Avg (₹) | Change % | Status |\n"
        "|-------|--------------|-----------|----------|--------|\n"
        "| Apr 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| May 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| Jun 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| Jul 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| Aug 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| Sep 2025 | ₹0 | −₹3,42,942 | −100.0% | ⬇️ Below (no sales) |\n"
        "| Oct 2025 | ₹5,44,000 | +₹2,01,058 | +58.6% | ✅ Above |\n"
        "| Nov 2025 | ₹2,29,500 | −₹1,13,442 | −33.1% | ⬇️ Below |\n"
        "| Dec 2025 | ₹4,17,750 | +₹74,808 | +21.8% | ✅ Above |\n"
        "| Jan 2026 | ₹3,36,400 | −₹6,542 | −1.9% | ⬇️ Below |\n"
        "| Feb 2026 | ₹2,14,000 | −₹1,28,942 | −37.6% | ⬇️ Below |\n"
        "| Mar 2026 | ₹3,16,000 | −₹26,942 | −7.9% | ⬇️ Below |\n"
        "| Total | ₹20,57,650 | — | — | — |\n\n"
        "Only 2 of 6 active months beat the average — Oct 2025 (+58.6%) and Dec 2025 (+21.8%) "
        "are the standout months, likely driven by festive/year-end demand for electronics.\n"
        "Oct 2025 is the single strongest month at ₹5,44,000 — nearly 59% above the "
        "active-month average; this is when the business appears to have launched with "
        "large initial orders.\n"
        "Q4 trend is consistently below average — Jan, Feb, and Mar 2026 all missed the "
        "₹3,42,942 benchmark, with Feb 2026 being the weakest active month (₹2,14,000, −37.6%).\n"
        "Jan 2026 nearly hit average — at just ₹6,542 below (−1.9%), it was the closest "
        "to benchmark among Q4 months, suggesting partial recovery after a slow Feb/Mar."
    ),
}

# ---------------------------------------------------------------------------
# Overspending analysis: two tables, picks the larger (7-row), TOTAL excluded
# query_type: comparison  |  chart_suggestion: bar
# ---------------------------------------------------------------------------

TURN_OVERSPENDING = {
    "query": "Where am I overspending compared to prior months?",
    "query_type": "comparison",
    "chart_suggestion": "bar",
    "message": """**⚠️ Data Note:** March 2026 has only **1 day** of records (Mar 1 — one sales invoice + one receipt). No expense payments have been posted yet. The analysis therefore uses **February 2026** as the most recent complete month and compares it against the prior 3-month average (Nov 2025–Jan 2026).

---

## 📊 Where Are You Overspending? — February 2026 vs 3-Month Average

**Two new expense categories appeared in Feb 2026 that had zero spend in any prior month**, pushing total operating expenses to ₹3,48,000 — ₹16,333 (+4.9%) above the 3-month average.

---

### 🔺 Overspending Categories (Feb 2026)

| Rank | Expense Category | Nov '25 | Dec '25 | Jan '26 | **Feb '26** | vs 3M Avg | Note |
|------|-----------------|---------|---------|---------|------------|-----------|------|
| **#1** | **Travel & Conveyance** | — | — | — | **₹15,000** | **+₹15,000** | Brand new expense |
| **#2** | **Office Maintenance** | — | — | — | **₹8,000** | **+₹8,000** | Brand new expense |

---

### 📋 Full Operating Expense Comparison (Feb 2026 vs Prior Months)

| Category | Nov '25 | Dec '25 | Jan '26 | 3M Avg | **Feb '26** | vs Avg (₹) | vs Avg (%) |
|---|---|---|---|---|---|---|---|
| Rent | ₹75,000 | ₹75,000 | ₹75,000 | ₹75,000 | ₹75,000 | — | Flat |
| Salaries | ₹2,50,000 | ₹2,50,000 | ₹2,50,000 | ₹2,50,000 | ₹2,50,000 | — | Flat |
| Travel & Conveyance | — | — | — | — | ₹15,000 | **+₹15,000** | **New** |
| Office Maintenance | — | — | — | — | ₹8,000 | **+₹8,000** | **New** |
| Electricity | — | ₹12,000 | — | ₹4,000 | — | -₹4,000 | Not billed |
| Internet & Phone | — | — | ₹8,000 | ₹2,667 | — | -₹2,667 | Not billed |
| **TOTAL** | **₹3,25,000** | **₹3,37,000** | **₹3,33,000** | **₹3,31,667** | **₹3,48,000** | **+₹16,333** | **+4.9%** |

---

- **#1 overspend: Travel & Conveyance at ₹15,000** — this is a brand-new expense category with no prior booking in any previous month. The sales team travel (PMT015) is the sole driver.
- **Office Maintenance (₹8,000)** is also a first-time expense — AC servicing charged in Feb 2026, with no equivalent in prior months.
- **Rent (₹75,000) and Salaries (₹2,50,000)** are perfectly flat across all months — these are fixed, non-overspent costs.
- **Electricity and Internet & Phone** are absent in Feb 2026 — these tend to be billed quarterly or irregularly, so they may appear in upcoming months and spike total spend.
- **Overall overspend is modest at +₹16,333 (+4.9%)**, but the emergence of Travel & Maintenance costs signals new recurring categories to budget for going forward.

Chart suggestion: bar
Chart title: Feb 2026 Operating Expenses vs 3-Month Average (Nov '25–Jan '26)""",
}

# ---------------------------------------------------------------------------
# Overdue receivables: two tables, picks Table 1 (7 rows > 5 rows),
# Rank skipped, Grand Total excluded, % of Total on secondary axis
# query_type: top_n  |  chart_suggestion: bar
# ---------------------------------------------------------------------------

TURN_OVERDUE_RECEIVABLES = {
    "query": "Which customers are delaying payments and impacting cash flow?",
    "query_type": "top_n",
    "chart_suggestion": "bar",
    "message": """## 💸 Customers Delaying Payments & Impacting Cash Flow

**₹8,24,650 is locked in unpaid receivables** across 6 customers, with **5 customers already past their due date**. The oldest unpaid invoice is **76 days overdue** — more than 2.5 months past due.

> 📌 All figures are invoice amounts (incl. GST). Reference date: **1 Mar 2026**.

---

### 🚨 Overdue Customers — Ranked by Age of Delay

| Rank | Customer | Due Date | Overdue Days | Aging Bucket | Pending Amount | % of Total |
|------|----------|----------|-------------|--------------|----------------|------------|
| **#1** | **Sunrise Electronics Mumbai** | 15-Dec-2025 | **76 days** | 🔴 61–90 days | **₹1,41,000** | 17.1% |
| #2 | Sharma & Sons Traders | 28-Dec-2025 | **63 days** | 🔴 61–90 days | ₹14,250 | 1.7% |
| #3 | Rajesh Computers | 20-Jan-2026 | **40 days** | 🟠 31–60 days | ₹1,39,400 | 16.9% |
| #4 | Eastern Digital Hub | 05-Feb-2026 | **24 days** | 🟡 1–30 days | ₹1,59,000 | 19.3% |
| #5 | Apex Technologies Pvt Ltd | 15-Feb-2026 | **14 days** | 🟡 1–30 days | ₹55,000 | 6.7% |
| — | Global IT Solutions | 01-Mar-2026 | 0 days | 🟢 Current | ₹3,16,000 | 38.3% |
| | **Grand Total** | | | | **₹8,24,650** | **100%** |

---

### 📦 Aging Bucket Summary

| Aging Bucket | Customers | Pending Amount | % Share |
|---|---|---|---|
| 🔴 61–90 days (Critical) | 2 | ₹1,55,250 | 18.8% |
| 🟠 31–60 days (High Risk) | 1 | ₹1,39,400 | 16.9% |
| 🟡 1–30 days (Watch) | 2 | ₹2,14,000 | 26.0% |
| 🟢 Current (Not yet due) | 1 | ₹3,16,000 | 38.3% |
| **Total** | **6** | **₹8,24,650** | **100%** |

---

### Key Insights

- **#1 Worst offender: Sunrise Electronics Mumbai** — ₹1,41,000 unpaid for **76 days**, now in the critical 61–90 day bucket. Immediate escalation recommended.
- **Rajesh Computers** (₹1,39,400, 40 days) and **Eastern Digital Hub** (₹1,59,000, 24 days) together account for **₹2,98,400 — 36.2%** of total overdue; both need urgent follow-up before they slip into the critical bucket.
- **Global IT Solutions** holds the **largest single invoice at ₹3,16,000** but is technically current (due today, 1 Mar 2026) — monitor closely to ensure timely payment.
- **₹5,08,650** (61.7% of total receivables) is already **past due**, creating significant working capital pressure, especially given Feb 2026's rising expense trend noted earlier.

Chart suggestion: bar
Chart title: Overdue Receivables by Customer — Days Past Due & Pending Amount""",
}
