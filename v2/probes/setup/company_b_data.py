"""Company B's dataset (S0 spec §4.3). Pure and offline: no Tally, no I/O.

Company B is the messy-shapes company: custom creditor sub-groups, a non-bill-wise debtor, a Hindi-named
debtor, a compound unit, a zero-rated USD export, cancelled and optional vouchers. Tasks 2, 5 and 6 build
on this module's `Dataset` to compute expected figures, drive the loader, and probe against live Tally.
"""
from __future__ import annotations

import random
from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

SEED = 20260923
COMPANY_B_BOOKS_FROM = date(2022, 4, 1)
COMPANY_B_LAST_MONTH = date(2026, 3, 1)
TAG_PREFIX = "S0-B"
VOUCHERS_PER_MONTH = 20

NON_BILLWISE_DEBTOR = "Kolhapur Retail Mart"     # LESSONS §15 r16 — never assert this one in a bills report
USD_DEBTOR = "Gulf Office Supplies LLC"
HINDI_DEBTOR = "शर्मा ट्रेडर्स"
COMPOUND_UNIT = "Box of 10 Nos"
BASE_UNIT = "Nos"
SALES_GST_VOUCHER_TYPE = "Sales - GST"           # created in the Tally UI, never by the loader

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Fixed-tag specials (S0 spec §4.3): tags land wherever they naturally fall in the calendar (always a sales
# slot, see the loop below) and are overridden in place, so the surrounding month's shape stays untouched.
_USD_TAGS = (101, 102)
_CANCELLED_TAGS = (201, 202)
_OPTIONAL_TAGS = (301, 302)


@dataclass(frozen=True)
class GroupSpec:
    name: str
    parent: str


@dataclass(frozen=True)
class UnitSpec:
    name: str
    base: str | None
    conversion: int | None


@dataclass(frozen=True)
class StockItemSpec:
    name: str
    unit: str
    hsn: str | None
    opening_qty: Decimal | None
    opening_rate: Decimal | None


@dataclass(frozen=True)
class LedgerSpec:
    name: str
    parent: str
    bill_wise: bool
    opening: Decimal | None
    gstin: str | None
    opening_bill: str | None


@dataclass(frozen=True)
class LineSpec:
    ledger: str
    amount: Decimal
    deemed_positive: bool


@dataclass(frozen=True)
class InventorySpec:
    item: str
    qty: Decimal
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class BillSpec:
    name: str
    bill_type: str
    amount: Decimal
    credit_period: str | None


@dataclass(frozen=True)
class VoucherSpec:
    tag: int
    kind: str
    vch_type: str
    date: date
    party: str
    narration: str
    lines: tuple[LineSpec, ...]
    inventory: tuple[InventorySpec, ...]
    bills: tuple[BillSpec, ...]
    cancelled: bool = False
    optional: bool = False
    currency: str = "INR"
    fx_amount: Decimal | None = None


@dataclass(frozen=True)
class Dataset:
    groups: tuple[GroupSpec, ...]
    units: tuple[UnitSpec, ...]
    items: tuple[StockItemSpec, ...]
    ledgers: tuple[LedgerSpec, ...]
    vouchers: tuple[VoucherSpec, ...]
    licence: str


@dataclass(frozen=True)
class Expected:
    ledger_month_end: dict[tuple[str, date], Decimal]   # (ledger, last day of month) -> balance
    ledger_fy_opening: dict[tuple[str, date], Decimal]  # (ledger, 1 April) -> balance
    voucher_count_by_month: dict[tuple[int, int], int]
    voucher_count_by_fy: dict[str, int]                 # "2022-23" -> n


def gstin(state_code: str, pan: str) -> str:
    """A GSTIN with a correct check digit, so Tally's format validation can't reject it."""
    body = f"{state_code}{pan}1Z"
    total = 0
    for i, ch in enumerate(body):
        value = _GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += value // 36 + value % 36
    return body + _GSTIN_CHARS[(36 - total % 36) % 36]


def _educational_days(year: int, month: int) -> tuple[int, ...]:
    """Educational Tally accepts the 1st, 2nd and 31st only (live 2026-09-22, see companies.py)."""
    return (1, 2, 31) if monthrange(year, month)[1] == 31 else (1, 2)


def _months() -> list[tuple[int, int]]:
    out, y, m = [], COMPANY_B_BOOKS_FROM.year, COMPANY_B_BOOKS_FROM.month
    while (y, m) <= (COMPANY_B_LAST_MONTH.year, COMPANY_B_LAST_MONTH.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _gst(goods: Decimal) -> tuple[Decimal, Decimal]:
    half = (goods * Decimal("0.09")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return half, half


def _groups() -> tuple[GroupSpec, ...]:
    return (
        GroupSpec(name="National Creditors", parent="Sundry Creditors"),
        GroupSpec(name="Local Creditors", parent="Sundry Creditors"),
    )


def _units() -> tuple[UnitSpec, ...]:
    return (
        UnitSpec(name=BASE_UNIT, base=None, conversion=None),
        UnitSpec(name=COMPOUND_UNIT, base=BASE_UNIT, conversion=10),
    )


def _items() -> tuple[StockItemSpec, ...]:
    return (
        StockItemSpec(name="USB Cable Type-C", unit=BASE_UNIT, hsn="8544",
                       opening_qty=Decimal("120"), opening_rate=Decimal("85.00")),
        StockItemSpec(name="Wireless Mouse", unit=BASE_UNIT, hsn="8471",
                       opening_qty=None, opening_rate=None),
        StockItemSpec(name="A4 Paper Ream", unit=COMPOUND_UNIT, hsn="4802",
                       opening_qty=Decimal("15"), opening_rate=Decimal("950.00")),
        StockItemSpec(name="Office Stapler", unit=BASE_UNIT, hsn=None,
                       opening_qty=None, opening_rate=None),
        StockItemSpec(name="Whiteboard Marker Set", unit=BASE_UNIT, hsn="9608",
                       opening_qty=None, opening_rate=None),
    )


def _ledgers() -> tuple[LedgerSpec, ...]:
    debtors = (
        LedgerSpec(name=NON_BILLWISE_DEBTOR, parent="Sundry Debtors", bill_wise=False,
                   opening=Decimal("-45000.00"), gstin=None, opening_bill=None),
        LedgerSpec(name=USD_DEBTOR, parent="Sundry Debtors", bill_wise=True,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name=HINDI_DEBTOR, parent="Sundry Debtors", bill_wise=True,
                   opening=None, gstin=gstin("27", "AABCS1234D"), opening_bill=None),
        LedgerSpec(name="Nagpur Wholesale Traders", parent="Sundry Debtors", bill_wise=True,
                   opening=None, gstin=gstin("27", "AAECN5678E"), opening_bill=None),
        LedgerSpec(name="Pune Digital Solutions", parent="Sundry Debtors", bill_wise=True,
                   opening=Decimal("-62500.00"), gstin=gstin("27", "AAFCP4321F"),
                   opening_bill="Op/2022-001"),
        LedgerSpec(name="Indore Home Needs", parent="Sundry Debtors", bill_wise=True,
                   opening=None, gstin=None, opening_bill=None),
    )
    creditors = (
        LedgerSpec(name="Delhi Metal Traders", parent="National Creditors", bill_wise=True,
                   opening=None, gstin=gstin("07", "AAACD1234E"), opening_bill=None),
        LedgerSpec(name="Chennai Components Ltd", parent="National Creditors", bill_wise=True,
                   opening=None, gstin=gstin("33", "AABCC5678F"), opening_bill=None),
        LedgerSpec(name="Kolhapur Hardware Suppliers", parent="Local Creditors", bill_wise=True,
                   opening=None, gstin=gstin("27", "AAFHK4321G"), opening_bill=None),
        LedgerSpec(name="Satara Packaging Co", parent="Local Creditors", bill_wise=True,
                   opening=None, gstin=None, opening_bill=None),
    )
    other = (
        # The balancing figure of the opening trial balance (capital introduced minus everything else already
        # committed elsewhere — debtors + opening stock — sits in the bank): -45000 (Kolhapur) - 62500 (Pune
        # Digital Solutions) - 24450 (opening stock: 120 USB Cable Type-C @ 85 + 15 A4 Paper Ream @ 950) -
        # 868050 (this ledger) + 1000000 (Capital Account) == 0.00 (F9; test_opening_balances_net_to_zero).
        LedgerSpec(name="HDFC Bank Current A/c", parent="Bank Accounts", bill_wise=False,
                   opening=Decimal("-868050.00"), gstin=None, opening_bill=None),
        LedgerSpec(name="Cash", parent="Cash-in-Hand", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Domestic Sales", parent="Sales Accounts", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Export Sales", parent="Sales Accounts", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Local Purchases", parent="Purchase Accounts", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Freight & Forwarding", parent="Indirect Expenses", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Office Rent", parent="Indirect Expenses", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Bank Charges", parent="Indirect Expenses", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Input CGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Input SGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Input IGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Output CGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Output SGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Output IGST", parent="Duties & Taxes", bill_wise=False,
                   opening=None, gstin=None, opening_bill=None),
        LedgerSpec(name="Capital Account", parent="Capital Account", bill_wise=False,
                   opening=Decimal("1000000.00"), gstin=None, opening_bill=None),
    )
    return debtors + creditors + other


def _build_sales(rng: random.Random, tag: int, d: date, party: str, vch_type: str,
                  item_names: list[str], item_rate_hint: dict[str, int],
                  bill_wise: dict[str, bool]) -> VoucherSpec:
    item_name = item_names[tag % len(item_names)]
    qty = Decimal(rng.randint(1, 20))
    rate = Decimal(rng.randint(*item_rate_hint[item_name])) / 100
    goods = (qty * rate).quantize(Decimal("0.01"))
    cgst, sgst = _gst(goods)
    party_amount = goods + cgst + sgst
    lines = (
        LineSpec(ledger=party, amount=party_amount, deemed_positive=True),
        LineSpec(ledger="Domestic Sales", amount=-goods, deemed_positive=False),
        LineSpec(ledger="Output CGST", amount=-cgst, deemed_positive=False),
        LineSpec(ledger="Output SGST", amount=-sgst, deemed_positive=False),
    )
    inventory = (InventorySpec(item=item_name, qty=qty, rate=rate, amount=goods),)
    bills = (BillSpec(name=f"Inv/{tag}", bill_type="New Ref", amount=party_amount,
                       credit_period="30 Days"),) if bill_wise.get(party, False) else ()
    narration = f"[{TAG_PREFIX}:{tag}] Sale to {party}"
    return VoucherSpec(tag=tag, kind="sales", vch_type=vch_type, date=d, party=party, narration=narration,
                        lines=lines, inventory=inventory, bills=bills)


def _build_usd_sale(rng: random.Random, tag: int, d: date) -> VoucherSpec:
    """The zero-rated export sale: party + sales only, no GST lines (S0 spec §4.3)."""
    qty = Decimal(rng.randint(5, 50))
    rate_usd = Decimal(rng.randint(500, 5000)) / 100
    fx_amount = (qty * rate_usd).quantize(Decimal("0.01"))
    fx_rate = Decimal(rng.randint(8000, 8500)) / 100
    inr_amount = (fx_amount * fx_rate).quantize(Decimal("0.01"))
    lines = (
        LineSpec(ledger=USD_DEBTOR, amount=inr_amount, deemed_positive=True),
        LineSpec(ledger="Export Sales", amount=-inr_amount, deemed_positive=False),
    )
    narration = f"[{TAG_PREFIX}:{tag}] Export sale to {USD_DEBTOR}"
    return VoucherSpec(tag=tag, kind="sales", vch_type="Sales", date=d, party=USD_DEBTOR, narration=narration,
                        lines=lines, inventory=(), bills=(), currency="USD", fx_amount=fx_amount)


def _build_purchase(rng: random.Random, tag: int, d: date, party: str,
                     bill_wise: dict[str, bool]) -> VoucherSpec:
    goods = Decimal(rng.randint(1000000, 8000000)) / 100
    cgst, sgst = _gst(goods)
    creditor_amount = goods + cgst + sgst
    lines = (
        LineSpec(ledger="Local Purchases", amount=goods, deemed_positive=True),
        LineSpec(ledger="Input CGST", amount=cgst, deemed_positive=True),
        LineSpec(ledger="Input SGST", amount=sgst, deemed_positive=True),
        LineSpec(ledger=party, amount=-creditor_amount, deemed_positive=False),
    )
    bills = (BillSpec(name=f"Pur/{tag}", bill_type="New Ref", amount=creditor_amount,
                       credit_period="45 Days"),) if bill_wise.get(party, False) else ()
    narration = f"[{TAG_PREFIX}:{tag}] Purchase from {party}"
    return VoucherSpec(tag=tag, kind="purchase", vch_type="Purchase", date=d, party=party, narration=narration,
                        lines=lines, inventory=(), bills=bills)


def _build_receipt(rng: random.Random, tag: int, d: date, party: str,
                    bill_wise: dict[str, bool]) -> VoucherSpec:
    amount = Decimal(rng.randint(500000, 5000000)) / 100
    bank_or_cash = "HDFC Bank Current A/c" if tag % 3 else "Cash"
    lines = (
        LineSpec(ledger=bank_or_cash, amount=amount, deemed_positive=True),
        LineSpec(ledger=party, amount=-amount, deemed_positive=False),
    )
    bills = (BillSpec(name=f"Inv/{tag}", bill_type="Agst Ref", amount=amount,
                       credit_period=None),) if bill_wise.get(party, False) else ()
    narration = f"[{TAG_PREFIX}:{tag}] Receipt from {party}"
    return VoucherSpec(tag=tag, kind="receipt", vch_type="Receipt", date=d, party=party, narration=narration,
                        lines=lines, inventory=(), bills=bills)


def _build_payment(rng: random.Random, tag: int, d: date, party: str,
                    bill_wise: dict[str, bool]) -> VoucherSpec:
    amount = Decimal(rng.randint(500000, 4000000)) / 100
    bank_or_cash = "HDFC Bank Current A/c" if tag % 2 else "Cash"
    lines = (
        LineSpec(ledger=party, amount=amount, deemed_positive=True),
        LineSpec(ledger=bank_or_cash, amount=-amount, deemed_positive=False),
    )
    bills = (BillSpec(name=f"Pur/{tag}", bill_type="Agst Ref", amount=amount,
                       credit_period=None),) if bill_wise.get(party, False) else ()
    narration = f"[{TAG_PREFIX}:{tag}] Payment to {party}"
    return VoucherSpec(tag=tag, kind="payment", vch_type="Payment", date=d, party=party, narration=narration,
                        lines=lines, inventory=(), bills=bills)


def _build_expense_payment(rng: random.Random, tag: int, d: date) -> VoucherSpec:
    expense = "Office Rent" if tag % 2 else "Bank Charges"
    amount = Decimal(rng.randint(100000, 800000)) / 100
    lines = (
        LineSpec(ledger=expense, amount=amount, deemed_positive=True),
        LineSpec(ledger="HDFC Bank Current A/c", amount=-amount, deemed_positive=False),
    )
    narration = f"[{TAG_PREFIX}:{tag}] Payment for {expense}"
    return VoucherSpec(tag=tag, kind="payment", vch_type="Payment", date=d, party=expense, narration=narration,
                        lines=lines, inventory=(), bills=())


def _vouchers(licence: str, rng: random.Random, ledgers: tuple[LedgerSpec, ...],
              items: tuple[StockItemSpec, ...]) -> tuple[VoucherSpec, ...]:
    bill_wise = {l.name: l.bill_wise for l in ledgers}
    debtor_names = [l.name for l in ledgers if l.parent == "Sundry Debtors"]
    creditor_names = [l.name for l in ledgers if l.parent in ("National Creditors", "Local Creditors")]
    item_names = [i.name for i in items]
    item_rate_hint = {i.name: (5000, 200000) for i in items}  # 50.00-2000.00 rupees, in paise

    vouchers: list[VoucherSpec] = []
    tag = 0
    sales_counter = 0
    for (y, m) in _months():
        for i in range(VOUCHERS_PER_MONTH):
            tag += 1
            if licence == "educational":
                allowed = _educational_days(y, m)
                day = allowed[i % len(allowed)]
            else:
                day = 2 + (i * 3) % 26
            d = date(y, m, day)

            if tag in _USD_TAGS:
                v = _build_usd_sale(rng, tag, d)
            elif i < 8:
                sales_counter += 1
                vch_type = SALES_GST_VOUCHER_TYPE if sales_counter % 4 == 0 else "Sales"
                party = HINDI_DEBTOR if sales_counter % 7 == 0 else debtor_names[sales_counter % len(debtor_names)]
                v = _build_sales(rng, tag, d, party, vch_type, item_names, item_rate_hint, bill_wise)
            elif i < 13:
                party = creditor_names[(tag + i) % len(creditor_names)]
                v = _build_purchase(rng, tag, d, party, bill_wise)
            elif i < 17:
                party = debtor_names[(tag + i) % len(debtor_names)]
                v = _build_receipt(rng, tag, d, party, bill_wise)
            elif i < 19:
                party = creditor_names[(tag + i) % len(creditor_names)]
                v = _build_payment(rng, tag, d, party, bill_wise)
            else:
                v = _build_expense_payment(rng, tag, d)

            if tag in _CANCELLED_TAGS:
                v = replace(v, cancelled=True)
            elif tag in _OPTIONAL_TAGS:
                v = replace(v, optional=True)

            vouchers.append(v)
    return tuple(vouchers)


def fy_label(day: date) -> str:
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def expected_figures(dataset: Dataset) -> Expected:
    """Balances and counts computed from the dataset alone — the anchor probes 16/18 check Tally against."""
    running: dict[str, Decimal] = {l.name: (l.opening or Decimal("0.00")) for l in dataset.ledgers}
    month_end: dict[tuple[str, date], Decimal] = {}
    fy_opening: dict[tuple[str, date], Decimal] = {}
    by_month: dict[tuple[int, int], int] = {}
    by_fy: dict[str, int] = {}
    for (year, month) in _months():
        last = date(year, month, monthrange(year, month)[1])
        if month == 4:
            for name, value in running.items():
                fy_opening[(name, date(year, 4, 1))] = value
        for v in sorted(dataset.vouchers, key=lambda v: (v.date, v.tag)):
            if (v.date.year, v.date.month) != (year, month):
                continue
            by_month[(year, month)] = by_month.get((year, month), 0) + 1
            by_fy[fy_label(v.date)] = by_fy.get(fy_label(v.date), 0) + 1
            if v.cancelled:                      # counted, but moves nothing
                continue
            for line in v.lines:
                running[line.ledger] = running.get(line.ledger, Decimal("0.00")) + line.amount
        for name, value in running.items():
            month_end[(name, last)] = value
    return Expected(month_end, fy_opening, by_month, by_fy)


def generate(licence: str = "licensed") -> Dataset:
    rng = random.Random(SEED)
    groups = _groups()
    units = _units()
    items = _items()
    ledgers = _ledgers()
    vouchers = _vouchers(licence, rng, ledgers, items)
    return Dataset(groups=groups, units=units, items=items, ledgers=ledgers, vouchers=vouchers, licence=licence)
