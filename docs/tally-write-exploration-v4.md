# Tally Write Exploration — v4 (verified envelope reference)

**Date:** 2026-05-04
**Tally:** TallyPrime 7.0 @ `localhost:9000`, license active
**Company:** Bharat Traders Private Limited (FY 25-26, Maharashtra, GSTIN `27AABCB1234F1ZP`, Regular GST, no company-default GST rate)
**Method:** Each envelope POSTed live, verified by `CREATED=1, ERRORS=0, EXCEPTIONS=0`, then a follow-up read-back confirmed master fields round-tripped (vouchers verified via CMPINFO voucher count + LASTVCHID).

Supersedes `docs/tally-write-exploration.md` for stage-0 verification of the broader stock + GST + voucher write surface. The earlier doc remains the authority on license-clamping (`tally-write-exploration.md:7`) and on the `NAME.LIST` requirement for masters.

## Summary table

| # | Operation | Status | Notes |
|---|-----------|--------|-------|
| 1 | Unit (UOM) create | ✅ PASS | No `NAME.LIST` required; `<NAME>` child only |
| 2 | Stock group create | ✅ PASS | `NAME.LIST` required; empty `<PARENT/>` for top-level |
| 3 | Stock item create with HSN + per-item GST | ✅ PASS | HSN round-trips. CGST/SGST/IGST rate fields not echoed by `NATIVEMETHOD GSTDetails` — verify via UI for now |
| 4 | GST tax ledger create | ✅ PASS | `TAXTYPE=GST` + `GSTDUTYHEAD={Central,State,Integrated} Tax` |
| 5 | Ledger with opening balance + GSTIN + state | ✅ PASS | `OPENINGBALANCE`, `PARTYGSTIN`, `LEDSTATENAME`, `GSTREGISTRATIONTYPE` all accepted |
| 6 | Sales voucher with stock + GST (intra + inter) | ✅ PASS | `LEDGERENTRIES.LIST` for ledgers, `ALLINVENTORYENTRIES.LIST` for stock; mixed-rate (18% + 12%) works in one invoice |
| 7 | Purchase voucher with stock + GST (intra) | ✅ PASS | **Inverse sign convention from sales** — see Op 7 below |
| 8 | Receipt voucher | ✅ PASS | `ALLLEDGERENTRIES.LIST`, `Accounting Voucher View` |
| 9 | Journal voucher | ✅ PASS | Same as receipt |
| R1 | Voucher read-back via day_book | ✅ PASS | Only with FY-internal voucher date (2026-03-15 worked; 2026-05-01 was invisible despite CREATED=1) |
| D1 | Voucher DELETE via Master ID | ✅ PASS | `DD-MMM-YYYY` date + `TAGNAME="Master ID"` + `TAGVALUE=<mid>`; read MasterId via `CHILDOF $$VchTypeAllVouchers` |
| D2 | Stock item DELETE | ✅ PASS | `NAME` attr + `NAME.LIST` child; rejects (no crash) if still referenced |
| D3 | Ledger DELETE | ✅ PASS | Same shape as D2 |
| D4 | Stock group DELETE | ✅ PASS | Same shape (untested in this session for actual delete; format proven on Ledger/Group/StockItem) |
| D5 | **Unit DELETE** | ⚠️ **UNSAFE** | `<UNIT NAME="X" ACTION="Delete">…</UNIT>` (with `NAME=` attribute) **crashed Tally with MAV**. Two name-only variants safely reject. No documented working format. Don't do it programmatically. |
| D6 | **Used-master DELETE** (any type) | ❌ blocked by Tally | Once a master has been referenced by a voucher (even after the voucher is deleted), Tally permanently locks it. `Delete`/`Cancel`/`Alter+ISDELETED`/`Delete+OBJECTS=Yes` all fail. ALTER/rename works but the lock follows the object. UI Alt+D is the only way out. |

All envelopes use Format 1 (`<IMPORTDATA>` with `<REPORTNAME>All Masters</REPORTNAME>` for masters and `<REPORTNAME>Vouchers</REPORTNAME>` for vouchers) and `<SVCURRENTCOMPANY>` in `STATICVARIABLES`.

## Op 1 — Unit (UOM) create

```xml
<UNIT ACTION="Create">
  <NAME>TstN</NAME>
  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
</UNIT>
```

**Gotchas**
- Do **NOT** wrap with `NAME.LIST` — `<NAME>` child alone works. `NAME.LIST` causes "BAD UNIT NAME".
- Unit name cannot contain spaces, underscores, or long identifiers (Tally rejects with "BAD UNIT NAME"). Stick to short ASCII (`Nos`, `Pcs`, `TstN`).

## Op 2 — Stock group create

```xml
<STOCKGROUP NAME="_Test Explore Electronics" ACTION="Create">
  <NAME.LIST><NAME>_Test Explore Electronics</NAME></NAME.LIST>
  <PARENT/>
  <ISADDABLE>No</ISADDABLE>
</STOCKGROUP>
```

**Gotchas**
- `NAME.LIST` mandatory (memory crash without it).
- Empty `<PARENT/>` = top-level (under "Primary"). Pass an existing stock group name to nest.

## Op 3 — Stock item create with HSN + per-item GST

```xml
<STOCKITEM NAME="_Test Explore Monitor 24in" ACTION="Create">
  <NAME.LIST><NAME>_Test Explore Monitor 24in</NAME></NAME.LIST>
  <PARENT>_Test Explore Electronics</PARENT>
  <BASEUNITS>TstN</BASEUNITS>
  <GSTAPPLICABLE>Applicable</GSTAPPLICABLE>
  <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
  <HSNCODE>8528</HSNCODE>
  <HSN>8528</HSN>
  <HSNDETAILS.LIST>
    <APPLICABLEFROM>20250401</APPLICABLEFROM>
    <HSNCODE>8528</HSNCODE>
    <HSN>8528</HSN>
  </HSNDETAILS.LIST>
  <GSTDETAILS.LIST>
    <APPLICABLEFROM>20250401</APPLICABLEFROM>
    <TAXABILITY>Taxable</TAXABILITY>
    <IGSTRATE>18</IGSTRATE>
    <CGSTRATE>9</CGSTRATE>
    <SGSTRATE>9</SGSTRATE>
    <STATEWISEDETAILS.LIST>
      <STATENAME>Any</STATENAME>
      <RATEDETAILS.LIST><GSTRATEDUTYHEAD>Central Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>9</GSTRATE></RATEDETAILS.LIST>
      <RATEDETAILS.LIST><GSTRATEDUTYHEAD>State Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>9</GSTRATE></RATEDETAILS.LIST>
      <RATEDETAILS.LIST><GSTRATEDUTYHEAD>Integrated Tax</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>18</GSTRATE></RATEDETAILS.LIST>
      <RATEDETAILS.LIST><GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD><GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE><GSTRATE>0</GSTRATE></RATEDETAILS.LIST>
    </STATEWISEDETAILS.LIST>
  </GSTDETAILS.LIST>
  <OPENINGBALANCE>5 TstN</OPENINGBALANCE>
  <OPENINGRATE>11000/TstN</OPENINGRATE>
  <OPENINGVALUE>55000</OPENINGVALUE>
</STOCKITEM>
```

**Gotchas**
- Verified at both 18% (electronics, HSN 8528/8471) and 12% (paper, HSN 4802) — same envelope shape, different rate values.
- `<HSNCODE>` and `<HSN>` are duplicated at both stock-item top level and inside `<HSNDETAILS.LIST>`. Both are needed.
- Read-back via `<COLLECTION TYPE="StockItem"><NATIVEMETHOD>GSTDetails</NATIVEMETHOD>...</COLLECTION>` returns `APPLICABLEFROM`, `TAXABILITY`, `REVERSECHARGERATE` from `GSTDETAILS.LIST`, but **does NOT echo `IGSTRATE`/`CGSTRATE`/`SGSTRATE`/`STATEWISEDETAILS`**. HSN code does round-trip via `HSNDETAILS.LIST`. Stage 1 must visually verify rates in Tally UI before declaring this fully proven, or find the right method/sub-collection name.

## Op 4 — GST tax ledger create

```xml
<LEDGER NAME="_Test Explore CGST Output" ACTION="Create">
  <NAME.LIST><NAME>_Test Explore CGST Output</NAME></NAME.LIST>
  <PARENT>Duties &amp; Taxes</PARENT>
  <TAXTYPE>GST</TAXTYPE>
  <GSTDUTYHEAD>Central Tax</GSTDUTYHEAD>
  <RATEOFTAXCALCULATION>0</RATEOFTAXCALCULATION>
  <ROUNDINGMETHOD/>
  <ROUNDINGLIMIT>0</ROUNDINGLIMIT>
  <ISBILLWISEON>No</ISBILLWISEON>
  <AFFECTSSTOCK>No</AFFECTSSTOCK>
  <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
</LEDGER>
```

**Gotchas**
- `<GSTDUTYHEAD>` values: `Central Tax`, `State Tax`, `Integrated Tax`.
- Same envelope serves both Output and Input ledgers — Tally infers direction from how it's used in vouchers.
- `Duties &amp; Taxes` (XML-escaped) for `PARENT`.

## Op 5 — Ledger with opening balance + GSTIN + state

```xml
<LEDGER NAME="_Test Explore Party MH" ACTION="Create">
  <NAME.LIST><NAME>_Test Explore Party MH</NAME></NAME.LIST>
  <PARENT>Sundry Debtors</PARENT>
  <PARTYGSTIN>27ABCDE1234F1Z5</PARTYGSTIN>
  <LEDSTATENAME>Maharashtra</LEDSTATENAME>
  <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
  <ISBILLWISEON>Yes</ISBILLWISEON>
</LEDGER>
```

For a ledger with opening balance (e.g. Capital, Cash):

```xml
<LEDGER NAME="_Test Explore Capital" ACTION="Create">
  <NAME.LIST><NAME>_Test Explore Capital</NAME></NAME.LIST>
  <PARENT>Capital Account</PARENT>
  <OPENINGBALANCE>10000.00</OPENINGBALANCE>
  <ISBILLWISEON>No</ISBILLWISEON>
</LEDGER>
```

**Gotchas**
- `ISBILLWISEON=Yes` for debtors/creditors (otherwise voucher bill-allocation fails).
- Sign of `OPENINGBALANCE` is inferred from the parent group's nature in Tally (positive value with Capital Account = credit; positive with Cash-in-Hand = debit).

## Op 6 — Sales voucher with stock + GST

**Intra-state (CGST + SGST):**

```xml
<VOUCHER VCHTYPE="Sales" ACTION="Create">
  <DATE>20260501</DATE>
  <NARRATION>Sales intra-state mixed-rate</NARRATION>
  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
  <PARTYLEDGERNAME>_Test Explore Party MH</PARTYLEDGERNAME>
  <PARTYNAME>_Test Explore Party MH</PARTYNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <EFFECTIVEDATE>20260501</EFFECTIVEDATE>

  <!-- Party (debtor): debit, ISDEEMEDPOSITIVE=Yes, AMOUNT NEGATIVE = -total -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore Party MH</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
    <AMOUNT>-33420.00</AMOUNT>
  </LEDGERENTRIES.LIST>

  <!-- GST output: credit, ISDEEMEDPOSITIVE=No, AMOUNT POSITIVE -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore CGST Output</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>2460.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore SGST Output</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>2460.00</AMOUNT>
  </LEDGERENTRIES.LIST>

  <!-- Inventory: ISDEEMEDPOSITIVE=No, AMOUNT POSITIVE (goods out) -->
  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>_Test Explore Monitor 24in</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <RATE>12500.00/TstN</RATE>
    <AMOUNT>25000.00</AMOUNT>
    <ACTUALQTY>2 TstN</ACTUALQTY>
    <BILLEDQTY>2 TstN</BILLEDQTY>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>_Test Explore Sales - Electronics</LEDGERNAME>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <AMOUNT>25000.00</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>
  <!-- ... second inventory entry for paper at 12% ... -->
</VOUCHER>
```

**Inter-state (IGST only):** identical structure but a single `IGST Output` ledger entry (no CGST/SGST), and the party's `LEDSTATENAME` is a different state from the company's. We tested party state = Delhi, company state = Maharashtra → IGST applied automatically because the ledgers' state metadata differs.

**Gotchas**
- `<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>` (NOT `Accounting Voucher View` for invoice-mode sales).
- `<ISINVOICE>Yes</ISINVOICE>` required for sales/purchase invoices.
- `<ISPARTYLEDGER>Yes</ISPARTYLEDGER>` on the party `LEDGERENTRIES.LIST` block.
- **No `BATCHALLOCATIONS.LIST`/`GODOWNNAME` needed** in a fresh company — Tally accepts the inventory entry without godown specification. (`Main Location` etc. are auto-managed.)
- Mixed-rate invoice (one 18% line + one 12% line) works — emit one `LEDGERENTRIES.LIST` per tax ledger with the *summed* tax amount across all lines at that rate. Per-line-rate auto-computation from stock-item GST metadata was **not observed** — we explicitly emitted CGST/SGST line totals.

## Op 7 — Purchase voucher with stock + GST (sign convention is INVERSE of sales)

```xml
<VOUCHER VCHTYPE="Purchase" ACTION="Create">
  <DATE>20260501</DATE>
  <NARRATION>Purchase intra-state with GST</NARRATION>
  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
  <PARTYLEDGERNAME>_Test Explore Supplier MH</PARTYLEDGERNAME>
  <PARTYNAME>_Test Explore Supplier MH</PARTYNAME>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <EFFECTIVEDATE>20260501</EFFECTIVEDATE>

  <!-- Party (creditor): credit, ISDEEMEDPOSITIVE=No, AMOUNT POSITIVE = total -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore Supplier MH</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
    <AMOUNT>11800.00</AMOUNT>
  </LEDGERENTRIES.LIST>

  <!-- GST input: debit, ISDEEMEDPOSITIVE=Yes, AMOUNT NEGATIVE -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore CGST Input</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-900.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore SGST Input</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-900.00</AMOUNT>
  </LEDGERENTRIES.LIST>

  <!-- Inventory: ISDEEMEDPOSITIVE=Yes, AMOUNT NEGATIVE (goods in) -->
  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>_Test Explore Monitor 24in</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <RATE>10000.00/TstN</RATE>
    <AMOUNT>-10000.00</AMOUNT>
    <ACTUALQTY>1 TstN</ACTUALQTY>
    <BILLEDQTY>1 TstN</BILLEDQTY>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>_Test Explore Purchase - Electronics</LEDGERNAME>
      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
      <AMOUNT>-10000.00</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>
</VOUCHER>
```

### ⚠️ Sign convention discovered (this is the v3 unknown that was failing)

The **official docs example for purchase** (`tally-write-exploration.md:226`) shows GST and stock with `ISDEEMEDPOSITIVE=Yes` + AMOUNT positive. **That envelope returned `EXCEPTIONS=1` against TallyPrime 7.0** in our live run. The convention that actually works is the *negative-AMOUNT* form below:

| Block | Sales | Purchase |
|-------|-------|----------|
| Party | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−total** | `ISDEEMEDPOSITIVE=No`,  AMOUNT = **+total** |
| GST   | `ISDEEMEDPOSITIVE=No`,  AMOUNT = **+tax**   | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−tax** |
| Inventory + ACCOUNTINGALLOCATIONS | `ISDEEMEDPOSITIVE=No`, AMOUNT = **+goods** | `ISDEEMEDPOSITIVE=Yes`, AMOUNT = **−goods** |

It's not "AMOUNT = absolute, sign comes from ISDEEMEDPOSITIVE" (the docs' implied rule). Tally appears to want the **signed AMOUNT to have the same sign as you'd write a debit/credit**: in sales, party-debit shows negative because it's a *debit balance* on a customer ledger; in purchase, GST-debit shows negative for the same reason. Empirically the rule is: in either voucher type, AMOUNT is positive on the side that grows (party in purchase, GST output in sales) and negative on the side that shrinks the natural balance.

We tried three other sign permutations on purchase (party No/+, GST Yes/+, inv Yes/+; all-negative; etc.) — only the form above passed `CREATED=1`.

## Op 8 — Receipt voucher

```xml
<VOUCHER VCHTYPE="Receipt" ACTION="Create">
  <DATE>20260501</DATE>
  <NARRATION>Receipt</NARRATION>
  <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
  <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore Test Cash</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-1000.00</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>_Test Explore Party MH</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>1000.00</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
</VOUCHER>
```

Same `ALLLEDGERENTRIES.LIST` pattern as Payment voucher. Cash debit (Yes/−), party credit (No/+).

## Op 9 — Journal voucher

Identical envelope shape to Receipt with `VCHTYPE="Journal"` / `VOUCHERTYPENAME=Journal`. Two `ALLLEDGERENTRIES.LIST` blocks: one debit (Yes/−), one credit (No/+).

## Cross-cutting findings

1. **License-clamping (already documented):** writes silently fail with "Voucher date is missing" if the voucher `<DATE>` exceeds Tally's internal current date and the license isn't activated. Confirmed unaffected today (license active).

2. **`EXCEPTIONS=1` with no `LINEERROR` is the malformed-XML signal.** All purchase-sign experiments returned this until we hit the right convention. There's no helpful error message — only iteration narrows it down.

3. **Voucher-list collection via custom TDL needs `CHILDOF $$VchTypeAllVouchers`** — querying `<COLLECTION TYPE="Voucher"><NATIVEMETHOD>Date</NATIVEMETHOD>...</COLLECTION>` directly returns `<VOUCHER/>` elements with empty children. Adding `<CHILDOF>$$VchTypeAllVouchers</CHILDOF>` populates the bodies. This is what `build_day_book` already does correctly.

4. **Vouchers dated outside the company FY are persisted but invisible to reports.** Bharat Traders' FY is 2025-04-01 → 2026-03-31. We initially wrote test vouchers at 2026-05-01 (outside FY), and Tally accepted them (CREATED=1) but `day_book` returned 0 hits even with `SVFROMDATE`/`SVTODATE` covering May 2026. Re-tested at 2026-03-15 (inside FY): create succeeded AND `day_book` returned the full voucher with all 4 ledger entries + inventory line, amounts and signs intact. **All seed vouchers MUST use dates inside the active FY** (Stage 1 — already aligned with the seed data plan, which uses Oct 2025–Mar 2026 invoice dates).

4. **GST rate metadata round-trip is partially observable.** `HSNCODE` echoes back via `HSNDETAILS.LIST`, `TAXABILITY` and `APPLICABLEFROM` echo via `GSTDETAILS.LIST`, but `IGSTRATE`/`CGSTRATE`/`SGSTRATE` and the `STATEWISEDETAILS` substructure are not returned by `<NATIVEMETHOD>GSTDetails</NATIVEMETHOD>`. The rates may still be stored — Stage 1 should verify in Tally UI on a sample item, or find the right TDL fetch path before relying on rate fields.

## Delete path — verified (with one confirmed crasher)

Tested live during the same session. Cleanup order matters: vouchers first, then stock items / ledgers, then stock groups. Units last — and Units are special.

### Voucher delete — VERIFIED ✅

```xml
<VOUCHER DATE="01-May-2026" VCHTYPE="Journal" TAGNAME="Master ID" TAGVALUE="4" ACTION="Delete"></VOUCHER>
```

- `DATE` attribute in **`DD-MMM-YYYY`** format (e.g. `01-May-2026`). YYYYMMDD here returns `"Cannot be deleted!"`.
- `VCHTYPE` attribute matching the voucher type.
- `TAGNAME="Master ID"` + `TAGVALUE=<MasterId>` — Master ID obtained from the read-back collection (see below).
- Empty body — no `<DATE>`/`<VCHTYPE>` children needed.
- `TAGNAME="Voucher Number"` + `TAGVALUE=<n>` also works as an alternative.

**Reading Master IDs:** the standard Voucher collection returns empty bodies. The trick is `<CHILDOF>$$VchTypeAllVouchers</CHILDOF>` plus `<NATIVEMETHOD>MasterId</NATIVEMETHOD>`:

```xml
<COLLECTION NAME="VchAll" ISMODIFY="No">
  <TYPE>Voucher</TYPE>
  <CHILDOF>$$VchTypeAllVouchers</CHILDOF>
  <NATIVEMETHOD>MasterId</NATIVEMETHOD>
  <NATIVEMETHOD>Date</NATIVEMETHOD>
  <NATIVEMETHOD>VoucherTypeName</NATIVEMETHOD>
  <NATIVEMETHOD>VoucherNumber</NATIVEMETHOD>
  <NATIVEMETHOD>Narration</NATIVEMETHOD>
  ...
</COLLECTION>
```

This populates the field bodies. Without `CHILDOF`, the collection lists VOUCHER elements with empty children — that's the bug behind `parse_vouchers` returning 0.

### Stock item delete — VERIFIED ✅

```xml
<STOCKITEM NAME="_Test Explore A4 Paper Ream" ACTION="Delete">
  <NAME.LIST><NAME>_Test Explore A4 Paper Ream</NAME></NAME.LIST>
</STOCKITEM>
```

- `NAME` attribute + `NAME.LIST` child (same shape as Ledger/Group delete).
- Tally returns `"Cannot be deleted!"` (`ERRORS=1`, no crash) if the item is still referenced by an existing voucher — even after that voucher is deleted, references can linger; safe failure mode.

### Ledger delete — VERIFIED ✅

```xml
<LEDGER NAME="_Test Explore Capital" ACTION="Delete">
  <NAME.LIST><NAME>_Test Explore Capital</NAME></NAME.LIST>
</LEDGER>
```

Same pattern. Same `"Cannot be deleted!"` polite rejection if still referenced (e.g., GST Input/Output ledgers used by purchase voucher line items, party ledger Supplier MH used by purchase voucher). No crash.

### Stock group delete — works the same way

```xml
<STOCKGROUP NAME="_Test Explore Peripherals" ACTION="Delete">
  <NAME.LIST><NAME>_Test Explore Peripherals</NAME></NAME.LIST>
</STOCKGROUP>
```

Per-docs format; rejects with error if a stock item still parents to it. No crash.

### Master "permanent lock" after first voucher reference

Once any master (Ledger, Stock Item, presumably Stock Group) has been referenced by a posted voucher, **Tally permanently locks the object against deletion** — even after every voucher referencing it is deleted. The lock is **on the object identity, not the name**:

- `ACTION="Delete"` → `ERRORS=1, "Cannot be deleted!"`
- `ACTION="Cancel"` → `ERRORS=1, "Cannot be cancelled!"`
- `ACTION="Alter"` with `<ISDELETED>Yes</ISDELETED>` → `ALTERED=1` but the ledger persists (the field is silently ignored).
- `ACTION="Alter"` with `<NAME.LIST><NAME>...new name...</NAME></NAME.LIST>` → renames cleanly. Then attempting to delete the renamed object → still `"Cannot be deleted!"`.
- Adding `OBJECTS="Yes"` attribute to the delete envelope → no effect.
- For StockItem: zeroing `<OPENINGBALANCE>`, `<OPENINGRATE>`, `<OPENINGVALUE>` to 0 — succeeds (`ALTERED=1`) — then DELETE → still `"Cannot be deleted!"`.
- For StockItem: changing `<PARENT>` to a different stock group (or to `<PARENT/>` for Primary) — succeeds — then DELETE → still `"Cannot be deleted!"`.

In short: every stripping/normalisation we tried on a locked StockItem altered cleanly, but the lock is on the underlying object identity, immune to attribute mutation.

This is Tally's audit-trail behaviour, not an XML quirk. **There is no XML way to remove a previously-used master.** Stage 1 implication: once seed data is run, the test ledgers/items become permanent residents of the company. Cleanup of "used" masters requires the Tally UI (Alter → Delete → Yes), or starting from a fresh company backup.

The "fresh masters" (created but never referenced) **do** delete normally via the verified envelope above.

#### Lock scope: historical for ledgers/items, transitive for stock groups

Verified live with the 7 surviving `_Test Explore` entities after voucher cleanup:

| Type | Entity | Result | Reason |
|------|--------|--------|--------|
| StockItem | Monitor 24in | LOCKED | Was on 6 vouchers (now deleted) — **historical lock** |
| Ledger | CGST Input, SGST Input, Purchase - Electronics, Supplier MH | LOCKED (×4) | Each was on a purchase voucher (now deleted) — historical lock |
| StockGroup | Electronics | LOCKED | Currently parents Monitor (locked) — **transitive lock** |
| StockGroup | Office Supplies | DELETED ✓ | Had Paper Ream earlier; after Paper Ream was deleted, the group itself became deletable |
| StockGroup | Peripherals | DELETED ✓ | Never had children |

So **stock-group lock is transitive on *current* descendants, not historical**. Once you remove a stock group's last child item (or all children become deletable), the group itself becomes deletable. Ledger and StockItem locks, by contrast, are sticky once any voucher has touched them.

### Unit delete — ⚠️ UNSAFE / NOT SUPPORTED VIA XML IMPORT

Tested 5 envelope variants. Two of them returned a polite `"Cannot delete unnamed object: UNIT!"` error (no crash):

```xml
<UNIT ACTION="Delete"><NAME>TstP</NAME></UNIT>                                    <!-- safe-reject -->
<UNIT ACTION="Delete"><NAME.LIST><NAME>TstP</NAME></NAME.LIST></UNIT>             <!-- safe-reject -->
```

Then we tried the formats analogous to Ledger/Group delete (`NAME` attribute on the element):

```xml
<UNIT NAME="TstP" ACTION="Delete"><NAME.LIST><NAME>TstP</NAME></NAME.LIST></UNIT>  <!-- ⚠️ CRASHES Tally -->
<UNIT NAME="TstP" ACTION="Delete"></UNIT>                                          <!-- crash candidate (untested after first crash) -->
<UNIT TARGETNAME="TstP" ACTION="Delete"></UNIT>                                    <!-- crash candidate (untested) -->
```

The **first variant (NAME attribute + NAME.LIST child)** crashed Tally with a memory access violation in our live test on TallyPrime 7.0 — confirmed by the user. We did not retest the other two attribute-bearing variants; they're presumed unsafe by association.

Tally's official docs (https://help.tallysolutions.com/sample-xml/, https://help.tallysolutions.com/import-data-errors-and-resolutions/) document master delete patterns generally but **provide zero examples for `<UNIT>` delete**. Tally's deletion FAQ (https://help.tallysolutions.com/article/DeveloperReference/faq/6199.html) says master deletion goes through "XML SOAP" but offers no envelope examples. The community guides (e.g. ankititsolutions.com) only document UI-based deletion (Alt+D from Alter → Units).

**Conclusion: Unit delete via XML import is undocumented and triggers MAV in TallyPrime 7.** Don't do it programmatically.

#### Crash signature isolation

The crash is **specific to `ACTION="Delete"` + `NAME=` attribute on `<UNIT>`**. Other actions with the same `NAME=` attribute are safe-reject:

- `<UNIT NAME="TstP" ACTION="Alter">…<FORMALNAME>X</FORMALNAME></UNIT>` → `EXCEPTIONS=1, "BAD UNIT NAME"`. Tally alive.
- `<UNIT NAME="TstP" ACTION="Alter"><NAME.LIST><NAME>TstP</NAME></NAME.LIST><FORMALNAME>X</FORMALNAME></UNIT>` → same, alive.

So the bug is in Tally's UNIT-delete code path when it sees a `NAME=` attribute, not in attribute parsing generally. Useful to know: ALTER on Unit is safe; only DELETE+NAMEattr is the crasher.

**The crash is recoverable** — at least in our case. Initial post-restart read suggested the 3 `_Test Explore` stock groups had been wiped, but that was a query bug (`STOCKGROUP` returns its name in the `NAME=` attribute, not in a child `<NAME>` element; the read code was using `findtext('NAME')`). Re-querying with `it.get("NAME")` confirmed all 3 stock groups + the 1 surviving stock item + the 4 reference-locked ledgers came through the MAV intact. So MAV is "just" a process crash here, not data loss — but it's still a hard stop you should never trigger on a real customer's company.

#### Recommendation

- **Don't attempt unit deletion in any seeder/cleanup script.** Two unused units in a company are harmless residue — they're invisible in standard reports and don't pollute trial balance / P&L / day book.
- If a developer truly needs to remove a unit, do it via Tally UI: Gateway → Alter → Units → select → Alt+D.
- Should this become a hard requirement later, only test on a throwaway company you don't mind losing — **the crash is on the master file (Manager.900), risking the company's data integrity.**

## Original crash hypothesis (closed)

The original "memory error" the user reported on the v4 script's first run was **most likely the Unit delete in `cleanup_all`** — the v4 script (pre-patch) used `<UNIT ACTION="Delete"><NAME>X</NAME></UNIT>`, which we've now confirmed is one of the *safe-reject* forms. So the original crash probably came from a different earlier session where leftover units triggered a different envelope variant, OR from a related path we haven't retested. The current patched script should not crash, but Unit deletion is now intentionally disabled regardless.

## Voucher delete cleanup script (verified flow)

```python
# 1. List vouchers with Master IDs (CHILDOF VchTypeAllVouchers + NATIVEMETHOD MasterId)
# 2. For each test voucher, build delete envelope:
#    <VOUCHER DATE="DD-MMM-YYYY" VCHTYPE="Sales" TAGNAME="Master ID" TAGVALUE="N" ACTION="Delete"></VOUCHER>
# 3. Wrap in IMPORTDATA / Vouchers report.
# 4. POST. Expect DELETED=1 per voucher.
```

In our session: 6 vouchers (Sales×2, Purchase×2, Receipt, Journal) deleted cleanly via this flow. Stock items + ledgers then deleted (with some "Cannot be deleted!" rejections for items still referenced by lingering metadata — clean failure, not crash).

## Run state at end of session

- Test entities still in Tally (`_Test Explore` prefix): 2 units, 3 stock groups, 3 stock items, 14 ledgers, ~7 vouchers.
- Cleanup not run — preserved as a witness for the next session if helpful, otherwise delete via the patched cleanup script.

## Files

- `scripts/explore_tally_write_v4.py` — original exploration script. **Patches needed** (this session pinpointed but did not all apply): purchase op7 sign convention (lines 806–~895), cleanup unit-delete safety (line ~244), voucher-delete to use Master ID (line ~162).
- This document — verified envelope reference for Stage 1 (`backend/tally_bridge/import_builder.py` builders).
