# Sidebar conversation actions — rename + delete (ChatGPT-style)

**Date:** 2026-06-12
**Branch:** `feat/sidebar-conversation-actions` (off `dev`)
**Type:** Feature — frontend-only (backend already supports it)

## Goal

Let users **rename** and **delete** individual conversations from the sidebar, the
way ChatGPT does: a kebab (`⋯`) menu per conversation row, with Rename (inline edit)
and Delete (confirm dialog).

## Why it's frontend-only

The backend and API client already exist:
- `DELETE /workspaces/{ws}/conversations/{id}` → soft-delete (`is_deleted = True`),
  returns `204` (`backend/api/conversations.py:125`).
- `PATCH /workspaces/{ws}/conversations/{id}` (rename via `{title}`) →
  `updateConversation` (`frontend/src/api/client.ts:145`).
- `deleteConversation` client fn exists (`client.ts:157`).

So no backend change. We wire these into the sidebar UI.

## Decisions (from brainstorming)

- **Actions:** Rename **and** Delete.
- **Affordance:** kebab `⋯` menu per row (hover-revealed; always shown for the active row).
- **Delete confirm:** a small confirm dialog ("Delete this chat? This can't be undone.").
- **Deleting the active chat:** navigate to the **workspace landing** (the New-Chat empty state).
- **Error handling:** no toast system exists → on API error, re-`loadData()` to resync
  with the server (reverts the optimistic change).

## Components

### `ConversationList.tsx`
Each row becomes a relative-positioned hover `group` containing:
- The existing title button (select) — unchanged behaviour, room made on the right for the kebab.
- A **kebab `⋯` button** — `opacity-0 group-hover:opacity-100`, plus always-visible when
  `conv.id === activeConversationId`; `aria-label="Conversation options"`,
  `data-testid={`conv-menu-btn-${conv.id}`}`.
- A **popover menu** (absolute, anchored to the row) with:
  - **Rename** → switches the row into an inline `<input>` (prefilled with current title;
    Enter saves via `onRename(id, value.trim())`, Esc cancels, blur cancels).
    Empty/whitespace title is ignored (no-op cancel).
  - **Delete** → opens a **confirm dialog** (Cancel · Delete). Confirm calls `onDelete(id)`.
- Menu closes on outside-click and Esc; only one menu open at a time (local `openMenuId` state).
- New props: `onRename(conversationId: string, title: string) => void`,
  `onDelete(conversationId: string) => void`.

State held locally in `ConversationList`: `openMenuId`, `renamingId`, `renameValue`,
`confirmDeleteId`.

### `Sidebar.tsx`
Implements the handlers and passes them down:
- `handleRename(wsId, id, title)` → `await updateConversation(wsId, id, { title })` →
  update `conversations[wsId]` in place (optimistic); on error → `loadData()`.
- `handleDelete(wsId, id)` → `await deleteConversation(wsId, id)` → drop from
  `conversations[wsId]` (optimistic); on error → `loadData()`. If `id === activeConversationId`,
  call new prop `onActiveConversationDeleted(wsId)`.
- New prop: `onActiveConversationDeleted?: (workspaceId: string) => void`.

### `ChatApp` (parent of Sidebar)
- Provide `onActiveConversationDeleted(wsId)` → navigate to the workspace landing
  (`/w/:wsId`) and reset the active conversation, mirroring the existing onNewChat-to-landing
  path. (Exact wiring confirmed against ChatApp during implementation.)

## State matrix (for tests / Playwright)

| Component | States |
|---|---|
| Conversation row | default · hover (kebab visible) · active (kebab visible) · menu-open · renaming (input) · delete-confirm-open |
| Sidebar | has-conversations · empty-after-deleting-last (only "+ New Chat" remains) |

## Test plan

### Frontend unit (Vitest — `ConversationList.test.tsx`, `Sidebar.test.tsx`)
- Kebab hidden by default, shown for active row; click opens menu; Esc / outside-click closes it.
- Rename: click Rename → input appears prefilled; Enter calls `onRename` with trimmed value;
  Esc/blur cancels (no call); empty value does not call `onRename`.
- Delete: click Delete → confirm dialog; Cancel does **not** call `onDelete`; Delete **does**.
- Selecting a row still calls `onSelect` (kebab click does not trigger select — stopPropagation).
- Sidebar: `handleDelete` removes the item and calls `onActiveConversationDeleted` only when the
  deleted id is active; `handleRename` updates the title; both call `loadData()` on a rejected API.
  (Mock `deleteConversation`/`updateConversation`.)

### Backend E2E (verify/extend `tests/e2e/test_db_*`)
- Rename: `PATCH` title → `GET` conversation reflects new title.
- Delete: `DELETE` → `204`; the conversation no longer appears in the list and `GET` of it 404s.
- Delete the active/only conversation → list becomes empty. (Confirm existing coverage; add gaps.)

### Playwright db-mode (`db-mode.spec.ts`, ×3 viewports)
New specs (mock `getConversations` + `DELETE`/`PATCH` routes):
- `conversation-row-menu` — hover/active kebab visible, menu open shows Rename + Delete.
- `conversation-rename` — Rename → input visible, prefilled.
- `conversation-delete-confirm` — Delete → confirm dialog visible.
- `conversation-empty-after-delete` — list shows only "+ New Chat".
Content assertions before each `toHaveScreenshot`; `// VISUAL CHECKLIST:` block per snapshot;
main agent visually inspects every viewport.

## Out of scope / YAGNI
- No multi-select / bulk delete. No drag-reorder. No "Archive". No undo/restore UI
  (soft-delete exists server-side but no restore surface this round).
- No toast/notification system (kept minimal — error → resync).

## Lifecycle
Spec → plan → implement (subagent + TDD) → tests (unit + E2E + Playwright) → code review →
merge to `dev` → docs (roadmap, CLAUDE.md row at merge).
