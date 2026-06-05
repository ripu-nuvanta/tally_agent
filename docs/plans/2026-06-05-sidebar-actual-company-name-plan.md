# Sidebar Actual Company Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sidebar workspace header shows `{config.tally_company} ({workspace.name})` when the actual Tally company name is stored, falling back to the friendly name alone.

**Architecture:** Frontend-only change. `workspace.config.tally_company` is already stored by `ConnectCompanyModal` and returned by `GET /api/workspaces`. `Sidebar.tsx` derives a display label per workspace; truncation via Tailwind `truncate` with full label in `title`.

**Tech Stack:** React + TypeScript, Vitest + React Testing Library, Playwright.

**Spec:** `docs/specs/2026-06-05-sidebar-actual-company-name.md`

---

### Task 1: Sidebar label logic (TDD)

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx:85` (workspace header `<span>`)
- Test: `frontend/src/__tests__/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/__tests__/Sidebar.test.tsx` inside `describe("Sidebar", ...)`:

```tsx
describe("workspace label with tally_company", () => {
  const wsWithCompany: WorkspaceData[] = [
    { id: "ws-1", name: "Hey", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    { id: "ws-2", name: "Nuvanta Co", agent_type: "tally", config: {}, memory: {}, created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
    { id: "ws-3", name: "Legacy Books", agent_type: "tally", config: { tally_company: "" }, memory: {}, created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" },
  ];

  beforeEach(() => {
    mockedClient.getWorkspaces.mockResolvedValue(wsWithCompany);
    mockedClient.getConversations.mockResolvedValue([]);
  });

  it("shows actual company name with friendly name in parentheses", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText("Bharat Traders Private Limited (Hey)")).toBeInTheDocument();
    });
  });

  it("falls back to friendly name when tally_company is missing", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText("Nuvanta Co")).toBeInTheDocument();
    });
  });

  it("falls back to friendly name when tally_company is empty string", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText("Legacy Books")).toBeInTheDocument();
    });
  });

  it("sets title attribute to the full label for hover on truncation", async () => {
    renderSidebar();
    await waitFor(() => {
      const label = screen.getByText("Bharat Traders Private Limited (Hey)");
      expect(label).toHaveAttribute("title", "Bharat Traders Private Limited (Hey)");
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: the 2 new label tests FAIL (`Bharat Traders Private Limited (Hey)` not found, title attr missing); fallback tests may pass already.

- [ ] **Step 3: Implement minimal change in Sidebar.tsx**

In `frontend/src/components/Sidebar.tsx`, inside `workspaces.map((ws) => {` (around line 72-74), derive the label:

```tsx
const tallyCompany = ws.config?.tally_company;
const label = typeof tallyCompany === "string" && tallyCompany ? `${tallyCompany} (${ws.name})` : ws.name;
```

Replace line 85:

```tsx
<span>{ws.name}</span>
```

with:

```tsx
<span className="truncate text-left" title={label}>{label}</span>
```

And on line 86 add `shrink-0` to the chevron so truncation doesn't squeeze it:

```tsx
<span className="text-sm text-gray-400 shrink-0">{isCollapsed ? "▸" : "▾"}</span>
```

Note: the parent `<button>` is `w-full flex items-center justify-between` — `truncate` on the label span works because flex children get `min-width: 0` is NOT automatic; add `min-w-0` to the label span if truncation fails in test/browser:

```tsx
<span className="truncate text-left min-w-0" title={label}>{label}</span>
```

(Use the `min-w-0` variant directly — it is harmless when not needed.)

- [ ] **Step 4: Run the full Sidebar test file**

Run: `cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx`
Expected: ALL tests PASS (new + existing — existing fixtures have `config: {}` so labels are unchanged).

- [ ] **Step 5: Run the whole frontend unit suite**

Run: `cd frontend && npm test`
Expected: all ~237+ tests pass. If any other test renders Sidebar with a `tally_company` config, update its expectation to the combined label.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/__tests__/Sidebar.test.tsx
git commit -m "feat(fe): sidebar shows actual Tally company name with friendly name"
```

---

### Task 2: Playwright db-mode coverage

**Files:**
- Modify: `frontend/tests/playwright/db-mode.spec.ts`
- Regenerate: `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/db-mode.spec.ts/` ONLY

PREREQUISITE: backend running (`uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 2>&1 | tee logs/be_sidebar_label.log`).

- [ ] **Step 1: Update mock workspace fixture**

In `frontend/tests/playwright/db-mode.spec.ts:7-22`, give ws-1 a `tally_company` and leave ws-2 without one (covers fallback visually):

```ts
const mockWorkspaces = [
  {
    id: "ws-1",
    name: "Bharat Traders",
    agent_type: "tally",
    config: { tally_host: "localhost", tally_port: 9000, tally_company: "Bharat Traders Private Limited" },
    created_at: "2025-04-01T00:00:00Z",
  },
  {
    id: "ws-2",
    name: "NUVANTA AI",
    agent_type: "tally",
    config: { tally_host: "localhost", tally_port: 9000 },
    created_at: "2025-04-02T00:00:00Z",
  },
];
```

- [ ] **Step 2: Update assertions that reference the ws-1 sidebar label**

Search the spec for sidebar-scoped `"Bharat Traders"` text assertions (e.g. the drawer tests near lines 473-485 and 543-555, and `sidebar-with-workspaces` near line 161). For each assertion that targets the SIDEBAR workspace header, change the expected text to `Bharat Traders Private Limited (Bharat Traders)`. Do NOT change header assertions — `[data-testid="header-workspace-name"]` still shows `Bharat Traders` (header is out of scope). Add a content assertion before the `sidebar-with-workspaces` screenshot:

```ts
await expect(
  page.locator("aside").getByText("Bharat Traders Private Limited (Bharat Traders)"),
).toBeVisible();
await expect(page.locator("aside").getByText("NUVANTA AI")).toBeVisible();
```

Update each affected `// VISUAL CHECKLIST:` block to state: sidebar shows "Bharat Traders Private Limited (Bharat Traders)" (truncated with ellipsis if it overflows), "NUVANTA AI" unchanged (no tally_company), chevron still visible at right edge.

- [ ] **Step 3: Delete ONLY db-mode screenshot baselines**

```bash
rm -rf "frontend/tests/playwright/__screenshots__/mobile/db-mode.spec.ts" \
       "frontend/tests/playwright/__screenshots__/tablet/db-mode.spec.ts" \
       "frontend/tests/playwright/__screenshots__/desktop/db-mode.spec.ts"
```

Do NOT touch responsive or eval-visual baselines.

- [ ] **Step 4: Run Playwright db-mode spec to regenerate**

Run: `cd frontend && npx playwright test tests/playwright/db-mode.spec.ts`
Expected: ~49 pass + 11 skip across 3 viewports; new baselines written.

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/playwright/db-mode.spec.ts "frontend/tests/playwright/__screenshots__"
git commit -m "test(playwright): db-mode sidebar label with actual company name"
```

---

### Task 3: Visual review + suite verification (MAIN AGENT — not a subagent)

- [ ] **Step 1: Main agent inspects regenerated screenshots**

Read PNGs in `frontend/tests/playwright/__screenshots__/{mobile,tablet,desktop}/db-mode.spec.ts/` (at minimum `sidebar-with-workspaces.png` and the drawer-open screenshots in all 3 viewports). Check: combined label visible/truncated cleanly, chevron not pushed out, no overlap/cutoff, NUVANTA AI unchanged.

- [ ] **Step 2: Run full frontend verification**

Run: `cd frontend && npm test && npx playwright test`
Expected: all unit tests pass; Playwright ~49 pass + 11 skip (responsive + eval-visual baselines untouched and green).

- [ ] **Step 3: Code review**

Use superpowers:requesting-code-review on the branch diff; store result in `docs/code-review-sidebar-company-name.md`. State which suites were NOT run (backend suites — no backend change; e2e_live; eval).

- [ ] **Step 4: Merge to dev**

```bash
git checkout dev && git merge --no-ff feat/sidebar-actual-company-name
```
