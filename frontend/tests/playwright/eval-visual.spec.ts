import { test, expect } from "@playwright/test";
import { readFileSync, mkdirSync } from "fs";
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

// Unclip scroll containers so element screenshots capture full content.
// toHaveScreenshot internally calls scrollIntoViewIfNeeded which re-scrolls,
// so we use raw .screenshot() after removing overflow constraints.
async function prepareForScreenshot(page: import("@playwright/test").Page) {
  await page.evaluate(() => {
    const header = document.querySelector("header");
    if (header) (header as HTMLElement).style.display = "none";
    const main = document.querySelector("main");
    if (main) {
      main.style.overflow = "visible";
      main.style.height = "auto";
    }
    const scrollContainer = document.querySelector(".overflow-y-auto");
    if (scrollContainer) {
      (scrollContainer as HTMLElement).style.overflow = "visible";
      (scrollContainer as HTMLElement).style.height = "auto";
    }
    // Also remove h-screen constraint on root app div
    const root = document.querySelector(".h-screen");
    if (root) {
      (root as HTMLElement).style.height = "auto";
      (root as HTMLElement).style.overflow = "visible";
    }
  });
}

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
    await page.waitForSelector("[class*='justify-start'] > div .prose", {
      timeout: 15000,
    });
    // Give charts/tables time to render
    await page.waitForTimeout(1000);

    // Unclip scroll containers for full element capture
    await prepareForScreenshot(page);

    // Use raw .screenshot() — toHaveScreenshot calls scrollIntoViewIfNeeded
    // which re-scrolls the container and undoes the overflow fix
    const lastMsg = page.locator("[class*='justify-start'] > div").last();
    const projectName = test.info().project.name; // mobile, tablet, desktop
    const screenshotDir = join(
      __dirname,
      "__screenshots__",
      projectName,
      "eval-visual.spec.ts",
    );
    mkdirSync(screenshotDir, { recursive: true });
    await lastMsg.screenshot({
      path: join(screenshotDir, `${fixture.name}_full.png`),
    });

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
