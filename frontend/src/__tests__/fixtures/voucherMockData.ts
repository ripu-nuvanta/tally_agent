import type { VoucherEntry } from "../../components/VoucherReviewCard";

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
  // Backend/orchestrator convention: Debit Note → party on CREDIT,
  // purchase-returns ledger on DEBIT.
  debit_ledger: "Purchase Returns",
  credit_ledger: "Acme Supplies",
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
  // Backend/orchestrator convention: Credit Note → party on DEBIT,
  // sales-returns ledger on CREDIT.
  debit_ledger: "Globex Ltd",
  credit_ledger: "Sales Returns",
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
