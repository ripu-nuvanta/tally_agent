"""E2E tests for chart stabilization pipeline.

Tests full flow: response text → markdown table parser → ChartAgent → chart spec.
Uses real transcript fixtures from eval run_20260316_160527.
"""

import pytest
from backend.agents.chart_agent import ChartAgent
from backend.agents.utils import parse_markdown_table_for_chart, parse_all_markdown_tables
from backend.agents.orchestrator import _filter_table_by_advice
from tests.fixtures.chart_transcript_fixtures import (
    TURN_2_TOP_CUSTOMERS,
    TURN_3_MOM_GROWTH,
    TURN_4_Q3_VS_Q4,
    TURN_5_EXPENSE_BREAKDOWN,
    TURN_7_AVG_MONTHLY,
    TURN_OVERSPENDING,
    TURN_OVERDUE_RECEIVABLES,
)


class TestChartPipelineE2E:

    def _run_pipeline(self, fixture):
        table_data = parse_markdown_table_for_chart(fixture["message"])
        assert table_data is not None, f"Failed to parse table from: {fixture['query']}"
        agent = ChartAgent()
        chart = agent.execute(
            table_data,
            fixture["query_type"],
            chart_suggestion=fixture.get("chart_suggestion"),
        )
        return table_data, chart

    def test_turn2_top_customers(self):
        """Turn 2: Rank skipped, Invoices excluded (scale), Total excluded."""
        table_data, chart = self._run_pipeline(TURN_2_TOP_CUSTOMERS)
        # X-axis should be Customer, not Rank
        assert table_data["headers"][0] == "Customer"
        assert chart is not None
        # Invoices excluded from y_keys (scale mismatch with Sales)
        assert "Invoices" not in chart["config"]["y_keys"]
        # Total row excluded
        labels = [d["label"] for d in chart["data"]]
        assert not any("total" in l.lower() for l in labels)
        assert not any("all customers" in l.lower() for l in labels)

    def test_turn3_mom_growth(self):
        """Turn 3: Change % parsed correctly (not zeroed), Vouchers excluded."""
        table_data, chart = self._run_pipeline(TURN_3_MOM_GROWTH)
        assert chart is not None
        # Vouchers excluded (scale mismatch)
        assert "Vouchers" not in chart["config"]["y_keys"]
        # Change % values should NOT all be zeros
        change_pcts = [d.get("Change %", 0) for d in chart["data"]]
        assert not all(v == 0 for v in change_pcts), f"Change % all zeroed: {change_pcts}"
        # Total row excluded
        labels = [d["label"] for d in chart["data"]]
        assert "Total" not in labels

    def test_turn4_q3_vs_q4(self):
        """Turn 4: Multiple tables → picks largest, totals excluded."""
        table_data, chart = self._run_pipeline(TURN_4_Q3_VS_Q4)
        assert chart is not None
        # Total rows excluded
        labels = [d["label"] for d in chart["data"]]
        assert not any("total" in l.lower() for l in labels)

    def test_turn5_expense_pie(self):
        """Turn 5: Pie chart, # column skipped, Grand Total excluded."""
        table_data, chart = self._run_pipeline(TURN_5_EXPENSE_BREAKDOWN)
        # X-axis is Expense Ledger, not #
        assert table_data["headers"][0] == "Expense Ledger" or table_data["headers"][0] == "Expense"
        assert chart is not None
        assert chart["chart_type"] == "pie"
        # Grand Total / — rows excluded
        labels = [d["label"] for d in chart["data"]]
        assert "Grand Total" not in labels
        assert "—" not in labels

    def test_turn7_avg_monthly(self):
        """Turn 7: All months' Change % parsed (including negatives)."""
        table_data, chart = self._run_pipeline(TURN_7_AVG_MONTHLY)
        assert chart is not None
        # Change % should include negative values (not zeroed)
        change_pcts = [d.get("Change %", 0) for d in chart["data"]]
        has_negative = any(v < 0 for v in change_pcts)
        assert has_negative, f"Expected negative Change %, got: {change_pcts}"

    def test_overspending_comparison(self):
        """Overspending: picks larger table (7 rows), TOTAL excluded, text values handled."""
        table_data, chart = self._run_pipeline(TURN_OVERSPENDING)
        assert table_data is not None
        # Should pick the 7-row table (Full Operating Expense Comparison)
        assert table_data["headers"][0] == "Category"
        assert chart is not None
        # TOTAL row excluded (bold **TOTAL**)
        labels = [d["label"] for d in chart["data"]]
        assert not any("total" in l.lower() for l in labels)
        # Should have 6 expense categories (minus TOTAL)
        assert len(chart["data"]) == 6

    def test_overdue_receivables(self):
        """Overdue: Rank skipped, Grand Total excluded, Customer as x-axis.

        The table has 3 non-numeric columns (Due Date, Overdue Days — "76 days"
        text does not parse, Aging Bucket emoji text), so ChartAgent correctly
        returns None (table_only). The table itself is still fully parsed.
        """
        table_data = parse_markdown_table_for_chart(TURN_OVERDUE_RECEIVABLES["message"])
        assert table_data is not None
        # Rank column skipped — Customer is x-axis
        assert table_data["headers"][0] == "Customer"
        # Table should have 7 rows including Grand Total
        assert len(table_data["rows"]) == 7
        # Grand Total row present in raw table data (chart exclusion happens in ChartAgent)
        labels = [row[0] for row in table_data["rows"]]
        assert any("Grand Total" in str(l) for l in labels)
        # Pending Amount column present
        assert "Pending Amount" in table_data["headers"]
        # % of Total column present
        assert "% of Total" in table_data["headers"]
        # ChartAgent returns None — too many non-numeric columns (Due Date, Overdue Days, Aging Bucket)
        agent = ChartAgent()
        chart = agent.execute(
            table_data,
            TURN_OVERDUE_RECEIVABLES["query_type"],
            chart_suggestion=TURN_OVERDUE_RECEIVABLES.get("chart_suggestion"),
        )
        assert chart is None, (
            "Expected table_only (None) due to 3 non-numeric columns: "
            "Due Date, Overdue Days ('76 days' text), Aging Bucket (emoji text)"
        )


class TestChartAdvisorPipelineE2E:
    """E2E tests simulating the chart advisor → filter → ChartAgent pipeline.

    These tests bypass the real Haiku API call and directly simulate the advisor
    output (as a dict), then verify that _filter_table_by_advice + ChartAgent
    produce the expected chart spec.
    """

    def test_overspending_with_advisor(self):
        """Advisor picks 3M Avg vs Feb columns → meaningful grouped_bar chart."""
        tables = parse_all_markdown_tables(TURN_OVERSPENDING["message"])
        assert len(tables) >= 2, f"Expected ≥2 tables, got {len(tables)}"

        # Table 1 is the full 7-row comparison table (Category + 7 columns)
        # Table 0 is the 2-row overspending-only table
        large_table_idx = max(range(len(tables)), key=lambda i: len(tables[i]["rows"]))
        selected_table = tables[large_table_idx]

        # Verify the expected headers exist before building advice
        actual_headers = selected_table["headers"]
        assert "Category" in actual_headers, f"Category not in headers: {actual_headers}"
        assert "3M Avg" in actual_headers, f"3M Avg not in headers: {actual_headers}"
        feb_col = next((h for h in actual_headers if "feb" in h.lower()), None)
        assert feb_col is not None, f"No Feb column in headers: {actual_headers}"

        # Simulate advisor output: pick Category as x, 3M Avg + Feb as y
        advice = {
            "table_index": large_table_idx,
            "x_column": "Category",
            "y_columns": ["3M Avg", feb_col],
            "secondary_y_columns": [],
            "chart_type": "grouped_bar",
            "chart_title": "Feb 2026 vs 3-Month Average",
        }

        filtered = _filter_table_by_advice(selected_table, advice)
        assert filtered is not None, f"Filter failed. Headers: {actual_headers}"

        # Only 3 columns: Category + 3M Avg + Feb
        assert len(filtered["headers"]) == 3
        assert filtered["headers"][0] == "Category"
        assert "3M Avg" in filtered["headers"]
        assert feb_col in filtered["headers"]

        agent = ChartAgent()
        chart = agent.execute(filtered, "comparison", chart_suggestion="grouped_bar")
        assert chart is not None
        assert chart["chart_type"] in ("grouped_bar", "bar")

        # TOTAL row must be excluded
        labels = [d["label"] for d in chart["data"]]
        assert not any("total" in l.lower() for l in labels), f"TOTAL row in chart: {labels}"

        # Should have expense categories (at least 4 of the 6)
        assert len(chart["data"]) >= 4, f"Expected ≥4 expense rows, got {len(chart['data'])}"

    def test_overdue_receivables_with_advisor(self):
        """Advisor picks Customer + Pending Amount → bar chart (not table_only).

        The full table has 3 non-numeric columns (Due Date, Overdue Days, Aging Bucket),
        causing ChartAgent to return None. But the advisor filters to just
        Customer + Pending Amount (+ optional % of Total), which gives ChartAgent
        clean numeric data and produces a bar chart.
        """
        tables = parse_all_markdown_tables(TURN_OVERDUE_RECEIVABLES["message"])
        assert len(tables) >= 1

        # Find the customer-level table (has "Customer" header)
        customer_table_idx = next(
            (i for i, t in enumerate(tables) if any("customer" in h.lower() for h in t["headers"])),
            0,
        )
        selected = tables[customer_table_idx]
        actual_headers = selected["headers"]

        customer_col = next((h for h in actual_headers if "customer" in h.lower()), None)
        pending_col = next((h for h in actual_headers if "pending" in h.lower()), None)
        pct_col = next((h for h in actual_headers if "%" in h), None)

        assert customer_col is not None, f"No Customer column in {actual_headers}"
        assert pending_col is not None, f"No Pending Amount column in {actual_headers}"

        # Simulate advisor output: Customer as x, Pending Amount as y, % of Total as secondary
        advice = {
            "table_index": customer_table_idx,
            "x_column": customer_col,
            "y_columns": [pending_col],
            "secondary_y_columns": [pct_col] if pct_col else [],
            "chart_type": "bar",
            "chart_title": "Overdue Receivables by Customer",
        }

        filtered = _filter_table_by_advice(selected, advice)
        assert filtered is not None, f"Filter failed. Headers: {actual_headers}"

        # Filtered table should have only Customer + Pending Amount (+ optional % of Total)
        expected_col_count = 2 + (1 if pct_col else 0)
        assert len(filtered["headers"]) == expected_col_count, (
            f"Expected {expected_col_count} columns, got {filtered['headers']}"
        )
        assert filtered["headers"][0] == customer_col
        assert pending_col in filtered["headers"]

        # ChartAgent should now produce a chart (text-only columns removed)
        agent = ChartAgent()
        chart = agent.execute(filtered, "top_n", chart_suggestion="bar")
        assert chart is not None, (
            "Expected a chart after advisor filtered out text columns "
            "(Due Date, Overdue Days, Aging Bucket)"
        )
        assert chart["chart_type"] in ("bar", "composed")

        # Grand Total row must be excluded
        labels = [d["label"] for d in chart["data"]]
        assert not any("grand total" in l.lower() for l in labels), (
            f"Grand Total row leaked into chart: {labels}"
        )

        # Should have customer rows (at least 4 of the 6)
        assert len(chart["data"]) >= 4, f"Expected ≥4 customer rows, got {len(chart['data'])}"
