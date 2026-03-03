# Phase 1: Tally Bridge Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundation layer that handles all HTTP communication with TallyPrime — request building, response parsing, Pydantic models, and query functions.

**Architecture:** Flat async functions per query module. TallyClient handles raw HTTP. Request builder creates XML strings. Response parser normalizes XML into dicts/models. Query functions compose these three layers.

**Tech Stack:** Python 3.12+, uv, httpx, pydantic, pydantic-settings, pytest, pytest-asyncio, aiohttp (mock server)

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/__init__.py`
- Create: `backend/tally_bridge/__init__.py`
- Create: `backend/tally_bridge/queries/__init__.py`
- Create: `backend/utils/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/fixtures/` (directory)
- Create: `tests/mocks/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "tallyprime-agent"
version = "0.1.0"
description = "AI-powered chatbot for TallyPrime accounting data"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "aiohttp>=3.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create .env.example**

```bash
TALLY_HOST=localhost
TALLY_PORT=9000
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
SESSION_TTL_MINUTES=60
VITE_API_URL=http://localhost:8000
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
.venv/
*.egg-info/
dist/
.coverage
htmlcov/
.pytest_cache/
node_modules/
```

**Step 4: Create all `__init__.py` files and directories**

All `__init__.py` files are empty. Create `tests/fixtures/` as an empty directory.

**Step 5: Install dependencies**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv sync --dev`
Expected: Lock file created, dependencies installed successfully.

**Step 6: Verify pytest runs**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest --co -q`
Expected: "no tests ran" (no test files yet, but pytest itself works)

**Step 7: Commit**

```bash
git add pyproject.toml .env.example .gitignore backend/ tests/
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: Config & Exceptions

**Files:**
- Create: `backend/config.py`
- Create: `backend/tally_bridge/exceptions.py`

**Step 1: Write config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TALLY_HOST: str = "localhost"
    TALLY_PORT: int = 9000
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    SESSION_TTL_MINUTES: int = 60

    @property
    def TALLY_URL(self) -> str:
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Step 2: Write exceptions.py**

```python
class TallyConnectionError(Exception):
    """Raised when TallyPrime is unreachable or times out."""
    pass


class TallyResponseError(Exception):
    """Raised when TallyPrime returns an unparseable or error response."""
    pass
```

**Step 3: Verify imports work**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run python -c "from backend.config import settings; print(settings.TALLY_URL)"`
Expected: `http://localhost:9000`

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run python -c "from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add backend/config.py backend/tally_bridge/exceptions.py
git commit -m "feat: add config settings and custom exceptions"
```

---

### Task 3: Pydantic Models

**Files:**
- Create: `backend/tally_bridge/models.py`
- Create: `tests/unit/test_models.py`

**Step 1: Write failing tests for models**

```python
# tests/unit/test_models.py
from datetime import date

from backend.tally_bridge.models import (
    Company,
    Ledger,
    TrialBalanceRow,
    VoucherEntry,
    ReportResponse,
    OutstandingBill,
)


def test_company_minimal():
    c = Company(name="Bharat Traders Pvt Ltd")
    assert c.name == "Bharat Traders Pvt Ltd"
    assert c.fy_start is None


def test_company_with_fy():
    c = Company(name="Test Co", fy_start=date(2025, 4, 1), fy_end=date(2026, 3, 31))
    assert c.fy_start == date(2025, 4, 1)


def test_ledger_defaults():
    l = Ledger(name="Cash", parent_group="Cash-in-Hand")
    assert l.closing_balance == 0.0
    assert l.opening_balance == 0.0


def test_ledger_with_balances():
    l = Ledger(name="HDFC Bank", parent_group="Bank Accounts", closing_balance=-500000.0, opening_balance=-200000.0)
    assert l.closing_balance == -500000.0


def test_trial_balance_row_defaults():
    r = TrialBalanceRow(account_name="Sales Accounts")
    assert r.debit_amount == 0.0
    assert r.credit_amount == 0.0
    assert r.closing_balance == 0.0


def test_voucher_entry():
    v = VoucherEntry(
        date=date(2025, 10, 1),
        voucher_type="Sales",
        voucher_number="S001",
        ledger_name="Sales - Electronics",
        amount=94000.0,
        party_name="Apex Technologies Pvt Ltd",
    )
    assert v.party_name == "Apex Technologies Pvt Ltd"
    assert v.narration is None


def test_report_response():
    r = ReportResponse(
        report_name="Trial Balance",
        company="Bharat Traders",
        rows=[{"account_name": "Cash", "closing_balance": 50000}],
    )
    assert len(r.rows) == 1
    assert r.from_date is None


def test_outstanding_bill():
    b = OutstandingBill(
        party_name="Apex Technologies Pvt Ltd",
        bill_number="S001",
        bill_date=date(2025, 10, 1),
        amount=94000.0,
        pending_amount=40000.0,
    )
    assert b.due_date is None
    assert b.pending_amount == 40000.0
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.tally_bridge.models'`

**Step 3: Write models.py**

```python
from datetime import date

from pydantic import BaseModel


class Company(BaseModel):
    name: str
    fy_start: date | None = None
    fy_end: date | None = None


class Ledger(BaseModel):
    name: str
    parent_group: str
    closing_balance: float = 0.0
    opening_balance: float = 0.0


class TrialBalanceRow(BaseModel):
    account_name: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    closing_balance: float = 0.0


class VoucherEntry(BaseModel):
    date: date
    voucher_type: str
    voucher_number: str
    party_name: str | None = None
    ledger_name: str
    amount: float
    narration: str | None = None


class ReportResponse(BaseModel):
    report_name: str
    company: str
    from_date: date | None = None
    to_date: date | None = None
    rows: list[dict]
    raw_response: dict | None = None


class OutstandingBill(BaseModel):
    party_name: str
    bill_number: str
    bill_date: date
    due_date: date | None = None
    amount: float
    pending_amount: float
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_models.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add backend/tally_bridge/models.py tests/unit/test_models.py
git commit -m "feat: add Pydantic models for Tally data structures"
```

---

### Task 4: Currency Formatting Utility

**Files:**
- Create: `backend/utils/currency_format.py`
- Create: `tests/unit/test_currency_format.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_currency_format.py
from backend.utils.currency_format import format_inr


def test_indian_format_lakhs():
    assert format_inr(123456.78) == "₹1,23,456.78"


def test_indian_format_crores():
    assert format_inr(12345678.90) == "₹1,23,45,678.90"


def test_negative_amount():
    assert format_inr(-50000) == "-₹50,000.00"


def test_zero():
    assert format_inr(0) == "₹0.00"


def test_small_number():
    assert format_inr(999.99) == "₹999.99"


def test_thousands():
    assert format_inr(50000) == "₹50,000.00"


def test_large_crores():
    assert format_inr(100000000) == "₹10,00,00,000.00"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_currency_format.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write currency_format.py**

```python
def format_inr(amount: float) -> str:
    """Format amount with Indian comma system (₹12,34,567.00)."""
    negative = amount < 0
    amount = abs(amount)

    # Split into integer and decimal parts
    integer_part = int(amount)
    decimal_part = f"{amount:.2f}".split(".")[1]

    # Indian comma system: first 3 digits from right, then groups of 2
    s = str(integer_part)
    if len(s) <= 3:
        formatted = s
    else:
        # Last 3 digits
        last3 = s[-3:]
        rest = s[:-3]
        # Group remaining digits in pairs from right
        pairs = []
        while len(rest) > 2:
            pairs.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            pairs.append(rest)
        pairs.reverse()
        formatted = ",".join(pairs) + "," + last3

    result = f"₹{formatted}.{decimal_part}"
    if negative:
        result = f"-{result}"
    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_currency_format.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/utils/currency_format.py tests/unit/test_currency_format.py
git commit -m "feat: add Indian currency formatting utility"
```

---

### Task 5: Date Utilities

**Files:**
- Create: `backend/utils/date_utils.py`
- Create: `tests/unit/test_date_utils.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_date_utils.py
from datetime import date

from backend.utils.date_utils import (
    get_fy_start,
    get_fy_end,
    get_last_fy_range,
    get_current_quarter_range,
    get_last_quarter_range,
    get_month_range,
    format_for_tally,
)


def test_fy_start_before_april():
    assert get_fy_start(date(2026, 1, 15)) == date(2025, 4, 1)


def test_fy_start_after_april():
    assert get_fy_start(date(2025, 6, 15)) == date(2025, 4, 1)


def test_fy_start_on_april_1():
    assert get_fy_start(date(2025, 4, 1)) == date(2025, 4, 1)


def test_fy_end_before_april():
    assert get_fy_end(date(2026, 1, 15)) == date(2026, 3, 31)


def test_fy_end_after_april():
    assert get_fy_end(date(2025, 6, 15)) == date(2026, 3, 31)


def test_last_fy_range():
    start, end = get_last_fy_range(date(2026, 1, 15))
    assert start == date(2024, 4, 1)
    assert end == date(2025, 3, 31)


def test_current_quarter_q1():
    # May 2025 = Q1 (Apr-Jun)
    start, end = get_current_quarter_range(date(2025, 5, 10))
    assert start == date(2025, 4, 1)
    assert end == date(2025, 6, 30)


def test_current_quarter_q4():
    # Jan 2026 = Q4 (Jan-Mar)
    start, end = get_current_quarter_range(date(2026, 1, 15))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 3, 31)


def test_last_quarter_from_q4():
    # Jan 2026 (Q4) -> last quarter = Q3 (Oct-Dec 2025)
    start, end = get_last_quarter_range(date(2026, 1, 15))
    assert start == date(2025, 10, 1)
    assert end == date(2025, 12, 31)


def test_last_quarter_from_q1():
    # May 2025 (Q1) -> last quarter = Q4 of prev FY (Jan-Mar 2025)
    start, end = get_last_quarter_range(date(2025, 5, 10))
    assert start == date(2025, 1, 1)
    assert end == date(2025, 3, 31)


def test_month_range_normal():
    start, end = get_month_range(date(2026, 1, 15))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)


def test_month_range_february_leap():
    start, end = get_month_range(date(2028, 2, 10))
    assert start == date(2028, 2, 1)
    assert end == date(2028, 2, 29)


def test_format_for_tally():
    assert format_for_tally(date(2025, 4, 1)) == "01-04-2025"


def test_format_for_tally_single_digit():
    assert format_for_tally(date(2025, 1, 5)) == "05-01-2025"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_date_utils.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write date_utils.py**

```python
import calendar
from datetime import date


def get_fy_start(ref: date) -> date:
    """Return April 1 of the current Indian financial year."""
    if ref.month >= 4:
        return date(ref.year, 4, 1)
    return date(ref.year - 1, 4, 1)


def get_fy_end(ref: date) -> date:
    """Return March 31 of the current Indian financial year."""
    if ref.month >= 4:
        return date(ref.year + 1, 3, 31)
    return date(ref.year, 3, 31)


def get_last_fy_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the previous Indian financial year."""
    fy_start = get_fy_start(ref)
    prev_end = fy_start - __import__("datetime").timedelta(days=1)
    prev_start = date(prev_end.year - 1, 4, 1) if prev_end.month >= 4 else date(prev_end.year, 4, 1)
    # Simpler: previous FY is always one year before current FY
    return date(fy_start.year - 1, 4, 1), date(fy_start.year, 3, 31)


# Indian FY quarters: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
_QUARTERS = [
    (4, 6),   # Q1
    (7, 9),   # Q2
    (10, 12), # Q3
    (1, 3),   # Q4
]


def _get_quarter_index(month: int) -> int:
    """Return 0-3 for the Indian FY quarter."""
    if 4 <= month <= 6:
        return 0
    elif 7 <= month <= 9:
        return 1
    elif 10 <= month <= 12:
        return 2
    else:
        return 3


def get_current_quarter_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the current Indian FY quarter."""
    qi = _get_quarter_index(ref.month)
    start_month, end_month = _QUARTERS[qi]
    if qi == 3:  # Q4 is Jan-Mar, same calendar year
        year = ref.year
    elif ref.month >= 4:
        year = ref.year
    else:
        year = ref.year - 1
    # For Q4, year is always ref.year
    if qi == 3:
        start_year = ref.year
    else:
        start_year = year
    last_day = calendar.monthrange(start_year, end_month)[1]
    return date(start_year, start_month, 1), date(start_year, end_month, last_day)


def get_last_quarter_range(ref: date) -> tuple[date, date]:
    """Return (start, end) of the previous Indian FY quarter."""
    qi = _get_quarter_index(ref.month)
    prev_qi = (qi - 1) % 4
    start_month, end_month = _QUARTERS[prev_qi]
    # Determine year for previous quarter
    if qi == 0:  # current is Q1 (Apr-Jun), prev is Q4 (Jan-Mar) of same calendar year
        year = ref.year
    elif qi == 3:  # current is Q4 (Jan-Mar), prev is Q3 (Oct-Dec) of previous calendar year
        year = ref.year - 1
    else:
        year = ref.year
    last_day = calendar.monthrange(year, end_month)[1]
    return date(year, start_month, 1), date(year, end_month, last_day)


def get_month_range(ref: date) -> tuple[date, date]:
    """Return (first day, last day) of the month containing ref."""
    last_day = calendar.monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)


def format_for_tally(d: date) -> str:
    """Format date as DD-MM-YYYY for Tally requests."""
    return d.strftime("%d-%m-%Y")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_date_utils.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add backend/utils/date_utils.py tests/unit/test_date_utils.py
git commit -m "feat: add Indian FY date utilities"
```

---

### Task 6: Request Builder — Master Queries

**Files:**
- Create: `backend/tally_bridge/request_builder.py`
- Create: `tests/unit/test_request_builder.py`

**Step 1: Write failing tests for master query builders**

```python
# tests/unit/test_request_builder.py
from backend.tally_bridge.request_builder import (
    build_list_companies,
    build_list_ledgers,
    build_list_groups,
    build_list_stock_items,
)


class TestMasterBuilders:
    def test_list_companies_has_envelope(self):
        xml = build_list_companies()
        assert "<ENVELOPE>" in xml
        assert "</ENVELOPE>" in xml

    def test_list_companies_has_export_request(self):
        xml = build_list_companies()
        assert "<TALLYREQUEST>Export</TALLYREQUEST>" in xml

    def test_list_companies_has_company_collection(self):
        xml = build_list_companies()
        assert "List of Companies" in xml

    def test_list_ledgers_has_collection_type(self):
        xml = build_list_ledgers()
        assert "<TYPE>Ledger</TYPE>" in xml

    def test_list_ledgers_has_native_methods(self):
        xml = build_list_ledgers()
        assert "<NATIVEMETHOD>Name</NATIVEMETHOD>" in xml
        assert "<NATIVEMETHOD>Parent</NATIVEMETHOD>" in xml
        assert "<NATIVEMETHOD>ClosingBalance</NATIVEMETHOD>" in xml

    def test_list_groups_has_group_type(self):
        xml = build_list_groups()
        assert "<TYPE>Group</TYPE>" in xml

    def test_list_stock_items_has_stock_type(self):
        xml = build_list_stock_items()
        assert "<TYPE>StockItem</TYPE>" in xml
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py::TestMasterBuilders -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write request_builder.py — master query builders only**

```python
"""
Build XML request payloads for TallyPrime HTTP API.

All functions are pure — no I/O, no side effects. Each returns an XML string
ready to POST to Tally's HTTP server.

Tally date format: DD-MM-YYYY
"""


def _wrap_envelope(header_id: str, body_desc: str) -> str:
    """Wrap content in standard Tally XML envelope."""
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>{header_id}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
{body_desc}
</DESC>
</BODY>
</ENVELOPE>"""


def _wrap_collection_envelope(collection_name: str, object_type: str, native_methods: list[str]) -> str:
    """Wrap a TDL collection query in an envelope."""
    methods_xml = "\n".join(f"<NATIVEMETHOD>{m}</NATIVEMETHOD>" for m in native_methods)
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>{collection_name}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="{collection_name}" ISMODIFY="No">
<TYPE>{object_type}</TYPE>
{methods_xml}
</COLLECTION>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""


def build_list_companies() -> str:
    """Build XML to list all companies loaded in TallyPrime."""
    return _wrap_envelope("List of Companies", "")


def build_list_ledgers() -> str:
    """Build XML to list all ledgers with parent group and balances."""
    return _wrap_collection_envelope(
        "CustomLedgerList",
        "Ledger",
        ["Name", "Parent", "ClosingBalance", "OpeningBalance"],
    )


def build_list_groups() -> str:
    """Build XML to list all account groups."""
    return _wrap_collection_envelope(
        "CustomGroupList",
        "Group",
        ["Name", "Parent"],
    )


def build_list_stock_items() -> str:
    """Build XML to list all stock items with details."""
    return _wrap_collection_envelope(
        "CustomStockItemList",
        "StockItem",
        ["Name", "Parent", "BaseUnits", "ClosingBalance", "ClosingRate", "ClosingValue"],
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py::TestMasterBuilders -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/tally_bridge/request_builder.py tests/unit/test_request_builder.py
git commit -m "feat: add XML request builders for master queries"
```

---

### Task 7: Request Builder — Report Queries

**Files:**
- Modify: `backend/tally_bridge/request_builder.py`
- Modify: `tests/unit/test_request_builder.py`

**Step 1: Write failing tests for report builders**

Append to `tests/unit/test_request_builder.py`:

```python
from backend.tally_bridge.request_builder import (
    build_trial_balance,
    build_profit_and_loss,
    build_balance_sheet,
    build_bills_receivable,
    build_bills_payable,
    build_stock_summary,
)


class TestReportBuilders:
    def test_trial_balance_dates(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_trial_balance_export_format(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "$$SysName:XML" in xml

    def test_trial_balance_report_id(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "Trial Balance" in xml

    def test_trial_balance_with_company(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026", company="ABC Pvt Ltd")
        assert "<SVCurrentCompany>ABC Pvt Ltd</SVCurrentCompany>" in xml

    def test_trial_balance_without_company(self):
        xml = build_trial_balance("01-04-2025", "31-03-2026")
        assert "SVCurrentCompany" not in xml

    def test_profit_and_loss_report_id(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "Profit and Loss" in xml

    def test_profit_and_loss_dates(self):
        xml = build_profit_and_loss("01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_balance_sheet_date(self):
        xml = build_balance_sheet("31-03-2026")
        assert "Balance Sheet" in xml
        assert "<SVTODATE>31-03-2026</SVTODATE>" in xml

    def test_bills_receivable(self):
        xml = build_bills_receivable("31-03-2026")
        assert "Bills Receivable" in xml

    def test_bills_payable(self):
        xml = build_bills_payable("31-03-2026")
        assert "Bills Payable" in xml

    def test_stock_summary(self):
        xml = build_stock_summary("31-03-2026")
        assert "Stock Summary" in xml

    def test_stock_summary_with_group(self):
        xml = build_stock_summary("31-03-2026", stock_group="Electronics")
        assert "Electronics" in xml
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py::TestReportBuilders -v`
Expected: FAIL — `ImportError`

**Step 3: Add report builder functions to request_builder.py**

Append to `backend/tally_bridge/request_builder.py`:

```python
def _wrap_report_envelope(report_id: str, from_date: str, to_date: str, company: str | None = None, extra_vars: str = "") -> str:
    """Wrap a standard report request with date range."""
    company_var = f"<SVCurrentCompany>{company}</SVCurrentCompany>" if company else ""
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>{report_id}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
{company_var}
{extra_vars}
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""


def build_trial_balance(from_date: str, to_date: str, company: str | None = None) -> str:
    """Build XML to fetch Trial Balance for a date range."""
    return _wrap_report_envelope("Trial Balance", from_date, to_date, company)


def build_profit_and_loss(from_date: str, to_date: str, company: str | None = None) -> str:
    """Build XML to fetch Profit & Loss statement."""
    return _wrap_report_envelope("Profit and Loss", from_date, to_date, company)


def build_balance_sheet(as_on_date: str, company: str | None = None) -> str:
    """Build XML to fetch Balance Sheet as on a date."""
    return _wrap_report_envelope("Balance Sheet", as_on_date, as_on_date, company)


def build_bills_receivable(as_on_date: str, company: str | None = None) -> str:
    """Build XML to fetch outstanding receivables."""
    return _wrap_report_envelope("Bills Receivable", as_on_date, as_on_date, company)


def build_bills_payable(as_on_date: str, company: str | None = None) -> str:
    """Build XML to fetch outstanding payables."""
    return _wrap_report_envelope("Bills Payable", as_on_date, as_on_date, company)


def build_stock_summary(as_on_date: str, stock_group: str | None = None, company: str | None = None) -> str:
    """Build XML to fetch stock/inventory summary."""
    extra = f"<SVSTOCKGROUP>{stock_group}</SVSTOCKGROUP>" if stock_group else ""
    return _wrap_report_envelope("Stock Summary", as_on_date, as_on_date, company, extra)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py -v`
Expected: All 19 tests PASS (7 master + 12 report)

**Step 5: Commit**

```bash
git add backend/tally_bridge/request_builder.py tests/unit/test_request_builder.py
git commit -m "feat: add XML request builders for report queries"
```

---

### Task 8: Request Builder — Voucher Queries

**Files:**
- Modify: `backend/tally_bridge/request_builder.py`
- Modify: `tests/unit/test_request_builder.py`

**Step 1: Write failing tests for voucher builders**

Append to `tests/unit/test_request_builder.py`:

```python
from backend.tally_bridge.request_builder import (
    build_day_book,
    build_ledger_vouchers,
    build_sales_register,
    build_purchase_register,
)


class TestVoucherBuilders:
    def test_day_book_dates(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml
        assert "<SVTODATE>30-04-2025</SVTODATE>" in xml

    def test_day_book_report_id(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "Day Book" in xml

    def test_day_book_with_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025", voucher_type="Sales")
        assert "Sales" in xml

    def test_day_book_without_voucher_type(self):
        xml = build_day_book("01-04-2025", "30-04-2025")
        assert "VCHTYPEFILTER" not in xml.upper() or "VOUCHERTYPENAME" not in xml

    def test_ledger_vouchers_includes_ledger_name(self):
        xml = build_ledger_vouchers("HDFC Bank", "01-04-2025", "31-03-2026")
        assert "HDFC Bank" in xml

    def test_ledger_vouchers_dates(self):
        xml = build_ledger_vouchers("Cash", "01-04-2025", "31-03-2026")
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_sales_register(self):
        xml = build_sales_register("01-04-2025", "31-03-2026")
        assert "Sales" in xml
        assert "<SVFROMDATE>01-04-2025</SVFROMDATE>" in xml

    def test_purchase_register(self):
        xml = build_purchase_register("01-04-2025", "31-03-2026")
        assert "Purchase" in xml
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py::TestVoucherBuilders -v`
Expected: FAIL — `ImportError`

**Step 3: Add voucher builder functions to request_builder.py**

Append to `backend/tally_bridge/request_builder.py`:

```python
def build_day_book(from_date: str, to_date: str, voucher_type: str | None = None, company: str | None = None) -> str:
    """Build XML to fetch Day Book (all vouchers in date range)."""
    extra = ""
    if voucher_type:
        extra = f"<VOUCHERTYPENAME>{voucher_type}</VOUCHERTYPENAME>"
    return _wrap_report_envelope("Day Book", from_date, to_date, company, extra)


def build_ledger_vouchers(ledger_name: str, from_date: str, to_date: str, company: str | None = None) -> str:
    """Build XML to fetch all vouchers for a specific ledger."""
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>Ledger Vouchers</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
<LEDGERNAME>{ledger_name}</LEDGERNAME>
{f"<SVCurrentCompany>{company}</SVCurrentCompany>" if company else ""}
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""


def build_sales_register(from_date: str, to_date: str, company: str | None = None) -> str:
    """Build XML to fetch Sales Register."""
    return _wrap_report_envelope("Sales Register", from_date, to_date, company,
                                  "<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>")


def build_purchase_register(from_date: str, to_date: str, company: str | None = None) -> str:
    """Build XML to fetch Purchase Register."""
    return _wrap_report_envelope("Purchase Register", from_date, to_date, company,
                                  "<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>")
```

**Step 4: Run all request builder tests**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_request_builder.py -v`
Expected: All 27 tests PASS

**Step 5: Commit**

```bash
git add backend/tally_bridge/request_builder.py tests/unit/test_request_builder.py
git commit -m "feat: add XML request builders for voucher queries"
```

---

### Task 9: Response Parser

**Files:**
- Create: `backend/tally_bridge/response_parser.py`
- Create: `tests/unit/test_response_parser.py`
- Create: `tests/fixtures/trial_balance.xml`
- Create: `tests/fixtures/ledger_list.xml`
- Create: `tests/fixtures/error_response.xml`

**Step 1: Create XML fixture files**

`tests/fixtures/trial_balance.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<DSPACCNAME>
<DSPDISPNAME>Capital Account</DSPDISPNAME>
<DSPCLDRAMT></DSPCLDRAMT>
<DSPCLCRAMT>7,50,000.00</DSPCLCRAMT>
<DSPCLAMT>7,50,000.00 Cr</DSPCLAMT>
</DSPACCNAME>
<DSPACCNAME>
<DSPDISPNAME>Sales Accounts</DSPDISPNAME>
<DSPCLDRAMT></DSPCLDRAMT>
<DSPCLCRAMT>15,45,000.00</DSPCLCRAMT>
<DSPCLAMT>15,45,000.00 Cr</DSPCLAMT>
</DSPACCNAME>
<DSPACCNAME>
<DSPDISPNAME>Purchase Accounts</DSPDISPNAME>
<DSPCLDRAMT>10,20,000.00</DSPCLDRAMT>
<DSPCLCRAMT></DSPCLCRAMT>
<DSPCLAMT>10,20,000.00 Dr</DSPCLAMT>
</DSPACCNAME>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/ledger_list.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
<LEDGER>
<NAME>HDFC Bank - Current A/c</NAME>
<PARENT>Bank Accounts</PARENT>
<CLOSINGBALANCE>-5,00,000.00</CLOSINGBALANCE>
<OPENINGBALANCE>-2,00,000.00</OPENINGBALANCE>
</LEDGER>
<LEDGER>
<NAME>Cash</NAME>
<PARENT>Cash-in-Hand</PARENT>
<CLOSINGBALANCE>-50,000.00</CLOSINGBALANCE>
<OPENINGBALANCE>-50,000.00</OPENINGBALANCE>
</LEDGER>
<LEDGER>
<NAME>Apex Technologies Pvt Ltd</NAME>
<PARENT>North Zone Debtors</PARENT>
<CLOSINGBALANCE>-94,000.00</CLOSINGBALANCE>
<OPENINGBALANCE></OPENINGBALANCE>
</LEDGER>
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/error_response.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<LINEERROR>Cannot export. Company not loaded.</LINEERROR>
</DATA>
</BODY>
</ENVELOPE>
```

**Step 2: Write failing tests**

```python
# tests/unit/test_response_parser.py
import os

import pytest

from backend.tally_bridge.response_parser import (
    parse_amount,
    parse_trial_balance,
    parse_ledger_list,
    detect_error,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return f.read()


class TestParseAmount:
    def test_normal_amount(self):
        assert parse_amount("1,23,456.78") == 123456.78

    def test_empty_string(self):
        assert parse_amount("") == 0.0

    def test_none_value(self):
        assert parse_amount(None) == 0.0

    def test_negative_amount(self):
        assert parse_amount("-1,23,456.78") == -123456.78

    def test_plain_number(self):
        assert parse_amount("50000.00") == 50000.0

    def test_whitespace(self):
        assert parse_amount("  1,000.00  ") == 1000.0


class TestParseTrialBalance:
    def test_parse_trial_balance_returns_rows(self):
        raw = _read_fixture("trial_balance.xml")
        rows = parse_trial_balance(raw)
        assert len(rows) == 3

    def test_parse_trial_balance_has_account_name(self):
        raw = _read_fixture("trial_balance.xml")
        rows = parse_trial_balance(raw)
        names = [r["account_name"] for r in rows]
        assert "Capital Account" in names

    def test_parse_trial_balance_debit_credit(self):
        raw = _read_fixture("trial_balance.xml")
        rows = parse_trial_balance(raw)
        purchase = next(r for r in rows if r["account_name"] == "Purchase Accounts")
        assert purchase["debit_amount"] == 1020000.0
        assert purchase["credit_amount"] == 0.0

    def test_parse_trial_balance_empty_amount_is_zero(self):
        raw = _read_fixture("trial_balance.xml")
        rows = parse_trial_balance(raw)
        capital = next(r for r in rows if r["account_name"] == "Capital Account")
        assert capital["debit_amount"] == 0.0


class TestParseLedgerList:
    def test_parse_ledger_list_returns_list(self):
        raw = _read_fixture("ledger_list.xml")
        ledgers = parse_ledger_list(raw)
        assert len(ledgers) == 3

    def test_parse_ledger_list_fields(self):
        raw = _read_fixture("ledger_list.xml")
        ledgers = parse_ledger_list(raw)
        hdfc = next(l for l in ledgers if "HDFC" in l["name"])
        assert hdfc["parent_group"] == "Bank Accounts"
        assert hdfc["closing_balance"] == -500000.0

    def test_parse_ledger_list_empty_opening(self):
        raw = _read_fixture("ledger_list.xml")
        ledgers = parse_ledger_list(raw)
        apex = next(l for l in ledgers if "Apex" in l["name"])
        assert apex["opening_balance"] == 0.0


class TestDetectError:
    def test_detect_error_response(self):
        raw = _read_fixture("error_response.xml")
        error = detect_error(raw)
        assert error is not None
        assert "Company not loaded" in error

    def test_no_error_in_valid_response(self):
        raw = _read_fixture("trial_balance.xml")
        error = detect_error(raw)
        assert error is None
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_response_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write response_parser.py**

```python
"""
Parse TallyPrime XML responses into normalized Python dicts.

Handles Tally's inconsistent casing, empty tags, comma-formatted amounts,
and varying response structures across different report types.
"""

import xml.etree.ElementTree as ET


def parse_amount(text: str | None) -> float:
    """Parse a Tally amount string into a float.

    Handles: commas, negatives, empty strings, None, whitespace.
    """
    if not text or not text.strip():
        return 0.0
    cleaned = text.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def detect_error(raw_xml: str) -> str | None:
    """Check if Tally returned an error response. Returns error message or None."""
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return f"Invalid XML response from Tally"

    # Check for LINEERROR tag
    error_el = root.find(".//LINEERROR")
    if error_el is not None and error_el.text:
        return error_el.text.strip()

    # Check for ERRORS tag with non-zero value
    errors_el = root.find(".//ERRORS")
    if errors_el is not None and errors_el.text and errors_el.text.strip() != "0":
        return f"Tally reported {errors_el.text.strip()} error(s)"

    return None


def _get_text(element: ET.Element, tag: str) -> str:
    """Safely get text content of a child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def parse_trial_balance(raw_xml: str) -> list[dict]:
    """Parse Trial Balance XML into list of row dicts."""
    root = ET.fromstring(raw_xml)
    rows = []

    for acc in root.iter("DSPACCNAME"):
        name = _get_text(acc, "DSPDISPNAME")
        if not name:
            continue
        rows.append({
            "account_name": name,
            "debit_amount": parse_amount(_get_text(acc, "DSPCLDRAMT")),
            "credit_amount": parse_amount(_get_text(acc, "DSPCLCRAMT")),
            "closing_balance": _get_text(acc, "DSPCLAMT"),
        })

    return rows


def parse_ledger_list(raw_xml: str) -> list[dict]:
    """Parse ledger collection XML into list of ledger dicts."""
    root = ET.fromstring(raw_xml)
    ledgers = []

    for ledger in root.iter("LEDGER"):
        name = _get_text(ledger, "NAME")
        if not name:
            continue
        ledgers.append({
            "name": name,
            "parent_group": _get_text(ledger, "PARENT"),
            "closing_balance": parse_amount(_get_text(ledger, "CLOSINGBALANCE")),
            "opening_balance": parse_amount(_get_text(ledger, "OPENINGBALANCE")),
        })

    return ledgers
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_response_parser.py -v`
Expected: All 14 tests PASS

**Step 6: Commit**

```bash
git add backend/tally_bridge/response_parser.py tests/unit/test_response_parser.py tests/fixtures/
git commit -m "feat: add XML response parser with amount parsing and error detection"
```

---

### Task 10: TallyClient

**Files:**
- Create: `backend/tally_bridge/client.py`
- Create: `tests/unit/test_client.py`

**Step 1: Write failing tests**

```python
# tests/unit/test_client.py
import pytest

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyConnectionError


@pytest.fixture
def client():
    return TallyClient(host="localhost", port=9000)


def test_client_base_url(client):
    assert client.base_url == "http://localhost:9000"


def test_client_custom_host_port():
    c = TallyClient(host="192.168.1.100", port=9001)
    assert c.base_url == "http://192.168.1.100:9001"


@pytest.mark.asyncio
async def test_post_xml_connection_error():
    """Connecting to a port with nothing listening should raise TallyConnectionError."""
    c = TallyClient(host="localhost", port=19999)
    with pytest.raises(TallyConnectionError):
        await c.post_xml("<ENVELOPE></ENVELOPE>")


@pytest.mark.asyncio
async def test_health_check_returns_false_when_unreachable():
    c = TallyClient(host="localhost", port=19999)
    result = await c.health_check()
    assert result is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write client.py**

```python
"""
Core async HTTP client for TallyPrime communication.

TallyPrime runs as an HTTP server. We POST XML requests and parse responses.
CONNECTION: http://<TALLY_HOST>:<TALLY_PORT> (default: localhost:9000)
"""

import httpx

from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError
from backend.tally_bridge.request_builder import build_list_companies


class TallyClient:
    def __init__(self, host: str = "localhost", port: int = 9000):
        self.base_url = f"http://{host}:{port}"
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def post_xml(self, xml_payload: str) -> str:
        """Send XML request to Tally, return raw XML response string."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    content=xml_payload,
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                )
                response.raise_for_status()
                return response.text
        except httpx.ConnectError:
            raise TallyConnectionError(
                f"Cannot connect to TallyPrime at {self.base_url}. "
                "Ensure Tally is running with a company loaded and port is configured."
            )
        except httpx.TimeoutException:
            raise TallyConnectionError(
                f"TallyPrime at {self.base_url} timed out. "
                "The request may be too heavy or Tally is busy."
            )
        except httpx.HTTPStatusError as e:
            raise TallyResponseError(f"Tally returned HTTP {e.response.status_code}")

    async def health_check(self) -> bool:
        """Check if Tally is reachable and has a company loaded."""
        try:
            result = await self.post_xml(build_list_companies())
            return "<COMPANY>" in result or "COMPANY" in result.upper()
        except (TallyConnectionError, TallyResponseError):
            return False
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/unit/test_client.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add backend/tally_bridge/client.py tests/unit/test_client.py
git commit -m "feat: add async TallyClient with connection error handling"
```

---

### Task 11: Query Functions — Masters

**Files:**
- Create: `backend/tally_bridge/queries/masters.py`
- Create: `tests/fixtures/company_list.xml`
- Create: `tests/mocks/mock_tally_server.py`
- Create: `tests/integration/test_masters.py`

**Step 1: Create company_list.xml fixture**

`tests/fixtures/company_list.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
<COMPANY>
<NAME>Bharat Traders Pvt Ltd</NAME>
</COMPANY>
<COMPANY>
<NAME>Demo Company</NAME>
</COMPANY>
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>
```

**Step 2: Create mock Tally server**

```python
# tests/mocks/mock_tally_server.py
"""
Lightweight HTTP server mimicking TallyPrime's behavior.
Receives XML POST requests, pattern-matches the report type,
and returns corresponding fixture data.
"""

import os

from aiohttp import web

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")

REPORT_FIXTURES = {
    "List of Companies": "company_list.xml",
    "Trial Balance": "trial_balance.xml",
    "CustomLedgerList": "ledger_list.xml",
}


async def handle_tally_request(request: web.Request) -> web.Response:
    body = await request.text()

    for report_name, fixture_file in REPORT_FIXTURES.items():
        if report_name in body:
            fixture_path = os.path.join(FIXTURES_DIR, fixture_file)
            if os.path.exists(fixture_path):
                with open(fixture_path) as f:
                    return web.Response(text=f.read(), content_type="text/xml")

    return web.Response(
        text="<ENVELOPE><BODY><DATA>Unknown request</DATA></BODY></ENVELOPE>",
        content_type="text/xml",
    )


def create_mock_tally_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/", handle_tally_request)
    return app
```

**Step 3: Write failing integration tests**

```python
# tests/integration/test_masters.py
import pytest

from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.masters import list_companies, list_ledgers, search_ledger


@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient(host="localhost", port=server.port)
    return client


@pytest.mark.asyncio
async def test_list_companies(mock_tally):
    companies = await list_companies(mock_tally)
    assert len(companies) == 2
    assert companies[0].name == "Bharat Traders Pvt Ltd"


@pytest.mark.asyncio
async def test_list_ledgers(mock_tally):
    ledgers = await list_ledgers(mock_tally)
    assert len(ledgers) == 3
    assert any(l.name == "Cash" for l in ledgers)


@pytest.mark.asyncio
async def test_search_ledger(mock_tally):
    results = await search_ledger(mock_tally, "HDFC")
    assert len(results) >= 1
    assert any("HDFC" in l.name for l in results)


@pytest.mark.asyncio
async def test_search_ledger_no_match(mock_tally):
    results = await search_ledger(mock_tally, "ZZZZNONEXISTENT")
    assert len(results) == 0
```

**Step 4: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/integration/test_masters.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 5: Write masters.py**

```python
"""
Query functions for Tally master data: companies, ledgers, groups, stock items.
"""

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.models import Company, Ledger
from backend.tally_bridge.request_builder import (
    build_list_companies,
    build_list_ledgers,
)
from backend.tally_bridge.response_parser import detect_error, parse_ledger_list
from backend.tally_bridge.exceptions import TallyResponseError

import xml.etree.ElementTree as ET


async def list_companies(client: TallyClient) -> list[Company]:
    """Fetch all companies loaded in TallyPrime."""
    raw = await client.post_xml(build_list_companies())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)

    root = ET.fromstring(raw)
    companies = []
    for comp in root.iter("COMPANY"):
        name_el = comp.find("NAME")
        if name_el is not None and name_el.text:
            companies.append(Company(name=name_el.text.strip()))
        elif comp.text and comp.text.strip():
            companies.append(Company(name=comp.text.strip()))
    return companies


async def list_ledgers(client: TallyClient) -> list[Ledger]:
    """Fetch all ledgers with parent groups and balances."""
    raw = await client.post_xml(build_list_ledgers())
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)

    parsed = parse_ledger_list(raw)
    return [Ledger(**row) for row in parsed]


async def search_ledger(client: TallyClient, search_term: str) -> list[Ledger]:
    """Search ledgers by partial name match (case-insensitive)."""
    all_ledgers = await list_ledgers(client)
    term_lower = search_term.lower()
    return [l for l in all_ledgers if term_lower in l.name.lower()]
```

**Step 6: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/integration/test_masters.py -v`
Expected: All 4 tests PASS

**Step 7: Commit**

```bash
git add backend/tally_bridge/queries/masters.py tests/mocks/mock_tally_server.py tests/integration/test_masters.py tests/fixtures/company_list.xml
git commit -m "feat: add master query functions with mock Tally integration tests"
```

---

### Task 12: Query Functions — Reports

**Files:**
- Create: `backend/tally_bridge/queries/reports.py`
- Create: `tests/fixtures/profit_and_loss.xml`
- Create: `tests/fixtures/balance_sheet.xml`
- Create: `tests/fixtures/bills_receivable.xml`
- Create: `tests/fixtures/stock_summary.xml`
- Modify: `tests/mocks/mock_tally_server.py` (add new fixtures)
- Create: `tests/integration/test_reports.py`

**Step 1: Create fixture files**

`tests/fixtures/profit_and_loss.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<DSPACCNAME>
<DSPDISPNAME>Sales Accounts</DSPDISPNAME>
<DSPCLDRAMT></DSPCLDRAMT>
<DSPCLCRAMT>15,45,000.00</DSPCLCRAMT>
<DSPCLAMT>15,45,000.00 Cr</DSPCLAMT>
</DSPACCNAME>
<DSPACCNAME>
<DSPDISPNAME>Purchase Accounts</DSPDISPNAME>
<DSPCLDRAMT>10,20,000.00</DSPCLDRAMT>
<DSPCLCRAMT></DSPCLCRAMT>
<DSPCLAMT>10,20,000.00 Dr</DSPCLAMT>
</DSPACCNAME>
<DSPACCNAME>
<DSPDISPNAME>Indirect Expenses</DSPDISPNAME>
<DSPCLDRAMT>3,50,000.00</DSPCLDRAMT>
<DSPCLCRAMT></DSPCLCRAMT>
<DSPCLAMT>3,50,000.00 Dr</DSPCLAMT>
</DSPACCNAME>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/balance_sheet.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<DSPACCNAME>
<DSPDISPNAME>Capital Account</DSPDISPNAME>
<DSPCLDRAMT></DSPCLDRAMT>
<DSPCLCRAMT>7,50,000.00</DSPCLCRAMT>
<DSPCLAMT>7,50,000.00 Cr</DSPCLAMT>
</DSPACCNAME>
<DSPACCNAME>
<DSPDISPNAME>Bank Accounts</DSPDISPNAME>
<DSPCLDRAMT>7,00,000.00</DSPCLDRAMT>
<DSPCLCRAMT></DSPCLCRAMT>
<DSPCLAMT>7,00,000.00 Dr</DSPCLAMT>
</DSPACCNAME>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/bills_receivable.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<BILLSFIXED>
<BILLNAME>S001</BILLNAME>
<BILLPARTY>Apex Technologies Pvt Ltd</BILLPARTY>
<BILLDATE>20251001</BILLDATE>
<BILLAMOUNT>-94000.00</BILLAMOUNT>
<BILLPENDING>-40000.00</BILLPENDING>
</BILLSFIXED>
<BILLSFIXED>
<BILLNAME>S007</BILLNAME>
<BILLPARTY>Eastern Digital Hub</BILLPARTY>
<BILLDATE>20251115</BILLDATE>
<BILLAMOUNT>-116000.00</BILLAMOUNT>
<BILLPENDING>-50000.00</BILLPENDING>
</BILLSFIXED>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/stock_summary.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<COLLECTION>
<STOCKITEM>
<NAME>Samsung 24 inch Monitor</NAME>
<PARENT>Electronics</PARENT>
<BASEUNITS>Nos</BASEUNITS>
<CLOSINGBALANCE>15 Nos</CLOSINGBALANCE>
<CLOSINGRATE>11,000.00</CLOSINGRATE>
<CLOSINGVALUE>1,65,000.00</CLOSINGVALUE>
</STOCKITEM>
<STOCKITEM>
<NAME>HP Laptop 15s</NAME>
<PARENT>Electronics</PARENT>
<BASEUNITS>Nos</BASEUNITS>
<CLOSINGBALANCE>8 Nos</CLOSINGBALANCE>
<CLOSINGRATE>38,000.00</CLOSINGRATE>
<CLOSINGVALUE>3,04,000.00</CLOSINGVALUE>
</STOCKITEM>
</COLLECTION>
</DATA>
</BODY>
</ENVELOPE>
```

**Step 2: Update mock_tally_server.py to include new fixtures**

Add to `REPORT_FIXTURES` dict:
```python
    "Profit and Loss": "profit_and_loss.xml",
    "Balance Sheet": "balance_sheet.xml",
    "Bills Receivable": "bills_receivable.xml",
    "Bills Payable": "bills_receivable.xml",  # reuse fixture
    "Stock Summary": "stock_summary.xml",
```

**Step 3: Add parser functions for new report types**

Append to `backend/tally_bridge/response_parser.py`:

```python
def parse_profit_and_loss(raw_xml: str) -> list[dict]:
    """Parse P&L XML — same structure as trial balance."""
    return parse_trial_balance(raw_xml)


def parse_balance_sheet(raw_xml: str) -> list[dict]:
    """Parse Balance Sheet XML — same structure as trial balance."""
    return parse_trial_balance(raw_xml)


def parse_bills(raw_xml: str) -> list[dict]:
    """Parse Bills Receivable/Payable XML into list of bill dicts."""
    root = ET.fromstring(raw_xml)
    bills = []
    for bill in root.iter("BILLSFIXED"):
        name = _get_text(bill, "BILLNAME")
        if not name:
            continue
        bills.append({
            "bill_number": name,
            "party_name": _get_text(bill, "BILLPARTY"),
            "bill_date": _get_text(bill, "BILLDATE"),
            "amount": abs(parse_amount(_get_text(bill, "BILLAMOUNT"))),
            "pending_amount": abs(parse_amount(_get_text(bill, "BILLPENDING"))),
        })
    return bills


def parse_stock_summary(raw_xml: str) -> list[dict]:
    """Parse Stock Summary XML into list of stock item dicts."""
    root = ET.fromstring(raw_xml)
    items = []
    for item in root.iter("STOCKITEM"):
        name = _get_text(item, "NAME")
        if not name:
            continue
        closing_bal = _get_text(item, "CLOSINGBALANCE")
        # Extract quantity number from strings like "15 Nos"
        qty = 0.0
        if closing_bal:
            parts = closing_bal.split()
            if parts:
                try:
                    qty = float(parts[0].replace(",", ""))
                except ValueError:
                    pass
        items.append({
            "name": name,
            "parent_group": _get_text(item, "PARENT"),
            "base_units": _get_text(item, "BASEUNITS"),
            "closing_quantity": qty,
            "closing_rate": parse_amount(_get_text(item, "CLOSINGRATE")),
            "closing_value": parse_amount(_get_text(item, "CLOSINGVALUE")),
        })
    return items
```

**Step 4: Write failing integration tests**

```python
# tests/integration/test_reports.py
import pytest

from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.reports import (
    trial_balance,
    profit_and_loss,
    balance_sheet,
    bills_receivable,
    stock_summary,
)


@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient(host="localhost", port=server.port)
    return client


@pytest.mark.asyncio
async def test_trial_balance(mock_tally):
    result = await trial_balance(mock_tally, "01-04-2025", "31-03-2026")
    assert result.report_name == "Trial Balance"
    assert len(result.rows) == 3


@pytest.mark.asyncio
async def test_profit_and_loss(mock_tally):
    result = await profit_and_loss(mock_tally, "01-04-2025", "31-03-2026")
    assert result.report_name == "Profit and Loss"
    assert len(result.rows) > 0


@pytest.mark.asyncio
async def test_balance_sheet(mock_tally):
    result = await balance_sheet(mock_tally, "31-03-2026")
    assert result.report_name == "Balance Sheet"


@pytest.mark.asyncio
async def test_bills_receivable(mock_tally):
    bills = await bills_receivable(mock_tally, "31-03-2026")
    assert len(bills) == 2
    assert bills[0].party_name == "Apex Technologies Pvt Ltd"
    assert bills[0].pending_amount == 40000.0


@pytest.mark.asyncio
async def test_stock_summary(mock_tally):
    items = await stock_summary(mock_tally, "31-03-2026")
    assert len(items) == 2
    assert items[0]["name"] == "Samsung 24 inch Monitor"
    assert items[0]["closing_quantity"] == 15.0
```

**Step 5: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/integration/test_reports.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 6: Write reports.py**

```python
"""
Query functions for Tally financial reports.
"""

from datetime import date, datetime

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.models import ReportResponse, OutstandingBill
from backend.tally_bridge.request_builder import (
    build_trial_balance,
    build_profit_and_loss,
    build_balance_sheet,
    build_bills_receivable,
    build_bills_payable,
    build_stock_summary,
)
from backend.tally_bridge.response_parser import (
    detect_error,
    parse_trial_balance as _parse_tb,
    parse_profit_and_loss as _parse_pnl,
    parse_balance_sheet as _parse_bs,
    parse_bills,
    parse_stock_summary as _parse_stock,
)
from backend.tally_bridge.exceptions import TallyResponseError


def _parse_tally_date(date_str: str) -> date | None:
    """Parse Tally date format YYYYMMDD into date object."""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        return None


async def trial_balance(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Trial Balance for a date range."""
    raw = await client.post_xml(build_trial_balance(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_tb(raw)
    return ReportResponse(
        report_name="Trial Balance",
        company=company or "",
        rows=rows,
    )


async def profit_and_loss(
    client: TallyClient, from_date: str, to_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Profit & Loss statement."""
    raw = await client.post_xml(build_profit_and_loss(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_pnl(raw)
    return ReportResponse(
        report_name="Profit and Loss",
        company=company or "",
        rows=rows,
    )


async def balance_sheet(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> ReportResponse:
    """Fetch Balance Sheet as on a date."""
    raw = await client.post_xml(build_balance_sheet(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    rows = _parse_bs(raw)
    return ReportResponse(
        report_name="Balance Sheet",
        company=company or "",
        rows=rows,
    )


async def bills_receivable(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> list[OutstandingBill]:
    """Fetch outstanding receivables."""
    raw = await client.post_xml(build_bills_receivable(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_bills(raw)
    return [
        OutstandingBill(
            party_name=b["party_name"],
            bill_number=b["bill_number"],
            bill_date=_parse_tally_date(b["bill_date"]) or date.today(),
            amount=b["amount"],
            pending_amount=b["pending_amount"],
        )
        for b in parsed
    ]


async def bills_payable(
    client: TallyClient, as_on_date: str, company: str | None = None
) -> list[OutstandingBill]:
    """Fetch outstanding payables."""
    raw = await client.post_xml(build_bills_payable(as_on_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    parsed = parse_bills(raw)
    return [
        OutstandingBill(
            party_name=b["party_name"],
            bill_number=b["bill_number"],
            bill_date=_parse_tally_date(b["bill_date"]) or date.today(),
            amount=b["amount"],
            pending_amount=b["pending_amount"],
        )
        for b in parsed
    ]


async def stock_summary(
    client: TallyClient, as_on_date: str, stock_group: str | None = None, company: str | None = None
) -> list[dict]:
    """Fetch stock/inventory summary."""
    raw = await client.post_xml(build_stock_summary(as_on_date, stock_group, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return _parse_stock(raw)
```

**Step 7: Run tests to verify they pass**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/integration/test_reports.py -v`
Expected: All 5 tests PASS

**Step 8: Commit**

```bash
git add backend/tally_bridge/queries/reports.py backend/tally_bridge/response_parser.py tests/integration/test_reports.py tests/fixtures/ tests/mocks/mock_tally_server.py
git commit -m "feat: add report query functions with integration tests"
```

---

### Task 13: Query Functions — Vouchers

**Files:**
- Create: `backend/tally_bridge/queries/vouchers.py`
- Create: `tests/fixtures/day_book.xml`
- Create: `tests/fixtures/sales_register.xml`
- Modify: `tests/mocks/mock_tally_server.py`
- Create: `tests/integration/test_vouchers.py`

**Step 1: Create fixture files**

`tests/fixtures/day_book.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<VOUCHER>
<DATE>20251001</DATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
<VOUCHERNUMBER>S001</VOUCHERNUMBER>
<PARTYLEDGERNAME>Apex Technologies Pvt Ltd</PARTYLEDGERNAME>
<NARRATION>Invoice #S001 - Laptops and peripherals</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Apex Technologies Pvt Ltd</LEDGERNAME>
<AMOUNT>-94000.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Sales - Electronics</LEDGERNAME>
<AMOUNT>94000.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
<VOUCHER>
<DATE>20251010</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<VOUCHERNUMBER>PMT001</VOUCHERNUMBER>
<PARTYLEDGERNAME>Samsung India Electronics</PARTYLEDGERNAME>
<NARRATION>Part payment for PO #P001</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Samsung India Electronics</LEDGERNAME>
<AMOUNT>-400000.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>HDFC Bank - Current A/c</LEDGERNAME>
<AMOUNT>400000.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

`tests/fixtures/sales_register.xml`:
```xml
<ENVELOPE>
<BODY>
<DATA>
<TALLYMESSAGE>
<VOUCHER>
<DATE>20251001</DATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
<VOUCHERNUMBER>S001</VOUCHERNUMBER>
<PARTYLEDGERNAME>Apex Technologies Pvt Ltd</PARTYLEDGERNAME>
<NARRATION>Invoice #S001 - Laptops and peripherals</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Apex Technologies Pvt Ltd</LEDGERNAME>
<AMOUNT>-94000.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
<VOUCHER>
<DATE>20251008</DATE>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
<VOUCHERNUMBER>S002</VOUCHERNUMBER>
<PARTYLEDGERNAME>Sunrise Electronics Mumbai</PARTYLEDGERNAME>
<NARRATION>Invoice #S002 - Samsung products</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>Sunrise Electronics Mumbai</LEDGERNAME>
<AMOUNT>-110500.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
</TALLYMESSAGE>
</DATA>
</BODY>
</ENVELOPE>
```

**Step 2: Add voucher parser to response_parser.py**

Append to `backend/tally_bridge/response_parser.py`:

```python
def parse_vouchers(raw_xml: str) -> list[dict]:
    """Parse voucher list XML (Day Book, Sales Register, etc.) into dicts."""
    root = ET.fromstring(raw_xml)
    vouchers = []
    for v in root.iter("VOUCHER"):
        date_str = _get_text(v, "DATE")
        voucher_type = _get_text(v, "VOUCHERTYPENAME")
        voucher_number = _get_text(v, "VOUCHERNUMBER")
        party = _get_text(v, "PARTYLEDGERNAME")
        narration = _get_text(v, "NARRATION")

        # Collect ledger entries
        ledger_entries = []
        for entry in v.findall("ALLLEDGERENTRIES.LIST"):
            ledger_entries.append({
                "ledger_name": _get_text(entry, "LEDGERNAME"),
                "amount": parse_amount(_get_text(entry, "AMOUNT")),
            })

        vouchers.append({
            "date": date_str,
            "voucher_type": voucher_type,
            "voucher_number": voucher_number,
            "party_name": party,
            "narration": narration,
            "ledger_entries": ledger_entries,
        })
    return vouchers
```

**Step 3: Update mock server with new fixtures**

Add to `REPORT_FIXTURES` in `mock_tally_server.py`:
```python
    "Day Book": "day_book.xml",
    "Sales Register": "sales_register.xml",
    "Purchase Register": "sales_register.xml",  # reuse
    "Ledger Vouchers": "day_book.xml",  # reuse
```

**Step 4: Write failing integration tests**

```python
# tests/integration/test_vouchers.py
import pytest

from tests.mocks.mock_tally_server import create_mock_tally_app
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.vouchers import (
    day_book,
    sales_register,
    ledger_vouchers,
)


@pytest.fixture
async def mock_tally(aiohttp_server):
    app = create_mock_tally_app()
    server = await aiohttp_server(app)
    client = TallyClient(host="localhost", port=server.port)
    return client


@pytest.mark.asyncio
async def test_day_book(mock_tally):
    vouchers = await day_book(mock_tally, "01-10-2025", "31-10-2025")
    assert len(vouchers) == 2
    assert vouchers[0]["voucher_type"] == "Sales"


@pytest.mark.asyncio
async def test_sales_register(mock_tally):
    vouchers = await sales_register(mock_tally, "01-10-2025", "31-10-2025")
    assert len(vouchers) == 2
    assert all(v["voucher_type"] == "Sales" for v in vouchers)


@pytest.mark.asyncio
async def test_ledger_vouchers(mock_tally):
    vouchers = await ledger_vouchers(mock_tally, "HDFC Bank - Current A/c", "01-10-2025", "31-10-2025")
    assert len(vouchers) >= 1
```

**Step 5: Run tests to verify they fail**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/integration/test_vouchers.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 6: Write vouchers.py**

```python
"""
Query functions for Tally voucher data: day book, registers, ledger transactions.
"""

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.request_builder import (
    build_day_book,
    build_ledger_vouchers,
    build_sales_register,
    build_purchase_register,
)
from backend.tally_bridge.response_parser import detect_error, parse_vouchers
from backend.tally_bridge.exceptions import TallyResponseError


async def day_book(
    client: TallyClient,
    from_date: str,
    to_date: str,
    voucher_type: str | None = None,
    company: str | None = None,
) -> list[dict]:
    """Fetch all voucher entries for a date range."""
    raw = await client.post_xml(build_day_book(from_date, to_date, voucher_type, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def ledger_vouchers(
    client: TallyClient,
    ledger_name: str,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch all vouchers for a specific ledger."""
    raw = await client.post_xml(build_ledger_vouchers(ledger_name, from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def sales_register(
    client: TallyClient,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch sales register."""
    raw = await client.post_xml(build_sales_register(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)


async def purchase_register(
    client: TallyClient,
    from_date: str,
    to_date: str,
    company: str | None = None,
) -> list[dict]:
    """Fetch purchase register."""
    raw = await client.post_xml(build_purchase_register(from_date, to_date, company))
    error = detect_error(raw)
    if error:
        raise TallyResponseError(error)
    return parse_vouchers(raw)
```

**Step 7: Run all tests**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/ -v`
Expected: All tests PASS

**Step 8: Commit**

```bash
git add backend/tally_bridge/queries/vouchers.py backend/tally_bridge/response_parser.py tests/integration/test_vouchers.py tests/fixtures/ tests/mocks/mock_tally_server.py
git commit -m "feat: add voucher query functions with integration tests"
```

---

### Task 14: Tally Connection Test Script

**Files:**
- Create: `scripts/test_tally_connection.py`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""
Quick connectivity test for TallyPrime.

Usage:
    python scripts/test_tally_connection.py
    python scripts/test_tally_connection.py --host 192.168.1.100 --port 9000
"""

import argparse
import asyncio
import sys

from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyConnectionError
from backend.tally_bridge.queries.masters import list_companies, list_ledgers


async def test_connection(host: str, port: int) -> None:
    client = TallyClient(host=host, port=port)

    print(f"Testing connection to TallyPrime at {client.base_url}...")
    print()

    # Test 1: Health check
    print("[1/3] Health check...", end=" ")
    healthy = await client.health_check()
    if not healthy:
        print("FAILED")
        print("  TallyPrime is not reachable or no company is loaded.")
        print(f"  Ensure Tally is running on {host}:{port} with a company open.")
        sys.exit(1)
    print("OK")

    # Test 2: List companies
    print("[2/3] Listing companies...", end=" ")
    try:
        companies = await list_companies(client)
        print(f"OK — {len(companies)} company(ies) found")
        for c in companies:
            print(f"  - {c.name}")
    except Exception as e:
        print(f"FAILED — {e}")
        sys.exit(1)

    # Test 3: List ledgers
    print("[3/3] Fetching ledger list...", end=" ")
    try:
        ledgers = await list_ledgers(client)
        print(f"OK — {len(ledgers)} ledger(s) found")
        if ledgers:
            print(f"  First 5: {', '.join(l.name for l in ledgers[:5])}")
    except Exception as e:
        print(f"FAILED — {e}")
        sys.exit(1)

    print()
    print("All checks passed! TallyPrime is ready.")


def main():
    parser = argparse.ArgumentParser(description="Test TallyPrime connectivity")
    parser.add_argument("--host", default="localhost", help="Tally host (default: localhost)")
    parser.add_argument("--port", default=9000, type=int, help="Tally port (default: 9000)")
    args = parser.parse_args()

    asyncio.run(test_connection(args.host, args.port))


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add scripts/test_tally_connection.py
git commit -m "feat: add Tally connection test script"
```

---

### Task 15: Full Test Suite Run & Cleanup

**Step 1: Run all tests with coverage**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 2: Run with coverage report**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run pytest tests/ --cov=backend --cov-report=term-missing`
Expected: Coverage report showing all modules, high coverage for request_builder and response_parser

**Step 3: Verify all imports work end-to-end**

Run: `cd /Users/ripu/work/nuvanta_repos/tally_agent && uv run python -c "
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.masters import list_companies, list_ledgers, search_ledger
from backend.tally_bridge.queries.reports import trial_balance, profit_and_loss, balance_sheet, bills_receivable, bills_payable, stock_summary
from backend.tally_bridge.queries.vouchers import day_book, ledger_vouchers, sales_register, purchase_register
from backend.utils.date_utils import get_fy_start, get_fy_end, format_for_tally
from backend.utils.currency_format import format_inr
print('All Phase 1 imports OK')
"`
Expected: `All Phase 1 imports OK`

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: Phase 1 complete — Tally Bridge Layer with full test suite"
```
