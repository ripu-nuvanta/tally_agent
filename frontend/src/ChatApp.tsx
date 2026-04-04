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
  const [sidebarRefresh, setSidebarRefresh] = useState(0);

  const handleConversationSelect = useCallback(
    (workspaceId: string, convId: string) => {
      setActiveWorkspaceId(workspaceId);
      navigate(`/c/${convId}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(
    async (workspaceId: string) => {
      const conv = await createConversation(workspaceId);
      setActiveWorkspaceId(workspaceId);
      navigate(`/c/${conv.id}`);
    },
    [navigate],
  );

  return (
    <div className="h-screen flex flex-col bg-white">
      <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
        </div>
        <div className="flex items-center gap-3">
          <UserMenu />
        </div>
      </header>
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeConversationId={conversationId} onConversationSelect={handleConversationSelect} onNewChat={handleNewChat} refreshTrigger={sidebarRefresh} />
        <main className="flex-1 overflow-hidden">
          <ChatWindow conversationId={conversationId} workspaceId={activeWorkspaceId || undefined} onMessageSent={() => setSidebarRefresh((n) => n + 1)} />
        </main>
      </div>
    </div>
  );
}
