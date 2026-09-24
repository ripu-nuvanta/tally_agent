# Backend date static-variable audit (C33 / C43) — 2026-09-24

**Question:** does the production backend (`backend/tally_bridge/`) suffer from the two date behaviours found live in
the v2 probe work — **C33** (untyped `SVFROMDATE`/`SVTODATE` ignored on a Voucher *collection*, Tally silently
answers for the current period) and **C43** (Educational Tally ignores a date variable whose day is not 1/2/31, even
typed, and falls back to the current period's end)?

**Answer: yes, C33 hits every voucher-collection read in production; reports are NOT affected by C33; C43 hits both
reports and collections on an Educational Tally.** Investigation only — no code changed.

- Live target: TallyPrime 7 Educational under Wine, `localhost:9000`, company B *Sharma & Sons' Probe Traders*
  (books from 01-04-2022, data Apr-2022..Mar-2026, current period 01-04-2025..31-03-2026). Read-only Export requests only.
- Method: import the backend's own `request_builder` functions, send the request **as shipped (untyped)**, a **typed
  copy** (only change: `<SVFROMDATE TYPE="Date">`, `<SVTODATE TYPE="Date">`) and, for reports, a **typed current-period
  control**. Collections were also run through the production parser (`parse_vouchers`, which applies the Python-side
  date filter `_filter_vouchers_by_date`) to see what the agent actually receives.
- Evidence: `logs/backend-date-audit-2026-09-24.log` (full requests + summaries, two runs appended),
  `logs/backend-date-audit-2026-09-24.json` (run 1 summaries). Scripts were throwaway (scratchpad), not committed.

## 1. Inventory — every place backend/ sends a date static variable

All dates are sent as `DD-MM-YYYY`, **untyped** (`<SVFROMDATE>dd-mm-yyyy</SVFROMDATE>`). Nothing in `backend/` emits
`TYPE="Date"`.

| # | Builder (request_builder.py) | Envelope / ID | TYPE | Callers → user-facing feature |
|---|---|---|---|---|
| 1 | `_wrap_voucher_collection` L67–108 (dates L92–93) via `build_day_book` L261 | Collection `DayBookVchs` | Collection | `vouchers.day_book` → tools `get_day_book`, **`get_payment_register`** (`voucher_type="Payment"`), **`get_receipt_register`** (`"Receipt"`); `GET /api/reports/day_book` |
| 2 | same, via `build_sales_register` L301 | Collection `SalesVchs` | Collection | `vouchers.sales_register` → tool `get_sales_register`; `/api/reports/sales_register` |
| 3 | same, via `build_purchase_register` L304 | Collection `PurchaseVchs` | Collection | `vouchers.purchase_register` → tool `get_purchase_register`; `/api/reports/purchase_register` |
| 4 | `build_ledger_vouchers` L264–299 (dates L283–284) | Collection `LedgerVchs` | Collection | `vouchers.ledger_vouchers` → tool `get_ledger_transactions` |
| 5 | `build_party_vouchers` L162–217 (dates L195–196) | Collection `PartyVouchers` | Collection | `vouchers.get_party_vouchers` (default window **hard-coded 01-04-2025..31-03-2026**) → write flow: `services/dedup.py` L94 (Tally duplicate-invoice check), `agents/orchestrator.py` L347/L373 (DN/CN "against which invoice") |
| 6 | `_wrap_report_envelope` L111–131 (dates L124–125) via `build_trial_balance` | Data `Trial Balance` | Data (report) | tool `get_trial_balance`; `/api/reports/trial_balance` |
| 7 | same, `build_profit_and_loss` | Data `Profit and Loss` | report | tool `get_profit_and_loss` (via `profit_and_loss_period`, which rejects non-FY-start `from_date`) |
| 8 | same, `build_balance_sheet` (from = to = as-on) | Data `Balance Sheet` | report | tool `get_balance_sheet` |
| 9 | same, `build_bills_receivable` / `build_bills_payable` (as-on) | Data `Bills Receivable` / `Bills Payable` | report | tools `get_outstanding_receivables` / `get_outstanding_payables` |
| 10 | same, `build_stock_summary` (as-on, + `SVSTOCKGROUP`) | Data `Stock Summary` | report | tool `get_stock_summary`; `/api/reports/stock_summary` |
| 11 | same, `build_cash_flow` | Data `Cash Flow` | report | tool `get_cash_flow` |
| — | `mock_handler._extract_svtodate` L72–78 | regex `<SVTODATE>(\d{2})-(\d{2})-(\d{4})</SVTODATE>` | (mock) | Demo/mock mode P&L cumulative computation. **Would stop matching a typed tag** → returns `None` → full-FY P&L for every date (silent mock regression if the builder is typed without updating this regex). |

No dated static variables elsewhere: `import_builder.py` only sets `SVCURRENTCOMPANY`; master collections
(`build_list_*`, `build_company_list`) carry no dates. Scripts under `scripts/` (probes, cleanup, manual tests) also
send untyped dates but are not production.

## 2. Live results (company B, current period FY 2025-26)

### 2a. Voucher collections — C33 **confirmed in production code**

"Raw" = vouchers Tally returned (date range of the payload); "agent gets" = after `parse_vouchers`' Python date filter.

| Request (backend builder) | Window asked | Untyped (as shipped): raw → agent gets | Typed copy: raw → agent gets |
|---|---|---|---|
| day_book | FY 2022-23 (01-04-2022..31-03-2023) | 240, all 2025-04-01..2026-03-31 → **0** | 238, 2022-04-01..2023-03-31 → **238** |
| payment_register (day_book Payment) | FY 2022-23 | 36 current-period → **0** | 36 → **36** |
| receipt_register (day_book Receipt) | FY 2022-23 | 48 current-period → **0** | 48 → **48** |
| sales_register | FY 2022-23 | 72 current-period → **0** | 71 → **71** |
| purchase_register | FY 2022-23 | 60 current-period → **0** | 60 → **60** |
| ledger_vouchers (party *शर्मा ट्रेडर्स*) | FY 2022-23 | 28 current-period → **0** | 26 → **26** |
| day_book / payment / receipt / sales / purchase | 01-06-2023..02-06-2023 | current period (240/36/48/72/60) → **0 each** | 20 / 3 / 4 / 6 / 5 → same |
| party_vouchers (Sales, *शर्मा ट्रेडर्स*) | FY 2022-23 | **28 current-period vouchers returned as the answer** (`parse_party_vouchers` has no date filter) | 26 FY 2022-23 |
| party_vouchers — production default window | 01-04-2025..31-03-2026 | 28 (correct only because the window = current period) | 28 |

Untyped payload is byte-identical regardless of the window asked (day book: 9,027,947 bytes every time) — Tally
ignores the dates completely. The Python "safety net" (`_filter_vouchers_by_date`) turns the wrong data into an
**empty result**, so the agent sees a clean success with zero vouchers and reports "no sales/transactions".

### 2b. Reports (TYPE=Data) — **C33 does NOT apply**

Untyped and typed responses are **byte-identical (same SHA-1)** for every report, and differ from the typed
current-period control — i.e. reports honour untyped dates. This settles the question probe 5 left open (its TB pair
was identical but had no control; this run adds one).

| Report | Window | untyped sha = typed sha | ≠ current-period control |
|---|---|---|---|
| Trial Balance | FY 2022-23 | `a22055d948` = `a22055d948` | ✓ (`2ae5150d0b`) |
| Trial Balance | 01-04-2023..02-06-2023 | `5ec0086504` = | ✓ |
| Profit and Loss | FY 2022-23 | `222caa7da4` = | ✓ (`a0d95c891e`) |
| Balance Sheet | as on 31-03-2023 | `d7961a0416` = | ✓ (`b615942c71`) |
| Bills Receivable | as on 31-03-2023 | `99ae41ee75` = (11 KB) | ✓ (46 KB) |
| Bills Payable | as on 31-03-2023 | `2236496554` = | ✓ |
| Stock Summary | as on 31-03-2023 | `c7c7770f93` = | ✓ (e.g. Wireless Mouse 69 vs 2 Nos) |
| Cash Flow | FY 2022-23 | `4c51d26d4c` = | ✓ |

### 2c. C43 (Educational: day not in {1, 2, 31} ignored) — **confirmed on backend requests, both kinds**

| Request | Result |
|---|---|
| TB 01-04-2023..**30**-06-2023 (untyped and typed) | sha `99b4bde448` = TB typed 01-04-2023..**31-03-2026** exactly → to-date fell back to current-period end; ≠ the honest 01-04-2023..31-07-2023 (`530aa243f0`) |
| Balance Sheet as on **30**-06-2023 | identical to as on 31-03-2026; as on 02-06-2023 differs |
| Bills Receivable as on 30-06-2023 | identical to as on 31-03-2026 |
| Stock Summary as on 30-06-2023 | identical to as on 31-03-2026 |
| day_book typed 01-06-2023..30-06-2023 | 680 vouchers 2023-06-01..2026-03-31 (25.5 MB); Python filter rescues → 20 correct |
| sales_register typed Q1 FY24 01-04-2023..30-06-2023 | 216 vouchers to 2026-03-31; filter → 18 correct |
| day_book typed 15-06-2023 (single day) | from also ignored → current period → filter → 0 (correct only because Educational can't hold a 15th voucher) |

So on Educational: **reports with a non-1/2/31 to-date are silently wrong** (no safety net); **typed collections
survive via the Python filter** but fetch up to the whole tail of the books (performance/timeout risk).

### 2d. Side finding (not dates)

`_wrap_report_envelope`, `_wrap_voucher_collection` and `build_ledger_vouchers` interpolate `company` **without
XML-escaping** (`build_party_vouchers`/`_wrap_collection_envelope` do escape). `build_trial_balance(..., company="Sharma &
Sons' Probe Traders")` → `<RESPONSE>Unknown Request, cannot be processed</RESPONSE>`. Any company whose name contains
`&` breaks every report/voucher read whenever the model fills the optional `company` tool param.

## 3. Real-world impact on the production app

- **Why nothing caught it:** the seed company Bharat Traders keeps all data in FY 2025-26, which *is* its current
  period — untyped reads coincidentally answer correctly; mock Tally ignores dates for collections; `e2e_live`/eval only
  ask about the seed FY. Same masking as company A in the v2 work.
- **Collections (C33, any Tally edition):** every question whose window is **outside the company's current period
  (F2/Alt+F2 period, normally the running FY)** silently returns **zero rows** → the agent answers "no sales / no
  payments / no transactions". Examples (real client, today 24-Sep-2026, current period FY 2026-27):
  - "last year's sales", "purchases in FY 2024-25", "payments made last year" (`resolve_date_range("last year")` →
    01-04-2025..31-03-2026) → **empty**.
  - "Q1 FY24 vs Q1 FY25 sales" → both **0** → a confident "no sales in either quarter" / 0% change (the
    AnalysisAgent computes on empties).
  - "day book for 15-Jun-2023", "ledger transactions for X in 2023", "receipts in March 2025" → **empty**.
  - Year-over-year trend charts: current-FY months populated, all prior-FY months zero → fabricated growth story.
  - Questions inside the current period ("this month", "last month" within the FY) are fine.
  - Write flow: `get_party_vouchers` is **unaffected today only by accident** — its hard-coded default window
    equals Tally's current period *for the seed company*; for a real client in FY 2026-27 Tally still returns the
    current period (so dedup/DN-CN keep working), but the moment the vars are typed the hard-coded
    01-04-2025..31-03-2026 becomes binding and **dedup would stop seeing this year's invoices** (see §4).
- **Reports (TB, P&L, BS, bills, stock, cash flow):** not affected by C33 — past-period reports are correct on a
  licensed Tally.
- **C43 (Educational Tally only — our dev/demo box):** any window ending on a 28/29/30 or mid-month day silently
  becomes "…to 31-03 of the current period" for reports: "Balance sheet as on 30 Jun 2023", "TB for June 2023",
  "outstanding receivables as on 30-Sep", "stock as on today (24-09)", "this quarter" (→ 30-09) all return
  current-period-end figures with no warning. Collections survive via the Python filter but pull multi-MB payloads.
  Matters for demos/eval on Educational; licensed Tally behaviour is an open tier-C check (LESSONS §15 rule 22 caveat).

## 4. Recommended fix shape (not implemented)

1. **Type the date vars** in `request_builder.py` — one small helper (e.g. `_date_vars(from, to)` →
   `<SVFROMDATE TYPE="Date">…</SVFROMDATE><SVTODATE TYPE="Date">…</SVTODATE>`) used by `_wrap_voucher_collection`,
   `build_ledger_vouchers`, `build_party_vouchers` (required) and `_wrap_report_envelope` (harmless, byte-identical
   live, keeps one convention). Keep `_filter_vouchers_by_date` as the safety net.
2. **Fix `get_party_vouchers`' hard-coded default** (01-04-2025..31-03-2026) *in the same change* — derive it from
   today's FY (or books-from..today for dedup, since a duplicate invoice can be from a prior FY). Typing without this
   silently breaks duplicate detection and DN/CN invoice lookup from 1-Apr-2026 onward.
3. **Update `mock_handler._extract_svtodate`** regex to accept an optional attribute
   (`<SVTODATE(?:\s+TYPE="Date")?>`), else mock/demo P&L silently becomes full-FY.
4. **Tests:** update ~22 string assertions in `tests/unit/test_request_builder.py` plus
   `test_mock_handler.py` (4), `test_tools.py` (2), `test_group_b_company_party.py` (2),
   `tests/integration/test_mock_format_parity.py` (4); add builder tests asserting `TYPE="Date"` on every dated
   builder; add a mock-parity/regression test that a **past-FY** collection read returns that FY's vouchers (a mock
   Tally that mimics C33 — returns current-period data when untyped — so the bug can't regress green); add a gated
   `e2e_live` case "sales register for a prior FY is non-empty" (needs a company with multi-FY data, e.g. company B).
5. **C43 (optional, Educational only):** a settings flag (`TALLY_EDUCATIONAL_MODE`, or auto-detect from probe 0's
   licence read) that clamps to-dates to the 31st/2nd for reports, or a warning in the tool result. Low priority for
   production, useful for demo/eval honesty.
6. **Side fix:** `xml_escape(company)` in `_wrap_report_envelope`, `_wrap_voucher_collection`, `build_ledger_vouchers`.

**Blast radius:** 3 builder functions + 1 wrapper in `request_builder.py`, 1 default in `queries/vouchers.py`, 1 regex
in `mock_handler.py`, ~34 string assertions across 5 test files. No parser, agent, API or frontend change. Behaviour
change is visible only for windows outside Tally's current period (they start returning data) and, via item 2, the
write-flow dedup window. Must also be recorded in `LESSONS.md` (production note under rules 21–22) and the roadmap
"Up next" hardening list.
