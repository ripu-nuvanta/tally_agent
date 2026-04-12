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
  test("sidebar-with-workspaces", async ({ page, viewport }) => {
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

    // On mobile (width < 768), sidebar is hidden behind hamburger drawer
    const isMobile = (viewport?.width ?? 1280) < 768;
    if (isMobile) {
      // Open the sidebar drawer first — on mobile the sidebar is hidden md:flex
      const hamburger = page.locator('[aria-label="Open sidebar"]');
      await hamburger.waitFor({ timeout: 10000 });
      await hamburger.click();
      // Wait for drawer sidebar content — use .last() because the desktop sidebar
      // is also in the DOM (hidden) and Playwright picks the first (hidden) element
      await page.locator("text=Bharat Traders").last().waitFor({ state: "visible", timeout: 10000 });
      await expect(page.locator("text=Bharat Traders").last()).toBeVisible();
      await expect(page.locator("text=NUVANTA AI").last()).toBeVisible();
    } else {
      // Desktop/tablet: sidebar is always visible
      await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });
      await expect(page.locator("text=Bharat Traders").first()).toBeVisible();
      await expect(page.locator("text=NUVANTA AI").first()).toBeVisible();
    }

    await expect(page).toHaveScreenshot("sidebar-with-workspaces.png");
  });

  // Test 4: Chat view with workspace name in header
  test("chat-with-header", async ({ page, viewport }) => {
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

    // Wait for conversation content to load — use message body text which is always
    // visible regardless of viewport (unlike sidebar content which is md:hidden on mobile)
    await page.waitForSelector("text=Here is the trial balance for April 2025:", { timeout: 10000 });

    // Verify workspace name appears in header (data-testid is always in DOM)
    await expect(page.locator('[data-testid="header-workspace-name"]')).toBeVisible();
    await expect(page.locator('[data-testid="header-workspace-name"]')).toHaveText("Bharat Traders");

    // Verify TallyPrime AI header
    await expect(page.locator("text=TallyPrime AI").first()).toBeVisible();

    // On desktop/tablet: also verify sidebar shows "Trial Balance April"
    const isMobile = (viewport?.width ?? 1280) < 768;
    if (!isMobile) {
      await expect(page.locator("text=Trial Balance April").first()).toBeVisible();
    }

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

  // Test 6: Mobile — hamburger button visible, sidebar hidden by default
  test("mobile-hamburger-closed", async ({ page, viewport }) => {
    // Skip on non-mobile viewports (hamburger is md:hidden)
    if ((viewport?.width ?? 1280) >= 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/");

    // Wait for app to load
    await page.waitForSelector('[aria-label="Open sidebar"]', { timeout: 10000 });

    // Hamburger button should be visible
    await expect(page.locator('[aria-label="Open sidebar"]')).toBeVisible();

    // Sidebar content (workspace names) should NOT be visible — hidden behind drawer
    await expect(page.locator("text=Bharat Traders")).not.toBeVisible();

    await expect(page).toHaveScreenshot("mobile-hamburger-closed.png");
  });

  // Test 7: Mobile — click hamburger opens sidebar drawer
  test("mobile-hamburger-open", async ({ page, viewport }) => {
    // Skip on non-mobile viewports
    if ((viewport?.width ?? 1280) >= 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/");

    // Click hamburger to open sidebar drawer
    const hamburger = page.locator('[aria-label="Open sidebar"]');
    await hamburger.waitFor({ timeout: 10000 });
    await hamburger.click();

    // Sidebar drawer with workspace names should now be visible.
    // Use .last() because the desktop sidebar is also in the DOM (inside hidden md:flex)
    // and Playwright picks the first (hidden) element. The drawer renders second.
    await page.locator("text=Bharat Traders").last().waitFor({ state: "visible", timeout: 10000 });
    await expect(page.locator("text=NUVANTA AI").last()).toBeVisible();

    await expect(page).toHaveScreenshot("mobile-hamburger-open.png");
  });

  // Test 8: Mobile — workspace landing page shows hamburger + hint text
  test("mobile-landing-page", async ({ page, viewport }) => {
    // Skip on non-mobile viewports
    if ((viewport?.width ?? 1280) >= 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/w/ws-1");

    // Wait for the TallyPrime AI header to load
    await page.waitForSelector("text=TallyPrime AI", { timeout: 10000 });

    // Hamburger should be visible on mobile
    await expect(page.locator('[aria-label="Open sidebar"]')).toBeVisible();

    // The app title should be visible
    await expect(page.locator("text=TallyPrime AI").first()).toBeVisible();

    // The chat window hint text should be visible (always visible regardless of sidebar)
    await expect(page.locator("text=Ask me anything about your accounting data")).toBeVisible();

    await expect(page).toHaveScreenshot("mobile-landing-page.png");
  });
});
