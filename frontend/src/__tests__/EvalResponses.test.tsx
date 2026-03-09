import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import fixtures from "./fixtures/eval_responses.json";
import DataTable from "../components/DataTable";
import ChartRenderer from "../components/ChartRenderer";
import MessageBubble from "../components/MessageBubble";
import type { ChatMessage, ChartSpec, TableData } from "../types";

describe("EvalResponses — real eval transcript fixtures", () => {
  test.each(fixtures)("MessageBubble renders $name without error", (fixture) => {
    const message: ChatMessage = {
      id: "eval-1",
      role: "assistant",
      content: fixture.message,
      data: fixture.data as TableData | TableData[] | undefined,
      chart: fixture.chart as ChartSpec | undefined,
    };
    const { container } = render(<MessageBubble message={message} />);
    expect(container).toBeTruthy();
    // Assistant messages should always render some text content
    expect(container.textContent).toBeTruthy();
  });

  test("profit_and_loss_response renders message text (no table/chart)", () => {
    const fixture = fixtures.find((f) => f.name === "profit_and_loss_response")!;
    const message: ChatMessage = {
      id: "eval-pl",
      role: "assistant",
      content: fixture.message,
    };
    render(<MessageBubble message={message} />);
    expect(screen.getByText(/Profit & Loss Statement/)).toBeInTheDocument();
    // No table or chart expected
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("quarterly_comparison_response renders DataTable with financial data", () => {
    const fixture = fixtures.find((f) => f.name === "quarterly_comparison_response")!;
    const tableData = fixture.data as TableData;
    render(<DataTable data={tableData} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    // Check headers from real eval response
    expect(screen.getByText("sales")).toBeInTheDocument();
    expect(screen.getByText("purchases")).toBeInTheDocument();
    expect(screen.getByText("indirect_expenses")).toBeInTheDocument();
    // Check row data
    expect(screen.getByText("57,21,850.00")).toBeInTheDocument();
  });

  test("top_customers_response renders both table and chart", () => {
    const fixture = fixtures.find((f) => f.name === "top_customers_response")!;
    const message: ChatMessage = {
      id: "eval-top",
      role: "assistant",
      content: fixture.message,
      data: fixture.data as TableData,
      chart: fixture.chart as ChartSpec,
    };
    render(<MessageBubble message={message} />);
    // Table should render
    expect(screen.getByRole("table")).toBeInTheDocument();
    // Chart title should render
    expect(screen.getByText("Top Customers by Sales")).toBeInTheDocument();
  });

  test("purchase_breakdown_response renders vendor data with commas in names", () => {
    const fixture = fixtures.find((f) => f.name === "purchase_breakdown_response")!;
    const tableData = fixture.data as TableData;
    render(<DataTable data={tableData} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    // Vendor name with comma should render correctly
    expect(screen.getByText("Anthropic, PBC")).toBeInTheDocument();
    expect(screen.getByText("Cursor")).toBeInTheDocument();
  });

  test("multi_dataset_response renders multiple DataTables", () => {
    const fixture = fixtures.find((f) => f.name === "multi_dataset_response")!;
    const message: ChatMessage = {
      id: "eval-multi",
      role: "assistant",
      content: fixture.message,
      data: fixture.data as TableData[],
      chart: fixture.chart as ChartSpec,
    };
    render(<MessageBubble message={message} />);
    // Should render 2 tables (one per dataset)
    const tables = screen.getAllByRole("table");
    expect(tables.length).toBe(2);
    // Chart should also render
    expect(screen.getByText("Q2 vs Q3 Comparison")).toBeInTheDocument();
  });

  // Chart-specific tests using real eval chart specs
  const chartFixtures = fixtures.filter((f) => f.chart !== null);

  test.each(chartFixtures)(
    "ChartRenderer handles $name chart spec",
    (fixture) => {
      const chart = fixture.chart as ChartSpec;
      const { container } = render(<ChartRenderer chart={chart} />);
      expect(container).toBeTruthy();
      // Title should be visible
      expect(screen.getByText(chart.title)).toBeInTheDocument();
    }
  );

  test("purchase_breakdown chart exposes data-chart-spec attribute", () => {
    const fixture = fixtures.find((f) => f.name === "purchase_breakdown_response")!;
    const chart = fixture.chart as ChartSpec;
    const { container } = render(<ChartRenderer chart={chart} />);
    const el = container.querySelector("[data-chart-spec]");
    expect(el).not.toBeNull();
    const spec = JSON.parse(el!.getAttribute("data-chart-spec")!);
    expect(spec.chart_type).toBe("bar");
    expect(spec.data).toHaveLength(2);
    expect(spec.config.currency_format).toBe(true);
  });

  test("grouped_bar chart renders with multiple y_keys", () => {
    const fixture = fixtures.find((f) => f.name === "multi_dataset_response")!;
    const chart = fixture.chart as ChartSpec;
    const { container } = render(<ChartRenderer chart={chart} />);
    const el = container.querySelector("[data-chart-spec]");
    expect(el).not.toBeNull();
    const spec = JSON.parse(el!.getAttribute("data-chart-spec")!);
    expect(spec.chart_type).toBe("grouped_bar");
    expect(spec.config.y_keys).toEqual(["Q2", "Q3"]);
  });
});
