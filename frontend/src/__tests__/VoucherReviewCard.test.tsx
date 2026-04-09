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
});
