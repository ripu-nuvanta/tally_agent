# Tally Write Exploration — Findings

**Date:** 2026-04-05
**Company:** NUVANTA AI TECHNOLOGIES PRIVATE LIMITED
**Tally:** localhost:9000

## Working XML Formats

### Ledger Creation (VERIFIED)

```xml
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>COMPANY NAME</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<LEDGER NAME="Ledger Name" ACTION="Create">
<NAME.LIST><NAME>Ledger Name</NAME></NAME.LIST>
<PARENT>Indirect Expenses</PARENT>
</LEDGER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>
```

**CRITICAL:** `<NAME.LIST><NAME>...</NAME></NAME.LIST>` is REQUIRED. Without it, creation silently fails with EXCEPTIONS=1 and CREATED=0.

### Payment Voucher Creation (VERIFIED)

```xml
<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>20260405</DATE>
<NARRATION>Description text</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Expense Ledger</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-500.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Cash</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>500.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
```

**Date format:** YYYYMMDD (not DD-MM-YYYY like queries).
**Amount sign:** Negative = debit (expense), Positive = credit (cash/bank).

## Response Format

```xml
<RESPONSE>
 <CREATED>1</CREATED>
 <ALTERED>0</ALTERED>
 <DELETED>0</DELETED>
 <LASTVCHID>301</LASTVCHID>
 <LASTMID>0</LASTMID>
 <COMBINED>0</COMBINED>
 <IGNORED>0</IGNORED>
 <ERRORS>0</ERRORS>
 <CANCELLED>0</CANCELLED>
 <EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>
```

**Success indicators:**
- `CREATED=1` (or `ALTERED=1`, `DELETED=1`) + `ERRORS=0` + `EXCEPTIONS=0`
- `LASTVCHID` returns Tally's internal voucher ID on voucher creation

**Failure indicators:**
- `EXCEPTIONS=1` — silent failure (usually bad XML format)
- `ERRORS=1` + `<LINEERROR>` — explicit error with message
- `LINEERROR` examples: `"Ledger 'XYZ' does not exist!"`

## GST Ledger Structure (Live Company)

| Ledger | Parent Group |
|--------|-------------|
| INPUT CGST | Duties & Taxes |
| INPUT SGST | Duties & Taxes |
| INPUT IGST | Duties & Taxes |
| OUTPUT CGST | Duties & Taxes |
| OUTPUTSGST | Duties & Taxes |
| OUTPUT IGST | Duties & Taxes |
| GST Payable | Duties & Taxes |

**Pattern:** Separate input/output ledgers per GST type. No rate-based sub-ledgers (e.g., no "CGST Input 9%").

## Cash/Bank Ledgers

- `Cash` (Cash-in-Hand)
- `Kotak Mahindra Bank Current A\c` (Bank Accounts)

## Existing Voucher Patterns

Payment vouchers use simple 2-entry structure:
- Debit entry: expense ledger (negative amount, ISDEEMEDPOSITIVE=Yes)
- Credit entry: bank ledger (positive amount, ISDEEMEDPOSITIVE=No)

## Voucher Cancel vs Delete (from official docs)

Tally supports three operations: `ACTION="Cancel"`, `ACTION="Delete"`, and `ACTION="Alter"`.

**Cancel** — marks voucher as cancelled (preserved in records, shows as cancelled):
```xml
<VOUCHER DATE="02-Apr-2008" TAGNAME="Voucher Number" TAGVALUE="3"
         VCHTYPE="Sales" ACTION="Cancel">
  <NARRATION>Being cancelled due to XYZ reasons</NARRATION>
</VOUCHER>
```

**Delete** — removes voucher entirely:
```xml
<VOUCHER DATE="02-Apr-2008" TAGNAME="Voucher Number" TAGVALUE="3"
         VCHTYPE="Sales" ACTION="Delete">
</VOUCHER>
```

**Voucher identification:** Uses `TAGNAME`/`TAGVALUE` pairs:
- `TAGNAME="Voucher Number"` + `TAGVALUE="3"` — by voucher number
- `TAGNAME="Master ID"` + `TAGVALUE="119"` — by Tally internal ID (LASTVCHID)
- Also requires `DATE` and `VCHTYPE`

**IMPORTANT: Our delete format was wrong.** We used `VCHKEY` attribute and `REMOTEID` which are not the documented approach. The correct format uses `TAGNAME`/`TAGVALUE` attributes on the VOUCHER element. The crashes were likely caused by the malformed delete XML.

**Recommendation for "Undo":**
- Use `ACTION="Cancel"` (safer, preserves audit trail)
- Identify voucher by `TAGNAME="Master ID"` + `TAGVALUE=LASTVCHID` from the create response
- Fall back to `ACTION="Delete"` only if cancel doesn't work

## Sales Voucher XML (from official docs)

```xml
<VOUCHER>
  <DATE>20160401</DATE>
  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
  <VOUCHERNUMBER>1</VOUCHERNUMBER>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <OBJVIEW>Invoice Voucher View</OBJVIEW>
  <!-- Party ledger (debtor) -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>ABC Company Limited</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
    <AMOUNT>-21546.00</AMOUNT>
    <BILLALLOCATIONS.LIST>
      <NAME>1</NAME>
      <BILLTYPE>New Ref</BILLTYPE>
      <AMOUNT>-21546.00</AMOUNT>
    </BILLALLOCATIONS.LIST>
  </LEDGERENTRIES.LIST>
  <!-- GST entries -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>CGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>1800.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>SGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>1800.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <!-- Stock items -->
  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>Sony Television</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <RATE>15000.00/nos</RATE>
    <AMOUNT>15000.00</AMOUNT>
    <ACTUALQTY>1 nos</ACTUALQTY>
    <BILLEDQTY>1 nos</BILLEDQTY>
    <BATCHALLOCATIONS.LIST>
      <GODOWNNAME>Main Location</GODOWNNAME>
      <BATCHNAME>Primary Batch</BATCHNAME>
      <AMOUNT>15000.00</AMOUNT>
      <ACTUALQTY>1 nos</ACTUALQTY>
      <BILLEDQTY>1 nos</BILLEDQTY>
    </BATCHALLOCATIONS.LIST>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
      <AMOUNT>15000.00</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>
</VOUCHER>
```

## Purchase Voucher XML (from official docs)

```xml
<VOUCHER>
  <DATE>20160401</DATE>
  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
  <VOUCHERNUMBER>1</VOUCHERNUMBER>
  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
  <ISINVOICE>Yes</ISINVOICE>
  <OBJVIEW>Invoice Voucher View</OBJVIEW>
  <!-- Party ledger (creditor) -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>Supplier XYZ</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
    <AMOUNT>21546.00</AMOUNT>
    <BILLALLOCATIONS.LIST>
      <NAME>PO123</NAME>
      <BILLTYPE>New Ref</BILLTYPE>
      <AMOUNT>21546.00</AMOUNT>
    </BILLALLOCATIONS.LIST>
  </LEDGERENTRIES.LIST>
  <!-- GST entries -->
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>CGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>1800.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <LEDGERENTRIES.LIST>
    <LEDGERNAME>SGST</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>1800.00</AMOUNT>
  </LEDGERENTRIES.LIST>
  <!-- Stock items -->
  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>Raw Material A</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <RATE>8000.00/nos</RATE>
    <AMOUNT>8000.00</AMOUNT>
    <ACTUALQTY>1 nos</ACTUALQTY>
    <BILLEDQTY>1 nos</BILLEDQTY>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>Purchases</LEDGERNAME>
      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
      <AMOUNT>8000.00</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>
</VOUCHER>
```

## Two Import XML Formats

Tally supports TWO different XML envelope formats for imports:

**Format 1: IMPORTDATA envelope (what we tested, works for masters)**
```xml
<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC><REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>Company</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA><TALLYMESSAGE>...</TALLYMESSAGE></REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>
```

**Format 2: TYPE=Data envelope (from official docs, used for vouchers)**
```xml
<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST>
<TYPE>Data</TYPE><ID>Vouchers</ID></HEADER>
<BODY><DESC></DESC><DATA>
<TALLYMESSAGE>...</TALLYMESSAGE>
</DATA></BODY></ENVELOPE>
```

Our live test used Format 1 for vouchers and it worked (CREATED=1). But Format 2 is what official docs show. Both may work — needs verification for edge cases.

## Official Ledger Creation Format (from docs)

Note: Official docs show `Action="Create"` (capital A) and use `<NAME>` child tag, NOT `NAME` attribute + `NAME.LIST`:
```xml
<LEDGER Action="Create">
  <NAME>Customer ABC</NAME>
  <PARENT>Sundry Debtors</PARENT>
</LEDGER>
```

But our live test showed this format gets EXCEPTIONS=1. The working format was:
```xml
<LEDGER NAME="_Test Ledger B" ACTION="Create">
  <NAME.LIST><NAME>_Test Ledger B</NAME></NAME.LIST>
  <PARENT>Indirect Expenses</PARENT>
</LEDGER>
```

This discrepancy may be version-specific (docs may be for older Tally versions).

## Known Issues

### Voucher Cancel/Delete: WORKS with correct format
Our v1 crashes were caused by wrong XML format (`VCHKEY`, `REMOTEID` — undocumented attributes).
The correct format uses `TAGNAME="Master ID" TAGVALUE="<LASTVCHID>"` and works perfectly:
- Cancel: returns ALTERED=1 (cancel is internally an alter)
- Delete: returns DELETED=1
- Delete after cancel: also works (DELETED=1)
- All voucher types tested: Payment, Sales, Purchase

### Master (Ledger/Group) Delete: WORKS with NAME.LIST
Earlier crashes were caused by missing `NAME.LIST` in delete XML (same issue as creation).
Correct format:
```xml
<GROUP NAME="_Test Group" ACTION="Delete">
<NAME.LIST><NAME>_Test Group</NAME></NAME.LIST>
</GROUP>
```
Without `NAME.LIST`, Tally crashes with memory violation. With it, returns DELETED=1 cleanly.

### Timeout Requirements
- 30s default timeout is insufficient for write operations
- Recommend 60-90s timeout for write operations
- Read operations work fine with 30s

### Format A vs B for Masters
- `<LEDGER NAME="X" ACTION="Create"><PARENT>Y</PARENT></LEDGER>` → FAILS (EXCEPTIONS=1)
- `<LEDGER NAME="X" ACTION="Create"><NAME.LIST><NAME>X</NAME></NAME.LIST><PARENT>Y</PARENT></LEDGER>` → WORKS (CREATED=1)

The NAME.LIST requirement is undocumented but essential. Likely applies to GROUP and STOCKITEM creation too.

## Verified Operations Summary

| Operation | Status | Key Requirement |
|-----------|--------|-----------------|
| Create Ledger | WORKS | Requires `NAME.LIST` child element |
| Create Group | WORKS | Both NAME.LIST and official format work |
| Create Payment | WORKS | `ALLLEDGERENTRIES.LIST`, amounts balance to 0 |
| Create Sales (with GST) | WORKS | `ALLLEDGERENTRIES.LIST` + `PERSISTEDVIEW` |
| Create Purchase (with GST) | WORKS | `ALLLEDGERENTRIES.LIST` + `PERSISTEDVIEW` |
| Cancel Voucher | WORKS | `TAGNAME="Master ID"` + `TAGVALUE=LASTVCHID` |
| Delete Voucher | WORKS | Same as Cancel, `ACTION="Delete"` |
| Delete Ledger | WORKS | Requires `NAME.LIST` (crashes without it) |
| Delete Group | WORKS | Requires `NAME.LIST` (crashes without it) |

## Sales/Purchase: Key Differences from Payment

- Need `PERSISTEDVIEW` tag (value: `"Accounting Voucher View"`)
- Party ledger needs `ISPARTYLEDGER` tag set to `Yes`
- GST entries: OUTPUT CGST/SGST for Sales, INPUT CGST/SGST for Purchase
- Sales: party amount negative (debit, ISDEEMEDPOSITIVE=Yes), sales positive
- Purchase: party amount positive (credit, ISDEEMEDPOSITIVE=No), purchase negative

## Company Data Summary

- 88 ledgers, 37 groups, 59 payment vouchers (as of 2026-04-05)
- 7 GST ledgers under Duties & Taxes
- Custom groups: Professional Creditors, Professional EXPENSES, EMAIL WEBSITE &RAZORPAY, etc.

## Scripts

- `scripts/explore_tally_write.py` — v1 exploration (caused crash via REMOTEID delete)
- `scripts/explore_tally_write_v2.py` — v2 exploration (format testing, verified results)
- `scripts/cleanup_tally_test.py` — cleanup test entities (use with caution, delete may crash)
