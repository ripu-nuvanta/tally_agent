"""Probe companies (S0 spec §4). One company is open in Tally at a time."""

COMPANIES: dict[str, str] = {
    "A": "Bharat Traders Probe Copy",
    "B": "Sharma & Sons' Probe Traders",
    "C": "Probe Vault Co",
}
SEED_COMPANY = "Bharat Traders Private Limited"
SEED_BACKUP = "seed_data/TDBK1800_100003.001"

# Throwaway objects on company A (S0 spec §4.2, §5.8). Educational mode accepts voucher dates on the 1st, 2nd or 31st
# of a month only (live 2026-09-22), so every throwaway voucher is dated 31-Mar-2026, inside A's books period.
THROWAWAY_DATE = "20260331"
THROWAWAY_DATE_TEXT = "31-Mar-2026"
THROWAWAY_EXPENSE_LEDGER = "Electricity"   # company A has no "Bank Charges"; this is its first Indirect Expenses ledger
