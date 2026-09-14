import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, TableData } from "../types";
import type { VoucherAction } from "../api/client";
import DataTable from "./DataTable";
import ChartRenderer from "./ChartRenderer";
import VoucherReviewCard, { type VoucherEntry } from "./VoucherReviewCard";

function hasMarkdownTable(text: string): boolean {
  // Check if text contains a markdown pipe table (at least a header + separator row)
  return /\|.+\|[\r\n]+\|[-:\s|]+\|/m.test(text);
}

function isTableData(d: unknown): d is TableData {
  return typeof d === "object" && d !== null && "headers" in d && "rows" in d;
}

interface MessageBubbleProps {
  message: ChatMessage;
  onVoucherAction?: (action: VoucherAction, entry: Record<string, unknown>) => void;
  // Edit-save: a PURELY LOCAL merge of edited fields into the entry (keeps it a
  // draft). Distinct from onVoucherAction, which round-trips to the backend and
  // would perform a premature write if used for Save.
  onVoucherEdit?: (entryId: string, updates: Partial<VoucherEntry>) => void;
  pendingVoucherAction?: { entryId: string; action: "approve" | "discard" } | null;
}

export default function MessageBubble({ message, onVoucherAction, onVoucherEdit, pendingVoucherAction }: MessageBubbleProps) {
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

  // Detect voucher review data (Set B1)
  const voucherData =
    message.data !== null &&
    message.data !== undefined &&
    typeof message.data === "object" &&
    !Array.isArray(message.data) &&
    (message.data as unknown as Record<string, unknown>).type === "voucher_review"
      ? (message.data as unknown as Record<string, unknown>)
      : null;
  const isVoucherReview = voucherData !== null;

  // Determine tables to render
  const tables: TableData[] = [];
  if (!isVoucherReview) {
    if (Array.isArray(message.data)) {
      for (const d of message.data) {
        if (isTableData(d)) tables.push(d);
      }
    } else if (isTableData(message.data)) {
      tables.push(message.data);
    }
  }

  // If message has markdown tables, render them inline (don't strip).
  // Only use DataTable as fallback when structured data exists but no markdown table in text.
  const textHasTable = hasMarkdownTable(message.content);
  const showDataTableFallback = tables.length > 0 && !textHasTable;

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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="min-w-full text-xs border-collapse border border-gray-200">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-50">{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2 text-left font-semibold text-gray-700 border border-gray-200">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-gray-600 border border-gray-200">
                    {children}
                  </td>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Voucher review card (Set B1) */}
        {voucherData && (() => {
          const entries = (voucherData.entries as VoucherEntry[]) || [];
          return (
            <VoucherReviewCard
              entries={entries}
              availableLedgers={(voucherData.available_ledgers as string[]) || []}
              availablePaymentLedgers={(voucherData.available_payment_ledgers as string[]) || []}
              availableSupplierLedgers={(voucherData.available_supplier_ledgers as string[]) || []}
              availableCustomerLedgers={(voucherData.available_customer_ledgers as string[]) || []}
              pendingAction={pendingVoucherAction}
              onApprove={(id) => {
                const entry = entries.find((e) => e.id === id);
                if (entry && onVoucherAction) {
                  onVoucherAction("approve", entry as unknown as Record<string, unknown>);
                }
              }}
              onDiscard={(id) => {
                const entry = entries.find((e) => e.id === id);
                if (entry && onVoucherAction) {
                  onVoucherAction("discard", entry as unknown as Record<string, unknown>);
                }
              }}
              onEdit={(id, updates) => {
                // Save is a LOCAL state merge — never a backend write. The user
                // writes later via "Write to Tally".
                if (onVoucherEdit) {
                  onVoucherEdit(id, updates);
                }
              }}
            />
          );
        })()}

        {/* Fallback: render DataTable only if structured data exists but no markdown table in text */}
        {!isVoucherReview && showDataTableFallback && tables.map((tableData, idx) => (
          <DataTable key={idx} data={tableData} />
        ))}
        {message.chart && <ChartRenderer chart={message.chart} />}
      </div>
    </div>
  );
}
