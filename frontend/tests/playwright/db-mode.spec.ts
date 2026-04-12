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
  { id: "conv-10", title: "Pending Voucher", tag: null, created_at: "2025-04-08T08:00:00Z", updated_at: "2025-04-08T08:05:00Z" },
  { id: "conv-11", title: "Written Voucher", tag: null, created_at: "2025-04-07T08:00:00Z", updated_at: "2025-04-07T08:05:00Z" },
  { id: "conv-12", title: "Discarded Voucher", tag: null, created_at: "2025-04-06T08:00:00Z", updated_at: "2025-04-06T08:05:00Z" },
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

  // Test 9: Voucher pending state — buttons disabled with spinner
  test("voucher-pending", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/workspaces/ws-1/conversations/conv-10", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-10",
            title: "Pending Voucher",
            workspace_id: "ws-1",
            messages: [
              {
                id: "msg-p1",
                role: "user",
                content: "Add expense for Staples ₹5,900",
                data: null,
                chart: null,
              },
              {
                id: "msg-p2",
                role: "assistant",
                content: "Writing to Tally...",
                data: {
                  type: "voucher_review",
                  entries: [
                    {
                      id: "entry-pending",
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
                      status: "pending",
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
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-10");

    await page.waitForSelector('[data-testid="voucher-review-entry-pending"]', { timeout: 10000 });

    // Verify pending state: "Write to Tally" button should be disabled
    const writeBtn = page.locator("button", { hasText: "Write to Tally" });
    await expect(writeBtn).toBeDisabled();

    // Verify "Pending" label is shown in the voucher card
    await expect(page.locator("text=Expense Entry — Pending")).toBeVisible();

    await expect(page).toHaveScreenshot("voucher-pending.png");
  });

  // Test 10: Voucher written state — green card, no action buttons
  test("voucher-written", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/workspaces/ws-1/conversations/conv-11", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-11",
            title: "Written Voucher",
            workspace_id: "ws-1",
            messages: [
              {
                id: "msg-w1",
                role: "user",
                content: "Add expense for Amazon ₹12,000",
                data: null,
                chart: null,
              },
              {
                id: "msg-w2",
                role: "assistant",
                content: "Entry written to Tally successfully.",
                data: {
                  type: "voucher_review",
                  entries: [
                    {
                      id: "entry-written",
                      voucher_type: "Journal",
                      date: "20250411",
                      vendor_name: "Amazon India",
                      amount: 12000,
                      debit_ledger: "Office Supplies",
                      credit_ledger: "ICICI Bank",
                      narration: "Office equipment from Amazon",
                      gst_entries: [],
                      status: "written",
                      warnings: [],
                      is_new_ledger: false,
                      suggested_parent: null,
                    },
                  ],
                  available_ledgers: ["Office Supplies", "Travel"],
                  available_payment_ledgers: ["ICICI Bank", "Cash"],
                },
                chart: null,
              },
            ],
            created_at: "2025-04-11T10:00:00Z",
            updated_at: "2025-04-11T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-11");

    await page.waitForSelector('[data-testid="voucher-review-entry-written"]', { timeout: 10000 });

    // Verify "Written" label in the voucher card
    await expect(page.locator("text=Expense Entry — Written")).toBeVisible();

    // No action buttons should be present inside the voucher card
    const writtenCard = page.locator('[data-testid="voucher-review-entry-written"]');
    await expect(writtenCard.locator("button", { hasText: "Write to Tally" })).not.toBeVisible();
    await expect(writtenCard.locator("button", { hasText: "Discard" })).not.toBeVisible();

    await expect(page).toHaveScreenshot("voucher-written.png");
  });

  // Test 11: Voucher discarded state — gray card, no action buttons
  test("voucher-discarded", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/workspaces/ws-1/conversations/conv-12", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-12",
            title: "Discarded Voucher",
            workspace_id: "ws-1",
            messages: [
              {
                id: "msg-d1",
                role: "user",
                content: "Add expense for Flipkart ₹8,500",
                data: null,
                chart: null,
              },
              {
                id: "msg-d2",
                role: "assistant",
                content: "Entry discarded.",
                data: {
                  type: "voucher_review",
                  entries: [
                    {
                      id: "entry-deleted",
                      voucher_type: "Journal",
                      date: "20250412",
                      vendor_name: "Flipkart India",
                      amount: 8500,
                      debit_ledger: "Office Supplies",
                      credit_ledger: "ICICI Bank",
                      narration: "Supplies from Flipkart",
                      gst_entries: [],
                      status: "deleted",
                      warnings: [],
                      is_new_ledger: false,
                      suggested_parent: null,
                    },
                  ],
                  available_ledgers: ["Office Supplies", "Travel"],
                  available_payment_ledgers: ["ICICI Bank", "Cash"],
                },
                chart: null,
              },
            ],
            created_at: "2025-04-12T10:00:00Z",
            updated_at: "2025-04-12T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-12");

    await page.waitForSelector('[data-testid="voucher-review-entry-deleted"]', { timeout: 10000 });

    // Verify "Discarded" label in the voucher card
    await expect(page.locator("text=Expense Entry — Discarded")).toBeVisible();

    // No action buttons inside the voucher card
    const discardedCard = page.locator('[data-testid="voucher-review-entry-deleted"]');
    await expect(discardedCard.locator("button", { hasText: "Write to Tally" })).not.toBeVisible();
    await expect(discardedCard.locator("button", { hasText: "Edit Entry" })).not.toBeVisible();

    await expect(page).toHaveScreenshot("voucher-discarded.png");
  });

  // Test 12: Sidebar active workspace highlight — bg-blue-50 on active workspace
  test("sidebar-active-highlight", async ({ page, viewport }) => {
    // Sidebar only visible on tablet/desktop
    if ((viewport?.width ?? 1280) < 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Mock the conversation endpoint so the route resolves
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
              { id: "msg-1", role: "user", content: "Show trial balance", data: null, chart: null },
              { id: "msg-2", role: "assistant", content: "Here is the trial balance.", data: null, chart: null },
            ],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-1");

    // Wait for sidebar to load with workspace names
    await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });

    // Verify ws-1 (Bharat Traders) has the active highlight class
    // The active workspace wrapper has bg-blue-50
    const activeWsSection = page.locator(".bg-blue-50").first();
    await expect(activeWsSection).toBeVisible();
    await expect(activeWsSection.locator("text=Bharat Traders")).toBeVisible();

    await expect(page).toHaveScreenshot("sidebar-active-highlight.png");
  });

  // Test 13: Sidebar collapsed workspace — inactive workspaces show ▸ arrow
  test("sidebar-collapsed-workspace", async ({ page, viewport }) => {
    // Sidebar only visible on tablet/desktop
    if ((viewport?.width ?? 1280) < 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);

    // Mock 3 workspaces
    const threeWorkspaces = [
      { id: "ws-1", name: "Bharat Traders", agent_type: "tally", config: {}, created_at: "2025-04-01T00:00:00Z" },
      { id: "ws-2", name: "NUVANTA AI", agent_type: "tally", config: {}, created_at: "2025-04-02T00:00:00Z" },
      { id: "ws-3", name: "Sunrise Corp", agent_type: "tally", config: {}, created_at: "2025-04-03T00:00:00Z" },
    ];

    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(threeWorkspaces) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-1/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(mockConversationsWs1) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-2/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-3/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      } else {
        route.continue();
      }
    });

    // Mock the conversation endpoint for conv-1
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
              { id: "msg-1", role: "user", content: "Hello", data: null, chart: null },
            ],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    // Navigate to conv-1 in ws-1 so ws-1 is active
    await page.goto("/c/conv-1");

    await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });

    // Collapse ws-2 and ws-3 by clicking their headers
    await page.locator("button", { hasText: "NUVANTA AI" }).first().click();
    await page.locator("button", { hasText: "Sunrise Corp" }).first().click();

    // Wait for collapsed state to render
    await page.waitForTimeout(300);

    // Verify collapsed arrows are visible
    await expect(page.locator("text=▸").first()).toBeVisible();

    await expect(page).toHaveScreenshot("sidebar-collapsed-workspace.png");
  });

  // Test 14: Sidebar empty workspace — workspace with 0 conversations shows only "+ New Chat"
  test("sidebar-empty-workspace", async ({ page, viewport }) => {
    // Sidebar only visible on tablet/desktop
    if ((viewport?.width ?? 1280) < 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);

    // One workspace with no conversations
    const emptyWorkspaces = [
      { id: "ws-empty", name: "Empty Company", agent_type: "tally", config: {}, created_at: "2025-04-01T00:00:00Z" },
    ];

    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(emptyWorkspaces) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-empty/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/");

    await page.waitForSelector("text=Empty Company", { timeout: 10000 });

    // Verify the workspace name is visible and "+ New Chat" button is shown
    await expect(page.locator("text=Empty Company").first()).toBeVisible();
    await expect(page.locator("text=+ New Chat").first()).toBeVisible();

    await expect(page).toHaveScreenshot("sidebar-empty-workspace.png");
  });

  // Test 15: Header long names — workspace name truncated with ellipsis
  test("header-long-names", async ({ page }) => {
    await mockLoggedIn(page);

    // Mock a workspace with a very long name
    const longNameWorkspaces = [
      {
        id: "ws-long",
        name: "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED",
        agent_type: "tally",
        config: { tally_host: "localhost", tally_port: 9000 },
        created_at: "2025-04-01T00:00:00Z",
      },
    ];

    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(longNameWorkspaces) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-long/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "conv-long",
              title: "What is the trial balance for April 2025 to March 2026?",
              tag: null,
              created_at: "2025-04-10T10:00:00Z",
              updated_at: "2025-04-10T10:05:00Z",
            },
          ]),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-long/conversations/conv-long", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-long",
            title: "What is the trial balance for April 2025 to March 2026?",
            workspace_id: "ws-long",
            messages: [
              { id: "msg-l1", role: "user", content: "What is the trial balance for April 2025 to March 2026?", data: null, chart: null },
              { id: "msg-l2", role: "assistant", content: "Here is the trial balance.", data: null, chart: null },
            ],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-long");

    // Wait for the workspace name to appear in the header
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });

    // Verify the long workspace name is rendered (may be truncated visually)
    await expect(page.locator('[data-testid="header-workspace-name"]')).toBeVisible();

    await expect(page).toHaveScreenshot("header-long-names.png");
  });

  // Test 16: Header demo badge — orange "Demo" badge when workspace has mock_mode: true
  test("header-demo-badge", async ({ page }) => {
    await mockLoggedIn(page);

    const demoWorkspaces = [
      {
        id: "ws-demo",
        name: "Demo Company",
        agent_type: "tally",
        config: { tally_host: "localhost", tally_port: 9000, mock_mode: true },
        created_at: "2025-04-01T00:00:00Z",
      },
    ];

    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(demoWorkspaces) });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-demo/conversations", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            { id: "conv-demo", title: "Demo Chat", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
          ]),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/workspaces/ws-demo/conversations/conv-demo", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-demo",
            title: "Demo Chat",
            workspace_id: "ws-demo",
            messages: [
              { id: "msg-dm1", role: "user", content: "Hello", data: null, chart: null },
              { id: "msg-dm2", role: "assistant", content: "Welcome to demo mode!", data: null, chart: null },
            ],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-demo");

    // Wait for workspace name to appear in header
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });

    // Verify the orange "Demo" badge is visible
    await expect(page.locator("text=Demo").first()).toBeVisible();

    await expect(page).toHaveScreenshot("header-demo-badge.png");
  });

  // Test 17: Connect company modal — click "+ Connect Company" to show form
  test("connect-company-modal", async ({ page, viewport }) => {
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

    const isMobile = (viewport?.width ?? 1280) < 768;
    if (isMobile) {
      // Open hamburger first to access sidebar
      const hamburger = page.locator('[aria-label="Open sidebar"]');
      await hamburger.waitFor({ timeout: 10000 });
      await hamburger.click();
      await page.locator("text=Bharat Traders").last().waitFor({ state: "visible", timeout: 10000 });
    } else {
      await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });
    }

    // Click "+ Connect Company" button at the bottom of the sidebar
    const connectBtn = page.locator("text=+ Connect Company");
    if (isMobile) {
      await connectBtn.last().click();
    } else {
      await connectBtn.first().click();
    }

    // Wait for modal to appear
    await page.waitForSelector("text=Connect Tally Company", { timeout: 10000 });

    // Verify modal form fields are visible
    await expect(page.locator("text=Company Name")).toBeVisible();
    await expect(page.locator("text=Tally Host")).toBeVisible();
    await expect(page.locator("text=Tally Port")).toBeVisible();

    await expect(page).toHaveScreenshot("connect-company-modal.png");
  });

  // Test 18: Voucher edit form — click "Edit Entry" on draft voucher to show inline edit form
  test("voucher-edit-form", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Re-use the same draft voucher data as test 5 (voucher-review-card)
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

    await page.route("**/api/health", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-2");

    // Wait for the voucher card to appear
    await page.waitForSelector('[data-testid="voucher-review-entry-1"]', { timeout: 10000 });

    // Click "Edit Entry" to open the inline edit form
    await page.locator("button", { hasText: "Edit Entry" }).click();

    // Wait for edit form inputs to appear
    await page.waitForSelector('input[aria-label="Vendor"]', { timeout: 5000 });

    // Verify edit form fields are visible
    await expect(page.locator('input[aria-label="Vendor"]')).toBeVisible();
    await expect(page.locator('input[aria-label="Date"]')).toBeVisible();
    await expect(page.locator('input[aria-label="Amount"]')).toBeVisible();
    await expect(page.locator('select[aria-label="Expense Ledger"]')).toBeVisible();
    await expect(page.locator('select[aria-label="Payment Ledger"]')).toBeVisible();
    await expect(page.locator("button", { hasText: "Confirm & Write to Tally" })).toBeVisible();

    await expect(page).toHaveScreenshot("voucher-edit-form.png");
  });
});
