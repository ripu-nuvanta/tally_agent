import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChartRenderer from "../components/ChartRenderer";
import type { ChartSpec } from "../types";

const barChart: ChartSpec = {
  chart_type: "bar",
  title: "Sales by Customer",
  data: [{ customer: "HCODE", amount: 500000 }, { customer: "SMARTBIKE", amount: 300000 }],
};

const lineChart: ChartSpec = {
  chart_type: "line",
  title: "Monthly Revenue",
  data: [{ month: "Apr", revenue: 100000 }, { month: "May", revenue: 150000 }, { month: "Jun", revenue: 120000 }],
};

const pieChart: ChartSpec = {
  chart_type: "pie",
  title: "Expense Breakdown",
  data: [{ category: "Rent", amount: 50000 }, { category: "Salary", amount: 200000 }],
};

describe("ChartRenderer", () => {
  it("renders chart title", () => {
    render(<ChartRenderer chart={barChart} />);
    expect(screen.getByText("Sales by Customer")).toBeInTheDocument();
  });

  it("renders bar chart container", () => {
    render(<ChartRenderer chart={barChart} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders line chart", () => {
    render(<ChartRenderer chart={lineChart} />);
    expect(screen.getByText("Monthly Revenue")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders pie chart", () => {
    render(<ChartRenderer chart={pieChart} />);
    expect(screen.getByText("Expense Breakdown")).toBeInTheDocument();
  });

  it("renders grouped_bar chart", () => {
    const grouped: ChartSpec = {
      chart_type: "grouped_bar",
      title: "Q1 vs Q2",
      data: [{ label: "Sales", q1: 100, q2: 150 }],
    };
    render(<ChartRenderer chart={grouped} />);
    expect(screen.getByText("Q1 vs Q2")).toBeInTheDocument();
  });

  it("returns null for empty data", () => {
    const empty: ChartSpec = { chart_type: "bar", title: "Empty", data: [] };
    const { container } = render(<ChartRenderer chart={empty} />);
    expect(container.firstChild).toBeNull();
  });

  it("exposes chart spec as data attribute", () => {
    const { container } = render(<ChartRenderer chart={barChart} />);
    const el = container.querySelector("[data-chart-spec]");
    expect(el).not.toBeNull();
    const spec = JSON.parse(el!.getAttribute("data-chart-spec")!);
    expect(spec.chart_type).toBe("bar");
    expect(spec.title).toBe("Sales by Customer");
    expect(spec.data).toHaveLength(2);
  });

  it("renders composed chart", () => {
    const composed: ChartSpec = {
      chart_type: "composed",
      title: "Revenue vs Growth",
      data: [
        { month: "Apr", revenue: 100000, growth: 10 },
        { month: "May", revenue: 150000, growth: 15 },
      ],
      config: {
        x_key: "month",
        y_keys: ["revenue"],
        secondary_y_keys: ["growth"],
        secondary_colors: ["#FF0000"],
      },
    };
    render(<ChartRenderer chart={composed} />);
    expect(screen.getByText("Revenue vs Growth")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders composed chart without secondary keys", () => {
    const composed: ChartSpec = {
      chart_type: "composed",
      title: "Just Bars",
      data: [
        { month: "Apr", revenue: 100000 },
        { month: "May", revenue: 150000 },
      ],
      config: {
        x_key: "month",
        y_keys: ["revenue"],
      },
    };
    render(<ChartRenderer chart={composed} />);
    expect(screen.getByText("Just Bars")).toBeInTheDocument();
  });

  it("hides legend when show_legend is false", () => {
    const chartNoLegend: ChartSpec = {
      chart_type: "bar",
      title: "No Legend Chart",
      data: [{ customer: "A", amount: 100 }],
      config: { show_legend: false },
    };
    const { container } = render(<ChartRenderer chart={chartNoLegend} />);
    const spec = JSON.parse(
      container.querySelector("[data-chart-spec]")!.getAttribute("data-chart-spec")!
    );
    expect(spec.config.show_legend).toBe(false);
    expect(screen.getByText("No Legend Chart")).toBeInTheDocument();
  });

  it("renders Change % line with linear interpolation in composed chart", () => {
    const spec: ChartSpec = {
      chart_type: "composed",
      title: "Test",
      data: [
        { label: "Nov 2025", Sales: 200000, "Change %": -27.3 },
        { label: "Dec 2025", Sales: 200000, "Change %": 0 },
      ],
      config: {
        x_key: "label",
        y_keys: ["Sales"],
        secondary_y_keys: ["Change %"],
        secondary_colors: ["#9CA3AF"],
      },
    };

    const { container } = render(<ChartRenderer chart={spec} />);

    expect(screen.getByText("Test")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    const chartSpec = JSON.parse(
      container.querySelector("[data-chart-spec]")!.getAttribute("data-chart-spec")!
    );
    expect(chartSpec.config.secondary_y_keys).toEqual(["Change %"]);
    expect(chartSpec.chart_type).toBe("composed");
  });

  it("uses config.y_keys when provided", () => {
    const chartWithKeys: ChartSpec = {
      chart_type: "bar",
      title: "With Y Keys",
      data: [
        { month: "Apr", revenue: 100000, expenses: 80000, notes: "good" },
      ],
      config: {
        x_key: "month",
        y_keys: ["revenue", "expenses"],
      },
    };
    const { container } = render(<ChartRenderer chart={chartWithKeys} />);
    const spec = JSON.parse(
      container.querySelector("[data-chart-spec]")!.getAttribute("data-chart-spec")!
    );
    // Verify config is passed through correctly
    expect(spec.config.y_keys).toEqual(["revenue", "expenses"]);
    expect(spec.config.x_key).toBe("month");
  });
});
