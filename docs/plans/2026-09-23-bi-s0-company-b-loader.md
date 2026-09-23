# Company B Loader (`setup-b`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `python -m v2.probes setup-b`, which loads probe company B ("Sharma & Sons' Probe Traders") from a deterministic dataset that also exports its own expected figures, so probes 21, 5, 11, 14, 15, 22 and the B parts of 3, 16, 18, 23, 25 have a company to run against.

**Architecture:** Two new modules under `v2/probes/setup/`. `company_b_data.py` is pure and offline: a seeded generator that produces the masters, the 960-voucher calendar and — computed independently in Python, never read back from Tally — the expected per-ledger month-end balances, FY openings and voucher counts. `company_b.py` is the loader: it lists what already exists, creates only what is missing, reads back every write, turns anything Tally won't accept over XML into a pause step, and finishes by checking Tally's figures against the generator's expectations. New write shapes go on the existing `TallyWriter` so they inherit `check_writable` + read-back. The CLI gains a `setup-b` branch mirroring `reset-a`.

**Tech Stack:** Python 3.12, `httpx` (the only runtime dep), `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`). No new dependencies.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md) — §4.3 (company B), §4.5 (guards), §4.6 (licence mode), §5.2/§5.6/§5.7 (context, capture, results), §5.3 (CLI), §6 (run order), §11.4 (the nine loader test cases), §12 (risks).
**Also binding:** [`LESSONS.md`](../../LESSONS.md) §15 and [`docs/tally-write-exploration-v4.md`](../tally-write-exploration-v4.md) (the only verified write shapes).

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Isolation.** All code under `v2/`. No import whose top-level module is `backend`, `scripts` or `tests` (`v2/tests/test_isolation.py` enforces this). `v2/agent/` must never import `v2.probes`. Nothing outside `v2/` and `docs/` changes.
- **Money is `Decimal`, built from int paise. No float anywhere.** The copied `amounts.parse_decimal` exists precisely because the current `parse_amount` returns `0.0` on failure.
- **Determinism.** `random.Random(20260923)` instantiated inside the generator. Never module-level state, never bare `random.*` — call order would then change the data.
- **LESSONS §15 rule 10 — never send a CREATE for a master that already exists.** A duplicate create raises a blocking modal that freezes the HTTP gateway; the first write times out and everything after it hangs until the modal is dismissed. List first, create only what is missing. This is the single most important rule in this plan.
- **Rule 11.** `created=0, altered=1, errors=0` on a master create means "already exists" and is a **success**, not a failure.
- **Rule 12.** A stock item with `GSTAPPLICABLE=Applicable` and no HSN raises a mandatory modal. Items without an HSN are created `Not Applicable`; the voucher's explicit GST ledger lines still post GST.
- **Rule 13.** Never create a stock group named `Primary` — it is reserved and can modal.
- **Rule 14.** F2 (working date) must be ≥ the latest voucher date before any voucher is written, or vouchers are silently dropped.
- **Rule 15.** Goods invoices go through the stock grid (`ALLINVENTORYENTRIES.LIST` with qty/rate). Never the ledger path with explicit GST legs — Tally re-computes the bill and stores a different amount.
- **Rule 16.** `bills_receivable` / `bills_payable` only return parties maintained bill-by-bill. The dataset contains one deliberately non-bill-wise debtor; **no assertion may ever expect it in a bills report.**
- **D5 — never send a UNIT delete.** `<UNIT NAME="X" ACTION="Delete">` crashed Tally with an MAV. The loader creates units and never deletes one.
- **Sign convention** — copied verbatim from `docs/tally-write-exploration-v4.md` Op 7. The docs' implied "AMOUNT is absolute, sign comes from ISDEEMEDPOSITIVE" rule is **wrong** and returns `EXCEPTIONS=1`:

  | Block | Sales | Purchase |
  |---|---|---|
  | Party | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−total** | `ISDEEMEDPOSITIVE=No`, AMOUNT = **+total** |
  | GST | `ISDEEMEDPOSITIVE=No`, AMOUNT = **+tax** | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−tax** |
  | Inventory + `ACCOUNTINGALLOCATIONS` | `ISDEEMEDPOSITIVE=No`, AMOUNT = **+goods** | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−goods** |

- **Voucher-type config is UI-only (rule 4).** The loader never creates or alters a voucher type. `Sales - GST` is created by the operator in the UI; the loader verifies it exists and pauses if it doesn't.
- **Company-level GST registration is UI-only** (spec §14 left this open). The loader never writes the company's GSTIN. Party ledgers carry a `PARTYGSTIN` whose check digit is computed correctly (Task 1) so Tally's format validation can't reject it.
- **Commands.** Tests: `uv run --project v2 pytest v2/tests -q`. Runner: `uv run --project v2 python -m v2.probes …`.
- **Every write goes through `TallyWriter`**, which calls `check_writable(company)` (refuses any company without "Probe" in the name) and reads back. "Sharma & Sons' Probe Traders" contains "Probe", so no exception like the seed rename is needed.

---

## File Structure

| File | Responsibility |
|---|---|
| `v2/probes/setup/company_b_data.py` *(create)* | Pure, offline. Dataclasses for the dataset; `generate(licence)`; `expected_figures(dataset)`; the GSTIN check-digit helper. No I/O, no httpx import. |
| `v2/probes/setup/company_b.py` *(create)* | The idempotent loader: list → create-missing → read back → pause for what XML can't set → verify against expectations. |
| `v2/probes/setup/writes.py` *(modify)* | New `TallyWriter` methods: master listers, `create_group`, `create_unit`, `create_stock_item`, `create_party_ledger`, `create_sales`, `create_purchase`, `create_receipt`, `create_payment_against`. |
| `v2/probes/operator/config.py` *(modify)* | `company_numbers` gains `"B"`. |
| `v2/probes/operator/auto.py` *(modify)* | `setup_company_b()` method; `open_company` works for B. |
| `v2/probes/__main__.py` *(modify)* | `setup-b` subcommand + `_setup_b()` branch. |
| `v2/tests/probes/fake_books.py` *(modify)* | `FakeBooks` branches for GROUP / UNIT / STOCKITEM / party-ledger / the new collection IDs. |
| `v2/tests/probes/test_company_b_data.py` *(create)* | Generator tests (test cases 1–4 of spec §11.4). |
| `v2/tests/probes/test_company_b.py` *(create)* | Loader tests (test cases 5–9 of spec §11.4). |
| `v2/tests/probes/test_setup_writes.py` *(modify)* | Tests for the new writer methods. |
| `v2/tests/probes/test_cli.py` *(modify)* | `setup-b` CLI test. |
| `v2/tests/probes/test_auto_operator.py` *(modify)* | Replace `test_open_company_b_is_not_configured_yet`. |

---

### Task 1: The dataset model and masters (`company_b_data.py`)

**Files:**
- Create: `v2/probes/setup/company_b_data.py`
- Test: `v2/tests/probes/test_company_b_data.py`

**Interfaces:**
- Consumes: nothing (pure module — it must not import `httpx` or anything under `v2/agent/`).
- Produces, for Tasks 2, 5, 6:
  ```python
  SEED = 20260923
  COMPANY_B_BOOKS_FROM = date(2022, 4, 1)
  COMPANY_B_LAST_MONTH = date(2026, 3, 1)
  TAG_PREFIX = "S0-B"
  NON_BILLWISE_DEBTOR = "Kolhapur Retail Mart"     # LESSONS §15 r16 — never assert this one in a bills report
  USD_DEBTOR = "Gulf Office Supplies LLC"
  HINDI_DEBTOR = "शर्मा ट्रेडर्स"
  COMPOUND_UNIT = "Box of 10 Nos"
  SALES_GST_VOUCHER_TYPE = "Sales - GST"           # created in the Tally UI, never by the loader

  @dataclass(frozen=True) class GroupSpec:  name: str; parent: str
  @dataclass(frozen=True) class UnitSpec:   name: str; base: str | None; conversion: int | None
  @dataclass(frozen=True) class StockItemSpec: name: str; unit: str; hsn: str | None; opening_qty: Decimal | None; opening_rate: Decimal | None
  @dataclass(frozen=True) class LedgerSpec: name: str; parent: str; bill_wise: bool; opening: Decimal | None; gstin: str | None; opening_bill: str | None
  @dataclass(frozen=True) class LineSpec:   ledger: str; amount: Decimal; deemed_positive: bool
  @dataclass(frozen=True) class InventorySpec: item: str; qty: Decimal; rate: Decimal; amount: Decimal
  @dataclass(frozen=True) class BillSpec:   name: str; bill_type: str; amount: Decimal; credit_period: str | None
  @dataclass(frozen=True) class VoucherSpec:
      tag: int; kind: str; vch_type: str; date: date; party: str; narration: str
      lines: tuple[LineSpec, ...]; inventory: tuple[InventorySpec, ...]; bills: tuple[BillSpec, ...]
      cancelled: bool = False; optional: bool = False; currency: str = "INR"; fx_amount: Decimal | None = None
  @dataclass(frozen=True) class Dataset:
      groups: tuple[GroupSpec, ...]; units: tuple[UnitSpec, ...]; items: tuple[StockItemSpec, ...]
      ledgers: tuple[LedgerSpec, ...]; vouchers: tuple[VoucherSpec, ...]; licence: str

  def gstin(state_code: str, pan: str) -> str
  def generate(licence: str = "licensed") -> Dataset
  ```

- [ ] **Step 1: Write the failing tests**

```python
# v2/tests/probes/test_company_b_data.py
from calendar import monthrange
from datetime import date
from decimal import Decimal

from v2.probes.setup.company_b_data import (
    COMPOUND_UNIT, HINDI_DEBTOR, NON_BILLWISE_DEBTOR, SALES_GST_VOUCHER_TYPE, USD_DEBTOR,
    generate, gstin,
)


def test_the_same_seed_generates_an_identical_dataset():
    assert generate() == generate()          # frozen dataclasses compare by value


def test_every_voucher_balances_to_zero():
    for v in generate().vouchers:
        total = sum((line.amount for line in v.lines), Decimal("0.00"))
        assert total == Decimal("0.00"), f"{v.tag} {v.kind} does not balance: {total}"


def test_the_calendar_covers_four_financial_years_at_twenty_a_month():
    ds = generate()
    assert len(ds.vouchers) == 960
    months = {(v.date.year, v.date.month) for v in ds.vouchers}
    assert len(months) == 48
    assert min(ds.vouchers, key=lambda v: v.date).date >= date(2022, 4, 1)
    assert max(ds.vouchers, key=lambda v: v.date).date <= date(2026, 3, 31)


def test_educational_mode_uses_only_dates_tally_accepts_and_keeps_the_tags_stable():
    licensed, educational = generate(), generate(licence="educational")
    for v in educational.vouchers:
        allowed = {1, 2, 31} if monthrange(v.date.year, v.date.month)[1] == 31 else {1, 2}
        assert v.date.day in allowed
    assert [v.tag for v in licensed.vouchers] == [v.tag for v in educational.vouchers]


def test_the_dataset_carries_the_messy_shapes_the_probes_need():
    ds = generate()
    by_name = {l.name: l for l in ds.ledgers}
    assert by_name[NON_BILLWISE_DEBTOR].bill_wise is False
    assert by_name[HINDI_DEBTOR].bill_wise is True
    assert {g.name for g in ds.groups} >= {"National Creditors", "Local Creditors"}
    assert all(g.parent == "Sundry Creditors" for g in ds.groups)
    assert any(u.name == COMPOUND_UNIT and u.conversion == 10 for u in ds.units)
    assert any(i.unit == COMPOUND_UNIT for i in ds.items)
    assert not any(i.name == "Primary" for i in ds.items)                      # LESSONS §15 r13
    assert all(i.hsn is not None or i.opening_qty is None for i in ds.items)   # r12: no GST item without an HSN


def test_the_non_billwise_debtor_never_gets_a_bill():
    for v in generate().vouchers:
        if v.party == NON_BILLWISE_DEBTOR:
            assert v.bills == ()


def test_the_special_vouchers_sit_on_fixed_tags():
    by_tag = {v.tag: v for v in generate().vouchers}
    assert by_tag[101].currency == "USD" and by_tag[101].fx_amount is not None
    assert by_tag[102].currency == "USD"
    assert by_tag[201].cancelled and by_tag[202].cancelled
    assert by_tag[301].optional and by_tag[302].optional
    assert any(v.vch_type == SALES_GST_VOUCHER_TYPE for v in by_tag.values())
    assert any(HINDI_DEBTOR in v.narration or "शर्मा" in v.narration for v in by_tag.values())


def test_every_narration_carries_its_idempotency_tag():
    for v in generate().vouchers:
        assert v.narration.startswith(f"[S0-B:{v.tag}]")


def test_gstin_check_digit_matches_the_official_algorithm():
    assert gstin("27", "AAAPL1234C") == "27AAAPL1234C1ZV"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.setup.company_b_data'`

- [ ] **Step 3: Implement the module**

Key implementation notes for the engineer:

*Dates.* Licensed days walk the month: `day = 2 + (i * 3) % 26` for the i-th voucher of that month — mid-month, so probe 5's month-bound test has unambiguous edges. Educational days come from `_educational_days(year, month)`, which is `(1, 2, 31)` when the month has 31 days and `(1, 2)` otherwise, cycled by `i`. **The clamp maps dates; it never drops vouchers** — that is what keeps the tags identical between modes.

*Amounts.* Work in int paise, convert once: `Decimal(paise) / 100`. Intra-state GST is 9% CGST + 9% SGST, each `(goods * Decimal("0.09")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`, and the party line is `-(goods + cgst + sgst)` **computed from the rounded parts**, so the voucher balances by construction rather than by luck.

*The two USD export sales* (tags 101, 102) are zero-rated: party + sales only, no GST lines. They carry `currency="USD"` and `fx_amount`; the INR `amount` is what probe 22 will compare against.

```python
"""Company B's dataset and its expected figures (S0 spec §4.3). Pure and offline: no Tally, no I/O.

The expected figures are computed here, in Python, and never read back from Tally — that is the whole
point of the loader. Probes 16 and 18 need an expectation Tally did not produce.
"""
from __future__ import annotations

import random
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

SEED = 20260923
COMPANY_B_BOOKS_FROM = date(2022, 4, 1)
COMPANY_B_LAST_MONTH = date(2026, 3, 1)
TAG_PREFIX = "S0-B"
VOUCHERS_PER_MONTH = 20

NON_BILLWISE_DEBTOR = "Kolhapur Retail Mart"
USD_DEBTOR = "Gulf Office Supplies LLC"
HINDI_DEBTOR = "शर्मा ट्रेडर्स"
COMPOUND_UNIT = "Box of 10 Nos"
BASE_UNIT = "Nos"
SALES_GST_VOUCHER_TYPE = "Sales - GST"

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


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
```

The generator then builds, in this order: `groups` (the two custom creditor sub-groups), `units` (`Nos`, then `Box of 10 Nos` with `base="Nos", conversion=10`), `items` (5, one on the compound unit, HSN only where GST applies), `ledgers` (6 debtors incl. the three named constants, 4 creditors split across the two sub-groups, bank, cash, sales, purchase, 3 expenses, CGST/SGST/IGST input + output, capital; openings on capital/bank/2 debtors; one debtor carrying `opening_bill`), and finally `vouchers` — per month 8 sales, 5 purchases, 4 receipts, 3 payments, tags running 1..960, every narration prefixed `[S0-B:{tag}] `, every 4th sale on `SALES_GST_VOUCHER_TYPE`, every 7th sale with a Hindi narration suffix, and the fixed-tag specials (101/102 USD, 201/202 cancelled, 301/302 optional).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b_data.py -q`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/setup/company_b_data.py v2/tests/probes/test_company_b_data.py
git commit -m "feat(bi/v2): company B dataset generator (deterministic, balances, Educational clamp)"
```

---

### Task 2: Expected figures

**Files:**
- Modify: `v2/probes/setup/company_b_data.py`
- Test: `v2/tests/probes/test_company_b_data.py`

**Interfaces:**
- Consumes: `Dataset`, `VoucherSpec`, `LineSpec` from Task 1.
- Produces, for Tasks 5 and the future probes 16/18/21:
  ```python
  @dataclass(frozen=True)
  class Expected:
      ledger_month_end: dict[tuple[str, date], Decimal]   # (ledger, last day of month) -> balance
      ledger_fy_opening: dict[tuple[str, date], Decimal]  # (ledger, 1 April) -> balance
      voucher_count_by_month: dict[tuple[int, int], int]
      voucher_count_by_fy: dict[str, int]                 # "2022-23" -> n

  def expected_figures(dataset: Dataset) -> Expected
  def fy_label(day: date) -> str                          # "2022-23" for anything from 1 Apr 2022
  ```

- [ ] **Step 1: Write the failing tests**

```python
def test_month_end_balances_equal_openings_plus_the_running_sum():
    ds = generate()
    exp = expected_figures(ds)
    for ledger in ("Sales", "Capital Account", USD_DEBTOR):
        for (name, day), value in exp.ledger_month_end.items():
            if name != ledger:
                continue
            opening = next((l.opening or Decimal("0.00") for l in ds.ledgers if l.name == name), Decimal("0.00"))
            moved = sum((line.amount for v in ds.vouchers if v.date <= day and not v.cancelled
                         for line in v.lines if line.ledger == name), Decimal("0.00"))
            assert value == opening + moved


def test_cancelled_vouchers_do_not_move_a_balance_but_are_still_counted():
    ds = generate()
    exp = expected_figures(ds)
    assert sum(exp.voucher_count_by_month.values()) == len(ds.vouchers)
    assert exp.voucher_count_by_fy["2022-23"] == 240


def test_fy_openings_are_the_previous_month_end():
    ds, exp = generate(), None
    exp = expected_figures(ds)
    assert exp.ledger_fy_opening[("Sales", date(2023, 4, 1))] == exp.ledger_month_end[("Sales", date(2023, 3, 31))]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b_data.py -q -k expected or month_end or fy_opening`
Expected: FAIL — `ImportError: cannot import name 'expected_figures'`

- [ ] **Step 3: Implement**

```python
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
```

Note the FY-opening loop runs **before** the month's vouchers are applied, so a 1-April opening is the previous 31-March close. The test above asserts exactly that.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b_data.py -q`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/setup/company_b_data.py v2/tests/probes/test_company_b_data.py
git commit -m "feat(bi/v2): expected figures for company B, computed independently of Tally"
```

---

### Task 3: Teach `FakeBooks` the new object types

**Files:**
- Modify: `v2/tests/probes/fake_books.py`
- Test: `v2/tests/probes/test_fake_books_masters.py` *(create)*

**Why first:** Tasks 4–6 are TDD against this fake. `FakeBooks._answer` / `_import` today only understand LEDGER, VOUCHER, COMPANY and STOCKGROUP, and route on the collection IDs `S0CompanyCounters`, `S0OpVouchers`, `S0LedgerList`, `S0OpLedger`/`S0OneLedger`. Without new branches the writer tests would pass against a fake that silently accepts anything.

**Interfaces:**
- Consumes: the existing `FakeBooks.state` dict shape and `import_result(...)` helper.
- Produces, for Tasks 4–6: `state["groups"]`, `state["units"]`, `state["items"]` keyed by name; collection IDs `S0BGroups`, `S0BUnits`, `S0BItems`, `S0BLedgers`, `S0BVouchers`; and **the duplicate-create modal for every new type**, not just stock groups.

- [ ] **Step 1: Write the failing tests**

```python
# v2/tests/probes/test_fake_books_masters.py
import httpx
import pytest

from v2.probes.setup.writes import TallyWriter
from v2.tests.probes.fake_books import FakeBooks, sync_client

B = "Sharma & Sons' Probe Traders"


def _writer(books):
    said: list[str] = []
    return TallyWriter(sync_client(books.transport()), said.append), said


def test_creating_a_group_then_listing_it_round_trips():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_group(B, "National Creditors", "Sundry Creditors")
    assert "National Creditors" in writer.list_groups(B)


def test_a_duplicate_create_raises_the_modal_for_every_new_type():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_unit(B, "Nos", base=None, conversion=None)
    with pytest.raises(httpx.ReadTimeout):
        # straight to the transport: the writer's own list-before-create guard is Task 4's job
        sync_client(books.transport()).post("/", content=_unit_create_xml(B, "Nos"), timeout=5)
```

(The helper `_unit_create_xml` is three lines in the test file — build it with `wrap_import("All Masters", B, '<UNIT NAME="Nos" ACTION="Create"><NAME>Nos</NAME></UNIT>')`.)

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_fake_books_masters.py -q`
Expected: FAIL — `AttributeError: 'TallyWriter' object has no attribute 'create_group'` (Task 4 supplies it; here you are proving the fake is the missing half by first adding the fake and watching the *second* test still fail for the right reason).

- [ ] **Step 3: Extend `FakeBooks`**

Add to `seed_state()`: `"groups": {}`, `"units": {}`, `"items": {}`. In `_import`, add an `ACTION="Create"` branch per new tag (`GROUP`, `UNIT`, `STOCKITEM`) that (a) raises `httpx.ReadTimeout` when the name already exists — matching the real modal, LESSONS §15 rule 10 — and (b) otherwise stores the parsed record and returns `import_result(created=1)`. In `_answer`, add collection branches for `S0BGroups` / `S0BUnits` / `S0BItems` / `S0BLedgers` / `S0BVouchers` returning `objects_xml(...)` over the stored state.

- [ ] **Step 4: Run to verify the fake half passes**

Run: `uv run --project v2 pytest v2/tests/probes/test_fake_books_masters.py -q`
Expected: the duplicate-modal test passes; the `create_group` test still fails on the missing writer method (Task 4).

- [ ] **Step 5: Commit**

```bash
git add v2/tests/probes/fake_books.py v2/tests/probes/test_fake_books_masters.py
git commit -m "test(bi/v2): FakeBooks understands groups, units and stock items"
```

---

### Task 4: Master writers on `TallyWriter`

**Files:**
- Modify: `v2/probes/setup/writes.py`
- Test: `v2/tests/probes/test_setup_writes.py`, `v2/tests/probes/test_fake_books_masters.py`

**Interfaces:**
- Consumes: `check_writable`, `wrap_import`, `esc`, `ImportResult`, `wrap_collection`, `formula_string` (all already in the module or imported by it).
- Produces, for Task 6:
  ```python
  def list_groups(self, company: str) -> dict[str, str]        # name -> parent
  def list_units(self, company: str) -> list[str]
  def list_stock_items(self, company: str) -> dict[str, str]   # name -> unit
  def list_ledgers(self, company: str) -> dict[str, str]       # name -> parent
  def list_voucher_types(self, company: str) -> list[str]
  def create_group(self, company: str, name: str, parent: str) -> None
  def create_unit(self, company: str, name: str, *, base: str | None = None, conversion: int | None = None) -> None
  def create_stock_item(self, company: str, name: str, *, unit: str, hsn: str | None = None,
                        opening_qty: Decimal | None = None, opening_rate: Decimal | None = None) -> None
  def create_party_ledger(self, company: str, name: str, *, parent: str, bill_wise: bool,
                          opening: Decimal | None = None, gstin: str | None = None) -> None
  ```

**Every one of these follows the same four-beat shape**, and the tests assert each beat:
1. `check_writable(company)` — inherited by calling it first thing.
2. **List first.** If the name is already there, log `f"{name} already exists — not re-created"` and **return without sending** (LESSONS §15 rule 10). This is the guard that keeps Tally alive.
3. `import_("All Masters", company, inner)`; accept `result.created == 1` **or** `result.altered == 1` with `result.clean` (rule 11 — altered-only means "already exists" and is benign).
4. Read back through the matching `list_*` and raise `WriteFailed` if the name isn't there.

- [ ] **Step 1: Write the failing tests**

```python
# additions to v2/tests/probes/test_setup_writes.py
B = "Sharma & Sons' Probe Traders"


def test_create_group_lists_before_creating_and_reads_back():
    books = FakeBooks(name=B)
    writer, said = _writer(books)
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    assert writer.list_groups(B)["Local Creditors"] == "Sundry Creditors"
    assert len(_imports(books)) == 1


def test_a_second_create_sends_nothing():
    books = FakeBooks(name=B)
    writer, said = _writer(books)
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    writer.create_group(B, "Local Creditors", "Sundry Creditors")
    assert len(_imports(books)) == 1                      # the second call never reached Tally
    assert any("already exists" in line for line in said)


def test_a_compound_unit_carries_its_base_and_conversion():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_unit(B, "Nos")
    writer.create_unit(B, "Box of 10 Nos", base="Nos", conversion=10)
    sent = _imports(books)[-1]
    assert "<BASEUNITS>Nos</BASEUNITS>" in sent and "<CONVERSION>10</CONVERSION>" in sent


def test_a_stock_item_without_an_hsn_is_created_gst_not_applicable():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_stock_item(B, "Whiteboard Marker", unit="Nos")
    sent = _imports(books)[-1]
    assert "<GSTAPPLICABLE>Not Applicable</GSTAPPLICABLE>" in sent    # LESSONS §15 r12
    assert "HSNCODE" not in sent


def test_a_party_ledger_carries_bill_wise_and_a_valid_gstin():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Pune Traders", parent="Local Creditors", bill_wise=True,
                               gstin="27AAAPL1234C1ZV")
    sent = _imports(books)[-1]
    assert "<ISBILLWISEON>Yes</ISBILLWISEON>" in sent
    assert "<PARTYGSTIN>27AAAPL1234C1ZV</PARTYGSTIN>" in sent


def test_the_non_billwise_debtor_is_written_bill_wise_off():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_party_ledger(B, "Kolhapur Retail Mart", parent="Sundry Debtors", bill_wise=False)
    assert "<ISBILLWISEON>No</ISBILLWISEON>" in _imports(books)[-1]


def test_a_write_to_a_company_without_probe_in_the_name_is_refused():
    books = FakeBooks(name="Sharma & Sons Traders")
    writer, _ = _writer(books)
    with pytest.raises(WriteRefused):
        writer.create_group("Sharma & Sons Traders", "Local Creditors", "Sundry Creditors")
    assert _imports(books) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_setup_writes.py -q`
Expected: FAIL — `AttributeError: 'TallyWriter' object has no attribute 'create_group'`

- [ ] **Step 3: Implement the writers**

Constants to add near `LEDGER_FIELDS`:
```python
GROUP_FIELDS = ["Name", "Parent"]
UNIT_FIELDS = ["Name", "BaseUnits", "Conversion"]
ITEM_FIELDS = ["Name", "BaseUnits", "Parent"]
PARTY_LEDGER_FIELDS = ["Name", "Parent", "IsBillWiseOn", "OpeningBalance", "PartyGSTIN"]
VOUCHER_TYPE_FIELDS = ["Name", "Parent"]
```

The XML bodies, all through `wrap_import("All Masters", …)` and all using the shapes verified in
`docs/tally-write-exploration-v4.md` Ops 1, 2, 3 and 5:

```python
# Op 2 — group. NAME.LIST required.
inner = (f'<GROUP NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
         f'  <PARENT>{esc(parent)}</PARENT>\n</GROUP>')

# Op 1 — unit. No NAME.LIST. A compound unit adds BASEUNITS/ADDITIONALUNITS/CONVERSION.
compound = ("" if base is None else
            f"\n  <BASEUNITS>{esc(base)}</BASEUNITS>\n  <ADDITIONALUNITS>{esc(base)}</ADDITIONALUNITS>"
            f"\n  <CONVERSION>{conversion}</CONVERSION>\n  <ISSIMPLEUNIT>No</ISSIMPLEUNIT>")
inner = f'<UNIT NAME="{esc(name)}" ACTION="Create">\n  <NAME>{esc(name)}</NAME>{compound}\n</UNIT>'

# Op 3 — stock item. HSN only when supplied (LESSONS §15 r12).
gst = (f"\n  <GSTAPPLICABLE>Applicable</GSTAPPLICABLE>\n  <HSNDETAILS.LIST><HSNCODE>{esc(hsn)}</HSNCODE></HSNDETAILS.LIST>"
       if hsn else "\n  <GSTAPPLICABLE>Not Applicable</GSTAPPLICABLE>")
opening = ("" if opening_qty is None else
           f"\n  <OPENINGBALANCE>{opening_qty} {esc(unit)}</OPENINGBALANCE>"
           f"\n  <OPENINGRATE>{opening_rate}/{esc(unit)}</OPENINGRATE>"
           f"\n  <OPENINGVALUE>{(opening_qty * opening_rate):.2f}</OPENINGVALUE>")
inner = (f'<STOCKITEM NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
         f'  <BASEUNITS>{esc(unit)}</BASEUNITS>{gst}{opening}\n</STOCKITEM>')

# Op 5 — party ledger with opening balance, GSTIN and state.
extra = "".join(filter(None, [
    f"\n  <OPENINGBALANCE>{opening:.2f}</OPENINGBALANCE>" if opening is not None else "",
    f"\n  <PARTYGSTIN>{esc(gstin)}</PARTYGSTIN>\n  <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>" if gstin else
    "\n  <GSTREGISTRATIONTYPE>Unregistered</GSTREGISTRATIONTYPE>",
]))
inner = (f'<LEDGER NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
         f'  <PARENT>{esc(parent)}</PARENT>\n  <ISBILLWISEON>{"Yes" if bill_wise else "No"}</ISBILLWISEON>'
         f'\n  <LEDSTATENAME>Maharashtra</LEDSTATENAME>{extra}\n</LEDGER>')
```

The listers reuse `wrap_collection` exactly as `ledger()` does today, with the collection IDs Task 3 taught the fake:
```python
def list_groups(self, company: str) -> dict[str, str]:
    xml = wrap_collection("S0BGroups", "Group", GROUP_FIELDS, company)
    return {row["Name"]: row.get("Parent", "") for row in read_objects(self.post(xml), "GROUP", GROUP_FIELDS)}
```

**Do not add a `create_voucher_type`.** Voucher-type writes look successful and don't change behaviour (LESSONS §15 rule 4); `list_voucher_types` exists so the loader can *verify* and pause.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_setup_writes.py v2/tests/probes/test_fake_books_masters.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/setup/writes.py v2/tests/probes/test_setup_writes.py v2/tests/probes/test_fake_books_masters.py
git commit -m "feat(bi/v2): master writers for company B (list-before-create, read-back)"
```

---

### Task 5: Voucher writers with inventory, GST and bill allocations

**Files:**
- Modify: `v2/probes/setup/writes.py`
- Test: `v2/tests/probes/test_setup_writes.py`

**Interfaces:**
- Consumes: `VoucherSpec`, `LineSpec`, `InventorySpec`, `BillSpec` (Task 1) — passed in as plain values, so `writes.py` does **not** import `company_b_data` (keeps the writer reusable and the dependency one-way).
- Produces, for Task 6:
  ```python
  def create_b_voucher(self, company: str, *, vch_type: str, date: str, narration: str, party: str,
                       lines: list[tuple[str, Decimal, bool]],           # (ledger, signed amount, deemed_positive)
                       inventory: list[tuple[str, Decimal, Decimal, Decimal]] = (),  # (item, qty, rate, amount)
                       bills: list[tuple[str, str, Decimal, str | None]] = (),       # (name, type, amount, credit period)
                       optional: bool = False) -> str                    # returns LASTVCHID
  def voucher_by_tag(self, company: str, tag: int) -> dict[str, str] | None
  ```

- [ ] **Step 1: Write the failing tests**

```python
def test_a_sales_voucher_uses_the_verified_sign_convention():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Sales", date="20230601", narration="[S0-B:7] sale", party="Pune Traders",
        lines=[("Pune Traders", Decimal("-11800.00"), True), ("Sales", Decimal("10000.00"), False),
               ("Output CGST", Decimal("900.00"), False), ("Output SGST", Decimal("900.00"), False)],
        inventory=[("A4 Paper", Decimal("10"), Decimal("1000.00"), Decimal("10000.00"))],
        bills=[("B/7", "New Ref", Decimal("-11800.00"), "30 Days")])
    sent = _imports(books)[-1]
    assert "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" in sent          # party
    assert "<AMOUNT>-11800.00</AMOUNT>" in sent
    assert "<ALLINVENTORYENTRIES.LIST>" in sent                         # r15: goods via the stock grid
    assert "<BILLCREDITPERIOD>30 Days</BILLCREDITPERIOD>" in sent


def test_a_purchase_inverts_the_signs():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(
        B, vch_type="Purchase", date="20230601", narration="[S0-B:9] buy", party="Mumbai Supplies",
        lines=[("Mumbai Supplies", Decimal("5900.00"), False), ("Purchase", Decimal("-5000.00"), True),
               ("Input CGST", Decimal("-450.00"), True), ("Input SGST", Decimal("-450.00"), True)])
    sent = _imports(books)[-1]
    party_block = sent.split("<ALLLEDGERENTRIES.LIST>")[1]
    assert "<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>" in party_block
    assert "<AMOUNT>5900.00</AMOUNT>" in party_block


def test_an_unbalanced_voucher_is_refused_before_anything_is_sent():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    with pytest.raises(ValueError, match="does not balance"):
        writer.create_b_voucher(B, vch_type="Sales", date="20230601", narration="[S0-B:1] x", party="P",
                                lines=[("P", Decimal("-100.00"), True), ("Sales", Decimal("90.00"), False)])
    assert _imports(books) == []


def test_a_voucher_is_read_back_by_its_tag():
    books = FakeBooks(name=B)
    writer, _ = _writer(books)
    writer.create_b_voucher(B, vch_type="Receipt", date="20230601", narration="[S0-B:42] got paid",
                            party="Pune Traders",
                            lines=[("Cash", Decimal("1000.00"), False), ("Pune Traders", Decimal("-1000.00"), True)])
    assert writer.voucher_by_tag(B, 42) is not None
    assert writer.voucher_by_tag(B, 43) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_setup_writes.py -q -k voucher`
Expected: FAIL — `AttributeError: 'TallyWriter' object has no attribute 'create_b_voucher'`

- [ ] **Step 3: Implement**

`create_b_voucher` starts with three refusals, all **before** any request:
```python
check_writable(company)
total = sum((amount for _, amount, _ in lines), Decimal("0.00"))
if total != Decimal("0.00"):
    raise ValueError(f"Voucher {narration!r} does not balance: {total}")
if inventory and vch_type not in ("Sales", "Purchase") and not vch_type.startswith("Sales"):
    raise ValueError("Inventory lines belong on Sales/Purchase only")
```
Then it builds `<ALLLEDGERENTRIES.LIST>` per line (`LEDGERNAME`, `ISDEEMEDPOSITIVE`, `AMOUNT` with the sign as given — the caller owns the convention, and the balance check proves it), nests `<BILLALLOCATIONS.LIST>` under the **party** line only (`NAME`, `BILLTYPE`, `AMOUNT`, and `BILLCREDITPERIOD` when supplied), and appends one `<ALLINVENTORYENTRIES.LIST>` per inventory row with `STOCKITEMNAME`, `ACTUALQTY`/`BILLEDQTY` as `f"{qty} {unit}"`, `RATE`, `AMOUNT` and a nested `<ACCOUNTINGALLOCATIONS.LIST>` pointing at the nominal ledger. `ISOPTIONAL` is emitted when `optional=True`.

**Cancelled is not written here.** Tally does not accept `ISCANCELLED` on import reliably; per spec §4.3 that becomes a pause step in Task 6.

`voucher_by_tag` reuses the existing `voucher()` read-back shape with B's own date window and a `$Narration` filter:
```python
xml = voucher_request("S0BVouchers", VOUCHER_FIELDS, company, from_date="01-04-2022", to_date="31-03-2026",
                      extra_collection_xml=VOUCHER_CHILDOF)
return next((v for v in read_objects(self.post(xml), "VOUCHER", VOUCHER_FIELDS)
             if v.get("Narration", "").startswith(f"[S0-B:{tag}]")), None)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_setup_writes.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/setup/writes.py v2/tests/probes/test_setup_writes.py
git commit -m "feat(bi/v2): voucher writer with inventory, GST and bill allocations"
```

---

### Task 6: The loader (`company_b.py`)

**Files:**
- Create: `v2/probes/setup/company_b.py`
- Test: `v2/tests/probes/test_company_b.py`

**Interfaces:**
- Consumes: `generate`, `expected_figures`, every dataclass (Task 1–2); `TallyWriter` incl. the new methods (Tasks 4–5); `check_writable`, `WriteFailed`, `WriteRefused`; `ProbeIO` + `Action` for pause steps.
- Produces, for Task 7:
  ```python
  @dataclass(frozen=True)
  class LoadReport:
      created: dict[str, int]          # "groups" / "units" / "items" / "ledgers" / "vouchers" -> count created
      skipped: dict[str, int]          # already present
      pauses: list[str]                # instructions handed to the operator
      problems: list[str]              # verification failures; empty == success

  class CompanyBLoadError(Exception): ...

  def load_company_b(writer: TallyWriter, io: ProbeIO, *, licence: str = "licensed",
                     company: str = COMPANIES["B"]) -> LoadReport
  ```

**Order of operations** (each stage fully read back before the next begins):
1. **Preflight.** `check_writable(company)`. Verify `Sales - GST` is in `list_voucher_types`; if absent, `io.wait(...)` asking the operator to create it in the UI (rule 4 — never via XML), then re-check and raise `CompanyBLoadError` if it is still missing.
2. **Groups → units → items → ledgers.** For each, diff the dataset against the `list_*` result and create only the missing ones. Units before items (an item names its unit); groups before ledgers (a ledger names its parent).
3. **Opening bill.** The one debtor with `opening_bill` is created with its opening balance, then read back through `bills_receivable` as on `01-04-2022`. If the bill isn't there, this becomes a pause step rather than a failure — the opening-bill shape is not in the verified-ops doc.
4. **F2.** Before any voucher: `io.wait("Set F2 (working date) to 31-03-2026 or later", Action("open_company", ...))` — LESSONS §15 rule 14; vouchers dated past F2 are silently dropped.
5. **Vouchers**, in date order. Skip any tag already present (`voucher_by_tag`). A second run therefore sends **zero** creates.
6. **Flags that don't stick.** After the create, re-read tags 201/202 (cancelled) and 301/302 (optional). Any flag that didn't take becomes a pause step **naming the voucher**, then a re-read.
7. **Verification.** Per-FY voucher counts and the four FY-end ledger balances from `expected_figures`, compared against Tally's own TB. Mismatches go into `LoadReport.problems` — the loader reports, it does not silently pass.

- [ ] **Step 1: Write the failing tests** — these are the nine cases from spec §11.4

```python
# v2/tests/probes/test_company_b.py
import pytest

from v2.probes.companies import COMPANIES
from v2.probes.setup.company_b import CompanyBLoadError, load_company_b
from v2.probes.setup.company_b_data import generate
from v2.probes.setup.writes import TallyWriter, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, sync_client
from v2.tests.probes.fakes import ScriptedIO

B = COMPANIES["B"]


def _loader(books, **io_kwargs):
    said: list[str] = []
    writer = TallyWriter(sync_client(books.transport()), said.append)
    return writer, ScriptedIO(**io_kwargs), said


def _empty_b():
    books = FakeBooks(name=B)
    books.state["voucherTypes"] = ["Sales", "Purchase", "Receipt", "Payment", "Sales - GST"]
    return books


def test_a_first_load_lists_before_creating_and_reads_back_every_write():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    ds = generate()
    assert report.created["groups"] == len(ds.groups)
    assert report.created["vouchers"] == len(ds.vouchers)
    assert report.problems == []
    # the first request for each type is a read, not an import
    first = books.requests[0]
    assert "<TALLYREQUEST>Import Data</TALLYREQUEST>" not in first


def test_a_second_load_sends_zero_creates():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    before = len([r for r in books.requests if "Import Data" in r])
    report = load_company_b(writer, io)
    after = len([r for r in books.requests if "Import Data" in r])
    assert after == before                       # nothing new was sent
    assert sum(report.created.values()) == 0
    assert report.skipped["vouchers"] == 960


def test_a_master_that_already_exists_is_not_recreated():
    books = _empty_b()
    books.state["groups"]["National Creditors"] = {"parent": "Sundry Creditors"}
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert report.skipped["groups"] == 1
    creates = [r for r in books.requests if 'GROUP NAME="National Creditors" ACTION="Create"' in r]
    assert creates == []                         # LESSONS §15 rule 10


def test_a_company_without_probe_in_the_name_is_refused_before_any_request():
    books = FakeBooks(name="Sharma & Sons Traders")
    writer, io, _ = _loader(books)
    with pytest.raises(WriteRefused):
        load_company_b(writer, io, company="Sharma & Sons Traders")
    assert books.requests == []


def test_a_missing_custom_voucher_type_pauses_and_then_fails_if_still_missing():
    books = _empty_b()
    books.state["voucherTypes"] = ["Sales", "Purchase", "Receipt", "Payment"]   # no "Sales - GST"
    writer, io, _ = _loader(books)
    with pytest.raises(CompanyBLoadError, match="Sales - GST"):
        load_company_b(writer, io)
    assert any("Sales - GST" in w for w in io.waits)         # the operator was asked first


def test_a_flag_that_did_not_stick_becomes_a_pause_naming_the_voucher():
    books = _empty_b()
    books.drop_flags = True                      # the fake accepts the voucher but not ISOPTIONAL/ISCANCELLED
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert any("[S0-B:201]" in p for p in report.pauses)
    assert any("[S0-B:301]" in p for p in report.pauses)


def test_the_run_ends_by_checking_counts_and_balances_against_the_expected_figures():
    books = _empty_b()
    writer, io, _ = _loader(books)
    report = load_company_b(writer, io)
    assert report.problems == []


def test_a_wrong_count_is_reported_as_a_problem_not_swallowed():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io)
    books.state["vouchers"].pop()                # something vanished behind our back
    report = load_company_b(writer, io)
    assert any("2025-26" in p or "count" in p.lower() for p in report.problems)


def test_educational_mode_only_uses_dates_tally_accepts():
    books = _empty_b()
    writer, io, _ = _loader(books)
    load_company_b(writer, io, licence="educational")
    dates = [v["date"] for v in books.state["vouchers"].values()]
    assert all(int(d[6:8]) in (1, 2, 31) for d in dates)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.setup.company_b'`

- [ ] **Step 3: Implement the loader**

Skeleton (the engineer fills each stage; every stage follows the same diff-then-create-then-read-back beat):

```python
"""The idempotent company B loader (S0 spec §4.3). Lists first, creates only what's missing, reads back
every write, and turns anything XML can't set into a pause step naming the object."""
from __future__ import annotations

from dataclasses import dataclass, field

from v2.probes.actions import Action
from v2.probes.companies import COMPANIES
from v2.probes.console import ProbeIO
from v2.probes.setup.company_b_data import (SALES_GST_VOUCHER_TYPE, Dataset, expected_figures, generate)
from v2.probes.setup.writes import TallyWriter, WriteFailed, check_writable

F2_INSTRUCTION = ("In TallyPrime press F2 and set the working date to 31-03-2026 or later, then press Enter here. "
                  "Vouchers dated after F2 are silently dropped (LESSONS §15 rule 14).")


class CompanyBLoadError(Exception):
    """The loader can't continue — a prerequisite the operator must fix first."""


@dataclass
class LoadReport:
    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    pauses: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def load_company_b(writer, io, *, licence="licensed", company=COMPANIES["B"]) -> LoadReport:
    check_writable(company)                       # before any request at all
    dataset = generate(licence=licence)
    report = LoadReport()
    _require_voucher_type(writer, io, company, report)
    _load_masters(writer, company, dataset, report)
    _load_openings(writer, io, company, dataset, report)
    io.wait(F2_INSTRUCTION)
    _load_vouchers(writer, company, dataset, report)
    _settle_flags(writer, io, company, dataset, report)
    _verify(writer, company, dataset, report)
    return report
```

`_verify` compares `expected_figures(dataset).voucher_count_by_fy` against a per-FY read and the FY-end balances against Tally's TB, appending one line per mismatch to `report.problems` — it never raises, so the operator sees the whole picture in one run.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_company_b.py -q`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/setup/company_b.py v2/tests/probes/test_company_b.py v2/tests/probes/fake_books.py
git commit -m "feat(bi/v2): idempotent company B loader with pause steps and verification"
```

---

### Task 7: Operator wiring

**Files:**
- Modify: `v2/probes/operator/config.py`, `v2/probes/operator/auto.py`
- Test: `v2/tests/probes/test_auto_operator.py`

**Interfaces:**
- Consumes: `load_company_b`, `LoadReport`, `CompanyBLoadError` (Task 6).
- Produces, for Task 8: `AutoOperator.setup_company_b() -> LoadReport`, and `open_company` working for label `"B"`.

Today `OperatorConfig.company_numbers` is `{"A": "100003"}` and `auto.py:142-143` raises `OperatorError(f"Auto mode can't open company {label} yet: no company number configured (plan part 3)")`. This task is that plan part.

- [ ] **Step 1: Write the failing tests**

```python
def test_company_b_has_a_configured_number(tmp_path):
    assert tmp_config(tmp_path).company_numbers["B"] == "100004"


def test_open_company_b_loads_it(tmp_path):
    op, books, runner, _ = _operator(tmp_path)
    op.wait("Switch Tally to company B", Action("open_company", {"label": "B"}))
    assert books.companies() == [COMPANIES["B"]]


def test_setup_company_b_wraps_write_failures_as_operator_errors(tmp_path):
    op, books, _, _ = _operator(tmp_path)
    books.fail_imports = True
    with pytest.raises(OperatorError, match="setup-b"):
        op.setup_company_b()
```

Replace `test_open_company_b_is_not_configured_yet` — delete it, don't leave it xfail: it asserted the very gap this task closes.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_auto_operator.py -q`
Expected: FAIL — `KeyError: 'B'`

- [ ] **Step 3: Implement**

`config.py`: `company_numbers` default becomes `{"A": "100003", "B": "100004"}`. **`100004` is the number Tally assigns the second company created in the `s0probe` data folder** — the operator must confirm it after creating B in the UI; a mismatch surfaces immediately as "wrong company loaded" from `wait_for_companies`.

`auto.py`: add `setup_company_b` mirroring `reset_company_a` exactly:
```python
def setup_company_b(self) -> LoadReport:
    self.log.write("setup-b: loading company B from the deterministic dataset")
    try:
        return load_company_b(self.writer, self, licence=self.licence)
    except (WriteFailed, WriteRefused, GuardError, CompanyBLoadError) as exc:
        raise OperatorError(f"setup-b: {exc}") from exc
```

**Pause kinds:** the loader's F2 step and its flag steps use plain `io.wait(instruction)` with **no `Action`**, which the `AutoOperator` will reject with "No automated action for this step". That is deliberate and correct — setting F2 and toggling a cancelled flag are UI-only. `setup-b` therefore runs with a person present; it is not an unattended command. Do **not** add new `PAUSE_KINDS` for them (adding one without a matching handler trips the `RuntimeError` guard in `AutoOperator.__init__`).

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests/probes/test_auto_operator.py -q`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add v2/probes/operator/config.py v2/probes/operator/auto.py v2/tests/probes/test_auto_operator.py
git commit -m "feat(bi/v2): operator can open and load company B"
```

---

### Task 8: The `setup-b` command

**Files:**
- Modify: `v2/probes/__main__.py`
- Test: `v2/tests/probes/test_cli.py`

**Interfaces:**
- Consumes: `AutoOperator.setup_company_b` (Task 7), `build_auto_operator`, `OperatorError`.
- Produces: the CLI surface the spec's §5.3 table promises and §6's run order calls for.

- [ ] **Step 1: Write the failing test**

```python
def test_setup_b_loads_company_b_and_reports(tmp_path, capsys):
    config = tmp_config(tmp_path)
    write_company_folder(config.company_folder("B"), COMPANIES["B"])
    books = FakeBooks(config.company_folder("B"), name=COMPANIES["B"])
    books.state["voucherTypes"] = ["Sales", "Purchase", "Receipt", "Payment", "Sales - GST"]
    op = build_auto_operator(config=config, transport=books.transport(),
                             runner=FakeRunner(books, []), echo=lambda line: None)
    assert main(["--results", str(tmp_path / "r.json"), "setup-b"], operator=op) == 0
    out = capsys.readouterr().out
    assert "Company B loaded" in out and "960" in out


def test_setup_b_returns_one_and_explains_when_the_loader_stops(tmp_path, capsys):
    books = FakeBooks(name=COMPANIES["B"])
    books.state["voucherTypes"] = ["Sales"]                      # no "Sales - GST"
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(),
                             runner=FakeRunner(books, []), echo=lambda line: None)
    assert main(["--results", str(tmp_path / "r.json"), "setup-b"], operator=op) == 1
    assert "setup-b failed" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_cli.py -q -k setup_b`
Expected: FAIL — `SystemExit: 2` (`invalid choice: 'setup-b'`)

- [ ] **Step 3: Implement**

In `build_parser()`, beside the `reset-a` parser:
```python
setup_b = sub.add_parser("setup-b", help="load company B from the deterministic dataset (S0 spec §4.3)")
setup_b.add_argument("--stop-any-tally", action="store_true")
setup_b.add_argument("--licence", choices=["licensed", "educational"], default=None,
                     help="default: whatever probe 0 recorded in results.json")
```
In `main()`, **before** the `if args.auto:` block (mirroring `_reset_a`'s placement):
```python
if args.command == "setup-b":
    return _setup_b(args, store, operator)
```
And `_setup_b` follows `_reset_a`'s shape exactly — `operator or build_auto_operator(...)`, `try/except OperatorError → print + return 1`, `finally: if operator is None: auto.close()` — then prints the counts and every problem, and records `company_b_loaded_at` into the environment. **Exit 0 only when `report.problems` is empty**; a verification mismatch is a failed load, not a warning.

Update the module docstring: `python -m v2.probes {list,run,report,reset-a,setup-b}`.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: the whole v2 suite green (351 existing + the new tests)

- [ ] **Step 5: Commit**

```bash
git add v2/probes/__main__.py v2/tests/probes/test_cli.py
git commit -m "feat(bi/v2): setup-b command"
```

---

### Task 9: Docs and tracker

**Files:**
- Modify: `docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md`, `docs/specs/2026-09-22-bi-s0-probes-design.md`

Per CLAUDE.md § Always update the tracker, this is part of the work, not a cleanup pass.

- [ ] **Step 1: Tracker** — flip the company-B-loader row to ✅ with its proof (test names + commit SHA); rewrite "▶ Resume here" so the next step is *create company B in the UI, run `setup-b`, then probe 21*; add a dated change-log row.
- [ ] **Step 2: Roadmap** — S0 row: loader built, batch 5 is next.
- [ ] **Step 3: Spec** — §14 said "how company B's GST registration is filled in" was left to the plan. Record the answer in the spec with a dated "Changed" line: company-level GST stays UI-only; party ledgers carry a check-digit-correct `PARTYGSTIN`; parties without one are written `GSTREGISTRATIONTYPE=Unregistered`.
- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs(bi/v2): company B loader built — tracker, roadmap and spec §14 answer"
```

---

## What this plan does NOT cover

- **Creating company B in Tally.** It is made by hand in the UI (spec §4.3): exact name `Sharma & Sons' Probe Traders`, books from 01-04-2022, Maharashtra, GST enabled, F2 ≥ 31-03-2026, and the custom voucher type `Sales - GST`. The loader verifies and pauses; it never creates a company or a voucher type.
- **The company-B probes** (21, 5, 11, 14, 15, 22 and the B parts of 3, 16, 18, 23, 25). They consume this loader and are their own plan.
- **Company C / probe 24.**
- **The live run.** Building and testing here is entirely offline against `FakeBooks`; running `setup-b` against real Tally is a separate, operator-present step.

## Self-review notes

- **Spec coverage.** §4.3 dataset table → Task 1; expected figures → Task 2; loader rules (list-before-create, read-back, pause on a flag that won't stick, duplicate-name pause) → Task 6; §4.6 Educational clamp → Tasks 1 and 6; §5.3 CLI row → Task 8; §6 run-order `setup-b` step → Task 8; §11.4's nine cases → the nine tests in Task 6; §12 risk row (setup-b freezes Tally) → the rule-10 guard in Task 4 plus the fake's modal in Task 3; §14's open GSTIN question → answered in Global Constraints, recorded in Task 9.
- **One spec item deliberately re-scoped:** §4.3's "duplicate ledger names (R9): a pause step asks you to try creating a ledger with an existing name under another parent in the UI" is a *probe* observation, not loader behaviour. It belongs to probe 25's B part, not to `setup-b`, and is listed above under "what this plan does not cover".
- **Type consistency.** `LoadReport` keys are the same five strings throughout (`groups`, `units`, `items`, `ledgers`, `vouchers`); `create_b_voucher` takes plain tuples, so `writes.py` never imports `company_b_data`; `list_groups` returns `dict[str, str]` in both its definition (Task 4) and its use (Task 6).
