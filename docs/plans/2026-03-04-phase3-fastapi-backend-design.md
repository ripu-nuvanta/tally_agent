# Phase 3: FastAPI Backend — Design Document

**Date**: 2026-03-04
**Status**: Approved

## Overview

Wire the existing orchestrator + tally_bridge into FastAPI REST endpoints. Four routers: chat, health, companies, reports. App-level TallyClient singleton with lifespan management. Dependency injection for testability.

## Architecture

```
backend/
├── main.py              # FastAPI app + lifespan + CORS + exception handlers
├── api/
│   ├── __init__.py
│   ├── models.py        # All request/response Pydantic models
│   ├── dependencies.py  # get_client(), get_session_store() FastAPI deps
│   ├── chat.py          # POST /api/chat
│   ├── health.py        # GET /api/health
│   ├── companies.py     # GET /api/companies
│   └── reports.py       # GET /api/reports/{name}
```

## App Initialization & Lifecycle

- `lifespan` async context manager creates TallyClient and SessionStore on startup, closes client on shutdown
- Singletons stored on `app.state`
- Dependencies in `dependencies.py` extract from `request.app.state`
- CORS middleware with `allow_origins=["*"]` for MVP
- Custom exception handlers for TallyConnectionError (503), TallyResponseError (502), generic Exception (500)

## Models

### Request Models

| Model | Fields |
|-------|--------|
| `ChatRequest` | `message: str`, `session_id: str | None`, `company: str | None` |

### Response Models

| Model | Fields |
|-------|--------|
| `ChatResponse` | `message: str`, `data: dict | None`, `chart: ChartSpec | None`, `session_id: str` |
| `ChartSpec` | `chart_type: str`, `title: str`, `data: list[dict]`, `config: dict | None` |
| `HealthResponse` | `status: str`, `tally_connected: bool`, `tally_url: str` |
| `CompanyItem` | `name: str` |
| `CompaniesResponse` | `companies: list[CompanyItem]` |
| `ReportResponse` | `headers: list[str]`, `rows: list[list]` |
| `ErrorResponse` | `error: str`, `detail: str | None` |

## Endpoints

### POST /api/chat
1. Get or create session via `session_store.get_or_create(session_id, company)`
2. Create `Orchestrator()`, call `process_query(message, client, session)`
3. Map orchestrator result → `ChatResponse`
4. Return with session_id

### GET /api/health
1. Call `client.health_check()` → bool
2. Return `HealthResponse(status="healthy"|"degraded", tally_connected, tally_url)`

### GET /api/companies
1. Call `list_companies(client)` from tally_bridge
2. Return `CompaniesResponse(companies=[...])`

### GET /api/reports/{name}
- Supported: trial_balance, profit_and_loss, balance_sheet, day_book, sales_register, purchase_register, stock_summary, bills_receivable, bills_payable
- Query params: `from_date`, `to_date` (DD-MM-YYYY), optional `company`
- Maps name → tally_bridge query function
- Returns `ReportResponse(headers, rows)`

## Error Handling

| Exception | HTTP Status | Meaning |
|-----------|-------------|---------|
| `TallyConnectionError` | 503 | Tally unreachable |
| `TallyResponseError` | 502 | Tally returned invalid response |
| `ValueError` (bad report name, bad dates) | 400 | Client error |
| Generic `Exception` | 500 | Unexpected server error |

All errors return `ErrorResponse` JSON body.

## Middleware

- CORS: `allow_origins=["*"]`, all methods, all headers
- X-Request-ID header for tracing (via middleware)

## Dependencies to Add

```
fastapi>=0.115
uvicorn>=0.34
```

## Testing Strategy

- **Unit tests**: `TestClient` with dependency overrides (mock TallyClient, mock SessionStore)
- **Integration tests**: Mock Tally HTTP server, test full request → response cycle
- **E2E tests**: Mock Claude API + mock Tally, test complete chat flow

## Design Decisions

1. **App-level singleton** for TallyClient — efficient connection pooling, proper async cleanup
2. **Dependency injection** via FastAPI `Depends()` — testable, swappable
3. **All reports on Day 1** — tally_bridge already supports them all
4. **Custom ErrorResponse** — consistent JSON error format for frontend
5. **Orchestrator created per-request** — stateless, no shared mutable state
