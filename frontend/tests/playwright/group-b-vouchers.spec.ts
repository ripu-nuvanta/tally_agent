import { test, expect } from "@playwright/test";

// Group B voucher-TYPE visual tests for VoucherReviewCard (Task 16).
// The VoucherReviewCard now renders five voucher types, each with a colored
// type badge, a party/vendor field, and (for Debit/Credit Note) an
// "Against: Invoice #…" reference line in the collapsed grid. Foreign-currency
// entries show an "Original" field collapsed and an FX "@ ₹" line when expanded.
//
// State matrix (VoucherReviewCard × voucher type × 3 viewports mobile/tablet/desktop):
//   1. payment-inr    — Payment, INR: Vendor field, NO Party, NO Against ref.
//   2. purchase-inr   — Purchase, INR: orange badge, Party field, GST line (expanded).
//   3. sales-inr      — Sales, INR: green badge, Party field.
//   4. debit-note     — Debit Note, INR: red badge, Party + "Against: Invoice #INV-2025".
//   5. credit-note    — Credit Note, INR: amber badge, Party + "Against: Invoice #SI-1001".
//   6. purchase-usd-expanded — Purchase, USD: orange badge, "Original USD 100.00" field
//                              collapsed; FX line "USD 100.00 @ ₹83.50 = ₹8,350.00" when expanded.
//
// NOTE: Slice A's fx-review-card.spec.ts already covers the FX warning states
// (doc/default/no-rate) on a Journal entry — this spec does NOT duplicate those.
// It focuses on the 5 voucher TYPES, the DN/CN against-invoice display, and the
// FX line on a Purchase-type card.
//
// Pattern mirrors fx-review-card.spec.ts / db-mode.spec.ts: mock auth + workspace
// + conversation endpoints, navigate to /c/<conv-id>, assert content BEFORE every
// screenshot.

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
      { id: "msg-u", role: "user", content: "Here is a document", data: null, chart: null },
      {
        id: "msg-a",
        role: "assistant",
        content: "I've extracted the voucher entry. Please review:",
        data: {
          type: "voucher_review",
          entries: [entry],
          available_ledgers: ["Purchase Accounts", "Sales Accounts", "Purchase Returns", "Sales Returns"],
          available_payment_ledgers: ["ICICI Bank", "Cash", "Petty Cash"],
          available_supplier_ledgers: ["Acme Supplies", "Beta Traders"],
          available_customer_ledgers: ["Globex Ltd", "Initech"],
        },
        chart: null,
      },
    ],
    created_at: "2025-04-10T10:00:00Z",
    updated_at: "2025-04-10T10:05:00Z",
  };
}

/** Register the single-conversation GET route for a given conv id + entry. */
async function routeConversation(
  page: import("@playwright/test").Page,
  convId: string,
  title: string,
  entry: Record<string, unknown>,
) {
  await page.route(`**/api/workspaces/ws-1/conversations/${convId}`, (route) => {
    if (route.request().method() === "GET") {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(conversationWith(entry, convId, title)),
      });
    } else {
      route.continue();
    }
  });
}

/** Wait for the workspace badge to settle (avoid "Checking" flicker in shots). */
async function settleBadge(page: import("@playwright/test").Page) {
  const badge = page.getByTestId("header-workspace-badge");
  if (await badge.count()) await expect(badge).not.toContainText("Checking", { timeout: 10000 });
}

test.describe("Group B voucher-type VoucherReviewCard visual tests", () => {
  // -----------------------------------------------------------------------
  // State 1: Payment, INR — Vendor field (NOT Party), no Against ref, blue badge.
  // -----------------------------------------------------------------------
  test("payment-inr", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-pay", title: "Payment INR", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "pay",
      voucher_type: "Payment",
      date: "20260404",
      vendor_name: "Uber",
      amount: 500,
      debit_ledger: "Travel Expenses",
      credit_ledger: "Cash",
      narration: "Uber — Ride",
      gst_entries: [],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
    };
    await routeConversation(page, "conv-pay", "Payment INR", entry);

    await page.goto("/c/conv-pay");
    await page.waitForSelector('[data-testid="voucher-review-pay"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-pay"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-pay")).toContainText("Payment");
    await expect(card).toContainText("Vendor:");
    await expect(card).toContainText("Uber");
    await expect(card).toContainText("₹500.00");
    // Payment has NO party field and NO against-invoice ref.
    await expect(card).not.toContainText("Party:");
    await expect(card).not.toContainText("Against:");

    // VISUAL CHECKLIST:
    // Layout: single blue draft card; type badge "Payment" (top-left) + "Draft" status text;
    //         field grid (Vendor / Date / Amount); "Show details" link; three action buttons.
    // Text:   badge "Payment"; "Vendor: Uber"; "Date: 04-Apr-2026"; "Amount: ₹500.00".
    // Colors: blue type badge (bg-blue-100 text-blue-800); blue draft border; green "Write to Tally".
    // Spacing: 1-col grid on mobile, 2-col on tablet/desktop.
    // NOT visible: NO "Party:" field, NO "Against:" reference, NO GST line, NO "Original" FX field.
    await settleBadge(page);
    await expect(page).toHaveScreenshot("payment-inr.png");
  });

  // -----------------------------------------------------------------------
  // State 2: Purchase, INR — orange badge, Party field, GST (expanded).
  // -----------------------------------------------------------------------
  test("purchase-inr", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-pur", title: "Purchase INR", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "pur",
      voucher_type: "Purchase",
      date: "20260410",
      vendor_name: "Acme Supplies",
      party_name: "Acme Supplies",
      party_ledger: "Acme Supplies",
      is_party_ledger: true,
      amount: 11800,
      debit_ledger: "Purchase Accounts",
      credit_ledger: "Acme Supplies",
      narration: "Purchase — Acme Supplies",
      bill_reference: "INV-2025",
      bill_type: "New Ref",
      gst_entries: [
        { ledger: "INPUT CGST", amount: 900 },
        { ledger: "INPUT SGST", amount: 900 },
      ],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
    };
    await routeConversation(page, "conv-pur", "Purchase INR", entry);

    await page.goto("/c/conv-pur");
    await page.waitForSelector('[data-testid="voucher-review-pur"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-pur"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-pur")).toContainText("Purchase");
    await expect(card).toContainText("Party:");
    await expect(card).toContainText("Acme Supplies");
    await expect(card).toContainText("₹11,800.00");
    await expect(card).not.toContainText("Vendor:");

    // Expand to reveal GST + ledger mapping.
    await card.getByRole("button", { name: "Show details" }).click();
    const expanded = page.locator('[data-testid="voucher-expanded-pur"]');
    await expect(expanded).toBeVisible();
    await expect(expanded).toContainText("Debit:");
    await expect(expanded).toContainText("Purchase Accounts");
    await expect(expanded).toContainText("INPUT CGST: ₹900.00, INPUT SGST: ₹900.00");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; orange "Purchase" badge; field grid (Party / Date / Amount);
    //         expanded detail block (Debit / Credit / Narration grid + GST line); "Hide details" link.
    // Text:   badge "Purchase"; "Party: Acme Supplies"; "Amount: ₹11,800.00";
    //         "Debit: Purchase Accounts"; "Credit: Acme Supplies";
    //         GST "INPUT CGST: ₹900.00, INPUT SGST: ₹900.00".
    // Colors: orange type badge (bg-orange-100 text-orange-800); blue draft border; GST text gray-500.
    // Spacing: expanded block sits between the grid and the action buttons.
    // NOT visible: NO "Vendor:" label, NO "Against:" reference, NO FX "@ ₹" line (INR entry).
    await settleBadge(page);
    await expect(page).toHaveScreenshot("purchase-inr-expanded.png");
  });

  // -----------------------------------------------------------------------
  // State 3: Sales, INR — green badge, Party field.
  // -----------------------------------------------------------------------
  test("sales-inr", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-sal", title: "Sales INR", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "sal",
      voucher_type: "Sales",
      date: "20260412",
      vendor_name: "Globex Ltd",
      party_name: "Globex Ltd",
      party_ledger: "Globex Ltd",
      is_party_ledger: true,
      amount: 23600,
      debit_ledger: "Globex Ltd",
      credit_ledger: "Sales Accounts",
      narration: "Sales — Globex Ltd",
      bill_reference: "SI-1001",
      bill_type: "New Ref",
      gst_entries: [
        { ledger: "OUTPUT CGST", amount: 1800 },
        { ledger: "OUTPUT SGST", amount: 1800 },
      ],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
    };
    await routeConversation(page, "conv-sal", "Sales INR", entry);

    await page.goto("/c/conv-sal");
    await page.waitForSelector('[data-testid="voucher-review-sal"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-sal"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-sal")).toContainText("Sales");
    await expect(card).toContainText("Party:");
    await expect(card).toContainText("Globex Ltd");
    await expect(card).toContainText("₹23,600.00");
    await expect(card).not.toContainText("Vendor:");
    await expect(card).not.toContainText("Against:");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; green "Sales" badge; field grid (Party / Date / Amount);
    //         "Show details" link; three action buttons.
    // Text:   badge "Sales"; "Party: Globex Ltd"; "Date: 12-Apr-2026"; "Amount: ₹23,600.00".
    // Colors: green type badge (bg-green-100 text-green-800); blue draft border.
    // Spacing: 1-col grid mobile, 2-col tablet/desktop.
    // NOT visible: NO "Vendor:" label, NO "Against:" reference (Sales is not a return), NO FX field.
    await settleBadge(page);
    await expect(page).toHaveScreenshot("sales-inr.png");
  });

  // -----------------------------------------------------------------------
  // State 4: Debit Note, INR — red badge, Party + "Against: Invoice #INV-2025".
  // -----------------------------------------------------------------------
  test("debit-note", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-dn", title: "Debit Note", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "dn",
      voucher_type: "Debit Note",
      date: "20260414",
      vendor_name: "Acme Supplies",
      party_name: "Acme Supplies",
      party_ledger: "Acme Supplies",
      is_party_ledger: true,
      amount: 2360,
      // Purchase return: party on DEBIT, purchase-returns on CREDIT.
      debit_ledger: "Acme Supplies",
      credit_ledger: "Purchase Returns",
      narration: "Debit Note — Acme Supplies",
      bill_reference: "INV-2025",
      bill_type: "Agst Ref",
      against_invoice_options: [
        { voucher_number: "INV-2025", date: "20260410", amount: 11800, reference: "INV-2025" },
        { voucher_number: "INV-2030", date: "20260411", amount: 5900, reference: "INV-2030" },
      ],
      gst_entries: [],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
    };
    await routeConversation(page, "conv-dn", "Debit Note", entry);

    await page.goto("/c/conv-dn");
    await page.waitForSelector('[data-testid="voucher-review-dn"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-dn"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-dn")).toContainText("Debit Note");
    await expect(card).toContainText("Party:");
    await expect(card).toContainText("Acme Supplies");
    await expect(card).toContainText("₹2,360.00");
    // The against-invoice reference shows in the collapsed grid for returns.
    await expect(card).toContainText("Against:");
    await expect(card).toContainText("Invoice #INV-2025");
    await expect(card).not.toContainText("Vendor:");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; red "Debit Note" badge; field grid (Party / Date / Amount / Against);
    //         "Show details" link; three action buttons.
    // Text:   badge "Debit Note"; "Party: Acme Supplies"; "Amount: ₹2,360.00";
    //         "Against: Invoice #INV-2025".
    // Colors: red type badge (bg-red-100 text-red-800); blue draft border.
    // Spacing: "Against" field appears as a grid cell alongside Party/Date/Amount.
    // NOT visible: NO "Vendor:" label, NO FX field (INR), NO GST line in collapsed view.
    await settleBadge(page);
    await expect(page).toHaveScreenshot("debit-note-against-invoice.png");
  });

  // -----------------------------------------------------------------------
  // State 5: Credit Note, INR — amber badge, Party + "Against: Invoice #SI-1001".
  // -----------------------------------------------------------------------
  test("credit-note", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-cn", title: "Credit Note", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "cn",
      voucher_type: "Credit Note",
      date: "20260416",
      vendor_name: "Globex Ltd",
      party_name: "Globex Ltd",
      party_ledger: "Globex Ltd",
      is_party_ledger: true,
      amount: 1180,
      // Sales return: party on CREDIT, sales-returns on DEBIT.
      debit_ledger: "Sales Returns",
      credit_ledger: "Globex Ltd",
      narration: "Credit Note — Globex Ltd",
      bill_reference: "SI-1001",
      bill_type: "Agst Ref",
      against_invoice_options: [
        { voucher_number: "SI-1001", date: "20260412", amount: 23600, reference: "SI-1001" },
      ],
      gst_entries: [],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
    };
    await routeConversation(page, "conv-cn", "Credit Note", entry);

    await page.goto("/c/conv-cn");
    await page.waitForSelector('[data-testid="voucher-review-cn"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-cn"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-cn")).toContainText("Credit Note");
    await expect(card).toContainText("Party:");
    await expect(card).toContainText("Globex Ltd");
    await expect(card).toContainText("₹1,180.00");
    await expect(card).toContainText("Against:");
    await expect(card).toContainText("Invoice #SI-1001");
    await expect(card).not.toContainText("Vendor:");

    // VISUAL CHECKLIST:
    // Layout: blue draft card; amber "Credit Note" badge; field grid (Party / Date / Amount / Against);
    //         "Show details" link; three action buttons.
    // Text:   badge "Credit Note"; "Party: Globex Ltd"; "Amount: ₹1,180.00";
    //         "Against: Invoice #SI-1001".
    // Colors: amber type badge (bg-amber-100 text-amber-800); blue draft border.
    // Spacing: "Against" field appears as a grid cell.
    // NOT visible: NO "Vendor:" label, NO FX field, NO GST line in collapsed view.
    await settleBadge(page);
    await expect(page).toHaveScreenshot("credit-note-against-invoice.png");
  });

  // -----------------------------------------------------------------------
  // State 6: Purchase, USD — "Original USD 100.00" collapsed; FX line when expanded.
  // (Slice A covers FX warning states on a Journal entry; this covers the FX line
  //  on a Purchase-TYPE card with the orange badge + Party field.)
  // -----------------------------------------------------------------------
  test("purchase-usd-fx", async ({ page }) => {
    await mockLoggedIn(page);
    await mockShell(page, [
      { id: "conv-pusd", title: "Purchase USD", tag: null, created_at: "2025-04-10T10:00:00Z", updated_at: "2025-04-10T10:05:00Z" },
    ]);

    const entry = {
      id: "pusd",
      voucher_type: "Purchase",
      date: "20260410",
      vendor_name: "Acme Supplies",
      party_name: "Acme Supplies",
      party_ledger: "Acme Supplies",
      is_party_ledger: true,
      amount: 8350, // 100 USD @ 83.50
      debit_ledger: "Purchase Accounts",
      credit_ledger: "Acme Supplies",
      narration: "Purchase — Acme Supplies (USD)",
      bill_reference: "INV-2025",
      bill_type: "New Ref",
      gst_entries: [],
      status: "draft",
      warnings: [],
      is_new_ledger: false,
      suggested_parent: null,
      original_currency: "USD",
      original_amount: 100,
      fx_rate: 83.5,
    };
    await routeConversation(page, "conv-pusd", "Purchase USD", entry);

    await page.goto("/c/conv-pusd");
    await page.waitForSelector('[data-testid="voucher-review-pusd"]', { timeout: 10000 });

    const card = page.locator('[data-testid="voucher-review-pusd"]');
    await expect(card).toBeVisible();
    await expect(page.getByTestId("voucher-type-badge-pusd")).toContainText("Purchase");
    await expect(card).toContainText("Party:");
    // Collapsed grid shows the "Original" foreign-amount field.
    await expect(card).toContainText("Original:");
    await expect(card).toContainText("USD 100.00");
    await expect(card).toContainText("₹8,350.00");

    // Expand to reveal the FX conversion line.
    await card.getByRole("button", { name: "Show details" }).click();
    const expanded = page.locator('[data-testid="voucher-expanded-pusd"]');
    await expect(expanded).toBeVisible();
    await expect(expanded).toContainText("USD 100.00 @ ₹83.50 = ₹8,350.00");
    await expect(expanded).toContainText('Wrong rate? Reply "use rate <n>" in chat.');

    // VISUAL CHECKLIST:
    // Layout: blue draft card; orange "Purchase" badge; field grid (Party / Date / Amount / Original);
    //         expanded detail block with the FX line + "Wrong rate?" hint; "Hide details" link.
    // Text:   badge "Purchase"; "Party: Acme Supplies"; "Amount: ₹8,350.00"; "Original: USD 100.00";
    //         FX line "USD 100.00 @ ₹83.50 = ₹8,350.00"; hint 'Wrong rate? Reply "use rate <n>" in chat.'.
    // Colors: orange type badge; blue draft border; FX line gray-600; hint gray-400.
    // Spacing: "Original" sits in the collapsed grid; FX block is inside the expanded detail view.
    // NOT visible: NO amber warning block (rate from doc), NO "Vendor:" label, NO GST line (none on this entry).
    await settleBadge(page);
    await expect(page).toHaveScreenshot("purchase-usd-fx-expanded.png");
  });
});
