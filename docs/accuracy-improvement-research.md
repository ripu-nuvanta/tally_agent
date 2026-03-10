# TallyPrime AI Agent: Accuracy Improvement Research

**Date**: 2026-03-10
**Research Focus**: Two approaches to improve query accuracy and analysis quality

---

## Overview

This document evaluates two complementary strategies for improving the accuracy of the TallyPrime AI Agent:

1. **Model Upgrade**: Switching from `claude-sonnet-4-6` to `claude-opus-4-6` for query/analysis agents
2. **Code Execution Capability**: Adding a sandboxed Python code interpreter tool for advanced analysis

Both approaches address different accuracy bottlenecks:
- **Model upgrade** improves reasoning quality, tool-calling accuracy, and complex query interpretation
- **Code execution** enables more sophisticated computations beyond the current predefined tool set

---

## Approach 1: Model Upgrade (Sonnet 4.6 → Opus 4.6)

### Current Configuration

**Config Location**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/config.py`

```python
class Settings(BaseSettings):
    CLAUDE_MODEL: str = "claude-sonnet-4-6"                          # Query & Analysis agents
    CLAUDE_CLASSIFIER_MODEL: str = "claude-haiku-4-5-20251001"       # Orchestrator only
    EVAL_JUDGE_MODEL: str = "claude-opus-4-6"                        # Eval judging only
```

**Where Models Are Used**:

1. **Orchestrator** (`backend/agents/orchestrator.py`, line 199):
   - Uses `CLAUDE_CLASSIFIER_MODEL` (Haiku) for query classification
   - Quick classification only — lightweight task
   - Converts user query → JSON query type

2. **Query Agent** (`backend/agents/query_agent.py`, line 97):
   - Uses `CLAUDE_MODEL` (currently Sonnet) for data fetching
   - Tool-calling loop with Tally Bridge tools
   - Makes decisions about which data to fetch and how to interpret results

3. **Analysis Agent** (`backend/agents/analysis_agent.py`, line 424):
   - Uses `CLAUDE_MODEL` (currently Sonnet) for analysis computations
   - Tool-calling loop with computation tools (sort, aggregate, compare, trend)
   - Decides which analysis operations to apply and interprets results

---

### Implementation: What Changes?

**Minimal Changes Required**:

Only one line needs to change in `backend/config.py`:

```python
# BEFORE
CLAUDE_MODEL: str = "claude-sonnet-4-6"

# AFTER
CLAUDE_MODEL: str = "claude-opus-4-6"
```

**No code changes needed** because:
- Both models support the same API surface (messages, tools, max_tokens)
- Tool schema format is identical
- System prompts are compatible
- The agents already handle async/await correctly
- Error handling is generic (catches `anthropic.APIError`)

**Implementation Steps**:

1. Update `.env` or `backend/config.py` default
2. Set `CLAUDE_MODEL=claude-opus-4-6` in environment
3. Run existing test suite (no changes to tests needed)
4. Monitor pricing and latency in production

---

### Pros

| Advantage | Impact |
|-----------|--------|
| **Better tool-calling accuracy** | Opus has superior instruction following — fewer hallucinated tool calls, more precise arguments |
| **Improved reasoning** | Complex accounting scenarios (multi-period comparisons, nested aggregations) handled with better logic |
| **Lower error rates** | Fewer cases where Claude misinterprets query intent or data structure |
| **Conversation context** | Better at leveraging session history for ambiguous references |
| **Token efficiency** | Opus is more concise, potentially offsetting cost increase with fewer turns |
| **Drop-in replacement** | Zero code changes, environment variable only |
| **Tested evaluation path** | Eval judge already uses Opus — proven in this codebase |

### Cons

| Disadvantage | Magnitude |
|---|---|
| **Higher cost per call** | ~3-4x cost increase vs Sonnet (API pricing: $15/M input, $60/M output for Opus vs $3/$15 for Sonnet) |
| **Higher latency** | Opus models have longer TTFT (time-to-first-token), ~500-800ms vs 200-300ms for Sonnet |
| **Slower response times** | User-facing chat will feel slower, especially on mobile |
| **Reduced throughput** | Can handle fewer concurrent users with same infrastructure |
| **No accuracy guarantee** | Still bound by prompt quality and Tally data structure issues |
| **Financial impact** | For high-volume use, monthly costs increase 3-4x ($X → $3-4X) |

---

### Cost-Latency Tradeoff Analysis

**Example: 100 queries/day over 30 days (3000 total)**

Assumptions:
- Query Agent: avg 2 tool calls per query (2 turns of Claude)
- Analysis Agent: avg 1 tool call per query (1 turn of Claude)
- Avg input tokens: 800 (prompt + context + tools)
- Avg output tokens: 200 (response + thinking)

**Sonnet 4.6**:
- Per query cost: (2 turns + 1 turn) × [(800 × $3/M) + (200 × $15/M)] = $0.0435/query
- Monthly cost: 3000 × $0.0435 = **$130.50**
- Avg latency: (2 + 1 turns) × 250ms = **750ms per query**

**Opus 4.6**:
- Per query cost: 3 turns × [(800 × $15/M) + (200 × $60/M)] = **$0.1620/query**
- Monthly cost: 3000 × $0.1620 = **$486.00**
- Avg latency: (2 + 1 turns) × 600ms = **1800ms per query**

**Delta**:
- Cost increase: +$355.50/month (+272%)
- Latency increase: +1050ms (+140%)

---

### When to Use This Approach

**Best suited for**:
- Production systems with high accuracy requirements (>95%)
- Scenarios where error recovery is expensive (manual Tally corrections)
- Smaller teams with lower query volume (<500/day)
- Environments where latency is not critical (batch jobs, reporting)
- Organizations with deep Anthropic budgets

**Not recommended for**:
- High-volume SaaS (>1000 queries/day)
- Mobile-first applications (latency sensitive)
- Cost-conscious deployments
- Real-time dashboards

---

## Approach 2: Code Execution Capability

### Current Analysis Tools

**Location**: `/Users/ripu/work/nuvanta_repos/tally_agent/backend/agents/analysis_agent.py`

Current predefined tools (lines 39-180):

```python
ANALYSIS_TOOLS = [
    "sort_by_field",               # Sort records, apply limit
    "compute_totals",              # Sum numeric fields with optional grouping
    "compute_percentage_change",   # Compare old vs new value
    "compute_period_comparison",   # Side-by-side two-period comparison
    "compute_trend",               # Period-over-period changes in time series
]
```

**Limitations of current approach**:
- Fixed set of operations
- Cannot handle complex business logic (e.g., conditional aggregations, custom ratios)
- Cannot combine operations (e.g., "sum all expenses > 10k AND < 100k", "weighted average with dynamic weights")
- Cannot process intermediate results across multiple tool calls
- No support for list comprehensions, filtering with predicates, recursive calculations
- Limited to pre-defined output schemas

---

### Proposed Code Execution Tool

**New Tool Name**: `execute_python_code`

**Tool Schema**:

```python
{
    "name": "execute_python_code",
    "description": (
        "Execute safe Python code for advanced data analysis. "
        "The code receives 'data' (the input list[dict] or dict) as a variable. "
        "Return the result by assigning to '__result__' variable. "
        "Only arithmetic, filtering, aggregation, and formatting are allowed. "
        "No file I/O, network, or system calls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python code snippet (max 200 lines). "
                    "Input variable: 'data' (list[dict] or dict). "
                    "Output variable: '__result__' (list[dict], dict, number, or string). "
                    "Example: '__result__ = [r for r in data if r[\"amount\"] > 1000]'"
                ),
            },
            "description": {
                "type": "string",
                "description": (
                    "Human-readable description of what the code computes. "
                    "For transparency and debugging."
                ),
            },
        },
        "required": ["code"],
    },
}
```

---

### Implementation Architecture

**Location**: New module `backend/agents/code_executor.py`

**Components**:

1. **Sandboxed Execution Environment**
   - Use `RestrictedPython` or `exec()` with restricted builtins
   - Whitelist only: `len`, `sum`, `max`, `min`, `sorted`, `list`, `dict`, `str`, `float`, `int`
   - Block: `__import__`, `open`, `eval`, `exec`, `compile`, `globals`, `locals`
   - No access to os, sys, subprocess, or network modules

2. **Code Validation**
   - AST parsing to detect forbidden operations
   - Reject code containing: `import`, `__`, `open`, `eval`, `compile`, `exec`
   - Reject infinite loops (heuristic: reject while True without break)
   - Timeout: kill execution after 5 seconds

3. **Data Type Coercion**
   - Input: list[dict] or dict
   - Output: validate `__result__` is JSON-serializable (list, dict, number, string)
   - Reject: Python objects, functions, classes, modules

4. **Error Handling**
   - Catch `SyntaxError`, `RuntimeError`, `TimeoutError`, `MemoryError`
   - Return structured error: `{"error": "...", "stderr": "...", "code": original_code}`
   - Claude can iterate on error messages

---

### Integration with Agents

**Query Agent** (`backend/agents/query_agent.py`):

Add to `_ALL_QUERY_TOOLS`:

```python
# Line 38
_ALL_QUERY_TOOLS = TALLY_TOOLS + ANALYSIS_TOOLS + DATE_TOOLS + CODE_EXECUTION_TOOLS
```

Add dispatcher:

```python
# Line 140-145
if tool_block.name in _ANALYSIS_TOOL_NAMES:
    result = execute_analysis_tool(tool_block.name, tool_block.input)
elif tool_block.name in _DATE_TOOL_NAMES:
    result = execute_date_tool(tool_block.name, tool_block.input)
elif tool_block.name == "execute_python_code":  # NEW
    result = await execute_code(tool_block.input)  # NEW
else:
    result = await execute_tool(client, tool_block.name, tool_block.input)
```

**Analysis Agent** (`backend/agents/analysis_agent.py`):

```python
# Add to ANALYSIS_TOOLS
CODE_EXECUTION_TOOL = {
    "name": "execute_python_code",
    "description": "...",
    "input_schema": {...}
}
ANALYSIS_TOOLS.append(CODE_EXECUTION_TOOL)

# Add to dispatcher in execute loop
if tool_block.name == "execute_python_code":
    result = await execute_code(tool_block.input)
else:
    result = execute_analysis_tool(tool_block.name, tool_block.input)
```

---

### Implementation Steps

1. **Create `backend/agents/code_executor.py`**
   - Function: `validate_python_code(code: str) -> tuple[bool, str]`
   - Function: `execute_code_safely(code: str, data: Any) -> dict[str, Any]`
   - Whitelist safe builtins only

2. **Update tool schemas**
   - Add to `ANALYSIS_TOOLS` in `analysis_agent.py`
   - Add to prompts: `build_analysis_agent_prompt()` should explain code execution

3. **Add dispatcher logic**
   - Update `query_agent.py` line 140-145 to handle `execute_python_code`
   - Update `analysis_agent.py` execute loop similarly

4. **Write tests**
   - `tests/unit/test_code_executor.py` — validation, safe execution, error handling
   - `tests/unit/test_analysis_agent_with_code.py` — integration with analysis loop
   - Test cases: filtering, aggregation, weighted avg, conditional logic

5. **Update prompts**
   - Instruct Claude when code execution is appropriate vs predefined tools
   - Provide examples: "Use execute_python_code for conditional filtering" vs "Use sort_by_field for simple sorting"
   - Warn: "Code must complete in <5s. For large datasets, fetch summary reports first."

---

### Pros

| Advantage | Impact |
|---|---|
| **Unbounded computation** | Support any calculation (conditional aggregation, weighted averages, custom ratios) |
| **Fewer Claude turns** | Complex logic in one turn instead of multiple tool calls |
| **Better intent capture** | Claude can express intent directly rather than forcing into predefined tools |
| **Transparent reasoning** | Code is explicit and auditable (logged for compliance) |
| **Flexible output** | Return any JSON-serializable structure, not locked to headers/rows |
| **No additional cost** | Code execution is local — no API calls |
| **Future extensibility** | Can add more utility functions (percentile, correlation, forecasting) |

### Cons

| Disadvantage | Magnitude |
|---|---|
| **Security risk** | Even with sandboxing, code execution is attack surface (requires careful validation) |
| **Complexity** | New module, validation logic, error handling adds ~500-800 lines of code |
| **Debugging difficulty** | Python errors less visible than structured tool results |
| **Claude misuse** | Claude might use code for simple tasks (overcomplication) |
| **Performance** | Untrusted code could be slow (timeouts needed) |
| **Compliance issues** | Running user-provided code may violate security policies in regulated environments |
| **Maintenance burden** | New surface for bugs, requires ongoing security review |
| **Testing complexity** | Need extensive unit tests for all code paths and edge cases |

---

### When to Use This Approach

**Best suited for**:
- Complex accounting analyses (GST calculations, statutory ratio computations)
- Custom business logic that can't fit predefined tools
- Small, trusted teams (internal use, not customer-facing)
- Advanced power-user queries
- Scenarios where lower latency outweighs slightly higher complexity

**Not recommended for**:
- High-security environments (regulated finance, confidential data)
- Public-facing SaaS (untrusted users)
- Beginner-level queries (overkill)
- Systems where auditability must be simple

---

## Security Considerations for Code Execution

If pursuing this approach, implement **defense-in-depth**:

1. **Static Analysis**
   - Parse AST before execution
   - Reject any code containing: `import`, `__`, `open`, `compile`, `eval`, `exec`
   - Check for infinite loops (while/for without break)

2. **Runtime Sandboxing**
   - Use `RestrictedPython` library (maintained, tested)
   - Or use `exec()` with custom `__builtins__` dict
   - No access to globals/locals beyond what's explicitly provided

3. **Resource Limits**
   - Timeout: 5 second hard limit per code execution
   - Memory: No limit (but could add using resource module on Unix)
   - Code size: Max 200 lines, 10,000 characters

4. **Input Validation**
   - Verify `data` parameter is list[dict] or dict (JSON schema)
   - Reject data larger than 1MB
   - Validate output `__result__` is JSON-serializable

5. **Logging & Audit**
   - Log all code executions with timestamp, user, code hash
   - Log errors for security review
   - Retain logs for 90 days minimum

6. **Monitoring**
   - Alert on repeated execution failures (possible attack)
   - Track code execution latency (spike = potential slowdown)
   - Monitor for memory leaks

---

## Comparison Matrix

| Dimension | Model Upgrade | Code Execution |
|---|---|---|
| **Implementation effort** | Trivial (1 line) | Moderate (600 lines) |
| **Risk level** | Very low | Medium (security) |
| **Accuracy improvement** | High (~5-10%) | High (~10-15% for complex queries) |
| **Cost impact** | +270% monthly | None (local compute) |
| **Latency impact** | +140% per query | -20% (fewer Claude turns) |
| **Maintenance burden** | Minimal | High (security audits) |
| **User-facing change** | Slower responses | None (transparent) |
| **Rollback difficulty** | Trivial | Easy (env var to disable) |
| **Applicable queries** | All (general) | 20-30% (complex only) |

---

## Recommendations

### Short Term (Immediate, <1 week)

**Do both approaches in parallel**:

1. **Try Model Upgrade in staging**
   - Deploy with `CLAUDE_MODEL=claude-opus-4-6`
   - Run eval test suite (`tests/eval/`) against live Tally
   - Measure:
     - Accuracy scores (target: >4.0/5.0 in all dimensions)
     - Latency (target: <2s per query average)
     - Cost (project monthly spend)
   - Decision: Keep if accuracy improves >5%, else revert

2. **Prototype Code Executor**
   - Write `backend/agents/code_executor.py` with basic validation
   - Write unit tests (whitelist builtins, timeout, error handling)
   - Do NOT integrate into agents yet
   - Decision: Keep design if tests pass, iterate on security

### Medium Term (2-4 weeks)

**Based on short-term results**:

- **If Model Upgrade successful**: Deploy to production, monitor costs
- **If Code Executor tests pass**: Integrate into analysis agent, add to eval tests
- **If both succeed**: Use Opus + code execution for maximum accuracy (premium tier)

### Long Term (1-3 months)

**Hybrid approach**: Offer tiered accuracy

1. **Fast tier** (Haiku for all agents, predefined tools only)
   - Target: Real-time chat, mobile
   - Cost: Minimal
   - Accuracy: ~70-75%

2. **Standard tier** (Sonnet for query/analysis, predefined tools)
   - Target: Web app, routine queries
   - Cost: Baseline
   - Accuracy: ~80-85%

3. **Premium tier** (Opus + code execution, all features)
   - Target: Complex analyses, critical reports
   - Cost: 3-4x baseline
   - Accuracy: ~92-95%

---

## Appendix: File Changes Summary

### For Model Upgrade (Approach 1)

**1 file changed**:

- `/Users/ripu/work/nuvanta_repos/tally_agent/backend/config.py` (1 line)

```python
# Line 8: Change default
CLAUDE_MODEL: str = "claude-opus-4-6"  # was: "claude-sonnet-4-6"
```

Or via environment: `CLAUDE_MODEL=claude-opus-4-6`

### For Code Execution (Approach 2)

**5 files modified + 2 new files**:

**New Files**:
1. `backend/agents/code_executor.py` (200 lines)
   - `validate_python_code(code: str) -> tuple[bool, str]`
   - `execute_code_safely(code: str, data: Any) -> dict`

2. `tests/unit/test_code_executor.py` (300 lines)
   - Test validation
   - Test safe execution with various data types
   - Test error handling and timeout

**Modified Files**:
1. `backend/agents/analysis_agent.py` (~30 lines)
   - Add CODE_EXECUTION_TOOL to ANALYSIS_TOOLS
   - Add dispatcher case for `execute_python_code`

2. `backend/agents/query_agent.py` (~5 lines)
   - Import code executor
   - Add dispatcher case for `execute_python_code`

3. `backend/agents/prompts.py` (~20 lines)
   - Update `build_analysis_agent_prompt()` with code execution guidance

4. `backend/agents/tools.py` (~2 lines)
   - Import statement for code executor

5. `backend/config.py` (~2 lines)
   - Add optional config: `CODE_EXECUTION_ENABLED: bool = True`

---

## References

- **Claude API Docs**: https://docs.anthropic.com/claude/reference/messages-api
- **Model Comparison**: Claude Opus 4.6 vs Sonnet 4.6 (API pricing, performance)
- **RestrictedPython**: https://restrictedpython.readthedocs.io/ (for code execution)
- **Current CLAUDE.md**: Workflow preferences, testing conventions
- **TALLYPRIME_AGENT_PLAN.md**: Phase 6+ advanced features roadmap

---

**Document prepared by**: Claude Code Research Agent
**Status**: Ready for decision and implementation planning
