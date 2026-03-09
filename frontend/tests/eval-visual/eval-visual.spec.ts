import { test, expect } from "@playwright/test";
import { readFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load fixtures
const fixtures = JSON.parse(
  readFileSync(
    join(__dirname, "../../src/__tests__/fixtures/eval_responses.json"),
    "utf-8"
  )
);

// Create timestamped output dir
const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const screenshotDir = join(
  __dirname,
  "../../test-results",
  `eval-visual-${timestamp}`
);
mkdirSync(screenshotDir, { recursive: true });

// Helper to setup route mocks
async function setupMocks(page: any, fixture: any) {
  await page.route("**/api/health", (route: any) => {
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
  await page.route("**/api/companies", (route: any) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        companies: [{ name: "Bharat Traders Pvt Ltd" }],
      }),
    });
  });
  await page.route("**/api/chat", (route: any) => {
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
  test(`visual: ${fixture.name}`, async ({ page }) => {
    await setupMocks(page, fixture);
    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 }
    );

    // Send a query to trigger the mocked response
    const textarea = page.locator("textarea");
    await textarea.fill("test query");
    await textarea.press("Enter");

    // Wait for assistant message to appear (left-aligned bubble)
    await page.waitForSelector("[class*='justify-start'] .prose", {
      timeout: 15000,
    });
    // Give charts/tables time to render
    await page.waitForTimeout(1000);

    // Screenshot the full assistant message
    const assistantMsgs = page.locator("[class*='justify-start']");
    const lastMsg = assistantMsgs.last();
    await lastMsg.screenshot({
      path: join(screenshotDir, `${fixture.name}_full.png`),
    });

    // Screenshot table if present
    const table = lastMsg.locator("table");
    if ((await table.count()) > 0) {
      await table.first().screenshot({
        path: join(screenshotDir, `${fixture.name}_table.png`),
      });
    }

    // Screenshot chart if present
    const chart = lastMsg.locator("[data-testid='chart-container']");
    if ((await chart.count()) > 0) {
      await chart.first().screenshot({
        path: join(screenshotDir, `${fixture.name}_chart.png`),
      });
    }

    // Basic assertions
    expect(await lastMsg.textContent()).toBeTruthy();

    if (fixture.data) {
      expect(await table.count()).toBeGreaterThan(0);
    }

    if (fixture.chart) {
      // Chart container should exist with data-chart-spec attribute
      const chartSpec = lastMsg.locator("[data-chart-spec]");
      expect(await chartSpec.count()).toBeGreaterThan(0);
    }
  });
}
