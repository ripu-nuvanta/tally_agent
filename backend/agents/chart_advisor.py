"""Chart Advisor — lightweight Haiku LLM call for chart column selection.

Makes a single API call to determine which table and columns to visualize,
replacing complex rule-based heuristics with semantic understanding.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)

# Module-level client (patchable in tests)
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

CHART_ADVISOR_SYSTEM_PROMPT = """You are a chart column selector. Given markdown tables from a data analysis response, select the BEST single chart configuration.

Rules:
1. Pick ONE table that best answers the user's query for visualization
2. Pick the x-axis column (categorical labels like names, months, categories — NOT rank/index columns)
3. Pick 1-3 y-axis columns (numeric values that are meaningful to compare at the same scale)
4. If there are percentage columns, put them on secondary_y_columns (right axis)
5. Do NOT include count columns (like "Invoices", "Vouchers", "Customers") alongside currency columns — different scales make bars invisible
6. Do NOT include total/summary rows — they skew the scale
7. Skip ordinal/rank columns (Rank, #, S.No) — not meaningful for charts
8. Prefer fewer y-axis columns — 2-3 series max for readability
9. Date columns (like "Due Date") are text, not numeric — don't chart them
10. If the user query asks to compare specific periods, pick those period columns as y-axis

Supported chart types: bar, grouped_bar, line, pie, composed, table_only

Choose chart type:
- bar: ranking or single metric comparison
- grouped_bar: comparing 2-3 metrics side by side
- line: trends over time (≥4 data points)
- pie: proportional breakdown (≤7 categories)
- composed: mixing bars (currency) with line (percentage on secondary axis)
- table_only: data not suitable for visualization

Respond with ONLY valid JSON:
{"table_index": 0, "x_column": "name", "y_columns": ["col1"], "secondary_y_columns": [], "chart_type": "bar", "chart_title": "Title"}"""


def _format_tables_for_prompt(tables: list[dict]) -> str:
    """Format parsed tables into readable text for the prompt."""
    parts = []
    for i, table in enumerate(tables):
        headers = table["headers"]
        rows = table["rows"]
        # Build markdown table string
        header_line = "| " + " | ".join(str(h) for h in headers) + " |"
        sep_line = "| " + " | ".join("---" for _ in headers) + " |"
        row_lines = []
        for row in rows[:10]:  # Max 10 rows to keep prompt short
            row_lines.append("| " + " | ".join(str(c) for c in row) + " |")
        if len(rows) > 10:
            row_lines.append(f"... ({len(rows) - 10} more rows)")

        parts.append(
            f"### Table {i} ({len(rows)} rows)\n{header_line}\n{sep_line}\n"
            + "\n".join(row_lines)
        )

    return "\n\n".join(parts)


async def get_chart_advice(
    tables: list[dict],
    user_query: str,
    chart_suggestion: str | None = None,
) -> dict | None:
    """Ask Haiku which table and columns to chart.

    Args:
        tables: List of parsed tables, each with {"headers": [...], "rows": [...]}
        user_query: The original user query for context
        chart_suggestion: Optional suggestion from AnalysisAgent

    Returns:
        Dict with keys: table_index, x_column, y_columns, secondary_y_columns,
        chart_type, chart_title. Returns None if call fails.
    """
    if not tables:
        logger.info("Chart advisor — no tables provided, skipping")
        return None

    logger.info("Chart advisor — %d tables, query=%r, suggestion=%s", len(tables), user_query[:80], chart_suggestion)
    tables_text = _format_tables_for_prompt(tables)

    user_prompt = f"User query: {user_query}\n\n"
    if chart_suggestion and chart_suggestion != "table_only":
        user_prompt += f"Suggested chart type: {chart_suggestion}\n\n"
    user_prompt += f"Tables found in the response:\n\n{tables_text}"

    try:
        response = await anthropic_client.messages.create(
            model=settings.CLAUDE_CLASSIFIER_MODEL,
            max_tokens=256,
            system=CHART_ADVISOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        advice = json.loads(text)

        # Validate required fields
        required = {"table_index", "x_column", "y_columns", "chart_type"}
        if not required.issubset(advice.keys()):
            logger.warning(
                "Chart advisor response missing required fields: %s",
                required - advice.keys(),
            )
            return None

        # Validate table_index
        if not 0 <= advice["table_index"] < len(tables):
            logger.warning(
                "Chart advisor returned invalid table_index: %d (have %d tables)",
                advice["table_index"],
                len(tables),
            )
            advice["table_index"] = 0

        # Ensure lists
        if isinstance(advice.get("y_columns"), str):
            advice["y_columns"] = [advice["y_columns"]]
        if "secondary_y_columns" not in advice:
            advice["secondary_y_columns"] = []
        if isinstance(advice.get("secondary_y_columns"), str):
            advice["secondary_y_columns"] = [advice["secondary_y_columns"]]

        # Validate chart_type
        valid_types = {"bar", "grouped_bar", "line", "pie", "composed", "table_only"}
        if advice["chart_type"] not in valid_types:
            advice["chart_type"] = "bar"

        logger.info(
            "Chart advisor: table=%d, x=%s, y=%s, secondary=%s, type=%s",
            advice["table_index"],
            advice["x_column"],
            advice["y_columns"],
            advice.get("secondary_y_columns", []),
            advice["chart_type"],
        )

        return advice

    except (json.JSONDecodeError, anthropic.APIError, KeyError, IndexError) as exc:
        logger.warning("Chart advisor failed: %s", exc)
        return None
