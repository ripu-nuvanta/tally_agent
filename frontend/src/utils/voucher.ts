import type { VoucherEntry } from "../components/VoucherReviewCard";

const PARTY_VOUCHER_TYPES = ["Purchase", "Sales", "Debit Note", "Credit Note"];

/**
 * Name + parent of the ledger the backend will actually create when
 * `is_new_ledger` is true. Mirrors `voucher_action` in backend/api/chat.py:
 *
 * - Party vouchers (Purchase/Sales/Debit Note/Credit Note) create the PARTY
 *   ledger; parent defaults to Sundry Debtors for Sales/Credit Note and
 *   Sundry Creditors otherwise.
 * - Everything else (e.g. Payment) creates the debit (expense) ledger under
 *   Indirect Expenses.
 *
 * In all cases an explicit `suggested_parent` overrides the fallback.
 */
export function newLedgerDisplay(entry: VoucherEntry): { name: string; parent: string } {
  if (PARTY_VOUCHER_TYPES.includes(entry.voucher_type)) {
    const name = entry.party_ledger || entry.party_name || "";
    const fallback =
      entry.voucher_type === "Sales" || entry.voucher_type === "Credit Note"
        ? "Sundry Debtors"
        : "Sundry Creditors";
    return { name, parent: entry.suggested_parent || fallback };
  }
  return {
    name: entry.debit_ledger,
    parent: entry.suggested_parent || "Indirect Expenses",
  };
}
