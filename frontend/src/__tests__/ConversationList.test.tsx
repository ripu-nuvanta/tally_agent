import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConversationList from "../components/ConversationList";
import type { ConversationSummary } from "../types";

const mockConversations: ConversationSummary[] = [
  { id: "conv-1", title: "Trial Balance Query", tag: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
  { id: "conv-2", title: "P&L Analysis", tag: null, created_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
  { id: "conv-3", title: null, tag: null, created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" },
];

function renderConversationList(
  conversations = mockConversations,
  activeConversationId?: string,
  onSelect = vi.fn(),
  onNewChat = vi.fn()
) {
  return render(
    <ConversationList
      workspaceId="ws-1"
      conversations={conversations}
      activeConversationId={activeConversationId}
      onSelect={onSelect}
      onNewChat={onNewChat}
    />
  );
}

describe("ConversationList", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders conversation buttons for each conversation", () => {
    renderConversationList();
    expect(screen.getByRole("button", { name: "Trial Balance Query" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "P&L Analysis" })).toBeInTheDocument();
  });

  it("renders 'New Chat' label for conversations with no title", () => {
    renderConversationList();
    // conv-3 has null title, should show "New Chat"
    const buttons = screen.getAllByRole("button", { name: "New Chat" });
    // One from conv-3 (null title) and one from the "+ New Chat" button
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it("highlights the active conversation", () => {
    renderConversationList(mockConversations, "conv-1");
    const activeButton = screen.getByRole("button", { name: "Trial Balance Query" });
    expect(activeButton.className).toContain("bg-blue-100");
    expect(activeButton.className).toContain("text-blue-900");
  });

  it("does not highlight inactive conversations", () => {
    renderConversationList(mockConversations, "conv-1");
    const inactiveButton = screen.getByRole("button", { name: "P&L Analysis" });
    expect(inactiveButton.className).not.toContain("bg-blue-100");
  });

  it("calls onSelect with conversation id when conversation is clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderConversationList(mockConversations, undefined, onSelect);

    await user.click(screen.getByRole("button", { name: "Trial Balance Query" }));
    expect(onSelect).toHaveBeenCalledWith("conv-1", "Trial Balance Query");
  });

  it("calls onSelect with correct id for each conversation", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderConversationList(mockConversations, undefined, onSelect);

    await user.click(screen.getByRole("button", { name: "P&L Analysis" }));
    expect(onSelect).toHaveBeenCalledWith("conv-2", "P&L Analysis");
  });

  it("has a '+ New Chat' button", () => {
    renderConversationList();
    expect(screen.getByRole("button", { name: "+ New Chat" })).toBeInTheDocument();
  });

  it("calls onNewChat when '+ New Chat' is clicked", async () => {
    const onNewChat = vi.fn();
    const user = userEvent.setup();
    renderConversationList(mockConversations, undefined, vi.fn(), onNewChat);

    await user.click(screen.getByRole("button", { name: "+ New Chat" }));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("renders empty list with just the '+ New Chat' button when no conversations", () => {
    renderConversationList([]);
    expect(screen.getByRole("button", { name: "+ New Chat" })).toBeInTheDocument();
    // Only one button total
    const allButtons = screen.getAllByRole("button");
    expect(allButtons).toHaveLength(1);
  });
});
