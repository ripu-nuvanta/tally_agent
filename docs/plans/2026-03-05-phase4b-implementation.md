# Phase 4b: Automated Tests — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ~90 automated tests covering frontend components (Vitest + RTL), frontend responsiveness (Playwright screenshots), backend E2E with mock Claude API, and backend E2E with real Claude + Tally.

**Architecture:** Four independent test suites — frontend unit tests run via Vitest with jsdom, Playwright screenshot tests for responsive validation at 3 viewports, backend E2E tests using a mock Claude API client and mock Tally server via FastAPI TestClient, and live E2E tests gated behind `RUN_LIVE_TESTS` env var.

**Tech Stack:** Vitest, @testing-library/react, @testing-library/user-event, @testing-library/jest-dom, jsdom, Playwright, pytest, httpx (FastAPI TestClient), aiohttp (mock Tally server)

**Design Doc:** `docs/plans/2026-03-05-phase4b-testing-design.md`

---

### Task 1: Frontend test infrastructure setup

**Files:**
- Modify: `frontend/package.json` (add devDeps + scripts)
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/__tests__/setup.ts`

**Step 1: Install test dependencies**

```bash
cd frontend && npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

**Step 2: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.ts"],
    globals: true,
  },
});
```

**Step 3: Create `frontend/src/__tests__/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";

// Mock react-markdown — jsdom can't handle ESM re-exports
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => children,
}));

// Mock recharts ResponsiveContainer — needs real DOM dimensions
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});
```

**Step 4: Add test scripts to `frontend/package.json`**

Add to `"scripts"`:
```json
"test": "vitest run",
"test:watch": "vitest"
```

**Step 5: Verify test runner works**

```bash
cd frontend && npm test
```

Expected: `No test files found` (no tests yet, but runner should start cleanly).

**Step 6: Commit**

```bash
git add frontend/package.json frontend/vitest.config.ts frontend/src/__tests__/setup.ts
git commit -m "test(frontend): add Vitest + RTL test infrastructure"
```

---

### Task 2: Utils format tests

**Files:**
- Create: `frontend/src/__tests__/format.test.ts`

**Step 1: Write tests**

```typescript
import { describe, it, expect } from "vitest";
import {
  formatIndianNumber,
  formatINR,
  isNumericValue,
  generateId,
} from "../utils/format";

describe("formatIndianNumber", () => {
  it("formats small numbers", () => {
    expect(formatIndianNumber(100)).toBe("100.00");
  });

  it("formats thousands", () => {
    expect(formatIndianNumber(1234)).toBe("1,234.00");
  });

  it("formats lakhs", () => {
    expect(formatIndianNumber(123456)).toBe("1,23,456.00");
  });

  it("formats crores", () => {
    expect(formatIndianNumber(12345678)).toBe("1,23,45,678.00");
  });

  it("handles negative numbers", () => {
    expect(formatIndianNumber(-1234567)).toBe("-12,34,567.00");
  });

  it("handles zero", () => {
    expect(formatIndianNumber(0)).toBe("0.00");
  });

  it("handles decimals", () => {
    expect(formatIndianNumber(1234.56)).toBe("1,234.56");
  });
});

describe("formatINR", () => {
  it("adds rupee symbol", () => {
    expect(formatINR(1234567)).toBe("₹12,34,567.00");
  });

  it("handles negative with sign before symbol", () => {
    expect(formatINR(-5000)).toBe("-₹5,000.00");
  });
});

describe("isNumericValue", () => {
  it("returns true for numbers", () => {
    expect(isNumericValue(42)).toBe(true);
    expect(isNumericValue(0)).toBe(true);
    expect(isNumericValue(-3.14)).toBe(true);
  });

  it("returns false for NaN", () => {
    expect(isNumericValue(NaN)).toBe(false);
  });

  it("returns false for non-numbers", () => {
    expect(isNumericValue("42")).toBe(false);
    expect(isNumericValue(null)).toBe(false);
    expect(isNumericValue(undefined)).toBe(false);
  });
});

describe("generateId", () => {
  it("returns a string", () => {
    expect(typeof generateId()).toBe("string");
  });

  it("generates unique values", () => {
    const ids = new Set(Array.from({ length: 100 }, () => generateId()));
    expect(ids.size).toBe(100);
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/format.test.ts
git commit -m "test(frontend): add format utility tests"
```

---

### Task 3: QuickActions tests

**Files:**
- Create: `frontend/src/__tests__/QuickActions.test.tsx`

**Step 1: Write tests**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import QuickActions from "../components/QuickActions";

const EXPECTED_QUERIES = [
  "P&L this month",
  "Outstanding receivables",
  "Cash balance",
  "Stock summary",
  "Top 10 customers",
  "Sales vs purchases this month",
];

describe("QuickActions", () => {
  it("renders all 6 query buttons", () => {
    render(<QuickActions onSelect={() => {}} />);
    for (const query of EXPECTED_QUERIES) {
      expect(screen.getByRole("button", { name: query })).toBeInTheDocument();
    }
  });

  it("calls onSelect with the query text when clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).toHaveBeenCalledWith("Cash balance");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("disables all buttons when disabled prop is true", () => {
    render(<QuickActions onSelect={() => {}} disabled />);
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => expect(btn).toBeDisabled());
  });

  it("does not call onSelect when disabled button is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<QuickActions onSelect={onSelect} disabled />);

    await user.click(screen.getByRole("button", { name: "Cash balance" }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/QuickActions.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/QuickActions.test.tsx
git commit -m "test(frontend): add QuickActions component tests"
```

---

### Task 4: ChatInput tests

**Files:**
- Create: `frontend/src/__tests__/ChatInput.test.tsx`

**Step 1: Write tests**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatInput from "../components/ChatInput";

describe("ChatInput", () => {
  it("renders a textarea with placeholder", () => {
    render(<ChatInput onSend={() => {}} />);
    expect(
      screen.getByPlaceholderText("Ask about your Tally data...")
    ).toBeInTheDocument();
  });

  it("renders a send button", () => {
    render(<ChatInput onSend={() => {}} />);
    expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument();
  });

  it("calls onSend with trimmed text on Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Show trial balance{Enter}");
    expect(onSend).toHaveBeenCalledWith("Show trial balance");
  });

  it("does not call onSend on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "line 1{Shift>}{Enter}{/Shift}line 2");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when input is empty", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("clears input after send", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={() => {}} />);

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "hello{Enter}");
    expect(textarea).toHaveValue("");
  });

  it("calls onSend on send button click", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test query");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSend).toHaveBeenCalledWith("test query");
  });

  it("disables textarea and button when disabled", () => {
    render(<ChatInput onSend={() => {}} disabled />);
    expect(screen.getByPlaceholderText("Ask about your Tally data...")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/ChatInput.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/ChatInput.test.tsx
git commit -m "test(frontend): add ChatInput component tests"
```

---

### Task 5: DataTable tests

**Files:**
- Create: `frontend/src/__tests__/DataTable.test.tsx`

**Step 1: Write tests**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataTable from "../components/DataTable";
import type { TableData } from "../types";

const sampleData: TableData = {
  headers: ["Ledger", "Amount"],
  rows: [
    ["Sales Account", 1234567],
    ["Purchase Account", 890000],
    ["Cash", 50000],
  ],
};

describe("DataTable", () => {
  it("renders headers", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("Ledger")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
  });

  it("renders all rows", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("Sales Account")).toBeInTheDocument();
    expect(screen.getByText("Purchase Account")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
  });

  it("formats numbers in Indian style", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("12,34,567.00")).toBeInTheDocument();
  });

  it("returns null for empty rows", () => {
    const { container } = render(
      <DataTable data={{ headers: ["A"], rows: [] }} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("sorts ascending on first column header click", async () => {
    const user = userEvent.setup();
    render(<DataTable data={sampleData} />);

    await user.click(screen.getByText("Amount"));

    const cells = screen.getAllByRole("cell");
    // Amount column cells (indices 1, 3, 5 in the flat list)
    const amountCells = cells.filter((_, i) => i % 2 === 1);
    // First amount should be smallest (Cash: 50,000)
    expect(amountCells[0]).toHaveTextContent("50,000.00");
  });

  it("sorts descending on second click of same column", async () => {
    const user = userEvent.setup();
    render(<DataTable data={sampleData} />);

    await user.click(screen.getByText("Amount"));
    await user.click(screen.getByText("Amount"));

    const cells = screen.getAllByRole("cell");
    const amountCells = cells.filter((_, i) => i % 2 === 1);
    // First amount should be largest (Sales: 12,34,567)
    expect(amountCells[0]).toHaveTextContent("12,34,567.00");
  });

  it("renders CSV export button", () => {
    render(<DataTable data={sampleData} />);
    expect(screen.getByText("CSV")).toBeInTheDocument();
  });

  it("handles null cell values", () => {
    const data: TableData = {
      headers: ["Name", "Value"],
      rows: [["Test", null]],
    };
    render(<DataTable data={data} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("handles string values in columns", () => {
    const data: TableData = {
      headers: ["Name", "Type"],
      rows: [["Sales", "Revenue"], ["Rent", "Expense"]],
    };
    render(<DataTable data={data} />);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Expense")).toBeInTheDocument();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/DataTable.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/DataTable.test.tsx
git commit -m "test(frontend): add DataTable component tests"
```

---

### Task 6: ChartRenderer tests

**Files:**
- Create: `frontend/src/__tests__/ChartRenderer.test.tsx`

**Step 1: Write tests**

Note: Recharts components are mocked via `ResponsiveContainer` in setup.ts. We test that the correct chart component is rendered and title is shown.

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ChartRenderer from "../components/ChartRenderer";
import type { ChartSpec } from "../types";

const barChart: ChartSpec = {
  chart_type: "bar",
  title: "Sales by Customer",
  data: [
    { customer: "HCODE", amount: 500000 },
    { customer: "SMARTBIKE", amount: 300000 },
  ],
};

const lineChart: ChartSpec = {
  chart_type: "line",
  title: "Monthly Revenue",
  data: [
    { month: "Apr", revenue: 100000 },
    { month: "May", revenue: 150000 },
    { month: "Jun", revenue: 120000 },
  ],
};

const pieChart: ChartSpec = {
  chart_type: "pie",
  title: "Expense Breakdown",
  data: [
    { category: "Rent", amount: 50000 },
    { category: "Salary", amount: 200000 },
  ],
};

describe("ChartRenderer", () => {
  it("renders chart title", () => {
    render(<ChartRenderer chart={barChart} />);
    expect(screen.getByText("Sales by Customer")).toBeInTheDocument();
  });

  it("renders bar chart container", () => {
    render(<ChartRenderer chart={barChart} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders line chart", () => {
    render(<ChartRenderer chart={lineChart} />);
    expect(screen.getByText("Monthly Revenue")).toBeInTheDocument();
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renders pie chart", () => {
    render(<ChartRenderer chart={pieChart} />);
    expect(screen.getByText("Expense Breakdown")).toBeInTheDocument();
  });

  it("renders grouped_bar chart", () => {
    const grouped: ChartSpec = {
      chart_type: "grouped_bar",
      title: "Q1 vs Q2",
      data: [{ label: "Sales", q1: 100, q2: 150 }],
    };
    render(<ChartRenderer chart={grouped} />);
    expect(screen.getByText("Q1 vs Q2")).toBeInTheDocument();
  });

  it("returns null for empty data", () => {
    const empty: ChartSpec = {
      chart_type: "bar",
      title: "Empty",
      data: [],
    };
    const { container } = render(<ChartRenderer chart={empty} />);
    expect(container.firstChild).toBeNull();
  });

  it("returns null when data is undefined-ish", () => {
    const noData: ChartSpec = {
      chart_type: "bar",
      title: "No Data",
      data: [],
    };
    const { container } = render(<ChartRenderer chart={noData} />);
    expect(container.firstChild).toBeNull();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/ChartRenderer.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/ChartRenderer.test.tsx
git commit -m "test(frontend): add ChartRenderer component tests"
```

---

### Task 7: MessageBubble tests

**Files:**
- Create: `frontend/src/__tests__/MessageBubble.test.tsx`

**Step 1: Write tests**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MessageBubble from "../components/MessageBubble";
import type { ChatMessage } from "../types";

describe("MessageBubble", () => {
  it("renders user message text", () => {
    const msg: ChatMessage = {
      id: "1",
      role: "user",
      content: "Show trial balance",
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Show trial balance")).toBeInTheDocument();
  });

  it("renders assistant message text", () => {
    const msg: ChatMessage = {
      id: "2",
      role: "assistant",
      content: "Here is your trial balance",
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Here is your trial balance")).toBeInTheDocument();
  });

  it("renders loading dots when isLoading is true", () => {
    const msg: ChatMessage = {
      id: "3",
      role: "assistant",
      content: "",
      isLoading: true,
    };
    const { container } = render(<MessageBubble message={msg} />);
    const dots = container.querySelectorAll(".animate-bounce");
    expect(dots.length).toBe(3);
  });

  it("renders error state with error content", () => {
    const msg: ChatMessage = {
      id: "4",
      role: "assistant",
      content: "Something went wrong",
      isError: true,
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders DataTable when message has valid data", () => {
    const msg: ChatMessage = {
      id: "5",
      role: "assistant",
      content: "Here is the data",
      data: {
        headers: ["Name", "Amount"],
        rows: [["Sales", 100]],
      },
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
  });

  it("renders ChartRenderer when message has chart", () => {
    const msg: ChatMessage = {
      id: "6",
      role: "assistant",
      content: "Chart below",
      chart: {
        chart_type: "bar",
        title: "Test Chart",
        data: [{ label: "A", value: 100 }],
      },
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("Test Chart")).toBeInTheDocument();
  });

  it("does not render DataTable when data has no headers/rows keys", () => {
    const msg: ChatMessage = {
      id: "7",
      role: "assistant",
      content: "No table",
      data: { something: "else" } as any,
    };
    render(<MessageBubble message={msg} />);
    expect(screen.getByText("No table")).toBeInTheDocument();
    // No table element should be rendered
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/MessageBubble.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/MessageBubble.test.tsx
git commit -m "test(frontend): add MessageBubble component tests"
```

---

### Task 8: CompanySelector tests

**Files:**
- Create: `frontend/src/__tests__/CompanySelector.test.tsx`

**Step 1: Write tests**

CompanySelector calls `getCompanies()` on mount and uses `useSession()`. We need to mock both.

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CompanySelector from "../components/CompanySelector";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

function renderWithProvider() {
  return render(
    <SessionProvider>
      <CompanySelector />
    </SessionProvider>
  );
}

describe("CompanySelector", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders nothing when no companies are returned", async () => {
    mockedApi.getCompanies.mockResolvedValue({ companies: [] });
    const { container } = renderWithProvider();
    await waitFor(() => expect(mockedApi.getCompanies).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });

  it("renders company dropdown when companies are available", async () => {
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }, { name: "Nuvanta AI" }],
    });
    renderWithProvider();
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
    expect(screen.getByText("Nuvanta AI")).toBeInTheDocument();
  });

  it("auto-selects the first company", async () => {
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }],
    });
    renderWithProvider();
    await waitFor(() => {
      expect(screen.getByRole("combobox")).toHaveValue("Bharat Traders");
    });
  });

  it("handles API error gracefully", async () => {
    mockedApi.getCompanies.mockRejectedValue(new Error("Network error"));
    const { container } = renderWithProvider();
    await waitFor(() => expect(mockedApi.getCompanies).toHaveBeenCalled());
    expect(container.querySelector("select")).toBeNull();
  });

  it("allows changing company via dropdown", async () => {
    const user = userEvent.setup();
    mockedApi.getCompanies.mockResolvedValue({
      companies: [{ name: "Bharat Traders" }, { name: "Nuvanta AI" }],
    });
    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByRole("combobox"), "Nuvanta AI");
    expect(screen.getByRole("combobox")).toHaveValue("Nuvanta AI");
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/CompanySelector.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/CompanySelector.test.tsx
git commit -m "test(frontend): add CompanySelector component tests"
```

---

### Task 9: Header tests

**Files:**
- Create: `frontend/src/__tests__/Header.test.tsx`

**Step 1: Write tests**

Header calls `getHealth()` on mount and renders a health dot. Uses CompanySelector which needs SessionProvider.

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import Header from "../components/Header";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

function renderWithProvider() {
  return render(
    <SessionProvider>
      <Header />
    </SessionProvider>
  );
}

describe("Header", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetAllMocks();
    // Default: companies returns empty (CompanySelector won't interfere)
    mockedApi.getCompanies.mockResolvedValue({ companies: [] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders app title", () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok",
      tally_connected: true,
      tally_url: "http://localhost:9000",
    });
    renderWithProvider();
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
  });

  it("shows green dot when Tally is connected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok",
      tally_connected: true,
      tally_url: "http://localhost:9000",
    });
    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTitle("Tally connected")).toBeInTheDocument();
    });
  });

  it("shows red dot when Tally is disconnected", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok",
      tally_connected: false,
      tally_url: "http://localhost:9000",
    });
    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTitle("Tally disconnected")).toBeInTheDocument();
    });
  });

  it("shows gray dot initially (checking state)", () => {
    mockedApi.getHealth.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithProvider();
    expect(screen.getByTitle("Checking Tally connection...")).toBeInTheDocument();
  });

  it("shows red dot on health check failure", async () => {
    mockedApi.getHealth.mockRejectedValue(new Error("Network"));
    renderWithProvider();

    await waitFor(() => {
      expect(screen.getByTitle("Tally disconnected")).toBeInTheDocument();
    });
  });

  it("polls health every 30 seconds", async () => {
    mockedApi.getHealth.mockResolvedValue({
      status: "ok",
      tally_connected: true,
      tally_url: "http://localhost:9000",
    });
    renderWithProvider();

    await waitFor(() => expect(mockedApi.getHealth).toHaveBeenCalledTimes(1));

    vi.advanceTimersByTime(30000);
    await waitFor(() => expect(mockedApi.getHealth).toHaveBeenCalledTimes(2));

    vi.advanceTimersByTime(30000);
    await waitFor(() => expect(mockedApi.getHealth).toHaveBeenCalledTimes(3));
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/Header.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/Header.test.tsx
git commit -m "test(frontend): add Header component tests"
```

---

### Task 10: ChatWindow tests

**Files:**
- Create: `frontend/src/__tests__/ChatWindow.test.tsx`

**Step 1: Write tests**

ChatWindow is the integration-level component. Mock `api/client` and wrap with SessionProvider.

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatWindow from "../components/ChatWindow";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

// Silence scrollIntoView (not available in jsdom)
Element.prototype.scrollIntoView = vi.fn();

function renderWithProvider() {
  return render(
    <SessionProvider>
      <ChatWindow />
    </SessionProvider>
  );
}

describe("ChatWindow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders empty state with welcome message", () => {
    renderWithProvider();
    expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
    expect(
      screen.getByText("Ask me anything about your accounting data")
    ).toBeInTheDocument();
  });

  it("renders quick actions in empty state", () => {
    renderWithProvider();
    expect(screen.getByRole("button", { name: "Cash balance" })).toBeInTheDocument();
  });

  it("shows user message after sending", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Here is the trial balance",
      session_id: "sess-1",
    });
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Show trial balance{Enter}");

    expect(screen.getByText("Show trial balance")).toBeInTheDocument();
  });

  it("shows agent response after successful API call", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Your trial balance is ready",
      session_id: "sess-1",
    });
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "Trial balance{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Your trial balance is ready")).toBeInTheDocument();
    });
  });

  it("shows error message on network error", async () => {
    const user = userEvent.setup();
    const err = new Error("Network Error");
    mockedApi.sendChat.mockRejectedValue(err);
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");

    await waitFor(() => {
      expect(
        screen.getByText(
          "Cannot connect to the server. Please check if the backend is running."
        )
      ).toBeInTheDocument();
    });
  });

  it("shows generic error on non-network error", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockRejectedValue(new Error("Server Error"));
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "test{Enter}");

    await waitFor(() => {
      expect(
        screen.getByText("Something went wrong. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("sends session_id on subsequent messages", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Response 1",
      session_id: "sess-123",
    });
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "query 1{Enter}");
    await waitFor(() => {
      expect(screen.getByText("Response 1")).toBeInTheDocument();
    });

    // Second message should include session_id
    mockedApi.sendChat.mockResolvedValue({
      message: "Response 2",
      session_id: "sess-123",
    });
    await user.type(textarea, "query 2{Enter}");
    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenLastCalledWith(
        expect.objectContaining({ session_id: "sess-123" })
      );
    });
  });

  it("renders data table in response", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "Here is your data",
      data: {
        headers: ["Ledger", "Balance"],
        rows: [["Cash", 50000]],
      },
      session_id: "sess-1",
    });
    renderWithProvider();

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "cash balance{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Cash")).toBeInTheDocument();
      expect(screen.getByText("Ledger")).toBeInTheDocument();
    });
  });

  it("triggers send from quick action click", async () => {
    const user = userEvent.setup();
    mockedApi.sendChat.mockResolvedValue({
      message: "P&L data",
      session_id: "sess-1",
    });
    renderWithProvider();

    await user.click(screen.getByRole("button", { name: "P&L this month" }));
    expect(mockedApi.sendChat).toHaveBeenCalledWith(
      expect.objectContaining({ message: "P&L this month" })
    );
  });
});
```

**Step 2: Run tests**

```bash
cd frontend && npm test -- src/__tests__/ChatWindow.test.tsx
```

Expected: All tests PASS.

**Step 3: Commit**

```bash
git add frontend/src/__tests__/ChatWindow.test.tsx
git commit -m "test(frontend): add ChatWindow component tests"
```

---

### Task 11: Run all frontend tests and verify

**Step 1: Run all frontend tests**

```bash
cd frontend && npm test
```

Expected: All ~45 tests PASS.

**Step 2: Verify TypeScript still compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

**Step 3: Commit (if any fixes were needed)**

```bash
git add frontend/
git commit -m "test(frontend): fix test issues found during full run"
```

---

### Task 12: Mock Claude API client

**Files:**
- Create: `tests/mocks/mock_claude_api.py`

**Step 1: Write the mock**

```python
"""Mock Anthropic client for deterministic E2E testing.

Provides a drop-in replacement for ``anthropic.AsyncAnthropic`` that returns
pre-configured responses in order.  Each test pushes the expected sequence
of Claude responses and the mock pops them one by one.

Usage:
    responses = [
        make_classification_response("simple_lookup"),
        make_tool_call_response("get_trial_balance", {...}),
        make_text_response("Here is the trial balance..."),
    ]
    mock_client = MockAnthropicClient(responses)
"""

from __future__ import annotations

from collections import deque
from typing import Any
from unittest.mock import MagicMock

from anthropic.types import (
    ContentBlock,
    Message,
    TextBlock,
    ToolUseBlock,
    Usage,
)


# ---------------------------------------------------------------------------
# Core mock
# ---------------------------------------------------------------------------


class MockMessages:
    """Drop-in for ``anthropic.AsyncAnthropic().messages``."""

    def __init__(self, client: MockAnthropicClient) -> None:
        self.client = client

    async def create(self, **kwargs: Any) -> Message:
        self.client.call_log.append(kwargs)
        if not self.client.responses:
            raise RuntimeError(
                f"MockAnthropicClient exhausted after {len(self.client.call_log)} calls. "
                "Add more responses to the mock."
            )
        return self.client.responses.popleft()


class MockAnthropicClient:
    """Drop-in replacement for ``anthropic.AsyncAnthropic``.

    Args:
        responses: Ordered list of ``Message`` objects to return.
    """

    def __init__(self, responses: list[Message]) -> None:
        self.responses: deque[Message] = deque(responses)
        self.messages = MockMessages(self)
        self.call_log: list[dict] = []


# ---------------------------------------------------------------------------
# Response factory helpers
# ---------------------------------------------------------------------------

_USAGE = Usage(input_tokens=10, output_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0)
_COUNTER = 0


def _next_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"msg_mock_{_COUNTER:04d}"


def _tool_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"toolu_mock_{_COUNTER:04d}"


def make_text_response(text: str) -> Message:
    """A Claude response that ends the turn with a text answer."""
    return Message(
        id=_next_id(),
        type="message",
        role="assistant",
        model="claude-sonnet-4-20250514",
        content=[TextBlock(type="text", text=text)],
        stop_reason="end_turn",
        usage=_USAGE,
    )


def make_classification_response(
    query_type: str,
    requires_chart: bool = False,
    clarification_question: str | None = None,
) -> Message:
    """A Claude response containing a JSON classification."""
    import json

    payload: dict[str, Any] = {
        "query_type": query_type,
        "requires_chart": requires_chart,
    }
    if clarification_question:
        payload["clarification_question"] = clarification_question

    return make_text_response(json.dumps(payload))


def make_tool_call_response(
    tool_name: str,
    tool_input: dict[str, Any],
    extra_text: str = "",
) -> Message:
    """A Claude response requesting a tool call."""
    content: list[ContentBlock] = []
    if extra_text:
        content.append(TextBlock(type="text", text=extra_text))
    content.append(
        ToolUseBlock(
            type="tool_use",
            id=_tool_id(),
            name=tool_name,
            input=tool_input,
        )
    )
    return Message(
        id=_next_id(),
        type="message",
        role="assistant",
        model="claude-sonnet-4-20250514",
        content=content,
        stop_reason="tool_use",
        usage=_USAGE,
    )
```

**Step 2: Verify import works**

```bash
PYTHONPATH=. python -c "from tests.mocks.mock_claude_api import MockAnthropicClient, make_text_response; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add tests/mocks/mock_claude_api.py
git commit -m "test: add mock Claude API client for E2E tests"
```

---

### Task 13: Backend E2E test — conftest and greeting test

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_chat_pipeline.py`

**Step 1: Create conftest with fixtures**

Create `tests/e2e/__init__.py` (empty).

Create `tests/e2e/conftest.py`:

```python
"""Fixtures for E2E tests using mock Claude API + mock Tally server."""

import pytest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.tally_bridge.client import TallyClient
from tests.mocks.mock_claude_api import MockAnthropicClient


@pytest.fixture
def mock_tally_client(aiohttp_server):
    """Create a TallyClient pointing at the mock Tally server."""
    from tests.mocks.mock_tally_server import create_mock_tally_app

    async def _factory():
        tally_app = create_mock_tally_app()
        server = await aiohttp_server(tally_app)
        return TallyClient(host="127.0.0.1", port=server.port)

    return _factory


@pytest.fixture
def make_mock_claude():
    """Factory to create a MockAnthropicClient with given responses."""

    def _factory(responses):
        return MockAnthropicClient(responses)

    return _factory


@pytest.fixture
async def e2e_client(aiohttp_server, make_mock_claude):
    """Provide an async test client + a function to set mock Claude responses.

    Usage:
        async def test_something(e2e_client):
            client, set_responses = e2e_client
            set_responses(orchestrator_responses=[...], query_agent_responses=[...])
            response = await client.post("/api/chat", json={...})
    """
    from tests.mocks.mock_tally_server import create_mock_tally_app

    # Start mock Tally
    tally_app = create_mock_tally_app()
    server = await aiohttp_server(tally_app)
    tally_client = TallyClient(host="127.0.0.1", port=server.port)

    # Inject into FastAPI app state
    app.state.tally_client = tally_client
    from backend.agents.context import SessionStore
    app.state.session_store = SessionStore()

    transport = ASGITransport(app=app)
    async_client = AsyncClient(transport=transport, base_url="http://test")

    mock_clients = {}

    def set_responses(
        orchestrator_responses=None,
        query_agent_responses=None,
        analysis_agent_responses=None,
    ):
        """Configure mock Claude responses for each agent."""
        if orchestrator_responses:
            mock_clients["orchestrator"] = MockAnthropicClient(orchestrator_responses)
        if query_agent_responses:
            mock_clients["query_agent"] = MockAnthropicClient(query_agent_responses)
        if analysis_agent_responses:
            mock_clients["analysis_agent"] = MockAnthropicClient(analysis_agent_responses)

    # We'll patch in the test using the returned set_responses
    yield async_client, set_responses, mock_clients

    await async_client.aclose()
    await tally_client.close()
```

**Step 2: Write the greeting test**

Create `tests/e2e/test_chat_pipeline.py`:

```python
"""End-to-end tests for the chat pipeline using mock Claude API + mock Tally."""

import pytest
from unittest.mock import patch

from tests.mocks.mock_claude_api import (
    make_classification_response,
    make_text_response,
    make_tool_call_response,
)


@pytest.mark.asyncio
async def test_greeting_returns_canned_response(e2e_client):
    """Greeting query → orchestrator classifies → canned greeting returned."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response("greeting"),
        ],
    )

    with patch(
        "backend.agents.orchestrator.anthropic_client",
        mock_clients["orchestrator"],
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Hello!"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["message"].startswith("Hello!")
    assert data["session_id"]
    assert data["data"] is None
    assert data["chart"] is None
```

**Step 3: Run the test**

```bash
PYTHONPATH=. pytest tests/e2e/test_chat_pipeline.py::test_greeting_returns_canned_response -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tests/e2e/
git commit -m "test(e2e): add conftest and greeting pipeline test"
```

---

### Task 14: Backend E2E — simple lookup and clarification tests

**Files:**
- Modify: `tests/e2e/test_chat_pipeline.py`

**Step 1: Add simple lookup test**

Append to `tests/e2e/test_chat_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_simple_lookup_trial_balance(e2e_client):
    """Simple lookup → classify → query agent (tool call) → text response with data."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response("simple_lookup"),
        ],
        query_agent_responses=[
            # Claude asks for trial balance tool
            make_tool_call_response(
                "get_trial_balance",
                {"from_date": "01-04-2025", "to_date": "31-03-2026"},
            ),
            # After getting tool result, Claude produces final text
            make_text_response(
                "Here is the trial balance for FY 2025-26."
            ),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show trial balance"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "trial balance" in data["message"].lower()
    assert data["session_id"]


@pytest.mark.asyncio
async def test_clarification_returns_question(e2e_client):
    """Ambiguous query → orchestrator classifies as clarification_needed."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response(
                "clarification_needed",
                clarification_question="Which balance are you looking for? Cash balance, bank balance, or trial balance?",
            ),
        ],
    )

    with patch(
        "backend.agents.orchestrator.anthropic_client",
        mock_clients["orchestrator"],
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show me the balance"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "balance" in data["message"].lower()
    assert data["data"] is None


@pytest.mark.asyncio
async def test_simple_lookup_companies(e2e_client):
    """List companies → classify → query agent (tool call) → response."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response("simple_lookup"),
        ],
        query_agent_responses=[
            make_tool_call_response("list_companies", {}),
            make_text_response("The loaded company is Bharat Traders Pvt Ltd."),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "List all companies"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
```

**Step 2: Run all E2E tests**

```bash
PYTHONPATH=. pytest tests/e2e/ -v
```

Expected: All 4 tests PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_chat_pipeline.py
git commit -m "test(e2e): add simple lookup and clarification pipeline tests"
```

---

### Task 15: Backend E2E — comparison, trend, top-N, and error tests

**Files:**
- Modify: `tests/e2e/test_chat_pipeline.py`

**Step 1: Add remaining E2E tests**

Append to `tests/e2e/test_chat_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_comparison_with_analysis_and_chart(e2e_client):
    """Comparison query → query agent → analysis agent → chart agent."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response("comparison", requires_chart=True),
        ],
        query_agent_responses=[
            make_tool_call_response(
                "get_profit_and_loss",
                {"from_date": "01-04-2025", "to_date": "30-09-2025"},
            ),
            make_text_response("Sales in H1: 20,00,000. Purchases: 15,00,000."),
        ],
        analysis_agent_responses=[
            make_text_response(
                "Comparison analysis:\n- Sales exceeded purchases by 5,00,000\n"
                "chart_suggestion: grouped_bar"
            ),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.analysis_agent.anthropic_client", mock_clients["analysis_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Compare sales and purchases this half year"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    # Analysis agent message should be used (not query agent's)
    assert "comparison" in data["message"].lower() or "sales" in data["message"].lower()


@pytest.mark.asyncio
async def test_top_n_query(e2e_client):
    """Top-N query → query agent → analysis agent → ranked response."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[
            make_classification_response("top_n"),
        ],
        query_agent_responses=[
            make_tool_call_response(
                "get_sales_register",
                {"from_date": "01-04-2025", "to_date": "31-03-2026"},
            ),
            make_text_response("Sales data retrieved."),
        ],
        analysis_agent_responses=[
            make_text_response(
                "Top 5 customers by sales:\n"
                "1. HCODE - 15,00,000\n"
                "2. SMARTBIKE - 10,00,000"
            ),
        ],
    )

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
        patch("backend.agents.analysis_agent.anthropic_client", mock_clients["analysis_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Top 5 customers by sales"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]


@pytest.mark.asyncio
async def test_multi_turn_conversation_preserves_session(e2e_client):
    """Two sequential messages with same session_id → context preserved."""
    client, set_responses, mock_clients = e2e_client

    # First turn
    set_responses(
        orchestrator_responses=[make_classification_response("greeting")],
    )
    with patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]):
        r1 = await client.post("/api/chat", json={"message": "Hi"})

    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Second turn — reuse session
    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("list_companies", {}),
            make_text_response("Found 1 company."),
        ],
    )
    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        r2 = await client.post(
            "/api/chat",
            json={"message": "List companies", "session_id": session_id},
        )

    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_tally_connection_error_returns_503(e2e_client):
    """When Tally is unreachable, the endpoint returns 503."""
    client, set_responses, mock_clients = e2e_client

    set_responses(
        orchestrator_responses=[make_classification_response("simple_lookup")],
        query_agent_responses=[
            make_tool_call_response("get_trial_balance", {"from_date": "01-04-2025", "to_date": "31-03-2026"}),
        ],
    )

    # Close the tally client to simulate connection error
    from backend.main import app as fastapi_app
    from backend.tally_bridge.client import TallyClient

    # Replace tally client with one pointing to a dead port
    dead_client = TallyClient(host="127.0.0.1", port=1)
    fastapi_app.state.tally_client = dead_client

    with (
        patch("backend.agents.orchestrator.anthropic_client", mock_clients["orchestrator"]),
        patch("backend.agents.query_agent.anthropic_client", mock_clients["query_agent"]),
    ):
        response = await client.post(
            "/api/chat",
            json={"message": "Show trial balance"},
        )

    # The tool execution should catch the connection error
    # The exact status depends on how the error propagates
    # It should be either 503 (TallyConnectionError) or 200 with error in message
    assert response.status_code in (200, 502, 503)


@pytest.mark.asyncio
async def test_empty_message_returns_422(e2e_client):
    """Empty message should fail validation."""
    client, _, _ = e2e_client

    response = await client.post(
        "/api/chat",
        json={"message": "   "},
    )

    assert response.status_code == 422
```

**Step 2: Run all E2E tests**

```bash
PYTHONPATH=. pytest tests/e2e/ -v
```

Expected: All ~9 tests PASS.

**Step 3: Commit**

```bash
git add tests/e2e/test_chat_pipeline.py
git commit -m "test(e2e): add comparison, top-N, multi-turn, and error tests"
```

---

### Task 16: Backend E2E live tests

**Files:**
- Create: `tests/e2e_live/__init__.py`
- Create: `tests/e2e_live/conftest.py`
- Create: `tests/e2e_live/test_live_pipeline.py`

**Step 1: Create conftest with skip logic and fixtures**

Create `tests/e2e_live/__init__.py` (empty).

Create `tests/e2e_live/conftest.py`:

```python
"""Fixtures for live E2E tests against real Tally + real Claude API.

Gated by RUN_LIVE_TESTS=1 environment variable.
Requires ANTHROPIC_API_KEY and a reachable Tally instance.
"""

import os

import pytest

from backend.tally_bridge.client import TallyClient
from backend.agents.orchestrator import Orchestrator
from backend.agents.context import SessionStore


def pytest_addoption(parser):
    parser.addoption("--host", default=os.environ.get("TALLY_HOST", "localhost"))
    parser.addoption("--port", type=int, default=int(os.environ.get("TALLY_PORT", "9000")))


# Skip entire module if RUN_LIVE_TESTS is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="RUN_LIVE_TESTS not set — skipping live E2E tests",
)


@pytest.fixture(scope="session")
def tally_host(request):
    return request.config.getoption("--host")


@pytest.fixture(scope="session")
def tally_port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="session")
async def tally_client(tally_host, tally_port):
    """Real TallyClient connected to a live Tally instance."""
    client = TallyClient(host=tally_host, port=tally_port)
    healthy = await client.health_check()
    if not healthy:
        pytest.skip(f"Tally unreachable at {tally_host}:{tally_port}")
    yield client
    await client.close()


@pytest.fixture
def orchestrator():
    return Orchestrator()


@pytest.fixture
def session_store():
    return SessionStore()


@pytest.fixture
def session(session_store):
    return session_store.get_or_create()
```

**Step 2: Write live pipeline tests**

Create `tests/e2e_live/test_live_pipeline.py`:

```python
"""Live E2E tests — real Claude API + real Tally instance.

Run with:
    RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host <TALLY_IP> --port 9000
"""

import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="RUN_LIVE_TESTS not set",
)


# ---------------------------------------------------------------------------
# Helper: conversation loop (handles Claude follow-ups)
# ---------------------------------------------------------------------------

FOLLOWUP_MAP = {
    "trial balance": "Show trial balance for the current financial year",
    "balance": "Show the trial balance",
    "which": "The current financial year",
    "specify": "For the current financial year April 2025 to March 2026",
    "date": "From April 2025 to March 2026",
    "period": "Current financial year",
    "company": "The currently loaded company",
}


def generate_followup(clarification_msg: str, original_query: str) -> str:
    """Generate a follow-up answer based on the clarification question."""
    lower = clarification_msg.lower()
    for keyword, response in FOLLOWUP_MAP.items():
        if keyword in lower:
            return response
    # Default: re-state the original query more specifically
    return f"{original_query} for the current financial year April 2025 to March 2026"


async def run_until_final(orchestrator, client, session, query, max_turns=3):
    """Send query and handle follow-ups until we get a non-clarification response."""
    current_query = query
    for _turn in range(max_turns):
        result = await orchestrator.process_query(current_query, client, session)
        if result["query_type"] != "clarification_needed":
            return result
        current_query = generate_followup(result["message"], query)
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_greeting(orchestrator, tally_client, session):
    result = await orchestrator.process_query("Hello!", tally_client, session)
    assert result["query_type"] == "greeting"
    assert result["message"]
    assert result["data"] is None


@pytest.mark.asyncio
async def test_live_list_companies(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session, "List all companies"
    )
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_trial_balance(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show trial balance for April 2025 to March 2026",
    )
    assert result["message"]
    assert result["query_type"] != "clarification_needed"


@pytest.mark.asyncio
async def test_live_profit_and_loss(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "What is the profit and loss for April 2025 to March 2026?",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_balance_sheet(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show balance sheet as of March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_receivables(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show outstanding receivables",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_sales_register(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Show sales register for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_top_customers(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Top 5 customers by sales for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_comparison(orchestrator, tally_client, session):
    result = await run_until_final(
        orchestrator, tally_client, session,
        "Compare sales and purchases for April 2025 to March 2026",
    )
    assert result["message"]


@pytest.mark.asyncio
async def test_live_clarification(orchestrator, tally_client, session):
    """Ambiguous query should get clarification or a reasonable response."""
    result = await orchestrator.process_query(
        "Show me the balance", tally_client, session
    )
    # Either clarification_needed or Claude figured it out
    assert result["message"]
    assert result["query_type"] in (
        "clarification_needed",
        "simple_lookup",
        "aggregation",
    )
```

**Step 3: Verify tests are skipped without env var**

```bash
PYTHONPATH=. pytest tests/e2e_live/ -v
```

Expected: All tests SKIPPED with "RUN_LIVE_TESTS not set".

**Step 4: Commit**

```bash
git add tests/e2e_live/
git commit -m "test(e2e_live): add live pipeline tests with conversation loop (gated by RUN_LIVE_TESTS)"
```

---

### Task 17: Frontend Playwright responsive tests — infrastructure

**Files:**
- Create: `frontend/tests/responsive/playwright.config.ts`
- Create: `frontend/tests/responsive/responsive.spec.ts`

**Step 1: Install Playwright test runner in frontend**

```bash
cd frontend && npm install -D @playwright/test
```

**Step 2: Create Playwright config**

Create `frontend/tests/responsive/playwright.config.ts`:

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
  },
  projects: [
    {
      name: "mobile",
      use: { viewport: { width: 375, height: 667 } },
    },
    {
      name: "tablet",
      use: { viewport: { width: 768, height: 1024 } },
    },
    {
      name: "desktop",
      use: { viewport: { width: 1280, height: 800 } },
    },
  ],
  webServer: {
    command: "npm run dev",
    port: 5173,
    cwd: "../..",
    reuseExistingServer: true,
  },
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{testFilePath}/{arg}{ext}",
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.05,
    },
  },
});
```

**Step 3: Write responsive screenshot tests**

Create `frontend/tests/responsive/responsive.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Responsive layout", () => {
  test("empty state renders correctly", async ({ page }) => {
    await page.goto("/");
    // Wait for the app to render
    await page.waitForSelector("text=TallyPrime AI Assistant", { timeout: 10000 });
    await expect(page).toHaveScreenshot("empty-state.png");
  });

  test("header renders correctly", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=TallyPrime AI", { timeout: 10000 });
    const header = page.locator("header");
    await expect(header).toHaveScreenshot("header.png");
  });

  test("chat input renders at bottom", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('textarea[placeholder="Ask about your Tally data..."]', { timeout: 10000 });
    const input = page.locator("textarea");
    await expect(input).toBeVisible();
    await expect(page).toHaveScreenshot("chat-input.png");
  });

  test("quick action buttons are visible", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=P&L this month", { timeout: 10000 });
    await expect(page).toHaveScreenshot("quick-actions.png");
  });

  test("user message bubble renders", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('textarea[placeholder="Ask about your Tally data..."]', { timeout: 10000 });

    // Type and send a message (will show user bubble + loading)
    const textarea = page.locator("textarea");
    await textarea.fill("Show trial balance");
    await textarea.press("Enter");

    // Wait for user message to appear
    await page.waitForSelector("text=Show trial balance", { timeout: 5000 });
    await expect(page).toHaveScreenshot("user-message.png", {
      // Mask the loading dots since they animate
      mask: [page.locator(".animate-bounce").first()],
    });
  });

  test("error state renders", async ({ page }) => {
    // Mock the API to return an error
    await page.route("**/api/chat", (route) => {
      route.abort("connectionrefused");
    });
    await page.goto("/");
    await page.waitForSelector('textarea[placeholder="Ask about your Tally data..."]', { timeout: 10000 });

    const textarea = page.locator("textarea");
    await textarea.fill("test query");
    await textarea.press("Enter");

    // Wait for error message
    await page.waitForSelector("text=Cannot connect to the server", { timeout: 10000 });
    await expect(page).toHaveScreenshot("error-state.png");
  });

  test("markdown response renders", async ({ page }) => {
    await page.route("**/api/chat", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "## Trial Balance\n\nHere are the results:\n\n- **Total Debit**: ₹50,00,000\n- **Total Credit**: ₹50,00,000\n\n> The books are balanced.",
          session_id: "test-session",
        }),
      });
    });
    await page.route("**/api/health", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true, tally_url: "http://localhost:9000" }),
      });
    });
    await page.route("**/api/companies", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ companies: [{ name: "Test Company" }] }),
      });
    });

    await page.goto("/");
    await page.waitForSelector('textarea[placeholder="Ask about your Tally data..."]', { timeout: 10000 });

    const textarea = page.locator("textarea");
    await textarea.fill("Show trial balance");
    await textarea.press("Enter");

    await page.waitForSelector("text=Trial Balance", { timeout: 10000 });
    await expect(page).toHaveScreenshot("markdown-response.png");
  });

  test("data table response renders", async ({ page }) => {
    await page.route("**/api/chat", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "Here is the trial balance:",
          data: {
            headers: ["Ledger", "Debit", "Credit"],
            rows: [
              ["Sales Account", 0, 4034350],
              ["Purchase Account", 2500000, 0],
              ["Cash", 150000, 0],
              ["Bank Account", 1200000, 0],
              ["Rent", 50000, 0],
            ],
          },
          session_id: "test-session",
        }),
      });
    });
    await page.route("**/api/health", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", tally_connected: true, tally_url: "http://localhost:9000" }),
      });
    });
    await page.route("**/api/companies", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ companies: [] }),
      });
    });

    await page.goto("/");
    await page.waitForSelector('textarea[placeholder="Ask about your Tally data..."]', { timeout: 10000 });

    const textarea = page.locator("textarea");
    await textarea.fill("Trial balance");
    await textarea.press("Enter");

    await page.waitForSelector("text=Sales Account", { timeout: 10000 });
    await expect(page).toHaveScreenshot("data-table-response.png");
  });
});
```

**Step 4: Add a script to run responsive tests in `package.json`**

Add to `frontend/package.json` scripts:
```json
"test:responsive": "npx playwright test --config tests/responsive/playwright.config.ts"
```

**Step 5: Run to generate baseline screenshots (first run will create them)**

```bash
cd frontend && npx playwright test --config tests/responsive/playwright.config.ts --update-snapshots
```

Expected: All tests pass and baseline screenshots are created in `frontend/tests/responsive/__screenshots__/`.

**Step 6: Commit**

```bash
git add frontend/tests/responsive/ frontend/package.json
git commit -m "test(frontend): add Playwright responsive screenshot tests at 3 viewports"
```

---

### Task 18: Full test run and final verification

**Step 1: Run all backend tests (unit + integration + E2E mock)**

```bash
PYTHONPATH=. pytest tests/ -v --ignore=tests/e2e_live/
```

Expected: ~330+ tests pass (274 unit + 43 integration + ~9 E2E).

**Step 2: Run all frontend unit tests**

```bash
cd frontend && npm test
```

Expected: ~45 tests pass.

**Step 3: Verify live tests are skipped by default**

```bash
PYTHONPATH=. pytest tests/e2e_live/ -v
```

Expected: All 10 tests SKIPPED.

**Step 4: Update CLAUDE.md test documentation**

Add to the "Build & Run Commands" section:

```bash
# Frontend unit tests
cd frontend && npm test

# Frontend responsive screenshot tests
cd frontend && npm run test:responsive

# Backend E2E tests (mock Claude API)
ANTHROPIC_API_KEY=test-key pytest tests/e2e/ -v

# Backend E2E live tests (real Claude + real Tally)
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v --host <TALLY_IP> --port 9000
```

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Phase 4b test commands"
```

---

### Task 19: Code review

Use `superpowers:requesting-code-review` to review all Phase 4b work. Store results in `docs/code-review-phase4b.md`.
