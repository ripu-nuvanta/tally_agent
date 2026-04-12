# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TallyPrime AI Agent — an AI-powered chatbot that connects to a live TallyPrime instance (default: `localhost:9000`; also works over LAN), lets users ask natural language questions about accounting data, and returns answers with charts and tables.

**Stack**: Python (FastAPI) backend + React (Vite) frontend + Claude API (Anthropic SDK with tool-calling)
**Tally Version**: TallyPrime 7.0+ (native JSON support, XML preferred for stability)
**Implementation Plan**: See `TALLYPRIME_AGENT_PLAN.md` for the full spec and phased build order.

## Build & Run Commands

### Backend (Python)
```bash
# Install dependencies
uv sync --extra dev --extra langfuse --extra db  # or: pip install -r requirements.txt

# Run the FastAPI server (legacy mode — no auth, in-memory sessions)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run the FastAPI server (DB mode — auth + persistence, requires Postgres)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent JWT_SECRET=<32+ chars> uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Run Alembic migrations (DB mode only)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent PYTHONPATH=. python -m alembic upgrade head

# Run all unit tests (fast, no external deps)
pytest tests/unit/ -v

# Run a single test file
pytest tests/unit/test_request_builder.py -v

# Run a single test
pytest tests/unit/test_request_builder.py::test_trial_balance_xml_has_correct_dates -v

# Integration tests (needs mock Tally server)
pytest tests/integration/ -v

# E2E scenario tests (includes legacy + DB smoke tests)
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v

# DB integration tests (requires Postgres)
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent_test ANTHROPIC_API_KEY=test-key pytest tests/integration/test_auth_flow.py tests/integration/test_workspace_flow.py tests/integration/test_conversation_flow.py tests/e2e/test_db_smoke.py -v

# All backend tests (unit + integration + E2E mock)
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/

# All tests with coverage
pytest --cov=backend --cov-report=html

# Live E2E tests (needs real Tally + Claude API key, -s for stdout logging)
# ⚠️ EXPENSIVE: Uses real Claude API calls. NEVER run twice — always tee to log on first run.
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v -s --host <TALLY_IP> --port 9000 2>&1 | tee docs/e2e-live-results.log

# E2E live tests in mock mode (no real Tally needed, still needs ANTHROPIC_API_KEY)
# ⚠️ EXPENSIVE: Uses real Claude API calls. NEVER run twice — always tee to log on first run.
PYTHONPATH=. pytest tests/e2e_live/ -v -s --tally-mode mock 2>&1 | tee docs/e2e-live-mock-results.log

# Verify Tally connectivity
python scripts/test_tally_connection.py

# Live test: agent pipeline against real Tally (needs ANTHROPIC_API_KEY)
PYTHONPATH=. uv run python scripts/test_agent_live.py --host <TALLY_IP> --port 9000

# Seed test data into Tally
python scripts/seed_tally_data.py --host <TALLY_IP> --port 9000

# Eval framework & Playwright tests — PREREQUISITE: backend AND frontend must be running:
#   Terminal 1: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
#   Terminal 2: cd frontend && npm run dev   (Vite dev server on port 5173)
# ⚠️ EXPENSIVE: Uses real Claude API calls. NEVER run twice — always tee to log on first run.
# Results auto-saved to tests/eval/results/ (transcripts, screenshots, scores, report)
PYTHONPATH=. python tests/eval/collect.py --scenario all --frontend-url http://localhost:5173 2>&1 | tee docs/eval-collect.log
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d= -f2) PYTHONPATH=. python tests/eval/judge.py 2>&1 | tee docs/eval-judge.log
PYTHONPATH=. python tests/eval/report.py               # → tests/eval/results/report.html

# Run single eval scenario
# ⚠️ EXPENSIVE: Uses real Claude API calls. NEVER run twice — always tee to log on first run.
PYTHONPATH=. python tests/eval/collect.py --scenario manual_test_regression --frontend-url http://localhost:5173 2>&1 | tee docs/eval-collect-manual.log

# Eval via pytest (all-in-one)
# ⚠️ EXPENSIVE: Uses real Claude API calls. NEVER run twice — always tee to log on first run.
RUN_EVAL_TESTS=1 PYTHONPATH=. pytest tests/eval/test_eval.py -v -s 2>&1 | tee docs/eval-pytest.log

# Generate golden fixtures from live Tally
PYTHONPATH=. python tests/eval/generate_golden.py --host <TALLY_IP> --port 9000
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev                          # Vite dev server (legacy mode)
VITE_DB_MODE=true npm run dev        # Vite dev server (DB mode — auth + sidebar)
npm run build                        # Production build
npm test                             # Vitest unit tests (116 tests)
npm run test:watch                   # Vitest in watch mode
npm run test:playwright              # Playwright visual tests (39 tests: responsive + eval-visual × 3 viewports)
                                     # PREREQUISITE: backend must be running (uvicorn on port 8000)

# IMPORTANT: To force-regenerate Playwright screenshots, DELETE the __screenshots__
# directory first. Playwright's pixel-diff threshold can hide stale content.
rm -rf tests/playwright/__screenshots__ && npm run test:playwright -- --update-snapshots
```

## Architecture

### Three-Layer Backend

1. **Tally Bridge** (`backend/tally_bridge/`) — HTTP client that communicates with TallyPrime's XML/JSON API (default endpoint `localhost:9000`; also works across the LAN). Core modules:
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
   - `GET /api/companies` — List loaded Tally companies (legacy mode)
   - `GET /api/reports/{name}` — Direct report access
   - DB mode adds: `POST /api/auth/{register,login,refresh,logout}`, `GET /api/auth/me`, workspace CRUD (`/api/workspaces`), conversation CRUD (`/api/workspaces/:id/conversations`), `GET /api/usage`

4. **Database Layer** (`backend/db/`) — PostgreSQL persistence (Set A1, optional via `DATABASE_URL`):
   - `engine.py` — Async SQLAlchemy engine + session factory
   - `models.py` — ORM models: User, Workspace, Conversation, Message, UsageLog
   - `migrations/` — Alembic migrations

5. **Agent Registry** (`backend/agents/registry.py`) — Pluggable agent types keyed by `workspace.agent_type`. Currently registers "tally" → `Orchestrator`. `BaseAgent` interface in `backend/agents/base.py`.

### Agent Pipeline Flow

```
User query → Orchestrator (classify) → Query Agent (fetch from Tally via tools)
  → Analysis Agent (if comparison/trend/top-N) → Chart Agent (if visual needed)
  → Final NL response with optional data table and chart spec
```

### Frontend (React + Vite + Tailwind + Recharts)

Chat-based UI at `frontend/src/`. Two modes controlled by `VITE_DB_MODE`:
- **Legacy mode** (default): `SessionProvider` → `Header` + `ChatWindow`. No auth, no sidebar.
- **DB mode** (`VITE_DB_MODE=true`): `BrowserRouter` + `AuthProvider` → `LoginPage`/`RegisterPage` (public) or `ChatApp` (protected: `Header` + `Sidebar` + `ChatWindow`).

Key components: `ChatWindow`, `MessageBubble` (renders text/table/chart inline), `ChartRenderer` (bar/line/pie via Recharts), `DataTable` (sortable with CSV export), `QuickActions` (preset query buttons), `Sidebar` (conversation list grouped by workspace), `ConnectCompanyModal`, `UserMenu`.

## Key Technical Conventions

- **Dates**: Tally expects DD-MM-YYYY format. Indian Financial Year = April 1 to March 31. Quarters: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.
- **Currency**: Use Indian comma formatting (₹12,34,567.00). Negative = outflow/debit, Positive = inflow/credit (Tally convention).
- **XML requests**: Preferred over JSON for Tally communication — more stable and documented across versions. Use `xml.etree.ElementTree` for parsing.
- **Claude models**: `claude-sonnet-4-6` for query/analysis agents, `claude-haiku-4-5-20251001` for orchestrator classification, `claude-opus-4-6` for eval judge.
- **Session management**: Two modes — **Legacy** (in-memory dict, session_id → conversation history, TTL 60 min, 20 message limit) and **DB mode** (Postgres-backed, persistent conversations, per-workspace config). Controlled by `DATABASE_URL` env var.
- **Tally Bridge is READ-ONLY** — no import/write operations except the seed data script.
- **Configuration**: All settings via `.env` file loaded by `pydantic_settings.BaseSettings` in `backend/config.py`.

## Environment Variables

```
TALLY_HOST, TALLY_PORT (default: localhost:9000)
ANTHROPIC_API_KEY
CLAUDE_MODEL (default: claude-sonnet-4-6)
CLAUDE_CLASSIFIER_MODEL (default: claude-haiku-4-5-20251001)
EVAL_JUDGE_MODEL (default: claude-opus-4-6)
APP_HOST, APP_PORT (default: 0.0.0.0:8000)
VITE_API_URL (default: http://localhost:8000)

# DB mode (Set A1) — all optional, app runs in legacy mode without them
DATABASE_URL                         # e.g. postgresql+asyncpg://user:pass@localhost/tallyagent
JWT_SECRET                           # minimum 32 chars, required when DATABASE_URL is set
JWT_ACCESS_TOKEN_EXPIRY_MINUTES      # default: 30
JWT_REFRESH_TOKEN_EXPIRY_DAYS        # default: 7
VITE_DB_MODE=true                    # frontend: enables auth pages + sidebar (omit for legacy)
TEST_DATABASE_URL                    # for DB integration tests (separate DB recommended)
```

## Testing

- **Unit tests** (`tests/unit/`): Pure logic, no I/O. Test request XML construction, response parsing, date utils, currency formatting, mock handler, auth utils, pricing, DB models. 760 tests.
- **Integration tests** (`tests/integration/`): Use mock Tally HTTP server (`tests/mocks/mock_tally_server.py`) built with aiohttp. Tests full request→parse→return cycle + mock format parity. Also includes DB integration tests (auth flow, workspace CRUD, conversation persistence) — these require `TEST_DATABASE_URL`. 120 + 9 DB tests.
- **E2E tests** (`tests/e2e/`): Full NL query → agent → Tally → response pipeline. Uses mock Claude API (`tests/mocks/mock_claude_api.py`) to avoid API costs. Includes legacy smoke tests (3) and DB smoke tests (6, require `TEST_DATABASE_URL`). 20 + 9 tests.
- **E2E live tests** (`tests/e2e_live/`): End-to-end against real Tally + real Claude API. Gated by `RUN_LIVE_TESTS=1` env var OR `--tally-mode mock`. In mock mode, uses built-in mock handler (no real Tally needed, still needs Claude API key). 19 tests.
- **Eval tests** (`tests/eval/`): Two-phase eval framework (collect → judge → report). Playwright drives multi-turn conversations against real frontend, LLM-as-a-judge scores responses across 5 dimensions (factual, quality, coherence, error handling, chart quality). 8 scenarios, 49 turns. Gated by `RUN_EVAL_TESTS=1`. Run standalone: `collect.py` → `judge.py` → `report.py`. Mock mode: `--tally-mode mock` auto-selects `*_mock.yaml` scenario variants when available.
- **Frontend unit tests** (`frontend/src/__tests__/`): Vitest + React Testing Library. Tests all components + utils. 237 tests.
- **Frontend Playwright tests** (`frontend/tests/playwright/`): Visual tests — responsive (5 page states × 3 viewports) + eval-visual (8 fixtures × 3 viewports) + db-mode (21 specs × 3 viewports, 11 skipped for viewport-specific) = 52 pass + 11 skip. **IMPORTANT: After running Playwright tests, the MAIN AGENT must visually inspect screenshots from ALL viewports** in `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/` before reporting pass/fail. Check for: blank space, content cutoff, sidebar/header overlap, missing text/tables/charts, unreadable elements. A test suite reporting "N passed" is NOT sufficient — screenshots must be visually verified. **Never delegate screenshot review to a subagent** — subagents cannot see images. The main orchestrating agent must use the Read tool on the PNG files itself.
- **Playwright test design**: Before writing Playwright specs, enumerate a `component × state × viewport` matrix. Cover ALL visually distinct states (e.g., voucher: draft/pending/written/discarded, sidebar: active/collapsed/empty, header: live/demo badge). Each state needs a mock data variant and separate screenshot. Add content assertions (`expect(locator).toHaveText(...)`) BEFORE `toHaveScreenshot()` — screenshots catch regressions but assertions catch functional bugs.
- **Playwright visual checklist**: Every `toHaveScreenshot()` call MUST be preceded by a `// VISUAL CHECKLIST:` comment block describing what the reviewer should verify in the screenshot: layout elements, specific text, colors/highlights, spacing/alignment, and what should NOT be visible. This guides the main agent's manual screenshot review and makes expected behavior explicit. Example:
  ```typescript
  // VISUAL CHECKLIST:
  // - Header: "TallyPrime AI | Trial Balance April" first line
  // - Subtitle: "Bharat Traders ● Live" below chat title
  // - Sidebar: BHARAT TRADERS has bg-blue-50 highlight
  // - NOT visible: no overlap between sidebar and chat content
  await expect(page).toHaveScreenshot("chat-with-header.png");
  ```
- **Playwright screenshot regeneration**: Only delete `frontend/tests/playwright/__screenshots__/` for the specific test file being regenerated (e.g., `__screenshots__/*/db-mode.spec.ts/`), NOT the entire directory. Deleting everything removes responsive + eval-visual baselines that require a different frontend mode to regenerate.
- **Fixtures** in `tests/fixtures/` — Sample Tally XML/JSON responses for each report type.
- Test company: "Bharat Traders Pvt Ltd" (Electronics & Office Supplies trader, Maharashtra, FY Apr 2025–Mar 2026).

## Workflow Preferences

- **Always use skills** for all tasks — debugging, feature development, TDD, planning, code review, etc. Never skip skill invocation even for seemingly simple tasks. If there's even a 1% chance a skill applies, invoke it.
- **Prefer superpowers skills over feature-dev**: When both `superpowers:*` and `feature-dev:*` skills could apply, always use the superpowers variant first (e.g., `superpowers:brainstorming` over `feature-dev:feature-dev`, `superpowers:systematic-debugging` over ad-hoc debugging, `superpowers:test-driven-development` over writing tests directly).
- **Code review after every implementation**: After completing any implementation task (feature, bugfix, refactor), always run a code review using `superpowers:requesting-code-review` or the `code-review` agent. Never skip this step. Store review results in `docs/`.
- **Main agent = orchestrator only**: The main conversation agent should NEVER write implementation code directly. Always spawn subagents (via the Agent tool) for code changes, writing tests, and debugging. The main agent's role is to plan, dispatch subagents, review their output, and integrate results. This preserves context window for planning and coordination.
- **Persist artifacts in docs/**: Store code review results, implementation plans, and status tracking in `docs/` so they survive across sessions. Reference `docs/code-review-phase1-2.md` for current review status.

## Implementation Phases (Build Order)

1. **Tally Bridge Layer** ✅ — client, request_builder, response_parser, models, exceptions
2. **Agent Orchestrator & Tools** ✅ — tool definitions, query_agent with Claude tool-calling loop, orchestrator routing
3. **FastAPI Backend** ✅ — main app, chat/health/companies/reports endpoints
4. **React Frontend** ✅ — chat UI with inline charts and tables
5. **Eval Framework** ✅ — two-phase eval (collect via Playwright → judge via LLM → HTML report), 8 scenarios, 49 turns
6. **Mock Tally & Demo Mode** ✅ — built-in mock handler, demo toggle, e2e_live mock mode
7. **Enriched Mock Data** ✅ — Fixture generator with complete Bharat Traders seed data, date-aware mock handler, 4 mock eval scenarios, 71 format parity tests
8. **Advanced Features** — conversation memory, cached ledger list, GST reports, ~~date-relative parsing~~ ✅, export, WhatsApp
