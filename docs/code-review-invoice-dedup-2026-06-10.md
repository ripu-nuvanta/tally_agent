# Code review — invoice-entry Phase 1 (feat/invoice-dedup-reference)

Date: 2026-06-10. Two finder passes (correctness/dedup + hard-block/FE/maintainability).

## Findings

### 1. [CRITICAL] Hard block trusts client-sent `entry["status"]` — bypassable + breaks edit-to-correct
`voucher_action` blocks only when `entry.get("status")=="duplicate"`. `entry` is client JSON, so a client
can send `status:"draft"` and bypass the "hard block." It also breaks the spec's edit path: a user who
edits a duplicate to fix a mis-read invoice no. stays blocked (status sticks) — or, if the client clears
status, bypasses entirely. Both wrong.
**Fix:** in `voucher_action`, **re-derive** the duplicate server-side on approve/edit by re-running the
business-key check (`find_duplicate` on party + reference against VoucherEntry + Tally), ignoring the
client `status`. Block if it's a dup; allow if the edited reference is no longer a dup. This makes the
block authoritative AND supports edit-to-correct in one move. (B1 file-hash dup is caught at upload; the
write-time re-check is the B2 party+reference key, which is what an edit changes.)

### 2. [MEDIUM] Dedup keys not normalized (whitespace/case)
`dedup.py` compares party/reference with exact `==`. OCR/Vision artifacts ("INV-100 ", "inv-100\n")
cause silent misses → the same invoice writes twice. **Fix:** normalize (strip + casefold) both sides of
the party and reference comparison in B2 (DB + Tally).

### 3. [LOW] Test gap — edit-a-duplicate-then-write path untested
Add tests: (a) server blocks a write even when client sends `status:"draft"` for a known dup;
(b) editing the reference to a non-duplicate value allows the write; (c) trimmed/case-different
reference still matches.

## Confirmed safe (not bugs)
B1 self-row excluded (`exclude_file_id`); per-workspace scoping (B1 + B2 + Tally); Tally-error swallow
(B1/DB-B2 still apply); reference_date YYYYMMDD validation; reference XML-escaped; empty reference emits
nothing; migration 003 nullable+indexed+downgrade; reference field naming consistent FE↔BE; invoice #
null renders "—"; reason strings single-sourced in backend.

## Disposition
Fix 1 (critical) + 2 + 3 on this branch with tests, then merge.
