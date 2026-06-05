import type { ConversationSummary } from "../types";

interface ConversationListProps {
  workspaceId: string;
  conversations: ConversationSummary[];
  activeConversationId?: string;
  isLandingPage?: boolean;
  onSelect: (conversationId: string, title: string | null) => void;
  onNewChat: () => void;
}

export default function ConversationList({ conversations, activeConversationId, isLandingPage, onSelect, onNewChat }: ConversationListProps) {
  return (
    <div className="space-y-0.5">
      {conversations.map((conv) => (
        <button key={conv.id} onClick={() => onSelect(conv.id, conv.title)}
          title={conv.title || "New Chat"}
          className={`w-full text-left px-2 py-1.5 rounded text-sm truncate ${
            conv.id === activeConversationId ? "bg-blue-100 text-blue-900" : "text-gray-700 hover:bg-gray-100"
          }`}>
          {conv.title || "New Chat"}
        </button>
      ))}
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
