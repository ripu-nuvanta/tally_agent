# Spec — Invoice entry Phase 2: inventory line items

**Date:** 2026-06-10
**Scope:** the document-upload → review → write flow for **Purchase & Sales** invoices that have
itemised line items. Phase 2 of "proper invoice entry" (Phase 1 = invoice no. + dedup, merged).
**Decisions (locked):** unmatched items → **user picks/creates in the card**; default unit **"Nos"**;
**goods-vs-services detection** (qty present → inventory, else accounting-only); new items → a
**configurable default stock group** (fallback "Primary"); **DN/CN stay accounting-only** for now.

## Trigger
In `process_file_upload`, for `doc_type ∈ {purchase, sales}`: if the doc has line items **with a
quantity**, route to the **inventory** path; otherwise keep the current **accounting-only** ledger
voucher (services/expenses unchanged). Payment/DN/CN unchanged.

## Pipeline

### 1. Vision (`document_parser.py`)
- Add `unit` to the per-line `line_items` schema (string, e.g. "Nos"/"Pcs"/"kg"; null if absent).
- `LineItem` gains `unit: str | None`. Default to `"Nos"` when null at build time.
- (Already extracts description/quantity/rate/gst_rate.)

### 2. Stock-item resolver (new `backend/services/stock_resolver.py`)
- `async def resolve_line_items(client, doc, *, direction) -> list[ResolvedLine]` where each
  `ResolvedLine` = `{description, qty, rate, unit, gst_rate, amount, matched_item: str|null, suggested_name}`.
- Fetch `list_stock_items(client)`; for each line, **fuzzy-match** the description to an existing stock
  item name (normalised contains / token overlap; pick best above a threshold) → `matched_item`; else
  `matched_item=None` and `suggested_name = description`.
- Pure-ish (Tally read only); deterministic matching, unit-tested.

### 3. Review entry + card
- Entry gains `line_items: ResolvedLine[]`, `is_inventory: bool`, and a per-workspace
  `available_stock_items: string[]` + `default_stock_group`.
- **Review card** renders a **line-items table**: description, qty, rate, amount; per line a control:
  **dropdown to match an existing stock item OR "Create new"** (with name/unit/GST/group editable when
  creating). Qty/rate/unit editable. The voucher amount is **derived from the lines** (base) + GST.
- INR/accounting-only invoices (no qty) render as today (no table).

### 4. Write (`voucher_action`)
- For an inventory voucher: for each line marked **create-new**, pre-flight **ensure the unit exists**
  (`create_unit` if missing) and the **stock group exists** (default group, create if missing), then
  `create_stock_item(name, group, uom, hsn?, gst_rate, opening 0)`. (Idempotent: skip if already exists.)
- Then call the **inventory builder** via `writer.create_purchase_voucher` / `create_sales_voucher`
  with item tuples `(name, qty, rate, ledger, uom, gst_rate)`, `gst_mode` from intra/inter, plus the
  Phase-1 `reference`/`reference_date` and the `New Ref` bill allocation. Items land in the stock grid
  with qty/rate; GST computed per rate bucket by the builder.
- Phase-1 **duplicate hard-block** still re-derived server-side before writing.

## Data flow
```
upload → Vision (line_items + unit) → goods? (qty present)
  ├─ yes → resolve_line_items (match/suggest) → entry.line_items + is_inventory=true → card line-table
  │         → write: create missing units/group/stock-items → create_purchase/sales_voucher (inventory)
  └─ no  → accounting-only ledger voucher (current Phase-1 behaviour)
```

## State matrix (review card)
| State | line table | per-line control | Write |
|---|---|---|---|
| goods invoice, all items matched | shown | dropdown = matched item | enabled |
| goods invoice, some unmatched | shown | unmatched rows show "Create new" (name/unit/GST/group) | enabled |
| services/expense (no qty) | hidden | — (accounting-only) | enabled |
| duplicate (Phase 1) | shown read-only | — | disabled (banner) |

## Testing
- **Unit:** Vision unit extraction (present/absent→"Nos"); `resolve_line_items` fuzzy match (exact, partial, no-match→new); item-tuple assembly `(name,qty,rate,ledger,uom,gst_rate)`; goods-vs-services detection; new-item field assembly (group default, gst from line, hsn passthrough).
- **Integration (mock Tally + DB):** upload goods purchase → inventory voucher built with items + correct GST; an unmatched line → stock-item create called then voucher; services invoice (no qty) → accounting-only (regression); sales mirror.
- **Frontend (Vitest):** line-items table renders qty/rate/amount; match dropdown + create-new fields; editing qty/rate recomputes total; accounting-only invoice shows no table; duplicate state still blocks.
- **Live-verify:** upload `tests/fixtures/pdf_flows/purchase_invoice.pdf` → items appear in the Tally **stock grid** with qty/rate (like seeded voucher No. 8) + GST split + supplier invoice no. → read back inventory entries → clean up.
- **Playwright:** line-items card states × viewports.

## Fixture matrix
- Vision JSON: goods purchase (qty+rate+unit), goods sales, a line with no unit (→"Nos"), a services invoice (no qty), a line matching a seeded item + a line that's new.
- Reuse seeded stock items (A4 Paper Ream, etc.) + `pdf_flows/purchase_invoice.pdf`.

## Out of scope
DN/CN inventory (stay accounting-only); godown/batch; multi-godown; auto-HSN lookup (use Vision's HSN if present, else blank).
