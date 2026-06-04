# UI/UX Fixes + OTel Streaming Fix + Tally Heartbeat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 chat-navigation/connect UX bugs, silence-and-fix the OTel Anthropic streaming `KeyError: 'input'`, and add a live Tally heartbeat status badge to the DB-mode header.

**Architecture:** Backend gains optional `host`/`port`/`mock` query params on `GET /api/companies` and `GET /api/health` (ad-hoc `TallyClient`, closed after use) so the frontend can probe a *workspace's* Tally instead of the app-level singleton. Frontend fixes are all state-flow corrections in `ChatWindow`/`ChatApp` plus a two-step `ConnectCompanyModal` and a new polling `TallyStatusBadge`.

**Tech Stack:** FastAPI + httpx (backend), React 18 + Vite + Vitest + Playwright (frontend), opentelemetry-instrumentation-anthropic (Langfuse tracing).

**Branch discipline:** work on a feature branch (e.g. `fix/uiux-nav-heartbeat`), merge into `dev`. Never merge `master` directly.

---

## Root-cause summary (investigated 2026-06-04)

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | Connect dialog doesn't show actual company name; button should be "Start chat" → new chat | `ConnectCompanyModal.tsx` just calls `createWorkspace` and closes; never queries Tally for the real company name, never navigates | Two-step modal: form → verify via `GET /api/companies?host&port` → create workspace with `config.tally_company` → success screen (actual + friendly name) → **Start chat** navigates to `/w/:id` |
| 2 | First message opens "new chat screen"; refresh needed to see the chat | `ChatWindow.handleSend` creates the conversation then `onConversationCreated` navigates immediately → `conversationId` prop changes → load-effect (`ChatWindow.tsx:32`) refetches the *still-empty* conversation and **clobbers the optimistic messages**; the in-flight `sendChat` response then maps onto a loading-msg id that no longer exists | One-shot ref guard: skip the refetch for a conversation this window just created |
| 3 | "New chat" while another chat open → needs refresh | Load-effect only runs when `conversationId && workspaceId`; when `conversationId` becomes `undefined` the old messages stay in state | `else` branch: `setMessages([])` (+ reset `sessionId`) when on the landing page |
| 4 | Landing page after connect: new-chat not highlighted in sidebar | After connect, `activeWorkspaceId` stays `null` (no navigation happens); same on plain `/` route | Fix 1's "Start chat" navigation + auto-redirect `/` → `/w/<first workspace>` so `isLandingPage` (`Sidebar.tsx:91`) is true |
| 5 | `KeyError: 'input'` in `opentelemetry.instrumentation.anthropic.streaming._process_response_item` | Known bug in `opentelemetry-instrumentation-anthropic` 0.53.0: streaming + tools emits `input_json_delta` before the event dict has an `input` key. Only trigger in this codebase: `AnalysisAgent` streaming with tools (`backend/agents/analysis_agent.py:491`). Effect: AnalysisAgent traces lost in Langfuse + log noise | **Verified**: fixed upstream in v0.61.0 (guarded `event.get("input", "")`). Upgrade 0.53.0 → ≥0.61.0 |
| 6 | Tally status heartbeat in header | DB-mode header badge (`ChatApp.tsx:100-110`) is static (`config.mock_mode` only) — no actual connection check. Legacy `Header.tsx` polls `getHealth()` every 30 s but `GET /api/health` only checks the app-level singleton, not the workspace's host/port | `GET /api/health?host&port` + new `TallyStatusBadge` polling per active workspace every 30 s (green/red/gray) |

**Key files:**
- Modify: `backend/api/companies.py`, `backend/api/health.py`
- Modify: `frontend/src/api/client.ts`, `frontend/src/components/ConnectCompanyModal.tsx`, `frontend/src/components/ChatWindow.tsx`, `frontend/src/ChatApp.tsx`, `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/TallyStatusBadge.tsx`
- Modify: `pyproject.toml` / `uv.lock` (otel upgrade)
- Tests: `tests/integration/test_api_endpoints*.py` (follow existing pattern), `frontend/src/__tests__/{ConnectCompanyModal,ChatWindow,ChatApp,TallyStatusBadge,Sidebar}.test.tsx`, `frontend/tests/playwright/db-mode.spec.ts`

---

## Task 1: Backend — `GET /api/companies` accepts `host`/`port`/`mock`

**Files:**
- Modify: `backend/api/companies.py`
- Test: `tests/integration/test_api_endpoints.py` (extend — do NOT import `backend.main:app`; this file builds a minimal FastAPI app + `dependency_overrides[get_client]` + ASGITransport to avoid lifespan issues. Reuse its `async_client` and `mock_tally` fixtures.)

- [ ] **Step 1: Write the failing tests** (append to `tests/integration/test_api_endpoints.py`)

```python
# --- Companies: ad-hoc host/port/mock params ---


async def test_companies_mock_param_returns_mock_company(async_client):
    """mock=true must answer from the built-in mock handler, regardless of app client."""
    resp = await async_client.get("/api/companies", params={"mock": "true"})
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["companies"]]
    assert "Bharat Traders Pvt Ltd" in names  # tests/fixtures/company_list.xml


async def test_companies_explicit_host_probes_that_tally(async_client, mock_tally):
    """host/port params probe that instance ad hoc (here: the aiohttp mock server)."""
    port = int(mock_tally.base_url.rsplit(":", 1)[1])
    resp = await async_client.get("/api/companies", params={"host": "localhost", "port": port})
    assert resp.status_code == 200
    assert len(resp.json()["companies"]) >= 1


async def test_companies_bad_host_returns_503(async_client):
    """Unreachable host/port must 503, not 500."""
    resp = await async_client.get("/api/companies", params={"host": "127.0.0.1", "port": 1})
    assert resp.status_code == 503
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/integration/test_api_endpoints.py -v -k companies`
Expected: FAIL — params ignored (`mock` test returns live-client data or connection error; bad-host test returns 200/500).

- [ ] **Step 3: Implement**

```python
"""Companies endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_client
from backend.api.models import CompaniesResponse, CompanyItem
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError
from backend.tally_bridge.queries.masters import list_companies

router = APIRouter()


@router.get("/companies", response_model=CompaniesResponse)
async def get_companies(
    host: str | None = None,
    port: int = 9000,
    mock: bool = False,
    client: TallyClient = Depends(get_client),
) -> CompaniesResponse:
    """List Tally companies.

    Without params: uses the app-level client (existing behavior).
    With mock=true: answers from the built-in mock handler.
    With host[/port]: probes that Tally instance ad hoc (used by ConnectCompanyModal).
    """
    ad_hoc: TallyClient | None = None
    if mock:
        ad_hoc = TallyClient()
        ad_hoc.mock_mode = True
    elif host:
        ad_hoc = TallyClient(host, port)
    try:
        companies = await list_companies(ad_hoc or client)
        return CompaniesResponse(
            companies=[CompanyItem(name=c.name) for c in companies],
        )
    except (TallyConnectionError, TallyResponseError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        if ad_hoc:
            await ad_hoc.close()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_api_endpoints.py -v`
Expected: PASS (new tests + no regression in existing companies tests).

- [ ] **Step 5: Commit**

```bash
git add backend/api/companies.py tests/integration/test_api_endpoints.py
git commit -m "feat(api): /api/companies accepts host/port/mock for ad-hoc Tally probe"
```

---

## Task 2: Backend — `GET /api/health` accepts `host`/`port`

**Files:**
- Modify: `backend/api/health.py`
- Test: `tests/integration/test_api_endpoints.py` (extend — same `async_client`/`mock_tally` fixtures as Task 1)

- [ ] **Step 1: Write the failing tests** (append to `tests/integration/test_api_endpoints.py`)

```python
# --- Health: ad-hoc host/port params ---


async def test_health_bad_host_reports_degraded(async_client):
    resp = await async_client.get("/api/health", params={"host": "127.0.0.1", "port": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tally_connected"] is False
    assert body["status"] == "degraded"
    assert body["tally_url"] == "http://127.0.0.1:1"
    assert body["mode"] == "live"


async def test_health_explicit_host_reports_connected(async_client, mock_tally):
    port = int(mock_tally.base_url.rsplit(":", 1)[1])
    resp = await async_client.get("/api/health", params={"host": "localhost", "port": port})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tally_connected"] is True
    assert body["status"] == "healthy"


async def test_health_without_params_unchanged(async_client):
    resp = await async_client.get("/api/health")
    assert resp.status_code == 200
    assert {"status", "tally_connected", "tally_url", "mode"} <= resp.json().keys()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/integration/test_api_endpoints.py -v -k health`
Expected: first test FAILS (params ignored → reports app-level client URL).

- [ ] **Step 3: Implement**

```python
"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import HealthResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    host: str | None = None,
    port: int = 9000,
    client: TallyClient = Depends(get_client),
) -> HealthResponse:
    """Health check. With host[/port], probes that Tally instance ad hoc
    (used by the per-workspace heartbeat badge); otherwise uses the app client."""
    if host:
        ad_hoc = TallyClient(host, port)
        try:
            connected = await ad_hoc.health_check()
        finally:
            await ad_hoc.close()
        return HealthResponse(
            status="healthy" if connected else "degraded",
            tally_connected=connected,
            tally_url=ad_hoc.base_url,
            mode="live",
        )
    if client.mock_mode:
        return HealthResponse(
            status="healthy",
            tally_connected=True,
            tally_url="mock://bharat-traders",
            mode="mock",
        )
    connected = await client.health_check()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        tally_connected=connected,
        tally_url=client.base_url,
        mode="live",
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_api_endpoints.py -v && pytest tests/unit/ -q`
Expected: PASS, no unit regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/api/health.py tests/integration/test_api_endpoints.py
git commit -m "feat(api): /api/health accepts host/port for per-workspace heartbeat"
```

---

## Task 3: Frontend — API client params for `getCompanies` / `getHealth`

**Files:**
- Modify: `frontend/src/api/client.ts:207-215`
- Test: `frontend/src/__tests__/client.test.ts` (extend if exists; otherwise covered indirectly by Tasks 4/8 component tests — check first)

- [ ] **Step 1: Implement (signature change, backward compatible)**

```ts
export async function getHealth(params?: { host?: string; port?: number }): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health", { params });
  return data;
}

export async function getCompanies(params?: {
  host?: string;
  port?: number;
  mock?: boolean;
}): Promise<CompaniesResponse> {
  const { data } = await api.get<CompaniesResponse>("/companies", { params });
  return data;
}
```

- [ ] **Step 2: Typecheck + run FE unit tests**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS (no callers pass args yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(fe-api): getHealth/getCompanies accept host/port/mock params"
```

---

## Task 4: Frontend — two-step ConnectCompanyModal (actual name + friendly name + "Start chat")

**Files:**
- Modify: `frontend/src/components/ConnectCompanyModal.tsx` (full rewrite below)
- Test: `frontend/src/__tests__/ConnectCompanyModal.test.tsx`

- [ ] **Step 1: Write the failing tests** (add to existing file; mock `../api/client` as the file already does — keep existing mock setup and extend it with `getCompanies`)

```tsx
it("verifies Tally, creates workspace, then shows confirmation with both names", async () => {
  vi.mocked(getCompanies).mockResolvedValue({
    companies: [{ name: "Bharat Traders Private Limited" }],
  });
  vi.mocked(createWorkspace).mockResolvedValue({
    id: "ws-1", name: "My Books", agent_type: "tally",
    config: { tally_company: "Bharat Traders Private Limited" },
  } as never);
  const onCreated = vi.fn();
  render(<ConnectCompanyModal onClose={() => {}} onCreated={onCreated} />);

  fireEvent.change(screen.getByLabelText(/friendly name/i), { target: { value: "My Books" } });
  fireEvent.click(screen.getByRole("button", { name: /connect/i }));

  // Confirmation step: actual Tally company name + friendly name + Start chat CTA
  expect(await screen.findByTestId("connect-confirm-company")).toHaveTextContent(
    "Bharat Traders Private Limited",
  );
  expect(screen.getByTestId("connect-confirm-name")).toHaveTextContent("My Books");
  expect(getCompanies).toHaveBeenCalledWith({ host: "localhost", port: 9000 });
  expect(createWorkspace).toHaveBeenCalledWith({
    name: "My Books",
    config: expect.objectContaining({ tally_company: "Bharat Traders Private Limited" }),
  });

  // onCreated fires only on Start chat, with the created workspace
  expect(onCreated).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /start chat/i }));
  expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "ws-1" }));
});

it("shows error and stays on form when Tally is unreachable", async () => {
  vi.mocked(getCompanies).mockRejectedValue(new Error("503"));
  render(<ConnectCompanyModal onClose={() => {}} onCreated={vi.fn()} />);
  fireEvent.change(screen.getByLabelText(/friendly name/i), { target: { value: "X" } });
  fireEvent.click(screen.getByRole("button", { name: /connect/i }));
  expect(await screen.findByText(/check that Tally is running/i)).toBeInTheDocument();
  expect(createWorkspace).not.toHaveBeenCalled();
});

it("demo mode verifies via mock=true", async () => {
  vi.mocked(getCompanies).mockResolvedValue({ companies: [{ name: "Bharat Traders Private Limited" }] });
  vi.mocked(createWorkspace).mockResolvedValue({ id: "ws-2", name: "Demo", config: {} } as never);
  render(<ConnectCompanyModal onClose={() => {}} onCreated={vi.fn()} />);
  fireEvent.change(screen.getByLabelText(/friendly name/i), { target: { value: "Demo" } });
  fireEvent.click(screen.getByRole("checkbox")); // Demo Mode toggle
  fireEvent.click(screen.getByRole("button", { name: /connect/i }));
  await screen.findByTestId("connect-confirm-company");
  expect(getCompanies).toHaveBeenCalledWith({ mock: true });
});
```

Also update the existing test "calls createWorkspace and onCreated on successful submit" — `onCreated` now fires on **Start chat** with the workspace object, and the existing label `Company Name` becomes `Friendly Name`.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- ConnectCompanyModal`
Expected: FAIL (no confirmation step, no getCompanies call).

- [ ] **Step 3: Rewrite the component**

```tsx
import { useState } from "react";
import { createWorkspace, getCompanies } from "../api/client";
import type { WorkspaceData } from "../types";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: (workspace: WorkspaceData) => void;
}

export default function ConnectCompanyModal({ onClose, onCreated }: ConnectCompanyModalProps) {
  const [step, setStep] = useState<"form" | "connected">("form");
  const [name, setName] = useState("");
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [mockMode, setMockMode] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      // 1. Verify connectivity and discover the actual Tally company name
      const res = await getCompanies(
        mockMode ? { mock: true } : { host: tallyHost, port: parseInt(tallyPort, 10) },
      );
      if (!res.companies.length) throw new Error("No companies loaded in Tally");
      const actualCompany = res.companies[0].name; // first loaded company; selector → parked
      // 2. Create the workspace storing both names
      const ws = await createWorkspace({
        name,
        config: {
          tally_host: tallyHost,
          tally_port: parseInt(tallyPort, 10),
          mock_mode: mockMode,
          tally_company: actualCompany,
        },
      });
      setCompanyName(actualCompany);
      setWorkspace(ws);
      setStep("connected");
    } catch {
      setError("Failed to connect. Check that Tally is running at the given host/port with a company loaded.");
    } finally {
      setLoading(false);
    }
  };

  if (step === "connected" && workspace) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm">✓</span>
            <h2 className="text-lg font-semibold text-gray-900">Company Connected</h2>
          </div>
          <dl className="space-y-2 mb-6">
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Tally Company</dt>
              <dd data-testid="connect-confirm-company" className="text-sm font-medium text-gray-900">{companyName}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-gray-500">Friendly Name</dt>
              <dd data-testid="connect-confirm-name" className="text-sm font-medium text-gray-900">{workspace.name}</dd>
            </div>
          </dl>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md">Close</button>
            <button
              type="button"
              data-testid="connect-start-chat"
              onClick={() => onCreated(workspace)}
              className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md"
            >
              Start chat
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full mx-4 md:mx-auto md:max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Connect Tally Company</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="bg-red-50 text-red-700 p-3 rounded text-sm">{error}</div>}
          <div>
            <label htmlFor="connect-name" className="block text-sm font-medium text-gray-700">Friendly Name</label>
            <input id="connect-name" type="text" required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Bharat Traders — Main Books"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label htmlFor="connect-host" className="block text-sm font-medium text-gray-700">Tally Host</label>
            <input id="connect-host" type="text" required value={tallyHost} onChange={(e) => setTallyHost(e.target.value)} placeholder="localhost or 192.168.1.5"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label htmlFor="connect-port" className="block text-sm font-medium text-gray-700">Tally Port</label>
            <input id="connect-port" type="number" required value={tallyPort} onChange={(e) => setTallyPort(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <span className="text-sm font-medium text-gray-700">Demo Mode</span>
            <div className="relative">
              <input type="checkbox" className="sr-only peer" checked={mockMode} onChange={(e) => setMockMode(e.target.checked)} />
              <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="text-xs text-gray-500">{mockMode ? "Uses sample data" : "Connects to live Tally"}</span>
          </label>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md">Cancel</button>
            <button type="submit" disabled={loading} className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50">
              {loading ? "Connecting..." : "Connect"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

Note: `onCreated` signature changed from `() => void` to `(workspace: WorkspaceData) => void` — Task 5 updates both call sites in the same PR; typecheck will fail until then (run Task 5 before pushing).

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- ConnectCompanyModal`
Expected: PASS (typecheck completes after Task 5).

- [ ] **Step 5: Commit** (after Task 5, as one unit — or commit here with `--no-verify` avoided; preferred: commit Tasks 4+5 together)

---

## Task 5: Frontend — wire "Start chat" through ChatApp + Sidebar

**Files:**
- Modify: `frontend/src/ChatApp.tsx:177-186` (modal `onCreated`)
- Modify: `frontend/src/components/Sidebar.tsx:105` (modal `onCreated`)
- Test: `frontend/src/__tests__/ChatApp.test.tsx`, `frontend/src/__tests__/Sidebar.test.tsx`

- [ ] **Step 1: Write the failing tests**

`ChatApp.test.tsx` (mock ConnectCompanyModal as the file already mocks children, or drive via real modal mocks):

```tsx
it("navigates to /w/:id after Start chat from connect modal", async () => {
  // Render ChatApp with zero workspaces so the connect prompt shows,
  // complete the modal flow (mocked getCompanies/createWorkspace),
  // click Start chat, then assert the URL is /w/ws-1 and the header shows "New Chat".
  // (Follow this file's existing MemoryRouter + mocked api/client pattern.)
});
```

`Sidebar.test.tsx`:

```tsx
it("starts a new chat in the created workspace after Start chat", async () => {
  // open + Connect Company from sidebar footer, complete modal flow,
  // assert onNewChat was called with ("ws-1", "My Books", config)
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- ChatApp Sidebar`
Expected: FAIL.

- [ ] **Step 3: Implement**

`ChatApp.tsx` — replace the modal block (lines 177-186):

```tsx
{showConnectModal && (
  <ConnectCompanyModal
    onClose={() => setShowConnectModal(false)}
    onCreated={(ws) => {
      setShowConnectModal(false);
      setHasWorkspaces(true);
      setSidebarRefresh((n) => n + 1);
      handleNewChat(ws.id, ws.name, ws.config as Record<string, unknown>);
    }}
  />
)}
```

`Sidebar.tsx` — replace line 105:

```tsx
{showModal && (
  <ConnectCompanyModal
    onClose={() => setShowModal(false)}
    onCreated={(ws) => {
      setShowModal(false);
      loadData();
      onNewChat(ws.id, ws.name, ws.config as Record<string, unknown>);
    }}
  />
)}
```

- [ ] **Step 4: Run tests + typecheck**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit Tasks 4+5**

```bash
git add frontend/src/components/ConnectCompanyModal.tsx frontend/src/ChatApp.tsx frontend/src/components/Sidebar.tsx frontend/src/__tests__/
git commit -m "feat(fe): two-step connect modal — verify Tally company, Start chat → new chat"
```

---

## Task 6: Frontend — ChatWindow stale-state fixes (bugs 2 + 3)

**Files:**
- Modify: `frontend/src/components/ChatWindow.tsx:32-51, 75-79`
- Test: `frontend/src/__tests__/ChatWindow.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it("does not clobber optimistic messages when first send creates the conversation", async () => {
  // Arrange: render with workspaceId only (landing). Mock createConversation -> {id: "conv-new"},
  // mock getConversation -> { messages: [] } (server hasn't persisted yet),
  // mock sendChat to resolve after a tick with an assistant reply.
  // Act: send "hello", then rerender with conversationId="conv-new" (simulates ChatApp navigate).
  // Assert: user message "hello" stays visible, and the assistant reply appears —
  // i.e. getConversation was NOT used to wipe state for the just-created conversation.
});

it("clears messages when navigating to the new-chat landing page", async () => {
  // Arrange: render with conversationId="conv-1"; getConversation -> 2 messages; await them.
  // Act: rerender with conversationId=undefined (same workspaceId).
  // Assert: previous messages are gone; empty/new-chat state is shown.
});
```

(Write these fully against the existing mock setup in `ChatWindow.test.tsx` — it already mocks `../api/client` and renders inside `SessionProvider`.)

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- ChatWindow`
Expected: both FAIL (clobber happens; messages persist on landing).

- [ ] **Step 3: Implement**

In `ChatWindow.tsx`, add a ref and rework the load-effect:

```tsx
const justCreatedConvRef = useRef<string | null>(null);

useEffect(() => {
  if (conversationId && workspaceId) {
    if (justCreatedConvRef.current === conversationId) {
      // This window just created the conversation via deferred creation —
      // optimistic state is already correct; skip the refetch once so the
      // in-flight response isn't clobbered. (Bug: first chat needed refresh.)
      justCreatedConvRef.current = null;
      return;
    }
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
  } else if (!conversationId) {
    // New-chat landing page: drop messages from any previously open conversation
    // and start a fresh agent session. (Bug: New Chat needed refresh.)
    setMessages([]);
    setSessionId(null);
  }
}, [conversationId, workspaceId, setSessionId]);
```

And in `handleSend` (line 75-79), mark the created conversation:

```tsx
// Deferred creation: create conversation on first send
if (!activeConvId && workspaceId) {
  const conv = await createConversation(workspaceId);
  activeConvId = conv.id;
  justCreatedConvRef.current = conv.id;
  onConversationCreated?.(conv.id);
}
```

**Required** (verified 2026-06-04): `SessionContext.tsx:5` types `setSessionId: (id: string) => void` while the state is already `string | null` — widen the interface to `setSessionId: (id: string | null) => void` (the `useState` setter already satisfies it; `_defaultSession` no-op unaffected).

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- ChatWindow && npx tsc --noEmit`
Expected: PASS, including the existing deferred-creation tests at line 256+.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatWindow.tsx frontend/src/__tests__/ChatWindow.test.tsx frontend/src/context/SessionContext.tsx
git commit -m "fix(fe): no refresh needed for first chat and New Chat — stale message state"
```

---

## Task 7: Frontend — default workspace on `/` + sidebar highlight (bug 4)

**Files:**
- Modify: `frontend/src/ChatApp.tsx:69-71` (`handleWorkspacesLoaded`)
- Modify: `frontend/src/components/Sidebar.tsx:26` (`onWorkspacesLoaded` call)
- Test: `frontend/src/__tests__/ChatApp.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it("redirects / to the first workspace landing page so New Chat is highlighted", async () => {
  // Render at "/" with one workspace (ws-1) mocked.
  // Assert URL becomes /w/ws-1 (replace) and sidebar-new-chat-active testid exists.
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- ChatApp`
Expected: FAIL (stays on `/`, no active highlight).

- [ ] **Step 3: Implement**

`Sidebar.tsx` line 26 — pass the first workspace id:

```tsx
onWorkspacesLoaded?.(ws.length, ws[0]?.id);
```

and widen the prop type (line 14):

```tsx
onWorkspacesLoaded?: (count: number, firstWorkspaceId?: string) => void;
```

`ChatApp.tsx` — replace `handleWorkspacesLoaded`:

```tsx
const handleWorkspacesLoaded = useCallback(
  (count: number, firstWorkspaceId?: string) => {
    setHasWorkspaces(count > 0);
    // Bare "/" with workspaces: land on the first workspace's new-chat page
    // so the sidebar "+ New Chat" highlight has an active workspace to bind to.
    if (count > 0 && firstWorkspaceId && !conversationId && !urlWorkspaceId) {
      navigate(`/w/${firstWorkspaceId}`, { replace: true });
    }
  },
  [conversationId, urlWorkspaceId, navigate],
);
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS (watch the existing "no workspaces" tests — redirect must not fire when count is 0).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/ChatApp.tsx frontend/src/components/Sidebar.tsx frontend/src/__tests__/ChatApp.test.tsx
git commit -m "fix(fe): land on first workspace from / so New Chat highlights in sidebar"
```

---

## Task 8: Frontend — Tally heartbeat badge in header

**Files:**
- Create: `frontend/src/components/TallyStatusBadge.tsx`
- Modify: `frontend/src/ChatApp.tsx:100-110` (replace static badge)
- Test: `frontend/src/__tests__/TallyStatusBadge.test.tsx` (new)

- [ ] **Step 1: Write the failing tests**

```tsx
import { render, screen, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import TallyStatusBadge from "../components/TallyStatusBadge";
import { getHealth } from "../api/client";

vi.mock("../api/client", () => ({ getHealth: vi.fn() }));

describe("TallyStatusBadge", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); });

  it("shows Demo (no polling) for mock workspaces", () => {
    render(<TallyStatusBadge config={{ mock_mode: true }} />);
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Demo");
    expect(getHealth).not.toHaveBeenCalled();
  });

  it("polls workspace host/port and shows Live when connected", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "healthy", tally_connected: true, tally_url: "http://192.168.1.5:9000", mode: "live",
    });
    render(<TallyStatusBadge config={{ tally_host: "192.168.1.5", tally_port: 9000 }} />);
    expect(screen.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "checking");
    await act(async () => { await vi.runOnlyPendingTimersAsync(); });
    expect(getHealth).toHaveBeenCalledWith({ host: "192.168.1.5", port: 9000 });
    expect(screen.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "connected");
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Live");
  });

  it("shows Offline when health reports disconnected, and re-polls every 30s", async () => {
    vi.mocked(getHealth)
      .mockResolvedValueOnce({ status: "degraded", tally_connected: false, tally_url: "x", mode: "live" })
      .mockResolvedValueOnce({ status: "healthy", tally_connected: true, tally_url: "x", mode: "live" });
    render(<TallyStatusBadge config={{ tally_host: "h" }} />);
    await act(async () => { await vi.runOnlyPendingTimersAsync(); });
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Offline");
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(screen.getByTestId("header-workspace-badge")).toHaveTextContent("Live");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- TallyStatusBadge`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement the component**

```tsx
import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

interface TallyStatusBadgeProps {
  config: Record<string, unknown>; // active workspace config
}

type Status = "checking" | "connected" | "disconnected";

const POLL_MS = 30000;

/** Heartbeat badge: polls /api/health for the active workspace's Tally host
 *  every 30s. Demo workspaces render a static Demo badge (no polling). */
export default function TallyStatusBadge({ config }: TallyStatusBadgeProps) {
  const mockMode = config.mock_mode === true;
  const host = (config.tally_host as string) || "localhost";
  const port = (config.tally_port as number) || 9000;
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    if (mockMode) return;
    let cancelled = false;
    setStatus("checking");
    const check = async () => {
      try {
        const h = await getHealth({ host, port });
        if (!cancelled) setStatus(h.tally_connected ? "connected" : "disconnected");
      } catch {
        if (!cancelled) setStatus("disconnected");
      }
    };
    check();
    const id = setInterval(check, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [mockMode, host, port]);

  if (mockMode) {
    return (
      <span data-testid="header-workspace-badge" data-status="demo" className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-orange-500" />
        Demo
      </span>
    );
  }

  const styles: Record<Status, { badge: string; dot: string; label: string }> = {
    checking: { badge: "bg-gray-100 text-gray-500", dot: "bg-gray-400 animate-pulse", label: "Checking…" },
    connected: { badge: "bg-green-100 text-green-700", dot: "bg-green-500", label: "Live" },
    disconnected: { badge: "bg-red-100 text-red-700", dot: "bg-red-500", label: "Offline" },
  };
  const s = styles[status];
  return (
    <span
      data-testid="header-workspace-badge"
      data-status={status}
      title={`Tally at ${host}:${port}`}
      className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full shrink-0 ${s.badge}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
```

Then in `ChatApp.tsx`, replace lines 100-110 (the static Demo/Live ternary) with:

```tsx
<TallyStatusBadge config={activeWorkspaceConfig} />
```

and add the import: `import TallyStatusBadge from "./components/TallyStatusBadge";`

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS. Existing `ChatApp.test.tsx` badge assertions (`header-workspace-badge` Demo/Live) may need `getHealth` mocked — update those tests to mock it resolving `tally_connected: true`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TallyStatusBadge.tsx frontend/src/ChatApp.tsx frontend/src/__tests__/
git commit -m "feat(fe): live Tally heartbeat badge in header (30s poll, per-workspace host)"
```

---

## Task 9: Backend — fix OTel Anthropic streaming `KeyError: 'input'`

**Files:**
- Modify: `pyproject.toml` (langfuse extra), `uv.lock`

**Verified (2026-06-04):** installed 0.53.0 has the unguarded line in `_process_response_item`:
`complete_response["events"][index]["input"] += item.delta.partial_json` (no `'input'` key guard).
The released **v0.61.0** (latest on PyPI) fixes it:
```python
elif item.delta.type == "input_json_delta":
    if event.get("type") == "tool_use":
        event["input"] = event.get("input", "") + item.delta.partial_json
```
plus an `index < len(events)` bounds check. Source: `traceloop/openllmetry` tag v0.61.0, `packages/opentelemetry-instrumentation-anthropic/.../streaming.py`. So the upgrade is the verified fix; the fallback below should not be needed.

- [ ] **Step 1: Upgrade the instrumentation package**

```bash
uv lock --upgrade-package opentelemetry-instrumentation-anthropic
uv sync --extra dev --extra langfuse --extra db
```

If `pyproject.toml` pins the package, bump the constraint to `>=0.61.0`.

- [ ] **Step 2: Verify the installed version and guard**

```bash
python - <<'EOF'
import inspect
import opentelemetry.instrumentation.anthropic.streaming as s
src = inspect.getsource(s._process_response_item)
assert 'event.get("input", "")' in src, "fix not present!"
print("guarded — OK")
EOF
uv pip show opentelemetry-instrumentation-anthropic | grep Version   # expect >= 0.61.0
```

Unlikely fallback (e.g. dependency conflict blocks the upgrade): stay on 0.53.0, add a parked item in `docs/open-items-parked.md` referencing the v0.61.0 fix, and silence the noise via `logging.getLogger("opentelemetry.instrumentation.anthropic.streaming").setLevel(logging.WARNING)` next to the instrumentor init in `backend/main.py:35-60` (AnalysisAgent streaming traces remain lossy).

- [ ] **Step 3: Regression check**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ -q`
Expected: full suite green (instrumentation only activates when Langfuse env vars are set, but the upgrade may bump shared otel deps — watch import errors).

- [ ] **Step 4: Live verification (deferred)**

Real verification needs a real streaming call with tools (AnalysisAgent). Fold into the single end-of-feature manual/eval pass (Task 11): watch the backend log for the `_process_response_item` traceback and confirm the AnalysisAgent generation appears in Langfuse. ⚠️ Do not run a live test just for this.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "fix(obs): upgrade opentelemetry-instrumentation-anthropic — streaming tool-use KeyError 'input'"
```

---

## Task 10: Playwright visual specs

**Files:**
- Modify: `frontend/tests/playwright/db-mode.spec.ts`
- Screenshots: regenerate ONLY `frontend/tests/playwright/__screenshots__/*/db-mode.spec.ts/` (never the whole `__screenshots__/` dir)

State matrix (component × state × viewport — all 3 viewports each):

| Component | States |
|---|---|
| ConnectCompanyModal | form (existing) / **connected-confirmation** (new) |
| Header TallyStatusBadge | **connected (Live)** / **disconnected (Offline)** / demo (existing baseline) |
| Sidebar + landing | new-chat-highlight after `/` redirect (existing spec 19/20 — re-verify against redirect) |

- [ ] **Step 1: Add specs** (route-mock the API per this file's existing pattern)

```ts
// VISUAL CHECKLIST: modal centered; green check + "Company Connected" title;
// "TALLY COMPANY" label with "Bharat Traders Private Limited"; "FRIENDLY NAME"
// label with "My Books"; Close + blue "Start chat" buttons right-aligned;
// NOT visible: form fields, error banner.
test("connect-company-confirmation", async ({ page }) => {
  await page.route("**/api/companies*", (r) =>
    r.fulfill({ json: { companies: [{ name: "Bharat Traders Private Limited" }] } }));
  await page.route("**/api/workspaces", (r) =>
    r.request().method() === "POST"
      ? r.fulfill({ json: { id: "ws-new", name: "My Books", agent_type: "tally", config: { tally_company: "Bharat Traders Private Limited" } } })
      : r.continue());
  // ...open modal, fill friendly name, submit (reuse spec 17 setup)...
  await expect(page.getByTestId("connect-confirm-company")).toHaveText("Bharat Traders Private Limited");
  await expect(page.getByTestId("connect-confirm-name")).toHaveText("My Books");
  await expect(page.getByTestId("connect-start-chat")).toBeVisible();
  await expect(page).toHaveScreenshot("connect-company-confirmation.png");
});

// VISUAL CHECKLIST: header right of workspace name shows red pill badge,
// red dot + "Offline" text; chat area unaffected; NOT visible: green Live badge.
test("header-tally-offline", async ({ page }) => {
  await page.route("**/api/health*", (r) =>
    r.fulfill({ json: { status: "degraded", tally_connected: false, tally_url: "http://h:9000", mode: "live" } }));
  // ...login + open live workspace landing (reuse existing setup)...
  await expect(page.getByTestId("header-workspace-badge")).toHaveAttribute("data-status", "disconnected");
  await expect(page.getByTestId("header-workspace-badge")).toHaveText(/Offline/);
  await expect(page).toHaveScreenshot("header-tally-offline.png");
});
// plus the connected twin asserting data-status="connected" + "Live"
```

- [ ] **Step 2: Regenerate db-mode screenshots only**

```bash
rm -rf frontend/tests/playwright/__screenshots__/*/db-mode.spec.ts/
cd frontend && npm run test:playwright   # backend must be running on :8000
```

- [ ] **Step 3: MAIN AGENT visually inspects every changed PNG** in `__screenshots__/{mobile,tablet,desktop}/db-mode.spec.ts/` via the Read tool (subagents can't see images). Check: no blank space, no cutoff, badge readable at mobile width, modal not overflowing.

- [ ] **Step 4: Commit**

```bash
git add frontend/tests/playwright/
git commit -m "test(playwright): connect confirmation + heartbeat badge states"
```

---

## Task 11: Full verification + code review + docs

- [ ] **Step 1: Full test suites** (report any suite NOT run)

```bash
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ 2>&1 | tail -20
cd frontend && npx tsc --noEmit && npm test && npm run build
```

- [ ] **Step 2: Manual smoke (DB mode)** — backend with `DATABASE_URL` + `JWT_SECRET`, log to `logs/be_manual_uiux.log`; frontend `VITE_DB_MODE=true npm run dev`. Walk: connect company (live + demo) → confirmation shows both names → Start chat → send first message (no refresh!) → New Chat from open conversation (no refresh!) → reload `/` (redirects to workspace landing, New Chat highlighted) → stop Tally → badge turns Offline ≤30 s → restart → Live. Watch `logs/be_manual_uiux.log` for the otel traceback (Task 9 verification) — needs Langfuse env + an analysis-type query ("compare Q1 vs Q2 sales").
- [ ] **Step 3: Code review** via `superpowers:requesting-code-review` → fixes → `docs/code-review-uiux-heartbeat.md`.
- [ ] **Step 4: Docs** — add parked items if any (company selector for multi-company Tally; otel upstream issue if fallback used). No roadmap change (bugfix set).
- [ ] **Step 5: Merge** feature branch → `dev` (per § Git branch discipline; never into `master`).

---

## Self-review notes

- All 6 reported issues map to tasks: 1→T1/T3/T4/T5, 2→T6, 3→T6, 4→T5/T7, otel→T9, heartbeat→T2/T3/T8.
- `onCreated` signature change (T4) and its call sites (T5) must land in the same commit to keep typecheck green.
- T7 redirect must not fight the existing "no workspaces → connect prompt" flow (guarded by `count > 0`).
- Per-poll ad-hoc `TallyClient` (T2) creates one httpx client per check; fine at 1 req/30 s/user — add TTL cache only if it shows up later.
- `setSessionId(null)` (T6): `SessionContext.tsx:5` typing confirmed too narrow — widen to `string | null` (required).
