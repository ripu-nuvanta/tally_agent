# Manual Test Issues — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 6 bugs/enhancements found during manual testing — JSON parsing, date resolution, multi-table rendering, quick action eval coverage, and single-query eval scenarios.

**Architecture:** Backend fixes in orchestrator (JSON fence stripping, multi-dataset packaging), new `resolve_date_range` tool in date_utils + tools.py, prompt injection of current date into QueryAgent. Frontend fix in MessageBubble for multi-table rendering and markdown table stripping. New eval YAML scenarios.

**Tech Stack:** Python (FastAPI, Pydantic), React (TypeScript, Vitest, React Testing Library), Playwright, Claude API tool-calling, YAML eval scenarios.

**Design doc:** `docs/plans/2026-03-06-manual-test-fixes-design.md`

---

### Task 1: Fix JSON Markdown Fence Stripping in Orchestrator

**Files:**
- Modify: `backend/agents/orchestrator.py:191-196`
- Test: `tests/unit/test_orchestrator.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_orchestrator.py`:

```python
import re
from backend.agents.orchestrator import _strip_markdown_fences


class TestStripMarkdownFences:
    def test_strips_json_fences(self):
        text = '```json\n{"query_type": "simple_lookup"}\n```'
        assert _strip_markdown_fences(text) == '{"query_type": "simple_lookup"}'

    def test_strips_plain_fences(self):
        text = '```\n{"query_type": "greeting"}\n```'
        assert _strip_markdown_fences(text) == '{"query_type": "greeting"}'

    def test_no_fences_passthrough(self):
        text = '{"query_type": "trend"}'
        assert _strip_markdown_fences(text) == '{"query_type": "trend"}'

    def test_strips_fences_with_extra_whitespace(self):
        text = '  ```json\n  {"query_type": "comparison"}  \n```  '
        result = _strip_markdown_fences(text)
        assert json.loads(result)["query_type"] == "comparison"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_orchestrator.py::TestStripMarkdownFences -v`
Expected: FAIL with `ImportError: cannot import name '_strip_markdown_fences'`

**Step 3: Implement `_strip_markdown_fences` and use it in `_classify`**

In `backend/agents/orchestrator.py`, add before `_extract_all_data`:

```python
import re

def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from text."""
    stripped = text.strip()
    match = re.match(r'^```(?:json)?\s*\n?(.*?)\n?\s*```$', stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped
```

Update `_classify` at line 192-193:

```python
        try:
            return json.loads(_strip_markdown_fences(text))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_orchestrator.py::TestStripMarkdownFences -v`
Expected: PASS (4 tests)

**Step 5: Also add integration test for classification with fences**

Add to `tests/unit/test_orchestrator.py`:

```python
class TestOrchestratorClassification:
    # ... existing tests ...

    @pytest.mark.asyncio
    async def test_classification_with_markdown_fences(self):
        """Claude response wrapped in ```json fences should still parse."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        fenced_json = '```json\n{"query_type": "greeting", "requires_chart": false, "reasoning": "hi", "clarification_question": null}\n```'

        msg = MagicMock()
        msg.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = fenced_json
        msg.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=msg)
            orch = Orchestrator()
            result = await orch.process_query("Hello!", mock_client, session)

        assert result["query_type"] == "greeting"
```

**Step 6: Run all orchestrator tests**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add backend/agents/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "fix: strip markdown fences from classification JSON response"
```

---

### Task 2: Fix ChatResponse.data Type to Accept list[dict]

**Files:**
- Modify: `backend/api/models.py:30-34`
- Modify: `backend/api/chat.py:32-37`
- Test: `tests/unit/test_api_models.py` (create if needed)

**Step 1: Write the failing tests**

Create or add to `tests/unit/test_api_models.py`:

```python
import pytest
from backend.api.models import ChatResponse


class TestChatResponseDataType:
    def test_accepts_dict_data(self):
        resp = ChatResponse(
            message="ok",
            data={"headers": ["A"], "rows": [[1]]},
            session_id="s1",
        )
        assert resp.data == {"headers": ["A"], "rows": [[1]]}

    def test_accepts_none_data(self):
        resp = ChatResponse(message="ok", session_id="s1")
        assert resp.data is None

    def test_accepts_list_of_dicts_data(self):
        data = [{"headers": ["A"], "rows": [[1]]}, {"headers": ["B"], "rows": [[2]]}]
        resp = ChatResponse(message="ok", data=data, session_id="s1")
        assert resp.data == data

    def test_rejects_string_data(self):
        with pytest.raises(Exception):
            ChatResponse(message="ok", data="bad", session_id="s1")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_api_models.py::TestChatResponseDataType -v`
Expected: `test_accepts_list_of_dicts_data` FAILS with Pydantic validation error

**Step 3: Widen the ChatResponse.data type**

In `backend/api/models.py` line 32, change:

```python
# FROM:
    data: dict[str, Any] | None = None
# TO:
    data: dict[str, Any] | list[dict[str, Any]] | None = None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_api_models.py::TestChatResponseDataType -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
git add backend/api/models.py tests/unit/test_api_models.py
git commit -m "fix: widen ChatResponse.data to accept list[dict] for multi-dataset responses"
```

---

### Task 3: Package Multi-Dataset Results in Orchestrator

**Files:**
- Modify: `backend/agents/orchestrator.py:118-119` and `:128`
- Modify: `backend/api/chat.py:32-37`
- Test: `tests/unit/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_orchestrator.py`:

```python
class TestOrchestratorMultiDataset:
    @pytest.mark.asyncio
    async def test_multiple_tool_results_packaged_as_datasets(self):
        """When QueryAgent returns multiple datasets, orchestrator packages them."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "comparison",
            "requires_chart": False,
            "reasoning": "comparing",
            "clarification_question": None,
        }

        # Mock query agent to return multiple tool results
        agent_result = {
            "message": "Here is the comparison",
            "tool_results": [
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q1"]]}}},
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q2"]]}}},
            ],
        }

        analysis_result = {
            "message": "Q1 vs Q2 analysis",
            "data": {"headers": ["Period", "Total"], "rows": [["Q1", 100], ["Q2", 200]]},
            "tool_results": [],
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            with patch.object(orch.query_agent, "execute", new_callable=AsyncMock, return_value=agent_result), \
                 patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock, return_value=analysis_result):
                result = await orch.process_query("Compare Q1 vs Q2", mock_client, session)

        # Analysis agent's data should be used when available
        assert result["data"] is not None
```

**Step 2: Run to verify it passes (baseline)**

Run: `pytest tests/unit/test_orchestrator.py::TestOrchestratorMultiDataset -v`

**Step 3: Update orchestrator to pass all data to frontend**

In `backend/agents/orchestrator.py`, modify `process_query` around line 119:

```python
        # Keep ALL datasets for comparison queries, not just the last
        raw_data = all_data[-1] if all_data else None
        all_datasets = all_data if len(all_data) > 1 else None
```

And around line 157-162, update the return:

```python
        # For multi-dataset responses, pass all datasets
        final_data = data
        if final_data is None and all_datasets is not None:
            final_data = all_datasets

        return {
            "query_type": query_type,
            "message": message,
            "data": final_data,
            "chart": chart,
            "session_id": session.session_id,
        }
```

**Step 4: Run all orchestrator tests**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/agents/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "fix: pass all datasets to frontend for multi-dataset comparison queries"
```

---

### Task 4: Add `resolve_date_range` Tool

**Files:**
- Modify: `backend/utils/date_utils.py`
- Modify: `backend/agents/tools.py`
- Test: `tests/unit/test_date_utils.py`

**Step 1: Write the failing tests for `resolve_date_range`**

Add to `tests/unit/test_date_utils.py`:

```python
from backend.utils.date_utils import resolve_date_range


class TestResolveDateRange:
    def test_q1(self):
        result = resolve_date_range("Q1", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "30-06-2025"
        assert "Q1" in result["description"]

    def test_q2(self):
        result = resolve_date_range("Q2", date(2026, 3, 6))
        assert result["from_date"] == "01-07-2025"
        assert result["to_date"] == "30-09-2025"

    def test_q3(self):
        result = resolve_date_range("Q3", date(2026, 3, 6))
        assert result["from_date"] == "01-10-2025"
        assert result["to_date"] == "31-12-2025"

    def test_q4(self):
        result = resolve_date_range("Q4", date(2026, 3, 6))
        assert result["from_date"] == "01-01-2026"
        assert result["to_date"] == "31-03-2026"

    def test_this_month(self):
        result = resolve_date_range("this month", date(2026, 3, 6))
        assert result["from_date"] == "01-03-2026"
        assert result["to_date"] == "31-03-2026"

    def test_last_month(self):
        result = resolve_date_range("last month", date(2026, 3, 6))
        assert result["from_date"] == "01-02-2026"
        assert result["to_date"] == "28-02-2026"

    def test_this_quarter(self):
        result = resolve_date_range("this quarter", date(2026, 3, 6))
        assert result["from_date"] == "01-01-2026"
        assert result["to_date"] == "31-03-2026"

    def test_last_quarter(self):
        result = resolve_date_range("last quarter", date(2026, 3, 6))
        assert result["from_date"] == "01-10-2025"
        assert result["to_date"] == "31-12-2025"

    def test_current_fy(self):
        result = resolve_date_range("current FY", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "31-03-2026"

    def test_last_fy(self):
        result = resolve_date_range("last FY", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2024"
        assert result["to_date"] == "31-03-2025"

    def test_ytd(self):
        result = resolve_date_range("YTD", date(2026, 3, 6))
        assert result["from_date"] == "01-04-2025"
        assert result["to_date"] == "06-03-2026"

    def test_last_n_months(self):
        result = resolve_date_range("last 3 months", date(2026, 3, 6))
        assert result["from_date"] == "01-12-2025"
        assert result["to_date"] == "06-03-2026"

    def test_q2_explicit_fy(self):
        result = resolve_date_range("Q2 2025-26", date(2026, 3, 6))
        assert result["from_date"] == "01-07-2025"
        assert result["to_date"] == "30-09-2025"

    def test_unknown_returns_error(self):
        result = resolve_date_range("banana", date(2026, 3, 6))
        assert "error" in result
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_date_utils.py::TestResolveDateRange -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_date_range'`

**Step 3: Implement `resolve_date_range` in date_utils.py**

Add to `backend/utils/date_utils.py`:

```python
import re
from dateutil.relativedelta import relativedelta


def resolve_date_range(description: str, ref: date | None = None) -> dict:
    """Resolve a natural-language date description to a from_date/to_date range.

    Args:
        description: Natural language like "Q2", "this month", "last quarter",
                     "last 3 months", "YTD", "current FY", "Q2 2025-26".
        ref: Reference date (defaults to today).

    Returns:
        {"from_date": "DD-MM-YYYY", "to_date": "DD-MM-YYYY", "description": "..."}
        or {"error": "Could not resolve..."} if unrecognized.
    """
    if ref is None:
        ref = date.today()

    desc = description.strip().lower()

    # --- Specific quarter: Q1, Q2, Q3, Q4 (optionally with FY year) ---
    q_match = re.match(r'^q([1-4])(?:\s+(\d{4})[-–](\d{2,4}))?$', desc)
    if q_match:
        q_num = int(q_match.group(1))
        if q_match.group(2):
            fy_start_year = int(q_match.group(2))
        else:
            fy_start_year = get_fy_start(ref).year
        start_month, end_month = _QUARTERS[q_num - 1]
        if q_num <= 3:  # Q1-Q3 are in the FY start year
            year = fy_start_year
        else:  # Q4 is in the FY end year
            year = fy_start_year + 1
        last_day = calendar.monthrange(year, end_month)[1]
        return {
            "from_date": format_for_tally(date(year, start_month, 1)),
            "to_date": format_for_tally(date(year, end_month, last_day)),
            "description": f"Q{q_num} FY {fy_start_year}-{(fy_start_year+1) % 100:02d}",
        }

    # --- This month ---
    if desc in ("this month", "current month"):
        start, end = get_month_range(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"{ref.strftime('%B %Y')}",
        }

    # --- Last month ---
    if desc == "last month":
        prev = ref.replace(day=1) - timedelta(days=1)
        start, end = get_month_range(prev)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"{prev.strftime('%B %Y')}",
        }

    # --- This quarter / current quarter ---
    if desc in ("this quarter", "current quarter"):
        start, end = get_current_quarter_range(ref)
        qi = _get_quarter_index(ref.month)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"Q{qi+1} (current quarter)",
        }

    # --- Last quarter ---
    if desc == "last quarter":
        start, end = get_last_quarter_range(ref)
        qi = (_get_quarter_index(ref.month) - 1) % 4
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"Q{qi+1} (previous quarter)",
        }

    # --- Current FY / this year ---
    if desc in ("current fy", "this fy", "this year", "current year", "current financial year"):
        start = get_fy_start(ref)
        end = get_fy_end(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"FY {start.year}-{(start.year+1) % 100:02d}",
        }

    # --- Last FY / last year ---
    if desc in ("last fy", "last year", "previous fy", "previous year", "last financial year"):
        start, end = get_last_fy_range(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(end),
            "description": f"FY {start.year}-{(start.year+1) % 100:02d}",
        }

    # --- YTD (Year to Date — from FY start to today) ---
    if desc in ("ytd", "year to date"):
        start = get_fy_start(ref)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(ref),
            "description": f"YTD ({format_for_tally(start)} to {format_for_tally(ref)})",
        }

    # --- Last N months ---
    last_n = re.match(r'^last\s+(\d+)\s+months?$', desc)
    if last_n:
        n = int(last_n.group(1))
        start = (ref.replace(day=1) - relativedelta(months=n - 1)).replace(day=1)
        return {
            "from_date": format_for_tally(start),
            "to_date": format_for_tally(ref),
            "description": f"Last {n} months",
        }

    return {"error": f"Could not resolve date range: '{description}'"}
```

Also add the import at top of date_utils.py:

```python
from datetime import date, timedelta
```

Note: `dateutil` dependency — check if already in pyproject.toml. If not, add `python-dateutil` to deps.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_date_utils.py::TestResolveDateRange -v`
Expected: All 14 PASS

**Step 5: Add tool schema and handler to tools.py**

In `backend/agents/tools.py`, add to `TALLY_TOOLS` list:

```python
    {
        "name": "resolve_date_range",
        "description": "Convert a natural-language date expression to exact DD-MM-YYYY from/to dates using the Indian Financial Year calendar. Use this BEFORE calling any Tally tool when the user uses relative dates like 'this month', 'Q2', 'last quarter', 'YTD', 'last 3 months', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural-language date expression (e.g. 'Q2', 'this month', 'last quarter', 'current FY', 'last 3 months', 'YTD', 'Q2 2025-26')",
                },
            },
            "required": ["description"],
        },
    },
```

Note: This tool does NOT go in TALLY_TOOLS — it doesn't need a TallyClient. Create a separate list or handle it specially.

Actually, simpler approach: add `resolve_date_range` as a **non-Tally tool** alongside the analysis tools in the QueryAgent's combined tool list. Add to `tools.py`:

```python
from backend.utils.date_utils import resolve_date_range as _resolve_date_range

DATE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "resolve_date_range",
        "description": "Convert a natural-language date expression to exact DD-MM-YYYY from/to dates using the Indian Financial Year calendar. ALWAYS call this BEFORE calling any Tally tool when the user uses relative dates like 'this month', 'Q2', 'last quarter', 'YTD', 'last 3 months', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural-language date expression (e.g. 'Q2', 'this month', 'last quarter', 'current FY', 'last 3 months', 'YTD', 'Q2 2025-26')",
                },
            },
            "required": ["description"],
        },
    },
]


def execute_date_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a date resolution tool synchronously."""
    if tool_name == "resolve_date_range":
        return {"success": True, "data": _resolve_date_range(tool_input["description"])}
    return {"error": f"Unknown date tool: {tool_name!r}"}
```

Then in `backend/agents/query_agent.py`, add DATE_TOOLS to the combined list:

```python
from backend.agents.tools import TALLY_TOOLS, execute_tool, DATE_TOOLS, execute_date_tool

_DATE_TOOL_NAMES = {t["name"] for t in DATE_TOOLS}
_ALL_QUERY_TOOLS = TALLY_TOOLS + ANALYSIS_TOOLS + DATE_TOOLS
```

And in the tool dispatch loop (line 132-135):

```python
                if tool_block.name in _ANALYSIS_TOOL_NAMES:
                    result = execute_analysis_tool(tool_block.name, tool_block.input)
                elif tool_block.name in _DATE_TOOL_NAMES:
                    result = execute_date_tool(tool_block.name, tool_block.input)
                else:
                    result = await execute_tool(client, tool_block.name, tool_block.input)
```

**Step 6: Write integration test for date tool execution**

Add to `tests/unit/test_tools.py` (or create):

```python
from backend.agents.tools import execute_date_tool


class TestDateToolExecution:
    def test_resolve_date_range_q2(self):
        result = execute_date_tool("resolve_date_range", {"description": "Q2"})
        assert result["success"] is True
        assert result["data"]["from_date"] == "01-07-2025"  # depends on today

    def test_unknown_date_tool(self):
        result = execute_date_tool("unknown_tool", {})
        assert "error" in result
```

**Step 7: Run all tests**

Run: `pytest tests/unit/test_date_utils.py tests/unit/test_tools.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add backend/utils/date_utils.py backend/agents/tools.py backend/agents/query_agent.py tests/unit/test_date_utils.py tests/unit/test_tools.py
git commit -m "feat: add resolve_date_range tool for accurate date interpretation"
```

---

### Task 5: Inject Current Date into QueryAgent Prompt

**Files:**
- Modify: `backend/agents/prompts.py:65-120`
- Modify: `backend/agents/query_agent.py:50`
- Modify: `backend/agents/orchestrator.py` (pass date to QueryAgent)
- Test: `tests/unit/test_prompts.py` (create if needed)

**Step 1: Write the failing test**

```python
from backend.agents.prompts import build_query_agent_prompt


class TestQueryAgentPrompt:
    def test_includes_current_date(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "06-03-2026" in prompt

    def test_includes_resolve_date_range_instruction(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "resolve_date_range" in prompt
```

**Step 2: Run to verify it fails**

Run: `pytest tests/unit/test_prompts.py::TestQueryAgentPrompt -v`
Expected: FAIL — `build_query_agent_prompt()` doesn't accept a date parameter

**Step 3: Update `build_query_agent_prompt` to accept current_date**

In `backend/agents/prompts.py`, modify `build_query_agent_prompt`:

```python
def build_query_agent_prompt(current_date: str) -> str:
```

Add to the prompt string after the opening line:

```
Today's date is {current_date}.
```

Add a new rule after rule 8:

```
9. **Date resolution**: When the user uses relative date expressions like "this month", \
"Q2", "last quarter", "YTD", "last 3 months", etc., ALWAYS call the `resolve_date_range` \
tool first to get exact DD-MM-YYYY dates before calling any Tally tool. Do NOT try to \
compute dates yourself.
```

**Step 4: Update QueryAgent to pass current_date**

In `backend/agents/query_agent.py`, change the constructor:

```python
class QueryAgent:
    def __init__(self, max_tool_calls: int = 10) -> None:
        self.max_tool_calls = max_tool_calls
        # System prompt is now built per-execution with current date
```

In the `execute` method, build the prompt dynamically:

```python
    async def execute(self, user_query, client, session):
        from backend.utils.date_utils import format_for_tally
        from datetime import date
        current_date = format_for_tally(date.today())
        system_prompt = build_query_agent_prompt(current_date)
        # ... use system_prompt instead of self.system_prompt ...
```

**Step 5: Run all tests**

Run: `pytest tests/unit/ -v`
Expected: All PASS (fix any tests that mock `build_query_agent_prompt()` to pass a date arg)

**Step 6: Commit**

```bash
git add backend/agents/prompts.py backend/agents/query_agent.py tests/unit/test_prompts.py
git commit -m "fix: inject current date into QueryAgent prompt and add resolve_date_range instruction"
```

---

### Task 6: Frontend Multi-Table Rendering + Markdown Table Stripping

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/MessageBubble.tsx`
- Test: `frontend/src/__tests__/MessageBubble.test.tsx`

**Step 1: Write the failing tests**

Add to `frontend/src/__tests__/MessageBubble.test.tsx`:

```typescript
  it("renders multiple DataTables when data is an array", () => {
    const msg: ChatMessage = {
      id: "8", role: "assistant", content: "Comparison data",
      data: [
        { headers: ["Name"], rows: [["Q1 Sales"]] },
        { headers: ["Name"], rows: [["Q2 Sales"]] },
      ] as any,
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Q1 Sales")).toBeInTheDocument();
    expect(screen.getByText("Q2 Sales")).toBeInTheDocument();
  });

  it("strips markdown tables from message text", () => {
    const msg: ChatMessage = {
      id: "9", role: "assistant",
      content: "Here is the data:\n\n| Name | Amount |\n|------|--------|\n| Sales | 100 |\n\nSummary: sales are 100.",
      data: { headers: ["Name", "Amount"], rows: [["Sales", 100]] },
    };
    render(<MessageBubble message={msg} />);
    // The structured DataTable should render
    expect(screen.getByText("Summary: sales are 100.")).toBeInTheDocument();
    // Markdown table should be stripped (not rendered twice)
    const tables = screen.getAllByRole("table");
    expect(tables.length).toBe(1); // only the DataTable, not the markdown table
  });
```

**Step 2: Run to verify they fail**

Run: `cd frontend && npm test -- --run src/__tests__/MessageBubble.test.tsx`
Expected: FAIL — data array not handled, markdown table still rendered

**Step 3: Update types to support data as array**

In `frontend/src/types/index.ts`, update `ChatMessage`:

```typescript
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  isError?: boolean;
  isLoading?: boolean;
}
```

Update `ChatResponse`:

```typescript
export interface ChatResponse {
  message: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  session_id: string;
}
```

**Step 4: Update MessageBubble to handle array data and strip markdown tables**

In `frontend/src/components/MessageBubble.tsx`:

```typescript
import ReactMarkdown from "react-markdown";
import type { ChatMessage, TableData } from "../types";
import DataTable from "./DataTable";
import ChartRenderer from "./ChartRenderer";

function stripMarkdownTables(text: string): string {
  // Remove markdown tables (lines starting with | and separator lines with |---|)
  return text
    .replace(/^\|.*\|$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function isTableData(d: unknown): d is TableData {
  return typeof d === "object" && d !== null && "headers" in d && "rows" in d;
}

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (message.isLoading) {
    return (
      <div className="flex justify-start">
        <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[85%]">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    );
  }

  // Determine tables to render
  const tables: TableData[] = [];
  if (Array.isArray(message.data)) {
    for (const d of message.data) {
      if (isTableData(d)) tables.push(d);
    }
  } else if (isTableData(message.data)) {
    tables.push(message.data);
  }

  // Strip markdown tables from text if we have structured data
  const displayContent = tables.length > 0
    ? stripMarkdownTables(message.content)
    : message.content;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] px-4 py-2.5 ${
          isUser
            ? "bg-blue-600 text-white rounded-2xl rounded-br-sm"
            : message.isError
              ? "bg-red-50 text-red-800 border border-red-200 rounded-2xl rounded-bl-sm"
              : "bg-gray-100 text-gray-900 rounded-2xl rounded-bl-sm"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="text-sm prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0">
            <ReactMarkdown>{displayContent}</ReactMarkdown>
          </div>
        )}

        {tables.map((tableData, idx) => (
          <DataTable key={idx} data={tableData} />
        ))}
        {message.chart && <ChartRenderer chart={message.chart} />}
      </div>
    </div>
  );
}
```

**Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- --run src/__tests__/MessageBubble.test.tsx`
Expected: All PASS

**Step 6: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: All 69+ tests PASS

**Step 7: Commit**

```bash
cd frontend
git add src/types/index.ts src/components/MessageBubble.tsx src/__tests__/MessageBubble.test.tsx
git commit -m "feat: render multiple DataTables and strip markdown tables from message text"
```

---

### Task 7: Add Simple Single-Query Eval Scenarios

**Files:**
- Create: `tests/eval/scenarios/simple_queries.yaml`

**Step 1: Create the eval scenario file**

```yaml
name: "Simple Single Queries"
description: "Basic single-turn queries matching e2e_live test coverage. Each turn is independent."
tags: [simple, single_query, smoke_test]

turns:
  - query: "Show me the trial balance for FY 2025-26"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Returns trial balance data with account names and balances"
        - "Indian rupee formatting used"
        - "Debit and credit columns present"

  - query: "Show profit and loss for April 2025 to March 2026"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Returns income and expense groups with amounts"
        - "Net profit or loss is mentioned"

  - query: "Show the balance sheet as on March 2026"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Assets and liabilities are listed"
        - "Balance sheet totals match (assets = liabilities + capital)"

  - query: "Show outstanding receivables"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Lists party names with outstanding amounts"
        - "Bill numbers and dates shown where available"

  - query: "Show stock summary"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Shows item names with quantities"
        - "Quantities include units (not just currency)"

  - query: "Show sales register for April 2025 to March 2026"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Lists sales vouchers with party names"
        - "Shows amounts for each sale"
```

**Step 2: Verify it loads with the collect framework**

Run: `PYTHONPATH=. python -c "from tests.eval.collect import list_scenarios; print([s['name'] for s in list_scenarios()])"`
Expected: Output includes `"Simple Single Queries"`

**Step 3: Commit**

```bash
git add tests/eval/scenarios/simple_queries.yaml
git commit -m "feat: add simple single-query eval scenarios for smoke testing"
```

---

### Task 8: Add Quick Action Button Eval Scenarios

**Files:**
- Create: `tests/eval/scenarios/quick_actions.yaml`

**Step 1: Create the eval scenario file**

The 6 quick action buttons trigger these queries: "P&L this month", "Outstanding receivables", "Cash balance", "Stock summary", "Top 10 customers", "Sales vs purchases this month".

```yaml
name: "Quick Action Buttons"
description: "Tests the 6 preset quick-action queries available in the UI. Each is a single-turn interaction."
tags: [quick_actions, single_query, ui_buttons]

turns:
  - query: "P&L this month"
    expect:
      has_data: true
      checks:
        - "Returns profit and loss data for the current month"
        - "Date range corresponds to the current calendar month"
        - "Income and expense categories shown"

  - query: "Outstanding receivables"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Lists parties with outstanding receivable amounts"
        - "Shows bill details where available"

  - query: "Cash balance"
    expect:
      has_data: true
      checks:
        - "Shows the cash ledger balance"
        - "Amount is in Indian rupee format"

  - query: "Stock summary"
    expect:
      query_type: simple_lookup
      has_data: true
      checks:
        - "Lists stock items with quantities and values"
        - "Quantities shown with units"

  - query: "Top 10 customers"
    expect:
      query_type: top_n
      has_data: true
      checks:
        - "Lists up to 10 customers ranked by sales amount"
        - "Amounts are sorted in descending order"

  - query: "Sales vs purchases this month"
    expect:
      query_type: comparison
      has_data: true
      checks:
        - "Shows both total sales and total purchases for current month"
        - "Comparison or difference is mentioned"
```

**Step 2: Commit**

```bash
git add tests/eval/scenarios/quick_actions.yaml
git commit -m "feat: add quick action button eval scenarios"
```

---

### Task 9: Add E2E Live Tests for Date Resolution + Quick Actions

**Files:**
- Modify: `tests/e2e_live/test_live_pipeline.py`

**Step 1: Add new live tests**

Add to `tests/e2e_live/test_live_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_quarterly_comparison_q2_vs_q3(orchestrator, tally_client, session):
    """Issue #2: Q2 vs Q3 comparison should use correct quarter dates."""
    query = "Compare sales in Q2 vs Q3 for FY 2025-26"
    result = await run_conversation(orchestrator, tally_client, session, query)
    log_result("quarterly_comparison_q2_vs_q3", query, result)
    assert result["message"]
    # Should mention both quarters with correct months
    msg_lower = result["message"].lower()
    assert any(term in msg_lower for term in ["q2", "jul", "jul-sep", "july"])
    assert any(term in msg_lower for term in ["q3", "oct", "oct-dec", "october"])


@pytest.mark.asyncio
async def test_this_month_date_resolution(orchestrator, tally_client, session):
    """Issue #5: 'this month' should resolve to current calendar month."""
    query = "Show P&L for this month"
    result = await run_conversation(orchestrator, tally_client, session, query)
    log_result("this_month_resolution", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_quick_action_cash_balance(orchestrator, tally_client, session):
    """Issue #4: Quick action 'Cash balance' should work."""
    query = "Cash balance"
    result = await run_conversation(orchestrator, tally_client, session, query)
    log_result("quick_action_cash_balance", query, result)
    assert result["message"]


@pytest.mark.asyncio
async def test_quick_action_top_10_customers(orchestrator, tally_client, session):
    """Issue #4: Quick action 'Top 10 customers' should work."""
    query = "Top 10 customers"
    result = await run_conversation(orchestrator, tally_client, session, query)
    log_result("quick_action_top_10_customers", query, result)
    assert result["message"]
```

Note: these tests depend on the `run_conversation` helper and fixtures already in the file. Read the full file first to match the existing pattern exactly.

**Step 2: Run (only when Tally is available)**

Run: `RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/test_live_pipeline.py -v -s --host <IP> --port 9000 -k "quarterly_comparison or this_month or quick_action"`

**Step 3: Commit**

```bash
git add tests/e2e_live/test_live_pipeline.py
git commit -m "test: add e2e live tests for date resolution and quick action queries"
```

---

### Task 10: Add E2E Mock Test for Multi-Dataset 500 Error Fix

**Files:**
- Modify: `tests/e2e/test_e2e_pipeline.py` (or similar)

**Step 1: Write test that reproduces the 500 error**

```python
@pytest.mark.asyncio
async def test_multi_dataset_response_no_500(client):
    """Issue #1: Multiple tool results should not cause a 500 error."""
    response = await client.post("/api/chat", json={
        "message": "Compare Q1 vs Q2 trial balance",
    })
    # Should not be 500 — the data field should accept list or dict
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
```

This test depends on the mock setup. Match existing patterns in the e2e test file.

**Step 2: Run**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v -k "multi_dataset"`

**Step 3: Commit**

```bash
git add tests/e2e/
git commit -m "test: add e2e mock test for multi-dataset response (no 500 error)"
```

---

### Task 11: Run Full Test Suite and Verify

**Step 1: Run backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/`
Expected: All PASS

**Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All PASS

**Step 3: Verify `python-dateutil` dependency**

Run: `grep dateutil pyproject.toml` — if missing, add to dependencies and run `uv sync`

**Step 4: Final commit if any fixups needed**

---

### Task 12: Final Review and Documentation

**Step 1: Run code review**

Use `superpowers:requesting-code-review` skill.

**Step 2: Update CLAUDE.md if needed**

Add `resolve_date_range` to the tool count (now 13 tools).

**Step 3: Update memory**

Update project memory with new tool and test counts.
