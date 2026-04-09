import { useRef } from "react";
import { Paperclip } from "lucide-react";

const ACCEPTED_TYPES = ".jpg,.jpeg,.png,.heic,.pdf,.csv,.xlsx,.xls";

interface FileAttachButtonProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export default function FileAttachButton({ onFileSelect, disabled }: FileAttachButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleClick() {
    inputRef.current?.click();
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
      // Reset so the same file can be selected again
      e.target.value = "";
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        onChange={handleChange}
        className="hidden"
        data-testid="file-input"
      />
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        aria-label="Attach file"
        title="Attach expense receipt, invoice, or statement"
        className="rounded-xl p-2.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        <Paperclip className="w-5 h-5" />
      </button>
    </>
  );
}
