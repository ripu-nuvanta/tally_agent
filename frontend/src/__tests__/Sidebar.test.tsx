import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Sidebar from "../components/Sidebar";
import type { ConversationSummary, WorkspaceData } from "../types";

vi.mock("../api/client");

const mockedClient = vi.mocked(await import("../api/client"));

const mockWorkspaces: WorkspaceData[] = [
  { id: "ws-1", name: "Bharat Traders", agent_type: "tally", config: {}, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  { id: "ws-2", name: "Nuvanta Co", agent_type: "tally", config: {}, memory: {}, created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
];

const mockConversationsWs1: ConversationSummary[] = [
  { id: "conv-1", title: "Trial Balance", tag: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  { id: "conv-2", title: "P&L Analysis", tag: null, created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
];

const mockConversationsWs2: ConversationSummary[] = [
  { id: "conv-3", title: "Cash Flow", tag: null, created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" },
];

function renderSidebar(
  props: Partial<React.ComponentProps<typeof Sidebar>> = {}
) {
  return render(
    <Sidebar
      onConversationSelect={vi.fn()}
      onNewChat={vi.fn()}
      {...props}
    />
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedClient.getWorkspaces.mockResolvedValue(mockWorkspaces);
    mockedClient.getConversations.mockImplementation((wsId: string) => {
      if (wsId === "ws-1") return Promise.resolve(mockConversationsWs1);
      if (wsId === "ws-2") return Promise.resolve(mockConversationsWs2);
      return Promise.resolve([]);
    });
  });

  it("renders workspace names from API", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
      expect(screen.getByText("Nuvanta Co")).toBeInTheDocument();
    });
  });

  it("renders conversations under each workspace", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "P&L Analysis" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cash Flow" })).toBeInTheDocument();
    });
  });

  it("highlights the active conversation", async () => {
    renderSidebar({ activeConversationId: "conv-1" });
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: "Trial Balance" });
      expect(btn.className).toContain("bg-blue-100");
    });
  });

  it("renders Connect Company button", async () => {
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "+ Connect Company" })).toBeInTheDocument();
    });
  });

  it("renders empty state with only Connect Company button when no workspaces", async () => {
    mockedClient.getWorkspaces.mockResolvedValue([]);
    renderSidebar();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "+ Connect Company" })).toBeInTheDocument();
    });
    // No workspace names
    expect(screen.queryByText("Bharat Traders")).not.toBeInTheDocument();
  });

  it("toggles workspace collapse when workspace header is clicked", async () => {
    const user = userEvent.setup();
    renderSidebar({ activeWorkspaceId: undefined });

    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });

    // Conversations visible initially
    expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();

    // Click to collapse workspace
    const wsButton = screen.getByRole("button", { name: /Bharat Traders/ });
    await user.click(wsButton);

    // Conversations should be hidden
    expect(screen.queryByRole("button", { name: "Trial Balance" })).not.toBeInTheDocument();
  });

  it("test_active_workspace_has_highlight_class — active workspace container has bg-blue-50", async () => {
    const { container } = renderSidebar({ activeWorkspaceId: "ws-1" });
    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });
    // The active workspace wrapper div should have bg-blue-50
    const highlighted = container.querySelector(".bg-blue-50");
    expect(highlighted).not.toBeNull();
  });

  it("test_inactive_workspace_no_highlight — inactive workspaces do not have bg-blue-50", async () => {
    const { container } = renderSidebar({ activeWorkspaceId: "ws-1" });
    await waitFor(() => {
      expect(screen.getByText("Nuvanta Co")).toBeInTheDocument();
    });
    const allHighlighted = container.querySelectorAll(".bg-blue-50");
    // Only one workspace should be highlighted (ws-1, not ws-2)
    expect(allHighlighted).toHaveLength(1);
  });

  it("highlights '+ New Chat' button when on landing page (no activeConversationId)", async () => {
    renderSidebar({ activeWorkspaceId: "ws-1" });
    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });
    // The "+ New Chat" button for the active workspace should be highlighted
    const newChatBtns = screen.getAllByRole("button", { name: "+ New Chat" });
    // First workspace (ws-1) is active — its "+ New Chat" should be highlighted
    const ws1NewChat = newChatBtns[0];
    expect(ws1NewChat.getAttribute("data-testid")).toBe("sidebar-new-chat-active");
    expect(ws1NewChat.className).toContain("bg-blue-100");
    expect(ws1NewChat.className).toContain("text-blue-700");

    // Second workspace (ws-2) is not active — its "+ New Chat" should not be highlighted
    const ws2NewChat = newChatBtns[1];
    expect(ws2NewChat.getAttribute("data-testid")).toBe("sidebar-new-chat");
    expect(ws2NewChat.className).not.toContain("bg-blue-100");
  });

  it("opens ConnectCompanyModal when Connect Company button is clicked", async () => {
    const user = userEvent.setup();
    renderSidebar();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "+ Connect Company" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "+ Connect Company" }));

    await waitFor(() => {
      expect(screen.getByText("Connect Tally Company")).toBeInTheDocument();
    });
  });

  describe("workspace label with tally_company", () => {
    const wsWithCompany: WorkspaceData[] = [
      { id: "ws-1", name: "Hey", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      { id: "ws-2", name: "Nuvanta Co", agent_type: "tally", config: {}, memory: {}, created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
      { id: "ws-3", name: "Legacy Books", agent_type: "tally", config: { tally_company: "" }, memory: {}, created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" },
    ];

    beforeEach(() => {
      mockedClient.getWorkspaces.mockResolvedValue(wsWithCompany);
      mockedClient.getConversations.mockResolvedValue([]);
    });

    it("shows actual company name with friendly name in parentheses", async () => {
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Bharat Traders Private Limited (Hey)")).toBeInTheDocument();
      });
    });

    it("shows company with nickname in parentheses when they differ", async () => {
      mockedClient.getWorkspaces.mockResolvedValue([
        { id: "ws-1", name: "My Books", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ]);
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Bharat Traders Private Limited (My Books)")).toBeInTheDocument();
      });
    });

    it("shows only the company name (no duplication) when name equals company", async () => {
      mockedClient.getWorkspaces.mockResolvedValue([
        { id: "ws-1", name: "Bharat Traders Private Limited", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ]);
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Bharat Traders Private Limited")).toBeInTheDocument();
      });
      expect(
        screen.queryByText("Bharat Traders Private Limited (Bharat Traders Private Limited)"),
      ).not.toBeInTheDocument();
    });

    it("shows only the company name when name differs only by case/whitespace", async () => {
      mockedClient.getWorkspaces.mockResolvedValue([
        { id: "ws-1", name: "  bharat traders private limited  ", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" }, memory: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
      ]);
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Bharat Traders Private Limited")).toBeInTheDocument();
      });
    });

    it("falls back to friendly name when tally_company is missing", async () => {
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Nuvanta Co")).toBeInTheDocument();
      });
    });

    it("falls back to friendly name when tally_company is empty string", async () => {
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByText("Legacy Books")).toBeInTheDocument();
      });
    });

    it("wraps long labels (no truncate class) and keeps full label in title attr", async () => {
      renderSidebar();
      await waitFor(() => {
        const label = screen.getByText("Bharat Traders Private Limited (Hey)");
        expect(label).toHaveAttribute("title", "Bharat Traders Private Limited (Hey)");
        expect(label.className).not.toContain("truncate");
        expect(label.className).toContain("break-words");
      });
    });
  });

  it("calls onNewChat with the new workspace after completing the connect flow", async () => {
    mockedClient.testConnection.mockResolvedValue({
      connected: true,
      companies: ["Bharat Traders Pvt Ltd"],
    });
    mockedClient.createWorkspace.mockResolvedValue({
      id: "ws-1",
      name: "Bharat Traders Pvt Ltd",
      agent_type: "tally",
      config: {},
      memory: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    const onNewChat = vi.fn();
    const user = userEvent.setup();
    renderSidebar({ onNewChat });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "+ Connect Company" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "+ Connect Company" }));

    await waitFor(() => {
      expect(screen.getByText("Connect Tally Company")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Check Connection" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create Workspace" })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "Create Workspace" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Start chat" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Start chat" }));

    expect(onNewChat).toHaveBeenCalledWith("ws-1", "Bharat Traders Pvt Ltd", {});
  });

  describe("conversation rename + delete", () => {
    it("handleDelete removes the conversation from the rendered list", async () => {
      mockedClient.deleteConversation.mockResolvedValue(undefined);
      const user = userEvent.setup();
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByTestId("conv-delete-confirm-btn-conv-1"));

      await waitFor(() => {
        expect(screen.queryByRole("button", { name: "Trial Balance" })).not.toBeInTheDocument();
      });
      expect(mockedClient.deleteConversation).toHaveBeenCalledWith("ws-1", "conv-1");
    });

    it("calls onActiveConversationDeleted with the workspace id when the deleted conversation is active", async () => {
      mockedClient.deleteConversation.mockResolvedValue(undefined);
      const onActiveConversationDeleted = vi.fn();
      const user = userEvent.setup();
      renderSidebar({ activeConversationId: "conv-1", onActiveConversationDeleted });
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByTestId("conv-delete-confirm-btn-conv-1"));

      await waitFor(() => {
        expect(onActiveConversationDeleted).toHaveBeenCalledWith("ws-1");
      });
    });

    it("does not call onActiveConversationDeleted when the deleted conversation is not active", async () => {
      mockedClient.deleteConversation.mockResolvedValue(undefined);
      const onActiveConversationDeleted = vi.fn();
      const user = userEvent.setup();
      renderSidebar({ activeConversationId: "conv-2", onActiveConversationDeleted });
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByTestId("conv-delete-confirm-btn-conv-1"));

      await waitFor(() => {
        expect(screen.queryByRole("button", { name: "Trial Balance" })).not.toBeInTheDocument();
      });
      expect(onActiveConversationDeleted).not.toHaveBeenCalled();
    });

    it("handleRename updates the displayed title", async () => {
      mockedClient.updateConversation.mockResolvedValue({
        id: "conv-1", title: "Renamed Chat", tag: null,
        created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
      });
      const user = userEvent.setup();
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "Renamed Chat{Enter}");

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Renamed Chat" })).toBeInTheDocument();
      });
      expect(mockedClient.updateConversation).toHaveBeenCalledWith("ws-1", "conv-1", { title: "Renamed Chat" });
    });

    it("re-invokes loadData (getConversations) when deleteConversation rejects", async () => {
      mockedClient.deleteConversation.mockRejectedValue(new Error("boom"));
      const user = userEvent.setup();
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });
      const callsBefore = mockedClient.getConversations.mock.calls.length;

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByTestId("conv-delete-confirm-btn-conv-1"));

      await waitFor(() => {
        expect(mockedClient.getConversations.mock.calls.length).toBeGreaterThan(callsBefore);
      });
      // Item restored
      expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
    });

    it("re-invokes loadData (getConversations) when updateConversation rejects", async () => {
      mockedClient.updateConversation.mockRejectedValue(new Error("boom"));
      const user = userEvent.setup();
      renderSidebar();
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Trial Balance" })).toBeInTheDocument();
      });
      const callsBefore = mockedClient.getConversations.mock.calls.length;

      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "Renamed Chat{Enter}");

      await waitFor(() => {
        expect(mockedClient.getConversations.mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });
  });
});
