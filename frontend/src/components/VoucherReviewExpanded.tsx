import type { VoucherEntry } from "./VoucherReviewCard";
import { formatINR } from "../utils/format";
import { newLedgerDisplay } from "../utils/voucher";

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

  const lineItems = entry.is_inventory && entry.line_items?.length ? entry.line_items : null;

  return (
    <div className="mt-2 space-y-2 text-sm" data-testid={`voucher-expanded-${entry.id}`}>
      {lineItems && (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-1">Items</div>
          <table
            className="w-full text-xs border-collapse"
            data-testid={`voucher-line-items-${entry.id}`}
          >
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200">
                <th className="py-1 pr-2 font-medium">Item</th>
                <th className="py-1 px-2 font-medium text-right">Qty</th>
                <th className="py-1 px-2 font-medium text-right">Rate</th>
                <th className="py-1 pl-2 font-medium text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {lineItems.map((line, i) => {
                const itemName = line.create_new
                  ? line.stock_name
                  : line.matched_item || line.description;
                return (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="py-1 pr-2 text-gray-900">
                      {itemName}
                      {line.create_new && (
                        <span
                          className="ml-1.5 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-medium"
                          data-testid={`line-new-badge-${entry.id}-${i}`}
                        >
                          new
                        </span>
                      )}
                    </td>
                    <td className="py-1 px-2 text-right text-gray-700">
                      {line.qty} {line.unit}
                    </td>
                    <td className="py-1 px-2 text-right text-gray-700">{formatINR(line.rate)}</td>
                    <td className="py-1 pl-2 text-right text-gray-900">{formatINR(line.amount)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

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

      {entry.is_new_ledger &&
        (() => {
          const { name, parent } = newLedgerDisplay(entry);
          return (
            <div className="text-xs text-amber-600">
              New ledger "{name}" will be created under "{parent}"
            </div>
          );
        })()}
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
