# Spec: Mobile header — brand moves into drawer, chat title gets full width

**Date:** 2026-06-05
**Status:** Approved
**Scope:** Frontend only (DB mode)

## Problem

On mobile, the header (`ChatApp.tsx:84-118`) shows hamburger + "TallyPrime AI" brand + chat title + workspace badge. The brand is `shrink-0`, so the chat title is squeezed into leftover space and barely readable.

## Design

**Mobile (< 768px / Tailwind below `md`):**
- Header: hamburger + chat title block (full remaining width) + UserMenu. Brand and the `|` separator hidden.
- Drawer: a "TallyPrime AI" brand block at the top of the slide-out drawer, above the workspace list, with a bottom border. Same typography as header brand (`text-lg font-semibold text-gray-900`).
- Header chat title and sidebar conversation title share the same data source (`activeConversationTitle` / `conversation.title`) — they always match.

**Desktop/tablet (≥ md):** unchanged — brand in header, no brand in sidebar.

**Sidebar conversation titles:** keep single-line ellipsis, add `title` attribute with the full title (hover/long-press reveal).

## State matrix

| Viewport | Header | Drawer/sidebar |
|---|---|---|
| Mobile, conversation open | `☰ hi / Hey ●Live (K)` — no brand | Drawer top shows "TallyPrime AI" brand |
| Mobile, landing page | `☰ New Chat / Hey ●Live (K)` | same |
| Tablet/desktop | `TallyPrime AI \| hi / Hey ●Live (K)` (unchanged) | No brand block (desktop sidebar) |

## Changes

- `frontend/src/ChatApp.tsx` — `hidden md:block` on the `<h1>` brand, `hidden md:inline` on the `|` separator; brand block inside the mobile drawer wrapper above `<Sidebar>`.
- `frontend/src/components/ConversationList.tsx` — `title` attribute on conversation title button/span.
- Vitest — header brand hidden classes; drawer brand presence is covered by Playwright (drawer markup lives in ChatApp's mobile-only branch).
- Playwright `db-mode.spec.ts` — mobile tests: assert brand NOT visible in mobile header, brand visible in open drawer; update VISUAL CHECKLIST blocks; regenerate only db-mode baselines.

## Not changing

- Desktop/tablet header and sidebar.
- Legacy `Header.tsx` (frozen mode).
- Chat title data flow (already shared).
