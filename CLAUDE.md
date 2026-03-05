# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TallyPrime AI Agent — an AI-powered chatbot that connects to a live TallyPrime instance over LAN, lets users ask natural language questions about accounting data, and returns answers with charts and tables.

**Stack**: Python (FastAPI) backend + React (Vite) frontend + Claude API (Anthropic SDK with tool-calling)
**Tally Version**: TallyPrime 7.0+ (native JSON support, XML preferred for stability)
**Implementation Plan**: See `TALLYPRIME_AGENT_PLAN.md` for the full spec and phased build order.

## Build & Run Commands

### Backend (Python)
```bash
# Install dependencies
uv sync                              # or: pip install -r requirements.txt

# Run the FastAPI server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run all unit tests (fast, no external deps)
pytest tests/unit/ -v

# Run a single test file
pytest tests/unit/test_request_builder.py -v

# Run a single test
pytest tests/unit/test_request_builder.py::test_trial_balance_xml_has_correct_dates -v

# Integration tests (needs mock Tally server)
pytest tests/integration/ -v

# E2E scenario tests
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v

# All backend tests (unit + integration + E2E mock)
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/

# All tests with coverage
pytest --cov=backend --cov-report=html

# Live E2E tests (needs real Tally + Claude API key)
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host <TALLY_IP> --port 9000

# Verify Tally connectivity
python scripts/test_tally_connection.py

# Live test: agent pipeline against real Tally (needs ANTHROPIC_API_KEY)
PYTHONPATH=. uv run python scripts/test_agent_live.py --host <TALLY_IP> --port 9000

# Seed test data into Tally
python scripts/seed_tally_data.py --host <TALLY_IP> --port 9000
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev                          # Vite dev server
npm run build                        # Production build
npm test                             # Vitest unit tests (68 tests)
npm run test:watch                   # Vitest in watch mode
npm run test:responsive              # Playwright responsive screenshot tests (15 tests)
```

## Architecture

### Three-Layer Backend

1. **Tally Bridge** (`backend/tally_bridge/`) — HTTP client that communicates with TallyPrime's XML/JSON API on the LAN. Core modules:
   - `client.py` — Async HTTP client (httpx) posting to `http://<TALLY_HOST>:<TALLY_PORT>`
   - `request_builder.py` — Builds XML request payloads for each Tally operation
   - `response_parser.py` — Parses XML/JSON responses into normalized Python dicts
   - `queries/` — Domain-specific queries: `masters.py` (ledgers, groups), `reports.py` (TB, P&L, BS), `vouchers.py` (day book, sales/purchase register)
   - `models.py` — Pydantic models for Tally data structures
   - `exceptions.py` — `TallyConnectionError`, `TallyResponseError`

2. **Multi-Agent System** (`backend/agents/`) — Orchestrator routes queries to specialized agents:
   - `orchestrator.py` — Classifies query type (simple_lookup, comparison, trend, top_n, aggregation, greeting) and routes to appropriate agent(s)
   - `query_agent.py` — Fetches raw data from Tally via Claude tool-calling loop
   - `analysis_agent.py` — Performs comparisons, trends, rankings on fetched data
   - `chart_agent.py` — Picks chart type and formats data for Recharts rendering
   - `tools.py` — Claude-compatible tool schemas + tool handler mapping to tally_bridge functions
   - `prompts.py` — System prompts for each agent
   - `context.py` — Session/conversation context management

3. **FastAPI Routes** (`backend/api/`) — REST endpoints:
   - `POST /api/chat` — Main chat endpoint (NL query → agent pipeline → response with optional table/chart)
   - `GET /api/health` — Tally connectivity check
   - `GET /api/companies` — List loaded Tally companies
   - `GET /api/reports/{name}` — Direct report access

### Agent Pipeline Flow

```
User query → Orchestrator (classify) → Query Agent (fetch from Tally via tools)
  → Analysis Agent (if comparison/trend/top-N) → Chart Agent (if visual needed)
  → Final NL response with optional data table and chart spec
```

### Frontend (React + Vite + Tailwind + Recharts)

Chat-based UI at `frontend/src/`. Key components: `ChatWindow`, `MessageBubble` (renders text/table/chart inline), `ChartRenderer` (bar/line/pie via Recharts), `DataTable` (sortable with CSV export), `QuickActions` (preset query buttons), `CompanySelector`.

## Key Technical Conventions

- **Dates**: Tally expects DD-MM-YYYY format. Indian Financial Year = April 1 to March 31. Quarters: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.
- **Currency**: Use Indian comma formatting (₹12,34,567.00). Negative = outflow/debit, Positive = inflow/credit (Tally convention).
- **XML requests**: Preferred over JSON for Tally communication — more stable and documented across versions. Use `xml.etree.ElementTree` for parsing.
- **Claude model**: `claude-sonnet-4-20250514` for all agents.
- **Session management**: In-memory dict for MVP (session_id → conversation history + company + cached data). TTL = 60 min. Limit to 20 messages for token control.
- **Tally Bridge is READ-ONLY** — no import/write operations except the seed data script.
- **Configuration**: All settings via `.env` file loaded by `pydantic_settings.BaseSettings` in `backend/config.py`.

## Environment Variables

```
TALLY_HOST, TALLY_PORT (default: localhost:9000)
ANTHROPIC_API_KEY
CLAUDE_MODEL (default: claude-sonnet-4-20250514)
APP_HOST, APP_PORT (default: 0.0.0.0:8000)
VITE_API_URL (default: http://localhost:8000)
```

## Testing

- **Unit tests** (`tests/unit/`): Pure logic, no I/O. Test request XML construction, response parsing, date utils, currency formatting. 274 tests.
- **Integration tests** (`tests/integration/`): Use mock Tally HTTP server (`tests/mocks/mock_tally_server.py`) built with aiohttp. Tests full request→parse→return cycle. 43 tests.
- **E2E tests** (`tests/e2e/`): Full NL query → agent → Tally → response pipeline. Uses mock Claude API (`tests/mocks/mock_claude_api.py`) to avoid API costs. 8 tests.
- **E2E live tests** (`tests/e2e_live/`): End-to-end against real Tally + real Claude API. Gated by `RUN_LIVE_TESTS=1` env var. Uses conversation loop to handle Claude follow-ups automatically. 10 tests.
- **Frontend unit tests** (`frontend/src/__tests__/`): Vitest + React Testing Library. Tests all 8 components + utils. 68 tests.
- **Frontend responsive tests** (`frontend/tests/responsive/`): Playwright screenshot tests at 3 viewports (mobile/tablet/desktop). 15 tests.
- **Fixtures** in `tests/fixtures/` — Sample Tally XML/JSON responses for each report type.
- Test company: "Bharat Traders Pvt Ltd" (Electronics & Office Supplies trader, Maharashtra, FY Apr 2025–Mar 2026).

## Workflow Preferences

- **Always use skills** for all tasks — debugging, feature development, TDD, planning, code review, etc. Never skip skill invocation even for seemingly simple tasks. If there's even a 1% chance a skill applies, invoke it.
- **Prefer superpowers skills over feature-dev**: When both `superpowers:*` and `feature-dev:*` skills could apply, always use the superpowers variant first (e.g., `superpowers:brainstorming` over `feature-dev:feature-dev`, `superpowers:systematic-debugging` over ad-hoc debugging, `superpowers:test-driven-development` over writing tests directly).
- **Code review after every implementation**: After completing any implementation task (feature, bugfix, refactor), always run a code review using `superpowers:requesting-code-review` or the `code-review` agent. Never skip this step. Store review results in `docs/`.
- **Main agent = orchestrator only**: The main conversation agent should NEVER write implementation code directly. Always spawn subagents (via the Agent tool) for code changes, writing tests, and debugging. The main agent's role is to plan, dispatch subagents, review their output, and integrate results. This preserves context window for planning and coordination.
- **Persist artifacts in docs/**: Store code review results, implementation plans, and status tracking in `docs/` so they survive across sessions. Reference `docs/code-review-phase1-2.md` for current review status.

## Implementation Phases (Build Order)

1. **Tally Bridge Layer** — client, request_builder, response_parser, models, exceptions
2. **Agent Orchestrator & Tools** — tool definitions, query_agent with Claude tool-calling loop, orchestrator routing
3. **FastAPI Backend** — main app, chat/health/companies/reports endpoints
4. **React Frontend** — chat UI with inline charts and tables
5. **Advanced Features** — conversation memory, cached ledger list, GST reports, date-relative parsing, export, WhatsApp
