"""Analysis Agent — runs Python computation tools in a Claude tool-calling loop.

Takes raw data from the QueryAgent, lets Claude decide which analysis operations
to apply (sort, aggregate, compare, trend), executes them in Python, and returns
a structured result with summary, table data, insights, and chart suggestion.

Exports:
    AnalysisAgent         — The main agent class.
    anthropic_client      — Module-level AsyncAnthropic instance (patched in tests).
    ANALYSIS_TOOLS        — Claude tool schema list for computation tools.
    execute_analysis_tool — Single entry point for tool execution.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.agents.prompts import build_analysis_agent_prompt
from backend.agents.utils import (
    extract_text,
    find_all_tool_use_blocks,
    find_custom_tool_use_blocks,
    extract_code_execution_results,
    extract_structured_from_code_execution,
)

# Module-level client — tests patch this object.
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MAX_TOOL_CALLS = 15


# ---------------------------------------------------------------------------
# Tool Schemas (Claude tool-calling format)
# ---------------------------------------------------------------------------

ANALYSIS_TOOLS: list[dict[str, Any]] = [
    {
        "name": "sort_by_field",
        "description": (
            "Sort a list of records by a numeric or string field. "
            "Use limit and direction to get top-N or bottom-N rankings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "records": {
                    "type": "array",
                    "description": "List of dicts to sort",
                    "items": {"type": "object"},
                },
                "field": {
                    "type": "string",
                    "description": "The dict key to sort by",
                },
                "descending": {
                    "type": "boolean",
                    "description": "True for highest-first, False for lowest-first. Default: True.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Return only the top N records after sorting. 0 = return all.",
                },
                "label_field": {
                    "type": "string",
                    "description": "The dict key to use as the row label in the result table.",
                },
            },
            "required": ["records", "field"],
        },
    },
    {
        "name": "compute_totals",
        "description": (
            "Sum one or more numeric fields across a list of records. "
            "Optionally group records by a string field first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "records": {
                    "type": "array",
                    "description": "List of dicts",
                    "items": {"type": "object"},
                },
                "numeric_fields": {
                    "type": "array",
                    "description": "Names of the numeric fields to sum",
                    "items": {"type": "string"},
                },
                "group_by": {
                    "type": "string",
                    "description": "Optional field name to group records by before summing",
                },
            },
            "required": ["records", "numeric_fields"],
        },
    },
    {
        "name": "compute_percentage_change",
        "description": (
            "Compute absolute change and percentage change between an old value "
            "and a new value. Handles zero base gracefully."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "old_value": {"type": "number", "description": "The baseline / earlier period value"},
                "new_value": {"type": "number", "description": "The current / later period value"},
                "label": {"type": "string", "description": "Human-readable label for this comparison"},
            },
            "required": ["old_value", "new_value"],
        },
    },
    {
        "name": "compute_period_comparison",
        "description": (
            "Compare two datasets (each a list of {label, value} dicts) side by side. "
            "Aligns rows by label and computes absolute and percentage change per row."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_a": {
                    "type": "array",
                    "description": "List of {label: str, value: number} for the base period",
                    "items": {"type": "object"},
                },
                "period_b": {
                    "type": "array",
                    "description": "List of {label: str, value: number} for the comparison period",
                    "items": {"type": "object"},
                },
                "period_a_name": {"type": "string", "description": "e.g. 'Q1 FY25'"},
                "period_b_name": {"type": "string", "description": "e.g. 'Q2 FY25'"},
                "label_key": {
                    "type": "string",
                    "description": "The key in each dict that holds the row label. Default: 'label'.",
                },
                "value_key": {
                    "type": "string",
                    "description": "The key in each dict that holds the numeric value. Default: 'value'.",
                },
            },
            "required": ["period_a", "period_b", "period_a_name", "period_b_name"],
        },
    },
    {
        "name": "compute_trend",
        "description": (
            "Calculate period-over-period absolute and percentage changes for a time series. "
            "Input is an ordered list of {period, value} records."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "series": {
                    "type": "array",
                    "description": "Ordered list of {period: str, value: number} dicts",
                    "items": {"type": "object"},
                },
                "period_key": {
                    "type": "string",
                    "description": "Key for the period label. Default: 'period'.",
                },
                "value_key": {
                    "type": "string",
                    "description": "Key for the numeric value. Default: 'value'.",
                },
                "value_label": {
                    "type": "string",
                    "description": "Human-readable name for the value column (e.g. 'Revenue')",
                },
            },
            "required": ["series"],
        },
    },
]


CODE_EXECUTION_TOOL = {"type": "code_execution_20260120", "name": "code_execution"}


def _build_analysis_tools(code_execution_enabled: bool) -> list:
    """Build tool list based on code execution config."""
    if code_execution_enabled:
        return [CODE_EXECUTION_TOOL]
    return ANALYSIS_TOOLS


# ---------------------------------------------------------------------------
# Pure Python computation functions
# ---------------------------------------------------------------------------


def _tool_sort_by_field(
    records: list[dict],
    field: str,
    descending: bool = True,
    limit: int = 0,
    label_field: str | None = None,
) -> dict:
    sorted_records = sorted(
        records,
        key=lambda r: (r.get(field) or 0),
        reverse=descending,
    )
    if limit and limit > 0:
        sorted_records = sorted_records[:limit]

    lf = label_field or field
    if lf != field:
        headers = [lf, field]
        rows = [[r.get(lf, ""), r.get(field, 0)] for r in sorted_records]
    else:
        headers = [field]
        rows = [[r.get(field, 0)] for r in sorted_records]

    return {"records": sorted_records, "headers": headers, "rows": rows}


def _tool_compute_totals(
    records: list[dict],
    numeric_fields: list[str],
    group_by: str | None = None,
) -> dict:
    # Coerce non-dict records to dicts
    coerced = []
    for r in records:
        if isinstance(r, dict):
            coerced.append(r)
        elif isinstance(r, (int, float)):
            coerced.append({"value": r})
        elif isinstance(r, str):
            try:
                coerced.append({"value": float(r.replace(",", "").replace("₹", ""))})
            except ValueError:
                coerced.append({"label": r})
        else:
            coerced.append({"value": str(r)})
    records = coerced

    if group_by:
        groups: dict[str, dict[str, float]] = {}
        for rec in records:
            key = str(rec.get(group_by, ""))
            if key not in groups:
                groups[key] = {f: 0.0 for f in numeric_fields}
            for f in numeric_fields:
                groups[key][f] += float(rec.get(f) or 0)
        result_records = [{group_by: k, **v} for k, v in groups.items()]
    else:
        totals = {f: sum(float(r.get(f) or 0) for r in records) for f in numeric_fields}
        result_records = [totals]

    headers = ([group_by] if group_by else []) + numeric_fields
    rows = [[r.get(h, 0) for h in headers] for r in result_records]
    return {"records": result_records, "headers": headers, "rows": rows}


def _tool_compute_percentage_change(
    old_value: float,
    new_value: float,
    label: str = "",
) -> dict:
    absolute_change = new_value - old_value
    if old_value == 0:
        pct_change = None
        pct_str = "N/A (base is zero)"
    else:
        pct_change = (absolute_change / abs(old_value)) * 100
        pct_str = f"{pct_change:+.1f}%"

    return {
        "label": label,
        "old_value": old_value,
        "new_value": new_value,
        "absolute_change": absolute_change,
        "percentage_change": pct_change,
        "percentage_change_str": pct_str,
        "direction": "increase" if absolute_change > 0 else ("decrease" if absolute_change < 0 else "no change"),
    }


def _tool_compute_period_comparison(
    period_a: list[dict],
    period_b: list[dict],
    period_a_name: str,
    period_b_name: str,
    label_key: str = "label",
    value_key: str = "value",
) -> dict:
    map_a = {str(r.get(label_key, "")): float(r.get(value_key) or 0) for r in period_a}
    map_b = {str(r.get(label_key, "")): float(r.get(value_key) or 0) for r in period_b}
    all_labels = list(dict.fromkeys(list(map_a.keys()) + list(map_b.keys())))

    rows = []
    records = []
    for lbl in all_labels:
        a_val = map_a.get(lbl, 0.0)
        b_val = map_b.get(lbl, 0.0)
        abs_change = b_val - a_val
        pct = ((abs_change / abs(a_val)) * 100) if a_val != 0 else None
        pct_str = f"{pct:+.1f}%" if pct is not None else "N/A"
        rows.append([lbl, a_val, b_val, abs_change, pct_str])
        records.append({
            "label": lbl,
            period_a_name: a_val,
            period_b_name: b_val,
            "change": abs_change,
            "change_pct": pct_str,
        })

    headers = ["Item", period_a_name, period_b_name, "Change", "Change %"]
    return {"records": records, "headers": headers, "rows": rows}


def _tool_compute_trend(
    series: list[dict],
    period_key: str = "period",
    value_key: str = "value",
    value_label: str = "Value",
) -> dict:
    rows = []
    records = []
    for i, point in enumerate(series):
        period = point.get(period_key, f"Period {i + 1}")
        value = float(point.get(value_key) or 0)
        if i == 0:
            abs_chg = None
            pct_chg = None
            abs_str = "—"
            pct_str = "—"
        else:
            prev = float(series[i - 1].get(value_key) or 0)
            abs_chg = value - prev
            if prev == 0 or value == 0:
                pct_chg = None
            else:
                pct_chg = ((abs_chg / abs(prev)) * 100)
            abs_str = f"{abs_chg:+,.2f}"
            pct_str = f"{pct_chg:+.1f}%" if pct_chg is not None else "N/A"
        rows.append([period, value, abs_str, pct_str])
        records.append({
            period_key: period,
            value_key: value,
            "abs_change": abs_chg,
            "pct_change": pct_chg,
        })

    headers = ["Period", value_label, "Change", "Change %"]
    return {"records": records, "headers": headers, "rows": rows}


# ---------------------------------------------------------------------------
# Tool handler registry + executor
# ---------------------------------------------------------------------------

_ANALYSIS_HANDLERS: dict[str, Any] = {
    "sort_by_field": _tool_sort_by_field,
    "compute_totals": _tool_compute_totals,
    "compute_percentage_change": _tool_compute_percentage_change,
    "compute_period_comparison": _tool_compute_period_comparison,
    "compute_trend": _tool_compute_trend,
}


def execute_analysis_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a named analysis tool synchronously.

    Returns {"success": True, "data": ...} or {"error": str}.
    """
    handler = _ANALYSIS_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown analysis tool: {tool_name!r}"}
    try:
        result = handler(**tool_input)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.exception("Error in analysis tool %r", tool_name)
        return {"error": f"Error in {tool_name!r}: {exc}"}


# ---------------------------------------------------------------------------
# AnalysisAgent
# ---------------------------------------------------------------------------


class AnalysisAgent:
    """Post-processes fetched Tally data using Python computation tools via Claude.

    Claude decides which analysis operations to apply to the raw data.
    The tools execute deterministic Python computation (no I/O).
    """

    def __init__(self, max_tool_calls: int = MAX_TOOL_CALLS) -> None:
        self.max_tool_calls = max_tool_calls

    async def execute(
        self,
        raw_data: list | dict,
        computed_data: list | None,
        user_query: str,
        query_type: str,
        session: Any | None = None,
    ) -> dict[str, Any]:
        """Run the analysis loop.

        Args:
            raw_data: Raw Tally API responses (vouchers, reports).
            computed_data: Pre-computed results from QueryAgent (totals, trends,
                comparisons). Can be used as-is or enhanced. May be None or empty.
            user_query: Original user question.
            query_type: Classification (comparison, trend, top_n, aggregation).
            session: Optional SessionContext with prior conversation messages.
                When provided, recent messages are prepended to the prompt so the
                model can reference prior-turn data. Defaults to None.

        Returns:
            {
                "message": str,
                "data": {"headers": list[str], "rows": list[list]},
                "insights": list[str],
                "chart_suggestion": str,
                "tool_results": list[dict],
            }
        """
        system_prompt = build_analysis_agent_prompt(query_type, code_execution_enabled=settings.CODE_EXECUTION_ENABLED)

        parts = [
            f"User query: {user_query}\n\n"
            f"Query type: {query_type}\n\n"
        ]

        if computed_data:
            parts.append(
                "## Pre-computed analysis (from data retrieval phase)\n"
                "The following results were already computed. You may use these directly, "
                "enhance them with additional analysis, or re-compute from raw data if needed.\n\n"
                f"{json.dumps(computed_data, default=str)}\n\n"
            )

        parts.append(
            "## Raw Tally data\n"
            "Original data fetched from Tally. Use this for additional analysis "
            "beyond what was pre-computed above.\n\n"
            f"{json.dumps(raw_data, default=str)}"
        )

        # Inject prior conversation context if session provided
        if session and session.messages:
            n = settings.ANALYSIS_CONTEXT_MESSAGES
            recent = session.messages[-n:]
            ctx_lines = []
            for msg in recent:
                role = msg["role"].capitalize()
                content = msg["content"][:1500]
                ctx_lines.append(f"{role}: {content}")
            context_str = "\n\n".join(ctx_lines)
            parts.insert(0,
                "## Prior Conversation Context\n"
                "These are recent messages from the conversation. If the user's current query "
                "can be answered using data from a prior turn, reference that data.\n\n"
                f"{context_str}\n\n"
            )

        user_content = "".join(parts)
        messages: list[dict] = [{"role": "user", "content": user_content}]
        tool_results_log: list[dict] = []
        tool_call_count = 0
        last_table_data: dict = {"headers": [], "rows": []}
        ranked_table_data: dict | None = None  # Prefer sort_by_field for top_n
        trend_table_data: dict | None = None   # Prefer compute_trend for trend
        comparison_table_data: dict | None = None  # Prefer compute_period_comparison for comparison
        turn = 0

        logger.info("AnalysisAgent start — query_type=%s, query=%r", query_type, user_query[:80])

        while True:
            turn += 1
            try:
                response = await anthropic_client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=21000,  # SDK limit: ~21333 for non-streaming (streaming needed for higher)
                    system=system_prompt,
                    tools=_build_analysis_tools(settings.CODE_EXECUTION_ENABLED),
                    messages=messages,
                )
            except anthropic.APIError as exc:
                logger.error("AnalysisAgent turn %d — API error: %s", turn, exc)
                preferred_data = (
                    trend_table_data if (query_type == "trend" and trend_table_data)
                    else comparison_table_data if (query_type == "comparison" and comparison_table_data)
                    else ranked_table_data if (query_type == "top_n" and ranked_table_data)
                    else last_table_data
                )
                if preferred_data and preferred_data.get("headers") and preferred_data.get("rows"):
                    preferred_data["rows"] = _ensure_totals_row(preferred_data["headers"], preferred_data["rows"], query_type)
                return _build_result(
                    f"Analysis could not be completed: {exc}",
                    preferred_data,
                    tool_results_log,
                )

            logger.info(
                "AnalysisAgent turn %d — stop_reason=%s, input=%d, output=%d tokens",
                turn, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            # Log Claude's text content for this turn
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    logger.debug("AnalysisAgent turn %d — Claude text:\n%s", turn, block.text)

            if settings.CODE_EXECUTION_ENABLED:
                code_blocks = extract_code_execution_results(response)
                for cer in code_blocks:
                    if cer["type"] == "code_written":
                        logger.info("AnalysisAgent turn %d — code_execution code:\n%s", turn, cer["code"])
                    elif cer["type"] == "code_result":
                        logger.info("AnalysisAgent turn %d — code_execution stdout:\n%s", turn, cer["stdout"])
                        if cer.get("stderr"):
                            logger.warning("AnalysisAgent turn %d — code_execution stderr:\n%s", turn, cer["stderr"])
                if code_blocks:
                    logger.info("AnalysisAgent — code_execution USED (%d block(s))", len(code_blocks))
                else:
                    logger.warning("AnalysisAgent — code_execution NOT USED (model skipped sandbox)")

            # Capture structured output from code execution
            if settings.CODE_EXECUTION_ENABLED:
                structured = extract_structured_from_code_execution(response)
                if structured and "headers" in structured and "rows" in structured:
                    last_table_data = {"headers": structured["headers"], "rows": structured["rows"]}
                    if query_type == "top_n":
                        ranked_table_data = last_table_data
                    elif query_type == "trend":
                        trend_table_data = last_table_data
                    elif query_type == "comparison":
                        comparison_table_data = last_table_data
                    logger.info(
                        "AnalysisAgent — STRUCTURED_RESULT captured: %d headers, %d rows",
                        len(structured["headers"]), len(structured["rows"]),
                    )
                elif response.stop_reason != "tool_use":
                    logger.warning("AnalysisAgent — no STRUCTURED_RESULT captured")

            # ---- End turn: Claude produced a final text answer ----
            if response.stop_reason != "tool_use":
                final_text = extract_text(response)
                logger.info("AnalysisAgent turn %d — final answer (%d chars)", turn, len(final_text))
                logger.debug("AnalysisAgent turn %d — FINAL ANSWER:\n%s", turn, final_text)

                # Fallback: parse STRUCTURED_RESULT from text if code_execution stdout missed it
                if settings.CODE_EXECUTION_ENABLED and not (last_table_data and last_table_data.get("headers")):
                    text_structured = _extract_structured_from_text(final_text)
                    if text_structured:
                        last_table_data = text_structured
                        if query_type == "top_n":
                            ranked_table_data = last_table_data
                        elif query_type == "trend":
                            trend_table_data = last_table_data
                        elif query_type == "comparison":
                            comparison_table_data = last_table_data
                        logger.info("AnalysisAgent turn %d — captured STRUCTURED_RESULT from text fallback", turn)

                # Fallback: parse markdown tables from text when no structured data found
                if not (last_table_data and last_table_data.get("headers")):
                    md_table = _parse_markdown_table(final_text)
                    if md_table:
                        last_table_data = md_table
                        if query_type == "top_n":
                            ranked_table_data = last_table_data
                        elif query_type == "trend":
                            trend_table_data = last_table_data
                        elif query_type == "comparison":
                            comparison_table_data = last_table_data
                        logger.info(
                            "AnalysisAgent — parsed markdown table fallback: %d headers, %d rows",
                            len(md_table["headers"]), len(md_table["rows"]),
                        )

                # For top_n, prefer the ranked (sort_by_field) data over aggregate totals
                preferred_data = (
                    trend_table_data if (query_type == "trend" and trend_table_data)
                    else comparison_table_data if (query_type == "comparison" and comparison_table_data)
                    else ranked_table_data if (query_type == "top_n" and ranked_table_data)
                    else last_table_data
                )
                if preferred_data and preferred_data.get("headers") and preferred_data.get("rows"):
                    preferred_data["rows"] = _ensure_totals_row(preferred_data["headers"], preferred_data["rows"], query_type)
                return _build_result(final_text, preferred_data, tool_results_log)

            # ---- Tool use: execute all requested analysis tools ----
            if settings.CODE_EXECUTION_ENABLED:
                tool_blocks = find_custom_tool_use_blocks(response)
            else:
                tool_blocks = find_all_tool_use_blocks(response)
            logger.info("AnalysisAgent turn %d — %d tool call(s)", turn, len(tool_blocks))

            tool_result_entries = []
            for tool_block in tool_blocks:
                logger.info(
                    "AnalysisAgent turn %d — calling %r with input:\n%s",
                    turn, tool_block.name, json.dumps(tool_block.input, default=str, indent=2),
                )
                result = execute_analysis_tool(tool_block.name, tool_block.input)

                logger.debug(
                    "AnalysisAgent turn %d — tool %r full result:\n%s",
                    turn, tool_block.name, json.dumps(result, default=str, indent=2),
                )

                # Capture the most recent successful table output
                if result.get("success") and isinstance(result.get("data"), dict):
                    d = result["data"]
                    if "headers" in d and "rows" in d:
                        last_table_data = {"headers": d["headers"], "rows": d["rows"]}
                        # For top_n, prefer sort_by_field (individual records) over
                        # compute_totals (aggregate). Track it separately.
                        if tool_block.name == "sort_by_field":
                            ranked_table_data = {"headers": d["headers"], "rows": d["rows"]}
                        if tool_block.name == "compute_trend":
                            trend_table_data = {"headers": d["headers"], "rows": d["rows"]}
                        if tool_block.name == "compute_period_comparison":
                            comparison_table_data = {"headers": d["headers"], "rows": d["rows"]}

                tool_results_log.append({
                    "tool_name": tool_block.name,
                    "tool_input": tool_block.input,
                    "result": result,
                })

                tool_result_entries.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": json.dumps(result),
                })

            tool_call_count += len(tool_blocks)

            messages.append({"role": "assistant", "content": response.content})
            if tool_result_entries:
                messages.append({"role": "user", "content": tool_result_entries})

            if tool_call_count >= self.max_tool_calls:
                preferred_data = (
                    trend_table_data if (query_type == "trend" and trend_table_data)
                    else comparison_table_data if (query_type == "comparison" and comparison_table_data)
                    else ranked_table_data if (query_type == "top_n" and ranked_table_data)
                    else last_table_data
                )
                if preferred_data and preferred_data.get("headers") and preferred_data.get("rows"):
                    preferred_data["rows"] = _ensure_totals_row(preferred_data["headers"], preferred_data["rows"], query_type)
                return _build_result(
                    f"Reached analysis tool limit ({self.max_tool_calls}). "
                    "Here is the analysis based on what was computed.",
                    preferred_data,
                    tool_results_log,
                )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_totals_row(headers: list[str], rows: list[list], query_type: str) -> list[list]:
    """Add a totals row if missing for comparison/top_n/aggregation queries."""
    if not rows or query_type not in ("comparison", "top_n", "aggregation", "trend"):
        return rows
    last_label = str(rows[-1][0]).lower() if rows else ""
    if "total" in last_label or "grand" in last_label:
        return rows
    totals: list[Any] = ["Total"]
    for col_idx in range(1, len(headers)):
        # Skip percentage columns — summing percentages is meaningless
        if "%" in headers[col_idx]:
            totals.append("")
            continue
        col_vals: list[float] = []
        for row in rows:
            if col_idx < len(row):
                val = row[col_idx]
                if isinstance(val, (int, float)):
                    col_vals.append(float(val))
                elif isinstance(val, str):
                    cleaned = val.replace("₹", "").replace(",", "").replace("%", "").strip()
                    try:
                        col_vals.append(float(cleaned))
                    except ValueError:
                        pass
        if col_vals:
            totals.append(sum(col_vals))
        else:
            totals.append("")
    return rows + [totals]


def _extract_structured_from_text(text: str) -> dict | None:
    """Fallback: extract STRUCTURED_RESULT from text when code_execution stdout missed it."""
    from backend.agents.utils import STRUCTURED_RESULT_PREFIX
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(STRUCTURED_RESULT_PREFIX):
            try:
                data = json.loads(stripped[len(STRUCTURED_RESULT_PREFIX):])
                if isinstance(data, dict) and "headers" in data and "rows" in data:
                    return {"headers": data["headers"], "rows": data["rows"]}
            except json.JSONDecodeError:
                pass
    return None


def _parse_markdown_table(text: str) -> dict | None:
    """Parse the last markdown table in text into {headers, rows} format.

    When AnalysisAgent skips code_execution and writes results as markdown
    tables in its text response, this function extracts the structured data
    so ChartAgent can still render charts.

    Returns {"headers": [...], "rows": [...]} or None if no table found.
    """
    lines = text.strip().split("\n")

    # Find all table blocks (consecutive lines starting and ending with |)
    table_blocks: list[list[str]] = []
    current_block: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current_block.append(stripped)
        else:
            if current_block:
                table_blocks.append(current_block)
                current_block = []
    if current_block:
        table_blocks.append(current_block)

    if not table_blocks:
        return None

    # Use the last table block (most likely the final result)
    block = table_blocks[-1]
    if len(block) < 3:  # Need header + separator + at least 1 data row
        return None

    # Parse header (first row)
    header_line = block[0]
    headers = [cell.strip().replace("*", "") for cell in header_line.split("|")[1:-1]]

    # Verify separator (second row) — should look like |---|---|
    separator = block[1]
    if not re.match(r"^[\s|:\-]+$", separator):
        return None

    # Parse data rows
    rows: list[list[str]] = []
    for row_line in block[2:]:
        cells = [cell.strip().replace("*", "") for cell in row_line.split("|")[1:-1]]
        # Pad or trim to match header count
        while len(cells) < len(headers):
            cells.append("")
        cells = cells[: len(headers)]
        rows.append(cells)

    if not headers or not rows:
        return None

    return {"headers": headers, "rows": rows}


def _strip_chart_metadata(text: str) -> str:
    """Remove Chart suggestion/Chart title/STRUCTURED_RESULT lines from message text."""
    text = re.sub(r'\n*\**\s*(?:chart[_\s]suggestion|suggested chart)\s*:\s*.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n*\**\s*chart[_\s]title\s*:\s*.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n*STRUCTURED_RESULT:\{.*\}', '', text)
    return text.strip()


def _build_result(
    message: str,
    table_data: dict,
    tool_results: list[dict],
) -> dict[str, Any]:
    """Build the standard AnalysisAgent result dict."""
    insights = _extract_insights(message)
    chart_suggestion = _extract_chart_suggestion(message)
    chart_title = _extract_chart_title(message)
    message = _strip_chart_metadata(message)
    result: dict[str, Any] = {
        "message": message,
        "data": table_data,
        "insights": insights,
        "chart_suggestion": chart_suggestion,
        "tool_results": tool_results,
    }
    if chart_title:
        result["chart_title"] = chart_title
    return result


def _extract_insights(text: str) -> list[str]:
    """Extract bullet-pointed insights from Claude's text response."""
    insights = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("- ", "• ", "* ")):
            insights.append(stripped[2:].strip())
    return insights


def _extract_chart_suggestion(text: str) -> str:
    """Look for a chart_suggestion in Claude's text response."""
    valid = {"bar", "grouped_bar", "line", "pie", "table_only", "stacked_bar", "composed"}
    # Strip markdown bold/italic markers before searching
    text_clean = re.sub(r'\*{1,2}', '', text)
    text_lower = text_clean.lower()
    for keyword in ("chart_suggestion:", "chart suggestion:", "suggested chart:"):
        if keyword in text_lower:
            idx = text_lower.index(keyword) + len(keyword)
            snippet = text_lower[idx:idx + 30].strip()
            words = snippet.split()
            # Try two-word match first (e.g. "grouped bar" -> "grouped_bar")
            if len(words) >= 2:
                two_word = (words[0].strip(".,\"'") + "_" + words[1].strip(".,\"'"))
                if two_word in valid:
                    return two_word
            # Fall back to single word
            if words:
                word = words[0].strip(".,\"'")
                if word in valid:
                    return word
    return "table_only"


def _extract_chart_title(text: str) -> str | None:
    """Extract a chart title suggestion from Claude's text response."""
    # Strip markdown bold/italic markers before searching
    text_clean = re.sub(r'\*{1,2}', '', text)
    text_lower = text_clean.lower()
    for keyword in ("chart title:", "chart_title:"):
        if keyword in text_lower:
            idx = text_lower.index(keyword) + len(keyword)
            # Extract the rest of the line
            rest = text_clean[idx:].split("\n")[0].strip()
            if rest:
                title = rest.strip('"\'')
                return title
    return None
