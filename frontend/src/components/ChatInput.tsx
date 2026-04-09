import { useState, useRef, type KeyboardEvent } from "react";
import { SendHorizontal, X } from "lucide-react";
import FileAttachButton from "./FileAttachButton";

interface ChatInputProps {
  onSend: (message: string, file?: File) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed && !attachedFile) return;
    if (disabled) return;
    onSend(trimmed, attachedFile ?? undefined);
    setInput("");
    setAttachedFile(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
    }
  }

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {attachedFile && (
        <div className="max-w-3xl mx-auto mb-2">
          <div className="inline-flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 px-3 py-1.5 text-sm text-blue-700">
            <span className="truncate max-w-[200px]">{attachedFile.name}</span>
            <span className="text-blue-400">({(attachedFile.size / 1024).toFixed(0)} KB)</span>
            <button
              type="button"
              onClick={() => setAttachedFile(null)}
              className="text-blue-400 hover:text-blue-600"
              aria-label="Remove file"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <FileAttachButton
          onFileSelect={setAttachedFile}
          disabled={disabled}
        />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder={attachedFile ? "Add a note (optional)..." : "Ask about your Tally data..."}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || (!input.trim() && !attachedFile)}
          aria-label="Send message"
          className="rounded-xl bg-blue-600 p-2.5 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <SendHorizontal className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
