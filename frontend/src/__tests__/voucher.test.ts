import { describe, it, expect } from "vitest";
import { newLedgerDisplay } from "../utils/voucher";
import type { VoucherEntry } from "../components/VoucherReviewCard";

function makeEntry(overrides: Partial<VoucherEntry> = {}): VoucherEntry {
  return {
    id: "v1",
    voucher_type: "Payment",
    date: "01-Apr-2026",
    vendor_name: null,
    amount: 100,
    debit_ledger: "Travel Expenses",
    credit_ledger: "Cash",
    narration: "",
    gst_entries: [],
    status: "draft",
    warnings: [],
    is_new_ledger: true,
    suggested_parent: null,
    ...overrides,
  };
}

describe("newLedgerDisplay", () => {
  it("Payment → debit_ledger under Indirect Expenses", () => {
    const r = newLedgerDisplay(makeEntry({ voucher_type: "Payment" }));
    expect(r).toEqual({ name: "Travel Expenses", parent: "Indirect Expenses" });
  });

  it("Purchase → party ledger under Sundry Creditors", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Purchase",
        party_ledger: "Acme Supplies",
        debit_ledger: "Purchase Accounts",
      }),
    );
    expect(r).toEqual({ name: "Acme Supplies", parent: "Sundry Creditors" });
  });

  it("Debit Note → party ledger under Sundry Creditors", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Debit Note",
        party_ledger: "Acme Supplies",
        debit_ledger: "Acme Supplies",
      }),
    );
    expect(r).toEqual({ name: "Acme Supplies", parent: "Sundry Creditors" });
  });

  it("Sales → party ledger under Sundry Debtors", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Sales",
        party_ledger: "Globex Ltd",
        debit_ledger: "Globex Ltd",
      }),
    );
    expect(r).toEqual({ name: "Globex Ltd", parent: "Sundry Debtors" });
  });

  it("Credit Note → party ledger under Sundry Debtors", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Credit Note",
        party_ledger: "Globex Ltd",
        debit_ledger: "Sales Returns",
      }),
    );
    expect(r).toEqual({ name: "Globex Ltd", parent: "Sundry Debtors" });
  });

  it("suggested_parent wins over the fallback (Purchase)", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Purchase",
        party_ledger: "Acme Supplies",
        suggested_parent: "Sundry Creditors - Overseas",
      }),
    );
    expect(r).toEqual({ name: "Acme Supplies", parent: "Sundry Creditors - Overseas" });
  });

  it("suggested_parent wins over the fallback (Payment)", () => {
    const r = newLedgerDisplay(
      makeEntry({ voucher_type: "Payment", suggested_parent: "Direct Expenses" }),
    );
    expect(r).toEqual({ name: "Travel Expenses", parent: "Direct Expenses" });
  });

  it("falls back to party_name when party_ledger is null (party voucher)", () => {
    const r = newLedgerDisplay(
      makeEntry({
        voucher_type: "Purchase",
        party_ledger: null,
        party_name: "Acme Supplies",
      }),
    );
    expect(r).toEqual({ name: "Acme Supplies", parent: "Sundry Creditors" });
  });
});
