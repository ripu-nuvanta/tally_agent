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

## Known Issues

### Delete Operations Crash Tally
Delete operations via XML API cause Tally to throw "memory violation" software exceptions. This happened consistently across multiple attempts. **Do not use XML delete in production.** Options:
1. Manual deletion via Tally UI
2. Use `ACTION="Alter"` to modify entries instead of deleting
3. Add a "void" narration prefix rather than deleting
4. Investigate if Tally version update fixes the XML delete bug

### Timeout Requirements
- 30s default timeout is insufficient for write operations
- Recommend 60-90s timeout for write operations
- Read operations work fine with 30s

### Format A vs B for Masters
- `<LEDGER NAME="X" ACTION="Create"><PARENT>Y</PARENT></LEDGER>` → FAILS (EXCEPTIONS=1)
- `<LEDGER NAME="X" ACTION="Create"><NAME.LIST><NAME>X</NAME></NAME.LIST><PARENT>Y</PARENT></LEDGER>` → WORKS (CREATED=1)

The NAME.LIST requirement is undocumented but essential. Likely applies to GROUP and STOCKITEM creation too.

## Company Data Summary

- 88 ledgers, 37 groups, 59 payment vouchers (as of 2026-04-05)
- 7 GST ledgers under Duties & Taxes
- Custom groups: Professional Creditors, Professional EXPENSES, EMAIL WEBSITE &RAZORPAY, etc.

## Scripts

- `scripts/explore_tally_write.py` — v1 exploration (caused crash via REMOTEID delete)
- `scripts/explore_tally_write_v2.py` — v2 exploration (format testing, verified results)
- `scripts/cleanup_tally_test.py` — cleanup test entities (use with caution, delete may crash)
