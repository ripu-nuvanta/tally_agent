# Code review — BI S0 company-B live fixes (C30–C34), 2026-09-24

**Scope:** `67a67a3` (C30 signed opening on the wire), `47cf175` (C31 compound unit), `4f81b1d` (`sign_check`),
`2c7860a` (C32 nominal line dropped when inventory is present), `7f32848` (C33 `TYPE="Date"` on SV*DATE vars),
`9a6f7b4` (C34 bill allocations take the party line's sign). Branch `feat/bi-s0-probe-harness`.
**Mode:** read-only. Nothing was sent to Tally (a live `setup-b` run 3 is in progress). The only file written is this one.
**Reference:** production `backend/tally_bridge/import_builder.py` (`_render_bill_allocations` L79,
`build_create_payment_voucher` L144, `_build_ledger_invoice_voucher` L219, `build_create_sales_voucher` L719,
`build_create_purchase_voucher` L824, `build_create_receipt_voucher` L926).

**Offline suite:** `uv run --project v2 pytest v2/tests -q` → **`480 passed in 79.48s`**.

## Verdict

**The six commits are correct as written.** C32, C33 and C34 match production and the live evidence, and they fail
safe: a voucher that breaks the new invariants raises before anything is sent. **Fix one dataset bug before the load
reaches voucher 14.** It is older than these commits, but C34 is what makes it matter. Every Agst Ref bill in
`company_b_data.py` points at a bill that does not exist (288 of 288). The USD export is also not written as forex
at all. Run 3 is paused at the opening-bill step (`logs/setup-b-live-2026-09-24-run3.log`), before any voucher, so
there is still time.

| # | Sev | Finding |
|---|---|---|
| 1 | **Critical** | All 288 Agst Ref bills (receipts + party payments) reference a bill name that no voucher ever opened |
| 2 | Important | USD export sales (tags 101/102) are written as plain INR sales; `currency`/`fx_amount` have no consumer |
| 3 | Important | Compound-unit quantity string `"<n> Box of 10 Nos"` is unverified and hits voucher 2 immediately |
| 4 | Important | FakeBooks' C33 model applies "untyped = ignored" to reports too, which contradicts p18 and reads.py |
| 5 | Important | FakeBooks still accepts several wrong shapes; 3 tests pass for the wrong reason (named below) |
| 6 | Minor | `sign_check` is non-discriminating: −1.00 under Sundry Debtors reads back −1.00 under C21 *and* C30 |
| 7 | Minor | Writer `ValueError`s (C32/C34 guards) are not caught by `_load_vouchers` and crash mid-load |
| 8 | Minor | The dropped nominal line's ISDEEMEDPOSITIVE is never cross-checked against the inventory flag |
| 9 | Minor | Asymmetric conventions: bill amounts are magnitudes, inventory amounts are signed |
| 10 | Minor | Production `request_builder.py` still sends untyped SVFROMDATE/SVTODATE (out of v2 scope; cross-ref) |

---

## Answers to the five questions

### (1) C32: nominal-line omission

- **Sales with inventory (Op 6):** correct. The party line is Yes/−, GST lines No/+, and inventory + allocation
  No/+goods. This is byte-for-byte production `build_create_sales_voucher` (L773–L800), and live
  `logs/debug-vch1-no-nominal-line-2026-09-24.log` returned CREATED=1.
- **Purchase with inventory (Op 7):** correct if the caller signs inventory amounts negative. The check at
  `v2/probes/setup/writes.py:277-281` needs `Σ inventory == nominal_amount` exactly, sign included. For a purchase
  that is −goods, which gives inventory + allocation `Yes/−goods` (writes.py:321, production L889–L897).
  `test_an_inventory_purchase_does_not_emit_the_nominal_ledger_line` pins this. **The dataset has no inventory
  purchases** (382 inventory vouchers, all sales), so this is not exercised live. The loader's M2 guard
  (`company_b.py:359`) also needs party-first ordering, and `_build_purchase` puts the party last. So adding
  inventory to purchases later would stop the load with `CompanyBLoadError`. That is safe, but the ordering
  contract is stricter than the writer needs.
- **Mixed-rate / multi-item:** multi-item vouchers with one nominal ledger are fine
  (`test_an_inventory_sale_does_not_emit_the_nominal_ledger_line` has two rows). Mixed GST rates are fine, because
  GST sits on separate lines. Two nominal ledgers (for example, a per-rate sales ledger) are **not supported**:
  every row is allocated to the first non-party line, and the second nominal line is still sent. The allocation
  check then fails (Σ inventory ≠ first nominal), so it raises rather than mis-posts. That is safe, but the
  message does not say "only one nominal ledger is supported".
- **Does the pre-send check guarantee balance?** Yes, for the ledger total Tally computes. `lines` sum to 0
  (L251), and Σ allocations = the dropped nominal amount (L278). So party + GST + allocations = 0. Each row's
  `ALLINVENTORYENTRIES/AMOUNT` and its `ACCOUNTINGALLOCATIONS/AMOUNT` are the same `amount` variable, so they
  cannot drift. The check does not cover Tally recomputing qty × rate against AMOUNT. The dataset is exact
  (integer qty, rate in paise, `quantize(0.01)`), so this only matters for future callers.
- **Purchases (240, no inventory):** unchanged. All four lines are sent in invoice mode, party `No/+` with New Ref
  `+`. This is the same shape as production `build_create_purchase_voucher_ledger` → `_build_ledger_invoice_voucher`
  (`party_on_debit=False`, bill sign +1), live-verified as E5/E6.
- **USD export sale (no inventory):** the ledger lines are unchanged, and production
  `build_create_sales_voucher_ledger` has the same shape. It will be created, but see finding 2.

### (2) C34: sign table vs production

| Voucher | Party line (v2 dataset) | v2 bill sign | Production | Match |
|---|---|---|---|---|
| Sales New Ref | Yes / −total | − | `party_line_sign=-1` (L773, L289 with `party_on_debit=True`) | ✅ |
| Purchase New Ref | No / +total | + | `party_line_sign=1` (L875; ledger path `party_on_debit=False`) | ✅ |
| Receipt Agst Ref | No / +amount | + | `party_line_sign=1` (L952) | ✅ |
| Payment Agst Ref | Yes / −amount | − | `party_line_sign=-1` (L183) | ✅ |

- No voucher kind has bills under a non-party line or more than one party line. I checked every voucher of
  `generate("educational")` and `generate("licensed")`. `_build_expense_payment` uses the expense ledger as
  `party`, but it carries no bills.
- There are no DN/CN vouchers in `company_b_data.py`.
- The writer's guard (`writes.py:296-298`) refuses bills unless there is exactly one party line.
- **But see finding 1:** the signs are right, and the bill *names* on every Agst Ref are wrong.

### (3) C33: STATICVARIABLES coverage and SVCURRENTDATE

- **Coverage is complete in v2.** `envelopes._static_vars` is the only renderer that emits date variables, used by
  `wrap_collection` and `wrap_report`. The other STATICVARIABLES blocks do not carry date variables:
  `p02_active_company_guid.py:26` (variant "b": `SVEXPORTFORMAT` only) and `setup/import_xml.py:28`
  (`SVCURRENTCOMPANY` only). All date-var callers go through the wrapper: `reads.voucher_request`,
  `writes.voucher` (L137), `company_b._read_vouchers` (L271), `b_trial_balance`, `b_bills_receivable`, and p16
  `_ledgers_request`.
- **Is typing SVCURRENTDATE safe?** Yes. No non-test code sends it today, and `<SVCURRENTDATE TYPE="Date">` is the
  standard TDL form. `_DATE_VAR` (`envelopes.py:17`) cannot catch non-date variables such as `SVCurrentCompany`
  or `EXPLODEFLAG`, and a test pins that.
- **Side effect to note:** p16's opt-in risky SVFROMDATE-on-Ledger step (`p16_ledger_closing_balance.py:208`) and
  its SVTODATE step now go out typed. The "freezes Tally" and "silently ignored" evidence behind
  `reads.MASTER_PERIOD_VARS` (`reads.py:48-62`) was all gathered untyped. The guard should stay, but its comment
  now describes an untested request, and a p16 re-run may behave differently. That includes a freeze, so keep
  `--allow-risky` off until it is re-measured.

### (4) FakeBooks fidelity

It now models the three rules correctly:
- **C32:** ledger lines + ACCOUNTINGALLOCATIONS must sum to 0, or the answer is EXCEPTIONS=1 with no LINEERROR.
- **C33:** only typed period variables are honoured; untyped ones fall back to the current period.
- **C34:** a bill is filed by its sign.

It can still pass a wrong shape. See finding 5, which names three false-passing tests.

### (5) USD export path

It is written as an ordinary INR "Sales" invoice. The party is `Gulf Office Supplies LLC` at `-inr_amount` and
`Export Sales` at `+inr_amount`. `currency="USD"` and `fx_amount` are dropped at `company_b.py:351-370`. No code
in `v2/` reads them. It **will not fail live**: the ledger-invoice sale shape is production-verified. That is the
problem: no Currency master, no ledger `CURRENCYNAME`, no forex `AMOUNT` expression, no rate. Probe 22 ("record
each line's raw AMOUNT text… it may be an expression like `$… @ ₹…/$ = ₹…`") will read plain INR decimals and
can report CONFIRMED vacuously. See finding 2.

---

## Findings

### 1. Critical: every Agst Ref points at a bill that was never opened

**Where:** `v2/probes/setup/company_b_data.py:329` (`_build_receipt`: `BillSpec(name=f"Inv/{tag}", "Agst Ref", …)`)
and `:346` (`_build_payment`: `f"Pur/{tag}"`). In both, `tag` is the receipt's or payment's **own** tag.

**Evidence (offline, both licences):** 288 Agst Ref allocations, **288 dangling**. The first four are `Inv/14`,
`Inv/15`, `Inv/16` and `Inv/17`, and all of those tags are receipts. The sales New Refs are `Inv/<sale tag>` (slots
i<8), and receipts are slots 13–16, so the names can never meet. The receipt amounts are also random
(`randint(5000.00, 50000.00)`) and unrelated to any invoice's outstanding amount.

**How it fails:** Tally either rejects an Agst Ref to an unknown bill, or it opens a new bill of that name. Which
one is unverified; the fake assumes the second (`fake_books.py:456-459`).
- **If it rejects:** the load pauses at tag 14 and the operator faces 288 manual vouchers.
- **If it opens a new bill (more likely):** each receipt opens a **+ (Cr) bill** under a debtor. By C34's own
  finding it lands in **Bills Payable**. Each party payment opens a **− (Dr) bill** under a creditor, in Bills
  Receivable. No sales invoice is ever knocked off.

**Consequences:**
- Bills Receivable is roughly every B2B sale plus 144 creditor payments, and Bills Payable holds 192 "debtor"
  receipts.
- Probe 6's "Receipts = Agst Ref" check passes structurally on nonsense.
- Probe 12's bills totals, probe 23's due-date / overdue split, and probe 18 bills all measure an impossible
  ledger state.
- The loader is idempotent by tag, so a finished run is not repaired by fixing the dataset. The 288 vouchers would
  need deleting, or the company restoring.

**Fix (before voucher 14 is sent):**
- In `_vouchers`, keep a per-party list of open New Ref bills with their outstanding amounts:
  `Inv/<sale tag>` for debtors and `Pur/<purchase tag>` for creditors.
- Build each receipt or payment **against a real open bill of the same party**, for an amount ≤ its outstanding.
  Either pay it in full, or split one voucher across several bills; the C34 guard already needs Σ bills = party
  line.
- Fall back to `On Account` (or no bills) when the party has nothing open.
- Keep the non-bill-wise debtor bill-less.
- Add a dataset test: every Agst Ref name exists as an earlier New Ref of the same party, and the running
  outstanding amount of every bill is never pushed past zero.
- Make the fake **refuse** (or at least record) an Agst Ref to an unknown bill, instead of silently opening one, so
  this can't regress.

### 2. Important: the USD export is not forex

**Where:** `company_b_data.py:269-282` builds `currency="USD"` and `fx_amount`. `company_b.py:351-370` never passes
them. `writes.create_b_voucher` has no currency parameter, and no Currency master is created in `_load_masters`.

**Failure scenario:** tags 101/102 (Sep 2022) land as INR sales of ₹37,216.04 and ₹95,897.68. Probe 22 then finds
plain decimals everywhere and either reports CONFIRMED for the wrong reason or measures nothing. Decision 15
(forex) gets settled on data that contains no forex. The loader is idempotent by tag, so a re-run never rewrites
them.

**Fix:** pick one of two paths:
- **(a)** Make it real:
  - Create the `USD` Currency master. It has no verified XML op, so this is probably a UI pause step like
    `Sales - GST`.
  - Set `CURRENCYNAME` on `Gulf Office Supplies LLC`.
  - Emit the forex AMOUNT form (`-$448.44 @ ₹82.99/$ = -₹37216.04`), or a plain INR amount plus the rate fields.
    Either needs its own live probe, the way Op 6/7 were probed, before 2 vouchers depend on it.
- **(b)** If (a) isn't ready, **skip tags 101/102 in this run**, leaving a hole the operator can fill later, and
  mark probe 22 blocked.

Either way, add an assertion that a voucher with `currency != "INR"` is never silently written as INR. In the
meantime, rename `test_a_sale_without_inventory_still_emits_every_line`'s docstring (finding 5).

A secondary point: `USD_DEBTOR` is `bill_wise=True`, but the export sales carry no bill. Tally will book the ledger
amount without a bill reference, so the party's bill-wise total won't equal its ledger balance.

### 3. Important: the compound-unit quantity string is unverified, and voucher 2 uses it

**Where:** `writes.py:318-323` sends `<RATE>{rate}/Box of 10 Nos</RATE>` and `<ACTUALQTY>{qty} Box of 10 Nos</ACTUALQTY>`.
In the dataset, `A4 Paper Ream` takes `item_names[tag % 5]`, which gives **tag 2**: the second voucher of the load.
95 sales use it.

**Failure scenario:** Tally reads compound quantities in the first unit ("5 Box", or "5 Box 3 Nos"). If it
mis-parses `"5 Box of 10 Nos"`, one of two things happens:
- It answers EXCEPTIONS=1 and the load pauses at voucher 2.
- Worse, it creates the voucher with a wrong quantity, and the Stock Summary / probe 15 go wrong silently. The
  loader never reads quantities back.

The tracker already lists this as a watch item (0b). No code guards it, and FakeBooks does not parse ACTUALQTY at
all.

**Fix:** after voucher 2 lands, read its inventory row back (`ActualQty`, `BilledQty`, `Rate`, `Amount`) and stop
if the quantity is not the one sent. If Tally wants the first unit, send `"{qty} Box"` / `"/Box"` for compound
items. Model whatever Tally accepts in the fake.

### 4. Important: FakeBooks applies C33 to reports, which contradicts the recorded evidence

**Where:** `fake_books.py:227-260`. `requested_period` drives both the voucher collections **and** the Trial
Balance `as_on`.

**Contradiction:**
- `v2/probes/reads.py:53-54` says "Reports (wrap_report, TYPE=Data) honour both", and `p18_historical_reports.py:30`
  says the same.
- The production chat app's dated TB/P&L reads have worked with untyped variables. C33's live evidence
  ("all return 0 untyped") is a voucher **count**, which means a collection.
- The tracker then generalises to "every v2 dated read so far read the current period" and marks p16/17/18 suspect.

The code fix (always typing) is harmless either way. The fake and the narrative may be over-broad, though. If
reports do honour untyped variables, the p18 conclusions stand, and the fake enforces a rule Tally doesn't have.

**Fix:** after the load, run one cheap read-only live A/B: an untyped vs typed TB as-on a past date. Record which
request types C33 covers. Then scope `requested_period`'s fallback in the fake (collections only, or everything)
and update the reads.py / p18 comments to match.

### 5. Important: FakeBooks can still pass wrong shapes (false-passing tests)

What the fake still does not model, each of which Tally would reject or mis-book:
- Bills: Σ bills vs the party line, bills on a non-bill-wise ledger, and Agst Ref to an unknown bill (it silently
  opens one).
- References: ledger, stock item and unit existence.
- Inventory: `ALLINVENTORYENTRIES/AMOUNT` vs Σ its allocations, qty × rate vs AMOUNT, and the ACTUALQTY/RATE unit
  text.

The writer enforces the bill and amount rules itself today, so these are not live bugs yet. But they are
unprotected if the writer changes.

Tests that are green for the wrong reason:
- **`v2/tests/probes/test_company_b_data.py::test_every_bill_is_a_magnitude_matching_its_party_line`** passes with
  288/288 dangling Agst Refs (finding 1). It checks sign and total, never the name.
- **`v2/tests/probes/test_fake_books_masters.py::test_an_agst_ref_receipt_knocks_the_receivable_off`** proves
  knock-off on hand-built XML with a matching `Inv/1`. No dataset voucher ever reaches that branch, so it
  gives false assurance that the dataset settles its receivables.
- **`v2/tests/probes/test_setup_writes.py::test_a_sale_without_inventory_still_emits_every_line`** has a docstring
  that calls it "the zero-rated export sale". It asserts ledger names only, and passes with the currency and rate
  dropped (finding 2).
- There is also a limitation, not a false pass: `test_company_b.py::test_a_first_load_lists_before_creating_and_reads_back_every_write`
  loads all 960 vouchers, including the 95 compound-unit sales, with no quantity-string check (finding 3).

### 6. Minor: `sign_check` cannot tell C30 from C21

**Where:** `v2/probes/setup/sign_check.py:1-8, 19`; `logs/sign-check-live-2026-09-24.log`.

It sends **−1.00 under Sundry Debtors**, a debit-natured group:
- Under C30 (the sign is read), that is Dr 1, exported as `-1.00`.
- Under C21 (the side is inferred from the group), it is also Dr 1, also exported as `-1.00`.

So the docstring's claim that "a positive 1.00 would mean … C21 stands" is wrong: neither hypothesis predicts
+1.00. The "Pune Digital Solutions 62,500 Dr" UI check is non-discriminating for the same reason.

C30 does stand, on company A's evidence: abs()'d HDFC/SBI openings landed as credits under Bank Accounts. That is
a real discriminator.

**Fix:** when Tally is free, send **+1.00 under Sundry Debtors**. C30 predicts `1.00` (Cr); C21 predicts `-1.00`.
Correct the docstring and the tracker's "live-verified" wording to cite the company-A evidence instead.

### 7. Minor: the new pre-send `ValueError`s crash the loader mid-run

`create_b_voucher` raises `ValueError` for the C32 allocation mismatch (`writes.py:279`) and for the C34 magnitude,
count and total checks (`:291, :297, :303`). `_load_vouchers` catches only `WriteFailed`
(`company_b.py:371`). This is the same class of problem M2 fixed for the ordering assert. Today the full-dataset
load test proves no current voucher trips these checks, but a dataset edit mid-load would give a traceback instead
of a `CompanyBLoadError` stop.

**Fix:** run the same validation for all vouchers up front, before the first send, with a `validate_b_voucher`
pure function. Or map `ValueError` to `CompanyBLoadError` naming the tag.

### 8. Minor: the dropped nominal line's flag isn't checked against the inventory flag

The nominal line's `deemed_positive` is discarded (`writes.py:282`). The inventory flag is derived from the voucher
type (`:311`). A caller that signs a Sales nominal line negative would pass the allocation check, because the
inventory amounts are negative too, and then send `No`/negative. Tally answers that with EXCEPTIONS=1. The fake
catches it; the writer doesn't.

**Fix:** assert `nominal deemed_positive == is_purchase_type`, and assert the sign of `nominal_amount`, before
sending.

### 9. Minor: asymmetric amount conventions

`bills` take magnitudes (C34), while `inventory` amounts are signed and must match the nominal line's sign (C32).
A future purchase-with-inventory caller reusing `InventorySpec.amount` (positive goods) will hit the C32
`ValueError`. That is safe, but surprising.

**Fix:** either document it in the `create_b_voucher` signature docstring, or take inventory magnitudes and sign
them from `is_purchase_type`, which mirrors production.

### 10. Minor (cross-reference, outside v2): production sends untyped date variables

`backend/tally_bridge/request_builder.py:92-93, 124-125` sends `<SVFROMDATE>`/`<SVTODATE>` untyped. The tracker
flags this as out of scope. If C33 holds for collections (see finding 4), the production voucher/register tools
may be answering for the current period rather than the requested window. This deserves its own ticket with a
live check. It must not be fixed on this branch (v2 isolation rule).

---

## Observation (not a code finding): run 3 is paused on the opening bill

`logs/setup-b-live-2026-09-24-run3.log` is waiting for the operator: "Opening bill 'Op/2022-001' … is not in Bills
Receivable as on 01-04-2022". The operator entered it in the UI during run 2, and tracker 0c notes it also does not
appear in the `Bill` collection. Possible causes:
1. It was entered under the wrong sign or party.
2. The now-typed as-on `01-04-2022` read excludes an opening bill dated on the books-start day.
3. The Bills Receivable report doesn't emit `BILLFIXED` for opening bills.

Before pressing Enter, check it in the UI (Display → Statements of Accounts → Outstandings → Ledger → Pune Digital
Solutions). Otherwise the pause repeats on every run.

## Not run

- No live Tally calls, by instruction.
- `tests/e2e_live`, eval, and the backend test suites were not run; `v2/` changes don't touch `backend/`.
- The Tally behaviour behind findings 1 (Agst Ref to an unknown bill), 3 (compound quantity text) and 4
  (untyped report variables) is unverified, and each needs one cheap live check once the load is idle.
