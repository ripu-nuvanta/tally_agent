const QUICK_QUERIES = [
  "P&L this month",
  "Outstanding receivables",
  "Cash balance",
  "Stock summary",
  "Top 10 customers",
  "Sales vs purchases this month",
];

interface QuickActionsProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export default function QuickActions({ onSelect, disabled }: QuickActionsProps) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {QUICK_QUERIES.map((query) => (
        <button
          key={query}
          onClick={() => onSelect(query)}
          disabled={disabled}
          className="px-3 py-1.5 text-sm text-blue-600 bg-blue-50 rounded-full hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {query}
        </button>
      ))}
    </div>
  );
}
