# Code review — Connect Tally Company modal improvements

**Date:** 2026-06-12
**Branch:** `feat/connect-modal-improvements` (off `dev`) — pending merge
**Spec:** [`specs/2026-06-12-connect-modal-improvements-design.md`](specs/2026-06-12-connect-modal-improvements-design.md)

## Scope

Frontend-only. `ConnectCompanyModal.tsx` (Check Connection rename + neutral restyle,
setup-steps on failure, restored optional nickname field) and `Sidebar.tsx`
(`Company (nickname)` label only when the nickname differs).

## Findings

1. **Stale `nickname` state (fixed).** `nickname` was not reset on demo toggle / re-check,
   while `companies`/`selectedCompany`/`error` were — so a typed nickname could carry over
   into a different company context. **Fix:** `setNickname("")` in `handleTestConnection`
   and `handleMockToggle` (alongside the existing `setError("")`). Covered by a new test.
2. (Informational, not a bug) Name field renders whenever `connected` even if
   `selectedCompany === ""`; `handleCreate` guards `if (!selectedCompany) return` and
   `canCreate` requires a selected company, so no empty-company write can occur.

### Verified safe
- Button rename — no remaining "Test Connection" references (all tests updated).
- `nickname.trim() || selectedCompany` — whitespace-only nickname falls back to company.
- Steps panel — `error` cleared at the start of both handlers, so it can't linger.
- Sidebar label — `company`/`nick` are trim/`|| ""` guarded; worst case `""`, never crashes; `title` intact.
- a11y — `label htmlFor="connect-name"` matches the input id.

## Verification

| Layer | Result |
|---|---|
| Vitest | 363 passed; `tsc --noEmit` clean |
| Playwright db-mode (×3 viewports) | `connect-company-modal`, `connect-company-confirmation` (rewritten to the current flow), `connect-company-steps` (new) — 9 passed; **baselines regenerated + visually inspected** (desktop + mobile) |

> Note: the rewritten `connect-company` specs replace the pre-Group-B "Connect + Friendly Name"
> specs that had been failing. During regeneration a stale desktop baseline slipped through a
> subagent's `--update-snapshots` (reported "pixel-identical"); caught by main-agent visual
> inspection, then force-regenerated against a confirmed-fresh Vite. Reinforces: "N passed" is
> not proof — inspect the pixels.

## Out of scope
No post-creation nickname editing; no backend changes.
