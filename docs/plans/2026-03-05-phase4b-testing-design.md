# Phase 4b: Automated Tests — Design Document

> **Created**: 2026-03-05
> **Status**: APPROVED

## Goal

Add comprehensive automated test coverage for the frontend (React components + responsiveness) and backend E2E pipeline (mock Claude + live Claude API).

## Current State

- 274 unit tests + 43 integration tests passing (backend only)
- 0 frontend tests, 0 E2E tests
- Frontend has 8 components, 1 context, 1 API client, 1 utils module
- `scripts/test_agent_live.py` exists for manual live testing but isn't a proper test suite

## Test Suites

### 1. Frontend Unit Tests (Vitest + React Testing Library)

**Infrastructure**:
- `vitest` + `@testing-library/react` + `@testing-library/user-event` + `@testing-library/jest-dom` + `jsdom`
- `vitest.config.ts` with jsdom environment
- Scripts: `"test": "vitest run"`, `"test:watch": "vitest"`

**Mocking strategy**:
- `api/client.ts` → `vi.mock()` per test
- `recharts` `ResponsiveContainer` → mock to render children directly (needs real DOM dimensions)
- `react-markdown` → light pass-through mock

**Test files** (`frontend/src/__tests__/`):

| File | Component | Key Tests |
|------|-----------|-----------|
| `QuickActions.test.tsx` | QuickActions | Renders 6 buttons, fires onSelect on click, respects disabled prop |
| `ChatInput.test.tsx` | ChatInput | Enter-to-send, Shift+Enter keeps newline, empty input blocked, disabled state |
| `DataTable.test.tsx` | DataTable | Renders headers/rows, column sorting (asc/desc), Indian number formatting, CSV export blob creation, empty rows returns null |
| `ChartRenderer.test.tsx` | ChartRenderer | Renders bar/line/pie/grouped_bar types, handles empty data, title displayed |
| `MessageBubble.test.tsx` | MessageBubble | User (blue/right) vs assistant (gray/left), error state (red), loading dots, renders DataTable when data present, renders ChartRenderer when chart present |
| `CompanySelector.test.tsx` | CompanySelector | Fetches on mount, auto-selects first company, dropdown onChange fires setCompany, returns null when empty |
| `Header.test.tsx` | Header | Health dot colors (green/red/gray), polls every 30s, tooltip text |
| `ChatWindow.test.tsx` | ChatWindow | Send message → loading → response, error handling (network error message), quick actions trigger send, session ID persistence, empty state renders welcome |
| `format.test.ts` | Utils | formatIndianNumber, formatINR, isNumericValue, generateId uniqueness |

**Estimated count**: ~40-50 tests

### 2. Frontend Responsive Tests (Playwright + Screenshots)

**Infrastructure**:
- Playwright test runner (already available via `.playwright-mcp/`)
- `playwright.config.ts` in `frontend/tests/` pointing at Vite dev server
- Baseline screenshots stored in `frontend/tests/responsive/__screenshots__/`
- Visual regression via `expect(page).toHaveScreenshot()`

**Viewports**:

| Name | Width × Height | Device |
|------|---------------|--------|
| mobile | 375 × 667 | iPhone SE |
| tablet | 768 × 1024 | iPad |
| desktop | 1280 × 800 | Standard laptop |

**Test scenarios** (each at all 3 viewports):

1. **Empty state** — welcome message + quick action buttons visible, nothing overflows
2. **Text message** — user bubble (right) + agent bubble (left) with plain text, no overflow
3. **Markdown response** — agent response with headers, lists, bold, code blocks — wraps properly
4. **Data table response** — table renders, horizontally scrollable on mobile, CSV button visible
5. **Chart response** — bar chart renders within container, ResponsiveContainer adapts to viewport
6. **Pie chart** — pie chart with legend, readable at all sizes
7. **Error state** — red error bubble, readable text
8. **Loading state** — animated dots visible

**Validation**: Screenshot comparison with `toHaveScreenshot()`. First run creates baseline images; subsequent runs compare pixel-by-pixel with configurable threshold.

**Run**: Requires frontend dev server running with mock data. Can use MSW (Mock Service Worker) or static mock responses to avoid needing real backend.

**Estimated count**: ~8 scenarios × 3 viewports = ~24 screenshot tests

### 3. Backend E2E Tests — Mock Claude API (`tests/e2e/`)

**Mock Claude API** (`tests/mocks/mock_claude_api.py`):

```python
class MockAnthropicClient:
    """Drop-in replacement for anthropic.AsyncAnthropic with queued responses."""
    def __init__(self, responses: list[dict]):
        self.responses = deque(responses)
        self.messages = MockMessages(self)
        self.call_log = []  # Record all calls for assertions

class MockMessages:
    async def create(self, **kwargs) -> Message:
        self.client.call_log.append(kwargs)
        return self.client.responses.popleft()
```

Each test provides a list of canned Claude responses that the mock returns in order. This allows deterministic testing of the full pipeline without API costs.

**Response factory helpers**:
- `make_classification_response(query_type, requires_chart)` — Returns a Claude message with JSON classification
- `make_tool_call_response(tool_name, tool_input)` — Returns a Claude message requesting a tool call
- `make_text_response(text)` — Returns a final text response
- `make_analysis_response(text, data)` — Returns analysis agent response

**Test structure** (`tests/e2e/`):
- `conftest.py` — FastAPI TestClient fixture, mock Claude client factory, mock Tally client (reuses `mock_tally_server.py`)
- `test_chat_pipeline.py`:

| Test | Flow |
|------|------|
| Greeting | classify → greeting → direct response (no Tally) |
| Simple lookup (trial balance) | classify → query_agent (tool call → execute → text) → response with data |
| Simple lookup (companies) | classify → query_agent (tool call → execute → text) → response |
| Comparison query | classify → query_agent → analysis_agent → chart_agent → response with data + chart |
| Trend query | classify → query_agent → analysis_agent → chart_agent → line chart response |
| Top-N query | classify → query_agent → analysis_agent → response with ranked data |
| Aggregation query | classify → query_agent → analysis_agent → response with summary |
| Clarification needed | classify → clarification → follow-up response |
| Tally connection error | query_agent tool call → TallyConnectionError → 503 response |
| Invalid Tally response | query_agent tool call → TallyResponseError → 502 response |
| Multi-turn conversation | 2 sequential chat requests with same session_id → context preserved |

**Patching strategy**: Patch `backend.agents.orchestrator.anthropic_client` and `backend.agents.query_agent.anthropic_client` module-level clients with mock instances.

**Estimated count**: ~10-12 tests

### 4. Backend E2E Live Tests (`tests/e2e_live/`)

**Gating**: `pytest.mark.skipif(not os.environ.get("RUN_LIVE_TESTS"))`. Also requires `ANTHROPIC_API_KEY` and reachable Tally instance.

**Conversation loop pattern**:
```python
async def run_until_final_response(orchestrator, client, session, initial_query, max_turns=3):
    """Send query, handle follow-ups until we get a final response."""
    query = initial_query
    for turn in range(max_turns):
        result = await orchestrator.process_query(query, client, session)
        if result["query_type"] != "clarification_needed":
            return result
        # Claude asked for clarification — provide a follow-up
        query = generate_followup(result["message"], initial_query)
    return result  # Return whatever we have after max turns
```

**Test structure** (`tests/e2e_live/`):
- `conftest.py` — Skip logic, TallyClient fixture (from CLI args `--host`/`--port`), Orchestrator + SessionStore fixtures
- `test_live_pipeline.py`:

| Test | Query | Assertions |
|------|-------|-----------|
| Greeting | "Hello!" | message is non-empty, query_type is greeting |
| List companies | "List all companies" | data is present with company names |
| Trial balance | "Show trial balance for this FY" | data has headers/rows, amounts are numeric |
| P&L | "What is the profit and loss?" | data present, has revenue/expense items |
| Balance sheet | "Show balance sheet" | data present |
| Receivables | "Show outstanding receivables" | data present with party names and amounts |
| Sales register | "Show sales register" | data present with voucher details |
| Top customers | "Top 5 customers by sales" | data has ≤5 items, sorted by amount |
| Sales vs purchases | "Compare sales and purchases this month" | response contains comparison data |
| Trend | "Monthly sales trend this FY" | response contains trend data or chart |
| Clarification | "Show me the balance" | expects clarification or reasonable response |

Each test uses `run_until_final_response()` to handle Claude follow-ups automatically.

**Run command**:
```bash
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host 172.26.104.48 --port 9000
```

Custom pytest args via `conftest.py` `pytest_addoption`.

**Estimated count**: ~10 tests

## Test Count Summary

| Suite | Tests | Runner | Requires |
|-------|-------|--------|----------|
| Frontend unit | ~45 | Vitest | Nothing |
| Frontend responsive | ~24 | Playwright | Dev server |
| Backend E2E (mock) | ~12 | pytest | Nothing |
| Backend E2E (live) | ~10 | pytest | Tally + API key + RUN_LIVE_TESTS |
| **Total new** | **~90** | | |
| **Total with existing** | **~407** | | 274 unit + 43 integration + ~90 new |

## File Structure

```
frontend/
├── vitest.config.ts              # NEW
├── src/
│   └── __tests__/
│       ├── setup.ts              # NEW — jsdom setup, global mocks
│       ├── QuickActions.test.tsx
│       ├── ChatInput.test.tsx
│       ├── DataTable.test.tsx
│       ├── ChartRenderer.test.tsx
│       ├── MessageBubble.test.tsx
│       ├── CompanySelector.test.tsx
│       ├── Header.test.tsx
│       ├── ChatWindow.test.tsx
│       └── format.test.ts
└── tests/
    └── responsive/
        ├── playwright.config.ts  # NEW
        ├── responsive.spec.ts    # NEW — screenshot tests
        └── __screenshots__/      # NEW — baseline images (gitignored initially)

tests/
├── mocks/
│   ├── mock_tally_server.py      # EXISTS
│   └── mock_claude_api.py        # NEW
├── e2e/
│   ├── conftest.py               # NEW
│   └── test_chat_pipeline.py     # NEW
└── e2e_live/
    ├── conftest.py               # NEW
    └── test_live_pipeline.py     # NEW
```

## Build Commands

```bash
# Frontend unit tests
cd frontend && npm test

# Frontend responsive tests (needs dev server running)
cd frontend && npx playwright test tests/responsive/

# Backend E2E (mock)
pytest tests/e2e/ -v

# Backend E2E (live)
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host <TALLY_IP> --port 9000

# All backend tests
pytest tests/ -v --ignore=tests/e2e_live/

# Everything except live
cd frontend && npm test && cd .. && pytest tests/ -v --ignore=tests/e2e_live/
```
