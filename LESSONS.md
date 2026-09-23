# LESSONS.md — Tally API Learnings

Hard-won lessons from building the TallyPrime AI Agent. These are NOT in Tally's official docs.

---

## 1. P&L TYPE=Data is unreliable for partial periods

**Discovery date:** 2026-03-15
**Diagnostic script:** `test_scripts/test_pnl_period.py` (15 tests against live Tally)
**Logs:** `test_scripts/logs/pnl_period_debug.log`

### The problem

Tally's XML API `TYPE=Data` for Profit & Loss returns **non-monotonic, unreliable values** when you query partial date ranges (e.g., Apr 1 → Jul 31).

Tested cumulative P&L for each month-end across a full FY. Expected monotonically increasing values for Sales. Got:

| Month-end | Expected (cumulative) | Actual from API |
|-----------|----------------------|-----------------|
| Apr 30 | 0 | ₹49,97,900 (full-year total!) |
| May 31 | 0 | 0 |
| Jun 30 | 0 | ₹49,97,900 |
| Jul 31 | ₹2,95,000 | ₹2,95,000 |
| Aug 31 | ₹5,95,000 | ₹5,95,000 |
| ... | ... | ... |
| Mar 31 | ₹49,97,900 | ₹49,97,900 ✓ |

Values jump between the full-year total and 0 for months with no transactions, instead of returning 0 consistently. This makes any subtraction-based approach (cumulative[month] − cumulative[month−1]) produce garbage.

### What works

- **Full-FY P&L** (Apr 1 → Mar 31): Always returns correct cumulative total. ✓
- **Voucher registers** (`get_sales_register`, `get_purchase_register`): Return transaction-level data with dates. Sum by month for accurate breakdowns. ✓
- **Day book** (`get_day_book`): Also transaction-level, works for expense trends. ✓

### What doesn't work

- **Partial-period P&L subtraction**: Garbage in → garbage out. The inputs are unreliable.
- **TYPE=Collection for P&L ledgers**: Revenue/expense ledgers are nominal accounts — ClosingBalance is always 0 by design (auto-closed to "Profit & Loss A/c").
- **Group objects via Collection**: CHILDOF on Group objects with Revenue/Expense filters returned empty results.

### Our fix

`profit_and_loss_period()` raises `TallyResponseError` for non-full-FY date ranges, with a message directing the agent to use voucher registers instead. Full-FY queries pass through unchanged.

---

## 2. SVFROMDATE is ignored for P&L reports

P&L reports always return cumulative data from FY start regardless of SVFROMDATE. Only SVTODATE is respected. This is why the "query each month separately" approach doesn't isolate monthly data — each call returns cumulative-to-date, not month-specific.

**Workaround:** Don't use P&L for period breakdowns. Use voucher registers.

---

## 3. `$$InDateRange` crashes Tally

The TDL function `$$InDateRange` is documented in some Tally resources but crashes TallyPrime 7.0 when used in Collection filters. Use `SVFROMDATE`/`SVTODATE` envelope parameters + Python-side filtering instead.

---

## 4. TYPE=Collection vs TYPE=Data

| Aspect | TYPE=Data | TYPE=Collection |
|--------|-----------|-----------------|
| Use case | Display reports (TB, P&L, BS) | Object queries (ledgers, vouchers) |
| XML structure | Sibling pairs (DSPACCNAME → DSPACCINFO) | Named fields (Name, Parent, ClosingBalance) |
| P&L reliability | Full-FY only | Always 0 for P&L ledgers (nominal accounts) |
| Voucher data | Summaries only | Full transaction detail with NATIVEMETHOD |

**Rule of thumb:** Use TYPE=Data only for aggregate report snapshots. Use TYPE=Collection for anything transactional.

---

## 5. XML field conventions

- Never use `*` in NATIVEMETHOD FETCH — crashes Tally. List specific fields.
- Sanitize `&#4;` control chars from XML responses before parsing.
- Dates always DD-MM-YYYY format.
- Indian FY: April 1 → March 31. Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.

---

## 6. P&L parser is correct (BSMAINAMT/PLSUBAMT)

After extensive testing, the `parse_profit_and_loss()` parser in `response_parser.py` was confirmed correct. It uses `BSMAINAMT` with `PLSUBAMT` fallback — this matches Tally's actual XML structure. The earlier hypothesis about sign alternation bugs was disproved.

---

## 7. Voucher-based monthly P&L (ground truth)

For the test company (NUVANTA AI TECHNOLOGIES PRIVATE LIMITED, FY 2025-26):

```
Jul: ₹2,95,000   Aug: ₹3,00,000   Sep: ₹6,00,000   Oct: ₹5,75,000
Nov: ₹5,00,000   Dec: ₹8,82,500   Jan: ₹6,11,850   Feb: ₹12,33,550
Full year total: ₹49,97,900
```

These values from `get_sales_register` match Tally desktop exactly.

---

## 8. `<VOUCHERNUMBER>` only sticks under specific UI-set numbering modes

**Discovery date:** 2026-05-05
**Probe logs:** `docs/probe-voucher-numbering.log`, `docs/probe-tally-config.log`, `docs/probe-reference-alter.log`
**Canonical evidence:** `docs/tally-write-exploration-v4.md` § "ALTER and config-write findings"

### Truth table (live-verified)

| NumberingMethod | How set | VOUCHERNUMBER on Create | VOUCHERNUMBER on ALTER |
|---|---|---|---|
| `Automatic` (default) | either | ❌ ignored | ❌ ignored |
| `Automatic (Manual Override)` | UI-set | ✅ honored | ? (likely honored) |
| `Automatic (Manual Override)` | XML-set | ❌ no runtime effect | ❌ |
| `Manual` | UI-set | ✅ honored | ✅ honored |
| `Manual` | XML-set | ❌ no runtime effect | ❌ |

**`Default` value is READ-ONLY** — Tally's "as-shipped" state. Cannot be set as a write value (silently coerced to `None`).

### What this means

- For default Tally companies, never trust `<VOUCHERNUMBER>` on import — Tally auto-overwrites with its sequential counter.
- `<REFERENCE>` is the right field for user-supplied invoice/bill numbers (works under any mode, see §9).
- For voucher-number control on imports, the user must change the voucher-type config via Tally UI (not XML — see §11).

---

## 9. `<REFERENCE>` is the canonical user-supplied invoice number field

**Discovery date:** 2026-05-05
**Probe log:** `docs/probe-reference-alter.log`

- Survives Create AND ALTER under any numbering mode.
- Mutable: subsequent ALTER overwrites the previous value cleanly.
- Minimal ALTER envelope (verified — `altered=1`, readback confirms):

```xml
<VOUCHER DATE="01-Oct-2025" TAGNAME="Master ID" TAGVALUE="20"
         VCHTYPE="Sales" ACTION="Alter">
  <REFERENCE>S001</REFERENCE>
</VOUCHER>
```

- **Visibility caveat**: `<REFERENCE>` is hidden in Tally voucher screens by default. Per-voucher-type F12 toggle ("Show Reference" / equivalent) must be enabled by the user. Storage is unaffected — agent can write/read regardless.
- For "find voucher S012" use cases, query Tally on the REFERENCE field, not VOUCHERNUMBER.

---

## 10. `BILLALLOCATIONS` works on Create only — cannot be retro-fitted via ALTER

**Discovery date:** 2026-05-05
**Probe logs:** `docs/probe-bill-allocations.log` (Create), session inline probes (ALTER)

### What works

- Builder support landed for all 4 voucher types (sales, purchase, payment, receipt) in `import_builder.py`. Pass `bill_allocations=[{"name": ..., "type": "New Ref"|"Agst Ref"|"On Account", "amount": ..., "credit_period": ...}]`.
- `BILLALLOCATIONS.NAME` survives round-trip and is ALWAYS visible in Tally UI (Bills Outstanding, voucher's bill-wise breakdown). No F12 toggle needed.
- Receipts/Payments with `Agst Ref` correctly clear the bill from `bills_receivable`/`bills_payable`.
- Sign convention: `BILLALLOCATIONS.AMOUNT` mirrors the party LEDGERENTRY.AMOUNT.

### What doesn't work — both ALTER paths fail

| Approach | Tally response | Actual result |
|---|---|---|
| Partial ALTER (send only `<ALLLEDGERENTRIES.LIST>` + BILLALLOCATIONS) | `altered=1, errors=0` | Silently ignored. No bill created. |
| Full-body ALTER (resend full voucher with bill_allocations + Master ID handle) | `CREATED=1, ALTERED=0` | Tally **ignores Master ID** and creates a DUPLICATE voucher with the bill. |

### Operational rule

Bills can only be added at voucher Create time. Vouchers seeded without `BILLALLOCATIONS` cannot have bills retro-fitted — only path is delete + recreate.

---

## 11. Voucher-type config writes via XML are unreliable (DANGEROUS)

**Discovery date:** 2026-05-05
**Live evidence**: User UI-set Sales NumberingMethod = "Automatic (Manual Override)" → VOUCHERNUMBER on Create immediately worked. We then XML-altered Purchase NumberingMethod from `Default` → `Manual`. Tally returned `altered=1`, readback showed `Manual`, BUT Tally UI continued to show `Automatic` and runtime behavior didn't change.

### The pattern

`<VOUCHERTYPE ACTION="Alter">` writes go to a "stored but ignored" shadow store:
- Tally always returns `altered=1, errors=0`.
- XML readback reflects the new value.
- **UI/runtime behavior does NOT change.**

Plus: invalid enum values silently coerce to `None` (e.g. `Default` → `None`).

### Operational rule

**Future write-agent must INSTRUCT the user to make voucher-type config changes via Tally UI** (Gateway → Alter → Voucher Types → ...). Do NOT attempt XML writes for behavior-affecting voucher-type fields. They look successful but don't take effect, and invalid values can leave the config in a broken state.

Read-side queries on voucher-type config remain reliable — use `TYPE=Object SUBTYPE=VoucherType ID="<name>" FETCHLIST=*` to inspect before recommending UI changes.

---

## 12. `altered=1` is NOT proof of actual change

**Always readback after ALTER**, especially for:

- Enum fields (Tally silently coerces invalid values).
- Sub-list ALTERs (partial `<ALLLEDGERENTRIES.LIST>` with bill_allocations is silently ignored).
- Voucher-type config (writes appear successful but don't propagate to runtime).
- VOUCHERNUMBER under Automatic mode (silently overwritten).

`altered=1` from Tally means "the request was accepted as well-formed" — not "the field changed". Compare the post-write read against the intent before reporting success to the user.

---

## 13. Read-config pattern is universal and reliable

`TYPE=Object SUBTYPE=<X> ID=<Y> FETCHLIST=*` works for `VoucherType`, `Company`, `StockItem`, `Ledger`. Use this freely to inspect before any write.

Sample envelope:

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Object</TYPE><SUBTYPE>VoucherType</SUBTYPE>
    <ID TYPE="Name">Sales</ID>
  </HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVCURRENTCOMPANY>...</SVCURRENTCOMPANY></STATICVARIABLES>
    <FETCHLIST><FETCH>*</FETCH></FETCHLIST>
  </DESC></BODY>
</ENVELOPE>
```

Use this to inspect: NumberingMethod, GST flags, F11/F12 toggles (where exposed), opening balances, etc. Read-side is honest; only write-side has the divergences described above.

---

## 14. REFERENCE / REFERENCEDATE — external document number/date fields, toggle-gated writes

**Discovery date:** 2026-05-07
**Canonical evidence:** `docs/tally-write-exploration-v4.md` § "REFERENCEDATE — supplier invoice date (toggle-gated)"
**Open enumeration:** `docs/open-items-parked.md` — "Per-voucher-type external-doc-date toggles"

### Field meaning + canonical names

- `<REFERENCE>` — external document number (supplier invoice no on Purchase, customer PO/reference on Sales, cheque/instrument no on Receipt/Payment).
- `<REFERENCEDATE>` — external document date (supplier invoice date on Purchase, customer PO date on Sales, cheque date on Receipt/Payment).
- Both are **top-level voucher fields**, siblings of `<DATE>`, `<VOUCHERNUMBER>`, `<NARRATION>`. NOT nested inside `<LEDGERENTRIES.LIST>` or `<BILLALLOCATIONS.LIST>`.
- `<REFERENCEDATE>` format is **`YYYYMMDD`** (e.g. `20250925` for 25-Sep-2025). Same format as `<DATE>` in voucher import envelopes.

### UI labels by voucher type

| Voucher type | REFERENCE label | REFERENCEDATE label | Default visibility |
|---|---|---|---|
| Purchase | "Supplier Invoice No" | "Supplier Invoice Date" | Visible by default once toggle enabled |
| Sales | "Reference" / "Order No." | "Reference Date" / "Order Date" | Hidden — F12 toggle on voucher type |
| Receipt | (bill reference) | (cheque date for post-dated) | Parked — not yet enumerated |
| Payment | (bill reference) | (cheque date for post-dated) | Parked — not yet enumerated |

### The toggle gate (silent-overwrite-to-voucher-DATE failure mode)

**REFERENCE/REFERENCEDATE writes are gated by a per-voucher-type configuration toggle**: Voucher Type → Configuration → "Use supplier invoice date" (label varies by voucher type — likely "Use customer PO date" / "Use cheque date" on others; not yet enumerated).

When the toggle is **OFF** and you send `<REFERENCEDATE>20250925</REFERENCEDATE>` on Create or ALTER:
- Tally returns `created=1` / `altered=1, errors=0` — no rejection, no error.
- Tally **silently overwrites the requested value with the voucher's main `<DATE>` field**. So if `<DATE>20251015</DATE>`, readback shows `REFERENCEDATE = 15-Oct-2025`, not the 25-Sep-2025 you sent.
- Looks like a successful round-trip on cursory inspection (the field is non-empty and well-formed). This is the most insidious silent-failure mode encountered so far.

When the toggle is **ON**, the same XML envelope sticks correctly. Verified empirically (2026-05-07): identical envelope, both outcomes observed before vs after toggling.

**Operational rule:** `altered=1` is NOT proof of correctness here either (cf. §12). For REFERENCEDATE, only readback comparison against the *intended* value confirms — not just that the field has *some* value.

### Voucher-type config is Tally-installation-scoped, not company-scoped

Voucher-type configurations (including these toggles) persist on the **Tally installation**, shared across all companies on the same install. Implication for backup/restore:

- `.tbk` restore **into the same Tally install** → toggles preserved (because they were never company-scoped to begin with).
- `.tbk` restore **into a different Tally install** (fresh install, different machine) → toggles do NOT travel with the backup. The voucher data restores fine, but any subsequent write that depends on the toggle will hit the silent-overwrite mode until the toggle is set manually on the new install.

Critical for any deployment story: customer-side write-agent sessions need the toggles probed/configured before relying on REFERENCE/REFERENCEDATE writes.

### Status across voucher types

- **Purchase** — confirmed (this session). Toggle: "Use supplier invoice date".
- **Sales / Receipt / Payment** — *likely* to have analogous toggles (customer PO date; cheque date for post-dated cheques), since REFERENCE/REFERENCEDATE have natural meaning on those types too. **Not yet probed.** Parked for write-agent design phase.

---

## 15. Tally Write Safety — Operational Rules

Distilled rules for any code path (or agent) that writes to Tally. Most of these are also "why" — the corresponding "what" is documented in §6–§14 above and in [`docs/tally-write-exploration-v4.md`](docs/tally-write-exploration-v4.md).

1. **Read config before writing anything that depends on it.** Fetch the voucher type via `TYPE=Object SUBTYPE=VoucherType ID="<Name>" FETCHLIST=*` and inspect `NUMBERINGMETHOD`, `ALLOWALTERATION`, display toggles, and any per-type "Use … date" gate. Don't assume defaults.
2. **`altered=1` / `created=1` is NOT proof of effect.** It only means the request parsed. Always readback after every ALTER — especially enum fields, sub-list ALTERs, and REFERENCEDATE.
3. **Tally silently coerces invalid enum input to `None`.** No error, no warning. Readback is the only safety net.
4. **Voucher-type config changes must be done in the Tally UI** (Gateway → Alter → Voucher Types → …). XML writes for behavior-affecting voucher-type fields (e.g. `NUMBERINGMETHOD`) appear successful — readback even confirms — but the runtime behavior doesn't change. Instruct the user; don't try to do it via XML.
5. **BILLALLOCATIONS cannot be retro-fitted on existing vouchers.** Partial ALTER silently ignored; full-body ALTER with `TAGNAME="Master ID"` creates a duplicate voucher (`CREATED=1, ALTERED=0`). Bills must be added on the original Create.
6. **REFERENCEDATE silent-overwrite check:** Before writing supplier-invoice-date (or analogous external-doc-date), confirm the per-voucher-type "Use supplier invoice date" toggle is ON. If OFF, Tally substitutes the voucher's main `DATE` field — readback alone won't catch it (the value looks plausible). Detection: write a value that differs from voucher DATE, then readback; if readback equals voucher DATE, the toggle is OFF.
7. **Voucher-type config is Tally-installation-scoped, not company-scoped.** A `.tbk` restored into a different Tally install does not carry the toggles. Fresh installs need toggles set manually before any write that depends on them.
8. **Sales numbering default ("Automatic") silently overwrites `<VOUCHERNUMBER>`.** Only `Manual` and `Automatic (Manual Override)` honor the supplied number — and the toggle change must be made in the UI (per rule 4).
9. **Distinguish "data is stored correctly" from "user can see it in UI."** Some fields (e.g. REFERENCE) are stored under any numbering mode but hidden in the UI unless a per-voucher-type F12 display toggle is on. Surface the relevant toggle to the user when behavior is config-dependent. Concretely (live 2026-06-12): **Purchase** vouchers show REFERENCE as "Supplier Invoice No." on the entry screen; **Sales** vouchers hide it unless F12 → "Provide Reference No." is on (it's still written + visible in print/registers). The seeder also mirrors the invoice no into the **Narration** so it's always visible — a useful pattern.

### Master-creation & inventory write gotchas (live-discovered 2026-06-11/12)

10. **NEVER send a CREATE for a master that already exists.** Re-importing a `<UNIT>`/`<STOCKGROUP>`/`<STOCKITEM>` `ACTION="Create"` for an existing master makes Tally pop a **blocking modal** that freezes the HTTP gateway — reads keep working, the first such write **times out**, and every subsequent request hangs until the modal is dismissed (a full Tally restart may be needed). Mitigation: list existing masters first (`list_stock_items` → item names + their units/groups; `list_stock_groups` → empty groups too) and create only the genuinely-missing ones. This is the #1 cause of "Tally froze" during inventory writes.
11. **`created=0, altered=1, errors=0` on a master CREATE = "already exists" (benign).** When Tally *does* respond (vs modal-hanging per #10), treat altered-only as success, not failure. Don't abort the voucher on it.
12. **A GST-rated stock item REQUIRES an HSN.** Creating a `GSTAPPLICABLE=Applicable` stock item with GST rates but no HSN pops a mandatory "HSN/SAC" modal (freezes per #10). When no HSN is extracted, create the item `GSTAPPLICABLE=Not Applicable` (omit `GSTDETAILS.LIST`/HSN) — the voucher's explicit CGST/SGST/IGST ledger lines still post GST correctly, independent of the item master.
13. **"Primary" is a reserved stock group name** — creating a group literally named "Primary" can modal. Use a non-reserved default (e.g. "AI Imported Items") and create it on demand.
14. **Future-dated vouchers are silently dropped / not visible.** A voucher dated after Tally's working date (F2) or outside the open financial year won't post, or won't show in current-period reports. Before writing, set F2 ≥ the voucher date and ensure the period covers it — otherwise use an in-period date. (Same root cause as the seeder's F2 preflight.)

When advising the user, distinguish these failure modes and surface the relevant Tally config — the agent can't see the modal it triggers without the user reading it on screen.

### GST-invoice recompute & bill-wise reporting (live-discovered 2026-06-23)

15. **`ISINVOICE=Yes` + auto-GST makes Tally RE-COMPUTE the bill total, overriding your `BILLALLOCATIONS` amount.** When a Purchase/Sales posts with `<ISINVOICE>Yes</ISINVOICE>` + `Invoice Voucher View` + GST ledger legs (Duties & Taxes), Tally's GST engine re-derives the assessable value and the party/bill total on its side. Live-observed: we POSTed a ₹11,800 gross (₹10,000 + ₹900 CGST + ₹900 SGST) with a `New Ref` bill of ₹11,800 — the **POSTed XML read back correct at every layer** (party `<AMOUNT>` and `<BILLALLOCATIONS><AMOUNT>` both 11,800), yet Tally **stored the bill as ₹9,440** (it back-computed a different assessable; exact 8,000-base derivation inferred from the stock items' own configured GST rates). **Detection:** read back the *bill's pending amount* (`bills_payable`/`bills_receivable`), not just the POSTed XML or `created=1`. **Mitigation:** goods/inventory invoices must go through the **stock-grid writer** (posts qty/rate; Tally computes consistently — live-verified correct), NOT the ledger-invoice writer (`create_*_voucher_ledger`) — that path with explicit GST legs is for **services** (no stock items). Never assert `bill == gross` for an inventory invoice written via the ledger path.
16. **`bills_payable` / `bills_receivable` only return parties maintained BILL-BY-BILL.** A Sundry Creditor/Debtor with "Maintain balances bill-by-bill" OFF carries its balance **on-account** and never appears in these reports — even with a non-zero closing balance, and even after you post a `New Ref` bill against it (the allocation is silently dropped from the outstanding view). Live-observed: `Acme Computer Distributors Pvt Ltd` had closing ₹25,960 but ₹0 bill-wise pending, while `Bharat Paper Supplies` (bill-wise) showed ₹91,993.60. **Implication for tests/seeders/writers:** any read-back that asserts bill-wise outstanding (payable/receivable delta, "bill present") MUST target a party known to be bill-wise — select one that already appears in `bills_payable`/`_receivable`, don't pick an arbitrary creditor/debtor by group. (This is also why new party ledgers are created `is_billwise=True` — see the write-flow party-ledger path.)

### Read-side freeze: period variables on a master collection (live-discovered 2026-09-23)

17. **NEVER send `SVFROMDATE` or `SVTODATE` on a master (Ledger) collection.** Same modal-freeze family as rule 10, but on the *read* path. Live 2026-09-23 (reproduced twice, freshly reset seed company; v2 S0 probe harness, logs in `v2/probes/results/logs/s0-ason-discriminator*-2026-09-23.log`):
    - **`SVFROMDATE` freezes Tally's XML server.** The Ledger-collection read timed out at 45 s and an *unrelated* counters read then timed out too — the whole gateway sits blocked behind a modal until Tally is **restarted**. On a customer's machine that freezes the accountant's Tally, not just our request.
    - **`SVTODATE` is silently ignored — the more dangerous failure.** It answers instantly with a healthy 200, byte-identical to the no-variable control, and **0 of 35** closing balances had changed: you get *today's* balances while believing they are as-on. A byte-count or "it returned 200" check confirms the wrong answer; only a per-ledger VALUE comparison catches it.
    - **As-on figures come from `TYPE=Data` reports instead.** Same builder, same DD-MM-YYYY dates: a Trial Balance for the full FY and an as-on Trial Balance both answered instantly and genuinely differed, and a *Voucher* collection with both variables was fine too. So this is neither a date-format bug nor a general period-variable bug — it is specific to master collections.
    - **Scope caveat:** proven on the **Ledger** collection only, in TallyPrime 7.0 **Educational** under **Wine**. Our build-time guard (`v2/probes/reads.py` `master_request`) is deliberately conservative and refuses both variables on *any* master collection; whether a licensed Tally on real Windows behaves the same is an open tier-C check.

### Read-side arithmetic: what a Tally integrator must know before summing anything (live-discovered 2026-09-23)

These three cost a full probe cycle of wrong conclusions. All were found on the seed company (company A, FY 2025-26, 50 vouchers) with the v2 S0 probe harness. **Scope caveat for all three:** TallyPrime 7.0 Edit Log, **Educational**, under **Wine 11.0**, one company — a licensed Windows Tally is an open tier-C check.

18. **An inventory voucher exports its nominal ledger TWICE — summing both double-counts by exactly 2×.** For Sales and Purchase vouchers the nominal leg (`Sales - Electronics`, `Purchase - Office Supplies`, …) appears in **both** `ALLLEDGERENTRIES.LIST` and each inventory entry's `ACCOUNTINGALLOCATIONS.LIST`. They are the *same* posting rendered twice, not two postings. Live: summing both left **24 of 50** vouchers (all 16 Sales + all 8 Purchase) failing a double-entry check and put Sales/Purchase at exactly 2× Tally's own as-on Trial Balance (−₹23,14,000 vs Tally's −₹11,57,000). **Rule: count `ALLLEDGERENTRIES.LIST` alone** — it is complete (party + nominal + GST legs) and gives 0 of 50 unbalanced, matching the TB to the paisa. Use `ACCOUNTINGALLOCATIONS.LIST` only when you need the per-stock-item split, never additively. (`v2/probes/reads.py` `PROBE_POSTING_RULE`.)

19. **The Trial Balance's stock-bearing group carries a synthetic `Opening Stock` row that NO ledger holds.** Under Current Assets the TB prints an `Opening Stock` row (₹18,55,800 for company A) that appears **zero** times in any Ledger collection. So a TB group row will *never* equal the rollup of its ledgers until you add it: live, Current Assets ₹26,05,093 = ledger rollup ₹7,49,293 + ₹18,55,800, exactly. Two traps: (a) it is a **static opening** figure — identical at different as-on dates — and it is **not** the Stock Summary *closing* total, which was −₹9,89,462.31 the same day and is a different quantity entirely; comparing against the Stock Summary makes a genuine reconciliation look like a mismatch. (b) Read it from the **same** TB response (`EXPLODEFLAG=Yes` exposes it and leaves the group rows byte-identical) so the two figures cannot drift apart. Related: a TB's rows do **not** net to zero — this row is part of why (see `docs/specs/2026-09-21-bi-part1-sync-design.md` for company A's full ₹33,05,800 explanation).

20. **A `TYPE=Data` Trial Balance honours its as-on date; Bills Receivable, Bills Payable and Stock Summary IGNORE it.** The TB as-on a past month-end really is history — every primary group reconciles to the vouchers up to that date, once rules 18 and 19 are applied. The other three return the books' **current** position while happily accepting the dates you pass: bills dated *after* the as-on date still came back, both sides' totals equalled the period-end (31-Mar) anchors rather than the as-on ones, and all 14 stock quantities equalled opening + the **full** year's movements, with the as-on group values byte-identical to the FY-end capture. **Rule:** never treat a dated Bills/Stock Summary read as a historical snapshot — compute those month-end figures from vouchers, or capture them *at* the month-end. (Also settled by the same read: `ISDEEMEDPOSITIVE=Yes` is inward for inventory entries — that rule reproduces Tally's own FY-end quantities exactly.)

---

## 16. Observability & tooling gotchas (non-Tally)

### `opentelemetry-instrumentation-anthropic` streaming tool-use `KeyError: 'input'`
Version **0.53.0** crashes (caught by its own `@dont_throw`, so it surfaces only as a DEBUG log) inside `_process_response_item` when a streaming response with tools emits an `input_json_delta` before the event dict has an `input` key:
```
complete_response["events"][index]["input"] += item.delta.partial_json   # KeyError
```
Effect: streaming generations that use tools (here: `AnalysisAgent`, the only streaming+tools call) are dropped from Langfuse traces and spam DEBUG noise. Fixed in **0.61.0**, which guards it: `event["input"] = event.get("input", "") + item.delta.partial_json` plus a `tool_use` type check and an `index < len(events)` bounds check. **Rule:** keep `opentelemetry-instrumentation-anthropic >= 0.61.0`. Verify the guard by reading the *installed file* (`<venv>/.../opentelemetry/instrumentation/anthropic/streaming.py`) — `inspect.getsource` on the function returns the `@dont_throw` wrapper, not the real body.

### `python-multipart` must be a declared dependency
FastAPI's `File`/`Form`/`UploadFile` (used by `/api/chat/upload`) require `python-multipart` at import time. It was historically only manually `pip install`ed, never in the lock — so `uv sync` silently removes it and the upload route breaks. It is now a declared core dep in `pyproject.toml`. Don't rely on manually-installed packages; declare them.

### Playwright route mocks must account for query strings
`page.route("**/api/health", ...)` does **not** match `/api/health?host=localhost&port=9000` — Playwright globs don't span the query string. The per-workspace heartbeat badge sends host/port as query params, so the mock never fulfilled and the badge stuck on "Checking…". Use `**/api/health**` (trailing `**`) for any endpoint the frontend calls with query params. Also: for async header badges, add a settle wait (`await expect(badge).not.toContainText("Checking")`) before `toHaveScreenshot` to keep screenshots deterministic.

## 17. DB-mode persistence: every chat-producing endpoint must persist `Message` rows

In DB mode the conversation is rehydrated **solely** from `Message` rows
(`getConversation` → `GET /workspaces/.../conversations/...`). Anything an endpoint
returns to the frontend but does **not** write as a `Message` row is lost on refresh/relogin.

- **`/chat/upload` must persist messages.** It originally wrote only an `UploadedFile`
  audit row, so uploaded `voucher_review` cards vanished on reload. Fix: persist a user
  `Message` (`"<msg> [filename]"`) + assistant `Message` (`data=result["data"]`), set
  `conversation.title`/`updated_at`, and `flush()` the user message before the assistant
  one so the per-row `created_at` default preserves order. (`_chat_db_mode` already does
  all this — mirror it in any new chat-producing endpoint.)
- **Persist *state changes* too, and thread `conversation_id` via the REQUEST.**
  `/chat/voucher-action` must update the originating `voucher_review` Message entry's
  `status` (→ `"written"`/`"deleted"`) so a written/discarded card doesn't reload as
  actionable `"draft"`. In-place JSONB mutation needs
  `sqlalchemy.orm.attributes.flag_modified(msg, "data")` or SQLAlchemy won't detect it.
  **Gotcha:** the production review-card `entry` dict has **no `conversation_id`** (the
  orchestrator never adds it, the frontend passes `entry` through unmodified) — so any
  `entry.get("conversation_id")` gate silently no-ops in production (this had already
  been silently skipping the `VoucherEntry` audit row). Pass `conversation_id` as an
  explicit request field and use `request.conversation_id or entry.get(...)`.
- **Test at the real shape.** A test that injects `conversation_id` *into the entry dict*
  passes while production no-ops. Pass it via the request body, and add a revert
  sanity-check (remove the threading → test must fail). See
  [`docs/code-review-upload-voucher-persistence-2026-06-12.md`](docs/code-review-upload-voucher-persistence-2026-06-12.md).
