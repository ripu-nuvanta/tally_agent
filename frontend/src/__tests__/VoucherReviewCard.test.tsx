import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoucherReviewCard from "../components/VoucherReviewCard";
import {
  paymentINR,
  purchaseINR,
  purchaseUSD,
  purchaseDuplicate,
  salesINR,
  debitNoteINR,
  creditNoteINR,
  purchaseInventory,
  purchaseInventoryDuplicate,
  availableLedgers,
  availablePaymentLedgers,
  availableSupplierLedgers,
  availableCustomerLedgers,
} from "./fixtures/voucherMockData";

const noop = vi.fn();

function renderCard(entry = paymentINR, extra = {}) {
  return render(
    <VoucherReviewCard
      entries={[entry]}
      availableLedgers={availableLedgers}
      availablePaymentLedgers={availablePaymentLedgers}
      availableSupplierLedgers={availableSupplierLedgers}
      availableCustomerLedgers={availableCustomerLedgers}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
      {...extra}
    />,
  );
}

describe("VoucherReviewCard — collapsed states", () => {
  it("renders Payment INR with vendor, date, amount, action buttons", () => {
    renderCard(paymentINR);
    expect(screen.getByText("Vendor:")).toBeInTheDocument();
    expect(screen.getAllByText(/Uber/).length).toBeGreaterThan(0);
    expect(screen.getByText("04-Apr-2026")).toBeInTheDocument();
    expect(screen.getByText("₹500.00")).toBeInTheDocument();
    expect(screen.getByText("Write to Tally")).toBeInTheDocument();
    expect(screen.getByText("Edit Entry")).toBeInTheDocument();
    expect(screen.getByText("Discard")).toBeInTheDocument();
  });

  it("shows the type badge for each voucher type", () => {
    renderCard(purchaseINR);
    expect(screen.getByTestId(`voucher-type-badge-${purchaseINR.id}`)).toHaveTextContent("Purchase");
  });

  it("Payment does not show a Party field", () => {
    renderCard(paymentINR);
    expect(screen.queryByText("Party:")).not.toBeInTheDocument();
  });

  it("Purchase shows party name and badge", () => {
    renderCard(purchaseINR);
    expect(screen.getByText("Party:")).toBeInTheDocument();
    expect(screen.getAllByText(/Acme Supplies/).length).toBeGreaterThan(0);
    expect(screen.getByTestId(`voucher-type-badge-${purchaseINR.id}`)).toHaveTextContent("Purchase");
  });

  it("Purchase USD shows both INR amount and original currency", () => {
    renderCard(purchaseUSD);
    expect(screen.getByText("₹8,350.00")).toBeInTheDocument();
    expect(screen.getByText("USD 100.00")).toBeInTheDocument();
  });

  it("Sales shows party and green badge", () => {
    renderCard(salesINR);
    expect(screen.getByText("Party:")).toBeInTheDocument();
    expect(screen.getByTestId(`voucher-type-badge-${salesINR.id}`)).toHaveTextContent("Sales");
  });

  it("Debit Note shows 'Against: Invoice #...'", () => {
    renderCard(debitNoteINR);
    expect(screen.getByText("Against:")).toBeInTheDocument();
    expect(screen.getByText("Invoice #INV-2025")).toBeInTheDocument();
    expect(screen.getByTestId(`voucher-type-badge-${debitNoteINR.id}`)).toHaveTextContent("Debit Note");
  });

  it("Credit Note shows 'Against: Invoice #...'", () => {
    renderCard(creditNoteINR);
    expect(screen.getByText("Invoice #SI-1001")).toBeInTheDocument();
    expect(screen.getByTestId(`voucher-type-badge-${creditNoteINR.id}`)).toHaveTextContent("Credit Note");
  });

  it("renders new-ledger warning", () => {
    renderCard({ ...paymentINR, is_new_ledger: true, suggested_parent: "Indirect Expenses" });
    expect(screen.getByText(/will be created/)).toBeInTheDocument();
    expect(screen.getByText(/Indirect Expenses/)).toBeInTheDocument();
  });

  it("renders amber warnings", () => {
    renderCard({ ...paymentINR, warnings: ["Total mismatch"] });
    expect(screen.getByText("Total mismatch")).toBeInTheDocument();
  });

  it("shows the supplier invoice number when reference is set", () => {
    renderCard(purchaseINR);
    expect(screen.getByText("Invoice #:")).toBeInTheDocument();
    expect(screen.getByText("PINV-FLOW-01")).toBeInTheDocument();
  });

  it("shows an em-dash for the invoice number when reference is null", () => {
    renderCard({ ...paymentINR, reference: null });
    expect(screen.getByText("Invoice #:")).toBeInTheDocument();
    const invoiceField = screen.getByText("Invoice #:").closest("div")!;
    expect(invoiceField).toHaveTextContent("Invoice #: —");
  });
});

describe("VoucherReviewCard — duplicate state", () => {
  it("renders a red banner naming the matched voucher and reason", () => {
    renderCard(purchaseDuplicate);
    const banner = screen.getByTestId(`voucher-duplicate-banner-${purchaseDuplicate.id}`);
    expect(banner).toHaveTextContent(
      "⚠ Duplicate of voucher #12 (written 10-Apr-2026) — same invoice no for party. Not written.",
    );
    expect(banner.className).toContain("red");
  });

  it("disables the Write to Tally button when status is duplicate", () => {
    renderCard(purchaseDuplicate);
    expect(screen.getByText("Write to Tally").closest("button")).toBeDisabled();
  });

  it("keeps Discard and Edit enabled when status is duplicate", () => {
    renderCard(purchaseDuplicate);
    expect(screen.getByText("Discard").closest("button")).not.toBeDisabled();
    expect(screen.getByText("Edit Entry").closest("button")).not.toBeDisabled();
  });

  it("does not render the duplicate banner for a draft entry (regression)", () => {
    renderCard(purchaseINR);
    expect(
      screen.queryByTestId(`voucher-duplicate-banner-${purchaseINR.id}`),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Write to Tally").closest("button")).not.toBeDisabled();
  });
});

describe("VoucherReviewCard — progressive disclosure", () => {
  it("toggles expanded detail view", () => {
    renderCard(purchaseINR);
    expect(screen.queryByTestId(`voucher-expanded-${purchaseINR.id}`)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByTestId(`voucher-expanded-${purchaseINR.id}`)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Hide details"));
    expect(screen.queryByTestId(`voucher-expanded-${purchaseINR.id}`)).not.toBeInTheDocument();
  });

  it("expanded view shows GST breakdown and ledger mappings", () => {
    renderCard(purchaseINR);
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByText("Debit:")).toBeInTheDocument();
    expect(screen.getByText("Credit:")).toBeInTheDocument();
    expect(screen.getByText(/INPUT CGST/)).toBeInTheDocument();
  });

  it("expanded view shows FX line for USD", () => {
    renderCard(purchaseUSD);
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByText(/USD 100\.00 @ ₹83\.50 = ₹8,350\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Wrong rate\?/)).toBeInTheDocument();
  });

  it("expanded view shows original invoice reference for Debit Note", () => {
    renderCard(debitNoteINR);
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.getByText(/Against: Invoice #INV-2025/)).toBeInTheDocument();
  });

  it("does not show FX line for INR payment (back-compat)", () => {
    renderCard(paymentINR);
    fireEvent.click(screen.getByText("Show details"));
    expect(screen.queryByText(/@ ₹/)).not.toBeInTheDocument();
  });
});

describe("VoucherReviewCard — inventory line items", () => {
  it("renders a line-items table for an inventory entry in the expanded view", () => {
    renderCard(purchaseInventory);
    fireEvent.click(screen.getByText("Show details"));
    const table = screen.getByTestId(`voucher-line-items-${purchaseInventory.id}`);
    expect(table).toBeInTheDocument();
    // column headers
    expect(screen.getByText("Item")).toBeInTheDocument();
    expect(screen.getByText("Qty")).toBeInTheDocument();
    expect(screen.getByText("Rate")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
  });

  it("shows the resolved item name, qty+unit, rate and amount per line", () => {
    renderCard(purchaseInventory);
    fireEvent.click(screen.getByText("Show details"));
    const table = screen.getByTestId(`voucher-line-items-${purchaseInventory.id}`);
    // matched line shows the matched_item name
    expect(table).toHaveTextContent("A4 Paper Ream");
    // qty with unit
    expect(table).toHaveTextContent("10 Nos");
    expect(table).toHaveTextContent("2 Nos");
    // rate + amount (INR formatted)
    expect(table).toHaveTextContent("₹250.00");
    expect(table).toHaveTextContent("₹2,500.00");
    expect(table).toHaveTextContent("₹9,000.00");
  });

  it("shows a 'new' badge with the stock_name on a create_new line", () => {
    renderCard(purchaseInventory);
    fireEvent.click(screen.getByText("Show details"));
    const table = screen.getByTestId(`voucher-line-items-${purchaseInventory.id}`);
    // create_new line shows its stock_name and a "new" badge
    expect(table).toHaveTextContent("Ergonomic Chair");
    expect(screen.getByTestId(`line-new-badge-${purchaseInventory.id}-1`)).toHaveTextContent(/new/i);
  });

  it("does not render the new badge on a matched line", () => {
    renderCard(purchaseInventory);
    fireEvent.click(screen.getByText("Show details"));
    expect(
      screen.queryByTestId(`line-new-badge-${purchaseInventory.id}-0`),
    ).not.toBeInTheDocument();
  });

  it("does not render a line-items table for an accounting-only invoice (regression)", () => {
    renderCard(purchaseINR);
    fireEvent.click(screen.getByText("Show details"));
    expect(
      screen.queryByTestId(`voucher-line-items-${purchaseINR.id}`),
    ).not.toBeInTheDocument();
  });

  it("still renders the line table for a duplicate inventory entry but blocks Write", () => {
    renderCard(purchaseInventoryDuplicate);
    fireEvent.click(screen.getByText("Show details"));
    expect(
      screen.getByTestId(`voucher-line-items-${purchaseInventoryDuplicate.id}`),
    ).toBeInTheDocument();
    expect(screen.getByText("Write to Tally").closest("button")).toBeDisabled();
  });
});

describe("VoucherReviewCard — actions", () => {
  it("calls onApprove when Write to Tally clicked", () => {
    const onApprove = vi.fn();
    renderCard(paymentINR, { onApprove });
    fireEvent.click(screen.getByText("Write to Tally"));
    expect(onApprove).toHaveBeenCalledWith(paymentINR.id);
  });

  it("calls onDiscard when Discard clicked", () => {
    const onDiscard = vi.fn();
    renderCard(paymentINR, { onDiscard });
    fireEvent.click(screen.getByText("Discard"));
    expect(onDiscard).toHaveBeenCalledWith(paymentINR.id);
  });

  it("opens the edit form when Edit Entry clicked", () => {
    renderCard(paymentINR);
    fireEvent.click(screen.getByText("Edit Entry"));
    expect(screen.getByTestId("voucher-edit-form")).toBeInTheDocument();
    expect(screen.getByLabelText("Voucher Type")).toBeInTheDocument();
  });

  it("shows written state without action buttons", () => {
    renderCard({ ...paymentINR, status: "written" });
    expect(screen.getByText(/Written/)).toBeInTheDocument();
    expect(screen.queryByText("Write to Tally")).not.toBeInTheDocument();
  });

  it("disables all buttons when status is pending", () => {
    renderCard({ ...paymentINR, status: "pending" });
    expect(screen.getByText("Write to Tally").closest("button")).toBeDisabled();
    expect(screen.getByText("Edit Entry").closest("button")).toBeDisabled();
    expect(screen.getByText("Discard").closest("button")).toBeDisabled();
  });

  it("shows spinner on approve button when pendingAction is approve", () => {
    renderCard(
      { ...paymentINR, status: "pending" },
      { pendingAction: { entryId: paymentINR.id, action: "approve" } },
    );
    const writeBtn = screen.getByText("Write to Tally").closest("button")!;
    expect(writeBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
  });

  it("shows spinner on discard button when pendingAction is discard", () => {
    renderCard(
      { ...paymentINR, status: "pending" },
      { pendingAction: { entryId: paymentINR.id, action: "discard" } },
    );
    const discardBtn = screen.getByText("Discard").closest("button")!;
    expect(discardBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
  });

  it("uses flex-wrap on action buttons container", () => {
    renderCard(paymentINR);
    const writeBtn = screen.getByText("Write to Tally");
    expect(writeBtn.closest("button")!.parentElement!.className).toContain("flex-wrap");
  });
});
