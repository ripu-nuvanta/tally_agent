# Phase 1: Tally Bridge Layer — Design Document

**Date**: 2026-03-03
**Status**: Approved
**Scope**: Foundation layer for TallyPrime HTTP communication

## Decisions

- **Package manager**: uv (pyproject.toml)
- **Protocol**: XML-only for Phase 1 (most stable, best documented)
- **Architecture**: Flat async functions per query, TallyClient passed as parameter
- **Testing**: Unit tests + mock Tally HTTP server + live Tally available for validation
- **Python**: 3.12+

## Module Structure

```
backend/
├── __init__.py
├── config.py                    # Settings via pydantic-settings, loads .env
├── tally_bridge/
│   ├── __init__.py
│   ├── client.py                # TallyClient: async post_xml(), health_check()
│   ├── request_builder.py       # Pure functions → XML strings per report type
│   ├── response_parser.py       # XML → normalized dicts, amount parsing, error detection
│   ├── models.py                # Pydantic models for Tally data structures
│   ├── exceptions.py            # TallyConnectionError, TallyResponseError
│   └── queries/
│       ├── __init__.py
│       ├── masters.py           # list_companies, list_ledgers, search_ledger, list_groups, list_stock_items
│       ├── reports.py           # trial_balance, profit_and_loss, balance_sheet, bills_receivable/payable, stock_summary
│       └── vouchers.py          # day_book, ledger_vouchers, sales_register, purchase_register
├── utils/
│   ├── __init__.py
│   ├── date_utils.py            # Indian FY logic, relative date parsing, format_for_tally()
│   └── currency_format.py       # format_inr() with Indian comma system
```

## Core Components

### TallyClient (`client.py`)
- `base_url` from settings, `httpx.Timeout(30.0, connect=5.0)`
- `async post_xml(xml_payload: str) -> str` — POST XML, return raw response
- `async health_check() -> bool` — connectivity + company loaded check
- Raises `TallyConnectionError` on connect/timeout, `TallyResponseError` on parse failures

### Request Builder (`request_builder.py`)
Pure functions, no I/O. Each returns XML string:
- Masters: `build_list_companies()`, `build_list_ledgers()`, `build_list_groups()`, `build_list_stock_items()`
- Reports: `build_trial_balance(from_date, to_date, company?)`, `build_profit_and_loss(from_date, to_date, detailed?)`, `build_balance_sheet(as_on_date)`, `build_bills_receivable(as_on_date)`, `build_bills_payable(as_on_date)`, `build_stock_summary(as_on_date, stock_group?)`
- Vouchers: `build_day_book(from_date, to_date, voucher_type?)`, `build_ledger_vouchers(ledger_name, from_date, to_date)`, `build_sales_register(from_date, to_date)`, `build_purchase_register(from_date, to_date)`

### Response Parser (`response_parser.py`)
- `parse_response(raw_xml: str) -> dict` — base parser with error detection
- Report-specific: `parse_trial_balance()`, `parse_ledger_list()`, `parse_profit_and_loss()`, etc.
- `parse_amount(text: str) -> float` — handles empty strings, commas, negatives
- Tally error XML detection

### Pydantic Models (`models.py`)
- `Company(name, fy_start?, fy_end?)`
- `Ledger(name, parent_group, closing_balance, opening_balance)`
- `VoucherEntry(date, voucher_type, voucher_number, party_name?, ledger_name, amount, narration?)`
- `TrialBalanceRow(account_name, debit_amount, credit_amount, closing_balance)`
- `ReportResponse(report_name, company, from_date?, to_date?, rows, raw_response?)`
- `OutstandingBill(party_name, bill_number, bill_date, due_date?, amount, pending_amount)`

### Query Functions (`queries/`)
Each async function: takes TallyClient + params → request_builder → client.post_xml → response_parser → Pydantic model(s).

## Testing Strategy

- **Unit tests** (`tests/unit/`): request_builder XML output, response_parser with fixture XML, date_utils, currency_format, Pydantic model validation
- **Fixtures** (`tests/fixtures/`): Hand-crafted XML files matching real Tally response structures
- **Integration tests** (`tests/integration/`): Mock Tally HTTP server (aiohttp), full request→parse→return cycle
- **Live validation**: `scripts/test_tally_connection.py` against real Tally instance
