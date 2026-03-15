# LESSONS.md — Tally API Learnings

Hard-won lessons from building the TallyPrime AI Agent. These are NOT in Tally's official docs.

---

## 1. P&L TYPE=Data is unreliable for partial periods

**Discovery date:** 2026-03-15
**Diagnostic script:** `test_scripts/test_pnl_period.py` (15 tests against live Tally)
**Logs:** `test_scripts/logs/pnl_period_debug.log`

### The problem

Tally's XML API `TYPE=Data` for Profit & Loss returns **non-monotonic, unreliable values** when you query partial date ranges (e.g., Apr 1 → Jul 31).

Tested cumulative P&L for each month-end across a full FY. Expected monotonically increasing values for Sales. Got:

| Month-end | Expected (cumulative) | Actual from API |
|-----------|----------------------|-----------------|
| Apr 30 | 0 | ₹49,97,900 (full-year total!) |
| May 31 | 0 | 0 |
| Jun 30 | 0 | ₹49,97,900 |
| Jul 31 | ₹2,95,000 | ₹2,95,000 |
| Aug 31 | ₹5,95,000 | ₹5,95,000 |
| ... | ... | ... |
| Mar 31 | ₹49,97,900 | ₹49,97,900 ✓ |

Values jump between the full-year total and 0 for months with no transactions, instead of returning 0 consistently. This makes any subtraction-based approach (cumulative[month] − cumulative[month−1]) produce garbage.

### What works

- **Full-FY P&L** (Apr 1 → Mar 31): Always returns correct cumulative total. ✓
- **Voucher registers** (`get_sales_register`, `get_purchase_register`): Return transaction-level data with dates. Sum by month for accurate breakdowns. ✓
- **Day book** (`get_day_book`): Also transaction-level, works for expense trends. ✓

### What doesn't work

- **Partial-period P&L subtraction**: Garbage in → garbage out. The inputs are unreliable.
- **TYPE=Collection for P&L ledgers**: Revenue/expense ledgers are nominal accounts — ClosingBalance is always 0 by design (auto-closed to "Profit & Loss A/c").
- **Group objects via Collection**: CHILDOF on Group objects with Revenue/Expense filters returned empty results.

### Our fix

`profit_and_loss_period()` raises `TallyResponseError` for non-full-FY date ranges, with a message directing the agent to use voucher registers instead. Full-FY queries pass through unchanged.

---

## 2. SVFROMDATE is ignored for P&L reports

P&L reports always return cumulative data from FY start regardless of SVFROMDATE. Only SVTODATE is respected. This is why the "query each month separately" approach doesn't isolate monthly data — each call returns cumulative-to-date, not month-specific.

**Workaround:** Don't use P&L for period breakdowns. Use voucher registers.

---

## 3. `$$InDateRange` crashes Tally

The TDL function `$$InDateRange` is documented in some Tally resources but crashes TallyPrime 7.0 when used in Collection filters. Use `SVFROMDATE`/`SVTODATE` envelope parameters + Python-side filtering instead.

---

## 4. TYPE=Collection vs TYPE=Data

| Aspect | TYPE=Data | TYPE=Collection |
|--------|-----------|-----------------|
| Use case | Display reports (TB, P&L, BS) | Object queries (ledgers, vouchers) |
| XML structure | Sibling pairs (DSPACCNAME → DSPACCINFO) | Named fields (Name, Parent, ClosingBalance) |
| P&L reliability | Full-FY only | Always 0 for P&L ledgers (nominal accounts) |
| Voucher data | Summaries only | Full transaction detail with NATIVEMETHOD |

**Rule of thumb:** Use TYPE=Data only for aggregate report snapshots. Use TYPE=Collection for anything transactional.

---

## 5. XML field conventions

- Never use `*` in NATIVEMETHOD FETCH — crashes Tally. List specific fields.
- Sanitize `&#4;` control chars from XML responses before parsing.
- Dates always DD-MM-YYYY format.
- Indian FY: April 1 → March 31. Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.

---

## 6. P&L parser is correct (BSMAINAMT/PLSUBAMT)

After extensive testing, the `parse_profit_and_loss()` parser in `response_parser.py` was confirmed correct. It uses `BSMAINAMT` with `PLSUBAMT` fallback — this matches Tally's actual XML structure. The earlier hypothesis about sign alternation bugs was disproved.

---

## 7. Voucher-based monthly P&L (ground truth)

For the test company (NUVANTA AI TECHNOLOGIES PRIVATE LIMITED, FY 2025-26):

```
Jul: ₹2,95,000   Aug: ₹3,00,000   Sep: ₹6,00,000   Oct: ₹5,75,000
Nov: ₹5,00,000   Dec: ₹8,82,500   Jan: ₹6,11,850   Feb: ₹12,33,550
Full year total: ₹49,97,900
```

These values from `get_sales_register` match Tally desktop exactly.
