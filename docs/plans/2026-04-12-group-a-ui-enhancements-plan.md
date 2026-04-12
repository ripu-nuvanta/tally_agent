# Group A: UI/UX Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement F4 (new chat flow with deferred conversation creation), F5 (voucher button disable), F6 (responsive layout with hamburger drawer) — all frontend changes, TDD approach.

**Architecture:** Modify ChatApp (drawer + header + deferred creation), ChatWindow (deferred send), VoucherReviewCard (button states), Sidebar (workspace highlight), App (new route). Add responsive Tailwind classes throughout.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, Vitest, React Testing Library, Playwright

**Spec:** `docs/specs/2026-04-12-group-a-ui-enhancements-design.md`

---

## Current File Inventory (verified)

| File | Key State |
|------|-----------|
| `frontend/src/ChatApp.tsx` | 72 lines. State: `conversationId` (useParams), `activeWorkspaceId`, `activeWorkspaceName`, `sidebarRefresh`. `handleNewChat` calls `createConversation` immediately. Header is single-line with pipe separator. Layout: `flex` with Sidebar + ChatWindow, no responsive classes. |
| `frontend/src/components/ChatWindow.tsx` | 187 lines. Props: `{ conversationId?, workspaceId?, onMessageSent? }`. `handleSend` sends to API directly — no deferred creation. `handleVoucherAction` has no pending state. Landing page shows "TallyPrime AI Assistant" + "Ask me anything about your accounting data". |
| `frontend/src/components/VoucherReviewCard.tsx` | 291 lines. `VoucherEntry.status`: "draft"/"written"/"deleted". Buttons show when `status === "draft"`. No "pending" state. No `pendingAction` prop. |
| `frontend/src/components/Sidebar.tsx` | 87 lines. Active workspace: bold text only. `onNewChat` prop called directly by ConversationList. No bg highlight class. |
| `frontend/src/components/ConversationList.tsx` | 28 lines. `onNewChat` button calls parent callback. No navigation logic here. |
| `frontend/src/App.tsx` | 59 lines. Routes: `/login`, `/register`, `/c/:conversationId`, `/*`. No `/w/:workspaceId` route. |
| `frontend/src/api/client.ts` | `createConversation(workspaceId, req?)` already exported. All APIs needed exist. |
| `frontend/src/types/index.ts` | `WorkspaceData.config: Record<string, unknown>` — `mock_mode` lives here. |
| `frontend/src/components/ConnectCompanyModal.tsx` | 71 lines. Modal width: `w-full max-w-md`. No mobile margin classes. |
| `frontend/src/components/ChatInput.tsx` | 88 lines. Placeholder: "Ask about your Tally data...". |
| `frontend/src/__tests__/VoucherReviewCard.test.tsx` | 9 tests. Tests draft/written states, edit form, callbacks. |
| `frontend/src/__tests__/ChatApp.test.tsx` | 5 tests. Uses `MemoryRouter`. Routes: `/` and `/c/:conversationId`. |
| `frontend/src/__tests__/Sidebar.test.tsx` | 7 tests. Tests workspace rendering, collapse, modal open. |
| `frontend/src/__tests__/ChatWindow.test.tsx` | 13 tests. Tests welcome, send, errors, page-reload workspace resolution. |
| `frontend/tests/playwright/db-mode.spec.ts` | 5 tests. Login, register, sidebar, chat-with-header, voucher-review-card. |

## Test Count Baseline

- Vitest frontend: **181 tests**
- Playwright db-mode: **5 tests** (x3 viewports = 15 runs)
- Target after plan: **~201+ Vitest** (20 new) + **8 Playwright** (3 new specs) = **~224+ total runs**

---

## Task 1: F5 — VoucherReviewCard Button Disable (Pending State)

**Scope:** Add `pendingAction` prop to VoucherReviewCard so buttons disable during API call, with spinner on the clicked button. Update ChatWindow.handleVoucherAction to set entry status to "pending" before API call.

**Files modified:** `VoucherReviewCard.tsx`, `ChatWindow.tsx`
**Test file:** `frontend/src/__tests__/VoucherReviewCard.test.tsx` (expand existing)

### Steps

- [ ] **1.1 — Write failing tests** in `frontend/src/__tests__/VoucherReviewCard.test.tsx`

Add these tests to the existing `describe("VoucherReviewCard", ...)` block:

```tsx
it("disables all buttons when status is pending", () => {
  render(
    <VoucherReviewCard
      entries={[{ ...mockEntry, status: "pending" }]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
    />
  );
  expect(screen.getByText("Write to Tally").closest("button")).toBeDisabled();
  expect(screen.getByText("Edit Entry").closest("button")).toBeDisabled();
  expect(screen.getByText("Discard").closest("button")).toBeDisabled();
});

it("shows spinner on approve button when pendingAction is approve", () => {
  render(
    <VoucherReviewCard
      entries={[{ ...mockEntry, status: "pending" }]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
      pendingAction={{ entryId: "test-1", action: "approve" }}
    />
  );
  const writeBtn = screen.getByText("Write to Tally").closest("button")!;
  expect(writeBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
  expect(writeBtn).toBeDisabled();
});

it("shows spinner on discard button when pendingAction is discard", () => {
  render(
    <VoucherReviewCard
      entries={[{ ...mockEntry, status: "pending" }]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
      pendingAction={{ entryId: "test-1", action: "discard" }}
    />
  );
  const discardBtn = screen.getByText("Discard").closest("button")!;
  expect(discardBtn.querySelector('[data-testid="spinner"]')).toBeInTheDocument();
  expect(discardBtn).toBeDisabled();
});

it("shows Pending label in status when status is pending", () => {
  render(
    <VoucherReviewCard
      entries={[{ ...mockEntry, status: "pending" }]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
    />
  );
  expect(screen.getByText(/Pending/)).toBeInTheDocument();
});
```

- [ ] **1.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/VoucherReviewCard.test.tsx
```

Expected: 4 new tests fail (pending status not handled, pendingAction prop doesn't exist).

- [ ] **1.3 — Implement VoucherReviewCard changes** in `frontend/src/components/VoucherReviewCard.tsx`

Add `pendingAction` to the props interface:

```tsx
interface VoucherReviewCardProps {
  entries: VoucherEntry[];
  availableLedgers: string[];
  availablePaymentLedgers: string[];
  onApprove: (entryId: string) => void;
  onDiscard: (entryId: string) => void;
  onEdit: (entryId: string, updates: Partial<VoucherEntry>) => void;
  pendingAction?: { entryId: string; action: "approve" | "discard" } | null;
}
```

Update the destructuring in the function signature to include `pendingAction`:

```tsx
export default function VoucherReviewCard({
  entries,
  availableLedgers,
  availablePaymentLedgers,
  onApprove,
  onDiscard,
  onEdit,
  pendingAction,
}: VoucherReviewCardProps) {
```

Add a small Spinner component inside the file (above the main export):

```tsx
function Spinner() {
  return (
    <svg data-testid="spinner" className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
```

Update the status label to include "pending":

```tsx
<span className="text-sm font-medium text-gray-700">
  Expense Entry — {
    entry.status === "written"
      ? "Written"
      : entry.status === "deleted"
      ? "Discarded"
      : entry.status === "pending"
      ? "Pending"
      : "Draft"
  }
</span>
```

Change the button rendering condition from `entry.status === "draft"` to `entry.status === "draft" || entry.status === "pending"`, and add disabled + spinner logic:

```tsx
{(entry.status === "draft" || entry.status === "pending") && (
  <div className="flex flex-wrap gap-2 mt-3">
    <button
      type="button"
      onClick={() => onApprove(entry.id)}
      disabled={entry.status === "pending"}
      className={`px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm transition-colors flex items-center gap-1.5 ${
        entry.status === "pending" ? "opacity-50 cursor-not-allowed" : "hover:bg-green-700"
      }`}
    >
      {pendingAction?.entryId === entry.id && pendingAction.action === "approve" && <Spinner />}
      Write to Tally
    </button>
    <button
      type="button"
      onClick={() => setEditingId(entry.id)}
      disabled={entry.status === "pending"}
      className={`px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-700 text-sm transition-colors ${
        entry.status === "pending" ? "opacity-50 cursor-not-allowed" : "hover:bg-gray-50"
      }`}
    >
      Edit Entry
    </button>
    <button
      type="button"
      onClick={() => onDiscard(entry.id)}
      disabled={entry.status === "pending"}
      className={`px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-600 text-sm transition-colors flex items-center gap-1.5 ${
        entry.status === "pending" ? "opacity-50 cursor-not-allowed" : "hover:bg-red-50"
      }`}
    >
      {pendingAction?.entryId === entry.id && pendingAction.action === "discard" && <Spinner />}
      Discard
    </button>
  </div>
)}
```

Also update the border color for pending status in the card wrapper:

```tsx
className={`rounded-lg border p-4 ${
  entry.status === "written"
    ? "border-green-200 bg-green-50"
    : entry.status === "deleted"
    ? "border-gray-200 bg-gray-50 opacity-60"
    : entry.status === "pending"
    ? "border-yellow-200 bg-yellow-50"
    : "border-blue-200 bg-blue-50"
}`}
```

- [ ] **1.4 — Update ChatWindow.handleVoucherAction** in `frontend/src/components/ChatWindow.tsx`

The `handleVoucherAction` needs to update the entry status to "pending" in the messages array before calling the API, and revert to "draft" on error. Also track which action is pending.

Add state for pending action tracking at the top of the component:

```tsx
const [pendingVoucherAction, setPendingVoucherAction] = useState<{
  entryId: string;
  action: "approve" | "discard";
} | null>(null);
```

Update `handleVoucherAction` to set pending status before API call:

```tsx
const handleVoucherAction = useCallback(
  async (action: VoucherAction, entry: Record<string, unknown>) => {
    const entryId = entry.id as string;

    // Set entry status to pending (optimistic UI)
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
```

Pass `pendingVoucherAction` to MessageBubble (which passes it to VoucherReviewCard). This requires updating MessageBubble to accept and forward the prop. In the JSX:

```tsx
{messages.map((msg) => (
  <MessageBubble key={msg.id} message={msg} onVoucherAction={handleVoucherAction} pendingVoucherAction={pendingVoucherAction} />
))}
```

Update `MessageBubble.tsx` to accept and forward `pendingVoucherAction` prop to `VoucherReviewCard`:
- Add `pendingVoucherAction?: { entryId: string; action: "approve" | "discard" } | null` to `MessageBubbleProps`
- Pass `pendingAction={pendingVoucherAction}` to `<VoucherReviewCard>` where it's rendered

- [ ] **1.5 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/VoucherReviewCard.test.tsx
```

Expected: All 13 tests pass (9 existing + 4 new).

- [ ] **1.6 — Commit**

```
feat(F5): add pending state to VoucherReviewCard buttons

Buttons disable on click with spinner. Entry status transitions:
draft -> pending -> written/discarded (on error: reverts to draft).
```

---

## Task 2: F6 — Responsive Sidebar (Hamburger Drawer)

**Scope:** Hide sidebar on mobile (`< md`), add hamburger button in header, drawer overlay on mobile.

**Files modified:** `ChatApp.tsx`
**Test file:** `frontend/src/__tests__/ChatApp.test.tsx` (expand existing)

### Steps

- [ ] **2.1 — Write failing tests** in `frontend/src/__tests__/ChatApp.test.tsx`

Update the `renderChatApp` helper to include the new `/w/:workspaceId` route (needed for Task 5 but harmless here):

```tsx
function renderChatApp(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<ChatApp />} />
        <Route path="/c/:conversationId" element={<ChatApp />} />
        <Route path="/w/:workspaceId" element={<ChatApp />} />
      </Routes>
    </MemoryRouter>
  );
}
```

Add these tests:

```tsx
it("sidebar wrapper has hidden md:flex classes for responsive behavior", async () => {
  renderChatApp();
  await waitFor(() => {
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
  });
  // The sidebar wrapper should have responsive classes
  const sidebar = screen.getByText("Bharat Traders").closest("aside")!;
  const sidebarWrapper = sidebar.parentElement!;
  expect(sidebarWrapper.className).toContain("hidden");
  expect(sidebarWrapper.className).toContain("md:flex");
});

it("renders hamburger button with md:hidden class", async () => {
  renderChatApp();
  await waitFor(() => {
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
  });
  const hamburger = screen.getByRole("button", { name: /open sidebar/i });
  expect(hamburger.className).toContain("md:hidden");
});

it("shows mobile drawer overlay when hamburger is clicked", async () => {
  const user = userEvent.setup();
  renderChatApp();
  await waitFor(() => {
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
  });
  const hamburger = screen.getByRole("button", { name: /open sidebar/i });
  await user.click(hamburger);
  // Drawer overlay should be present
  const overlay = document.querySelector('[data-testid="sidebar-overlay"]');
  expect(overlay).toBeInTheDocument();
});

it("closes mobile drawer when overlay backdrop is clicked", async () => {
  const user = userEvent.setup();
  renderChatApp();
  await waitFor(() => {
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
  });
  const hamburger = screen.getByRole("button", { name: /open sidebar/i });
  await user.click(hamburger);
  const backdrop = document.querySelector('[data-testid="sidebar-backdrop"]')!;
  await user.click(backdrop);
  expect(document.querySelector('[data-testid="sidebar-overlay"]')).not.toBeInTheDocument();
});
```

- [ ] **2.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/ChatApp.test.tsx
```

Expected: 4 new tests fail (no hamburger, no responsive classes, no drawer).

- [ ] **2.3 — Implement responsive layout** in `frontend/src/ChatApp.tsx`

Add `sidebarOpen` state and `Menu` icon import:

```tsx
import { Menu } from "lucide-react";
// ... existing imports

export default function ChatApp() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [activeWorkspaceName, setActiveWorkspaceName] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
```

Update `handleConversationSelect` to close drawer:

```tsx
const handleConversationSelect = useCallback(
  (workspaceId: string, convId: string, workspaceName: string) => {
    setActiveWorkspaceId(workspaceId);
    setActiveWorkspaceName(workspaceName);
    navigate(`/c/${convId}`);
    setSidebarOpen(false);
  },
  [navigate],
);
```

Replace the header with two-line layout and hamburger (also part of Task 4, but the hamburger is Task 2):

In the `<header>`:
```tsx
<header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
  <div className="flex items-center gap-3">
    <button
      type="button"
      onClick={() => setSidebarOpen(true)}
      className="md:hidden p-1 -ml-1 text-gray-500 hover:text-gray-900"
      aria-label="Open sidebar"
    >
      <Menu className="w-5 h-5" />
    </button>
    <h1 className="text-lg font-semibold text-gray-900">TallyPrime AI</h1>
    {activeWorkspaceName && (
      <span className="text-sm text-gray-500 border-l border-gray-200 pl-3">{activeWorkspaceName}</span>
    )}
  </div>
  <div className="flex items-center gap-3">
    <UserMenu />
  </div>
</header>
```

Replace the body layout:

```tsx
<div className="flex-1 flex overflow-hidden">
  {/* Desktop sidebar — always visible on md+ */}
  <div className="hidden md:flex">
    <Sidebar
      activeConversationId={conversationId}
      activeWorkspaceId={activeWorkspaceId || undefined}
      onConversationSelect={handleConversationSelect}
      onNewChat={handleNewChat}
      refreshTrigger={sidebarRefresh}
      onWorkspaceResolved={handleWorkspaceResolved}
    />
  </div>

  {/* Mobile drawer overlay */}
  {sidebarOpen && (
    <div className="fixed inset-0 z-40 md:hidden" data-testid="sidebar-overlay">
      <div
        className="fixed inset-0 bg-black/50"
        data-testid="sidebar-backdrop"
        onClick={() => setSidebarOpen(false)}
      />
      <div className="fixed inset-y-0 left-0 w-72 bg-white shadow-xl z-50">
        <Sidebar
          activeConversationId={conversationId}
          activeWorkspaceId={activeWorkspaceId || undefined}
          onConversationSelect={handleConversationSelect}
          onNewChat={handleNewChat}
          refreshTrigger={sidebarRefresh}
          onWorkspaceResolved={handleWorkspaceResolved}
        />
      </div>
    </div>
  )}

  <main className="flex-1 overflow-hidden">
    <ChatWindow conversationId={conversationId} workspaceId={activeWorkspaceId || undefined} onMessageSent={() => setSidebarRefresh((n) => n + 1)} />
  </main>
</div>
```

- [ ] **2.4 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/ChatApp.test.tsx
```

Expected: All 9 tests pass (5 existing + 4 new).

- [ ] **2.5 — Commit**

```
feat(F6): add responsive sidebar with hamburger drawer on mobile

Sidebar hidden on mobile (< md breakpoint), hamburger button opens
drawer overlay. Backdrop click or conversation select closes drawer.
```

---

## Task 3: F6 — Responsive VoucherReviewCard + ConnectCompanyModal

**Scope:** Add responsive grid classes to VoucherReviewCard and mobile-safe width to ConnectCompanyModal.

**Files modified:** `VoucherReviewCard.tsx`, `ConnectCompanyModal.tsx`
**Test files:** Expand `VoucherReviewCard.test.tsx`, add new `ConnectCompanyModal.test.tsx`

### Steps

- [ ] **3.1 — Write failing tests**

In `frontend/src/__tests__/VoucherReviewCard.test.tsx`, add:

```tsx
it("uses responsive grid classes on field grid", () => {
  render(
    <VoucherReviewCard
      entries={[mockEntry]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
    />
  );
  const grid = screen.getByText("Vendor:").closest("div")!.parentElement!;
  expect(grid.className).toContain("grid-cols-1");
  expect(grid.className).toContain("md:grid-cols-2");
});

it("uses flex-wrap on action buttons container", () => {
  render(
    <VoucherReviewCard
      entries={[mockEntry]}
      availableLedgers={[]}
      availablePaymentLedgers={[]}
      onApprove={noop}
      onDiscard={noop}
      onEdit={noop}
    />
  );
  const writeBtn = screen.getByText("Write to Tally");
  const btnContainer = writeBtn.closest("button")!.parentElement!;
  expect(btnContainer.className).toContain("flex-wrap");
});
```

Create `frontend/src/__tests__/ConnectCompanyModal.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ConnectCompanyModal from "../components/ConnectCompanyModal";

vi.mock("../api/client");

describe("ConnectCompanyModal", () => {
  it("renders modal with mobile-safe width classes", () => {
    render(<ConnectCompanyModal onClose={vi.fn()} onCreated={vi.fn()} />);
    const modalPanel = screen.getByText("Connect Tally Company").closest("div")!;
    expect(modalPanel.className).toContain("mx-4");
    expect(modalPanel.className).toContain("md:mx-auto");
    expect(modalPanel.className).toContain("md:max-w-md");
  });
});
```

- [ ] **3.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/VoucherReviewCard.test.tsx src/__tests__/ConnectCompanyModal.test.tsx
```

- [ ] **3.3 — Implement responsive classes**

In `VoucherReviewCard.tsx`, change the field grid from:
```tsx
<div className="grid grid-cols-2 gap-2 text-sm mb-3">
```
to:
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm mb-3">
```

The button container change from Task 1 already uses `flex flex-wrap gap-2 mt-3`. If Task 1 kept the original `flex gap-2 mt-3`, update to:
```tsx
<div className="flex flex-wrap gap-2 mt-3">
```

In `ConnectCompanyModal.tsx`, change the modal panel from:
```tsx
<div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
```
to:
```tsx
<div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
```

- [ ] **3.4 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/VoucherReviewCard.test.tsx src/__tests__/ConnectCompanyModal.test.tsx
```

- [ ] **3.5 — Commit**

```
feat(F6): add responsive grid and mobile-safe modal classes

VoucherReviewCard fields stack on mobile (grid-cols-1 md:grid-cols-2).
ConnectCompanyModal uses mobile margins (mx-4 md:mx-auto md:max-w-md).
```

---

## Task 4: F4 — Two-Line Header with Demo/Live Badge

**Scope:** Replace single-line header in ChatApp with two-line layout (title + workspace name), add demo/live badge from workspace config.

**Files modified:** `ChatApp.tsx`
**Test file:** `frontend/src/__tests__/ChatApp.test.tsx` (expand)

### Steps

- [ ] **4.1 — Write failing tests** in `frontend/src/__tests__/ChatApp.test.tsx`

Add `activeWorkspaceConfig` state support. Update mock workspace to include `mock_mode`:

```tsx
const mockWorkspaceDemo = {
  ...mockWorkspace,
  config: { tally_host: "localhost", tally_port: 9000, mock_mode: true },
};

const mockWorkspaceLive = {
  ...mockWorkspace,
  config: { tally_host: "localhost", tally_port: 9000, mock_mode: false },
};
```

Add tests:

```tsx
it("renders two-line header with title and workspace subtitle", async () => {
  renderChatApp("/c/conv-1");
  await waitFor(() => {
    // Title line
    expect(screen.getByText("TallyPrime AI")).toBeInTheDocument();
    // Workspace subtitle line (separate element from sidebar instance)
    const headerEl = document.querySelector("header")!;
    expect(headerEl.textContent).toContain("Bharat Traders");
  });
});

it("shows workspace subtitle with truncate class for long names", async () => {
  const longNameWs = { ...mockWorkspace, name: "A Very Long Company Name That Should Truncate" };
  mockedClient.getWorkspaces.mockResolvedValue([longNameWs]);
  mockedClient.getConversations.mockResolvedValue([mockConversation]);

  renderChatApp("/c/conv-1");
  await waitFor(() => {
    const header = document.querySelector("header")!;
    const subtitle = header.querySelector('[data-testid="header-workspace-name"]');
    expect(subtitle).toBeInTheDocument();
    expect(subtitle!.className).toContain("truncate");
  });
});

it("shows Demo badge when workspace mock_mode is true", async () => {
  mockedClient.getWorkspaces.mockResolvedValue([mockWorkspaceDemo]);
  mockedClient.getConversations.mockResolvedValue([mockConversation]);

  renderChatApp("/c/conv-1");
  await waitFor(() => {
    expect(screen.getByText("Demo")).toBeInTheDocument();
  });
});

it("shows Live badge when workspace mock_mode is false", async () => {
  mockedClient.getWorkspaces.mockResolvedValue([mockWorkspaceLive]);
  mockedClient.getConversations.mockResolvedValue([mockConversation]);

  renderChatApp("/c/conv-1");
  await waitFor(() => {
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
});
```

- [ ] **4.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/ChatApp.test.tsx
```

- [ ] **4.3 — Implement two-line header + badge** in `frontend/src/ChatApp.tsx`

Add state to track workspace config:

```tsx
const [activeWorkspaceConfig, setActiveWorkspaceConfig] = useState<Record<string, unknown>>({});
```

Update `handleConversationSelect`, `handleNewChat`, and `handleWorkspaceResolved` to also receive and store the workspace config. This requires updating Sidebar's `onConversationSelect` and `onNewChat` callbacks to pass the full workspace. Alternatively, store a reference to the workspaces list.

**Simpler approach:** Add a `workspaces` ref in ChatApp that gets populated from Sidebar via a new callback, OR have ChatApp look up the config from `activeWorkspaceId` after sidebar resolves. The cleanest approach is to have `handleWorkspaceResolved` also receive config:

Update `handleWorkspaceResolved`:
```tsx
const handleWorkspaceResolved = useCallback(
  (wsId: string, wsName: string, wsConfig?: Record<string, unknown>) => {
    if (!activeWorkspaceId) {
      setActiveWorkspaceId(wsId);
      setActiveWorkspaceName(wsName);
      if (wsConfig) setActiveWorkspaceConfig(wsConfig);
    }
  },
  [activeWorkspaceId],
);
```

Update `handleConversationSelect`:
```tsx
const handleConversationSelect = useCallback(
  (workspaceId: string, convId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => {
    setActiveWorkspaceId(workspaceId);
    setActiveWorkspaceName(workspaceName);
    if (workspaceConfig) setActiveWorkspaceConfig(workspaceConfig);
    navigate(`/c/${convId}`);
    setSidebarOpen(false);
  },
  [navigate],
);
```

**Note:** The Sidebar `onConversationSelect` and `onWorkspaceResolved` signatures need to be updated. In Sidebar.tsx, the workspace data is already available when these are called. Update the calls:

In `Sidebar.tsx`:
- `onConversationSelect(ws.id, cid, ws.name)` → `onConversationSelect(ws.id, cid, ws.name, ws.config)`
- `onWorkspaceResolved(w.id, w.name)` → `onWorkspaceResolved(w.id, w.name, w.config)`

In `Sidebar.tsx` SidebarProps interface:
```tsx
onConversationSelect: (workspaceId: string, conversationId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => void;
onWorkspaceResolved?: (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => void;
```

Similarly update `handleNewChat`:
```tsx
const handleNewChat = useCallback(
  async (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => {
    // Will be changed to deferred creation in Task 6
    const conv = await createConversation(workspaceId);
    setActiveWorkspaceId(workspaceId);
    setActiveWorkspaceName(workspaceName);
    if (workspaceConfig) setActiveWorkspaceConfig(workspaceConfig);
    navigate(`/c/${conv.id}`);
  },
  [navigate],
);
```

In `Sidebar.tsx`, update `onNewChat` calls:
- `onNewChat(ws.id, ws.name)` → `onNewChat(ws.id, ws.name, ws.config)`

Update `SidebarProps`:
```tsx
onNewChat: (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => void;
```

Now implement the two-line header in ChatApp's JSX:

```tsx
<header className="border-b border-gray-200 bg-white px-4 py-3 flex items-center justify-between">
  <div className="flex items-center gap-3 min-w-0">
    <button
      type="button"
      onClick={() => setSidebarOpen(true)}
      className="md:hidden p-1 -ml-1 text-gray-500 hover:text-gray-900 shrink-0"
      aria-label="Open sidebar"
    >
      <Menu className="w-5 h-5" />
    </button>
    <div className="min-w-0">
      <h1 className="text-lg font-semibold text-gray-900 truncate">
        {conversationId ? "TallyPrime AI" : <span className="text-blue-600">New Chat</span>}
      </h1>
      {activeWorkspaceName && (
        <div className="flex items-center gap-2">
          <span data-testid="header-workspace-name" className="text-sm text-gray-500 truncate">
            {activeWorkspaceName}
          </span>
          {activeWorkspaceConfig.mock_mode !== undefined && (
            activeWorkspaceConfig.mock_mode ? (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                Demo
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                Live
              </span>
            )
          )}
        </div>
      )}
    </div>
  </div>
  <div className="flex items-center gap-3 shrink-0">
    <UserMenu />
  </div>
</header>
```

- [ ] **4.4 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/ChatApp.test.tsx
```

Also run Sidebar tests to confirm the prop changes don't break anything:
```bash
cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx
```

- [ ] **4.5 — Commit**

```
feat(F4): add two-line header with demo/live badge

Header shows title + workspace name on separate lines. Demo/Live badge
reads from workspace.config.mock_mode. Sidebar passes config through.
```

---

## Task 5: F4 — New Route `/w/:workspaceId` + Landing Page

**Scope:** Add `/w/:workspaceId` route to App.tsx. ChatApp reads `workspaceId` from URL params. ChatWindow shows workspace-aware landing page when no `conversationId`.

**Files modified:** `App.tsx`, `ChatApp.tsx`, `ChatWindow.tsx`
**Test files:** Expand `ChatApp.test.tsx`, `ChatWindow.test.tsx`

### Steps

- [ ] **5.1 — Write failing tests**

In `frontend/src/__tests__/ChatWindow.test.tsx`, add:

```tsx
it("shows workspace name on landing page when workspaceId is provided but no conversationId", () => {
  render(
    <SessionProvider>
      <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
    </SessionProvider>
  );
  expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
  expect(screen.getByText(/Bharat Traders/)).toBeInTheDocument();
});

it("shows landing page placeholder when on workspace route", () => {
  render(
    <SessionProvider>
      <ChatWindow workspaceId="ws-1" workspaceName="Bharat Traders" />
    </SessionProvider>
  );
  const textarea = screen.getByPlaceholderText(/Type or upload to start a conversation/);
  expect(textarea).toBeInTheDocument();
});
```

In `frontend/src/__tests__/ChatApp.test.tsx`, add:

```tsx
it("renders landing page when navigated to /w/:workspaceId", async () => {
  renderChatApp("/w/ws-1");
  await waitFor(() => {
    expect(screen.getByText("TallyPrime AI Assistant")).toBeInTheDocument();
  });
  // Should show workspace name from sidebar resolution
  await waitFor(() => {
    expect(screen.getAllByText("Bharat Traders").length).toBeGreaterThanOrEqual(1);
  });
});
```

- [ ] **5.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/ChatWindow.test.tsx src/__tests__/ChatApp.test.tsx
```

- [ ] **5.3 — Add route** in `frontend/src/App.tsx`

Add the new route before the catch-all:

```tsx
<Route path="/w/:workspaceId" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
<Route path="/c/:conversationId" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
<Route path="/*" element={<ProtectedRoute><ChatApp /></ProtectedRoute>} />
```

- [ ] **5.4 — Update ChatApp to read workspaceId from URL** in `frontend/src/ChatApp.tsx`

```tsx
const { conversationId, workspaceId: urlWorkspaceId } = useParams();
```

When `urlWorkspaceId` is present, set it as the active workspace on mount:

```tsx
useEffect(() => {
  if (urlWorkspaceId && !activeWorkspaceId) {
    setActiveWorkspaceId(urlWorkspaceId);
  }
}, [urlWorkspaceId, activeWorkspaceId]);
```

Pass `workspaceName` to ChatWindow:

```tsx
<ChatWindow
  conversationId={conversationId}
  workspaceId={activeWorkspaceId || urlWorkspaceId || undefined}
  workspaceName={activeWorkspaceName || undefined}
  onMessageSent={() => setSidebarRefresh((n) => n + 1)}
/>
```

- [ ] **5.5 — Update ChatWindow props and landing page** in `frontend/src/components/ChatWindow.tsx`

Add `workspaceName` to props:

```tsx
interface ChatWindowProps {
  conversationId?: string;
  workspaceId?: string;
  workspaceName?: string;
  onMessageSent?: () => void;
}

export default function ChatWindow({ conversationId, workspaceId, workspaceName, onMessageSent }: ChatWindowProps) {
```

Update the landing page (empty state) to show workspace name and different placeholder:

```tsx
{messages.length === 0 && (
  <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-6">
    <div className="text-center">
      <h2 className="text-2xl font-semibold text-gray-800 mb-2">
        TallyPrime AI Assistant
      </h2>
      <p className="text-gray-500">
        {workspaceName
          ? <>Connected to <strong>{workspaceName}</strong></>
          : "Ask me anything about your accounting data"
        }
      </p>
    </div>
    <QuickActions onSelect={handleSend} disabled={loading} />
  </div>
)}
```

Update ChatInput placeholder based on whether we're on a landing page (no conversationId):

Pass a `placeholderText` or handle it in ChatInput. Simpler approach: change the placeholder prop in ChatInput:

```tsx
<ChatInput
  onSend={handleSend}
  disabled={loading}
  placeholder={!conversationId && workspaceId ? "Type or upload to start a conversation..." : undefined}
/>
```

Add optional `placeholder` prop to ChatInput:

```tsx
interface ChatInputProps {
  onSend: (message: string, file?: File) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  // ...
  // In the textarea:
  placeholder={attachedFile ? "Add a note (optional)..." : (placeholder || "Ask about your Tally data...")}
```

- [ ] **5.6 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/ChatWindow.test.tsx src/__tests__/ChatApp.test.tsx
```

- [ ] **5.7 — Commit**

```
feat(F4): add /w/:workspaceId route and workspace-aware landing page

New route shows landing page with "Connected to {workspace}" subtitle.
Input placeholder changes to "Type or upload to start a conversation".
```

---

## Task 6: F4 — Deferred Conversation Creation

**Scope:** When on landing page (no conversationId), first send creates a conversation in DB, then sends the message. Same for file upload and quick actions.

**Files modified:** `ChatWindow.tsx`, `ChatApp.tsx`
**Test file:** New `frontend/src/__tests__/ChatWindow.deferred.test.tsx`

### Steps

- [ ] **6.1 — Write failing tests** in new file `frontend/src/__tests__/ChatWindow.deferred.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ChatWindow from "../components/ChatWindow";
import { SessionProvider } from "../context/SessionContext";
import * as api from "../api/client";

vi.mock("../api/client");
const mockedApi = vi.mocked(api);

Element.prototype.scrollIntoView = vi.fn();

// Track navigation
let navigatedTo: string | null = null;
function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={["/w/ws-1"]}>
      <SessionProvider>
        <Routes>
          <Route path="/w/:workspaceId" element={children} />
          <Route path="/c/:conversationId" element={<div data-testid="conv-page">Conversation Page</div>} />
        </Routes>
      </SessionProvider>
    </MemoryRouter>
  );
}

describe("ChatWindow deferred conversation creation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    navigatedTo = null;
    mockedApi.createConversation.mockResolvedValue({
      id: "new-conv-1",
      title: null,
      tag: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    mockedApi.sendChat.mockResolvedValue({
      message: "Response",
      session_id: "sess-1",
    });
  });

  it("creates conversation then sends message when conversationId is undefined", async () => {
    const onConversationCreated = vi.fn();
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <ChatWindow
          workspaceId="ws-1"
          workspaceName="Test Workspace"
          onMessageSent={vi.fn()}
          onConversationCreated={onConversationCreated}
        />
      </TestWrapper>
    );

    const textarea = screen.getByPlaceholderText(/Type or upload to start a conversation/);
    await user.type(textarea, "Show trial balance{Enter}");

    await waitFor(() => {
      expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
    });

    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenCalledWith(
        expect.objectContaining({
          message: "Show trial balance",
          workspace_id: "ws-1",
          conversation_id: "new-conv-1",
        })
      );
    });

    expect(onConversationCreated).toHaveBeenCalledWith("new-conv-1");
  });

  it("creates conversation then sends file when conversationId is undefined", async () => {
    const onConversationCreated = vi.fn();
    const user = userEvent.setup();

    mockedApi.sendChatWithFile.mockResolvedValue({
      message: "File processed",
      session_id: "sess-1",
    });

    render(
      <TestWrapper>
        <ChatWindow
          workspaceId="ws-1"
          workspaceName="Test Workspace"
          onMessageSent={vi.fn()}
          onConversationCreated={onConversationCreated}
        />
      </TestWrapper>
    );

    // Attach a file via the file input
    const file = new File(["receipt"], "receipt.jpg", { type: "image/jpeg" });
    const fileInput = document.querySelector('input[type="file"]')!;
    await user.upload(fileInput, file);

    // Send with the attached file
    const sendBtn = screen.getByRole("button", { name: /send message/i });
    await user.click(sendBtn);

    await waitFor(() => {
      expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
    });

    await waitFor(() => {
      expect(mockedApi.sendChatWithFile).toHaveBeenCalledWith(
        file,
        expect.any(String),
        "ws-1",
        "new-conv-1",
      );
    });
  });

  it("quick action triggers deferred creation", async () => {
    const onConversationCreated = vi.fn();
    const user = userEvent.setup();

    render(
      <TestWrapper>
        <ChatWindow
          workspaceId="ws-1"
          workspaceName="Test Workspace"
          onMessageSent={vi.fn()}
          onConversationCreated={onConversationCreated}
        />
      </TestWrapper>
    );

    await user.click(screen.getByRole("button", { name: "Cash balance" }));

    await waitFor(() => {
      expect(mockedApi.createConversation).toHaveBeenCalledWith("ws-1");
    });

    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenCalledWith(
        expect.objectContaining({
          message: "Cash balance",
          conversation_id: "new-conv-1",
        })
      );
    });
  });

  it("prevents double send during conversation creation", async () => {
    const user = userEvent.setup();

    // Make createConversation slow
    mockedApi.createConversation.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        id: "new-conv-1",
        title: null,
        tag: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }), 100))
    );

    render(
      <TestWrapper>
        <ChatWindow
          workspaceId="ws-1"
          workspaceName="Test Workspace"
          onMessageSent={vi.fn()}
          onConversationCreated={vi.fn()}
        />
      </TestWrapper>
    );

    const textarea = screen.getByPlaceholderText(/Type or upload to start a conversation/);
    await user.type(textarea, "query 1{Enter}");

    // Send button should be disabled while loading
    const sendBtn = screen.getByRole("button", { name: /send message/i });
    expect(sendBtn).toBeDisabled();

    await waitFor(() => {
      // Only one createConversation call
      expect(mockedApi.createConversation).toHaveBeenCalledTimes(1);
    });
  });

  it("does not call createConversation when conversationId is already set", async () => {
    const user = userEvent.setup();

    mockedApi.getConversation.mockResolvedValue({
      id: "existing-conv",
      title: "Existing",
      tag: null,
      messages: [],
    });

    render(
      <MemoryRouter initialEntries={["/c/existing-conv"]}>
        <SessionProvider>
          <Routes>
            <Route
              path="/c/:conversationId"
              element={
                <ChatWindow
                  conversationId="existing-conv"
                  workspaceId="ws-1"
                  workspaceName="Test"
                  onMessageSent={vi.fn()}
                />
              }
            />
          </Routes>
        </SessionProvider>
      </MemoryRouter>
    );

    const textarea = screen.getByPlaceholderText("Ask about your Tally data...");
    await user.type(textarea, "query{Enter}");

    await waitFor(() => {
      expect(mockedApi.sendChat).toHaveBeenCalled();
    });

    expect(mockedApi.createConversation).not.toHaveBeenCalled();
  });
});
```

- [ ] **6.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/ChatWindow.deferred.test.tsx
```

- [ ] **6.3 — Implement deferred creation** in `frontend/src/components/ChatWindow.tsx`

Add `onConversationCreated` callback prop and `useNavigate`:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createConversation, getConversation, sendChat, sendChatWithFile, voucherAction, type VoucherAction } from "../api/client";
// ...

interface ChatWindowProps {
  conversationId?: string;
  workspaceId?: string;
  workspaceName?: string;
  onMessageSent?: () => void;
  onConversationCreated?: (conversationId: string) => void;
}

export default function ChatWindow({ conversationId, workspaceId, workspaceName, onMessageSent, onConversationCreated }: ChatWindowProps) {
  const navigate = useNavigate();
  // ... existing state
```

Update `handleSend` to check for deferred creation:

```tsx
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
      // Deferred conversation creation: create on first send
      let convId = conversationId;
      if (!convId && workspaceId) {
        const conv = await createConversation(workspaceId);
        convId = conv.id;
        onConversationCreated?.(convId);
        navigate(`/c/${convId}`, { replace: true });
      }

      const response = file
        ? await sendChatWithFile(file, text, workspaceId, convId)
        : await sendChat({
            message: text,
            session_id: sessionId ?? undefined,
            company: company ?? undefined,
            workspace_id: workspaceId,
            conversation_id: convId,
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
  [sessionId, company, setSessionId, workspaceId, conversationId, onMessageSent, onConversationCreated, navigate]
);
```

- [ ] **6.4 — Update ChatApp.handleNewChat** in `frontend/src/ChatApp.tsx`

Change from creating conversation to just navigating to workspace landing page:

```tsx
const handleNewChat = useCallback(
  (workspaceId: string, workspaceName: string, workspaceConfig?: Record<string, unknown>) => {
    setActiveWorkspaceId(workspaceId);
    setActiveWorkspaceName(workspaceName);
    if (workspaceConfig) setActiveWorkspaceConfig(workspaceConfig);
    navigate(`/w/${workspaceId}`);
    setSidebarOpen(false);
  },
  [navigate],
);
```

Note: `handleNewChat` is no longer async (no `createConversation` call). This also means removing the `createConversation` import if it's no longer used in ChatApp.

Add `onConversationCreated` handler to update sidebar refresh:

```tsx
const handleConversationCreated = useCallback(
  (newConvId: string) => {
    setSidebarRefresh((n) => n + 1);
  },
  [],
);
```

Pass it to ChatWindow:

```tsx
<ChatWindow
  conversationId={conversationId}
  workspaceId={activeWorkspaceId || urlWorkspaceId || undefined}
  workspaceName={activeWorkspaceName || undefined}
  onMessageSent={() => setSidebarRefresh((n) => n + 1)}
  onConversationCreated={handleConversationCreated}
/>
```

- [ ] **6.5 — Update ChatApp test for non-creation behavior** in `frontend/src/__tests__/ChatApp.test.tsx`

The existing test "navigates to new conversation URL when New Chat is clicked" now expects navigation to `/w/ws-1` instead of calling `createConversation`. Update:

```tsx
it("navigates to workspace landing page when New Chat is clicked (no conversation created)", async () => {
  const user = userEvent.setup();
  renderChatApp();

  await waitFor(() => {
    expect(screen.getByText("Bharat Traders")).toBeInTheDocument();
  });

  const newChatBtn = screen.getByRole("button", { name: "+ New Chat" });
  await user.click(newChatBtn);

  // createConversation should NOT be called — deferred to first send
  expect(mockedClient.createConversation).not.toHaveBeenCalled();
});
```

- [ ] **6.6 — Run all tests, confirm pass**

```bash
cd frontend && npx vitest run src/__tests__/ChatWindow.deferred.test.tsx src/__tests__/ChatWindow.test.tsx src/__tests__/ChatApp.test.tsx
```

- [ ] **6.7 — Commit**

```
feat(F4): implement deferred conversation creation

Conversations created on first send/upload, not on "+ New Chat" click.
handleSend checks !conversationId → createConversation → sendChat.
Navigates to /c/{newId} after creation. Sidebar refreshes via callback.
```

---

## Task 7: F4 — Sidebar Active Workspace Highlight + New Chat Navigation

**Scope:** Add visual highlight (`bg-blue-50`) to the active workspace header in Sidebar. Ensure `onNewChat` callback changed to match new non-creating signature.

**Files modified:** `Sidebar.tsx`
**Test file:** `frontend/src/__tests__/Sidebar.test.tsx` (expand)

### Steps

- [ ] **7.1 — Write failing tests** in `frontend/src/__tests__/Sidebar.test.tsx`

```tsx
it("highlights active workspace with bg-blue-50 background", async () => {
  renderSidebar({ activeWorkspaceId: "ws-1" });
  await waitFor(() => {
    const wsButton = screen.getByRole("button", { name: /Bharat Traders/ });
    expect(wsButton.className).toContain("bg-blue-50");
  });
});

it("does not highlight inactive workspace with bg-blue-50", async () => {
  renderSidebar({ activeWorkspaceId: "ws-1" });
  await waitFor(() => {
    const wsButton = screen.getByRole("button", { name: /Nuvanta Co/ });
    expect(wsButton.className).not.toContain("bg-blue-50");
  });
});
```

- [ ] **7.2 — Run tests, confirm failures**

```bash
cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx
```

- [ ] **7.3 — Implement highlight** in `frontend/src/components/Sidebar.tsx`

Update the workspace header button classes to include `bg-blue-50` when active:

```tsx
<button
  onClick={() => toggleCollapse(ws.id)}
  className={`w-full flex items-center justify-between text-xs uppercase tracking-wide px-2 py-1 rounded mb-1 ${
    isActive
      ? "font-bold text-gray-900 bg-blue-50"
      : "font-semibold text-gray-500"
  }`}
>
```

- [ ] **7.4 — Update ConversationList onNewChat** in `frontend/src/components/ConversationList.tsx`

The `onNewChat` callback in ConversationList needs to pass workspace config. Update the Sidebar to pass the config through:

In `Sidebar.tsx`, update the ConversationList rendering:
```tsx
<ConversationList
  workspaceId={ws.id}
  conversations={conversations[ws.id] || []}
  activeConversationId={activeConversationId}
  onSelect={(cid) => onConversationSelect(ws.id, cid, ws.name, ws.config)}
  onNewChat={() => onNewChat(ws.id, ws.name, ws.config)}
/>
```

This is a no-op change for ConversationList itself (it just calls the callback). The signature change in `onConversationSelect` and `onNewChat` was already done in Task 4.

- [ ] **7.5 — Run tests, confirm all pass**

```bash
cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx
```

- [ ] **7.6 — Commit**

```
feat(F4): add active workspace highlight in sidebar

Active workspace header gets bg-blue-50 background. Inactive workspaces
remain plain. Sidebar passes workspace config through callbacks.
```

---

## Task 8: Playwright Visual Tests Update

**Scope:** Update existing db-mode Playwright baselines (header changed, sidebar changed). Add 3 new mobile viewport specs.

**File modified:** `frontend/tests/playwright/db-mode.spec.ts`

### Steps

- [ ] **8.1 — Delete existing screenshots**

```bash
rm -rf frontend/tests/playwright/__screenshots__
```

- [ ] **8.2 — Add new mobile test specs** to `frontend/tests/playwright/db-mode.spec.ts`

Add at the end of the `test.describe("DB-mode visual tests", ...)` block:

```tsx
// Test 6: Mobile viewport — hamburger visible, sidebar hidden
test("mobile-hamburger-closed", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 }); // iPhone-ish
  await mockLoggedIn(page);
  await mockWorkspaceData(page);

  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", tally_connected: true }),
    }),
  );

  await page.goto("/");

  // Wait for header to render
  await page.waitForSelector("text=TallyPrime AI", { timeout: 10000 });

  // Hamburger should be visible on mobile
  const hamburger = page.getByRole("button", { name: /open sidebar/i });
  await expect(hamburger).toBeVisible();

  // Sidebar workspace names should NOT be visible (hidden on mobile)
  // Note: they exist in DOM but are hidden via CSS
  await expect(page).toHaveScreenshot("mobile-hamburger-closed.png");
});

// Test 7: Mobile viewport — drawer open
test("mobile-hamburger-open", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockLoggedIn(page);
  await mockWorkspaceData(page);

  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", tally_connected: true }),
    }),
  );

  await page.goto("/");
  await page.waitForSelector("text=TallyPrime AI", { timeout: 10000 });

  // Open the drawer
  const hamburger = page.getByRole("button", { name: /open sidebar/i });
  await hamburger.click();

  // Wait for drawer animation
  await page.waitForSelector('[data-testid="sidebar-overlay"]', { timeout: 5000 });

  // Sidebar content should now be visible in the drawer
  await expect(page.locator("text=Bharat Traders").first()).toBeVisible();

  await expect(page).toHaveScreenshot("mobile-hamburger-open.png");
});

// Test 8: Mobile viewport — workspace landing page
test("mobile-landing-page", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockLoggedIn(page);
  await mockWorkspaceData(page);

  await page.route("**/api/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", tally_connected: true }),
    }),
  );

  await page.goto("/w/ws-1");

  // Wait for landing page content
  await page.waitForSelector("text=TallyPrime AI Assistant", { timeout: 10000 });

  await expect(page).toHaveScreenshot("mobile-landing-page.png");
});
```

- [ ] **8.3 — Regenerate all screenshots**

```bash
cd frontend && npx playwright test tests/playwright/db-mode.spec.ts --update-snapshots
```

- [ ] **8.4 — Visually inspect all screenshots**

Check each screenshot in `frontend/tests/playwright/__screenshots__/`:
- `login-page.png` — should be unchanged
- `register-page.png` — should be unchanged
- `sidebar-with-workspaces.png` — should show bg-blue-50 on first workspace
- `chat-with-header.png` — should show two-line header with workspace name
- `voucher-review-card.png` — should show responsive grid (desktop view)
- `mobile-hamburger-closed.png` — mobile viewport, hamburger visible, no sidebar
- `mobile-hamburger-open.png` — drawer open with workspace list
- `mobile-landing-page.png` — landing page with workspace name + quick actions

- [ ] **8.5 — Run Playwright tests to confirm baselines**

```bash
cd frontend && npx playwright test tests/playwright/db-mode.spec.ts
```

Expected: 8 tests pass.

- [ ] **8.6 — Commit**

```
test: update Playwright screenshots and add mobile viewport specs

Add 3 new mobile specs: hamburger-closed, hamburger-open, landing-page.
Regenerate all db-mode screenshots to reflect header and sidebar changes.
```

---

## Task 9: Final Verification

**Scope:** Run all test suites, verify counts, confirm no regressions.

### Steps

- [ ] **9.1 — Run all Vitest tests**

```bash
cd frontend && npx vitest run
```

Expected: **~201+ tests** pass (181 baseline + ~20 new).

Breakdown of new tests:
| File | New Tests |
|------|-----------|
| `VoucherReviewCard.test.tsx` | +6 (4 pending + 2 responsive) |
| `ConnectCompanyModal.test.tsx` | +1 (modal width) |
| `ChatApp.test.tsx` | +8 (4 responsive + 3 header + 1 route) |
| `ChatWindow.test.tsx` | +2 (workspace landing page) |
| `ChatWindow.deferred.test.tsx` | +5 (deferred creation) |
| `Sidebar.test.tsx` | +2 (highlight) |
| **Total new** | **~24** |

- [ ] **9.2 — Run all Playwright tests**

```bash
cd frontend && npx playwright test tests/playwright/db-mode.spec.ts
```

Expected: 8 tests pass (5 existing + 3 new mobile specs).

- [ ] **9.3 — Visually inspect mobile screenshots** (mandatory per CLAUDE.md)

Inspect `frontend/tests/playwright/__screenshots__/` for:
- No blank space or content cutoff
- Header text visible and not truncated incorrectly
- Mobile drawer renders correctly with workspace list
- Landing page shows quick actions and input
- No header leaking into screenshot areas

- [ ] **9.4 — Run existing backend tests** to confirm no regressions

```bash
ANTHROPIC_API_KEY=test-key pytest tests/unit/ tests/integration/ tests/e2e/ -v --tb=short
```

Expected: All existing backend tests pass (no backend changes in this plan).

- [ ] **9.5 — Final commit (if any fixups needed)**

---

## Summary of All Changes

### Files Modified

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Add `/w/:workspaceId` route |
| `frontend/src/ChatApp.tsx` | Add `sidebarOpen` state, `Menu` icon, hamburger button, mobile drawer overlay, two-line header with demo/live badge, `urlWorkspaceId` from params, `activeWorkspaceConfig` state, deferred `handleNewChat` (navigate only), `onConversationCreated` callback |
| `frontend/src/components/ChatWindow.tsx` | Add `workspaceName` + `onConversationCreated` props, deferred creation in `handleSend`, pending voucher action state, `useNavigate`, workspace-aware landing page text, custom placeholder |
| `frontend/src/components/ChatInput.tsx` | Add optional `placeholder` prop |
| `frontend/src/components/VoucherReviewCard.tsx` | Add `pendingAction` prop, `Spinner` component, pending status rendering (disabled buttons, spinner, yellow border), responsive grid (`grid-cols-1 md:grid-cols-2`), `flex-wrap` on buttons |
| `frontend/src/components/MessageBubble.tsx` | Add `pendingVoucherAction` prop, forward to VoucherReviewCard |
| `frontend/src/components/Sidebar.tsx` | Add `bg-blue-50` highlight on active workspace, pass `ws.config` through callbacks, update prop types for config |
| `frontend/src/components/ConversationList.tsx` | No changes (callbacks unchanged from its perspective) |
| `frontend/src/components/ConnectCompanyModal.tsx` | Add mobile-safe width classes (`mx-4 md:mx-auto md:max-w-md`) |

### Files Created

| File | Purpose |
|------|---------|
| `frontend/src/__tests__/ChatWindow.deferred.test.tsx` | 5 tests for deferred conversation creation |
| `frontend/src/__tests__/ConnectCompanyModal.test.tsx` | 1 test for mobile-safe modal width |

### Files Expanded (existing test files)

| File | New Tests |
|------|-----------|
| `frontend/src/__tests__/VoucherReviewCard.test.tsx` | +6 |
| `frontend/src/__tests__/ChatApp.test.tsx` | +8 (+ 1 updated) |
| `frontend/src/__tests__/ChatWindow.test.tsx` | +2 |
| `frontend/src/__tests__/Sidebar.test.tsx` | +2 |
| `frontend/tests/playwright/db-mode.spec.ts` | +3 new specs |

### Test Count Target

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Frontend Vitest | 181 | ~205 | +24 |
| Playwright db-mode | 5 | 8 | +3 |
| Backend (unchanged) | ~1000 | ~1000 | 0 |
| **Total** | ~1186 | ~1213 | +27 |
