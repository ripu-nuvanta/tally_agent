# Mock Tally, Quick Actions & Eval Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mock Tally mode (built-in handler with Bharat Traders data), update quick action buttons, and add eval mock support with `--tally-mode` CLI flag.

**Architecture:** In-process mock handler in `backend/tally_bridge/mock_handler.py` intercepts `TallyClient.post_xml()` when `mock_mode=True`. Frontend toggle switches mode via `POST /api/tally-mode`. Eval collector uses `--tally-mode mock` flag and clicks the frontend toggle via Playwright before running scenarios.

**Tech Stack:** Python/FastAPI, React/TypeScript, Playwright, Vitest, pytest

**Design Spec:** `docs/plans/2026-03-12-enhancements-mock-tally-design.md`

**Note:** Deliverable 0 (Extract Phase 4) was already completed in this session — see commit `05a96f9`.

---

## Chunk 1: Quick Action Button Updates (Feature A)

### Task 1: Update QuickActions Component

**Files:**
- Modify: `frontend/src/components/QuickActions.tsx`
- Modify: `frontend/src/__tests__/QuickActions.test.tsx`

- [x] **Step 1: Update button text and remove Stock summary**

In `frontend/src/components/QuickActions.tsx`, replace the `QUICK_QUERIES` array:

```typescript
const QUICK_QUERIES = [
  "P&L last month",
  "Outstanding receivables",
  "Cash balance",
  "Top 10 customers",
  "Sales vs purchases last month",
];
```

- [x] **Step 2: Update test expectations**

In `frontend/src/__tests__/QuickActions.test.tsx`, update:

```typescript
const EXPECTED_QUERIES = [
  "P&L last month", "Outstanding receivables", "Cash balance",
  "Top 10 customers", "Sales vs purchases last month",
];

describe("QuickActions", () => {
  it("renders all 5 query buttons", () => {
    render(<QuickActions onSelect={() => {}} />);
    for (const query of EXPECTED_QUERIES) {
      expect(screen.getByRole("button", { name: query })).toBeInTheDocument();
    }
  });

  it("calls onSelect with the query text when clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} />);
    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).toHaveBeenCalledWith("Cash balance");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("calls onSelect with correct text for each button", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} />);
    for (const query of EXPECTED_QUERIES) {
      await user.click(screen.getByRole("button", { name: query }));
      expect(onSelect).toHaveBeenLastCalledWith(query);
    }
    expect(onSelect).toHaveBeenCalledTimes(EXPECTED_QUERIES.length);
  });

  it("disables all buttons when disabled prop is true", () => {
    render(<QuickActions onSelect={() => {}} disabled />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(5);
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("does not call onSelect when disabled button is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} disabled />);
    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
```

- [x] **Step 3: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All QuickActions tests PASS (5 tests)

- [x] **Step 4: Commit**

```bash
git add frontend/src/components/QuickActions.tsx frontend/src/__tests__/QuickActions.test.tsx
git commit -m "feat: update quick action buttons — last month, remove stock summary"
```

### Task 2: Update Eval Scenarios

**Files:**
- Modify: `tests/eval/scenarios/quick_actions.yaml`
- Modify: `tests/eval/scenarios/manual_test_regression.yaml`

- [x] **Step 1: Update quick_actions.yaml**

Replace full content:

```yaml
name: "Quick Action Buttons"
description: "Tests the 5 preset quick-action queries available in the UI. Each is a single-turn interaction."
tags: [quick_actions, single_query, ui_buttons]

turns:
  - query: "P&L last month"
    expect:
      has_data: true
      checks:
        - "Returns profit and loss data for last month"
        - "Date range corresponds to the previous calendar month"
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

  - query: "Top 10 customers"
    expect:
      query_type: top_n
      has_data: true
      checks:
        - "Lists up to 10 customers ranked by sales amount"
        - "Amounts are sorted in descending order"

  - query: "Sales vs purchases last month"
    expect:
      query_type: comparison
      has_data: true
      checks:
        - "Shows both total sales and total purchases for last month"
        - "Comparison or difference is mentioned"
```

- [x] **Step 2: Update manual_test_regression.yaml turn 1**

Change only the first turn — replace `"P&L this month"` with `"P&L last month"` and update checks:

```yaml
  - query: "P&L last month"
    expect:
      has_data: true
      checks:
        - "Returns profit and loss data for the previous calendar month"
        - "Date range is correct for last month (not full year)"
        - "Income and expense categories shown"
```

- [x] **Step 3: Commit**

```bash
git add tests/eval/scenarios/quick_actions.yaml tests/eval/scenarios/manual_test_regression.yaml
git commit -m "feat: update eval scenarios for new quick action button text"
```

### Task 3: Update Playwright Screenshots

**Files:**
- Modify: `frontend/tests/playwright/` (screenshot baselines will update automatically)

- [x] **Step 1: Run Playwright tests to update screenshots**

Run: `cd frontend && npm run test:playwright -- --update-snapshots`
Expected: Tests run, screenshots regenerated with new button text (5 buttons instead of 6).

- [x] **Step 2: Visually inspect screenshots**

Check `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/` for:
- Empty chat state shows 5 buttons (not 6)
- No "Stock summary" button visible
- Buttons say "last month" not "this month"
- No blank space, cutoffs, or layout issues

- [x] **Step 3: Commit**

```bash
git add frontend/tests/playwright/
git commit -m "test: update Playwright screenshots for new quick action buttons"
```

---

## Chunk 2: Backend Mock Tally Infrastructure

### Task 4: Add TALLY_MODE to Config

**Files:**
- Modify: `backend/config.py`
- Test: `tests/unit/test_config.py` (if exists, otherwise skip test — config is trivial)

- [x] **Step 1: Add TALLY_MODE setting**

In `backend/config.py`, add after `SESSION_TTL_MINUTES`:

```python
TALLY_MODE: str = "live"  # "live" or "mock"
```

- [x] **Step 2: Commit**

```bash
git add backend/config.py
git commit -m "feat: add TALLY_MODE config setting (default: live)"
```

### Task 5: Create Mock Handler

**Files:**
- Create: `backend/tally_bridge/mock_handler.py`
- Test: `tests/unit/test_mock_handler.py`

- [x] **Step 1: Write failing tests for mock handler**

Create `tests/unit/test_mock_handler.py`:

```python
"""Tests for the in-process mock Tally handler."""

import pytest
from backend.tally_bridge.mock_handler import mock_tally_request, REPORT_FIXTURES


class TestMockHandler:
    """Test pattern matching and fixture loading."""

    def test_report_fixtures_mapping_exists(self):
        """All expected report types are mapped."""
        expected = [
            "List of Companies", "Trial Balance", "CustomLedgerList",
            "Profit and Loss", "Balance Sheet", "Bills Receivable",
            "Bills Payable", "Stock Summary", "DayBookVchs",
            "SalesVchs", "PurchaseVchs", "LedgerVchs",
        ]
        for name in expected:
            assert name in REPORT_FIXTURES, f"Missing fixture for {name}"

    def test_company_list_request(self):
        xml = '<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "<COMPANY>" in result
        assert "Bharat Traders" in result

    def test_trial_balance_request(self):
        xml = '<ENVELOPE><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>Trial Balance</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result
        assert len(result) > 100  # Non-trivial response

    def test_profit_and_loss_request(self):
        xml = '<REPORTNAME>Profit and Loss</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_balance_sheet_request(self):
        xml = '<REPORTNAME>Balance Sheet</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_sales_register_request(self):
        xml = '<COLLECTION>SalesVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_purchase_register_request(self):
        xml = '<COLLECTION>PurchaseVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_day_book_request(self):
        xml = '<COLLECTION>DayBookVchs</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_bills_receivable_request(self):
        xml = '<REPORTNAME>Bills Receivable</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_stock_summary_request(self):
        xml = '<REPORTNAME>Stock Summary</REPORTNAME>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_ledger_list_request(self):
        xml = '<COLLECTION>CustomLedgerList</COLLECTION>'
        result = mock_tally_request(xml)
        assert "<ENVELOPE>" in result

    def test_unknown_request_returns_error(self):
        xml = '<ENVELOPE><BODY>Something Unknown</BODY></ENVELOPE>'
        result = mock_tally_request(xml)
        assert "Unknown request" in result

    def test_all_fixtures_return_valid_xml(self):
        """Every fixture response should start with < (valid XML)."""
        for report_name in REPORT_FIXTURES:
            xml = f'<REPORTNAME>{report_name}</REPORTNAME>'
            result = mock_tally_request(xml)
            assert result.strip().startswith("<"), f"Invalid XML for {report_name}"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mock_handler.py -v`
Expected: FAIL — `mock_handler` module does not exist

- [x] **Step 3: Implement mock handler**

Create `backend/tally_bridge/mock_handler.py`:

```python
"""In-process mock Tally handler.

Returns fixture XML data for Bharat Traders Pvt Ltd demo company.
Pattern-matches report names in XML request body and returns
corresponding fixture files. This is the single canonical mock
implementation — tests/mocks/mock_tally_server.py delegates to this.
"""

import os
from functools import lru_cache

FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures"
)

# Same mapping as tests/mocks/mock_tally_server.py — kept in sync
REPORT_FIXTURES: dict[str, str] = {
    "List of Companies": "company_list.xml",
    "Trial Balance": "trial_balance.xml",
    "CustomLedgerList": "ledger_list.xml",
    "Profit and Loss": "profit_and_loss.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_receivable.xml",
    "Stock Summary": "stock_summary.xml",
    "DayBookVchs": "day_book.xml",
    "SalesVchs": "sales_register.xml",
    "PurchaseVchs": "sales_register.xml",
    "LedgerVchs": "day_book.xml",
}

_ERROR_RESPONSE = (
    "<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>"
)


@lru_cache(maxsize=32)
def _load_fixture(filename: str) -> str:
    """Load a fixture file, cached for performance."""
    path = os.path.join(FIXTURES_DIR, filename)
    if not os.path.exists(path):
        return _ERROR_RESPONSE
    with open(path) as f:
        return f.read()


def mock_tally_request(xml_body: str) -> str:
    """Process an XML request and return mock fixture response.

    Args:
        xml_body: The raw XML request string (same as what TallyClient.post_xml sends)

    Returns:
        XML response string from fixture files
    """
    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in xml_body:
            return _load_fixture(fixture_file)
    return _ERROR_RESPONSE
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_mock_handler.py -v`
Expected: All 14 tests PASS

- [x] **Step 5: Commit**

```bash
git add backend/tally_bridge/mock_handler.py tests/unit/test_mock_handler.py
git commit -m "feat: add in-process mock Tally handler with fixture loading"
```

### Task 5b: Augment Fixture Files for Bharat Traders

**Files:**
- Create: `tests/fixtures/purchase_register.xml`
- Modify: `tests/fixtures/sales_register.xml` (expand to 16 invoices if needed)
- Modify: `tests/fixtures/day_book.xml` (expand to include more voucher types)
- Modify: `backend/tally_bridge/mock_handler.py` (update PurchaseVchs mapping)

The current fixtures are minimal. For mock Tally to behave realistically, the key fixture that needs creating is `purchase_register.xml` (currently PurchaseVchs maps to sales_register.xml which returns wrong data). The existing sales_register.xml and day_book.xml are sufficient for initial mock mode — they can be expanded later as needed when eval results show gaps.

- [x] **Step 1: Create purchase_register.xml**

Create `tests/fixtures/purchase_register.xml` with Bharat Traders purchase vouchers (structure matching sales_register.xml but with purchase data). Use the same XML structure as sales_register.xml but with purchase ledgers/parties from the TALLYPRIME_AGENT_PLAN.md spec.

- [x] **Step 2: Update mock handler mapping**

In `backend/tally_bridge/mock_handler.py`, change:
```python
"PurchaseVchs": "purchase_register.xml",  # was: "sales_register.xml"
```

- [x] **Step 3: Run mock handler tests**

Run: `pytest tests/unit/test_mock_handler.py -v`
Expected: All tests PASS (purchase register now returns purchase data)

- [x] **Step 4: Commit**

```bash
git add tests/fixtures/purchase_register.xml backend/tally_bridge/mock_handler.py
git commit -m "feat: add purchase_register fixture, fix PurchaseVchs mapping"
```

### Task 6: Add mock_mode to TallyClient

**Files:**
- Modify: `backend/tally_bridge/client.py`
- Test: `tests/unit/test_tally_client_mock.py`

- [x] **Step 1: Write failing tests**

Create `tests/unit/test_tally_client_mock.py`:

```python
"""Tests for TallyClient mock_mode switching."""

import pytest
from backend.tally_bridge.client import TallyClient


class TestTallyClientMockMode:
    def test_mock_mode_defaults_to_false(self):
        client = TallyClient()
        assert client.mock_mode is False

    def test_mock_mode_can_be_set(self):
        client = TallyClient()
        client.mock_mode = True
        assert client.mock_mode is True

    @pytest.mark.asyncio
    async def test_post_xml_mock_mode_returns_fixture(self):
        client = TallyClient()
        client.mock_mode = True
        xml = '<REPORTNAME>List of Companies</REPORTNAME>'
        result = await client.post_xml(xml)
        assert "Bharat Traders" in result
        await client.close()

    @pytest.mark.asyncio
    async def test_post_xml_mock_mode_unknown_request(self):
        client = TallyClient()
        client.mock_mode = True
        xml = '<REPORTNAME>NonexistentReport</REPORTNAME>'
        result = await client.post_xml(xml)
        assert "Unknown request" in result
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_mock_mode_returns_true(self):
        client = TallyClient()
        client.mock_mode = True
        result = await client.health_check()
        assert result is True
        await client.close()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tally_client_mock.py -v`
Expected: FAIL — `TallyClient` has no `mock_mode` attribute

- [x] **Step 3: Add mock_mode to TallyClient**

In `backend/tally_bridge/client.py`, modify the class:

```python
"""
Core async HTTP client for TallyPrime communication.
TallyPrime runs as an HTTP server. We POST XML requests and parse responses.
CONNECTION: http://<TALLY_HOST>:<TALLY_PORT> (default: localhost:9000)
"""
import httpx
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError
from backend.tally_bridge.request_builder import build_list_companies


class TallyClient:
    def __init__(self, host: str = "localhost", port: int = 9000):
        self.base_url = f"http://{host}:{port}"
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self.mock_mode: bool = False

    async def post_xml(self, xml_payload: str) -> str:
        if self.mock_mode:
            from backend.tally_bridge.mock_handler import mock_tally_request
            return mock_tally_request(xml_payload)
        try:
            response = await self._client.post(
                self.base_url,
                content=xml_payload,
                headers={"Content-Type": "text/xml; charset=utf-8"},
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
        except httpx.HTTPStatusError as e:
            raise TallyResponseError(f"Tally returned HTTP {e.response.status_code}")
        except httpx.TransportError as e:
            raise TallyConnectionError(
                f"Transport error communicating with TallyPrime at {self.base_url}: {e}"
            )

    async def close(self) -> None:
        await self._client.aclose()

    async def health_check(self) -> bool:
        try:
            result = await self.post_xml(build_list_companies())
            return "<COMPANY>" in result or "COMPANY" in result.upper()
        except (TallyConnectionError, TallyResponseError):
            return False
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_tally_client_mock.py -v`
Expected: All 5 tests PASS

- [x] **Step 5: Commit**

```bash
git add backend/tally_bridge/client.py tests/unit/test_tally_client_mock.py
git commit -m "feat: add mock_mode to TallyClient — routes to mock handler when active"
```

### Task 7: Refactor mock_tally_server.py to Delegate

**Files:**
- Modify: `tests/mocks/mock_tally_server.py`

- [x] **Step 1: Refactor to delegate to mock_handler**

Replace `tests/mocks/mock_tally_server.py`:

```python
"""
Lightweight HTTP server mimicking TallyPrime's behavior.
Delegates pattern-matching to backend.tally_bridge.mock_handler
for a single canonical implementation.
"""

from aiohttp import web
from backend.tally_bridge.mock_handler import mock_tally_request


async def handle_tally_request(request: web.Request) -> web.Response:
    body = await request.text()
    result = mock_tally_request(body)
    return web.Response(text=result, content_type="text/xml")


def create_mock_tally_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/", handle_tally_request)
    return app
```

- [x] **Step 2: Run existing integration and E2E tests to verify no regression**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/integration/ tests/e2e/ -v`
Expected: All existing tests PASS (mock server still works, now via mock_handler)

- [x] **Step 3: Commit**

```bash
git add tests/mocks/mock_tally_server.py
git commit -m "refactor: mock_tally_server delegates to canonical mock_handler"
```

### Task 8: Add Tally Mode API Endpoints

**Files:**
- Modify: `backend/api/models.py`
- Create: `backend/api/tally_mode.py`
- Modify: `backend/main.py`
- Modify: `backend/api/health.py`
- Test: `tests/unit/test_tally_mode_api.py`

- [x] **Step 1: Write failing tests**

Create `tests/unit/test_tally_mode_api.py`:

```python
"""Tests for tally-mode API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app
from backend.tally_bridge.client import TallyClient


@pytest.fixture
async def client():
    # Ensure clean state — create a mock-ready TallyClient
    tally_client = TallyClient()
    tally_client.mock_mode = False
    app.state.tally_client = tally_client
    from backend.agents.context import SessionStore
    app.state.session_store = SessionStore()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Cleanup — reset mock_mode
    app.state.tally_client.mock_mode = False
    await tally_client.close()


@pytest.mark.asyncio
class TestTallyModeAPI:
    async def test_get_tally_mode_default_live(self, client):
        resp = await client.get("/api/tally-mode")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    async def test_set_tally_mode_mock(self, client):
        resp = await client.post("/api/tally-mode", json={"mode": "mock"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "mock"

    async def test_set_tally_mode_live(self, client):
        # First set to mock, then back to live
        await client.post("/api/tally-mode", json={"mode": "mock"})
        resp = await client.post("/api/tally-mode", json={"mode": "live"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    async def test_set_tally_mode_invalid(self, client):
        resp = await client.post("/api/tally-mode", json={"mode": "invalid"})
        assert resp.status_code == 422

    async def test_get_mode_after_set(self, client):
        await client.post("/api/tally-mode", json={"mode": "mock"})
        resp = await client.get("/api/tally-mode")
        assert resp.json()["mode"] == "mock"

    async def test_health_includes_mode_when_mock(self, client):
        await client.post("/api/tally-mode", json={"mode": "mock"})
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "mock"
        assert body["tally_connected"] is True

    async def test_health_mode_none_when_live(self, client):
        # mock_mode is False (set in fixture) — health_check will fail
        # (no real Tally running) but mode should be None
        resp = await client.get("/api/health")
        body = resp.json()
        assert body.get("mode") is None
        # tally_connected will be False since no real Tally
        assert body["tally_connected"] is False
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tally_mode_api.py -v`
Expected: FAIL — `/api/tally-mode` endpoint does not exist

- [x] **Step 3: Add TallyModeRequest/Response models**

In `backend/api/models.py`, add at end:

```python
class TallyModeRequest(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        if v not in ("mock", "live"):
            raise ValueError("Mode must be 'mock' or 'live'")
        return v


class TallyModeResponse(BaseModel):
    mode: str
```

Also add `mode: str | None = None` to `HealthResponse`:

```python
class HealthResponse(BaseModel):
    status: str
    tally_connected: bool
    tally_url: str
    mode: str | None = None
```

- [x] **Step 4: Create tally_mode endpoint**

Create `backend/api/tally_mode.py`:

```python
"""Tally mode switching — toggle between live and mock Tally."""

from fastapi import APIRouter, Depends, Request

from backend.api.models import TallyModeRequest, TallyModeResponse
from backend.tally_bridge.client import TallyClient
from backend.api.dependencies import get_client

router = APIRouter()


@router.get("/tally-mode", response_model=TallyModeResponse)
async def get_tally_mode(client: TallyClient = Depends(get_client)) -> TallyModeResponse:
    return TallyModeResponse(mode="mock" if client.mock_mode else "live")


@router.post("/tally-mode", response_model=TallyModeResponse)
async def set_tally_mode(
    request: TallyModeRequest,
    client: TallyClient = Depends(get_client),
) -> TallyModeResponse:
    client.mock_mode = request.mode == "mock"
    return TallyModeResponse(mode=request.mode)
```

- [x] **Step 5: Update health endpoint to include mode**

In `backend/api/health.py`:

```python
"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import HealthResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(client: TallyClient = Depends(get_client)) -> HealthResponse:
    if client.mock_mode:
        return HealthResponse(
            status="healthy",
            tally_connected=True,
            tally_url="mock://bharat-traders",
            mode="mock",
        )
    connected = await client.health_check()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        tally_connected=connected,
        tally_url=client.base_url,
    )
```

- [x] **Step 6: Register route in main.py**

In `backend/main.py`, add import and router:

```python
from backend.api import chat, companies, health, reports, tally_mode
```

And after existing router registrations:

```python
app.include_router(tally_mode.router, prefix="/api")
```

Also initialize mock_mode from config in lifespan, after creating tally_client:

```python
app.state.tally_client = TallyClient(settings.TALLY_HOST, settings.TALLY_PORT)
app.state.tally_client.mock_mode = settings.TALLY_MODE == "mock"
```

- [x] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_tally_mode_api.py -v`
Expected: All 7 tests PASS

- [x] **Step 8: Run all backend tests to check for regressions**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v`
Expected: All existing tests still PASS

- [x] **Step 9: Commit**

```bash
git add backend/api/models.py backend/api/tally_mode.py backend/api/health.py backend/main.py tests/unit/test_tally_mode_api.py
git commit -m "feat: add /api/tally-mode endpoints and health mode indicator"
```

### Task 9: Integration Test — Mock Handler Through Parse Pipeline

**Files:**
- Create: `tests/integration/test_mock_tally_integration.py`

- [x] **Step 1: Write integration tests**

Create `tests/integration/test_mock_tally_integration.py`:

```python
"""Integration tests: mock_handler → response_parser full cycle.

Verifies that mock fixture XML responses parse correctly through
the same pipeline used for live Tally responses.
"""

import pytest
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries import masters, reports


@pytest.fixture
async def mock_client():
    client = TallyClient()
    client.mock_mode = True
    yield client
    await client.close()


@pytest.mark.asyncio
class TestMockTallyIntegration:
    async def test_list_companies(self, mock_client):
        companies = await masters.list_companies(mock_client)
        assert len(companies) >= 1
        names = [c.name for c in companies]
        assert any("Bharat" in n for n in names)

    async def test_trial_balance(self, mock_client):
        result = await reports.trial_balance(mock_client, "01-04-2025", "31-03-2026")
        assert result.headers
        assert len(result.rows) > 0

    async def test_profit_and_loss(self, mock_client):
        result = await reports.profit_and_loss(mock_client, "01-04-2025", "31-03-2026")
        assert result.headers
        assert len(result.rows) > 0

    async def test_balance_sheet(self, mock_client):
        result = await reports.balance_sheet(mock_client, "31-03-2026")
        assert result.headers
        assert len(result.rows) > 0

    async def test_stock_summary(self, mock_client):
        result = await reports.stock_summary(mock_client, "31-03-2026")
        assert result.headers
        assert len(result.rows) > 0

    async def test_ledger_list(self, mock_client):
        ledgers = await masters.list_ledgers(mock_client)
        assert len(ledgers) > 0
```

- [x] **Step 2: Run integration tests**

Run: `pytest tests/integration/test_mock_tally_integration.py -v`
Expected: All 6 tests PASS (fixture XML parses through real response_parser)

- [x] **Step 3: Commit**

```bash
git add tests/integration/test_mock_tally_integration.py
git commit -m "test: integration tests for mock Tally through parse pipeline"
```

---

## Chunk 3: Frontend Mock Tally Toggle

### Task 10: Add Frontend API and Types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [x] **Step 1: Add TypeScript types**

In `frontend/src/types/index.ts`, add at end:

```typescript
export interface TallyModeResponse {
  mode: "mock" | "live";
}

export interface TallyModeRequest {
  mode: "mock" | "live";
}
```

Also update `HealthResponse`:

```typescript
export interface HealthResponse {
  status: string;
  tally_connected: boolean;
  tally_url: string;
  mode?: "mock" | "live" | null;
}
```

- [x] **Step 2: Add API functions**

In `frontend/src/api/client.ts`, add imports and functions:

```typescript
import type {
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  HealthResponse,
  TallyModeRequest,
  TallyModeResponse,
} from "../types";

// ... existing code ...

export async function getTallyMode(): Promise<TallyModeResponse> {
  const { data } = await api.get<TallyModeResponse>("/tally-mode");
  return data;
}

export async function setTallyMode(mode: "mock" | "live"): Promise<TallyModeResponse> {
  const { data } = await api.post<TallyModeResponse>("/tally-mode", { mode });
  return data;
}
```

- [x] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat: add tally mode API types and client functions"
```

### Task 11: Add Toggle to Header Component

**Files:**
- Modify: `frontend/src/components/Header.tsx`
- Test: `frontend/src/__tests__/Header.test.tsx`

- [x] **Step 1: Update Header component**

Replace `frontend/src/components/Header.tsx`:

```typescript
import { useEffect, useState } from "react";
import { getHealth, getTallyMode, setTallyMode } from "../api/client";
import CompanySelector from "./CompanySelector";

export default function Header() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [tallyMode, setTallyModeState] = useState<"mock" | "live">("live");

  useEffect(() => {
    // Initialize tally mode from backend
    getTallyMode()
      .then((res) => setTallyModeState(res.mode))
      .catch(() => {});

    // Health polling
    const checkHealth = () => {
      getHealth()
        .then((res) => {
          setConnected(res.tally_connected);
          if (res.mode) setTallyModeState(res.mode);
        })
        .catch(() => setConnected(false));
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleMode = async () => {
    const newMode = tallyMode === "live" ? "mock" : "live";
    try {
      const res = await setTallyMode(newMode);
      setTallyModeState(res.mode);
      // Re-check health after mode switch
      getHealth()
        .then((res) => {
          setConnected(res.tally_connected);
        })
        .catch(() => setConnected(false));
    } catch {
      // Reconcile on error
      getTallyMode()
        .then((res) => setTallyModeState(res.mode))
        .catch(() => {});
    }
  };

  const isMock = tallyMode === "mock";

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
      <div className="flex items-center gap-3">
        <button
          onClick={handleToggleMode}
          data-testid="tally-mode-toggle"
          className="flex items-center gap-1.5 px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-50 transition-colors"
          title={isMock ? "Switch to Live Tally" : "Switch to Mock Tally"}
        >
          <div
            data-testid="tally-mode-indicator"
            className={`w-2 h-2 rounded-full ${
              isMock
                ? "bg-green-500"
                : connected === null
                  ? "bg-gray-300"
                  : connected
                    ? "bg-green-500"
                    : "bg-red-500"
            }`}
          />
          <span data-testid="tally-mode-label">
            {isMock ? "Mock Tally" : "Tally"}
          </span>
        </button>
        <CompanySelector />
      </div>
    </header>
  );
}
```

- [x] **Step 2: Add toggle tests to existing Header.test.tsx**

The existing `Header.test.tsx` uses `vi.mock("../api/client")` + `vi.mocked(api)` pattern with `SessionProvider` wrapper. **Preserve all 6 existing tests.** Add the new mock functions to `beforeEach` and append new toggle tests.

In `frontend/src/__tests__/Header.test.tsx`, update imports and beforeEach, then add new tests:

Add to imports:
```typescript
import userEvent from "@testing-library/user-event";
```

In the `beforeEach`, add after existing mocks:
```typescript
mockedApi.getTallyMode.mockResolvedValue({ mode: "live" });
mockedApi.setTallyMode.mockResolvedValue({ mode: "mock" });
```

Update existing `getHealth` mocks to include `mode: null`:
```typescript
mockedApi.getHealth.mockResolvedValue({
  status: "ok", tally_connected: true, tally_url: "http://localhost:9000", mode: null,
});
```

Add new tests inside the existing `describe("Header")` block:

```typescript
  it("shows Tally label in live mode", async () => {
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTestId("tally-mode-label")).toHaveTextContent("Tally");
  });

  it("shows Mock Tally label after toggle", async () => {
    vi.useRealTimers(); // userEvent needs real timers
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    expect(screen.getByTestId("tally-mode-label")).toHaveTextContent("Mock Tally");
    vi.useFakeTimers();
  });

  it("calls setTallyMode API on toggle click", async () => {
    vi.useRealTimers();
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    expect(mockedApi.setTallyMode).toHaveBeenCalledWith("mock");
    vi.useFakeTimers();
  });

  it("has correct data-testid attributes", async () => {
    await act(async () => {
      renderWithProvider();
    });
    expect(screen.getByTestId("tally-mode-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("tally-mode-indicator")).toBeInTheDocument();
    expect(screen.getByTestId("tally-mode-label")).toBeInTheDocument();
  });

  it("reconciles mode on toggle error", async () => {
    vi.useRealTimers();
    mockedApi.setTallyMode.mockRejectedValue(new Error("fail"));
    const user = userEvent.setup();
    await act(async () => {
      renderWithProvider();
    });
    await user.click(screen.getByTestId("tally-mode-toggle"));
    // Should call getTallyMode to reconcile (once on mount + once on error)
    expect(mockedApi.getTallyMode).toHaveBeenCalled();
    vi.useFakeTimers();
  });
```

**Important:** The existing Header now uses a `<button>` with `title` attributes for the toggle, so update existing tests that check `title` attributes (e.g., "Tally connected", "Tally disconnected", "Checking Tally connection...") to use `data-testid` or adjust the title prop on the toggle button to preserve backward compatibility. The simplest fix: keep the `title` attribute on the toggle button matching the existing test expectations based on connection state.

- [x] **Step 3: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All Header and QuickActions tests PASS

- [x] **Step 4: Run Playwright to update screenshots**

Run: `cd frontend && npm run test:playwright -- --update-snapshots`
Expected: Screenshots updated with new toggle button in header

- [x] **Step 5: Visually inspect Playwright screenshots**

Check header area in `frontend/tests/playwright/__screenshots__/` for:
- Toggle button visible with "Tally" label
- Green/red/gray dot present
- No layout overflow or misalignment

- [x] **Step 6: Commit**

```bash
git add frontend/src/components/Header.tsx frontend/src/__tests__/Header.test.tsx frontend/tests/playwright/
git commit -m "feat: add mock Tally toggle to Header with indicator and tests"
```

---

## Chunk 4: Eval Mock Support (Feature C)

### Task 12: Add --tally-mode to collect.py

**Files:**
- Modify: `tests/eval/collect.py`

- [x] **Step 1: Add CLI argument**

In `tests/eval/collect.py`, in the `main()` function's argparse section, add:

```python
parser.add_argument(
    "--tally-mode",
    choices=["mock", "live"],
    default="live",
    help="Tally mode: mock (uses built-in mock data) or live (real Tally)"
)
```

- [x] **Step 2: Add Playwright toggle action**

After the page loads and before running scenarios, add the toggle logic. Find the line `await page.wait_for_selector("textarea", timeout=30000)` and add after it:

```python
# Set tally mode via frontend toggle if mock
if args.tally_mode == "mock":
    toggle = page.get_by_test_id("tally-mode-toggle")
    label = page.get_by_test_id("tally-mode-label")
    current_label = await label.inner_text()
    if current_label != "Mock Tally":
        await toggle.click()
        await page.wait_for_function(
            '() => document.querySelector("[data-testid=tally-mode-label]")?.textContent === "Mock Tally"',
            timeout=5000,
        )
    print("Tally mode set to: mock")
```

- [x] **Step 3: Record tally_mode in transcript metadata**

In the transcript output dict, add `"tally_mode": args.tally_mode` alongside existing fields like `"scenario_name"`, `"timestamp"`, etc.

- [x] **Step 4: Skip live ground truth when mock**

Wrap the live ground truth collection block with:

```python
if args.tally_mode == "live" and args.host:
    # ... existing live ground truth collection ...
```

When `args.tally_mode == "mock"`, load mock golden data instead:

```python
if args.tally_mode == "mock":
    mock_golden_path = GOLDEN_DIR / "mock_golden.json"
    if mock_golden_path.exists():
        with open(mock_golden_path) as f:
            live_golden = json.load(f)
        print(f"Loaded mock golden data from {mock_golden_path}")
```

- [x] **Step 5: Commit**

```bash
git add tests/eval/collect.py
git commit -m "feat: add --tally-mode flag to eval collector with Playwright toggle"
```

### Task 13: Update judge.py for Mock Mode

**Files:**
- Modify: `tests/eval/judge.py`

- [x] **Step 1: Add tally_mode awareness**

In `judge.py`, when loading transcript data, read `tally_mode` from metadata:

```python
tally_mode = transcript.get("tally_mode", "live")
```

Pass this to ground truth loading so the judge uses correct golden data. No other changes needed — the judge already receives ground truth as a parameter.

- [x] **Step 2: Commit**

```bash
git add tests/eval/judge.py
git commit -m "feat: judge.py reads tally_mode from transcript metadata"
```

### Task 14: Create Mock Golden Data

**Files:**
- Create: `tests/eval/golden/mock_golden.json`
- Create: `scripts/generate_mock_golden.py`

- [x] **Step 1: Create generation script**

Create `scripts/generate_mock_golden.py`:

```python
"""Generate golden data from mock Tally handler for eval judging.

Usage:
    PYTHONPATH=. python scripts/generate_mock_golden.py
"""

import asyncio
import json
from pathlib import Path

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries import masters, reports


async def main():
    client = TallyClient()
    client.mock_mode = True

    golden = {}
    try:
        golden["trial_balance"] = (
            await reports.trial_balance(client, "01-04-2025", "31-03-2026")
        ).model_dump(mode="json")

        golden["profit_and_loss"] = (
            await reports.profit_and_loss(client, "01-04-2025", "31-03-2026")
        ).model_dump(mode="json")

        golden["balance_sheet"] = (
            await reports.balance_sheet(client, "31-03-2026")
        ).model_dump(mode="json")

        golden["stock_summary"] = (
            await reports.stock_summary(client, "31-03-2026")
        ).model_dump(mode="json")

        golden["bills_receivable"] = (
            await reports.bills_receivable(client, "31-03-2026")
        ).model_dump(mode="json")
    finally:
        await client.close()

    output_path = Path("tests/eval/golden/mock_golden.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(golden, f, indent=2)
    print(f"Mock golden data written to {output_path} ({len(golden)} reports)")


if __name__ == "__main__":
    asyncio.run(main())
```

- [x] **Step 2: Run the script to generate golden data**

Run: `PYTHONPATH=. python scripts/generate_mock_golden.py`
Expected: `tests/eval/golden/mock_golden.json` created with 5 report types

- [x] **Step 3: Commit**

```bash
git add scripts/generate_mock_golden.py tests/eval/golden/mock_golden.json
git commit -m "feat: add mock golden data generation for eval judging"
```

### Task 15: Create mock_tally_validation Eval Scenario

**Files:**
- Create: `tests/eval/scenarios/mock_tally_validation.yaml`

- [x] **Step 1: Create scenario**

Create `tests/eval/scenarios/mock_tally_validation.yaml`:

```yaml
name: "Mock Tally Validation"
description: "Validates mock Tally coverage across all report types. Run with --tally-mode mock."
tags: [mock_tally, validation, coverage]

turns:
  - query: "Show trial balance for FY 2025-26"
    expect:
      has_data: true
      checks:
        - "Returns trial balance with debit and credit columns"
        - "Account groups are listed"

  - query: "P&L last month"
    expect:
      has_data: true
      checks:
        - "Returns profit and loss data"
        - "Income and expense categories shown"

  - query: "Show balance sheet"
    expect:
      has_data: true
      checks:
        - "Returns balance sheet with assets and liabilities"

  - query: "Outstanding receivables"
    expect:
      has_data: true
      checks:
        - "Lists parties with outstanding amounts"

  - query: "Stock summary"
    expect:
      has_data: true
      checks:
        - "Lists stock items with quantities"

  - query: "Top 10 customers"
    expect:
      query_type: top_n
      has_data: true
      checks:
        - "Lists customers ranked by sales"
```

- [x] **Step 2: Commit**

```bash
git add tests/eval/scenarios/mock_tally_validation.yaml
git commit -m "feat: add mock_tally_validation eval scenario"
```

### Task 16: E2E Tests with Mock Mode

**Files:**
- Modify: `tests/e2e/test_chat_pipeline.py` (add mock mode test class)

- [x] **Step 1: Add mock mode E2E tests**

In `tests/e2e/test_chat_pipeline.py`, add a new test class at the end of the file:

Note: The existing E2E `conftest.py` provides an `e2e_client` fixture that yields `(async_client, set_responses, mock_clients)`. For mock Tally tests we need the async_client but can set mock_mode directly on `app.state.tally_client`.

```python
class TestChatPipelineMockTally:
    """E2E tests running the full pipeline with mock Tally mode."""

    @pytest.fixture(autouse=True)
    async def setup_mock_mode(self):
        """Switch to mock mode before tests, restore after."""
        from backend.main import app
        app.state.tally_client.mock_mode = True
        yield
        app.state.tally_client.mock_mode = False

    @pytest.mark.asyncio
    async def test_health_in_mock_mode(self, e2e_client):
        client, _, _ = e2e_client
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tally_connected"] is True
        assert body["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_companies_in_mock_mode(self, e2e_client):
        client, _, _ = e2e_client
        resp = await client.get("/api/companies")
        assert resp.status_code == 200
        companies = resp.json()["companies"]
        assert len(companies) >= 1

    @pytest.mark.asyncio
    async def test_tally_mode_toggle_endpoint(self, e2e_client):
        client, _, _ = e2e_client
        # GET mode
        resp = await client.get("/api/tally-mode")
        assert resp.json()["mode"] == "mock"  # set by fixture
        # Toggle to live and back
        resp = await client.post("/api/tally-mode", json={"mode": "live"})
        assert resp.json()["mode"] == "live"
        resp = await client.post("/api/tally-mode", json={"mode": "mock"})
        assert resp.json()["mode"] == "mock"
```

- [x] **Step 2: Run E2E tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/e2e/test_chat_pipeline.py::TestChatPipelineMockTally -v`
Expected: All 3 mock mode E2E tests PASS

- [x] **Step 3: Commit**

```bash
git add tests/e2e/test_chat_pipeline.py
git commit -m "test: E2E tests for chat pipeline with mock Tally mode"
```

### Task 17: Final Verification

- [x] **Step 1: Run ALL backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v`
Expected: All tests PASS, no regressions

- [x] **Step 2: Run ALL frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: All tests PASS

- [x] **Step 3: Run Playwright**

Run: `cd frontend && npm run test:playwright`
Expected: All tests PASS. Visually inspect screenshots.

- [x] **Step 4: Manual smoke test (optional)**

Start backend and frontend, verify:
1. Toggle button visible in header
2. Clicking toggle switches to "Mock Tally" with green indicator
3. Quick action buttons show correct text (5 buttons, "last month")
4. Sending a query in mock mode returns data

- [x] **Step 5: Final commit (if any remaining changes)**

```bash
git add -A
git commit -m "chore: final verification — all tests passing"
```
