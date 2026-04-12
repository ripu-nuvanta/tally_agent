import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import UserMenu from "./components/UserMenu";

export default function ChatApp() {
  const { conversationId, workspaceId: urlWorkspaceId } = useParams();
  const navigate = useNavigate();
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [activeWorkspaceName, setActiveWorkspaceName] = useState<string | null>(null);
  const [activeWorkspaceConfig, setActiveWorkspaceConfig] = useState<Record<string, unknown>>({});
  const [activeConversationTitle, setActiveConversationTitle] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Sync activeWorkspaceId from URL param when on /w/:workspaceId route
  useEffect(() => {
    if (urlWorkspaceId && urlWorkspaceId !== activeWorkspaceId) {
      setActiveWorkspaceId(urlWorkspaceId);
    }
  }, [urlWorkspaceId, activeWorkspaceId]);

  const handleConversationSelect = useCallback(
    (workspaceId: string, convId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>, convTitle?: string | null) => {
      setActiveWorkspaceId(workspaceId);
      setActiveWorkspaceName(workspaceName);
      if (workspaceConfig) setActiveWorkspaceConfig(workspaceConfig);
      setActiveConversationTitle(convTitle ?? null);
      navigate(`/c/${convId}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(
    (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => {
      setActiveWorkspaceId(workspaceId);
      setActiveWorkspaceName(workspaceName);
      if (workspaceConfig) setActiveWorkspaceConfig(workspaceConfig);
      setActiveConversationTitle(null);
      navigate(`/w/${workspaceId}`);
      setSidebarOpen(false);
    },
    [navigate],
  );

  const handleConversationCreated = useCallback(
    (convId: string) => {
      navigate(`/c/${convId}`);
      setSidebarRefresh((n) => n + 1);
    },
    [navigate],
  );

  const handleWorkspaceResolved = useCallback(
    (wsId: string, wsName: string, wsConfig?: Record<string, unknown>, convTitle?: string | null) => {
      setActiveWorkspaceId(wsId);
      setActiveWorkspaceName(wsName);
      if (wsConfig) setActiveWorkspaceConfig(wsConfig);
      setActiveConversationTitle(convTitle ?? null);
    },
    [],
  );

  return (
    <div className="h-screen flex flex-col bg-white">
      <header className="border-b border-gray-200 bg-white px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <button
            className="md:hidden p-1 rounded text-gray-600 hover:text-gray-900 hover:bg-gray-100 shrink-0"
            aria-label="Open sidebar"
            onClick={() => setSidebarOpen(true)}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <h1 className="text-lg font-semibold text-gray-900 shrink-0">TallyPrime AI</h1>
              {activeWorkspaceName && (
                <>
                  <span className="text-gray-300 shrink-0">|</span>
                  <span data-testid="header-chat-title" className={`text-lg truncate ${conversationId ? "text-gray-700" : "text-blue-600"}`}>
                    {conversationId ? (activeConversationTitle || "Chat") : "New Chat"}
                  </span>
                </>
              )}
            </div>
            {activeWorkspaceName && (
              <div className="flex items-center gap-2">
                <span data-testid="header-workspace-name" className="text-xs text-gray-500 truncate">
                  {activeWorkspaceName}
                </span>
                {activeWorkspaceConfig.mock_mode === true ? (
                  <span data-testid="header-workspace-badge" className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                    Demo
                  </span>
                ) : (
                  <span data-testid="header-workspace-badge" className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                    Live
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
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
                onConversationSelect={(ws, conv, name, config, title) => {
                  handleConversationSelect(ws, conv, name, config, title);
                  setSidebarOpen(false);
                }}
                onNewChat={(ws, name, config) => {
                  handleNewChat(ws, name, config);
                }}
                refreshTrigger={sidebarRefresh}
                onWorkspaceResolved={handleWorkspaceResolved}
              />
            </div>
          </div>
        )}

        <main className="flex-1 overflow-hidden">
          <ChatWindow conversationId={conversationId} workspaceId={activeWorkspaceId || undefined} workspaceName={activeWorkspaceName || undefined} onMessageSent={() => setSidebarRefresh((n) => n + 1)} onConversationCreated={handleConversationCreated} />
        </main>
      </div>
    </div>
  );
}
