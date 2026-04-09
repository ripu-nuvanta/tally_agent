import { useState } from "react";

export interface VoucherEntry {
  id: string;
  voucher_type: string;
  date: string;
  vendor_name: string | null;
  amount: number;
  debit_ledger: string;
  credit_ledger: string;
  narration: string;
  gst_entries: Array<{ ledger: string; amount: number }>;
  status: string;
  warnings: string[];
  is_new_ledger: boolean;
  suggested_parent: string | null;
}

interface VoucherReviewCardProps {
  entries: VoucherEntry[];
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  onApprove: (entryId: string) => void;
  onDiscard: (entryId: string) => void;
  onEdit: (entryId: string, updates: Partial<VoucherEntry>) => void;
}

function formatDate(dateStr: string): string {
  // YYYYMMDD → DD-MMM-YYYY
  if (dateStr.length === 8 && /^\d{8}$/.test(dateStr)) {
    const y = dateStr.slice(0, 4);
    const m = dateStr.slice(4, 6);
    const d = dateStr.slice(6, 8);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${d}-${months[parseInt(m, 10) - 1]}-${y}`;
  }
  return dateStr;
}

function formatAmount(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(amount);
}

export default function VoucherReviewCard({
  entries,
  availableLedgers,
  availablePaymentLedgers,
  onApprove,
  onDiscard,
  onEdit,
}: VoucherReviewCardProps) {
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className={`rounded-lg border p-4 ${
            entry.status === "written"
              ? "border-green-200 bg-green-50"
              : entry.status === "deleted"
              ? "border-gray-200 bg-gray-50 opacity-60"
              : "border-blue-200 bg-blue-50"
          }`}
          data-testid={`voucher-review-${entry.id}`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-700">
              Expense Entry — {
                entry.status === "written"
                  ? "Written"
                  : entry.status === "deleted"
                  ? "Discarded"
                  : "Draft"
              }
            </span>
          </div>

          {editingId === entry.id ? (
            <EditForm
              entry={entry}
              availableLedgers={availableLedgers}
              availablePaymentLedgers={availablePaymentLedgers}
              onSave={(updates) => {
                onEdit(entry.id, updates);
                setEditingId(null);
              }}
              onCancel={() => setEditingId(null)}
            />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                <Field label="Vendor" value={entry.vendor_name || "—"} />
                <Field label="Date" value={formatDate(entry.date)} />
                <Field label="Amount" value={formatAmount(entry.amount)} />
                <Field label="Expense Ledger" value={entry.debit_ledger} />
                <Field label="Paid via" value={entry.credit_ledger} />
                <Field label="Narration" value={entry.narration} />
              </div>

              {entry.is_new_ledger && (
                <div className="text-xs text-amber-600 mb-2">
                  New ledger "{entry.debit_ledger}" will be created under "{entry.suggested_parent}"
                </div>
              )}

              {entry.warnings.length > 0 && (
                <div className="text-xs text-amber-600 mb-2">
                  {entry.warnings.map((w, i) => (
                    <div key={i}>{w}</div>
                  ))}
                </div>
              )}

              {entry.gst_entries.length > 0 && (
                <div className="text-xs text-gray-500 mb-2">
                  GST:{" "}
                  {entry.gst_entries
                    .map((g) => `${g.ledger}: ${formatAmount(g.amount)}`)
                    .join(", ")}
                </div>
              )}

              {entry.status === "draft" && (
                <div className="flex gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => onApprove(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700 transition-colors"
                  >
                    Write to Tally
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingId(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 text-sm hover:bg-gray-50 transition-colors"
                  >
                    Edit Entry
                  </button>
                  <button
                    type="button"
                    onClick={() => onDiscard(entry.id)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-600 text-sm hover:bg-red-50 transition-colors"
                  >
                    Discard
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}:</span>{" "}
      <span className="text-gray-900">{value}</span>
    </div>
  );
}

interface EditFormProps {
  entry: VoucherEntry;
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  onSave: (updates: Partial<VoucherEntry>) => void;
  onCancel: () => void;
}

function EditForm({
  entry,
  availableLedgers,
  availablePaymentLedgers,
  onSave,
  onCancel,
}: EditFormProps) {
  const [vendor, setVendor] = useState(entry.vendor_name || "");
  const [amount, setAmount] = useState(String(entry.amount));
  const [debitLedger, setDebitLedger] = useState(entry.debit_ledger);
  const [creditLedger, setCreditLedger] = useState(entry.credit_ledger);
  const [narration, setNarration] = useState(entry.narration);

  return (
    <div className="space-y-2">
      <input
        value={vendor}
        onChange={(e) => setVendor(e.target.value)}
        placeholder="Vendor"
        aria-label="Vendor"
        className="w-full rounded border px-2 py-1 text-sm"
      />
      <input
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        type="number"
        placeholder="Amount"
        aria-label="Amount"
        className="w-full rounded border px-2 py-1 text-sm"
      />
      <select
        value={debitLedger}
        onChange={(e) => setDebitLedger(e.target.value)}
        aria-label="Expense Ledger"
        className="w-full rounded border px-2 py-1 text-sm"
      >
        {availableLedgers.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
        {!availableLedgers.includes(debitLedger) && (
          <option value={debitLedger}>{debitLedger} (new)</option>
        )}
      </select>
      <select
        value={creditLedger}
        onChange={(e) => setCreditLedger(e.target.value)}
        aria-label="Payment Ledger"
        className="w-full rounded border px-2 py-1 text-sm"
      >
        {availablePaymentLedgers.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
      <input
        value={narration}
        onChange={(e) => setNarration(e.target.value)}
        placeholder="Narration"
        aria-label="Narration"
        className="w-full rounded border px-2 py-1 text-sm"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() =>
            onSave({
              vendor_name: vendor,
              amount: parseFloat(amount),
              debit_ledger: debitLedger,
              credit_ledger: creditLedger,
              narration,
            })
          }
          className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700"
        >
          Confirm & Write to Tally
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-700 text-sm hover:bg-gray-50"
        >
          Edit Again
        </button>
      </div>
    </div>
  );
}
