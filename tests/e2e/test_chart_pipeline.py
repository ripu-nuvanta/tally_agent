"""E2E tests for chart stabilization pipeline.

Tests full flow: response text → markdown table parser → ChartAgent → chart spec.
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
