import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataTable from "../components/DataTable";
import type { TableData } from "../types";

const sampleData: TableData = {
  headers: ["Ledger", "Amount"],
  rows: [
    ["Sales Account", 1234567],
    ["Purchase Account", 890000],
    ["Cash", 50000],
  ],
};

describe("DataTable", () => {
  it("renders headers", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("Ledger")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
  });

  it("renders all rows", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("Sales Account")).toBeInTheDocument();
    expect(screen.getByText("Purchase Account")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
  });

  it("formats numbers in Indian style", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("12,34,567.00")).toBeInTheDocument();
  });

  it("returns null for empty rows", () => {
    const { container } = render(<DataTable data={{ headers: ["A"], rows: [] }} />);
    expect(container.firstChild).toBeNull();
  });

  it("sorts ascending on first column header click", async () => {
    const user = userEvent.setup();
    render(<DataTable data={sampleData} />);
    await user.click(screen.getByText("Amount"));
    const cells = screen.getAllByRole("cell");
    const amountCells = cells.filter((_, i) => i % 2 === 1);
    expect(amountCells[0]).toHaveTextContent("50,000.00");
  });

  it("sorts descending on second click of same column", async () => {
    const user = userEvent.setup();
    render(<DataTable data={sampleData} />);
    await user.click(screen.getByText("Amount"));
    await user.click(screen.getByText("Amount"));
    const cells = screen.getAllByRole("cell");
    const amountCells = cells.filter((_, i) => i % 2 === 1);
    expect(amountCells[0]).toHaveTextContent("12,34,567.00");
  });

  it("renders CSV export button", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("CSV")).toBeInTheDocument();
  });

  it("handles null cell values", () => {
    const data: TableData = { headers: ["Name", "Value"], rows: [["Test", null]] };
    render(<DataTable data={data} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("handles string values in columns", () => {
    const data: TableData = { headers: ["Name", "Type"], rows: [["Sales", "Revenue"], ["Rent", "Expense"]] };
    render(<DataTable data={data} />);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Expense")).toBeInTheDocument();
  });
});
