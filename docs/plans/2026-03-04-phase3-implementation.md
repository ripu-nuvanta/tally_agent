# Phase 3: FastAPI Backend — Implementation Plan

> **Status: COMPLETE** — 2026-03-04. 317 tests passing (275 unit + 43 integration), 96% coverage.

**Goal:** Wire the existing orchestrator + tally_bridge into FastAPI REST endpoints (chat, health, companies, reports).

**Architecture:** Flat router pattern with FastAPI dependency injection. App-level TallyClient singleton managed via lifespan context manager. Custom exception handlers for consistent error responses.

**Tech Stack:** FastAPI, uvicorn, Pydantic v2 (already in use), httpx (already in use)

## Completion Summary

| Task | Status | Commit |
|------|--------|--------|
| Task 1: Add dependencies | ✅ | `fffe913` |
| Task 2: API models | ✅ | `f0bd53d` |
| Task 3: Dependencies module | ✅ | `f0c14c0` |
| Task 4: Health endpoint | ✅ | `19268be` |
| Task 5: Companies endpoint | ✅ | `af0bd23` |
| Task 6: Reports endpoint | ✅ | `2c635e2` |
| Task 7: Chat endpoint | ✅ | `9e6cf56` |
| Task 8: Main app + lifespan | ✅ | `0e147f5` |
| Task 9: Full test verification | ✅ | `4cb34c6` |
| Task 10: Update docs/memory | ✅ | `3a7c047` |
| Task 11: API integration tests | ✅ | `a41c250`, `c658849` |

### Code Review Results
- **C1 (getattr dispatch):** Left as-is — safe because name is validated against hardcoded set, and `getattr` is more mockable than dict references.
- **C2 (inconsistent error format):** Fixed — moved empty message check to Pydantic `field_validator`.
- **I2 (no logging in 500 handler):** Fixed — added `logger.exception()`.
- **I1 (X-Request-ID middleware):** Deferred to hardening pass.
- **I4 (CORS credentials + wildcard):** Acceptable for MVP, lock down before deployment.

### Integration Tests (Task 11)
7 tests in `tests/integration/test_api_endpoints.py` — full HTTP → FastAPI → mock Tally → parsed JSON:
- `GET /api/health` — healthy status
- `GET /api/companies` — parsed company list
- `GET /api/reports/trial_balance` — date-range report
- `GET /api/reports/balance_sheet` — as-on-date report
- `GET /api/reports/day_book` — voucher report
- `GET /api/reports/bills_receivable` — outstanding bills
- `GET /api/reports/nonexistent` — 400 error

Uses `httpx.AsyncClient` with `ASGITransport` (same event loop as aiohttp mock server).

### Deviations from Plan
- Reports endpoint uses `getattr()` instead of dict-based function dispatch (better mockability).
- `test_main.py` uses `importlib.reload` with patcher for proper lifespan handling.
- Added CORS headers test and route registration test (not in original plan).
- Integration tests use minimal FastAPI app with dependency overrides instead of importing `backend.main.app` (avoids lifespan/event loop issues).

---

### Task 1: Add FastAPI and uvicorn dependencies

**Files:**
- Modify: `pyproject.toml:6-12`

**Step 1: Add dependencies**

Add `fastapi>=0.115` and `uvicorn>=0.34` to the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "anthropic>=0.84.0",
    "fastapi>=0.115",
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
    "uvicorn>=0.34",
]
```

Also add `httpx[cli]` to dev dependencies for `TestClient` async support:

```toml
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "aiohttp>=3.9",
    "pytest-aiohttp>=1.0",
    "httpx[cli]>=0.27",
]
```

**Step 2: Install**

Run: `uv sync --all-extras`
Expected: All packages install successfully, lock file updates.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add fastapi and uvicorn dependencies"
```

---

### Task 2: Create API models (request/response Pydantic models)

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/models.py`
- Test: `tests/unit/test_api_models.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_models.py`:

```python
"""Tests for API request/response models."""

from backend.api.models import (
    ChatRequest,
    ChatResponse,
    ChartSpec,
    ErrorResponse,
    HealthResponse,
    CompaniesResponse,
    CompanyItem,
    ReportResponse,
)


def test_chat_request_minimal():
    req = ChatRequest(message="What is my sales total?")
    assert req.message == "What is my sales total?"
    assert req.session_id is None
    assert req.company is None


def test_chat_request_full():
    req = ChatRequest(message="Hello", session_id="abc-123", company="Test Co")
    assert req.session_id == "abc-123"
    assert req.company == "Test Co"


def test_chat_response_minimal():
    resp = ChatResponse(message="Your sales are ₹10,000", session_id="abc")
    assert resp.data is None
    assert resp.chart is None


def test_chat_response_with_chart():
    chart = ChartSpec(
        chart_type="bar",
        title="Sales",
        data=[{"name": "Q1", "value": 100}],
    )
    resp = ChatResponse(message="Here's a chart", chart=chart, session_id="abc")
    assert resp.chart.chart_type == "bar"
    assert resp.chart.config is None


def test_health_response():
    resp = HealthResponse(status="healthy", tally_connected=True, tally_url="http://localhost:9000")
    assert resp.tally_connected is True


def test_companies_response():
    resp = CompaniesResponse(companies=[CompanyItem(name="Test Co")])
    assert len(resp.companies) == 1


def test_report_response():
    resp = ReportResponse(
        headers=["Account", "Debit", "Credit"],
        rows=[["Cash", 1000, 0]],
    )
    assert len(resp.headers) == 3
    assert len(resp.rows) == 1


def test_error_response():
    resp = ErrorResponse(error="Tally unreachable")
    assert resp.detail is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.api'`

**Step 3: Write implementation**

Create `backend/api/__init__.py` (empty file).

Create `backend/api/models.py`:

```python
"""Request and response models for the FastAPI endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    company: str | None = None


class ChartSpec(BaseModel):
    chart_type: str
    title: str
    data: list[dict[str, Any]]
    config: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    message: str
    data: dict[str, Any] | None = None
    chart: ChartSpec | None = None
    session_id: str


class HealthResponse(BaseModel):
    status: str
    tally_connected: bool
    tally_url: str


class CompanyItem(BaseModel):
    name: str


class CompaniesResponse(BaseModel):
    companies: list[CompanyItem]


class ReportResponse(BaseModel):
    headers: list[str]
    rows: list[list[Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_models.py -v`
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/__init__.py backend/api/models.py tests/unit/test_api_models.py
git commit -m "feat(api): add request/response Pydantic models"
```

---

### Task 3: Create dependencies module

**Files:**
- Create: `backend/api/dependencies.py`
- Test: `tests/unit/test_api_dependencies.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_dependencies.py`:

```python
"""Tests for FastAPI dependency functions."""

from unittest.mock import MagicMock

from backend.api.dependencies import get_client, get_session_store
from backend.tally_bridge.client import TallyClient
from backend.agents.context import SessionStore


def test_get_client_returns_client_from_app_state():
    mock_request = MagicMock()
    mock_request.app.state.tally_client = TallyClient("localhost", 9000)
    result = get_client(mock_request)
    assert isinstance(result, TallyClient)


def test_get_session_store_returns_store_from_app_state():
    mock_request = MagicMock()
    mock_request.app.state.session_store = SessionStore(ttl_minutes=60)
    result = get_session_store(mock_request)
    assert isinstance(result, SessionStore)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_dependencies.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `backend/api/dependencies.py`:

```python
"""FastAPI dependency functions for injecting shared resources."""

from fastapi import Request

from backend.agents.context import SessionStore
from backend.tally_bridge.client import TallyClient


def get_client(request: Request) -> TallyClient:
    """Return the app-level TallyClient singleton."""
    return request.app.state.tally_client


def get_session_store(request: Request) -> SessionStore:
    """Return the app-level SessionStore singleton."""
    return request.app.state.session_store
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_dependencies.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/dependencies.py tests/unit/test_api_dependencies.py
git commit -m "feat(api): add dependency injection functions"
```

---

### Task 4: Create health endpoint

**Files:**
- Create: `backend/api/health.py`
- Test: `tests/unit/test_api_health.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_health.py`:

```python
"""Tests for GET /api/health endpoint."""

import pytest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.health import router
from backend.api.dependencies import get_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.base_url = "http://localhost:9000"
    return client


def test_health_tally_connected(app, mock_client):
    mock_client.health_check.return_value = True
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["tally_connected"] is True
    assert "tally_url" in body


def test_health_tally_disconnected(app, mock_client):
    mock_client.health_check.return_value = False
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["tally_connected"] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_health.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `backend/api/health.py`:

```python
"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import HealthResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(client: TallyClient = Depends(get_client)) -> HealthResponse:
    connected = await client.health_check()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        tally_connected=connected,
        tally_url=client.base_url,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_health.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/health.py tests/unit/test_api_health.py
git commit -m "feat(api): add GET /api/health endpoint"
```

---

### Task 5: Create companies endpoint

**Files:**
- Create: `backend/api/companies.py`
- Test: `tests/unit/test_api_companies.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_companies.py`:

```python
"""Tests for GET /api/companies endpoint."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.companies import router
from backend.api.dependencies import get_client
from backend.tally_bridge.models import Company


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def mock_client():
    return AsyncMock()


def test_companies_returns_list(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    with patch("backend.api.companies.list_companies", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [Company(name="Test Co"), Company(name="Other Co")]
        with TestClient(app) as tc:
            resp = tc.get("/api/companies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["companies"]) == 2
    assert body["companies"][0]["name"] == "Test Co"


def test_companies_empty(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    with patch("backend.api.companies.list_companies", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        with TestClient(app) as tc:
            resp = tc.get("/api/companies")
    assert resp.status_code == 200
    assert resp.json()["companies"] == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_companies.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/api/companies.py`:

```python
"""Companies endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import CompaniesResponse, CompanyItem
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.masters import list_companies

router = APIRouter()


@router.get("/companies", response_model=CompaniesResponse)
async def get_companies(
    client: TallyClient = Depends(get_client),
) -> CompaniesResponse:
    companies = await list_companies(client)
    return CompaniesResponse(
        companies=[CompanyItem(name=c.name) for c in companies],
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_companies.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/companies.py tests/unit/test_api_companies.py
git commit -m "feat(api): add GET /api/companies endpoint"
```

---

### Task 6: Create reports endpoint

**Files:**
- Create: `backend/api/reports.py`
- Test: `tests/unit/test_api_reports.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_reports.py`:

```python
"""Tests for GET /api/reports/{name} endpoint."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.reports import router
from backend.api.dependencies import get_client
from backend.tally_bridge.models import ReportResponse as TallyReportResponse, OutstandingBill
from datetime import date


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def mock_client():
    return AsyncMock()


def test_trial_balance(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    tally_resp = TallyReportResponse(
        report_name="Trial Balance",
        company="Test",
        rows=[{"account_name": "Cash", "debit_amount": 1000, "credit_amount": 0, "closing_balance": 1000}],
    )
    with patch("backend.api.reports.reports.trial_balance", new_callable=AsyncMock) as mock_tb:
        mock_tb.return_value = tally_resp
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/trial_balance?from_date=01-04-2025&to_date=31-03-2026")
    assert resp.status_code == 200
    body = resp.json()
    assert "headers" in body
    assert "rows" in body
    assert len(body["rows"]) == 1


def test_balance_sheet(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    tally_resp = TallyReportResponse(
        report_name="Balance Sheet",
        company="Test",
        rows=[{"group_name": "Current Assets", "amount": 50000}],
    )
    with patch("backend.api.reports.reports.balance_sheet", new_callable=AsyncMock) as mock_bs:
        mock_bs.return_value = tally_resp
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/balance_sheet?as_on_date=31-03-2026")
    assert resp.status_code == 200


def test_bills_receivable(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    bills = [
        OutstandingBill(
            party_name="Customer A", bill_number="INV-001",
            bill_date=date(2025, 7, 1), amount=10000, pending_amount=10000,
        ),
    ]
    with patch("backend.api.reports.reports.bills_receivable", new_callable=AsyncMock) as mock_br:
        mock_br.return_value = bills
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/bills_receivable?as_on_date=31-03-2026")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 1


def test_stock_summary(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    stock_data = [{"item_name": "Widget", "quantity": 100, "rate": 50, "value": 5000}]
    with patch("backend.api.reports.reports.stock_summary", new_callable=AsyncMock) as mock_ss:
        mock_ss.return_value = stock_data
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/stock_summary?as_on_date=31-03-2026")
    assert resp.status_code == 200


def test_invalid_report_name(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/reports/nonexistent?from_date=01-04-2025&to_date=31-03-2026")
    assert resp.status_code == 400


def test_missing_required_dates(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    with TestClient(app) as tc:
        resp = tc.get("/api/reports/trial_balance")
    assert resp.status_code == 422  # FastAPI validation error


def test_day_book(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    vouchers = [
        {"date": "20250701", "voucher_type": "Sales", "voucher_number": "S-001",
         "party_name": "Customer A", "amount": 10000},
    ]
    with patch("backend.api.reports.vouchers.day_book", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = vouchers
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/day_book?from_date=01-04-2025&to_date=31-03-2026")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 1


def test_sales_register(app, mock_client):
    app.dependency_overrides[get_client] = lambda: mock_client
    vouchers = [{"date": "20250701", "voucher_type": "Sales", "amount": 5000}]
    with patch("backend.api.reports.vouchers.sales_register", new_callable=AsyncMock) as mock_sr:
        mock_sr.return_value = vouchers
        with TestClient(app) as tc:
            resp = tc.get("/api/reports/sales_register?from_date=01-04-2025&to_date=31-03-2026")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_reports.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/api/reports.py`:

```python
"""Reports endpoint — direct access to Tally reports bypassing the agent pipeline."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_client
from backend.api.models import ReportResponse
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries import reports, vouchers

router = APIRouter()

# Reports that take from_date + to_date
_DATE_RANGE_REPORTS = {
    "trial_balance": reports.trial_balance,
    "profit_and_loss": reports.profit_and_loss,
}

# Reports that take as_on_date
_AS_ON_DATE_REPORTS = {
    "balance_sheet": reports.balance_sheet,
    "bills_receivable": reports.bills_receivable,
    "bills_payable": reports.bills_payable,
    "stock_summary": reports.stock_summary,
}

# Voucher reports that take from_date + to_date
_VOUCHER_REPORTS = {
    "day_book": vouchers.day_book,
    "sales_register": vouchers.sales_register,
    "purchase_register": vouchers.purchase_register,
}

ALL_REPORT_NAMES = set(_DATE_RANGE_REPORTS) | set(_AS_ON_DATE_REPORTS) | set(_VOUCHER_REPORTS)


def _to_table(data: Any) -> ReportResponse:
    """Convert various tally_bridge return types into a uniform ReportResponse."""
    # ReportResponse (from reports module) — has .rows list[dict]
    if hasattr(data, "rows"):
        rows = data.rows
        if rows:
            headers = list(rows[0].keys())
            return ReportResponse(
                headers=headers,
                rows=[list(r.values()) for r in rows],
            )
        return ReportResponse(headers=[], rows=[])

    # list[OutstandingBill] — Pydantic models
    if isinstance(data, list) and data and hasattr(data[0], "model_dump"):
        first = data[0].model_dump(mode="json")
        headers = list(first.keys())
        return ReportResponse(
            headers=headers,
            rows=[list(item.model_dump(mode="json").values()) for item in data],
        )

    # list[dict] — voucher data, stock summary
    if isinstance(data, list):
        if not data:
            return ReportResponse(headers=[], rows=[])
        headers = list(data[0].keys())
        return ReportResponse(
            headers=headers,
            rows=[list(row.values()) for row in data],
        )

    return ReportResponse(headers=[], rows=[])


@router.get("/reports/{name}", response_model=ReportResponse)
async def get_report(
    name: str,
    from_date: str | None = Query(None, description="Start date DD-MM-YYYY"),
    to_date: str | None = Query(None, description="End date DD-MM-YYYY"),
    as_on_date: str | None = Query(None, description="As-on date DD-MM-YYYY"),
    company: str | None = Query(None, description="Company name"),
    client: TallyClient = Depends(get_client),
) -> ReportResponse:
    if name not in ALL_REPORT_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report: {name}. Valid reports: {sorted(ALL_REPORT_NAMES)}",
        )

    if name in _DATE_RANGE_REPORTS:
        if not from_date or not to_date:
            raise HTTPException(status_code=422, detail="from_date and to_date are required")
        data = await _DATE_RANGE_REPORTS[name](client, from_date, to_date, company)
        return _to_table(data)

    if name in _AS_ON_DATE_REPORTS:
        date_val = as_on_date or to_date
        if not date_val:
            raise HTTPException(status_code=422, detail="as_on_date (or to_date) is required")
        if name == "stock_summary":
            data = await reports.stock_summary(client, date_val, company=company)
        else:
            data = await _AS_ON_DATE_REPORTS[name](client, date_val, company)
        return _to_table(data)

    # Voucher reports
    if not from_date or not to_date:
        raise HTTPException(status_code=422, detail="from_date and to_date are required")
    data = await _VOUCHER_REPORTS[name](client, from_date, to_date, company=company)
    return _to_table(data)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_reports.py -v`
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/reports.py tests/unit/test_api_reports.py
git commit -m "feat(api): add GET /api/reports/{name} endpoint with all report types"
```

---

### Task 7: Create chat endpoint

**Files:**
- Create: `backend/api/chat.py`
- Test: `tests/unit/test_api_chat.py`

**Step 1: Write the failing test**

Create `tests/unit/test_api_chat.py`:

```python
"""Tests for POST /api/chat endpoint."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.chat import router
from backend.api.dependencies import get_client, get_session_store
from backend.agents.context import SessionStore, SessionContext


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_session_store():
    store = SessionStore(ttl_minutes=60)
    return store


def test_chat_greeting(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "greeting",
        "message": "Hello! I'm your TallyPrime assistant.",
        "data": None,
        "chart": None,
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "Hello! I'm your TallyPrime assistant."
    assert "session_id" in body


def test_chat_with_data(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "simple_lookup",
        "message": "Here is your trial balance.",
        "data": {"rows": [{"account": "Cash", "balance": 10000}]},
        "chart": None,
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Show trial balance"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] is not None


def test_chat_with_chart(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "comparison",
        "message": "Here is the comparison.",
        "data": {"rows": []},
        "chart": {"chart_type": "bar", "title": "Sales", "data": [{"x": "Q1", "y": 100}], "config": None},
        "session_id": "test-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={"message": "Compare Q1 vs Q2 sales"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["chart"]["chart_type"] == "bar"


def test_chat_preserves_session_id(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store

    orchestrator_result = {
        "query_type": "greeting",
        "message": "Hi",
        "data": None,
        "chart": None,
        "session_id": "existing-session",
    }

    with patch("backend.api.chat.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.process_query = AsyncMock(return_value=orchestrator_result)
        with TestClient(app) as tc:
            resp = tc.post("/api/chat", json={
                "message": "Hello",
                "session_id": "existing-session",
            })

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "existing-session"


def test_chat_empty_message_rejected(app, mock_client, mock_session_store):
    app.dependency_overrides[get_client] = lambda: mock_client
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    with TestClient(app) as tc:
        resp = tc.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_api_chat.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/api/chat.py`:

```python
"""Chat endpoint — main conversational interface to the agent pipeline."""

from fastapi import APIRouter, Depends, HTTPException

from backend.agents.context import SessionStore
from backend.agents.orchestrator import Orchestrator
from backend.api.dependencies import get_client, get_session_store
from backend.api.models import ChatRequest, ChatResponse, ChartSpec
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: TallyClient = Depends(get_client),
    session_store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    session = session_store.get_or_create(
        session_id=request.session_id,
        company=request.company,
    )

    orchestrator = Orchestrator()
    result = await orchestrator.process_query(request.message, client, session)

    chart = None
    if result.get("chart"):
        chart = ChartSpec(**result["chart"])

    return ChatResponse(
        message=result["message"],
        data=result.get("data"),
        chart=chart,
        session_id=result["session_id"],
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_api_chat.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add backend/api/chat.py tests/unit/test_api_chat.py
git commit -m "feat(api): add POST /api/chat endpoint"
```

---

### Task 8: Create main app with lifespan and exception handlers

**Files:**
- Create: `backend/main.py`
- Test: `tests/unit/test_main.py`

**Step 1: Write the failing test**

Create `tests/unit/test_main.py`:

```python
"""Tests for the FastAPI application setup."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_app_starts_and_has_routes():
    with patch("backend.main.TallyClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value = mock_instance
        from backend.main import app
        with TestClient(app) as tc:
            # Health endpoint should exist
            resp = tc.get("/api/health")
            assert resp.status_code == 200


def test_tally_connection_error_returns_503():
    from backend.tally_bridge.exceptions import TallyConnectionError
    with patch("backend.main.TallyClient") as MockClient:
        MockClient.return_value = AsyncMock()
        from backend.main import app
        with TestClient(app) as tc:
            # Simulate by calling a handler that raises TallyConnectionError
            @app.get("/test-conn-error")
            async def trigger_conn_error():
                raise TallyConnectionError("Tally unreachable")

            resp = tc.get("/test-conn-error")
            assert resp.status_code == 503
            assert resp.json()["error"] == "Tally unreachable"


def test_tally_response_error_returns_502():
    from backend.tally_bridge.exceptions import TallyResponseError
    with patch("backend.main.TallyClient") as MockClient:
        MockClient.return_value = AsyncMock()
        from backend.main import app
        with TestClient(app) as tc:
            @app.get("/test-resp-error")
            async def trigger_resp_error():
                raise TallyResponseError("Invalid XML from Tally")

            resp = tc.get("/test-resp-error")
            assert resp.status_code == 502
            assert resp.json()["error"] == "Invalid XML from Tally"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `backend/main.py`:

```python
"""FastAPI application — main entry point for the TallyPrime AI Agent."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agents.context import SessionStore
from backend.api import chat, companies, health, reports
from backend.api.models import ErrorResponse
from backend.config import settings
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tally_client = TallyClient(settings.TALLY_HOST, settings.TALLY_PORT)
    app.state.session_store = SessionStore(ttl_minutes=settings.SESSION_TTL_MINUTES)
    yield
    await app.state.tally_client.close()


app = FastAPI(
    title="TallyPrime AI Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.exception_handler(TallyConnectionError)
async def tally_connection_error_handler(
    request: Request, exc: TallyConnectionError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(error=str(exc)).model_dump(),
    )


@app.exception_handler(TallyResponseError)
async def tally_response_error_handler(
    request: Request, exc: TallyResponseError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(error=str(exc)).model_dump(),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add backend/main.py tests/unit/test_main.py
git commit -m "feat: add FastAPI main app with lifespan, CORS, and exception handlers"
```

---

### Task 9: Run full test suite and verify everything works together

**Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests pass (existing + ~28 new tests).

**Step 2: Run all tests with coverage**

Run: `pytest tests/ --cov=backend --cov-report=term-missing -v`
Expected: Coverage should be ≥85% across all backend modules.

**Step 3: Manual smoke test — start the server**

Run: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
Expected: Server starts. Visit `http://localhost:8000/docs` to see auto-generated API docs.

Test endpoints manually:
- `GET http://localhost:8000/api/health` → returns health status
- `GET http://localhost:8000/api/companies` → returns companies (needs Tally running)
- `POST http://localhost:8000/api/chat` with `{"message": "Hello"}` → returns greeting

**Step 4: Commit any fixes**

If any issues found, fix and commit.

---

### Task 10: Update CLAUDE.md build commands

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Verify the run command works**

The CLAUDE.md already has `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000` listed. Verify this works after Task 9.

**Step 2: Commit if any changes needed**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Phase 3 status"
```
