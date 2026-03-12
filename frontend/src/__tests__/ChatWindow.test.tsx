import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatWindow from "../components/ChatWindow";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

Element.prototype.scrollIntoView = vi.fn();

function renderWithProvider() {
  return render(
    <SessionProvider>
      <ChatWindow />
    </SessionProvider>
  );
}

describe("ChatWindow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders empty state with welcome message", () => {
    renderWithProvider();
    expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    expect(screen.getByText("Ask me anything about your accounting data")).toBeInTheDocument();
  });

  it("renders quick actions in empty state", () => {
    renderWithProvider();
    expect(screen.getByRole("button", { name: "Cash balance" })).toBeInTheDocument();
  });

  it("shows user message after sending", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Here is the trial balance", session_id: "sess-1" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Show trial balance{Enter}");
    expect(screen.getByText("Show trial balance")).toBeInTheDocument();
  });

  it("shows agent response after successful API call", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Your trial balance is ready", session_id: "sess-1" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Trial balance{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Your trial balance is ready")).toBeInTheDocument();
    });
  });

  it("shows error message on network error", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockRejectedValue(new Error("Network Error"));
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Cannot connect to the server. Please check if the backend is running.")).toBeInTheDocument();
    });
  });

  it("shows generic error on non-network error", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockRejectedValue(new Error("Server Error"));
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Something went wrong. Please try again.")).toBeInTheDocument();
    });
  });

  it("sends session_id on subsequent messages", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "Response 1", session_id: "sess-123" });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "query 1{Enter}");
    await waitFor(() => { expect(screen.getByText("Response 1")).toBeInTheDocument(); });

    mockedApi.sendChat.mockResolvedValue({ message: "Response 2", session_id: "sess-123" });
    await user.type(textarea, "query 2{Enter}");
    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(expect.objectContaining({ session_id: "sess-123" }));
    });
  });

  it("renders data table in response", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Here is your data",
      data: { headers: ["Ledger", "Balance"], rows: [["Cash", 50000]] },
      session_id: "sess-1",
    });
    renderWithProvider();
    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "cash balance{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Cash")).toBeInTheDocument();
      expect(screen.getByText("Ledger")).toBeInTheDocument();
    });
  });

  it("triggers send from quick action click", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({ message: "P&L data", session_id: "sess-1" });
    renderWithProvider();
    await user.click(screen.getByRole("button", { name: "P&L last month" }));
    expect(mockedApi.sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "P&L last month" }));
  });
});
