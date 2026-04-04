import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
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

  describe("page-reload: workspace resolution after mount", () => {
    const mockConversation = {
      id: "conv-1",
      title: "Test conversation",
      tag: null,
      messages: [
        { id: "msg-1", role: "user" as const, content: "Hello", created_at: "2024-01-01T00:00:00Z" },
        { id: "msg-2", role: "assistant" as const, content: "Hi there!", created_at: "2024-01-01T00:00:01Z" },
      ],
    };

    it("loads messages immediately when both conversationId and workspaceId are provided at mount", async () => {
      mockedApi.getConversation.mockResolvedValue(mockConversation);
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument();
        expect(screen.getByText("Hi there!")).toBeInTheDocument();
      });
      expect(mockedApi.getConversation).toHaveBeenCalledWith("ws-1", "conv-1");
    });

    it("does not call getConversation when workspaceId is missing", () => {
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" />
        </SessionProvider>
      );
      expect(mockedApi.getConversation).not.toHaveBeenCalled();
    });

    it("loads messages when workspaceId is resolved after mount (page-reload scenario)", async () => {
      mockedApi.getConversation.mockResolvedValue(mockConversation);

      // Simulate page-reload: initially no workspaceId (sidebar hasn't resolved yet)
      const { rerender } = render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId={undefined} />
        </SessionProvider>
      );

      // workspaceId is undefined — getConversation should NOT be called yet
      expect(mockedApi.getConversation).not.toHaveBeenCalled();
      expect(screen.queryByText("Hello")).not.toBeInTheDocument();

      // Sidebar resolves the workspace and ChatApp sets activeWorkspaceId → workspaceId prop updates
      await act(async () => {
        rerender(
          <SessionProvider>
            <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
          </SessionProvider>
        );
      });

      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument();
        expect(screen.getByText("Hi there!")).toBeInTheDocument();
      });
      expect(mockedApi.getConversation).toHaveBeenCalledWith("ws-1", "conv-1");
    });

    it("shows empty state when getConversation returns no messages", async () => {
      mockedApi.getConversation.mockResolvedValue({ ...mockConversation, messages: [] });
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(mockedApi.getConversation).toHaveBeenCalled();
      });
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });

    it("shows empty state when getConversation fails", async () => {
      mockedApi.getConversation.mockRejectedValue(new Error("Not found"));
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" />
        </SessionProvider>
      );
      await waitFor(() => {
        expect(mockedApi.getConversation).toHaveBeenCalled();
      });
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });
  });
});
