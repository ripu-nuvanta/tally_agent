# Code Review: Phase 10 -- Enriched Mock Tally Data

**Review Date:** 2026-03-13
**Reviewer:** Claude Opus 4.6 (code review agent)
**Base Commit:** `0ca06d1` (docs: add enriched mock tally plan, eval results, update CLAUDE.md)
**Head Commit:** `3ecacaa` (docs: update CLAUDE.md for enriched mock data phase, save e2e results)
**Commits Reviewed:** 7
**Files Changed:** 28 (+3956 / -558 lines)

---

## 1. Plan Alignment

**Plan:** `docs/plans/2026-03-12-enriched-mock-tally.md`

| Plan Task | Status | Notes |
|-----------|--------|-------|
| Fixture generator from seed data | DONE | `tests/fixtures/generate_fixtures.py` -- 823 lines, generates all 11 fixture files |
| Date-aware mock handler for P&L | DONE | `backend/tally_bridge/mock_handler.py` -- parses SVTODATE, computes cumulative |
| Mock eval scenario variants | DONE | 4 `*_mock.yaml` files for edge_case, financial_deep_dive, manual_test_regression, trends_and_breakdowns |
| Format parity tests | DONE | `tests/integration/test_mock_format_parity.py` -- 70 tests across 11 report types |
| Eval collector auto-selects mock scenarios | DONE | `collect.py` updated with `--tally-mode mock` and `load_scenario()` logic |
| Updated unit tests for new fixtures | DONE | `test_mock_handler.py`, `test_response_parser.py` updated |
| Updated integration tests | DONE | `test_api_endpoints.py`, `test_masters.py`, `test_reports.py`, `test_vouchers.py` updated |
| Updated mock golden data | DONE | `mock_golden.json` enriched to match new fixture data |

**Assessment:** Full alignment with the plan. All 5 chunks and their sub-tasks are implemented. No missing deliverables.

---

## 2. What Was Done Well

**Single source of truth architecture.** The `generate_fixtures.py` design is excellent. All fixture data derives from a single set of Python constants (LEDGERS, SALES_INVOICES, PURCHASE_INVOICES, PAYMENTS, RECEIPTS, STOCK_ITEMS). Balances, P&L, TB, and BS are all computed from the same voucher data, ensuring internal consistency. This eliminates the class of bugs where fixture files contradict each other.

**Date-aware P&L is the right fix.** The core problem (mock P&L returning identical data for all date ranges, causing subtraction-to-zero) is cleanly solved. The `_compute_cumulative_pnl(up_to_date)` function correctly filters vouchers by date, matching real Tally's cumulative-from-FY-start behavior.

**Comprehensive format parity tests.** The 70 parity tests in `test_mock_format_parity.py` verify that every mock response parses correctly through the production parsers. This is a strong regression safety net -- if someone edits the fixture generator and breaks XML format, the parity tests will catch it.

**Mock eval scenarios are well-designed.** The `*_mock.yaml` variants replace live-only entities (HCODE -> Apex Technologies, Q1/Q2 -> Q3/Q4) while preserving the same testing intent. The `checks` lists are specific and actionable.

**Clean separation of concerns.** The mock handler remains thin (99 lines), delegating computation to the fixture generator. The eval collector's `load_scenario()` cleanly prefers `*_mock.yaml` when available.

**Test results are solid.** 641 backend tests pass, 19/19 e2e_live mock tests pass, 92/92 mock handler + parity tests pass.

---

## 3. Issues

### Important (should fix)

**I-1: `_generate_cumulative_pnl` re-executes the module on every call.**

File: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/tally_bridge/mock_handler.py`, lines 67-76.

The `importlib.util` pattern loads and executes `generate_fixtures.py` from scratch on every P&L request. This re-parses all constants and re-defines all functions. While the module is small enough that performance impact is negligible in test scenarios, this is architecturally wasteful and could become problematic if the fixture generator grows.

The `@lru_cache` used for `_load_fixture` (line 45) shows the pattern is understood but not applied here. The reason for using `importlib` instead of a direct import is likely to avoid circular imports or test-path pollution, but the module could be cached after first load.

Recommendation: Cache the loaded module in a module-level variable, or use `lru_cache` on `_generate_cumulative_pnl` (with the date parameter as the cache key).

```python
_fixture_generator_module = None

def _get_fixture_generator():
    global _fixture_generator_module
    if _fixture_generator_module is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "generate_fixtures",
            FIXTURES_DIR / "generate_fixtures.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _fixture_generator_module = mod
    return _fixture_generator_module
```

**I-2: `%-d` date format is not cross-platform.**

File: `/Users/ripu/work/nuvanta_repos/tally_agent/tests/fixtures/generate_fixtures.py`, lines 771 and 781.

`d.strftime("%-d-%b-%y")` uses the `%-d` modifier (no zero-padding) which works on macOS and Linux but fails on Windows (`%#d` is the Windows equivalent). Since the project runs on macOS/Linux, this is not a blocker, but if CI ever runs on Windows or a contributor uses Windows, the fixture generator will break silently.

Recommendation: Use `str(d.day)` instead: `f"{d.day}-{d.strftime('%b-%y')}"`.

**I-3: Sales invoice totals are redundantly declared, not computed.**

File: `/Users/ripu/work/nuvanta_repos/tally_agent/tests/fixtures/generate_fixtures.py`, lines 94-143.

Each `SALES_INVOICES` entry declares a `total` field (e.g., `94000`) alongside the line items. The `_build_sales_voucher` function uses `total` for the party debit entry but sums `qty * rate` for individual sales ledger entries. If someone adds a line item but forgets to update the total, the voucher will be unbalanced (debit != credit).

I manually verified all 16 sales and 8 purchase totals and they are currently correct. However, the design invites future bugs.

Recommendation: Compute the total from items instead of relying on the declared value:
```python
computed_total = sum(qty * rate for _, qty, rate in items)
# Use computed_total for the party entry
```

This could be done in `_build_sales_voucher` and `_build_purchase_voucher`, or the `total` field could be removed from the data tuples entirely.

### Suggestions (nice to have)

**S-1: Consider using `@dataclass` or `NamedTuple` for voucher data.**

The positional tuples like `(vnum, date_str, party, items, total, narration)` are unpacked in 10+ places. A named structure would improve readability and catch field-order bugs:

```python
from typing import NamedTuple

class SalesInvoice(NamedTuple):
    voucher_number: str
    date: str
    party: str
    items: list[tuple[str, int, float]]
    total: float
    narration: str
```

**S-2: Trial Balance is not date-aware in the mock handler.**

The plan mentions making Trial Balance date-aware, but it remains a static fixture (line 24 of `mock_handler.py`). The P&L was made date-aware because it was the root cause of the zero-subtraction bug. TB is less critical because the agent typically requests a single TB for the full year, but if an agent ever requests period-specific TB, the mock will return the same data regardless.

Not urgent -- this is consistent with the plan's priority of fixing P&L first.

**S-3: No test for the fixture generator itself.**

The fixture generator is a critical single source of truth but has no dedicated test file. The format parity tests indirectly validate the output, but there is no test that verifies:
- All 16 sales invoice totals match `sum(qty * rate for items)`
- All receivable/payable expectations match computed values
- Ledger balance computation is correct (debits = credits)

A `tests/unit/test_generate_fixtures.py` with arithmetic consistency checks would catch data entry errors.

**S-4: `mock_handler.py` uses string-contains matching for report dispatch.**

The `if report_name in xml_body` pattern (lines 82-96) is simple but could produce false positives if a report name appears in the narration or a different context. For example, a request containing "Stock Summary Report" in a narration field would incorrectly match. In practice this is unlikely with the current fixture data, but a regex match like `re.search(r'<REPORTNAME>Stock Summary</REPORTNAME>', xml_body)` would be more robust.

---

## 4. Architecture Assessment

The implementation follows the project's three-layer architecture well:
- Fixture generator is a standalone script (no backend imports)
- Mock handler delegates to the fixture generator for date-aware reports
- Format parity tests bridge the gap by running mock responses through production parsers
- Eval scenarios cleanly separate mock variants from live ones

The `importlib` approach for the mock handler -> fixture generator dependency is unorthodox but justified: it avoids adding `tests/` to the production import path while keeping the fixture generator as the single source of truth.

---

## 5. Test Coverage Assessment

| Test Area | Count | Coverage Quality |
|-----------|-------|-----------------|
| Mock handler unit tests | 22 | Good -- covers all report types, date-aware P&L, voucher counts |
| Format parity (integration) | 70 | Excellent -- validates every field of every parsed report type |
| Updated unit tests | ~50 (response_parser adjustments) | Good -- expectations match new fixture data |
| Updated integration tests | ~6 adjustments | Adequate -- company name, count, and amount expectations updated |

**Missing coverage:**
- No unit tests for `generate_fixtures.py` arithmetic (see S-3)
- No test for cache invalidation of `_load_fixture` after fixture regeneration
- No negative test for `_generate_cumulative_pnl` with invalid date format

---

## 6. Summary

| Category | Count |
|----------|-------|
| Critical | 0 |
| Important | 3 (I-1, I-2, I-3) |
| Suggestions | 4 (S-1, S-2, S-3, S-4) |

The implementation is well-executed, closely follows the plan, and solves the core problem (date-blind P&L causing zero-value subtraction in mock mode). The fixture generator design is architecturally sound. All tests pass. The three Important issues are about defensive coding practices rather than correctness bugs -- the current code works correctly but has patterns that invite future errors. None of these block merging.

**Verdict:** Ready to merge. Address I-1 and I-3 in a follow-up if convenient.
