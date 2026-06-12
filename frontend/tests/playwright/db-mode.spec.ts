import { test, expect } from "@playwright/test";

// Shared mock data
const mockUser = { id: "user-1", email: "test@example.com", name: "Test User" };
const mockToken = "fake-access-token-for-testing";

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

    // VISUAL CHECKLIST:
    // - Email and password input fields centered on the page
    // - "Sign in" submit button is blue (primary color)
    // - "Register" link visible below the form
    // - Page title "TallyPrime AI" visible at top
    // - NO sidebar visible (unauthenticated state)
    // - Form card has proper padding and centering (no overflow)
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

    // VISUAL CHECKLIST:
    // - Email and password input fields visible and centered
    // - Password strength indicator bar visible below password field (triggered by "TestPass123!")
    // - "Create account" submit button visible
    // - "TallyPrime AI" heading visible
    // - NO sidebar visible (unauthenticated state)
    // - Confirm password field visible below the main password field
    await expect(page).toHaveScreenshot("register-page.png");
  });

  // Test 3: Sidebar with workspace list renders for logged-in user
  test("sidebar-with-workspaces", async ({ page, viewport }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    // Mock health endpoint to avoid errors
    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    // Mock the specific conversation endpoint so /c/conv-1 loads correctly
    await page.route("**/api/workspaces/ws-1/conversations/conv-1", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-1",
            title: "Trial Balance April",
            workspace_id: "ws-1",
            messages: [],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    // Navigate to /c/conv-1 so there is clear workspace + conversation context
    // This ensures both the active workspace (bg-blue-50) and active conversation
    // (bg-blue-100) highlights are visible in the sidebar.
    await page.goto("/c/conv-1");

    // On mobile (width < 768), sidebar is hidden behind hamburger drawer
    const isMobile = (viewport?.width ?? 1280) < 768;
    if (isMobile) {
      // Open the sidebar drawer first — on mobile the sidebar is hidden md:flex
      const hamburger = page.locator('[aria-label="Open sidebar"]');
      await hamburger.waitFor({ timeout: 10000 });
      await hamburger.click();
      // Wait for drawer sidebar content — use .last() because the desktop sidebar
      // is also in the DOM (hidden) and Playwright picks the first (hidden) element
      await page.locator("text=Bharat Traders Private Limited (Bharat Traders)").last().waitFor({ state: "visible", timeout: 10000 });
      await expect(page.locator("text=Bharat Traders Private Limited (Bharat Traders)").last()).toBeVisible();
      await expect(page.locator("text=NUVANTA AI").last()).toBeVisible();
      // Verify active conversation highlight is visible in the drawer sidebar
      await expect(page.locator("text=Trial Balance April").last()).toBeVisible();
    } else {
      // Desktop/tablet: sidebar is always visible
      await page.waitForSelector("text=Bharat Traders Private Limited (Bharat Traders)", { timeout: 10000 });
      await expect(page.locator("text=Bharat Traders Private Limited (Bharat Traders)").first()).toBeVisible();
      await expect(page.locator("text=NUVANTA AI").first()).toBeVisible();
      // Verify active conversation is visible and highlighted
      await expect(page.locator("text=Trial Balance April").first()).toBeVisible();
    }

    // Verify "+ New Chat" button is visible in at least one workspace
    if (isMobile) {
      await expect(page.locator("text=+ New Chat").last()).toBeVisible();
    } else {
      await expect(page.locator("text=+ New Chat").first()).toBeVisible();
    }

    // Content assertions before screenshot (catch functional bugs independently of pixel diff)
    // Use .last() to handle mobile where two <aside> elements may be in DOM simultaneously
    // (hidden desktop sidebar + visible drawer sidebar — drawer renders second)
    await expect(
      page.locator("aside").getByText("Bharat Traders Private Limited (Bharat Traders)").last(),
    ).toBeVisible();
    await expect(page.locator("aside").getByText("NUVANTA AI").last()).toBeVisible();

    // VISUAL CHECKLIST:
    // - Sidebar shows "Bharat Traders Private Limited (Bharat Traders)" as the ws-1 workspace header
    //   fully visible, wrapping to 2-3 lines (no truncation/ellipsis); "NUVANTA AI" unchanged (no tally_company)
    // - Collapse chevron still visible at the right edge of each workspace header
    // - Conversations listed under each workspace (e.g., "Trial Balance April", "Expense Entry" under Bharat Traders; "P&L Summary" under NUVANTA AI)
    // - "+ New Chat" buttons visible for each workspace
    // - "+ Connect Company" button visible at the bottom of the sidebar
    // - "Bharat Traders Private Limited (Bharat Traders)" section has bg-blue-50 background (active workspace)
    // - "Trial Balance April" has bg-blue-100 background (active conversation)
    // - On mobile: drawer overlay slides in from left, main content partially visible behind it
    // - On mobile: backdrop dimming effect visible behind the drawer
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
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
    await page.route("**/api/health**", (route) =>
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

    // Verify conversation title in header
    await expect(page.locator('[data-testid="header-chat-title"]')).toHaveText("Trial Balance April");

    // Verify Live badge (workspace config has no mock_mode)
    await expect(page.locator('[data-testid="header-workspace-badge"]')).toContainText("Live");

    // Verify TallyPrime AI brand: visible in header on desktop/tablet, hidden on mobile (moved to drawer)
    const isMobile = (viewport?.width ?? 1280) < 768;
    if (isMobile) {
      await expect(page.locator("header").getByText("TallyPrime AI")).not.toBeVisible();
    } else {
      await expect(page.locator("header").getByText("TallyPrime AI")).toBeVisible();
    }

    // On desktop/tablet: also verify sidebar shows "Trial Balance April"
    if (!isMobile) {
      await expect(page.locator("text=Trial Balance April").first()).toBeVisible();
    }

    // VISUAL CHECKLIST:
    // - Desktop/tablet header: "TallyPrime AI | Trial Balance April" (brand + pipe + conversation title)
    // - Mobile header: NO "TallyPrime AI" brand (hidden md:block); shows chat title full-width instead
    // - Header subtitle (second line): "Bharat Traders ● Live" — subtitle is under the chat title, NOT under "TallyPrime AI"
    // - "Live" badge is green (not orange/demo)
    // - Sidebar (desktop/tablet): "Bharat Traders" section has bg-blue-50 background
    // - Sidebar (desktop/tablet): "Trial Balance April" item has bg-blue-100 background (active)
    // - Data table visible in chat area with 3 rows: Sales Account, Purchase Account, Cash
    // - Table headers: "Ledger", "Debit", "Credit"
    // - User message bubble above the assistant response
    // - NOT visible: no orange "Demo" badge
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
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
    await page.route("**/api/health**", (route) =>
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

    // VISUAL CHECKLIST:
    // - Voucher card has blue border (draft status styling)
    // - Vendor field shows "Staples India"
    // - Date field shows "10-Apr-2025" (formatted from 20250410)
    // - Amount field shows ₹5,000
    // - GST entries listed: "Input CGST 9%" ₹450 and "Input SGST 9%" ₹450
    // - Three action buttons visible: "Write to Tally" (green), "Edit Entry" (white/outlined), "Discard" (red border)
    // - "Expense Entry — Draft" status label visible in card header
    // - NOT visible: no disabled/grayed buttons (draft state has all buttons enabled)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // Brand "TallyPrime AI" should NOT be visible in the mobile header (moved to drawer)
    await expect(page.locator("header").getByText("TallyPrime AI")).not.toBeVisible();

    // Drawer brand block should not be present (drawer is closed)
    await expect(page.getByTestId("drawer-brand")).not.toBeAttached();

    // Sidebar content (workspace names) should NOT be visible — hidden behind drawer.
    // Scope to the sidebar <aside>: the header now shows the active workspace name on the
    // landing page (header-workspace-name), so the bare text locator would also match the
    // header. We only assert the SIDEBAR copy is hidden on mobile.
    await expect(page.locator("aside").getByText("Bharat Traders Private Limited (Bharat Traders)")).not.toBeVisible();

    // VISUAL CHECKLIST:
    // - Hamburger ☰ icon visible in the top-left corner of the header
    // - Header has NO "TallyPrime AI" brand text (brand hidden on mobile, md:block)
    // - Header shows: hamburger + chat title block + user avatar only
    // - Avatar/user icon visible in the top-right corner
    // - Quick action buttons visible in the main content area
    // - Chat input box visible at the bottom
    // - NOT visible: "TallyPrime AI" brand in the header
    // - NOT visible: sidebar workspace header "Bharat Traders Private Limited (Bharat Traders)" (hidden behind drawer)
    // - NOT visible: "NUVANTA AI" sidebar label (hidden behind drawer)
    // - NOT visible: no drawer overlay
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("mobile-hamburger-closed.png");
  });

  // Test 7: Mobile — click hamburger opens sidebar drawer with highlights
  test("mobile-hamburger-open", async ({ page, viewport }) => {
    // Skip on non-mobile viewports
    if ((viewport?.width ?? 1280) >= 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    // Mock the conversation endpoint so /c/conv-1 loads correctly
    await page.route("**/api/workspaces/ws-1/conversations/conv-1", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "conv-1",
            title: "Trial Balance April",
            workspace_id: "ws-1",
            messages: [],
            created_at: "2025-04-10T10:00:00Z",
            updated_at: "2025-04-10T10:05:00Z",
          }),
        });
      } else {
        route.continue();
      }
    });

    // Navigate to /c/conv-1 so there is clear workspace + conversation context.
    // On /, activeWorkspaceId starts null — navigating to a conversation URL ensures
    // the sidebar resolves the active workspace and conversation before the drawer opens.
    await page.goto("/c/conv-1");

    // Click hamburger to open sidebar drawer
    const hamburger = page.locator('[aria-label="Open sidebar"]');
    await hamburger.waitFor({ timeout: 10000 });
    await hamburger.click();

    // Sidebar drawer with workspace names should now be visible.
    // Use .last() because the desktop sidebar is also in the DOM (inside hidden md:flex)
    // and Playwright picks the first (hidden) element. The drawer renders second.
    await page.locator("text=Bharat Traders Private Limited (Bharat Traders)").last().waitFor({ state: "visible", timeout: 10000 });
    await expect(page.locator("text=NUVANTA AI").last()).toBeVisible();

    // Drawer brand block must be visible once drawer opens
    await expect(page.getByTestId("drawer-brand")).toBeVisible();

    // Brand still hidden in header (even when drawer is open)
    await expect(page.locator("header").getByText("TallyPrime AI")).not.toBeVisible();

    // Verify the active conversation is shown and highlighted (bg-blue-100) in the drawer
    await expect(page.locator("text=Trial Balance April").last()).toBeVisible();

    // VISUAL CHECKLIST:
    // - Sidebar drawer slides in from the left and is fully visible
    // - Drawer TOP shows "TallyPrime AI" brand block with bottom border (data-testid="drawer-brand")
    // - Header does NOT show "TallyPrime AI" brand (hidden md:block — hidden on mobile)
    // - Workspace list visible below the brand block: "Bharat Traders Private Limited (Bharat Traders)" and "NUVANTA AI"
    // - "Bharat Traders Private Limited (Bharat Traders)" wraps to multiple lines (fully visible, no ellipsis)
    // - "NUVANTA AI" unchanged (no tally_company)
    // - Collapse chevron still visible at the right edge of each workspace header
    // - "Bharat Traders Private Limited (Bharat Traders)" section has bg-blue-50 background (active workspace)
    // - "Trial Balance April" conversation item has bg-blue-100 background (active)
    // - Backdrop behind the drawer dims the main content
    // - Main content partially visible behind the semi-transparent backdrop
    // - "+ New Chat" and "+ Connect Company" visible in the drawer
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/w/ws-1");

    // Wait for app to fully load (hint text is always in DOM regardless of brand visibility)
    await page.waitForSelector("text=Type or upload to start a conversation", { timeout: 10000 });

    // Hamburger should be visible on mobile
    await expect(page.locator('[aria-label="Open sidebar"]')).toBeVisible();

    // Header does NOT show "TallyPrime AI" brand on mobile (hidden md:block)
    await expect(page.locator("header").getByText("TallyPrime AI")).not.toBeVisible();

    // chat title element is visible in the header
    await expect(page.locator('[data-testid="header-chat-title"]')).toBeVisible();

    // The chat window hint text should be visible (always visible regardless of sidebar)
    await expect(page.locator("text=Type or upload to start a conversation")).toBeVisible();

    // VISUAL CHECKLIST:
    // - Hamburger ☰ icon visible in the top-left of the header
    // - Header does NOT show "TallyPrime AI" brand (hidden on mobile — brand is in the drawer)
    // - Header shows: hamburger + chat title (full width) + user avatar
    // - [data-testid="header-chat-title"] visible in the header (shows "New Chat" in blue)
    // - "TallyPrime AI Assistant" heading centered in the main content area
    // - Hint text "Type or upload to start a conversation" visible below the heading
    // - Quick action buttons visible in the center
    // - Chat input box visible at the bottom
    // - NOT visible: "TallyPrime AI" brand text in the header
    // - NOT visible: no sidebar content (mobile drawer is closed)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // Verify "Pending" status word is shown in the voucher card (scoped to the
    // card so it doesn't match the sidebar "Pending Voucher" button)
    const pendingCard = page.locator('[data-testid="voucher-review-entry-pending"]');
    await expect(pendingCard.getByText("Pending", { exact: true })).toBeVisible();

    // VISUAL CHECKLIST:
    // - Voucher card has yellow/amber border (pending status styling)
    // - "Journal" type badge + "Pending" status word visible in the card header
    // - Action buttons visible but DISABLED (opacity-50 / grayed appearance)
    // - Spinner or loading indicator on the "Write to Tally" button area
    // - Buttons should not look clickable (disabled cursor style)
    // - Vendor "Staples India", amount ₹5,000 still readable in the card
    // - NOT visible: no green border (not written), no gray (not discarded)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-11");

    await page.waitForSelector('[data-testid="voucher-review-entry-written"]', { timeout: 10000 });

    // Verify "Written" status word in the voucher card (scoped to the card so it
    // doesn't match the sidebar "Written Voucher" button)
    const writtenCard = page.locator('[data-testid="voucher-review-entry-written"]');
    await expect(writtenCard.getByText("Written", { exact: true })).toBeVisible();

    // No action buttons should be present inside the voucher card
    await expect(writtenCard.locator("button", { hasText: "Write to Tally" })).not.toBeVisible();
    await expect(writtenCard.locator("button", { hasText: "Discard" })).not.toBeVisible();

    // VISUAL CHECKLIST:
    // - Voucher card has green border and/or green background tint (written status styling)
    // - "Journal" type badge + "Written" status word visible in the card header
    // - Entry fields still readable: "Amazon India", ₹12,000, date 11-Apr-2025
    // - NOT visible: no "Write to Tally" action button
    // - NOT visible: no "Edit Entry" action button
    // - NOT visible: no "Discard" action button
    // - Card appears settled/final (no interactive elements)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-12");

    await page.waitForSelector('[data-testid="voucher-review-entry-deleted"]', { timeout: 10000 });

    // Verify "Discarded" status word in the voucher card (scoped to the card so it
    // doesn't match the sidebar "Discarded Voucher" button)
    const discardedCard = page.locator('[data-testid="voucher-review-entry-deleted"]');
    await expect(discardedCard.getByText("Discarded", { exact: true })).toBeVisible();

    // No action buttons inside the voucher card
    await expect(discardedCard.locator("button", { hasText: "Write to Tally" })).not.toBeVisible();
    await expect(discardedCard.locator("button", { hasText: "Edit Entry" })).not.toBeVisible();

    // VISUAL CHECKLIST:
    // - Voucher card has gray border and/or reduced opacity (discarded/deleted status styling)
    // - "Journal" type badge + "Discarded" status word visible in the card header
    // - Entry fields dimmed/muted: "Flipkart India", ₹8,500, date 12-Apr-2025
    // - NOT visible: no "Write to Tally" action button
    // - NOT visible: no "Edit Entry" action button
    // - NOT visible: no "Discard" action button
    // - Card appears finalized with no interactive controls
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // VISUAL CHECKLIST:
    // - "Bharat Traders Private Limited (Bharat Traders)" workspace section has bg-blue-50 light blue background
    //   fully visible, wrapping to 2-3 lines (chevron aligned to the top-right of the first line)
    // - Collapse chevron still visible at the right edge of the workspace header
    // - "Trial Balance April" conversation item has bg-blue-100 slightly darker blue background
    // - "NUVANTA AI" workspace section has NO blue highlight (plain/white background)
    // - Conversations under Bharat Traders visible: Trial Balance April, Expense Entry, etc.
    // - Conversations under NUVANTA AI visible: P&L Summary
    // - Both workspace sections expanded with their conversation lists
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // VISUAL CHECKLIST:
    // - Three workspaces visible: Bharat Traders (expanded/active), NUVANTA AI (collapsed), Sunrise Corp (collapsed)
    // - Bharat Traders: expanded with conversation list visible, bg-blue-50 background
    // - NUVANTA AI: collapsed, shows only workspace name + ▸ right-pointing arrow
    // - Sunrise Corp: collapsed, shows only workspace name + ▸ right-pointing arrow
    // - "Trial Balance April" has bg-blue-100 highlight (active conversation under Bharat Traders)
    // - Collapsed workspace rows show NO conversation items listed below them
    // - ▸ arrow aligns to the right of the workspace name button
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // VISUAL CHECKLIST:
    // - "Empty Company" workspace name visible in the sidebar
    // - "+ New Chat" button visible directly below the workspace name
    // - NO conversation items listed under the workspace (empty list)
    // - Workspace section is expanded (no collapse arrow, or expanded state)
    // - Proper spacing between workspace header and "+ New Chat" button
    // - "+ Connect Company" button visible at the bottom of the sidebar
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // VISUAL CHECKLIST:
    // - Header subtitle line: "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED" truncated with "..." (ellipsis)
    // - Header title line: "What is the trial balance for April 2025 to March 2026?" truncated with "..."
    // - Both lines truncated independently — no text overflow beyond the header width
    // - Truncation does not cause text to overlap the avatar or other header elements
    // - The "..." appears at the end of the truncated text (not mid-word if possible)
    // - "Live" badge visible in the subtitle without being pushed off screen
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/c/conv-demo");

    // Wait for workspace name to appear in header
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });

    // Verify the orange "Demo" badge is visible via data-testid
    await expect(page.locator('[data-testid="header-workspace-badge"]')).toContainText("Demo");

    // VISUAL CHECKLIST:
    // - Header subtitle shows "Demo Company" as the workspace name
    // - Orange "● Demo" badge visible next to the workspace name in the subtitle
    // - Badge text reads "Demo" (not "Live")
    // - Orange color clearly distinguishable from the green "Live" badge color
    // - NOT visible: no green "Live" badge
    // - Header title: "Demo Chat" (the conversation title)
    await expect(page).toHaveScreenshot("header-demo-badge.png");
  });

  // Test 17: Connect company modal — click "+ Connect Company" to show form
  test("connect-company-modal", async ({ page, viewport }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health**", (route) =>
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
    await expect(page.locator("text=Friendly Name")).toBeVisible();
    await expect(page.locator("text=Tally Host")).toBeVisible();
    await expect(page.locator("text=Tally Port")).toBeVisible();

    // VISUAL CHECKLIST:
    // - Modal overlay visible with semi-transparent backdrop behind it
    // - Modal title "Connect Tally Company" visible at the top
    // - Form fields visible: "Friendly Name" input, "Tally Host" (pre-filled "localhost"), "Tally Port" (pre-filled "9000")
    // - "Demo Mode" toggle switch visible in the form
    // - "Cancel" and "Connect" buttons visible at the bottom of the modal
    // - Modal is centered on the screen with appropriate width (not full screen)
    // - Backdrop dims the sidebar and main content behind the modal
    // - Proper vertical spacing between form fields (no cramping)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
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

    await page.route("**/api/health**", (route) =>
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

    // Wait for the edit form to appear (data-testid on the form root)
    await page.waitForSelector('[data-testid="voucher-edit-form"]', { timeout: 5000 });

    // Verify edit form fields are visible. For a "Journal" voucher the form
    // renders: Voucher Type, Date, Supplier Invoice No., and the primary money
    // line (Narration / Amount / Ledger). The non-party-ledger label defaults to
    // "Ledger" for Journal (see primaryLedgerLabel in VoucherEditForm.tsx).
    await expect(page.locator('select[aria-label="Voucher Type"]')).toBeVisible();
    await expect(page.locator('input[aria-label="Date"]')).toBeVisible();
    await expect(page.locator('input[aria-label="Supplier Invoice No."]')).toBeVisible();
    await expect(page.locator('input[aria-label="Amount"]')).toBeVisible();
    await expect(page.locator('select[aria-label="Ledger"]')).toBeVisible();
    await expect(page.locator('input[aria-label="Narration"]')).toBeVisible();
    await expect(page.locator("button", { hasText: "Save" })).toBeVisible();

    // VISUAL CHECKLIST:
    // - Inline edit form visible within the voucher card (replaces the review display)
    // - "Voucher Type" select visible (pre-selected "Journal")
    // - "Date" input field visible (pre-filled "2025-04-10" or formatted equivalent)
    // - "Supplier Invoice No." input field visible
    // - "Amount" input field visible (pre-filled "5000")
    // - "Ledger" dropdown/select visible (pre-selected "Office Supplies")
    // - "Narration" / Description text input visible
    // - "Save" button visible (green)
    // - "Cancel" button visible (secondary styling)
    // - NOT visible: "Write to Tally" standalone button (replaced by inline form)
    // - NOT visible: "Discard" button
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("voucher-edit-form.png");
  });

  // Test 19: Desktop landing page — "New Chat" in header, Live badge, sidebar highlight
  test("desktop-landing-page", async ({ page, viewport }) => {
    // Skip on mobile (sidebar not visible)
    if ((viewport?.width ?? 1280) < 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/w/ws-1");

    // Wait for workspace to resolve
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });

    // Verify "New Chat" shown in header chat title (blue)
    await expect(page.locator('[data-testid="header-chat-title"]')).toHaveText("New Chat");

    // Verify workspace name + Live badge in subtitle
    await expect(page.locator('[data-testid="header-workspace-name"]')).toHaveText("Bharat Traders");
    await expect(page.locator('[data-testid="header-workspace-badge"]')).toContainText("Live");

    // Verify "+ New Chat" highlighted in sidebar for active workspace
    await expect(page.locator('[data-testid="sidebar-new-chat-active"]').first()).toBeVisible();

    // Verify hint text in chat area
    await expect(page.locator("text=Type or upload to start a conversation")).toBeVisible();

    // VISUAL CHECKLIST:
    // - Header first line: "TallyPrime AI | New Chat" — "New Chat" rendered in blue text
    // - Header subtitle: "Bharat Traders ● Live" — workspace name + green Live badge
    // - Sidebar: "Bharat Traders" section expanded, "+ New Chat" button highlighted bg-blue-100
    // - Sidebar: NUVANTA AI section visible but NOT highlighted
    // - Main content: "TallyPrime AI Assistant" heading centered
    // - Main content: "Connected to Bharat Traders" subtitle text visible
    // - Hint text "Type or upload to start a conversation" visible below heading
    // - Quick action buttons visible
    // - Chat input box visible at the bottom
    // - NOT visible: no message bubbles (fresh new chat)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("desktop-landing-page.png");
  });

  // Test 20: Sidebar new chat highlighted — on landing page, active workspace's "+ New Chat" is highlighted
  test("sidebar-new-chat-highlighted", async ({ page, viewport }) => {
    // Sidebar only visible on tablet/desktop
    if ((viewport?.width ?? 1280) < 768) {
      test.skip();
      return;
    }

    await mockLoggedIn(page);
    await mockWorkspaceData(page);

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true }),
      }),
    );

    await page.goto("/w/ws-1");

    // Wait for sidebar to load
    await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });

    // The active workspace's "+ New Chat" should have highlighted styling
    const highlightedBtn = page.locator('[data-testid="sidebar-new-chat-active"]').first();
    await expect(highlightedBtn).toBeVisible();
    await expect(highlightedBtn).toHaveText("+ New Chat");

    // The inactive workspace's "+ New Chat" should NOT be highlighted
    const normalBtn = page.locator('[data-testid="sidebar-new-chat"]').first();
    await expect(normalBtn).toBeVisible();

    // VISUAL CHECKLIST:
    // - "Bharat Traders" workspace section: "+ New Chat" button has bg-blue-100 blue background (active/highlighted)
    // - "NUVANTA AI" workspace section: "+ New Chat" button has normal gray/white background (inactive)
    // - The highlighted "+ New Chat" button is clearly visually distinct from the plain one
    // - Both workspaces are expanded showing their "+ New Chat" buttons
    // - Conversations listed under each workspace (Trial Balance April, Expense Entry, etc. under Bharat Traders)
    // - No conversation item is highlighted with bg-blue-100 (landing page, no active conversation)
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("sidebar-new-chat-highlighted.png");
  });

  // Test 21: No-workspaces landing — shows welcome prompt + Connect Company button instead of chat UI
  test("no-workspaces-landing", async ({ page }) => {
    await mockLoggedIn(page);

    // Mock getWorkspaces to return empty array
    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      } else {
        route.continue();
      }
    });

    await page.route("**/api/health**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: false }),
      }),
    );

    await page.goto("/");

    // Wait for the no-workspaces prompt to appear
    await page.waitForSelector('[data-testid="no-workspaces-prompt"]', { timeout: 10000 });

    // Verify welcome message
    await expect(page.locator("text=Welcome to TallyPrime AI")).toBeVisible();
    await expect(page.locator("text=Connect your first Tally company to get started")).toBeVisible();

    // Verify the Connect Company button in the main area
    await expect(page.locator('[data-testid="connect-company-button"]')).toBeVisible();

    // Verify chat input is NOT visible (no workspace to chat with)
    await expect(page.locator('textarea[placeholder="Ask about your Tally data..."]')).not.toBeVisible();

    // VISUAL CHECKLIST:
    // - Header shows "TallyPrime AI" only — NO workspace name subtitle, NO Live/Demo badge
    // - Main content: "Welcome to TallyPrime AI" heading centered on page
    // - Main content: "Connect your first Tally company to get started" subtitle text visible
    // - Blue "+ Connect Company" button centered below the subtitle text
    // - NO sidebar content visible (no workspace list, no conversations)
    // - NOT visible: chat input box (no workspace to chat with)
    // - NOT visible: quick action buttons
    // - NOT visible: any conversation messages
    await expect(page).toHaveScreenshot("no-workspaces-landing.png");
  });

  // Test 22: Connect company confirmation — two-step modal lands on confirmation screen
  test("connect-company-confirmation", async ({ page, viewport }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);
    await page.route("**/api/health**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "healthy", tally_connected: true, tally_url: "http://localhost:9000", mode: "live" }) }));
    await page.route("**/api/companies**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ companies: [{ name: "Bharat Traders Private Limited" }] }) }));
    await page.route("**/api/workspaces", (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "ws-new", name: "My Books", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }) });
      } else {
        // Fall through to the GET handler registered by mockWorkspaceData (route.continue
        // would hit the network and bypass the mock; fallback re-enters the route chain).
        route.fallback();
      }
    });
    await page.goto("/");
    const isMobile = (viewport?.width ?? 1280) < 768;
    // open the connect modal (mirror the connect-company-modal test's mobile/desktop handling)
    if (isMobile) {
      const hamburger = page.locator('[aria-label="Open sidebar"]');
      await hamburger.waitFor({ timeout: 10000 });
      await hamburger.click();
      await page.locator("text=Bharat Traders").last().waitFor({ state: "visible", timeout: 10000 });
    } else {
      await page.waitForSelector("text=Bharat Traders", { timeout: 10000 });
    }
    const connectBtn = page.locator("text=+ Connect Company");
    await (isMobile ? connectBtn.last() : connectBtn.first()).click();
    await page.waitForSelector("text=Connect Tally Company", { timeout: 10000 });
    // fill friendly name and submit
    await page.locator("#connect-name").fill("My Books");
    // exact:true to avoid matching the sidebar "+ Connect Company" button
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    // confirmation screen
    await expect(page.getByTestId("connect-confirm-company")).toHaveText("Bharat Traders Private Limited");
    await expect(page.getByTestId("connect-confirm-name")).toHaveText("My Books");
    await expect(page.getByTestId("connect-start-chat")).toBeVisible();
    // VISUAL CHECKLIST:
    // - Modal centered with backdrop; green check + "Company Connected" title
    // - "TALLY COMPANY" label with value "Bharat Traders Private Limited"
    // - "FRIENDLY NAME" label with value "My Books"
    // - "Close" (secondary) and blue "Start chat" buttons, right-aligned
    // - NOT visible: the form fields (Friendly Name input, Tally Host/Port, Demo toggle), no error banner
    await expect(page).toHaveScreenshot("connect-company-confirmation.png");
  });

  // Test 23: Header Tally live — health reports connected → green "Live" badge
  test("header-tally-live", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);
    await page.route("**/api/health**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "healthy", tally_connected: true, tally_url: "http://localhost:9000", mode: "live" }) }));

    await page.goto("/w/ws-1");

    // Wait for workspace to resolve in header
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });
    await expect(page.locator('[data-testid="header-workspace-name"]')).toHaveText("Bharat Traders");

    // Badge resolves to connected/Live
    await expect(page.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "connected", { timeout: 10000 });
    await expect(page.getByTestId("header-workspace-badge")).toContainText("Live");

    // VISUAL CHECKLIST:
    // - Green pill badge with green dot + "Live" to the right of the workspace name
    // - Header title line ("TallyPrime AI | New Chat") and workspace name "Bharat Traders" visible
    // - NOT visible: red/Offline badge, gray/Checking badge, orange/Demo badge
    await expect(page).toHaveScreenshot("header-tally-live.png");
  });

  // Test 24: Header Tally offline — health reports disconnected → red "Offline" badge
  test("header-tally-offline", async ({ page }) => {
    await mockLoggedIn(page);
    await mockWorkspaceData(page);
    await page.route("**/api/health**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "degraded", tally_connected: false, tally_url: "http://localhost:9000", mode: "live" }) }));

    await page.goto("/w/ws-1");

    // Wait for workspace to resolve in header
    await page.waitForSelector('[data-testid="header-workspace-name"]', { timeout: 10000 });
    await expect(page.locator('[data-testid="header-workspace-name"]')).toHaveText("Bharat Traders");

    // Badge resolves to disconnected/Offline
    await expect(page.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "disconnected", { timeout: 10000 });
    await expect(page.getByTestId("header-workspace-badge")).toContainText("Offline");

    // VISUAL CHECKLIST:
    // - Red pill badge with red dot + "Offline" to the right of the workspace name
    // - Header title line and workspace name "Bharat Traders" otherwise normal
    // - NOT visible: green/Live badge, gray/Checking badge, orange/Demo badge
    await expect(page).toHaveScreenshot("header-tally-offline.png");
  });
});
