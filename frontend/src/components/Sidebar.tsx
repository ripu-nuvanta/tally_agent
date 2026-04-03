import { useEffect, useState } from "react";
import { getConversations, getWorkspaces } from "../api/client";
import type { ConversationSummary, WorkspaceData } from "../types";
import ConversationList from "./ConversationList";
import ConnectCompanyModal from "./ConnectCompanyModal";

interface SidebarProps {
  activeConversationId?: string;
  onConversationSelect: (workspaceId: string, conversationId: string) => void;
  onNewChat: (workspaceId: string) => void;
}

export default function Sidebar({ activeConversationId, onConversationSelect, onNewChat }: SidebarProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceData[]>([]);
  const [conversations, setConversations] = useState<Record<string, ConversationSummary[]>>({});
  const [showModal, setShowModal] = useState(false);

  const loadData = async () => {
    const ws = await getWorkspaces();
    setWorkspaces(ws);
    const convMap: Record<string, ConversationSummary[]> = {};
    for (const w of ws) {
      convMap[w.id] = await getConversations(w.id);
    }
    setConversations(convMap);
  };

  useEffect(() => { loadData(); }, []);

  return (
    <aside className="w-70 border-r border-gray-200 bg-gray-50 flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {workspaces.map((ws) => (
          <div key={ws.id}>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-2 mb-1">{ws.name}</h3>
            <ConversationList workspaceId={ws.id} conversations={conversations[ws.id] || []}
              activeConversationId={activeConversationId}
              onSelect={(cid) => onConversationSelect(ws.id, cid)}
              onNewChat={() => onNewChat(ws.id)} />
          </div>
        ))}
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
