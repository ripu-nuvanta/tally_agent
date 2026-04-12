import { useCallback, useEffect, useRef, useState } from "react";
import { createConversation, getConversation, sendChat, sendChatWithFile, voucherAction, type VoucherAction } from "../api/client";
import { useSession } from "../context/SessionContext";
import type { ChatMessage } from "../types";
import { generateId } from "../utils/format";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import QuickActions from "./QuickActions";

interface ChatWindowProps {
  conversationId?: string;
  workspaceId?: string;
  workspaceName?: string;
  onMessageSent?: () => void;
  onConversationCreated?: (convId: string) => void;
}

export default function ChatWindow({ conversationId, workspaceId, workspaceName, onMessageSent, onConversationCreated }: ChatWindowProps = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingVoucherAction, setPendingVoucherAction] = useState<{
    entryId: string;
    action: "approve" | "discard";
  } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sessionId, setSessionId, company } = useSession();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (conversationId && workspaceId) {
      getConversation(workspaceId, conversationId)
        .then((conv) => {
          setMessages(
            conv.messages.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
              data: m.data,
              chart: m.chart,
            })),
          );
        })
        .catch(() => {
          // Conversation may have been deleted or is inaccessible
          setMessages([]);
        });
    }
  }, [conversationId, workspaceId]);

  const handleSend = useCallback(
    async (text: string, file?: File) => {
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: file ? `${text || "Uploading file"} [${file.name}]` : text,
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
        let activeConvId = conversationId;

        // Deferred creation: create conversation on first send
        if (!activeConvId && workspaceId) {
          const conv = await createConversation(workspaceId);
          activeConvId = conv.id;
          onConversationCreated?.(conv.id);
        }

        const response = file
          ? await sendChatWithFile(file, text, workspaceId, activeConvId)
          : await sendChat({
              message: text,
              session_id: sessionId ?? undefined,
              company: company ?? undefined,
              workspace_id: workspaceId,
              conversation_id: activeConvId,
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
        onMessageSent?.();
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
    [sessionId, company, setSessionId, workspaceId, conversationId, onMessageSent, onConversationCreated]
  );

  const handleVoucherAction = useCallback(
    async (action: VoucherAction, entry: Record<string, unknown>) => {
      const entryId = entry.id as string;

      // Set entry status to pending (optimistic UI) and track pending action
      setPendingVoucherAction({ entryId, action: action as "approve" | "discard" });
      setMessages((prev) =>
        prev.map((m) => {
          if (!m.data || !("entries" in (m.data as Record<string, unknown>))) return m;
          const d = m.data as Record<string, unknown>;
          const entries = d.entries as Array<Record<string, unknown>>;
          const updated = entries.map((e) =>
            e.id === entryId ? { ...e, status: "pending" } : e
          );
          return { ...m, data: { ...d, entries: updated } };
        })
      );

      const loadingMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "",
        isLoading: true,
      };
      setMessages((prev) => [...prev, loadingMsg]);
      setLoading(true);

      try {
        const response = await voucherAction(
          action,
          entry,
          company ?? "",
          sessionId ?? "",
          workspaceId ?? "",
        );
        const resultMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: response.message,
          data: response.data,
        };
        setMessages((prev) =>
          prev.map((m) => (m.id === loadingMsg.id ? resultMsg : m))
        );
      } catch {
        // Revert entry status to draft on error
        setMessages((prev) =>
          prev.map((m) => {
            if (!m.data || !("entries" in (m.data as Record<string, unknown>))) return m;
            const d = m.data as Record<string, unknown>;
            const entries = d.entries as Array<Record<string, unknown>>;
            const updated = entries.map((e) =>
              e.id === entryId ? { ...e, status: "draft" } : e
            );
            return { ...m, data: { ...d, entries: updated } };
          })
        );
        const errorMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: "Failed to perform action. Please try again.",
          isError: true,
        };
        setMessages((prev) =>
          prev.map((m) => (m.id === loadingMsg.id ? errorMsg : m))
        );
      } finally {
        setLoading(false);
        setPendingVoucherAction(null);
      }
    },
    [company, sessionId, workspaceId]
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
                {workspaceName && !conversationId ? (
                  <p className="text-gray-500">
                    Connected to <strong>{workspaceName}</strong>
                  </p>
                ) : (
                  <p className="text-gray-500">
                    Ask me anything about your accounting data
                  </p>
                )}
                {!conversationId && workspaceId && (
                  <p className="text-sm text-gray-400 mt-1">
                    Type or upload to start a conversation
                  </p>
                )}
              </div>
              <QuickActions onSelect={handleSend} disabled={loading} />
            </div>
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} onVoucherAction={handleVoucherAction} pendingVoucherAction={pendingVoucherAction} />
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
