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
});
