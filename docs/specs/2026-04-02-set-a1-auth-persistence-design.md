# Set A1: Auth + Persistence — Design Spec

**Date**: 2026-04-02
**Status**: Draft
**Scope**: User authentication, persistent chat history, agent memory, usage logging, templateized agent architecture
**Depends on**: Nothing (foundational)
**Blocks**: Set A2 (billing/Razorpay), Set B (compliance), Set C (sync & store)

---

## 1. Overview

Transform the TallyPrime AI Agent from a single-user in-memory app into a multi-user persistent platform with authentication, conversation history, and a templateized agent architecture that can support different agent types beyond Tally.

### What Changes

| Current | New |
|---------|-----|
| No auth, single user | JWT auth, multi-user |
| In-memory sessions (60 min TTL) | Postgres-backed conversations (permanent) |
| Single TallyClient singleton | Per-workspace TallyClient from DB config |
| Hardcoded Tally orchestrator | Agent registry (pluggable agent types) |
| No usage tracking | Per-message usage logging with cost |
| Frontend: single-page, no routing | React Router, sidebar, auth pages |

### What Doesn't Change

- `tally_bridge/` — all 18 tools, request_builder, response_parser, models, exceptions
- Agent code — query_agent, analysis_agent, chart_agent, prompts, tools
- Frontend components — MessageBubble, ChartRenderer, DataTable, QuickActions
- All 1024 existing tests — run unchanged in legacy mode (no DB)

---

## 2. Database Schema

**Engine**: PostgreSQL (no pgvector yet — deferred to Set C)
**ORM**: SQLAlchemy 2.0 (async) + Alembic for migrations

### 2.1 users

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| email | VARCHAR(255) | UNIQUE, NOT NULL, indexed |
| password_hash | VARCHAR(255) | NOT NULL (bcrypt) |
| name | VARCHAR(255) | NOT NULL |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), on update |

### 2.2 workspaces

Generic container for agent context. Displayed as "companies" in the Tally agent UI — the label is agent-type-specific, not hardcoded.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| user_id | UUID | FK → users, NOT NULL, indexed |
| name | VARCHAR(255) | NOT NULL |
| agent_type | VARCHAR(50) | NOT NULL, DEFAULT "tally" |
| config | JSONB | NOT NULL, DEFAULT {} |
| memory | JSONB | NOT NULL, DEFAULT {} |
| is_deleted | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), on update |

**config schema for agent_type="tally":**
```json
{
  "tally_host": "192.168.1.5",
  "tally_port": 9000
}
```

**memory schema for agent_type="tally":**
```json
{
  "fy_start": "01-04-2025",
  "fy_end": "31-03-2026",
  "branches": ["Mumbai", "Pune"],
  "bank_accounts": ["HDFC Bank", "SBI Current A/c"],
  "common_ledgers": ["Sales - Haryana", "Purchase - Maharashtra"]
}
```

### 2.3 conversations

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| user_id | UUID | FK → users, NOT NULL, indexed |
| workspace_id | UUID | FK → workspaces, NOT NULL, indexed |
| title | VARCHAR(255) | NULL (auto-generated from first message) |
| tag | VARCHAR(50) | NULL (optional: "Sales", "GST", "Expenses") |
| is_deleted | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | DEFAULT now(), on update |

### 2.4 messages

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| conversation_id | UUID | FK → conversations, NOT NULL, indexed |
| role | VARCHAR(20) | NOT NULL ("user" or "assistant") |
| content | TEXT | NOT NULL |
| data | JSONB | NULL (table: {headers, rows}) |
| chart | JSONB | NULL (chart spec) |
| created_at | TIMESTAMP | DEFAULT now() |

Index: `(conversation_id, created_at)` for ordered message retrieval.

### 2.5 usage_logs

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| message_id | UUID | FK → messages, UNIQUE, NOT NULL |
| user_id | UUID | FK → users, NOT NULL, indexed |
| workspace_id | UUID | FK → workspaces, NOT NULL, indexed |
| conversation_id | UUID | FK → conversations, NOT NULL |
| total_input_tokens | INTEGER | NOT NULL |
| total_output_tokens | INTEGER | NOT NULL |
| total_cost_usd | DECIMAL(10,6) | NOT NULL |
| model_primary | VARCHAR(50) | NOT NULL |
| latency_ms | INTEGER | NOT NULL |
| agent_calls | JSONB | NOT NULL |
| created_at | TIMESTAMP | DEFAULT now() |

**agent_calls schema:**
```json
[
  {"agent": "classifier", "model": "claude-haiku-4-5-20251001", "input_tokens": 800, "output_tokens": 50, "cost_usd": 0.0002},
  {"agent": "query", "model": "claude-sonnet-4-6", "input_tokens": 5000, "output_tokens": 1200, "cost_usd": 0.012},
  {"agent": "analysis", "model": "claude-sonnet-4-6", "input_tokens": 8000, "output_tokens": 2800, "cost_usd": 0.024},
  {"agent": "chart_advisor", "model": "claude-haiku-4-5-20251001", "input_tokens": 1500, "output_tokens": 100, "cost_usd": 0.0004}
]
```

Indexes for billing queries:
- `(user_id, created_at)` — per-user monthly cost
- `(workspace_id, created_at)` — per-company cost breakdown

---

## 3. Authentication

### 3.1 Password Policy

Financial data warrants strong passwords:
- Minimum 12 characters
- Must contain: uppercase + lowercase + digit + special character
- Validated server-side (not just frontend)

### 3.2 JWT Tokens

| Token | Expiry | Storage |
|-------|--------|---------|
| Access token | 30 minutes | Frontend memory (React state) |
| Refresh token | 7 days | httpOnly secure cookie |

Signed with `JWT_SECRET` environment variable (minimum 32 chars).

### 3.3 Rate Limiting

- Login: 5 attempts per 15 minutes per email address
- Register: 3 attempts per hour per IP
- Implementation: in-memory counter (upgrade to Redis when scaling)

### 3.4 Endpoints

```
POST /api/auth/register
  Body: {email, password, name}
  Returns: {user: {id, email, name}, access_token}
  Sets: refresh_token httpOnly cookie
  Validates: email format, password policy, email uniqueness

POST /api/auth/login
  Body: {email, password}
  Returns: {user: {id, email, name}, access_token}
  Sets: refresh_token httpOnly cookie
  Rate limited: 5/15min per email

POST /api/auth/refresh
  Reads: refresh_token from cookie
  Returns: {access_token}

GET /api/auth/me
  Auth: required
  Returns: {id, email, name, created_at}

POST /api/auth/logout
  Clears: refresh_token cookie
```

### 3.5 Auth Middleware

FastAPI dependency `get_current_user()`:
- Extracts Bearer token from Authorization header
- Validates JWT signature + expiry
- Returns user_id (injected into endpoint handlers)
- Public endpoints (no auth): `/api/auth/*`, `/api/health`
- All other endpoints: auth required

---

## 4. API Changes

### 4.1 New Endpoints

**Workspaces** (displayed as "companies" in Tally agent UI):

```
GET /api/workspaces
  Auth: required
  Returns: [{id, name, agent_type, config, memory, created_at, updated_at}]
  Filter: user's workspaces only, excludes soft-deleted

POST /api/workspaces
  Auth: required
  Body: {name, agent_type?, config}
  Returns: {id, name, agent_type, config, memory}
  Default: agent_type = "tally"

PATCH /api/workspaces/:id
  Auth: required (owner only)
  Body: {name?, config?, memory?}
  Returns: updated workspace

DELETE /api/workspaces/:id
  Auth: required (owner only)
  Effect: soft delete (is_deleted = true)
```

**Conversations:**

```
GET /api/workspaces/:id/conversations
  Auth: required
  Returns: [{id, title, tag, created_at, updated_at}]
  Sorted: by updated_at desc
  Filter: excludes soft-deleted

POST /api/workspaces/:id/conversations
  Auth: required
  Body: {title?, tag?}
  Returns: {id, title, tag, workspace_id}

GET /api/workspaces/:id/conversations/:cid
  Auth: required
  Returns: {id, title, tag, messages: [{id, role, content, data, chart, created_at}]}

PATCH /api/workspaces/:id/conversations/:cid
  Auth: required
  Body: {title?, tag?}
  Returns: updated conversation

DELETE /api/workspaces/:id/conversations/:cid
  Auth: required
  Effect: soft delete
```

### 4.2 Modified Endpoints

**POST /api/chat** (main chat endpoint):

```
Auth: required
Body: {message, workspace_id, conversation_id}
Returns: {message, data?, chart?, conversation_id, usage?}

Behavior:
  1. Load workspace config (tally_host, tally_port, agent_type)
  2. Load conversation history from DB (last N messages)
  3. Persist user message to messages table
  4. Route to agent_registry[agent_type].process_query()
  5. Persist assistant response to messages table (content + data + chart)
  6. Log usage to usage_logs table
  7. Auto-generate conversation title from first message (if title is null)
  8. Return response
```

**GET /api/reports/{name}:**
- Now requires auth
- Reads tally_host/port from workspace config (passed via query param `workspace_id`)

**GET/POST /api/tally-mode:**
- Now requires auth
- Scoped to workspace (per-workspace mock/live toggle, not global singleton)

**Deprecated (legacy mode only):**
- `GET /api/companies` — still served in legacy mode (no DB). In DB mode, company info comes from workspace config. Existing file `backend/api/companies.py` kept for backward compatibility.

### 4.3 Usage Endpoint

```
GET /api/usage
  Auth: required
  Query: ?from=YYYY-MM-DD&to=YYYY-MM-DD&workspace_id=<optional>
  Returns: {
    total_input_tokens, total_output_tokens, total_cost_usd,
    by_workspace: [{workspace_id, name, cost_usd, message_count}],
    by_day: [{date, cost_usd, message_count}]
  }
```

---

## 5. Agent Registry & Templateization

### 5.1 Registry

```python
# backend/agents/registry.py

from backend.agents.orchestrator import Orchestrator as TallyOrchestrator

agent_registry: dict[str, type] = {
    "tally": TallyOrchestrator,
    # future: "support": SupportOrchestrator,
}

def get_agent(agent_type: str):
    if agent_type not in agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return agent_registry[agent_type]
```

### 5.2 Agent Interface

Each registered agent must implement:

```python
class BaseAgent:
    async def process_query(
        self,
        message: str,
        workspace_config: dict,    # from workspace.config JSONB
        workspace_memory: dict,    # from workspace.memory JSONB
        conversation_messages: list[dict],  # history from DB
    ) -> AgentResponse:
        ...
```

The existing `Orchestrator` is renamed to `TallyOrchestrator` and adapted to accept `workspace_config` (extracts tally_host/port) instead of reading from global `Settings`. Internal logic (classify → query → analysis → chart) unchanged.

### 5.3 Per-Workspace TallyClient

Currently `TallyClient` is a singleton created at app startup with host/port from `.env`. New behavior:

- Chat endpoint creates `TallyClient(host=workspace.config["tally_host"], port=workspace.config["tally_port"])` per request
- Client instances are lightweight (just stores host/port, uses httpx async) so per-request creation is fine
- Mock mode stored in workspace config: `workspace.config.mock_mode` (not global)

---

## 6. Frontend Architecture

### 6.1 Routing

Using React Router v7:

```
/login              → LoginPage (public)
/register           → RegisterPage (public)
/                   → ChatApp (protected, redirect to latest conversation)
/c/:convId          → ChatApp with specific conversation (protected)
/settings           → UserSettings (protected)
```

Protected routes redirect to `/login` if not authenticated.

### 6.2 Layout

```
┌──────────────────────────────────────────────────────┐
│ Header  [Company Dropdown ▼]           [User ▼ Logout]│
├────────────┬─────────────────────────────────────────┤
│ Sidebar    │ Chat Area (existing ChatWindow)          │
│ 280px      │                                          │
│            │ ┌─────────────────────────────────────┐  │
│ BHARAT TR  │ │ MessageBubble                       │  │
│  Sales Q3  │ │ MessageBubble + DataTable           │  │
│  GST Rev   │ │ MessageBubble + ChartRenderer       │  │
│  + New Chat│ │                                     │  │
│            │ ├─────────────────────────────────────┤  │
│ OTHER CO   │ │ Input bar                           │  │
│  Stock..   │ │                                     │  │
│  + New Chat│ └─────────────────────────────────────┘  │
│            │                                          │
│ ────────── │                                          │
│ + Connect  │                                          │
│   Company  │                                          │
├────────────┴─────────────────────────────────────────┤
│ Mobile: sidebar as hamburger drawer                   │
└──────────────────────────────────────────────────────┘
```

### 6.3 New Components

| Component | Purpose |
|-----------|---------|
| `LoginPage` | Email + password form, link to register |
| `RegisterPage` | Email + password + name form, password strength indicator |
| `AuthContext` | Provider: user state, tokens, login/logout/refresh functions |
| `ProtectedRoute` | Wrapper: redirects to /login if unauthenticated |
| `Sidebar` | Conversation list grouped by workspace (company) |
| `ConversationList` | List of chats under a company, "+ New Chat" button |
| `ConnectCompanyModal` | Form: company name, tally_host, tally_port |
| `UserMenu` | Dropdown: profile, settings, usage, logout |

### 6.4 Existing Component Changes

| Component | Change |
|-----------|--------|
| `App.tsx` | Wrap with AuthContext + BrowserRouter, add route definitions |
| `ChatWindow` | Get conversationId from route params, load history from API on mount |
| `Header` | Company selector now DB-backed (from workspaces API), add UserMenu |
| `SessionContext` | Removed — replaced by AuthContext + route params |

### 6.5 State Management

- **Auth state**: `AuthContext` — user object, access token, refresh logic
- **Workspace/conversation state**: fetched from API, cached in React state (no global store needed)
- **Chat messages**: loaded from API on conversation open, appended on new messages (same as current, but persisted)
- No Redux/Zustand — React context + local state sufficient for this scope

---

## 7. Usage Logging & Langfuse Enrichment

### 7.1 Usage Capture

Each agent call already logs token counts (added in Phase 16). The pipeline aggregates them:

```python
# In chat endpoint, after agent pipeline completes:
usage_data = {
    "total_input_tokens": sum(call.input_tokens for call in agent_calls),
    "total_output_tokens": sum(call.output_tokens for call in agent_calls),
    "total_cost_usd": compute_cost(agent_calls),  # model → price lookup
    "model_primary": workspace.config.get("model", "claude-sonnet-4-6"),
    "latency_ms": int((end_time - start_time) * 1000),
    "agent_calls": [call.to_dict() for call in agent_calls],
}
# Insert into usage_logs table
```

### 7.2 Cost Calculation

```python
# backend/utils/pricing.py
PRICING = {
    "claude-sonnet-4-6":       {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-opus-4-6":          {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
}
```

Updated when Anthropic changes pricing. Used for cost_usd calculation per agent call.

### 7.3 Langfuse Trace Enrichment

Current: auto-instrumented via OpenTelemetry, traces have no business context.

New: add span attributes so Langfuse traces are filterable:

```python
span.set_attribute("user_id", str(user_id))
span.set_attribute("workspace_id", str(workspace_id))
span.set_attribute("conversation_id", str(conversation_id))
span.set_attribute("agent_type", workspace.agent_type)
span.set_attribute("workspace_name", workspace.name)
```

This lets you filter traces in Langfuse by user, company, or conversation.

---

## 8. Configuration

### 8.1 New Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | None | Postgres connection string. If unset, app runs in legacy mode. |
| `JWT_SECRET` | None (required when DB mode) | JWT signing key, minimum 32 chars |
| `JWT_ACCESS_TOKEN_EXPIRY_MINUTES` | 30 | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRY_DAYS` | 7 | Refresh token lifetime |

### 8.2 Legacy Mode

When `DATABASE_URL` is not set:
- App runs exactly as today: in-memory SessionStore, no auth, no persistence
- All 1024 existing tests pass unchanged
- Useful for local development and testing without Postgres

When `DATABASE_URL` is set:
- Full auth + persistence enabled
- Requires `JWT_SECRET` to be set
- Alembic migrations must be run first

---

## 9. Migration Path

Six incremental steps, each independently testable:

### Step 1: Database Layer
- Add SQLAlchemy 2.0 (async), Alembic, asyncpg to dependencies
- Define models: users, workspaces, conversations, messages, usage_logs
- Create initial Alembic migration
- Add `DATABASE_URL` to config
- New tests: model creation, migration up/down

### Step 2: Auth
- Add `backend/api/auth.py` — register, login, refresh, me, logout
- Add `get_current_user()` dependency
- Password hashing (passlib + bcrypt), JWT (python-jose or PyJWT)
- Rate limiting (in-memory)
- Guard existing endpoints with auth (skip if legacy mode)
- New tests: auth flow, password validation, rate limiting, JWT expiry

### Step 3: Persistence
- Replace `SessionStore` usage in chat endpoint with DB read/write
- Load conversation history from messages table
- Persist user + assistant messages after each chat turn
- Auto-generate conversation title from first user message
- New tests: message persistence, conversation loading, title generation

### Step 4: Workspace Routing
- Add workspace CRUD endpoints
- `TallyClient` created per-request from workspace config
- Agent registry routes by `workspace.agent_type`
- Rename `Orchestrator` → `TallyOrchestrator`, implement `BaseAgent` interface
- Add usage logging to chat endpoint
- New tests: workspace CRUD, per-workspace client, usage logging

### Step 5: Frontend UI
- Add React Router, AuthContext, ProtectedRoute
- Login/Register pages
- Sidebar with conversation list grouped by company
- ConnectCompanyModal
- ChatWindow loads conversation from API
- UserMenu with logout
- New tests: auth pages, sidebar, conversation navigation, protected routes

### Step 6: Langfuse Enrichment
- Add user/workspace/conversation attributes to OTLP spans
- Verify traces appear with metadata in Langfuse dashboard
- Usage endpoint for frontend display

---

## 10. New File Structure

```
backend/
├── db/
│   ├── __init__.py
│   ├── engine.py          # async engine + session factory
│   ├── models.py          # SQLAlchemy ORM models
│   └── migrations/        # Alembic migrations
│       ├── env.py
│       └── versions/
├── api/
│   ├── auth.py            # register, login, refresh, me, logout
│   ├── workspaces.py      # workspace CRUD
│   ├── conversations.py   # conversation CRUD + messages
│   ├── usage.py           # usage aggregation endpoint
│   ├── chat.py            # existing, modified
│   ├── dependencies.py    # existing + get_current_user, get_db_session
│   └── models.py          # existing + new request/response models
├── agents/
│   ├── registry.py        # agent_registry mapping
│   ├── base.py            # BaseAgent interface
│   ├── orchestrator.py    # renamed to TallyOrchestrator internally
│   └── ...                # existing agent files unchanged
├── utils/
│   └── pricing.py         # model → cost lookup
└── config.py              # existing + new DB/JWT settings

frontend/src/
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   └── SettingsPage.tsx
├── components/
│   ├── Sidebar.tsx
│   ├── ConversationList.tsx
│   ├── ConnectCompanyModal.tsx
│   ├── UserMenu.tsx
│   ├── ProtectedRoute.tsx
│   └── ...                # existing components unchanged
├── context/
│   ├── AuthContext.tsx     # new
│   └── SessionContext.tsx  # removed
├── api/
│   └── client.ts          # API client with auth headers
└── App.tsx                # updated with Router + AuthContext
```

---

## 11. Out of Scope (Deferred)

| Item | Deferred To |
|------|-------------|
| Password reset (email) | Set A2 (needs email service) |
| Razorpay billing | Set A2 |
| Team management (multi-user per workspace) | Set A2 |
| pgvector / semantic memory | Set C |
| Tally data sync to cloud DB | Set C |
| File upload / compliance features | Set B (see below) |
| OAuth (Google/Microsoft) | Future |
| Email verification | Future |

### Set B: Compliance & Automation (Deferred)

Tally Bridge is currently **read-only** (18 query tools). Set B adds **write operations** and **file-driven workflows**:

**File Upload & Processing:**
- Upload bank statements (CSV/PDF/Excel), invoices, employee expense reports
- AI parses uploaded files, extracts structured data (amounts, dates, parties, GST numbers)
- User reviews and approves extracted data before any Tally write

**Tally Write Operations (new tools):**
- Ledger creation — auto-create ledgers for new parties/expense heads found in uploads
- Voucher posting — create sales/purchase invoices, payment/receipt entries, journal entries
- Expense entry — employee expenses → vouchers with appropriate ledger mappings

**Reconciliation:**
- Bank reconciliation — match bank statement entries against Tally receipts/payments, flag unmatched
- Purchase reconciliation — match purchase invoices against GRNs and vendor statements
- Auto-suggest matches, user confirms

**GST Compliance:**
- Update invoices with ITC (Input Tax Credit) classification
- GSTR-1 / GSTR-3B preparation assistance
- Flag mismatches between purchase register and GST portal data

**Dependency on Set A1:** Requires auth (multi-user access control for write operations), persistent chat history (audit trail of what was posted), and workspace config (Tally connection for writes).
