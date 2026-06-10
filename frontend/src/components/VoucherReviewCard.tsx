import { useState } from "react";
import { formatINR } from "../utils/format";
import VoucherReviewExpanded from "./VoucherReviewExpanded";
import VoucherEditForm from "./VoucherEditForm";
import type { AgainstInvoiceOption } from "./VoucherRefSelect";

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
  // Invoice-entry Phase 1
  reference?: string | null;
  reference_date?: string | null;
  duplicate_of?: { voucher_no: string; date: string; reason: string } | null;
  // Group B additions
  party_name?: string | null;
  party_ledger?: string | null;
  is_party_ledger?: boolean;
  bill_reference?: string | null;
  bill_type?: string | null;
  against_invoice_options?: AgainstInvoiceOption[];
  original_currency?: string;
  original_amount?: number;
  fx_rate?: number;
  inr_amount?: number;
  original_gst_entries?: Array<{ ledger: string; amount: number }>;
}

interface VoucherReviewCardProps {
  entries: VoucherEntry[];
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  availableSupplierLedgers?: string[];
  availableCustomerLedgers?: string[];
  onApprove: (entryId: string) => void;
  onDiscard: (entryId: string) => void;
  onEdit: (entryId: string, updates: Partial<VoucherEntry>) => void;
  pendingAction?: { entryId: string; action: "approve" | "discard" } | null;
}

function formatDate(dateStr: string): string {
  if (dateStr.length === 8 && /^\d{8}$/.test(dateStr)) {
    const y = dateStr.slice(0, 4);
    const m = dateStr.slice(4, 6);
    const d = dateStr.slice(6, 8);
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${d}-${months[parseInt(m, 10) - 1]}-${y}`;
  }
  return dateStr;
}

const TYPE_BADGE: Record<string, string> = {
  Payment: "bg-blue-100 text-blue-800",
  Purchase: "bg-orange-100 text-orange-800",
  Sales: "bg-green-100 text-green-800",
  "Debit Note": "bg-red-100 text-red-800",
  "Credit Note": "bg-amber-100 text-amber-800",
};

function Spinner() {
  return (
    <svg data-testid="spinner" className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

export default function VoucherReviewCard({
  entries,
  availableLedgers,
  availablePaymentLedgers,
  availableSupplierLedgers = [],
  availableCustomerLedgers = [],
  onApprove,
  onDiscard,
  onEdit,
  pendingAction,
}: VoucherReviewCardProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {entries.map((entry) => {
        const isEditing = editingId === entry.id;
        const isExpanded = expandedId === entry.id;
        const isForeign = !!entry.original_currency && entry.original_currency !== "INR";
        const partyLabel = entry.party_name || entry.vendor_name || "—";
        const isReturn = entry.voucher_type === "Debit Note" || entry.voucher_type === "Credit Note";
        const isDuplicate = entry.status === "duplicate";

        return (
          <div
            key={entry.id}
            className={`rounded-lg border p-4 ${
              entry.status === "written"
                ? "border-green-200 bg-green-50"
                : entry.status === "deleted"
                ? "border-gray-200 bg-gray-50 opacity-60"
                : entry.status === "pending"
                ? "border-yellow-200 bg-yellow-50"
                : isDuplicate
                ? "border-red-300 bg-red-50"
                : "border-blue-200 bg-blue-50"
            }`}
            data-testid={`voucher-review-${entry.id}`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    TYPE_BADGE[entry.voucher_type] || "bg-gray-100 text-gray-800"
                  }`}
                  data-testid={`voucher-type-badge-${entry.id}`}
                >
                  {entry.voucher_type}
                </span>
                <span className="text-sm font-medium text-gray-700">
                  {entry.status === "written"
                    ? "Written"
                    : entry.status === "deleted"
                    ? "Discarded"
                    : entry.status === "pending"
                    ? "Pending"
                    : isDuplicate
                    ? "Duplicate"
                    : "Draft"}
                </span>
              </div>
            </div>

            {isDuplicate && entry.duplicate_of && (
              <div
                className="mb-3 rounded-md border border-red-300 bg-red-100 px-3 py-2 text-sm font-medium text-red-800"
                data-testid={`voucher-duplicate-banner-${entry.id}`}
              >
                {`⚠ Duplicate of voucher #${entry.duplicate_of.voucher_no} (written ${formatDate(
                  entry.duplicate_of.date,
                )}) — ${entry.duplicate_of.reason}. Not written.`}
              </div>
            )}

            {isEditing ? (
              <VoucherEditForm
                entry={entry}
                availableLedgers={availableLedgers}
                availablePaymentLedgers={availablePaymentLedgers}
                availableSupplierLedgers={availableSupplierLedgers}
                availableCustomerLedgers={availableCustomerLedgers}
                onSave={(updates) => {
                  onEdit(entry.id, updates);
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm mb-3">
                  {entry.voucher_type !== "Payment" && (
                    <Field label="Party" value={partyLabel} />
                  )}
                  {entry.voucher_type === "Payment" && (
                    <Field label="Vendor" value={entry.vendor_name || "—"} />
                  )}
                  <Field label="Date" value={formatDate(entry.date)} />
                  <Field label="Invoice #" value={entry.reference || "—"} muted={!entry.reference} />
                  <Field label="Amount" value={formatINR(entry.amount)} />
                  {isForeign && (
                    <Field
                      label="Original"
                      value={`${entry.original_currency} ${(entry.original_amount ?? 0).toFixed(2)}`}
                    />
                  )}
                  {isReturn && entry.bill_reference && (
                    <Field label="Against" value={`Invoice #${entry.bill_reference}`} />
                  )}
                </div>

                {entry.is_new_ledger && (
                  <div className="text-xs text-amber-600 mb-2">
                    New ledger "{entry.debit_ledger}" will be created under "{entry.suggested_parent}"
                  </div>
                )}

                {entry.warnings.length > 0 && (
                  <div className="text-xs text-amber-600 mb-2" data-testid={`voucher-warnings-${entry.id}`}>
                    {entry.warnings.map((w, i) => (
                      <div key={i}>{w}</div>
                    ))}
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {isExpanded ? "Hide details" : "Show details"}
                </button>

                {isExpanded && <VoucherReviewExpanded entry={entry} />}

                {(entry.status === "draft" || entry.status === "pending" || isDuplicate) && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {(() => {
                      // Pending blocks every action; a duplicate hard-blocks the
                      // write only (Edit/Discard stay live so a mis-read invoice
                      // no. can be corrected or the entry dropped).
                      const blockAll = entry.status === "pending";
                      const writeDisabled = blockAll || isDuplicate;
                      return (
                        <>
                          <button
                            type="button"
                            onClick={() => onApprove(entry.id)}
                            disabled={writeDisabled}
                            className={`px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm transition-colors flex items-center gap-1.5 ${
                              writeDisabled ? "opacity-50 cursor-not-allowed" : "hover:bg-green-700"
                            }`}
                          >
                            {pendingAction?.entryId === entry.id && pendingAction.action === "approve" && <Spinner />}
                            Write to Tally
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingId(entry.id)}
                            disabled={blockAll}
                            className={`px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 text-sm transition-colors ${
                              blockAll ? "opacity-50 cursor-not-allowed" : "hover:bg-gray-50"
                            }`}
                          >
                            Edit Entry
                          </button>
                          <button
                            type="button"
                            onClick={() => onDiscard(entry.id)}
                            disabled={blockAll}
                            className={`px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-600 text-sm transition-colors flex items-center gap-1.5 ${
                              blockAll ? "opacity-50 cursor-not-allowed" : "hover:bg-red-50"
                            }`}
                          >
                            {pendingAction?.entryId === entry.id && pendingAction.action === "discard" && <Spinner />}
                            Discard
                          </button>
                        </>
                      );
                    })()}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <span className="text-gray-500">{label}:</span>{" "}
      <span className={muted ? "text-gray-400" : "text-gray-900"}>{value}</span>
    </div>
  );
}
