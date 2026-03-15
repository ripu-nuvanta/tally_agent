"""Unit tests for Orchestrator — query classification and routing.

Uses unittest.mock to patch the module-level anthropic_client so no real
API calls are made.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.context import SessionContext
from backend.agents.orchestrator import _strip_markdown_fences


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classification_response(classification: dict):
    """Mock Claude response with JSON classification."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(classification)
    msg.content = [block]
    return msg


# ---------------------------------------------------------------------------
# Tests: Classification and routing
# ---------------------------------------------------------------------------


class TestOrchestratorClassification:
    @pytest.mark.asyncio
    async def test_greeting_returns_direct_response(self):
        """classification.query_type == 'greeting' -> canned response."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()  # TallyClient stub
        session = SessionContext()

        classification = {
            "query_type": "greeting",
            "requires_chart": False,
            "reasoning": "User said hello",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            result = await orch.process_query("Hello!", mock_client, session)

        assert result["query_type"] == "greeting"
        assert "TallyPrime assistant" in result["message"]
        assert result["data"] is None
        assert result["chart"] is None
        assert result["session_id"] == session.session_id

    @pytest.mark.asyncio
    async def test_clarification_needed(self):
        """classification has clarification_question -> returns the question."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "clarification_needed",
            "requires_chart": False,
            "reasoning": "User query is ambiguous",
            "clarification_question": "Which ledger are you referring to?",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            result = await orch.process_query("Show me the balance", mock_client, session)

        assert result["query_type"] == "clarification_needed"
        assert "Which ledger" in result["message"]
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_simple_lookup_routes_to_query_agent(self):
        """simple_lookup classification -> routes to query_agent then analysis_agent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "User wants trial balance",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            # Patch both query_agent and analysis_agent
            with (
                patch.object(
                    orch.query_agent, "execute", new_callable=AsyncMock
                ) as mock_execute,
                patch.object(
                    orch.analysis_agent, "execute", new_callable=AsyncMock
                ) as mock_analysis,
            ):
                mock_execute.return_value = {
                    "message": "The trial balance shows debits of ₹50,00,000.",
                    "tool_results": [
                        {
                            "tool_name": "get_trial_balance",
                            "tool_input": {"from_date": "01-04-2025", "to_date": "31-03-2026"},
                            "result": {
                                "success": True,
                                "data": {"report_name": "Trial Balance", "entries": []},
                            },
                        }
                    ],
                }
                mock_analysis.return_value = {
                    "message": "The trial balance shows debits of ₹50,00,000.",
                    "data": {"report_name": "Trial Balance", "entries": []},
                    "tool_results": [],
                    "chart_suggestion": "table_only",
                }

                result = await orch.process_query(
                    "Show trial balance", mock_client, session
                )

                mock_execute.assert_awaited_once_with(
                    "Show trial balance", mock_client, session
                )
                mock_analysis.assert_awaited_once()

        assert result["query_type"] == "simple_lookup"
        assert result["message"] == "The trial balance shows debits of ₹50,00,000."
        assert result["data"] == {"report_name": "Trial Balance", "entries": []}

    @pytest.mark.asyncio
    async def test_session_messages_updated(self):
        """After greeting, session has 2 messages (user + assistant)."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "greeting",
            "requires_chart": False,
            "reasoning": "User greeted",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            await orch.process_query("Hi there", mock_client, session)

        msgs = session.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hi there"
        assert msgs[1]["role"] == "assistant"
        assert "TallyPrime assistant" in msgs[1]["content"]

    @pytest.mark.asyncio
    async def test_invalid_json_classification_fallback(self):
        """Claude returns non-JSON text -> fallback to simple_lookup -> routes to query_agent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        # Return non-JSON text
        bad_response = MagicMock()
        bad_response.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "I'm not sure how to classify this query."
        bad_response.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=bad_response)

            orch = Orchestrator()

            with patch.object(
                orch.query_agent, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "message": "Here is the data you requested.",
                    "tool_results": [],
                }

                result = await orch.process_query(
                    "Something ambiguous", mock_client, session
                )

                # Should have fallen back to simple_lookup and called query_agent
                mock_execute.assert_awaited_once()

        assert result["query_type"] == "simple_lookup"
        assert result["message"] == "Here is the data you requested."

    @pytest.mark.asyncio
    async def test_classification_with_markdown_fences(self):
        """Claude response wrapped in ```json fences should still parse."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        fenced_json = '```json\n{"query_type": "greeting", "requires_chart": false, "reasoning": "hi", "clarification_question": null}\n```'
        msg = MagicMock()
        msg.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = fenced_json
        msg.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=msg)
            orch = Orchestrator()
            result = await orch.process_query("Hello!", mock_client, session)

        assert result["query_type"] == "greeting"


# ---------------------------------------------------------------------------
# Tests: _strip_markdown_fences
# ---------------------------------------------------------------------------


class TestStripMarkdownFences:
    def test_strips_json_fences(self):
        text = '```json\n{"query_type": "simple_lookup"}\n```'
        assert _strip_markdown_fences(text) == '{"query_type": "simple_lookup"}'

    def test_strips_plain_fences(self):
        text = '```\n{"query_type": "greeting"}\n```'
        assert _strip_markdown_fences(text) == '{"query_type": "greeting"}'

    def test_no_fences_passthrough(self):
        text = '{"query_type": "trend"}'
        assert _strip_markdown_fences(text) == '{"query_type": "trend"}'

    def test_strips_fences_with_extra_whitespace(self):
        text = '  ```json\n  {"query_type": "comparison"}  \n```  '
        result = _strip_markdown_fences(text)
        assert json.loads(result)["query_type"] == "comparison"


# ---------------------------------------------------------------------------
# Tests: Analysis Agent routing
# ---------------------------------------------------------------------------


class TestOrchestratorAnalysisRouting:
    @pytest.mark.asyncio
    async def test_comparison_routes_to_analysis_agent(self):
        """comparison query type -> QueryAgent then AnalysisAgent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "comparison",
            "requires_chart": True,
            "reasoning": "User wants to compare Q1 vs Q2",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "Raw data fetched.",
                    "tool_results": [
                        {
                            "tool_name": "get_sales_register",
                            "tool_input": {},
                            "result": {"success": True, "data": [{"party": "A", "amount": 100}]},
                        }
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Q1 sales were ₹100, Q2 were ₹150 — a 50% increase.",
                    "data": {"headers": ["Period", "Sales"], "rows": [["Q1", 100], ["Q2", 150]]},
                    "insights": ["Sales grew 50%"],
                    "chart_suggestion": "grouped_bar",
                    "tool_results": [],
                }

                result = await orch.process_query("Compare Q1 vs Q2 sales", mock_client, session)

                mock_query.assert_awaited_once()
                mock_analysis.assert_awaited_once_with(
                    [[{"party": "A", "amount": 100}]],
                    [],
                    "Compare Q1 vs Q2 sales",
                    "comparison",
                    session=session,
                )

        assert result["query_type"] == "comparison"
        assert "50%" in result["message"]
        assert result["chart"] is not None
        assert result["chart"]["chart_type"] == "grouped_bar"

    @pytest.mark.asyncio
    async def test_simple_lookup_routes_to_analysis_agent(self):
        """simple_lookup with data -> QueryAgent then AnalysisAgent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "Simple data query",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "Trial balance shows...",
                    "tool_results": [
                        {
                            "tool_name": "get_trial_balance",
                            "tool_input": {},
                            "result": {"success": True, "data": {"entries": []}},
                        }
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Trial balance shows...",
                    "data": {"entries": []},
                    "tool_results": [],
                    "chart_suggestion": "table_only",
                }

                result = await orch.process_query("Show trial balance", mock_client, session)

                mock_query.assert_awaited_once()
                mock_analysis.assert_awaited_once()

        assert result["query_type"] == "simple_lookup"
        assert result["chart"] is None

    @pytest.mark.asyncio
    async def test_chart_generated_when_requires_chart(self):
        """requires_chart=True on simple_lookup -> ChartAgent runs."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": True,
            "reasoning": "Data with chart",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query:
                mock_query.return_value = {
                    "message": "Top expenses.",
                    "tool_results": [
                        {
                            "tool_name": "get_trial_balance",
                            "tool_input": {},
                            "result": {
                                "success": True,
                                "data": {
                                    "headers": ["Account", "Amount"],
                                    "rows": [["Rent", 5000], ["Salary", 8000], ["Travel", 2000]],
                                },
                            },
                        }
                    ],
                }

                result = await orch.process_query("Show expenses chart", mock_client, session)

        # ChartAgent should have run (though it may return None for non-matching shapes)
        assert result["query_type"] == "simple_lookup"

    @pytest.mark.asyncio
    async def test_analysis_skipped_when_no_data(self):
        """If QueryAgent returns no data, AnalysisAgent is skipped."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "top_n",
            "requires_chart": True,
            "reasoning": "Ranking query",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "No data found.",
                    "tool_results": [],
                }

                result = await orch.process_query("Top 5 customers", mock_client, session)

                mock_analysis.assert_not_awaited()

        assert result["data"] is None


# ---------------------------------------------------------------------------
# Tests: _extract_all_data (Fix #5)
# ---------------------------------------------------------------------------


class TestExtractAllData:
    def test_single_successful_result(self):
        from backend.agents.orchestrator import _extract_all_data

        results = [
            {"tool_name": "t1", "tool_input": {}, "result": {"success": True, "data": {"entries": [1]}}},
        ]
        assert _extract_all_data(results) == [{"entries": [1]}]

    def test_multiple_successful_results(self):
        from backend.agents.orchestrator import _extract_all_data

        results = [
            {"tool_name": "t1", "tool_input": {}, "result": {"success": True, "data": {"q1": 100}}},
            {"tool_name": "t2", "tool_input": {}, "result": {"success": True, "data": {"q2": 200}}},
        ]
        data = _extract_all_data(results)
        assert len(data) == 2
        assert data[0] == {"q1": 100}
        assert data[1] == {"q2": 200}

    def test_filters_out_failed_results(self):
        from backend.agents.orchestrator import _extract_all_data

        results = [
            {"tool_name": "t1", "tool_input": {}, "result": {"success": True, "data": {"ok": 1}}},
            {"tool_name": "t2", "tool_input": {}, "result": {"error": "failed"}},
            {"tool_name": "t3", "tool_input": {}, "result": {"success": True, "data": {"ok": 2}}},
        ]
        data = _extract_all_data(results)
        assert len(data) == 2

    def test_empty_results_returns_empty_list(self):
        from backend.agents.orchestrator import _extract_all_data

        assert _extract_all_data([]) == []

    def test_no_successful_results_returns_empty_list(self):
        from backend.agents.orchestrator import _extract_all_data

        results = [{"tool_name": "t1", "tool_input": {}, "result": {"error": "fail"}}]
        assert _extract_all_data(results) == []

    def test_filters_null_data(self):
        from backend.agents.orchestrator import _extract_all_data

        results = [
            {"tool_name": "t1", "tool_input": {}, "result": {"success": True, "data": None}},
        ]
        assert _extract_all_data(results) == []


# ---------------------------------------------------------------------------
# Tests: Orchestrator API error handling (Fix #3)
# ---------------------------------------------------------------------------


class TestOrchestratorAPIError:
    @pytest.mark.asyncio
    async def test_classify_api_error_falls_back_to_simple_lookup(self):
        """When classification API call fails, orchestrator falls back to simple_lookup."""
        import anthropic
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                side_effect=anthropic.APIConnectionError(request=MagicMock())
            )

            orch = Orchestrator()

            with patch.object(
                orch.query_agent, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = {
                    "message": "Here is the data.",
                    "tool_results": [],
                }

                result = await orch.process_query("Show sales", mock_client, session)

                # Should have fallen back to simple_lookup and called query_agent
                mock_execute.assert_awaited_once()

        assert result["query_type"] == "simple_lookup"


# ---------------------------------------------------------------------------
# Tests: Multiple data passed to analysis (Fix #5)
# ---------------------------------------------------------------------------


class TestOrchestratorMultipleData:
    @pytest.mark.asyncio
    async def test_comparison_passes_all_data_to_analysis(self):
        """When multiple tool results succeed, analysis agent gets all data."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "comparison",
            "requires_chart": False,
            "reasoning": "Compare Q1 vs Q2",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "Data fetched.",
                    "tool_results": [
                        {
                            "tool_name": "get_sales_register",
                            "tool_input": {"from_date": "01-04-2025", "to_date": "30-06-2025"},
                            "result": {"success": True, "data": [{"q": "Q1", "amount": 100}]},
                        },
                        {
                            "tool_name": "get_sales_register",
                            "tool_input": {"from_date": "01-07-2025", "to_date": "30-09-2025"},
                            "result": {"success": True, "data": [{"q": "Q2", "amount": 200}]},
                        },
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Q2 sales doubled.",
                    "data": {"headers": ["Q", "Amount"], "rows": [["Q1", 100], ["Q2", 200]]},
                    "insights": [],
                    "chart_suggestion": "grouped_bar",
                    "tool_results": [],
                }

                result = await orch.process_query("Compare Q1 vs Q2", mock_client, session)

                # analysis_agent.execute should receive raw_tally_data and computed_data
                call_args = mock_analysis.call_args
                raw_tally_data = call_args[0][0]  # first positional arg
                computed_data = call_args[0][1]   # second positional arg
                assert isinstance(raw_tally_data, list)
                assert len(raw_tally_data) == 2
                assert raw_tally_data[0] == [{"q": "Q1", "amount": 100}]
                assert raw_tally_data[1] == [{"q": "Q2", "amount": 200}]
                assert computed_data == []  # no computed tools in this test

        assert result["query_type"] == "comparison"

    @pytest.mark.asyncio
    async def test_handoff_separates_raw_and_computed_data(self):
        """When QueryAgent returns both raw and computed tools, handoff separates them."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "comparison",
            "requires_chart": False,
            "reasoning": "Compare Q2 vs Q3",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "Data fetched and compared.",
                    "tool_results": [
                        {
                            "tool_name": "get_profit_and_loss",
                            "tool_input": {"from_date": "01-07-2025", "to_date": "30-09-2025"},
                            "result": {"success": True, "data": [{"account": "Sales", "amount": 1195000}]},
                        },
                        {
                            "tool_name": "get_profit_and_loss",
                            "tool_input": {"from_date": "01-10-2025", "to_date": "31-12-2025"},
                            "result": {"success": True, "data": [{"account": "Sales", "amount": 1957500}]},
                        },
                        {
                            "tool_name": "compute_period_comparison",
                            "tool_input": {},
                            "result": {
                                "success": True,
                                "data": {
                                    "headers": ["Metric", "Q2", "Q3", "Change"],
                                    "rows": [["Sales", 1195000, 1957500, 762500]],
                                },
                            },
                        },
                        {
                            "tool_name": "compute_totals",
                            "tool_input": {},
                            "result": {
                                "success": True,
                                "data": {"headers": ["amount"], "rows": [[216000]]},
                            },
                        },
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Q3 sales grew 64%.",
                    "data": {"headers": ["Metric", "Q2", "Q3"], "rows": [["Sales", 1195000, 1957500]]},
                    "insights": [],
                    "chart_suggestion": "grouped_bar",
                    "tool_results": [],
                }

                result = await orch.process_query("Compare Q2 vs Q3 P&L", mock_client, session)

                # Verify handoff separates raw from computed
                call_args = mock_analysis.call_args
                raw_tally_data = call_args[0][0]
                computed_data = call_args[0][1]

                # Raw: 2 P&L fetches (list[dict] each)
                assert len(raw_tally_data) == 2
                assert raw_tally_data[0] == [{"account": "Sales", "amount": 1195000}]
                assert raw_tally_data[1] == [{"account": "Sales", "amount": 1957500}]

                # Computed: period comparison + totals
                assert len(computed_data) == 2
                assert computed_data[0]["headers"] == ["Metric", "Q2", "Q3", "Change"]
                assert computed_data[1]["headers"] == ["amount"]

        assert result["query_type"] == "comparison"


# ---------------------------------------------------------------------------
# Tests: Classification fallback logs warning (Fix #8)
# ---------------------------------------------------------------------------


class TestOrchestratorMultiDataset:
    @pytest.mark.asyncio
    async def test_multiple_datasets_passed_to_analysis(self):
        """When simple_lookup has multiple tool results, analysis agent processes them."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "lookup",
            "clarification_question": None,
        }

        agent_result = {
            "message": "Here are both reports",
            "tool_results": [
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q1"]]}}},
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q2"]]}}},
            ],
        }

        analysis_result = {
            "message": "Here are both reports analysed",
            "data": {"headers": ["Name", "Period"], "rows": [["Q1", "H1"], ["Q2", "H2"]]},
            "tool_results": [],
            "chart_suggestion": "table_only",
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            orch = Orchestrator()
            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock, return_value=agent_result),
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock, return_value=analysis_result) as mock_analysis,
            ):
                result = await orch.process_query("Show both reports", mock_client, session)

        # Analysis agent should have been called with the data
        mock_analysis.assert_awaited_once()
        # Analysis result's data should be used
        assert isinstance(result["data"], dict)
        assert result["data"]["headers"] == ["Name", "Period"]

    @pytest.mark.asyncio
    async def test_analysis_result_data_used_over_raw(self):
        """When analysis agent returns data, use that instead of raw datasets."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "comparison",
            "requires_chart": False,
            "reasoning": "comparing",
            "clarification_question": None,
        }

        agent_result = {
            "message": "Here is the data",
            "tool_results": [
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q1"]]}}},
                {"tool_name": "get_trial_balance", "tool_input": {}, "result": {"success": True, "data": {"headers": ["Name"], "rows": [["Q2"]]}}},
            ],
        }

        analysis_result = {
            "message": "Q1 vs Q2",
            "data": {"headers": ["Period", "Total"], "rows": [["Q1", 100], ["Q2", 200]]},
            "tool_results": [],
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            orch = Orchestrator()
            with patch.object(orch.query_agent, "execute", new_callable=AsyncMock, return_value=agent_result), \
                 patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock, return_value=analysis_result):
                result = await orch.process_query("Compare Q1 vs Q2", mock_client, session)

        # Analysis result's data should be used (it's a merged table)
        assert isinstance(result["data"], dict)
        assert result["data"]["headers"] == ["Period", "Total"]


# ---------------------------------------------------------------------------
# Tests: Classification fallback logs warning (Fix #8)
# ---------------------------------------------------------------------------


class TestClassificationFallbackLogging:
    @pytest.mark.asyncio
    async def test_non_json_response_logs_warning(self):
        """Issue #8: When Claude returns non-JSON, a warning must be logged."""
        from backend.agents.orchestrator import Orchestrator

        # Make a response that's valid text but not JSON
        non_json_response = MagicMock()
        non_json_response.stop_reason = "end_turn"
        block = MagicMock()
        block.type = "text"
        block.text = "I think this is a simple lookup query."
        non_json_response.content = [block]

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(return_value=non_json_response)

            with patch("backend.agents.orchestrator.logger") as mock_logger:
                orch = Orchestrator()
                result = await orch._classify("Show me sales")

                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "fallback" in warning_msg.lower() or "Classification" in warning_msg

        assert result["query_type"] == "simple_lookup"


# ---------------------------------------------------------------------------
# Tests: _flatten_datasets helper
# ---------------------------------------------------------------------------


class TestFlattenDatasets:
    """Test _flatten_datasets helper."""

    def test_flattens_two_lists(self):
        from backend.agents.orchestrator import _flatten_datasets
        result = _flatten_datasets([[{"a": 1}], [{"b": 2}]])
        assert len(result) == 2
        assert result[0] == {"a": 1, "_dataset_index": 0}
        assert result[1] == {"b": 2, "_dataset_index": 1}

    def test_handles_dict_dataset(self):
        from backend.agents.orchestrator import _flatten_datasets
        result = _flatten_datasets([{"x": 1}])
        assert result == [{"x": 1, "_dataset_index": 0}]

    def test_does_not_mutate_input(self):
        from backend.agents.orchestrator import _flatten_datasets
        original = {"key": "val"}
        _flatten_datasets([[original]])
        assert "_dataset_index" not in original

    def test_empty_input(self):
        from backend.agents.orchestrator import _flatten_datasets
        assert _flatten_datasets([]) == []

    def test_skips_non_dict_items(self):
        from backend.agents.orchestrator import _flatten_datasets
        result = _flatten_datasets([[{"a": 1}, "string_item", 42]])
        assert len(result) == 1
        assert result[0]["a"] == 1


# ---------------------------------------------------------------------------
# Tests: Auto-enable chart for aggregation
# ---------------------------------------------------------------------------


class TestAutoEnableChart:
    @pytest.mark.asyncio
    async def test_aggregation_auto_enables_chart(self):
        """aggregation query type with requires_chart=False should auto-enable chart."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "aggregation",
            "requires_chart": False,
            "reasoning": "User wants totals",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
                patch.object(orch.chart_agent, "execute") as mock_chart,
            ):
                mock_query.return_value = {
                    "message": "Total sales: ₹10,00,000",
                    "tool_results": [
                        {
                            "tool_name": "get_sales_register",
                            "tool_input": {},
                            "result": {"success": True, "data": [{"party": "A", "amount": 100}]},
                        }
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Total: ₹10,00,000",
                    "data": [{"party": "A", "amount": 100}],
                    "tool_results": [],
                    "chart_suggestion": "bar",
                }
                mock_chart.return_value = {"chart_type": "bar", "data": [], "config": {}}

                result = await orch.process_query("Total sales this year", mock_client, session)

                # Chart agent should have been called because aggregation auto-enables chart
                mock_chart.assert_called_once()

        assert result["chart"] is not None


# ---------------------------------------------------------------------------
# Tests: Classifier receives session context
# ---------------------------------------------------------------------------


class TestClassifierSessionContext:
    @pytest.mark.asyncio
    async def test_classify_includes_session_history(self):
        """Classifier messages should include recent session history."""
        from backend.agents.orchestrator import Orchestrator

        session = SessionContext()
        session.add_message("user", "Show trial balance")
        session.add_message("assistant", "Here is the trial balance.")

        classification = {
            "query_type": "simple_lookup",
            "requires_chart": False,
            "reasoning": "Follow-up",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()
            await orch._classify("Show me the details", session)

            # Inspect the messages passed to the classifier
            call_kwargs = mock_claude.messages.create.call_args[1]
            messages = call_kwargs["messages"]

            # Should have session history (2 messages) + current query (1) = 3
            assert len(messages) == 3
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Show trial balance"
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "Here is the trial balance."
            assert messages[2]["role"] == "user"
            assert messages[2]["content"] == "Show me the details"


# ---------------------------------------------------------------------------
# Tests: _separate_tool_results
# ---------------------------------------------------------------------------


class TestOrchestratorPromptContainsToolNames:
    def test_classifier_prompt_contains_tally_tool_names(self):
        """The orchestrator classifier prompt should list available Tally tool names."""
        from backend.agents.prompts import build_orchestrator_prompt
        from backend.agents.tools import TALLY_TOOLS

        prompt = build_orchestrator_prompt("13-03-2026")

        for tool in TALLY_TOOLS:
            assert tool["name"] in prompt, f"Tool {tool['name']} not found in classifier prompt"

        # Also verify the "Available Data Sources" section exists
        assert "Available Data Sources" in prompt
        assert "list_stock_items" in prompt
        assert "get_stock_summary" in prompt


class TestSeparateToolResults:
    def test_separate_raw_and_computed_data(self):
        """Orchestrator should separate raw Tally data from pre-computed results."""
        from backend.agents.orchestrator import _separate_tool_results
        tool_results = [
            {"tool_name": "get_sales_register", "result": {"success": True, "data": [{"amount": 100}]}},
            {"tool_name": "get_purchase_register", "result": {"success": True, "data": [{"amount": 50}]}},
            {"tool_name": "compute_totals", "result": {"success": True, "data": {"headers": ["Q", "Total"], "rows": [["Q2", 100]]}}},
            {"tool_name": "compute_period_comparison", "result": {"success": True, "data": {"headers": ["Metric", "Q2", "Q3"], "rows": [["Sales", 100, 200]]}}},
        ]
        raw, computed = _separate_tool_results(tool_results)
        assert len(raw) == 2
        assert len(computed) == 2
        assert raw[0] == [{"amount": 100}]
        assert computed[0]["headers"] == ["Q", "Total"]

    def test_separate_skips_failed_results(self):
        """Failed tool results should be excluded from both categories."""
        from backend.agents.orchestrator import _separate_tool_results
        tool_results = [
            {"tool_name": "get_sales_register", "result": {"success": True, "data": [{"amount": 100}]}},
            {"tool_name": "get_trial_balance", "result": {"error": "Tally unreachable"}},
            {"tool_name": "compute_totals", "result": {"success": True, "data": {"headers": ["A"], "rows": [[1]]}}},
        ]
        raw, computed = _separate_tool_results(tool_results)
        assert len(raw) == 1
        assert len(computed) == 1

    def test_separate_handles_report_response_conversion(self):
        """ReportResponse-style dicts in raw data should be converted to list[dict]."""
        from backend.agents.orchestrator import _separate_tool_results
        tool_results = [
            {"tool_name": "get_profit_and_loss", "result": {"success": True, "data": {"headers": ["Account", "Amount"], "rows": [["Sales", 100]]}}},
        ]
        raw, computed = _separate_tool_results(tool_results)
        assert len(raw) == 1
        assert raw[0] == [{"Account": "Sales", "Amount": 100}]


# ---------------------------------------------------------------------------
# Tests: AnalysisAgent prompt column naming rules
# ---------------------------------------------------------------------------


class TestAnalysisPromptColumnNamingRules:
    def test_analysis_prompt_contains_column_naming_rules(self):
        """AnalysisAgent prompt (code_execution=True) must include standard column naming rules."""
        from backend.agents.prompts import build_analysis_agent_prompt

        prompt = build_analysis_agent_prompt("trend", code_execution_enabled=True)

        assert "Change" in prompt and "Change %" in prompt
        assert "STRUCTURED_RESULT" in prompt
        assert "column naming" in prompt.lower() or "standard column" in prompt.lower()

    def test_analysis_prompt_column_rules_present_for_all_query_types(self):
        """Column naming rules should appear for all query types when code_execution=True."""
        from backend.agents.prompts import build_analysis_agent_prompt

        for query_type in ("comparison", "trend", "top_n", "aggregation"):
            prompt = build_analysis_agent_prompt(query_type, code_execution_enabled=True)
            assert "column naming" in prompt.lower() or "standard column" in prompt.lower(), (
                f"Column naming rules missing for query_type={query_type}"
            )

    def test_analysis_prompt_column_rules_absent_when_code_exec_disabled(self):
        """Column naming rules in the code-exec block should not appear when code_execution=False."""
        from backend.agents.prompts import build_analysis_agent_prompt

        prompt = build_analysis_agent_prompt("trend", code_execution_enabled=False)
        # The standard column names rule is only needed when code_execution generates columns
        assert "standard column" not in prompt.lower() or "column naming" not in prompt.lower()

    def test_analysis_prompt_forbids_non_standard_column_names(self):
        """Prompt should explicitly forbid common non-standard column name variations."""
        from backend.agents.prompts import build_analysis_agent_prompt

        prompt = build_analysis_agent_prompt("comparison", code_execution_enabled=True)
        # At least some of the forbidden aliases must be mentioned
        forbidden_variants = ["MoM Change", "Abs Change", "MoM %", "% vs Avg"]
        assert any(v in prompt for v in forbidden_variants), (
            "Prompt should list at least one forbidden column name variant"
        )


# ---------------------------------------------------------------------------
# Tests: _has_table_intent — Bug B3
# ---------------------------------------------------------------------------


class TestHasTableIntent:
    """Bug B3: User saying 'show as a table' should suppress chart generation."""

    def test_positive_show_as_a_table(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show sales as a table") is True

    def test_positive_in_table_format(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show P&L in table format") is True

    def test_positive_table_only(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Give me table only") is True

    def test_positive_just_a_table(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("I want just a table") is True

    def test_positive_only_table(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show only table please") is True

    def test_positive_no_chart(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Sales report no chart") is True

    def test_positive_case_insensitive(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show As A Table") is True
        assert _has_table_intent("NO CHART please") is True

    def test_negative_normal_query(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show me total sales") is False

    def test_negative_show_me_the_data(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show me the data") is False

    def test_negative_chart_request(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show sales as a bar chart") is False

    def test_negative_empty_string(self):
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("") is False

    def test_negative_table_word_alone(self):
        """The word 'table' alone should NOT trigger table-only intent."""
        from backend.agents.orchestrator import _has_table_intent
        assert _has_table_intent("Show the balance sheet table") is False


class TestTableIntentSuppressesChart:
    """Integration: table-only intent should prevent chart agent from being called."""

    @pytest.mark.asyncio
    async def test_table_intent_suppresses_chart_for_aggregation(self):
        """User saying 'as a table' on an aggregation query should NOT call chart agent."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "aggregation",
            "requires_chart": True,
            "reasoning": "User wants totals",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            orch = Orchestrator()
            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
                patch.object(orch.chart_agent, "execute") as mock_chart,
            ):
                mock_query.return_value = {
                    "message": "Total sales",
                    "tool_results": [
                        {"tool_name": "get_sales_register", "tool_input": {}, "result": {"success": True, "data": [{"party": "A", "amount": 100}]}},
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Total: ₹100",
                    "data": [{"party": "A", "amount": 100}],
                    "tool_results": [],
                    "chart_suggestion": "bar",
                }

                result = await orch.process_query(
                    "Show total sales as a table", mock_client, session
                )

                # Chart agent should NOT have been called
                mock_chart.assert_not_called()

        assert result["chart"] is None

    @pytest.mark.asyncio
    async def test_no_table_intent_still_auto_enables_chart(self):
        """Normal aggregation query (no table intent) should still auto-enable chart."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()

        classification = {
            "query_type": "aggregation",
            "requires_chart": False,
            "reasoning": "User wants totals",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )
            orch = Orchestrator()
            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
                patch.object(orch.chart_agent, "execute") as mock_chart,
            ):
                mock_query.return_value = {
                    "message": "Total sales",
                    "tool_results": [
                        {"tool_name": "get_sales_register", "tool_input": {}, "result": {"success": True, "data": [{"party": "A", "amount": 100}]}},
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Total: ₹100",
                    "data": [{"party": "A", "amount": 100}],
                    "tool_results": [],
                    "chart_suggestion": "bar",
                }
                mock_chart.return_value = {"chart_type": "bar", "data": [], "config": {}}

                result = await orch.process_query(
                    "Show total sales", mock_client, session
                )

                # Chart agent SHOULD have been called (auto-enable)
                mock_chart.assert_called_once()

        assert result["chart"] is not None


# ---------------------------------------------------------------------------
# Phase 14: Orchestrator passes session to AnalysisAgent
# ---------------------------------------------------------------------------


class TestOrchestratorPassesSession:
    @pytest.mark.asyncio
    async def test_analysis_agent_receives_session(self):
        """Orchestrator passes session kwarg to analysis_agent.execute()."""
        from backend.agents.orchestrator import Orchestrator

        mock_client = MagicMock()
        session = SessionContext()
        session.add_message("user", "Show me sales data")
        session.add_message("assistant", "Here is the sales data.")

        classification = {
            "query_type": "aggregation",
            "requires_chart": False,
            "reasoning": "Total sales",
            "clarification_question": None,
        }

        with patch("backend.agents.orchestrator.anthropic_client") as mock_claude:
            mock_claude.messages.create = AsyncMock(
                return_value=_make_classification_response(classification)
            )

            orch = Orchestrator()

            with (
                patch.object(orch.query_agent, "execute", new_callable=AsyncMock) as mock_query,
                patch.object(orch.analysis_agent, "execute", new_callable=AsyncMock) as mock_analysis,
            ):
                mock_query.return_value = {
                    "message": "Data fetched.",
                    "tool_results": [
                        {
                            "tool_name": "get_trial_balance",
                            "tool_input": {},
                            "result": {"success": True, "data": [{"account": "Sales", "amount": 500000}]},
                        },
                    ],
                }
                mock_analysis.return_value = {
                    "message": "Total sales: ₹5,00,000.",
                    "data": {"headers": ["Account", "Amount"], "rows": [["Sales", 500000]]},
                    "insights": [],
                    "chart_suggestion": None,
                    "tool_results": [],
                }

                await orch.process_query("What are total sales?", mock_client, session)

                # Verify session was passed as kwarg
                mock_analysis.assert_called_once()
                call_kwargs = mock_analysis.call_args.kwargs
                assert "session" in call_kwargs
                assert call_kwargs["session"] is session
