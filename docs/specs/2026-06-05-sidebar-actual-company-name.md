# Spec: Sidebar shows actual Tally company name

**Date:** 2026-06-05
**Status:** Approved
**Scope:** Frontend only (DB mode)

## Problem

The sidebar workspace header shows only the user-entered friendly name (e.g. "HEY"). The actual Tally company name is already captured at connect time (two-step `ConnectCompanyModal`, merged `497971a`) and stored in `workspace.config.tally_company`, but never surfaced in the sidebar.

## Design

**Display format (single line):**

```
{config.tally_company} ({workspace.name})
```

Example: `Bharat Traders Private Limited (Hey)`

**Fallback:** If `config.tally_company` is absent (workspaces created before the two-step connect modal shipped), show just `workspace.name` — identical to current behavior.

**Long names:** Truncate with ellipsis (Tailwind `truncate`) so the label never wraps or pushes out the collapse chevron. Full label in `title` attribute for hover.

## State matrix

| State | tally_company | Render |
|---|---|---|
| New workspace | `"Bharat Traders Private Limited"` | `Bharat Traders Private Limited (Hey)` (truncated, title attr = full) |
| Legacy workspace | missing/undefined | `Hey` |
| Empty string edge case | `""` | `Hey` (treat falsy as missing) |

## Changes

- `frontend/src/components/Sidebar.tsx` — read `ws.config.tally_company` (string, falsy → fallback), render combined label with `truncate` + `title`.
- Vitest (`frontend/src/__tests__/`) — cases: with `tally_company`, without, empty string, `title` attribute contains full label.
- Playwright `db-mode.spec.ts` — mock workspace fixture gains `config.tally_company`; content assertion on new label before screenshots; regenerate **only** `__screenshots__/*/db-mode.spec.ts/` baselines per § Playwright discipline.

## Not changing

- Header top bar (still friendly name).
- Backend — `tally_company` already stored and returned by `GET /api/workspaces`.
- Multi-company selector — parked (`docs/open-items-parked.md`).
