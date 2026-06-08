import { test, expect } from "@playwright/test";

// FX → INR conversion visual tests for VoucherReviewCard (task T11).
// The VoucherReviewCard now renders an FX line for foreign-currency entries:
//   `<CUR> <orig> @ ₹<rate> = ₹<inr>` followed by a "Wrong rate?" hint.
// State matrix (VoucherReviewCard × state × 3 viewports mobile/tablet/desktop):
//   1. inr                 — INR entry: NO FX line.
//   2. foreign_doc_rate    — USD, rate from doc, no warning: FX line + hint.
//   3. foreign_default_rate— USD, rate from default, "Used default ... rate" warning.
//   4. foreign_no_rate     — USD, no rate (amount 0), "No conversion rate ..." warning.
//
// Pattern mirrors db-mode.spec.ts: mock auth + workspace + conversation endpoints,
// navigate to /c/<conv-id>, then assert content BEFORE every screenshot.

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

/** Helper: mock workspace list + health + the per-conversation list endpoint */
async function mockShell(
  page: import("@playwright/test").Page,
  conversations: Array<Record<string, unknown>>,
) {
  await page.route("**/api/workspaces", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(mockWorkspaces) });
    } else {
      route.continue();
    }
  });
  await page.route("**/api/workspaces/ws-1/conversations", (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(conversations) });
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
}

/** Build a conversation payload that renders a single voucher_review entry. */
function conversationWith(entry: Record<string, unknown>, convId: string, title: string) {
  return {
    id: convId,
    title,
    workspace_id: "ws-1",
    messages: [
      { id: "msg-u", role: "user", content: "Here is a receipt", data: null, chart: null },
      {
        id: "msg-a",
        role: "assistant",
        content: "I've extracted the expense entry. Please review:",
        data: {
          type: "voucher_review",
          entries: [entry],
          available_ledgers: ["Office Supplies", "Travel", "Utilities"],
          available_payment_ledgers: ["ICICI Bank", "Cash", "Petty Cash"],
        },
        chart: null,
      },
    ],
    created_at: "2025-04-10T10:00:00Z",
    updated_at: "2025-04-10T10:05:00Z",
  };
}

test.describe("FX → INR VoucherReviewCard visual tests", () => {
  // -----------------------------------------------------------------------
  // State 1: INR entry — NO FX line.
  // -----------------------------------------------------------------------
  test("fx-inr", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-inr", title: "INR Entry", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "entry-inr",
      voucher_type: "Journal",
      date: "20250410",
      vendor_name: "Staples India",
      amount: 5900,
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
      original_currency: "INR",
      original_amount: 5900,
      fx_rate: 1,
      original_gst_entries: [],
    };

    await page.route("**/api/workspaces/ws-1/conversations/conv-inr", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(conversationWith(entry, "conv-inr", "INR Entry")),
        });
      } else {
        route.continue();
      }
    });

    await page.goto("/c/conv-inr");
    await page.waitForSelector('[data-testid="voucher-review-entry-inr"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-entry-inr"]');
    await expect(card).toBeVisible();
    // Core fields render
    await expect(card).toContainText("Staples India");
    await expect(card).toContainText("₹5,900.00");
    await expect(card).toContainText("Expense Entry — Draft");
    // No FX line: the "@ ₹" rate syntax and the "Wrong rate?" hint must be ABSENT.
    await expect(card).not.toContainText("@ ₹");
    await expect(card).not.toContainText("Wrong rate?");

    // VISUAL CHECKLIST:
    // Layout: single voucher card, blue border (draft); field grid (Vendor/Date/Amount/Expense Ledger/Paid via/Narration);
    //         GST line below the grid; three action buttons (Write to Tally / Edit Entry / Discard).
    // Text:   "Expense Entry — Draft" header; "Staples India"; "₹5,900.00"; GST "Input CGST 9%: ₹450.00, Input SGST 9%: ₹450.00".
    // Colors: blue draft border (border-blue-200 bg-blue-50); green "Write to Tally"; red-outlined "Discard".
    // Spacing: field grid 2-col on tablet/desktop, 1-col on mobile; consistent row gaps.
    // NOT visible: NO FX line (no "USD ... @ ₹ ... = ₹"), NO "Wrong rate?" hint, NO amber warning block.
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("fx-inr.png");
  });

  // -----------------------------------------------------------------------
  // State 2: USD entry, rate from doc, no warning — FX line + hint, NO warning.
  // -----------------------------------------------------------------------
  test("fx-foreign-doc-rate", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-doc", title: "USD Doc Rate", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "entry-doc",
      voucher_type: "Journal",
      date: "20250410",
      vendor_name: "AWS Inc",
      amount: 8350, // 100 USD @ 83.50
      debit_ledger: "Cloud Hosting",
      credit_ledger: "ICICI Bank",
      narration: "AWS hosting invoice",
      gst_entries: [],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
      original_currency: "USD",
      original_amount: 100,
      fx_rate: 83.5,
      original_gst_entries: [],
    };

    await page.route("**/api/workspaces/ws-1/conversations/conv-doc", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(conversationWith(entry, "conv-doc", "USD Doc Rate")),
        });
      } else {
        route.continue();
      }
    });

    await page.goto("/c/conv-doc");
    await page.waitForSelector('[data-testid="voucher-review-entry-doc"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-entry-doc"]');
    await expect(card).toBeVisible();
    await expect(card).toContainText("AWS Inc");
    // FX line: "USD 100.00 @ ₹83.50 = ₹8,350.00"
    await expect(card).toContainText("USD 100.00 @ ₹83.50 = ₹8,350.00");
    // Hint (renders &lt;n&gt; as <n>)
    await expect(card).toContainText('Wrong rate? Reply "use rate <n>" in chat.');
    // INR amount in the Amount field
    await expect(card).toContainText("₹8,350.00");
    // No warning block (rate came from the doc)
    await expect(card).not.toContainText("Used default");
    await expect(card).not.toContainText("No conversion rate");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; field grid; FX block (2 lines) directly under the grid, above the action buttons;
    //         three action buttons (Write to Tally / Edit Entry / Discard).
    // Text:   FX line "USD 100.00 @ ₹83.50 = ₹8,350.00" (gray text-xs); hint line
    //         'Wrong rate? Reply "use rate <n>" in chat.' (lighter gray text-gray-400);
    //         Amount field "₹8,350.00"; vendor "AWS Inc".
    // Colors: blue draft border; FX line gray-600; hint gray-400; green Write button.
    // Spacing: FX block has mb-2; hint sits on its own line directly under the FX amount line.
    // NOT visible: NO amber warning block, NO "Used default" text, NO "No conversion rate" text, NO GST line.
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("fx-foreign-doc-rate.png");
  });

  // -----------------------------------------------------------------------
  // State 3: USD entry, rate from default — FX line + hint + "Used default" warning.
  // -----------------------------------------------------------------------
  test("fx-foreign-default-rate", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-def", title: "USD Default Rate", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "entry-def",
      voucher_type: "Journal",
      date: "20250410",
      vendor_name: "GitHub Inc",
      amount: 8300, // 100 USD @ 83.00 (default rate)
      debit_ledger: "Software Subscriptions",
      credit_ledger: "ICICI Bank",
      narration: "GitHub annual subscription",
      gst_entries: [],
      status: "draft",
      warnings: ["Used default USD→INR rate of 83.00 (no rate found on the document)."],
      is_new_ledger: false,
      suggested_parent: null,
      original_currency: "USD",
      original_amount: 100,
      fx_rate: 83.0,
      original_gst_entries: [],
    };

    await page.route("**/api/workspaces/ws-1/conversations/conv-def", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(conversationWith(entry, "conv-def", "USD Default Rate")),
        });
      } else {
        route.continue();
      }
    });

    await page.goto("/c/conv-def");
    await page.waitForSelector('[data-testid="voucher-review-entry-def"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-entry-def"]');
    await expect(card).toBeVisible();
    await expect(card).toContainText("GitHub Inc");
    // FX line: "USD 100.00 @ ₹83.00 = ₹8,300.00"
    await expect(card).toContainText("USD 100.00 @ ₹83.00 = ₹8,300.00");
    // Hint present
    await expect(card).toContainText('Wrong rate? Reply "use rate <n>" in chat.');
    // INR amount
    await expect(card).toContainText("₹8,300.00");
    // Warning present
    await expect(card).toContainText("Used default USD→INR rate of 83.00 (no rate found on the document).");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; field grid; FX block (2 lines); amber warning block below the FX block;
    //         three action buttons (Write to Tally / Edit Entry / Discard).
    // Text:   FX line "USD 100.00 @ ₹83.00 = ₹8,300.00"; hint 'Wrong rate? Reply "use rate <n>" in chat.';
    //         warning "Used default USD→INR rate of 83.00 (no rate found on the document)."; Amount "₹8,300.00".
    // Colors: blue draft border; FX line gray-600 + hint gray-400; warning amber (text-amber-600).
    // Spacing: FX block mb-2 above warning block (also mb-2); both above the action buttons.
    // NOT visible: NO "No conversion rate" text; entry still has all three action buttons enabled (draft).
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("fx-foreign-default-rate.png");
  });

  // -----------------------------------------------------------------------
  // State 4: USD entry, no rate (amount 0) — "No conversion rate ..." warning.
  // -----------------------------------------------------------------------
  test("fx-foreign-no-rate", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-no", title: "USD No Rate", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "entry-no",
      voucher_type: "Journal",
      date: "20250410",
      vendor_name: "Stripe Inc",
      amount: 0, // no rate → INR amount could not be computed
      debit_ledger: "Payment Gateway Fees",
      credit_ledger: "ICICI Bank",
      narration: "Stripe processing fee",
      gst_entries: [],
      status: "draft",
      warnings: ["No conversion rate for USD — this entry can't be written yet. Reply \"use rate <n>\" in chat."],
      is_new_ledger: false,
      suggested_parent: null,
      original_currency: "USD",
      original_amount: 100,
      fx_rate: 0,
      original_gst_entries: [],
    };

    await page.route("**/api/workspaces/ws-1/conversations/conv-no", (route) => {
      if (route.request().method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(conversationWith(entry, "conv-no", "USD No Rate")),
        });
      } else {
        route.continue();
      }
    });

    await page.goto("/c/conv-no");
    await page.waitForSelector('[data-testid="voucher-review-entry-no"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-entry-no"]');
    await expect(card).toBeVisible();
    await expect(card).toContainText("Stripe Inc");
    // FX line with zero rate/amount: "USD 100.00 @ ₹0.00 = ₹0.00"
    await expect(card).toContainText("USD 100.00 @ ₹0.00 = ₹0.00");
    // Hint still rendered for the foreign-currency block
    await expect(card).toContainText('Wrong rate? Reply "use rate <n>" in chat.');
    // The "can't be written yet" warning
    await expect(card).toContainText(
      'No conversion rate for USD — this entry can\'t be written yet. Reply "use rate <n>" in chat.',
    );

    // VISUAL CHECKLIST:
    // Layout: blue draft card; field grid (Amount shows ₹0.00); FX block (2 lines); amber warning block;
    //         three action buttons (Write to Tally / Edit Entry / Discard).
    // Text:   FX line "USD 100.00 @ ₹0.00 = ₹0.00"; hint 'Wrong rate? Reply "use rate <n>" in chat.';
    //         warning 'No conversion rate for USD — this entry can't be written yet. Reply "use rate <n>" in chat.';
    //         Amount field "₹0.00".
    // Colors: blue draft border; FX line gray-600 + hint gray-400; warning amber (text-amber-600).
    // Spacing: FX block mb-2 above warning block; warning text may wrap to 2 lines on mobile.
    // NOT visible: NO "Used default" text; NO non-zero INR amount in the FX line.
    {
      const badge = page.getByTestId("header-workspace-badge");
      if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
    }
    await expect(page).toHaveScreenshot("fx-foreign-no-rate.png");
  });
});
