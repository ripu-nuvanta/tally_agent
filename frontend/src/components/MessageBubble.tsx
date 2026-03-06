import ReactMarkdown from "react-markdown";
import type { ChatMessage, TableData } from "../types";
import DataTable from "./DataTable";
import ChartRenderer from "./ChartRenderer";

function stripMarkdownTables(text: string): string {
  // Remove markdown tables (lines starting with | and separator lines like |---|)
  return text
    .replace(/^\|.*\|$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function isTableData(d: unknown): d is TableData {
  return typeof d === "object" && d !== null && "headers" in d && "rows" in d;
}

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (message.isLoading) {
    return (
      <div className="flex justify-start">
        <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[85%]">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    );
  }

  // Determine tables to render
  const tables: TableData[] = [];
  if (Array.isArray(message.data)) {
    for (const d of message.data) {
      if (isTableData(d)) tables.push(d);
    }
  } else if (isTableData(message.data)) {
    tables.push(message.data);
  }

  // Strip markdown tables from text if we have structured data
  const displayContent = tables.length > 0
    ? stripMarkdownTables(message.content)
    : message.content;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] px-4 py-2.5 ${
          isUser
            ? "bg-blue-600 text-white rounded-2xl rounded-br-sm"
            : message.isError
              ? "bg-red-50 text-red-800 border border-red-200 rounded-2xl rounded-bl-sm"
              : "bg-gray-100 text-gray-900 rounded-2xl rounded-bl-sm"
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="text-sm prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0">
            <ReactMarkdown>{displayContent}</ReactMarkdown>
          </div>
        )}

        {tables.map((tableData, idx) => (
          <DataTable key={idx} data={tableData} />
        ))}
        {message.chart && <ChartRenderer chart={message.chart} />}
      </div>
    </div>
  );
}
