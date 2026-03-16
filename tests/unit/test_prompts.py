"""Unit tests for backend.agents.prompts — system prompt builders."""

import pytest

from backend.agents.prompts import (
    build_analysis_agent_prompt,
    build_orchestrator_prompt,
    build_query_agent_prompt,
)
from backend.agents.tools import TALLY_TOOLS


# ---------------------------------------------------------------------------
# TestOrchestratorPrompt
# ---------------------------------------------------------------------------


class TestOrchestratorPrompt:
    """Tests for build_orchestrator_prompt()."""

    def test_contains_current_date(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        assert "04-03-2026" in prompt

    def test_contains_query_types(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        for qt in [
            "simple_lookup",
            "comparison",
            "trend",
            "top_n",
            "aggregation",
            "greeting",
            "clarification_needed",
        ]:
            assert qt in prompt, f"Missing query type: {qt}"

    def test_contains_fy_rules(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        assert "April 1" in prompt
        assert "March 31" in prompt

    def test_contains_quarter_definitions(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        assert "Q1" in prompt
        assert "Apr" in prompt
        assert "Q4" in prompt
        assert "Jan" in prompt and "Mar" in prompt

    def test_contains_json_output_instruction(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        assert "query_type" in prompt
        assert "requires_chart" in prompt
        assert "reasoning" in prompt
        assert "clarification_question" in prompt

    def test_json_only_rule(self):
        prompt = build_orchestrator_prompt("04-03-2026")
        assert "JSON" in prompt

    def test_different_date_injected(self):
        prompt = build_orchestrator_prompt("15-06-2025")
        assert "15-06-2025" in prompt


# ---------------------------------------------------------------------------
# TestQueryAgentPrompt
# ---------------------------------------------------------------------------


class TestQueryAgentPrompt:
    """Tests for build_query_agent_prompt()."""

    def test_contains_tool_names(self):
        prompt = build_query_agent_prompt("06-03-2026")
        for tool in TALLY_TOOLS:
            assert tool["name"] in prompt, f"Missing tool name: {tool['name']}"

    def test_contains_date_format_instruction(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "DD-MM-YYYY" in prompt

    def test_contains_search_ledger_first_instruction(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "search_ledger" in prompt

    def test_contains_rupee_formatting_instruction(self):
        prompt = build_query_agent_prompt("06-03-2026")
        # Should mention Indian Rupee or ₹ formatting
        assert "₹" in prompt or "Indian" in prompt or "Rupee" in prompt

    def test_contains_sign_convention(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "negative" in prompt.lower() or "debit" in prompt.lower()
        assert "positive" in prompt.lower() or "credit" in prompt.lower()

    def test_returns_string(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be a substantial prompt

    def test_includes_current_date(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "06-03-2026" in prompt

    def test_includes_resolve_date_range_instruction(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "resolve_date_range" in prompt

    def test_includes_date_resolution_rule(self):
        prompt = build_query_agent_prompt("06-03-2026")
        assert "Date resolution" in prompt

    def test_different_date_injected(self):
        prompt = build_query_agent_prompt("15-06-2025")
        assert "15-06-2025" in prompt
        assert "06-03-2026" not in prompt

    def test_query_prompt_warns_pnl_rejects_partial_periods(self):
        """Rule 11 must warn that get_profit_and_loss rejects partial-period requests."""
        prompt = build_query_agent_prompt("13-03-2026")
        assert "get_profit_and_loss" in prompt
        assert "reject partial-period requests" in prompt.lower()

    def test_query_prompt_lists_valid_voucher_types(self):
        prompt = build_query_agent_prompt("13-03-2026")
        for vtype in ["Sales", "Purchase", "Payment", "Receipt", "Journal", "Contra", "Credit Note", "Debit Note"]:
            assert vtype in prompt

    def test_query_prompt_has_always_fetch_fresh_data_rule(self):
        """Rule 13 must instruct the agent to always fetch fresh data."""
        prompt = build_query_agent_prompt("13-03-2026")
        assert "Always fetch fresh data" in prompt
        assert "never skip tool calls" in prompt.lower()

    def test_query_prompt_has_quarterly_use_day_book_rule(self):
        """Rule 14 must warn that Trial Balance is not date-aware."""
        prompt = build_query_agent_prompt("13-03-2026")
        assert "Trial Balance" in prompt
        assert "NOT date-aware" in prompt
        assert "get_day_book" in prompt

    def test_query_prompt_fresh_data_rule_in_code_exec_mode(self):
        """Rule 13 must appear in code_execution_enabled mode too."""
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "Always fetch fresh data" in prompt

    def test_query_prompt_quarterly_rule_in_code_exec_mode(self):
        """Rule 14 must appear in code_execution_enabled mode too."""
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "Trial Balance" in prompt
        assert "get_day_book" in prompt


# ---------------------------------------------------------------------------
# TestAnalysisAgentPrompt
# ---------------------------------------------------------------------------


class TestAnalysisAgentPrompt:
    """Tests for build_analysis_agent_prompt()."""

    def test_analysis_prompt_contains_gst_rule(self):
        prompt = build_analysis_agent_prompt("comparison")
        assert "GST" in prompt
        assert "base value" in prompt
        assert "invoice value" in prompt

    def test_analysis_prompt_has_exact_ledger_names_rule(self):
        prompt = build_analysis_agent_prompt("comparison")
        assert "exact ledger names" in prompt.lower() or "exact names from the data" in prompt.lower()

    def test_analysis_prompt_has_chart_title_accuracy_rule(self):
        prompt = build_analysis_agent_prompt("comparison")
        assert "chart title" in prompt.lower() and "match" in prompt.lower()

    def test_analysis_prompt_has_tool_computation_rule(self):
        prompt = build_analysis_agent_prompt("comparison")
        assert "never compute" in prompt.lower() or "always use tools" in prompt.lower() or "never manually" in prompt.lower()

    def test_analysis_prompt_has_missing_months_rule(self):
        prompt = build_analysis_agent_prompt("trend")
        assert "no transactions" in prompt.lower() or "data gap" in prompt.lower()

    def test_analysis_prompt_has_complete_pnl_rule(self):
        """Rule 16: comparison queries must include Purchases/COGS, not just OpEx."""
        prompt = build_analysis_agent_prompt("comparison")
        assert "purchases" in prompt.lower() and "cogs" in prompt.lower()
        assert "gross profit" in prompt.lower()
        assert "net profit" in prompt.lower()
        assert "never omit" in prompt.lower()

    def test_analysis_prompt_complete_pnl_rule_present_with_code_exec(self):
        prompt = build_analysis_agent_prompt("comparison", code_execution_enabled=True)
        assert "purchases" in prompt.lower() and "cogs" in prompt.lower()
