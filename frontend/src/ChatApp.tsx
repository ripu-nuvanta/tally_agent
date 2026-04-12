import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createConversation } from "./api/client";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import UserMenu from "./components/UserMenu";

export default function ChatApp() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [activeWorkspaceName, setActiveWorkspaceName] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleConversationSelect = useCallback(
    (workspaceId: string, convId: string, workspaceName: string) => {
      setActiveWorkspaceId(workspaceId);
      setActiveWorkspaceName(workspaceName);
      navigate(`/c/${convId}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(
    async (workspaceId: string, workspaceName: string) => {
      const conv = await createConversation(workspaceId);
      setActiveWorkspaceId(workspaceId);
      setActiveWorkspaceName(workspaceName);
      navigate(`/c/${conv.id}`);
    },
    [navigate],
  );

  const handleWorkspaceResolved = useCallback(
    (wsId: string, wsName: string) => {
      if (!activeWorkspaceId) {
        setActiveWorkspaceId(wsId);
        setActiveWorkspaceName(wsName);
      }
    },
    [activeWorkspaceId],
  );

  return (
    <div className="h-screen flex flex-col bg-white">
      <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            className="md:hidden p-1 rounded text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            aria-label="Open sidebar"
            onClick={() => setSidebarOpen(true)}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
          {activeWorkspaceName && (
            <span className="text-sm text-gray-500 border-l border-gray-200 pl-3">{activeWorkspaceName}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <UserMenu />
        </div>
      </header>
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop sidebar — always visible at md+ */}
        <div className="hidden md:flex">
          <Sidebar
            activeConversationId={conversationId}
            activeWorkspaceId={activeWorkspaceId || undefined}
            onConversationSelect={handleConversationSelect}
            onNewChat={handleNewChat}
            refreshTrigger={sidebarRefresh}
            onWorkspaceResolved={handleWorkspaceResolved}
          />
        </div>

        {/* Mobile drawer overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div
              className="fixed inset-0 bg-black/50"
              onClick={() => setSidebarOpen(false)}
              aria-hidden="true"
            />
            <div className="fixed inset-y-0 left-0 w-72 bg-white shadow-xl z-50">
              <Sidebar
                activeConversationId={conversationId}
                activeWorkspaceId={activeWorkspaceId || undefined}
                onConversationSelect={(ws, conv, name) => {
                  handleConversationSelect(ws, conv, name);
                  setSidebarOpen(false);
                }}
                onNewChat={async (ws, name) => {
                  await handleNewChat(ws, name);
                  setSidebarOpen(false);
                }}
                refreshTrigger={sidebarRefresh}
                onWorkspaceResolved={handleWorkspaceResolved}
              />
            </div>
          </div>
        )}

        <main className="flex-1 overflow-hidden">
          <ChatWindow conversationId={conversationId} workspaceId={activeWorkspaceId || undefined} onMessageSent={() => setSidebarRefresh((n) => n + 1)} />
        </main>
      </div>
    </div>
  );
}
