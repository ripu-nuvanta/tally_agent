# Group A: UI/UX Enhancements — Design Spec

**Date:** 2026-04-12
**Status:** Draft
**Scope:** F4 (New Chat flow), F5 (voucher button disable), F6 (responsive layout) + demo/live indicator in DB mode header.
**Approach:** TDD — write tests first, then implement.

## Overview

Three follow-up enhancements from the B1a smoke test, packaged as one spec because they share the same components (ChatApp, Sidebar, Header, VoucherReviewCard, ChatWindow).

---

## F4: New Chat Flow Redesign

### Problem

1. Clicking "+ New Chat" creates a conversation in the DB immediately, even if the user never sends a message (orphan conversations).
2. Landing page (no conversation selected) looks identical to an active chat — unclear state.
3. On mobile, no indication of which workspace/conversation is active.

### Design

#### Deferred Conversation Creation

Conversations are created on first interaction, not on "+ New Chat" click.

**Flow:**
```
"+ New Chat" click → navigate to /w/{workspace-id} → show landing page (no conv in DB)
  → user types + sends OR clicks quick action OR uploads file
  → POST /api/workspaces/{id}/conversations → get conv_id
  → POST /api/chat (with conv_id) → get response
  → URL updates to /c/{conv_id}
  → sidebar refreshes via refreshTrigger → new conversation appears highlighted
```

**State management in ChatWindow:**
- `conversationId` starts as `undefined` on the landing page
- `handleSend` checks `if (!conversationId)` → creates conversation first, then sends
- `handleSendWithFile` does the same check
- Quick actions also route through `handleSend`
- After creation, `setConversationId(newId)` + `navigate(/c/${newId})` + increment `refreshTrigger`

**Edge cases:**
- File upload on landing page: creates conversation at upload time (same deferred logic)
- Page reload on `/w/{workspace-id}`: shows landing page again (no conversation to load)
- Quick action click: triggers `handleSend` with pre-filled message → creates conversation + sends
- Double-click protection: `loading` flag prevents duplicate creation

#### Landing Page

When workspace is active but no conversation selected (URL: `/w/{workspace-id}` or `/`):

- Show "TallyPrime AI Assistant" heading
- Show "Connected to **{workspace name}**" subtitle
- Show demo/live badge next to workspace name
- Show quick action buttons (P&L, receivables, cash balance, etc.)
- Show input box at bottom with placeholder: "Type or upload to start a conversation"
- Show paperclip (attach file) button
- No "+ New Chat" button on the landing page itself — the input box IS the new chat action

#### "+ New Chat" Sidebar Button

- Click navigates to `/w/{workspace-id}` (landing page)
- Does NOT create a conversation in DB
- Clears active conversation in ChatApp state (`setConversationId(undefined)`)
- Sidebar: no phantom "New Chat" entry — just the existing conversations

#### Active Workspace Highlight in Sidebar

- The workspace containing the active conversation (or the workspace navigated to via `/w/{id}`) gets a visual highlight: bold name, subtle background color (e.g., `bg-blue-50` on the workspace header row)
- Other workspaces remain normal weight

#### Mobile Header (Two-Line)

On mobile (`< md`), the header shows:
- **Line 1 (bold):** Chat title (or "New Chat" in blue if on landing page)
- **Line 2 (small, gray):** Workspace name
- Both lines truncate independently with `text-overflow: ellipsis`
- Hamburger ☰ icon on the left (for sidebar drawer)
- User avatar on the right

On desktop (`>= md`):
- Same two-line layout in the header area (replaces current single-line breadcrumb)
- No hamburger icon (sidebar always visible)

#### Demo/Live Mode Indicator

Add to the DB-mode header (currently missing — only legacy `Header.tsx` has it):
- Small badge next to workspace name or in the header: green dot + "Live" or orange dot + "Demo"
- Read from workspace config `mock_mode` field (already stored per workspace)
- No toggle in DB mode — workspace config controls mode (user changes it via ConnectCompanyModal or workspace settings)

---

## F5: VoucherReviewCard Button Disable After Action

### Problem

After clicking "Write to Tally" or "Discard," buttons remain active and can be clicked again, causing duplicate requests or confusing errors.

### Design

**State machine for entry status:**
```
draft → pending (on click) → written | discarded | error
                                                    ↓
                                                  draft (re-enable on error)
```

**Implementation in ChatWindow.handleVoucherAction:**
1. On action click: immediately update the entry's `status` to `"pending"` in the message data (optimistic UI)
2. Call `voucherAction()` API
3. On success: status already updated by server response (`"written"` or `"discarded"`)
4. On error: revert entry status to `"draft"` (buttons re-enable), show error message

**VoucherReviewCard rendering by status:**
- `draft`: All 3 buttons enabled (Write to Tally, Edit Entry, Discard)
- `pending`: All buttons disabled, clicked button shows spinner, others grayed out
- `written`: Green "Written to Tally ✓" badge, no buttons (already implemented)
- `discarded`: Gray "Discarded" badge, no buttons
- `error` (reverts to `draft`): Buttons re-enabled, error message shown above buttons

**Implementation in VoucherReviewCard:**
- Accept `status` from entry data (already in VoucherEntry interface)
- `pending` status: render buttons with `disabled` attribute + `opacity-50 cursor-not-allowed`
- Show spinner on the button that was clicked (pass `pendingAction` prop: `"approve" | "discard" | null`)

---

## F6: Responsive Layout

### Problem

Zero responsive classes in the codebase. Sidebar takes 75% of mobile viewport. VoucherReviewCard grid cramped. Modal overflows.

### Design

#### Sidebar — Hamburger Drawer (mobile < md)

**ChatApp layout changes:**
```tsx
// Desktop: sidebar always visible
<div className="flex-1 flex overflow-hidden">
  <div className="hidden md:flex">
    <Sidebar ... />
  </div>
  <main className="flex-1 overflow-hidden">
    <ChatWindow ... />
  </main>
</div>

// Mobile drawer overlay (when open):
{sidebarOpen && (
  <div className="fixed inset-0 z-40 md:hidden">
    <div className="fixed inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
    <div className="fixed inset-y-0 left-0 w-72 bg-white shadow-xl z-50">
      <Sidebar ... onConversationSelect={(ws, conv, name) => {
        handleConversationSelect(ws, conv, name);
        setSidebarOpen(false);
      }} />
    </div>
  </div>
)}
```

**Hamburger button:** Visible only on mobile (`md:hidden`), in the header, left side.

**Close triggers:**
- Tap backdrop (black/50 overlay)
- Select a conversation
- Click "+ New Chat"

#### VoucherReviewCard — Responsive Grid

```
grid-cols-1 md:grid-cols-2  (stack on mobile, 2-col on tablet+)
```

Action buttons: `flex flex-wrap gap-2` (natural wrapping on small screens).

#### ConnectCompanyModal — Mobile-Safe Width

```
w-full mx-4 md:mx-auto md:max-w-md
```

Full-width with 16px margins on mobile, centered max-width on desktop.

#### ChatWindow — No Change

`max-w-3xl mx-auto` already works well. Message bubbles at `max-w-[85%]` are responsive.

---

## New Routes

Add a workspace-scoped route for the landing page:

```tsx
<Route path="/w/:workspaceId" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
```

ChatApp reads `workspaceId` from params. If present without `conversationId`, shows landing page.

---

## Test Plan (TDD)

### Vitest Tests (write first)

**ChatWindow deferred creation (5 tests):**
1. `test_landing_page_shows_welcome_with_workspace_name` — render without conversationId, verify "Connected to {workspace}" text
2. `test_send_message_creates_conversation_then_sends` — mock createConversation + sendChat, verify both called in order
3. `test_file_upload_creates_conversation_first` — mock createConversation + sendChatWithFile, verify order
4. `test_quick_action_creates_conversation` — click quick action, verify createConversation called
5. `test_double_send_prevented_during_creation` — loading flag prevents duplicate

**VoucherReviewCard disable (4 tests):**
6. `test_buttons_disabled_when_status_pending` — render with status="pending", verify disabled attribute
7. `test_spinner_shown_on_pending_button` — verify spinner on the clicked action
8. `test_buttons_reenabled_on_error` — status reverts to draft after error
9. `test_buttons_not_shown_when_written` — status="written" shows badge, no buttons (already exists, verify)

**Sidebar active workspace (2 tests):**
10. `test_active_workspace_highlighted` — verify bg-blue-50 or similar on active workspace
11. `test_new_chat_navigates_to_workspace_landing` — verify onNewChat doesn't create conversation

**ChatApp responsive (3 tests):**
12. `test_sidebar_hidden_on_mobile_class` — verify `hidden md:flex` classes
13. `test_hamburger_visible_on_mobile` — verify `md:hidden` on hamburger button
14. `test_drawer_opens_on_hamburger_click` — click hamburger, verify sidebar overlay renders

**Header (3 tests):**
15. `test_two_line_header_shows_title_and_workspace` — verify both lines rendered
16. `test_header_truncates_long_names` — verify truncate/ellipsis classes
17. `test_demo_live_badge_shown` — verify mode indicator from workspace config

### Playwright Visual Tests (update existing + add new)

Update `db-mode.spec.ts` baselines after implementation (sidebar, header, landing page all change).

Add mobile-specific specs:
18. `mobile-hamburger-closed` — mobile viewport, sidebar hidden, hamburger visible
19. `mobile-hamburger-open` — click hamburger, sidebar drawer visible
20. `mobile-landing-page` — landing page on mobile with workspace name

**Total new tests: ~20 Vitest + ~3 Playwright specs (× 3 viewports = 9 runs)**

---

## Files Modified

| File | Changes |
|------|---------|
| `frontend/src/ChatApp.tsx` | Add hamburger state, mobile drawer, two-line header, `/w/:workspaceId` route handling, workspace landing page logic |
| `frontend/src/components/ChatWindow.tsx` | Deferred conversation creation in handleSend/handleSendWithFile, landing page welcome with workspace name |
| `frontend/src/components/Sidebar.tsx` | Active workspace highlight (bg-blue-50), onNewChat doesn't create conv |
| `frontend/src/components/VoucherReviewCard.tsx` | Button disable on pending status, spinner, error revert |
| `frontend/src/components/Header.tsx` | No changes (legacy only) |
| `frontend/src/App.tsx` | Add `/w/:workspaceId` route |
| `frontend/src/api/client.ts` | Possibly: createConversation function if not already exported |

## Files Created

| File | Purpose |
|------|---------|
| `frontend/src/__tests__/ChatWindow.deferred.test.tsx` | Deferred creation tests |
| `frontend/src/__tests__/VoucherReviewCard.disable.test.tsx` | Button disable tests |
| (expand existing test files for Sidebar, ChatApp, Header) | |

---

## Non-Goals

- No chat history list on workspace landing page (deferred — sidebar drawer covers this)
- No demo/live toggle in DB mode (workspace config controls mode)
- No conversation pagination or search
- No workspace settings page
- No drag-to-reorder conversations
- Desktop layout fundamentally unchanged (only header gets two-line treatment)

## Dependencies

- None — all frontend changes, no backend modifications needed
- Deferred conversation creation uses existing `POST /api/workspaces/{id}/conversations` endpoint
- Demo/live badge reads existing `workspace.config.mock_mode` field
