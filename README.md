# TallyPrime AI Agent

AI-powered chatbot that connects to a live TallyPrime instance, lets users ask natural-language questions about accounting data, and replies with answers, charts, and tables.

**Stack:** Python (FastAPI) backend · React (Vite + Tailwind + Recharts) frontend · Claude API (tool-calling) · PostgreSQL (optional, for auth + persistence)

---

## Prerequisites

- **Python 3.12+** with [`uv`](https://docs.astral.sh/uv/) (recommended) or pip
- **Node.js 20+** and npm
- **TallyPrime 7.0+** running with the HTTP/XML server enabled (default `localhost:9000`) — see [Installing TallyPrime on macOS](#installing-tallyprime-on-macos) if you don't already have it
- **Anthropic API key** — get one at <https://console.anthropic.com/>
- **PostgreSQL 14+** *(only if you want auth + persistent conversations; optional)*

> No Tally instance handy? You can run the app in **mock mode** for tests and demos — see [Testing](#testing).

---

## Installing TallyPrime on macOS

TallyPrime is a Windows-only application, but it runs reliably on macOS via [Wine](https://www.winehq.org/). Use the **Edit Log** edition — it exposes the HTTP/XML server this project depends on.

### 1. Install Wine

```bash
brew install --cask --no-quarantine wine-stable
```

### 2. Download TallyPrime 7.0 Edit Log

Get the **TallyPrime Edit Log** installer (version 7.0 or later) from <https://tallysolutions.com/download/>. Save the `.exe` to `~/Downloads`.

### 3. Install under Wine

```bash
cd ~/Downloads
wine TallyPrime_EditLog_Setup.exe   # filename will vary; use the one you downloaded
```

Click through the installer with default options. It installs to `~/.wine/drive_c/Program Files/TallyPrimeEditLog/`.

### 4. Run TallyPrime

```bash
wine ~/.wine/drive_c/Program\ Files/TallyPrimeEditLog/tally.exe
```

### 5. Enable the HTTP/XML server

Inside TallyPrime: **F1 (Help) → Settings → Connectivity → Client/Server configuration** → set *TallyPrime is acting as* to **Both**, *Port* to **9000**. Save and restart Tally.

Verify from the host:

```bash
curl http://localhost:9000   # should return a small XML response
python scripts/test_tally_connection.py
```

---

## Quick start (legacy mode — no auth, in-memory sessions)

This is the fastest way to see the app working end-to-end.

### 1. Clone and configure

```bash
git clone <repo-url>
cd tally_agent
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY (and TALLY_HOST/PORT if Tally isn't on localhost:9000)
```

### 2. Install backend dependencies

```bash
uv sync --extra dev --extra langfuse
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Run it

Open two terminals:

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Visit <http://localhost:5173>.

### 5. (Optional) Verify Tally connectivity

```bash
python scripts/test_tally_connection.py
```

---

## Running with auth + persistence (DB mode)

DB mode adds user accounts, workspaces (one per Tally company), and persistent conversation history. **All new feature work targets DB mode** — legacy mode is frozen.

### 1. Create the database

```bash
createdb tallyagent
createdb tallyagent_test   # for DB integration tests
```

### 2. Configure `.env`

Uncomment and fill in the DB-mode block in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent
JWT_SECRET=<generate-a-random-32+-char-string>
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent_test
```

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Install DB dependencies and run migrations

```bash
uv sync --extra dev --extra langfuse --extra db
PYTHONPATH=. python -m alembic upgrade head
PYTHONPATH=. DATABASE_URL=$TEST_DATABASE_URL python -m alembic upgrade head   # also migrate the test DB
```

### 4. Run with DB mode enabled

```bash
# Terminal 1 — backend (auto-detects DB mode from DATABASE_URL)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend (must opt in to DB mode)
cd frontend
VITE_DB_MODE=true npm run dev
```

Register a user at <http://localhost:5173/register>, then connect a Tally company workspace from the sidebar.

---

## Database migrations (DB mode)

Schema is managed by [Alembic](https://alembic.sqlalchemy.org/). Migration files live in `backend/db/migrations/versions/`. ORM models live in `backend/db/models.py`.

### Apply migrations

```bash
# Upgrade the dev DB to the latest schema
PYTHONPATH=. python -m alembic upgrade head

# Upgrade the test DB too (same migrations, different URL)
PYTHONPATH=. DATABASE_URL=$TEST_DATABASE_URL python -m alembic upgrade head
```

Run `alembic upgrade head` after pulling new commits whenever `backend/db/migrations/versions/` has new files. The backend will refuse to start in DB mode if migrations are out of date.

### Create a new migration

After editing `backend/db/models.py`:

```bash
# Autogenerate from model diff
PYTHONPATH=. python -m alembic revision --autogenerate -m "add foo column to bar"

# Review the generated file in backend/db/migrations/versions/ — autogenerate
# misses things like enum changes and server defaults; edit by hand if needed.

# Apply locally
PYTHONPATH=. python -m alembic upgrade head
```

Conventions:
- File prefix is sequential (`003_`, `004_`, …) — match the existing pattern.
- Always include a working `downgrade()` so rollbacks are possible.
- Don't edit a migration after it has been merged to `master` — write a new one.

### Rollback

```bash
PYTHONPATH=. python -m alembic downgrade -1        # one step back
PYTHONPATH=. python -m alembic downgrade <rev>     # to a specific revision
PYTHONPATH=. python -m alembic history             # see all revisions
PYTHONPATH=. python -m alembic current             # see what's applied
```

### Seed / reference data

The schema does not require any seed data — a fresh DB after `alembic upgrade head` is fully usable. Users register through the UI and create workspaces from there.

To populate **Tally** (not Postgres) with the Bharat Traders sample data used by tests and demos:

```bash
python scripts/seed_tally_data.py --host <TALLY_HOST> --port 9000
```

### Reset a local DB

```bash
dropdb tallyagent && createdb tallyagent
PYTHONPATH=. python -m alembic upgrade head
```

---

## Repository layout

```
backend/
  tally_bridge/    # HTTP client, XML request builder, response parser, Tally queries
  agents/          # Multi-agent system: orchestrator, query, analysis, chart agents
  api/             # FastAPI routes: chat, health, auth, workspaces, conversations
  db/              # SQLAlchemy models + Alembic migrations (DB mode)
  config.py        # pydantic-settings (loads .env)
  main.py          # FastAPI app entry point
frontend/
  src/             # React app (chat UI, sidebar, auth pages)
  tests/           # Vitest unit tests + Playwright visual tests
tests/
  unit/            # Backend unit tests (pure logic, no I/O)
  integration/     # Mock-Tally integration tests (some require Postgres)
  e2e/             # End-to-end with mock Claude (legacy + DB smoke)
  e2e_live/        # End-to-end against real Tally + real Claude (gated)
  eval/            # LLM-as-a-judge eval framework
  fixtures/        # Sample Tally XML/JSON responses
scripts/           # Utilities: connection test, seed data, live agent test
docs/              # Design specs, plans, code reviews
CLAUDE.md          # Detailed engineering guide for AI assistants (also useful for humans)
TALLYPRIME_AGENT_PLAN.md   # Full project spec and phased build order
LESSONS.md         # Hard-won Tally API learnings
```

---

## Testing

> ⚠️ Live and eval tests hit the real Claude API and cost money. Always pipe to a log file with `tee` and never re-run unnecessarily.

### Backend — fast, no external deps

```bash
pytest tests/unit/ -v                                        # 896 unit tests
ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/   # all mock tests
pytest --cov=backend --cov-report=html                       # with coverage
```

### Backend — DB tests (requires Postgres)

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tallyagent_test \
ANTHROPIC_API_KEY=test-key \
pytest tests/integration/test_auth_flow.py \
       tests/integration/test_workspace_flow.py \
       tests/integration/test_conversation_flow.py \
       tests/e2e/test_db_smoke.py -v
```

### Backend — live tests (real Tally + real Claude)

```bash
RUN_LIVE_TESTS=1 PYTHONPATH=. pytest tests/e2e_live/ -v -s \
  --host <TALLY_HOST> --port 9000 2>&1 | tee docs/e2e-live-results.log
```

Or in mock mode (no Tally needed, still uses Claude API):

```bash
PYTHONPATH=. pytest tests/e2e_live/ -v -s --tally-mode mock \
  2>&1 | tee docs/e2e-live-mock-results.log
```

### Frontend

```bash
cd frontend
npm test                     # Vitest unit tests
npm run test:playwright      # Visual tests (backend must be running on :8000)
```

To regenerate Playwright baselines for a single spec only:

```bash
rm -rf tests/playwright/__screenshots__/*/<spec-name>.spec.ts/
npm run test:playwright -- --update-snapshots
```

---

## Useful scripts

```bash
# Verify Tally is reachable
python scripts/test_tally_connection.py

# Seed Bharat Traders test data into a Tally instance
python scripts/seed_tally_data.py --host <TALLY_HOST> --port 9000

# Run the full agent pipeline against a real Tally (needs ANTHROPIC_API_KEY)
PYTHONPATH=. uv run python scripts/test_agent_live.py --host <TALLY_HOST> --port 9000
```

---

## Contributing

1. Read [`CLAUDE.md`](CLAUDE.md) — it's the canonical engineering guide (build commands, conventions, testing rules, DB-mode notes).
2. Read [`LESSONS.md`](LESSONS.md) for non-obvious Tally API gotchas before touching `backend/tally_bridge/` or write paths.
3. New work goes through DB mode. Legacy mode is frozen.
4. Specs and plans live in `docs/specs/` and `docs/plans/`. Code review notes in `docs/code-review-*.md`.
5. Test counts and current architecture status are tracked in `CLAUDE.md`.

---

## Configuration reference

All settings load from `.env` via `pydantic-settings`. See [`.env.example`](.env.example) for the full list. Quick reference:

| Variable | Default | Notes |
|---|---|---|
| `TALLY_HOST` / `TALLY_PORT` | `localhost` / `9000` | Tally HTTP endpoint |
| `ANTHROPIC_API_KEY` | — | Required |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Query + analysis agents |
| `CLAUDE_CLASSIFIER_MODEL` | `claude-haiku-4-5-20251001` | Orchestrator routing |
| `DATABASE_URL` | *(unset)* | Set to enable DB mode |
| `JWT_SECRET` | — | Required when `DATABASE_URL` is set; min 32 chars |
| `VITE_DB_MODE` | *(unset)* | Frontend: set to `true` for auth pages + sidebar |
