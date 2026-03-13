"""Tests for code-execution-aware prompt generation."""


class TestQueryAgentPromptCodeExec:
    def test_code_exec_enabled_data_fetch_only_prompt(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "DATA FETCHING agent only" in prompt
        assert "specialist computation agent" in prompt
        assert "## Code Execution" not in prompt
        assert "code_execution tool for ALL calculations" not in prompt
        assert "STRUCTURED_RESULT:" not in prompt

    def test_code_exec_disabled_keeps_computation_tools(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=False)
        assert "## Computation Tools" in prompt
        assert "compute_totals" in prompt
        assert "STRUCTURED_RESULT:" not in prompt

    def test_code_exec_enabled_updates_rule_5(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "Do NOT compute" in prompt
        assert "specialist computation agent will handle" in prompt

    def test_code_exec_enabled_updates_rule_11(self):
        from backend.agents.prompts import build_query_agent_prompt
        prompt = build_query_agent_prompt("13-03-2026", code_execution_enabled=True)
        assert "code_execution to aggregate" not in prompt
        assert "compute_totals with group_by" not in prompt


class TestAnalysisAgentPromptCodeExec:
    def test_code_exec_enabled_replaces_available_tools(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        prompt = build_analysis_agent_prompt("top_n", code_execution_enabled=True)
        assert "## Code Execution" in prompt
        assert "## Available Tools" not in prompt
        assert "sort_by_field" not in prompt
        assert "STRUCTURED_RESULT:" in prompt

    def test_code_exec_disabled_keeps_analysis_tools(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        prompt = build_analysis_agent_prompt("top_n", code_execution_enabled=False)
        assert "## Available Tools" in prompt
        assert "sort_by_field" in prompt

    def test_code_exec_enabled_updates_type_guidance(self):
        from backend.agents.prompts import build_analysis_agent_prompt
        for qt in ("comparison", "trend", "top_n", "aggregation"):
            prompt = build_analysis_agent_prompt(qt, code_execution_enabled=True)
            assert "code_execution" in prompt.lower() or "python" in prompt.lower(), f"Failed for {qt}"
