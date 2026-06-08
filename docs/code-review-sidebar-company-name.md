# Code Review: Sidebar Actual Company Name

**Branch:** `feat/sidebar-actual-company-name` vs `dev`
**Date:** 2026-06-05
**Spec:** `docs/specs/2026-06-05-sidebar-actual-company-name.md`
**Plan:** `docs/plans/2026-06-05-sidebar-actual-company-name-plan.md`

## Summary

The branch surfaces the actual Tally company name (`workspace.config.tally_company`) in the sidebar workspace header, rendered as `{tally_company} ({name})` with fallback to the friendly name when `tally_company` is missing or empty. Truncation + `title` hover applied. Diff is tightly scoped: one component change, 4 new Vitest cases, Playwright `db-mode.spec.ts` assertion/checklist updates, and only `db-mode.spec.ts` screenshot baselines regenerated.

## Strengths

- **Correct type-safe falsy guard.** `typeof tallyCompany === "string" && tallyCompany` handles `undefined`, non-string, and empty-string in one expression — all three state-matrix rows.
- **Spec-faithful.** Display format, fallback, truncate + `title`, and "header unchanged" implemented exactly as specified (header top bar verified in screenshots).
- **Robust truncation CSS.** `truncate min-w-0` on the label span + `overflow-hidden` on the button + `shrink-0` on the chevron — chevron never pushed out (verified visually in all 3 viewports by main agent).
- **Playwright discipline.** Content assertions before screenshots; assertions scoped to `aside` (not header); VISUAL CHECKLIST blocks updated; only db-mode baselines regenerated — responsive/eval-visual confirmed untouched.
- **Vitest coverage matches spec exactly:** with company, missing, empty string, title attribute.

## Issues

### Critical / Important
None.

### Minor (advisory, not blocking)

1. `frontend/tests/playwright/db-mode.spec.ts` — several pre-existing `text=Bharat Traders` substring locators remain; they still resolve correctly (label contains the substring) and target highlight/navigation, not label text. Acceptable as-is.
2. `frontend/src/components/Sidebar.tsx:87` (UX note) — for long company names at sidebar width `w-70`, the `(friendly name)` suffix truncates away entirely; full label available via `title` hover, per spec. No change required.

## Verification (run by main agent)

- Vitest: **254/254 passed** (`npm test`)
- Playwright: **61 passed + 11 skipped, 0 failed** (`npm run test:playwright`, all 3 viewports; responsive + eval-visual baselines green)
- Main-agent screenshot inspection: `sidebar-with-workspaces.png` in mobile/tablet/desktop — truncated label clean, chevron visible, NUVANTA AI fallback unchanged, header unaffected.

## Test suites NOT run

- Backend suites (unit/integration/e2e) — no backend change in this branch.
- `e2e_live` — requires real Tally + real Claude API.
- Eval (`collect`/`judge`) — requires real Claude API.

## Verdict

**Approve.** Merged into `dev`.
