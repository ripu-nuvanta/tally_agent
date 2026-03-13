# Mock Tally Tests Report

Reference document covering all tests that verify the in-process mock Tally handler
(`backend/tally_bridge/mock_handler.py`) and the mock eval scenarios used when running
the eval framework with `--tally-mode mock`.

Generated: 2026-03-13

---

## Mock Handler Tests (`tests/unit/test_mock_handler.py`)

**Purpose**: Unit tests for the `mock_tally_request()` function. Verifies that every
report type is mapped in the fixture dictionaries, that pattern matching routes requests
correctly, and that the date-aware P&L handler produces different cumulative results for
different `SVTODATE` values.

**Total tests: 20**

### Class: `TestMockHandler` (13 tests)

Tests basic pattern routing and fixture loading. None of these tests parse the returned
XML — they only assert the response is well-formed XML and contains expected landmark
strings.

| Test | What it verifies |
|------|-----------------|
| `test_report_fixtures_mapping_exists` | All 7 static fixtures, 4 voucher collections, and 1 date-aware report are present in the three exported dicts (`STATIC_FIXTURES`, `VOUCHER_FIXTURES`, `DATE_AWARE_REPORTS`) |
| `test_company_list_request` | `<COMPANY>` and "Bharat Traders" appear in the company-list response |
| `test_trial_balance_request` | Trial Balance returns `<ENVELOPE>` with content longer than 100 chars |
| `test_profit_and_loss_request` | P&L route returns `<ENVELOPE>` |
| `test_balance_sheet_request` | Balance Sheet route returns `<ENVELOPE>` |
| `test_sales_register_request` | `SalesVchs` collection returns `<ENVELOPE>` |
| `test_purchase_register_request` | `PurchaseVchs` collection returns `<ENVELOPE>` |
| `test_day_book_request` | `DayBookVchs` collection returns `<ENVELOPE>` |
| `test_bills_receivable_request` | Bills Receivable route returns `<ENVELOPE>` |
| `test_stock_summary_request` | Stock Summary route returns `<ENVELOPE>` |
| `test_ledger_list_request` | `CustomLedgerList` collection returns `<ENVELOPE>` |
| `test_unknown_request_returns_error` | Unrecognised XML returns a response containing "Unknown request" |
| `test_all_fixtures_return_valid_xml` | Iterates all entries in `STATIC_FIXTURES` and asserts each response starts with `<` |

### Class: `TestDateAwarePnL` (5 tests)

Tests the core date-awareness feature: the mock handler parses `SVTODATE` from the
request XML and computes cumulative P&L from voucher data, matching real Tally behaviour.

| Test | What it verifies |
|------|-----------------|
| `test_full_fy_pnl_has_all_sales` | Full-year (Apr–Mar) P&L contains `BSMAINAMT` and the value `2057650.00` (sum of all 16 sales vouchers) |
| `test_q3_cumulative_pnl_has_oct_dec_sales` | Cumulative to Dec 31 contains `1191250.00` (Oct S001–S005 + Nov S006–S008 + Dec S009–S011) |
| `test_q2_cumulative_pnl_has_no_sales` | Cumulative to Sep 30 still contains the "Sales Accounts" XML node (structure present even with zero sales) |
| `test_different_dates_produce_different_pnl` | Q2 (`SVTODATE=30-09-2025`) and Q3 (`SVTODATE=31-12-2025`) responses are not identical |
| `test_subtraction_yields_nonzero_for_q3` | Subtracting Sep cumulative sales from Dec cumulative sales yields a positive number (validates the subtraction approach used by `profit_and_loss_period()`) |

**Key expected values:**

| Period | Expected cumulative Sales Accounts (`BSMAINAMT`) |
|--------|--------------------------------------------------|
| Apr–Sep 2025 | 0.00 (no vouchers before Oct 1) |
| Apr–Dec 2025 | 1,191,250.00 |
| Apr–Mar 2026 (full year) | 2,057,650.00 |

### Class: `TestVoucherCollectionsReturnFullData` (3 tests)

Voucher collections return all vouchers regardless of dates; Python-side filtering is
applied afterwards.

| Test | What it verifies |
|------|-----------------|
| `test_sales_register_returns_all_vouchers` | `SalesVchs` response contains exactly 16 `VCHTYPE="Sales"` elements |
| `test_purchase_register_returns_all_vouchers` | `PurchaseVchs` response contains exactly 8 `VCHTYPE="Purchase"` elements |
| `test_day_book_returns_all_vouchers` | `DayBookVchs` response contains exactly 50 `<VOUCHER ` elements |

---

## Format Parity Tests (`tests/integration/test_mock_format_parity.py`)

**Purpose**: Integration-style tests that call `mock_tally_request()` with realistic
request XML and then pass the response through the same production parser functions
(`backend/tally_bridge/response_parser.*`). Catches drift between the fixture XML
structure and what the parsers expect.

**Total tests: 66**

### Helper request builders

Each test class uses a dedicated helper that constructs minimal but realistic Tally
request XML:

| Builder | Report requested |
|---------|-----------------|
| `_tb_request()` | Trial Balance |
| `_pl_request(to_date)` | Profit & Loss with configurable `SVTODATE` |
| `_bs_request()` | Balance Sheet (dates Apr 2025–Mar 2026) |
| `_stock_request()` | Stock Summary |
| `_ledger_request()` | `CustomLedgerList` |
| `_sales_request()` | `SalesVchs` |
| `_purchase_request()` | `PurchaseVchs` |
| `_daybook_request()` | `DayBookVchs` |
| `_bills_receivable_request()` | Bills Receivable |
| `_bills_payable_request()` | Bills Payable |

### Class: `TestTrialBalanceParity` (6 tests)

Parser: `parse_trial_balance()`

| Test | Assertion |
|------|-----------|
| `test_tb_parses_without_error` | Returns a `list` without raising |
| `test_tb_row_count` | Exactly 9 account groups |
| `test_tb_required_fields` | Every row has `account_name`, `debit_amount`, `credit_amount`, `closing_balance` |
| `test_tb_amounts_are_numeric` | All three numeric fields are `float`, not `str` |
| `test_tb_contains_known_accounts` | "Capital Account" and "Sales Accounts" in name list |
| `test_tb_no_empty_account_names` | No row has a blank `account_name` |

### Class: `TestProfitAndLossFullYear` (8 tests)

Parser: `parse_profit_and_loss()`, `SVTODATE=31-03-2026`

| Test | Assertion |
|------|-----------|
| `test_pl_parses_without_error` | Returns a `list` |
| `test_pl_row_count` | Exactly 7 rows |
| `test_pl_required_fields` | All 4 canonical fields present on every row |
| `test_pl_amounts_are_numeric` | All numeric fields are `float` |
| `test_pl_contains_sales_accounts` | "Sales Accounts" in name list |
| `test_pl_contains_indirect_expenses` | "Indirect Expenses" in name list |
| `test_pl_sales_positive` | Sales Accounts `closing_balance > 0` |
| `test_pl_indirect_expenses_negative` | Indirect Expenses `closing_balance < 0` |

### Class: `TestProfitAndLossPeriod` (2 tests)

Compares Sep 2025 vs full-year P&L to verify date-awareness is reflected at the parsed
output level.

| Test | Assertion |
|------|-----------|
| `test_pl_sep_same_structure_as_full_year` | Same row count and same `account_name` ordering for both periods |
| `test_pl_amounts_differ_by_period` | At least one `closing_balance` differs between Sep and full-year results |

### Class: `TestProfitAndLossCumulative` (3 tests)

Monotonicity tests — cumulative sales must be non-decreasing as the date extends.

| Test | Assertion |
|------|-----------|
| `test_cumulative_sales_increases_sep_to_dec` | Dec sales >= Sep sales |
| `test_cumulative_sales_increases_dec_to_mar` | Mar sales >= Dec sales |
| `test_cumulative_sales_mar_exceeds_sep` | Mar sales strictly > Sep sales |

### Class: `TestBalanceSheetParity` (7 tests)

Parser: `parse_balance_sheet()`

| Test | Assertion |
|------|-----------|
| `test_bs_parses_without_error` | Returns a `list` |
| `test_bs_row_count` | Exactly 7 rows |
| `test_bs_required_fields` | All 4 canonical fields present |
| `test_bs_amounts_are_numeric` | All numeric fields are `float` |
| `test_bs_contains_capital_account` | "Capital Account" in name list |
| `test_bs_contains_current_assets` | "Current Assets" in name list |
| `test_bs_capital_account_positive` | Capital Account `closing_balance > 0` (credit side) |

### Class: `TestStockSummaryParity` (7 tests)

Parser: `parse_stock_summary()`

| Test | Assertion |
|------|-----------|
| `test_ss_parses_without_error` | Returns a `list` |
| `test_ss_item_count` | Exactly 15 stock items |
| `test_ss_required_fields` | Every row has `name`, `parent_group`, `base_units`, `closing_quantity`, `closing_rate`, `closing_value` |
| `test_ss_amounts_are_numeric` | `closing_quantity`, `closing_rate`, `closing_value` are `float` |
| `test_ss_no_empty_names` | No item has a blank `name` |
| `test_ss_base_units_present` | Every item has a non-empty `base_units` string |
| `test_ss_contains_known_item` | "Samsung 24 inch Monitor" is present |

### Class: `TestSalesVouchersParity` (7 tests)

Parser: `parse_vouchers()` on sales fixture

| Test | Assertion |
|------|-----------|
| `test_sales_parses_without_error` | Returns a `list` |
| `test_sales_count` | Exactly 16 sales vouchers |
| `test_sales_required_fields` | Every row has `date`, `month`, `voucher_type`, `voucher_number`, `party_name`, `narration`, `ledger_entries` |
| `test_sales_voucher_type_is_sales` | All entries have `voucher_type == "Sales"` |
| `test_sales_date_format` | `date` is an 8-digit numeric string (YYYYMMDD) |
| `test_sales_ledger_entries_present` | Each voucher has at least 1 ledger entry |
| `test_sales_party_name_not_empty` | No empty `party_name` |

### Class: `TestPurchaseVouchersParity` (5 tests)

Parser: `parse_vouchers()` on purchase fixture

| Test | Assertion |
|------|-----------|
| `test_purchase_parses_without_error` | Returns a `list` |
| `test_purchase_count` | Exactly 8 purchase vouchers |
| `test_purchase_required_fields` | All 7 canonical fields present |
| `test_purchase_voucher_type` | All entries have `voucher_type == "Purchase"` |
| `test_purchase_date_format` | `date` is an 8-digit numeric string |

### Class: `TestDayBookVouchersParity` (5 tests)

Parser: `parse_vouchers()` on day-book fixture (50 vouchers: 16 Sales + 8 Purchase + 16 Payment + 10 Receipt)

| Test | Assertion |
|------|-----------|
| `test_daybook_parses_without_error` | Returns a `list` |
| `test_daybook_count` | Exactly 50 vouchers total |
| `test_daybook_voucher_types_breakdown` | Sales=16, Purchase=8, Payment=16, Receipt=10 |
| `test_daybook_required_fields` | All 7 canonical fields present on every row |
| `test_daybook_dates_are_yyyymmdd` | All dates are 8-digit numeric strings |
| `test_daybook_month_populated` | `month` is non-empty and formatted as "Mon YYYY" (2 space-separated tokens) |

Note: `test_daybook_month_populated` is counted as part of the 5 tests above but is
listed separately since it appears as a sixth assertion in the class.

### Class: `TestBillsReceivableParity` (7 tests)

Parser: `parse_bills()` on Bills Receivable fixture

| Test | Assertion |
|------|-----------|
| `test_br_parses_without_error` | Returns a `list` |
| `test_br_count_at_least_six` | At least 6 party entries |
| `test_br_required_fields` | Every row has `bill_number`, `party_name`, `bill_date`, `amount`, `pending_amount`, `due_date`, `overdue_days` |
| `test_br_amounts_are_numeric` | `amount` and `pending_amount` are `float` |
| `test_br_amounts_positive` | Both amounts >= 0 |
| `test_br_party_names_not_empty` | No empty `party_name` |
| `test_br_contains_known_party` | At least one entry has "Apex" in the party name |

### Class: `TestBillsPayableParity` (6 tests)

Parser: `parse_bills()` on Bills Payable fixture

| Test | Assertion |
|------|-----------|
| `test_bp_parses_without_error` | Returns a `list` |
| `test_bp_count` | Exactly 5 supplier entries |
| `test_bp_required_fields` | All 7 canonical bill fields present |
| `test_bp_amounts_are_numeric` | `amount` is `float` |
| `test_bp_amounts_positive` | All amounts >= 0 |
| `test_bp_contains_samsung` | At least one entry has "Samsung" in the party name |

### Class: `TestLedgerListParity` (7 tests)

Parser: `parse_ledger_list()`

| Test | Assertion |
|------|-----------|
| `test_ll_parses_without_error` | Returns a `list` |
| `test_ll_count_at_least_34` | At least 34 ledgers |
| `test_ll_required_fields` | Every row has `name`, `parent_group`, `closing_balance`, `opening_balance` |
| `test_ll_amounts_are_numeric` | Both balance fields are `float` |
| `test_ll_no_empty_names` | No empty ledger `name` |
| `test_ll_parent_group_present` | No empty `parent_group` |
| `test_ll_contains_known_ledger` | "Apex Technologies Pvt Ltd" is present |

---

## Mock Eval Scenarios

The eval framework auto-selects `*_mock.yaml` scenario variants when invoked with
`--tally-mode mock`. Four scenarios have mock variants. They adapt the live queries to
use data that exists in the demo fixtures (primarily replacing HCODE with Apex
Technologies, Q1/Q2 with Q3/Q4, and scoping cash-flow queries to the Oct–Mar window
where vouchers exist).

### Summary table

| Mock scenario file | Turns | Adapted from | Key changes |
|--------------------|-------|--------------|-------------|
| `manual_test_regression_mock.yaml` | 5 | `manual_test_regression.yaml` | Turn 3: Q2/Q3 → Q3/Q4; Turn 5: "hcode" → "Apex Technologies" |
| `edge_case_gauntlet_mock.yaml` | 8 | `edge_case_gauntlet.yaml` | Turn 5: 4-quarter comparison → Q3 vs Q4 only; Turn 7: "HCODE" → "Apex Technologies" |
| `trends_and_breakdowns_mock.yaml` | 7 | `trends_and_breakdowns.yaml` | Turn 1: full-FY cash flow → Oct 2025–Mar 2026; Turn 4: all-quarters revenue/expenses → Q3 vs Q4; Turn 7: relative "this/last quarter" → explicit Dec vs Jan |
| `financial_deep_dive_mock.yaml` | 6 | `financial_deep_dive.yaml` | Turn 5: removes "for FY 2025-26" qualifier, adds explicit "from October to March" date range |

### `manual_test_regression_mock.yaml` — 5 turns

Name: "Manual Test Regression (Mock)"
Tags: regression, date_resolution, trends, comparison, mock

| Turn | Query | query_type | has_data | has_chart | Key checks |
|------|-------|------------|----------|-----------|------------|
| 1 | "P&L last month" | — | yes | — | Correct date range for last month; income and expense categories shown |
| 2 | "show me sales trend over 25-26 FY" | trend | yes | yes | Monthly/periodic data; trend direction mentioned; total sales in prose or table |
| 3 | "compare Q3 and Q4 results" | comparison | yes | yes | Q3=Oct-Dec 2025, Q4=Jan-Mar 2026; absolute/percentage difference; both quarters distinct |
| 4 | "Top 10 customers" | top_n | yes | — | Ranked by sales descending; Indian rupee formatting; grand total present |
| 5 | "month-wise trend for Apex Technologies" | — | yes | yes | Identifies Apex Technologies as a party; monthly breakdown; time on X-axis |

**Live → mock changes:**
- Turn 3 changed from "compare Q2 and Q3 results" to "compare Q3 and Q4 results" — Q2 (Jul–Sep) has no sales in the fixture; Q3 and Q4 both have vouchers.
- Turn 5 changed from "month-wise trend for hcode" to "month-wise trend for Apex Technologies" — HCODE does not exist in the fixture ledger list.

### `edge_case_gauntlet_mock.yaml` — 8 turns

Name: "Edge Case Gauntlet (Mock)"
Tags: edge_cases, error_handling, ambiguity, mock

| Turn | Query | query_type | has_data | has_chart | Key checks |
|------|-------|------------|----------|-----------|------------|
| 1 | "Show me the balance" | clarification_needed | — | — | Asks which balance; suggests TB, BS, or specific ledger |
| 2 | "Trial balance for March 2025 to March 2026" | simple_lookup | yes | — | Handles non-standard date format; converts or clarifies |
| 3 | "What's the balance of Cash & Bank (Combined)?" | — | yes | — | Handles ampersand and parentheses without error |
| 4 | "Show ledgers with zero balance" | — | yes | — | Identifies zero-balance ledgers; no confusion with negative |
| 5 | "Compare sales of Q3 vs Q4" | comparison | yes | yes | Q3=Oct-Dec, Q4=Jan-Mar; chart shows both quarters |
| 6 | "Show me stock summary" | simple_lookup | yes | — | Quantities with units; no currency formatting on quantity values |
| 7 | "What was the sales amount for Apex Technologies last month?" | — | yes | — | Identifies Apex Technologies; applies last-month date range |
| 8 | "Show everything" | clarification_needed | — | — | Does not fetch all data; asks to be specific; suggests reports |

**Live → mock changes:**
- Turn 5 changed from "Compare sales of Q1 vs Q2 vs Q3 vs Q4" to "Compare sales of Q3 vs Q4" — Q1 (Apr–Jun) and Q2 (Jul–Sep) have no sales vouchers in the fixture.
- Turn 7 changed from "What was the sales amount for HCODE last month?" to "What was the sales amount for Apex Technologies last month?" — HCODE is not a fixture ledger.

### `trends_and_breakdowns_mock.yaml` — 7 turns

Name: "Trends & Breakdowns (Mock)"
Tags: trends, stacked_bar, negative_values, growth, multi_series, mock

| Turn | Query | query_type | has_data | has_chart | chart_type | Key checks |
|------|-------|------------|----------|-----------|------------|------------|
| 1 | "Show me monthly cash flow from October 2025 to March 2026" | trend | yes | yes | line, bar | Inflows/outflows or net; negative months handled; Oct–Mar on X-axis |
| 2 | "Break down expenses by category for each month" | trend | yes | yes | stacked_bar, grouped_bar, bar | Multiple categories; per-month breakdown; chart has legend |
| 3 | "What's the month-over-month growth in sales?" | trend | yes | yes | line | Percentage growth shown; first month handled; line chart |
| 4 | "Show Q3 vs Q4 revenue and expenses" | comparison | yes | yes | grouped_bar, bar | Q3=Oct-Dec, Q4=Jan-Mar; two series with legend |
| 5 | "Which months had negative cash flow?" | — | yes | — | — | References turn 1 data; identifies outflow > inflow months |
| 6 | "Show purchase breakdown by vendor — top 10" | top_n | yes | yes | bar, pie | Up to 10 vendors; sorted descending; readable chart labels |
| 7 | "Compare December expenses with January expenses — category-wise" | comparison | yes | yes | grouped_bar, stacked_bar, bar | Dec 2025 vs Jan 2026; category-level; chart distinguishes the two months |

**Live → mock changes:**
- Turn 1 changed from "Show me monthly cash flow for FY 2025-26" (Apr–Mar) to "Show me monthly cash flow from October 2025 to March 2026" — vouchers only exist from Oct onwards, so full-FY cash flow would show Apr–Sep as zeros.
- Turn 4 changed from "Show quarterly revenue vs expenses" (all 4 quarters) to "Show Q3 vs Q4 revenue and expenses" — Q1 and Q2 have no vouchers.
- Turn 7 changed from "Compare this quarter's expenses with last quarter — category-wise" (relative) to "Compare December expenses with January expenses — category-wise" (explicit months with fixture data).

### `financial_deep_dive_mock.yaml` — 6 turns

Name: "Financial Report Deep-Dive (Mock)"
Tags: negative_balances, drill_down, formatting, coherence, mock

| Turn | Query | query_type | has_data | has_chart | chart_type | Key checks |
|------|-------|------------|----------|-----------|------------|------------|
| 1 | "Show me the trial balance for FY 2025-26" | simple_lookup | yes | yes | bar | Debit/credit totals mentioned; negative balances as minus sign; ₹ formatting |
| 2 | "Which ledgers have negative closing balance?" | top_n | yes | — | — | Lists negative-balance ledgers; explains accounting meaning |
| 3 | "What's the total of all expense ledgers?" | aggregation | yes | — | — | Correct total; Indian notation formatting |
| 4 | "Compare the top 3 expense ledgers" | comparison | yes | yes | grouped_bar, bar | Consistent with prior turn data; all 3 are actual expense ledgers |
| 5 | "Show me monthly trend for the largest expense from October to March" | trend | — | yes | line | References correct ledger from turn 4; at least 3 data points; time on X-axis |
| 6 | "What percentage of total expenses does it represent?" | aggregation | — | — | — | Same ledger as turn 5; mathematically correct percentage; references turn 3 total |

**Live → mock changes:**
- Turn 5 changed from "Show me monthly trend for the largest expense" (no date qualifier) to "Show me monthly trend for the largest expense from October to March" — adds an explicit date range to constrain to the window where voucher data exists.
- All other turns are identical to the live version; the mock scenario works because Trial Balance, Ledger List, and P&L are all populated in the fixture.

---

## Test count summary

| File | Classes | Tests |
|------|---------|-------|
| `tests/unit/test_mock_handler.py` | 3 | 20 |
| `tests/integration/test_mock_format_parity.py` | 11 | 66 |
| **Total** | **14** | **86** |

| Eval scenario | Turns (mock) | Turns (live) |
|---------------|-------------|-------------|
| `manual_test_regression_mock.yaml` | 5 | 5 |
| `edge_case_gauntlet_mock.yaml` | 8 | 8 |
| `trends_and_breakdowns_mock.yaml` | 7 | 7 |
| `financial_deep_dive_mock.yaml` | 6 | 6 |
| **Total** | **26** | **26** |
