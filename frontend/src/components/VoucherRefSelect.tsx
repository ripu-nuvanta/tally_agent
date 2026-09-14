import { formatINR } from "../utils/format";

export interface AgainstInvoiceOption {
  voucher_number: string;
  date: string;
  amount: number;
  reference: string;
}

interface VoucherRefSelectProps {
  options: AgainstInvoiceOption[];
  value: string;
  onChange: (reference: string) => void;
}

function formatDate(dateStr: string): string {
  if (dateStr.length === 8 && /^\d{8}$/.test(dateStr)) {
    const y = dateStr.slice(0, 4);
    const m = dateStr.slice(4, 6);
    const d = dateStr.slice(6, 8);
    return `${d}-${m}-${y}`;
  }
  return dateStr;
}

/**
 * "Against Invoice" reference picker for Debit/Credit Notes.
 * When options are available, shows a dropdown of matching party vouchers and
 * sets bill_reference to the chosen invoice. When empty, falls back to free-text.
 */
export default function VoucherRefSelect({ options, value, onChange }: VoucherRefSelectProps) {
  if (options.length === 0) {
    return (
      <div>
        <label htmlFor="against-invoice" className="block text-xs text-gray-500 mb-1">
          Against Invoice
        </label>
        <input
          id="against-invoice"
          aria-label="Against Invoice"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter invoice reference"
          className="w-full rounded border px-2 py-1 text-sm"
        />
      </div>
    );
  }

  return (
    <div>
      <label htmlFor="against-invoice" className="block text-xs text-gray-500 mb-1">
        Against Invoice
      </label>
      <select
        id="against-invoice"
        aria-label="Against Invoice"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border px-2 py-1 text-sm"
      >
        <option value="">Select invoice...</option>
        {options.map((o) => (
          <option key={o.reference} value={o.reference}>
            #{o.voucher_number} — {formatDate(o.date)} — {formatINR(o.amount)}
          </option>
        ))}
      </select>
    </div>
  );
}
