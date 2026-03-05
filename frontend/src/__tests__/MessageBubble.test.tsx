import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MessageBubble from "../components/MessageBubble";
import type { ChatMessage } from "../types";

describe("MessageBubble", () => {
  it("renders user message text", () => {
    const msg: ChatMessage = { id: "1", role: "user", content: "Show trial balance" };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Show trial balance")).toBeInTheDocument();
  });

  it("renders assistant message text", () => {
    const msg: ChatMessage = { id: "2", role: "assistant", content: "Here is your trial balance" };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Here is your trial balance")).toBeInTheDocument();
  });

  it("renders loading dots when isLoading is true", () => {
    const msg: ChatMessage = { id: "3", role: "assistant", content: "", isLoading: true };
    const { container } = render(<MessageBubble message={msg} />);
    const dots = container.querySelectorAll(".animate-bounce");
    expect(dots.length).toBe(3);
  });

  it("renders error state with error content", () => {
    const msg: ChatMessage = { id: "4", role: "assistant", content: "Something went wrong", isError: true };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders DataTable when message has valid data", () => {
    const msg: ChatMessage = {
      id: "5", role: "assistant", content: "Here is the data",
      data: { headers: ["Name", "Amount"], rows: [["Sales", 100]] },
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
  });

  it("renders ChartRenderer when message has chart", () => {
    const msg: ChatMessage = {
      id: "6", role: "assistant", content: "Chart below",
      chart: { chart_type: "bar", title: "Test Chart", data: [{ label: "A", value: 100 }] },
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Test Chart")).toBeInTheDocument();
  });

  it("does not render DataTable when data has no headers/rows keys", () => {
    const msg: ChatMessage = {
      id: "7", role: "assistant", content: "No table",
      data: { something: "else" } as any,
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("No table")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
