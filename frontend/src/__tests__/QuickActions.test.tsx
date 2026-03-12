import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import QuickActions from "../components/QuickActions";

const EXPECTED_QUERIES = [
  "P&L last month", "Outstanding receivables", "Cash balance",
  "Top 10 customers", "Sales vs purchases last month",
];

describe("QuickActions", () => {
  it("renders all 5 query buttons", () => {
    render(<QuickActions onSelect={() => {}} />);
    for (const query of EXPECTED_QUERIES) {
      expect(screen.getByRole("button", { name: query })).toBeInTheDocument();
    }
  });

  it("calls onSelect with the query text when clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} />);
    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).toHaveBeenCalledWith("Cash balance");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("disables all buttons when disabled prop is true", () => {
    render(<QuickActions onSelect={() => {}} disabled />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("does not call onSelect when disabled button is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} disabled />);
    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
