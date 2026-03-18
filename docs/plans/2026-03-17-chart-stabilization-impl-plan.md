# Chart Stabilization Implementation Plan

**Status:** COMPLETE — merged to master 2026-03-18. 863 tests, multiple post-merge fixes.

**Goal:** Make chart rendering deterministic and correct by parsing markdown tables instead of STRUCTURED_RESULT, adding scale mismatch detection, fixing numeric parsing, and using a Haiku LLM advisor for semantic column selection.

**Architecture:** Markdown table parser extracts all tables from AnalysisAgent text. Haiku chart advisor (via tool_use) selects the best table and columns. ChartAgent formats the filtered data for Recharts. No rule-based fallback. AnalysisAgent uses streaming API for higher max_tokens.

**Tech Stack:** Python (FastAPI), pytest, Recharts (frontend unchanged), Claude Haiku (chart advisor via tool_use)

**Spec:** `docs/plans/2026-03-17-chart-stabilization-design.md`

**Additions beyond original plan:**
- Tasks 15-18: Haiku chart advisor (rule-based column selection proved insufficient)
- Post-merge: tool_use for advisor, streaming for AA, secondary promotion, token logging, timeout 480s

---

### Task 1: Add `CHARTS_ENABLED` config + test

**Files:**
- Modify: `backend/config.py:4-28`
- Modify: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: Add config field**

In `backend/config.py`, add after `ANALYSIS_CONTEXT_MESSAGES` (line 16):

```python
CHARTS_ENABLED: bool = True  # kill switch for chart rendering
```

- [ ] **Step 2: Run existing tests to verify no breakage**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: All existing tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/config.py
git commit -m "feat: add CHARTS_ENABLED config kill switch (default True)"
```

---

### Task 2: Move and enhance `_to_numeric()` to `utils.py` (TDD)

**Files:**
- Create: `tests/unit/test_chart_utils.py`
- Modify: `backend/agents/utils.py`
- Modify: `backend/agents/chart_agent.py:1-23,364-374`

- [ ] **Step 1: Write failing tests for enhanced `_to_numeric()`**

Create `tests/unit/test_chart_utils.py`:

```python
"""Tests for shared chart utility functions in backend.agents.utils."""

import pytest
from backend.agents.utils import to_numeric


class TestToNumeric:
    """Enhanced _to_numeric with emoji/symbol stripping."""

    def test_int(self):
        assert to_numeric(42) == 42.0

    def test_float(self):
        assert to_numeric(3.14) == 3.14

    def test_plain_string(self):
        assert to_numeric("123") == 123.0

    def test_negative(self):
        assert to_numeric("-45.6") == -45.6

    def test_currency_inr(self):
        assert to_numeric("₹7,08,500.00") == 708500.0

    def test_percentage(self):
        assert to_numeric("34.4%") == 34.4

    def test_bold_markers(self):
        assert to_numeric("**₹5,44,000**") == 544000.0

    def test_emoji_negative_percent(self):
        """🔴 −57.8% → -57.8"""
        assert to_numeric("🔴 −57.8%") == -57.8

    def test_emoji_positive_percent(self):
        """🟢 +82.0% → 82.0"""
        assert to_numeric("🟢 +82.0%") == 82.0

    def test_arrow_down_currency(self):
        """▼ −₹3,14,500.00 → -314500.0"""
        assert to_numeric("▼ −₹3,14,500.00") == -314500.0

    def test_arrow_up_currency(self):
        """▲ +₹1,88,250.00 → 188250.0"""
        assert to_numeric("▲ +₹1,88,250.00") == 188250.0

    def test_checkmark_emoji(self):
        assert to_numeric("✅ Above") == 0.0

    def test_down_arrow_emoji(self):
        assert to_numeric("⬇️ Below") == 0.0

    def test_medal_emoji_rank(self):
        """🥇 1 → 1.0"""
        assert to_numeric("🥇 1") == 1.0

    def test_medal_emoji_rank_2(self):
        """🥈 2 → 2.0"""
        assert to_numeric("🥈 2") == 2.0

    def test_dash_base(self):
        """'— (base)' → 0.0"""
        assert to_numeric("— (base)") == 0.0

    def test_single_dash(self):
        """'—' → 0.0"""
        assert to_numeric("—") == 0.0

    def test_na(self):
        assert to_numeric("N/A") == 0.0

    def test_pure_text(self):
        """Non-numeric text returns 0.0"""
        assert to_numeric("Global IT Solutions") == 0.0

    def test_unicode_minus(self):
        """Unicode minus U+2212 → regular minus"""
        assert to_numeric("−100.0%") == -100.0

    def test_none(self):
        assert to_numeric(None) == 0.0

    def test_flat_arrow(self):
        """➡️ Flat → 0.0"""
        assert to_numeric("➡️ Flat") == 0.0

    def test_parenthetical_note(self):
        """(Q3 lump-sum; Q4 bill pending) → 0.0"""
        assert to_numeric("(Q3 lump-sum; Q4 bill pending)") == 0.0

    def test_new_in_q4(self):
        """New in Q4 → 0.0"""
        assert to_numeric("New in Q4") == 0.0

    def test_negative_percentage_points(self):
        """−23.0 pp → -23.0"""
        assert to_numeric("−23.0 pp") == -23.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_utils.py -v`
Expected: FAIL — `to_numeric` not importable

- [ ] **Step 3: Implement `to_numeric()` in `utils.py`**

Add to `backend/agents/utils.py` (after existing functions, before EOF):

```python
import re

# Regex to strip emoji codepoints (covers most emoji ranges)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Misc symbols, emoticons, etc.
    "\U00002702-\U000027B0"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation selectors
    "\U0000200D"             # Zero width joiner
    "\U000025B2-\U000025BD"  # ▲▼△▽
    "\U00002B06-\U00002B07"  # ⬆⬇
    "\U000027A1"             # ➡
    "]+",
    flags=re.UNICODE,
)

# Sentinel strings that mean "no numeric value"
_NON_NUMERIC_SENTINELS = {"—", "–", "-", "n/a", "nil", "none", ""}


def to_numeric(val: Any) -> float:
    """Coerce a value to float, stripping currency, emoji, arrows, and symbols.

    Shared converter used by both the markdown table parser and ChartAgent.
    Returns 0.0 for non-numeric text.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return 0.0

    # Strip emoji and special symbols
    cleaned = _EMOJI_RE.sub("", val)
    # Unicode minus → ASCII minus
    cleaned = cleaned.replace("\u2212", "-")
    # Currency, formatting, percentage
    cleaned = cleaned.replace("₹", "").replace(",", "").replace("*", "").replace("%", "")
    # Percentage points suffix
    cleaned = cleaned.replace(" pp", "")
    # Strip whitespace
    cleaned = cleaned.strip()

    # Check sentinels (after stripping)
    if cleaned.lower() in _NON_NUMERIC_SENTINELS:
        return 0.0

    # Handle parenthetical notes like "(base)", "(Q3 lump-sum; Q4 bill pending)"
    if cleaned.startswith("(") and cleaned.endswith(")"):
        return 0.0

    # Strip leading + sign (keep -)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    try:
        return float(cleaned)
    except ValueError:
        return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_utils.py -v`
Expected: All PASS

- [ ] **Step 5: Update ChartAgent to use shared `to_numeric()`**

In `backend/agents/chart_agent.py`:

1. Add import at top (after line 14):
```python
from backend.agents.utils import to_numeric as _to_numeric
```

2. Delete the local `_to_numeric` function (lines 364-374).

- [ ] **Step 6: Run existing chart agent tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All existing tests PASS (behavior preserved)

- [ ] **Step 7: Commit**

```bash
git add backend/agents/utils.py backend/agents/chart_agent.py tests/unit/test_chart_utils.py
git commit -m "refactor: move _to_numeric to utils.py with emoji/symbol stripping"
```

---

### Task 3: Implement `parse_markdown_table_for_chart()` (TDD)

**Files:**
- Add to: `tests/unit/test_chart_utils.py`
- Modify: `backend/agents/utils.py`

- [ ] **Step 1: Write failing tests for markdown table parser**

Append to `tests/unit/test_chart_utils.py`:

```python
from backend.agents.utils import parse_markdown_table_for_chart


class TestParseMarkdownTableForChart:
    """Tests for parse_markdown_table_for_chart()."""

    def test_single_table(self):
        text = """Some intro text.

| Month | Sales |
|-------|-------|
| Jan | ₹1,00,000 |
| Feb | ₹2,00,000 |
| Mar | ₹3,00,000 |

Some outro text."""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Month", "Sales"]
        assert len(result["rows"]) == 3
        assert result["rows"][0] == ["Jan", 100000.0]

    def test_no_table(self):
        text = "No tables here, just text."
        assert parse_markdown_table_for_chart(text) is None

    def test_table_too_small(self):
        """Tables with < 2 data rows are skipped."""
        text = """| Name | Value |
|------|-------|
| Only | 100 |"""
        assert parse_markdown_table_for_chart(text) is None

    def test_multiple_tables_picks_most_rows(self):
        """When multiple tables, pick the one with most rows."""
        text = """Summary:
| Category | Total |
|----------|-------|
| A | 100 |
| B | 200 |

Details:
| Month | Amount | Growth |
|-------|--------|--------|
| Jan | 50 | 5% |
| Feb | 60 | 10% |
| Mar | 70 | 15% |
| Apr | 80 | 20% |
"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Month", "Amount", "Growth"]
        assert len(result["rows"]) == 4

    def test_multiple_tables_same_rows_picks_later(self):
        """Tie-break: prefer the later table when row counts are equal."""
        text = """First:
| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |

Second:
| X | Y |
|---|---|
| 5 | 6 |
| 7 | 8 |
"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["X", "Y"]

    def test_rank_column_skipped(self):
        """Rank column excluded, Customer becomes x-axis."""
        text = """| Rank | Customer | Sales |
|------|----------|-------|
| 1 | Alice | 100 |
| 2 | Bob | 200 |
| 3 | Carol | 300 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Customer", "Sales"]
        assert result["rows"][0][0] == "Alice"

    def test_hash_column_skipped(self):
        """# column excluded."""
        text = """| # | Ledger | Amount |
|---|--------|--------|
| 1 | Rent | 50000 |
| 2 | Salary | 100000 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Ledger", "Amount"]

    def test_emoji_rank_column_skipped(self):
        """🥇/🥈/🥉 ordinal column detected and skipped."""
        text = """| # | Expense | Amount |
|---|---------|--------|
| 🥇 | Salaries | 1000000 |
| 🥈 | Rent | 300000 |
| 🥉 | Travel | 15000 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Expense", "Amount"]
        assert result["rows"][0][0] == "Salaries"

    def test_sequential_int_column_skipped(self):
        """Column with sequential integers (1,2,3) detected as ordinal."""
        text = """| No | Item | Price |
|----|------|-------|
| 1 | Apple | 10 |
| 2 | Banana | 20 |
| 3 | Cherry | 30 |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["headers"] == ["Item", "Price"]

    def test_numeric_conversion_with_emoji(self):
        """Emoji-prefixed values parsed correctly."""
        text = """| Month | Sales | Change % |
|-------|-------|----------|
| Oct | ₹5,44,000 | — (base) |
| Nov | ₹2,29,500 | 🔴 −57.8% |
| Dec | ₹4,17,750 | 🟢 +82.0% |"""
        result = parse_markdown_table_for_chart(text)
        assert result is not None
        assert result["rows"][1][2] == -57.8
        assert result["rows"][2][2] == 82.0

    def test_total_row_preserved_in_parser(self):
        """Parser does NOT strip totals — that's ChartAgent's job."""
        text = """| Customer | Sales |
|----------|-------|
| Alice | 100 |
| Bob | 200 |
| Total | 300 |"""
        result = parse_markdown_table_for_chart(text)
        assert len(result["rows"]) == 3  # Total preserved

    def test_text_values_kept_as_strings(self):
        """Non-numeric cell values kept as strings (not converted to 0.0)."""
        text = """| Month | Sales | Status |
|-------|-------|--------|
| Jan | 100 | Good |
| Feb | 200 | Bad |"""
        result = parse_markdown_table_for_chart(text)
        assert result["rows"][0][2] == "Good"
        assert result["rows"][1][2] == "Bad"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_utils.py::TestParseMarkdownTableForChart -v`
Expected: FAIL — `parse_markdown_table_for_chart` not importable

- [ ] **Step 3: Implement `parse_markdown_table_for_chart()` in utils.py**

Add to `backend/agents/utils.py`:

```python
def _is_ordinal_header(header: str) -> bool:
    """Check if a column header suggests an ordinal/index column."""
    h = header.strip().lower().rstrip(".")
    return h in {"rank", "#", "s.no", "s no", "sr", "no", "sl", "sl no", "sl. no"}


def _is_ordinal_column(values: list, header: str) -> bool:
    """Detect ordinal columns: known headers or sequential integers."""
    if _is_ordinal_header(header):
        return True
    # Check if all values are sequential integers (via to_numeric)
    if len(values) < 2:
        return False
    nums = [to_numeric(v) for v in values]
    # All must be integers
    if not all(n == int(n) for n in nums if n != 0.0):
        return False
    ints = [int(n) for n in nums]
    # Check sequential (1,2,3... or 0,1,2...)
    if ints == list(range(ints[0], ints[0] + len(ints))):
        return True
    return False


def parse_markdown_table_for_chart(text: str) -> dict[str, Any] | None:
    """Parse the best markdown table from text for chart rendering.

    Finds all markdown tables, selects the one with most rows
    (tie-break: later table, then most columns), and returns
    {headers, rows} with ordinal columns stripped.

    Returns None if no suitable table found (< 2 data rows).
    """
    # Find all markdown table blocks (consecutive lines starting with |)
    lines = text.split("\n")
    tables: list[list[str]] = []
    current_block: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_block.append(stripped)
        else:
            if current_block:
                tables.append(current_block)
                current_block = []
    if current_block:
        tables.append(current_block)

    if not tables:
        return None

    # Parse each table block into (headers, rows, block_index)
    parsed: list[tuple[list[str], list[list], int]] = []
    for idx, block in enumerate(tables):
        if len(block) < 3:  # header + separator + at least 1 row
            continue
        # Parse header
        header_line = block[0]
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]

        # Find separator row and skip it
        data_start = 1
        for i, line in enumerate(block[1:], 1):
            # Separator row: |---|---|
            if all(cell.strip().replace("-", "").replace(":", "") == "" for cell in line.strip("|").split("|")):
                data_start = i + 1
                break

        # Parse data rows
        rows = []
        for line in block[data_start:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.append(cells)

        if len(rows) >= 2:
            parsed.append((headers, rows, idx))

    if not parsed:
        return None

    # Select best table: most rows, tie-break later table, then most columns
    best = max(parsed, key=lambda t: (len(t[1]), t[2], len(t[0])))
    headers, rows, _ = best

    # Detect and skip leading ordinal columns
    skip_cols = 0
    for col_idx, header in enumerate(headers):
        col_values = [row[col_idx] for row in rows if col_idx < len(row)]
        if _is_ordinal_column(col_values, header):
            skip_cols = col_idx + 1
        else:
            break

    # Apply column skip
    if skip_cols > 0:
        headers = headers[skip_cols:]
        rows = [[cell for i, cell in enumerate(row) if i >= skip_cols] for row in rows]

    # Convert numeric values, keep text as strings
    converted_rows = []
    for row in rows:
        converted = []
        for i, cell in enumerate(row):
            if i == 0:
                # First column (x-axis label) always kept as string
                converted.append(cell)
            else:
                num = to_numeric(cell)
                # Keep as string if to_numeric returned 0.0 but cell has text content
                # (not a dash/sentinel/empty)
                cell_stripped = cell.strip()
                if num == 0.0 and cell_stripped and cell_stripped.lower() not in _NON_NUMERIC_SENTINELS:
                    # Check if it's truly non-numeric text vs a legitimate zero
                    try:
                        float(cell_stripped.replace("₹", "").replace(",", "").replace("%", "").replace("*", "").strip())
                        converted.append(num)  # Legitimate zero
                    except ValueError:
                        converted.append(cell_stripped)  # Text value
                else:
                    converted.append(num)
        converted_rows.append(converted)

    return {"headers": headers, "rows": converted_rows}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_utils.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/utils.py tests/unit/test_chart_utils.py
git commit -m "feat: add parse_markdown_table_for_chart() with ordinal column detection"
```

---

### Task 4: ChartAgent Rule A — Scale mismatch detection (TDD)

**Files:**
- Add to: `tests/unit/test_chart_agent.py`
- Modify: `backend/agents/chart_agent.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_chart_agent.py` (in a new test class):

```python
class TestScaleMismatchDetection:
    """Rule A: detect and exclude mismatched-scale columns."""

    def test_count_column_excluded_when_scale_mismatch(self):
        """Invoices (2-3) vs Sales (₹7L) → Invoices excluded from y_keys."""
        headers = ["Customer", "Invoices", "Total Sales Amount"]
        rows = [
            ["Alice", 3, 708500],
            ["Bob", 2, 377000],
            ["Carol", 2, 275000],
        ]
        config = _build_config("bar", headers, rows)
        assert "Total Sales Amount" in config["y_keys"]
        assert "Invoices" not in config["y_keys"]

    def test_vouchers_excluded_when_scale_mismatch(self):
        """Vouchers (1-5) vs Sales Amount (₹2L-5L) → Vouchers excluded."""
        headers = ["Month", "Vouchers", "Sales Amount"]
        rows = [
            ["Oct", 5, 544000],
            ["Nov", 3, 229500],
            ["Dec", 3, 417750],
        ]
        config = _build_config("bar", headers, rows)
        assert "Sales Amount" in config["y_keys"]
        assert "Vouchers" not in config["y_keys"]

    def test_no_exclusion_when_same_scale(self):
        """Both columns similar scale → both kept."""
        headers = ["Month", "Revenue", "Expenses"]
        rows = [
            ["Q1", 500000, 400000],
            ["Q2", 600000, 450000],
        ]
        config = _build_config("bar", headers, rows)
        assert "Revenue" in config["y_keys"]
        assert "Expenses" in config["y_keys"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestScaleMismatchDetection -v`
Expected: FAIL — Invoices/Vouchers still in y_keys

- [ ] **Step 3: Implement scale mismatch detection**

In `backend/agents/chart_agent.py`, modify `_build_config()` (after line 319, where `numeric_cols` is computed):

```python
# --- Scale mismatch detection (Rule A) ---
_COUNT_COLUMN_PATTERNS = {"invoice", "voucher", "count", "no. of", "qty", "quantity", "number"}

def _detect_scale_mismatches(headers: list[str], rows: list[list], numeric_cols: set[str]) -> set[str]:
    """Detect columns with >100x scale difference from the largest column.

    Returns set of column headers to exclude from primary y_keys.
    Count columns are excluded entirely; other mismatches go to secondary axis.
    """
    if not rows or len(numeric_cols) < 2:
        return set()

    # Compute max absolute value per numeric column
    col_maxes: dict[str, float] = {}
    for h in numeric_cols:
        idx = headers.index(h) if h in headers else -1
        if idx < 0:
            continue
        max_val = max((abs(_to_numeric(row[idx])) for row in rows if idx < len(row)), default=0)
        col_maxes[h] = max_val

    if not col_maxes:
        return set()

    overall_max = max(col_maxes.values())
    if overall_max == 0:
        return set()

    exclude = set()
    for h, max_val in col_maxes.items():
        if max_val == 0 or overall_max / max(max_val, 0.001) > 100:
            h_lower = h.lower()
            if any(p in h_lower for p in _COUNT_COLUMN_PATTERNS):
                exclude.add(h)
            # Non-count mismatched columns: handled by secondary axis logic

    return exclude
```

Then in `_build_config()`, after `numeric_cols = _identify_numeric_columns(headers, rows)`:

```python
    scale_exclude = _detect_scale_mismatches(headers, rows, numeric_cols)
    y_keys = [h for h in headers[1:] if h in numeric_cols and h not in scale_exclude]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py::TestScaleMismatchDetection -v`
Expected: All PASS

- [ ] **Step 5: Run all chart agent tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "feat: chart Rule A — exclude count columns with >100x scale mismatch"
```

---

### Task 5: ChartAgent Rule B — Percentage value detection (TDD)

**Files:**
- Add to: `tests/unit/test_chart_agent.py`
- Modify: `backend/agents/chart_agent.py:25-30`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_chart_agent.py`:

```python
class TestPercentageValueDetection:
    """Rule B: detect percentage columns by header keywords, not just '%' symbol."""

    def test_operating_margin_detected_as_secondary(self):
        """'Operating Profit Margin' → secondary axis."""
        assert _is_secondary_axis_column("Operating Profit Margin") is True

    def test_growth_rate_detected(self):
        assert _is_secondary_axis_column("Growth Rate") is True

    def test_margin_detected(self):
        assert _is_secondary_axis_column("Gross Margin") is True

    def test_ratio_detected(self):
        assert _is_secondary_axis_column("Debt-Equity Ratio") is True

    def test_regular_column_not_detected(self):
        assert _is_secondary_axis_column("Sales Amount") is False

    def test_existing_percent_still_works(self):
        assert _is_secondary_axis_column("Change %") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestPercentageValueDetection -v`
Expected: FAIL — "Operating Profit Margin" returns False

- [ ] **Step 3: Enhance `_is_secondary_axis_column()`**

In `backend/agents/chart_agent.py`, modify `_is_secondary_axis_column()` (lines 25-30):

```python
_PERCENTAGE_HEADER_KEYWORDS = {"margin", "rate", "ratio", "growth"}

def _is_secondary_axis_column(header: str) -> bool:
    """Detect columns that belong on a secondary (percentage) axis."""
    if "%" in header:
        return True
    h_lower = header.lower()
    return any(kw in h_lower for kw in _PERCENTAGE_HEADER_KEYWORDS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py::TestPercentageValueDetection -v`
Expected: All PASS

- [ ] **Step 5: Run all chart agent tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All PASS (check for regressions in secondary axis detection)

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "feat: chart Rule B — detect % columns by header keywords (Margin, Rate, Ratio, Growth)"
```

---

### Task 6: ChartAgent Rule C — Enhanced total row exclusion (TDD)

**Files:**
- Add to: `tests/unit/test_chart_agent.py`
- Modify: `backend/agents/chart_agent.py:224-246`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_chart_agent.py`:

```python
class TestEnhancedTotalRowExclusion:
    """Rule C: expanded total row detection."""

    def test_total_revenue_skipped(self):
        headers = ["Ledger", "Q3", "Q4"]
        rows = [
            ["Sales - Electronics", 1139500, 811400],
            ["Sales - Office Supplies", 51750, 55000],
            ["Total Revenue", 1191250, 866400],
        ]
        data = _format_xy_data(headers, rows)
        labels = [d["label"] for d in data]
        assert "Total Revenue" not in labels
        assert "Sales - Electronics" in labels

    def test_total_opex_skipped(self):
        headers = ["Ledger", "Amount"]
        rows = [
            ["Rent", 150000],
            ["Salaries", 500000],
            ["Total OpEx", 650000],
        ]
        data = _format_xy_data(headers, rows)
        labels = [d["label"] for d in data]
        assert "Total OpEx" not in labels

    def test_grand_total_skipped(self):
        headers = ["Item", "Amount"]
        rows = [
            ["A", 100],
            ["B", 200],
            ["Grand Total", 300],
        ]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_net_total_skipped(self):
        headers = ["Item", "Amount"]
        rows = [
            ["A", 100],
            ["B", 200],
            ["Net Total", 300],
        ]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_bold_total_skipped(self):
        """**Total** with bold markers."""
        headers = ["Item", "Amount"]
        rows = [
            ["A", 100],
            ["B", 200],
            ["**Total**", 300],
        ]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_overall_skipped(self):
        headers = ["Item", "Amount"]
        rows = [
            ["A", 100],
            ["B", 200],
            ["Overall", 300],
        ]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2

    def test_non_total_kept(self):
        """Rows that happen to contain 'total' in a non-label context are kept."""
        headers = ["Item", "Amount"]
        rows = [
            ["Subtotal Adjustment", 100],
            ["Regular Item", 200],
        ]
        data = _format_xy_data(headers, rows)
        assert len(data) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestEnhancedTotalRowExclusion -v`
Expected: FAIL — "Total Revenue" not skipped

- [ ] **Step 3: Update `_format_xy_data()` total detection**

In `backend/agents/chart_agent.py`, modify `_format_xy_data()` (around line 230-232):

Replace:
```python
        if label.lower() in ("total", "grand total"):
            continue
```

With:
```python
        clean_label = label.replace("**", "").replace("*", "").strip().lower()
        if (clean_label in ("total", "grand total", "net total", "sub total", "overall")
                or clean_label.startswith("total ")):
            continue
```

Also apply the same fix in `_format_pie_data()` — add total row filtering before the existing sort at line 264:

```python
    # Filter out total rows before sorting
    filtered_rows = []
    for row in rows:
        label = str(row[0]) if row else ""
        clean_label = label.replace("**", "").replace("*", "").strip().lower()
        if (clean_label in ("total", "grand total", "net total", "sub total", "overall", "—")
                or clean_label.startswith("total ")):
            continue
        filtered_rows.append(row)
    sorted_rows = sorted(
        filtered_rows,
        key=lambda r: abs(_to_numeric(r[value_idx]) if len(r) > value_idx else 0),
        reverse=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py::TestEnhancedTotalRowExclusion -v`
Expected: All PASS

- [ ] **Step 5: Run all chart agent tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "feat: chart Rule C — enhanced total row exclusion (Total Revenue, OpEx, etc.)"
```

---

### Task 7: ChartAgent Rule D — Smarter zero trimming (TDD)

**Files:**
- Add to: `tests/unit/test_chart_agent.py`
- Modify: `backend/agents/chart_agent.py:347-361`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_chart_agent.py`:

```python
class TestSmarterZeroTrimming:
    """Rule D: preserve zeros when non-zero middle has < 3 points."""

    def test_preserves_zeros_when_few_nonzero_points(self):
        """6 leading zeros + 2 non-zero → preserve all (< 3 non-zero middle)."""
        headers = ["Month", "Sales"]
        rows = [
            ["Apr", 0], ["May", 0], ["Jun", 0],
            ["Jul", 0], ["Aug", 0], ["Sep", 0],
            ["Oct", 544000], ["Nov", 229500],
        ]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 8  # All preserved

    def test_trims_zeros_when_enough_nonzero(self):
        """3 leading zeros + 4 non-zero + 2 trailing zeros → trim edges."""
        headers = ["Month", "Sales"]
        rows = [
            ["Jan", 0], ["Feb", 0], ["Mar", 0],
            ["Apr", 100], ["May", 200], ["Jun", 300], ["Jul", 400],
            ["Aug", 0], ["Sep", 0],
        ]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 4
        assert result[0][0] == "Apr"
        assert result[-1][0] == "Jul"

    def test_no_zeros_unchanged(self):
        headers = ["Month", "Sales"]
        rows = [["Jan", 100], ["Feb", 200], ["Mar", 300]]
        result = _trim_trailing_zeros(headers, rows)
        assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestSmarterZeroTrimming -v`
Expected: FAIL — zeros trimmed even when few non-zero points

- [ ] **Step 3: Update `_trim_trailing_zeros()`**

In `backend/agents/chart_agent.py`, modify `_trim_trailing_zeros()` (lines 347-361):

```python
def _trim_trailing_zeros(headers: list[str], rows: list[list]) -> list[list]:
    """Remove leading and trailing all-zero rows from trend data.

    Only trims when the non-zero middle has >= 3 data points.
    This preserves contextually meaningful zero months.
    """
    if not rows or len(headers) < 2:
        return rows
    first_nonzero = None
    last_nonzero = None
    for i, row in enumerate(rows):
        val = _to_numeric(row[1]) if len(row) > 1 else 0
        if val != 0:
            if first_nonzero is None:
                first_nonzero = i
            last_nonzero = i
    if first_nonzero is None:
        return rows
    # Only trim if non-zero middle has >= 3 data points
    nonzero_span = last_nonzero - first_nonzero + 1
    if nonzero_span < 3:
        return rows  # Preserve all rows for context
    return rows[first_nonzero : last_nonzero + 1]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_chart_agent.py::TestSmarterZeroTrimming -v`
Expected: All PASS

- [ ] **Step 5: Run all chart agent tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "feat: chart Rule D — smarter zero trimming (preserve when < 3 non-zero points)"
```

---

### Task 8: Update ChartAgent.execute() signature (TDD)

**Files:**
- Add to: `tests/unit/test_chart_agent.py`
- Modify: `backend/agents/chart_agent.py:49-133,141-153`

- [ ] **Step 1: Write failing tests for new signature**

Append to `tests/unit/test_chart_agent.py`:

```python
class TestChartAgentNewSignature:
    """ChartAgent.execute() accepts {headers, rows} + chart_suggestion."""

    def test_basic_bar_chart(self):
        agent = ChartAgent()
        table_data = {
            "headers": ["Month", "Sales"],
            "rows": [["Jan", 100000], ["Feb", 200000], ["Mar", 300000]],
        }
        result = agent.execute(table_data, "top_n", chart_suggestion="bar")
        assert result is not None
        assert result["chart_type"] == "bar"
        assert len(result["data"]) == 3

    def test_table_only_suggestion(self):
        agent = ChartAgent()
        table_data = {
            "headers": ["Month", "Sales"],
            "rows": [["Jan", 100000], ["Feb", 200000]],
        }
        result = agent.execute(table_data, "simple_lookup", chart_suggestion="table_only")
        assert result is None

    def test_no_suggestion_infers_from_query_type(self):
        agent = ChartAgent()
        table_data = {
            "headers": ["Month", "Sales"],
            "rows": [["Jan", 100], ["Feb", 200], ["Mar", 300], ["Apr", 400]],
        }
        result = agent.execute(table_data, "trend")
        assert result is not None
        assert result["chart_type"] == "line"  # trend + ≥4 rows → line

    def test_chart_title_from_suggestion(self):
        agent = ChartAgent()
        table_data = {
            "headers": ["Customer", "Sales"],
            "rows": [["Alice", 100], ["Bob", 200], ["Carol", 300]],
        }
        result = agent.execute(table_data, "top_n", chart_suggestion="bar",
                               chart_title="Top Customers by Sales")
        assert result["title"] == "Top Customers by Sales"

    def test_empty_rows_returns_none(self):
        agent = ChartAgent()
        table_data = {"headers": ["A", "B"], "rows": []}
        result = agent.execute(table_data, "simple_lookup")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_chart_agent.py::TestChartAgentNewSignature -v`
Expected: FAIL — signature mismatch

- [ ] **Step 3: Update `ChartAgent.execute()` signature**

In `backend/agents/chart_agent.py`, replace the `execute()` method (lines 49-133):

```python
    def execute(
        self,
        table_data: dict[str, Any],
        query_type: str,
        chart_suggestion: str | None = None,
        chart_title: str | None = None,
    ) -> dict[str, Any] | None:
        """Determine chart spec from table data.

        Args:
            table_data: Dict with "headers" and "rows" keys.
            query_type: One of simple_lookup, comparison, trend, top_n, aggregation.
            chart_suggestion: Optional chart type suggestion from AnalysisAgent.
            chart_title: Optional chart title from AnalysisAgent.

        Returns:
            Chart spec dict or None if no chart is appropriate.
        """
        if not table_data or not table_data.get("rows"):
            logger.info("ChartAgent — no table data, skipping chart")
            return None

        headers = table_data["headers"]
        rows = table_data["rows"]

        # Trim leading/trailing zero-value rows from trend data
        if query_type in ("trend",) and rows:
            rows = _trim_trailing_zeros(headers, rows)
            if not rows:
                return None

        chart_type = _select_chart_type(chart_suggestion or "", query_type, rows)
        logger.info(
            "ChartAgent — suggestion=%r, query_type=%s, rows=%d, selected=%s",
            chart_suggestion, query_type, len(rows), chart_type,
        )

        if chart_type == "table_only":
            logger.info("ChartAgent — table_only, returning None")
            return None

        title = chart_title or _generate_title(query_type, headers)
        numeric_cols = _identify_numeric_columns(headers, rows)

        # Force table_only if too many non-numeric columns
        non_label_headers = headers[1:]
        non_numeric_count = sum(
            1 for h in non_label_headers
            if h not in numeric_cols
            and not _is_secondary_axis_column(h)
            and not _is_excluded_column(h)
        )
        if non_numeric_count >= 3:
            logger.info("ChartAgent — %d non-numeric columns, forcing table_only", non_numeric_count)
            return None

        chart_data = _format_chart_data(chart_type, headers, rows, numeric_cols)
        config = _build_config(chart_type, headers, rows)

        if not config["y_keys"]:
            logger.info("ChartAgent — no numeric y_keys, returning None")
            return None

        if config.get("secondary_y_keys"):
            chart_type = "composed"

        logger.info(
            "ChartAgent — chart_type=%s, y_keys=%s, secondary=%s",
            chart_type, config["y_keys"], config.get("secondary_y_keys", []),
        )

        return {
            "chart_type": chart_type,
            "title": title,
            "data": chart_data,
            "config": config,
        }
```

Also delete `_extract_table_data()` function (lines 141-153) — no longer needed.

- [ ] **Step 4: Update existing tests that use old signature**

In `tests/unit/test_chart_agent.py`, these specific tests need updating:

**Delete** (behavior moved to orchestrator):
- `test_returns_none_when_not_required` (line 79) — `requires_chart` no longer in ChartAgent

**Update signature** — change `execute(data_dict, query_type, requires_chart)` to `execute(table_data, query_type, chart_suggestion=...)`:

| Test method | Line | Change |
|-------------|------|--------|
| `test_returns_none_for_empty_data` | 87 | `execute({"headers": [], "rows": []}, "top_n")` |
| `test_returns_none_for_single_row` | 95 | `execute({"headers": ["Name", "Amount"], "rows": [["A", 100]]}, "top_n")` |
| `test_bar_chart_for_top_n` | 103 | `execute({"headers": [...], "rows": [...]}, "top_n")` — unwrap from `"data"` key |
| `test_composed_chart_for_comparison_with_change_pct` | 121 | Unwrap `"data"` key, no `requires_chart` |
| `test_composed_chart_for_trend_with_change_pct` | 143 | Same pattern |
| `test_no_composed_override_without_change_pct` | 160 | Same pattern |
| `test_pie_chart_for_aggregation` | 173 | Unwrap `"data"`, move `chart_suggestion` to kwarg |
| `test_pie_chart_groups_beyond_7_slices` | 191 | Same pattern |
| `test_config_has_required_keys` | 203 | Same pattern |
| `test_chart_with_analysis_result_shape` | 218 | Unwrap `"data"`, move `chart_suggestion` to kwarg |
| `test_chart_agent_returns_none_when_no_numeric_columns` | 456 | Same pattern |
| `test_force_table_only_when_many_non_numeric_columns` | 563 | Same pattern |
| `test_allows_chart_when_few_non_numeric_columns` | 580 | Same pattern |
| `test_allows_chart_with_two_text_columns` | 598 | Same pattern |
| `test_excludes_secondary_axis_columns_from_non_numeric_count` | 615 | Same pattern |
| `test_chart_agent_mixed_columns_charts_only_numeric` | 483 | Same pattern |

Also update the import line (line 10): remove `_to_numeric` from `chart_agent` imports, add `from backend.agents.utils import to_numeric as _to_numeric` for any tests that still reference it directly (TestToNumeric class can be moved/duplicated to test_chart_utils.py or updated to import from utils).

- [ ] **Step 5: Run all tests**

Run: `pytest tests/unit/test_chart_agent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agents/chart_agent.py tests/unit/test_chart_agent.py
git commit -m "refactor: update ChartAgent.execute() signature — table_data + chart_suggestion"
```

---

### Task 9: Update orchestrator to use new chart pipeline (TDD)

**Files:**
- Add to: `tests/unit/test_orchestrator.py`
- Modify: `backend/agents/orchestrator.py`

- [ ] **Step 1: Write tests for CHARTS_ENABLED behavior**

Append to `tests/unit/test_orchestrator.py`. Follow the existing test patterns in the file (AsyncMock, patching `backend.agents.orchestrator.anthropic_client`, mocking agent classes).

The key tests to add:

1. **`test_charts_disabled_no_chart_in_response`**: Patch `settings.CHARTS_ENABLED = False`. Mock AnalysisAgent to return a result with a markdown table in `message` and `chart_suggestion="bar"`. Assert `response["chart"] is None`. Assert chart metadata ("Chart suggestion:", "Chart title:") is still stripped from `response["message"]`.

2. **`test_charts_enabled_with_markdown_table`**: Keep `settings.CHARTS_ENABLED = True`. Mock AnalysisAgent to return a message containing a markdown table (e.g., `| Month | Sales |\n|---|---|\n| Jan | 100 |\n| Feb | 200 |\n| Mar | 300 |`). Assert `response["chart"] is not None` and has correct chart_type.

3. **`test_requires_chart_false_overrides_config`**: `settings.CHARTS_ENABLED = True` but classifier returns `requires_chart=False`. Assert `response["chart"] is None`.

4. **`test_table_only_suggestion_no_chart`**: `settings.CHARTS_ENABLED = True`, classifier returns `requires_chart=True`, but AnalysisAgent returns `chart_suggestion="table_only"`. Assert `response["chart"] is None`.

**Note on chart metadata stripping**: The stripping of "Chart suggestion:" and "Chart title:" lines from message text is already done by `AnalysisAgent._strip_chart_metadata()` (analysis_agent.py:779-784) BEFORE the result reaches the orchestrator. The orchestrator receives a result dict where `message` is already cleaned and `chart_suggestion`/`chart_title` are separate fields. Test #1 should verify this by checking the mock's return value is passed through correctly.

- [ ] **Step 2: Update orchestrator flow**

In `backend/agents/orchestrator.py`:

1. Add import at top (note: `settings` is already imported at line 25):
```python
from backend.agents.utils import parse_markdown_table_for_chart
```

2. Replace the chart generation block (around line 173-176):

Old:
```python
if requires_chart:
    chart = self.chart_agent.execute(analysis_result, query_type, requires_chart)
```

New:
```python
chart = None
if settings.CHARTS_ENABLED and requires_chart:
    chart_table = parse_markdown_table_for_chart(analysis_result.get("message", ""))
    if chart_table and analysis_result.get("chart_suggestion") != "table_only":
        chart = self.chart_agent.execute(
            chart_table,
            query_type,
            chart_suggestion=analysis_result.get("chart_suggestion"),
            chart_title=analysis_result.get("chart_title"),
        )
```

- [ ] **Step 3: Run all orchestrator tests**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 4: Run full unit test suite**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agents/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "feat: orchestrator uses markdown table parser for chart input + CHARTS_ENABLED"
```

---

### Task 10: Archive prompt rules 14-15, add table ordering guidance

**Files:**
- Modify: `backend/agents/prompts.py`

- [ ] **Step 1: Archive Rules 14-15**

In `backend/agents/prompts.py`, find Rules 14-15 (STRUCTURED_RESULT format rules, around lines 298-331). Move them to a new string constant:

```python
# Archived prompt rules — not included in active prompt.
# Preserved for reference and potential future reuse.
DEPRECATED_ANALYSIS_RULES = """
Rule 14 (ARCHIVED): STRUCTURED_RESULT output format...
Rule 15 (ARCHIVED): Standard column naming...
"""
```

Remove them from the active `ANALYSIS_SYSTEM_PROMPT` string.

- [ ] **Step 2: Add table ordering guidance**

Add a new rule in the active prompt (where Rules 14-15 were):

```
Rule 14: Table ordering — Always put the comprehensive/complete table LAST in your response. If you produce summary or filtered sub-tables (e.g., "Above Average", "Below Average"), place them BEFORE the main result table.
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/agents/prompts.py
git commit -m "refactor: archive STRUCTURED_RESULT prompt rules, add table ordering guidance"
```

---

### Task 11: Create E2E test fixtures from eval transcripts

**Files:**
- Create: `tests/fixtures/chart_transcript_fixtures.py`

- [ ] **Step 1: Create fixture module**

Create `tests/fixtures/chart_transcript_fixtures.py` with the actual AnalysisAgent response text from eval run `run_20260316_160527`, turns 2, 3, 4, 5, 7.

```python
"""Real AnalysisAgent response fixtures from eval run_20260316_160527.

Each fixture contains the exact response_message text with markdown tables,
used for testing the chart stabilization pipeline end-to-end.
"""

# Turn 2: Top 10 customers by sales amount
TURN_2_TOP_CUSTOMERS = {
    "query": "Top 10 customers by sales amount",
    "query_type": "top_n",
    "chart_suggestion": "bar",
    "message": """🏆 Top 10 Customers by Sales Amount — FY 2025-26

...full text from transcript...

| Rank | Customer | Invoices | Total Sales Amount | % of Total |
|------|----------|----------|-------------------|-----------|
| 🥇 1 | Global IT Solutions | 3 | ₹7,08,500.00 | 34.4% |
| 🥈 2 | Patel Enterprises | 2 | ₹3,77,000.00 | 18.3% |
| 🥉 3 | Eastern Digital Hub | 2 | ₹2,75,000.00 | 13.4% |
| 4 | Sunrise Electronics Mumbai | 2 | ₹2,51,500.00 | 12.2% |
| 5 | Apex Technologies Pvt Ltd | 3 | ₹2,37,000.00 | 11.5% |
| 6 | Rajesh Computers | 2 | ₹1,64,900.00 | 8.0% |
| 7 | Sharma & Sons Traders | 2 | ₹43,750.00 | 2.1% |
| Total | All Customers | 16 | ₹20,57,650.00 | 100.0% |
""",
    "expected_chart": {
        "x_axis_header": "Customer",
        "excluded_columns": {"Invoices"},  # scale mismatch
        "y_keys_must_include": ["Total Sales Amount"],
        "secondary_y_keys": ["% of Total"],
        "total_row_excluded": True,
        "row_count": 7,  # 7 data rows (Total excluded)
    },
}

# Turn 3, 4, 5, 7: Same structure as Turn 2 above.
# Implementer MUST extract the full response_message text — see extraction instructions below.
```

**Fixture extraction instructions:**

The implementer MUST extract the EXACT `response_message` text from the transcript JSON file:

**Source file**: `tests/eval/results/run_20260316_160527/transcripts/stock_reorder_mock_20260316_161719.json`

**JSON path per turn** (0-indexed in the `turns` array):
- Turn 2: `turns[1].response_message` — "Top 10 customers by sales"
- Turn 3: `turns[2].response_message` — "MoM growth"
- Turn 4: `turns[3].response_message` — "Q3 vs Q4 revenue and expenses"
- Turn 5: `turns[4].response_message` — "Expense ledger breakdown"
- Turn 7: `turns[6].response_message` — "Average monthly sales"

**Each fixture dict must include**:
- `query`: The user query string
- `query_type`: One of `top_n`, `trend`, `comparison`, `aggregation`
- `chart_suggestion`: The chart type (e.g., `"bar"`, `"composed"`, `"pie"`)
- `message`: The FULL `response_message` text (copy-paste, preserving all emoji, formatting, tables)
- `expected_chart`: Dict with validation expectations (x_axis_header, excluded_columns, y_keys, secondary_y_keys, etc.)

**Expected chart values per turn**:
- Turn 3 (MoM): `query_type="trend"`, `chart_suggestion="composed"`, x_axis="Month", exclude Vouchers (scale), Change % must NOT be zeroed
- Turn 4 (Q3 vs Q4): `query_type="comparison"`, `chart_suggestion="grouped_bar"`, x_axis="Ledger" or "Metric", Operating Profit Margin → secondary axis, has 3 tables (Revenue, OpEx, P&L Summary — parser should pick P&L Summary as largest)
- Turn 5 (Expense): `query_type="aggregation"`, `chart_suggestion="pie"`, x_axis="Expense Ledger" (# skipped), Grand Total excluded, 6 data slices
- Turn 7 (Avg monthly): `query_type="trend"`, `chart_suggestion="composed"`, x_axis="Month", all Change % values must be present (negatives too), zero months preserved

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/chart_transcript_fixtures.py
git commit -m "test: add real transcript fixtures for chart pipeline E2E tests"
```

---

### Task 12: E2E chart pipeline tests

**Files:**
- Create: `tests/e2e/test_chart_pipeline.py`

- [ ] **Step 1: Write E2E tests**

Create `tests/e2e/test_chart_pipeline.py`:

```python
"""E2E tests for chart stabilization pipeline.

Tests the full flow: AnalysisAgent response text → markdown table parser
→ ChartAgent → chart spec validation.

Uses real transcript fixtures from eval run_20260316_160527.
"""

import pytest
from backend.agents.chart_agent import ChartAgent
from backend.agents.utils import parse_markdown_table_for_chart
from tests.fixtures.chart_transcript_fixtures import (
    TURN_2_TOP_CUSTOMERS,
    TURN_3_MOM_GROWTH,
    TURN_4_Q3_VS_Q4,
    TURN_5_EXPENSE_BREAKDOWN,
    TURN_7_AVG_MONTHLY,
)


class TestChartPipelineE2E:

    def _run_pipeline(self, fixture):
        """Parse markdown table → ChartAgent → chart spec."""
        table_data = parse_markdown_table_for_chart(fixture["message"])
        assert table_data is not None, f"Failed to parse table from fixture: {fixture['query']}"

        agent = ChartAgent()
        chart = agent.execute(
            table_data,
            fixture["query_type"],
            chart_suggestion=fixture.get("chart_suggestion"),
        )
        return table_data, chart

    def test_turn2_top_customers(self):
        """Turn 2: Rank skipped, Invoices excluded (scale), Total excluded."""
        expected = TURN_2_TOP_CUSTOMERS["expected_chart"]
        table_data, chart = self._run_pipeline(TURN_2_TOP_CUSTOMERS)

        # X-axis is Customer, not Rank
        assert table_data["headers"][0] == expected["x_axis_header"]

        assert chart is not None
        # Invoices excluded from y_keys
        for col in expected["excluded_columns"]:
            assert col not in chart["config"]["y_keys"]
        # Sales Amount in y_keys
        for col in expected["y_keys_must_include"]:
            assert col in chart["config"]["y_keys"]
        # % of Total on secondary axis
        assert chart["config"].get("secondary_y_keys") == expected["secondary_y_keys"]
        # Total row excluded
        labels = [d["label"] for d in chart["data"]]
        assert not any("total" in l.lower() for l in labels)
        assert len(chart["data"]) == expected["row_count"]

    def test_turn3_mom_growth(self):
        """Turn 3: Change % parsed correctly (not zeroed), Vouchers excluded."""
        expected = TURN_3_MOM_GROWTH["expected_chart"]
        table_data, chart = self._run_pipeline(TURN_3_MOM_GROWTH)

        assert chart is not None
        assert chart["chart_type"] == "composed"  # has secondary axis

        # Vouchers excluded
        for col in expected["excluded_columns"]:
            assert col not in chart["config"]["y_keys"]

        # Change % values are NOT all zeros
        change_pcts = [d.get("Change %", 0) for d in chart["data"]]
        assert not all(v == 0 for v in change_pcts), \
            f"Change % all zeroed: {change_pcts}"

        # Total row excluded
        labels = [d["label"] for d in chart["data"]]
        assert "Total" not in labels

    def test_turn4_q3_vs_q4(self):
        """Turn 4: Multiple tables → picks P&L Summary, Margin on secondary axis."""
        expected = TURN_4_Q3_VS_Q4["expected_chart"]
        table_data, chart = self._run_pipeline(TURN_4_Q3_VS_Q4)

        assert chart is not None
        # Operating Profit Margin should be on secondary axis
        secondary = chart["config"].get("secondary_y_keys", [])
        assert any("margin" in k.lower() or "%" in k for k in secondary), \
            f"Expected Margin on secondary axis, got: {secondary}"

        # Change % not zeroed
        change_pcts = [d.get("Change %", 0) for d in chart["data"]]
        assert not all(v == 0 for v in change_pcts)

    def test_turn5_expense_pie(self):
        """Turn 5: Pie chart, # column skipped, Grand Total excluded."""
        expected = TURN_5_EXPENSE_BREAKDOWN["expected_chart"]
        table_data, chart = self._run_pipeline(TURN_5_EXPENSE_BREAKDOWN)

        # X-axis is Expense Ledger, not #
        assert table_data["headers"][0] == expected["x_axis_header"]

        assert chart is not None
        assert chart["chart_type"] == expected["chart_type"]
        # Grand Total / — rows excluded
        labels = [d["label"] for d in chart["data"]]
        assert "Grand Total" not in labels
        assert "—" not in labels

    def test_turn7_avg_monthly(self):
        """Turn 7: All months' Change % parsed (including negatives)."""
        expected = TURN_7_AVG_MONTHLY["expected_chart"]
        table_data, chart = self._run_pipeline(TURN_7_AVG_MONTHLY)

        assert chart is not None
        # Change % values should include negatives (not zeroed)
        change_pcts = [d.get("Change %", 0) for d in chart["data"]]
        has_negative = any(v < 0 for v in change_pcts)
        assert has_negative, f"Expected negative Change % values, got: {change_pcts}"
```

- [ ] **Step 2: Run E2E tests**

Run: `pytest tests/e2e/test_chart_pipeline.py -v`
Expected: All 5 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_chart_pipeline.py
git commit -m "test: E2E chart pipeline tests with real transcript fixtures (5 turns)"
```

---

### Task 13: Run full test suite + verify

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/`
Expected: All PASS. Note the total count for MEMORY.md update.

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All 116 tests PASS (no frontend changes, just confirming no breakage)

- [ ] **Step 3: Commit any fixes**

If any tests fail, fix and commit separately.

---

### Task 14: Playwright visual tests for chart rendering

**Files:**
- Modify: `frontend/tests/playwright/eval-visual.spec.ts` (or new file)
- Create: Chart fixture JSON files for Playwright tests

This task depends on the frontend test infrastructure. The implementer should:

1. Create chart spec JSON fixtures that match the E2E test outputs (Turn 2 bar, Turn 3 composed, Turn 5 pie)
2. Create a Playwright test that renders these fixtures in a test page
3. Screenshot and visually verify:
   - Correct x-axis labels (names not ranks)
   - No invisible bars (scale mismatch fixed)
   - Change % line not flat at zero
   - Total rows not in chart

- [ ] **Step 1: Create chart fixture data**
- [ ] **Step 2: Write Playwright tests**
- [ ] **Step 3: Run and capture screenshots**

Run: `cd frontend && npm run test:playwright -- --update-snapshots`

- [ ] **Step 4: Visually inspect screenshots**

Check `frontend/tests/playwright/__screenshots__/` for chart screenshots. Verify correctness manually.

- [ ] **Step 5: Commit**

```bash
git add frontend/tests/playwright/
git commit -m "test: Playwright visual tests for chart stabilization"
```

---

## Task Dependency Graph

```
Task 1 (config) ─────────────────────────────────────────┐
Task 2 (to_numeric) ──┐                                  │
Task 3 (parser) ──────┤                                  │
Task 4 (Rule A) ──────┤                                  │
Task 5 (Rule B) ──────┼── Task 8 (signature) ── Task 9 (orchestrator) ── Task 13 (verify)
Task 6 (Rule C) ──────┤                                  │
Task 7 (Rule D) ──────┘                                  │
                                                          │
Task 10 (prompts) ────────────────────────────────────────┘
Task 11 (fixtures) ── Task 12 (E2E tests) ── Task 13
Task 14 (Playwright) ── after Task 13
```

**Parallelizable:** Tasks 1, 4, 5, 6, 7 can all run in parallel. Tasks 2→3 must be sequential (3 depends on 2's `to_numeric`). Tasks 4-7 are independent of each other and of 2-3.

**Sequential:** Task 8 depends on Tasks 2-7. Task 9 depends on Tasks 1, 8. Task 12 depends on Tasks 9, 11. Task 13 depends on all. Task 14 depends on Task 13.
