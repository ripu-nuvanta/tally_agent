# Bharat Traders demo company — setup guide

A canonical TallyPrime demo company for the TallyPrime AI Agent. Produced by
`scripts/seed_tally_data.py`; the resulting state is captured in a Tally backup
under `seed_data/`.

This guide covers two paths:

- **Restore from backup** (fast, recommended for everyone): use the captured
  `.tbk` to drop a ready-made `Bharat Traders Private Limited` into your Tally
  install in ~30 seconds.
- **Reseed from scratch** (for contributors changing fixtures or seeder code):
  re-runs the full seeder against an empty company.

Both paths require a few **Tally-install-scoped voucher-type toggles** that
don't travel via the .tbk — see [Required UI toggles](#required-ui-toggles).

---

## What's in the seeded company

- Company: `Bharat Traders Private Limited` (Maharashtra, GSTIN 27AABCB1234F1ZP, GST regular)
- FY: 1 April 2025 – 31 March 2026
- 35 ledgers (7 debtors, 5 creditors, 2 banks, 1 cash, expense accounts, GST tax ledgers, capital)
- 15 stock items across Electronics / Peripherals / Office Supplies (HSN + GST rates)
- **50 vouchers**: 16 Sales, 8 Purchase, 16 Payment, 10 Receipt
- Sales/Purchase carry REFERENCE = invoice number; Purchase carries REFERENCEDATE = voucher_date − 2 days
- BILLALLOCATIONS populated:
  - Sales/Purchase use `New Ref` (one bill per invoice, gross incl GST)
  - Receipts use `Agst Ref` against the matching sales bill — clears the receivable
  - 4 party Payments use `Agst Ref` against the matching purchase bill — partial settlement, residual remains
  - 12 expense Payments (Rent/Salaries/etc.) carry no allocation

### Expected end state (as on 31-03-2026)

**Bills Receivable** — 6 bills, **₹9,70,537** total:

| Party | Bill | Outstanding |
|---|---|---|
| Apex Technologies Pvt Ltd | S015 | ₹62,800 |
| Sunrise Electronics Mumbai | S010 | ₹1,66,380 |
| Global IT Solutions | S016 | ₹3,72,880 |
| Sharma & Sons Traders | S011 | ₹16,365 |
| Rajesh Computers | S013 | ₹1,64,492 |
| Eastern Digital Hub | S014 | ₹1,87,620 |

(Patel Enterprises: S005+S012 fully cleared → ₹0)

**Bills Payable** — 8 bills across 5 parties, **₹18,34,142** total:

| Party | Bill | Outstanding | Note |
|---|---|---|---|
| Samsung India Electronics | P001 | ₹2,43,100 | residual after PMT001 ₹4,00,000 |
| Samsung India Electronics | P004 | ₹4,98,550 | unpaid |
| HP India Sales Pvt Ltd | P002 | ₹2,22,160 | residual after PMT002 ₹5,00,000 |
| HP India Sales Pvt Ltd | P005 | ₹4,88,048 | unpaid |
| Logitech India Pvt Ltd | P003 | ₹1,17,270 | residual after PMT005 ₹1,50,000 |
| Logitech India Pvt Ltd | P007 | ₹1,20,950 | unpaid |
| Local Stationery Mart | P006 | ₹62,464 | residual after PMT009 ₹80,000 |
| Bharat Paper Supplies | P008 | ₹81,600 | unpaid |

The canonical figures live in `scripts/seed_data/bharat_traders.py`
(`EXPECTED_BILLS_RECEIVABLE`, `EXPECTED_BILLS_PAYABLE`).

---

## Required UI toggles

These are **Tally-install-scoped** — they don't travel via .tbk and must be set
manually in the UI on the machine running Tally, before either seeding or
relying on the restored data. (See `LESSONS.md` §14 and
`docs/tally-write-exploration-v4.md` § "REFERENCEDATE — supplier invoice date
(toggle-gated)".)

1. **Purchase voucher type → "Use supplier invoice date" = Yes**
   Gateway of Tally → Alter → Voucher Types → Purchase → set "Use supplier
   invoice date for vouchers" to **Yes**. Without this, REFERENCEDATE on
   purchase imports is silently dropped.
2. **Sales voucher type → Numbering → "Automatic (Manual Override)"**
   Gateway of Tally → Alter → Voucher Types → Sales → Method of Voucher
   Numbering = **Automatic (Manual Override)**. Without this, Tally renumbers
   sales vouchers and breaks the S001/S002/... naming convention.

---

## Path 1 — restore from backup

### Backup location

`seed_data/` in this repo contains the raw Tally backup:

```
seed_data/
├── TDBK1800_100003.001     ← Tally backup file
└── 100003/                 ← unpacked company data folder
```

The folder name `100003` is the company number Tally assigned when the backup
was taken. Tally's restore step will recreate the company under
`Bharat Traders Private Limited` regardless of folder name.

### Restore procedure (TallyPrime 7.0+)

1. **Set up the toggles** above first if you haven't.
2. **Gateway of Tally** → press **F3** → **Restore**.
3. Set **Source** to the directory containing the backup (e.g.
   `<repo>/seed_data`). Tally will scan the folder and offer to restore the
   company found there.
4. Confirm **Destination** (your Tally `Data` directory — accept the default
   unless you've configured otherwise).
5. Restore. The company `Bharat Traders Private Limited` will appear in the
   company list.
6. Open the company. Press **F2** and set the working date to **08-May-2026**
   (or any date ≥ 01-Mar-2026 — the latest seeded voucher).
7. Optional sanity check (from the repo root):
   ```bash
   PYTHONPATH=. python scripts/verify_tally_bridge_live.py \
       --host localhost --port 9000 \
       --company "Bharat Traders Private Limited"
   ```
   Should print 14 OK lines including `bills_receivable >= 6 — got 6` and
   `bills_payable >= 5 — got 8`.
8. Optional per-bill check — see [Verifying outstanding bills](#verifying-outstanding-bills).

---

## Path 2 — reseed from scratch

Use this when you've changed `scripts/seed_data/bharat_traders.py` or
`scripts/seed_tally_data.py` and want to regenerate the company.

> ⚠ **One-shot per company.** Per `docs/tally-write-exploration-v4.md`, once
> any master is referenced by a voucher Tally permanently locks it. To iterate,
> create a new empty company.

### Steps

1. **Set up the toggles** above on your Tally install.
2. **Tally UI**: rename any existing `Bharat Traders Private Limited` (e.g. to
   `Bharat Traders V_<n>`) to preserve probe artifacts, then **Create
   Company** → `Bharat Traders Private Limited`:
   - Period: 01-04-2025 to 31-03-2026
   - State: Maharashtra
   - GSTIN: 27AABCB1234F1ZP
   - GST registration: Regular
   - No company-default GST rate
3. **Tally UI**: press **F2** at Gateway of Tally and set the working date to
   **08-May-2026** (or any date ≥ 01-Mar-2026). The seeder's preflight
   check would otherwise abort because a fresh company starts at FY-start.
4. Run the seeder:
   ```bash
   PYTHONPATH=. python scripts/seed_tally_data.py \
       --host localhost --port 9000 \
       --company "Bharat Traders Private Limited" \
       --skip-preflight
   ```
   `--skip-preflight` is the project default — see
   `memory/feedback_skip_preflight_seeder.md`.
5. Run the verifier (same command as in Path 1, step 7).
6. Verify per-bill residuals — see next section.

### Why not patch in place?

`scripts/patch_bill_allocations.py` exists as a one-off (the in-place patch
that retrofitted Agst Ref onto an already-seeded company). For a fresh seed it
isn't needed — the seeder now writes BILLALLOCATIONS directly. Keep the patch
script around in case you need to surgically retrofit an existing seeded
instance after a fixture change.

---

## Verifying outstanding bills

Quick Python check that the per-bill residuals match `EXPECTED_BILLS_*`:

```bash
PYTHONPATH=. python -c "
import asyncio
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.reports import bills_receivable, bills_payable
from scripts.seed_data import bharat_traders as bt

async def main():
    c = TallyClient(host='localhost', port=9000)
    company = 'Bharat Traders Private Limited'
    br = await bills_receivable(c, '31-03-2026', company=company)
    bp = await bills_payable(c, '31-03-2026', company=company)
    actual_br = {(b.party_name.strip(), b.bill_number.strip()): float(b.pending_amount) for b in br}
    actual_bp = {(b.party_name.strip(), b.bill_number.strip()): float(b.pending_amount) for b in bp}
    exp_br = {(p, n): float(a) for p, n, a in bt.EXPECTED_BILLS_RECEIVABLE}
    exp_bp = {(p, n): float(a) for p, n, a in bt.EXPECTED_BILLS_PAYABLE}
    fail = sum(1 for k, e in {**exp_br, **exp_bp}.items()
               if abs(({**actual_br, **actual_bp}.get(k, -1)) - e) > 0.5)
    print(f'BR {len(actual_br)}/{len(exp_br)} bills, BP {len(actual_bp)}/{len(exp_bp)} bills, '
          f'{fail} mismatches')
    await c.close()
asyncio.run(main())
"
```

Expected: `BR 6/6 bills, BP 8/8 bills, 0 mismatches`.

---

## Distributing the backup (future)

When/if we want to publish the backup outside the repo:

1. `gh release create stage1-seed-v<n> seed_data/TDBK1800_100003.001 \`
   `--title "Bharat Traders demo seed v<n>" \`
   `--notes-file docs/seed-data-release-notes.md`
2. Add a `sha256` to the release notes for tamper-checking.
3. Update Path 1's "Backup location" section to point at the release URL +
   download instructions.

Currently the `.tbk` is committed at `seed_data/TDBK1800_100003.001` — the
size (~110 KB) is small enough to live in the repo, so we can defer Release
publishing until there's a reason to slim git or version the backup
externally.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Verifier reports `day_book < 50` | Tally's F2 date was earlier than the latest voucher (2026-03-01); writes past the F2 date silently dropped | Press F2 in Tally UI, set to ≥ 01-Mar-2026, delete the partial company, recreate empty, reseed |
| `bills_payable` shows 4 bills instead of 8 | Purchase "Use supplier invoice date" toggle off → REFERENCEDATE dropped, but BILLALLOCATIONS shouldn't be affected. If counts are off, check that the seeder ran the vouchers phase to completion | Verify toggles, re-check seeder log |
| Bill names show as integer voucher numbers (e.g. `1`, `2`) instead of `S001`/`P001` | Sales numbering toggle isn't on "Automatic (Manual Override)" | Set it in voucher type, then re-seed (full reset required — Tally won't backfill) |
| Receivable totals are off by ~18% on every bill | Receipt amounts in fixture were base, not gross. Check `RECEIPTS` rows in `bharat_traders.py` — they should be at gross | Already fixed in current seeder; if you see this on an older backup, restore the latest `.tbk` |

---

## Manual UI inspection

License not detected: 
- Change hostname to last known hostname from terminal; 
- Always check if EDU mode or licensed Silver/Gold plan on left side
- Some paths for reports: Go To -> Voucher Reports -> Sales, Purchase, More -> Credit Note, Debit Note, Journal, Receipt, Payment etc.
- Adding reference/supplier info to voucher types: Gateway -> Alter -> Voucher Type -> Sales, Purchase, Payment, Receipt etc.  
- Go To -> Registers -> Sales / Purchase
- Alter -> Stock Groups, Stock Items etc. 



