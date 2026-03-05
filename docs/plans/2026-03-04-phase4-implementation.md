# Phase 4: React Frontend Implementation Plan

> **Status: COMPLETE** — All 13 tasks done. 12 commits (`1cbec8f`..`5228c2a`). Implemented 2026-03-04.

**Goal:** Build a chat-based React frontend that sends natural language queries to the FastAPI backend and renders responses with inline charts and tables.

**Architecture:** Single-page React app with TypeScript. Chat UI in a centered column. Messages rendered with markdown support. Data tables and Recharts charts rendered inline within agent message bubbles. State managed via useState + React Context (session ID, active company).

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Recharts, react-markdown, axios, lucide-react

**Design Doc:** `docs/plans/2026-03-04-phase4-frontend-design.md`

## Test Status

| Suite | Count | Status | Notes |
|-------|-------|--------|-------|
| **Backend unit tests** | 274 | ALL PASSING | No regressions from Phase 4 (frontend-only phase) |
| **Backend integration tests** | 43 | ALL PASSING | No regressions |
| **Backend E2E tests** | — | Not yet created | `tests/e2e/` dir does not exist yet |
| **Frontend TypeScript** | — | CLEAN | `tsc --noEmit` passes with 0 errors |
| **Frontend build** | — | PASSING | `npm run build` succeeds (746KB bundle, Recharts heavy) |
| **Frontend smoke test** | 13 checks | PASSING | Playwright visual verification: empty state, chat flow, error handling, quick actions |

**Frontend has no automated tests** — this is a known gap. **Next step**: Phase 4b — automated frontend tests (Vitest + React Testing Library) and backend E2E tests (full NL query → agent → Tally → response pipeline with mock Claude API). This comes before Phase 5 (Advanced Features).

## Reviews

- **Spec compliance**: PASSED — all design doc requirements implemented, no missing or extra work
- **Code quality**: PASSED with fixes — 1 critical (data type guard), 4 important (CSV escaping, health tooltip, timeout, a11y) all fixed in commit `5228c2a`

## Remaining Minor Issues (from code review, not blocking)

- `formatINR` utility exported but unused
- Leftover Vite boilerplate (`src/assets/react.svg`, `public/vite.svg`)
- No `useMemo` on SessionContext provider value (minor perf optimization)
- Favicon still Vite default (cosmetic)

---

### Task 1: Scaffold Vite + React + TypeScript project

**Files:**
- Create: `frontend/` (Vite scaffold)
- Modify: `frontend/package.json` (add deps)
- Modify: `frontend/vite.config.ts` (add Tailwind plugin + proxy)
- Create: `frontend/src/index.css` (Tailwind imports)

**Step 1: Scaffold with Vite**

```bash
cd /Users/ripu/work/nuvanta_repos/tally_agent
npm create vite@latest frontend -- --template react-ts
```

**Step 2: Install dependencies**

```bash
cd frontend
npm install recharts axios lucide-react react-markdown
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Configure Vite with Tailwind + API proxy**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

**Step 4: Set up Tailwind in index.css**

Replace `frontend/src/index.css`:

```css
@import "tailwindcss";
```

**Step 5: Clean up scaffold — remove boilerplate**

- Delete `frontend/src/App.css`
- Replace `frontend/src/App.tsx` with a minimal placeholder:

```typescript
function App() {
  return <div className="min-h-screen bg-white">TallyPrime AI</div>;
}

export default App;
```

- Replace `frontend/src/main.tsx`:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

**Step 6: Verify it runs**

```bash
cd frontend && npm run dev
```

Expected: Vite dev server at http://localhost:5173 showing "TallyPrime AI" with Tailwind active.

**Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + TypeScript + Tailwind"
```

---

### Task 2: Types and API client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`

**Step 1: Define TypeScript types**

Create `frontend/src/types/index.ts`:

```typescript
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: TableData;
  chart?: ChartSpec;
  isError?: boolean;
  isLoading?: boolean;
}

export interface TableData {
  headers: string[];
  rows: (string | number | null)[][];
}

export interface ChartSpec {
  chart_type: "bar" | "line" | "pie" | "grouped_bar";
  title: string;
  data: Record<string, unknown>[];
  config?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  company?: string;
}

export interface ChatResponse {
  message: string;
  data?: TableData;
  chart?: ChartSpec;
  session_id: string;
}

export interface HealthResponse {
  status: string;
  tally_connected: boolean;
  tally_url: string;
}

export interface Company {
  name: string;
}

export interface CompaniesResponse {
  companies: Company[];
}
```

**Step 2: Create API client**

Create `frontend/src/api/client.ts`:

```typescript
import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  HealthResponse,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/chat", request);
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function getCompanies(): Promise<CompaniesResponse> {
  const { data } = await api.get<CompaniesResponse>("/companies");
  return data;
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/ frontend/src/api/
git commit -m "feat(frontend): add TypeScript types and API client"
```

---

### Task 3: SessionContext

**Files:**
- Create: `frontend/src/context/SessionContext.tsx`
- Modify: `frontend/src/App.tsx` (wrap with provider)

**Step 1: Create SessionContext**

Create `frontend/src/context/SessionContext.tsx`:

```typescript
import { createContext, useContext, useState, type ReactNode } from "react";

interface SessionContextValue {
  sessionId: string | null;
  setSessionId: (id: string) => void;
  company: string | null;
  setCompany: (name: string | null) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [company, setCompany] = useState<string | null>(null);

  return (
    <SessionContext.Provider
      value={{ sessionId, setSessionId, company, setCompany }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
```

**Step 2: Wrap App with SessionProvider**

Update `frontend/src/App.tsx`:

```typescript
import { SessionProvider } from "./context/SessionContext";

function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen bg-white">TallyPrime AI</div>
    </SessionProvider>
  );
}

export default App;
```

**Step 3: Commit**

```bash
git add frontend/src/context/ frontend/src/App.tsx
git commit -m "feat(frontend): add SessionContext for session and company state"
```

---

### Task 4: Utility functions

**Files:**
- Create: `frontend/src/utils/format.ts`

**Step 1: Create Indian formatting utilities**

Create `frontend/src/utils/format.ts`:

```typescript
/**
 * Format a number in Indian comma style: 12,34,567.00
 */
export function formatIndianNumber(num: number): string {
  const [intPart, decPart] = Math.abs(num).toFixed(2).split(".");
  const lastThree = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted =
    rest.length > 0
      ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + lastThree
      : lastThree;
  const sign = num < 0 ? "-" : "";
  return `${sign}${formatted}.${decPart}`;
}

/**
 * Format as Indian Rupees: ₹12,34,567.00
 */
export function formatINR(num: number): string {
  const sign = num < 0 ? "-" : "";
  return `${sign}₹${formatIndianNumber(Math.abs(num))}`;
}

/**
 * Check if a value looks numeric.
 */
export function isNumericValue(val: unknown): val is number {
  return typeof val === "number" && !isNaN(val);
}

/**
 * Generate a unique ID for messages.
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
```

**Step 2: Commit**

```bash
git add frontend/src/utils/
git commit -m "feat(frontend): add Indian number formatting utilities"
```

---

### Task 5: Header + CompanySelector + Health indicator

**Files:**
- Create: `frontend/src/components/Header.tsx`
- Create: `frontend/src/components/CompanySelector.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create CompanySelector**

Create `frontend/src/components/CompanySelector.tsx`:

```typescript
import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { getCompanies } from "../api/client";
import { useSession } from "../context/SessionContext";
import type { Company } from "../types";

export default function CompanySelector() {
  const { company, setCompany } = useSession();
  const [companies, setCompanies] = useState<Company[]>([]);

  useEffect(() => {
    getCompanies()
      .then((res) => {
        setCompanies(res.companies);
        if (res.companies.length > 0 && !company) {
          setCompany(res.companies[0].name);
        }
      })
      .catch(() => setCompanies([]));
  }, []);

  if (companies.length === 0) return null;

  return (
    <div className="relative">
      <select
        value={company ?? ""}
        onChange={(e) => setCompany(e.target.value)}
        className="appearance-none bg-white border border-gray-200 rounded-lg px-3 py-1.5 pr-8 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {companies.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
    </div>
  );
}
```

**Step 2: Create Header**

Create `frontend/src/components/Header.tsx`:

```typescript
import { useEffect, useState } from "react";
import { getHealth } from "../api/client";
import CompanySelector from "./CompanySelector";

export default function Header() {
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((res) => setConnected(res.tally_connected))
      .catch(() => setConnected(false));

    const interval = setInterval(() => {
      getHealth()
        .then((res) => setConnected(res.tally_connected))
        .catch(() => setConnected(false));
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
      <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5" title={connected ? "Tally connected" : "Tally disconnected"}>
          <div
            className={`w-2 h-2 rounded-full ${
              connected === null
                ? "bg-gray-300"
                : connected
                  ? "bg-green-500"
                  : "bg-red-500"
            }`}
          />
          <span className="text-xs text-gray-500">Tally</span>
        </div>
        <CompanySelector />
      </div>
    </header>
  );
}
```

**Step 3: Wire Header into App**

Update `frontend/src/App.tsx`:

```typescript
import { SessionProvider } from "./context/SessionContext";
import Header from "./components/Header";

function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen bg-white flex flex-col">
        <Header />
        <main className="flex-1">
          {/* ChatWindow will go here */}
        </main>
      </div>
    </SessionProvider>
  );
}

export default App;
```

**Step 4: Verify header renders**

```bash
cd frontend && npm run dev
```

Expected: Header with "TallyPrime AI" title, health dot, and company selector (may be empty if backend not running).

**Step 5: Commit**

```bash
git add frontend/src/components/Header.tsx frontend/src/components/CompanySelector.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Header with health indicator and CompanySelector"
```

---

### Task 6: ChatInput component

**Files:**
- Create: `frontend/src/components/ChatInput.tsx`

**Step 1: Create ChatInput**

Create `frontend/src/components/ChatInput.tsx`:

```typescript
import { useState, useRef, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
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
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Ask about your Tally data..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="rounded-xl bg-blue-600 p-2.5 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <SendHorizontal className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ChatInput.tsx
git commit -m "feat(frontend): add ChatInput with auto-grow and Enter-to-send"
```

---

### Task 7: DataTable component

**Files:**
- Create: `frontend/src/components/DataTable.tsx`

**Step 1: Create DataTable**

Create `frontend/src/components/DataTable.tsx`:

```typescript
import { useState } from "react";
import { ArrowUpDown, Download } from "lucide-react";
import type { TableData } from "../types";
import { formatIndianNumber, isNumericValue } from "../utils/format";

interface DataTableProps {
  data: TableData;
}

export default function DataTable({ data }: DataTableProps) {
  const { headers, rows } = data;
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  if (rows.length === 0) return null;

  function handleSort(colIndex: number) {
    if (sortCol === colIndex) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colIndex);
      setSortAsc(true);
    }
  }

  const sortedRows = [...rows];
  if (sortCol !== null) {
    sortedRows.sort((a, b) => {
      const aVal = a[sortCol];
      const bVal = b[sortCol];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortAsc ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });
  }

  function exportCSV() {
    const csvRows = [
      headers.join(","),
      ...sortedRows.map((row) =>
        row.map((cell) => {
          const val = cell == null ? "" : String(cell);
          return val.includes(",") ? `"${val}"` : val;
        }).join(",")
      ),
    ];
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tally-data.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function formatCell(val: string | number | null): string {
    if (val == null) return "";
    if (isNumericValue(val)) return formatIndianNumber(val);
    return String(val);
  }

  return (
    <div className="mt-3 border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex justify-end px-3 py-1.5 bg-gray-50 border-b border-gray-200">
        <button
          onClick={exportCSV}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
        >
          <Download className="w-3 h-3" /> CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {headers.map((header, i) => (
                <th
                  key={i}
                  onClick={() => handleSort(i)}
                  className="px-3 py-2 text-left font-medium text-gray-600 cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                >
                  <span className="flex items-center gap-1">
                    {header}
                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, ri) => (
              <tr key={ri} className="border-b border-gray-100 hover:bg-gray-50">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={`px-3 py-1.5 whitespace-nowrap ${
                      isNumericValue(cell) ? "text-right tabular-nums" : ""
                    }`}
                  >
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/DataTable.tsx
git commit -m "feat(frontend): add DataTable with sorting and CSV export"
```

---

### Task 8: ChartRenderer component

**Files:**
- Create: `frontend/src/components/ChartRenderer.tsx`

**Step 1: Create ChartRenderer**

Create `frontend/src/components/ChartRenderer.tsx`:

```typescript
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartSpec } from "../types";

const DEFAULT_COLORS = [
  "#4F46E5", "#10B981", "#F59E0B", "#EF4444",
  "#8B5CF6", "#EC4899", "#06B6D4",
];

interface ChartRendererProps {
  chart: ChartSpec;
}

export default function ChartRenderer({ chart }: ChartRendererProps) {
  const { chart_type, title, data, config } = chart;
  const colors = (config?.colors as string[]) || DEFAULT_COLORS;

  if (!data || data.length === 0) return null;

  // Determine data keys (all keys except the first one, which is the label axis)
  const allKeys = Object.keys(data[0]);
  const labelKey = allKeys[0];
  const valueKeys = allKeys.slice(1);

  return (
    <div className="mt-3 border border-gray-200 rounded-lg p-4 bg-white">
      <h3 className="text-sm font-medium text-gray-700 mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        {chart_type === "pie" ? (
          <PieChart>
            <Pie
              data={data}
              dataKey={valueKeys[0]}
              nameKey={labelKey}
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ name, percent }) =>
                `${name}: ${(percent * 100).toFixed(0)}%`
              }
            >
              {data.map((_, i) => (
                <Cell key={i} fill={colors[i % colors.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        ) : chart_type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={labelKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {valueKeys.map((key, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[i % colors.length]}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        ) : (
          /* bar and grouped_bar */
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={labelKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {valueKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={colors[i % colors.length]} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ChartRenderer.tsx
git commit -m "feat(frontend): add ChartRenderer with bar/line/pie support"
```

---

### Task 9: MessageBubble component

**Files:**
- Create: `frontend/src/components/MessageBubble.tsx`

**Step 1: Create MessageBubble**

Create `frontend/src/components/MessageBubble.tsx`:

```typescript
import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../types";
import DataTable from "./DataTable";
import ChartRenderer from "./ChartRenderer";

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
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.data && <DataTable data={message.data} />}
        {message.chart && <ChartRenderer chart={message.chart} />}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/MessageBubble.tsx
git commit -m "feat(frontend): add MessageBubble with markdown, table, and chart rendering"
```

---

### Task 10: QuickActions component

**Files:**
- Create: `frontend/src/components/QuickActions.tsx`

**Step 1: Create QuickActions**

Create `frontend/src/components/QuickActions.tsx`:

```typescript
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
```

**Step 2: Commit**

```bash
git add frontend/src/components/QuickActions.tsx
git commit -m "feat(frontend): add QuickActions preset query buttons"
```

---

### Task 11: ChatWindow — main orchestrating component

**Files:**
- Create: `frontend/src/components/ChatWindow.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create ChatWindow**

Create `frontend/src/components/ChatWindow.tsx`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { sendChat } from "../api/client";
import { useSession } from "../context/SessionContext";
import type { ChatMessage } from "../types";
import { generateId } from "../utils/format";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import QuickActions from "./QuickActions";

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sessionId, setSessionId, company } = useSession();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    [sessionId, company, setSessionId]
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
```

**Step 2: Wire ChatWindow into App**

Update `frontend/src/App.tsx`:

```typescript
import { SessionProvider } from "./context/SessionContext";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";

function App() {
  return (
    <SessionProvider>
      <div className="h-screen flex flex-col bg-white">
        <Header />
        <main className="flex-1 overflow-hidden">
          <ChatWindow />
        </main>
      </div>
    </SessionProvider>
  );
}

export default App;
```

**Step 3: Verify full app**

```bash
cd frontend && npm run dev
```

Expected: Full chat UI with header, empty state with quick actions, input at bottom. If backend is running, typing a query should get a response.

**Step 4: Commit**

```bash
git add frontend/src/components/ChatWindow.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add ChatWindow — full chat UI with message flow"
```

---

### Task 12: Build verification and final polish

**Files:**
- Modify: `frontend/index.html` (title)
- Modify: `frontend/package.json` (verify)

**Step 1: Update page title**

In `frontend/index.html`, change `<title>` to `TallyPrime AI`.

**Step 2: Production build check**

```bash
cd frontend && npm run build
```

Expected: Clean build with no TypeScript errors. Output in `frontend/dist/`.

**Step 3: Verify type-checking**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No type errors.

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): final polish — title, build verification"
```

---

### Task 13: Manual E2E smoke test

**Files:** None (manual testing)

**Step 1: Start backend**

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Step 2: Start frontend**

```bash
cd frontend && npm run dev
```

**Step 3: Test checklist**

- [ ] Page loads with header, health dot, company selector
- [ ] Empty state shows welcome message and quick action buttons
- [ ] Typing a message and pressing Enter sends it
- [ ] User message appears right-aligned in blue
- [ ] Loading dots appear while waiting
- [ ] Agent response appears left-aligned in gray with markdown rendered
- [ ] If response has data table, it renders with sortable columns
- [ ] If response has chart, it renders inline
- [ ] CSV export button works on data tables
- [ ] Quick action buttons send queries
- [ ] Error state shows red bubble when backend is down
- [ ] Company selector works
- [ ] Health dot is green when Tally is connected, red otherwise

**Step 4: Final commit (if any fixes needed)**

```bash
git add frontend/
git commit -m "fix(frontend): address smoke test findings"
```
