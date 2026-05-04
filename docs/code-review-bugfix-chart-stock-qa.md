# Code Review: Chart Numeric Filtering, Stock Fixture Closing Balances, QueryAgent Token Limit

**Commit:** bd94f6a
**Reviewer:** Claude Opus 4.6 (Senior Code Reviewer)
**Date:** 2026-03-13
**Plan:** `docs/plans/2026-03-13-stock-chart-queryagent-bugfixes.md`
**Verdict:** APPROVED with one Important issue (negative stock) and minor suggestions

---

## Summary

The commit fixes three bugs in a single, well-scoped change:
1. ChartAgent now detects non-numeric columns and excludes them from chart y_keys
2. Stock fixture generator computes closing quantities instead of echoing opening values
3. QueryAgent max_tokens reduced from 4096 to 1024 to prevent computation waste

All 704 backend tests pass. The implementation faithfully follows the plan with no meaningful deviations.

---

## Plan Alignment

The implementation matches the plan (`docs/plans/2026-03-13-stock-chart-queryagent-bugfixes.md`) with near-exact fidelity across all four tasks. The plan called for separate commits per task; the implementation squashed into one. This is a reasonable deviation for a tightly-coupled bugfix batch.

One minor deviation: the plan's test `test_build_config_excludes_non_numeric_columns` used longer header names ("Closing Stock (Units)") while the implementation used shorter names ("Closing Stock"). This has no functional impact and the tests are equivalent in what they verify.

---

## Bug 1: ChartAgent Numeric Column Filtering

**Files:** `backend/agents/chart_agent.py`, `tests/unit/test_chart_agent.py`

### What Was Done Well

- `_identify_numeric_columns()` correctly handles currency-formatted strings (stripping commas, rupee symbol, percent sign) before numeric detection.
- The >50% threshold is a sensible heuristic -- columns with occasional text (like "N/A") in otherwise numeric data will still be charted.
- Backward compatibility is preserved: `_build_config()` accepts `rows=None` by default, so existing callers (including 4 tests in `TestBuildConfigSecondaryAxis`) that pass only `(chart_type, headers)` continue to work without modification.
- The early return (`if not config["y_keys"]: return None`) prevents empty charts from reaching the frontend.
- Four tests cover the key scenarios: pure numeric filtering, config integration, all-text fallback (returns None), and mixed real-world data.

### Issues

None critical.

### Suggestions (nice to have)

**S1: Edge case -- single-row data with all numeric columns.**
`_identify_numeric_columns()` uses `headers[1:]` as fallback when `not rows`, but `_select_chart_type` already returns `table_only` for <2 rows. No bug here, but the double fallback could be documented with a comment for clarity.

**S2: "Rank" column in test data.**
In `test_build_config_uses_only_numeric_y_keys`, the first header is "Rank" (x-axis), and the second is "Item" (text). Since `_identify_numeric_columns` starts at index 1, "Rank" is always the x-axis label and never tested for numericity. The plan noted this ambiguity but left it unresolved. The current behavior is correct -- `Rank` is the label column and should be x-axis.

**S3: `_format_xy_data` still calls `_to_numeric` on text columns.**
When text columns are included in the chart data points, `_to_numeric` returns 0.0 for strings like "Watch" or "OK". The new `_identify_numeric_columns` filter in `_build_config` prevents these from appearing in `y_keys`, but `_format_xy_data` still converts all non-label columns. This is harmless (the frontend ignores keys not in `y_keys`) but could be tightened to skip non-numeric columns in data formatting too, reducing payload size.

---

## Bug 2: Stock Fixture Closing Balances

**Files:** `tests/fixtures/generate_fixtures.py`, `tests/fixtures/stock_items_list.xml`

### What Was Done Well

- The closing balance logic (`opening - sold + purchased`) exactly matches `generate_stock_summary()` at line 462, maintaining internal consistency between the two fixture generators.
- The docstring clearly explains the rationale and references real Tally behavior (NATIVEMETHOD:ClosingBalance).
- The regenerated XML fixture reflects the computed values correctly.

### Issues

**IMPORTANT: Lenovo Ideapad Slim 3 has negative closing stock (-1 Nos, -36000.00 value).**

The seed data has:
- Opening: 12 units
- Sold: S005 (4) + S010 (3) + S016 (6) = 13 units
- Purchased: 0 units (not in any PURCHASE_INVOICES)
- Closing: 12 - 13 + 0 = **-1 units**

While Tally technically allows negative stock (it shows as a warning), this is an unintentional data inconsistency in the test seed data. It will cause confusing results in eval scenarios involving stock queries (e.g., "which items have low stock?" returning -1 units). Similarly, Dell Desktop Optiplex has closing=0, which is valid but worth noting.

**Recommendation:** Add a purchase invoice for Lenovo Ideapad (e.g., 5 units in P002 or a new P009) to bring closing stock positive. This is a separate fix, not a blocker for this commit.

**S4: No dedicated test for `generate_stock_items_list()` output.**
The fixture is verified implicitly via `test_mock_format_parity.py`, but there is no unit test that asserts specific closing quantities for known items. A targeted test would catch data regressions like the negative stock issue above.

---

## Bug 3: QueryAgent Token Limit + Prompt Strengthening

**Files:** `backend/agents/query_agent.py`, `backend/agents/prompts.py`, `tests/unit/test_query_agent.py`

### What Was Done Well

- The max_tokens reduction from 4096 to 1024 is well-motivated: QueryAgent is data-fetch only, so its text output should be a brief summary sentence, not a full analysis.
- The strengthened prompt is specific and actionable: it gives an example response format ("Fetched 15 stock items...") and explicitly lists prohibited behaviors (no computing, no tables, no analysis).
- The `table_only` guidance added to the AnalysisAgent prompt provides a soft defense-in-depth alongside the hard ChartAgent filter.
- The test `test_max_tokens_is_1024` correctly intercepts the API call and asserts the parameter value.

### Issues

None critical.

### Suggestions (nice to have)

**S5: 1024 tokens may be tight for complex multi-tool fetches.**
If QueryAgent fetches 5+ different data sources (e.g., stock items, sales register, purchase register, trial balance, ledger details), its summary sentence could approach 1024 tokens -- especially if Claude decides to list each data source. In practice, the data goes into tool results (not counted against max_tokens), so the 1024 limit only constrains the final text response. This should be fine, but worth monitoring in e2e_live runs.

**S6: Test uses `call_args.kwargs.get("max_tokens")` only.**
The test asserts `call_kwargs.kwargs.get("max_tokens") == 1024`. The plan's version also checked `call_kwargs[1].get("max_tokens")` as a fallback for positional args. The implementation dropped this fallback. Since the actual code uses keyword args (`max_tokens=1024`), this is fine -- but the plan was more defensive.

---

## Test Coverage Assessment

| Area | Tests Added | Coverage |
|------|-------------|----------|
| `_identify_numeric_columns` | 1 | Good: text vs numeric, mixed data |
| `_build_config` with rows | 1 | Good: verifies y_keys filtering |
| ChartAgent.execute with no numeric cols | 1 | Good: returns None |
| ChartAgent.execute with mixed cols | 1 | Good: real-world scenario |
| QueryAgent max_tokens | 1 | Good: intercepts API call |
| **Total new tests** | **5** | |
| **Total backend tests** | **704** | Up from 699 |

Missing test coverage (non-blocking):
- `_identify_numeric_columns` with currency-formatted string values (e.g., rows containing "12,34,567" strings)
- `_identify_numeric_columns` with empty rows or jagged rows (col_idx >= len(row))
- `generate_stock_items_list()` closing balance correctness for specific items

---

## Architecture and Design

- The `_identify_numeric_columns` function follows the existing pattern of private helper functions in `chart_agent.py`. Good separation of concerns.
- The function reuses the same currency-cleaning logic as `_to_numeric`. Could be DRY-ed into a shared helper, but the duplication is minimal and localized.
- The `rows=None` default on `_build_config` maintains backward compatibility without a breaking API change. Clean approach.

---

## Issue Summary

| # | Severity | Description | File |
|---|----------|-------------|------|
| I1 | **Important** | Lenovo Ideapad Slim 3 has negative closing stock (-1 units) due to seed data imbalance | `tests/fixtures/generate_fixtures.py` |
| S1 | Suggestion | Document the double-fallback in `_identify_numeric_columns` for empty rows | `backend/agents/chart_agent.py` |
| S3 | Suggestion | `_format_xy_data` still converts text columns to 0.0 via `_to_numeric` | `backend/agents/chart_agent.py` |
| S4 | Suggestion | Add unit test for `generate_stock_items_list()` closing quantities | `tests/fixtures/generate_fixtures.py` |
| S5 | Suggestion | Monitor 1024 token limit in complex multi-tool fetch scenarios | `backend/agents/query_agent.py` |

---

## Files Reviewed

- `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/chart_agent.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/prompts.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/query_agent.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/tests/fixtures/generate_fixtures.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/tests/fixtures/stock_items_list.xml`
- `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_chart_agent.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_query_agent.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/docs/plans/2026-03-13-stock-chart-queryagent-bugfixes.md`
