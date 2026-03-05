import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatInput from "../components/ChatInput";

describe("ChatInput", () => {
  it("renders a textarea with placeholder", () => {
    render(<ChatInput onSend={() => {}} />);
    expect(screen.getByPlaceholderText("Ask about your Tally data...")).toBeInTheDocument();
  });

  it("renders a send button", () => {
    render(<ChatInput onSend={() => {}} />);
    expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument();
  });

  it("calls onSend with trimmed text on Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Show trial balance{Enter}");
    expect(onSend).toHaveBeenCalledWith("Show trial balance");
  });

  it("does not call onSend on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "line 1{Shift>}{Enter}{/Shift}line 2");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when input is empty", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("clears input after send", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={() => {}} />);
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "hello{Enter}");
    expect(textarea).toHaveValue("");
  });

  it("calls onSend on send button click", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test query");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSend).toHaveBeenCalledWith("test query");
  });

  it("disables textarea and button when disabled", () => {
    render(<ChatInput onSend={() => {}} disabled />);
    expect(screen.getByPlaceholderText("Ask about your Tally data...")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
});
