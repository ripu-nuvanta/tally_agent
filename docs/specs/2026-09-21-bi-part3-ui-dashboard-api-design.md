# Part 3 — UI and the report/dashboard API

> **Brainstorm design, not yet implemented.** Docs only; no code changes have been made for this.
> Split from `2026-09-15-bi-sync-agent-design.md` on 2026-09-21. The original is kept unchanged.
>
> This part covers the web app: navigation and pages, the state screens, the integrity and history
> cards, the Dashboard and Insights, and the report/dashboard API behind them.
>
> The other two parts:
> - **Part 1** (`2026-09-21-bi-part1-sync-design.md`): syncing. It also holds the shared context,
>   out of scope, R20 and the cross-cutting questions.
> - **Part 2** (`2026-09-21-bi-part2-ai-db-queries-design.md`): the query layer and AI chat.
>
> IDs are the same as in the original (decision N, Rn, Qn, probe n).

## 1. Scope
- The new navigation, page layout, routes and responsive behaviour (§8).
- The sync, backfill and integrity state screens, plus the Sync / Settings cards (§4, §7, §8).
- The Dashboard KPI tiles and the Insights list (§6), and the report/dashboard API that serves them
  (§5, still to design).
- Context and what is out of scope: Part 1, "Context" and "Out of scope (v1)".

## 2. Decisions this part implements
| # | Decision |
|---|---|
| 1 | Existing write features untouched. **Existing live-connected workspaces (with `tally_host`) keep the write flow exactly as today.** |
| 10 | Sync-agent workspaces have no `tally_host`, so **the write flow is not available on them in v1**. The UI says so ("Writing to Tally isn't available for synced companies yet") instead of hiding it silently. |

Decisions 8 (chat locked only during the first sync) and 13 (an integrity alert never blocks chat or
dashboards) are defined in Part 2; decision 12 (no full resync is ever automatic) in Part 1. This part
renders them.

## 3. Depends on / provides
**Depends on Part 1:**
- **Status contract:** `GET /api/workspaces/{id}/sync-status` (sync state incl. `restore_detected`,
  backfill `{oldest_available_fy, oldest_complete_fy, books_from, percent, state}`, `last_parity`, a
  pending re-link prompt) and `GET/DELETE /api/devices`.
- **Integrity contract:** parity states and the surfacing rules.

**Depends on Part 2:**
- **The query layer:** every Dashboard tile is computed through Part 2's Rules 1–2, never with its
  own SQL.
- **The answer contract:** `source`, `as_of`, `warnings[]` and the refusal wording on every figure.

**Provides:** the web UI and the report/dashboard API (§5).

## 4. Web states (S3)
- States: **connecting** (waiting for the first connection) / **syncing %** / **error** / **Tally offline** / **ready** / **stale** / **restore detected** (Part 1, "Company identity changes"), each combined with chat locked or unlocked. A pending **Re-link** prompt (same name, new GUID) is shown alongside whichever state applies.
- "Last synced X ago" is always visible once ready; a stale badge appears when the last sync is old (threshold: open question Q3).
- Synced workspaces show the "writing not available yet" note (decision 10).
- Integrity state (Part 1, "Integrity (parity) system") overlays these as an independent dimension — see §8.9.
- Backfill state (decision 7b) is a third dimension — History card in §8.4, matrix in §8.9.
- Navigation and page layout: see §8.

## 5. Report / dashboard API (open design item)
The original spec defines what every tile shows (§6) but never the endpoints that serve them. This
section lists only the known requirements; the S5 spec designs the endpoints and response shapes.

- **Serves** every Dashboard tile and the Insights list (§6) for the selected workspace, with the
  period selector (this month / this FY / last FY / custom).
- **Built on Part 2's query layer.** No endpoint re-implements a figure; tiles go through the same
  Rules 1–2 as the chat tools, so a tile and its chat click-through always agree.
- **Every tile result carries Part 2's answer contract** (`source`, `as_of`, `warnings[]`), plus a
  status the UI can render for the §6 states: "still loading", "no month-end figure yet", "no
  comparison yet", "no figure yet". The structured status is Part 2's open design item ("Open design
  items", item 1); this API depends on it.
- **The freshness header** ("Last synced X ago", stale badge) comes from Part 1's status contract,
  not from these endpoints.
- **Insights items** carry a statement, the evidence, a severity, a first-seen date and a dismiss
  action. Dismissals need storage (§9).
- **The integrity ribbon** is scoped per tile (§9).
- **Workspaces:** sync-agent workspaces only. Live-connected ones show "Connect via sync agent to see
  dashboards" (assumed, §8.9). Who can see a workspace is Q28 (Part 1).

## 6. Dashboard & Insights (S5)

Answers Q13. Two distinct pages, two distinct jobs:

| Page | Job | Character |
|---|---|---|
| **Dashboard** | **KPIs** — what the numbers are right now | Fixed, always the same tiles, glanceable |
| **Insights** | **Demands, reconciliation, alerts** — what needs attention | Variable, a ranked list of things to act on; empty when all is well |

The distinction: Dashboard tells you *how the business is doing*; Insights tells you *what to do
today*. A number belongs on the Dashboard; a number that implies an action belongs in Insights.

### Dashboard — the KPI set
Every tile names its source per Part 2 "Sources" (computed / mirrored / snapshot) and carries the
freshness label. All figures are INR base amounts (decision 15). Cancelled and optional vouchers are
excluded from every computed tile (R16) — that exclusion is a property of the query layer, not of
each tile.

| Tile | Definition | Source | Comparison |
|---|---|---|---|
| Sales | Sum of sales vouchers, MTD and YTD | computed | vs same period last FY |
| Purchases | Sum of purchase vouchers, MTD and YTD | computed | vs same period last FY |
| Gross margin | Sales − cost of goods sold, as ₹ and %. COGS = opening stock + purchases − closing stock, with the stock values taken from Tally's Stock Summary snapshots at the period's start and end | computed (sales, purchases) + snapshot (stock values) | vs same period last FY, only when stock snapshots exist for all four dates; otherwise "no comparison yet" |
| Cash & bank | Closing balance of the ledgers under Cash-in-Hand + Bank Accounts | mirrored (current); computed (month-end baseline — see notes) | vs last month-end |
| Receivables | Total outstanding, split current vs overdue (overdue = past the due date Tally reports on each bill — probe 23) | snapshot (Bills Receivable) | vs last month-end |
| Payables | Total outstanding, split current vs overdue (same due-date rule) | snapshot (Bills Payable) | vs last month-end |
| Stock value | Closing stock value | snapshot (Stock Summary) | vs last month-end |
| GST position | Output tax − input tax for the period, by duty head (IGST / CGST / SGST / cess). Output = GST-ledger lines on sales-side vouchers (sales, credit notes); input = those on purchase-side vouchers (purchases, debit notes); tax payments and set-off journals excluded. GST ledgers are identified by Tally's own classification (probe 23), never by name. Indicative, not a GSTR-3B figure | computed | current period |
| Top customers | Top N by sales for the period | computed | — |
| Top items | Top N by value sold for the period | computed | — |
| Sales trend | Monthly sales, last 12–24 months | computed | — |

Notes:
- **Period selector** (this month / this FY / last FY / custom) applies to the period-scoped tiles;
  balance tiles are always "as on" the latest available date.
- **Multi-year comparisons become possible as the backfill fills in** (decision 7b). A comparison
  whose baseline period is behind the watermark shows the "still loading" treatment rather than a
  wrong or absent baseline (Part 2, "Rule 2").
- **"vs last month-end" baselines** come from the routine month-end snapshots (Part 1, "Month-end
  snapshots"). No snapshot for that month-end → "no month-end figure yet", never a zero baseline.
- **Exception — Cash & bank.** The month-end TB holds only the top-level groups (Cash-in-Hand and
  Bank Accounts sit inside Current Assets, Part 1 "What the code already gives us"), so it cannot
  supply this baseline. The baseline is **computed backwards** by Part 2's Rule 1: the current
  mirrored balance minus our lines dated after the month-end, labelled *computed*. It is the same
  rule chat uses, so the tile and its chat click-through give the same figure.
- **Gross margin stock values:** MTD uses the last month-end Stock Summary and the current one; YTD
  uses the 31 March snapshot the first sync captures (Part 1, "Month-end snapshots"). A boundary with
  no stock snapshot → "no figure yet". Sales − purchases is never shown as margin. A company with no
  inventory has zero stock, so its margin is sales − purchases by definition.
- Every tile is **clickable through to AI Chat** with the equivalent question pre-filled, so the
  dashboard is an entry point to the chat rather than a dead end.

### Insights — three pillars
A ranked list of items needing attention, each with a plain-language statement, the evidence, and a
link that opens it in AI Chat. **Insights is empty when nothing needs attention** — it must never
manufacture findings to look busy.

1. **Demands** — money to chase or to pay: overdue receivables by party and age, overdue payables,
   large bills approaching due date, parties who have stopped buying. *(Scope needs confirming —
   see Q13a below.)*
2. **Reconciliation** — items that don't tie out **within the Tally data we hold**: party ledger
   balance vs the sum of its open bills, stock ledger movement vs Stock Summary value, a voucher
   with no bill allocation against a bill-wise party, suspense/unclassified ledger activity.
   *(External-source reconciliation is a different feature — see Q13b.)*
3. **Alerts** — anomalies and exceptions: unusual transaction size for a party, a sudden margin
   drop, negative stock, a ledger that changed after being reconciled, duplicate-looking vouchers.
   The **data-integrity alert** (Part 1, "Integrity (parity) system") also surfaces here, alongside
   its dashboard ribbon.

Each item carries a severity, a first-seen date, and a dismiss action; a dismissed item does not
return unless its underlying condition changes.

### What Insights is not (v1)
- **Not** bank reconciliation against a bank statement — that needs an external file and Tally's own
  reconciliation mechanism, which probe work showed does not persist via voucher import (B1d,
  deferred, `docs/roadmap.md`).
- **Not** GST return reconciliation (GSTR-2B vs purchase register) — that needs GSTN data we do not
  sync. A candidate for a later slice, not v1.
- **Not** predictive forecasting.

Both exclusions matter because "reconciliation" usually means one of those two in Indian practice;
v1's reconciliation is strictly *internal consistency within the synced books*.

## 7. Integrity surfacing in the UI
How each integrity state shows on the web pages. The rules every surface follows (`suspect` is
invisible, chat is never blocked, the wording never implies their books are wrong) are in Part 1,
"Surfacing rules". The AI Chat row is in Part 2, "Caveats in chat"; the tray row is in Part 1.

| Surface | `ok` | `suspect` | `alert` | `hard_alert` |
|---|---|---|---|---|
| Sync / Settings "Data integrity" card | green "Matches Tally as of 18 Sep, 9:12 pm" | amber "Re-checking a difference with Tally" | red "3 ledgers don't match Tally" + affected list + "Re-check now"; **"Re-sync this year" only after two failed heals** (escalation step 3, decision 12) | red card + affected list + "Contact support"; internal engineering flag raised |
| Dashboard / Insights | nothing | nothing | amber ribbon, scoped: "Receivables may be off — we're re-checking with Tally" | same ribbon, stronger wording |

Implementation note: there is no notification system today — the only backend→frontend state channel
is the 30s health poll in `TallyStatusBadge.tsx:10`. Integrity state rides on
`GET /api/workspaces/{id}/sync-status` (Part 1's status contract).

## 8. Navigation & page layout (new design, 2026-09-15)

> Source: design input shared on 2026-09-15. Items marked **(given)** come directly from that input. Items marked **(assumed)** are interpretations to confirm via Q11–Q18.

### 8.1 The change as given
| Area | What it holds |
|---|---|
| **Top bar** | Logo, Company selector, User **(given)** |
| **Page titles** | Move out of the top bar into the main right section **(given)** |
| **High-level menu** | Dashboard, Insights, AI Chat, Sync / Settings **(given)** |
| **AI Chat** | Chats become a submenu under it **(given)** |
| **Sync / Settings** | Connect Tally status and company selector; picks up companies automatically **(given)** |

### 8.2 Layout (desktop)
```
┌──────────────────────────────────────────────────────────────────┐
│ TOP BAR:  [Logo]            [Company selector ▾]        [User ▾] │
├───────────────────┬──────────────────────────────────────────────┤
│ LEFT MENU         │  MAIN SECTION                                │
│                   │  ┌────────────────────────────────────────┐  │
│ ▸ Dashboard       │  │ Page title          [page actions]     │  │
│ ▸ Insights        │  │ Last synced 8 min ago                  │  │
│ ▾ AI Chat         │  └────────────────────────────────────────┘  │
│     + New chat    │                                              │
│     Chat 1   ⋯    │  …page content…                              │
│     Chat 2   ⋯    │                                              │
│ ▸ Sync / Settings │                                              │
└───────────────────┴──────────────────────────────────────────────┘
```

### 8.3 Top bar
| Element | Behaviour |
|---|---|
| **Logo** | Click → Dashboard of the selected company **(assumed)** |
| **Company selector** | Dropdown of the user's connected companies (one workspace each). Selecting one switches the whole app to that workspace and stays on the same menu page (e.g. Dashboard → Dashboard) **(assumed, Q12)**. Each entry shows a small sync-state dot (ready / syncing / stale / offline / restore detected) **(assumed)**. A footer link "Connect a company" goes to Sync / Settings **(assumed)** |
| **User menu** | Existing `UserMenu.tsx` (profile, logout) **(given: "user")** |
| **Removed from top bar** | Page/chat title (moves to main section, **given**); Live/Demo badge and demo toggle (move to Sync / Settings, **assumed, Q17**) |

### 8.4 Left menu
**Dashboard**
- Purpose: the **KPI** overview for the selected company (S5) — sales, purchases, gross margin, cash & bank, receivables/payables, stock value, GST position, top customers/items, sales trend. Full tile definitions in **§6**.
- Period selector on period-scoped tiles; balance tiles are always "as on" the latest available date. Every tile links through to AI Chat with the equivalent question pre-filled.
- Data: our DB + Tally report snapshots with "as of" time (Part 2, "Sources"), served by the report/dashboard API (§5).
- Page title: "Dashboard". Header shows "Last synced X ago" and the stale badge.
- First sync not finished → progress panel instead of tiles; nothing synced yet → "Waiting for Tally" panel (Q2).

**Insights**
- Purpose: **demands, reconciliation, alerts** — a ranked list of things needing attention (§6). Not a second dashboard.
- Each item: plain-language statement + evidence + severity + first-seen date + dismiss, with a link that opens it in AI Chat.
- **Empty state is a success state** ("Nothing needs your attention") — Insights must never manufacture findings to look busy.
- The data-integrity alert (Part 1, "Integrity (parity) system") surfaces here as well as in the dashboard ribbon.
- Same freshness header and first-sync states as Dashboard.

**AI Chat** (expandable)
- Submenu = today's conversation list for the **selected company only** (`ConversationList.tsx`), with the existing rename/delete kebab (⋯) and "+ New chat" at the top.
- The active chat is highlighted. The submenu expands automatically when a chat is open.
- Main section title = conversation title (inline rename could move here later), or "New chat" for a new conversation.
- On sync-agent workspaces, answers come from our DB (Part 2, S4); live-connected and demo workspaces keep today's path (decision 8). Chat is locked during the first sync with the progress message.
- Upload → Write to Tally stays inside AI Chat **for live-connected workspaces only**. Synced workspaces show the "writing not available yet" note (decision 10, Q14).

**Sync / Settings**
- **Connection status card:** agent online/offline (Q1), Tally reachable, our company open, sync state (connecting / syncing % / ready / stale / error / restore detected), last synced time, last error in plain words.
- **Company identity prompts** (Part 1, "Company identity changes"): "This looks like a new copy of *Bharat Traders* in Tally. Re-link?" (Q25), and the backup-restore card "Tally was restored from a backup — our copy may include entries that no longer exist" with **"Re-sync now"**. Both are offers the user acts on; nothing starts automatically (decision 12).
- **Companies:** list picked up **automatically** from the agent (given). The user connects one → a workspace is created (binding rules: Q11). Already-connected companies show their status.
- **History card** (decision 7b): "Full history loaded (Apr 2019 onwards)" when complete. When this company's books start later because it was split from an older Tally company, the card says so plainly, e.g. "Full history loaded — this company's books start in Apr 2023" (Part 1, "Background history backfill", Q32); after a restore or re-link, "Refreshing history after a restore — 40%" (all years stay available, Part 1 "What a full resync does…"); otherwise "Loading history — 2019-20 onwards, 60%" with the span already available. Shows an available-from date, not a false ETA (R29). If progress has stalled for several days while the agent is healthy, adds "Leave TallyPrime open longer to finish loading". Detail level: Q24.
- **Data integrity card** (§7): green "Matches Tally as of 18 Sep, 9:12 pm" / amber "Re-checking a difference with Tally" / red "3 ledgers don't match Tally" with the affected list. Actions: **"Re-check now"** and, only after two failed heals, **"Re-sync this year"** (decision 12 — never automatic). `hard_alert` keeps the red card and adds "Contact support" (§7). The `suspect` state renders as the amber "re-checking" wording, never as an alarm. While the backfill is incomplete the card states the verified span ("Checked against Apr 2024 onwards") so a green tick never overstates what was proven (R30).
- **Devices:** the PCs running the agent for this account, with "Remove device" (uses `GET/DELETE /api/devices`) **(assumed)**.
- **Setup help:** onboarding checklist (turn on Tally XML server, port 9000, keep Tally open, don't log off) linked to R10/R11 **(assumed)**.
- **Demo mode** toggle and **live-connected manual connect** (today's `ConnectCompanyModal.tsx`), if kept (Q16, Q17).
- "Sync now" is **not** on the web in v1; it stays in the agent tray **(assumed)**.

### 8.5 Two company selectors: roles
| Where | Role |
|---|---|
| Top bar | **Switch** between companies already connected (**assumed, Q12**) |
| Sync / Settings | **Connect** a new company from the automatically found list, and see each company's sync status (**given + assumed**) |

### 8.6 Routes (proposal)
| Route | Page |
|---|---|
| `/w/:workspaceId/dashboard` | Dashboard |
| `/w/:workspaceId/insights` | Insights |
| `/w/:workspaceId/chat` | AI Chat, new chat |
| `/w/:workspaceId/chat/:conversationId` | AI Chat, open conversation |
| `/w/:workspaceId/settings` | Sync / Settings |
| `/` after login | Redirect to the last used workspace's Dashboard (Q15) |
| Existing `/c/:conversationId`, `/w/:workspaceId` (`App.tsx:26-27`) | Redirect to the new chat / dashboard routes so old links keep working |

The workspace lives in the URL so a reload or shared link opens the same company and page.

### 8.7 Mapping from today's frontend
| Today (`frontend/src/`) | New |
|---|---|
| `components/Header.tsx`: brand, `CompanySelector`, chat title, demo toggle | Top bar with logo + company selector + user only. Chat title → main section header. Demo toggle → Settings (Q17) |
| `components/CompanySelector.tsx` | Reused in the top bar (switch) |
| `components/TallyStatusBadge.tsx` (Live/Demo) | Status card in Sync / Settings; small status dot in the company selector |
| `components/Sidebar.tsx`: workspace groups, conversations, "+ Connect Company" | Becomes the left menu with 4 items. Conversations → AI Chat submenu. "+ Connect Company" → Sync / Settings |
| `components/ConversationList.tsx` (rename/delete kebab) | Reused as the AI Chat submenu |
| `components/ConnectCompanyModal.tsx` (manual host/port, Check Connection, setup steps) | Replaced by Sync / Settings company list; kept only for live-connected mode if Q16 says so |
| `components/UserMenu.tsx` | Unchanged, in the top bar |
| `ChatApp.tsx` + `components/ChatWindow.tsx` | AI Chat page content |
| `App.tsx` routes | New routes (§8.6) with redirects |
| Nothing | New pages: Dashboard, Insights, Sync / Settings, plus a shared page header (title + freshness) |

### 8.8 Responsive
| Viewport | Behaviour |
|---|---|
| Desktop | Left menu always visible; AI Chat submenu expandable |
| Tablet | Left menu collapses to an icon rail; expands on tap **(assumed, Q18)** |
| Mobile | Top bar: menu button + logo + compact company selector + user avatar. Left menu opens as a drawer (like today's responsive drawer, Group A F6) and closes after navigation **(assumed, Q18)** |

Page titles stay in the main section on all viewports. Long company names and chat titles truncate with a tooltip.

### 8.9 Page × sync state matrix
| Sync state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| Connecting (never synced) | "Waiting for Tally" panel | Same | Locked, "Waiting for Tally" | Checklist + status "Waiting for Tally" |
| Syncing (first sync) | Progress panel (%) | Same | Locked, progress message | Progress bar + current step |
| Error | Last good data + error banner (or panel if no data) | Same | Unlocked if a first sync ever completed | Plain-language error + fix steps |
| Tally offline (after first sync) | Data + "last synced X ago" | Same | Unlocked | "Tally closed / company not open" (Q1) |
| Ready | Data | Data | Unlocked | "Up to date" |
| Stale | Data + stale badge | Same | Unlocked + stale note | Stale warning + likely cause |
| Restore detected (R8) | Data + restore caveat banner | Same | Unlocked; answers carry the restore caveat (Q26) | Restore card + "Re-sync now" (offer only, decision 12) |
| Re-link offered (same name, new GUID) | Data + "last synced X ago" (sync is paused) | Same | Unlocked | Re-link prompt (Q25); on confirm, new GUID saved + full resync offered |

**History backfill is a third, independent dimension** (decision 7b). Like integrity, it only ever
adds to the page and never locks anything — the 2-FY window is already `ready` by the time it runs:

| Backfill state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| `running` | data for the synced span; no banner (Q24) | same | unlocked; pre-watermark dates answer "still loading, 60% done" | "Loading history — 2019-20 onwards, 60%" |
| `complete` | no change | no change | all dates answer normally | "Full history loaded (Apr 2019 onwards)" |
| stalled (R29) | no change | no change | same "still loading" wording | progress + "Leave TallyPrime open longer to finish loading" |
| `resyncing` (whole-company resync after a restore / re-link) | data for every loaded year + restore caveat banner | same | unlocked; `resyncing` years answer **normally** with the restore caveat — never "still loading" | "Refreshing history after a restore — 40%" |

A single-FY parity resync does not change `backfill.state` (Part 1, "What a full resync does…"). It
shows only in the integrity dimension below, and that year keeps answering normally with its
integrity caveat.

**Integrity is a second, independent dimension** (Part 1, "Integrity (parity) system") — it overlays
whatever sync state applies, and only ever adds to the page; it never removes data or locks anything
(decision 13):

| Integrity state | Dashboard | Insights | AI Chat | Sync / Settings |
|---|---|---|---|---|
| `ok` | no change | no change | no change | green "Matches Tally as of …" |
| `suspect` | no change (invisible to the user) | no change | no change | amber "Re-checking a difference with Tally" |
| `alert` | scoped amber ribbon ("Receivables may be off — we're re-checking with Tally") | same | unlocked; affected answers carry a one-line caveat | red card + affected ledgers + "Re-check now" (+ "Re-sync this year" only after two failed heals) |
| `hard_alert` | same ribbon, stronger wording | same | same caveat | red card + "Contact support" + internal engineering flag raised |

Plus, per workspace type: **live-connected** workspaces keep today's chat + write flow; Dashboard/Insights behaviour for them is open (not synced → no BI data) **(assumed: show "Connect via sync agent to see dashboards")**.

### 8.10 Accessibility
- Top bar = `header`, left menu = `nav` with `aria-label="Main"`, main section = `main` with the page title as its `h1`.
- Active menu item uses `aria-current="page"`. The AI Chat submenu is a disclosure button with `aria-expanded`.
- Company selector and user menu keyboard-operable (arrow keys, Esc closes), matching the existing kebab menu roles.

### 8.11 Testing (per CLAUDE.md rules)
- **Vitest, top-level container:** render the app shell, click each menu item, assert the main section title and content change; switch company in the top bar and assert chat submenu + page data switch; open a chat from the submenu and assert the title shows in the main section, not the top bar. Mock only the HTTP API.
- **Refresh round trip:** on each page, reload → same company, same page, same open chat, submenu state restored (URL-driven).
- **Route redirects:** old `/c/:id` and `/w/:id` links land on the new pages.
- **Sync-state matrix:** each cell in §8.9 has a mock data variant and a test.
- **Playwright:** page × sync state × viewport (mobile/tablet/desktop) screenshots, each with a `// VISUAL CHECKLIST:` block and content assertions first; main agent reviews every PNG. Includes long company name / long chat title truncation and mobile drawer open/closed.
- **Regression:** existing chat, upload → voucher card → write, rename/delete conversation all still work from the AI Chat page.

### 8.12 Assumptions to confirm
1. Top bar selector switches; Settings connects (Q12).
2. Upload → write stays in AI Chat for live-connected workspaces (Q14).
3. Landing page is Dashboard (Q15).
4. Demo toggle and Live/Demo badge move to Settings (Q17).
5. Mobile drawer, tablet icon rail (Q18).
6. Workspace in the URL; old routes redirect.
7. "Sync now" stays in the agent tray only.
8. ~~Insights = AI-generated findings (Q13).~~ Superseded by §6: Insights is a rule-based ranked list of demands / reconciliation / alerts, never AI-invented. Remaining sub-questions: Q13a, Q13b.

## 9. Other open design items
Not designed in the original spec. Only the known requirements are listed; the S5 spec settles them.

1. **Storage for dismissed Insights.** "A dismissed item does not return unless its underlying
   condition changes" (§6) needs a table remembering each dismissed item and enough of its condition
   to tell when it has changed. Part 1's migration 006 has no such table, so this part adds a
   migration 007.
2. **Scoping the integrity ribbon.** "Receivables may be off" means mapping mismatched ledgers and
   groups to the tiles they feed. It must use the same "touches an affected ledger" rule as chat
   (Part 2, "Open design items", item 2), so the ribbon and the chat caveat never disagree.

## 10. Verification (when built, later)
Navigation, routing and page tests are in §8.11.

- **Dashboard definitions:** gross margin uses COGS from stock snapshots and shows "no figure yet" when a boundary snapshot is missing (never sales − purchases); GST position reads only ledgers Tally classifies as GST, excludes tax payments and set-offs, and splits by duty head; the overdue split uses Tally's due dates.
- **Month-end baselines:** a dashboard baseline with no snapshot shows "no month-end figure yet", never zero. The Cash & bank month-end baseline equals current mirrored minus lines after the month-end, and equals chat's answer to the same question. The Cash & bank tile moves in the same cycle as the voucher that changed it.
- **Frontend:** state matrix (connecting / syncing % / error / Tally offline / ready / stale / restore detected / re-link offered × chat lock) with Vitest + Playwright screenshots, including a reload mid-sync.
- **Refresh round-trip** (CLAUDE.md rule 7): act → reload → the Settings card and the dashboard ribbon show the same state, rehydrated from the DB.
- **Playwright:** integrity card × {ok, suspect, alert, hard_alert, never-run} × 3 viewports, each with a `// VISUAL CHECKLIST:` block and content assertions before the screenshot; main agent reviews every PNG.
- **Report/dashboard API:** tests are defined with its design (§5).

## 11. Risks
R24 and R28 live here. The rest are in Part 1 (shared ones included) and Part 2.

| ID | Risk | Likelihood | Impact | Status |
|---|---|---|---|---|
| R24 | Web can't tell agent offline from Tally closed | High | Medium | Open question Q1 |
| R28 | No write flow on synced workspaces | Certain | Medium | **Accepted** for v1 |

**R24: Web can't tell agent offline from Tally closed**
- *What:* skips are quiet and the heartbeat is sent only when connected, so "PC off / agent uninstalled" looks the same as "Tally closed".
- *Handling:* open question Q1 (Part 1).

**R28: No write flow on synced workspaces (accepted)**
- *What:* customers who sync can't use upload → Write to Tally on that workspace in v1.
- *Handling:* a clear UI note (decision 10). Revisit writes after the BI layer.

## 12. Open questions
| # | Question | Linked risk | Options / notes |
|---|---|---|---|
| Q2 | **Before the first sync ever runs:** what does the web show if Tally hasn't been opened since install? | R22 | e.g. locked chat + "Waiting for Tally: open Bharat Traders in TallyPrime" |
| Q3 | **Stale threshold:** after how long is the stale badge shown? | R1 | e.g. >1 hour amber, >24 hours red |
| Q9 | **Tally offline state on web:** full set of UI states and messages | R24 | Decide in S3 spec (see §4 Web states) |
| Q11 | **Where the company is picked:** decision 3 says inside the Windows agent; the new Sync / Settings page "picks up companies automatically". Does the web show the agent's company list and the user picks there, or does the agent pick and the web only display it? | R2 | A: pick in web Settings (agent reports list) · B: pick in agent, web displays · C: both |
| Q12 | **Two company selectors:** is the top bar for **switching** between connected companies and Sync / Settings for **connecting** a new one? | R2 | Assumed yes in §8.5 |
| Q13 | ~~**Dashboard vs Insights**~~ | R25 | **Answered (§6):** Dashboard = **KPIs** (fixed tiles, glanceable); Insights = **demands, reconciliation, alerts** (ranked list of things to act on). Two sub-questions remain: Q13a, Q13b. |
| Q13a | **"Demands" — which meaning?** Collections/dunning (overdue receivables to chase, payables to pay) is the reading assumed in §6. It could instead mean statutory **tax demands** (GST/TDS notices), which we hold no data for. | — | Confirm before S5 |
| Q13b | **"Reconciliation" — internal only?** §6 assumes *internal consistency within the synced books* (party ledger vs open bills, stock ledger vs Stock Summary, unallocated bill-wise vouchers). Bank-statement and GSTR-2B reconciliation both need external data we don't sync and are excluded from v1. | B1d | Confirm the v1 line |
| Q14 | **Upload → Write to Tally:** does the existing write flow stay inside AI Chat, for live-connected workspaces only? | R28 | Assumed yes in §8.4 |
| Q15 | **Landing page:** after login, does the user land on Dashboard or AI Chat? | — | Assumed Dashboard in §8.6 |
| Q16 | **Existing live-connected companies:** keep manual host/port connect (today's `ConnectCompanyModal`) somewhere in Settings, or hide it? | — | |
| Q17 | **Demo mode toggle + Live/Demo badge** (today in `Header.tsx` / `TallyStatusBadge.tsx`): move to Sync / Settings, or remove? | — | Assumed moved to Settings in §8.3 |
| Q18 | **Mobile and tablet:** left menu as a drawer (like today's sidebar)? Collapsed icon rail on tablet? | — | Assumed drawer on mobile in §8.8 |
| Q24 | **What does the web show while history loads?** A progress line in Settings only, or a subtle indicator on Dashboard/Insights too? Chat already answers "still loading" for un-backfilled dates (decision 7b). | R29, Q2 | Decide in S3 spec |

Q2, Q3, Q11, Q12 and Q14–Q17 are product decisions to settle first; Q13a and Q13b before S5. Q9,
Q18 and Q24 can be settled in the S3 spec. Q28 (who can see a synced workspace, Part 1) must be
settled before the S3 spec too.

## 13. Sub-projects
| # | Scope | Depends on |
|---|---|---|
| S3 | Web shell with the new navigation (§8) + onboarding + sync status + **Data integrity card + History card** (§8.4) | S1 (Part 1) |
| S5 | BI dashboards (incl. the integrity ribbon) and the report/dashboard API behind them (§5) | S4 query layer (Part 2) |

## 14. Next step
Brainstorm only so far. When approved: settle Q2, Q3, Q11, Q12, Q14–Q17 (and Q28 in Part 1) → design
the report/dashboard API (§5) and the §9 items → S3 and S5 specs → implementation plans. S3 can start
once S1 (Part 1) is built; S5 needs Part 2's query layer (S4).
