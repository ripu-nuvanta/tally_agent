import { test, expect } from "@playwright/test";

test.describe("Responsive layout", () => {
  test("empty state renders correctly", async ({ page }) => {
    // Mock API endpoints to avoid needing backend
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

    await page.goto("/");
    await page.waitForSelector("text=TallyPrime AI Assistant", {
      timeout: 10000,
    });
    await expect(page).toHaveScreenshot("empty-state.png");
  });

  test("error state renders", async ({ page }) => {
    await page.route("**/api/health", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          tally_connected: false,
          tally_url: "http://localhost:9000",
        }),
      });
    });
    await page.route("**/api/companies", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ companies: [] }),
      });
    });
    await page.route("**/api/chat", (route) => {
      route.abort("connectionrefused");
    });

    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 },
    );

    const textarea = page.locator("textarea");
    await textarea.fill("test query");
    await textarea.press("Enter");

    await page.waitForSelector("text=Cannot connect to the server", {
      timeout: 10000,
    });
    await expect(page).toHaveScreenshot("error-state.png");
  });

  test("markdown response renders", async ({ page }) => {
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
        body: JSON.stringify({ companies: [] }),
      });
    });
    await page.route("**/api/chat", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message:
            "## Trial Balance\n\nHere are the results:\n\n- **Total Debit**: ₹50,00,000\n- **Total Credit**: ₹50,00,000\n\n> The books are balanced.",
          session_id: "test-session",
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 },
    );

    const textarea = page.locator("textarea");
    await textarea.fill("Show trial balance");
    await textarea.press("Enter");

    await page.waitForSelector("text=Trial Balance", { timeout: 10000 });
    await expect(page).toHaveScreenshot("markdown-response.png");
  });

  test("data table response renders", async ({ page }) => {
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
        body: JSON.stringify({ companies: [] }),
      });
    });
    await page.route("**/api/chat", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Here is the trial balance:",
          data: {
            headers: ["Ledger", "Debit", "Credit"],
            rows: [
              ["Sales Account", 0, 4034350],
              ["Purchase Account", 2500000, 0],
              ["Cash", 150000, 0],
              ["Bank Account", 1200000, 0],
              ["Rent", 50000, 0],
            ],
          },
          session_id: "test-session",
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 },
    );

    const textarea = page.locator("textarea");
    await textarea.fill("Trial balance");
    await textarea.press("Enter");

    await page.waitForSelector("text=Sales Account", { timeout: 10000 });
    await expect(page).toHaveScreenshot("data-table-response.png");
  });

  test("chart response renders", async ({ page }) => {
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
        body: JSON.stringify({ companies: [] }),
      });
    });
    await page.route("**/api/chat", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Sales breakdown by customer:",
          chart: {
            chart_type: "bar",
            title: "Sales by Customer",
            data: [
              { label: "HCODE", Sales: 1500000 },
              { label: "SMARTBIKE", Sales: 1000000 },
              { label: "ABC Corp", Sales: 800000 },
              { label: "XYZ Ltd", Sales: 500000 },
            ],
          },
          session_id: "test-session",
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector(
      'textarea[placeholder="Ask about your Tally data..."]',
      { timeout: 10000 },
    );

    const textarea = page.locator("textarea");
    await textarea.fill("Sales by customer");
    await textarea.press("Enter");

    await page.waitForSelector("text=Sales by Customer", { timeout: 10000 });
    await expect(page).toHaveScreenshot("chart-response.png");
  });
});
