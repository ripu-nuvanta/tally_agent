# Tally Stage 1 — Seeder Implementation Plan

> **Status (2026-05-05):** Tasks 1–10 implemented; Tasks 11–13 partially executed. Live seed Runs A+B+C clean (57 entities). Run D (vouchers) silently dropped 48/50 due to Tally license-date-clamping; writer didn't check `CREATED >= 1`. After discovery, the company went read-only and is no longer findable. Hardening landed (`TallyWriteError` on silent drops, seeder pre-flights Tally current-date). **Re-run pending next session in a fresh company.** See `memory/stage_1_seeder.md` for the full incident report + next-session checklist.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable seeder that populates a fresh `Bharat Traders Private Limited` company in TallyPrime with the full Bharat Traders dataset (groups, units, stock groups, ledgers w/ opening balances, stock items w/ HSN+GST, sales/purchase invoices w/ GST, payments, receipts), then run it once and verify the result via the read path.

**Architecture:** Build verified envelopes from `docs/tally-write-exploration-v4.md` into `backend/tally_bridge/import_builder.py` as pure builder functions. Wrap them in `TallyWriter` methods. The seeder script (`scripts/seed_tally_data.py`) orchestrates phases in dependency order using a single `TallyClient` + `TallyWriter` instance. Seed data lives in `scripts/seed_data/bharat_traders.py` (extracted from `tests/fixtures/generate_fixtures.py`) and is the single source of truth for both the seeder and fixture generation.

**Tech Stack:** Python (httpx async), TallyPrime XML import API, pytest for unit tests.

**Reference docs:**
- `docs/tally-write-exploration-v4.md` — verified envelope reference (THE authority)
- `docs/plans/2026-05-04-tally-seed-data-plan.md` — Stage 1 design (this plan implements it)
- `memory/stage_0_seed_exploration.md` — cheat sheet of gotchas

---

## File Structure

**New files:**
- `scripts/seed_data/__init__.py` — package marker
- `scripts/seed_data/bharat_traders.py` — extracted seed data: GROUPS, UNITS, STOCK_GROUPS, STOCK_ITEMS (with HSN/GST), LEDGERS (with state/GSTIN/opening), GST_LEDGERS, SALES_INVOICES, PURCHASE_INVOICES, PAYMENTS, RECEIPTS, plus a `PARTY_STATES` map for intra/inter-state classification.
- `scripts/seed_tally_data.py` — orchestrator CLI.
- `scripts/verify_tally_bridge_live.py` — Tier-3 read-side verification against seeded company.
- `tests/unit/test_import_builder_voucher_types.py` — XML structure assertions for new builders.

**Modified files:**
- `backend/tally_bridge/import_builder.py` — add 7 builders (unit, stock_group, stock_item, gst_ledger, sales_voucher, purchase_voucher, receipt_voucher, journal_voucher) + extend `build_create_ledger` for opening balance / state / GST.
- `backend/tally_bridge/writer.py` — add async write methods that wrap each new builder.
- `backend/tally_bridge/client.py` — bump write-path HTTP timeout to 90s.

**Out of scope for this plan** (deferred):
- Mock handler import-side support / Tier-2 seeder integration test (Tier-1 unit + Tier-3 live verify is sufficient gate).
- Backup distribution (Stage 2).
- Fixture regeneration to include GST on totals (fixtures currently exclude GST; seed values will include GST, which is intentional — fixtures are for read-side mock testing, not a 1:1 mirror of seeded company).

---

## Key invariants (from v4 doc)

1. Voucher dates use **YYYYMMDD** in `<DATE>` body. Voucher delete uses **DD-MMM-YYYY** in attribute (we do not delete in the seeder).
2. All seed voucher dates are **2025-10-01 .. 2026-03-15** — inside Bharat Traders FY (April 2025–March 2026).
3. **Sign convention** (Op 6 / Op 7 of v4):
   - Sales:    party `Yes/-tot`, GST `No/+tax`, inv `No/+goods`, alloc `No/+goods`
   - Purchase: party `No/+tot`,  GST `Yes/-tax`, inv `Yes/-goods`, alloc `Yes/-goods`
4. All masters except Unit need `<NAME.LIST><NAME>...</NAME></NAME.LIST>`. Units take a single `<NAME>` child (NO `NAME.LIST` — causes "BAD UNIT NAME").
5. Sales/Purchase vouchers need `<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>` + `<ISINVOICE>Yes</ISINVOICE>`. Receipt/Journal/Payment use `Accounting Voucher View`.
6. Intra-state vs inter-state: derived from party `LEDSTATENAME` vs company state (Maharashtra). Bharat Traders' debtors/creditors states determine CGST+SGST vs IGST. Seed data treats all parties as Maharashtra-based (intra-state) for simplicity unless we explicitly mark otherwise — see `PARTY_STATES` in `bharat_traders.py`.
7. Mixed-rate invoices: emit one `LEDGERENTRIES.LIST` per tax ledger with the **summed** tax amount across lines at that rate. Per-line auto-compute is NOT observed.
8. Seeder is **one-shot per company** — re-running leaves audit-locked residue.
9. HTTP write timeout must be **90s**.

---

## GST + HSN mapping (seed data decisions)

| Stock group | Items | HSN | GST rate |
|---|---|---|---|
| Electronics | Samsung 24" Monitor (8528), HP Laptop 15s (8471), Samsung Galaxy Tab A8 (8471), Dell Desktop Optiplex (8471), Lenovo Ideapad Slim 3 (8471) | 8528 / 8471 | 18% |
| Peripherals | Logitech Wireless Mouse (8471), Logitech Keyboard K380 (8471), HP DeskJet Printer 2723 (8443), TP-Link WiFi Router AC750 (8517), USB-C Hub 7-in-1 (8471) | 8471 / 8443 / 8517 | 18% |
| Office Supplies | A4 Paper Ream (4802), Whiteboard Marker Set (9608), Box File Pack (4820), Pen Drive 32GB (8523) | 4802 / 9608 / 4820 / 8523 | **12%** for paper/markers/box files; **18%** for stapler/pen drive |

Per-line GST rate is read off the item's mapping. Voucher builder sums tax-by-rate buckets and emits one CGST+SGST (or IGST) line per bucket.

---

### Task 1: Extract seed data into `scripts/seed_data/bharat_traders.py`

**Why first:** every subsequent task imports from this module.

**Files:**
- Create: `scripts/seed_data/__init__.py` (empty)
- Create: `scripts/seed_data/bharat_traders.py`

- [ ] **Step 1: Create empty package marker**

```python
# scripts/seed_data/__init__.py
"""Seed data for live Tally companies."""
```

- [ ] **Step 2: Create `scripts/seed_data/bharat_traders.py` with the full dataset**

Copy data from `tests/fixtures/generate_fixtures.py:16-227` plus add:
- `COMPANY_NAME = "Bharat Traders Private Limited"` (NOTE: matches the live company exactly — different from fixture's `"Bharat Traders Pvt Ltd"`).
- `COMPANY_STATE = "Maharashtra"`.
- `COMPANY_GSTIN = "27AABCB1234F1ZP"`.
- `GROUPS` — list of `(name, parent)` for sub-groups that don't ship by default in Tally. From the existing `ACCOUNT_GROUPS` list, only the *non-default* groups are needed: `("North Zone Debtors", "Sundry Debtors")`, `("South Zone Debtors", "Sundry Debtors")`, `("National Creditors", "Sundry Creditors")`, `("Local Creditors", "Sundry Creditors")`. (`Sundry Debtors`, `Sundry Creditors`, `Bank Accounts`, `Cash-in-Hand`, `Sales Accounts`, `Purchase Accounts`, `Direct Expenses`, `Indirect Expenses`, `Duties & Taxes`, `Capital Account` ship with Tally — do NOT recreate.)
- `UNITS = [("Nos", "Numbers"), ("Pcs", "Pieces")]` — short ASCII names per v4 doc.
- `STOCK_GROUPS = [("Electronics", ""), ("Peripherals", ""), ("Office Supplies", "")]` — empty parent = top-level (Primary).
- `GST_LEDGERS` — six tax ledgers under `Duties & Taxes`:
  ```python
  GST_LEDGERS = [
      ("CGST Output", "Central Tax"),
      ("SGST Output", "State Tax"),
      ("IGST Output", "Integrated Tax"),
      ("CGST Input",  "Central Tax"),
      ("SGST Input",  "State Tax"),
      ("IGST Input",  "Integrated Tax"),
  ]
  ```
- `STOCK_ITEMS` — augment existing 15-item list with `(hsn, gst_rate)` per item. Add a 7th tuple field. Mapping (per the table above):
  - Monitor → 8528 / 18, HP Laptop → 8471 / 18, Galaxy Tab → 8471 / 18, Dell Desktop → 8471 / 18, Lenovo Ideapad → 8471 / 18
  - Logitech Mouse → 8471 / 18, Logitech Keyboard → 8471 / 18, HP DeskJet → 8443 / 18, TP-Link Router → 8517 / 18, USB-C Hub → 8471 / 18
  - A4 Paper Ream → 4802 / 12, Whiteboard Marker → 9608 / 12, Stapler → 8205 / 18, Box File → 4820 / 12, Pen Drive → 8523 / 18
- `LEDGERS` — augment existing 33-ledger list. Add fields per ledger: `state` (string or None), `gstin` (string or None), `gst_reg_type` (string or None — "Regular"/"Unregistered"/None). For seed-data simplicity, ALL parties are Maharashtra-based so all sales/purchases are intra-state CGST+SGST. Set `state="Maharashtra"`, `gst_reg_type="Regular"`, fake-but-valid `gstin` (e.g. `"27AAAAA0000A1Z5"` series) for every Sundry Debtor and Sundry Creditor. For non-party ledgers (cash, banks, expense, sales, purchase, capital, GST), pass `state=None, gstin=None, gst_reg_type=None`.
- `SALES_INVOICES`, `PURCHASE_INVOICES`, `PAYMENTS`, `RECEIPTS` — copy the lists verbatim from `generate_fixtures.py`.

Tuple shape changes (so subsequent tasks compile):
```python
# LEDGER tuple: (name, parent, opening_balance, state, gstin, gst_reg_type)
# STOCK_ITEM tuple: (name, group, uom, selling_rate, opening_qty, opening_rate, opening_value, hsn, gst_rate)
```

- [ ] **Step 3: Sanity check — import the module and verify counts**

```bash
PYTHONPATH=. python -c "from scripts.seed_data import bharat_traders as bt; print(len(bt.LEDGERS), len(bt.STOCK_ITEMS), len(bt.SALES_INVOICES), len(bt.PURCHASE_INVOICES), len(bt.PAYMENTS), len(bt.RECEIPTS))"
```

Expected: `33 15 16 8 16 10`

- [ ] **Step 4: Commit**

```bash
git add scripts/seed_data/
git commit -m "feat(seed): extract Bharat Traders seed data with HSN/GST + state metadata"
```

---

### Task 2: Builder — `build_create_unit`

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_import_builder_voucher_types.py
"""Unit tests for new Stage 1 builders (Unit, StockGroup, StockItem, GST ledger,
Sales/Purchase/Receipt/Journal vouchers). Each test asserts XML structure only —
no live Tally calls."""
import xml.etree.ElementTree as ET

from backend.tally_bridge.import_builder import build_create_unit


def _root(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_build_create_unit_has_no_name_list():
    xml = build_create_unit("Nos", formal_name="Numbers", company="Bharat Traders Private Limited")
    root = _root(xml)
    unit = root.find(".//UNIT")
    assert unit is not None
    assert unit.get("ACTION") == "Create"
    # NAME.LIST is forbidden on UNIT (causes "BAD UNIT NAME" per v4 doc)
    assert unit.find("NAME.LIST") is None
    assert unit.findtext("NAME") == "Nos"
    assert unit.findtext("ISSIMPLEUNIT") == "Yes"


def test_build_create_unit_uses_all_masters_report():
    xml = build_create_unit("Nos", formal_name="Numbers", company="Bharat Traders Private Limited")
    root = _root(xml)
    assert root.findtext(".//REPORTNAME") == "All Masters"
    assert root.findtext(".//SVCURRENTCOMPANY") == "Bharat Traders Private Limited"
```

- [ ] **Step 2: Run test → expect FAIL with ImportError**

```bash
PYTHONPATH=. pytest tests/unit/test_import_builder_voucher_types.py::test_build_create_unit_has_no_name_list -v
```

Expected: `ImportError: cannot import name 'build_create_unit'`

- [ ] **Step 3: Implement `build_create_unit` in `import_builder.py`**

Append to `backend/tally_bridge/import_builder.py`:

```python
def build_create_unit(name: str, formal_name: str, company: str) -> str:
    """Build XML to create a unit (UOM) master in Tally.

    NOTE: UNIT does NOT take NAME.LIST — that triggers "BAD UNIT NAME".
    Stick to short ASCII names (Nos, Pcs). See docs/tally-write-exploration-v4.md Op 1.
    """
    _require(name, "name")
    _require(formal_name, "formal_name")
    _require(company, "company")

    unit_xml = f"""<UNIT ACTION="Create">
<NAME>{_esc(name)}</NAME>
<ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
<FORMALNAME>{_esc(formal_name)}</FORMALNAME>
</UNIT>"""
    return _wrap_import("All Masters", company, unit_xml)
```

- [ ] **Step 4: Run test → PASS**

```bash
PYTHONPATH=. pytest tests/unit/test_import_builder_voucher_types.py::test_build_create_unit_has_no_name_list tests/unit/test_import_builder_voucher_types.py::test_build_create_unit_uses_all_masters_report -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/tally_bridge/import_builder.py tests/unit/test_import_builder_voucher_types.py
git commit -m "feat(tally): add build_create_unit (no NAME.LIST per v4 envelope)"
```

---

### Task 3: Builder — `build_create_stock_group`

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

- [ ] **Step 1: Write failing test**

```python
def test_build_create_stock_group_has_name_list():
    from backend.tally_bridge.import_builder import build_create_stock_group
    xml = build_create_stock_group("Electronics", parent="", company="Bharat Traders Private Limited")
    root = _root(xml)
    sg = root.find(".//STOCKGROUP")
    assert sg.get("NAME") == "Electronics"
    assert sg.get("ACTION") == "Create"
    name_list = sg.find("NAME.LIST")
    assert name_list is not None
    assert name_list.findtext("NAME") == "Electronics"
    parent = sg.find("PARENT")
    assert parent is not None
    assert (parent.text or "") == ""
    assert sg.findtext("ISADDABLE") == "No"


def test_build_create_stock_group_with_parent():
    from backend.tally_bridge.import_builder import build_create_stock_group
    xml = build_create_stock_group("Sub Group", parent="Electronics", company="X")
    root = _root(xml)
    assert root.find(".//STOCKGROUP/PARENT").text == "Electronics"
```

- [ ] **Step 2: Run → FAIL** (`ImportError`)

- [ ] **Step 3: Implement**

```python
def build_create_stock_group(name: str, parent: str, company: str) -> str:
    """Build XML to create a stock group. Empty parent = top-level (under Primary)."""
    _require(name, "name")
    _require(company, "company")

    parent_xml = f"<PARENT>{_esc(parent)}</PARENT>" if parent else "<PARENT/>"
    sg_xml = f"""<STOCKGROUP NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
{parent_xml}
<ISADDABLE>No</ISADDABLE>
</STOCKGROUP>"""
    return _wrap_import("All Masters", company, sg_xml)
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): add build_create_stock_group"
```

---

### Task 4: Builder — `build_create_stock_item` (with HSN + per-item GST)

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

- [ ] **Step 1: Write failing test**

```python
def test_build_create_stock_item_18pct_rate():
    from backend.tally_bridge.import_builder import build_create_stock_item
    xml = build_create_stock_item(
        name="Samsung 24 inch Monitor",
        group="Electronics",
        uom="Nos",
        opening_qty=20,
        opening_rate=11000,
        hsn_code="8528",
        gst_rate=18,
        company="Bharat Traders Private Limited",
    )
    root = _root(xml)
    si = root.find(".//STOCKITEM")
    assert si.get("NAME") == "Samsung 24 inch Monitor"
    assert si.find("NAME.LIST/NAME").text == "Samsung 24 inch Monitor"
    assert si.findtext("PARENT") == "Electronics"
    assert si.findtext("BASEUNITS") == "Nos"
    assert si.findtext("HSNCODE") == "8528"
    assert si.findtext("HSN") == "8528"
    assert si.findtext("GSTAPPLICABLE") == "Applicable"
    assert si.findtext("GSTTYPEOFSUPPLY") == "Goods"

    # GSTDETAILS rates: 18% IGST, 9% CGST, 9% SGST
    gd = si.find("GSTDETAILS.LIST")
    assert gd.findtext("IGSTRATE") == "18"
    assert gd.findtext("CGSTRATE") == "9"
    assert gd.findtext("SGSTRATE") == "9"
    assert gd.findtext("TAXABILITY") == "Taxable"

    # Opening balance
    assert si.findtext("OPENINGBALANCE") == "20 Nos"
    assert si.findtext("OPENINGRATE") == "11000.00/Nos"
    assert si.findtext("OPENINGVALUE") == "220000.00"


def test_build_create_stock_item_12pct_rate_splits_correctly():
    from backend.tally_bridge.import_builder import build_create_stock_item
    xml = build_create_stock_item(
        name="A4 Paper Ream",
        group="Office Supplies",
        uom="Pcs",
        opening_qty=200,
        opening_rate=280,
        hsn_code="4802",
        gst_rate=12,
        company="X",
    )
    root = _root(xml)
    gd = root.find(".//GSTDETAILS.LIST")
    assert gd.findtext("IGSTRATE") == "12"
    assert gd.findtext("CGSTRATE") == "6"
    assert gd.findtext("SGSTRATE") == "6"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** (matches v4 Op 3 exactly)

```python
def build_create_stock_item(
    name: str,
    group: str,
    uom: str,
    opening_qty: float,
    opening_rate: float,
    hsn_code: str,
    gst_rate: int,
    company: str,
    applicable_from: str = "20250401",
) -> str:
    """Build XML to create a stock item with HSN + per-item GST rate.

    Splits gst_rate evenly across CGST/SGST (intra-state) and uses full rate for IGST
    (inter-state). E.g. 18% → 9 CGST + 9 SGST + 18 IGST.
    See docs/tally-write-exploration-v4.md Op 3.
    """
    _require(name, "name")
    _require(group, "group")
    _require(uom, "uom")
    _require(hsn_code, "hsn_code")
    _require(company, "company")
    if opening_qty < 0 or opening_rate < 0:
        raise ValueError("opening_qty and opening_rate must be non-negative")
    if gst_rate not in (0, 5, 12, 18, 28):
        raise ValueError(f"gst_rate must be one of (0, 5, 12, 18, 28); got {gst_rate}")

    half = gst_rate / 2
    half_str = f"{half:g}"  # 9 not 9.0; 2.5 stays 2.5
    igst_str = f"{gst_rate:g}"
    opening_value = opening_qty * opening_rate

    si_xml = f"""<STOCKITEM NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
<PARENT>{_esc(group)}</PARENT>
<BASEUNITS>{_esc(uom)}</BASEUNITS>
<GSTAPPLICABLE>Applicable</GSTAPPLICABLE>
<GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
<HSNCODE>{_esc(hsn_code)}</HSNCODE>
<HSN>{_esc(hsn_code)}</HSN>
<HSNDETAILS.LIST>
<APPLICABLEFROM>{applicable_from}</APPLICABLEFROM>
<HSNCODE>{_esc(hsn_code)}</HSNCODE>
<HSN>{_esc(hsn_code)}</HSN>
</HSNDETAILS.LIST>
<GSTDETAILS.LIST>
<APPLICABLEFROM>{applicable_from}</APPLICABLEFROM>
<TAXABILITY>Taxable</TAXABILITY>
<IGSTRATE>{igst_str}</IGSTRATE>
<CGSTRATE>{half_str}</CGSTRATE>
<SGSTRATE>{half_str}</SGSTRATE>
<STATEWISEDETAILS.LIST>
<STATENAME>Any</STATENAME>
<RATEDETAILS.LIST><GSTRATEDUTYHEAD>Central Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>{half_str}</GSTRATE></RATEDETAILS.LIST>
<RATEDETAILS.LIST><GSTRATEDUTYHEAD>State Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>{half_str}</GSTRATE></RATEDETAILS.LIST>
<RATEDETAILS.LIST><GSTRATEDUTYHEAD>Integrated Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>{igst_str}</GSTRATE></RATEDETAILS.LIST>
<RATEDETAILS.LIST><GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>0</GSTRATE></RATEDETAILS.LIST>
</STATEWISEDETAILS.LIST>
</GSTDETAILS.LIST>
<OPENINGBALANCE>{opening_qty:g} {_esc(uom)}</OPENINGBALANCE>
<OPENINGRATE>{opening_rate:.2f}/{_esc(uom)}</OPENINGRATE>
<OPENINGVALUE>{opening_value:.2f}</OPENINGVALUE>
</STOCKITEM>"""
    return _wrap_import("All Masters", company, si_xml)
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): add build_create_stock_item with HSN + per-item GST"
```

---

### Task 5: Builder — extend `build_create_ledger` + add `build_create_gst_ledger`

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py` (add new tests; existing `build_create_ledger` tests in `tests/unit/test_import_builder.py` must still pass)

- [ ] **Step 1: Write failing tests**

```python
def test_build_create_ledger_with_opening_state_gstin():
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger(
        name="Apex Technologies Pvt Ltd",
        parent="North Zone Debtors",
        company="X",
        gstin="27AAACA0000A1Z5",
        state="Maharashtra",
        gst_reg_type="Regular",
        opening_balance=0,
        is_billwise=True,
    )
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.findtext("PARTYGSTIN") == "27AAACA0000A1Z5"
    assert led.findtext("LEDSTATENAME") == "Maharashtra"
    assert led.findtext("GSTREGISTRATIONTYPE") == "Regular"
    assert led.findtext("ISBILLWISEON") == "Yes"


def test_build_create_ledger_with_opening_balance_only():
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger(
        name="Capital Account",
        parent="Capital Account",
        company="X",
        opening_balance=750000,
    )
    root = _root(xml)
    assert root.find(".//LEDGER").findtext("OPENINGBALANCE") == "750000.00"


def test_build_create_ledger_back_compat():
    """Existing call signature (positional + gstin only) still works."""
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger("Travel", "Indirect Expenses", "X")
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.findtext("PARENT") == "Indirect Expenses"
    assert led.find("OPENINGBALANCE") is None  # not emitted when 0/None


def test_build_create_gst_ledger():
    from backend.tally_bridge.import_builder import build_create_gst_ledger
    xml = build_create_gst_ledger(
        name="CGST Output",
        duty_head="Central Tax",
        company="X",
    )
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.get("NAME") == "CGST Output"
    assert led.findtext("PARENT") == "Duties & Taxes"
    assert led.findtext("TAXTYPE") == "GST"
    assert led.findtext("GSTDUTYHEAD") == "Central Tax"
    assert led.findtext("ISBILLWISEON") == "No"
    assert led.findtext("AFFECTSSTOCK") == "No"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** (replace existing `build_create_ledger` and add `build_create_gst_ledger`)

```python
def build_create_ledger(
    name: str,
    parent: str,
    company: str,
    gstin: str | None = None,
    state: str | None = None,
    gst_reg_type: str | None = None,
    opening_balance: float | None = None,
    is_billwise: bool = False,
) -> str:
    """Build XML to create a ledger master in Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.

    Args:
        opening_balance: Positive value; sign inferred from parent group nature
            (Capital → credit; Cash-in-Hand → debit). Pass None or 0 to omit.
        is_billwise: Set True for Sundry Debtors/Creditors (otherwise voucher
            bill-allocation fails).
    """
    _require(name, "name")
    _require(parent, "parent")
    _require(company, "company")

    extras = []
    if gstin:
        extras.append(f"<PARTYGSTIN>{_esc(gstin)}</PARTYGSTIN>")
    if state:
        extras.append(f"<LEDSTATENAME>{_esc(state)}</LEDSTATENAME>")
    if gst_reg_type:
        extras.append(f"<GSTREGISTRATIONTYPE>{_esc(gst_reg_type)}</GSTREGISTRATIONTYPE>")
    if opening_balance is not None and opening_balance != 0:
        extras.append(f"<OPENINGBALANCE>{abs(float(opening_balance)):.2f}</OPENINGBALANCE>")
    if is_billwise:
        extras.append("<ISBILLWISEON>Yes</ISBILLWISEON>")
    extras_xml = ("\n" + "\n".join(extras)) if extras else ""

    ledger_xml = f"""<LEDGER NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
<PARENT>{_esc(parent)}</PARENT>{extras_xml}
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_create_gst_ledger(name: str, duty_head: str, company: str) -> str:
    """Build XML to create a GST tax ledger under Duties & Taxes.

    duty_head: one of "Central Tax", "State Tax", "Integrated Tax".
    Same envelope serves both Output and Input ledgers — Tally infers direction
    from voucher usage. See docs/tally-write-exploration-v4.md Op 4.
    """
    _require(name, "name")
    _require(company, "company")
    if duty_head not in ("Central Tax", "State Tax", "Integrated Tax"):
        raise ValueError(f"invalid duty_head: {duty_head}")

    led_xml = f"""<LEDGER NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
<PARENT>Duties &amp; Taxes</PARENT>
<TAXTYPE>GST</TAXTYPE>
<GSTDUTYHEAD>{_esc(duty_head)}</GSTDUTYHEAD>
<RATEOFTAXCALCULATION>0</RATEOFTAXCALCULATION>
<ROUNDINGMETHOD/>
<ROUNDINGLIMIT>0</ROUNDINGLIMIT>
<ISBILLWISEON>No</ISBILLWISEON>
<AFFECTSSTOCK>No</AFFECTSSTOCK>
<ISCOSTCENTRESON>No</ISCOSTCENTRESON>
</LEDGER>"""
    return _wrap_import("All Masters", company, led_xml)
```

- [ ] **Step 4: Run new tests + existing ledger tests → all PASS**

```bash
PYTHONPATH=. pytest tests/unit/test_import_builder.py tests/unit/test_import_builder_voucher_types.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): extend build_create_ledger (state/GSTIN/opening) + add build_create_gst_ledger"
```

---

### Task 6: Builder — `build_create_sales_voucher` (with stock + GST, intra-state)

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

The builder takes a list of line items and a `gst_mode` (`"intra"` or `"inter"`). For intra, it groups lines by GST rate, computes CGST+SGST per bucket, emits one CGST + one SGST `LEDGERENTRIES.LIST` per bucket. For inter, single IGST line per bucket.

- [ ] **Step 1: Write failing tests**

```python
def test_build_create_sales_voucher_intra_state_18pct():
    from backend.tally_bridge.import_builder import build_create_sales_voucher
    xml = build_create_sales_voucher(
        date="20251001",
        voucher_number="S001",
        party="Apex Technologies Pvt Ltd",
        items=[
            # (item_name, qty, rate, sales_ledger, uom, gst_rate)
            ("HP Laptop 15s", 2, 45000, "Sales - Electronics", "Nos", 18),
            ("Logitech Wireless Mouse", 5, 800, "Sales - Electronics", "Nos", 18),
        ],
        narration="Invoice #S001 - Laptops and peripherals",
        gst_mode="intra",
        company="Bharat Traders Private Limited",
    )
    root = _root(xml)
    v = root.find(".//VOUCHER")
    assert v.get("VCHTYPE") == "Sales"
    assert v.get("ACTION") == "Create"
    assert v.findtext("DATE") == "20251001"
    assert v.findtext("VOUCHERNUMBER") == "S001"
    assert v.findtext("PARTYLEDGERNAME") == "Apex Technologies Pvt Ltd"
    assert v.findtext("PERSISTEDVIEW") == "Invoice Voucher View"
    assert v.findtext("ISINVOICE") == "Yes"

    ledger_entries = v.findall("LEDGERENTRIES.LIST")
    # Expected: 1 party + 1 CGST + 1 SGST = 3
    assert len(ledger_entries) == 3

    # Party: ISDEEMEDPOSITIVE=Yes, AMOUNT = -94000.00 - 18% = -110920.00
    party = ledger_entries[0]
    assert party.findtext("LEDGERNAME") == "Apex Technologies Pvt Ltd"
    assert party.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert party.findtext("ISPARTYLEDGER") == "Yes"
    assert float(party.findtext("AMOUNT")) == -110920.00

    # CGST: +8460 (94000 * 9% = 8460)
    cgst = ledger_entries[1]
    assert cgst.findtext("LEDGERNAME") == "CGST Output"
    assert cgst.findtext("ISDEEMEDPOSITIVE") == "No"
    assert float(cgst.findtext("AMOUNT")) == 8460.00

    sgst = ledger_entries[2]
    assert sgst.findtext("LEDGERNAME") == "SGST Output"
    assert float(sgst.findtext("AMOUNT")) == 8460.00

    inv_entries = v.findall("ALLINVENTORYENTRIES.LIST")
    assert len(inv_entries) == 2
    laptop = inv_entries[0]
    assert laptop.findtext("STOCKITEMNAME") == "HP Laptop 15s"
    assert laptop.findtext("ISDEEMEDPOSITIVE") == "No"
    assert float(laptop.findtext("AMOUNT")) == 90000.00  # 2 * 45000
    assert laptop.findtext("ACTUALQTY") == "2 Nos"
    alloc = laptop.find("ACCOUNTINGALLOCATIONS.LIST")
    assert alloc.findtext("LEDGERNAME") == "Sales - Electronics"
    assert float(alloc.findtext("AMOUNT")) == 90000.00


def test_build_create_sales_voucher_mixed_rate_18_and_12():
    from backend.tally_bridge.import_builder import build_create_sales_voucher
    xml = build_create_sales_voucher(
        date="20251001",
        voucher_number="S004",
        party="Sharma & Sons Traders",
        items=[
            ("A4 Paper Ream 500 sheets", 50, 350, "Sales - Office Supplies", "Pcs", 12),  # 17500 @ 12% → 2100 GST
            ("Box File Pack of 10",       20, 600, "Sales - Office Supplies", "Pcs", 12),  # 12000 @ 12% → 1440 GST
        ],
        narration="Invoice #S004",
        gst_mode="intra",
        company="X",
    )
    root = _root(xml)
    v = root.find(".//VOUCHER")
    ledger_entries = v.findall("LEDGERENTRIES.LIST")
    # Both lines at 12% → grouped into ONE bucket → 1 party + 1 CGST + 1 SGST
    assert len(ledger_entries) == 3
    cgst = ledger_entries[1]
    sgst = ledger_entries[2]
    # (17500+12000) * 6% = 1770 each
    assert float(cgst.findtext("AMOUNT")) == 1770.00
    assert float(sgst.findtext("AMOUNT")) == 1770.00
    # Party = -(29500 + 2*1770) = -33040
    assert float(ledger_entries[0].findtext("AMOUNT")) == -33040.00


def test_build_create_sales_voucher_inter_state_uses_igst():
    from backend.tally_bridge.import_builder import build_create_sales_voucher
    xml = build_create_sales_voucher(
        date="20251001",
        voucher_number="S100",
        party="Out of State Buyer",
        items=[("HP Laptop 15s", 1, 45000, "Sales - Electronics", "Nos", 18)],
        narration="Inter-state",
        gst_mode="inter",
        company="X",
    )
    root = _root(xml)
    ledger_entries = root.find(".//VOUCHER").findall("LEDGERENTRIES.LIST")
    # 1 party + 1 IGST (no CGST/SGST)
    assert len(ledger_entries) == 2
    assert ledger_entries[1].findtext("LEDGERNAME") == "IGST Output"
    assert float(ledger_entries[1].findtext("AMOUNT")) == 8100.00  # 45000 * 18%
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
def build_create_sales_voucher(
    date: str,
    voucher_number: str,
    party: str,
    items: list[tuple],
    narration: str,
    gst_mode: str,  # "intra" or "inter"
    company: str,
) -> str:
    """Build XML to create a Sales voucher with stock + GST.

    items: list of (item_name, qty, rate, sales_ledger, uom, gst_rate) tuples.
    gst_mode: "intra" → CGST+SGST split; "inter" → IGST only.

    Sign convention (v4 Op 6): party Yes/-tot, GST No/+tax, inv/alloc No/+goods.
    Mixed-rate invoices are supported — per-rate GST totals are summed and emitted
    as one CGST+SGST (or IGST) line per rate bucket.
    """
    _require(date, "date")
    _require(voucher_number, "voucher_number")
    _require(party, "party")
    _require(narration, "narration")
    _require(company, "company")
    if gst_mode not in ("intra", "inter"):
        raise ValueError(f"gst_mode must be 'intra' or 'inter'; got {gst_mode!r}")
    if not items:
        raise ValueError("items must be non-empty")

    # Group line totals by GST rate (taxable_base per rate)
    rate_buckets: dict[int, float] = {}
    for _name, qty, rate, _ledger, _uom, gst_rate in items:
        rate_buckets[gst_rate] = rate_buckets.get(gst_rate, 0.0) + (qty * rate)

    base_total = sum(rate_buckets.values())
    tax_lines: list[str] = []
    tax_total = 0.0
    for rate, base in sorted(rate_buckets.items()):
        if rate == 0:
            continue
        if gst_mode == "intra":
            half = base * (rate / 2) / 100
            tax_total += 2 * half
            tax_lines.append(_sales_tax_line("CGST Output", half))
            tax_lines.append(_sales_tax_line("SGST Output", half))
        else:
            full = base * rate / 100
            tax_total += full
            tax_lines.append(_sales_tax_line("IGST Output", full))

    party_total = base_total + tax_total
    party_block = f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(party)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>{-party_total:.2f}</AMOUNT>
</LEDGERENTRIES.LIST>"""

    inventory_blocks: list[str] = []
    for item_name, qty, rate, sales_ledger, uom, _gst_rate in items:
        amount = qty * rate
        inventory_blocks.append(f"""<ALLINVENTORYENTRIES.LIST>
<STOCKITEMNAME>{_esc(item_name)}</STOCKITEMNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<RATE>{rate:.2f}/{_esc(uom)}</RATE>
<AMOUNT>{amount:.2f}</AMOUNT>
<ACTUALQTY>{qty:g} {_esc(uom)}</ACTUALQTY>
<BILLEDQTY>{qty:g} {_esc(uom)}</BILLEDQTY>
<ACCOUNTINGALLOCATIONS.LIST>
<LEDGERNAME>{_esc(sales_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ACCOUNTINGALLOCATIONS.LIST>
</ALLINVENTORYENTRIES.LIST>""")

    voucher_xml = f"""<VOUCHER VCHTYPE="Sales" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<NARRATION>{_esc(narration)}</NARRATION>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
<VOUCHERNUMBER>{_esc(voucher_number)}</VOUCHERNUMBER>
<PARTYLEDGERNAME>{_esc(party)}</PARTYLEDGERNAME>
<PARTYNAME>{_esc(party)}</PARTYNAME>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<EFFECTIVEDATE>{_esc(date)}</EFFECTIVEDATE>
{party_block}
{chr(10).join(tax_lines)}
{chr(10).join(inventory_blocks)}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def _sales_tax_line(ledger: str, amount: float) -> str:
    return f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</LEDGERENTRIES.LIST>"""
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): add build_create_sales_voucher with GST + mixed-rate support"
```

---

### Task 7: Builder — `build_create_purchase_voucher` (inverse sign convention)

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

- [ ] **Step 1: Write failing tests**

```python
def test_build_create_purchase_voucher_intra_state_signs():
    from backend.tally_bridge.import_builder import build_create_purchase_voucher
    xml = build_create_purchase_voucher(
        date="20250928",
        voucher_number="P001",
        party="Samsung India Electronics",
        items=[
            ("Samsung 24 inch Monitor", 25, 11000, "Purchase - Electronics", "Nos", 18),
        ],
        narration="P001",
        gst_mode="intra",
        company="X",
    )
    root = _root(xml)
    v = root.find(".//VOUCHER")
    assert v.get("VCHTYPE") == "Purchase"
    assert v.findtext("PERSISTEDVIEW") == "Invoice Voucher View"
    assert v.findtext("ISINVOICE") == "Yes"

    ledger_entries = v.findall("LEDGERENTRIES.LIST")
    # 1 party + 1 CGST + 1 SGST
    assert len(ledger_entries) == 3

    # Party: ISDEEMEDPOSITIVE=No, AMOUNT = +275000 + 18% = +324500
    party = ledger_entries[0]
    assert party.findtext("ISDEEMEDPOSITIVE") == "No"
    assert party.findtext("ISPARTYLEDGER") == "Yes"
    assert float(party.findtext("AMOUNT")) == 324500.00

    # GST input: ISDEEMEDPOSITIVE=Yes, AMOUNT NEGATIVE
    cgst = ledger_entries[1]
    assert cgst.findtext("LEDGERNAME") == "CGST Input"
    assert cgst.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert float(cgst.findtext("AMOUNT")) == -24750.00  # -(275000 * 9%)

    # Inventory: ISDEEMEDPOSITIVE=Yes, AMOUNT NEGATIVE
    inv = v.find("ALLINVENTORYENTRIES.LIST")
    assert inv.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert float(inv.findtext("AMOUNT")) == -275000.00
    alloc = inv.find("ACCOUNTINGALLOCATIONS.LIST")
    assert alloc.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert float(alloc.findtext("AMOUNT")) == -275000.00
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement** (mirror of sales with inverted signs per v4 Op 7)

```python
def build_create_purchase_voucher(
    date: str,
    voucher_number: str,
    party: str,
    items: list[tuple],
    narration: str,
    gst_mode: str,
    company: str,
) -> str:
    """Build XML to create a Purchase voucher with stock + GST.

    items: list of (item_name, qty, rate, purchase_ledger, uom, gst_rate) tuples.

    INVERSE sign convention from sales (v4 Op 7):
      party No/+tot, GST Yes/-tax, inv/alloc Yes/-goods.
    """
    _require(date, "date")
    _require(voucher_number, "voucher_number")
    _require(party, "party")
    _require(narration, "narration")
    _require(company, "company")
    if gst_mode not in ("intra", "inter"):
        raise ValueError(f"gst_mode must be 'intra' or 'inter'; got {gst_mode!r}")
    if not items:
        raise ValueError("items must be non-empty")

    rate_buckets: dict[int, float] = {}
    for _name, qty, rate, _ledger, _uom, gst_rate in items:
        rate_buckets[gst_rate] = rate_buckets.get(gst_rate, 0.0) + (qty * rate)

    base_total = sum(rate_buckets.values())
    tax_lines: list[str] = []
    tax_total = 0.0
    for rate, base in sorted(rate_buckets.items()):
        if rate == 0:
            continue
        if gst_mode == "intra":
            half = base * (rate / 2) / 100
            tax_total += 2 * half
            tax_lines.append(_purchase_tax_line("CGST Input", half))
            tax_lines.append(_purchase_tax_line("SGST Input", half))
        else:
            full = base * rate / 100
            tax_total += full
            tax_lines.append(_purchase_tax_line("IGST Input", full))

    party_total = base_total + tax_total
    party_block = f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(party)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<ISPARTYLEDGER>Yes</ISPARTYLEDGER>
<AMOUNT>{party_total:.2f}</AMOUNT>
</LEDGERENTRIES.LIST>"""

    inventory_blocks: list[str] = []
    for item_name, qty, rate, purchase_ledger, uom, _gst_rate in items:
        amount = qty * rate
        inventory_blocks.append(f"""<ALLINVENTORYENTRIES.LIST>
<STOCKITEMNAME>{_esc(item_name)}</STOCKITEMNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<RATE>{rate:.2f}/{_esc(uom)}</RATE>
<AMOUNT>{-amount:.2f}</AMOUNT>
<ACTUALQTY>{qty:g} {_esc(uom)}</ACTUALQTY>
<BILLEDQTY>{qty:g} {_esc(uom)}</BILLEDQTY>
<ACCOUNTINGALLOCATIONS.LIST>
<LEDGERNAME>{_esc(purchase_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>{-amount:.2f}</AMOUNT>
</ACCOUNTINGALLOCATIONS.LIST>
</ALLINVENTORYENTRIES.LIST>""")

    voucher_xml = f"""<VOUCHER VCHTYPE="Purchase" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<NARRATION>{_esc(narration)}</NARRATION>
<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
<VOUCHERNUMBER>{_esc(voucher_number)}</VOUCHERNUMBER>
<PARTYLEDGERNAME>{_esc(party)}</PARTYLEDGERNAME>
<PARTYNAME>{_esc(party)}</PARTYNAME>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<ISINVOICE>Yes</ISINVOICE>
<EFFECTIVEDATE>{_esc(date)}</EFFECTIVEDATE>
{party_block}
{chr(10).join(tax_lines)}
{chr(10).join(inventory_blocks)}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def _purchase_tax_line(ledger: str, amount: float) -> str:
    return f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>{-amount:.2f}</AMOUNT>
</LEDGERENTRIES.LIST>"""
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): add build_create_purchase_voucher (inverse sign convention)"
```

---

### Task 8: Builder — `build_create_receipt_voucher` + `build_create_journal_voucher`

**Files:**
- Modify: `backend/tally_bridge/import_builder.py`
- Test: `tests/unit/test_import_builder_voucher_types.py`

Both share the `ALLLEDGERENTRIES.LIST` shape from v4 Op 8 / Op 9.

- [ ] **Step 1: Write failing tests**

```python
def test_build_create_receipt_voucher():
    from backend.tally_bridge.import_builder import build_create_receipt_voucher
    xml = build_create_receipt_voucher(
        date="20251020",
        voucher_number="RCT001",
        party="Apex Technologies Pvt Ltd",
        bank_ledger="HDFC Bank - Current A/c",
        amount=94000,
        narration="Receipt against S001",
        company="X",
    )
    root = _root(xml)
    v = root.find(".//VOUCHER")
    assert v.get("VCHTYPE") == "Receipt"
    assert v.findtext("PERSISTEDVIEW") == "Accounting Voucher View"
    assert v.findtext("VOUCHERNUMBER") == "RCT001"

    entries = v.findall("ALLLEDGERENTRIES.LIST")
    assert len(entries) == 2
    bank, party = entries[0], entries[1]
    assert bank.findtext("LEDGERNAME") == "HDFC Bank - Current A/c"
    assert bank.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert float(bank.findtext("AMOUNT")) == -94000.00
    assert party.findtext("LEDGERNAME") == "Apex Technologies Pvt Ltd"
    assert party.findtext("ISDEEMEDPOSITIVE") == "No"
    assert float(party.findtext("AMOUNT")) == 94000.00


def test_build_create_journal_voucher():
    from backend.tally_bridge.import_builder import build_create_journal_voucher
    xml = build_create_journal_voucher(
        date="20251031",
        voucher_number="J001",
        debit_ledger="Rent",
        credit_ledger="HDFC Bank - Current A/c",
        amount=75000,
        narration="Adjusting entry",
        company="X",
    )
    root = _root(xml)
    v = root.find(".//VOUCHER")
    assert v.get("VCHTYPE") == "Journal"
    assert v.findtext("PERSISTEDVIEW") == "Accounting Voucher View"
    entries = v.findall("ALLLEDGERENTRIES.LIST")
    assert len(entries) == 2
    debit, credit = entries[0], entries[1]
    assert debit.findtext("LEDGERNAME") == "Rent"
    assert debit.findtext("ISDEEMEDPOSITIVE") == "Yes"
    assert float(debit.findtext("AMOUNT")) == -75000.00
    assert credit.findtext("LEDGERNAME") == "HDFC Bank - Current A/c"
    assert credit.findtext("ISDEEMEDPOSITIVE") == "No"
    assert float(credit.findtext("AMOUNT")) == 75000.00
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
def build_create_receipt_voucher(
    date: str,
    voucher_number: str,
    party: str,
    bank_ledger: str,
    amount: float,
    narration: str,
    company: str,
) -> str:
    """Build XML to create a Receipt voucher (party → bank).

    Bank debit (Yes/-amount), party credit (No/+amount). See v4 Op 8.
    """
    _require(date, "date")
    _require(voucher_number, "voucher_number")
    _require(party, "party")
    _require(bank_ledger, "bank_ledger")
    _require(narration, "narration")
    _require(company, "company")
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")

    voucher_xml = f"""<VOUCHER VCHTYPE="Receipt" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<NARRATION>{_esc(narration)}</NARRATION>
<VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
<VOUCHERNUMBER>{_esc(voucher_number)}</VOUCHERNUMBER>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(bank_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>{-amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(party)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_create_journal_voucher(
    date: str,
    voucher_number: str,
    debit_ledger: str,
    credit_ledger: str,
    amount: float,
    narration: str,
    company: str,
) -> str:
    """Build XML to create a Journal voucher.

    Debit (Yes/-amount), credit (No/+amount). See v4 Op 9.
    """
    _require(date, "date")
    _require(voucher_number, "voucher_number")
    _require(debit_ledger, "debit_ledger")
    _require(credit_ledger, "credit_ledger")
    _require(narration, "narration")
    _require(company, "company")
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")

    voucher_xml = f"""<VOUCHER VCHTYPE="Journal" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<NARRATION>{_esc(narration)}</NARRATION>
<VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
<VOUCHERNUMBER>{_esc(voucher_number)}</VOUCHERNUMBER>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(debit_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>{-amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(credit_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(tally): add build_create_receipt_voucher + build_create_journal_voucher"
```

---

### Task 9: Writer methods + 90s timeout bump

**Files:**
- Modify: `backend/tally_bridge/writer.py`
- Modify: `backend/tally_bridge/client.py`

- [ ] **Step 1: Bump client write timeout to 90s**

Read `backend/tally_bridge/client.py` first. Find the timeout setting and change from current value to **90.0** for write operations. If a single timeout governs all calls, raise it to 90s. (Reads are typically <1s; the bump is safe.) Add a comment: `# 90s — write operations can be slow per docs/tally-write-exploration-v4.md`.

- [ ] **Step 2: Add writer methods**

In `backend/tally_bridge/writer.py`, add imports and methods:

```python
from backend.tally_bridge.import_builder import (
    # ... existing imports ...
    build_create_unit,
    build_create_stock_group,
    build_create_stock_item,
    build_create_gst_ledger,
    build_create_sales_voucher,
    build_create_purchase_voucher,
    build_create_receipt_voucher,
    build_create_journal_voucher,
)
```

Then, inside the `TallyWriter` class:

```python
async def create_unit(self, name: str, formal_name: str) -> dict:
    xml = build_create_unit(name, formal_name, self.company)
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_stock_group(self, name: str, parent: str = "") -> dict:
    xml = build_create_stock_group(name, parent, self.company)
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_stock_item(
    self, name: str, group: str, uom: str, opening_qty: float,
    opening_rate: float, hsn_code: str, gst_rate: int,
) -> dict:
    xml = build_create_stock_item(
        name, group, uom, opening_qty, opening_rate, hsn_code, gst_rate, self.company,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_gst_ledger(self, name: str, duty_head: str) -> dict:
    xml = build_create_gst_ledger(name, duty_head, self.company)
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

# Override existing create_ledger to expose new kwargs:
async def create_ledger(
    self, name: str, parent: str, gstin: str | None = None,
    state: str | None = None, gst_reg_type: str | None = None,
    opening_balance: float | None = None, is_billwise: bool = False,
) -> dict:
    xml = build_create_ledger(
        name, parent, self.company, gstin=gstin, state=state,
        gst_reg_type=gst_reg_type, opening_balance=opening_balance,
        is_billwise=is_billwise,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_sales_voucher(
    self, date: str, voucher_number: str, party: str, items: list[tuple],
    narration: str, gst_mode: str = "intra",
) -> dict:
    xml = build_create_sales_voucher(
        date, voucher_number, party, items, narration, gst_mode, self.company,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_purchase_voucher(
    self, date: str, voucher_number: str, party: str, items: list[tuple],
    narration: str, gst_mode: str = "intra",
) -> dict:
    xml = build_create_purchase_voucher(
        date, voucher_number, party, items, narration, gst_mode, self.company,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_receipt_voucher(
    self, date: str, voucher_number: str, party: str, bank_ledger: str,
    amount: float, narration: str,
) -> dict:
    xml = build_create_receipt_voucher(
        date, voucher_number, party, bank_ledger, amount, narration, self.company,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)

async def create_journal_voucher(
    self, date: str, voucher_number: str, debit_ledger: str, credit_ledger: str,
    amount: float, narration: str,
) -> dict:
    xml = build_create_journal_voucher(
        date, voucher_number, debit_ledger, credit_ledger, amount, narration, self.company,
    )
    response_xml = await self.client.post_xml(xml)
    return parse_import_response(response_xml)
```

- [ ] **Step 3: Verify existing writer tests still pass**

```bash
PYTHONPATH=. pytest tests/unit/test_writer.py tests/unit/test_import_builder.py -v
```

Existing `create_ledger` callers may break because we added kwargs — verify the signature change is back-compat (positional `name, parent, gstin` still works since `gstin` was already a kwarg). Update any test that uses `gstin=` positionally.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(tally): writer methods for unit/stock_group/stock_item/gst_ledger/sales/purchase/receipt/journal + 90s timeout"
```

---

### Task 10: Seeder script — `scripts/seed_tally_data.py`

**Files:**
- Create: `scripts/seed_tally_data.py`

- [ ] **Step 1: Implement the seeder**

```python
#!/usr/bin/env python3
"""Seed a fresh Tally company with the Bharat Traders dataset.

PREREQUISITE: An empty company "Bharat Traders Private Limited" must already exist
in Tally UI (Create-Company has no documented import envelope). FY 2025-04-01 to
2026-03-31, Maharashtra, GSTIN 27AABCB1234F1ZP, GST registration Regular,
no company-default GST rate.

⚠ ONE-SHOT per company. Per docs/tally-write-exploration-v4.md, once any master is
referenced by a voucher, Tally permanently locks it. To iterate, restore from a
fresh backup or recreate the company.

Usage:
    PYTHONPATH=. python scripts/seed_tally_data.py \\
        --host localhost --port 9000 \\
        --company "Bharat Traders Private Limited"
    # add --dry-run to print XML without POSTing
    # add --phases groups,units,stock_groups,gst_ledgers,ledgers,stock_items,vouchers
    #   to run a subset (default: all phases in this order)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Iterable

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyResponseError
from backend.tally_bridge.writer import TallyWriter
from scripts.seed_data import bharat_traders as bt

OFFICE_SUPPLY_ITEMS = {
    "A4 Paper Ream 500 sheets", "Whiteboard Marker Set",
    "Stapler Heavy Duty", "Box File Pack of 10", "Pen Drive 32GB",
}
PHASES_DEFAULT = ["groups", "units", "stock_groups", "gst_ledgers", "ledgers", "stock_items", "vouchers"]


def _sales_ledger(item_name: str) -> str:
    return "Sales - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Sales - Electronics"


def _purchase_ledger(item_name: str) -> str:
    return "Purchase - Office Supplies" if item_name in OFFICE_SUPPLY_ITEMS else "Purchase - Electronics"


def _item_meta() -> dict[str, dict]:
    """Build {name: {uom, hsn, gst_rate}} lookup from STOCK_ITEMS."""
    return {
        name: {"uom": uom, "hsn": hsn, "gst_rate": gst}
        for name, _grp, uom, _sell, _oq, _or, _ov, hsn, gst in bt.STOCK_ITEMS
    }


def _build_voucher_items(
    invoice_lines: list[tuple], meta: dict, ledger_fn,
) -> list[tuple]:
    """Convert (item_name, qty, rate) list into builder tuple format."""
    return [
        (name, qty, rate, ledger_fn(name), meta[name]["uom"], meta[name]["gst_rate"])
        for name, qty, rate in invoice_lines
    ]


async def _phase_groups(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Groups ({len(bt.GROUPS)}) ===")
    for name, parent in bt.GROUPS:
        print(f"  + {name} (parent: {parent})")
        if not dry_run:
            await writer.create_group(name=name, parent=parent)


async def _phase_units(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Units ({len(bt.UNITS)}) ===")
    for name, formal in bt.UNITS:
        print(f"  + {name} ({formal})")
        if not dry_run:
            await writer.create_unit(name=name, formal_name=formal)


async def _phase_stock_groups(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Stock Groups ({len(bt.STOCK_GROUPS)}) ===")
    for name, parent in bt.STOCK_GROUPS:
        print(f"  + {name}")
        if not dry_run:
            await writer.create_stock_group(name=name, parent=parent)


async def _phase_gst_ledgers(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: GST Ledgers ({len(bt.GST_LEDGERS)}) ===")
    for name, duty_head in bt.GST_LEDGERS:
        print(f"  + {name} ({duty_head})")
        if not dry_run:
            await writer.create_gst_ledger(name=name, duty_head=duty_head)


async def _phase_ledgers(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Ledgers ({len(bt.LEDGERS)}) ===")
    for name, parent, opening, state, gstin, gst_reg in bt.LEDGERS:
        is_billwise = parent in (
            "North Zone Debtors", "South Zone Debtors",
            "National Creditors", "Local Creditors",
        )
        print(f"  + {name} (parent: {parent}, opening: {opening})")
        if not dry_run:
            await writer.create_ledger(
                name=name, parent=parent, gstin=gstin, state=state,
                gst_reg_type=gst_reg, opening_balance=opening if opening else None,
                is_billwise=is_billwise,
            )


async def _phase_stock_items(writer: TallyWriter, dry_run: bool):
    print(f"\n=== Phase: Stock Items ({len(bt.STOCK_ITEMS)}) ===")
    for name, group, uom, _sell_rate, open_qty, open_rate, _open_val, hsn, gst_rate in bt.STOCK_ITEMS:
        print(f"  + {name} (HSN {hsn}, GST {gst_rate}%)")
        if not dry_run:
            await writer.create_stock_item(
                name=name, group=group, uom=uom,
                opening_qty=open_qty, opening_rate=open_rate,
                hsn_code=hsn, gst_rate=gst_rate,
            )


async def _phase_vouchers(writer: TallyWriter, dry_run: bool):
    meta = _item_meta()

    # Combine all vouchers with a sort key (date) so chronological order is preserved.
    sales = [("S", v) for v in bt.SALES_INVOICES]
    purchases = [("P", v) for v in bt.PURCHASE_INVOICES]
    payments = [("PMT", v) for v in bt.PAYMENTS]
    receipts = [("R", v) for v in bt.RECEIPTS]
    all_vouchers = sales + purchases + payments + receipts
    all_vouchers.sort(key=lambda x: x[1][1])  # date is index 1 in every tuple

    print(f"\n=== Phase: Vouchers ({len(all_vouchers)}) ===")
    for kind, v in all_vouchers:
        if kind == "S":
            vnum, date, party, lines, _total, narration = v
            items = _build_voucher_items(lines, meta, _sales_ledger)
            print(f"  + Sales {vnum} {date} {party} ({len(lines)} lines)")
            if not dry_run:
                await writer.create_sales_voucher(
                    date=date, voucher_number=vnum, party=party,
                    items=items, narration=narration, gst_mode="intra",
                )
        elif kind == "P":
            vnum, date, party, lines, _total, narration = v
            items = _build_voucher_items(lines, meta, _purchase_ledger)
            print(f"  + Purchase {vnum} {date} {party} ({len(lines)} lines)")
            if not dry_run:
                await writer.create_purchase_voucher(
                    date=date, voucher_number=vnum, party=party,
                    items=items, narration=narration, gst_mode="intra",
                )
        elif kind == "PMT":
            vnum, date, payee, bank, amount, narration = v
            print(f"  + Payment {vnum} {date} {payee} ₹{amount}")
            if not dry_run:
                # Payment = debit payee, credit bank
                await writer.create_payment_voucher(
                    date=date, debit_ledger=payee, credit_ledger=bank,
                    amount=amount, narration=narration,
                )
        elif kind == "R":
            vnum, date, party, bank, amount, narration = v
            print(f"  + Receipt {vnum} {date} {party} ₹{amount}")
            if not dry_run:
                await writer.create_receipt_voucher(
                    date=date, voucher_number=vnum, party=party,
                    bank_ledger=bank, amount=amount, narration=narration,
                )


PHASE_FNS = {
    "groups": _phase_groups,
    "units": _phase_units,
    "stock_groups": _phase_stock_groups,
    "gst_ledgers": _phase_gst_ledgers,
    "ledgers": _phase_ledgers,
    "stock_items": _phase_stock_items,
    "vouchers": _phase_vouchers,
}


async def run(host: str, port: int, company: str, phases: list[str], dry_run: bool):
    client = TallyClient(host=host, port=port)
    writer = TallyWriter(client=client, company=company)

    print(f"Seeding {company} @ {host}:{port}")
    if dry_run:
        print("(DRY-RUN — no POST)\n")

    for phase in phases:
        if phase not in PHASE_FNS:
            print(f"  unknown phase: {phase}", file=sys.stderr)
            sys.exit(2)
        try:
            await PHASE_FNS[phase](writer, dry_run)
        except TallyResponseError as e:
            print(f"\n!! TallyResponseError in phase {phase}: {e}", file=sys.stderr)
            print("   Stopping. Inspect Tally UI before re-running.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n!! Unexpected error in phase {phase}: {e!r}", file=sys.stderr)
            sys.exit(1)

    print("\nDone.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--company", default=bt.COMPANY_NAME)
    p.add_argument("--phases", default=",".join(PHASES_DEFAULT),
                   help=f"comma-sep subset of {PHASES_DEFAULT}")
    p.add_argument("--dry-run", action="store_true",
                   help="build + log XML, do not POST")
    args = p.parse_args()
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    asyncio.run(run(args.host, args.port, args.company, phases, args.dry_run))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run the seeder against the live host (no POST, just structure check)**

```bash
PYTHONPATH=. python scripts/seed_tally_data.py --dry-run 2>&1 | tee docs/seed-dry-run.log
```

Expected: full phase listing without errors. Exit code 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_tally_data.py docs/seed-dry-run.log
git commit -m "feat(seed): orchestrator script with phased dependency order + dry-run"
```

---

### Task 11: Live seed run against `Bharat Traders Private Limited`

**Files:** none (live execution)

⚠ This is the irreversible step. The plan says one-shot per company.

- [ ] **Step 1: Pre-flight — confirm fresh company**

```bash
PYTHONPATH=. python scripts/test_tally_connection.py
```

Expected: `Bharat Traders Private Limited` in company list, only 2 default ledgers (Cash, Profit & Loss A/c). If `Bharat Traders V0` is also listed, it's the renamed Stage 0 leftover and will not be touched.

- [ ] **Step 2: Run the seeder live**

```bash
PYTHONPATH=. python scripts/seed_tally_data.py 2>&1 | tee docs/seed-live-run.log
```

Expected: every phase prints `+ <name>` lines without trailing exception. Total ~100 entities created (4 groups + 2 units + 3 stock groups + 6 GST ledgers + 33 ledgers + 15 stock items + 16 sales + 8 purchase + 16 payments + 10 receipts = 113 entities, ~50 vouchers).

If a phase fails partway:
- Read the error in the log.
- Inspect the offending entity in Tally UI.
- DO NOT just re-run — masters created so far become locked once vouchers reference them. Restart by deleting and recreating the company in Tally UI, then re-running the full seeder.

- [ ] **Step 3: Eyeball verification in Tally UI** (manual, ~2 minutes)

User checks:
- Trial Balance shows non-zero figures across debtors, creditors, sales, purchase, capital, banks.
- Stock Summary shows 15 items across 3 groups.
- Day Book for Oct 2025 – Mar 2026 shows ~50 vouchers.
- Open one Sales voucher and verify CGST/SGST line items are present and rates look right (this is the v4 doc's residual unknown — `IGSTRATE`/`CGSTRATE`/`SGSTRATE` round-trip via UI).

- [ ] **Step 4: Commit log**

```bash
git add docs/seed-live-run.log
git commit -m "docs(seed): Stage 1 live seeder run log"
```

---

### Task 12: Tier-3 read-side verification — `scripts/verify_tally_bridge_live.py`

**Files:**
- Create: `scripts/verify_tally_bridge_live.py`

This calls the read-path tally_bridge functions against the seeded company and asserts shape + count. No Claude API.

- [ ] **Step 1: Implement**

```python
#!/usr/bin/env python3
"""Tier-3 verification: hit every read query against the seeded company.

Usage:
    PYTHONPATH=. python scripts/verify_tally_bridge_live.py \\
        --host localhost --port 9000

Asserts shape + counts of:
  - companies, ledgers, groups, stock items
  - trial balance totals
  - day book voucher count
  - bills receivable / payable totals
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries import masters, reports, vouchers


async def run(host: str, port: int, company: str):
    client = TallyClient(host=host, port=port)
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = ""):
        status = "OK" if condition else "FAIL"
        print(f"  [{status}] {name}{(' — ' + detail) if detail else ''}")
        if not condition:
            failures.append(name)

    print(f"Verifying {company} @ {host}:{port}\n")

    # 1. Companies
    companies = await masters.list_companies(client)
    check("list_companies includes target", company in [c.get("name", "") for c in companies],
          f"got {[c.get('name', '') for c in companies]}")

    # 2. Ledgers
    ledger_list = await masters.list_ledgers(client)
    check("list_ledgers has >= 35 entries", len(ledger_list) >= 35,
          f"got {len(ledger_list)}")

    # 3. Stock items
    stock_items = await masters.list_stock_items(client)
    check("list_stock_items has 15", len(stock_items) == 15,
          f"got {len(stock_items)}")

    # 4. Trial balance
    tb = await reports.get_trial_balance(client, from_date="01-04-2025", to_date="31-03-2026")
    check("trial_balance has rows", len(tb.get("rows", [])) > 0,
          f"got {len(tb.get('rows', []))}")

    # 5. Day book voucher count
    db = await vouchers.get_day_book(client, from_date="01-10-2025", to_date="15-03-2026")
    n = len(db.get("vouchers", []))
    check("day_book has >= 50 vouchers", n >= 50, f"got {n}")

    # 6. Bills receivable / payable
    br = await reports.get_bills_receivable(client)
    bp = await reports.get_bills_payable(client)
    check("bills_receivable non-empty", len(br.get("bills", [])) > 0)
    check("bills_payable non-empty", len(bp.get("bills", [])) > 0)

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    print("All verification checks passed.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--company", default="Bharat Traders Private Limited")
    args = p.parse_args()
    asyncio.run(run(args.host, args.port, args.company))


if __name__ == "__main__":
    main()
```

NOTE: import paths (`masters.list_companies`, `reports.get_trial_balance`, etc.) must match the actual module structure. Before writing the file, run:

```bash
grep -rn "^def list_ledgers\|^def list_stock_items\|^def get_trial_balance\|^def get_day_book\|^def get_bills_receivable\|^def get_bills_payable\|^def list_companies\|^def get_companies" backend/tally_bridge/queries/
```

and adjust function names / args to match what's actually defined. If a query returns a different shape, update assertions accordingly.

- [ ] **Step 2: Run it**

```bash
PYTHONPATH=. python scripts/verify_tally_bridge_live.py 2>&1 | tee docs/tally-bridge-live-verify.log
```

Expected: all checks `[OK]`. Any `[FAIL]` indicates a seed-data discrepancy or a read-path bug — investigate before declaring Stage 1 complete.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_tally_bridge_live.py docs/tally-bridge-live-verify.log
git commit -m "feat(seed): tier-3 live read-side verification script + log"
```

---

### Task 13: Update memory + close-out

**Files:**
- Modify: `/Users/ripu/.claude/projects/-Users-ripu-work-nuvanta-repos-tally-agent/memory/MEMORY.md`
- Create: `/Users/ripu/.claude/projects/-Users-ripu-work-nuvanta-repos-tally-agent/memory/stage_1_seeder.md`

- [ ] **Step 1: Write `memory/stage_1_seeder.md` with status, deliverables, and follow-ups**

Include:
- Status: COMPLETE on `<date>`
- Live seed entity counts (groups, units, stock groups, GST ledgers, ledgers, stock items, vouchers)
- Tier-3 verification result
- Known follow-ups: (a) Stage 2 backup distribution, (b) per-line GST rate auto-compute on vouchers (currently we emit explicit tax lines), (c) IGSTRATE/CGSTRATE/SGSTRATE round-trip not observable via NATIVEMETHOD GSTDetails.

- [ ] **Step 2: Update `MEMORY.md` index**

Add line under "Phase Summary":
```
| Tally seed Stage 1 (seeder build + run) | COMPLETE <date> | See `memory/stage_1_seeder.md` |
```

Update "Current Status" section accordingly.

- [ ] **Step 3: Commit**

```bash
git add ...
git commit -m "docs(seed): close Stage 1 — Bharat Traders seeded + verified"
```

---

## Self-review checklist (run before handoff)

1. **Spec coverage:** every Stage 1 deliverable in `docs/plans/2026-05-04-tally-seed-data-plan.md` is mapped to a task above:
   - Builders: Tasks 2-8 ✓
   - Writer methods + 90s timeout: Task 9 ✓
   - Seed data extraction: Task 1 ✓
   - Seeder script: Task 10 ✓
   - Live run: Task 11 ✓
   - Tier-3 verify: Task 12 ✓
   - Memory close-out: Task 13 ✓
   - **Deferred (intentional, called out in plan header):** mock_handler import support, Tier-2 seeder integration test, fixture regeneration to include GST.
2. **Placeholder scan:** no "TBD"/"implement later"/"similar to Task N"/"add error handling" — every code step has full code.
3. **Type consistency:** builder/writer signatures match across tasks. Voucher item tuple `(name, qty, rate, ledger, uom, gst_rate)` is consistent in Tasks 6, 7, 10. Ledger tuple `(name, parent, opening, state, gstin, gst_reg_type)` consistent in Tasks 1, 10. Stock item tuple `(name, group, uom, sell_rate, open_qty, open_rate, open_val, hsn, gst_rate)` consistent in Tasks 1, 4, 10.

## Risks / known unknowns

1. **Sales/purchase voucher rejection on first live POST.** Mitigation: dry-run prints XML so issues can be diffed against `tally-write-exploration-v4.md`. If a voucher fails, halt — don't continue (would create orphan masters that lock).
2. **GST rate round-trip.** v4 doc notes `IGSTRATE`/`CGSTRATE`/`SGSTRATE` not echoed via `NATIVEMETHOD GSTDetails`. Visual UI check in Task 11 Step 3 confirms rates persisted.
3. **Read-path query name mismatches in `verify_tally_bridge_live.py`.** Mitigation: explicit grep + adjust step before the file is finalised.
4. **Voucher number collisions.** Tally auto-generates voucher numbers per type when `<VOUCHERNUMBER>` is present — using S001..S016 etc. should be unique within type. If Tally rejects, drop `VOUCHERNUMBER` and let Tally auto-number.
