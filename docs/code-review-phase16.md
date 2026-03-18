# Code Review: Phase 16 -- Chart Stabilization

**Date**: 2026-03-17
**Branch**: `feature/chart-stabilization` (13 commits, d1c27dd..6bb819b)
**Reviewer**: Claude Opus 4.6 (Code Review Agent)
**Spec**: `docs/plans/2026-03-17-chart-stabilization-design.md`
**Plan**: `docs/plans/2026-03-17-chart-stabilization-impl-plan.md`

---

## Summary

Phase 16 replaces STRUCTURED_RESULT as the chart data source with a markdown table parser, adds scale mismatch detection (Rule A), percentage column detection (Rule B), enhanced total row exclusion (Rule C), smarter zero trimming (Rule D), a Haiku chart advisor for semantic column selection, and a CHARTS_ENABLED kill switch. The implementation is well-structured, follows the spec closely, and has strong test coverage with real eval transcript fixtures.

---

## What Was Done Well

1. **Real transcript fixtures**: Using actual AnalysisAgent responses from eval run `run_20260316_160527` as test fixtures is excellent. This ensures the parser and chart rules work against real-world data, not synthetic examples.

2. **Shared `_parse_raw_tables()` factoring**: The markdown parser has a clean separation between the internal `_parse_raw_tables()` (shared logic) and the two public APIs (`parse_markdown_table_for_chart` for best-table selection, `parse_all_markdown_tables` for advisor). This avoids code duplication.

3. **Chart advisor with clean fallback**: The Haiku advisor -> filter -> ChartAgent pipeline has a well-designed fallback chain: advisor success -> use advisor's selection; advisor returns None (failure) -> fall back to rule-based `parse_markdown_table_for_chart`; advisor returns `table_only` -> respect as "no chart" decision. This is a clear three-way branch.

4. **Prompt archival**: Moving STRUCTURED_RESULT rules to `DEPRECATED_ANALYSIS_RULES` preserves context without cluttering the active prompt.

5. **`_filter_table_by_advice()` is well-tested**: The orchestrator test file has 7 tests for this new function covering edge cases (missing x_column, duplicate columns, shorter rows, unknown columns).

---

## Spec Compliance

### Implemented (all core sections)

| Spec Section | Status | Notes |
|--------------|--------|-------|
| S1: CHARTS_ENABLED config | DONE | Added to `config.py` line 17, checked in orchestrator line 177 |
| S2: Markdown table parser | DONE | `parse_markdown_table_for_chart()` and `parse_all_markdown_tables()` in `utils.py` |
| S2: X-axis ordinal skip | DONE | `_is_ordinal_header()` + `_is_ordinal_column()` with sequential int detection |
| S2: Enhanced `to_numeric()` | DONE | Emoji, arrows, unicode minus, `pp` suffix, `(base)` sentinels |
| S3: Rule A (scale mismatch) | DONE | `_detect_scale_mismatches()` with `_COUNT_COLUMN_PATTERNS` |
| S3: Rule B (% value detection) | DONE | `_is_secondary_axis_column()` with keyword set: margin, rate, ratio, growth |
| S3: Rule C (total exclusion) | DONE | Enhanced in `_format_xy_data()` and `_format_pie_data()` |
| S3: Rule D (zero trimming) | DONE | `_trim_trailing_zeros()` with >= 3 non-zero span check |
| S4: Prompt archival | DONE | `DEPRECATED_ANALYSIS_RULES` constant in `prompts.py` |
| S4: Table ordering guidance | DONE | Rule 14 in `build_analysis_agent_prompt()` (code_execution path only) |
| S5: ChartAgent signature | DONE | `execute(table_data, query_type, chart_suggestion, chart_title)` |
| S5: Orchestrator integration | DONE | Parses markdown tables, calls advisor, filters, calls ChartAgent |
| S6: Unit tests | DONE | `test_chart_utils.py` (30 tests), `test_chart_agent.py` (50+ tests), `test_chart_advisor.py` (10 tests) |
| S6: E2E tests | DONE | `test_chart_pipeline.py` (9 tests: 7 rule-based + 2 advisor pipeline) |
| S6: Playwright visual tests | NOT DONE | Spec calls for rendering chart specs in frontend -- not implemented |

### Deviations from Spec

1. **Chart advisor (not in original spec)**: The Haiku chart advisor (`chart_advisor.py`) is an addition beyond the spec. The spec described a purely rule-based approach. This is a **beneficial deviation** -- the advisor adds semantic understanding for multi-table scenarios and column selection, with a clean fallback to the rule-based approach when the advisor fails.

2. **`parse_all_markdown_tables()` (not in spec)**: Added to support the advisor's need to see all tables. Another beneficial addition that follows naturally from the advisor design.

3. **Playwright visual tests not implemented**: The spec (Section 6) calls for Playwright visual tests to render chart specs and screenshot them. These are not present. This is a **gap** but is low-risk since the E2E tests validate the chart spec correctness, and visual rendering has separate Playwright tests from prior phases.

4. **Table ordering rule only in code_execution path**: The spec says to add table ordering guidance to AnalysisAgent prompts, but the implementation only adds Rule 14 when `code_execution_enabled=True`. The non-code-execution path has `structured_rule_block = ""`. This is **intentional** -- without code execution the old analysis tools don't produce multiple tables -- but worth noting.

---

## Issues

### Critical (must fix)

None found.

### Important (should fix)

**I1. No tests for `CHARTS_ENABLED=False` path**

The spec (Section 6) explicitly calls for:
- `CHARTS_ENABLED=True` -> chart in response
- `CHARTS_ENABLED=False` -> no chart, text still stripped
- Chart suggestion stripped from message text in both modes

There are zero tests exercising the `CHARTS_ENABLED=False` path. The config field exists and the orchestrator checks `settings.CHARTS_ENABLED` at line 177, but no test patches `settings.CHARTS_ENABLED = False` to verify that charts are suppressed. This is a **spec requirement gap**.

**Recommendation**: Add 2 orchestrator integration tests:
1. `test_charts_disabled_suppresses_chart` -- patch `settings.CHARTS_ENABLED = False`, verify `chart` is `None` even when `requires_chart=True` and analysis returns a markdown table.
2. `test_charts_disabled_still_strips_metadata` -- verify that "Chart suggestion:" and "Chart title:" lines are still removed from the message text when charts are disabled. (Note: this stripping happens in `analysis_agent.py`, not orchestrator, so it should already work -- but a test confirms the contract.)

**I2. Chart metadata stripping not tested end-to-end with new pipeline**

The spec states that chart title and chart suggestion are "always stripped from user-facing message text, regardless of config." The existing E2E test `test_chart_metadata_stripped_from_response` in `test_chat_pipeline.py` tests stripping but does not go through the new advisor pipeline (it uses mock responses without markdown tables). The new chart pipeline tests in `test_chart_pipeline.py` do not verify that the final user-facing message has metadata stripped.

**Recommendation**: Add an assertion in one of the E2E chart pipeline tests that the chart metadata lines are not present in the message after full pipeline processing.

**I3. `_is_ordinal_column` false positive risk with zero values**

In `_is_ordinal_column()` (line 167-168 of `utils.py`):
```python
if not all(n == int(n) for n in nums if n != 0.0):
    return False
```

The `if n != 0.0` filter means zero values (which `to_numeric` returns for non-numeric text) are silently excluded from the integer check. If a column has some text values that parse to 0.0, the remaining numeric values might form a sequential pattern, causing a false positive ordinal detection. Consider: a column with values `["1", "text", "3"]` -> nums = `[1.0, 0.0, 3.0]` -> after filtering zeros: `[1.0, 3.0]` -> not sequential -> safe. But `["1", "text", "2"]` -> `[1.0, 0.0, 2.0]` -> after filtering: `[1.0, 2.0]` -> ints `[1, 2]` -> matches `range(1, 3)` -> falsely detected as ordinal.

This is an edge case and unlikely in practice (the header check would normally catch it first), but worth noting.

**Recommendation**: Consider requiring that ALL values in the column are integers (no zeros from failed parsing) before checking for sequential pattern, or require a minimum count of valid integers (e.g., all values must parse as integers).

### Suggestions (nice to have)

**S1. Module-level `anthropic_client` in `chart_advisor.py` creates import-time API key requirement**

Line 20 of `chart_advisor.py`:
```python
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
```

This follows the existing pattern from `orchestrator.py` and `query_agent.py`, so it is consistent. However, it means importing the module requires a valid-looking API key at import time. Tests work around this by patching the module-level variable. This is a pre-existing pattern, not a new issue.

**S2. `_format_tables_for_prompt` truncates to 10 rows silently**

The advisor prompt formatter (line 60) truncates tables to 10 rows for the prompt. This is a reasonable optimization, but for tables with many similar-value rows at the top (e.g., all "Flat" expenses), the truncation might hide the more interesting rows. Consider adding a note to the advisor prompt that tables may be truncated.

**S3. `to_numeric` returns 0.0 for parenthetical values**

Line 137-138 of `utils.py`:
```python
if cleaned.startswith("(") and cleaned.endswith(")"):
    return 0.0
```

In accounting, parenthetical values often indicate negative amounts (e.g., `(500)` means -500). The current implementation discards these as 0.0. This is fine for the chart use case (parenthetical text like "(base)" should be 0.0), but could cause data loss for values like "(₹5,00,000)". The emoji/currency stripping runs first, so "₹5,00,000" inside parens would become "500000" with parens -> 0.0. A more robust approach would check if the inner content is numeric after stripping.

**S4. Fixture file is a `.py` module, not a directory**

The spec (Section 6, "Files to Modify") calls for `tests/fixtures/chart_transcript_fixtures/` as a directory. The implementation uses `tests/fixtures/chart_transcript_fixtures.py` as a single Python module. This is a **reasonable deviation** -- a single file is simpler and all fixtures are modest in size. The module approach also avoids `__init__.py` boilerplate.

**S5. Consider logging advisor latency**

The chart advisor makes a real API call to Haiku. Consider adding timing logs around the `get_chart_advice()` call in the orchestrator to track its impact on response time. This would help diagnose latency issues in production.

---

## Test Coverage Assessment

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_chart_utils.py` | ~30 | `to_numeric()` (21 cases), `parse_markdown_table_for_chart()` (13 cases), `parse_all_markdown_tables()` (7 cases) |
| `test_chart_agent.py` | ~50+ | Chart type selection, execute(), excluded columns, secondary axis, scale mismatch (Rule A), % detection (Rule B), total exclusion (Rule C), zero trimming (Rule D) |
| `test_chart_advisor.py` | 10 | API response parsing, code fence stripping, error handling, field validation, normalization |
| `test_orchestrator.py` | 7 new | `_filter_table_by_advice()` edge cases |
| `test_chart_pipeline.py` | 9 | E2E with real transcript fixtures (5 turns + 2 overspending + 2 advisor pipeline) |

### Eval Bug Coverage

| Eval Turn | Bug | Tested? |
|-----------|-----|---------|
| Turn 2 | Rank as x-axis | Yes (`test_turn2_top_customers`, `test_rank_column_skipped`) |
| Turn 2 | Invoices invisible (scale) | Yes (`test_count_column_excluded_when_scale_mismatch`) |
| Turn 3 | Change % zeroed (emoji) | Yes (`test_emoji_negative_percent`, `test_turn3_mom_growth`) |
| Turn 3 | Vouchers invisible (scale) | Yes (`test_vouchers_excluded_when_scale_mismatch`) |
| Turn 4 | Operating Margin not on secondary | Yes (`test_operating_margin_detected_as_secondary`) |
| Turn 4 | Total Revenue in chart | Yes (`test_total_revenue_skipped`, `test_turn4_q3_vs_q4`) |
| Turn 5 | Pie chart with # column | Yes (`test_turn5_expense_pie`) |
| Turn 7 | Zero months trimmed | Yes (`test_preserves_zeros_when_few_nonzero_points`, `test_turn7_avg_monthly`) |

All eval-identified bugs have test coverage.

### Missing Test Coverage

1. **`CHARTS_ENABLED=False` orchestrator path** (Important -- see I1)
2. **Orchestrator advisor fallback path** -- when advisor returns `None`, the fallback to `parse_markdown_table_for_chart` is not directly tested in an integration test (it is implied by the E2E rule-based tests, but no test explicitly exercises the `if chart is None and advice is None:` branch in the orchestrator with a mocked advisor returning None)
3. **Playwright visual tests** (spec requirement, not implemented)

---

## Architecture Assessment

The architecture change is sound:

1. **Data flow is cleaner**: `AnalysisAgent text -> markdown table parser -> ChartAgent` is more robust than `code_execution stdout -> STRUCTURED_RESULT JSON -> ChartAgent`. The markdown table is the same data the user sees, eliminating data divergence (Bug #1 from the spec).

2. **Advisor adds semantic layer**: The Haiku advisor bridges the gap between rule-based parsing (which can pick the wrong table or wrong columns in multi-table responses) and full LLM chart generation (which would be expensive and non-deterministic). The advisor is cheap (256 max_tokens, classifier model) and has a clean fallback.

3. **Separation of concerns is good**: The advisor selects columns, `_filter_table_by_advice` transforms the data, and ChartAgent applies rules and formatting. Each component is independently testable.

4. **Backward compatibility preserved**: STRUCTURED_RESULT extraction code remains in `utils.py` (used by DataTable rendering), AnalysisAgent still produces `data` field for DataTable, and the frontend is unchanged.

---

## Verdict

**Approve with minor issues.** The implementation is well-structured, follows the spec closely, and has strong test coverage against real eval transcript data. The Haiku advisor is a valuable addition beyond the original spec. The two important issues (I1: missing CHARTS_ENABLED=False tests, I2: metadata stripping not tested in new pipeline) should be addressed before merge to ensure the kill switch works correctly.

**Estimated test delta**: +90 tests across unit, E2E, and orchestrator test files.
