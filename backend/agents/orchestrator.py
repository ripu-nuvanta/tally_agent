"""Orchestrator — classifies user queries and routes to the appropriate agent.

The Orchestrator is the main entry point for the agent pipeline.  It uses
Claude to classify the user's natural-language query into a structured type
(e.g. simple_lookup, comparison, greeting) and then routes to the QueryAgent
for data fetching.

Exports:
    Orchestrator      — The main orchestrator class.
    anthropic_client  — Module-level AsyncAnthropic instance (patched in tests).
"""

from __future__ import annotations

import json
import re
import logging
from datetime import date
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

from backend.config import settings
from backend.agents.base import BaseAgent
from backend.agents.prompts import build_orchestrator_prompt
from backend.agents.query_agent import QueryAgent
from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.chart_agent import ChartAgent
from backend.agents.context import SessionContext
from backend.agents.chart_advisor import get_chart_advice
from backend.agents.utils import parse_all_markdown_tables
from backend.tally_bridge.client import TallyClient
from backend.utils.date_utils import format_for_tally

# Patterns indicating user wants table-only output (no chart)
_TABLE_INTENT_PATTERNS = (
    "show as a table", "as a table", "in table format",
    "table only", "just a table", "only table", "no chart",
)


def _has_table_intent(user_message: str) -> bool:
    """Return True if the user message explicitly requests table-only output."""
    lower = user_message.lower()
    return any(p in lower for p in _TABLE_INTENT_PATTERNS)

# Module-level client — tests patch this object.
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

GREETING_RESPONSE = (
    "Hello! I'm your TallyPrime assistant. Ask me about your accounting data "
    "— balances, sales, outstanding bills, profit & loss, and more."
)


class Orchestrator(BaseAgent):
    """Classifies user queries and routes to the appropriate agent.

    Flow:
        1. Classify the user's query via Claude.
        2. Route based on classification:
           - greeting -> canned greeting
           - clarification_needed -> return the clarification question
           - anything else -> QueryAgent
    """

    def __init__(self) -> None:
        self.query_agent = QueryAgent()
        self.analysis_agent = AnalysisAgent()
        self.chart_agent = ChartAgent()

    # --- BaseAgent interface implementation (with backward compatibility) ---
    async def process_query(
        self,
        message: str,
        workspace_config: dict[str, Any] | Any | None = None,
        workspace_memory: dict[str, Any] | Any | None = None,
        conversation_messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process a query with support for both signatures.

        Can be called as:
        1. BaseAgent interface: process_query(message, workspace_config, workspace_memory, conversation_messages, **kwargs)
        2. Legacy interface: process_query(user_message, client, session)

        Args:
            message: The user's query text.
            workspace_config: Either a dict (BaseAgent mode) or TallyClient (legacy mode).
            workspace_memory: Either a dict (BaseAgent mode) or SessionContext (legacy mode).
            conversation_messages: List of dicts (BaseAgent mode) or None (legacy mode).
            **kwargs: Additional params.

        Returns:
            Response dict with keys: query_type, message, data, chart, session_id.
        """
        # Detect which signature was used by checking if workspace_config has async methods (TallyClient-like)
        # or if it's a dict (BaseAgent mode)
        if workspace_config is not None and not isinstance(workspace_config, dict) and isinstance(workspace_memory, SessionContext):
            # Legacy mode: process_query(user_message, client, session)
            client = workspace_config
            session = workspace_memory
            return await self._execute_internal(message, client, session)

        # BaseAgent mode: process_query(message, workspace_config, workspace_memory, conversation_messages, **kwargs)
        if not isinstance(workspace_config, dict):
            workspace_config = {}
        if workspace_memory is None:
            workspace_memory = {}
        if conversation_messages is None:
            conversation_messages = []

        # Extract Tally client from kwargs or create one from config
        client = kwargs.get("client")
        if client is None:
            from backend.tally_bridge.client import TallyClient
            host = workspace_config.get("TALLY_HOST", "localhost")
            port = workspace_config.get("TALLY_PORT", 9000)
            client = TallyClient(host=host, port=port)

        # Reconstruct session from conversation_messages or create new one
        session = SessionContext(company=workspace_config.get("company", ""))
        for msg in conversation_messages:
            session.add_message(msg.get("role", "user"), msg.get("content", ""))

        # Delegate to the internal execution method
        return await self._execute_internal(message, client, session)

    async def process_file_upload(
        self,
        file_path: str,
        filename: str,
        mime_type: str,
        user_message: str,
        client,  # TallyClient
        session,  # SessionContext
        file_id: str,
    ) -> dict:
        """Process an uploaded file for data entry.

        Pipeline: parse document → fetch Tally ledgers → map vendor → build voucher
        → return review card data.

        The actual Tally write happens later when the user clicks "Write to Tally"
        (via /chat/voucher-action endpoint).

        Returns a dict with keys: message, data (ChatResponse-compatible).
        """
        import base64
        import uuid as uuid_mod

        from backend.services.document_parser import (
            build_vision_prompt,
            detect_file_type,
            parse_vision_response,
            validate_extracted_amounts,
        )
        from backend.services.ledger_mapper import LedgerMapper
        from backend.services.voucher_builder import build_payment_voucher_data
        from backend.tally_bridge.request_builder import build_list_ledgers
        from backend.tally_bridge.response_parser import parse_ledger_list

        # 1. Parse the document
        file_type = detect_file_type(filename, mime_type)
        if file_type != "vision":
            return {
                "message": (
                    f"File type '{file_type}' not yet supported in B1a. "
                    "Please upload an image or PDF of an expense receipt."
                ),
                "data": None,
            }

        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Map MIME type for Claude Vision
        media_type = mime_type or "image/jpeg"
        if media_type == "image/heic":
            media_type = "image/jpeg"  # Claude doesn't support HEIC directly

        if media_type == "application/pdf":
            # PDF support via document block
            content_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": image_data,
                },
            }
        else:
            content_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            }

        response = await anthropic_client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": build_vision_prompt()},
                ],
            }],
        )
        extracted_text = response.content[0].text
        try:
            extracted = parse_vision_response(extracted_text)
        except Exception as e:
            return {
                "message": f"Could not parse document: {e}. Raw response:\n{extracted_text[:500]}",
                "data": None,
            }

        # 2. Validate amounts (warnings, not blocking)
        warnings = validate_extracted_amounts(extracted)

        # 3. Fetch Tally ledgers for mapping
        ledger_xml = await client.post_xml(build_list_ledgers())
        tally_ledgers = parse_ledger_list(ledger_xml)
        ledger_names = [l["name"] for l in tally_ledgers]

        payment_groups = {"cash-in-hand", "bank accounts", "bank occ a/c"}
        payment_ledgers = [
            l["name"] for l in tally_ledgers
            if l.get("parent_group", "").lower() in payment_groups
        ]
        if not payment_ledgers:
            payment_ledgers = ["Cash"]

        # 4. Map vendor to ledger
        mapper = LedgerMapper()
        # TODO(Task 14+): Load stored mappings from DB (ledger_mappings table) per workspace
        mapping = await mapper.find_mapping(
            extracted.vendor_name or "Expense",
            "Payment",
            tally_ledgers=ledger_names,
        )

        # 5. Build voucher payload
        voucher = build_payment_voucher_data(
            doc=extracted,
            expense_ledger=mapping.ledger_name,
            payment_ledger=payment_ledgers[0],
        )

        # 6. Assemble review card response
        entry_id = str(uuid_mod.uuid4())
        review_data = {
            "type": "voucher_review",
            "file_id": file_id,
            "entries": [{
                "id": entry_id,
                "voucher_type": voucher.voucher_type,
                "date": voucher.date,
                "vendor_name": extracted.vendor_name,
                "amount": float(voucher.amount),
                "debit_ledger": voucher.debit_ledger,
                "credit_ledger": voucher.credit_ledger,
                "narration": voucher.narration,
                "gst_entries": voucher.gst_entries,
                "status": "draft",
                "warnings": warnings,
                "is_new_ledger": mapping.is_new_ledger,
                "suggested_parent": mapping.suggested_parent,
            }],
            "available_ledgers": ledger_names,
            "available_payment_ledgers": payment_ledgers,
        }

        vendor_display = extracted.vendor_name or "Unknown vendor"
        amount_display = f"₹{float(voucher.amount):,.2f}"
        message = (
            f"I've extracted the expense details from your receipt:\n\n"
            f"**{vendor_display}** — {amount_display} on {extracted.date}\n\n"
            f"Please review the entry below and click **Write to Tally** to create "
            f"the payment voucher, or **Edit Entry** to make corrections."
        )
        if warnings:
            message += "\n\n⚠️ " + " | ".join(warnings)

        return {"message": message, "data": review_data}

    async def _execute_internal(
        self,
        user_message: str,
        client: TallyClient,
        session: SessionContext,
    ) -> dict[str, Any]:
        """Internal query execution (called by process_query).

        Returns:
            {
                "query_type": str,
                "message": str,
                "data": dict | None,
                "chart": None,
                "session_id": str,
                "usage": list[dict],
            }
        """
        usage_records: list[dict[str, Any]] = []

        classification = await self._classify(user_message, session)
        query_type = classification.get("query_type", "simple_lookup")
        requires_chart = classification.get("requires_chart", False)

        # Capture classifier usage
        if "usage" in classification:
            usage_records.append(classification["usage"])

        # Respect explicit table-only intent from user message
        if _has_table_intent(user_message):
            requires_chart = False
            logger.info("Orchestrator — user requested table-only, suppressing chart")
        elif not requires_chart and query_type in ("trend", "comparison", "top_n", "aggregation"):
            requires_chart = True
            logger.info("Orchestrator — auto-enabling chart for query_type=%s", query_type)

        logger.info(
            "Orchestrator — classified %r as query_type=%s, requires_chart=%s",
            user_message[:80], query_type, requires_chart,
        )

        # --- Greeting ---
        if query_type == "greeting":
            session.add_message("user", user_message)
            session.add_message("assistant", GREETING_RESPONSE)
            return {
                "query_type": "greeting",
                "message": GREETING_RESPONSE,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
                "usage": usage_records,
            }

        # --- Clarification needed ---
        if query_type == "clarification_needed":
            clarification = classification.get(
                "clarification_question",
                "Could you please provide more details about what you'd like to know?",
            )
            session.add_message("user", user_message)
            session.add_message("assistant", clarification)
            return {
                "query_type": "clarification_needed",
                "message": clarification,
                "data": None,
                "chart": None,
                "session_id": session.session_id,
                "usage": usage_records,
            }

        # --- All other types: route to QueryAgent ---
        logger.info("Orchestrator — routing to QueryAgent")
        agent_result = await self.query_agent.execute(user_message, client, session)
        tool_results = agent_result.get("tool_results", [])
        all_data = _extract_all_data(tool_results)
        raw_data = all_data[-1] if all_data else None
        raw_tally_data, computed_data = _separate_tool_results(tool_results)

        # Capture QueryAgent usage
        if agent_result.get("usage"):
            usage_records.extend(agent_result["usage"])

        logger.info(
            "Orchestrator — QueryAgent returned %d tool call(s), %d data set(s) "
            "(%d raw, %d computed)",
            len(tool_results), len(all_data), len(raw_tally_data), len(computed_data),
        )

        # --- Analysis Agent (unconditional for all non-greeting/non-clarification queries) ---
        # NOTE: Session messages are added AFTER AnalysisAgent runs, not before.
        # QueryAgent no longer touches session — this prevents the AnalysisAgent from
        # seeing the current turn's user query + QueryAgent text as a "prior turn",
        # which caused it to say "same question as prior turn" or reconcile against
        # QueryAgent's incorrect intermediate numbers.
        message = agent_result["message"]
        data = raw_data

        logger.info("Orchestrator — routing to AnalysisAgent (query_type=%s)", query_type)
        analysis_result = await self.analysis_agent.execute(
            raw_tally_data, computed_data, user_message, query_type,
            session=session,
        )
        message = analysis_result["message"]
        data = analysis_result.get("data", raw_data)

        # Capture AnalysisAgent usage
        if analysis_result.get("usage"):
            usage_records.extend(analysis_result["usage"])

        logger.info(
            "Orchestrator — AnalysisAgent returned %d tool call(s), chart_suggestion=%s",
            len(analysis_result.get("tool_results", [])),
            analysis_result.get("chart_suggestion"),
        )

        # Add the final user query + analysis result to session AFTER both agents complete.
        session.add_message("user", user_message)
        session.add_message("assistant", message)

        # --- Chart Agent (when chart is needed) ---
        chart = None
        if settings.CHARTS_ENABLED and requires_chart:
            message_text = analysis_result.get("message", "")
            chart_suggestion = analysis_result.get("chart_suggestion")
            chart_title = analysis_result.get("chart_title")

            if chart_suggestion != "table_only":
                all_tables = parse_all_markdown_tables(message_text)
                logger.info("Chart pipeline — found %d tables, suggestion=%s", len(all_tables), chart_suggestion)

                if all_tables:
                    # Try Haiku chart advisor first
                    advice, advisor_usage = await get_chart_advice(
                        all_tables,
                        user_message,
                        chart_suggestion=chart_suggestion,
                    )
                    if advisor_usage:
                        usage_records.append(advisor_usage)
                    logger.info("Chart advisor returned: %s", advice)

                    if advice and advice.get("chart_type") != "table_only":
                        # Use advisor's table and column selections
                        selected_table = all_tables[advice["table_index"]]

                        # Filter table to only advisor-selected columns
                        filtered = _filter_table_by_advice(selected_table, advice)
                        logger.info(
                            "Chart filter — headers=%s, rows=%d",
                            filtered["headers"] if filtered else None,
                            len(filtered["rows"]) if filtered else 0,
                        )
                        if filtered:
                            chart = self.chart_agent.execute(
                                filtered,
                                query_type,
                                chart_suggestion=advice.get("chart_type", chart_suggestion),
                                chart_title=advice.get("chart_title", chart_title),
                            )

                    if chart is None:
                        logger.info("Chart pipeline — no chart produced (advisor=%s)", "failed" if advice is None else "no suitable columns")
            else:
                logger.info("Chart pipeline — skipped (chart_suggestion=table_only)")

        # Final data from analysis result
        final_data = data

        return {
            "query_type": query_type,
            "message": message,
            "data": final_data,
            "chart": chart,
            "session_id": session.session_id,
            "usage": usage_records,
        }

    async def _classify(self, user_message: str, session: SessionContext | None = None) -> dict:
        """Use Claude to classify the user's query into a structured type.

        Returns a dict with at least ``query_type``.  Falls back to
        ``{"query_type": "simple_lookup", "requires_chart": False}`` when
        the response cannot be parsed as JSON.
        """
        current_date = format_for_tally(date.today())
        system_prompt = build_orchestrator_prompt(current_date)

        # Build messages with conversation context for better classification
        messages: list[dict[str, Any]] = []
        if session and session.messages:
            # Last 4 messages for context
            recent = session.messages[-4:]
            for msg in recent:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        try:
            response = await anthropic_client.messages.create(
                model=settings.CLAUDE_CLASSIFIER_MODEL,
                max_tokens=512,
                system=system_prompt,
                messages=messages,
            )
        except anthropic.APIError:
            return {"query_type": "simple_lookup", "requires_chart": False}

        # Extract text from response
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        logger.info(
            "Orchestrator classifier — input=%d, output=%d tokens",
            response.usage.input_tokens, response.usage.output_tokens,
        )

        classifier_usage = {
            "agent": "classifier",
            "model": settings.CLAUDE_CLASSIFIER_MODEL,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        try:
            result = json.loads(_strip_markdown_fences(text))
            result["usage"] = classifier_usage
            return result
        except (json.JSONDecodeError, TypeError):
            logger.warning("Classification fallback: could not parse Claude response as JSON. Raw text: %s", text)
            return {"query_type": "simple_lookup", "requires_chart": False, "usage": classifier_usage}


def _filter_table_by_advice(table: dict, advice: dict) -> dict | None:
    """Filter table columns to only those selected by the chart advisor.

    Returns a new {headers, rows} dict with only the columns named in
    advice["x_column"], advice["y_columns"], and advice["secondary_y_columns"].
    Returns None if the x_column is not found or fewer than 2 columns survive.
    """
    headers = table["headers"]
    rows = table["rows"]

    x_col = advice.get("x_column", "")
    if not x_col or x_col not in headers:
        return None

    # Build ordered list of column indices: x first, then y, then secondary_y
    col_indices: list[int] = []

    col_indices.append(headers.index(x_col))

    for col in advice.get("y_columns", []):
        if col in headers:
            idx = headers.index(col)
            if idx not in col_indices:
                col_indices.append(idx)

    for col in advice.get("secondary_y_columns", []):
        if col in headers:
            idx = headers.index(col)
            if idx not in col_indices:
                col_indices.append(idx)

    if len(col_indices) < 2:  # Need at least x + 1 y column
        return None

    new_headers = [headers[i] for i in col_indices]
    new_rows = []
    for row in rows:
        new_row = [row[i] if i < len(row) else "" for i in col_indices]
        new_rows.append(new_row)

    return {"headers": new_headers, "rows": new_rows}


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from text."""
    stripped = text.strip()
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


# Tool names from ANALYSIS_TOOLS (pre-computed by QueryAgent)
_COMPUTED_TOOL_NAMES = {
    "compute_totals", "compute_trend", "compute_period_comparison",
    "compute_percentage_change", "sort_by_field",
    "code_execution",
}


def _separate_tool_results(
    tool_results: list[dict],
) -> tuple[list, list]:
    """Separate tool results into raw Tally data and pre-computed analysis.

    Returns:
        (raw_data_list, computed_data_list) — each entry is the tool's data payload.
        ReportResponse-style dicts (headers/rows) in raw data are converted to list[dict].
        Computed data is kept as-is (may be headers/rows or list[dict]).
    """
    raw: list = []
    computed: list = []

    for tr in tool_results:
        result = tr.get("result", {})
        if result.get("success") is not True or result.get("data") is None:
            continue

        tool_name = tr.get("tool_name", "")
        if not tool_name:
            logger.warning("Tool result missing tool_name key — treating as raw data: %s", tr)
        data = result["data"]

        if tool_name in _COMPUTED_TOOL_NAMES:
            computed.append(data)
        else:
            # Convert ReportResponse-style dicts to list[dict] for raw data
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                data = [dict(zip(data["headers"], row)) for row in data["rows"]]
            raw.append(data)

    return raw, computed


def _extract_all_data(tool_results: list[dict]) -> list[dict]:
    """Extract all successful tool result data entries.

    Returns a list of data dicts from tool results where ``success=True``
    and ``data`` is present.  This enables comparison queries that need
    multiple datasets (e.g. Q1 vs Q2 fetched via separate tool calls).

    ReportResponse-style dicts (with ``headers`` and ``rows`` keys) are
    automatically converted to ``list[dict]`` for uniform downstream handling.
    """
    data_list = []
    for tr in tool_results:
        result = tr.get("result", {})
        if result.get("success") is True and result.get("data") is not None:
            data = result["data"]

            # Handle ReportResponse-style dicts (headers/rows)
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                rows_as_dicts = []
                for row in data["rows"]:
                    # zip truncates to shortest; safe because headers define the schema
                    rows_as_dicts.append(dict(zip(data["headers"], row)))
                data = rows_as_dicts

            data_list.append(data)
    return data_list
