import { useEffect, useState } from "react";
import { getConversations, getWorkspaces } from "../api/client";
import type { ConversationSummary, WorkspaceData } from "../types";
import ConversationList from "./ConversationList";
import ConnectCompanyModal from "./ConnectCompanyModal";

interface SidebarProps {
  activeConversationId?: string;
  activeWorkspaceId?: string;
  onConversationSelect: (workspaceId: string, conversationId: string, workspaceName: string) => void;
  onNewChat: (workspaceId: string, workspaceName: string) => void;
  refreshTrigger?: number;
  onWorkspaceResolved?: (workspaceId: string, workspaceName: string) => void;
}

export default function Sidebar({ activeConversationId, activeWorkspaceId, onConversationSelect, onNewChat, refreshTrigger, onWorkspaceResolved }: SidebarProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceData[]>([]);
  const [conversations, setConversations] = useState<Record<string, ConversationSummary[]>>({});
  const [showModal, setShowModal] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    const ws = await getWorkspaces();
    setWorkspaces(ws);
    const convMap: Record<string, ConversationSummary[]> = {};
    for (const w of ws) {
      convMap[w.id] = await getConversations(w.id);
    }
    setConversations(convMap);
    if (activeConversationId && onWorkspaceResolved) {
      for (const w of ws) {
        const convs = convMap[w.id] || [];
        if (convs.some((c) => c.id === activeConversationId)) {
          onWorkspaceResolved(w.id, w.name);
          break;
        }
      }
    }
  };

  const toggleCollapse = (wsId: string) => {
    setCollapsed((prev) => ({
      ...prev,
      [wsId]: !prev[wsId],
    }));
  };

  useEffect(() => { loadData(); }, [refreshTrigger]);

  return (
    <aside className="w-70 border-r border-gray-200 bg-gray-50 flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {workspaces.map((ws) => {
          const isActive = ws.id === activeWorkspaceId;
          const isCollapsed = collapsed[ws.id] && !isActive;
          return (
            <div key={ws.id}>
              <button
                onClick={() => toggleCollapse(ws.id)}
                className={`w-full flex items-center justify-between text-xs uppercase tracking-wide px-2 mb-1 ${
                  isActive
                    ? "font-bold text-gray-900"
                    : "font-semibold text-gray-500"
                }`}
              >
                <span>{ws.name}</span>
                <span className="text-sm text-gray-400">{isCollapsed ? "▸" : "▾"}</span>
              </button>
              {!isCollapsed && (
                <ConversationList workspaceId={ws.id} conversations={conversations[ws.id] || []}
                  activeConversationId={activeConversationId}
                  onSelect={(cid) => onConversationSelect(ws.id, cid, ws.name)}
                  onNewChat={() => onNewChat(ws.id, ws.name)} />
              )}
            </div>
          );
        })}
      </div>
      <div className="border-t border-gray-200 p-3">
        <button onClick={() => setShowModal(true)}
          className="w-full text-sm text-gray-600 hover:text-gray-900 flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-100">
          + Connect Company
        </button>
      </div>
      {showModal && <ConnectCompanyModal onClose={() => setShowModal(false)} onCreated={() => { setShowModal(false); loadData(); }} />}
    </aside>
  );
}
