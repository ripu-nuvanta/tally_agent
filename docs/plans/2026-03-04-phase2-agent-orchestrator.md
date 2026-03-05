# Phase 2: Agent Orchestrator & Tools — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the core agent layer that takes natural language queries, classifies them, fetches data from Tally via Claude tool-calling, and returns structured responses.

**Architecture:** Three-module agent pipeline: `tools.py` defines Claude-compatible tool schemas and maps them to `tally_bridge` query functions; `query_agent.py` runs Claude's tool-calling loop to fetch Tally data; `orchestrator.py` uses Claude to classify queries and route them. Session context (`context.py`) tracks conversation history and selected company. Analysis and chart agents are deferred to a follow-up.

**Tech Stack:** `anthropic` Python SDK (async), `pydantic` for models, `unittest.mock.patch` for test mocking.

---

## Prerequisites

Add `anthropic` to project dependencies before starting:

```bash
# In pyproject.toml, add to dependencies:
#   "anthropic>=0.45",
uv add anthropic
uv sync
```

Create the agents directory:

```bash
mkdir -p backend/agents
touch backend/agents/__init__.py
```

---

## Task 1: Tool Definitions (`agents/tools.py`)

**Files:**
- Create: `backend/agents/tools.py`
- Test: `tests/unit/test_tools.py`

### Step 1: Write failing tests for tool schema structure

```python
# tests/unit/test_tools.py
"""Tests for Claude tool definitions and handler mapping."""

from backend.agents.tools import TALLY_TOOLS, TOOL_HANDLERS


class TestToolSchemas:
    """Validate Claude-compatible tool schema structure."""

    def test_all_tools_have_required_fields(self):
        for tool in TALLY_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool['name']} missing 'input_schema'"
            assert tool["input_schema"]["type"] == "object"

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in TALLY_TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_exist(self):
        names = {t["name"] for t in TALLY_TOOLS}
        expected = {
            "get_trial_balance",
            "get_profit_and_loss",
            "get_balance_sheet",
            "get_ledger_transactions",
            "get_day_book",
            "get_outstanding_receivables",
            "get_outstanding_payables",
            "get_stock_summary",
            "get_sales_register",
            "get_purchase_register",
            "search_ledger",
            "list_companies",
        }
        assert expected == names

    def test_date_tools_require_dates(self):
        """Tools that need date ranges must mark them required."""
        date_range_tools = [
            "get_trial_balance", "get_profit_and_loss",
            "get_day_book", "get_sales_register", "get_purchase_register",
            "get_ledger_transactions",
        ]
        for tool in TALLY_TOOLS:
            if tool["name"] in date_range_tools:
                required = tool["input_schema"].get("required", [])
                assert "from_date" in required, f"{tool['name']} missing required from_date"
                assert "to_date" in required, f"{tool['name']} missing required to_date"

    def test_as_on_date_tools(self):
        """Tools that need a single date must require as_on_date."""
        as_on_tools = [
            "get_balance_sheet", "get_outstanding_receivables",
            "get_outstanding_payables", "get_stock_summary",
        ]
        for tool in TALLY_TOOLS:
            if tool["name"] in as_on_tools:
                required = tool["input_schema"].get("required", [])
                assert "as_on_date" in required, f"{tool['name']} missing required as_on_date"


class TestToolHandlers:
    """Validate tool handler mapping."""

    def test_every_tool_has_handler(self):
        tool_names = {t["name"] for t in TALLY_TOOLS}
        handler_names = set(TOOL_HANDLERS.keys())
        assert tool_names == handler_names

    def test_handlers_are_callable(self):
        for name, handler in TOOL_HANDLERS.items():
            assert callable(handler), f"Handler for {name} is not callable"
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/unit/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.agents'`

### Step 3: Write the tool definitions

```python
# backend/agents/tools.py
"""Claude-compatible tool schemas and handler mapping for Tally queries.

Each tool maps to a tally_bridge query function. Tool handlers are async
functions that take a TallyClient + kwargs and return JSON-serializable dicts.
"""

import json
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries import masters, reports, vouchers
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError


# --- Claude Tool Schemas ---

TALLY_TOOLS = [
    {
        "name": "get_trial_balance",
        "description": (
            "Fetch Trial Balance showing debit/credit amounts and closing balances "
            "for all groups and ledgers. Use for questions about overall account balances, "
            "total assets/liabilities, or financial position overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional, uses session default)"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_profit_and_loss",
        "description": (
            "Fetch Profit & Loss statement showing revenue, expenses, gross profit, "
            "and net profit/loss for a date range. Use for profitability questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_balance_sheet",
        "description": (
            "Fetch Balance Sheet showing assets, liabilities, and equity as on a specific date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["as_on_date"],
        },
    },
    {
        "name": "get_ledger_transactions",
        "description": (
            "Fetch all transactions for a specific ledger/account. Use when user asks "
            "about a particular party, customer, vendor, bank account, or expense head."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ledger_name": {"type": "string", "description": "Exact ledger name as in Tally"},
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["ledger_name", "from_date", "to_date"],
        },
    },
    {
        "name": "get_day_book",
        "description": (
            "Fetch all voucher entries for a date range. Optionally filter by voucher type: "
            "Sales, Purchase, Payment, Receipt, Journal, Contra, Credit Note, Debit Note."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "voucher_type": {"type": "string", "description": "Filter by voucher type (optional)"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_outstanding_receivables",
        "description": (
            "Fetch bills receivable — money owed TO the business by customers/debtors. "
            "Shows bill numbers, dates, amounts, and pending amounts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Outstanding as on date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["as_on_date"],
        },
    },
    {
        "name": "get_outstanding_payables",
        "description": (
            "Fetch bills payable — money owed BY the business to vendors/creditors. "
            "Shows bill numbers, dates, amounts, and pending amounts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Outstanding as on date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["as_on_date"],
        },
    },
    {
        "name": "get_stock_summary",
        "description": (
            "Fetch inventory/stock position showing items, quantities, rates, and values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Stock position as on date in DD-MM-YYYY format"},
                "stock_group": {"type": "string", "description": "Filter by stock group (optional)"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["as_on_date"],
        },
    },
    {
        "name": "get_sales_register",
        "description": (
            "Fetch all sales transactions for a date range. "
            "Useful for sales analysis, revenue breakdown, customer-wise sales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "get_purchase_register",
        "description": (
            "Fetch all purchase transactions for a date range. "
            "Useful for expense analysis, vendor-wise purchases."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date in DD-MM-YYYY format"},
                "to_date": {"type": "string", "description": "End date in DD-MM-YYYY format"},
                "company": {"type": "string", "description": "Company name (optional)"},
            },
            "required": ["from_date", "to_date"],
        },
    },
    {
        "name": "search_ledger",
        "description": (
            "Search for a ledger by partial name. Use this FIRST when user mentions a "
            "party/account name and you need the exact Tally ledger name before calling other tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search_term": {"type": "string", "description": "Partial name to search for"},
            },
            "required": ["search_term"],
        },
    },
    {
        "name": "list_companies",
        "description": "List all companies currently loaded in TallyPrime.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# --- Tool Handlers ---
# Each handler is an async function: (client: TallyClient, **tool_input) -> dict
# Handlers normalize return types: Pydantic models → .model_dump(), lists → serialized.

async def _handle_trial_balance(client: TallyClient, **kwargs) -> dict:
    result = await reports.trial_balance(client, **kwargs)
    return result.model_dump(mode="json")


async def _handle_profit_and_loss(client: TallyClient, **kwargs) -> dict:
    result = await reports.profit_and_loss(client, **kwargs)
    return result.model_dump(mode="json")


async def _handle_balance_sheet(client: TallyClient, **kwargs) -> dict:
    result = await reports.balance_sheet(client, **kwargs)
    return result.model_dump(mode="json")


async def _handle_ledger_transactions(client: TallyClient, **kwargs) -> list[dict]:
    return await vouchers.ledger_vouchers(client, **kwargs)


async def _handle_day_book(client: TallyClient, **kwargs) -> list[dict]:
    return await vouchers.day_book(client, **kwargs)


async def _handle_outstanding_receivables(client: TallyClient, **kwargs) -> list[dict]:
    result = await reports.bills_receivable(client, **kwargs)
    return [b.model_dump(mode="json") for b in result]


async def _handle_outstanding_payables(client: TallyClient, **kwargs) -> list[dict]:
    result = await reports.bills_payable(client, **kwargs)
    return [b.model_dump(mode="json") for b in result]


async def _handle_stock_summary(client: TallyClient, **kwargs) -> list[dict]:
    return await reports.stock_summary(client, **kwargs)


async def _handle_sales_register(client: TallyClient, **kwargs) -> list[dict]:
    return await vouchers.sales_register(client, **kwargs)


async def _handle_purchase_register(client: TallyClient, **kwargs) -> list[dict]:
    return await vouchers.purchase_register(client, **kwargs)


async def _handle_search_ledger(client: TallyClient, **kwargs) -> list[dict]:
    result = await masters.search_ledger(client, **kwargs)
    return [l.model_dump(mode="json") for l in result]


async def _handle_list_companies(client: TallyClient, **kwargs) -> list[dict]:
    result = await masters.list_companies(client)
    return [c.model_dump(mode="json") for c in result]


TOOL_HANDLERS = {
    "get_trial_balance": _handle_trial_balance,
    "get_profit_and_loss": _handle_profit_and_loss,
    "get_balance_sheet": _handle_balance_sheet,
    "get_ledger_transactions": _handle_ledger_transactions,
    "get_day_book": _handle_day_book,
    "get_outstanding_receivables": _handle_outstanding_receivables,
    "get_outstanding_payables": _handle_outstanding_payables,
    "get_stock_summary": _handle_stock_summary,
    "get_sales_register": _handle_sales_register,
    "get_purchase_register": _handle_purchase_register,
    "search_ledger": _handle_search_ledger,
    "list_companies": _handle_list_companies,
}


async def execute_tool(client: TallyClient, tool_name: str, tool_input: dict) -> dict:
    """Execute a tool by name, return result dict or error dict.

    This is the single entry point for tool execution. It catches Tally errors
    and returns them as structured error responses that Claude can understand.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        result = await handler(client, **tool_input)
        return {"success": True, "data": result}
    except TallyConnectionError as e:
        return {"error": f"Tally connection failed: {e}"}
    except TallyResponseError as e:
        return {"error": f"Tally returned an error: {e}"}
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/unit/test_tools.py -v`
Expected: All PASS

### Step 5: Commit

```bash
git add backend/agents/__init__.py backend/agents/tools.py tests/unit/test_tools.py
git commit -m "feat(agents): add tool schemas and handler mapping for tally_bridge"
```

---

## Task 2: Session Context (`agents/context.py`)

**Files:**
- Create: `backend/agents/context.py`
- Test: `tests/unit/test_context.py`

### Step 1: Write failing tests

```python
# tests/unit/test_context.py
"""Tests for session context management."""

import time
from unittest.mock import patch
from backend.agents.context import SessionContext, SessionStore


class TestSessionContext:
    def test_create_with_defaults(self):
        ctx = SessionContext()
        assert ctx.session_id is not None
        assert ctx.company is None
        assert ctx.messages == []

    def test_create_with_company(self):
        ctx = SessionContext(company="Test Co")
        assert ctx.company == "Test Co"

    def test_add_user_message(self):
        ctx = SessionContext()
        ctx.add_message("user", "What is my profit?")
        assert len(ctx.messages) == 1
        assert ctx.messages[0] == {"role": "user", "content": "What is my profit?"}

    def test_add_assistant_message(self):
        ctx = SessionContext()
        ctx.add_message("assistant", "Your profit is 1 lakh.")
        assert ctx.messages[0]["role"] == "assistant"

    def test_message_limit_enforced(self):
        ctx = SessionContext(max_messages=4)
        for i in range(6):
            ctx.add_message("user", f"msg {i}")
        # Should keep only the last 4 messages
        assert len(ctx.messages) == 4
        assert ctx.messages[0]["content"] == "msg 2"

    def test_get_messages_returns_copy(self):
        ctx = SessionContext()
        ctx.add_message("user", "hello")
        msgs = ctx.get_messages()
        msgs.append({"role": "user", "content": "injected"})
        assert len(ctx.messages) == 1


class TestSessionStore:
    def test_get_or_create_new(self):
        store = SessionStore()
        ctx = store.get_or_create(session_id=None, company="Test Co")
        assert ctx.company == "Test Co"
        assert ctx.session_id is not None

    def test_get_existing(self):
        store = SessionStore()
        ctx1 = store.get_or_create(session_id=None, company="Co")
        ctx2 = store.get_or_create(session_id=ctx1.session_id)
        assert ctx1.session_id == ctx2.session_id

    def test_ttl_expiry(self):
        store = SessionStore(ttl_minutes=0)
        ctx = store.get_or_create(session_id=None)
        # Manually backdate
        store._sessions[ctx.session_id].created_at = time.time() - 100
        ctx2 = store.get_or_create(session_id=ctx.session_id)
        # Should create new session (old one expired)
        assert ctx2.session_id != ctx.session_id
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/unit/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 3: Write the implementation

```python
# backend/agents/context.py
"""Session and conversation context management.

Each chat session tracks:
- session_id: Unique identifier
- company: Currently selected Tally company
- messages: Conversation history (capped at max_messages)
"""

import time
import uuid


class SessionContext:
    def __init__(
        self,
        session_id: str | None = None,
        company: str | None = None,
        max_messages: int = 20,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.company = company
        self.max_messages = max_messages
        self.messages: list[dict] = []
        self.created_at: float = time.time()

    def add_message(self, role: str, content) -> None:
        """Append a message and trim to max_messages."""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_messages(self) -> list[dict]:
        """Return a copy of the message history."""
        return list(self.messages)


class SessionStore:
    """In-memory session store with TTL expiry."""

    def __init__(self, ttl_minutes: int = 60):
        self._sessions: dict[str, SessionContext] = {}
        self._ttl_seconds = ttl_minutes * 60

    def get_or_create(
        self,
        session_id: str | None = None,
        company: str | None = None,
    ) -> SessionContext:
        if session_id and session_id in self._sessions:
            ctx = self._sessions[session_id]
            if time.time() - ctx.created_at < self._ttl_seconds:
                if company:
                    ctx.company = company
                return ctx
            # Expired — remove
            del self._sessions[session_id]

        ctx = SessionContext(company=company)
        self._sessions[ctx.session_id] = ctx
        return ctx
```

### Step 4: Run tests

Run: `pytest tests/unit/test_context.py -v`
Expected: All PASS

### Step 5: Commit

```bash
git add backend/agents/context.py tests/unit/test_context.py
git commit -m "feat(agents): add session context and in-memory session store"
```

---

## Task 3: System Prompts (`agents/prompts.py`)

**Files:**
- Create: `backend/agents/prompts.py`
- Test: `tests/unit/test_prompts.py`

### Step 1: Write failing tests

```python
# tests/unit/test_prompts.py
"""Tests for agent system prompts."""

from backend.agents.prompts import (
    build_orchestrator_prompt,
    build_query_agent_prompt,
)
from backend.agents.tools import TALLY_TOOLS


class TestOrchestratorPrompt:
    def test_contains_current_date(self):
        prompt = build_orchestrator_prompt(current_date="04-03-2026")
        assert "04-03-2026" in prompt

    def test_contains_query_types(self):
        prompt = build_orchestrator_prompt(current_date="04-03-2026")
        assert "simple_lookup" in prompt
        assert "comparison" in prompt
        assert "greeting" in prompt

    def test_contains_fy_rules(self):
        prompt = build_orchestrator_prompt(current_date="04-03-2026")
        assert "April 1" in prompt
        assert "March 31" in prompt


class TestQueryAgentPrompt:
    def test_contains_tool_names(self):
        prompt = build_query_agent_prompt()
        for tool in TALLY_TOOLS:
            assert tool["name"] in prompt

    def test_contains_date_format_instruction(self):
        prompt = build_query_agent_prompt()
        assert "DD-MM-YYYY" in prompt
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/unit/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 3: Write the implementation

```python
# backend/agents/prompts.py
"""System prompts for each agent in the pipeline."""

from backend.agents.tools import TALLY_TOOLS


def build_orchestrator_prompt(current_date: str) -> str:
    """Build the orchestrator system prompt with current date injected."""
    return f"""You are the routing layer of a TallyPrime accounting assistant.

Given a user message, classify the query and output a JSON response:
{{
    "query_type": "simple_lookup | comparison | trend | top_n | aggregation | greeting | clarification_needed",
    "requires_chart": false,
    "reasoning": "brief explanation",
    "clarification_question": "only if query_type is clarification_needed"
}}

QUERY TYPE DEFINITIONS:
- simple_lookup: Direct data retrieval (balances, lists, single reports)
- comparison: Compare two entities or periods
- trend: Track changes over time (month-over-month, quarter-over-quarter)
- top_n: Rank items (top customers, biggest expenses)
- aggregation: Totals, averages, percentages across data
- greeting: Hello, thanks, non-data conversation
- clarification_needed: Query is too ambiguous to process

DATE RULES:
- Current date: {current_date}
- Indian Financial Year: April 1 to March 31
- "This month" = current calendar month
- "This quarter" = current Indian FY quarter (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
- "This year" or "this FY" = April 1 of current FY to today
- "Last year" = previous full FY (April 1 to March 31)

OUTPUT RULES:
- Respond ONLY with valid JSON, no extra text
- For greetings, set query_type to "greeting"
- If the user mentions a party/customer/vendor name, note it in reasoning
- If ambiguous (e.g., "show me the balance" without specifying which), use clarification_needed"""


def build_query_agent_prompt() -> str:
    """Build the query agent system prompt with available tool names."""
    tool_names = [t["name"] for t in TALLY_TOOLS]
    tool_list = ", ".join(tool_names)
    return f"""You are a TallyPrime data retrieval specialist. You have tools to fetch
data from TallyPrime's accounting system.

Given the user's query, execute the appropriate tool(s) and return the data.
Summarize the data clearly in natural language, using Indian Rupee formatting
(₹12,34,567.00) and the Indian comma system.

IMPORTANT RULES:
- Use search_ledger FIRST if you're unsure of the exact ledger name
- All dates must be in DD-MM-YYYY format for Tally
- If a tool returns an error, report it clearly to the user
- For "list of X" queries, use the appropriate list/collection tool
- You may call multiple tools sequentially if needed
- Present amounts with proper Indian number formatting
- Negative amounts mean debit/outflow, positive means credit/inflow (Tally convention)

Available tools: {tool_list}"""
```

### Step 4: Run tests

Run: `pytest tests/unit/test_prompts.py -v`
Expected: All PASS

### Step 5: Commit

```bash
git add backend/agents/prompts.py tests/unit/test_prompts.py
git commit -m "feat(agents): add system prompts for orchestrator and query agent"
```

---

## Task 4: Query Agent (`agents/query_agent.py`)

**Files:**
- Create: `backend/agents/query_agent.py`
- Test: `tests/unit/test_query_agent.py`

This is the core — runs Claude's tool-calling loop against Tally.

### Step 1: Write failing tests

```python
# tests/unit/test_query_agent.py
"""Tests for the query agent — Claude tool-calling loop."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.query_agent import QueryAgent
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient


def _make_text_response(text: str):
    """Create a mock Claude response with just text (no tool calls)."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg.content = [block]
    return msg


def _make_tool_call_response(tool_name: str, tool_input: dict, tool_use_id: str = "tu_123"):
    """Create a mock Claude response requesting a tool call."""
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = tool_use_id
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = ""
    msg.content = [text_block, tool_block]
    return msg


class TestQueryAgentDirectAnswer:
    """Test when Claude answers directly without tool calls."""

    async def test_direct_text_response(self):
        agent = QueryAgent()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext(company="Test Co")

        mock_response = _make_text_response("Your profit is ₹5,00,000")

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=mock_response)
            result = await agent.execute("What is my profit?", client, session)

        assert result["message"] == "Your profit is ₹5,00,000"
        assert result["tool_results"] == []


class TestQueryAgentToolCalling:
    """Test Claude tool-calling loop."""

    async def test_single_tool_call(self):
        """Claude calls one tool, gets result, then responds."""
        agent = QueryAgent()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext(company="Test Co")

        tool_response = _make_tool_call_response(
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
        )
        final_response = _make_text_response("Here is your trial balance.")

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                side_effect=[tool_response, final_response]
            )
            with patch("backend.agents.query_agent.execute_tool") as mock_exec:
                mock_exec.return_value = {
                    "success": True,
                    "data": {"report_name": "Trial Balance", "rows": []},
                }
                result = await agent.execute("Show trial balance", client, session)

        assert result["message"] == "Here is your trial balance."
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["tool_name"] == "get_trial_balance"

    async def test_multiple_tool_calls(self):
        """Claude calls two tools sequentially."""
        agent = QueryAgent()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        # First: search_ledger, second: get_ledger_transactions, third: final text
        call1 = _make_tool_call_response("search_ledger", {"search_term": "HCODE"}, "tu_1")
        call2 = _make_tool_call_response(
            "get_ledger_transactions",
            {"ledger_name": "HCODE TECHNOLOGIES", "from_date": "01-04-2025", "to_date": "31-03-2026"},
            "tu_2",
        )
        final = _make_text_response("HCODE has 3 transactions totaling ₹10,00,000.")

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(side_effect=[call1, call2, final])
            with patch("backend.agents.query_agent.execute_tool") as mock_exec:
                mock_exec.side_effect = [
                    {"success": True, "data": [{"name": "HCODE TECHNOLOGIES"}]},
                    {"success": True, "data": [{"date": "20250701", "amount": 1000000}]},
                ]
                result = await agent.execute("Show HCODE transactions", client, session)

        assert len(result["tool_results"]) == 2
        assert result["tool_results"][0]["tool_name"] == "search_ledger"
        assert result["tool_results"][1]["tool_name"] == "get_ledger_transactions"

    async def test_tool_error_propagated(self):
        """Tool execution errors are sent back to Claude."""
        agent = QueryAgent()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        tool_call = _make_tool_call_response("get_trial_balance", {"from_date": "01-04-2025", "to_date": "31-03-2026"})
        final = _make_text_response("Sorry, Tally is not reachable.")

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(side_effect=[tool_call, final])
            with patch("backend.agents.query_agent.execute_tool") as mock_exec:
                mock_exec.return_value = {"error": "Tally connection failed"}
                result = await agent.execute("Show TB", client, session)

        assert "not reachable" in result["message"] or "Sorry" in result["message"]

    async def test_max_tool_calls_safety(self):
        """Agent stops after max tool iterations to prevent infinite loops."""
        agent = QueryAgent(max_tool_calls=2)
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        # Claude keeps requesting tools forever
        tool_call = _make_tool_call_response("list_companies", {})

        with patch("backend.agents.query_agent.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=tool_call)
            with patch("backend.agents.query_agent.execute_tool") as mock_exec:
                mock_exec.return_value = {"success": True, "data": []}
                result = await agent.execute("list companies", client, session)

        # Should have stopped after max_tool_calls
        assert len(result["tool_results"]) == 2
        assert "maximum" in result["message"].lower() or result["message"] != ""
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/unit/test_query_agent.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 3: Write the implementation

```python
# backend/agents/query_agent.py
"""Query Agent — runs Claude's tool-calling loop to fetch data from Tally.

Flow:
1. Send user query + system prompt + tools to Claude
2. If Claude requests a tool call, execute it against Tally and feed result back
3. Repeat until Claude returns a text response or max iterations reached
"""

import json
import anthropic

from backend.config import settings
from backend.agents.prompts import build_query_agent_prompt
from backend.agents.tools import TALLY_TOOLS, execute_tool
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


class QueryAgent:
    def __init__(self, max_tool_calls: int = 10):
        self.max_tool_calls = max_tool_calls
        self.system_prompt = build_query_agent_prompt()

    async def execute(
        self,
        user_query: str,
        client: TallyClient,
        session: SessionContext,
    ) -> dict:
        """Run the tool-calling loop and return structured result.

        Returns:
            {
                "message": str,          # Final text from Claude
                "tool_results": [        # All tool calls made
                    {"tool_name": str, "tool_input": dict, "result": dict}
                ]
            }
        """
        messages = session.get_messages()
        messages.append({"role": "user", "content": user_query})

        tool_results = []
        tool_call_count = 0

        while True:
            response = await anthropic_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=self.system_prompt,
                tools=TALLY_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_block = next(b for b in response.content if b.type == "tool_use")
                tool_name = tool_block.name
                tool_input = tool_block.input

                result = await execute_tool(client, tool_name, tool_input)
                tool_results.append({
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "result": result,
                })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": json.dumps(result),
                        }
                    ],
                })

                tool_call_count += 1
                if tool_call_count >= self.max_tool_calls:
                    return {
                        "message": "Reached maximum number of tool calls. Here's what I found so far.",
                        "tool_results": tool_results,
                    }
                continue

            # Extract final text response
            text = next((b.text for b in response.content if b.type == "text"), "")
            return {
                "message": text,
                "tool_results": tool_results,
            }
```

### Step 4: Run tests

Run: `pytest tests/unit/test_query_agent.py -v`
Expected: All PASS

### Step 5: Commit

```bash
git add backend/agents/query_agent.py tests/unit/test_query_agent.py
git commit -m "feat(agents): add query agent with Claude tool-calling loop"
```

---

## Task 5: Orchestrator (`agents/orchestrator.py`)

**Files:**
- Create: `backend/agents/orchestrator.py`
- Test: `tests/unit/test_orchestrator.py`

### Step 1: Write failing tests

```python
# tests/unit/test_orchestrator.py
"""Tests for the orchestrator — query classification and routing."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.orchestrator import Orchestrator
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient


def _make_classification_response(classification: dict):
    """Create a mock Claude response with a JSON classification."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(classification)
    msg.content = [block]
    return msg


class TestOrchestratorClassification:
    async def test_greeting_returns_direct_response(self):
        orch = Orchestrator()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        classification = {
            "query_type": "greeting",
            "requires_chart": False,
            "reasoning": "User said hello",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            result = await orch.process_query("Hello!", client, session)

        assert result["query_type"] == "greeting"
        assert "message" in result

    async def test_clarification_needed(self):
        orch = Orchestrator()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        classification = {
            "query_type": "clarification_needed",
            "requires_chart": False,
            "reasoning": "Ambiguous query",
            "clarification_question": "Which ledger do you want to check?",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            result = await orch.process_query("Show me the balance", client, session)

        assert result["query_type"] == "clarification_needed"
        assert "which ledger" in result["message"].lower()

    async def test_simple_lookup_routes_to_query_agent(self):
        orch = Orchestrator()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "User wants trial balance",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            with patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_qa:
                mock_qa.return_value = {
                    "message": "Here is your trial balance.",
                    "tool_results": [{"tool_name": "get_trial_balance", "tool_input": {}, "result": {}}],
                }
                result = await orch.process_query("Show trial balance", client, session)

        assert result["query_type"] == "simple_lookup"
        assert result["message"] == "Here is your trial balance."
        mock_qa.assert_called_once()

    async def test_session_messages_updated(self):
        """Orchestrator should update session with user query and response."""
        orch = Orchestrator()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        classification = {"query_type": "greeting", "requires_chart": False, "reasoning": "hi"}

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            await orch.process_query("Hi there", client, session)

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    async def test_invalid_json_classification_fallback(self):
        """If Claude returns invalid JSON, treat as simple_lookup."""
        orch = Orchestrator()
        client = TallyClient(host="localhost", port=9999)
        session = SessionContext()

        bad_msg = MagicMock()
        bad_msg.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "I think this is a simple lookup"
        bad_msg.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=bad_msg)
            with patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_qa:
                mock_qa.return_value = {"message": "Fetched data.", "tool_results": []}
                result = await orch.process_query("Show TB", client, session)

        # Should fallback to query agent
        mock_qa.assert_called_once()
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError`

### Step 3: Write the implementation

```python
# backend/agents/orchestrator.py
"""Orchestrator Agent — classifies queries and routes to appropriate agents.

Flow:
1. Send user query to Claude for classification (query type, chart needed)
2. Route based on classification:
   - greeting → direct response
   - clarification_needed → ask clarifying question
   - simple_lookup → query_agent
   - comparison/trend/top_n/aggregation → query_agent (analysis_agent deferred)
"""

import json
import anthropic

from backend.config import settings
from backend.agents.prompts import build_orchestrator_prompt
from backend.agents.query_agent import QueryAgent
from backend.agents.context import SessionContext
from backend.tally_bridge.client import TallyClient
from backend.utils.date_utils import format_for_tally
from datetime import date

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

GREETING_RESPONSES = [
    "Hello! I'm your TallyPrime assistant. Ask me about your accounting data — "
    "balances, sales, outstanding bills, profit & loss, and more.",
]


class Orchestrator:
    def __init__(self):
        self.query_agent = QueryAgent()

    async def process_query(
        self,
        user_message: str,
        client: TallyClient,
        session: SessionContext,
    ) -> dict:
        """Main entry point. Classify and route the query.

        Returns:
            {
                "query_type": str,
                "message": str,
                "data": dict | None,
                "chart": dict | None,
                "session_id": str,
            }
        """
        # Step 1: Classify
        classification = await self._classify(user_message)

        # Step 2: Route
        if classification["query_type"] == "greeting":
            response_msg = GREETING_RESPONSES[0]
            session.add_message("user", user_message)
            session.add_message("assistant", response_msg)
            return {
                "query_type": "greeting",
                "message": response_msg,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
            }

        if classification["query_type"] == "clarification_needed":
            clarification = classification.get(
                "clarification_question",
                "Could you please be more specific about what data you need?",
            )
            session.add_message("user", user_message)
            session.add_message("assistant", clarification)
            return {
                "query_type": "clarification_needed",
                "message": clarification,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
            }

        # All other types → query agent (analysis/chart agents deferred)
        query_result = await self.query_agent.execute(user_message, client, session)

        session.add_message("user", user_message)
        session.add_message("assistant", query_result["message"])

        return {
            "query_type": classification["query_type"],
            "message": query_result["message"],
            "data": self._extract_last_data(query_result["tool_results"]),
            "chart": None,  # Chart agent deferred
            "session_id": session.session_id,
        }

    async def _classify(self, user_message: str) -> dict:
        """Use Claude to classify the query type."""
        current_date = format_for_tally(date.today())
        prompt = build_orchestrator_prompt(current_date)

        response = await anthropic_client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = next((b.text for b in response.content if b.type == "text"), "")

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Fallback: treat as simple_lookup
            return {
                "query_type": "simple_lookup",
                "requires_chart": False,
                "reasoning": "Classification failed, defaulting to simple_lookup",
            }

    @staticmethod
    def _extract_last_data(tool_results: list[dict]) -> dict | None:
        """Extract data from the last successful tool result."""
        for tr in reversed(tool_results):
            result = tr.get("result", {})
            if result.get("success") and result.get("data"):
                return result["data"]
        return None
```

### Step 4: Run tests

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: All PASS

### Step 5: Commit

```bash
git add backend/agents/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "feat(agents): add orchestrator with Claude-based query classification"
```

---

## Task 6: Integration Test — Tool Handlers Against Mock Tally

**Files:**
- Create: `tests/integration/test_tool_execution.py`

### Step 1: Write integration tests

```python
# tests/integration/test_tool_execution.py
"""Integration tests — tool handlers execute against mock Tally server."""

import pytest
from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient
from backend.agents.tools import execute_tool


@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient(host="localhost", port=server.port)
    return client


class TestToolExecution:
    async def test_get_trial_balance(self, mock_tally):
        result = await execute_tool(
            mock_tally,
            "get_trial_balance",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
        )
        assert result["success"] is True
        assert result["data"]["report_name"] == "Trial Balance"
        assert len(result["data"]["rows"]) > 0

    async def test_list_companies(self, mock_tally):
        result = await execute_tool(mock_tally, "list_companies", {})
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) > 0

    async def test_search_ledger(self, mock_tally):
        result = await execute_tool(
            mock_tally,
            "search_ledger",
            {"search_term": "Cash"},
        )
        assert result["success"] is True
        assert isinstance(result["data"], list)

    async def test_get_sales_register(self, mock_tally):
        result = await execute_tool(
            mock_tally,
            "get_sales_register",
            {"from_date": "01-04-2025", "to_date": "31-03-2026"},
        )
        assert result["success"] is True
        assert isinstance(result["data"], list)

    async def test_get_outstanding_receivables(self, mock_tally):
        result = await execute_tool(
            mock_tally,
            "get_outstanding_receivables",
            {"as_on_date": "31-03-2026"},
        )
        assert result["success"] is True
        assert isinstance(result["data"], list)

    async def test_unknown_tool_returns_error(self, mock_tally):
        result = await execute_tool(mock_tally, "nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    async def test_connection_error_returns_error(self):
        bad_client = TallyClient(host="localhost", port=19999)
        result = await execute_tool(
            bad_client,
            "list_companies",
            {},
        )
        assert "error" in result
        assert "connection" in result["error"].lower()
```

### Step 2: Run tests

Run: `pytest tests/integration/test_tool_execution.py -v`
Expected: All PASS

### Step 3: Commit

```bash
git add tests/integration/test_tool_execution.py
git commit -m "test: add integration tests for tool execution against mock Tally"
```

---

## Task 7: Add `anthropic` Dependency and Final Verification

**Files:**
- Modify: `pyproject.toml`

### Step 1: Add anthropic dependency

```bash
uv add anthropic
```

### Step 2: Run all tests

```bash
pytest tests/unit/ tests/integration/ -v --tb=short
```

Expected: All existing Phase 1 tests + new Phase 2 tests pass.

### Step 3: Run coverage check

```bash
pytest --cov=backend --cov-report=term-missing tests/unit/ tests/integration/
```

### Step 4: Commit

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add anthropic SDK dependency"
```

---

## Summary

| Task | Module | What it does |
|------|--------|-------------|
| 1 | `agents/tools.py` | Tool schemas + handlers mapping to tally_bridge |
| 2 | `agents/context.py` | Session context with TTL and message capping |
| 3 | `agents/prompts.py` | System prompts for orchestrator + query agent |
| 4 | `agents/query_agent.py` | Claude tool-calling loop |
| 5 | `agents/orchestrator.py` | Query classification + routing |
| 6 | Integration tests | Tool handlers against mock Tally server |
| 7 | Dependencies | Add anthropic SDK |
| 8 | Live validation | Test agent pipeline against real Tally |

---

## Task 8: Live Tally Validation

**Prerequisites:** Tally running at configured host:port with a company loaded, valid `ANTHROPIC_API_KEY` in `.env`.

**Files:**
- Create: `scripts/test_agent_live.py`

### Step 1: Write the live test script

```python
# scripts/test_agent_live.py
"""Live validation of the agent pipeline against a real Tally instance.

Usage:
    PYTHONPATH=. uv run python scripts/test_agent_live.py --host <TALLY_IP> --port 9000

Requires: ANTHROPIC_API_KEY set in .env or environment.
"""

import asyncio
import argparse
import json

from backend.tally_bridge.client import TallyClient
from backend.agents.orchestrator import Orchestrator
from backend.agents.context import SessionContext, SessionStore


LIVE_TEST_QUERIES = [
    # Greetings
    ("Hello!", "greeting"),
    # Simple lookups
    ("List all companies", "simple_lookup"),
    ("Show me the trial balance for this financial year", "simple_lookup"),
    ("What is the profit and loss for April 2025 to March 2026?", "simple_lookup"),
    ("Show balance sheet as of today", "simple_lookup"),
    ("Show outstanding receivables", "simple_lookup"),
    ("Show sales register for this month", "simple_lookup"),
    # Clarification
    ("Show me the balance", "clarification_needed"),
]


async def run_live_tests(host: str, port: int):
    client = TallyClient(host=host, port=port)

    # Verify Tally is reachable
    healthy = await client.health_check()
    if not healthy:
        print(f"FAIL: Cannot reach Tally at {host}:{port}")
        return

    print(f"OK: Tally reachable at {host}:{port}\n")

    orchestrator = Orchestrator()
    store = SessionStore()
    session = store.get_or_create()

    passed = 0
    failed = 0

    for query, expected_type in LIVE_TEST_QUERIES:
        try:
            result = await orchestrator.process_query(query, client, session)
            actual_type = result["query_type"]
            status = "PASS" if actual_type == expected_type else "WARN"
            if status == "WARN":
                print(f"  WARN: Expected {expected_type}, got {actual_type}")
            else:
                passed += 1
            print(f"  {status}: [{actual_type}] {query}")
            print(f"         → {result['message'][:120]}...")
            if result.get("data"):
                data = result["data"]
                if isinstance(data, list):
                    print(f"         → {len(data)} items returned")
                elif isinstance(data, dict) and "rows" in data:
                    print(f"         → {len(data['rows'])} rows returned")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {query}")
            print(f"         → {type(e).__name__}: {e}")
        print()

    print(f"\nResults: {passed} passed, {failed} failed, {len(LIVE_TEST_QUERIES) - passed - failed} warnings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live agent pipeline test")
    parser.add_argument("--host", default="172.26.104.48")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    asyncio.run(run_live_tests(args.host, args.port))
```

### Step 2: Run against live Tally

```bash
PYTHONPATH=. uv run python scripts/test_agent_live.py --host 172.26.104.48 --port 9000
```

Expected: All queries return reasonable responses. Greetings classified as greeting, data queries fetch real data.

### Step 3: Commit

```bash
git add scripts/test_agent_live.py
git commit -m "test: add live Tally validation script for agent pipeline"
```

---

## Deferred Follow-up (Phase 2b)

The following are **not in this plan** and should be built as a separate plan after Phase 2 core is complete and validated:

### Analysis Agent (`agents/analysis_agent.py`)
- Takes raw data from query agent + classification from orchestrator
- Performs: period-vs-period comparisons, month-over-month trends, top-N rankings, aggregations (totals, averages, percentages), ratio calculations (gross margin, current ratio)
- Output: `{ summary, data: {headers, rows}, insights, chart_suggestion }`
- Orchestrator routes `comparison`, `trend`, `top_n`, `aggregation` query types to this agent after query agent fetches data
- Uses Claude to generate analysis from structured data

### Chart Agent (`agents/chart_agent.py`)
- Takes analyzed data + orchestrator classification
- Selects chart type: bar, line, pie, stacked_bar, grouped_bar, table_only
- Outputs Recharts-compatible spec: `{ chart_type, title, data: [{label, value, category}], config }`
- Rules: comparison → grouped_bar, trend 4+ points → line, composition → pie (max 7 slices), ranking → horizontal bar, < 3 points → table_only
- Orchestrator calls chart agent when `requires_chart` is true

### Phase 3: FastAPI Backend
- Wire orchestrator into FastAPI endpoints: `POST /api/chat`, `GET /api/health`, `GET /api/companies`, `GET /api/reports/{name}`
- Request/response Pydantic models for the chat endpoint
- CORS middleware, session management via SessionStore
