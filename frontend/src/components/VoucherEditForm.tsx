import { useState } from "react";
import type { VoucherEntry, LineItem } from "./VoucherReviewCard";
import LineItemEditor from "./LineItemEditor";
import InventoryLineEditor from "./InventoryLineEditor";
import VoucherRefSelect from "./VoucherRefSelect";

export const VOUCHER_TYPES = ["Payment", "Purchase", "Sales", "Debit Note", "Credit Note"] as const;
export type VoucherType = (typeof VOUCHER_TYPES)[number];

interface VoucherEditFormProps {
  entry: VoucherEntry;
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  availableSupplierLedgers: string[];
  availableCustomerLedgers: string[];
  onSave: (updates: Partial<VoucherEntry>) => void;
  onCancel: () => void;
}

function formatDateForInput(yyyymmdd: string): string {
  if (yyyymmdd.length === 8 && /^\d{8}$/.test(yyyymmdd)) {
    return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
  }
  return yyyymmdd;
}

function formatDateForStorage(yyyy_mm_dd: string): string {
  return yyyy_mm_dd.replace(/-/g, "");
}

/** Payment is the only type without a party ledger. */
function typeHasParty(t: string): boolean {
  return t !== "Payment";
}

function isReturnNote(t: string): boolean {
  return t === "Debit Note" || t === "Credit Note";
}

/** Party ledger candidates depend on the voucher direction. */
function partyLedgersForType(
  t: string,
  suppliers: string[],
  customers: string[],
): string[] {
  // Purchase / Debit Note → suppliers (Sundry Creditors)
  // Sales / Credit Note → customers (Sundry Debtors)
  if (t === "Purchase" || t === "Debit Note") return suppliers;
  if (t === "Sales" || t === "Credit Note") return customers;
  return [];
}

/** Label for the non-party (primary) ledger by type. */
function primaryLedgerLabel(t: string): string {
  switch (t) {
    case "Payment":
      return "Expense Ledger";
    case "Purchase":
      return "Purchase Ledger";
    case "Sales":
      return "Revenue Ledger";
    case "Debit Note":
      return "Returns Ledger";
    case "Credit Note":
      return "Returns Ledger";
    default:
      return "Ledger";
  }
}

/**
 * Edit form for any voucher type. Mobile: full-page overlay; Desktop: modal.
 * Reclassifying the voucher type toggles the party-ledger field and the
 * "Against Invoice" picker (DN/CN only).
 */
export default function VoucherEditForm({
  entry,
  availableLedgers,
  availablePaymentLedgers,
  availableSupplierLedgers,
  availableCustomerLedgers,
  onSave,
  onCancel,
}: VoucherEditFormProps) {
  const [voucherType, setVoucherType] = useState<string>(entry.voucher_type);
  const [partyLedger, setPartyLedger] = useState(entry.party_ledger || "");
  const [date, setDate] = useState(formatDateForInput(entry.date));
  const [amount, setAmount] = useState(String(entry.amount));
  const [narration, setNarration] = useState(entry.narration);
  const [billReference, setBillReference] = useState(entry.bill_reference || "");
  const [reference, setReference] = useState(entry.reference || "");
  const [error, setError] = useState("");

  // Inventory line items (Phase 2). Editable only for goods Purchase/Sales.
  const isInventory = !!entry.is_inventory && !!entry.line_items?.length;
  const [lineItems, setLineItems] = useState<LineItem[]>(
    entry.line_items ? entry.line_items.map((l) => ({ ...l })) : [],
  );

  // Primary (non-party) ledger = the contra/returns/expense ledger. It sits on
  // the side OPPOSITE the party. Party-on-debit types (Sales, Debit Note) keep
  // the contra on credit; party-on-credit types (Payment, Purchase, Credit
  // Note) keep the contra on debit.
  const initialPrimary =
    entry.voucher_type === "Sales" || entry.voucher_type === "Debit Note"
      ? entry.credit_ledger
      : entry.debit_ledger;
  const [primaryLedger, setPrimaryLedger] = useState(initialPrimary);
  const [paymentLedger, setPaymentLedger] = useState(entry.credit_ledger);

  // FX override (only meaningful for foreign currency).
  const isForeign = !!entry.original_currency && entry.original_currency !== "INR";

  const showParty = typeHasParty(voucherType);
  const showRef = isReturnNote(voucherType);
  const partyOptions = partyLedgersForType(
    voucherType,
    availableSupplierLedgers,
    availableCustomerLedgers,
  );
  const againstOptions = entry.against_invoice_options || [];
  // Finding 5: a row is invalid when it's neither matched nor create_new. Used
  // to disable Save (with a hint) so an unresolved row can't be written.
  const hasInvalidInventoryRow =
    isInventory && lineItems.some((l) => !l.create_new && !l.matched_item);

  const handleSave = () => {
    if (showParty && !partyLedger) {
      setError("Select a party ledger.");
      return;
    }
    if (!primaryLedger) {
      setError("Select a ledger.");
      return;
    }
    // Finding 5: every inventory row must be EITHER matched to an existing item
    // OR create_new — never neither. Toggling "Create new" off without picking
    // an existing item leaves the row invalid (create_new=false && matched_item
    // =null); block the write until it's resolved.
    if (isInventory) {
      const invalid = lineItems.findIndex(
        (l) => !l.create_new && !l.matched_item,
      );
      if (invalid !== -1) {
        const label = lineItems[invalid].description || `Item ${invalid + 1}`;
        setError(
          `Line '${label}': select an existing item or toggle Create new.`,
        );
        return;
      }
    }

    // Map fields back onto debit/credit by voucher direction. A return (DN/CN)
    // posts INVERSE to its base invoice so it reduces the bill:
    //   - Purchase: party on CREDIT, purchase ledger on DEBIT.
    //   - Sales:    party on DEBIT,  sales ledger on CREDIT.
    //   - Debit Note (purchase return): party on DEBIT, returns ledger on CREDIT.
    //   - Credit Note (sales return):   party on CREDIT, returns ledger on DEBIT.
    // chat.py reads party_ledger from party and the contra from the OTHER leg
    // (DN: purchase_ledger=credit_ledger; CN: sales_ledger=debit_ledger).
    let debitLedger: string;
    let creditLedger: string;
    if (voucherType === "Payment") {
      debitLedger = primaryLedger;
      creditLedger = paymentLedger;
    } else if (voucherType === "Purchase" || voucherType === "Credit Note") {
      // party on CREDIT, contra (primary) on DEBIT
      debitLedger = primaryLedger;
      creditLedger = partyLedger;
    } else {
      // Sales / Debit Note: party on DEBIT, contra (primary) on CREDIT
      debitLedger = partyLedger;
      creditLedger = primaryLedger;
    }

    const updates: Partial<VoucherEntry> = {
      voucher_type: voucherType,
      date: formatDateForStorage(date),
      amount: parseFloat(amount),
      narration,
      debit_ledger: debitLedger,
      credit_ledger: creditLedger,
      // Supplier invoice no. — editable so a mis-read number can be corrected.
      reference: reference.trim() || null,
    };
    // Party fields: set for party vouchers, explicitly CLEAR for Payment so a
    // reclassify (e.g. Sales → Payment) can't carry a stale party into the
    // partial merge the parent performs.
    if (showParty) {
      updates.party_name = partyLedger;
      updates.party_ledger = partyLedger;
      updates.is_party_ledger = true;
    } else {
      updates.party_name = "";
      updates.party_ledger = "";
      updates.is_party_ledger = false;
    }
    // Bill/against-invoice fields: "Agst Ref" only for DN/CN. For Purchase/Sales
    // default to "New Ref" with a cleared reference; Payment carries none. This
    // prevents a reclassify (e.g. DN → Purchase) leaving a stale "Agst Ref".
    if (showRef) {
      updates.bill_reference = billReference;
      updates.bill_type = "Agst Ref";
    } else if (voucherType === "Purchase" || voucherType === "Sales") {
      updates.bill_reference = "";
      updates.bill_type = "New Ref";
    } else {
      updates.bill_reference = "";
      updates.bill_type = "";
    }
    // Inventory: emit the edited line array. Each row carries its match-or-create
    // state plus qty/rate/amount so the backend can build the stock grid.
    if (isInventory) {
      updates.line_items = lineItems;
    }
    onSave(updates);
  };

  return (
    <div className="space-y-3" data-testid="voucher-edit-form">
      {error && <div className="text-xs text-red-600">{error}</div>}

      <div>
        <label htmlFor="edit-voucher-type" className="block text-xs text-gray-500 mb-1">
          Voucher Type
        </label>
        <select
          id="edit-voucher-type"
          aria-label="Voucher Type"
          value={voucherType}
          onChange={(e) => {
            const next = e.target.value;
            setVoucherType(next);
            setError("");
            // Reset party when the candidate list changes.
            const nextOptions = partyLedgersForType(
              next,
              availableSupplierLedgers,
              availableCustomerLedgers,
            );
            if (!nextOptions.includes(partyLedger)) {
              setPartyLedger("");
            }
          }}
          className="w-full rounded border px-2 py-1 text-sm"
        >
          {VOUCHER_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {showParty && (
        <div>
          <label htmlFor="edit-party" className="block text-xs text-gray-500 mb-1">
            Party Ledger
          </label>
          <select
            id="edit-party"
            aria-label="Party Ledger"
            value={partyLedger}
            onChange={(e) => setPartyLedger(e.target.value)}
            className="w-full rounded border px-2 py-1 text-sm"
          >
            <option value="">Select party...</option>
            {partyOptions.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
            {partyLedger && !partyOptions.includes(partyLedger) && (
              <option value={partyLedger}>{partyLedger}</option>
            )}
          </select>
        </div>
      )}

      <div>
        <label htmlFor="edit-date" className="block text-xs text-gray-500 mb-1">
          Date
        </label>
        <input
          id="edit-date"
          type="date"
          aria-label="Date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-full rounded border px-2 py-1 text-sm"
        />
      </div>

      <div>
        <label htmlFor="edit-reference" className="block text-xs text-gray-500 mb-1">
          Supplier Invoice No.
        </label>
        <input
          id="edit-reference"
          type="text"
          aria-label="Supplier Invoice No."
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          className="w-full rounded border px-2 py-1 text-sm"
        />
      </div>

      {isInventory ? (
        <InventoryLineEditor
          lines={lineItems}
          availableStockItems={entry.available_stock_items || []}
          defaultStockGroup={entry.default_stock_group || "Primary"}
          onChange={setLineItems}
        />
      ) : (
        <LineItemEditor
          ledgerLabel={primaryLedgerLabel(voucherType)}
          amount={amount}
          onAmountChange={setAmount}
          ledger={primaryLedger}
          onLedgerChange={setPrimaryLedger}
          availableLedgers={availableLedgers}
          narration={narration}
          onNarrationChange={setNarration}
        />
      )}

      {voucherType === "Payment" && (
        <div>
          <label htmlFor="edit-payment-ledger" className="block text-xs text-gray-500 mb-1">
            Paid via
          </label>
          <select
            id="edit-payment-ledger"
            aria-label="Payment Ledger"
            value={paymentLedger}
            onChange={(e) => setPaymentLedger(e.target.value)}
            className="w-full rounded border px-2 py-1 text-sm"
          >
            {availablePaymentLedgers.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
      )}

      {entry.gst_entries.length > 0 && (
        <div className="text-xs text-gray-500">
          GST: {entry.gst_entries.map((g) => `${g.ledger}: ₹${g.amount}`).join(", ")}
        </div>
      )}

      {isForeign && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2">
          <label htmlFor="edit-inr" className="block text-xs text-amber-700 mb-1">
            INR Amount (override)
          </label>
          <input
            id="edit-inr"
            aria-label="INR Amount"
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded border px-2 py-1 text-sm"
          />
        </div>
      )}

      {showRef && (
        <VoucherRefSelect
          options={againstOptions}
          value={billReference}
          onChange={setBillReference}
        />
      )}

      {hasInvalidInventoryRow && (
        <div className="text-xs text-red-600" role="alert">
          Each item must be matched to an existing stock item or marked Create
          new before you can save.
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={hasInvalidInventoryRow}
          title={
            hasInvalidInventoryRow
              ? "Each item must be matched to an existing stock item or marked Create new."
              : undefined
          }
          className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 text-sm hover:bg-gray-50"
        >
          Back
        </button>
      </div>
    </div>
  );
}
