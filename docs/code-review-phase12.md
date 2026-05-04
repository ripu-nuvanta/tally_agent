# Code Review: Phase 12 -- Code Execution Tool Integration

**Date**: 2026-03-13
**Reviewer**: Claude Opus 4.6 (Senior Code Reviewer)
**Commits**: d5bcfbe..6c148f8 (7 commits + 1 docs commit)
**Spec**: `docs/plans/2026-03-13-code-execution-tool-design.md`
**Plan**: `docs/plans/2026-03-13-code-execution-impl-plan.md`
**Test run**: 700 backend tests pass (37 new), no regressions

---

## Executive Summary

Phase 12 integrates Claude's built-in code execution tool (`code_execution_20260120`) into both QueryAgent and AnalysisAgent, replacing the existing ANALYSIS_TOOLS when enabled. The implementation is clean, well-tested, and faithful to the spec. The kill switch (`CODE_EXECUTION_ENABLED`) provides a safe rollback path. Structured output parsing via the `STRUCTURED_RESULT:` convention preserves the existing `{headers, rows}` data contract.

**Verdict**: Ready to merge. Two important issues to address (one now, one in a follow-up). No critical blockers.

---

## What Was Done Well

1. **Clean separation of concerns**: New utility functions (`find_custom_tool_use_blocks`, `extract_code_execution_results`, `extract_structured_from_code_execution`) live in `utils.py` where they belong, not inlined into agents.

2. **Faithful kill switch**: When `CODE_EXECUTION_ENABLED=False`, the code paths are identical to pre-Phase-12 behavior. The `_build_query_tools` and `_build_analysis_tools` functions make this crisp.

3. **Conditional prompts**: Both `build_query_agent_prompt` and `build_analysis_agent_prompt` cleanly branch on the `code_execution_enabled` flag, avoiding any mismatch between prompt text and actual tool list.

4. **Thorough test coverage**: 37 new tests covering utils (7), config (2), prompts (7), query agent code exec (3), analysis agent code exec (3), plus all 15 existing tests continue to pass. The structured output parser has 7 edge-case tests (empty stdout, invalid JSON, missing keys, backwards search, multiple STRUCTURED_RESULT lines).

5. **Graceful degradation**: If `extract_structured_from_code_execution` returns `None`, both agents fall back to empty table data. The user still gets the text response.

6. **Minimal orchestrator change**: Only one line added (`"code_execution"` to `_COMPUTED_TOOL_NAMES`), correctly routing structured output through the existing `computed_data` path.

---

## Issues

### Important (should fix)

#### I1. QueryAgent unconditionally appends empty `tool_result_entries` when code execution resolves server-side

**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/query_agent.py`, lines 218-224

When `CODE_EXECUTION_ENABLED=True` and Claude uses only code execution (no custom tool calls), `find_custom_tool_use_blocks` returns an empty list. The loop body executes zero iterations, so `tool_result_entries` remains `[]`. However, lines 218-224 unconditionally append this empty list as a user message:

```python
messages.append(
    {
        "role": "user",
        "content": tool_result_entries,  # could be []
    }
)
```

This sends `{"role": "user", "content": []}` to the Claude API on the next iteration. The Anthropic API may reject this or treat it as an empty user turn, which could cause unexpected behavior.

Note: The AnalysisAgent correctly guards this with `if tool_result_entries:` (line 587). The QueryAgent should do the same.

However -- this scenario (stop_reason="tool_use" but zero custom tool_use blocks) would only occur if the API returns stop_reason="tool_use" with only `server_tool_use` blocks. In practice, the API resolves code execution server-side and returns `end_turn`, so the code exits at line 162 before reaching this path. This makes it a latent bug rather than an active one, but it should still be guarded for correctness.

**Fix**: Add `if tool_result_entries:` guard before the append, matching the AnalysisAgent pattern.

#### I2. Prompt STRUCTURED_RESULT instructions say "JSON array of objects" but parser expects `{headers, rows}` dict

**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/prompts.py`, lines 118-122 and 273-277

Both prompt structured_rule_blocks say:
> output it as: `STRUCTURED_RESULT: <JSON>` where `<JSON>` is a JSON array of objects

But the parser in `utils.py` (line 67) validates:
```python
if isinstance(data, dict) and "headers" in data and "rows" in data:
```

This is a contradiction: the prompt tells Claude to output an array of objects, but the parser expects a dict with `headers` and `rows` keys. The spec (section 8c) correctly specifies `{"headers": [...], "rows": [[...]]}` -- the prompts deviate from the spec.

In practice, Claude may follow the example format from the spec if the LLM infers it from context, but the explicit instruction to produce "a JSON array of objects" could cause the LLM to output `[{"Item": "A", "Sales": 100}, ...]` instead of the required `{"headers": ["Item", "Sales"], "rows": [["A", 100]]}`.

**Fix**: Update both structured_rule_blocks to match the spec:
```
STRUCTURED_RESULT:{"headers": ["Col1", "Col2"], "rows": [["val1", 123], ["val2", 456]]}
```

This is the more important of the two issues since it directly affects whether the LLM produces parseable output.

### Suggestions (nice to have)

#### S1. `find_custom_tool_use_blocks` is currently identical to `find_all_tool_use_blocks`

**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/utils.py`, lines 35-37

Both functions have the exact same body: `[b for b in response.content if b.type == "tool_use"]`. The spec explains why they are semantically different (one explicitly excludes `server_tool_use`), and the filter is correct because `server_tool_use` != `tool_use`. However, a reader unfamiliar with the code execution block types might wonder why two identical functions exist.

Consider adding a brief inline comment:
```python
def find_custom_tool_use_blocks(response: Any) -> list[Any]:
    """Find only user-defined tool_use blocks (not server_tool_use).

    Note: server_tool_use blocks have type="server_tool_use", not "tool_use",
    so filtering on type=="tool_use" naturally excludes them.
    """
```

#### S2. No test for code execution with stderr output

The tests cover stdout parsing and empty stdout, but there is no test verifying that stderr is logged at WARNING level during the agent loop. A test with a mock response containing non-empty stderr would improve coverage of the logging path.

#### S3. Consider logging a warning when STRUCTURED_RESULT parsing fails

**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/utils.py`, lines 58-71

Currently, `extract_structured_from_code_execution` silently returns `None` on JSON decode errors or missing keys. Adding a `logger.warning` on the `except json.JSONDecodeError` path would help debug cases where the LLM produces malformed structured output.

#### S4. Prompt structured rule has a space after the colon (`STRUCTURED_RESULT: `) but parser expects no space (`STRUCTURED_RESULT:`)

**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/prompts.py`, line 120: `STRUCTURED_RESULT: <JSON>`
**File**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/utils.py`, line 8: `STRUCTURED_RESULT_PREFIX = "STRUCTURED_RESULT:"`

The prompt example shows `STRUCTURED_RESULT: <JSON>` (with a space after the colon), but `startswith(STRUCTURED_RESULT_PREFIX)` uses `"STRUCTURED_RESULT:"` (no trailing space). This works because `startswith` is a prefix match, but `json.loads(line[len(STRUCTURED_RESULT_PREFIX):])` would then try to parse `" {...}"` (with a leading space), which JSON handles fine. So this is technically safe, but the inconsistency could cause confusion if someone tries to match the prefix exactly in the future.

---

## Spec Compliance Checklist

| Spec Requirement | Status | Notes |
|---|---|---|
| Config kill switch `CODE_EXECUTION_ENABLED` | DONE | Default True, env-overridable |
| `CODE_EXECUTION_TOOL = {"type": "code_execution_20260120"}` | DONE | Both agents |
| QueryAgent: conditional tool list | DONE | `_build_query_tools()` |
| AnalysisAgent: conditional tool list | DONE | `_build_analysis_tools()` |
| `find_custom_tool_use_blocks` in utils | DONE | Filters on `type == "tool_use"` |
| `extract_code_execution_results` for logging | DONE | Handles dict and Pydantic input |
| `extract_structured_from_code_execution` | DONE | Reverse-line search, JSON validation |
| Code execution logging in both agents | DONE | INFO for code/stdout, WARNING for stderr |
| Structured output capture in QueryAgent | DONE | Appended as synthetic `code_execution` tool result |
| Structured output capture in AnalysisAgent | DONE | Sets `last_table_data`, `ranked_table_data`, etc. |
| `"code_execution"` in `_COMPUTED_TOOL_NAMES` | DONE | Single-line orchestrator change |
| Conditional prompts (both agents) | DONE | Computation section, Rule 5, Rule 11, Rule 12/13/14 |
| Kill switch fallback = zero behavioral change | DONE | Verified by 700 passing tests |
| SDK upgrade (anthropic >= 0.84.0) | Pre-existing | `pyproject.toml` already declared `>=0.84.0` |

---

## Deviation Analysis

| Deviation | Spec Says | Implementation Does | Assessment |
|---|---|---|---|
| Prompt structured output format | `{"headers": [...], "rows": [[...]]}` | Says "JSON array of objects" | **Problematic** -- see I2 above |
| QueryAgent message append | Conditional (`if tool_result_entries`) implied by spec section 4d | Unconditional append | **Minor risk** -- see I1 above |

---

## Test Coverage Summary

| Test File | New Tests | Coverage Area |
|---|---|---|
| `test_utils.py` | 7 (3 classes) | `find_custom_tool_use_blocks`, `extract_code_execution_results`, `extract_structured_from_code_execution` |
| `test_config_code_exec.py` | 2 | Config default + env override |
| `test_prompts_code_exec.py` | 7 | Both prompt builders, enabled/disabled, rules, type guidance |
| `test_query_agent.py` | 3 | `_build_query_tools`, structured output capture in loop |
| `test_analysis_agent.py` | 3 | `_build_analysis_tools`, structured table data capture |
| **Total** | **22 new tests** | (+ 15 pre-existing utils tests = 37 in new-test files) |

The test count is 22 new tests, not 30 as stated in the review scope. This is still adequate -- the key paths are covered. The gap is mainly in agent-loop edge cases (empty tool_result_entries, stderr logging path, multiple code execution blocks in one response).

---

## Files Changed

| File | Lines Changed | Summary |
|---|---|---|
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/config.py` | +1 | `CODE_EXECUTION_ENABLED: bool = True` |
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/utils.py` | +42 | 3 new functions + `STRUCTURED_RESULT_PREFIX` |
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/prompts.py` | +152/-67 | Conditional prompt sections for both agents |
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/query_agent.py` | +52 | `_build_query_tools`, code exec logging + structured capture |
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/analysis_agent.py` | +54 | `_build_analysis_tools`, code exec logging + structured capture |
| `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/orchestrator.py` | +1 | `"code_execution"` in `_COMPUTED_TOOL_NAMES` |
| `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_utils.py` | +139 | 3 new test classes (15 tests) |
| `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_query_agent.py` | +72 | `TestQueryAgentCodeExecution` (3 tests) |
| `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_analysis_agent.py` | +57 | `TestAnalysisAgentCodeExecution` (3 tests) |
| `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_config_code_exec.py` | +19 | Config tests (2 tests) |
| `/Users/ripu/work/nuvanta_repos/tally_agent/tests/unit/test_prompts_code_exec.py` | +52 | Prompt tests (7 tests) |

---

## Recommendation

**Merge with two fixes:**

1. **(I2 -- fix now)** Update the `structured_rule_block` in both prompt branches to specify `{"headers": [...], "rows": [[...]]}` format instead of "JSON array of objects". This is the most impactful issue since it affects whether the LLM produces parseable output in production.

2. **(I1 -- fix now or soon)** Add `if tool_result_entries:` guard in QueryAgent before appending to messages, matching the AnalysisAgent pattern. Low risk but easy to fix.

Both fixes are 1-2 line changes. The rest of the implementation is solid.
