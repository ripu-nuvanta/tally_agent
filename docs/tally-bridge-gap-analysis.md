# TallyPrime Agent — Tally Bridge Tool Layer Gap Analysis

**Generated:** 2026-03-13
**Author:** Claude Code analysis
**Scope:** `backend/agents/tools.py`, `backend/tally_bridge/queries/`, `backend/tally_bridge/request_builder.py`, `backend/tally_bridge/mock_handler.py`, `backend/agents/prompts.py`

---

## 1. All Current Agent Tools

These are the tools exposed to Claude via `TALLY_TOOLS` in `backend/agents/tools.py` plus `DATE_TOOLS` (line 272).

| Tool Name | Required Params | Optional Params | Returns |
|-----------|----------------|-----------------|---------
| `get_trial_balance` | `from_date`, `to_date` | `company` | Account names with debit/credit/closing balances |
| `get_profit_and_loss` | `from_date`, `to_date` | `company` | Income and expense groups with amounts (period-specific via subtraction) |
| `get_balance_sheet` | `as_on_date` | `company` | Assets and liabilities with amounts |
| `get_ledger_transactions` | `ledger_name`, `from_date`, `to_date` | `company` | Per-voucher: date, type, number, party, narration, ledger entries |
| `get_day_book` | `from_date`, `to_date` | `voucher_type`, `company` | All vouchers (or filtered by type) with party, narration, ledger entries |
| `get_outstanding_receivables` | `as_on_date` | `company` | Party, bill number, date, amount, pending amount |
| `get_outstanding_payables` | `as_on_date` | `company` | Party, bill number, date, amount, pending amount |
| `get_stock_summary` | `as_on_date` | `stock_group`, `company` | Item names, quantities, rates, closing values |
| `get_sales_register` | `from_date`, `to_date` | `company` | Sales vouchers with party, ledger entries (amount per line item) |
| `get_purchase_register` | `from_date`, `to_date` | `company` | Purchase vouchers with party, ledger entries |
| `search_ledger` | `search_term` | — | Matching ledger names, parent groups, opening/closing balances |
| `list_companies` | — | — | Company names loaded in Tally |
| `resolve_date_range` *(date tool)* | `description` | — | `from_date` + `to_date` in DD-MM-YYYY (Indian FY-aware) |

**Total Tally tools exposed to agent: 12 + 1 date tool = 13**

---

## 2. All Tally Bridge Query Functions

### 2a. `backend/tally_bridge/queries/masters.py`

| Function | Exposed as Tool? | Notes |
|----------|-----------------|-------|
| `list_companies(client)` | Yes — `list_companies` | Returns `list[Company]` |
| `list_ledgers(client)` | No (indirect only) | Used internally by `search_ledger`. Returns `list[Ledger]` with name, parent_group, opening/closing balance. Never returned directly to agent. |
| `search_ledger(client, search_term)` | Yes — `search_ledger` | Calls `list_ledgers` then filters by case-insensitive substring. |

**Missing query functions in masters.py (request builders exist but no query layer):**

| Request Builder | Query Function | Agent Tool |
|----------------|---------------|-----------
| `build_list_groups()` | None | None |
| `build_list_stock_items()` | None | None |

### 2b. `backend/tally_bridge/queries/reports.py`

| Function | Exposed as Tool? | Notes |
|----------|-----------------|-------|
| `trial_balance(client, from_date, to_date, company)` | Yes — `get_trial_balance` | Returns `ReportResponse` |
| `profit_and_loss(client, from_date, to_date, company)` | No (internal helper) | Used by `profit_and_loss_period`. Returns cumulative P&L. |
| `profit_and_loss_period(client, from_date, to_date, company)` | Yes — `get_profit_and_loss` | Period-specific via double-fetch subtraction |
| `balance_sheet(client, as_on_date, company)` | Yes — `get_balance_sheet` | Returns `ReportResponse` |
| `bills_receivable(client, as_on_date, company)` | Yes — `get_outstanding_receivables` | Returns `list[OutstandingBill]` |
| `bills_payable(client, as_on_date, company)` | Yes — `get_outstanding_payables` | Returns `list[OutstandingBill]` |
| `stock_summary(client, as_on_date, stock_group, company)` | Yes — `get_stock_summary` | Returns `list[dict]` with item, qty, rate, value |

**Missing report functions (no request builder, no query function, no tool):**

- `cash_flow_statement` — Tally has this as a built-in TYPE=Data report
- `fund_flow_statement` — Tally built-in
- `ratio_analysis` — Tally built-in
- `ageing_analysis` (receivables/payables) — variation on bills reports with age buckets
- `gst_summary` / `gstr1` / `gstr3b` — GST reports (Tally has these natively)

### 2c. `backend/tally_bridge/queries/vouchers.py`

| Function | Exposed as Tool? | Notes |
|----------|-----------------|-------|
| `day_book(client, from_date, to_date, voucher_type, company)` | Yes — `get_day_book` | TYPE=Collection with optional voucher_type filter |
| `ledger_vouchers(client, ledger_name, from_date, to_date, company)` | Yes — `get_ledger_transactions` | Filters by `$PartyLedgerName` TDL formula |
| `sales_register(client, from_date, to_date, company)` | Yes — `get_sales_register` | Day book filtered to "Sales" voucher type |
| `purchase_register(client, from_date, to_date, company)` | Yes — `get_purchase_register` | Day book filtered to "Purchase" voucher type |

**Missing voucher functions:**

- `payment_register` — day_book with voucher_type="Payment" would work but is not exposed separately
- `receipt_register` — same; no dedicated tool
- `journal_register` — same; no dedicated tool
- `contra_register` — same
- `credit_note_register` / `debit_note_register` — no dedicated tools
- `stock_vouchers` — movement/inward/outward vouchers (stock journal, delivery notes)

---

## 3. Request Builders with No Downstream Usage

These exist in `backend/tally_bridge/request_builder.py` but have **no query function, no response parser, and no agent tool**:

| Request Builder | XML Request Built | Missing Layer |
|----------------|------------------|--------------
| `build_list_groups()` | `CustomGroupList` Collection, fetches Name + Parent | Query fn, parser, tool |
| `build_list_stock_items()` | `CustomStockItemList` Collection, fetches Name, Parent, BaseUnits, ClosingBalance, ClosingRate, ClosingValue | Query fn, parser, tool |

`build_list_stock_items` is particularly notable — it already requests all the fields needed for a complete stock master list (item name, group, unit of measure, closing qty, rate, value) but nothing consumes it.

---

## 4. Mock Handler Coverage

`backend/tally_bridge/mock_handler.py` maps XML request body substrings to fixture files.

| Report Name in XML | Fixture File | Coverage Type |
|-------------------|-------------|---------------
| `"List of Companies"` | `company_list.xml` | Static |
| `"CustomLedgerList"` | `ledger_list.xml` | Static |
| `"Trial Balance"` | `trial_balance.xml` | Static |
| `"Balance Sheet"` | `balance_sheet.xml` | Static |
| `"Bills Receivable"` | `bills_receivable.xml` | Static |
| `"Bills Payable"` | `bills_payable.xml` | Static |
| `"Stock Summary"` | `stock_summary.xml` | Static |
| `"DayBookVchs"` | `day_book.xml` | Voucher (Python date filter) |
| `"SalesVchs"` | `sales_register.xml` | Voucher (Python date filter) |
| `"PurchaseVchs"` | `purchase_register.xml` | Voucher (Python date filter) |
| `"LedgerVchs"` | `day_book.xml` | Voucher (reuses day_book) |
| `"Profit and Loss"` | Generated dynamically | Date-aware: computes cumulative from voucher data |

**Not covered in mock:**
- `CustomGroupList` (no fixture, no handler entry)
- `CustomStockItemList` (no fixture, no handler entry)
- Any future reports (cash flow, GST, ageing, etc.)

---

## 5. Gap Analysis by Category

### 5a. Masters

| Capability | Status | Notes |
|------------|--------|-------|
| List all companies | Available | `list_companies` tool |
| List all ledgers (full dump) | Partial — not exposed | `masters.list_ledgers()` exists, returns all 30+ ledgers. Not a direct tool — agent must use `search_ledger` with broad terms to approximate. |
| Search ledgers by name | Available | `search_ledger` tool |
| Get ledger details (balance, parent) | Available via search | `search_ledger` returns parent_group, opening/closing balance |
| List account groups hierarchy | Missing | `build_list_groups()` exists in request_builder. No query fn, no parser, no tool. Agent cannot enumerate group hierarchy. |
| List all stock items (master) | Missing | `build_list_stock_items()` exists in request_builder with correct fields. No query fn, no parser, no tool. Agent cannot list all stock items without going through stock_summary. |
| Stock item details (UOM, group) | Missing | Partially available via `get_stock_summary` (returns closing qty/rate/value but no group). The master query would add group and UOM. |
| Cost centres / cost categories | Missing | No request builder, no query, no tool. |
| Units of measure | Missing | Only available as a field in `build_list_stock_items` output; no standalone tool. |

### 5b. Financial Reports

| Report | Status | Notes |
|--------|--------|-------|
| Trial Balance | Available | Full debit/credit/closing balance per account |
| Profit & Loss | Available | Period-specific via subtraction approach |
| Balance Sheet | Available | Assets and liabilities as on date |
| Cash Flow Statement | Missing | Tally has this as a built-in TYPE=Data report named "Cash Flow" |
| Fund Flow Statement | Missing | Tally has "Fund Flow" built-in |
| Ratio Analysis | Missing | Tally has "Ratio Analysis" report; useful for liquidity/profitability ratios |
| Comparative Balance Sheet | Missing | Could be synthesised with two BS calls + analysis agent, but no dedicated tool |
| Budgets vs Actuals | Missing | Requires budget master + comparison logic |
| Cost Centre Summary | Missing | No tools for cost centres at all |

### 5c. Vouchers and Registers

| Register / Voucher Type | Status | Notes |
|------------------------|--------|-------|
| Day Book (all types) | Available | `get_day_book`, optional `voucher_type` filter |
| Sales Register | Available | `get_sales_register` (dedicated tool) |
| Purchase Register | Available | `get_purchase_register` (dedicated tool) |
| Payment Register | Partial | Agent can call `get_day_book` with `voucher_type="Payment"`. No dedicated tool or shortcut. |
| Receipt Register | Partial | Same — via `get_day_book` with `voucher_type="Receipt"` |
| Journal Register | Partial | Via `get_day_book` with `voucher_type="Journal"` |
| Contra Register | Partial | Via `get_day_book` with `voucher_type="Contra"` |
| Credit Note Register | Partial | Via `get_day_book` with `voucher_type="Credit Note"` |
| Debit Note Register | Partial | Via `get_day_book` with `voucher_type="Debit Note"` |
| Ledger-specific transactions | Available | `get_ledger_transactions` |
| Voucher line items (stock items in invoice) | Partial | `ledger_entries` field has ledger name + amount. Item names/quantities NOT in voucher response — `AllLedgerEntries` field only fetches ledger names, not inventory allocations. |

**Critical gap:** The voucher response schema only fetches `AllLedgerEntries` (ledger name + amount per line). It does NOT fetch `AllInventoryEntries` (stock item, quantity, rate). This means the agent cannot answer "which items were in invoice S001?" from the day book / sales register alone.

### 5d. Bills and Ageing

| Capability | Status | Notes |
|------------|--------|-------|
| Outstanding receivables (full list) | Available | `get_outstanding_receivables` — party, bill, date, amount, pending |
| Outstanding payables (full list) | Available | `get_outstanding_payables` |
| Due date per bill | Partial | `OutstandingBill` model has `due_date` field; response parser extracts `BILLDUE`. Available but not prominently surfaced in tool description. |
| Overdue days per bill | Partial | Parser extracts `BILLOVERDUE`; stored in raw parsed dict but stripped when converting to `OutstandingBill` model — lost before reaching the agent. |
| Ageing buckets (0-30, 31-60, 61-90, 90+) | Missing | Would require post-processing of the bills list using the `due_date` field. Could be done in the analysis agent but no dedicated tool or prompt guidance exists for it. |
| Party-wise outstanding summary | Missing | No group-by capability in the bills tool. Agent would need to aggregate using `compute_totals(group_by="party_name")` from the analysis tools. |

### 5e. Stock and Inventory

| Capability | Status | Notes |
|------------|--------|-------|
| Stock summary (closing qty + value per item) | Available | `get_stock_summary` — item name, qty, rate, value |
| Filter stock summary by group | Available | `stock_group` optional param |
| Stock category / group breakdown | Missing | `get_stock_summary` returns items with empty `parent_group` field (TYPE=Data reports don't include group hierarchy) |
| Individual stock item details | Missing | `build_list_stock_items()` exists but no query fn / parser / tool |
| Stock movement (inward/outward per item) | Missing | Would require fetching stock vouchers with inventory allocations |
| Stock valuation method (FIFO/Avg) | Missing | Master data query needed |
| Reorder level / min stock level | Missing | Master data |
| Item-wise sales analysis | Missing | Would require cross-referencing inventory allocations in sales vouchers — currently `AllLedgerEntries` is fetched, not `AllInventoryEntries` |
| Item-wise purchase analysis | Missing | Same — inventory allocations not fetched |
| Top selling items by quantity | Missing | No inventory allocation data in voucher responses |
| Stock turnover ratio | Missing | Needs both stock summary and purchases/sales data |

### 5f. GST Reports

| Capability | Status | Notes |
|------------|--------|-------|
| GSTR-1 summary | Missing | No request builder, no tool |
| GSTR-3B summary | Missing | No request builder, no tool |
| HSN summary | Missing | No tool |
| GST tax collected (CGST/SGST/IGST totals) | Partial | Agents can approximate by querying ledger balances for CGST/SGST/IGST Output ledgers via `search_ledger` + `get_ledger_transactions`. No dedicated tool. |
| Input tax credit summary | Partial | Same approximation via CGST/SGST/IGST Input ledgers |
| E-invoice / E-way bill status | Missing | Not in scope for current Tally bridge |

### 5g. Period Queries and Comparisons

| Capability | Status | Notes |
|------------|--------|-------|
| Single period (any date range) | Available | All tools accept from_date/to_date |
| Financial year | Available | Agent computes directly (Apr 1 – Mar 31) |
| Quarter (Q1–Q4 Indian FY) | Available | Agent computes dates directly from prompt guidance |
| Relative dates (this month, last quarter) | Available | `resolve_date_range` date tool |
| Period comparison (Q1 vs Q2) | Available | `compute_period_comparison` analysis tool |
| YoY comparison | Available | Two separate fetches + analysis tools |
| Month-wise trend | Available | Full range fetch + `compute_totals(group_by='month')` |
| Multi-company comparison | Missing | Tools accept `company` param but there's no tool to fetch the same report for multiple companies and merge. |

---

## 6. Stock-Specific Deep Dive

### What the agent CAN do with stock today

1. **Closing stock summary as on any date** — `get_stock_summary(as_on_date)` returns every stock item with closing quantity, rate, and value. Supports optional `stock_group` filter.
2. **Filter by stock group name** — `SVSTOCKGROUP` variable is sent in the request. Tally filters items to that group.
3. **Ranking by value** — Agent can call `get_stock_summary` then `sort_by_field(field="closing_value", descending=True, limit=10)` to get top 10 items by value.
4. **Total stock value** — `compute_totals(records=..., numeric_fields=["closing_value"])`.

### What is BLOCKED

| Desired Query | Why It Fails | Root Cause |
|--------------|-------------|-----------
| "What items did I sell in October?" | Sales register returns `AllLedgerEntries` only (ledger name + rupee amount). Inventory allocations (`AllInventoryEntries`) are not fetched. | `_voucher_native_methods()` in `request_builder.py` line 60 does not include `AllInventoryEntries` |
| "Top 5 selling products by quantity" | No quantity data in voucher responses | Same — no inventory allocation fields |
| "Slow-moving stock (sold < 5 units this FY)" | Cross-reference closing stock with sales quantities — impossible without inventory allocation data | Same |
| "Which stock group is worth most?" | `get_stock_summary` returns items with empty `parent_group` (TYPE=Data doesn't expose groups) | Tally's Stock Summary TYPE=Data report doesn't include parent group in its output structure. Need `build_list_stock_items()` (TYPE=Collection) which does include `Parent`. |
| "List all stock items with UOM" | `build_list_stock_items()` exists and would return this, but no query function or parser exists | Missing query layer and response parser |
| "Stock movement for HP Laptop 15s in Q3" | No stock voucher query exists | No request builder for stock journals / delivery notes |
| "What is my reorder level for monitors?" | Master attribute not queried | No master detail tool |

### Stock Gap: Request Builder vs Full Stack

```
build_list_stock_items()   ←── EXISTS (request_builder.py:156)
        │
        ▼
  query function           ←── MISSING (masters.py has no list_stock_items())
        │
        ▼
  response parser          ←── MISSING (response_parser.py has no parse_stock_items())
        │
        ▼
  agent tool               ←── MISSING (tools.py has no list_stock_items tool)
```

Completing this chain requires approximately 20–30 lines of code across three files and would immediately unlock "list all stock items with group and UOM" queries.

---

## 7. Agent Prompt vs Actual Tool Reality

The query agent prompt (`build_query_agent_prompt` in `prompts.py`) lists tool names dynamically from `TALLY_TOOLS`. This means the prompt is always in sync with the tools — no phantom tools are mentioned. However, several implicit assumptions in the prompt diverge from reality:

| Prompt Assumption | Reality |
|------------------|---------
| Rule 11: "fetch FULL date range in ONE call, then use compute_totals with group_by='month'" | Works for vouchers (day book, sales register). Does NOT work for `get_profit_and_loss` or `get_balance_sheet` — these are TYPE=Data aggregated reports, not raw records. Agent sometimes incorrectly tries to group-by-month on P&L rows. |
| Rule 2: "call search_ledger first to find exact ledger name" | Correct in principle. But `search_ledger` filters `list_ledgers()` results which only includes the 30-ledger fixture in mock mode — live Tally has 82 ledgers. Partial name matches can still fail if the ledger name contains special characters. |
| `get_day_book` with `voucher_type` filter | Prompt doesn't document the valid values. Agent sometimes passes "Payments" (plural) or "payment" (lowercase) — the request builder calls `.title()` which normalises case, but Tally may reject unknown types silently. |
| Stock data granularity | Prompt says "Returns item names, quantities, rates, and values" for `get_stock_summary`. This is accurate. But there is no hint that inventory allocations within sales/purchase vouchers are NOT available — agent may incorrectly assume voucher data contains item quantities. |

The analysis agent prompt (`build_analysis_agent_prompt`) is well-structured and does not mention any tools that don't exist. Rule 8 (GST handling) is excellent given the GST component ledgers in the fixture data.

---

## 8. Priority Recommendations

### HIGH Priority (blocks common business queries)

| # | Gap | Effort | Value |
|---|-----|--------|-------|
| H1 | **Add `list_stock_items` tool** — complete the chain from `build_list_stock_items()` through query fn + parser + tool schema. Unlocks "list all items with group/UOM" and fixes the empty `parent_group` problem in stock summary. | ~30 lines across 3 files | High — stock queries are blocked |
| H2 | **Fetch inventory allocations in vouchers** — add `AllInventoryEntries` to `_voucher_native_methods()` in `request_builder.py`. Parse item name, quantity, rate from `ALLINVENTORYENTRIES.LIST` elements in `parse_vouchers()`. | ~20 lines request builder + ~15 lines parser | Very high — blocks all item-level sales/purchase analysis |
| H3 | **Expose `list_ledgers` as a direct tool** — currently the agent must use `search_ledger` with heuristic terms to enumerate ledger accounts. A `list_all_ledgers` tool would let the agent discover available ledger names without guessing. Also critical for top-N-customers-by-ledger-balance queries. | ~5 lines in tools.py | High — needed for top-N ledger queries |
| H4 | **Ageing analysis from bills data** — the `overdue_days` field is parsed by `parse_bills()` but stripped when constructing `OutstandingBill` model. Add `overdue_days` to the model and surface it in the tool response. Then add prompt guidance for bucketing. | ~10 lines models.py + tools.py | High — "how old are my receivables?" is a standard query |

### MEDIUM Priority (improves coverage of existing categories)

| # | Gap | Effort | Value |
|---|-----|--------|-------|
| M1 | **Dedicated payment/receipt register tools** — wrap `get_day_book` calls with fixed `voucher_type` values. Reduces cognitive load on the agent (it won't have to guess the right filter value). | ~20 lines tools.py | Medium |
| M2 | **Cash Flow Statement** — Tally has a built-in TYPE=Data report. Add `build_cash_flow()` in request_builder, `cash_flow()` in reports.py, and `get_cash_flow` tool. | ~40 lines across 3 files + parser | Medium — common CFO query |
| M3 | **List account groups** — complete `build_list_groups()` chain. Lets the agent understand the chart of accounts hierarchy and explain group-level totals. | ~25 lines across 3 files | Medium |
| M4 | **Add `due_date` and `overdue_days` to tool description** — currently the `get_outstanding_receivables` tool description does not mention overdue days. Updating the description would prompt Claude to surface them. | 1 line tools.py | Low effort / medium value |
| M5 | **Fix P&L month-trend pattern** — add a note in the query agent prompt that `get_profit_and_loss` returns one row per account, not per voucher, and cannot be grouped by month. For monthly P&L trends, the agent must call `get_profit_and_loss` N times or use sales register as a proxy. | ~3 lines prompts.py | Medium — prevents wrong tool usage |

### LOW Priority (advanced / future features)

| # | Gap | Effort | Value |
|---|-----|--------|-------|
| L1 | **GST reports (GSTR-1, GSTR-3B, HSN summary)** — requires new request builders, parsers, and tools. Tally's GST reports use TYPE=Data with specific report IDs. | ~100 lines new code | High business value, high effort |
| L2 | **Ratio Analysis** — Tally built-in. Useful for liquidity/profitability ratios without manual calculation. | ~30 lines | Low — agent can compute ratios from TB/BS |
| L3 | **Fund Flow Statement** | ~30 lines | Low — niche use case |
| L4 | **Multi-company fetch tool** — a tool that accepts a list of companies and returns a merged dataset. | ~50 lines + orchestrator changes | Low for current single-company setup |
| L5 | **Cost centre queries** | ~80 lines new code | Low — not in seed data |
| L6 | **Budget vs Actuals** | ~80 lines + budget master support | Low — requires budget setup in Tally |
| L7 | **Stock movement / stock journal register** | ~50 lines | Medium once inventory allocations (H2) are done |

---

## 9. Summary Statistics

| Category | Available | Partial | Missing |
|----------|-----------|---------|---------
| Masters | 2 of 5 | 1 | 2 |
| Financial Reports | 3 of 7 | 0 | 4 |
| Voucher Registers | 4 of 10 | 5 | 1 |
| Bills / Ageing | 2 of 5 | 2 | 1 |
| Stock / Inventory | 1 of 8 | 0 | 7 |
| GST | 0 of 4 | 2 | 2 |
| Period Queries | 6 of 7 | 0 | 1 |
| **Total** | **18 of 46** | **10** | **18** |

**Overall coverage: ~39% fully available, ~22% partially available, ~39% missing.**

---

## 10. Files Most Relevant to Closing These Gaps

| File | Role |
|------|-------|
| `backend/agents/tools.py` | Add new tool schemas and handlers |
| `backend/tally_bridge/request_builder.py` | Add new XML request builders; add `AllInventoryEntries` to voucher fields |
| `backend/tally_bridge/queries/masters.py` | Add `list_stock_items()`, `list_groups()` query functions |
| `backend/tally_bridge/queries/reports.py` | Add `cash_flow()`, `ageing_analysis()` |
| `backend/tally_bridge/queries/vouchers.py` | Inventory allocation parsing |
| `backend/tally_bridge/response_parser.py` | Add `parse_stock_items()`, `parse_groups()`, extend `parse_vouchers()` for inventory allocations |
| `backend/tally_bridge/models.py` | Add `overdue_days` to `OutstandingBill`; add `StockItem` model |
| `backend/tally_bridge/mock_handler.py` | Add mock entries for new fixtures |
| `backend/agents/prompts.py` | Fix P&L monthly trend guidance; document voucher_type valid values |
| `tests/fixtures/generate_fixtures.py` | Add fixtures for stock items master, groups, inventory allocations in sales |

## Analysis Complete
