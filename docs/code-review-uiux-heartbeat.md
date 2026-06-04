# Code Review — UI/UX nav fixes + OTel streaming fix + Tally heartbeat

**Branch:** `fix/uiux-nav-heartbeat` (base `master`)
**Date:** 2026-06-04
**Plan:** [`docs/plans/2026-06-04-uiux-fixes-otel-heartbeat.md`](plans/2026-06-04-uiux-fixes-otel-heartbeat.md)

## Scope (6 reported issues)
1. Connect-company dialog → two-step (verify Tally, show actual company + friendly name, "Start chat" → new chat). FE + BE.
2. First chat no longer needs a refresh (ChatWindow ref-guard vs optimistic-message clobber). FE.
3. "New Chat" no longer needs a refresh (clear on landing, guarded against mid-send workspace change). FE.
4. Landing on `/` redirects to first workspace so sidebar "+ New Chat" highlights. FE.
5. OTel `KeyError: 'input'` fixed by upgrading `opentelemetry-instrumentation-anthropic` 0.53.0→0.61.0; also declared `python-multipart` as a core dep. BE.
6. Tally heartbeat badge in header (`TallyStatusBadge`, 30s per-workspace poll). FE + BE.

## Commits
- `8478d5a` feat(api): /api/companies + /api/health host/port/mock params (auth + port validation fix folded in)
- `584f834` feat(fe-api): getHealth/getCompanies accept params
- `232c391` feat(fe): two-step connect modal + Start chat wiring
- `8ffc179` + `8747b6b` fix(fe): ChatWindow stale-state fixes + mid-send race guard
- `ca456ff` fix(fe): `/` → first workspace redirect + highlight
- `39dcc28` feat(fe): TallyStatusBadge heartbeat
- `7dde939` fix(obs): otel 0.53→0.61 + python-multipart dep
- `6901297` test(playwright): confirmation + badge states
- `58b7903` polish(fe): clearer connect errors, NaN port guard, sturdier badge tests

## Review process
Per-task two-stage review (spec compliance + code quality) on every task, plus a final holistic seam-level review of the whole branch. Notable findings caught and fixed mid-flight:
- **SSRF / unauthenticated probe** — host/port params let an unauthenticated caller probe arbitrary hosts. Fixed: both endpoints now require `get_current_user`; `port` validated `Query(ge=1, le=65535)` (was a 500 → now 422). (`8478d5a`)
- **Mid-send race** — the new-chat clear branch could wipe optimistic messages if `workspaceId` changed during an in-flight first send. Fixed with a synchronous `sendingRef`. (`8747b6b`)
- **`python-multipart` latent breakage** — never in the lock (manual install only); `uv sync` removed it, which would break `/api/chat/upload`. Now a declared core dep. (`7dde939`)
- **Playwright health route glob** — `**/api/health` didn't match the client's `?host&port` query string, leaving the badge stuck on "Checking…". Fixed to `**/api/health**`.

Final assessment: **Ready to merge.** Only Minor findings remain (one cosmetic `act()` warning in a ChatWindow test; defensive notes on badge default config — cannot trigger today).

## Verification (run 2026-06-04)
| Suite | Result |
|---|---|
| Backend `pytest tests/ --ignore=e2e_live` | **1134 passed, 41 skipped** (`logs/be_final_verify.log`) |
| Frontend Vitest | **250 passed** (22 files) |
| `npx tsc --noEmit` (project gate) | **clean** |
| Playwright db-mode (×3 viewports) | **61 passed, 11 skipped**; new/changed PNGs visually inspected by main agent across mobile/tablet/desktop |

## NOT run (require external resources)
- **`e2e_live`** — needs a real Tally instance.
- **Manual live smoke** — connect to a real Tally, watch the otel traceback disappear during an AnalysisAgent streaming query, confirm the Langfuse generation appears. Needs the user's Tally + Langfuse env. The otel fix is verified by reading the installed 0.61.0 source (guarded `event.get("input", "")` + bounds check) and the full backend suite passing on the upgraded deps.
- **Eval (`collect/judge/report`)** — real Claude API; deferred to the end-of-everything eval pass. (Eval still covers query flow only; write-flow eval remains a gap.)
- **`npm run build` (`tsc -b`)** — broken on `master` pre-existing (unrelated stricter tsconfig with test files + recharts/chart typing errors). Not a regression from this branch. Parked.
