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
  onNewChat = vi.fn(),
  onRename = vi.fn(),
  onDelete = vi.fn()
) {
  return render(
    <ConversationList
      workspaceId="ws-1"
      conversations={conversations}
      activeConversationId={activeConversationId}
      onSelect={onSelect}
      onNewChat={onNewChat}
      onRename={onRename}
      onDelete={onDelete}
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

  it("conversation button has title attribute equal to its title text", () => {
    renderConversationList();
    const button = screen.getByRole("button", { name: "Trial Balance Query" });
    expect(button).toHaveAttribute("title", "Trial Balance Query");
  });

  it("conversation button with null title has title attribute 'New Chat'", () => {
    renderConversationList();
    // conv-3 has null title → displays "New Chat" → title attr should also be "New Chat"
    // Find by exact textContent "New Chat" only — excludes "+ New Chat" action button whose text differs
    const btn = screen.getAllByRole("button").find((b) => b.textContent === "New Chat");
    expect(btn).toBeDefined();
    expect(btn).toHaveAttribute("title", "New Chat");
  });

  describe("kebab menu", () => {
    it("kebab button is hidden by default (opacity-0) for non-active rows", () => {
      renderConversationList();
      const kebab = screen.getByTestId("conv-menu-btn-conv-1");
      expect(kebab.className).toContain("opacity-0");
      expect(kebab.className).toContain("group-hover:opacity-100");
    });

    it("kebab button is always visible for the active row (no opacity-0)", () => {
      renderConversationList(mockConversations, "conv-1");
      const kebab = screen.getByTestId("conv-menu-btn-conv-1");
      expect(kebab.className).not.toContain("opacity-0");
    });

    it("clicking the kebab opens the menu with Rename and Delete", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      const menu = screen.getByTestId("conv-menu-conv-1");
      expect(menu).toBeInTheDocument();
      expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
      expect(screen.getByRole("menuitem", { name: "Delete" })).toBeInTheDocument();
    });

    it("clicking the kebab does not call onSelect", async () => {
      const onSelect = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, onSelect);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      expect(onSelect).not.toHaveBeenCalled();
    });

    it("Escape closes the open menu", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      expect(screen.getByTestId("conv-menu-conv-1")).toBeInTheDocument();
      await user.keyboard("{Escape}");
      expect(screen.queryByTestId("conv-menu-conv-1")).not.toBeInTheDocument();
    });

    it("outside click closes the open menu", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      expect(screen.getByTestId("conv-menu-conv-1")).toBeInTheDocument();
      await user.click(document.body);
      expect(screen.queryByTestId("conv-menu-conv-1")).not.toBeInTheDocument();
    });
  });

  describe("rename", () => {
    it("clicking Rename shows an input prefilled with the current title", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1") as HTMLInputElement;
      expect(input).toBeInTheDocument();
      expect(input.value).toBe("Trial Balance Query");
    });

    it("Enter calls onRename with trimmed value and exits edit", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "  New Title  {Enter}");
      expect(onRename).toHaveBeenCalledWith("conv-1", "New Title");
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });

    it("Escape cancels rename without calling onRename", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "Whatever{Escape}");
      expect(onRename).not.toHaveBeenCalled();
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });

    it("empty/whitespace value + Enter does not call onRename", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "   {Enter}");
      expect(onRename).not.toHaveBeenCalled();
    });

    it("blur COMMITS the rename (calls onRename with new value) and exits edit", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "  Blurred Title  ");
      // Click elsewhere to blur the input
      await user.click(screen.getByRole("button", { name: "+ New Chat" }));
      expect(onRename).toHaveBeenCalledWith("conv-1", "Blurred Title");
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });

    it("blur with unchanged value does NOT call onRename", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      // Value is prefilled with current title "Trial Balance Query" — do not change it
      await user.click(screen.getByRole("button", { name: "+ New Chat" }));
      expect(onRename).not.toHaveBeenCalled();
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });

    it("blur with empty value does NOT call onRename", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.click(screen.getByRole("button", { name: "+ New Chat" }));
      expect(onRename).not.toHaveBeenCalled();
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });

    it("Escape never commits even though it triggers a blur", async () => {
      const onRename = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), onRename);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Rename" }));
      const input = screen.getByTestId("conv-rename-input-conv-1");
      await user.clear(input);
      await user.type(input, "Changed But Escaped{Escape}");
      expect(onRename).not.toHaveBeenCalled();
      expect(screen.queryByTestId("conv-rename-input-conv-1")).not.toBeInTheDocument();
    });
  });

  describe("popover positioning (openUp)", () => {
    it("opens the menu UPWARD (bottom-full) for the last row", async () => {
      const user = userEvent.setup();
      renderConversationList();
      // conv-3 is the last of 3 rows → openUp should be true
      await user.click(screen.getByTestId("conv-menu-btn-conv-3"));
      const menu = screen.getByTestId("conv-menu-conv-3");
      expect(menu.className).toContain("bottom-full");
      expect(menu.className).not.toContain("top-full");
    });

    it("opens the menu DOWNWARD (top-full) for the first row when 3+ rows", async () => {
      const user = userEvent.setup();
      renderConversationList();
      // conv-1 is the first of 3 rows → openUp false (index 0 < length-2)
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      const menu = screen.getByTestId("conv-menu-conv-1");
      expect(menu.className).toContain("top-full");
      expect(menu.className).not.toContain("bottom-full");
    });

    it("opens the delete-confirm UPWARD (bottom-full) for the last row", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-3"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      const dialog = screen.getByTestId("conv-delete-confirm-conv-3");
      expect(dialog.className).toContain("bottom-full");
      expect(dialog.className).not.toContain("top-full");
    });
  });

  describe("accessibility", () => {
    it("kebab button has aria-haspopup=menu and aria-expanded toggles", async () => {
      const user = userEvent.setup();
      renderConversationList();
      const kebab = screen.getByTestId("conv-menu-btn-conv-1");
      expect(kebab).toHaveAttribute("aria-haspopup", "menu");
      expect(kebab).toHaveAttribute("aria-expanded", "false");
      await user.click(kebab);
      expect(kebab).toHaveAttribute("aria-expanded", "true");
    });

    it("the open menu has role=menu and items have role=menuitem", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      const menu = screen.getByTestId("conv-menu-conv-1");
      expect(menu).toHaveAttribute("role", "menu");
      const items = screen.getAllByRole("menuitem");
      expect(items).toHaveLength(2);
    });

    it("the delete-confirm popover is an accessible dialog", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      const dialog = screen.getByTestId("conv-delete-confirm-conv-1");
      expect(dialog).toHaveAttribute("role", "dialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
      expect(dialog).toHaveAttribute("aria-label", "Confirm delete");
    });
  });

  describe("delete", () => {
    it("clicking Delete opens a confirm dialog", async () => {
      const user = userEvent.setup();
      renderConversationList();
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      const dialog = screen.getByTestId("conv-delete-confirm-conv-1");
      expect(dialog).toBeInTheDocument();
      expect(dialog).toHaveTextContent("Delete this chat? This can't be undone.");
    });

    it("Cancel closes the confirm dialog without calling onDelete", async () => {
      const onDelete = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), vi.fn(), onDelete);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByRole("button", { name: "Cancel" }));
      expect(onDelete).not.toHaveBeenCalled();
      expect(screen.queryByTestId("conv-delete-confirm-conv-1")).not.toBeInTheDocument();
    });

    it("confirming Delete calls onDelete with the conversation id", async () => {
      const onDelete = vi.fn();
      const user = userEvent.setup();
      renderConversationList(mockConversations, undefined, vi.fn(), vi.fn(), vi.fn(), onDelete);
      await user.click(screen.getByTestId("conv-menu-btn-conv-1"));
      await user.click(screen.getByRole("menuitem", { name: "Delete" }));
      await user.click(screen.getByTestId("conv-delete-confirm-btn-conv-1"));
      expect(onDelete).toHaveBeenCalledWith("conv-1");
    });
  });
});
