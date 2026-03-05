# Phase 4: React Frontend — Design Document

**Date**: 2026-03-04
**Status**: Approved

## Tech Stack

- React 19 + TypeScript + Vite
- Tailwind CSS v4 (utility classes only, no component library)
- Recharts (bar, line, pie, grouped_bar charts)
- react-markdown (agent response rendering)
- axios (HTTP client)
- lucide-react (icons)
- Light theme only

## State Management

useState + React Context. No external state library.

- `useState` in ChatWindow for messages array, loading state, input value
- `SessionContext` for session_id and active company (global)

## Project Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── api/
│   │   └── client.ts            # axios instance + typed API functions
│   ├── context/
│   │   └── SessionContext.tsx    # session_id, company, setters
│   ├── types/
│   │   └── index.ts             # ChatMessage, ChartSpec, Company, etc.
│   ├── components/
│   │   ├── ChatWindow.tsx        # Main container: message list + input
│   │   ├── MessageBubble.tsx     # Single message with optional table/chart
│   │   ├── ChatInput.tsx         # Textarea + send button
│   │   ├── ChartRenderer.tsx     # Recharts wrapper
│   │   ├── DataTable.tsx         # Sortable table + CSV export
│   │   ├── QuickActions.tsx      # Preset query buttons
│   │   ├── CompanySelector.tsx   # Company dropdown
│   │   └── Header.tsx            # Top bar: title + health + company
│   └── utils/
│       └── format.ts            # Indian currency/number formatting
```

## API Contract

All calls to `http://localhost:8000/api/`.

### POST /api/chat
```typescript
// Request
{ message: string; session_id?: string; company?: string }

// Response
{ message: string; data?: { headers: string[]; rows: any[][] }; chart?: ChartSpec; session_id: string }
```

### GET /api/health
```typescript
{ status: string; tally_connected: boolean; tally_url: string }
```

### GET /api/companies
```typescript
{ companies: { name: string }[] }
```

### ChartSpec
```typescript
{ chart_type: string; title: string; data: Record<string, any>[]; config?: Record<string, any> }
```

## Component Behaviors

### ChatWindow
- Holds `messages: ChatMessage[]` in useState
- Auto-scrolls to bottom on new message
- Shows "Thinking..." skeleton bubble while loading
- On mount: fetches companies and health status

### MessageBubble
- User messages: right-aligned, blue background
- Agent messages: left-aligned, gray background, markdown rendered
- If response has `data` → renders DataTable below text
- If response has `chart` → renders ChartRenderer below table

### ChatInput
- Auto-growing textarea
- Enter to send, Shift+Enter for newline
- Disabled while loading

### ChartRenderer
- Maps chart_type to Recharts component:
  - `bar` → BarChart
  - `line` → LineChart
  - `pie` → PieChart
  - `grouped_bar` → BarChart with multiple Bar children
- ResponsiveContainer for auto-sizing
- Colors from config or defaults

### DataTable
- Renders headers + rows
- Click column header to sort (toggle asc/desc)
- "Export CSV" button
- Indian number formatting for numeric cells

### QuickActions
- Shown when chat is empty or below input
- 6 presets: "P&L this month", "Outstanding receivables", "Cash balance", "Stock summary", "Top 10 customers", "Sales vs purchases"
- Click sends query as if user typed it

### CompanySelector
- Fetches from GET /api/companies on mount
- Dropdown in Header
- Selection stored in SessionContext, sent with chat requests

### Header
- Fixed top bar
- Left: app title ("TallyPrime AI")
- Right: health indicator dot (green/red) + CompanySelector

## Styling

- Tailwind utility classes, no custom CSS beyond index.css imports
- Max-width 768px container, centered, full viewport height
- User bubbles: `bg-blue-600 text-white rounded-2xl rounded-br-sm`
- Agent bubbles: `bg-gray-100 text-gray-900 rounded-2xl rounded-bl-sm`
- Charts/tables: full width within bubble, subtle border
- Loading: pulsing dot animation in agent-style bubble
- Responsive: single column, wrapping quick actions on mobile
- System font stack

## Error Handling

- Network/API errors → red-tinted error bubble in chat
- Tally disconnected → red health dot, tooltip
- Session expiry → auto-create new session silently

## Out of Scope

- Dark mode
- Conversation persistence (localStorage)
- PDF/Excel export
- Streaming responses
- WhatsApp integration
