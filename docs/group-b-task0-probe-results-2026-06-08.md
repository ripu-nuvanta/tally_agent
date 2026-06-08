# Group B — Task 0 Live Exploration Results

**Date:** 2026-06-08
**Company:** Bharat Traders Private Limited (seed company, license active)
**Tally:** localhost:9000, TallyPrime 7.0+
**Script:** `scripts/probe_group_b.py` — full log at `logs/probe_group_b.log`
**Outcome:** 12 probes run, **11 PASS / 1 FAIL** (the fail is an intentional isolation test, see E3).

All probes self-clean: every created voucher deleted by Master ID, every created
ledger deleted by name. Verified afterward — ledger count back to 35, no `_Probe*`
residue. Books unchanged.

> **Read-back verification — DONE (2026-06-08).** `scripts/probe_group_b_readback.py`
> re-created T1a/T1b/B1/B1b, read each voucher back via a `day_book`-style collection
> with explicit native methods (incl. `AllLedgerEntries.BankAllocations` and `CHILDOF`),
> asserted the special fields survived, then deleted. Log: `logs/probe_group_b_readback2.log`.
> (First read-back attempt used `NATIVEMETHOD *`, which returns header-only and showed
> false "dropped" verdicts — corrected.) Conclusive results folded into the T1/B1 rows below.

## Results table

| Probe | Result | What it tested | Finding |
|---|---|---|---|
| **E1** | ✅ PASS | Purchase w/ `LEDGERENTRIES.LIST` + `Invoice Voucher View` + `ISPARTYLEDGER=Yes` | Invoice-style purchase works |
| **E2** | ✅ PASS | Purchase w/ `ALLLEDGERENTRIES.LIST` + `Accounting Voucher View` (control) | Known-good control confirmed |
| **E3** | ❌ FAIL | Purchase w/ `ALLLEDGERENTRIES.LIST` + `Invoice Voucher View` | **Bad combo** — Tally raises 1 exception. Conclusion: pair `LEDGERENTRIES.LIST` with Invoice View, or `ALLLEDGERENTRIES.LIST` with Accounting View. Do **not** mix `ALLLEDGERENTRIES.LIST` + Invoice View. |
| **E4** | ✅ PASS | Purchase w/ `ISPARTYLEDGER=Yes` + `BILLALLOCATIONS.LIST` (New Ref) | Party-ledger + bill allocation on create works |
| **E5** | ✅ PASS | **Debit Note** (`VCHTYPE="Debit Note"`) + Agst Ref bill allocation | DN creation works — first time verified |
| **E6** | ✅ PASS | **Credit Note** (`VCHTYPE="Credit Note"`) + Agst Ref bill allocation | CN creation works — first time verified |
| **E7** | ✅ PASS | `get_company_list()` read envelope | Both `Collection ID="List of Companies"` and custom `Collection TYPE=Company` return the company name → company dropdown is feasible |
| **E8** | ✅ PASS | `get_party_vouchers(party, types)` TDL filter | Filter by `$PartyLedgerName` works; returned Sales=4 / Purchase=4 vouchers, all for the requested party → "which bill is this against?" dropdown is feasible |
| **T1a** | ✅ PASS (persisted) | **TDS receivable** Journal (Dr TDS Receivable / Cr customer) | Read-back confirms: type=Journal, both legs survive — `(_ProbeGroupB TDS Receivable, -100)`, `(Apex…, +100)`. TDS-as-journal works. |
| **T1b** | ✅ PASS (persisted) | **TDS payable** Journal (Dr supplier / Cr TDS Payable) | Read-back confirms both legs survive — `(Apex…, -100)`, `(_ProbeGroupB TDS Payable, +100)`. Works. |
| **B1** | ✅ PASS (persisted) | **Bank instrument** — Payment w/ `BANKALLOCATIONS.LIST` | Read-back confirms `BANKALLOCATIONS.LIST` persisted on the bank leg with **INSTRUMENTNUMBER, INSTRUMENTDATE, TRANSACTIONTYPE** (cheque/UTR details). ⚠️ But **no `<DATE>` (bank-clearance/reconciliation date) came back** — instrument metadata persists, the *reconciliation date* does not. |
| **B1b** | ❌ FAIL (not persisted) | **Bank recon date** — Payment w/ top-level `<BANKDATE>` | Read-back: top-level `BANKDATE` **dropped entirely**. The naive "set the reconciliation date in the voucher" approach does NOT work. |

## What this unblocks

- **Debit Note / Credit Note** (E5/E6): verified — Group B can build these as planned.
- **Company dropdown** (E7) and **party-invoice dropdown** (E8): both read primitives work.
- **Purchase invoice format** (E1–E4): confirmed XML shape — `LEDGERENTRIES.LIST` +
  `Invoice Voucher View` + `ISPARTYLEDGER` + `BILLALLOCATIONS`.
- **TDS journals** (T1a/T1b): **confirmed working** — representing TDS as a balanced
  Journal voucher (TDS ledger leg + party leg) persists correctly in both directions.
- **Bank reconciliation** (B1/B1b): **partially feasible**, with an important limit:
  - Cheque/instrument details (`INSTRUMENTNUMBER`, `INSTRUMENTDATE`, `TRANSACTIONTYPE`)
    **do persist** via `BANKALLOCATIONS.LIST` on the bank leg at voucher-create time.
  - The actual **bank-reconciliation date** (the "cleared in bank on DD-MM-YYYY" marker)
    does **NOT** persist — neither as a `<DATE>` inside `BANKALLOCATIONS.LIST` nor as a
    top-level `<BANKDATE>`. This matches real Tally behaviour: the reconciliation date
    is set through the **Bank Reconciliation screen**, not on the payment voucher.

## Open question for bank reconciliation (needs its own probe)

How to set the reconciliation/clearance date programmatically. Options to probe later:
(a) Tally's dedicated bank-reconciliation import/`ALTER` against the bank ledger, or
(b) treat reconciliation as a manual post-entry step in Tally (instrument details still
captured on the voucher). This does **not** block Group B voucher writes — only the
"auto-mark cleared in bank" part of the Payment/Receipt reconciliation feature.
