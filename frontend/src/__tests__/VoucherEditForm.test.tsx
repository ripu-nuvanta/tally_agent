import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoucherEditForm from "../components/VoucherEditForm";
import {
  paymentINR,
  purchaseINR,
  purchaseUSD,
  salesINR,
  debitNoteINR,
  creditNoteINR,
  purchaseInventory,
  availableLedgers,
  availablePaymentLedgers,
  availableSupplierLedgers,
  availableCustomerLedgers,
} from "./fixtures/voucherMockData";
import type { VoucherEntry } from "../components/VoucherReviewCard";

function renderForm(entry: VoucherEntry, onSave = vi.fn(), onCancel = vi.fn()) {
  render(
    <VoucherEditForm
      entry={entry}
      availableLedgers={availableLedgers}
      availablePaymentLedgers={availablePaymentLedgers}
      availableSupplierLedgers={availableSupplierLedgers}
      availableCustomerLedgers={availableCustomerLedgers}
      onSave={onSave}
      onCancel={onCancel}
    />,
  );
  return { onSave, onCancel };
}

describe("VoucherEditForm — fields by type", () => {
  it("Payment hides the party ledger field", () => {
    renderForm(paymentINR);
    expect(screen.queryByLabelText("Party Ledger")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Payment Ledger")).toBeInTheDocument();
  });

  it("Purchase shows party ledger populated from supplier ledgers", () => {
    renderForm(purchaseINR);
    const party = screen.getByLabelText("Party Ledger") as HTMLSelectElement;
    expect(party).toBeInTheDocument();
    const optionTexts = Array.from(party.options).map((o) => o.value);
    expect(optionTexts).toContain("Acme Supplies");
    expect(optionTexts).toContain("Beta Traders");
    expect(optionTexts).not.toContain("Globex Ltd");
  });

  it("Sales shows party ledger populated from customer ledgers", () => {
    renderForm(salesINR);
    const party = screen.getByLabelText("Party Ledger") as HTMLSelectElement;
    const optionTexts = Array.from(party.options).map((o) => o.value);
    expect(optionTexts).toContain("Globex Ltd");
    expect(optionTexts).toContain("Initech");
    expect(optionTexts).not.toContain("Acme Supplies");
  });
});

describe("VoucherEditForm — reclassify", () => {
  it("hides party field after reclassifying Purchase → Payment", () => {
    renderForm(purchaseINR);
    expect(screen.getByLabelText("Party Ledger")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Payment" } });
    expect(screen.queryByLabelText("Party Ledger")).not.toBeInTheDocument();
  });

  it("shows party field after reclassifying Payment → Purchase", () => {
    renderForm(paymentINR);
    expect(screen.queryByLabelText("Party Ledger")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Purchase" } });
    const party = screen.getByLabelText("Party Ledger") as HTMLSelectElement;
    const optionTexts = Array.from(party.options).map((o) => o.value);
    expect(optionTexts).toContain("Acme Supplies");
  });

  it("shows the Against Invoice picker only after reclassifying to Debit Note", () => {
    renderForm(purchaseINR);
    expect(screen.queryByLabelText("Against Invoice")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Debit Note" } });
    expect(screen.getByLabelText("Against Invoice")).toBeInTheDocument();
  });

  it("swaps party candidates when reclassifying Purchase → Sales", () => {
    renderForm(purchaseINR);
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Sales" } });
    const party = screen.getByLabelText("Party Ledger") as HTMLSelectElement;
    const optionTexts = Array.from(party.options).map((o) => o.value);
    expect(optionTexts).toContain("Globex Ltd");
    expect(optionTexts).not.toContain("Acme Supplies");
  });

  // Finding 2: reclassify must not leave stale party/bill fields on the entry.
  it("reclassifying Debit Note → Purchase clears bill_reference and uses New Ref", () => {
    const onSave = vi.fn();
    renderForm(debitNoteINR, onSave);
    // Pick the supplier party so the Purchase save passes validation.
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Purchase" } });
    fireEvent.change(screen.getByLabelText("Party Ledger"), { target: { value: "Acme Supplies" } });
    fireEvent.click(screen.getByText("Save"));
    const updates = onSave.mock.calls[0][0];
    expect(updates.voucher_type).toBe("Purchase");
    expect(updates.bill_reference).toBe("");
    expect(updates.bill_type).toBe("New Ref");
  });

  it("reclassifying Sales → Payment clears party fields", () => {
    const onSave = vi.fn();
    renderForm(salesINR, onSave);
    fireEvent.change(screen.getByLabelText("Voucher Type"), { target: { value: "Payment" } });
    fireEvent.click(screen.getByText("Save"));
    const updates = onSave.mock.calls[0][0];
    expect(updates.voucher_type).toBe("Payment");
    expect(updates.party_ledger).toBe("");
    expect(updates.party_name).toBe("");
    expect(updates.is_party_ledger).toBe(false);
  });
});

describe("VoucherEditForm — Against Invoice (DN/CN)", () => {
  it("shows the dropdown populated from against_invoice_options", () => {
    renderForm(debitNoteINR);
    const select = screen.getByLabelText("Against Invoice") as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toContain("INV-2025");
    expect(values).toContain("INV-2030");
  });

  it("selecting an invoice sets bill_reference on save", () => {
    const onSave = vi.fn();
    renderForm({ ...debitNoteINR, bill_reference: "" }, onSave);
    fireEvent.change(screen.getByLabelText("Against Invoice"), { target: { value: "INV-2030" } });
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ bill_reference: "INV-2030", bill_type: "Agst Ref" }),
    );
  });

  it("falls back to free-text when no options are present", () => {
    renderForm({ ...debitNoteINR, against_invoice_options: [], bill_reference: "" });
    const input = screen.getByLabelText("Against Invoice") as HTMLInputElement;
    expect(input.tagName).toBe("INPUT");
    fireEvent.change(input, { target: { value: "MANUAL-1" } });
    expect(input.value).toBe("MANUAL-1");
  });
});

describe("VoucherEditForm — FX override", () => {
  it("shows the INR override field for a foreign-currency entry", () => {
    renderForm(purchaseUSD);
    expect(screen.getByLabelText("INR Amount")).toBeInTheDocument();
  });

  it("hides the INR override field for INR entries", () => {
    renderForm(purchaseINR);
    expect(screen.queryByLabelText("INR Amount")).not.toBeInTheDocument();
  });

  it("uses the overridden INR amount on save", () => {
    const onSave = vi.fn();
    renderForm(purchaseUSD, onSave);
    fireEvent.change(screen.getByLabelText("INR Amount"), { target: { value: "9000" } });
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ amount: 9000 }));
  });
});

describe("VoucherEditForm — inventory line items", () => {
  it("renders an editable line-items section for an inventory entry", () => {
    renderForm(purchaseInventory);
    expect(screen.getByTestId("line-items-edit")).toBeInTheDocument();
    // one editor row per line item
    expect(screen.getAllByTestId(/^line-item-row-/)).toHaveLength(2);
  });

  it("does not render the line-items section for an accounting-only invoice", () => {
    renderForm(purchaseINR);
    expect(screen.queryByTestId("line-items-edit")).not.toBeInTheDocument();
  });

  it("matched line shows a stock-item dropdown populated from available items", () => {
    renderForm(purchaseInventory);
    const select = screen.getByLabelText("Stock Item 1") as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toContain("A4 Paper Ream");
    expect(values).toContain("Stapler");
    // matched line preselects its matched_item
    expect(select.value).toBe("A4 Paper Ream");
  });

  it("toggling 'Create new' reveals stock_name/unit/group/gst fields", () => {
    renderForm(purchaseInventory);
    // matched line (row 0) starts without the create-new fields
    expect(screen.queryByLabelText("New Item Name 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Create new 1"));
    expect(screen.getByLabelText("New Item Name 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Unit 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Stock Group 1")).toBeInTheDocument();
    expect(screen.getByLabelText("GST Rate 1")).toBeInTheDocument();
  });

  it("create-new line defaults unit to Nos and group to default_stock_group", () => {
    renderForm(purchaseInventory);
    // row 1 (lineItemNew) is already create_new
    expect((screen.getByLabelText("Unit 2") as HTMLInputElement).value).toBe("Nos");
    expect((screen.getByLabelText("Stock Group 2") as HTMLInputElement).value).toBe(
      "Office Supplies",
    );
  });

  it("editing qty and rate recomputes the displayed amount", () => {
    renderForm(purchaseInventory);
    fireEvent.change(screen.getByLabelText("Qty 1"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Rate 1"), { target: { value: "100" } });
    expect(screen.getByTestId("line-amount-0")).toHaveTextContent("₹400.00");
  });

  it("emits the updated line_items array on save", () => {
    const onSave = vi.fn();
    renderForm(purchaseInventory, onSave);
    fireEvent.change(screen.getByLabelText("Qty 1"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Rate 1"), { target: { value: "100" } });
    fireEvent.click(screen.getByText("Save"));
    const updates = onSave.mock.calls[0][0];
    expect(updates.line_items).toHaveLength(2);
    const matched = updates.line_items[0];
    expect(matched.matched_item).toBe("A4 Paper Ream");
    expect(matched.create_new).toBe(false);
    expect(matched.qty).toBe(4);
    expect(matched.rate).toBe(100);
    expect(matched.amount).toBe(400);
    const created = updates.line_items[1];
    expect(created.create_new).toBe(true);
    expect(created.stock_name).toBe("Ergonomic Chair");
    expect(created.unit).toBe("Nos");
    expect(created.stock_group).toBe("Office Supplies");
    expect(created.gst_rate).toBe(18);
  });

  it("switching a matched line to Create new emits create_new with cleared matched_item", () => {
    const onSave = vi.fn();
    renderForm(purchaseInventory, onSave);
    fireEvent.click(screen.getByLabelText("Create new 1"));
    fireEvent.change(screen.getByLabelText("New Item Name 1"), {
      target: { value: "Premium A4 Paper" },
    });
    fireEvent.click(screen.getByText("Save"));
    const line = onSave.mock.calls[0][0].line_items[0];
    expect(line.create_new).toBe(true);
    expect(line.matched_item).toBeNull();
    expect(line.stock_name).toBe("Premium A4 Paper");
    expect(line.unit).toBe("Nos");
    expect(line.stock_group).toBe("Office Supplies");
  });

  it("blocks save when an inventory row is neither matched nor create_new", () => {
    const onSave = vi.fn();
    renderForm(purchaseInventory, onSave);
    // Row 2 is create_new; toggling it off clears matched_item → invalid state
    // (create_new=false AND matched_item=null). Save must be blocked.
    fireEvent.click(screen.getByLabelText("Create new 2"));
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /matched to an existing stock item or marked Create new/i,
    );
  });

  it("re-selecting an existing item on a toggled-off row restores a valid save", () => {
    const onSave = vi.fn();
    renderForm(purchaseInventory, onSave);
    fireEvent.click(screen.getByLabelText("Create new 2"));
    // Now a dropdown is shown for row 2; pick an existing item.
    fireEvent.change(screen.getByLabelText("Stock Item 2"), {
      target: { value: "Stapler" },
    });
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalled();
    const line = onSave.mock.calls[0][0].line_items[1];
    expect(line.create_new).toBe(false);
    expect(line.matched_item).toBe("Stapler");
  });

  it("keeps non-inventory edit fields working for an accounting-only purchase", () => {
    const onSave = vi.fn();
    renderForm(purchaseINR, onSave);
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ voucher_type: "Purchase", party_ledger: "Acme Supplies" }),
    );
    // no line_items emitted for accounting-only
    expect(onSave.mock.calls[0][0].line_items).toBeUndefined();
  });
});

describe("VoucherEditForm — save & validation", () => {
  it("saves updated date and narration", () => {
    const onSave = vi.fn();
    renderForm(paymentINR, onSave);
    fireEvent.change(screen.getByLabelText("Date"), { target: { value: "2026-03-02" } });
    fireEvent.change(screen.getByLabelText("Narration"), { target: { value: "Updated note" } });
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ date: "20260302", narration: "Updated note" }),
    );
  });

  it("blocks save and shows error when a non-Payment voucher has no party", () => {
    const onSave = vi.fn();
    renderForm({ ...purchaseINR, party_ledger: "" }, onSave);
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/Select a party ledger/i)).toBeInTheDocument();
  });

  it("calls onCancel when Back clicked", () => {
    const onCancel = vi.fn();
    renderForm(paymentINR, vi.fn(), onCancel);
    fireEvent.click(screen.getByText("Back"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  // Correctness (live test 2026-06-09): a return posts INVERSE to its base
  // invoice so it reduces the bill. DN (purchase return) → party on DEBIT,
  // returns ledger on CREDIT. CN (sales return) → party on CREDIT, returns
  // ledger on DEBIT. chat.py reads the contra from the OTHER leg (DN:
  // purchase_ledger=credit_ledger; CN: sales_ledger=debit_ledger), so the two
  // legs must stay distinct.
  it("editing a Debit Note keeps party on debit, returns ledger on credit", () => {
    const onSave = vi.fn();
    renderForm(debitNoteINR, onSave);
    fireEvent.click(screen.getByText("Save"));
    const updates = onSave.mock.calls[0][0];
    expect(updates.debit_ledger).not.toBe(updates.credit_ledger);
    // party (Acme Supplies) must be on DEBIT for a Debit Note
    expect(updates.debit_ledger).toBe("Acme Supplies");
    expect(updates.credit_ledger).toBe("Purchase Returns");
    expect(updates.party_ledger).toBe("Acme Supplies");
    // dispatch reads purchase_ledger=credit_ledger → must NOT equal party
    expect(updates.credit_ledger).not.toBe(updates.party_ledger);
  });

  it("editing a Credit Note keeps party on credit, returns ledger on debit", () => {
    const onSave = vi.fn();
    renderForm(creditNoteINR, onSave);
    fireEvent.click(screen.getByText("Save"));
    const updates = onSave.mock.calls[0][0];
    expect(updates.debit_ledger).not.toBe(updates.credit_ledger);
    // party (Globex Ltd) must be on CREDIT for a Credit Note
    expect(updates.credit_ledger).toBe("Globex Ltd");
    expect(updates.debit_ledger).toBe("Sales Returns");
    expect(updates.party_ledger).toBe("Globex Ltd");
    // dispatch reads sales_ledger=debit_ledger → must NOT equal party
    expect(updates.debit_ledger).not.toBe(updates.party_ledger);
  });

  it("edits and round-trips the supplier invoice number (reference) on save", () => {
    const onSave = vi.fn();
    renderForm(purchaseINR, onSave);
    const field = screen.getByLabelText("Supplier Invoice No.") as HTMLInputElement;
    expect(field.value).toBe("PINV-FLOW-01");
    fireEvent.change(field, { target: { value: "PINV-FLOW-99" } });
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ reference: "PINV-FLOW-99" }),
    );
  });

  it("maps party to credit ledger for Purchase on save", () => {
    const onSave = vi.fn();
    renderForm(purchaseINR, onSave);
    fireEvent.click(screen.getByText("Save"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        voucher_type: "Purchase",
        credit_ledger: "Acme Supplies",
        party_ledger: "Acme Supplies",
        is_party_ledger: true,
      }),
    );
  });
});
