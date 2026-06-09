# Code analysis — write-flow implementation (2026-06-09)

Read-only analysis across 4 lenses (architecture, correctness/edge-cases, security, maintainability/tests)
of the document-upload → Vision → classify → review → Tally-write pipeline. No code changed.
Reconciled against this session's merged fixes (so already-fixed items are not re-listed as open).

## Verified working / strong
- **End-to-end correctness proven live**: real Vision → classify → live Tally write → read-back, all 5 voucher
  types, correct posting direction (DN reduces payable, CN reduces receivable), GST split to Input/Output
  ledgers, books restored. (`logs/manual_test_*_live.log`.)
- **Security controls confirmed**: XML escaping (`_esc`) on all user/Vision strings; tenant isolation
  (`user_id` in every workspace/conversation query); secrets not logged; JWT (32+ char, HS256, expiries);
  UUID file storage prevents path traversal; `TALLY_WRITE_ENABLED` enforced server-side; `_assert_created`
  raises on `CREATED=0`/`EXCEPTIONS=1` (silent-drop guard).
- **FX is centralized & deterministic** (`_resolve_fx`, `_round_inr` single source, `_fx_trail` shared);
  no-rate writes blocked; rate-override recompute hardened. DN/CN direction fixed + live-verified.

## Open findings (prioritized — none are regressions; correctness is proven, these are hardening/quality)

### Security
| # | Finding | Severity | Where |
|---|---|---|---|
| S1 | **SSRF: user-controlled `tally_host`/`tally_port`** has no validation — a workspace could point the backend at internal addresses (e.g. cloud metadata, localhost services). Add an allowlist / block private+link-local ranges. | **HIGH** | `api/workspaces.py`, `api/tally.py` test-connection |
| S2 | No **rate limiting** on `/chat/upload` and `/chat/voucher-action` (write spam / Tally queue exhaustion). | MED | `api/chat.py` |
| S3 | File type validated by **extension only** (no magic-bytes). Mitigated by UUID storage in a non-web dir, so practical risk is low. | LOW–MED | `api/chat.py`, `document_parser.py` |

### Architecture / maintainability
| # | Finding | Severity | Where |
|---|---|---|---|
| A1 | **Entry-dict contract is untyped** (`VoucherActionRequest.entry: dict[str,Any]`). A `VoucherReviewEntry` Pydantic model exists but isn't used to validate. Wire it up to catch malformed entries at the boundary. | HIGH | `api/models.py`, `api/chat.py` |
| A2 | **Sign convention encoded in ~5 places** (voucher_builder `party_on_debit`, import_builder XML, writer validation, chat dispatch, docstrings). Extract a single source (a `voucher_type → (party_on_debit, gst_direction, bill_type)` config) so a new type is one line. | HIGH | builder/writer/chat |
| A3 | **`debit_ledger`/`credit_ledger` are semantically overloaded** per voucher type (party vs contra vs expense). The frontend must know `voucher_type` to interpret them. Consider explicit `party_ledger`/`contra_ledger` naming. | MED | orchestrator/chat/frontend |
| A4 | **Chat dispatch is a copy-pasted 5-branch if/elif ladder.** Replace with a dispatch table keyed by voucher_type. | MED | `api/chat.py` voucher_action |
| A5 | **Dual Purchase/Sales builder families** (stock-based seeder vs ledger-based agent path) with no shared base → drift risk. Document the ledger-based as canonical + stock as frozen-seeder; ideally unify on `_build_ledger_invoice_voucher`. | MED | `import_builder.py`, `writer.py` |
| A6 | **INR formatting duplicated** backend (`currency_format.py`) ↔ frontend (`format.ts`). Magic strings `bill_type`/`rate_source` → use Enums/`Literal`. | LOW | both |

### Correctness edge cases (all currently caught by Tally or surfaced as warnings; hardening)
| # | Finding | Severity | Where |
|---|---|---|---|
| C1 | **DN/CN with no original-invoice reference** → silently posts "On Account" (no Agst Ref), no warning. Add a warning when DN/CN lacks a reference. | MED | `document_parser.validate_extracted_amounts`, orchestrator |
| C2 | **Currency missing from Vision → defaults to INR**: a foreign doc could be treated as INR silently. Warn when `fx_rate` present but currency defaulted to INR. | MED | `document_parser.parse_vision_response` |
| C3 | **GST ledger not found → warning but does not block** the write (voucher posts without the GST leg). Consider blocking (like the party guard) when the doc has GST but the ledger is missing. | MED | `orchestrator._resolve_gst_ledgers`, `voucher_action` |
| C4 | **`is_new_ledger` reads `debit_ledger` for all types** — for Sales/CN that's the party, so "create new ledger" could create the wrong ledger type/parent. Scope new-ledger creation per voucher type. | LOW–MED | `api/chat.py` |
| C5 | **Unknown `doc_type` silently defaults to Payment.** Warn on unexpected doc_type. | LOW | `document_parser`, orchestrator |

### Test gaps
| # | Gap | Note |
|---|---|---|
| T1 | **FX × GST combination** lacks a unit test (foreign invoice with GST — all legs scaled, balance holds). NOTE: now covered END-TO-END by the live PDF test, but add a fast unit test. | add unit test |
| T2 | **Eval mock-Tally lacks GST ledgers** → mock-mode eval can't score GST split. Add CGST/SGST/IGST Input+Output to the mock handler's ledger fixture. | `mock_handler.py` |
| T3 | FX override fast-path end-to-end (DB mode) integration test. | `test_api_chat_db.py` |

## Already fixed this session (do NOT re-open)
No-rate write guard; recompute silent-0/KeyError; rate-override regex over-match; DN/CN posting direction
(live-verified); GST-on-invoices ledger mapping; DN/CN edit-form debit/credit inversion + reclassify
stale-field clearing + empty-party guard (with tests); test-isolation `importlib.reload` leak; stale health smoke test.

## Recommended next steps (in order)
1. **S1 SSRF host/port allowlist** — highest-risk, small fix.
2. **A1 entry-dict Pydantic validation** + **A2 sign-convention single source** — biggest maintainability wins; also reduce the chance of a future DN/CN-style bug.
3. **C1/C2/C3 warnings** (no-ref DN/CN, currency-defaulted-to-INR, GST-ledger-missing block) — cheap correctness guards.
4. **T2 mock GST ledgers** so the write-flow eval scores GST accurately.
5. Defer A3–A6 cleanups as a dedicated refactor slice.
