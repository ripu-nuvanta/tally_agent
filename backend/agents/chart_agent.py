"""Chart Agent — rule-based chart type selection and Recharts data formatting.

Pure Python, no Claude API call. Deterministically selects the appropriate chart
type based on query_type and data shape, then formats data for the React frontend
(Recharts library).

Exports:
    ChartAgent — The main agent class.
"""

from __future__ import annotations

from typing import Any

# Default color palette for Recharts
DEFAULT_COLORS = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"]

# Columns excluded from chart data points (absolute change is noise; Change % goes to secondary axis)
_EXCLUDED_CHART_COLUMNS = {"Change"}


class ChartAgent:
    """Selects chart type and formats data for Recharts rendering."""

    def execute(
        self,
        data: dict[str, Any],
        query_type: str,
        requires_chart: bool,
    ) -> dict[str, Any] | None:
        """Determine chart spec from analysis result.

        Args:
            data: Either an AnalysisAgent result dict (with "data", "chart_suggestion")
                  or raw data dict from query agent.
            query_type: One of simple_lookup, comparison, trend, top_n, aggregation.
            requires_chart: Whether the orchestrator determined a chart is needed.

        Returns:
            Chart spec dict or None if no chart is appropriate.
        """
        if not requires_chart:
            return None

        table_data = _extract_table_data(data)
        if not table_data or not table_data.get("rows"):
            return None

        headers = table_data["headers"]
        rows = table_data["rows"]

        # Trim leading/trailing zero-value rows from trend data
        if query_type in ("trend",) and rows:
            rows = _trim_trailing_zeros(headers, rows)
            if not rows:
                return None

        # Use analysis agent's suggestion if available, otherwise infer from query_type
        chart_suggestion = data.get("chart_suggestion", "")
        chart_type = _select_chart_type(chart_suggestion, query_type, rows)

        if chart_type == "table_only":
            return None

        # Prefer analysis agent's suggested title over auto-generated one
        title = data.get("chart_title") or _generate_title(query_type, headers)
        chart_data = _format_chart_data(chart_type, headers, rows)
        config = _build_config(chart_type, headers, rows)

        # No numeric columns to chart → skip
        if not config["y_keys"]:
            return None

        # Override to composed chart when secondary axis data is present
        if config.get("secondary_y_keys"):
            chart_type = "composed"

        return {
            "chart_type": chart_type,
            "title": title,
            "data": chart_data,
            "config": config,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_table_data(data: dict[str, Any]) -> dict | None:
    """Extract headers/rows from either analysis result or raw data."""
    # Analysis agent result shape
    if isinstance(data.get("data"), dict):
        inner = data["data"]
        if "headers" in inner and "rows" in inner:
            return inner

    # Raw data might be a ReportResponse-style dict
    if "headers" in data and "rows" in data:
        return data

    return None


def _select_chart_type(suggestion: str, query_type: str, rows: list) -> str:
    """Select chart type based on suggestion, query type, and data shape."""
    num_rows = len(rows)

    # Too few data points — table only
    if num_rows < 2:
        return "table_only"

    # If analysis agent gave a valid suggestion, prefer it
    # (pie charts handle >7 slices by grouping into "Others" in _format_pie_data)
    valid_types = {"bar", "grouped_bar", "line", "pie", "stacked_bar", "composed", "table_only"}
    if suggestion in valid_types:
        return suggestion

    # Infer from query_type
    if query_type == "comparison":
        return "grouped_bar"

    if query_type == "trend":
        return "line" if num_rows >= 4 else "grouped_bar"

    if query_type == "top_n":
        return "bar"

    if query_type == "aggregation":
        if num_rows <= 7:
            return "pie"
        return "bar"

    # simple_lookup or unknown — bar if enough data, else table
    if num_rows >= 3:
        return "bar"

    return "table_only"


def _generate_title(query_type: str, headers: list[str]) -> str:
    """Generate a reasonable chart title from context."""
    type_titles = {
        "comparison": "Comparison",
        "trend": "Trend Analysis",
        "top_n": "Ranking",
        "aggregation": "Summary",
        "simple_lookup": "Data Overview",
    }
    base = type_titles.get(query_type, "Chart")
    if len(headers) >= 2:
        # Use first non-excluded numeric header for meaningful titles
        value_headers = [
            h for h in headers[1:]
            if h not in _EXCLUDED_CHART_COLUMNS and h != "Change %"
        ]
        value_label = value_headers[0] if value_headers else headers[1]
        return f"{base}: {value_label} by {headers[0]}"
    return base


def _format_chart_data(
    chart_type: str, headers: list[str], rows: list[list]
) -> list[dict[str, Any]]:
    """Format rows into Recharts-compatible data points."""
    if chart_type == "pie":
        return _format_pie_data(headers, rows)

    # bar, grouped_bar, line, stacked_bar, composed — all use standard x/y format
    return _format_xy_data(headers, rows)


def _format_xy_data(headers: list[str], rows: list[list]) -> list[dict[str, Any]]:
    """Standard label/value format for bar and line charts."""
    data = []
    for row in rows:
        label = str(row[0]) if row else ""
        if label.lower() in ("total", "grand total"):
            continue
        point: dict[str, Any] = {"label": label}
        for i, header in enumerate(headers[1:], start=1):
            if header in _EXCLUDED_CHART_COLUMNS:
                continue
            if i < len(row):
                point[header] = _to_numeric(row[i])
        data.append(point)
    return data


def _format_pie_data(headers: list[str], rows: list[list]) -> list[dict[str, Any]]:
    """Pie chart: label + value, max 7 slices (rest grouped as 'Others')."""
    value_idx = min(1, len(headers) - 1)
    sorted_rows = sorted(rows, key=lambda r: abs(_to_numeric(r[value_idx]) if len(r) > value_idx else 0), reverse=True)

    data = []
    others_total = 0.0
    for i, row in enumerate(sorted_rows):
        val = _to_numeric(row[value_idx]) if len(row) > value_idx else 0
        if i < 6 or len(sorted_rows) <= 7:
            data.append({"label": str(row[0]) if row else "", "value": abs(val)})
        else:
            others_total += abs(val)

    if others_total > 0:
        data.append({"label": "Others", "value": others_total})

    return data


def _identify_numeric_columns(headers: list[str], rows: list[list]) -> set[str]:
    """Identify columns where >50% of values are numeric.

    Skips the first column (label/x-axis). Returns set of header names
    that should be used as y-axis values.
    """
    if not rows or len(headers) < 2:
        return set(headers[1:])

    numeric_headers = set()
    for col_idx in range(1, len(headers)):
        header = headers[col_idx]
        if header in _EXCLUDED_CHART_COLUMNS or header == "Change %":
            continue
        numeric_count = 0
        total = 0
        for row in rows:
            if col_idx < len(row):
                total += 1
                val = row[col_idx]
                if isinstance(val, (int, float)):
                    numeric_count += 1
                elif isinstance(val, str):
                    cleaned = val.replace("₹", "").replace(",", "").replace("%", "").replace(" ", "").strip()
                    try:
                        float(cleaned)
                        numeric_count += 1
                    except ValueError:
                        pass
        if total > 0 and numeric_count / total > 0.5:
            numeric_headers.add(header)
    return numeric_headers


def _build_config(chart_type: str, headers: list[str], rows: list[list] | None = None) -> dict[str, Any]:
    """Build Recharts config with axis labels and colors."""
    x_key = "label"
    if rows is not None:
        numeric_cols = _identify_numeric_columns(headers, rows)
        y_keys = [h for h in headers[1:] if h in numeric_cols]
    else:
        y_keys = [h for h in headers[1:] if h not in _EXCLUDED_CHART_COLUMNS and h != "Change %"]

    # Detect secondary axis data (Change % column)
    secondary_y_keys = [h for h in headers[1:] if h == "Change %"]

    # For numeric-only data, limit to actual value columns
    if chart_type == "pie":
        y_keys = ["value"]
        secondary_y_keys = []

    config: dict[str, Any] = {
        "x_key": x_key,
        "y_keys": y_keys,
        "colors": DEFAULT_COLORS[: max(len(y_keys), 1)],
        "currency_format": True,
        "show_legend": len(y_keys) > 1 or bool(secondary_y_keys),
    }

    if secondary_y_keys:
        config["secondary_y_keys"] = secondary_y_keys
        config["secondary_colors"] = ["#9CA3AF"]  # gray for Change % line

    return config


def _trim_trailing_zeros(headers: list[str], rows: list[list]) -> list[list]:
    """Remove leading and trailing all-zero rows from trend data."""
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
    return rows[first_nonzero : last_nonzero + 1]


def _to_numeric(val: Any) -> float:
    """Coerce a value to float, stripping currency symbols and commas."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("₹", "").replace(",", "").replace("%", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0
