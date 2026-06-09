import { useState } from "react";
import type { VoucherEntry } from "./VoucherReviewCard";
import LineItemEditor from "./LineItemEditor";
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
  const [error, setError] = useState("");

  // Primary (non-party) ledger. For Payment this is the expense ledger and
  // the credit (payment) ledger is editable separately.
  const initialPrimary =
    entry.voucher_type === "Sales" || entry.voucher_type === "Credit Note"
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

  const handleSave = () => {
    if (showParty && !partyLedger) {
      setError("Select a party ledger.");
      return;
    }
    if (!primaryLedger) {
      setError("Select a ledger.");
      return;
    }

    // Map fields back onto debit/credit by voucher direction.
    let debitLedger: string;
    let creditLedger: string;
    if (voucherType === "Payment") {
      debitLedger = primaryLedger;
      creditLedger = paymentLedger;
    } else if (voucherType === "Purchase" || voucherType === "Debit Note") {
      // party on credit (Purchase) / debit (DN) — keep party + primary distinct
      if (voucherType === "Purchase") {
        debitLedger = primaryLedger;
        creditLedger = partyLedger;
      } else {
        debitLedger = partyLedger;
        creditLedger = primaryLedger;
      }
    } else {
      // Sales / Credit Note
      if (voucherType === "Sales") {
        debitLedger = partyLedger;
        creditLedger = primaryLedger;
      } else {
        debitLedger = primaryLedger;
        creditLedger = partyLedger;
      }
    }

    const updates: Partial<VoucherEntry> = {
      voucher_type: voucherType,
      date: formatDateForStorage(date),
      amount: parseFloat(amount),
      narration,
      debit_ledger: debitLedger,
      credit_ledger: creditLedger,
    };
    if (showParty) {
      updates.party_name = partyLedger;
      updates.party_ledger = partyLedger;
      updates.is_party_ledger = true;
    }
    if (showRef) {
      updates.bill_reference = billReference;
      updates.bill_type = "Agst Ref";
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

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSave}
          className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700"
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
