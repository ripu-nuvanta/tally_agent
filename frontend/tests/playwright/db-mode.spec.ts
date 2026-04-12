import { test, expect } from "@playwright/test";

// Shared mock data
const mockUser = { id: "user-1", email: "test@example.com", name: "Test User" };
const mockToken = "fake-access-token-for-testing";

const mockWorkspaces = [
  {
    id: "ws-1",
    name: "Bharat Traders",
    agent_type: "tally",
    config: { tally_host: "localhost", tally_port: 9000 },
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

const mockConversationsWs1 = [
  { id: "conv-1", title: "Trial Balance April", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
  { id: "conv-2", title: "Expense Entry", tag: null, created_at: "2025-04-09T09:00:00Z", updated_at: "2025-04-09T09:30:00Z" },
];

const mockConversationsWs2 = [
  { id: "conv-3", title: "P&L Summary", tag: null, created_at: "2025-04-08T08:00:00Z", updated_at: "2025-04-08T08:15:00Z" },
];

/** Helper: mock auth endpoints to simulate a logged-in user */
async function mockLoggedIn(page: import("@playwright/test").Page) {
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: mockToken }),
    }),
  );
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockUser),
    }),
  );
}

/** Helper: mock workspace + conversation list endpoints */
async function mockWorkspaceData(page: import("@playwright/test").Page) {
  await page.route("**/api/workspaces", (route) => {
    // Only intercept GET requests (not POST)
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockWorkspaces),
      });
    } else {
      route.continue();
    }
  });

  await page.route("**/api/workspaces/ws-1/conversations", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockConversationsWs1),
      });
    } else {
      route.continue();
    }
  });

  await page.route("**/api/workspaces/ws-2/conversations", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockConversationsWs2),
      });
    } else {
      route.continue();
    }
  });
}

test.describe("DB-mode visual tests", () => {
  // Test 1: Login page renders when not authenticated
  test("login-page", async ({ page }) => {
    // Mock refresh to 401 → not logged in
    await page.route("**/api/auth/refresh", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid or expired token" }),
      }),
    );

    await page.goto("/login");

    // Wait for login form to appear
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });

    // Verify login form elements
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page.locator("text=TallyPrime AI")).toBeVisible();

    await expect(page).toHaveScreenshot("login-page.png");
  });

  // Test 2: Register page renders with password strength indicator
  test("register-page", async ({ page }) => {
    // Mock refresh to 401 → not logged in
    await page.route("**/api/auth/refresh", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid or expired token" }),
      }),
    );

    await page.goto("/register");

    // Wait for register form
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });

    // Verify register form is visible
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]').first()).toBeVisible();

    // Type a password to trigger password strength rendering
    await page.locator('input[type="password"]').first().fill("TestPass123!");

    await expect(page).toHaveScreenshot("register-page.png");
  });

  // Test 3: Sidebar with workspace list renders for logged-in user
  test("sidebar-with-workspaces", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Mock health endpoint to avoid errors
    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/");

    // Wait for sidebar with workspace names
    await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });

    // Verify both workspaces are shown
    await expect(page.locator("text=Bharat Traders")).toBeVisible();
    await expect(page.locator("text=NUVANTA AI")).toBeVisible();

    await expect(page).toHaveScreenshot("sidebar-with-workspaces.png");
  });

  // Test 4: Chat view with workspace name in header
  test("chat-with-header", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Mock the specific conversation endpoint
    await page.route("**/api/workspaces/ws-1/conversations/conv-1", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-1",
            title: "Trial Balance April",
            workspace_id: "ws-1",
            messages: [
              {
                id: "msg-1",
                role: "user",
                content: "Show me the trial balance for April 2025",
                data: null,
                chart: null,
              },
              {
                id: "msg-2",
                role: "assistant",
                content: "Here is the trial balance for April 2025:",
                data: {
                  headers: ["Ledger", "Debit", "Credit"],
                  rows: [
                    ["Sales Account", 0, 4034350],
                    ["Purchase Account", 2500000, 0],
                    ["Cash", 150000, 0],
                  ],
                },
                chart: null,
              },
            ],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    // Mock health
    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-1");

    // Wait for conversation content to load
    await page.waitForSelector("text=Trial Balance April", { timeout: 10000 });

    // Verify workspace name appears in header
    await expect(page.locator("text=Bharat Traders").first()).toBeVisible();

    // Verify TallyPrime AI header
    await expect(page.locator("text=TallyPrime AI").first()).toBeVisible();

    await expect(page).toHaveScreenshot("chat-with-header.png");
  });

  // Test 5: Voucher review card renders in chat
  test("voucher-review-card", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Mock conversation with voucher_review data message
    await page.route("**/api/workspaces/ws-1/conversations/conv-2", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-2",
            title: "Expense Entry",
            workspace_id: "ws-1",
            messages: [
              {
                id: "msg-1",
                role: "user",
                content: "I have a receipt from Staples for ₹5,900 on April 10",
                data: null,
                chart: null,
              },
              {
                id: "msg-2",
                role: "assistant",
                content: "I've extracted the expense entry. Please review:",
                data: {
                  type: "voucher_review",
                  entries: [
                    {
                      id: "entry-1",
                      voucher_type: "Journal",
                      date: "20250410",
                      vendor_name: "Staples India",
                      amount: 5000,
                      debit_ledger: "Office Supplies",
                      credit_ledger: "ICICI Bank",
                      narration: "Office supplies from Staples",
                      gst_entries: [
                        { ledger: "Input CGST 9%", amount: 450 },
                        { ledger: "Input SGST 9%", amount: 450 },
                      ],
                      status: "draft",
                      warnings: [],
                      is_new_ledger: false,
                      suggested_parent: null,
                    },
                  ],
                  available_ledgers: ["Office Supplies", "Travel", "Utilities"],
                  available_payment_ledgers: ["ICICI Bank", "Cash", "Petty Cash"],
                },
                chart: null,
              },
            ],
            created_at: "2025-04-09T09:00:00Z",
            updated_at: "2025-04-09T09:30:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    // Mock health
    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-2");

    // Wait for voucher review card to appear
    await page.waitForSelector('[data-testid="voucher-review-entry-1"]', {
      timeout: 10000,
    });

    // Verify voucher review card content
    await expect(
      page.locator('[data-testid="voucher-review-entry-1"]'),
    ).toBeVisible();
    await expect(page.locator("text=Staples India")).toBeVisible();
    await expect(page.locator("text=Write to Tally")).toBeVisible();

    await expect(page).toHaveScreenshot("voucher-review-card.png");
  });
});
