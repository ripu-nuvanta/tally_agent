import { useEffect, useRef, useState } from "react";
import type { ConversationSummary } from "../types";

interface ConversationListProps {
  workspaceId: string;
  conversations: ConversationSummary[];
  activeConversationId?: string;
  isLandingPage?: boolean;
  onSelect: (conversationId: string, title: string | null) => void;
  onNewChat: () => void;
  onRename: (conversationId: string, title: string) => void;
  onDelete: (conversationId: string) => void;
}

export default function ConversationList({ conversations, activeConversationId, isLandingPage, onSelect, onNewChat, onRename, onDelete }: ConversationListProps) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cancelledRef = useRef(false);

  const closeMenu = () => {
    setOpenMenuId(null);
    setConfirmDeleteId(null);
  };

  // Close menu/confirm on Escape and outside-click (only when a menu/confirm is open).
  useEffect(() => {
    if (!openMenuId && !confirmDeleteId) return;
    const onMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenu();
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openMenuId, confirmDeleteId]);

  const startRename = (conv: ConversationSummary) => {
    cancelledRef.current = false;
    setRenamingId(conv.id);
    setRenameValue(conv.title || "");
    setOpenMenuId(null);
  };

  const commitRename = (id: string, currentTitle: string | null) => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== (currentTitle || "")) onRename(id, trimmed);
    setRenamingId(null);
  };

  const cancelRename = () => {
    cancelledRef.current = true;
    setRenamingId(null);
  };

  return (
    <div className="space-y-0.5" ref={containerRef}>
      {conversations.map((conv, i) => {
        const openUp = conversations.length > 2 && i >= conversations.length - 2;
        return (
        <div key={conv.id} className="relative group">
          {renamingId === conv.id ? (
            <input
              data-testid={`conv-rename-input-${conv.id}`}
              autoFocus
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename(conv.id, conv.title);
                else if (e.key === "Escape") {
                  cancelledRef.current = true;
                  e.currentTarget.blur();
                }
              }}
              onBlur={() => {
                if (cancelledRef.current) {
                  cancelRename();
                } else {
                  commitRename(conv.id, conv.title);
                }
              }}
              className="w-full px-2 py-1.5 rounded text-sm border border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          ) : (
            <>
              <button onClick={() => onSelect(conv.id, conv.title)}
                title={conv.title || "New Chat"}
                className={`w-full text-left pl-2 pr-8 py-1.5 rounded text-sm truncate ${
                  conv.id === activeConversationId ? "bg-blue-100 text-blue-900" : "text-gray-700 hover:bg-gray-100"
                }`}>
                {conv.title || "New Chat"}
              </button>
              <button
                data-testid={`conv-menu-btn-${conv.id}`}
                aria-label="Conversation options"
                aria-haspopup="menu"
                aria-expanded={openMenuId === conv.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmDeleteId(null);
                  setOpenMenuId((prev) => (prev === conv.id ? null : conv.id));
                }}
                className={`absolute right-1 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded text-gray-500 hover:bg-gray-200 ${
                  conv.id === activeConversationId ? "" : "opacity-0 group-hover:opacity-100"
                }`}>
                ⋯
              </button>
            </>
          )}

          {openMenuId === conv.id && (
            <div data-testid={`conv-menu-${conv.id}`}
              role="menu"
              className={`absolute right-1 z-10 w-32 rounded-md border border-gray-200 bg-white py-1 shadow-lg ${
                openUp ? "bottom-full mb-1" : "top-full mt-0.5"
              }`}>
              <button role="menuitem" onClick={() => startRename(conv)}
                className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100">
                Rename
              </button>
              <button role="menuitem" onClick={() => setConfirmDeleteId(conv.id)}
                className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-gray-100">
                Delete
              </button>
            </div>
          )}

          {confirmDeleteId === conv.id && (
            <div data-testid={`conv-delete-confirm-${conv.id}`}
              role="dialog"
              aria-modal="true"
              aria-label="Confirm delete"
              className={`absolute right-1 z-20 w-56 rounded-md border border-gray-200 bg-white p-3 shadow-lg ${
                openUp ? "bottom-full mb-1" : "top-full mt-0.5"
              }`}>
              <p className="text-sm text-gray-700 mb-2">Delete this chat? This can't be undone.</p>
              <div className="flex justify-end gap-2">
                <button onClick={() => setConfirmDeleteId(null)}
                  className="px-2 py-1 text-sm text-gray-600 rounded hover:bg-gray-100">
                  Cancel
                </button>
                <button
                  data-testid={`conv-delete-confirm-btn-${conv.id}`}
                  onClick={() => { onDelete(conv.id); closeMenu(); }}
                  className="px-2 py-1 text-sm text-white bg-red-600 rounded hover:bg-red-700">
                  Delete
                </button>
              </div>
            </div>
          )}
        </div>
        );
      })}
      <button onClick={onNewChat}
        data-testid={isLandingPage ? "sidebar-new-chat-active" : "sidebar-new-chat"}
        className={`w-full text-left px-2 py-1.5 rounded text-sm ${
          isLandingPage ? "bg-blue-100 text-blue-700 font-medium" : "text-gray-500 hover:bg-gray-100"
        }`}>
        + New Chat
      </button>
    </div>
  );
}
