# Set B1a Final Code Review

## Summary

**Verdict: NEEDS CHANGES before merge.**

The XML/writer/parser core is well-built and thoroughly tested (102 targeted
tests, 1023 total backend passing, 181 frontend passing), and the previously
known issues (XML escaping, validator robustness, EXCEPTIONS handling, date
error translation) are all correctly fixed and regression-tested. However,
there are two concrete **user-facing bugs** in the approve/edit flow, one
**config default** that silently enables production Tally writes, and a
**test-setup regression** that makes every new endpoint test fail on any dev
machine that has `DATABASE_URL` set in `.env` (i.e. everyone who is on Set A1
DB mode — which is the default going forward). These should be fixed before
merging to `master`.

Scope reviewed:
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/tally_bridge/import_builder.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/tally_bridge/writer.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/tally_bridge/response_parser.py` (parse_import_response)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/tally_bridge/mock_handler.py` (_handle_import)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/services/document_parser.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/services/ledger_mapper.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/services/voucher_builder.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/agents/orchestrator.py` (process_file_upload)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py` (/chat/upload, /chat/voucher-action)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/models.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/config.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/db/models.py`, `backend/db/migrations/versions/002_data_entry.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/components/{ChatInput,ChatWindow,FileAttachButton,MessageBubble,VoucherReviewCard}.tsx`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/api/client.ts`
- All new tests under `tests/unit/`, `tests/integration/`, `tests/e2e/`, and `frontend/src/__tests__/`

## Critical Issues

### C1. Edit flow is broken end-to-end — backend rejects `action: "edit"`

**Files:**
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/components/MessageBubble.tsx:133-138` (sends `"edit"` action)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/components/VoucherReviewCard.tsx:265-280` (EditForm "Confirm & Write to Tally" button)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/api/client.ts:188` (`VoucherAction = "approve" | "discard" | "edit"`)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py:151-202` (only `approve`/`discard`)

**Symptom:** User clicks **Edit Entry** → modifies fields → clicks **Confirm &
Write to Tally**. The frontend fires `onVoucherAction("edit", {...entry,
...updates})`, which POSTs `/api/chat/voucher-action` with `action: "edit"`.
`chat.py` has no handler for `"edit"` and falls through to:

```python
raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
```

The user sees "Failed to perform action. Please try again." — the edits are
silently lost AND no voucher is written. This is a 100% reproducible
user-facing break of the happy path.

The design plan (`2026-04-04-set-b1a-expense-entry-plan.md`, lines 3163+3172)
specifies an `edit` action, but it was dropped during implementation in
commit `eae4322` without updating the frontend.

**The button label is also misleading**: "Confirm & Write to Tally" implies a
write will happen, but the handler only updates local state and fires a
(broken) edit call that does not write.

**Fix (pick one):**
1. **Simplest**: remove `"edit"` from `VoucherAction` and have EditForm close
   the form locally with the updated entry; then require the user to click
   **Write to Tally** to actually write. Rename the button to
   **Save Changes**.
2. **Correct per plan**: add an `elif action == "edit":` branch in
   `voucher_action` that (a) validates the updated entry via
   `TallyWriter.validate_voucher`, (b) immediately writes to Tally if valid
   (approve-after-edit), and (c) optionally calls `learn_mapping` on the
   `LedgerMapper` so corrections train the system.

The plan clearly wanted option 2 (user correction → learn_mapping →
auto-write). Either works, but something needs to ship.

**Test to add:** a Vitest test that asserts clicking
"Confirm & Write to Tally" calls `onVoucherAction` with an action the
backend actually accepts, AND a backend test that posts
`{"action": "edit", ...}` and asserts a non-400 response.

### C2. Approve flow silently fails for `is_new_ledger=True` suggestions

**Files:**
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/agents/orchestrator.py:243-280` (marks entries with `is_new_ledger`)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py:151-193` (approve handler, never calls `create_ledger`)
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/frontend/src/components/VoucherReviewCard.tsx:119-122` ("New ledger will be created under...")

**Symptom:** When `LedgerMapper` returns an `ai_suggestion` result, the orchestrator
sets `is_new_ledger=True` and `suggested_parent="Indirect Expenses"` (or
similar). The UI displays "New ledger '<name>' will be created under
'<parent>'". The user clicks **Write to Tally**. The approve handler calls
`writer.create_payment_voucher(debit_ledger=<new name>, ...)` **without first
calling `writer.create_ledger(name, parent)`**. Tally responds with a LINEERROR
like "Ledger <name> does not exist" → the user sees a red error. The UI
promised ledger creation; the backend never delivers.

Because `known_ledgers` is not passed to `create_payment_voucher` in the
endpoint, the local validator also skips the existence check and the error
only surfaces after the round-trip to Tally.

**Fix:** In the approve handler, before `create_payment_voucher`, inspect
`entry.get("is_new_ledger")` and `entry.get("suggested_parent")` and call
`writer.create_ledger(entry["debit_ledger"], entry["suggested_parent"])`
first. Abort the voucher write if the ledger creation fails. Also call
`mapper.learn_mapping(vendor, debit_ledger, "Payment", source="ai_suggestion")`
on success so the same vendor hits a stored rule next time.

### C3. `TALLY_WRITE_ENABLED` defaults to `True`

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/config.py:34`

```python
TALLY_WRITE_ENABLED: bool = True
```

This is the first feature in the project that can mutate a customer's
production Tally database. A pull from `master`, `uvicorn backend.main:app`,
and a plausible prompt is enough to create live vouchers by default. The
kill switch exists but is inverted from safe-by-default.

**Fix:** Default to `False`. Add a clear log line on startup when it is
`True`, e.g. `logger.warning("TALLY_WRITE_ENABLED=true — voucher writes will
hit Tally.")`. Update `.env.example` and CLAUDE.md accordingly.

### C4. Unit/E2E tests for the new endpoints fail on any dev machine with `DATABASE_URL` set

**Files:**
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/tests/unit/test_file_upload_endpoint.py`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/tests/e2e/test_data_entry.py`

**Reproduction:**
```
cd .worktrees/set-b1a-expense-entry
ANTHROPIC_API_KEY=test-key PYTHONPATH=. pytest \
    tests/unit/test_file_upload_endpoint.py tests/e2e/test_data_entry.py -q
```

Result: 8 failures, all `401 Unauthorized`. Root cause: when `.env` contains
`DATABASE_URL=...` (the normal Set A1 dev configuration, committed to
`CLAUDE.md` and documented in the roadmap), `settings.db_mode` becomes
`True`, the chat endpoints route through `get_current_user` which requires
a JWT, and TestClient posts without a token → 401. The tests only pass if
the developer manually removes `.env`. Set A1 landed this merge cycle — from
now on DB mode is the default developer setup, so these tests will fail for
every reviewer and in any CI environment seeded with a `.env`.

The existing Set A1 suites handled this by using a dedicated
`TEST_DATABASE_URL` + injecting JWTs. The new B1a endpoint tests did not
follow that pattern.

**Fix options (pick whichever is cleaner):**
1. Add a `tests/conftest.py` that monkeypatches `settings.DATABASE_URL = None`
   and `settings.JWT_SECRET = None` for endpoint tests in this suite. (Fast.)
2. In each new test's `client` fixture, use
   `app.dependency_overrides[get_current_user] = lambda: "test-user"` to
   bypass auth, and monkeypatch `settings.db_mode` to `False` before the app
   starts (note: `db_mode` is a property of `DATABASE_URL` — patching
   `DATABASE_URL=None` is the way).
3. Add explicit DB-mode coverage: register a user, log in, carry the JWT,
   and assert workspace ownership is enforced. (Matches how Set A1 tests
   were written.)

Option 3 is the strongest and surfaces the ownership gap in C5/C6.

## Important Issues

### I1. No workspace ownership checks in `/chat/upload` or `/chat/voucher-action` (DB mode)

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py:52-202`

Both endpoints declare `Depends(get_current_user)` so they're behind auth,
but:

- They accept `workspace_id` / `company` / `session_id` / `conversation_id`
  straight from the client with zero DB verification. `user_id` is fetched
  and then never used.
- They never load the `Workspace` row or check `Workspace.user_id == user_id`.
- They use the shared `client: TallyClient = Depends(get_client)` pointing
  at the globally configured Tally host, not the workspace-configured one.
  This is inconsistent with `_chat_db_mode` (lines 316-325), which
  correctly re-resolves the Tally endpoint from `workspace.config`. A user
  who has one workspace on mock-mode and another on a live Tally LAN host
  cannot target the mock workspace for testing — `/chat/upload` always
  hits the global setting. And in a multi-tenant deploy, user A could
  potentially write vouchers into user B's Tally by crafting a
  `/chat/voucher-action` request with B's `company` string.
- In DB mode, nothing persists. The `uploaded_files` / `voucher_entries`
  tables exist (and the migration landed) but the orchestrator never
  writes rows. This is called out in the "Known Gaps" list, but combined
  with the missing ownership checks it means the endpoint is effectively
  an unauthenticated multi-tenant write tool in DB mode.

**Fix:** Mirror the `_chat_db_mode` pattern. Require `workspace_id`, load
`Workspace`, verify `workspace.user_id == user_id`, reconstruct the
`TallyClient` from `workspace.config`, and pass `workspace.name` as the
company rather than trusting the client-supplied string. Return 404 on
ownership mismatch.

### I2. `/chat/voucher-action` takes `request: dict` instead of the existing `VoucherReviewEntry` Pydantic model

**Files:**
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py:128-149`
- `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/models.py:170-193`

The endpoint already has `VoucherReviewEntry` + `VoucherReviewData`
Pydantic models defined but doesn't use them. Consequences:

- `entry["date"]`, `entry["debit_ledger"]`, `entry["credit_ledger"]`,
  `entry["amount"]`, `entry["narration"]` are all raw `dict` access. If
  the frontend sends a malformed payload (missing `date`, say), the
  endpoint raises `KeyError` → FastAPI returns a 500, not a 400.
- No field-level validation: amount can be negative, date can be any
  string, narration can be empty. `TallyWriter.validate_voucher` catches
  most of these, but they'd be cleaner as pydantic validators.
- No discoverability: OpenAPI shows an untyped body.

**Fix:** Define a `VoucherActionRequest(BaseModel)` with
`action: Literal["approve","discard","edit"]`, `entry: VoucherReviewEntry`,
`company: str`, `session_id: str | None`. Use it as the request type.

### I3. `process_file_upload` uses synchronous `anthropic.Anthropic` inside an async method

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/agents/orchestrator.py:184-216`

```python
ai_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
...
response = ai_client.messages.create(...)
```

This is a blocking HTTP call inside an async coroutine. On a busy server
every upload will stall the event loop for 5-15s (Claude Vision latency).
The module already has `anthropic_client = anthropic.AsyncAnthropic(...)`
at the top for classification; the same pattern should be used here.

Also: a new client is instantiated per upload instead of reusing the
module-level async client, which wastes connection pooling.

**Fix:** Use `await anthropic_client.messages.create(...)` with the
module-level `AsyncAnthropic` instance.

### I4. File handling in `/chat/upload` leaks on error and does not bound user disk usage

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/api/chat.py:93-119`

1. The file is written to `FILE_STORAGE_PATH` before the pipeline runs.
   If `orchestrator.process_file_upload` raises, the file stays on disk
   forever. No `try/finally` cleanup.
2. `os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)` is called on
   every request — fine, but no per-user or global quota. A malicious
   authenticated user can fill disk with near-max-size uploads.
3. `ext = os.path.splitext(file.filename)[1]` preserves whatever the
   client sends (no sanitization). `splitext` does prevent directory
   traversal (it takes only the final extension), but an extension like
   `.jpg.php` or weird unicode is stored verbatim. Low impact because
   the file is served from a managed path and never executed, but worth
   whitelisting to `[".jpg",".jpeg",".png",".heic",".pdf",".csv",".xlsx",".xls"]`
   from `detect_file_type`.
4. The file is read synchronously with `open(storage_path, "wb")` inside
   the async endpoint — another event-loop blocker for large files, though
   bounded by the 10 MB limit.

**Fix:** Wrap the pipeline call in `try/except` that deletes `storage_path`
on failure. Whitelist the extension. Optionally use `aiofiles` for the
write. Add a per-user quota check if/when DB persistence lands.

### I5. `LedgerMapper.use_count` is dead — never incremented

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/services/ledger_mapper.py:44-54, 94-127`

`find_mapping` sorts by `-m["use_count"]` for hot-path priority but neither
`find_mapping` on a hit nor `learn_mapping` on an update ever increments
`use_count`. The field is stored but always `0`, so the sort is a no-op.
This is also the field used for "learning loop" reporting in the plan.

**Fix:** Increment `use_count` on a stored-rule hit inside `find_mapping`,
and on update inside `learn_mapping`. If not fixed now, delete the sort
and the field so the model matches reality.

### I6. `validate_voucher` balance check uses raw `amount` without any sign convention enforcement

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/tally_bridge/writer.py:77-84`

The validator sums `float(e["amount"])` and checks `abs(total) > 0.01`.
This correctly catches imbalances *for voucher dicts that callers build
with the Tally sign convention* (debits negative, credits positive). But
the validator is also exposed as a public dry-run primitive and callers
from `api/chat.py` never go through it (the approve endpoint skips the
`known_ledgers` check entirely). There's no mention of the sign convention
in the docstring, and the test suite only exercises the negative-debit
convention.

If a future feature calls `validate_voucher` with debit=+500, credit=+500
(natural signs), it would silently report `Ledger entries do not balance`
— or worse, with debit=+500, credit=-500 it would *pass* an invalid
voucher.

**Fix:** Either (a) document the expected convention in the docstring and
reject non-conforming inputs explicitly, or (b) add an `is_debit` check
that rewrites signs before summing. Same comment applies to all test
fixtures.

### I7. `parse_vision_response` does not tolerate `json.JSONDecodeError` or extra top-level keys

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/services/document_parser.py:117-167`

If Claude Vision returns a sentence like "I cannot read this image" or a
JSON blob missing `total_amount`, `json.loads` raises `JSONDecodeError`
which is caught in `orchestrator.process_file_upload` at line 218-224 and
surfaced to the user as a helpful error — OK, but the dict access with
`data["doc_type"]` vs `data.get("doc_type", "expense")` is inconsistent
(the function uses `.get` with defaults for most fields but does a direct
access to `data["line_items"]`-derived dicts on line 135-143). Not a bug
today because `line_items` has a default of `[]`, but any missing key in
a list item could raise.

**Fix:** Nothing urgent — current tests cover the happy path. Optional:
wrap the whole function body in `try/except Exception: return <empty
ExtractedDocument with warnings>` and return a validation warning rather
than raising.

### I8. `process_file_upload` ignores `user_message` and `session` (dead params)

**File:** `/Users/ripu/work/nuvanta_repos/tally_agent/.worktrees/set-b1a-expense-entry/backend/agents/orchestrator.py:131-149`

Known gap in the review brief ("reserved for future context-aware
extraction"). Fine. Add a `# noqa: ARG002` or `_ = user_message, session`
line to document the intent so the next reviewer doesn't think it's a
bug.

## Minor Suggestions

### M1. `import_builder` docstrings should note the date format rule

`build_create_payment_voucher` documents `YYYYMMDD`, but the `build_delete_*`
and `build_cancel_voucher` functions take `date: str` without a format note.
Since the rest of the codebase uses `DD-MM-YYYY` for queries, a reader
might pass the wrong format. Add "(YYYYMMDD format)" to each signature.

### M2. `_handle_import` in mock_handler uses substring match on XML

`if 'ACTION="Delete"' in xml_body:` — fragile against whitespace variation
in a real request. It happens to work because `import_builder` always emits
exactly that string, but an ElementTree parse would be more robust.

### M3. `VoucherReviewCard.EditForm` "Confirm & Write to Tally" button label is misleading

See C1. Even if the edit action is fixed, the button currently only saves
the draft and exits edit mode. Rename to "Save Changes" or have it trigger
approval.

### M4. `frontend/src/api/client.ts` `voucherAction` sends `session_id` that is already the conversation id

`ChatWindow.handleVoucherAction` passes `sessionId ?? ""`. In DB mode the
"session id" is the conversation UUID; in legacy mode it's the in-memory
session id. The backend ignores it today (it's round-tripped back to the
client), but the semantic is fuzzy. Consider passing `conversation_id`
explicitly in DB mode.

### M5. `process_file_upload` does not clean up after itself

If the Claude Vision call succeeds but the ledger list fetch fails, the
uploaded file stays on disk and the user gets a 500. The endpoint-level
fix in I4 would cover this, but the orchestrator could also surface a
structured error.

### M6. `_build_narration` truncates silently at 3 line items

`doc.line_items[:3]` is fine for display, but a receipt with 10 line items
loses 7 of them from the narration. Consider appending "…(+7 more)" or
making the slice configurable.

### M7. `voucher_builder._convert_date` has no validation

`"2026-04-04".replace("-", "")` gives "20260404", good. But
`"04/04/2026".replace("-", "")` gives "04/04/2026" unchanged, which Tally
will reject. Document that the input MUST already be `YYYY-MM-DD`, or
validate with a regex.

### M8. `TALLY_DRY_RUN` config is declared but never referenced

`backend/config.py:35` adds `TALLY_DRY_RUN: bool = False` but no code
reads it. Either wire it into `TallyWriter` (short-circuit the HTTP call
and return a synthetic success) or remove it.

## Strengths

- **`import_builder.py` is excellent.** Pure functions, well-scoped
  `_esc`/`_require` helpers, NAME.LIST/PERSISTEDVIEW/Master ID learnings
  from `docs/tally-write-exploration.md` are all encoded correctly with
  inline comments explaining *why*. All user strings are escaped. GST math
  validated at the builder boundary.

- **`parse_import_response` handles real Tally quirks well.** Correct
  priority order: LINEERROR > ERRORS > EXCEPTIONS. The misleading "Voucher
  date is missing" translation is a genuine product-thinking win — the
  smoke test surfaced a bad Tally error message and you made the product
  friendlier rather than ignoring it.

- **`validate_voucher` is defensive** — never raises, validates per-entry,
  skips balance check on invalid entries so you don't cascade errors.

- **`validate_extracted_amounts` never-raises contract** is correctly
  implemented and tested. Symmetric CGST/SGST/IGST checks.

- **Test coverage for the pure modules is strong**:
  `test_import_builder.py` (309 lines), `test_writer.py` (232), and the
  integration tests exercising `mock_handler._handle_import` together
  cover the round-trip path thoroughly.

- **Mock handler supports writes** so the demo and mock-mode eval tests
  don't need a live Tally. `_mock_vch_counter` is a nice touch for
  realistic LASTVCHID returns.

- **Frontend component is clean** with clear separation between display
  mode and EditForm, ARIA labels on every input, sensible status colors,
  and tests for rendering, edit, and button clicks.

- **Known-issue fixes are all verified present in code:** `_esc` on all
  user strings, `validate_voucher` dict-key guarding, LINEERROR priority,
  date-error translation, date field in EditForm.

## Test Coverage Assessment

**Solid:**
- `tests/unit/test_import_builder.py` — 309 lines, exercises XML escaping,
  GST math, validation errors, delete/cancel, NAME.LIST presence. Exactly
  where you want dense tests for a feature that could corrupt customer data.
- `tests/unit/test_writer.py` — 232 lines, covers validator edge cases
  (missing keys, wrong types, unbalanced amounts, unknown ledgers) plus
  writer orchestration with mocked client.
- `tests/unit/test_import_response.py` — LINEERROR > EXCEPTIONS priority,
  PERSISTEDVIEW echo, malformed XML handling.
- `tests/integration/test_tally_write.py` — round-trips through the
  mock handler.
- `frontend/src/__tests__/VoucherReviewCard.test.tsx` — 9 tests covering
  render variations, edit mode, warnings, GST entries.

**Blind spots:**
1. **No test for the approve→edit→write flow.** The Vitest suite verifies
   `onEdit` is called with the right arguments but never integrates with
   `voucherAction` or asserts the backend accepts the resulting call.
   The backend has no test for `action: "edit"`. This is exactly why C1
   shipped.
2. **No test for `is_new_ledger=True` approve flow.** The review card
   advertises "new ledger will be created", but no test verifies the
   actual write succeeds. This is why C2 shipped.
3. **Endpoint tests don't exercise DB mode.** Every new endpoint test
   uses the legacy (non-DB) code path, so the missing workspace-ownership
   checks (I1) and the C4 401 bug are invisible to CI.
4. **No test for concurrent mock write counter.** Minor, but worth one.
5. **No test for `process_file_upload` with a real-ish Claude response
   that is missing fields.** The happy path is tested; malformed
   extractions hit the except branch but the assertion on `data is None`
   is never verified for a partial JSON.

## Recommendation

**Fix-then-merge.** Close the two user-facing bugs (C1, C2), flip the
write default (C3), and either make the new endpoint tests pass in DB
mode or add a conftest that forces legacy mode (C4). The Important
category can be scheduled for a follow-up as long as C1/C2 block merging
— I1 is security-adjacent and should also land before a multi-user demo.

After those are addressed, this is genuinely good work: the Tally XML
layer is the highest-risk part and it's been done with care, tests, and
lessons from the exploration doc. Ship it once the wiring is fixed.
