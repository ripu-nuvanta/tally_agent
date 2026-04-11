# DB-Mode Test Coverage Fill — Design Spec

**Date:** 2026-04-11
**Status:** Draft
**Scope:** Fix known failures, fix environmental issues, fill DB-mode test gaps across all layers.
**Baseline:** 1210 tests (1209 pass, 1 fail), 83% backend unit coverage.

## Goals

1. **Fix the 1 pre-existing failure** on master.
2. **Fix the environmental issue** where E2E legacy tests fail when `.env` has `DATABASE_URL`.
3. **Fill DB-mode test gaps** identified in the coverage audit (P0–P3).
4. **Raise backend unit coverage** from 83% to ≥88%, specifically targeting `backend/api/` modules (currently 24–47%).

## Non-Goals

- No legacy-mode test additions.
- No new tests for e2e_live or eval (expensive, separate concern).
- No refactoring of production code except the 2 bug fixes.
- No Tally bridge query coverage improvements (41–43% is acceptable — covered by integration tests).

---

## Part 1: Bug Fixes (2 items)

### Fix 1: `test_trend_total_row_in_table_excluded_from_chart` (pre-existing failure)

**File:** `tests/e2e/test_chat_pipeline.py:560`

**Root cause:** The mock patches `get_chart_advice` with `return_value=chart_advice` (a dict), but `orchestrator.py:426` unpacks the return as `advice, advisor_usage = await get_chart_advice(...)`, expecting a tuple of `(dict, dict)`.

**Fix:** Change line 560 from:
```python
return_value=chart_advice
```
to:
```python
return_value=(chart_advice, {"agent": "chart_advisor", "model": "test", "input_tokens": 0, "output_tokens": 0})
```

**Verification:** Test passes; no other tests affected (grep for other `get_chart_advice` mocks to ensure consistency).

### Fix 2: E2E legacy tests fail when `.env` has `DATABASE_URL`

**Root cause:** `test_legacy_smoke.py`, `test_chat_pipeline.py`, `test_data_entry.py` create a FastAPI test client without overriding `settings.DATABASE_URL`. When `.env` sets it, the app boots in DB mode and all unauthenticated requests get 401.

**Fix:** In `tests/e2e/conftest.py`, add a session-scoped autouse fixture that patches `backend.config.settings.DATABASE_URL` to `None` and `backend.config.settings.db_mode` to return `False` for all E2E tests that don't explicitly opt into DB mode. DB-mode tests (`test_db_smoke.py`, `test_db_playwright.py`, `test_db_data_entry.py`) will import their own conftest that overrides this back to the real `TEST_DATABASE_URL`.

**Pattern:** Follow the existing pattern in `test_data_entry.py:17` which already does `settings.DATABASE_URL = None`, but centralize it in conftest so all legacy E2E tests get it automatically.

---

## Part 2: P0 — DB-Mode File Upload + Voucher Write E2E

**New file:** `tests/e2e/test_db_data_entry.py`

**Gate:** `TEST_DATABASE_URL` env var (skip if not set, same as `test_db_smoke.py`).

**Dependencies:** Mock Claude API (no real API calls), mock Tally (client.mock_mode=True), real Postgres via TEST_DATABASE_URL.

### Tests (5)

1. **`test_db_upload_receipt_returns_review_card`**
   - Register user → create workspace (with `tally_company` config) → upload PDF → verify review card response.
   - Asserts workspace_id is accepted, conversation context propagated.

2. **`test_db_voucher_approve_writes_to_tally`**
   - Full pipeline: upload → extract → approve → verify CREATED=1 from mock Tally.
   - Asserts workspace's `tally_company` is used as `SVCURRENTCOMPANY` in the XML.

3. **`test_db_voucher_discard`**
   - Upload → extract → discard → verify no Tally call, response acknowledges discard.

4. **`test_db_voucher_approve_creates_new_ledger`**
   - Upload → extract → entry has `is_new_ledger=True` → approve → verify ledger created then voucher created.

5. **`test_db_upload_requires_workspace_id`**
   - Upload without workspace_id in DB mode → 400 "workspace_id is required in DB mode".

### Key assertions
- Workspace ownership is verified (user A can't write to user B's workspace).
- `SVCURRENTCOMPANY` in generated XML matches workspace config, not workspace name.
- Mock Tally responses are verified (CREATED=1, ERRORS=0).

---

## Part 3: P1 — Backend Unit Tests for DB-Mode API Endpoints

Target modules and expected new test counts:

### `tests/unit/test_auth_api.py` (expand existing, +8 tests)

Currently 4 tests (rate limiting, password rules). Add:

1. `test_register_success` — mock DB, verify user creation + JWT response
2. `test_register_duplicate_email` — mock DB IntegrityError → 409
3. `test_login_success` — mock DB user lookup + password verify → tokens
4. `test_login_invalid_password` — mock DB → 401
5. `test_refresh_valid_token` — mock JWT decode → new access token
6. `test_refresh_invalid_token` — invalid refresh → 401
7. `test_logout_clears_cookie` — verify Set-Cookie with max-age=0
8. `test_me_returns_user_info` — mock get_current_user → user dict

### `tests/unit/test_api_workspaces.py` (new file, +8 tests)

1. `test_list_workspaces_for_user` — mock DB, verify user isolation
2. `test_create_workspace_defaults` — verify default agent_type, config
3. `test_create_workspace_with_config` — tally_host, tally_port, tally_company
4. `test_patch_workspace_name` — mock DB update
5. `test_patch_workspace_config` — update tally_company
6. `test_delete_workspace_soft_delete` — verify is_deleted flag set
7. `test_workspace_not_found_404` — nonexistent ID
8. `test_workspace_wrong_user_404` — user A can't access user B's workspace

### `tests/unit/test_api_conversations.py` (new file, +6 tests)

1. `test_list_conversations_for_workspace` — mock DB, ordered by updated_at
2. `test_create_conversation` — verify workspace ownership check
3. `test_get_conversation_with_messages` — verify message list
4. `test_patch_conversation_title` — title update
5. `test_delete_conversation` — soft delete
6. `test_conversation_wrong_workspace_404` — cross-workspace access denied

### `tests/unit/test_api_chat_db.py` (new file, +5 tests)

1. `test_chat_db_mode_requires_auth` — no token → 401
2. `test_chat_db_mode_requires_workspace_id` — missing workspace_id → 400
3. `test_chat_db_mode_saves_messages` — mock DB, verify user + assistant messages saved
4. `test_chat_db_mode_logs_usage` — verify UsageLog created with token counts
5. `test_chat_db_mode_workspace_ownership` — wrong user → 404

### `tests/unit/test_api_usage.py` (new file, +4 tests)

1. `test_usage_totals` — mock DB, verify aggregation
2. `test_usage_by_workspace` — grouped response
3. `test_usage_by_day` — daily breakdown
4. `test_usage_empty` — no logs → zero counts

### `tests/unit/test_api_dependencies.py` (expand existing, +4 tests)

1. `test_get_current_user_valid_token` — mock JWT decode → user_id
2. `test_get_current_user_expired_token` — → 401
3. `test_get_current_user_malformed_header` — no "Bearer" prefix → 401
4. `test_get_optional_db_returns_session` — verify AsyncSession type

**P1 subtotal: ~35 new unit tests**

---

## Part 4: P2 — Frontend Vitest (DB-Mode Components)

### `frontend/src/__tests__/AuthContext.test.tsx` (new file, +8 tests)

1. `test_initial_state_unauthenticated` — no token → isAuthenticated=false
2. `test_login_sets_user_and_token` — mock API → isAuthenticated=true
3. `test_register_sets_user_and_token` — mock API → auto-login
4. `test_logout_clears_state` — isAuthenticated=false, user=null
5. `test_refresh_on_mount` — stored refresh token → auto-login
6. `test_refresh_failure_clears_state` — expired refresh → logout
7. `test_provides_access_token` — verify token in context
8. `test_api_interceptor_adds_auth_header` — verify Authorization header

### `frontend/src/__tests__/Sidebar.test.tsx` (new file, +7 tests)

1. `test_renders_workspace_list` — mock workspaces → workspace names displayed
2. `test_conversation_list_under_workspace` — expand → conversations listed
3. `test_active_conversation_highlighted` — selected conv has active style
4. `test_new_chat_button_calls_handler` — onClick fired
5. `test_connect_company_button` — opens modal (or fires callback)
6. `test_empty_workspace_shows_new_chat` — workspace with 0 convs
7. `test_collapse_expand_workspace` — toggle visibility

### `frontend/src/__tests__/ConnectCompanyModal.test.tsx` (new file, +5 tests)

1. `test_renders_form_fields` — Company Name, Tally Host, Port visible
2. `test_mock_mode_toggle` — demo mode checkbox
3. `test_submit_calls_create_workspace` — mock API, verify payload
4. `test_error_display` — API error → error message shown
5. `test_close_button` — onClose callback fired

### `frontend/src/__tests__/ChatApp.test.tsx` (new file, +5 tests)

1. `test_renders_sidebar_and_chat` — both present
2. `test_workspace_selection_updates_header` — active workspace name in header
3. `test_new_chat_creates_conversation` — mock API, verify navigation
4. `test_conversation_click_loads_messages` — mock API, verify ChatWindow props
5. `test_no_workspaces_shows_connect_prompt` — empty state

**P2 subtotal: ~25 new frontend tests**

---

## Part 5: P3 — Frontend Playwright DB-Mode Visual Tests

**New file:** `frontend/tests/playwright/db-mode.spec.ts`

**Gate:** `RUN_PLAYWRIGHT_DB_TESTS=1` env var. Requires backend (port 8000) + frontend (port 5173, VITE_DB_MODE=true) running.

### Tests (5 specs × 3 viewports = 15 test runs)

1. **login-page** — Login form layout across mobile/tablet/desktop
2. **register-page** — Register form with password strength indicator
3. **sidebar-with-workspaces** — Sidebar with workspace list + conversations
4. **chat-with-header** — Chat window with workspace name in header breadcrumb
5. **voucher-review-card** — VoucherReviewCard rendered inline in chat

**Prerequisite:** Seed DB with test user, workspace, conversation + messages (including a voucher review card message) via API calls in `beforeAll`.

**Screenshot directory:** `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/db-mode.spec.ts/`

**P3 subtotal: 15 new Playwright test runs (5 specs × 3 viewports)**

---

## Summary

| Part | What | New Tests | Files |
|------|------|-----------|-------|
| 1 | Bug fixes | 0 (fix 1 existing) | 2 files modified |
| 2 (P0) | DB-mode file upload + voucher E2E | 5 | 1 new file |
| 3 (P1) | Backend unit tests for DB API | ~35 | 4 new + 2 expanded |
| 4 (P2) | Frontend Vitest DB components | ~25 | 4 new files |
| 5 (P3) | Frontend Playwright DB visual | 15 (5×3) | 1 new file |
| **Total** | | **~80 new tests** | **9 new + 4 modified** |

### Expected coverage after implementation

| Metric | Before | After (target) |
|--------|--------|----------------|
| Total tests | 1210 | ~1290 |
| Failing tests | 1 | 0 |
| Backend unit coverage | 83% | ≥88% |
| `api/chat.py` coverage | 35% | ≥60% |
| `api/auth.py` coverage | 47% | ≥75% |
| `api/workspaces.py` coverage | 38% | ≥75% |
| `api/conversations.py` coverage | 34% | ≥70% |
| `api/usage.py` coverage | 24% | ≥65% |
| `api/dependencies.py` coverage | 44% | ≥75% |

### Execution order

```
Part 1 (bug fixes) → Part 2 (P0 E2E) → Part 3 (P1 unit) → Part 4 (P2 frontend) → Part 5 (P3 Playwright)
```

Each part is independently committable and testable. Parts 3 and 4 can run in parallel via subagents.
