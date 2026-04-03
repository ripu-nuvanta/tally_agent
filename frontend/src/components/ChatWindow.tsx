import { useCallback, useEffect, useRef, useState } from "react";
import { getConversation, sendChat } from "../api/client";
import { useSession } from "../context/SessionContext";
import type { ChatMessage } from "../types";
import { generateId } from "../utils/format";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import QuickActions from "./QuickActions";

interface ChatWindowProps {
  conversationId?: string;
  workspaceId?: string;
}

export default function ChatWindow({ conversationId, workspaceId }: ChatWindowProps = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sessionId, setSessionId, company } = useSession();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (conversationId && workspaceId) {
      getConversation(workspaceId, conversationId).then((conv) => {
        setMessages(
          conv.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            data: m.data,
            chart: m.chart,
          })),
        );
      });
    }
  }, [conversationId, workspaceId]);

  const handleSend = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: text,
      };

      const loadingMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "",
        isLoading: true,
      };

      setMessages((prev) => [...prev, userMsg, loadingMsg]);
      setLoading(true);

      try {
        const response = await sendChat({
          message: text,
          session_id: sessionId ?? undefined,
          company: company ?? undefined,
          workspace_id: workspaceId,
          conversation_id: conversationId,
        });

        setSessionId(response.session_id);

        const agentMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: response.message,
          data: response.data,
          chart: response.chart,
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === loadingMsg.id ? agentMsg : m))
        );
      } catch (err) {
        const errorMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content:
            err instanceof Error && err.message.includes("Network Error")
              ? "Cannot connect to the server. Please check if the backend is running."
              : "Something went wrong. Please try again.",
          isError: true,
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === loadingMsg.id ? errorMsg : m))
        );
      } finally {
        setLoading(false);
      }
    },
    [sessionId, company, setSessionId, workspaceId, conversationId]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-6">
              <div className="text-center">
                <h2 className="text-2xl font-semibold text-gray-800 mb-2">
                  TallyPrime AI Assistant
                </h2>
                <p className="text-gray-500">
                  Ask me anything about your accounting data
                </p>
              </div>
              <QuickActions onSelect={handleSend} disabled={loading} />
            </div>
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
      {messages.length > 0 && (
        <div className="max-w-3xl mx-auto w-full px-4 pb-2">
          <QuickActions onSelect={handleSend} disabled={loading} />
        </div>
      )}
      <ChatInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
