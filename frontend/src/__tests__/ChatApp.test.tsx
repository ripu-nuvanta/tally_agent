import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ChatApp from "../ChatApp";

vi.mock("../api/client");
vi.mock("../context/AuthContext");

const mockedClient = vi.mocked(await import("../api/client"));
const mockedAuth = vi.mocked(await import("../context/AuthContext"));

// Silence scrollIntoView in jsdom
Element.prototype.scrollIntoView = vi.fn();

const mockUser = { id: "user-1", email: "test@example.com", name: "Test User" };

const mockWorkspace = {
  id: "ws-1",
  name: "Bharat Traders",
  agent_type: "tally",
  config: {},
  memory: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockConversation = {
  id: "conv-1",
  title: "Trial Balance",
  tag: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockConversationDetail = {
  id: "conv-1",
  title: "Trial Balance",
  tag: null,
  messages: [
    { id: "msg-1", role: "user" as const, content: "Show trial balance", created_at: "2026-01-01T00:00:00Z" },
    { id: "msg-2", role: "assistant" as const, content: "Here is the trial balance", created_at: "2026-01-01T00:00:01Z" },
  ],
};

function setupAuthMock(user = mockUser) {
  mockedAuth.useAuth.mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  });
}

function renderChatApp(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<ChatApp />} />
        <Route path="/c/:conversationId" element={<ChatApp />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ChatApp", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setupAuthMock();
    mockedClient.getWorkspaces.mockResolvedValue([mockWorkspace]);
    mockedClient.getConversations.mockResolvedValue([mockConversation]);
    mockedClient.getConversation.mockResolvedValue(mockConversationDetail);
  });

  it("renders the header with TallyPrime AI title", async () => {
    renderChatApp();
    await waitFor(() => {
      expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    });
  });

  it("renders sidebar with workspace name", async () => {
    renderChatApp();
    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });
  });

  it("shows workspace name in header when workspace is active", async () => {
    // Render with an existing conversation so workspace gets resolved
    mockedClient.getWorkspaces.mockResolvedValue([mockWorkspace]);
    mockedClient.getConversations.mockResolvedValue([mockConversation]);

    renderChatApp("/c/conv-1");

    await waitFor(() => {
      // "Bharat Traders" appears in both the sidebar and header when workspace resolves
      const matches = screen.getAllByText("Bharat Traders");
      expect(matches.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("navigates to new conversation URL when New Chat is clicked", async () => {
    const newConv = { id: "conv-new", title: null, tag: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
    mockedClient.createConversation.mockResolvedValue(newConv);

    const user = userEvent.setup();
    renderChatApp();

    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });

    // Click the "+ New Chat" button inside the ConversationList
    const newChatBtn = screen.getByRole("button", { name: "+ New Chat" });
    await user.click(newChatBtn);

    await waitFor(() => {
      expect(mockedClient.createConversation).toHaveBeenCalledWith("ws-1");
    });
  });

  it("shows empty chat window when no workspaces are available", async () => {
    mockedClient.getWorkspaces.mockResolvedValue([]);
    mockedClient.getConversations.mockResolvedValue([]);

    renderChatApp();

    await waitFor(() => {
      // No workspace names should appear
      expect(screen.queryByText("Bharat Traders")).not.toBeInTheDocument();
    });

    // The Connect Company button should be visible
    expect(screen.getByRole("button", { name: "+ Connect Company" })).toBeInTheDocument();
  });

  it("sidebar container has hidden md:flex classes for responsive layout", async () => {
    renderChatApp();

    await waitFor(() => {
      expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    });

    // The desktop sidebar wrapper should have hidden md:flex classes
    const desktopSidebarWrapper = document.querySelector(".hidden.md\\:flex");
    expect(desktopSidebarWrapper).toBeInTheDocument();
  });

  it("hamburger button has md:hidden class and is present in the DOM", async () => {
    renderChatApp();

    await waitFor(() => {
      expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    });

    // Hamburger button should exist and have md:hidden class
    const hamburger = screen.getByRole("button", { name: /open sidebar/i });
    expect(hamburger).toBeInTheDocument();
    expect(hamburger.className).toContain("md:hidden");
  });

  it("clicking hamburger opens mobile drawer overlay", async () => {
    const user = userEvent.setup();
    renderChatApp();

    await waitFor(() => {
      expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    });

    // Drawer should not be visible initially
    expect(document.querySelector(".fixed.inset-0.z-40")).not.toBeInTheDocument();

    // Click hamburger
    const hamburger = screen.getByRole("button", { name: /open sidebar/i });
    await user.click(hamburger);

    // Drawer overlay should appear
    expect(document.querySelector(".fixed.inset-0.z-40")).toBeInTheDocument();
  });

  it("clicking backdrop closes mobile drawer", async () => {
    const user = userEvent.setup();
    renderChatApp();

    await waitFor(() => {
      expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    });

    // Open drawer
    const hamburger = screen.getByRole("button", { name: /open sidebar/i });
    await user.click(hamburger);

    expect(document.querySelector(".fixed.inset-0.z-40")).toBeInTheDocument();

    // Click backdrop
    const backdrop = document.querySelector(".bg-black\\/50") as HTMLElement;
    expect(backdrop).toBeInTheDocument();
    await user.click(backdrop);

    // Drawer should close
    expect(document.querySelector(".fixed.inset-0.z-40")).not.toBeInTheDocument();
  });
});
