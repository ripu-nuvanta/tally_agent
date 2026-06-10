# Spec — Invoice entry Phase 1: Supplier Invoice No. + duplicate blocking

**Date:** 2026-06-10
**Scope:** the document-upload → review → write flow (all 5 voucher types). Phase 1 of the
"proper invoice entry" feature. **Phase 2 (separate spec): inventory line items.**
**Decisions (locked):** duplicates = **hard block, no override**; dedup checks both the app DB
**and** Tally; per-workspace scope.

## Part A — Supplier Invoice No. (show + write)

- Vision already extracts `original_invoice_ref` (+ the invoice `date`). No prompt change needed.
- **Display:** review card shows `Invoice #: <ref>` (when present) for every voucher type; the
  edit form lets the user correct it.
- **Write to Tally:** map `original_invoice_ref` → the voucher `REFERENCE` field and the invoice
  date → `REFERENCEDATE` (YYYYMMDD). The `_render_reference_block()` helper already emits these;
  thread `reference`/`reference_date` through: orchestrator entry → `voucher_action` → writer →
  builder. The **ledger-based** builders (`build_create_purchase_voucher_ledger`,
  `..._sales_voucher_ledger`, `build_create_debit_note`, `build_create_credit_note`) and their
  `writer` methods must gain `reference`/`reference_date` params and emit the reference block.
- Entry dict gains `reference: str | None` and `reference_date: str | None` (YYYYMMDD).

## Part B — Duplicate detection (hard block, runs on upload)

Two independent checks; if **either** fires, the entry is returned with `status="duplicate"` and a
`duplicate_of` descriptor; the write is disabled (no override). Scope = the **workspace** (Tally company).

### B1 — Exact-file check
- Add `content_hash: str | None` (sha256 hex, indexed) to `UploadedFile` (+ Alembic migration).
- On upload, hash the raw bytes. If an `UploadedFile` with the same `content_hash` **and** same
  `workspace_id` already exists → duplicate (`reason="same file"`).

### B2 — Same-invoice (business key) check
- Key = **(party/supplier ledger, supplier-invoice-no)**; amount used as confirmation, not as key.
- Checked against:
  1. **App DB** — prior `VoucherEntry` rows in the workspace whose `voucher_data` has the same
     party + reference (status `written`).
  2. **Tally (authoritative)** — query the party's vouchers (`get_party_vouchers`) and match the
     extracted invoice no against their `Reference` field (catches invoices entered outside the app).
- If a match in either → duplicate (`reason="same invoice no for party"`, include the matched voucher number/date).

### Edge rules
- **No invoice number extracted** → skip B2 (can't key on it); only B1 applies. Surface a soft note
  "No invoice number found — duplicate check limited to exact-file."
- Match key is deliberately strict (party **and** invoice-no) so two genuinely different invoices
  don't collide under the hard block.
- Dedup is per `workspace_id`.

### Data flow
```
upload → sha256(bytes) + Vision extract
       → B1 (hash vs UploadedFile in workspace)
       → B2 (party+ref vs VoucherEntry + Tally get_party_vouchers)
       → if dup: entry.status="duplicate", entry.duplicate_of={voucher_no,date,reason}, write disabled
       → else: normal review card, now showing Invoice #
```

## Frontend
- `VoucherEntry` gains `reference`, `reference_date`, `duplicate_of` (`{voucher_no, date, reason}` | null).
- Review card: show `Invoice #: <ref>`; when `status==="duplicate"`, render a red banner
  *"Duplicate of voucher #N (written <date>) — <reason>. Not written."* and **disable Write to Tally**
  (Discard still allowed). Edit allowed (so a user can correct a mis-read invoice no, which re-runs the check on save/write).

## State matrix (review card)
| State | reference shown | status | Write button |
|---|---|---|---|
| normal, has invoice no | yes | draft | enabled |
| normal, no invoice no | "—" + soft note | draft | enabled |
| duplicate (same file) | yes | duplicate | **disabled** + red banner |
| duplicate (same invoice no) | yes | duplicate | **disabled** + red banner (shows matched voucher) |

## Testing
- **Unit:** sha256 hashing; B1 hash match (+ per-workspace isolation: same hash, different workspace → not dup); B2 business-key match against VoucherEntry; B2 against Tally `get_party_vouchers` references; no-invoice-no path (B2 skipped); reference/reference_date threaded into builder XML (`REFERENCE`/`REFERENCEDATE` present).
- **Integration (mock Tally + DB):** upload same file twice → 2nd `status=duplicate`, writer NOT called; upload same invoice-no via a different file → blocked; Tally-side reference match → blocked; distinct invoice → writes + reference present.
- **Frontend (Vitest):** card shows Invoice #; duplicate state disables Write + shows banner; non-dup enables Write.
- **Live-verify:** write `purchase_invoice.pdf` (invoice no set in Tally) → re-upload same PDF → blocked (file hash) → re-upload a re-saved copy (same invoice no, different bytes) → blocked (business key) → read back to confirm REFERENCE written; clean up.

## Fixture matrix
- Two PDFs with the **same** invoice no/party (different bytes) for the B2-different-file test.
- Reuse `tests/fixtures/pdf_flows/purchase_invoice.pdf` for B1.
- Vision JSON fixtures with/without `original_invoice_ref`.
- DB fixtures: a pre-existing `UploadedFile` (hash) + `VoucherEntry` (party+ref) to match against.

## Out of scope (Phase 2)
Inventory line items (stock-item match/create, qty/rate/units, per-item GST). Tracked separately.
