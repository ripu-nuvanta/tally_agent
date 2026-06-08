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

  describe("workspace landing page (Task 5)", () => {
    it("shows workspace name when workspaceName is provided without conversationId", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
      expect(screen.getByText(/Connected to/)).toBeInTheDocument();
    });

    it("shows hint text on landing page", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByText("Type or upload to start a conversation")).toBeInTheDocument();
    });

    it("shows quick action buttons on landing page", () => {
      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.getByRole("button", { name: "Cash balance" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Top 10 customers" })).toBeInTheDocument();
    });

    it("does not show hint text when conversationId is set", () => {
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [],
      });
      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" workspaceName="Bharat Traders" />
        </SessionProvider>
      );
      expect(screen.queryByText("Type or upload to start a conversation")).not.toBeInTheDocument();
    });
  });

  describe("deferred conversation creation (Task 6)", () => {
    it("creates conversation on first send when no conversationId", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-new", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Show trial balance{Enter}");

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalledWith(
          expect.objectContaining({ conversation_id: "conv-new" }),
        );
      });
      expect(onCreated).toHaveBeenCalledWith("conv-new");
    });

    it("does not create conversation when conversationId is already set", async () => {
      const user = userEvent.setup();
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [],
      });
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow conversationId="conv-1" workspaceId="ws-1" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Show trial balance{Enter}");

      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalled();
      });
      expect(mockedApi.createConversation).not.toHaveBeenCalled();
      expect(onCreated).not.toHaveBeenCalled();
    });

    it("quick action triggers deferred creation", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-qa", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      mockedApi.sendChat.mockResolvedValue({ message: "P&L data", session_id: "sess-1" });
      const onCreated = vi.fn();

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" onConversationCreated={onCreated} />
        </SessionProvider>
      );

      await user.click(screen.getByRole("button", { name: "P&L last month" }));

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });
      await waitFor(() => {
        expect(mockedApi.sendChat).toHaveBeenCalledWith(
          expect.objectContaining({ conversation_id: "conv-qa" }),
        );
      });
      expect(onCreated).toHaveBeenCalledWith("conv-qa");
    });

    it("does not clobber optimistic messages when first send creates the conversation", async () => {
      const user = userEvent.setup();
      const newConv = { id: "conv-new", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockResolvedValue(newConv);
      // Server hasn't persisted the optimistic messages yet
      mockedApi.getConversation.mockResolvedValue({ id: "conv-new", title: null, tag: null, messages: [] });
      mockedApi.sendChat.mockResolvedValue({ message: "Reply A", session_id: "s1" });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" />);

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "First question{Enter}");

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
      });

      // Simulate parent navigation to /c/:id after creation
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-1" conversationId="conv-new" />);
      });

      // The ref guard should prevent getConversation from wiping optimistic state
      await waitFor(() => {
        expect(screen.getByText("Reply A")).toBeInTheDocument();
      });
      expect(screen.getByText("First question")).toBeInTheDocument();
    });

    it("does not clear optimistic messages when workspaceId changes mid-send", async () => {
      const user = userEvent.setup();
      // createConversation never resolves → the send stays in flight and
      // conversationId remains undefined for the whole test window.
      mockedApi.createConversation.mockReturnValue(new Promise(() => {}));
      mockedApi.getConversation.mockResolvedValue({ id: "conv-x", title: null, tag: null, messages: [] });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" />);

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      await user.type(textarea, "Mid-send question{Enter}");

      // Optimistic user message is rendered while the send is in flight.
      expect(screen.getByText("Mid-send question")).toBeInTheDocument();

      // workspaceId changes mid-send (conversationId still undefined). The
      // load-effect re-runs and would hit the clear branch — but the
      // sendingRef guard must skip it so the optimistic message survives.
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-2" />);
      });

      expect(screen.getByText("Mid-send question")).toBeInTheDocument();
    });

    it("clears messages when navigating to the new-chat landing page", async () => {
      mockedApi.getConversation.mockResolvedValue({
        id: "conv-1",
        title: "Test",
        tag: null,
        messages: [
          { id: "m1", role: "user" as const, content: "old question", created_at: "2026-01-01T00:00:00Z" },
          { id: "m2", role: "assistant" as const, content: "old answer", created_at: "2026-01-01T00:00:01Z" },
        ],
      });

      function Wrapper(props: { conversationId?: string; workspaceId?: string }) {
        return (
          <SessionProvider>
            <ChatWindow {...props} />
          </SessionProvider>
        );
      }

      const { rerender } = render(<Wrapper workspaceId="ws-1" conversationId="conv-1" />);

      await waitFor(() => {
        expect(screen.getByText("old answer")).toBeInTheDocument();
      });

      // Navigate to new-chat landing page (conversationId becomes undefined)
      await act(async () => {
        rerender(<Wrapper workspaceId="ws-1" conversationId={undefined} />);
      });

      await waitFor(() => {
        expect(screen.queryByText("old question")).not.toBeInTheDocument();
      });
      expect(screen.queryByText("old answer")).not.toBeInTheDocument();
      expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    });

    it("loading prevents double creation on rapid sends", async () => {
      const user = userEvent.setup();
      // Make createConversation slow so we can test double-send prevention
      const newConv = { id: "conv-once", title: null, tag: null, created_at: "2026-01-01", updated_at: "2026-01-01" };
      mockedApi.createConversation.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(newConv), 100))
      );
      mockedApi.sendChat.mockResolvedValue({ message: "Response", session_id: "sess-1" });

      render(
        <SessionProvider>
          <ChatWindow workspaceId="ws-1" workspaceName="Test" />
        </SessionProvider>
      );

      const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
      // First send
      await user.type(textarea, "Query 1{Enter}");

      // The loading state should disable the send button, preventing second send
      // The send button should be disabled while loading
      const sendButton = screen.getByRole("button", { name: "Send message" });
      expect(sendButton).toBeDisabled();

      await waitFor(() => {
        expect(mockedApi.createConversation).toHaveBeenCalledTimes(1);
      });
    });
  });
});
