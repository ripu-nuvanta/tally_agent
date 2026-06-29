# Edit-flow correctness + edit-history version trail + file_id linkage (2026-06-29)

Manual-testing-driven fixes and two features for the DB-mode upload → review → edit → write flow.
Committed locally on `feat/connect-modal-improvements` (`1735e8c`/`5c040e4`). No standalone spec preceded these
(they were reactive bug fixes); this doc is the canonical reference. One-line summary lives in
`CLAUDE.md` § Implementation Phases; status in `docs/roadmap.md`.

## 1. Edit-flow correctness fixes

| Fix | Was | Now |
|---|---|---|
| Edit **Save** | routed to the backend `edit` action → **wrote to Tally early** + the card showed stale values | a **local merge** that updates the card in place; persisted via `save_draft` (no write) |
| Draft edits on refresh | lost (only `messages.data` overwrite, never persisted) | persisted via new `save_draft` action + `_update_persisted_voucher_entry` → survive reload |
| Voucher-action result messages (written/discarded/duplicate) | shown live, **lost on refresh** | persisted via `_persist_action_response` → survive reload |
| Inventory edit | line amount recomputed, but header **total + GST stayed stale** → inconsistent voucher | recomputes `amount = Σ(lines) + GST` and scales GST proportionally to the new taxable |
| Upload intro text | baked in `— ₹{amount} on {date}` → **went stale after an edit** | states only the party; amount/date live solely on the card |

Note: the production inventory write path always recomputed the gross from line items
(`import_builder.compute_invoice_gross`, "Vision's total is stale"), so Tally was never wrong — the bug was
display/audit only. See `LESSONS.md` §15 (ISINVOICE GST recompute, bill-wise reporting).

## 2. Edit-history version trail

Every version of a card entry is snapshotted in a new table **`voucher_entry_revisions`** (migration **004**):
`id, workspace_id, conversation_id, entry_id, version_no, source ('upload'|'edit'|'write'), voucher_data (jsonb), file_id, created_at`.

Recorded at three hooks in `backend/api/chat.py` via `_record_voucher_revision()`:
- **upload** → `v1` (`source='upload'`) — the original card entry
- **save_draft** → `v+1` (`source='edit'`)
- **write success** → `v+1` (`source='write'`) (alongside the `voucher_entries` audit row)

## 3. Data lineage — original vs current vs history

| What | Table | Column | Behavior |
|---|---|---|---|
| **Original** (as extracted) | `uploaded_files` | `extracted_data` | immutable — never changes |
| **Current / editable card** | `messages` | `data.entries[]` | overwritten in place on each Save |
| **Full version trail** | `voucher_entry_revisions` | `voucher_data` (one row/version) | append-only |
| **Write audit** | `voucher_entries` | `voucher_data` | one row per successful write |

## 4. file_id linkage (migration 005)

The card entry now carries `file_id` (`orchestrator.py` — base + inventory entry dicts), and
`voucher_entry_revisions.file_id` is a real FK. So all four layers **join on one key**:

```
uploaded_files.id  =  messages.data.entries[].file_id  =  voucher_entry_revisions.file_id  =  voucher_entries.file_id
```
Plus `messages.data.entries[].id = voucher_entry_revisions.entry_id` ties a card to its version trail, and
`conversation_id` (real FK) groups everything in one chat.

**Backfill** for legacy rows: `scripts/backfill_entry_file_id.py` (idempotent, `--dry-run` default / `--commit`),
matches on the *original* (v1) reference so edited cards still link; leaves genuinely-ambiguous historical rows null.

## 5. Tests

- Refresh round-trip (act → reload → re-assert the WHOLE state) — the discipline now in CLAUDE.md.
- `tests/e2e/test_db_voucher_revisions.py` — version trail + file_id join (incl. write path).
- `tests/e2e_live/test_db_write_live.py` — mock-Claude + live-Tally + real-DB write across 5 voucher types, with cleanup.
- Hierarchy ledger matching, billwise, inventory recompute, company-anchoring — unit + e2e.

## Migrations
- `004_voucher_entry_revisions.py`
- `005_voucher_revision_file_id.py`
