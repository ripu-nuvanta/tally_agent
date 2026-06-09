import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoucherReviewCard from "../components/VoucherReviewCard";
import {
  paymentINR,
  purchaseINR,
  purchaseUSD,
  salesINR,
  debitNoteINR,
  creditNoteINR,
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
