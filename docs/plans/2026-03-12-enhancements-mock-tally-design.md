# Design: Mock Tally Mode, Quick Action Updates & Eval Enhancements

**Date**: 2026-03-12
**Status**: Approved

---

## Overview

Three features that improve developer experience and test reliability:

1. **Quick Action Button Updates** — Change "this month" → "last month", remove "Stock summary" (5 buttons)
2. **Mock Tally Server (Built-in Handler)** — In-process mock using Bharat Traders demo data, togglable via frontend switch
3. **Eval Mock Support** — Run evals against mock Tally with `--tally-mode mock` CLI flag

Plus: **Extract Phase 4** from `2026-03-09-eval-regression-fixes.md` into a standalone future plan.

---

## Feature A: Quick Action Button Updates

### Changes

`frontend/src/components/QuickActions.tsx` — update `QUICK_QUERIES`:

```
"P&L last month"
"Outstanding receivables"
"Cash balance"
"Top 10 customers"
"Sales vs purchases last month"
```

Down from 6 buttons to 5. Removed: "Stock summary". Changed: "this month" → "last month" on two buttons.

### Tests

| Layer | What to update |
|-------|---------------|
| Frontend unit | Update button text assertions (6→5), click handler tests for each button |
| Playwright | Update responsive screenshots showing empty chat state, add click interaction test |
| E2E | Update any tests sending old button queries |
| Eval scenarios | `quick_actions.yaml`: update text, remove stock summary turn, update `checks` text ("this month" → "last month"). `manual_test_regression.yaml`: "P&L this month" → "P&L last month", update checks text |

---

## Feature B: Mock Tally Server (Built-in Handler)

### Architecture

```
Frontend toggle → POST /api/tally-mode {"mode": "mock"|"live"}
                → Backend sets TallyClient.mock_mode = True/False

                  GET /api/tally-mode
                → Returns {"mode": "mock"|"live"}
                → Frontend calls on mount to initialize toggle state

                  TallyClient.post() checks mock_mode:
                    if True  → mock_handler(xml_request) → XML response
                    if False → httpx.post(tally_host, xml_request) → XML response
```

### Design Decisions

- **Built-in handler** (not separate process): Mock logic lives inside the backend, toggled by a flag. No process management needed.
- **Returns full dataset**: Mock server returns all Bharat Traders data regardless of date parameters. Backend's existing Python-side date filtering (`_filter_vouchers_by_date()`) handles date-range queries.
- **Backend-driven switching**: Frontend sends toggle request to `POST /api/tally-mode`, backend switches `TallyClient` state. Instant, no restart.
- **Single-developer tool**: `TallyClient` is a shared singleton — toggling mock mode affects all concurrent requests. This is acceptable for the current single-developer use case. Documented as a known limitation.
- **One canonical mock implementation**: `mock_handler.py` is the single source of truth for mock pattern-matching. The existing `tests/mocks/mock_tally_server.py` will be refactored to delegate to `mock_handler.py`, eliminating duplication.
- **Fixture-based data**: Mock data uses enhanced XML fixture files in `tests/fixtures/` (not hardcoded XML strings) loaded at import time. Existing Bharat Traders fixtures are augmented with missing data (vouchers, stock, purchase register). Keeps data human-readable and maintainable.
- **Optimistic UI with reconciliation**: Frontend toggle is optimistic. On error or reconnect, `GET /api/tally-mode` reconciles state.
- **Environment config**: `TALLY_MODE: str = "live"` in `backend/config.py` sets initial mode. Useful for CI (`TALLY_MODE=mock pytest`) and headless runs without frontend toggle.

### New Files

| File | Purpose |
|------|---------|
| `backend/tally_bridge/mock_handler.py` | Takes XML request string, pattern-matches report type, returns XML response from fixture files. Single canonical mock implementation — `tests/mocks/mock_tally_server.py` delegates to this. |
| `backend/api/tally_mode.py` | `POST /api/tally-mode` + `GET /api/tally-mode` endpoints |

### Modified Files

| File | Changes |
|------|---------|
| `backend/tally_bridge/client.py` | Add `mock_mode` flag, `post()` short-circuits to mock_handler when active |
| `backend/api/health.py` | Return `{"tally_connected": true, "mode": "mock"}` when mock active |
| `backend/api/models.py` | Add `mode: str \| None = None` to `HealthResponse`, add `TallyModeResponse` model |
| `backend/config.py` | Add `TALLY_MODE: str = "live"` to Settings |
| `backend/main.py` | Register tally_mode routes, initialize `mock_mode` from config |
| `tests/mocks/mock_tally_server.py` | Refactor to delegate to `mock_handler.py` |
| `frontend/src/components/Header.tsx` | Toggle button (`data-testid="tally-mode-toggle"`) next to health dot, "Mock Tally" label + green indicator (`data-testid="tally-mode-indicator"`). Calls `GET /api/tally-mode` on mount to initialize state. |
| `frontend/src/api.ts` | `setTallyMode()` and `getTallyMode()` API calls |
| `frontend/src/types/index.ts` | `TallyModeResponse` type, add `mode?: string` to `HealthResponse` |
| `tests/fixtures/` | Augment Bharat Traders fixtures: add purchase_register.xml, expand day_book.xml with all 50 vouchers, expand sales_register.xml with all 16 invoices |

### Mock Data Scope (from Bharat Traders spec in TALLYPRIME_AGENT_PLAN.md)

| Report | Data |
|--------|------|
| Company list | 1 company: Bharat Traders Pvt Ltd |
| Ledger list | 28 ledgers with groups |
| Trial balance | All account balances |
| P&L | Sales (Electronics/Office Supplies), Purchases, 8 expense ledgers |
| Balance sheet | Assets, liabilities, capital |
| Day book | 50 vouchers (16 sales, 8 purchase, 16 payment, 10 receipt) |
| Sales register | 16 sales invoices with party, date, amount |
| Purchase register | 8 purchase invoices |
| Bills receivable/payable | Derived from unpaid invoices |
| Stock summary | 15 stock items with quantities |

All vouchers span **Oct 2025 – Mar 2026**.

### Tests

| Layer | What |
|-------|------|
| Unit (`test_mock_handler.py`) | Each report type returns valid XML, pattern matching, unknown request → error |
| Unit (`test_tally_client.py`) | mock_mode flag toggles behavior, post() routes correctly |
| Integration | Full request → mock_handler → response_parser cycle for each report |
| E2E | `/api/tally-mode` endpoint, health reflects mode, chat works end-to-end with mock |
| E2E (mock mode) | Existing E2E tests run with mock_mode=True as parallel configuration |
| E2E live (mock mode) | `TALLY_MODE=mock` runs e2e_live tests against mock Tally with Bharat Traders assertions |
| Frontend unit | Toggle component, API calls, indicator state changes |
| Playwright | Visual test of toggle in both states |

---

## Feature C: Eval Mock Support

### `collect.py` Changes

- New CLI arg: `--tally-mode mock|live` (default: `live`)
- First Playwright action after page load: if `--tally-mode mock`, click frontend Tally toggle (`data-testid="tally-mode-toggle"`), wait for indicator (`data-testid="tally-mode-indicator"`) to show "Mock Tally"
- Skip live Tally ground truth collection in mock mode; use `tests/eval/golden/mock_golden.json` (auto-generated from mock handler output via a generate script)
- Transcript metadata records `tally_mode: "mock"|"live"`

### `judge.py` Changes

- Load correct golden data based on `tally_mode` in transcript metadata
- Bharat Traders golden values for factual scoring in mock mode

### New Eval Scenario

`mock_tally_validation.yaml` — Queries designed to validate mock coverage: P&L, trial balance, sales trend, top customers, outstanding receivables, stock summary. Success = comparable eval scores in mock vs live.

### Existing Scenario Updates

| Scenario | Change |
|----------|--------|
| `quick_actions.yaml` | Update button text ("last month"), remove stock summary turn (6→5 turns), update checks text |
| `manual_test_regression.yaml` | "P&L this month" → "P&L last month", update checks text |

### Tests

| Layer | What |
|-------|------|
| Unit | CLI arg parsing for `--tally-mode` |
| Playwright | Toggle click before eval sets correct mode |
| Eval integration | `collect.py --tally-mode mock --scenario quick_actions` end-to-end, verify transcript metadata |

---

## Deliverable 0: Extract Phase 4

Move Phase 4 content (lines 179-249) from `docs/plans/2026-03-09-eval-regression-fixes.md` into `docs/plans/2026-03-12-agent-architecture-exploration.md`. Replace original section with cross-reference link. No code changes, no tests.

Content includes:
- Option A: Model upgrade (Sonnet → Opus)
- Option B: Code execution capability
- Option C: Agent architecture redesign (C1-C4 options, Phase 8b status, revised recommendation)
- Priority assessment

---

## Known Limitations

- **Single-user mode switching**: `TallyClient.mock_mode` is a singleton flag. Toggling affects all concurrent requests. Acceptable for single-developer use; not suitable for multi-tenant deployment.

---

## Out of Scope

- Seed data script execution (mock uses fixture files, not seeded Tally)
- Agent architecture redesign (extracted to separate plan)
- Model upgrade evaluation
- GST report enhancements
