"""Unit tests for backend.agents.prompts — system prompt builders."""

import pytest

from backend.agents.prompts import build_orchestrator_prompt, build_query_agent_prompt
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
