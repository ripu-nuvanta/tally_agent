# Bug fix + code review — upload/voucher review cards vanish on reload (DB mode)

**Date:** 2026-06-12
**Branch:** `fix/upload-voucher-persistence` (off `dev`) — pending merge
**Type:** Bug fix (DB-mode conversation persistence). No formal spec — fix, not a feature.

## Reported bug

After uploading a sale/purchase invoice or credit-note PDF, the voucher review card
appeared in chat, but on **page refresh or relogin the card (and the upload itself)
vanished** from the conversation.

## Root cause (verified)

DB-mode message persistence had two gaps in the write/upload flow:

1. **Primary — cards vanish.** `POST /chat/upload` (`chat_with_file`) →
   `orchestrator.process_file_upload()` persisted only an `UploadedFile` *audit* row
   (`orchestrator.py`), but created **no `Message` rows**. The normal `/chat` path
   persists both a user and an assistant `Message`; the upload path persisted neither.
   On reload, `getConversation()` returns only `Message` rows → the upload bubble *and*
   the `voucher_review` card were gone.

2. **Secondary — status didn't survive reload.** `POST /chat/voucher-action`
   (Write to Tally / Discard) updated a `VoucherEntry` audit row and the React state,
   but never updated the originating `Message.data` entry status. So even after gap 1,
   a written/discarded card would reload as re-actionable `"draft"`.

### Critical review finding (caught before merge)

The first implementation gated the `voucher-action` status update — and the
**pre-existing** `VoucherEntry` audit row — on `entry.get("conversation_id")`. But the
production entry dict (built in `orchestrator.py`) **never carries `conversation_id`**,
and the frontend passes `entry` through unmodified. So both silently no-op'd in
production; the first tests passed only because they injected a fake `conversation_id`
into the entry. This also revealed the pre-existing `VoucherEntry` audit row was a
silent no-op for the same reason.

**Fix:** thread `conversation_id` through the **request** (`VoucherActionRequest`), not
the entry dict. A revert sanity-check confirms the tests now fail without real threading.

## The fix

Backend (`backend/api/chat.py`, `backend/api/models.py`):

- **Upload path** (`chat_with_file`): after `process_file_upload` succeeds (DB mode +
  `conversation_id`), persist a user `Message` (`"<msg> [filename]"`) + assistant
  `Message` (`content=result["message"]`, `data=result["data"]`). Flush the user message
  before adding the assistant one (per-row `created_at` default → guarantees
  user→assistant reload order). Set `conversation.title` (if `None`) + bump
  `updated_at`, mirroring `_chat_db_mode`, so upload-first chats aren't stuck "New Chat".
- **Voucher-action path** (`voucher_action`): added `conversation_id: str = ""` to
  `VoucherActionRequest`; compute `conv_id = request.conversation_id or
  entry.get("conversation_id")` once; use it for the discard status update, the
  `VoucherEntry` audit row, and the approve status update. New helper
  `_update_persisted_voucher_status(db, conversation_id, entry_id, new_status)` mutates
  the originating `voucher_review` Message entry in place + `flag_modified(msg, "data")`
  so the JSONB change persists. → entry status reloads as `"written"` / `"deleted"`.

Frontend (`frontend/src/api/client.ts`, `frontend/src/components/ChatWindow.tsx`):

- `voucherAction(...)` gained a `conversationId` param, sent as `conversation_id` in the
  POST body; `ChatWindow.handleVoucherAction` passes the active `conversationId`.
- No `VoucherReviewCard`/`MessageBubble` change — they already render persisted
  `data.type === "voucher_review"` and read `entry.status`.

## Verification

| Layer | Result |
|---|---|
| Backend integration (`tests/integration/test_upload_voucher_persistence.py`, new) | 7 passed — incl. revert sanity-check proving tests depend on *real* `conversation_id` threading |
| Backend E2E (`tests/e2e/test_db_data_entry.py`, +3, real routes + Postgres, mock Vision/Tally) | 9 passed — upload→reload card persists + title set; approve→reload `status=="written"` + `VoucherEntry` row; discard→reload `status=="deleted"` |
| Backend regression (`-k voucher/upload/conversation/message`) | 87 passed, 3 skipped |
| Frontend unit (Vitest) | 323 passed; `tsc --noEmit` clean |
| Playwright db-mode voucher specs (×3 viewports) | 15 passed; screenshots visually inspected (draft/written/discarded/edit-form correct) |

Also repaired 4 **pre-existing** broken Playwright specs (`voucher-pending/written/discarded/edit-form`,
stale assertion text/selectors — confirmed failing on clean `dev`); regenerated one
baseline (`voucher-edit-form.png` mobile).

## Known / out of scope

- **No idempotency key** on upload `Message` insertion — a network-retried upload could
  persist a duplicate card. Matches existing `UploadedFile` behavior; the Tally-write
  dedup hard-block still prevents an actual double-write.
- 6 pre-existing `connect-company-*` Playwright failures — separate feature, untouched.
- Manual smoke against real Tally (upload → refresh → Write → refresh → "Written")
  recommended before merge; needs `TALLY_WRITE_ENABLED=true`.

## Lesson

Captured as [`LESSONS.md` §17](../LESSONS.md) — DB-mode write/upload endpoints must
persist `Message` rows and thread `conversation_id` via the request, not the entry dict.
