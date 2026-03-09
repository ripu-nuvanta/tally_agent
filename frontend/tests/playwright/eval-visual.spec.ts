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
