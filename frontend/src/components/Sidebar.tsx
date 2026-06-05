import { useEffect, useState } from "react";
import { getConversations, getWorkspaces } from "../api/client";
import type { ConversationSummary, WorkspaceData } from "../types";
import ConversationList from "./ConversationList";
import ConnectCompanyModal from "./ConnectCompanyModal";

interface SidebarProps {
  activeConversationId?: string;
  activeWorkspaceId?: string;
  onConversationSelect: (workspaceId: string, conversationId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>, conversationTitle?: string | null) => void;
  onNewChat: (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => void;
  refreshTrigger?: number;
  onWorkspaceResolved?: (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>, conversationTitle?: string | null) => void;
  onWorkspacesLoaded?: (count: number, firstWorkspaceId?: string) => void;
}

export default function Sidebar({ activeConversationId, activeWorkspaceId, onConversationSelect, onNewChat, refreshTrigger, onWorkspaceResolved, onWorkspacesLoaded }: SidebarProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceData[]>([]);
  const [conversations, setConversations] = useState<Record<string, ConversationSummary[]>>({});
  const [showModal, setShowModal] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    const ws = await getWorkspaces();
    setWorkspaces(ws);
    onWorkspacesLoaded?.(ws.length, ws[0]?.id);
    const convResults = await Promise.all(ws.map((w) => getConversations(w.id)));
    const convMap: Record<string, ConversationSummary[]> = {};
    ws.forEach((w, i) => { convMap[w.id] = convResults[i]; });
    setConversations(convMap);
    if (onWorkspaceResolved) {
      if (activeConversationId) {
        for (const w of ws) {
          const convs = convMap[w.id] || [];
          const matchedConv = convs.find((c) => c.id === activeConversationId);
          if (matchedConv) {
            onWorkspaceResolved(w.id, w.name, w.config as Record<string, unknown>, matchedConv.title);
            break;
          }
        }
      } else if (activeWorkspaceId) {
        // Resolve workspace name for /w/:workspaceId landing page
        const w = ws.find((w) => w.id === activeWorkspaceId);
        if (w) {
          onWorkspaceResolved(w.id, w.name, w.config as Record<string, unknown>, null);
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

  // Re-resolve workspace when activeWorkspaceId or workspaces change (e.g., navigating to /w/:workspaceId)
  useEffect(() => {
    if (!onWorkspaceResolved || !activeWorkspaceId || activeConversationId) return;
    const ws = workspaces.find((w) => w.id === activeWorkspaceId);
    if (ws) {
      onWorkspaceResolved(ws.id, ws.name, ws.config as Record<string, unknown>, null);
    }
  }, [activeWorkspaceId, workspaces]);

  return (
    <aside className="w-70 border-r border-gray-200 bg-gray-50 flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {workspaces.map((ws) => {
          const isActive = ws.id === activeWorkspaceId;
          const isCollapsed = collapsed[ws.id] && !isActive;
          const tallyCompany = ws.config?.tally_company;
          const label = typeof tallyCompany === "string" && tallyCompany ? `${tallyCompany} (${ws.name})` : ws.name;
          return (
            <div key={ws.id} className={isActive ? "bg-blue-50 rounded-lg px-1 py-0.5" : ""}>
              <button
                onClick={() => toggleCollapse(ws.id)}
                className={`w-full flex items-start justify-between text-xs uppercase tracking-wide px-2 mb-1 overflow-hidden ${
                  isActive
                    ? "font-bold text-gray-900"
                    : "font-semibold text-gray-500"
                }`}
              >
                <span className="text-left min-w-0 break-words" title={label}>{label}</span>
                <span className="text-sm text-gray-400 shrink-0">{isCollapsed ? "▸" : "▾"}</span>
              </button>
              {!isCollapsed && (
                <ConversationList workspaceId={ws.id} conversations={conversations[ws.id] || []}
                  activeConversationId={activeConversationId}
                  isLandingPage={isActive && !activeConversationId}
                  onSelect={(cid, title) => onConversationSelect(ws.id, cid, ws.name, ws.config as Record<string, unknown>, title)}
                  onNewChat={() => onNewChat(ws.id, ws.name, ws.config as Record<string, unknown>)} />
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
      {showModal && (
        <ConnectCompanyModal
          onClose={() => setShowModal(false)}
          onCreated={(ws) => {
            setShowModal(false);
            loadData();
            onNewChat(ws.id, ws.name, ws.config as Record<string, unknown>);
          }}
        />
      )}
    </aside>
  );
}
