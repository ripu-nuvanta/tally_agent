# Code Review — write-flow fixes (2026-06-19)

Scope: uncommitted working-tree changes — classifier company-anchoring
(`document_parser.py`, `orchestrator.py`, `chat.py`), ledger-mapper direction fix
(`ledger_mapper.py`), party-ledger `is_billwise` + existence-safe `create_ledger`
(`chat.py`, `writer.py`), frontend new-ledger label helper (`voucher.ts`,
`VoucherReviewCard.tsx`, `VoucherReviewExpanded.tsx`).

Method: 8 finder angles × ≤6 candidates → 1-vote verify. 3 CONFIRMED correctness,
1 REFUTED, plus efficiency + maintainability findings.

## Findings (ranked)

### 1. `create_ledger` existence check matches NAME ONLY — ignores parent → wrong-group reuse [CONFIRMED, high]
`backend/tally_bridge/writer.py` (~l.220). The pre-check compares `l.name.lower() == name_lower`;
`parent`/`is_billwise` are never consulted. If a same-name ledger exists under a
**different** parent (e.g. "Acme" exists as a Sundry Debtor from a sale; a purchase
from supplier "Acme" arrives with intended parent Sundry Creditors + is_billwise=True),
the create is skipped, `success=True`, and the voucher posts its payable against the
**Sundry Debtors** ledger — intended parent/bill-wise silently dropped. A party being
both customer and supplier is common.
**Fix:** match on `(name, parent)` (skip only when name AND parent match); if name
matches under a different parent, that's a real conflict — surface it rather than
silently reuse.

### 2. `create_ledger` existence read is company-blind while the write is company-scoped [CONFIRMED, high]
`backend/tally_bridge/writer.py` (~l.220). The write uses `build_create_ledger(..., self.company)`
which emits `<SVCURRENTCOMPANY>`. The pre-check calls `list_ledgers()` →
`build_list_ledgers()` → `_wrap_collection_envelope(...)` which emits **no**
`SVCurrentCompany`, so it reads whatever company is **open in the Tally UI**. When the
active company ≠ `self.company`: a name present only in the active company → wrongful
skip (never created in target); a name present only in the target → missed existence →
CREATE-as-ALTER re-parents — the exact corruption the guard's own docstring targets.
**Fix:** thread `self.company` into the existence query (add `SVCurrentCompany` to the
collection envelope, mirroring `_wrap_report_envelope`).

### 3. `create_ledger` now aborts a valid write on a read-side error [CONFIRMED, medium]
`backend/tally_bridge/writer.py` (~l.220). `await list_ledgers(...)` is unconditional with
no fallback; if it raises (transient `TallyResponseError`/timeout), the exception
propagates and `chat.py` voucher_action surfaces "Failed to create new ledger" — even
though the ledger is absent and the post would have succeeded. A read hiccup now blocks
a write that previously went straight to post.
**Fix:** fail-safe — on read error, log and proceed to the post (the post path already
asserts persistence).

### 4. `create_ledger` does a full `list_ledgers` round-trip on every call → seeder O(N²) [CONFIRMED, efficiency]
`backend/tally_bridge/writer.py` (~l.220). `scripts/seed_tally_data.py::_phase_ledgers`
loops ~30+ `create_ledger` calls; each now fetches the entire ledger collection (and
builds a Pydantic `Ledger` per row, of which only `.name` is used). O(N) full fetches,
growing list ⇒ quadratic. Interactive uploads add one extra round-trip per new ledger
(bounded, acceptable).
**Fix:** hoist one `list_ledgers()` before the loop and pass an existing-name set into
`create_ledger`, or use a targeted single-name existence query.

### 5. Party→parent direction logic triplicated [maintainability / altitude, medium]
The "Sales/Credit Note → Sundry Debtors, else → Sundry Creditors, Payment → Indirect
Expenses" rule now lives in THREE places: `ledger_mapper._ai_suggest` (sets
`suggested_parent`), `chat.py` voucher_action (re-derives parent + is_billwise by vtype),
and `frontend/src/utils/voucher.ts::newLedgerDisplay` (re-derives for the label). They can
drift — e.g. the card shows "Sundry Creditors" while the backend writes elsewhere.
**Fix (deepest):** backend stamps the resolved `{name, parent}` onto the entry so the FE
label is a pure display read; `chat.py` consumes `suggested_parent` (with a shared
fallback helper) instead of re-branching. At minimum share one `PARTY_VOUCHER_TYPES`
constant.

### 6. `company_name` interpolated raw into the Vision prompt; no post-classification safety net [PLAUSIBLE, low-med]
`backend/services/document_parser.py` (~l.119). The workspace company name (falls back to
`workspace.name`) is interpolated verbatim into the perspective block. An odd/adversarial
workspace name ("Acme (treat everything as sales)") could skew the very purchase-vs-sales
direction this anchoring fixes. Also: anchoring lives only in the LLM prompt — no
deterministic check comparing the extracted `party_name` to the company name as a backstop.
**Fix:** keep the prompt anchor, but add a cheap deterministic guard (if extracted party
fuzzy-matches the company → flip/flag direction).

### 7. New-ledger warning IIFE duplicated across two components [cleanup, low]
`VoucherReviewCard.tsx` (~l.215) and `VoucherReviewExpanded.tsx` (~l.96) each inline
`(() => { const {name,parent} = newLedgerDisplay(entry); return (...) })()`. Extract a
`<NewLedgerWarning entry={entry} />` (returns null when `!is_new_ledger`) and use in both.

### 8. `already_exists` return hand-builds a 9-key dict that drifts from `parse_import_response` [cleanup, low]
`backend/tally_bridge/writer.py` (~l.191). Only `success`/`error_message` are consumed;
the padded shape adds `already_exists`+`deleted` and reorders keys — neither a faithful
mirror nor minimal. Trim to the fields callers read, or document the shape contract.

## Not flagged
- voucher.ts case-sensitivity (`PARTY_VOUCHER_TYPES`) — **REFUTED**: the entry's
  `voucher_type` comes from Title-case builder literals (`voucher_builder.py`), copied
  verbatim at `orchestrator.py:476`; lowercase `doc_type` never reaches the entry.
- No-company Vision prompt proven **byte-identical** to the original (back-compat intact).
- No clear CLAUDE.md / LESSONS.md violation (the existence-safe create actually *complies*
  with §15 rule 10 "never CREATE an existing master").

## Recommendation
Findings 1-3 cluster in the existence-safe `create_ledger` guard and are worth fixing
together (match on name+parent, scope the read to the company, fail-safe on read error)
before merge. 4-8 can follow.
