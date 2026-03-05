# Phase 1 & 2 Code Review Results

**Date**: 2026-03-04
**Status**: All CRITICAL, HIGH, and MEDIUM fixes applied

## Summary

- 273 tests passing (240 unit + 33 integration)
- 5 CRITICAL bugs fixed
- 5 HIGH issues fixed
- 7 MEDIUM issues fixed, 1 deferred (#14 format_inr — needed in Phase 3)

---

## CRITICAL — FIXED

### 1. Only first tool_use block processed per iteration
- **Files**: `backend/agents/query_agent.py`, `backend/agents/analysis_agent.py`, `backend/agents/utils.py`
- **Fix**: Added `find_all_tool_use_blocks()`, updated both agent loops to process all blocks
- **Tests**: 5 new tests (parallel calls, count toward max, results sent back)

### 2. closing_balance returned as raw string, not float
- **File**: `backend/tally_bridge/response_parser.py:60`
- **Fix**: `parse_amount(_get_text(acc, "DSPCLAMT"))` instead of `_get_text(acc, "DSPCLAMT")`
- **Tests**: 5 new tests (float type, comma format, empty, P&L, BS delegation)

### 3. No Claude API error handling in any agent
- **Files**: `backend/agents/query_agent.py`, `backend/agents/analysis_agent.py`, `backend/agents/orchestrator.py`
- **Fix**: Wrapped `anthropic_client.messages.create()` in `try-except anthropic.APIError`
- **Tests**: 4 new tests (error return, mid-loop preservation, analysis graceful, orchestrator fallback)

### 4. Hardcoded LAN IP as default TALLY_HOST
- **File**: `backend/config.py:5`
- **Fix**: Changed `"192.168.31.179"` to `"localhost"`
- **Tests**: 3 new tests (host default, port default, URL property)

### 5. Only last tool result passed to AnalysisAgent
- **File**: `backend/agents/orchestrator.py`
- **Fix**: Replaced `_extract_last_data` with `_extract_all_data`, passes list when multiple results
- **Tests**: 7 new tests (single, multiple, filter failed, empty, null, API error, multi-data routing)

---

## HIGH — FIXED

### 6. XML injection in request_builder — ledger names with & or " crash
- **Files**: `backend/tally_bridge/request_builder.py`
- **Fix**: Added `xml.sax.saxutils.escape()` for ledger_name, voucher_type_filter, and stock_group in f-string XML templates

### 7. Broad except Exception with no logging in tool executors
- **Files**: `backend/agents/tools.py`, `backend/agents/analysis_agent.py`
- **Fix**: Added `logging.getLogger(__name__)` and `logger.exception()` before returning error dict

### 8. Classification fallback silently degrades entire system
- **File**: `backend/agents/orchestrator.py`
- **Fix**: Added `logger.warning()` with raw Claude response text on JSON parse fallback

### 9. Unhandled httpx.TransportError variants in client
- **File**: `backend/tally_bridge/client.py`
- **Fix**: Added catch for `httpx.TransportError` base class after specific exception handlers

### 10. find_tool_use_block raises unhandled ValueError
- **File**: `backend/agents/utils.py`
- **Fix**: Returns `None` instead of raising `ValueError`. Function is unused in production (agents use `find_all_tool_use_blocks`), but now safe if called

---

## MEDIUM — FIXED

### 11. Session TTL measures from creation time, not last activity
- **Fix**: Added `last_activity` field, updated on `add_message()`, used for TTL expiry check

### 12. SessionStore TTL not wired to settings.SESSION_TTL_MINUTES
- **Fix**: Default `ttl_minutes` now reads from `settings.SESSION_TTL_MINUTES`

### 13. Private _sanitize_xml imported across module boundary
- **Fix**: Renamed to `sanitize_xml` (public), updated all imports

### 14. format_inr utility is dead code
- **Deferred**: Will be used in Phase 3 (FastAPI endpoints with formatted responses)

### 15. _extract_chart_suggestion fails on space-separated names
- **Fix**: Now joins first 2 words with underscore and checks multi-word names ("grouped bar" → "grouped_bar")

### 16. Voucher type filter is case-sensitive
- **Fix**: Applied `.title()` to `voucher_type_filter` before XML injection

### 17. parse_bills lookahead window of 5 siblings may be too small
- **Fix**: Increased lookahead from 5 to 10

### 18. No session cleanup for abandoned sessions (memory leak)
- **Fix**: Added `cleanup_expired()` method, called lazily when sessions > 100

### 19. httpx.AsyncClient created per request — no connection pooling
- **Fix**: Client created once in `__init__`, reused across requests, `close()` method added

---

## Test Coverage Gaps (prioritized)

| Priority | Gap |
|----------|-----|
| Critical | `response_parser.py` — no tests for `parse_vouchers`, `parse_bills`, `parse_stock_summary` |
| High | `reports.py` — `_parse_tally_date` with all 3 formats untested |
| Medium | Mock server reuses fixtures — purchase register test validates sales data |
