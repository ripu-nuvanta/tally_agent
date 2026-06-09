import type { VoucherEntry } from "./VoucherReviewCard";
import { formatINR } from "../utils/format";

interface VoucherReviewExpandedProps {
  entry: VoucherEntry;
}

function formatFx(entry: VoucherEntry): string {
  const cur = entry.original_currency ?? "";
  const orig = (entry.original_amount ?? 0).toFixed(2);
  const rate = (entry.fx_rate ?? 0).toFixed(2);
  return `${cur} ${orig} @ ₹${rate} = ${formatINR(entry.amount)}`;
}

/** Read-only detail view: ledger mappings, GST, FX, bill reference. */
export default function VoucherReviewExpanded({ entry }: VoucherReviewExpandedProps) {
  const isForeign = !!entry.original_currency && entry.original_currency !== "INR";

  return (
    <div className="mt-2 space-y-2 text-sm" data-testid={`voucher-expanded-${entry.id}`}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <Field label="Debit" value={entry.debit_ledger} />
        <Field label="Credit" value={entry.credit_ledger} />
        <Field label="Narration" value={entry.narration} />
      </div>

      {isForeign && (
        <div className="text-xs text-gray-600">
          <div>{formatFx(entry)}</div>
          <div className="text-gray-400">Wrong rate? Reply "use rate &lt;n&gt;" in chat.</div>
        </div>
      )}

      {entry.gst_entries.length > 0 && (
        <div className="text-xs text-gray-500">
          GST:{" "}
          {entry.gst_entries.map((g) => `${g.ledger}: ${formatINR(g.amount)}`).join(", ")}
        </div>
      )}

      {(entry.voucher_type === "Debit Note" || entry.voucher_type === "Credit Note") &&
        entry.bill_reference && (
          <div className="text-xs text-gray-600">Against: Invoice #{entry.bill_reference}</div>
        )}

      {entry.is_new_ledger && (
        <div className="text-xs text-amber-600">
          New ledger "{entry.debit_ledger}" will be created under "{entry.suggested_parent}"
        </div>
      )}
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
