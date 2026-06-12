# Code review — sidebar conversation actions (rename + delete)

**Date:** 2026-06-12
**Branch:** `feat/sidebar-conversation-actions` (off `dev`) — pending merge
**Spec:** [`specs/2026-06-12-sidebar-conversation-actions-design.md`](specs/2026-06-12-sidebar-conversation-actions-design.md)

## Scope reviewed

Frontend-only feature: ChatGPT-style per-conversation kebab (`⋯`) menu with **Rename**
(inline edit) and **Delete** (confirm dialog) in the sidebar. Files: `ConversationList.tsx`,
`Sidebar.tsx`, `ChatApp.tsx`. Backend `DELETE`/`PATCH` endpoints + client fns pre-existed.

## Findings (3) — all fixed

1. **Popover clipped by the scroll container (reachability, fixed).** Menu/confirm were
   `absolute top-full`; the sidebar's `overflow-y-auto` clips overflow, so for the
   bottom-most conversation the menu opened off-screen and was unreachable. **Fix:** open
   upward (`bottom-full`) for the last two rows (guarded to lists of >2 so short lists and
   the top row are unaffected). No portal/fixed-positioning introduced.
2. **Rename blur silently discarded the edit (data loss, fixed).** Spec'd blur=cancel, but
   ChatGPT commits on blur. **Fix:** `commitRename` on Enter **and** blur (only when the
   trimmed value is non-empty and changed); Escape cancels via a `cancelledRef` so it never
   commits through the ensuing blur.
3. **a11y gaps on the menu/confirm (fixed).** Added `aria-haspopup="menu"` +
   `aria-expanded` on the kebab, `role="menu"`/`role="menuitem"` on the menu, and
   `role="dialog"`/`aria-modal`/`aria-label` on the delete confirm.

### Verified NOT bugs (during review)
- Enter-vs-blur rename race — `commitRename` reads the value synchronously; no stale value.
- Outside-click listener — added/removed with correct deps; uses `mousedown` + `containerRef.contains()` so in-menu clicks still fire.
- Kebab `stopPropagation` — kebab is a DOM sibling of the select button, never triggers select; one `openMenuId` closes other rows' menus.
- Sidebar error path — state mutated only after the awaited API resolves; `onActiveConversationDeleted` gated on success + `id === activeConversationId`; `prev[wsId]` guarded with `|| []`.

## Verification

| Layer | Result |
|---|---|
| Frontend unit (Vitest) | 351 passed (+19 feature, +review-fix tests); `tsc --noEmit` clean |
| Backend E2E (`tests/e2e/test_db_smoke.py`, +3) | 20 passed — rename reflected in detail GET; delete→404; delete scoped to owner |
| Playwright db-mode (×3 viewports) | 12 passed (`conversation-row-menu`, `-rename`, `-delete-confirm`, `-empty-after-delete`); screenshots visually inspected (desktop + mobile) |

## Out of scope
No bulk delete, drag-reorder, archive, or undo/restore UI (soft-delete exists server-side,
no restore surface this round). No toast system — API errors resync via `loadData()`.
