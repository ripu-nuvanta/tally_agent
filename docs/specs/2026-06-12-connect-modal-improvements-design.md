# Connect Tally Company modal — UX improvements

**Date:** 2026-06-12
**Branch:** `feat/connect-modal-improvements` (off `dev`)
**Type:** Feature / UX — frontend-only

## Goals (from user)

1. Rename **"Test Connection" → "Check Connection"** and restyle it (the full-width bright-blue
   button clashes with the green "Create Workspace").
2. When the connection check **fails**, show **setup steps** to enable Tally connectivity.
3. **Restore the workspace Name (nickname) field** (it existed before Group B, was removed).
4. Sidebar label shows the **original company name** with the **nickname in brackets** —
   and stops the current redundant `Company (Company)` duplication.

## Changes

### `ConnectCompanyModal.tsx`
- **Check Connection button:** text "Test Connection"→"Check Connection", "Connecting…"→"Checking…".
  Restyle from `bg-blue-600` to the neutral secondary style:
  `w-full px-4 py-2 text-sm rounded-lg bg-white border border-gray-300 text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50`.
- **Setup steps on failure:** when `connectionState === "error"` (live mode), below the existing
  red error line, render a steps panel (`data-testid="connect-steps"`, bordered info box):
  > To enable the connection:
  > 1. Open TallyPrime and load your company.
  > 2. Press **F1 (Help) → Settings → Connectivity**.
  > 3. Under **Client/Server configuration**, set **TallyPrime acts as: Both**.
  > 4. Set **Port** to 9000 (or match the port above).
  > 5. Ensure this device can reach the Tally machine (same network; allow the port through the firewall).
  > Then click **Check Connection** again.
- **Name (nickname) field:** restore `id="connect-name"`. Shown in the `connected` state
  (after Company, for both live and demo). Label "Name (optional)", `placeholder={selectedCompany || "e.g. My Books"}`,
  helper "Shown in the sidebar — defaults to the company name." New `nickname` state.
- **Create:** `name: nickname.trim() || selectedCompany` (config.tally_company stays `selectedCompany`).

### `Sidebar.tsx` (label, ~line 76)
Replace the unconditional `${tallyCompany} (${ws.name})` with: show `tallyCompany`, and append
` (${ws.name})` **only when** `ws.name` differs from `tallyCompany` (trim + case-insensitive).
No company configured → fall back to `ws.name`. Result:
- nickname given → `Bharat Traders Private Limited (My Books)`
- no nickname (name == company) → `Bharat Traders Private Limited`

## Tests

### Vitest
- `ConnectCompanyModal.test.tsx`: button label "Check Connection"; after a successful check the
  Name field (`#connect-name`) appears and is optional; Create with a nickname calls
  `createWorkspace` with `name` = nickname; Create with blank nickname → `name` = company; on a
  failed check the steps panel (`connect-steps`) is shown.
- `Sidebar.test.tsx`: label shows `Company (nick)` when they differ, and just `Company` when equal.

### Playwright (rewrite the 2 broken `connect-company` specs to the CURRENT flow)
The existing `connect-company-modal` / `connect-company-confirmation` specs encode the pre-Group-B
single-step "Connect" + friendly-name flow and have been failing. Rewrite to:
mock `**/api/tally/test-connection**` (POST → `{connected:true, companies:[...]}`) and `**/api/workspaces**`
(POST → workspace with `name:"My Books"`); open modal → **Check Connection** → company appears →
fill `#connect-name` "My Books" → **Create Workspace** → confirmation asserts
`connect-confirm-company` = company and `connect-confirm-name` = "My Books".
Add a `connect-company-steps` spec: failed check → assert the steps panel is visible.
Regenerate ONLY these specs' baselines; main agent visually inspects.

## Out of scope
No persisting/editing nickname after creation (separate from this modal); no new backend.
