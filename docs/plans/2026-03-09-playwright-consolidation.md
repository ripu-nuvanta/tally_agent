# Playwright Test Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge responsive and eval-visual Playwright tests into a single suite under `frontend/tests/playwright/` with unified config, 3 viewports, and full-message screenshots.

**Architecture:** Single Playwright config with 3 viewport projects (mobile/tablet/desktop). Two spec files share the config: `responsive.spec.ts` (page-level regression screenshots) and `eval-visual.spec.ts` (fixture-driven full-message screenshots). Both run across all viewports.

**Tech Stack:** Playwright, TypeScript, Vite dev server

---

### Task 1: Create unified Playwright config

**Files:**
- Create: `frontend/tests/playwright/playwright.config.ts`

**Step 1: Write the config file**

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
  },
  projects: [
    {
      name: "mobile",
      use: { viewport: { width: 375, height: 667 } },
    },
    {
      name: "tablet",
      use: { viewport: { width: 768, height: 1024 } },
    },
    {
      name: "desktop",
      use: { viewport: { width: 1280, height: 900 } },
    },
  ],
  webServer: {
    command: "npm run dev",
    port: 5173,
    cwd: "../..",
    reuseExistingServer: true,
  },
  snapshotPathTemplate:
    "{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.05,
    },
  },
});
```

**Step 2: Verify config loads**

Run: `cd frontend && npx playwright test --config tests/playwright/playwright.config.ts --list`
Expected: No errors (0 tests found since no spec files yet)

---

### Task 2: Move responsive spec to new location

**Files:**
- Create: `frontend/tests/playwright/responsive.spec.ts` (copy from `frontend/tests/responsive/responsive.spec.ts`)

**Step 1: Copy the responsive spec**

Copy `frontend/tests/responsive/responsive.spec.ts` to `frontend/tests/playwright/responsive.spec.ts` unchanged.

**Step 2: Verify tests are discovered**

Run: `cd frontend && npx playwright test --config tests/playwright/playwright.config.ts --list`
Expected: 15 tests listed (5 tests × 3 viewports)

**Step 3: Run the tests to generate baseline screenshots**

Run: `cd frontend && npx playwright test --config tests/playwright/playwright.config.ts responsive.spec.ts --update-snapshots`
Expected: 15 passed. Screenshots in `tests/playwright/__screenshots__/{mobile,tablet,desktop}/`

**Step 4: Commit**

```bash
git add frontend/tests/playwright/playwright.config.ts frontend/tests/playwright/responsive.spec.ts frontend/tests/playwright/__screenshots__/
git commit -m "feat: create unified playwright config, move responsive tests"
```

---

### Task 3: Move and rewrite eval-visual spec

**Files:**
- Create: `frontend/tests/playwright/eval-visual.spec.ts`

The key changes from the old version:
1. Remove separate element screenshots (table, chart) — full message bubble captures everything
2. Remove timestamped output dir — use Playwright's standard snapshot flow
3. Keep fixture-driven dynamic test generation
4. Add `toHaveScreenshot` for regression comparison (like responsive tests)

**Step 1: Write the new eval-visual spec**

```typescript
import { test, expect } from "@playwright/test";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load fixtures from shared location
const fixtures = JSON.parse(
  readFileSync(
    join(__dirname, "../../src/__tests__/fixtures/eval_responses.json"),
    "utf-8",
  ),
);

// Helper to setup route mocks
async function setupMocks(
  page: import("@playwright/test").Page,
  fixture: { message: string; data?: unknown; chart?: unknown },
) {
  await page.route("**/api/health", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        tally_connected: true,
        tally_url: "http://localhost:9000",
      }),
    });
  });
  await page.route("**/api/companies", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        companies: [{ name: "Bharat Traders Pvt Ltd" }],
      }),
    });
  });
  await page.route("**/api/chat", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message: fixture.message,
        data: fixture.data,
        chart: fixture.chart,
        session_id: "eval-test-session",
      }),
    });
  });
}

for (const fixture of fixtures) {
  test(`eval visual: ${fixture.name}`, async ({ page }) => {
    await setupMocks(page, fixture);
    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 },
    );

    // Send a query to trigger the mocked response
    const textarea = page.locator("textarea");
    await textarea.fill("test query");
    await textarea.press("Enter");

    // Wait for assistant message to appear
    await page.waitForSelector("[class*='justify-start'] .prose", {
      timeout: 15000,
    });
    // Give charts/tables time to render
    await page.waitForTimeout(1000);

    // Screenshot the full assistant message bubble (captures full element even if taller than viewport)
    const assistantMsgs = page.locator("[class*='justify-start']");
    const lastMsg = assistantMsgs.last();
    await expect(lastMsg).toHaveScreenshot(`${fixture.name}_full.png`);

    // Assertions
    expect(await lastMsg.textContent()).toBeTruthy();

    if (fixture.data) {
      const tables = lastMsg.locator("table");
      const expectedCount =
        Array.isArray(fixture.data) &&
        fixture.data.length > 0 &&
        typeof fixture.data[0] === "object" &&
        "headers" in fixture.data[0]
          ? fixture.data.length
          : 1;
      expect(await tables.count()).toBe(expectedCount);
    }

    if (fixture.chart) {
      const chartSpec = lastMsg.locator("[data-chart-spec]");
      expect(await chartSpec.count()).toBeGreaterThan(0);
    }
  });
}
```

**Step 2: Run tests to generate baseline screenshots**

Run: `cd frontend && npx playwright test --config tests/playwright/playwright.config.ts eval-visual.spec.ts --update-snapshots`
Expected: 15 passed (5 fixtures × 3 viewports). Screenshots in `__screenshots__/{mobile,tablet,desktop}/`

**Step 3: Verify screenshot quality**

Manually inspect a few screenshots to confirm:
- Full message bubble captured (text + table + chart all in one image)
- No cutoff at top or bottom (element screenshot captures full height)
- Multi-dataset fixture shows both tables + chart

**Step 4: Commit**

```bash
git add frontend/tests/playwright/eval-visual.spec.ts frontend/tests/playwright/__screenshots__/
git commit -m "feat: add eval-visual tests with full-message screenshots across 3 viewports"
```

---

### Task 4: Update package.json scripts and clean up old dirs

**Files:**
- Modify: `frontend/package.json` (scripts section)
- Delete: `frontend/tests/responsive/` (entire directory)
- Delete: `frontend/tests/eval-visual/` (entire directory)

**Step 1: Update package.json scripts**

Replace lines 13-15 in `frontend/package.json`:

```json
"test:responsive": "npx playwright test --config tests/responsive/playwright.config.ts",
"test:eval-visual": "npx playwright test --config tests/eval-visual/playwright.config.ts",
"test:all": "vitest run && npx playwright test --config tests/responsive/playwright.config.ts && npx playwright test --config tests/eval-visual/playwright.config.ts"
```

With:

```json
"test:playwright": "npx playwright test --config tests/playwright/playwright.config.ts",
"test:all": "vitest run && npm run test:playwright"
```

**Step 2: Delete old test directories**

```bash
rm -rf frontend/tests/responsive/
rm -rf frontend/tests/eval-visual/
```

**Step 3: Verify new scripts work**

Run: `cd frontend && npm run test:playwright`
Expected: 30 passed (15 responsive + 15 eval-visual)

Run: `cd frontend && npm run test:all`
Expected: Vitest unit tests pass, then Playwright tests pass

**Step 4: Update CLAUDE.md**

In the root `CLAUDE.md`, update the Frontend commands section:
- Replace `npm run test:responsive` and `npm run test:eval-visual` references with `npm run test:playwright`
- Update test count: "Playwright visual tests (30 tests: 5 responsive + 5 eval-visual × 3 viewports)"

**Step 5: Commit**

```bash
git add frontend/package.json CLAUDE.md
git rm -r frontend/tests/responsive/ frontend/tests/eval-visual/
git commit -m "refactor: consolidate playwright tests, update scripts"
```

---

### Task 5: Run full test suite and verify

**Step 1: Run complete frontend test suite**

Run: `cd frontend && npm run test:all`
Expected: All Vitest unit tests pass + all 30 Playwright tests pass

**Step 2: Verify no broken imports or references**

Run: `grep -r "test:responsive\|test:eval-visual\|tests/responsive\|tests/eval-visual" frontend/ --include="*.ts" --include="*.json" --include="*.md"`
Expected: No matches (all references cleaned up)

**Step 3: Final commit if any cleanup needed**

---

## Summary

| Before | After |
|--------|-------|
| 2 Playwright configs | 1 config |
| 2 test directories | 1 directory (`tests/playwright/`) |
| 3 npm scripts | 2 scripts (`test:playwright`, `test:all`) |
| Eval-visual: desktop only | Eval-visual: 3 viewports |
| Eval-visual: element screenshots | Full-message screenshots |
| 20 Playwright tests | 30 Playwright tests |
