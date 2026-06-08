import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoucherReviewCard, { type VoucherEntry } from "../components/VoucherReviewCard";

const mockEntry: VoucherEntry = {
  id: "test-1",
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

const noop = vi.fn();

describe("VoucherReviewCard", () => {
  it("renders entry fields", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={["Travel Expenses", "Office Supplies"]}
        availablePaymentLedgers={["Cash", "Bank Account"]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getAllByText(/Uber/).length).toBeGreaterThan(0);
    expect(screen.getByText("Travel Expenses")).toBeInTheDocument();
    expect(screen.getByText("04-Apr-2026")).toBeInTheDocument();
    expect(screen.getByText("Write to Tally")).toBeInTheDocument();
    expect(screen.getByText("Edit Entry")).toBeInTheDocument();
    expect(screen.getByText("Discard")).toBeInTheDocument();
  });

  it("calls onApprove when Write to Tally clicked", () => {
    const onApprove = vi.fn();
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={onApprove}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    fireEvent.click(screen.getByText("Write to Tally"));
    expect(onApprove).toHaveBeenCalledWith("test-1");
  });

  it("calls onDiscard when Discard clicked", () => {
    const onDiscard = vi.fn();
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={onDiscard}
        onEdit={noop}
      />
    );
    fireEvent.click(screen.getByText("Discard"));
    expect(onDiscard).toHaveBeenCalledWith("test-1");
  });

  it("shows warning for new ledger", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, is_new_ledger: true, suggested_parent: "Indirect Expenses" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText(/will be created/)).toBeInTheDocument();
    expect(screen.getByText(/Indirect Expenses/)).toBeInTheDocument();
  });

  it("shows written state without action buttons", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "written" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText(/Written/)).toBeInTheDocument();
    expect(screen.queryByText("Write to Tally")).not.toBeInTheDocument();
  });

  it("shows warnings when present", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, warnings: ["Total mismatch"] }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText("Total mismatch")).toBeInTheDocument();
  });

  it("opens edit form when Edit Entry clicked", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={["Travel Expenses", "Office Supplies"]}
        availablePaymentLedgers={["Cash"]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    fireEvent.click(screen.getByText("Edit Entry"));
    expect(screen.getByLabelText("Vendor")).toBeInTheDocument();
    expect(screen.getByText("Confirm & Write to Tally")).toBeInTheDocument();
  });

  it("allows editing the date", () => {
    const onEdit = vi.fn();
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={["Travel Expenses"]}
        availablePaymentLedgers={["Cash"]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={onEdit}
      />
    );
    fireEvent.click(screen.getByText("Edit Entry"));
    const dateInput = screen.getByLabelText("Date");
    fireEvent.change(dateInput, { target: { value: "2026-03-02" } });
    fireEvent.click(screen.getByText("Confirm & Write to Tally"));
    expect(onEdit).toHaveBeenCalledWith(
      "test-1",
      expect.objectContaining({ date: "20260302" })
    );
  });

  it("calls onEdit with updated values when confirmed", () => {
    const onEdit = vi.fn();
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={["Travel Expenses", "Office Supplies"]}
        availablePaymentLedgers={["Cash"]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={onEdit}
      />
    );
    fireEvent.click(screen.getByText("Edit Entry"));
    const vendorInput = screen.getByLabelText("Vendor");
    fireEvent.change(vendorInput, { target: { value: "Ola" } });
    fireEvent.click(screen.getByText("Confirm & Write to Tally"));
    expect(onEdit).toHaveBeenCalledWith(
      "test-1",
      expect.objectContaining({ vendor_name: "Ola" })
    );
  });

  it("disables all buttons when status is pending", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "pending" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText("Write to Tally").closest("button")).toBeDisabled();
    expect(screen.getByText("Edit Entry").closest("button")).toBeDisabled();
    expect(screen.getByText("Discard").closest("button")).toBeDisabled();
  });

  it("shows spinner on approve button when pendingAction is approve", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "pending" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
        pendingAction={{ entryId: "test-1", action: "approve" }}
      />
    );
    const writeBtn = screen.getByText("Write to Tally").closest("button")!;
    expect(writeBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
    expect(writeBtn).toBeDisabled();
  });

  it("shows spinner on discard button when pendingAction is discard", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "pending" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
        pendingAction={{ entryId: "test-1", action: "discard" }}
      />
    );
    const discardBtn = screen.getByText("Discard").closest("button")!;
    expect(discardBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
    expect(discardBtn).toBeDisabled();
  });

  it("shows Pending label in status when status is pending", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, status: "pending" }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText(/Pending/)).toBeInTheDocument();
  });

  it("uses responsive grid classes on field grid", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    const grid = screen.getByText("Vendor:").closest("div")!.parentElement!;
    expect(grid.className).toContain("grid-cols-1");
    expect(grid.className).toContain("md:grid-cols-2");
  });

  it("renders FX line and hint for a foreign-currency entry", () => {
    render(
      <VoucherReviewCard
        entries={[
          {
            ...mockEntry,
            amount: 8350,
            original_currency: "USD",
            original_amount: 100,
            fx_rate: 83.5,
          },
        ]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.getByText(/USD 100\.00 @ ₹83\.50 = ₹8,350\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Wrong rate\? Reply "use rate <n>" in chat\./)).toBeInTheDocument();
    // Posted INR amount still rendered as today
    expect(screen.getByText("₹8,350.00")).toBeInTheDocument();
  });

  it("does not render FX line for an INR entry", () => {
    render(
      <VoucherReviewCard
        entries={[{ ...mockEntry, original_currency: "INR", original_amount: 500, fx_rate: 1 }]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.queryByText(/@ ₹/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Wrong rate\?/)).not.toBeInTheDocument();
  });

  it("does not render FX line when original_currency is absent (back-compat)", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    expect(screen.queryByText(/@ ₹/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Wrong rate\?/)).not.toBeInTheDocument();
  });

  it("uses flex-wrap on action buttons container", () => {
    render(
      <VoucherReviewCard
        entries={[mockEntry]}
        availableLedgers={[]}
        availablePaymentLedgers={[]}
        onApprove={noop}
        onDiscard={noop}
        onEdit={noop}
      />
    );
    const writeBtn = screen.getByText("Write to Tally");
    const btnContainer = writeBtn.closest("button")!.parentElement!;
    expect(btnContainer.className).toContain("flex-wrap");
  });
});
