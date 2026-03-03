# TALLYPRIME AI AGENT — Implementation Plan for Claude Code

> **Project**: TallyPrime Chatbot Agent
> **Stack**: Python (FastAPI) + React + Claude API
> **Target**: Web app (primary), WhatsApp (future)
> **Tally Version**: TallyPrime 7.0+ (native JSON support)

---

## TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [Multi-Agent Architecture](#3-multi-agent-architecture)
4. [Implementation Phases](#4-implementation-phases)
5. [Phase 1: Tally Bridge Layer](#5-phase-1-tally-bridge-layer)
6. [Phase 2: Agent Orchestrator & Tools](#6-phase-2-agent-orchestrator--tools)
7. [Phase 3: FastAPI Backend](#7-phase-3-fastapi-backend)
8. [Phase 4: React Frontend](#8-phase-4-react-frontend)
9. [Phase 5: Advanced Features](#9-phase-5-advanced-features)
10. [Testing Strategy](#10-testing-strategy)
11. [Configuration & Environment](#11-configuration--environment)
12. [Key Technical Decisions](#12-key-technical-decisions)
13. [Seed Data Script](#13-seed-data-script)

---

## 1. PROJECT OVERVIEW

### What We're Building

An AI-powered chatbot that connects to a live TallyPrime instance over LAN/localhost, lets users ask natural language questions about their accounting data, and returns answers with optional charts and tables.

### How TallyPrime Integration Works

- TallyPrime runs on a Windows machine as an HTTP server on a configurable port (default 9000).
- It accepts XML or JSON (7.0+) requests via HTTP POST.
- It responds with the requested data (reports, masters, vouchers) in XML or JSON.
- The agent runs on a separate machine on the same LAN, communicating over `http://<tally-ip>:9000`.
- TallyPrime must be running with a company loaded for requests to work.

### Network Topology

```
ACCOUNTANT MACHINE (Windows)          AGENT SERVER (any OS)
┌────────────────────────┐            ┌─────────────────────────┐
│  TallyPrime 7.0+       │            │  FastAPI Backend         │
│  Company: loaded        │◄──LAN────►│  React Frontend          │
│  Port: 9000 (HTTP)      │  WiFi/    │  Claude API integration  │
│  Firewall: port open    │  Ethernet │                          │
└────────────────────────┘            └─────────────────────────┘
                                              ▲
                                              │ Browser
                                        ┌─────┴──────┐
                                        │ Users on    │
                                        │ LAN / VPN   │
                                        └────────────┘
```

---

## 2. REPOSITORY STRUCTURE

```
tallyprime-agent/
├── README.md
├── pyproject.toml                    # Python project config (use uv or poetry)
├── .env.example                      # Environment variables template
├── docker-compose.yml                # Optional: containerized deployment
│
├── backend/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app entry point
│   ├── config.py                     # Settings (Tally host, port, API keys)
│   │
│   ├── tally_bridge/                 # Layer 1: Tally HTTP Communication
│   │   ├── __init__.py
│   │   ├── client.py                 # Core async HTTP client for Tally
│   │   ├── request_builder.py        # Build XML/JSON request payloads
│   │   ├── response_parser.py        # Parse XML/JSON responses into dicts
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── masters.py            # Ledgers, Groups, Stock Items, UOMs
│   │   │   ├── reports.py            # Trial Balance, P&L, Balance Sheet, etc.
│   │   │   ├── vouchers.py           # Day Book, Sales/Purchase Register
│   │   │   └── custom_tdl.py         # Custom TDL-based queries
│   │   ├── models.py                 # Pydantic models for Tally data
│   │   └── exceptions.py             # TallyConnectionError, TallyResponseError, etc.
│   │
│   ├── agents/                       # Layer 2: Multi-Agent System
│   │   ├── __init__.py
│   │   ├── orchestrator.py           # Main orchestrator agent (router)
│   │   ├── query_agent.py            # Handles data retrieval queries
│   │   ├── analysis_agent.py         # Handles comparisons, trends, top-N
│   │   ├── chart_agent.py            # Decides chart type & formats chart data
│   │   ├── tools.py                  # Tool definitions for Claude function-calling
│   │   ├── prompts.py                # System prompts for each agent
│   │   └── context.py                # Session/conversation context manager
│   │
│   ├── api/                          # Layer 3: FastAPI Routes
│   │   ├── __init__.py
│   │   ├── chat.py                   # POST /api/chat — main chat endpoint
│   │   ├── health.py                 # GET /api/health — Tally connectivity check
│   │   ├── companies.py              # GET /api/companies — list loaded companies
│   │   └── reports.py                # GET /api/reports/{name} — direct report access
│   │
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py             # Indian FY awareness, date parsing
│       ├── currency_format.py        # ₹ formatting with Indian comma system
│       └── logger.py                 # Structured logging
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx                   # Main app with routing
│       ├── main.jsx                  # Entry point
│       ├── components/
│       │   ├── ChatWindow.jsx        # Chat container with message list
│       │   ├── MessageBubble.jsx     # Single message (text, table, chart)
│       │   ├── ChatInput.jsx         # Input box with send button
│       │   ├── ChartRenderer.jsx     # Renders charts (Recharts)
│       │   ├── DataTable.jsx         # Sortable data table
│       │   ├── CompanySelector.jsx   # Dropdown to switch companies
│       │   ├── QuickActions.jsx      # Preset query buttons
│       │   ├── LoadingIndicator.jsx  # Typing/thinking animation
│       │   └── ErrorBoundary.jsx     # Error handling wrapper
│       ├── hooks/
│       │   ├── useChat.js            # Chat state & API communication
│       │   └── useCompanies.js       # Company list fetching
│       ├── utils/
│       │   └── formatters.js         # Currency, date formatting
│       └── styles/
│           └── globals.css           # Tailwind + custom styles
│
├── tests/
│   ├── conftest.py                   # Shared fixtures (mock Tally server, etc.)
│   ├── fixtures/                     # Sample Tally XML/JSON responses
│   │   ├── trial_balance.xml
│   │   ├── trial_balance.json
│   │   ├── ledger_list.xml
│   │   ├── profit_and_loss.json
│   │   ├── day_book.json
│   │   ├── sales_register.json
│   │   ├── bills_receivable.json
│   │   └── error_responses.xml
│   ├── unit/
│   │   ├── test_request_builder.py   # XML/JSON payload construction
│   │   ├── test_response_parser.py   # Response parsing logic
│   │   ├── test_date_utils.py        # Date inference & FY logic
│   │   ├── test_currency_format.py   # Indian number formatting
│   │   └── test_models.py            # Pydantic model validation
│   ├── integration/
│   │   ├── test_tally_client.py      # Tests against mock Tally HTTP server
│   │   ├── test_chat_endpoint.py     # Full chat flow with mocked Tally
│   │   └── test_tool_execution.py    # Tool call → Tally request → response
│   ├── e2e/
│   │   ├── test_live_tally.py        # Tests against real Tally (optional, manual)
│   │   └── test_agent_scenarios.py   # End-to-end NL query → response tests
│   └── mocks/
│       ├── mock_tally_server.py      # Fake Tally HTTP server for testing
│       └── mock_claude_api.py        # Mock Claude responses with tool calls
│
└── scripts/
    ├── seed_tally_data.py            # Script to create sample data in Tally
    └── test_tally_connection.py      # Quick connectivity test script
```

---

## 3. MULTI-AGENT ARCHITECTURE

### Why Multi-Agent?

A single monolithic prompt handling everything (query classification, tool selection, data analysis, chart formatting) leads to poor results on complex queries. Instead, we split responsibilities across specialized agents.

### Agent Roles

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT                  │
│                                                  │
│  Role: Classify the query, route to the right    │
│  agent, combine results, return final response   │
│                                                  │
│  Decides:                                        │
│  - Is this a simple data lookup?    → Query Agent│
│  - Is this a comparison/trend?      → Analysis   │
│  - Does user want a chart?          → Chart      │
│  - Is this a greeting/non-data?     → Direct     │
│  - Is this ambiguous?               → Clarify    │
└───────┬───────────┬──────────────┬──────────────┘
        │           │              │
        ▼           ▼              ▼
┌──────────┐ ┌─────────────┐ ┌──────────┐
│  QUERY   │ │  ANALYSIS   │ │  CHART   │
│  AGENT   │ │  AGENT      │ │  AGENT   │
│          │ │             │ │          │
│ Calls    │ │ Multi-tool  │ │ Takes    │
│ single   │ │ calls,      │ │ data,    │
│ Tally    │ │ aggregates, │ │ picks    │
│ tool,    │ │ compares,   │ │ chart    │
│ returns  │ │ ranks       │ │ type,    │
│ data     │ │             │ │ formats  │
└──────────┘ └─────────────┘ └──────────┘
```

### Agent Definitions

#### 3.1 Orchestrator Agent

```python
# agents/orchestrator.py

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the routing layer of a TallyPrime accounting assistant.

Given a user message, decide:
1. QUERY_TYPE: one of [simple_lookup, comparison, trend, top_n, aggregation, greeting, clarification_needed]
2. AGENTS_NEEDED: which agents to invoke (query, analysis, chart)
3. REQUIRES_CHART: boolean — does the user want or would benefit from a visual?

Output your decision as JSON:
{
    "query_type": "...",
    "agents": ["query"],
    "requires_chart": false,
    "reasoning": "brief explanation",
    "inferred_params": {
        "date_range": {"from": "...", "to": "..."},
        "entities": ["ledger names", "report types"],
        "filters": {}
    }
}

RULES:
- Current date: {current_date}
- Indian Financial Year: April 1 to March 31
- "This month" = current calendar month
- "This quarter" = current quarter of the Indian FY (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
- "This year" or "this FY" = April 1 of current FY to today
- "Last year" = previous full FY (April 1 to March 31)
- If the user says a party/customer/vendor name, note it in entities
- If ambiguous (e.g., "show me the balance"), ask for clarification
"""
```

#### 3.2 Query Agent

```python
# agents/query_agent.py

QUERY_AGENT_SYSTEM_PROMPT = """
You are a TallyPrime data retrieval specialist. You have tools to fetch
data from TallyPrime's API.

Given the orchestrator's plan, execute the appropriate tool(s) and return
the raw data. Do NOT analyze or summarize — just fetch and return.

IMPORTANT:
- Use search_ledger first if you're unsure of the exact ledger name
- Dates must be in DD-MM-YYYY format for Tally
- If a tool returns an error, report it clearly
- For "List of X" queries, use the appropriate collection endpoint
- You may call multiple tools sequentially if needed

Available tools: {tool_list}
"""
```

#### 3.3 Analysis Agent

```python
# agents/analysis_agent.py

ANALYSIS_AGENT_SYSTEM_PROMPT = """
You are a financial analysis specialist for Indian businesses using TallyPrime.

Given raw data from the Query Agent, perform the requested analysis:
- Comparisons: period vs period, entity vs entity
- Trends: month-over-month, quarter-over-quarter
- Rankings: top N customers/vendors/items by amount
- Aggregations: totals, averages, percentages
- Ratios: gross margin, current ratio, etc.

OUTPUT FORMAT:
{
    "summary": "Natural language summary in 2-3 sentences",
    "data": {
        "headers": ["Column1", "Column2", ...],
        "rows": [[val1, val2, ...], ...]
    },
    "insights": ["Key insight 1", "Key insight 2"],
    "chart_suggestion": "bar|line|pie|none"
}

RULES:
- All amounts in ₹ with Indian comma format (12,34,567.00)
- Negative amounts = outflow/debit; Positive = inflow/credit (Tally convention)
- Round percentages to 1 decimal place
- For comparisons, always show absolute change AND percentage change
"""
```

#### 3.4 Chart Agent

```python
# agents/chart_agent.py

CHART_AGENT_SYSTEM_PROMPT = """
You format data for chart rendering. Given analysis results, produce
a chart specification.

OUTPUT FORMAT:
{
    "chart_type": "bar|line|pie|stacked_bar|grouped_bar|table_only",
    "title": "Chart title",
    "data": [
        {"label": "...", "value": 123, "category": "..."},
        ...
    ],
    "config": {
        "x_axis_label": "...",
        "y_axis_label": "...",
        "currency_format": true,
        "show_legend": true,
        "colors": ["#4F46E5", "#10B981", "#F59E0B", "#EF4444"]
    }
}

CHART TYPE SELECTION RULES:
- Comparison of 2-3 periods → grouped_bar
- Trend over time (4+ points) → line
- Composition/share (parts of whole) → pie (max 7 slices)
- Ranking (top N) → horizontal bar
- Simple data display → table_only
- If < 3 data points, prefer table_only over chart
"""
```

### Agent Orchestration Flow (Code)

```python
# agents/orchestrator.py — main execution flow

async def process_query(user_message: str, session: SessionContext) -> AgentResponse:
    """
    Main entry point. Routes user query through the agent pipeline.
    """
    # Step 1: Orchestrator classifies and plans
    plan = await classify_query(user_message, session)

    if plan.query_type == "greeting":
        return AgentResponse(message=generate_greeting())

    if plan.query_type == "clarification_needed":
        return AgentResponse(message=plan.clarification_question)

    # Step 2: Query Agent fetches data from Tally
    raw_data = await query_agent.execute(plan, session)

    if raw_data.error:
        return AgentResponse(message=format_error(raw_data.error))

    # Step 3: Analysis Agent processes data (if needed)
    if plan.query_type in ("comparison", "trend", "top_n", "aggregation"):
        analyzed = await analysis_agent.execute(raw_data, plan)
    else:
        analyzed = raw_data

    # Step 4: Chart Agent formats visualization (if needed)
    chart = None
    if plan.requires_chart:
        chart = await chart_agent.execute(analyzed, plan)

    # Step 5: Generate final natural language response
    response_text = await generate_response(analyzed, plan, session)

    return AgentResponse(
        message=response_text,
        data=analyzed.data if analyzed.has_table else None,
        chart=chart
    )
```

---

## 4. IMPLEMENTATION PHASES

Build in this exact order. Each phase must be complete and tested before moving to the next.

### Phase 1: Tally Bridge Layer (Days 1-3)
### Phase 2: Agent Orchestrator & Tools (Days 4-6)
### Phase 3: FastAPI Backend (Days 7-8)
### Phase 4: React Frontend (Days 9-11)
### Phase 5: Advanced Features (Days 12-14)

---

## 5. PHASE 1: TALLY BRIDGE LAYER

This is the foundation. Everything depends on reliable communication with Tally.

### 5.1 Core Client (`tally_bridge/client.py`)

```python
"""
Core async HTTP client for TallyPrime communication.

TallyPrime runs as an HTTP server. We POST XML/JSON requests and parse responses.
For TallyPrime 7.0+, prefer JSON where supported. Fall back to XML for custom TDL queries.

CONNECTION: http://<TALLY_HOST>:<TALLY_PORT> (default: localhost:9000)
"""

import httpx
from backend.config import settings
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError

class TallyClient:
    def __init__(self):
        self.base_url = f"http://{settings.TALLY_HOST}:{settings.TALLY_PORT}"
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def post_xml(self, xml_payload: str) -> str:
        """Send XML request to Tally, return raw XML response string."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    content=xml_payload,
                    headers={"Content-Type": "text/xml; charset=utf-8"}
                )
                response.raise_for_status()
                return response.text
        except httpx.ConnectError:
            raise TallyConnectionError(
                f"Cannot connect to TallyPrime at {self.base_url}. "
                "Ensure Tally is running with a company loaded and port is configured."
            )
        except httpx.TimeoutException:
            raise TallyConnectionError(
                f"TallyPrime at {self.base_url} timed out. "
                "The request may be too heavy or Tally is busy."
            )

    async def post_json(self, json_payload: dict, headers: dict) -> dict:
        """Send JSON request to Tally 7.0+, return parsed JSON response."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    json=json_payload,
                    headers={**headers, "Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise TallyConnectionError(...)
        except Exception as e:
            raise TallyResponseError(f"Failed to parse Tally response: {e}")

    async def health_check(self) -> bool:
        """Check if Tally is reachable and has a company loaded."""
        try:
            result = await self.post_xml(REQUEST_TEMPLATES["list_companies"])
            return "<COMPANY>" in result or "COMPANY" in result
        except TallyConnectionError:
            return False
```

### 5.2 Request Builder (`tally_bridge/request_builder.py`)

Build XML request payloads for each Tally operation. Key requests to implement:

```
EXPORT REQUESTS (read data):
├── list_companies          — Get all companies loaded in Tally
├── list_ledgers            — Get all ledger names + parent groups
├── list_groups             — Get all account groups
├── list_stock_items        — Get all stock items
├── list_voucher_types      — Get all voucher types
├── trial_balance           — Trial Balance for date range
├── profit_and_loss         — P&L for date range
├── balance_sheet           — Balance Sheet as on date
├── day_book                — All transactions for date range
├── ledger_vouchers         — Transactions for a specific ledger
├── sales_register          — Sales vouchers for date range
├── purchase_register       — Purchase vouchers for date range
├── bills_receivable        — Outstanding receivables
├── bills_payable           — Outstanding payables
├── stock_summary           — Inventory position
└── cash_flow               — Cash/bank transactions
```

For each request, implement a function that takes parameters (dates, ledger names, filters) and returns a properly formatted XML string.

**Example — Trial Balance XML:**
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Trial Balance</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
        <SVCurrentCompany>{company}</SVCurrentCompany>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

**Example — List of Ledgers with balance:**
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CustomLedgerList</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="CustomLedgerList" ISMODIFY="No">
            <TYPE>Ledger</TYPE>
            <NATIVEMETHOD>Name</NATIVEMETHOD>
            <NATIVEMETHOD>Parent</NATIVEMETHOD>
            <NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>
            <NATIVEMETHOD>OpeningBalance</NATIVEMETHOD>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

### 5.3 Response Parser (`tally_bridge/response_parser.py`)

Tally returns XML (or JSON on 7.0+) in varying structures depending on the report.
Parse into normalized Python dicts. Use `xml.etree.ElementTree` for XML parsing.

Key challenges:
- Tally XML uses inconsistent casing (DSPDISPNAME, DSPCLCRAMT, etc.)
- Amounts may have negative signs, commas, or be empty strings
- Some collections nest deeply (voucher → ledger entries → inventory entries → batch)
- Error responses have a different structure than success responses

Build a base parser and report-specific parsers that normalize into consistent structures.

### 5.4 Pydantic Models (`tally_bridge/models.py`)

```python
from pydantic import BaseModel
from datetime import date

class Ledger(BaseModel):
    name: str
    parent_group: str
    closing_balance: float = 0.0
    opening_balance: float = 0.0

class VoucherEntry(BaseModel):
    date: date
    voucher_type: str
    voucher_number: str
    party_name: str | None = None
    ledger_name: str
    amount: float
    narration: str | None = None

class TrialBalanceRow(BaseModel):
    account_name: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    closing_balance: float = 0.0

class ReportResponse(BaseModel):
    report_name: str
    company: str
    from_date: date | None = None
    to_date: date | None = None
    rows: list[dict]
    raw_response: dict | None = None  # for debugging

class OutstandingBill(BaseModel):
    party_name: str
    bill_number: str
    bill_date: date
    due_date: date | None = None
    amount: float
    pending_amount: float
```

---

## 6. PHASE 2: AGENT ORCHESTRATOR & TOOLS

### 6.1 Tool Definitions (`agents/tools.py`)

Define Claude-compatible tool schemas. Each tool maps to a `tally_bridge` function.

```python
TALLY_TOOLS = [
    {
        "name": "get_trial_balance",
        "description": "Fetch Trial Balance showing opening, transaction, and closing balances for all groups and ledgers. Use for questions about overall account balances, total assets/liabilities, or financial position overview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"},
                "company": {"type": "string", "description": "Company name. Optional."}
            },
            "required": ["from_date", "to_date"]
        }
    },
    {
        "name": "get_profit_and_loss",
        "description": "Fetch Profit & Loss statement showing revenue, expenses, gross profit, and net profit/loss. Use for profitability questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"},
                "detailed": {"type": "boolean", "description": "Show sub-group breakdown. Default false."}
            },
            "required": ["from_date", "to_date"]
        }
    },
    {
        "name": "get_balance_sheet",
        "description": "Fetch Balance Sheet showing assets, liabilities, and equity as on a date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Date DD-MM-YYYY"}
            },
            "required": ["as_on_date"]
        }
    },
    {
        "name": "get_ledger_transactions",
        "description": "Fetch all transactions for a specific ledger/account. Use when user asks about a particular party, bank account, expense head, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ledger_name": {"type": "string", "description": "Exact ledger name as in Tally"},
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"}
            },
            "required": ["ledger_name", "from_date", "to_date"]
        }
    },
    {
        "name": "get_day_book",
        "description": "Fetch all voucher entries for a date range. Optionally filter by voucher type (Sales, Purchase, Payment, Receipt, Journal, Contra, Credit Note, Debit Note).",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"},
                "voucher_type": {"type": "string", "description": "Optional: filter by type"}
            },
            "required": ["from_date", "to_date"]
        }
    },
    {
        "name": "get_outstanding_receivables",
        "description": "Fetch bills receivable — money owed TO the business by customers/debtors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Outstanding as on date DD-MM-YYYY"}
            },
            "required": ["as_on_date"]
        }
    },
    {
        "name": "get_outstanding_payables",
        "description": "Fetch bills payable — money owed BY the business to vendors/creditors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Outstanding as on date DD-MM-YYYY"}
            },
            "required": ["as_on_date"]
        }
    },
    {
        "name": "get_stock_summary",
        "description": "Fetch inventory/stock position showing items, quantities, rates, and values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "as_on_date": {"type": "string", "description": "Stock position as on date DD-MM-YYYY"},
                "stock_group": {"type": "string", "description": "Optional: filter by stock group"}
            },
            "required": ["as_on_date"]
        }
    },
    {
        "name": "get_sales_register",
        "description": "Fetch all sales transactions. Useful for sales analysis, revenue breakdown, customer-wise sales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"}
            },
            "required": ["from_date", "to_date"]
        }
    },
    {
        "name": "get_purchase_register",
        "description": "Fetch all purchase transactions. Useful for expense analysis, vendor-wise purchases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date DD-MM-YYYY"},
                "to_date": {"type": "string", "description": "End date DD-MM-YYYY"}
            },
            "required": ["from_date", "to_date"]
        }
    },
    {
        "name": "search_ledger",
        "description": "Search for a ledger by partial name. Use this FIRST when user mentions a party/account name and you need the exact Tally ledger name before calling other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "search_term": {"type": "string", "description": "Partial name to search"}
            },
            "required": ["search_term"]
        }
    },
    {
        "name": "list_companies",
        "description": "List all companies currently loaded in TallyPrime.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]
```

### 6.2 Tool Executor

Map each tool name to its `tally_bridge` function:

```python
# agents/tools.py

TOOL_HANDLERS = {
    "get_trial_balance":          tally_bridge.queries.reports.trial_balance,
    "get_profit_and_loss":        tally_bridge.queries.reports.profit_and_loss,
    "get_balance_sheet":          tally_bridge.queries.reports.balance_sheet,
    "get_ledger_transactions":    tally_bridge.queries.vouchers.ledger_vouchers,
    "get_day_book":               tally_bridge.queries.vouchers.day_book,
    "get_outstanding_receivables": tally_bridge.queries.reports.bills_receivable,
    "get_outstanding_payables":   tally_bridge.queries.reports.bills_payable,
    "get_stock_summary":          tally_bridge.queries.reports.stock_summary,
    "get_sales_register":         tally_bridge.queries.vouchers.sales_register,
    "get_purchase_register":      tally_bridge.queries.vouchers.purchase_register,
    "search_ledger":              tally_bridge.queries.masters.search_ledger,
    "list_companies":             tally_bridge.queries.masters.list_companies,
}
```

### 6.3 Claude API Integration

Use Anthropic Python SDK with tool-calling:

```python
# agents/query_agent.py

import anthropic

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

async def execute(plan: QueryPlan, session: SessionContext) -> QueryResult:
    messages = session.get_conversation_history()
    messages.append({"role": "user", "content": plan.original_query})

    # Claude tool-calling loop
    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=QUERY_AGENT_SYSTEM_PROMPT,
            tools=TALLY_TOOLS,
            messages=messages,
        )

        # Check if Claude wants to call a tool
        if response.stop_reason == "tool_use":
            tool_block = next(b for b in response.content if b.type == "tool_use")
            tool_name = tool_block.name
            tool_input = tool_block.input

            # Execute the tool against Tally
            try:
                result = await TOOL_HANDLERS[tool_name](**tool_input)
                tool_result = {"type": "tool_result", "tool_use_id": tool_block.id, "content": json.dumps(result)}
            except TallyConnectionError as e:
                tool_result = {"type": "tool_result", "tool_use_id": tool_block.id, "content": str(e), "is_error": True}

            # Feed result back to Claude
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": [tool_result]})
            continue

        # Claude is done — extract final text
        text = next((b.text for b in response.content if b.type == "text"), "")
        return QueryResult(text=text, raw_data=last_tool_result)
```

---

## 7. PHASE 3: FASTAPI BACKEND

### 7.1 Main App (`main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import chat, health, companies, reports

app = FastAPI(title="TallyPrime AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
```

### 7.2 Chat Endpoint (`api/chat.py`)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    company: str | None = None

class ChartSpec(BaseModel):
    chart_type: str
    title: str
    data: list[dict]
    config: dict | None = None

class ChatResponse(BaseModel):
    message: str
    data: dict | None = None         # table data: {headers, rows}
    chart: ChartSpec | None = None   # chart specification
    session_id: str

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint.
    Receives NL query, routes through agent pipeline, returns response.
    """
    session = get_or_create_session(request.session_id, request.company)
    result = await orchestrator.process_query(request.message, session)

    return ChatResponse(
        message=result.message,
        data=result.data,
        chart=result.chart,
        session_id=session.id,
    )
```

### 7.3 Health Endpoint (`api/health.py`)

```python
@router.get("/health")
async def health_check():
    """Check Tally connectivity and return status."""
    tally_ok = await tally_client.health_check()
    return {
        "status": "healthy" if tally_ok else "degraded",
        "tally_connected": tally_ok,
        "tally_url": settings.TALLY_URL,
    }
```

---

## 8. PHASE 4: REACT FRONTEND

### 8.1 Tech Setup

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install recharts axios lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

### 8.2 Core Components

**ChatWindow.jsx**: Main container. Maintains messages array in state. Renders MessageBubble for each message. ChatInput at bottom. Calls `/api/chat` on send.

**MessageBubble.jsx**: Renders a single message. If `data` exists, renders DataTable. If `chart` exists, renders ChartRenderer. Otherwise renders text.

**ChartRenderer.jsx**: Takes chart spec from API response. Uses Recharts to render:
- `bar` → `<BarChart>`
- `line` → `<LineChart>`
- `pie` → `<PieChart>`
- `grouped_bar` → `<BarChart>` with multiple `<Bar>` components

**DataTable.jsx**: Renders tabular data with sortable columns. Add an "Export CSV" button.

**QuickActions.jsx**: Preset buttons for common queries:
- "P&L this month"
- "Outstanding receivables"
- "Cash balance"
- "Stock summary"
- "Top 10 customers"
- "Sales vs purchases this month"

**CompanySelector.jsx**: Dropdown fetched from `/api/companies`. Sets active company in session.

### 8.3 Design Guidelines

- Clean, minimal UI. White background, subtle borders.
- Chat messages: user on right (blue), agent on left (gray).
- Charts should be inline within chat bubbles, not in separate panels.
- Mobile responsive — single column on small screens.
- Use Indian Rupee symbol (₹) and Indian number formatting throughout.
- Loading state: show a pulsing "Thinking..." bubble while waiting.

---

## 9. PHASE 5: ADVANCED FEATURES

After the core is working:

1. **Conversation Memory**: Maintain last 10 messages in session for multi-turn context (e.g., "What about last quarter?" after a sales query).

2. **Cached Ledger List**: Fetch ledger/master list once per session, cache it. Use for fuzzy matching in `search_ledger` without hitting Tally every time.

3. **GST Reports**: Add tools for GSTR-1 summary, GSTR-3B, tax liability.

4. **Date-Relative Intelligence**: "yesterday", "last week", "last Monday", "since Diwali" — parse these into actual date ranges.

5. **Export**: Allow exporting any data table or chart as PDF or Excel from the frontend.

6. **WhatsApp Integration**: Add Twilio/Meta webhook endpoint. Format responses as text-only (no charts). Send tables as formatted text.

---

## 10. TESTING STRATEGY

### 10.1 Testing Pyramid

```
        ╱  E2E Tests  ╲              ← Few: real Tally or full mock
       ╱──────────────────╲
      ╱  Integration Tests  ╲         ← Medium: mock Tally HTTP server
     ╱────────────────────────╲
    ╱      Unit Tests           ╲      ← Many: pure logic, no I/O
   ╱──────────────────────────────╲
```

### 10.2 Unit Tests

**No external dependencies. Fast. Run on every commit.**

#### test_request_builder.py
```python
def test_trial_balance_xml_has_correct_dates():
    xml = build_trial_balance_request("01-04-2025", "31-03-2026")
    assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
    assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

def test_trial_balance_xml_has_export_format():
    xml = build_trial_balance_request("01-04-2025", "31-03-2026")
    assert "$$SysName:XML" in xml

def test_ledger_vouchers_xml_includes_ledger_name():
    xml = build_ledger_vouchers_request("HDFC Bank", "01-04-2025", "31-03-2026")
    assert "<LEDGERNAME>HDFC Bank</LEDGERNAME>" in xml

def test_day_book_xml_with_voucher_type_filter():
    xml = build_day_book_request("01-04-2025", "30-04-2025", voucher_type="Sales")
    assert "VchTypeFilter" in xml
    assert "Sales" in xml

def test_company_name_included_when_specified():
    xml = build_trial_balance_request("01-04-2025", "31-03-2026", company="ABC Pvt Ltd")
    assert "<SVCurrentCompany>ABC Pvt Ltd</SVCurrentCompany>" in xml
```

#### test_response_parser.py
```python
def test_parse_trial_balance_xml():
    with open("tests/fixtures/trial_balance.xml") as f:
        raw = f.read()
    result = parse_trial_balance(raw)
    assert len(result) > 0
    assert "account_name" in result[0]
    assert "closing_balance" in result[0]

def test_parse_empty_amount_as_zero():
    # Tally sometimes returns empty tags for zero amounts
    xml_fragment = "<DSPCLCRAMTA></DSPCLCRAMTA>"
    assert parse_amount(xml_fragment) == 0.0

def test_parse_negative_amount():
    assert parse_amount("-1,23,456.78") == -123456.78

def test_parse_error_response():
    with open("tests/fixtures/error_responses.xml") as f:
        raw = f.read()
    result = parse_response(raw)
    assert result.is_error
    assert "DESC not found" in result.error_message
```

#### test_date_utils.py
```python
from datetime import date

def test_current_fy_start():
    # If today is Jan 2026, FY start is April 2025
    assert get_fy_start(date(2026, 1, 15)) == date(2025, 4, 1)

def test_current_fy_start_after_april():
    assert get_fy_start(date(2025, 6, 15)) == date(2025, 4, 1)

def test_last_fy_range():
    start, end = get_last_fy_range(date(2026, 1, 15))
    assert start == date(2024, 4, 1)
    assert end == date(2025, 3, 31)

def test_parse_this_month():
    from_d, to_d = parse_relative_date("this month", reference=date(2026, 1, 15))
    assert from_d == date(2026, 1, 1)
    assert to_d == date(2026, 1, 31)

def test_parse_last_quarter_indian_fy():
    # If current is Jan 2026 (Q4), last quarter = Q3 (Oct-Dec 2025)
    from_d, to_d = parse_relative_date("last quarter", reference=date(2026, 1, 15))
    assert from_d == date(2025, 10, 1)
    assert to_d == date(2025, 12, 31)

def test_format_date_for_tally():
    assert format_for_tally(date(2025, 4, 1)) == "01-04-2025"
```

#### test_currency_format.py
```python
def test_indian_format_lakhs():
    assert format_inr(123456.78) == "₹1,23,456.78"

def test_indian_format_crores():
    assert format_inr(12345678.90) == "₹1,23,45,678.90"

def test_negative_amount():
    assert format_inr(-50000) == "-₹50,000.00"

def test_zero():
    assert format_inr(0) == "₹0.00"
```

### 10.3 Integration Tests

**Use a mock Tally HTTP server. Test the full request → parse → return cycle.**

#### Mock Tally Server (`tests/mocks/mock_tally_server.py`)

```python
"""
A lightweight HTTP server that mimics TallyPrime's behavior.
Receives XML POST requests, pattern-matches the report type,
and returns corresponding fixture data.
"""

from aiohttp import web
import os

FIXTURE_DIR = "tests/fixtures"

REPORT_FIXTURES = {
    "Trial Balance": "trial_balance.xml",
    "Profit and Loss": "profit_and_loss.xml",
    "List of Ledgers": "ledger_list.xml",
    "DayBook": "day_book.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_payable.xml",
    "Stock Summary": "stock_summary.xml",
    "List of Companies": "company_list.xml",
}

async def handle_tally_request(request):
    body = await request.text()

    # Match report ID from XML
    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in body:
            fixture_path = os.path.join(FIXTURE_DIR, fixture_file)
            with open(fixture_path) as f:
                return web.Response(text=f.read(), content_type="text/xml")

    return web.Response(text="<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>", content_type="text/xml")

def create_mock_tally_app():
    app = web.Application()
    app.router.add_post("/", handle_tally_request)
    return app
```

#### Integration Test Examples

```python
# tests/integration/test_tally_client.py

import pytest
from aiohttp.test_utils import AioHTTPTestCase
from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient

@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient()
    client.base_url = f"http://localhost:{server.port}"
    return client

async def test_fetch_trial_balance(mock_tally):
    result = await mock_tally.queries.reports.trial_balance("01-04-2025", "31-03-2026")
    assert result.report_name == "Trial Balance"
    assert len(result.rows) > 0

async def test_fetch_ledger_list(mock_tally):
    ledgers = await mock_tally.queries.masters.list_ledgers()
    assert isinstance(ledgers, list)
    assert all("name" in l for l in ledgers)

async def test_connection_error_when_tally_down():
    client = TallyClient()
    client.base_url = "http://localhost:19999"  # nothing here
    with pytest.raises(TallyConnectionError):
        await client.health_check()

async def test_search_ledger_fuzzy_match(mock_tally):
    results = await mock_tally.queries.masters.search_ledger("HDFC")
    assert any("HDFC" in r["name"] for r in results)
```

```python
# tests/integration/test_chat_endpoint.py

import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

async def test_chat_simple_query(client, monkeypatch):
    # Mock the Tally bridge to return fixture data
    monkeypatch.setattr("backend.agents.tools.TOOL_HANDLERS", mock_tool_handlers)

    response = await client.post("/api/chat", json={
        "message": "What is our profit this month?",
    })
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["session_id"] is not None

async def test_chat_returns_chart_for_trend(client, monkeypatch):
    monkeypatch.setattr("backend.agents.tools.TOOL_HANDLERS", mock_tool_handlers)

    response = await client.post("/api/chat", json={
        "message": "Show me sales trend for last 6 months",
    })
    data = response.json()
    assert data["chart"] is not None
    assert data["chart"]["chart_type"] in ("line", "bar")

async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert "tally_connected" in response.json()
```

### 10.4 E2E / Scenario Tests

**Test the full NL query → agent → Tally → response pipeline.**
These use mocked Tally + mocked Claude (or real Claude with a test key).

```python
# tests/e2e/test_agent_scenarios.py

SCENARIOS = [
    {
        "query": "What is our profit this month?",
        "expected_tools": ["get_profit_and_loss"],
        "expected_in_response": ["profit", "loss", "₹"],
        "should_have_chart": False,
    },
    {
        "query": "Top 5 customers by sales this quarter",
        "expected_tools": ["get_sales_register"],
        "expected_in_response": ["₹"],
        "should_have_chart": True,
        "expected_chart_type": "bar",
    },
    {
        "query": "Compare sales this month vs last month",
        "expected_tools": ["get_sales_register"],  # called twice
        "min_tool_calls": 2,
        "should_have_chart": True,
        "expected_chart_type": "grouped_bar",
    },
    {
        "query": "What is the balance in HDFC Bank account?",
        "expected_tools": ["search_ledger", "get_ledger_transactions"],
        "expected_in_response": ["HDFC", "₹"],
    },
    {
        "query": "Show me all pending receivables",
        "expected_tools": ["get_outstanding_receivables"],
        "should_have_chart": False,
    },
    {
        "query": "How much stock do we have of Electronics?",
        "expected_tools": ["get_stock_summary"],
        "expected_in_response": ["Electronics"],
    },
    {
        "query": "Hello!",
        "expected_tools": [],
        "expected_in_response": ["hello", "help", "Hi"],
    },
    {
        "query": "Show me the P&L",
        "expected_tools": ["get_profit_and_loss"],
        "should_have_chart": False,
    },
    {
        "query": "Who do we owe the most money to?",
        "expected_tools": ["get_outstanding_payables"],
        "should_have_chart": True,
    },
    {
        "query": "Daily sales for last week",
        "expected_tools": ["get_day_book"],
        "should_have_chart": True,
        "expected_chart_type": "line",
    },
]

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["query"][:40] for s in SCENARIOS])
async def test_scenario(scenario, mock_tally, mock_claude_or_real):
    response = await orchestrator.process_query(scenario["query"], test_session)

    # Verify correct tools were called
    tools_called = [call.tool_name for call in response.tool_calls]
    for expected_tool in scenario["expected_tools"]:
        assert expected_tool in tools_called, f"Expected tool {expected_tool} not called"

    # Verify response content
    for expected_text in scenario.get("expected_in_response", []):
        assert expected_text.lower() in response.message.lower()

    # Verify chart
    if scenario.get("should_have_chart"):
        assert response.chart is not None
        if "expected_chart_type" in scenario:
            assert response.chart.chart_type == scenario["expected_chart_type"]

    # Verify min tool calls
    if "min_tool_calls" in scenario:
        assert len(tools_called) >= scenario["min_tool_calls"]
```

### 10.5 Fixture Data Collection

**CRITICAL**: To build good fixtures, export real data from TallyPrime.

Steps to collect fixtures:
1. Open TallyPrime with a sample company (use the built-in sample companies or create one).
2. Use Tally Connector (from TallyPrime Developer) or curl/Postman to send each XML request.
3. Save each response as a fixture file in `tests/fixtures/`.
4. Alternatively, use the `scripts/seed_tally_data.py` script to create a test company with known data, then export.

If Tally is not available during development, manually create fixture files based on the XML response structures documented in the Tally developer reference.

### 10.6 Mock Claude API (`tests/mocks/mock_claude_api.py`)

For tests that don't need real LLM reasoning, mock Claude's response:

```python
"""
Mock that returns pre-defined tool calls for known query patterns.
Avoids API costs during testing.
"""

MOCK_RESPONSES = {
    "profit": {
        "tool_calls": [{"name": "get_profit_and_loss", "input": {"from_date": "01-03-2026", "to_date": "31-03-2026"}}],
        "final_text": "Your net profit this month is ₹2,45,000."
    },
    "receivable": {
        "tool_calls": [{"name": "get_outstanding_receivables", "input": {"as_on_date": "03-03-2026"}}],
        "final_text": "Total outstanding receivables: ₹15,67,800."
    },
    # ... more patterns
}
```

### 10.7 Test Execution

```bash
# Run all unit tests (fast, no external deps)
pytest tests/unit/ -v

# Run integration tests (needs mock server)
pytest tests/integration/ -v

# Run E2E scenario tests (needs mock or real Claude API key)
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v

# Run everything with coverage
pytest --cov=backend --cov-report=html
```

---

## 11. CONFIGURATION & ENVIRONMENT

### .env.example

```bash
# TallyPrime Connection
TALLY_HOST=192.168.1.100          # IP of the machine running TallyPrime
TALLY_PORT=9000                    # Tally's configured port

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...       # Claude API key
CLAUDE_MODEL=claude-sonnet-4-20250514

# App Settings
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
SESSION_TTL_MINUTES=60             # How long to keep chat sessions

# Frontend
VITE_API_URL=http://localhost:8000  # Backend URL for the React app
```

### config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TALLY_HOST: str = "localhost"
    TALLY_PORT: int = 9000
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SESSION_TTL_MINUTES: int = 60

    @property
    def TALLY_URL(self) -> str:
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 12. KEY TECHNICAL DECISIONS

### 12.1 XML vs JSON for Tally Communication

- **Use XML for all requests initially**. It's the most documented, battle-tested approach.
- TallyPrime 7.0+ supports native JSON, but documentation is newer and edge cases may exist.
- XML request format is stable across all Tally versions.
- Parse XML responses using `xml.etree.ElementTree`.
- If JSON proves more reliable after testing, migrate individual endpoints.

### 12.2 Claude Model

- Use `claude-sonnet-4-20250514` for all agents — best balance of tool-calling quality and speed.
- Orchestrator calls are lightweight (classification only) — fast.
- Query Agent may need multiple tool-call rounds — Sonnet handles this well.
- Analysis Agent gets pre-fetched data — doesn't need tools, just reasoning.

### 12.3 Session Management

- Use in-memory dict for MVP. Key = session_id, Value = {conversation history, company, cached data}.
- Session TTL = 60 minutes of inactivity.
- Limit conversation history to last 20 messages to control token usage.
- For production, move to Redis.

### 12.4 Error Handling Priority

Handle these failure modes gracefully:
1. **Tally not running** → Clear error: "Cannot connect to TallyPrime. Please ensure it's running on {host}:{port}."
2. **No company loaded** → "TallyPrime is running but no company is loaded. Please open a company."
3. **Invalid ledger name** → Suggest closest matches from cached ledger list.
4. **Date range error** → "The date range seems incorrect. Indian FY runs April to March."
5. **Tally timeout** → "The report is taking too long. Try a shorter date range."
6. **Claude API error** → "AI service is temporarily unavailable. Try again."

### 12.5 Security (MVP)

- No auth for MVP (LAN-only access).
- Do NOT log raw financial data in production.
- Tally bridge is READ-ONLY in Phase 1 (no import/write operations).
- Add API key auth before exposing outside LAN.

---

## 13. SEED DATA SCRIPT

### Purpose

Creates a complete test company in TallyPrime with realistic Indian business data — enough to exercise every tool and query type. This is useful for:
- Development without touching real company data
- Consistent test data for automated tests
- Demos and walkthroughs

### Company Profile

```
Company Name:    Bharat Traders Pvt Ltd
Financial Year:  April 2025 – March 2026
Industry:        Trading (Electronics & Office Supplies)
GST Registered:  Yes (GSTIN: 27AABCB1234F1ZP)
State:           Maharashtra
```

### Script: `scripts/seed_tally_data.py`

```python
"""
Seed data script for TallyPrime.

Creates a test company "Bharat Traders Pvt Ltd" with:
- 30+ ledgers across all major groups
- 15 stock items in 3 stock groups
- 6 months of transactions (Oct 2025 – Mar 2026)
- Sales, purchases, payments, receipts, journal entries
- Outstanding receivables and payables
- Multi-godown inventory

Usage:
    python scripts/seed_tally_data.py --host 192.168.1.100 --port 9000

Prerequisites:
    - TallyPrime must be running with port configured
    - Create a blank company "Bharat Traders Pvt Ltd" manually in Tally
      (FY: April 2025 - March 2026) and load it before running this script
    - Enable GST in the company: F11 > Statutory > Enable GST = Yes
"""

import httpx
import argparse
import time
import sys

# ---------------------------------------------------------------------------
# XML TEMPLATES
# ---------------------------------------------------------------------------

CREATE_GROUP_XML = """
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
  <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
  <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
      {groups_xml}
    </TALLYMESSAGE>
  </REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>
"""

CREATE_LEDGER_XML = """
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
  <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
  <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
      {ledgers_xml}
    </TALLYMESSAGE>
  </REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>
"""

CREATE_STOCKGROUP_XML = """
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
  <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
  <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
      {stock_groups_xml}
    </TALLYMESSAGE>
  </REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>
"""

CREATE_STOCKITEM_XML = """
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
  <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
  <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
      {stock_items_xml}
    </TALLYMESSAGE>
  </REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>
"""

CREATE_UOM_XML = """
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY>
<IMPORTDATA>
  <REQUESTDESC><REPORTNAME>All Masters</REPORTNAME></REQUESTDESC>
  <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
      <UNIT Action="Create">
        <NAME>{name}</NAME>
        <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
        <ORIGINALNAME>{original_name}</ORIGINALNAME>
      </UNIT>
    </TALLYMESSAGE>
  </REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>
"""

CREATE_VOUCHER_XML = """
<ENVELOPE>
<HEADER>
  <VERSION>1</VERSION>
  <TALLYREQUEST>Import</TALLYREQUEST>
  <TYPE>Data</TYPE>
  <ID>Vouchers</ID>
</HEADER>
<BODY>
<DESC></DESC>
<DATA>
<TALLYMESSAGE>
  {voucher_xml}
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
"""

# ---------------------------------------------------------------------------
# MASTER DATA DEFINITIONS
# ---------------------------------------------------------------------------

GROUPS = [
    ("North Zone Debtors", "Sundry Debtors"),
    ("South Zone Debtors", "Sundry Debtors"),
    ("Local Creditors", "Sundry Creditors"),
    ("National Creditors", "Sundry Creditors"),
]

LEDGERS = [
    # Party Ledgers (Debtors)
    {"name": "Apex Technologies Pvt Ltd", "parent": "North Zone Debtors",
     "address": "45 Nehru Place, New Delhi", "state": "Delhi", "pincode": "110019",
     "gstin": "07AABCA1234B1ZP"},
    {"name": "Sunrise Electronics Mumbai", "parent": "South Zone Debtors",
     "address": "12 Andheri West, Mumbai", "state": "Maharashtra", "pincode": "400053",
     "gstin": "27AABCS5678C1ZP"},
    {"name": "Global IT Solutions", "parent": "North Zone Debtors",
     "address": "78 Cyber City, Gurugram", "state": "Haryana", "pincode": "122002",
     "gstin": "06AABCG9012D1ZP"},
    {"name": "Sharma & Sons Traders", "parent": "South Zone Debtors",
     "address": "23 MG Road, Bangalore", "state": "Karnataka", "pincode": "560001",
     "gstin": "29AABCS3456E1ZP"},
    {"name": "Patel Enterprises", "parent": "North Zone Debtors",
     "address": "56 CG Road, Ahmedabad", "state": "Gujarat", "pincode": "380006",
     "gstin": "24AABCP7890F1ZP"},
    {"name": "Rajesh Computers", "parent": "South Zone Debtors",
     "address": "34 Anna Salai, Chennai", "state": "Tamil Nadu", "pincode": "600002",
     "gstin": "33AABCR1234G1ZP"},
    {"name": "Eastern Digital Hub", "parent": "North Zone Debtors",
     "address": "89 Park Street, Kolkata", "state": "West Bengal", "pincode": "700016",
     "gstin": "19AABCE5678H1ZP"},

    # Party Ledgers (Creditors / Suppliers)
    {"name": "Samsung India Electronics", "parent": "National Creditors",
     "address": "Samsung Hub, Noida", "state": "Uttar Pradesh", "pincode": "201301",
     "gstin": "09AABCS9012I1ZP"},
    {"name": "HP India Sales Pvt Ltd", "parent": "National Creditors",
     "address": "DLF Cyber City, Gurugram", "state": "Haryana", "pincode": "122002",
     "gstin": "06AABCH3456J1ZP"},
    {"name": "Logitech India Pvt Ltd", "parent": "National Creditors",
     "address": "Whitefield, Bangalore", "state": "Karnataka", "pincode": "560066",
     "gstin": "29AABCL7890K1ZP"},
    {"name": "Local Stationery Mart", "parent": "Local Creditors",
     "address": "101 Dadar TT, Mumbai", "state": "Maharashtra", "pincode": "400014",
     "gstin": "27AABCL1234L1ZP"},
    {"name": "Bharat Paper Supplies", "parent": "Local Creditors",
     "address": "45 Parel, Mumbai", "state": "Maharashtra", "pincode": "400012",
     "gstin": "27AABCB5678M1ZP"},

    # Bank Accounts
    {"name": "HDFC Bank - Current A/c", "parent": "Bank Accounts",
     "opening_balance": -500000},  # negative = debit balance in Tally
    {"name": "SBI Savings A/c", "parent": "Bank Accounts",
     "opening_balance": -200000},
    {"name": "Cash", "parent": "Cash-in-Hand",
     "opening_balance": -50000},

    # Revenue Ledgers
    {"name": "Sales - Electronics", "parent": "Sales Accounts"},
    {"name": "Sales - Office Supplies", "parent": "Sales Accounts"},

    # Purchase Ledgers
    {"name": "Purchase - Electronics", "parent": "Purchase Accounts"},
    {"name": "Purchase - Office Supplies", "parent": "Purchase Accounts"},

    # Expense Ledgers
    {"name": "Rent", "parent": "Indirect Expenses"},
    {"name": "Salaries", "parent": "Indirect Expenses"},
    {"name": "Electricity", "parent": "Indirect Expenses"},
    {"name": "Internet & Phone", "parent": "Indirect Expenses"},
    {"name": "Office Maintenance", "parent": "Indirect Expenses"},
    {"name": "Travel & Conveyance", "parent": "Indirect Expenses"},
    {"name": "Courier & Freight", "parent": "Direct Expenses"},
    {"name": "Packing Charges", "parent": "Direct Expenses"},

    # Tax Ledgers
    {"name": "CGST Output", "parent": "Duties & Taxes"},
    {"name": "SGST Output", "parent": "Duties & Taxes"},
    {"name": "IGST Output", "parent": "Duties & Taxes"},
    {"name": "CGST Input", "parent": "Duties & Taxes"},
    {"name": "SGST Input", "parent": "Duties & Taxes"},
    {"name": "IGST Input", "parent": "Duties & Taxes"},

    # Capital
    {"name": "Capital Account", "parent": "Capital Account",
     "opening_balance": 750000},
]

STOCK_GROUPS = [
    "Electronics",
    "Peripherals",
    "Office Supplies",
]

STOCK_ITEMS = [
    # Electronics
    {"name": "Samsung 24 inch Monitor", "group": "Electronics", "uom": "Nos",
     "rate": 12500, "opening_qty": 20, "opening_rate": 11000},
    {"name": "HP Laptop 15s", "group": "Electronics", "uom": "Nos",
     "rate": 45000, "opening_qty": 10, "opening_rate": 38000},
    {"name": "Samsung Galaxy Tab A8", "group": "Electronics", "uom": "Nos",
     "rate": 16000, "opening_qty": 15, "opening_rate": 13500},
    {"name": "Dell Desktop Optiplex", "group": "Electronics", "uom": "Nos",
     "rate": 35000, "opening_qty": 8, "opening_rate": 29000},
    {"name": "Lenovo Ideapad Slim 3", "group": "Electronics", "uom": "Nos",
     "rate": 42000, "opening_qty": 12, "opening_rate": 36000},

    # Peripherals
    {"name": "Logitech Wireless Mouse", "group": "Peripherals", "uom": "Nos",
     "rate": 800, "opening_qty": 100, "opening_rate": 550},
    {"name": "Logitech Keyboard K380", "group": "Peripherals", "uom": "Nos",
     "rate": 2500, "opening_qty": 60, "opening_rate": 1800},
    {"name": "HP DeskJet Printer 2723", "group": "Peripherals", "uom": "Nos",
     "rate": 5500, "opening_qty": 10, "opening_rate": 4200},
    {"name": "TP-Link WiFi Router AC750", "group": "Peripherals", "uom": "Nos",
     "rate": 1800, "opening_qty": 25, "opening_rate": 1300},
    {"name": "USB-C Hub 7-in-1", "group": "Peripherals", "uom": "Nos",
     "rate": 1500, "opening_qty": 40, "opening_rate": 950},

    # Office Supplies
    {"name": "A4 Paper Ream 500 sheets", "group": "Office Supplies", "uom": "Pcs",
     "rate": 350, "opening_qty": 200, "opening_rate": 280},
    {"name": "Whiteboard Marker Set", "group": "Office Supplies", "uom": "Pcs",
     "rate": 250, "opening_qty": 50, "opening_rate": 180},
    {"name": "Stapler Heavy Duty", "group": "Office Supplies", "uom": "Nos",
     "rate": 450, "opening_qty": 30, "opening_rate": 320},
    {"name": "Box File Pack of 10", "group": "Office Supplies", "uom": "Pcs",
     "rate": 600, "opening_qty": 40, "opening_rate": 420},
    {"name": "Pen Drive 32GB", "group": "Office Supplies", "uom": "Nos",
     "rate": 400, "opening_qty": 80, "opening_rate": 280},
]

# ---------------------------------------------------------------------------
# TRANSACTION DATA — 6 months of varied transactions
# ---------------------------------------------------------------------------

# Each transaction: (date, voucher_type, debit_ledger, credit_ledger, amount, narration)
# For sales invoices and purchase invoices, a separate format is used.

SALES_INVOICES = [
    # (date, party, items: [(item, qty, rate)], narration)
    ("20251001", "Apex Technologies Pvt Ltd",
     [("HP Laptop 15s", 2, 45000), ("Logitech Wireless Mouse", 5, 800)],
     "Invoice #S001 - Laptops and peripherals"),
    ("20251008", "Sunrise Electronics Mumbai",
     [("Samsung 24 inch Monitor", 5, 12500), ("Samsung Galaxy Tab A8", 3, 16000)],
     "Invoice #S002 - Samsung products"),
    ("20251015", "Global IT Solutions",
     [("Dell Desktop Optiplex", 3, 35000), ("Logitech Keyboard K380", 10, 2500)],
     "Invoice #S003 - Desktop setup"),
    ("20251022", "Sharma & Sons Traders",
     [("A4 Paper Ream 500 sheets", 50, 350), ("Box File Pack of 10", 20, 600)],
     "Invoice #S004 - Office supplies bulk"),
    ("20251030", "Patel Enterprises",
     [("Lenovo Ideapad Slim 3", 4, 42000), ("USB-C Hub 7-in-1", 8, 1500)],
     "Invoice #S005 - Lenovo laptops"),
    ("20251105", "Rajesh Computers",
     [("HP DeskJet Printer 2723", 3, 5500), ("TP-Link WiFi Router AC750", 5, 1800)],
     "Invoice #S006 - Printers and networking"),
    ("20251115", "Eastern Digital Hub",
     [("Samsung 24 inch Monitor", 8, 12500), ("Logitech Wireless Mouse", 20, 800)],
     "Invoice #S007 - Monitor bulk order"),
    ("20251125", "Apex Technologies Pvt Ltd",
     [("Samsung Galaxy Tab A8", 5, 16000), ("Pen Drive 32GB", 20, 400)],
     "Invoice #S008 - Tablets and storage"),
    ("20251205", "Global IT Solutions",
     [("HP Laptop 15s", 5, 45000), ("Logitech Keyboard K380", 15, 2500)],
     "Invoice #S009 - Laptop bulk"),
    ("20251215", "Sunrise Electronics Mumbai",
     [("Lenovo Ideapad Slim 3", 3, 42000), ("USB-C Hub 7-in-1", 10, 1500)],
     "Invoice #S010 - Lenovo order"),
    ("20251228", "Sharma & Sons Traders",
     [("Whiteboard Marker Set", 30, 250), ("Stapler Heavy Duty", 15, 450)],
     "Invoice #S011 - Office stationery"),
    ("20260110", "Patel Enterprises",
     [("Dell Desktop Optiplex", 5, 35000), ("HP DeskJet Printer 2723", 4, 5500)],
     "Invoice #S012 - Desktop + printers"),
    ("20260120", "Rajesh Computers",
     [("Samsung 24 inch Monitor", 10, 12500), ("TP-Link WiFi Router AC750", 8, 1800)],
     "Invoice #S013 - Networking order"),
    ("20260205", "Eastern Digital Hub",
     [("HP Laptop 15s", 3, 45000), ("Logitech Wireless Mouse", 30, 800)],
     "Invoice #S014 - Laptop reorder"),
    ("20260215", "Apex Technologies Pvt Ltd",
     [("A4 Paper Ream 500 sheets", 100, 350), ("Pen Drive 32GB", 50, 400)],
     "Invoice #S015 - Office supplies"),
    ("20260301", "Global IT Solutions",
     [("Lenovo Ideapad Slim 3", 6, 42000), ("Samsung Galaxy Tab A8", 4, 16000)],
     "Invoice #S016 - IT equipment"),
]

PURCHASE_INVOICES = [
    # (date, supplier, items: [(item, qty, rate)], narration)
    ("20250928", "Samsung India Electronics",
     [("Samsung 24 inch Monitor", 25, 11000), ("Samsung Galaxy Tab A8", 20, 13500)],
     "PO #P001 - Samsung restock"),
    ("20251020", "HP India Sales Pvt Ltd",
     [("HP Laptop 15s", 15, 38000), ("HP DeskJet Printer 2723", 10, 4200)],
     "PO #P002 - HP products"),
    ("20251110", "Logitech India Pvt Ltd",
     [("Logitech Wireless Mouse", 150, 550), ("Logitech Keyboard K380", 80, 1800)],
     "PO #P003 - Peripherals bulk"),
    ("20251128", "Samsung India Electronics",
     [("Samsung 24 inch Monitor", 20, 11000), ("Samsung Galaxy Tab A8", 15, 13500)],
     "PO #P004 - Samsung restock #2"),
    ("20251215", "HP India Sales Pvt Ltd",
     [("HP Laptop 15s", 10, 38000), ("HP DeskJet Printer 2723", 8, 4200)],
     "PO #P005 - HP restock"),
    ("20260105", "Local Stationery Mart",
     [("A4 Paper Ream 500 sheets", 300, 280), ("Whiteboard Marker Set", 100, 180),
      ("Box File Pack of 10", 60, 420)],
     "PO #P006 - Stationery restock"),
    ("20260125", "Logitech India Pvt Ltd",
     [("Logitech Wireless Mouse", 100, 550), ("USB-C Hub 7-in-1", 50, 950)],
     "PO #P007 - Peripherals reorder"),
    ("20260210", "Bharat Paper Supplies",
     [("A4 Paper Ream 500 sheets", 200, 280), ("Stapler Heavy Duty", 50, 320)],
     "PO #P008 - Paper and stationery"),
]

# Payment & Receipt entries
PAYMENTS = [
    ("20251010", "Samsung India Electronics", "HDFC Bank - Current A/c", 400000, "Part payment for PO #P001"),
    ("20251105", "HP India Sales Pvt Ltd", "HDFC Bank - Current A/c", 500000, "Payment for PO #P002"),
    ("20251130", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - November"),
    ("20251130", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - November"),
    ("20251205", "Logitech India Pvt Ltd", "HDFC Bank - Current A/c", 150000, "Part payment PO #P003"),
    ("20251231", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - December"),
    ("20251231", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - December"),
    ("20251231", "Electricity", "HDFC Bank - Current A/c", 12000, "Electricity bill Q3"),
    ("20260115", "Local Stationery Mart", "HDFC Bank - Current A/c", 80000, "Payment PO #P006"),
    ("20260131", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - January"),
    ("20260131", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - January"),
    ("20260131", "Internet & Phone", "HDFC Bank - Current A/c", 8000, "Monthly internet"),
    ("20260228", "Rent", "HDFC Bank - Current A/c", 75000, "Office rent - February"),
    ("20260228", "Salaries", "HDFC Bank - Current A/c", 250000, "Staff salaries - February"),
    ("20260215", "Travel & Conveyance", "Cash", 15000, "Sales team travel"),
    ("20260220", "Office Maintenance", "Cash", 8000, "AC servicing"),
]

RECEIPTS = [
    ("20251020", "Apex Technologies Pvt Ltd", "HDFC Bank - Current A/c", 94000, "Receipt against S001"),
    ("20251105", "Sunrise Electronics Mumbai", "HDFC Bank - Current A/c", 110500, "Receipt against S002"),
    ("20251125", "Global IT Solutions", "HDFC Bank - Current A/c", 130000, "Part receipt S003"),
    ("20251210", "Sharma & Sons Traders", "SBI Savings A/c", 29500, "Receipt against S004"),
    ("20251228", "Patel Enterprises", "HDFC Bank - Current A/c", 180000, "Receipt against S005"),
    ("20260110", "Rajesh Computers", "HDFC Bank - Current A/c", 25500, "Receipt against S006"),
    ("20260120", "Eastern Digital Hub", "HDFC Bank - Current A/c", 116000, "Part receipt S007"),
    ("20260205", "Apex Technologies Pvt Ltd", "SBI Savings A/c", 88000, "Receipt against S008"),
    ("20260220", "Global IT Solutions", "HDFC Bank - Current A/c", 262500, "Receipt S009"),
    ("20260301", "Patel Enterprises", "HDFC Bank - Current A/c", 197000, "Receipt against S012"),
]

# ---------------------------------------------------------------------------
# SEND TO TALLY FUNCTIONS
# ---------------------------------------------------------------------------

def send_to_tally(url: str, xml: str) -> dict:
    """POST XML to Tally and return parsed response summary."""
    response = httpx.post(url, content=xml, headers={"Content-Type": "text/xml"}, timeout=30)
    text = response.text
    # Parse basic response counts
    created = extract_tag(text, "CREATED")
    errors = extract_tag(text, "ERRORS")
    return {"created": created, "errors": errors, "raw": text[:500]}

def extract_tag(xml_text: str, tag: str) -> str:
    import re
    match = re.search(f"<{tag}>(.*?)</{tag}>", xml_text)
    return match.group(1) if match else "?"

def build_ledger_xml(ledger: dict) -> str:
    """Build XML for a single ledger."""
    xml = f'<LEDGER Action="Create">\n'
    xml += f'  <NAME>{ledger["name"]}</NAME>\n'
    xml += f'  <PARENT>{ledger["parent"]}</PARENT>\n'
    if "address" in ledger:
        xml += f'  <ADDRESS.LIST TYPE="String"><ADDRESS>{ledger["address"]}</ADDRESS></ADDRESS.LIST>\n'
    if "state" in ledger:
        xml += f'  <LEDSTATENAME>{ledger["state"]}</LEDSTATENAME>\n'
    if "pincode" in ledger:
        xml += f'  <PINCODE>{ledger["pincode"]}</PINCODE>\n'
    if "gstin" in ledger:
        xml += f'  <PARTYGSTIN>{ledger["gstin"]}</PARTYGSTIN>\n'
    if "opening_balance" in ledger:
        xml += f'  <OPENINGBALANCE>{ledger["opening_balance"]}</OPENINGBALANCE>\n'
    xml += '</LEDGER>\n'
    return xml

def build_sales_voucher_xml(date, party, items, narration, inv_number):
    """Build XML for a sales invoice (Invoice Voucher View)."""
    total = sum(qty * rate for _, qty, rate in items)

    xml = f'<VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">\n'
    xml += f'  <DATE>{date}</DATE>\n'
    xml += f'  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>\n'
    xml += f'  <VOUCHERNUMBER>{inv_number}</VOUCHERNUMBER>\n'
    xml += f'  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n'
    xml += f'  <ISINVOICE>Yes</ISINVOICE>\n'
    xml += f'  <NARRATION>{narration}</NARRATION>\n'

    # Party ledger entry (Debit)
    xml += f'  <ALLLEDGERENTRIES.LIST>\n'
    xml += f'    <LEDGERNAME>{party}</LEDGERNAME>\n'
    xml += f'    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n'
    xml += f'    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n'
    xml += f'    <AMOUNT>-{total:.2f}</AMOUNT>\n'
    xml += f'    <BILLALLOCATIONS.LIST>\n'
    xml += f'      <NAME>{inv_number}</NAME>\n'
    xml += f'      <BILLTYPE>New Ref</BILLTYPE>\n'
    xml += f'      <AMOUNT>-{total:.2f}</AMOUNT>\n'
    xml += f'    </BILLALLOCATIONS.LIST>\n'
    xml += f'  </ALLLEDGERENTRIES.LIST>\n'

    # Inventory entries
    for item_name, qty, rate in items:
        amt = qty * rate
        # Determine sales ledger based on stock group
        sales_ledger = "Sales - Electronics"
        for si in STOCK_ITEMS:
            if si["name"] == item_name and si["group"] == "Office Supplies":
                sales_ledger = "Sales - Office Supplies"
                break

        xml += f'  <ALLINVENTORYENTRIES.LIST>\n'
        xml += f'    <STOCKITEMNAME>{item_name}</STOCKITEMNAME>\n'
        xml += f'    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n'
        xml += f'    <RATE>{rate:.2f}/Nos</RATE>\n'
        xml += f'    <AMOUNT>{amt:.2f}</AMOUNT>\n'
        xml += f'    <ACTUALQTY> {qty} Nos</ACTUALQTY>\n'
        xml += f'    <BILLEDQTY> {qty} Nos</BILLEDQTY>\n'
        xml += f'    <BATCHALLOCATIONS.LIST>\n'
        xml += f'      <GODOWNNAME>Main Location</GODOWNNAME>\n'
        xml += f'      <BATCHNAME>Primary Batch</BATCHNAME>\n'
        xml += f'      <AMOUNT>{amt:.2f}</AMOUNT>\n'
        xml += f'      <ACTUALQTY> {qty} Nos</ACTUALQTY>\n'
        xml += f'      <BILLEDQTY> {qty} Nos</BILLEDQTY>\n'
        xml += f'    </BATCHALLOCATIONS.LIST>\n'
        xml += f'    <ACCOUNTINGALLOCATIONS.LIST>\n'
        xml += f'      <LEDGERNAME>{sales_ledger}</LEDGERNAME>\n'
        xml += f'      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n'
        xml += f'      <AMOUNT>{amt:.2f}</AMOUNT>\n'
        xml += f'    </ACCOUNTINGALLOCATIONS.LIST>\n'
        xml += f'  </ALLINVENTORYENTRIES.LIST>\n'

    xml += '</VOUCHER>\n'
    return xml

# build_purchase_voucher_xml, build_payment_xml, build_receipt_xml follow
# similar patterns — see Tally developer reference for exact XML structures.
# The script should implement all four voucher builders.

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed TallyPrime with test data")
    parser.add_argument("--host", default="localhost", help="Tally host IP")
    parser.add_argument("--port", default=9000, type=int, help="Tally port")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print(f"Connecting to TallyPrime at {url}...")

    # Step 1: Create UOMs
    print("\n[1/6] Creating Units of Measure...")
    for name, full in [("Nos", "Numbers"), ("Pcs", "Pieces")]:
        xml = CREATE_UOM_XML.format(name=name, original_name=full)
        result = send_to_tally(url, xml)
        print(f"  UOM '{name}': created={result['created']}, errors={result['errors']}")

    # Step 2: Create Groups
    print("\n[2/6] Creating Account Groups...")
    groups_xml = "\n".join(
        f'<GROUP Action="Create"><NAME>{name}</NAME><PARENT>{parent}</PARENT></GROUP>'
        for name, parent in GROUPS
    )
    result = send_to_tally(url, CREATE_GROUP_XML.format(groups_xml=groups_xml))
    print(f"  Groups: created={result['created']}, errors={result['errors']}")

    # Step 3: Create Ledgers
    print("\n[3/6] Creating Ledgers...")
    ledgers_xml = "\n".join(build_ledger_xml(l) for l in LEDGERS)
    result = send_to_tally(url, CREATE_LEDGER_XML.format(ledgers_xml=ledgers_xml))
    print(f"  Ledgers: created={result['created']}, errors={result['errors']}")

    # Step 4: Create Stock Groups & Items
    print("\n[4/6] Creating Stock Groups & Items...")
    sg_xml = "\n".join(
        f'<STOCKGROUP Action="Create"><NAME>{sg}</NAME></STOCKGROUP>'
        for sg in STOCK_GROUPS
    )
    result = send_to_tally(url, CREATE_STOCKGROUP_XML.format(stock_groups_xml=sg_xml))
    print(f"  Stock Groups: created={result['created']}, errors={result['errors']}")

    si_xml_parts = []
    for si in STOCK_ITEMS:
        opening_val = si["opening_qty"] * si["opening_rate"]
        si_xml_parts.append(f'''<STOCKITEM Action="Create">
            <NAME>{si["name"]}</NAME>
            <PARENT>{si["group"]}</PARENT>
            <BASEUNITS>{si["uom"]}</BASEUNITS>
            <OPENINGBALANCE>{si["opening_qty"]} {si["uom"]}</OPENINGBALANCE>
            <OPENINGRATE>{si["opening_rate"]}</OPENINGRATE>
            <OPENINGVALUE>{opening_val}</OPENINGVALUE>
        </STOCKITEM>''')
    result = send_to_tally(url, CREATE_STOCKITEM_XML.format(stock_items_xml="\n".join(si_xml_parts)))
    print(f"  Stock Items: created={result['created']}, errors={result['errors']}")

    # Step 5: Create Sales & Purchase Invoices
    print("\n[5/6] Creating Vouchers (Sales & Purchases)...")
    for i, (date, party, items, narr) in enumerate(SALES_INVOICES):
        inv_num = f"S{i+1:03d}"
        voucher_xml = build_sales_voucher_xml(date, party, items, narr, inv_num)
        result = send_to_tally(url, CREATE_VOUCHER_XML.format(voucher_xml=voucher_xml))
        print(f"  Sales {inv_num}: created={result['created']}, errors={result['errors']}")
        time.sleep(0.2)  # avoid overwhelming Tally

    # Similar loop for PURCHASE_INVOICES with build_purchase_voucher_xml
    # ...

    # Step 6: Create Payments & Receipts
    print("\n[6/6] Creating Payments & Receipts...")
    # Similar loops for PAYMENTS and RECEIPTS
    # ...

    print("\n" + "="*60)
    print("SEED DATA COMPLETE!")
    print(f"Company: Bharat Traders Pvt Ltd")
    print(f"Period: Oct 2025 – Mar 2026")
    print(f"Sales Invoices: {len(SALES_INVOICES)}")
    print(f"Purchase Invoices: {len(PURCHASE_INVOICES)}")
    print(f"Payments: {len(PAYMENTS)}")
    print(f"Receipts: {len(RECEIPTS)}")
    print("="*60)

if __name__ == "__main__":
    main()
```

### Seed Data Summary

After running, the test company will have:

| Data | Count | Purpose |
|------|-------|---------|
| Account Groups | 4 custom + defaults | Test group hierarchy |
| Ledgers | 30+ | Debtors, creditors, banks, expenses, tax |
| Stock Groups | 3 | Electronics, Peripherals, Office Supplies |
| Stock Items | 15 | Range of prices from ₹250 to ₹45,000 |
| Sales Invoices | 16 | Across 7 customers, 6 months |
| Purchase Invoices | 8 | Across 5 suppliers |
| Payments | 16 | Rent, salaries, supplier payments |
| Receipts | 10 | Partial & full customer payments |

This creates realistic **outstanding receivables** (not all invoices are fully paid), **outstanding payables** (not all purchase invoices are settled), and enough **monthly variation** in sales for meaningful trend charts.

### Queries This Seed Data Can Answer

```
✓ "What is our profit this month?"           → P&L from seed transactions
✓ "Top 5 customers by sales"                 → 7 customers with varying sales
✓ "Compare sales this month vs last month"   → Monthly variation built in
✓ "Outstanding receivables"                  → Partial payments create real outstandings
✓ "How much do we owe Samsung?"              → Unpaid purchase invoices
✓ "Stock summary for Electronics"            → 5 electronics items with movements
✓ "What's in our HDFC Bank account?"         → Bank ledger with payments/receipts
✓ "Monthly expense breakdown"                → Rent, salaries, utilities every month
✓ "Who are our biggest suppliers?"           → 5 suppliers with different volumes
✓ "Sales trend for last 6 months"            → Oct-Mar data with variation
```

---

## QUICKSTART CHECKLIST

```
□ 1. Clone repo, install dependencies (uv sync or pip install -r requirements.txt)
□ 2. Copy .env.example to .env, fill in TALLY_HOST and ANTHROPIC_API_KEY
□ 3. Run scripts/test_tally_connection.py to verify Tally is reachable
□ 4. OPTIONAL: Create blank company in Tally, run scripts/seed_tally_data.py
□ 5. Build tally_bridge/client.py + request_builder.py + response_parser.py
□ 6. Test with: get list of companies, get trial balance, get ledger list
□ 7. Build agents/tools.py with all tool definitions
□ 8. Build agents/query_agent.py with Claude tool-calling loop
□ 9. Build agents/orchestrator.py to route queries
□ 10. Build api/chat.py endpoint
□ 11. Run pytest tests/unit/ — all green
□ 12. Run pytest tests/integration/ — all green
□ 13. Build frontend React app
□ 14. End-to-end test: open browser, ask "What is our profit this month?"
□ 15. Iterate on prompt quality and response formatting
```
