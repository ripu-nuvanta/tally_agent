interface LineItemEditorProps {
  /** Label for the primary (non-party) ledger, e.g. "Expense Ledger" / "Revenue Ledger". */
  ledgerLabel: string;
  amount: string;
  onAmountChange: (v: string) => void;
  ledger: string;
  onLedgerChange: (v: string) => void;
  availableLedgers: string[];
  narration: string;
  onNarrationChange: (v: string) => void;
}

/**
 * Editor for the voucher's primary money line: description, amount, and the
 * non-party ledger. Renders as a stacked card (mobile) / inline group (desktop).
 */
export default function LineItemEditor({
  ledgerLabel,
  amount,
  onAmountChange,
  ledger,
  onLedgerChange,
  availableLedgers,
  narration,
  onNarrationChange,
}: LineItemEditorProps) {
  return (
    <div className="rounded border border-gray-200 p-2 space-y-2" data-testid="line-item">
      <div>
        <label htmlFor="line-narration" className="block text-xs text-gray-500 mb-1">
          Description
        </label>
        <input
          id="line-narration"
          aria-label="Narration"
          value={narration}
          onChange={(e) => onNarrationChange(e.target.value)}
          placeholder="Narration"
          className="w-full rounded border px-2 py-1 text-sm"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div>
          <label htmlFor="line-amount" className="block text-xs text-gray-500 mb-1">
            Amount
          </label>
          <input
            id="line-amount"
            aria-label="Amount"
            type="number"
            value={amount}
            onChange={(e) => onAmountChange(e.target.value)}
            placeholder="Amount"
            className="w-full rounded border px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label htmlFor="line-ledger" className="block text-xs text-gray-500 mb-1">
            {ledgerLabel}
          </label>
          <select
            id="line-ledger"
            aria-label={ledgerLabel}
            value={ledger}
            onChange={(e) => onLedgerChange(e.target.value)}
            className="w-full rounded border px-2 py-1 text-sm"
          >
            {availableLedgers.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
            {ledger && !availableLedgers.includes(ledger) && (
              <option value={ledger}>{ledger} (new)</option>
            )}
          </select>
        </div>
      </div>
    </div>
  );
}
