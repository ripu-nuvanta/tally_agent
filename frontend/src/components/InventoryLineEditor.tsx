import { formatINR } from "../utils/format";
import type { LineItem } from "./VoucherReviewCard";

interface InventoryLineEditorProps {
  lines: LineItem[];
  availableStockItems: string[];
  defaultStockGroup: string;
  onChange: (lines: LineItem[]) => void;
}

/**
 * Editable inventory line-items section (Phase 2). Per row the user either
 * matches an existing Tally stock item via the dropdown, or toggles "Create
 * new" to reveal editable name/unit/group/GST. Qty and rate are always
 * editable; amount = qty × rate, recomputed live and displayed read-only.
 */
export default function InventoryLineEditor({
  lines,
  availableStockItems,
  defaultStockGroup,
  onChange,
}: InventoryLineEditorProps) {
  const update = (idx: number, patch: Partial<LineItem>) => {
    const next = lines.map((line, i) => {
      if (i !== idx) return line;
      const merged = { ...line, ...patch };
      // amount always tracks qty × rate
      merged.amount = (merged.qty || 0) * (merged.rate || 0);
      return merged;
    });
    onChange(next);
  };

  return (
    <div className="space-y-3" data-testid="line-items-edit">
      <div className="text-xs font-medium text-gray-600">Items</div>
      {lines.map((line, i) => {
        const n = i + 1; // 1-based labels for humans
        const itemName = line.create_new
          ? line.stock_name
          : line.matched_item || line.description;
        return (
          <div
            key={i}
            className="rounded border border-gray-200 p-2 space-y-2"
            data-testid={`line-item-row-${i}`}
          >
            <div className="text-xs text-gray-700 font-medium">{itemName || line.description}</div>

            {!line.create_new ? (
              <div>
                <label htmlFor={`line-stock-${i}`} className="block text-xs text-gray-500 mb-1">
                  Stock Item {n}
                </label>
                <select
                  id={`line-stock-${i}`}
                  aria-label={`Stock Item ${n}`}
                  value={line.matched_item || ""}
                  onChange={(e) => update(i, { matched_item: e.target.value })}
                  className="w-full rounded border px-2 py-1 text-sm"
                >
                  <option value="">Select item...</option>
                  {availableStockItems.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                  {line.matched_item && !availableStockItems.includes(line.matched_item) && (
                    <option value={line.matched_item}>{line.matched_item}</option>
                  )}
                </select>
              </div>
            ) : (
              <div className="space-y-2">
                <div>
                  <label htmlFor={`line-name-${i}`} className="block text-xs text-gray-500 mb-1">
                    New Item Name {n}
                  </label>
                  <input
                    id={`line-name-${i}`}
                    aria-label={`New Item Name ${n}`}
                    value={line.stock_name}
                    onChange={(e) => update(i, { stock_name: e.target.value })}
                    className="w-full rounded border px-2 py-1 text-sm"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div>
                    <label htmlFor={`line-unit-${i}`} className="block text-xs text-gray-500 mb-1">
                      Unit {n}
                    </label>
                    <input
                      id={`line-unit-${i}`}
                      aria-label={`Unit ${n}`}
                      value={line.unit}
                      onChange={(e) => update(i, { unit: e.target.value })}
                      className="w-full rounded border px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label htmlFor={`line-group-${i}`} className="block text-xs text-gray-500 mb-1">
                      Stock Group {n}
                    </label>
                    <input
                      id={`line-group-${i}`}
                      aria-label={`Stock Group ${n}`}
                      value={line.stock_group}
                      onChange={(e) => update(i, { stock_group: e.target.value })}
                      className="w-full rounded border px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label htmlFor={`line-gst-${i}`} className="block text-xs text-gray-500 mb-1">
                      GST Rate {n}
                    </label>
                    <input
                      id={`line-gst-${i}`}
                      aria-label={`GST Rate ${n}`}
                      type="number"
                      value={line.gst_rate}
                      onChange={(e) => update(i, { gst_rate: parseFloat(e.target.value) || 0 })}
                      className="w-full rounded border px-2 py-1 text-sm"
                    />
                  </div>
                </div>
              </div>
            )}

            <label className="flex items-center gap-1.5 text-xs text-gray-600">
              <input
                type="checkbox"
                aria-label={`Create new ${n}`}
                checked={line.create_new}
                onChange={(e) => {
                  const createNew = e.target.checked;
                  update(i, {
                    create_new: createNew,
                    // Switching to create-new clears the match and seeds defaults;
                    // switching back drops the match so the user re-selects.
                    matched_item: null,
                    stock_name: createNew ? line.stock_name || line.description : line.stock_name,
                    unit: line.unit || "Nos",
                    stock_group: line.stock_group || defaultStockGroup,
                  });
                }}
              />
              Create new
            </label>

            <div className="grid grid-cols-3 gap-2 items-end">
              <div>
                <label htmlFor={`line-qty-${i}`} className="block text-xs text-gray-500 mb-1">
                  Qty {n}
                </label>
                <input
                  id={`line-qty-${i}`}
                  aria-label={`Qty ${n}`}
                  type="number"
                  value={line.qty}
                  onChange={(e) => update(i, { qty: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded border px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label htmlFor={`line-rate-${i}`} className="block text-xs text-gray-500 mb-1">
                  Rate {n}
                </label>
                <input
                  id={`line-rate-${i}`}
                  aria-label={`Rate ${n}`}
                  type="number"
                  value={line.rate}
                  onChange={(e) => update(i, { rate: parseFloat(e.target.value) || 0 })}
                  className="w-full rounded border px-2 py-1 text-sm"
                />
              </div>
              <div className="text-sm text-right text-gray-900" data-testid={`line-amount-${i}`}>
                {formatINR(line.amount)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
