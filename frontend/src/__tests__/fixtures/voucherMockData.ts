import type { VoucherEntry, LineItem } from "../../components/VoucherReviewCard";

// Base entry — INR Payment (back-compat shape)
export const paymentINR: VoucherEntry = {
  id: "v-payment-inr",
  voucher_type: "Payment",
  date: "20260404",
  vendor_name: "Uber",
  amount: 500,
  debit_ledger: "Travel Expenses",
  credit_ledger: "Cash",
  narration: "Uber — Ride",
  gst_entries: [],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

export const purchaseINR: VoucherEntry = {
  id: "v-purchase-inr",
  voucher_type: "Purchase",
  date: "20260410",
  vendor_name: "Acme Supplies",
  party_name: "Acme Supplies",
  party_ledger: "Acme Supplies",
  is_party_ledger: true,
  amount: 11800,
  debit_ledger: "Purchase Accounts",
  credit_ledger: "Acme Supplies",
  narration: "Purchase — Acme Supplies",
  reference: "PINV-FLOW-01",
  reference_date: "20260410",
  bill_reference: "INV-2025",
  bill_type: "New Ref",
  gst_entries: [
    { ledger: "INPUT CGST", amount: 900 },
    { ledger: "INPUT SGST", amount: 900 },
  ],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

// Duplicate-state entry — write must be hard-blocked, red banner shown.
export const purchaseDuplicate: VoucherEntry = {
  ...purchaseINR,
  id: "v-purchase-duplicate",
  reference: "PINV-FLOW-01",
  status: "duplicate",
  duplicate_of: {
    voucher_no: "12",
    date: "20260410",
    reason: "same invoice no for party",
  },
};

export const purchaseUSD: VoucherEntry = {
  ...purchaseINR,
  id: "v-purchase-usd",
  amount: 8350,
  original_currency: "USD",
  original_amount: 100,
  fx_rate: 83.5,
  narration: "Purchase — Acme Supplies (USD)",
};

export const salesINR: VoucherEntry = {
  id: "v-sales-inr",
  voucher_type: "Sales",
  date: "20260412",
  vendor_name: "Globex Ltd",
  party_name: "Globex Ltd",
  party_ledger: "Globex Ltd",
  is_party_ledger: true,
  amount: 23600,
  debit_ledger: "Globex Ltd",
  credit_ledger: "Sales Accounts",
  narration: "Sales — Globex Ltd",
  bill_reference: "SI-1001",
  bill_type: "New Ref",
  gst_entries: [
    { ledger: "OUTPUT CGST", amount: 1800 },
    { ledger: "OUTPUT SGST", amount: 1800 },
  ],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

export const debitNoteINR: VoucherEntry = {
  id: "v-dn-inr",
  voucher_type: "Debit Note",
  date: "20260414",
  vendor_name: "Acme Supplies",
  party_name: "Acme Supplies",
  party_ledger: "Acme Supplies",
  is_party_ledger: true,
  amount: 2360,
  // Correct convention (purchase return): Debit Note → party on DEBIT,
  // purchase-returns ledger on CREDIT (reduces the payable).
  debit_ledger: "Acme Supplies",
  credit_ledger: "Purchase Returns",
  narration: "Debit Note — Acme Supplies",
  bill_reference: "INV-2025",
  bill_type: "Agst Ref",
  against_invoice_options: [
    { voucher_number: "INV-2025", date: "20260410", amount: 11800, reference: "INV-2025" },
    { voucher_number: "INV-2030", date: "20260411", amount: 5900, reference: "INV-2030" },
  ],
  gst_entries: [],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

export const creditNoteINR: VoucherEntry = {
  id: "v-cn-inr",
  voucher_type: "Credit Note",
  date: "20260416",
  vendor_name: "Globex Ltd",
  party_name: "Globex Ltd",
  party_ledger: "Globex Ltd",
  is_party_ledger: true,
  amount: 1180,
  // Correct convention (sales return): Credit Note → party on CREDIT,
  // sales-returns ledger on DEBIT (reduces the receivable).
  debit_ledger: "Sales Returns",
  credit_ledger: "Globex Ltd",
  narration: "Credit Note — Globex Ltd",
  bill_reference: "SI-1001",
  bill_type: "Agst Ref",
  against_invoice_options: [
    { voucher_number: "SI-1001", date: "20260412", amount: 23600, reference: "SI-1001" },
  ],
  gst_entries: [],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
};

// --- Invoice-entry Phase 2 (inventory line items) ---

export const availableStockItems = [
  "A4 Paper Ream",
  "Stapler",
  "Wireless Mouse",
  "USB Cable",
];

// A matched line resolves to an existing stock item; a create_new line carries
// a brand-new stock_name/unit/group/gst_rate.
export const lineItemMatched: LineItem = {
  description: "A4 Paper Ream 500 sheets",
  qty: 10,
  rate: 250,
  unit: "Nos",
  gst_rate: 18,
  amount: 2500,
  matched_item: "A4 Paper Ream",
  create_new: false,
  stock_name: "A4 Paper Ream 500 sheets",
  stock_group: "Office Supplies",
  hsn: "4802",
  ledger: "Purchase Accounts",
};

export const lineItemNew: LineItem = {
  description: "Ergonomic Chair",
  qty: 2,
  rate: 4500,
  unit: "Nos",
  gst_rate: 18,
  amount: 9000,
  matched_item: null,
  create_new: true,
  stock_name: "Ergonomic Chair",
  stock_group: "Office Supplies",
  hsn: "9401",
  ledger: "Purchase Accounts",
};

// Goods Purchase with 2 line items (one matched, one new). amount = lines + GST
// (11500 base + 2070 GST = 13570) — backend-derived, left on the entry.
export const purchaseInventory: VoucherEntry = {
  id: "v-purchase-inventory",
  voucher_type: "Purchase",
  date: "20260410",
  vendor_name: "Acme Supplies",
  party_name: "Acme Supplies",
  party_ledger: "Acme Supplies",
  is_party_ledger: true,
  amount: 13570,
  debit_ledger: "Purchase Accounts",
  credit_ledger: "Acme Supplies",
  narration: "Purchase — Acme Supplies",
  reference: "PINV-INV-01",
  reference_date: "20260410",
  bill_reference: "PINV-INV-01",
  bill_type: "New Ref",
  gst_entries: [
    { ledger: "INPUT CGST", amount: 1035 },
    { ledger: "INPUT SGST", amount: 1035 },
  ],
  status: "draft",
  warnings: [],
  is_new_ledger: false,
  suggested_parent: null,
  is_inventory: true,
  line_items: [lineItemMatched, lineItemNew],
  available_stock_items: availableStockItems,
  default_stock_group: "Office Supplies",
};

// Duplicate inventory entry — write must be hard-blocked, line table read-only.
export const purchaseInventoryDuplicate: VoucherEntry = {
  ...purchaseInventory,
  id: "v-purchase-inventory-duplicate",
  status: "duplicate",
  duplicate_of: {
    voucher_no: "12",
    date: "20260410",
    reason: "same invoice no for party",
  },
};

export const availableLedgers = [
  "Travel Expenses",
  "Office Supplies",
  "Purchase Accounts",
  "Sales Accounts",
  "Purchase Returns",
  "Sales Returns",
];
export const availablePaymentLedgers = ["Cash", "Bank Account"];
export const availableSupplierLedgers = ["Acme Supplies", "Beta Traders"];
export const availableCustomerLedgers = ["Globex Ltd", "Initech"];
