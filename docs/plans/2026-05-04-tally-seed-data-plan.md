# Plan: Programmatic Tally Seed + Distributable Backup

## Context

New devs need a working TallyPrime instance with realistic Bharat Traders data to develop against. CLAUDE.md and the README already reference `scripts/seed_tally_data.py` but the file doesn't exist on disk — the original sketch lives in `TALLYPRIME_AGENT_PLAN.md:1465-2062`.

The plan: verify the unproven Tally write envelopes (Stage 0), build the seeder using the project's existing import builders + fixture data (Stage 1), run it once against a fresh company "Bharat Traders Pvt Ltd", take a Tally backup, and distribute that backup so future onboarding is one click (Stage 2). The script remains the regenerable source of truth — when fixtures change, re-seed and re-backup.

This also exercises the write path end-to-end against live Tally — a forcing function that surfaces gaps before B1b (broader voucher-type support) lands.

## Status of the original seed script in `TALLYPRIME_AGENT_PLAN.md:1486-2062`

**Verdict: scaffold, not a runnable program — ~60% complete. Treat as a reference for the data, not the code.**

What's reusable:
- All data definitions (`GROUPS`, `LEDGERS`, `STOCK_GROUPS`, `STOCK_ITEMS`, `SALES_INVOICES`, `PURCHASE_INVOICES`, `PAYMENTS`, `RECEIPTS`) at lines 1624–1874. The same data already lives in `tests/fixtures/generate_fixtures.py:16-227`.
- Phase ordering and the high-level pipeline shape at lines 1979–2058.

What's broken or missing (so we can't just lift-and-shift):
1. **Missing builders.** Lines 1971–1973, 2042–2047 explicitly say "build_purchase_voucher_xml, build_payment_xml, build_receipt_xml follow similar patterns" — they're not implemented. Script would crash on `NameError` if executed.
2. **Missing `NAME.LIST` on every master.** Per `docs/tally-write-exploration.md:62, 318, 326`, omitting this causes a Tally memory-violation crash. The script omits it everywhere.
3. **Missing `SVCURRENTCOMPANY`** in `REQUESTDESC`. Without it Tally writes to whatever company is currently loaded — brittle for an unattended seeder.
4. **No XML escaping.** Raw f-string interpolation will corrupt the XML for any name/narration containing `&`, `<`, `>` (the seed data has `&` in "Sharma & Sons Traders" and "Internet & Phone").
5. **Sales/Purchase envelope unverified.** The previous live attempt (`docs/tally-write-exploration-v3.log`) had Sales and Purchase create calls returning `EXCEPTIONS=1` despite the v3 attempt closely mirroring this script's structure. Hardcoded `Main Location` godown and `Primary Batch` may not exist in a fresh company.
6. **Missing GST tax line items.** Spec ships CGST/SGST/IGST ledgers but the sales builder doesn't emit tax entries — GST reports would be empty.
7. **Voucher envelope uses the older `<TYPE>Data</TYPE><ID>Vouchers</ID>` format**, while our verified path uses `<IMPORTDATA><REPORTNAME>Vouchers</REPORTNAME>`.
8. **No idempotency** — re-runs fail; partial failures leave inconsistent state.
9. **Doesn't reuse `backend/tally_bridge/import_builder.py`** — duplicates logic that's already proven for Payment/Ledger/Group.

So: keep the data, throw away the XML templating, build on top of the verified write path.

## What's already proven (and what's not) in the existing write path

`backend/tally_bridge/import_builder.py` + `writer.py` have **verified, working** builders for:
- `build_create_payment_voucher` (line 48)
- `build_create_ledger` (line 117) — used in production B1a
- `build_create_group` (line 139)
- `build_delete_voucher` / `build_cancel_voucher` / `build_delete_ledger` / `build_delete_group`

**Not yet verified against live Tally** (creates returned `EXCEPTIONS=1` in `docs/tally-write-exploration-v3.log`):
- Sales voucher with stock + GST (intra-state CGST+SGST and inter-state IGST, mixed-rate invoices)
- Purchase voucher with stock + GST
- Receipt voucher
- Journal voucher
- Stock item create with HSN code + per-item GST rate (18% electronics/peripherals, 12% paper/stationery)
- GST tax ledger create with `GSTDUTYHEAD` / `TAXTYPE` so tax auto-computes on vouchers
- Unit (UOM) create
- Stock group create
- Ledger opening balance setting

These are the unknowns Stage 0 must resolve before any seeder code is written.

## Approach — three stages

### Stage 0: Write exploration (resolve the unknowns) — ✅ CLOSED 2026-05-04

**Outcome:** All 9 write operations verified live against `Bharat Traders Private Limited`. Delete path mapped (4 verified-safe + 1 confirmed Tally MAV crasher on UNIT delete with `NAME=` attribute). FY-date constraint on voucher visibility discovered. Audit-lock behaviour on used masters fully characterised (no XML escape; UI-only cleanup). See **`docs/tally-write-exploration-v4.md`** for the verified envelope reference Stage 1 should build on.

Key gotchas locked in for Stage 1:
- Purchase voucher signs are inverse of sales (`party No/+, GST Yes/-, inv Yes/-, alloc Yes/-`).
- All voucher dates must be inside the company's active FY (otherwise CREATED=1 but invisible to reports).
- Voucher Master IDs read via Voucher collection with `<CHILDOF>$$VchTypeAllVouchers</CHILDOF>`.
- Voucher delete envelope uses `DD-MMM-YYYY` date attribute (NOT `YYYYMMDD`).
- `<UNIT NAME="X" ACTION="Delete">…</UNIT>` is a Tally crasher — never emit it from any tooling.
- Seeder is one-shot per company — re-running against a previously-seeded company leaves locked residue. Iterate via backup-restore or company recreate.

**Goal:** end with a verified, runnable XML envelope for each missing operation, plus parsed response showing `CREATED=1, ERRORS=0, EXCEPTIONS=0`.

Build `scripts/explore_tally_write_v4.py` (next iteration of the v1–v3 series). Each test:
1. Uses a `_Test Explore` namespace prefix on the live company so cleanup is mechanical.
2. POSTs the candidate envelope.
3. Parses response via `parse_import_response`.
4. On failure, logs the exact XML + response so we can iterate.
5. On success, records the canonical envelope to `docs/tally-write-exploration-v4.md`.

Operations to verify, in dependency order:
- **Unit (UOM) create** — `Nos`, `Pcs`. Required before stock items.
- **Stock group create** — `Electronics`, `Peripherals`, `Office Supplies`. Required before stock items.
- **Stock item create with HSN + per-item GST rate** — `BASEUNITS`, `OPENINGBALANCE`, `OPENINGRATE`, `OPENINGVALUE`, plus the GST/HSN block:
  - `<HSNCODE>` / `<HSNDETAILS.LIST>` — HSN code per item (e.g. monitors `8528`, laptops `8471`, paper `4802`, stationery `9608`).
  - `<GSTAPPLICABLE>` = `Applicable`.
  - `<GSTTYPEOFSUPPLY>` = `Goods`.
  - `<GSTDETAILS.LIST>` with `TAXABILITY=Taxable`, `IGSTRATE`, `CGSTRATE`, `SGSTRATE` (and effective `APPLICABLEFROM` date).
  - Two rate variants to verify: **18%** (electronics, peripherals — most items) and **12%** (paper, box files, whiteboard markers).
  - We chose company-level GST default = **None** during company setup, so per-item rates are the source of truth and must round-trip cleanly.
- **GST tax ledger create** — confirm CGST/SGST/IGST output + input ledgers under `Duties & Taxes` carry the right `GSTDUTYHEAD` / `TAXTYPE` / `RATEOFTAXCALCULATION` so they auto-compute on sales/purchase vouchers.
- **Ledger create with opening balance** — verify `OPENINGBALANCE` actually shows up in trial balance (may need `ISBILLWISEON` + offsetting "Opening Balance Difference" ledger).
- **Sales voucher with GST** — intra-state (Maharashtra → CGST+SGST) variant + inter-state (Delhi/Karnataka → IGST) variant. Verify:
  - Tax line items are auto-populated from the stock item's GST rate, OR explicitly emitted in `LEDGERENTRIES.LIST`.
  - Mixed-rate invoice (one 18% line + one 12% line) produces correct CGST/SGST/IGST split per line.
  - Party state vs. company state determines intra- vs. inter-state. Pin down `PERSISTEDVIEW`, godown handling (does `Main Location` exist in a fresh company? Probably not — investigate).
- **Purchase voucher with GST** — symmetrical to sales, party `ISDEEMEDPOSITIVE=Yes`, GST input ledgers.
- **Receipt voucher** — accounting-only, party debit / bank credit.
- **Journal voucher** — accounting-only, debit + credit ledger.

**Read-back verification per envelope:** after each successful create, query the same item back via the existing read path (`get_stock_item_details`, `get_voucher_by_id`) and assert HSN / GST rate / tax line amounts match what was sent. A `CREATED=1` response is necessary but not sufficient — Tally can accept malformed GST blocks silently and just drop the rate metadata.

Deliverables from Stage 0:
- `scripts/explore_tally_write_v4.py` (one runnable script that exercises every envelope).
- `docs/tally-write-exploration-v4.md` — verified envelope reference, supersedes prior versions.
- Cleanup helper extending `scripts/cleanup_tally_test.py` so iteration is fast.

**Stage 0 must complete before Stage 1.** If a verified envelope can't be reached for any operation, halt and re-plan.

### Stage 1: Seeder

Once Stage 0 is green:

**New files**
- `scripts/seed_tally_data.py` — orchestrator. CLI: `--host`, `--port`, `--company "Bharat Traders Pvt Ltd"`, `--dry-run` (build XML, don't POST), `--skip-existing` (catch "already exists" and continue), `--phases groups,ledgers,stock,vouchers` (run a subset).
- `scripts/seed_data/__init__.py` and `scripts/seed_data/bharat_traders.py` — extracted seed data constants lifted from `tests/fixtures/generate_fixtures.py:16-227`. Both seeder and fixture generator import from one place.
- `tests/unit/test_import_builder_voucher_types.py` — XML-structure assertions for the new builders (PERSISTEDVIEW, NAME.LIST, date format, ledger entry signs, GST tax lines).
- `tests/integration/test_seeder_smoke.py` — runs the seeder against the mock Tally handler; gated, no live API.
- `scripts/verify_tally_bridge_live.py` — read-side smoke runner against live Tally (see Tier 3 in Verification). No Claude API cost; runs every read query and asserts shape/counts.
- `fixtures/tally-backups/README.md` — restore instructions for the distributed backup; `.900` file goes to a GitHub Release (not committed).

**Modify**
- `backend/tally_bridge/import_builder.py` — add the verified builders from Stage 0:
  - `build_create_sales_voucher(date, party, items, gst_mode, company)` — `Invoice Voucher View`, `ALLINVENTORYENTRIES.LIST`, party `ISDEEMEDPOSITIVE=No`, CGST/SGST or IGST tax line based on `gst_mode`.
  - `build_create_purchase_voucher(...)` — mirror.
  - `build_create_receipt_voucher(date, party, amount, bank, company)`.
  - `build_create_journal_voucher(date, debit_ledger, credit_ledger, amount, narration, company)`.
  - `build_create_stock_item(name, group, uom, opening_qty, opening_rate, hsn_code, gst_rate, company)` — emits the HSN + GST block verified in Stage 0; per-item rates (no company default).
  - `build_create_unit(name, formal_name, company)`.
  - `build_create_stock_group(name, parent, company)`.
- `backend/tally_bridge/writer.py` — add `write_sales`, `write_purchase`, `write_receipt`, `write_journal`, `write_stock_item`, `write_unit`, `write_stock_group` methods. Each follows the existing pattern: pre-flight validation → build → POST → `parse_import_response` → raise on `EXCEPTIONS=1` or `LINEERROR`.
- `backend/tally_bridge/client.py` — bump write-path timeout to 90s (already noted as needed in `docs/tally-write-exploration.md:343`).
- `backend/tally_bridge/mock_handler.py` — extend to handle import envelopes (currently read-only) so the integration smoke test runs without live Tally.
- `tests/fixtures/generate_fixtures.py` — replace inline data constants with imports from `scripts/seed_data/bharat_traders.py`. Generation logic stays untouched so existing fixtures regenerate identically. Adds HSN code + GST rate fields to each stock item (currently absent in the spec) — backfill from the `STOCK_ITEMS` list using the 18% / 12% mapping noted above.
- `README.md` — add a "Sample data" section explaining backup restore (primary path) and seeder run (advanced path).
- `CLAUDE.md` — note that `scripts/seed_tally_data.py` is real now; document the manual create-company prerequisite.

**Critical Tally write gotchas to honour** (from `docs/tally-write-exploration.md` + `LESSONS.md`):
1. `NAME.LIST` mandatory on every master create/delete.
2. Voucher dates use `YYYYMMDD` (not `DD-MM-YYYY` used in queries).
3. Voucher date must be ≤ Tally's internal current date — if license is unactivated, this clamps. Seeder pre-flight check fetches Tally's current date and warns if seed dates exceed it.
4. Sales/Purchase need `<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>`; Payment/Receipt/Journal need `<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>`.
5. `EXCEPTIONS=1` with no `LINEERROR` = malformed XML — `parse_import_response` already raises.
6. Sequence: stock groups → units → ledgers (need parent groups) → stock items (need UOM + stock groups) → opening balances → vouchers (chronological by date, need ledgers + stock items).
7. 90s HTTP timeout for write operations.

**One manual step we accept:** Create-Company has no documented import envelope. Seeder requires an empty company already created via Tally UI (one-time, ~30s). Document in script `--help` and README.

### Stage 2: Backup distribution

1. From the seeded Tally: `F3 → Backup` → produces `.900` file.
2. Upload to a GitHub Release tagged `seed-data-v1`.
3. `fixtures/tally-backups/README.md` documents `F3 → Restore` for new devs.
4. README's "Sample data" section points there as the primary onboarding path; seeder remains the source-of-truth for regeneration.

## Reuse (don't reimplement)

- `backend/tally_bridge/import_builder.py:_wrap_import`, `_esc`, `_require` — XML envelope helpers; all new builders use these.
- `backend/tally_bridge/import_builder.py:build_create_ledger` (line 117), `build_create_group` (line 139), `build_create_payment_voucher` (line 48) — already verified working; seeder calls these directly.
- `backend/tally_bridge/writer.py:TallyWriter` — pre-flight validation (date format, balance, ledger existence) reused; new write methods plug in.
- `backend/tally_bridge/response_parser.py:parse_import_response` — handles `LASTVCHID`, `LASTMID`, `EXCEPTIONS`, `LINEERROR`. Seeder relies on its raise-on-error contract.
- `tests/fixtures/generate_fixtures.py:16-227` — the data definitions to extract into `scripts/seed_data/bharat_traders.py`.
- `backend/tally_bridge/client.py:TallyClient` — async HTTP client.
- `backend/tally_bridge/queries/` — every read query (masters, reports, vouchers); `verify_tally_bridge_live.py` calls each one against the seeded company.
- `scripts/cleanup_tally_test.py` — extend for Stage 0 cleanup.

## Verification — cheap → expensive ladder

Run each tier and gate the next on it passing. Don't burn Claude API credits debugging a bridge-layer bug.

**Tier 1 — Backend unit tests (no Tally, no API)**
```bash
pytest tests/unit/test_import_builder_voucher_types.py -v
pytest tests/unit/ -v
```
Asserts XML structure for each new builder: PERSISTEDVIEW present, NAME.LIST on masters, date format YYYYMMDD, ledger entry signs, GST tax line presence/absence based on intra/inter-state.

**Tier 2 — Mock integration (no Tally, no API)**
```bash
pytest tests/integration/test_seeder_smoke.py -v
pytest tests/integration/ -v
```
Seeder runs against `mock_handler.py`'s extended import endpoint; mock ends up with the expected counts of ledgers/vouchers. Existing read-side mock integration tests (`test_masters.py`, `test_reports.py`, `test_vouchers.py`) keep passing — proves the data shape didn't drift.

**Tier 3 — Live Tally bridge verification (real Tally, no Claude API)**

After seeding, before any LLM-involved test, run the bridge layer directly against the seeded company. This is the cheap forcing function — if a read query returns the wrong shape against a live Tally, fix it here, not by paying for Claude API tokens.

```bash
PYTHONPATH=. python scripts/verify_tally_bridge_live.py --host localhost --port 9000 \
  2>&1 | tee docs/tally-bridge-live-verify.log
```
Calls every function in `backend/tally_bridge/queries/` against the seeded company and asserts:
- `get_companies()` returns "Bharat Traders Pvt Ltd"
- `list_ledgers()` returns 30+ ledgers across the expected groups
- `get_trial_balance(FY 25-26)` totals match seed (sales ₹1,899,250 / purchases ₹2,619,700)
- `get_day_book(2025-10-01..2026-03-31)` returns 50 vouchers
- `list_stock_items()` returns 15 items
- `get_bills_receivable()` totals ₹824,650, `get_bills_payable()` totals ₹1,791,300

Also rerun the integration suite pointed at live Tally (env-var swap so `TallyClient` hits real host instead of mock fixture) — flushes out any regression that mock-only tests miss.

**Tier 4 — Live agent (real Tally + real Claude API, EXPENSIVE)**

Only run after Tier 3 is green.

```bash
python scripts/test_tally_connection.py
PYTHONPATH=. python scripts/test_agent_live.py --host localhost --port 9000 \
  2>&1 | tee docs/test-agent-live-seed.log
```
Ask the agent: "What's the trial balance for FY 25–26?" and "Show top 5 customers by sales." Sanity-check totals against spec.

**Tier 5 — Full e2e_live (real Tally + real Claude API, MOST EXPENSIVE)**

Only run after Tier 4 is green.

```bash
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v -s --host localhost --port 9000 \
  -k "trial_balance or top_customers or bills_receivable" \
  2>&1 | tee docs/e2e-live-seed-verify.log
```

**Distribution verification**
1. `F3 → Backup` → `.900` file → upload to GitHub Release.
2. On a clean machine: `F3 → Restore` → run Tier 3 against the restored company → must pass identically. (Skip Tiers 4–5 on the verifier machine — Tier 3 is sufficient proof of distribution fidelity.)

## Setup decisions already made (2026-05-04 session)

- Company "Bharat Traders Pvt Ltd" created in Tally UI: FY 2025-04-01 to 2026-03-31, Maharashtra, GSTIN `27AABCB1234F1ZP`, GST registration type **Regular**, periodicity **Monthly**, applicable from 01-04-2025.
- **Company-level default GST rate: NOT set.** Per-stock-item HSN + rate is the source of truth. Stage 0 must verify the per-item GST envelope round-trips correctly.
- TDS: not enabled — seed data has no TDS scenarios.

## Deferred / out of scope

- **Create-company envelope** — manual UI step accepted.
- **Set B1b voucher writes via the agent** — this plan only covers seeding. The same builders unblock B1b later; agent integration is its own design.
- **Multi-company seed** — one company is enough for onboarding.
- **Backup automation** — Tally backup/restore stays manual; not worth automating for a quarterly operation.
