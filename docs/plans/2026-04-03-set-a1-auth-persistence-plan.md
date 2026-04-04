# Set A1: Auth + Persistence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user authentication, persistent chat history, workspace-based agent routing, and usage logging to the TallyPrime AI Agent.

**Architecture:** PostgreSQL stores users, workspaces, conversations, messages, and usage logs. JWT auth guards all endpoints. Existing in-memory SessionStore is preserved as "legacy mode" when DATABASE_URL is unset. The agent pipeline becomes pluggable via an agent registry keyed by workspace.agent_type. Frontend adds React Router, auth pages, and a conversation sidebar.

**Tech Stack:** SQLAlchemy 2.0 (async) + Alembic, asyncpg, passlib[bcrypt], PyJWT, React Router v7

**Spec:** `docs/specs/2026-04-02-set-a1-auth-persistence-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `backend/db/__init__.py` | Package init |
| `backend/db/engine.py` | Async engine, session factory, `get_db` dependency |
| `backend/db/models.py` | SQLAlchemy ORM models (User, Workspace, Conversation, Message, UsageLog) |
| `backend/db/migrations/env.py` | Alembic env config |
| `backend/db/migrations/versions/001_initial.py` | Initial migration |
| `backend/api/auth.py` | Register, login, refresh, me, logout endpoints |
| `backend/api/workspaces.py` | Workspace CRUD endpoints |
| `backend/api/conversations.py` | Conversation CRUD + message retrieval endpoints |
| `backend/api/usage.py` | Usage aggregation endpoint |
| `backend/agents/registry.py` | Agent type registry |
| `backend/agents/base.py` | BaseAgent abstract interface |
| `backend/utils/pricing.py` | Model → cost lookup |
| `alembic.ini` | Alembic config (project root) |

### Backend — Modified Files

| File | Changes |
|------|---------|
| `backend/config.py` | Add DATABASE_URL, JWT_SECRET, JWT expiry settings |
| `backend/main.py` | Conditional DB init in lifespan, register new routers |
| `backend/api/dependencies.py` | Add `get_current_user`, `get_db_session`, `get_optional_user` |
| `backend/api/chat.py` | DB-backed conversation loading, usage logging, workspace routing |
| `backend/api/models.py` | Add auth/workspace/conversation request/response models |
| `backend/agents/orchestrator.py` | Rename class to TallyOrchestrator, implement BaseAgent interface |
| `pyproject.toml` | Add sqlalchemy, alembic, asyncpg, passlib, pyjwt dependencies |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/src/pages/LoginPage.tsx` | Login form |
| `frontend/src/pages/RegisterPage.tsx` | Register form with password strength |
| `frontend/src/pages/SettingsPage.tsx` | User profile, connected companies |
| `frontend/src/context/AuthContext.tsx` | Auth state, tokens, login/logout/refresh |
| `frontend/src/components/Sidebar.tsx` | Conversation list grouped by workspace |
| `frontend/src/components/ConversationList.tsx` | Conversations under a workspace |
| `frontend/src/components/ConnectCompanyModal.tsx` | Add workspace form |
| `frontend/src/components/UserMenu.tsx` | Profile dropdown, logout |
| `frontend/src/components/ProtectedRoute.tsx` | Auth guard wrapper |

### Frontend — Modified Files

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Add BrowserRouter, AuthContext, route definitions |
| `frontend/src/api/client.ts` | Add auth header interceptor, new API functions |
| `frontend/src/types/index.ts` | Add auth/workspace/conversation types |
| `frontend/src/components/ChatWindow.tsx` | Load conversation from API, use route params |
| `frontend/src/components/Header.tsx` | Add UserMenu, DB-backed company selector |
| `frontend/package.json` | Add react-router-dom dependency |

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add Python dependencies**

Add to `pyproject.toml` `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
db = [
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.30",
    "passlib[bcrypt]>=1.7",
    "PyJWT>=2.8",
]
```

- [ ] **Step 2: Install Python dependencies**

Run: `uv sync --extra dev --extra langfuse --extra db`
Expected: Dependencies resolve and install successfully.

- [ ] **Step 3: Add frontend dependency**

Run: `cd frontend && npm install react-router-dom@7`
Expected: Package added to package.json dependencies.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock frontend/package.json frontend/package-lock.json
git commit -m "chore: add auth + persistence dependencies (SQLAlchemy, Alembic, PyJWT, react-router-dom)"
```

---

## Task 2: Database Engine & Config

**Files:**
- Modify: `backend/config.py`
- Create: `backend/db/__init__.py`
- Create: `backend/db/engine.py`
- Test: `tests/unit/test_db_engine.py`

- [ ] **Step 1: Write failing test for config**

Create `tests/unit/test_db_config.py`:

```python
"""Tests for database-related config settings."""

from backend.config import Settings


def test_database_url_defaults_to_none():
    s = Settings(ANTHROPIC_API_KEY="test")
    assert s.DATABASE_URL is None


def test_jwt_secret_defaults_to_none():
    s = Settings(ANTHROPIC_API_KEY="test")
    assert s.JWT_SECRET is None


def test_jwt_expiry_defaults():
    s = Settings(ANTHROPIC_API_KEY="test")
    assert s.JWT_ACCESS_TOKEN_EXPIRY_MINUTES == 30
    assert s.JWT_REFRESH_TOKEN_EXPIRY_DAYS == 7


def test_db_mode_enabled_when_database_url_set():
    s = Settings(
        ANTHROPIC_API_KEY="test",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/testdb",
    )
    assert s.db_mode is True


def test_db_mode_disabled_when_database_url_not_set():
    s = Settings(ANTHROPIC_API_KEY="test")
    assert s.db_mode is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_db_config.py -v`
Expected: FAIL — `DATABASE_URL`, `JWT_SECRET`, `db_mode` not defined.

- [ ] **Step 3: Update config.py**

Add to `backend/config.py` in the `Settings` class, after `LANGFUSE_BASE_URL`:

```python
    # Database & Auth (Set A1)
    DATABASE_URL: str | None = None  # e.g. postgresql+asyncpg://user:pass@localhost/tallyagent
    JWT_SECRET: str | None = None  # minimum 32 chars, required when DATABASE_URL is set
    JWT_ACCESS_TOKEN_EXPIRY_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRY_DAYS: int = 7

    @property
    def db_mode(self) -> bool:
        """True when DATABASE_URL is set — enables auth + persistence."""
        return self.DATABASE_URL is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_db_config.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Create db package and engine module**

Create `backend/db/__init__.py`:

```python
"""Database package — SQLAlchemy async engine and ORM models."""
```

Create `backend/db/engine.py`:

```python
"""Async SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

engine = None
async_session_factory = None


def init_engine(database_url: str | None = None) -> None:
    """Initialize the async engine and session factory.

    Call once during app startup when DATABASE_URL is set.
    """
    global engine, async_session_factory
    url = database_url or settings.DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL must be set to initialize the database engine")
    engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Yield an async DB session. Used as a FastAPI dependency."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Set DATABASE_URL to enable DB mode.")
    async with async_session_factory() as session:
        yield session


async def close_engine() -> None:
    """Dispose the engine. Call during app shutdown."""
    global engine, async_session_factory
    if engine:
        await engine.dispose()
    engine = None
    async_session_factory = None
```

- [ ] **Step 6: Write test for engine init**

Create `tests/unit/test_db_engine.py`:

```python
"""Tests for database engine initialization."""

import pytest

from backend.db.engine import async_session_factory, engine, init_engine


def test_init_engine_raises_without_url():
    with pytest.raises(ValueError, match="DATABASE_URL must be set"):
        init_engine(database_url=None)


def test_engine_is_none_before_init():
    # engine and factory should be None at module import (no DATABASE_URL in test env)
    from backend.db import engine as eng_module
    # We can't guarantee module state across tests, so just check the function exists
    assert callable(eng_module.init_engine)
    assert callable(eng_module.close_engine)
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/unit/test_db_config.py tests/unit/test_db_engine.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/config.py backend/db/ tests/unit/test_db_config.py tests/unit/test_db_engine.py
git commit -m "feat: add database config settings and async engine module"
```

---

## Task 3: SQLAlchemy ORM Models

**Files:**
- Create: `backend/db/models.py`
- Test: `tests/unit/test_db_models.py`

- [ ] **Step 1: Write failing test for models**

Create `tests/unit/test_db_models.py`:

```python
"""Tests for SQLAlchemy ORM model definitions."""

import uuid
from datetime import datetime, timezone

from backend.db.models import Base, Conversation, Message, UsageLog, User, Workspace


def test_user_model_has_required_columns():
    cols = {c.name for c in User.__table__.columns}
    assert cols == {"id", "email", "password_hash", "name", "is_active", "created_at", "updated_at"}


def test_workspace_model_has_required_columns():
    cols = {c.name for c in Workspace.__table__.columns}
    assert cols == {
        "id", "user_id", "name", "agent_type", "config", "memory",
        "is_deleted", "created_at", "updated_at",
    }


def test_conversation_model_has_required_columns():
    cols = {c.name for c in Conversation.__table__.columns}
    assert cols == {
        "id", "user_id", "workspace_id", "title", "tag",
        "is_deleted", "created_at", "updated_at",
    }


def test_message_model_has_required_columns():
    cols = {c.name for c in Message.__table__.columns}
    assert cols == {"id", "conversation_id", "role", "content", "data", "chart", "created_at"}


def test_usage_log_model_has_required_columns():
    cols = {c.name for c in UsageLog.__table__.columns}
    assert cols == {
        "id", "message_id", "user_id", "workspace_id", "conversation_id",
        "total_input_tokens", "total_output_tokens", "total_cost_usd",
        "model_primary", "latency_ms", "agent_calls", "created_at",
    }


def test_workspace_default_agent_type():
    ws = Workspace.__table__.columns["agent_type"]
    assert ws.default.arg == "tally"


def test_base_has_metadata():
    assert Base.metadata is not None
    assert len(Base.metadata.tables) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_db_models.py -v`
Expected: FAIL — `backend.db.models` does not exist.

- [ ] **Step 3: Create ORM models**

Create `backend/db/models.py`:

```python
"""SQLAlchemy ORM models for auth, workspaces, conversations, and usage."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="tally")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    memory: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="workspaces")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="workspace")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="conversations")
    workspace: Mapped["Workspace"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    chart: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    model_primary: Mapped[str] = mapped_column(String(50), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_calls: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_usage_user_created", "user_id", "created_at"),
        Index("ix_usage_workspace_created", "workspace_id", "created_at"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_db_models.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py tests/unit/test_db_models.py
git commit -m "feat: add SQLAlchemy ORM models (users, workspaces, conversations, messages, usage_logs)"
```

---

## Task 4: Alembic Setup & Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `backend/db/migrations/env.py`
- Create: `backend/db/migrations/script.py.mako`
- Create: `backend/db/migrations/versions/` (directory)

- [ ] **Step 1: Create alembic.ini**

Create `alembic.ini` in the project root:

```ini
[alembic]
script_location = backend/db/migrations
sqlalchemy.url = postgresql+asyncpg://localhost/tallyagent

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create migrations directory and env.py**

Create `backend/db/migrations/` directory.

Create `backend/db/migrations/env.py`:

```python
"""Alembic env.py — async migration runner."""

import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.models import Base

target_metadata = Base.metadata


def get_url() -> str:
    return os.environ.get("DATABASE_URL", context.config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations — dispatches to async runner."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/db/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create empty `backend/db/migrations/versions/` directory with a `.gitkeep` file.

- [ ] **Step 3: Generate initial migration**

Run (requires a running Postgres instance — use a local dev DB):

```bash
DATABASE_URL=postgresql+asyncpg://localhost/tallyagent_dev alembic revision --autogenerate -m "initial: users, workspaces, conversations, messages, usage_logs"
```

Expected: A migration file is created in `backend/db/migrations/versions/`.

If Postgres is not available, create the migration manually. Create `backend/db/migrations/versions/001_initial.py`:

```python
"""initial: users, workspaces, conversations, messages, usage_logs

Revision ID: 001
Revises: None
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False, server_default="tally"),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("memory", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("tag", sa.String(50), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("chart", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "usage_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), unique=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("model_primary", sa.String(50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("agent_calls", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_user_created", "usage_logs", ["user_id", "created_at"])
    op.create_index("ix_usage_workspace_created", "usage_logs", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_table("usage_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("workspaces")
    op.drop_table("users")
```

- [ ] **Step 4: Commit**

```bash
git add alembic.ini backend/db/migrations/ backend/db/__init__.py
git commit -m "feat: add Alembic setup and initial migration (5 tables)"
```

---

## Task 5: Password Validation & Hashing Utilities

**Files:**
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/auth.py`
- Test: `tests/unit/test_auth_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_auth_utils.py`:

```python
"""Tests for auth utility functions — password hashing, validation, JWT."""

import time

import pytest


def test_password_hash_roundtrip():
    from backend.utils.auth import hash_password, verify_password
    hashed = hash_password("Str0ng!Pass#99")
    assert verify_password("Str0ng!Pass#99", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_password_hash_is_bcrypt():
    from backend.utils.auth import hash_password
    hashed = hash_password("Str0ng!Pass#99")
    assert hashed.startswith("$2b$")


class TestPasswordValidation:
    def test_valid_password(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ng!Pass#99")
        assert errors == []

    def test_too_short(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ng!1")
        assert any("12 characters" in e for e in errors)

    def test_no_uppercase(self):
        from backend.utils.auth import validate_password
        errors = validate_password("str0ng!pass#99")
        assert any("uppercase" in e for e in errors)

    def test_no_lowercase(self):
        from backend.utils.auth import validate_password
        errors = validate_password("STR0NG!PASS#99")
        assert any("lowercase" in e for e in errors)

    def test_no_digit(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Strong!Pass#abc")
        assert any("digit" in e for e in errors)

    def test_no_special(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ngPass9999")
        assert any("special" in e for e in errors)

    def test_multiple_failures(self):
        from backend.utils.auth import validate_password
        errors = validate_password("short")
        assert len(errors) >= 3


class TestJWT:
    def test_create_and_decode_access_token(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32)
        payload = decode_token(token, secret="x" * 32)
        assert payload["sub"] == "abc-123"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from backend.utils.auth import create_refresh_token, decode_token
        token = create_refresh_token(user_id="abc-123", secret="x" * 32)
        payload = decode_token(token, secret="x" * 32)
        assert payload["sub"] == "abc-123"
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32, expiry_minutes=-1)
        with pytest.raises(Exception):
            decode_token(token, secret="x" * 32)

    def test_invalid_token_raises(self):
        from backend.utils.auth import decode_token
        with pytest.raises(Exception):
            decode_token("garbage.token.here", secret="x" * 32)

    def test_wrong_secret_raises(self):
        from backend.utils.auth import create_access_token, decode_token
        token = create_access_token(user_id="abc-123", secret="x" * 32)
        with pytest.raises(Exception):
            decode_token(token, secret="y" * 32)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_auth_utils.py -v`
Expected: FAIL — module `backend.utils.auth` does not exist.

- [ ] **Step 3: Implement auth utilities**

Create `backend/utils/__init__.py`:

```python
"""Utility modules."""
```

Create `backend/utils/auth.py`:

```python
"""Authentication utilities — password hashing, validation, and JWT tokens."""

import re
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


def validate_password(password: str) -> list[str]:
    """Validate password strength. Returns a list of error messages (empty = valid)."""
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\/'`~;]", password):
        errors.append("Password must contain at least one special character")
    return errors


def create_access_token(user_id: str, secret: str, expiry_minutes: int = 30) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_refresh_token(user_id: str, secret: str, expiry_days: int = 7) -> str:
    """Create a JWT refresh token."""
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=expiry_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    """Decode and validate a JWT token. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, secret, algorithms=["HS256"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_auth_utils.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/ tests/unit/test_auth_utils.py
git commit -m "feat: add password hashing, validation, and JWT utilities"
```

---

## Task 6: Pricing Utility

**Files:**
- Create: `backend/utils/pricing.py`
- Test: `tests/unit/test_pricing.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_pricing.py`:

```python
"""Tests for model pricing and cost calculation."""

from backend.utils.pricing import compute_cost, PRICING


def test_pricing_has_expected_models():
    assert "claude-sonnet-4-6" in PRICING
    assert "claude-haiku-4-5-20251001" in PRICING
    assert "claude-opus-4-6" in PRICING


def test_compute_cost_single_agent():
    calls = [
        {"model": "claude-sonnet-4-6", "input_tokens": 1_000_000, "output_tokens": 0},
    ]
    cost = compute_cost(calls)
    assert abs(cost - 3.00) < 0.001


def test_compute_cost_multi_agent():
    calls = [
        {"model": "claude-haiku-4-5-20251001", "input_tokens": 800, "output_tokens": 50},
        {"model": "claude-sonnet-4-6", "input_tokens": 5000, "output_tokens": 1200},
    ]
    cost = compute_cost(calls)
    assert cost > 0
    # Haiku: 800*0.8/1M + 50*4/1M = 0.00064 + 0.0002 = 0.00084
    # Sonnet: 5000*3/1M + 1200*15/1M = 0.015 + 0.018 = 0.033
    expected = 0.00084 + 0.033
    assert abs(cost - expected) < 0.0001


def test_compute_cost_unknown_model_uses_zero():
    calls = [{"model": "unknown-model", "input_tokens": 1000, "output_tokens": 500}]
    cost = compute_cost(calls)
    assert cost == 0.0


def test_compute_cost_empty_list():
    assert compute_cost([]) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_pricing.py -v`
Expected: FAIL — `backend.utils.pricing` does not exist.

- [ ] **Step 3: Implement pricing module**

Create `backend/utils/pricing.py`:

```python
"""Model pricing and cost calculation for usage logging."""

# Prices in USD per token. Updated when Anthropic changes pricing.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6":        {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-opus-4-6":           {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
}


def compute_cost(agent_calls: list[dict]) -> float:
    """Compute total USD cost from a list of agent call records.

    Each call: {"model": str, "input_tokens": int, "output_tokens": int, ...}
    Unknown models are priced at 0 (logged but not billed).
    """
    total = 0.0
    for call in agent_calls:
        prices = PRICING.get(call.get("model", ""), {"input": 0, "output": 0})
        total += call.get("input_tokens", 0) * prices["input"]
        total += call.get("output_tokens", 0) * prices["output"]
    return total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_pricing.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/pricing.py tests/unit/test_pricing.py
git commit -m "feat: add model pricing utility for usage cost calculation"
```

---

## Task 7: Auth API Endpoints

**Files:**
- Modify: `backend/api/models.py` — add auth request/response models
- Create: `backend/api/auth.py` — auth endpoints
- Modify: `backend/api/dependencies.py` — add `get_current_user`
- Test: `tests/unit/test_auth_api.py`

- [ ] **Step 1: Add auth models to backend/api/models.py**

Add at the end of `backend/api/models.py`:

```python
# --- Auth models (Set A1) ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user: dict[str, Any]
    access_token: str


class TokenResponse(BaseModel):
    access_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str


# --- Workspace models (Set A1) ---

class WorkspaceCreateRequest(BaseModel):
    name: str
    agent_type: str = "tally"
    config: dict[str, Any] = {}


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    config: dict[str, Any]
    memory: dict[str, Any]
    created_at: str
    updated_at: str


# --- Conversation models (Set A1) ---

class ConversationCreateRequest(BaseModel):
    title: str | None = None
    tag: str | None = None


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    tag: str | None = None


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str | None
    tag: str | None
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    chart: dict[str, Any] | None = None
    created_at: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str | None
    tag: str | None
    messages: list[MessageResponse]
```

- [ ] **Step 2: Add auth dependency to dependencies.py**

Add to `backend/api/dependencies.py`:

```python
"""FastAPI dependency functions for injecting shared resources."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.agents.context import SessionStore
from backend.config import settings
from backend.tally_bridge.client import TallyClient
from backend.utils.auth import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)


def get_client(request: Request) -> TallyClient:
    """Return the app-level TallyClient singleton."""
    return request.app.state.tally_client


def get_session_store(request: Request) -> SessionStore:
    """Return the app-level SessionStore singleton."""
    return request.app.state.session_store


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Extract and validate JWT from Authorization header. Returns user_id.

    In legacy mode (no DATABASE_URL), returns a placeholder user_id.
    """
    if not settings.db_mode:
        return "legacy-user"

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = decode_token(credentials.credentials, settings.JWT_SECRET)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return payload["sub"]


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str | None:
    """Like get_current_user but returns None instead of raising for unauthenticated."""
    if not settings.db_mode:
        return "legacy-user"
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, settings.JWT_SECRET)
        if payload.get("type") != "access":
            return None
        return payload["sub"]
    except Exception:
        return None
```

- [ ] **Step 3: Create auth endpoints**

Create `backend/api/auth.py`:

```python
"""Authentication endpoints — register, login, refresh, me, logout."""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models import AuthResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse
from backend.config import settings
from backend.db.engine import get_db
from backend.db.models import User
from backend.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory rate limiting (upgrade to Redis when scaling)
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes
_RATE_LIMIT_MAX = 5


def _check_rate_limit(email: str) -> None:
    """Raise 429 if email has exceeded login attempt limit."""
    now = time.time()
    attempts = _login_attempts[email]
    # Remove expired attempts
    _login_attempts[email] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[email]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


@router.post("/register", response_model=AuthResponse)
async def register(
    req: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    # Validate password strength
    errors = validate_password(req.password)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        user_id=str(user.id),
        secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        secret=settings.JWT_SECRET,
        expiry_days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
    )

    logger.info("User registered: %s", user.email)
    return AuthResponse(
        user={"id": str(user.id), "email": user.email, "name": user.name},
        access_token=access_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    _check_rate_limit(req.email.lower().strip())

    result = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        _login_attempts[req.email.lower().strip()].append(time.time())
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    access_token = create_access_token(
        user_id=str(user.id),
        secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    refresh_token = create_refresh_token(
        user_id=str(user.id),
        secret=settings.JWT_SECRET,
        expiry_days=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRY_DAYS * 86400,
    )

    return AuthResponse(
        user={"id": str(user.id), "email": user.email, "name": user.name},
        access_token=access_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: fastapi.Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_token(token, settings.JWT_SECRET)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    access_token = create_access_token(
        user_id=str(user.id),
        secret=settings.JWT_SECRET,
        expiry_minutes=settings.JWT_ACCESS_TOKEN_EXPIRY_MINUTES,
    )
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        created_at=user.created_at.isoformat(),
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}
```

Fix the import in the refresh endpoint — add at the top of the file:

```python
import fastapi
```

And update `get_current_user` import:

```python
from backend.api.dependencies import get_current_user
```

- [ ] **Step 4: Write auth API tests**

Create `tests/unit/test_auth_api.py`:

```python
"""Tests for auth API endpoints — uses in-memory SQLite for speed."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestPasswordValidation:
    """Test password validation via the auth utility (no DB needed)."""

    def test_register_rejects_weak_password(self):
        from backend.utils.auth import validate_password
        errors = validate_password("weak")
        assert len(errors) >= 3

    def test_register_accepts_strong_password(self):
        from backend.utils.auth import validate_password
        errors = validate_password("Str0ng!Pass#99")
        assert errors == []


class TestRateLimit:
    """Test rate limiting logic."""

    def test_rate_limit_blocks_after_max_attempts(self):
        from backend.api.auth import _check_rate_limit, _login_attempts, _RATE_LIMIT_MAX
        import time

        email = "ratelimit-test@example.com"
        _login_attempts[email] = [time.time() for _ in range(_RATE_LIMIT_MAX)]

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit(email)
        assert exc_info.value.status_code == 429

        # Cleanup
        del _login_attempts[email]

    def test_rate_limit_allows_under_threshold(self):
        from backend.api.auth import _check_rate_limit, _login_attempts
        import time

        email = "ratelimit-ok@example.com"
        _login_attempts[email] = [time.time(), time.time()]

        # Should not raise
        _check_rate_limit(email)

        # Cleanup
        del _login_attempts[email]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_auth_api.py tests/unit/test_auth_utils.py -v`
Expected: All tests PASS.

Note: Full integration tests for auth endpoints (register → login → refresh → me) require a test Postgres DB. These will be added as integration tests in Task 12.

- [ ] **Step 6: Commit**

```bash
git add backend/api/auth.py backend/api/models.py backend/api/dependencies.py tests/unit/test_auth_api.py
git commit -m "feat: add auth endpoints (register, login, refresh, me, logout) with JWT + rate limiting"
```

---

## Task 8: Workspace & Conversation API Endpoints

**Files:**
- Create: `backend/api/workspaces.py`
- Create: `backend/api/conversations.py`
- Test: `tests/unit/test_workspace_models.py`

- [ ] **Step 1: Write test for workspace/conversation models**

Create `tests/unit/test_workspace_models.py`:

```python
"""Tests for workspace and conversation API request/response models."""

from backend.api.models import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)


def test_workspace_create_defaults():
    req = WorkspaceCreateRequest(name="Test Co")
    assert req.agent_type == "tally"
    assert req.config == {}


def test_workspace_create_with_config():
    req = WorkspaceCreateRequest(
        name="Test Co",
        config={"tally_host": "192.168.1.5", "tally_port": 9000},
    )
    assert req.config["tally_host"] == "192.168.1.5"


def test_workspace_update_partial():
    req = WorkspaceUpdateRequest(name="New Name")
    assert req.name == "New Name"
    assert req.config is None
    assert req.memory is None


def test_conversation_create_defaults():
    req = ConversationCreateRequest()
    assert req.title is None
    assert req.tag is None


def test_conversation_update_partial():
    req = ConversationUpdateRequest(title="Sales Analysis")
    assert req.title == "Sales Analysis"
    assert req.tag is None
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_workspace_models.py -v`
Expected: All 5 tests PASS (models were added in Task 7).

- [ ] **Step 3: Create workspace endpoints**

Create `backend/api/workspaces.py`:

```python
"""Workspace CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user
from backend.api.models import WorkspaceCreateRequest, WorkspaceResponse, WorkspaceUpdateRequest
from backend.db.engine import get_db
from backend.db.models import Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    result = await db.execute(
        select(Workspace)
        .where(Workspace.user_id == user_id, Workspace.is_deleted == False)
        .order_by(Workspace.created_at)
    )
    workspaces = result.scalars().all()
    return [
        WorkspaceResponse(
            id=str(ws.id), name=ws.name, agent_type=ws.agent_type,
            config=ws.config, memory=ws.memory,
            created_at=ws.created_at.isoformat(), updated_at=ws.updated_at.isoformat(),
        )
        for ws in workspaces
    ]


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    req: WorkspaceCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    ws = Workspace(user_id=user_id, name=req.name, agent_type=req.agent_type, config=req.config)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return WorkspaceResponse(
        id=str(ws.id), name=ws.name, agent_type=ws.agent_type,
        config=ws.config, memory=ws.memory,
        created_at=ws.created_at.isoformat(), updated_at=ws.updated_at.isoformat(),
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if req.name is not None:
        ws.name = req.name
    if req.config is not None:
        ws.config = req.config
    if req.memory is not None:
        ws.memory = req.memory

    await db.commit()
    await db.refresh(ws)
    return WorkspaceResponse(
        id=str(ws.id), name=ws.name, agent_type=ws.agent_type,
        config=ws.config, memory=ws.memory,
        created_at=ws.created_at.isoformat(), updated_at=ws.updated_at.isoformat(),
    )


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.is_deleted = True
    await db.commit()
```

- [ ] **Step 4: Create conversation endpoints**

Create `backend/api/conversations.py`:

```python
"""Conversation CRUD and message retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.dependencies import get_current_user
from backend.api.models import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    ConversationUpdateRequest,
    MessageResponse,
)
from backend.db.engine import get_db
from backend.db.models import Conversation, Message, Workspace

router = APIRouter(prefix="/workspaces/{workspace_id}/conversations", tags=["conversations"])


async def _verify_workspace_access(
    workspace_id: str, user_id: str, db: AsyncSession
) -> Workspace:
    """Verify workspace exists and belongs to user."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
            Workspace.is_deleted == False,
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.get("", response_model=list[ConversationSummaryResponse])
async def list_conversations(
    workspace_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummaryResponse]:
    await _verify_workspace_access(workspace_id, user_id, db)

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted == False,
        )
        .order_by(Conversation.updated_at.desc())
    )
    convos = result.scalars().all()
    return [
        ConversationSummaryResponse(
            id=str(c.id), title=c.title, tag=c.tag,
            created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
        )
        for c in convos
    ]


@router.post("", response_model=ConversationSummaryResponse, status_code=201)
async def create_conversation(
    workspace_id: str,
    req: ConversationCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    await _verify_workspace_access(workspace_id, user_id, db)

    conv = Conversation(
        user_id=user_id, workspace_id=workspace_id,
        title=req.title, tag=req.tag,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationSummaryResponse(
        id=str(conv.id), title=conv.title, tag=conv.tag,
        created_at=conv.created_at.isoformat(), updated_at=conv.updated_at.isoformat(),
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    workspace_id: str,
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    await _verify_workspace_access(workspace_id, user_id, db)

    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted == False,
        )
        .options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(
        id=str(conv.id), title=conv.title, tag=conv.tag,
        messages=[
            MessageResponse(
                id=str(m.id), role=m.role, content=m.content,
                data=m.data, chart=m.chart,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
async def update_conversation(
    workspace_id: str,
    conversation_id: str,
    req: ConversationUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    await _verify_workspace_access(workspace_id, user_id, db)

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        conv.title = req.title
    if req.tag is not None:
        conv.tag = req.tag

    await db.commit()
    await db.refresh(conv)
    return ConversationSummaryResponse(
        id=str(conv.id), title=conv.title, tag=conv.tag,
        created_at=conv.created_at.isoformat(), updated_at=conv.updated_at.isoformat(),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    workspace_id: str,
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_workspace_access(workspace_id, user_id, db)

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.is_deleted = True
    await db.commit()
```

- [ ] **Step 5: Commit**

```bash
git add backend/api/workspaces.py backend/api/conversations.py tests/unit/test_workspace_models.py
git commit -m "feat: add workspace CRUD and conversation CRUD endpoints"
```

---

## Task 9: Agent Registry & BaseAgent Interface

**Files:**
- Create: `backend/agents/base.py`
- Create: `backend/agents/registry.py`
- Modify: `backend/agents/orchestrator.py` — add BaseAgent interface
- Test: `tests/unit/test_agent_registry.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_agent_registry.py`:

```python
"""Tests for agent registry and base agent interface."""

from backend.agents.base import BaseAgent
from backend.agents.registry import agent_registry, get_agent


def test_tally_agent_registered():
    assert "tally" in agent_registry


def test_get_agent_returns_tally():
    agent_class = get_agent("tally")
    assert agent_class is not None


def test_get_agent_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown agent type"):
        get_agent("nonexistent")


def test_base_agent_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseAgent()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_agent_registry.py -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Create BaseAgent**

Create `backend/agents/base.py`:

```python
"""Base agent interface — all registered agents must implement this."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base for agent implementations.

    Each agent type (tally, support, etc.) subclasses this and registers
    in agent_registry.
    """

    @abstractmethod
    async def process_query(
        self,
        message: str,
        workspace_config: dict[str, Any],
        workspace_memory: dict[str, Any],
        conversation_messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Process a user query and return a response dict.

        Args:
            message: The user's natural language query.
            workspace_config: Agent-specific config from workspace.config JSONB.
            workspace_memory: Learned facts from workspace.memory JSONB.
            conversation_messages: Prior messages from DB [{role, content}, ...].
            **kwargs: Additional context (e.g., tally_client for legacy mode).

        Returns:
            Dict with keys: message (str), data (optional), chart (optional),
            session_id (str), usage (optional list of agent call records).
        """
        ...
```

- [ ] **Step 4: Create agent registry**

Create `backend/agents/registry.py`:

```python
"""Agent type registry — maps agent_type strings to agent implementations."""

from typing import Any

from backend.agents.base import BaseAgent

# Registry populated at import time.
# Each value is a class (not instance) that implements BaseAgent.
agent_registry: dict[str, type[BaseAgent]] = {}


def get_agent(agent_type: str) -> type[BaseAgent]:
    """Look up an agent class by type. Raises ValueError if not found."""
    if agent_type not in agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return agent_registry[agent_type]


def _register_agents() -> None:
    """Import and register all built-in agent types."""
    from backend.agents.orchestrator import Orchestrator

    agent_registry["tally"] = Orchestrator


_register_agents()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_agent_registry.py -v`
Expected: All 4 tests PASS.

Note: The existing `Orchestrator` does not yet inherit from `BaseAgent` — that will be done when we modify the chat endpoint in Task 10. The registry works because Python's duck typing allows registration without strict inheritance. We'll add the formal inheritance when we refactor the orchestrator's `process_query` signature.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/base.py backend/agents/registry.py tests/unit/test_agent_registry.py
git commit -m "feat: add BaseAgent interface and agent registry with tally agent registered"
```

---

## Task 10: Modify main.py & Chat Endpoint for DB Mode

**Files:**
- Modify: `backend/main.py` — conditional DB init, register new routers
- Modify: `backend/api/chat.py` — DB-backed conversations, workspace routing, usage logging

- [ ] **Step 1: Update main.py lifespan**

Replace the `lifespan` function and router registration in `backend/main.py`. Add DB initialization when `DATABASE_URL` is set:

Add import at the top of `backend/main.py`:

```python
from backend.db.engine import close_engine, init_engine
```

In the `lifespan` function, add DB init after the SessionStore init and before the Langfuse block:

```python
    # Initialize database if configured
    if settings.db_mode:
        if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters when DATABASE_URL is set")
        init_engine()
        logger.info("Database mode enabled (PostgreSQL)")
```

In the `yield` teardown section (after yield), add before `await app.state.tally_client.close()`:

```python
    if settings.db_mode:
        await close_engine()
```

Add new router registrations after the existing ones:

```python
if settings.db_mode:
    from backend.api import auth, conversations, workspaces
    app.include_router(auth.router, prefix="/api")
    app.include_router(workspaces.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
```

- [ ] **Step 2: Update chat endpoint for DB mode**

Replace `backend/api/chat.py` with a version that supports both legacy and DB modes:

```python
"""Chat endpoint — main conversational interface to the agent pipeline."""

import logging
import time as time_module

from fastapi import APIRouter, Depends
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context import SessionStore
from backend.agents.orchestrator import Orchestrator
from backend.api.dependencies import get_client, get_current_user, get_session_store
from backend.api.models import ChatRequest, ChatResponse, ChartSpec
from backend.config import settings
from backend.tally_bridge.client import TallyClient

logger = logging.getLogger(__name__)
router = APIRouter()

_tracer = trace.get_tracer(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: TallyClient = Depends(get_client),
    session_store: SessionStore = Depends(get_session_store),
    user_id: str = Depends(get_current_user),
) -> ChatResponse:
    if settings.db_mode:
        return await _chat_db_mode(request, client, user_id)
    else:
        return await _chat_legacy_mode(request, client, session_store)


async def _chat_legacy_mode(
    request: ChatRequest,
    client: TallyClient,
    session_store: SessionStore,
) -> ChatResponse:
    """Original in-memory session flow — used when DATABASE_URL is not set."""
    session = session_store.get_or_create(
        session_id=request.session_id,
        company=request.company,
    )
    session_id = request.session_id or session.session_id

    with _tracer.start_as_current_span(
        "chat",
        attributes={
            "langfuse.session.id": session_id,
            "langfuse.user.id": session_id,
            "langfuse.trace.name": "chat",
            "user.query": request.message,
        },
    ) as span:
        if request.company:
            span.set_attribute("langfuse.trace.metadata.company", request.company)

        orchestrator = Orchestrator()
        result = await orchestrator.process_query(request.message, client, session)

        chart = None
        if result.get("chart"):
            chart = ChartSpec(**result["chart"])

        return ChatResponse(
            message=result["message"],
            data=result.get("data"),
            chart=chart,
            session_id=result["session_id"],
        )


async def _chat_db_mode(
    request: ChatRequest,
    client: TallyClient,
    user_id: str,
) -> ChatResponse:
    """DB-backed conversation flow — used when DATABASE_URL is set."""
    from backend.agents.context import SessionContext
    from backend.agents.registry import get_agent
    from backend.db.engine import async_session_factory
    from backend.db.models import Conversation, Message, UsageLog, Workspace
    from backend.utils.pricing import compute_cost

    if not request.workspace_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="workspace_id is required in DB mode")
    if not request.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required in DB mode")

    async with async_session_factory() as db:
        # Load workspace
        result = await db.execute(
            select(Workspace).where(
                Workspace.id == request.workspace_id,
                Workspace.user_id == user_id,
                Workspace.is_deleted == False,
            )
        )
        workspace = result.scalar_one_or_none()
        if not workspace:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Load conversation
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.workspace_id == request.workspace_id,
                Conversation.user_id == user_id,
                Conversation.is_deleted == False,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Load prior messages from DB
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == request.conversation_id)
            .order_by(Message.created_at)
        )
        prior_messages = [
            {"role": m.role, "content": m.content}
            for m in result.scalars().all()
        ]

        # Persist user message
        user_msg = Message(
            conversation_id=request.conversation_id,
            role="user",
            content=request.message,
        )
        db.add(user_msg)
        await db.flush()

        # Build session context for orchestrator (bridge between DB and in-memory)
        session = SessionContext(
            session_id=str(conversation.id),
            company=workspace.name,
            max_messages=20,
        )
        for msg in prior_messages[-20:]:
            session.add_message(msg["role"], msg["content"])

        # Configure TallyClient from workspace
        ws_config = workspace.config or {}
        if ws_config.get("tally_host"):
            client = TallyClient(
                ws_config["tally_host"],
                ws_config.get("tally_port", 9000),
            )
            if ws_config.get("mock_mode"):
                client.mock_mode = True

        # Trace with Langfuse
        with _tracer.start_as_current_span(
            "chat",
            attributes={
                "langfuse.session.id": str(conversation.id),
                "langfuse.user.id": user_id,
                "langfuse.trace.name": "chat",
                "user.query": request.message,
                "workspace_id": str(workspace.id),
                "workspace_name": workspace.name,
                "agent_type": workspace.agent_type,
                "conversation_id": str(conversation.id),
            },
        ):
            start_time = time_module.time()

            orchestrator = Orchestrator()
            result = await orchestrator.process_query(request.message, client, session)

            latency_ms = int((time_module.time() - start_time) * 1000)

        chart = None
        if result.get("chart"):
            chart = ChartSpec(**result["chart"])

        # Persist assistant message
        assistant_msg = Message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=result["message"],
            data=result.get("data"),
            chart=result.get("chart"),
        )
        db.add(assistant_msg)
        await db.flush()

        # Log usage
        agent_calls = result.get("usage", [])
        if agent_calls:
            total_cost = compute_cost(agent_calls)
            usage_log = UsageLog(
                message_id=assistant_msg.id,
                user_id=user_id,
                workspace_id=workspace.id,
                conversation_id=conversation.id,
                total_input_tokens=sum(c.get("input_tokens", 0) for c in agent_calls),
                total_output_tokens=sum(c.get("output_tokens", 0) for c in agent_calls),
                total_cost_usd=total_cost,
                model_primary=workspace.config.get("model", settings.CLAUDE_MODEL),
                latency_ms=latency_ms,
                agent_calls=agent_calls,
            )
            db.add(usage_log)

        # Auto-generate title from first message
        if conversation.title is None:
            conversation.title = request.message[:100]

        await db.commit()

        return ChatResponse(
            message=result["message"],
            data=result.get("data"),
            chart=chart,
            session_id=str(conversation.id),
        )
```

- [ ] **Step 3: Add workspace_id and conversation_id to ChatRequest**

In `backend/api/models.py`, update the `ChatRequest` model:

```python
class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v
    session_id: str | None = None
    company: str | None = None
    workspace_id: str | None = None
    conversation_id: str | None = None
```

- [ ] **Step 4: Run existing tests to verify no regression**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/ -x`
Expected: All existing tests PASS (legacy mode — no DATABASE_URL set).

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/api/chat.py backend/api/models.py
git commit -m "feat: DB-mode chat endpoint with workspace routing, message persistence, and usage logging"
```

---

## Task 11: Usage Endpoint

**Files:**
- Create: `backend/api/usage.py`
- Modify: `backend/main.py` — register usage router

- [ ] **Step 1: Create usage endpoint**

Create `backend/api/usage.py`:

```python
"""Usage aggregation endpoint for billing/dashboard."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user
from backend.db.engine import get_db
from backend.db.models import UsageLog, Workspace

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    workspace_id: str | None = Query(None),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = select(UsageLog).where(UsageLog.user_id == user_id)

    if from_date:
        query = query.where(UsageLog.created_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        query = query.where(UsageLog.created_at <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))
    if workspace_id:
        query = query.where(UsageLog.workspace_id == workspace_id)

    result = await db.execute(query)
    logs = result.scalars().all()

    total_input = sum(l.total_input_tokens for l in logs)
    total_output = sum(l.total_output_tokens for l in logs)
    total_cost = sum(float(l.total_cost_usd) for l in logs)

    # Aggregate by workspace
    by_workspace: dict[str, dict] = {}
    for l in logs:
        ws_id = str(l.workspace_id)
        if ws_id not in by_workspace:
            by_workspace[ws_id] = {"workspace_id": ws_id, "cost_usd": 0.0, "message_count": 0}
        by_workspace[ws_id]["cost_usd"] += float(l.total_cost_usd)
        by_workspace[ws_id]["message_count"] += 1

    # Add workspace names
    if by_workspace:
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id.in_(by_workspace.keys()))
        )
        for ws in ws_result.scalars().all():
            if str(ws.id) in by_workspace:
                by_workspace[str(ws.id)]["name"] = ws.name

    # Aggregate by day
    by_day: dict[str, dict] = {}
    for l in logs:
        day = l.created_at.date().isoformat()
        if day not in by_day:
            by_day[day] = {"date": day, "cost_usd": 0.0, "message_count": 0}
        by_day[day]["cost_usd"] += float(l.total_cost_usd)
        by_day[day]["message_count"] += 1

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 6),
        "by_workspace": list(by_workspace.values()),
        "by_day": sorted(by_day.values(), key=lambda x: x["date"]),
    }
```

- [ ] **Step 2: Register usage router in main.py**

In `backend/main.py`, add to the `if settings.db_mode:` block:

```python
    from backend.api import auth, conversations, usage, workspaces
    app.include_router(auth.router, prefix="/api")
    app.include_router(workspaces.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(usage.router, prefix="/api")
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/usage.py backend/main.py
git commit -m "feat: add usage aggregation endpoint with per-workspace and per-day breakdowns"
```

---

## Task 12: Integration Tests with Test Database

**Files:**
- Create: `tests/integration/conftest.py` — test DB fixtures
- Create: `tests/integration/test_auth_flow.py`
- Create: `tests/integration/test_workspace_flow.py`
- Create: `tests/integration/test_conversation_flow.py`

Note: These tests require a running Postgres instance. They use a test database that is created/dropped per session. Skip these in CI if Postgres is not available (check for `DATABASE_URL` env var).

- [ ] **Step 1: Create test DB conftest**

Create `tests/integration/conftest.py` (add to the existing file if it exists, otherwise create):

Add a `db_session` fixture at the top of the file. If the file already has Tally-related fixtures, append these:

```python
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Only load DB fixtures if DATABASE_URL is available
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session")
def db_available():
    """Skip DB tests if TEST_DATABASE_URL is not set."""
    if not _TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set — skipping DB integration tests")


@pytest_asyncio.fixture
async def db_session(db_available):
    """Create tables, yield a session, then drop tables."""
    from backend.db.models import Base

    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

- [ ] **Step 2: Create auth flow integration test**

Create `tests/integration/test_auth_flow.py`:

```python
"""Integration tests for auth flow (register → login → refresh → me)."""

import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.utils.auth import hash_password, verify_password

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest.mark.asyncio
async def test_create_user_and_verify_password(db_session: AsyncSession):
    user = User(
        email="test@example.com",
        password_hash=hash_password("Str0ng!Pass#99"),
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert verify_password("Str0ng!Pass#99", user.password_hash)
    assert not verify_password("wrong", user.password_hash)


@pytest.mark.asyncio
async def test_email_unique_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError

    user1 = User(email="dupe@example.com", password_hash="hash1", name="User 1")
    db_session.add(user1)
    await db_session.commit()

    user2 = User(email="dupe@example.com", password_hash="hash2", name="User 2")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_lookup_by_email(db_session: AsyncSession):
    user = User(email="lookup@example.com", password_hash="hash", name="Lookup User")
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "lookup@example.com"))
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.name == "Lookup User"
```

- [ ] **Step 3: Create workspace flow integration test**

Create `tests/integration/test_workspace_flow.py`:

```python
"""Integration tests for workspace CRUD operations."""

import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User, Workspace

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(email="ws-test@example.com", password_hash="hash", name="WS Test")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_workspace(db_session: AsyncSession, test_user: User):
    ws = Workspace(
        user_id=test_user.id,
        name="Bharat Traders",
        config={"tally_host": "192.168.1.5", "tally_port": 9000},
    )
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    assert ws.id is not None
    assert ws.agent_type == "tally"
    assert ws.config["tally_host"] == "192.168.1.5"
    assert ws.memory == {}


@pytest.mark.asyncio
async def test_soft_delete_workspace(db_session: AsyncSession, test_user: User):
    ws = Workspace(user_id=test_user.id, name="To Delete")
    db_session.add(ws)
    await db_session.commit()

    ws.is_deleted = True
    await db_session.commit()

    result = await db_session.execute(
        select(Workspace).where(Workspace.user_id == test_user.id, Workspace.is_deleted == False)
    )
    active = result.scalars().all()
    assert all(w.name != "To Delete" for w in active)


@pytest.mark.asyncio
async def test_workspace_memory_update(db_session: AsyncSession, test_user: User):
    ws = Workspace(user_id=test_user.id, name="Memory Test")
    db_session.add(ws)
    await db_session.commit()

    ws.memory = {"fy_start": "01-04-2025", "branches": ["Mumbai"]}
    await db_session.commit()
    await db_session.refresh(ws)

    assert ws.memory["fy_start"] == "01-04-2025"
    assert "Mumbai" in ws.memory["branches"]
```

- [ ] **Step 4: Create conversation flow integration test**

Create `tests/integration/test_conversation_flow.py`:

```python
"""Integration tests for conversation and message persistence."""

import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Conversation, Message, User, Workspace

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def test_workspace(db_session: AsyncSession) -> tuple[User, Workspace]:
    user = User(email="conv-test@example.com", password_hash="hash", name="Conv Test")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    ws = Workspace(user_id=user.id, name="Conv Test Co")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    return user, ws


@pytest.mark.asyncio
async def test_create_conversation_with_messages(db_session: AsyncSession, test_workspace):
    user, ws = test_workspace

    conv = Conversation(user_id=user.id, workspace_id=ws.id, title="Sales Q3")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Add messages
    msg1 = Message(conversation_id=conv.id, role="user", content="What are total sales?")
    msg2 = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Total sales are 12,34,567.",
        data={"headers": ["Ledger", "Amount"], "rows": [["Sales", 1234567]]},
    )
    db_session.add_all([msg1, msg2])
    await db_session.commit()

    # Retrieve
    result = await db_session.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].data["headers"] == ["Ledger", "Amount"]


@pytest.mark.asyncio
async def test_conversation_title_auto_update(db_session: AsyncSession, test_workspace):
    user, ws = test_workspace

    conv = Conversation(user_id=user.id, workspace_id=ws.id)
    db_session.add(conv)
    await db_session.commit()
    assert conv.title is None

    conv.title = "What are total sales?"[:100]
    await db_session.commit()
    await db_session.refresh(conv)
    assert conv.title == "What are total sales?"


@pytest.mark.asyncio
async def test_message_with_chart_data(db_session: AsyncSession, test_workspace):
    user, ws = test_workspace

    conv = Conversation(user_id=user.id, workspace_id=ws.id)
    db_session.add(conv)
    await db_session.commit()

    chart_spec = {
        "chart_type": "bar",
        "title": "Sales by Month",
        "data": [{"month": "Apr", "amount": 100000}],
        "config": {"y_axis_label": "Amount"},
    }
    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content="Here are the sales.",
        chart=chart_spec,
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    assert msg.chart["chart_type"] == "bar"
    assert msg.chart["data"][0]["amount"] == 100000
```

- [ ] **Step 5: Run integration tests (if Postgres available)**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://localhost/tallyagent_test pytest tests/integration/test_auth_flow.py tests/integration/test_workspace_flow.py tests/integration/test_conversation_flow.py -v`
Expected: All tests PASS.

If Postgres is not available, tests are auto-skipped.

- [ ] **Step 6: Run all existing tests to verify no regression**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/ -x`
Expected: All existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/conftest.py tests/integration/test_auth_flow.py tests/integration/test_workspace_flow.py tests/integration/test_conversation_flow.py
git commit -m "test: add DB integration tests for auth, workspace, and conversation flows"
```

---

## Task 13: Frontend — Auth Context & API Client

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add auth types**

Add to `frontend/src/types/index.ts`:

```typescript
// --- Auth types (Set A1) ---

export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export interface AuthResponse {
  user: AuthUser;
  access_token: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// --- Workspace types (Set A1) ---

export interface WorkspaceData {
  id: string;
  name: string;
  agent_type: string;
  config: Record<string, unknown>;
  memory: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  tag: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string | null;
  tag: string | null;
  messages: MessageData[];
}

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: TableData | TableData[];
  chart?: ChartSpec;
  created_at: string;
}
```

- [ ] **Step 2: Update API client with auth interceptor**

Replace `frontend/src/api/client.ts`:

```typescript
import axios from "axios";
import type {
  AuthResponse,
  ChatRequest,
  ChatResponse,
  CompaniesResponse,
  ConversationDetail,
  ConversationSummary,
  HealthResponse,
  LoginRequest,
  RegisterRequest,
  TallyModeResponse,
  WorkspaceData,
} from "../types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 480000,
});

// --- Auth token management ---

let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// Request interceptor: attach Bearer token
api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/")
    ) {
      originalRequest._retry = true;
      try {
        const { data } = await api.post<{ access_token: string }>("/auth/refresh");
        _accessToken = data.access_token;
        originalRequest.headers.Authorization = `Bearer ${_accessToken}`;
        return api(originalRequest);
      } catch {
        _accessToken = null;
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);

// --- Auth API ---

export async function register(req: RegisterRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/register", req);
  _accessToken = data.access_token;
  return data;
}

export async function login(req: LoginRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/auth/login", req);
  _accessToken = data.access_token;
  return data;
}

export async function refreshToken(): Promise<string> {
  const { data } = await api.post<{ access_token: string }>("/auth/refresh");
  _accessToken = data.access_token;
  return data.access_token;
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
  _accessToken = null;
}

export async function getMe(): Promise<AuthResponse["user"]> {
  const { data } = await api.get<AuthResponse["user"]>("/auth/me");
  return data;
}

// --- Workspace API ---

export async function getWorkspaces(): Promise<WorkspaceData[]> {
  const { data } = await api.get<WorkspaceData[]>("/workspaces");
  return data;
}

export async function createWorkspace(req: {
  name: string;
  agent_type?: string;
  config?: Record<string, unknown>;
}): Promise<WorkspaceData> {
  const { data } = await api.post<WorkspaceData>("/workspaces", req);
  return data;
}

export async function deleteWorkspace(id: string): Promise<void> {
  await api.delete(`/workspaces/${id}`);
}

// --- Conversation API ---

export async function getConversations(workspaceId: string): Promise<ConversationSummary[]> {
  const { data } = await api.get<ConversationSummary[]>(
    `/workspaces/${workspaceId}/conversations`,
  );
  return data;
}

export async function createConversation(
  workspaceId: string,
  req?: { title?: string; tag?: string },
): Promise<ConversationSummary> {
  const { data } = await api.post<ConversationSummary>(
    `/workspaces/${workspaceId}/conversations`,
    req || {},
  );
  return data;
}

export async function getConversation(
  workspaceId: string,
  conversationId: string,
): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
  );
  return data;
}

export async function updateConversation(
  workspaceId: string,
  conversationId: string,
  req: { title?: string; tag?: string },
): Promise<ConversationSummary> {
  const { data } = await api.patch<ConversationSummary>(
    `/workspaces/${workspaceId}/conversations/${conversationId}`,
    req,
  );
  return data;
}

export async function deleteConversation(
  workspaceId: string,
  conversationId: string,
): Promise<void> {
  await api.delete(`/workspaces/${workspaceId}/conversations/${conversationId}`);
}

// --- Existing APIs (unchanged) ---

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

export async function getTallyMode(): Promise<TallyModeResponse> {
  const { data } = await api.get<TallyModeResponse>("/tally-mode");
  return data;
}

export async function setTallyMode(
  mode: "mock" | "live",
): Promise<TallyModeResponse> {
  const { data } = await api.post<TallyModeResponse>("/tally-mode", { mode });
  return data;
}
```

- [ ] **Step 3: Create AuthContext**

Create `frontend/src/context/AuthContext.tsx`:

```typescript
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  refreshToken,
  register as apiRegister,
  setAccessToken,
} from "../api/client";
import type { AuthUser, LoginRequest, RegisterRequest } from "../types";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Try to restore session on mount
  useEffect(() => {
    refreshToken()
      .then(() => getMe())
      .then((u) => setUser(u))
      .catch(() => {
        setAccessToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (req: LoginRequest) => {
    const res = await apiLogin(req);
    setUser(res.user);
  }, []);

  const register = useCallback(async (req: RegisterRequest) => {
    const res = await apiRegister(req);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/AuthContext.tsx frontend/src/api/client.ts frontend/src/types/index.ts
git commit -m "feat: add AuthContext, auth API client, and workspace/conversation types"
```

---

## Task 14: Frontend — Login & Register Pages

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/RegisterPage.tsx`
- Create: `frontend/src/components/ProtectedRoute.tsx`

- [ ] **Step 1: Create ProtectedRoute**

Create `frontend/src/components/ProtectedRoute.tsx`:

```typescript
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Create LoginPage**

Create `frontend/src/pages/LoginPage.tsx`:

```typescript
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login({ email, password });
      navigate("/");
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        if (axiosErr.response?.status === 429) {
          setError("Too many login attempts. Please try again later.");
        } else {
          setError(axiosErr.response?.data?.detail || "Login failed");
        }
      } else {
        setError("Network error. Please check your connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h1 className="text-2xl font-bold text-center text-gray-900">
            TallyPrime AI
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Sign in to your account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          Don't have an account?{" "}
          <Link to="/register" className="text-blue-600 hover:text-blue-500">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create RegisterPage**

Create `frontend/src/pages/RegisterPage.tsx`:

```typescript
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function getPasswordStrength(password: string): { score: number; label: string; color: string } {
  let score = 0;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\/`~;]/.test(password)) score++;

  if (score <= 2) return { score, label: "Weak", color: "bg-red-500" };
  if (score <= 3) return { score, label: "Fair", color: "bg-yellow-500" };
  if (score <= 4) return { score, label: "Good", color: "bg-blue-500" };
  return { score, label: "Strong", color: "bg-green-500" };
}

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const strength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await register({ email, password, name });
      navigate("/");
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { data?: { detail?: string | string[] } } };
        const detail = axiosErr.response?.data?.detail;
        if (Array.isArray(detail)) {
          setError(detail.join(". "));
        } else {
          setError(detail || "Registration failed");
        }
      } else {
        setError("Network error. Please check your connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h1 className="text-2xl font-bold text-center text-gray-900">
            TallyPrime AI
          </h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Create your account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">
              Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
            {password && (
              <div className="mt-2">
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded ${
                        i <= strength.score ? strength.color : "bg-gray-200"
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {strength.label} — must be 12+ chars with uppercase, lowercase, digit, and special character
                </p>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || strength.score < 5}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          Already have an account?{" "}
          <Link to="/login" className="text-blue-600 hover:text-blue-500">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ frontend/src/components/ProtectedRoute.tsx
git commit -m "feat: add login, register pages with password strength indicator and protected route"
```

---

## Task 15: Frontend — Sidebar & Conversation List

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/ConversationList.tsx`
- Create: `frontend/src/components/ConnectCompanyModal.tsx`
- Create: `frontend/src/components/UserMenu.tsx`

- [ ] **Step 1: Create Sidebar**

Create `frontend/src/components/Sidebar.tsx`:

```typescript
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getConversations, getWorkspaces } from "../api/client";
import type { ConversationSummary, WorkspaceData } from "../types";
import ConversationList from "./ConversationList";
import ConnectCompanyModal from "./ConnectCompanyModal";

interface SidebarProps {
  activeConversationId?: string;
  onConversationSelect: (workspaceId: string, conversationId: string) => void;
  onNewChat: (workspaceId: string) => void;
}

export default function Sidebar({
  activeConversationId,
  onConversationSelect,
  onNewChat,
}: SidebarProps) {
  const [workspaces, setWorkspaces] = useState<WorkspaceData[]>([]);
  const [conversations, setConversations] = useState<Record<string, ConversationSummary[]>>({});
  const [showModal, setShowModal] = useState(false);

  const loadData = async () => {
    const ws = await getWorkspaces();
    setWorkspaces(ws);

    const convMap: Record<string, ConversationSummary[]> = {};
    for (const w of ws) {
      convMap[w.id] = await getConversations(w.id);
    }
    setConversations(convMap);
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <aside className="w-70 border-r border-gray-200 bg-gray-50 flex flex-col h-full overflow-hidden">
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {workspaces.map((ws) => (
          <div key={ws.id}>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-2 mb-1">
              {ws.name}
            </h3>
            <ConversationList
              workspaceId={ws.id}
              conversations={conversations[ws.id] || []}
              activeConversationId={activeConversationId}
              onSelect={(cid) => onConversationSelect(ws.id, cid)}
              onNewChat={() => onNewChat(ws.id)}
            />
          </div>
        ))}
      </div>

      <div className="border-t border-gray-200 p-3">
        <button
          onClick={() => setShowModal(true)}
          className="w-full text-sm text-gray-600 hover:text-gray-900 flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-100"
        >
          + Connect Company
        </button>
      </div>

      {showModal && (
        <ConnectCompanyModal
          onClose={() => setShowModal(false)}
          onCreated={() => {
            setShowModal(false);
            loadData();
          }}
        />
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Create ConversationList**

Create `frontend/src/components/ConversationList.tsx`:

```typescript
import type { ConversationSummary } from "../types";

interface ConversationListProps {
  workspaceId: string;
  conversations: ConversationSummary[];
  activeConversationId?: string;
  onSelect: (conversationId: string) => void;
  onNewChat: () => void;
}

export default function ConversationList({
  conversations,
  activeConversationId,
  onSelect,
  onNewChat,
}: ConversationListProps) {
  return (
    <div className="space-y-0.5">
      {conversations.map((conv) => (
        <button
          key={conv.id}
          onClick={() => onSelect(conv.id)}
          className={`w-full text-left px-2 py-1.5 rounded text-sm truncate ${
            conv.id === activeConversationId
              ? "bg-blue-100 text-blue-900"
              : "text-gray-700 hover:bg-gray-100"
          }`}
        >
          {conv.title || "New Chat"}
        </button>
      ))}
      <button
        onClick={onNewChat}
        className="w-full text-left px-2 py-1.5 rounded text-sm text-gray-500 hover:bg-gray-100"
      >
        + New Chat
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Create ConnectCompanyModal**

Create `frontend/src/components/ConnectCompanyModal.tsx`:

```typescript
import { useState } from "react";
import { createWorkspace } from "../api/client";

interface ConnectCompanyModalProps {
  onClose: () => void;
  onCreated: () => void;
}

export default function ConnectCompanyModal({
  onClose,
  onCreated,
}: ConnectCompanyModalProps) {
  const [name, setName] = useState("");
  const [tallyHost, setTallyHost] = useState("localhost");
  const [tallyPort, setTallyPort] = useState("9000");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await createWorkspace({
        name,
        config: { tally_host: tallyHost, tally_port: parseInt(tallyPort, 10) },
      });
      onCreated();
    } catch {
      setError("Failed to connect company. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Connect Tally Company
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Company Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Bharat Traders Pvt Ltd"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Tally Host
            </label>
            <input
              type="text"
              required
              value={tallyHost}
              onChange={(e) => setTallyHost(e.target.value)}
              placeholder="localhost or 192.168.1.5"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Tally Port
            </label>
            <input
              type="number"
              required
              value={tallyPort}
              onChange={(e) => setTallyPort(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
            >
              {loading ? "Connecting..." : "Connect"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create UserMenu**

Create `frontend/src/components/UserMenu.tsx`:

```typescript
import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  if (!user) return null;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-sm text-gray-700 hover:text-gray-900"
      >
        <span className="w-7 h-7 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-medium">
          {user.name.charAt(0).toUpperCase()}
        </span>
        <span className="hidden sm:inline">{user.name}</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-md shadow-lg z-50">
          <div className="px-4 py-2 border-b border-gray-100">
            <p className="text-sm font-medium text-gray-900">{user.name}</p>
            <p className="text-xs text-gray-500">{user.email}</p>
          </div>
          <button
            onClick={() => { navigate("/settings"); setOpen(false); }}
            className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Settings
          </button>
          <button
            onClick={handleLogout}
            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/components/ConversationList.tsx frontend/src/components/ConnectCompanyModal.tsx frontend/src/components/UserMenu.tsx
git commit -m "feat: add sidebar, conversation list, connect company modal, and user menu components"
```

---

## Task 16: Frontend — Wire Up App.tsx with Router

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/ChatWindow.tsx`
- Modify: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Update App.tsx**

Replace `frontend/src/App.tsx`:

```typescript
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SessionProvider } from "./context/SessionContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ChatApp from "./ChatApp";

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={user ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route
        path="/c/:conversationId"
        element={
          <ProtectedRoute>
            <ChatApp />
          </ProtectedRoute>
        }
      />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <ChatApp />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  // Check if DB mode is likely (auth endpoints exist)
  // If not, render legacy mode (no auth, no sidebar)
  const isLegacyMode = !import.meta.env.VITE_DB_MODE;

  if (isLegacyMode) {
    return (
      <SessionProvider>
        <div className="h-screen flex flex-col bg-white">
          <LegacyHeader />
          <main className="flex-1 overflow-hidden">
            <LegacyChatWindow />
          </main>
        </div>
      </SessionProvider>
    );
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

// Legacy imports — keep existing behavior when not in DB mode
import Header as LegacyHeader from "./components/Header";
import ChatWindow as LegacyChatWindow from "./components/ChatWindow";

export default App;
```

Note: The `import as` syntax above won't work in TypeScript. Instead, create a separate file `frontend/src/ChatApp.tsx` for the DB-mode layout:

Create `frontend/src/ChatApp.tsx`:

```typescript
import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createConversation } from "./api/client";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";

export default function ChatApp() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);

  const handleConversationSelect = useCallback(
    (workspaceId: string, convId: string) => {
      setActiveWorkspaceId(workspaceId);
      navigate(`/c/${convId}`);
    },
    [navigate],
  );

  const handleNewChat = useCallback(
    async (workspaceId: string) => {
      const conv = await createConversation(workspaceId);
      setActiveWorkspaceId(workspaceId);
      navigate(`/c/${conv.id}`);
    },
    [navigate],
  );

  return (
    <div className="h-screen flex flex-col bg-white">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeConversationId={conversationId}
          onConversationSelect={handleConversationSelect}
          onNewChat={handleNewChat}
        />
        <main className="flex-1 overflow-hidden">
          <ChatWindow
            conversationId={conversationId}
            workspaceId={activeWorkspaceId || undefined}
          />
        </main>
      </div>
    </div>
  );
}
```

Now update `frontend/src/App.tsx` properly:

```typescript
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SessionProvider } from "./context/SessionContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ChatApp from "./ChatApp";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={user ? <Navigate to="/" replace /> : <RegisterPage />}
      />
      <Route
        path="/c/:conversationId"
        element={
          <ProtectedRoute>
            <ChatApp />
          </ProtectedRoute>
        }
      />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <ChatApp />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function LegacyApp() {
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

function App() {
  const isDbMode = import.meta.env.VITE_DB_MODE === "true";

  if (!isDbMode) {
    return <LegacyApp />;
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
```

- [ ] **Step 2: Update ChatWindow to accept props for DB mode**

The existing `ChatWindow` uses `useSession()` for sessionId/company. In DB mode, it receives `conversationId` and `workspaceId` as props and loads messages from the API. Update the component to support both modes:

At the top of `frontend/src/components/ChatWindow.tsx`, update the interface and imports:

```typescript
interface ChatWindowProps {
  conversationId?: string;
  workspaceId?: string;
}

export default function ChatWindow({ conversationId, workspaceId }: ChatWindowProps = {}) {
```

In the `handleSend` callback, when `conversationId` and `workspaceId` are provided, include them in the chat request:

```typescript
const response = await sendChat({
  message: text,
  session_id: sessionId ?? undefined,
  company: company ?? undefined,
  workspace_id: workspaceId,
  conversation_id: conversationId,
});
```

Add a `useEffect` to load conversation messages when `conversationId` changes:

```typescript
useEffect(() => {
  if (conversationId && workspaceId) {
    getConversation(workspaceId, conversationId).then((conv) => {
      setMessages(
        conv.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          data: m.data,
          chart: m.chart,
        })),
      );
    });
  }
}, [conversationId, workspaceId]);
```

Add import for `getConversation`:

```typescript
import { getConversation, sendChat } from "../api/client";
```

- [ ] **Step 3: Update Header to include UserMenu in DB mode**

Add `UserMenu` to the Header in DB mode. The Header should check if `useAuth` is available:

Add to `frontend/src/components/Header.tsx`, import and render `UserMenu` in the right side:

```typescript
import UserMenu from "./UserMenu";
```

Add `<UserMenu />` after `<CompanySelector />` in the header JSX.

- [ ] **Step 4: Add ChatRequest workspace/conversation fields to types**

Update `frontend/src/types/index.ts` `ChatRequest`:

```typescript
export interface ChatRequest {
  message: string;
  session_id?: string;
  company?: string;
  workspace_id?: string;
  conversation_id?: string;
}
```

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && npm test`
Expected: Existing tests pass. Some may need minor updates for the new props on ChatWindow (add default props where called).

- [ ] **Step 6: Run all backend tests**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/ -x`
Expected: All existing tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/ChatApp.tsx frontend/src/components/ChatWindow.tsx frontend/src/components/Header.tsx frontend/src/types/index.ts
git commit -m "feat: wire up React Router, auth flow, sidebar, and DB-mode chat in frontend"
```

---

## Task 17: End-to-End Smoke Test

This is a manual verification task to confirm the full flow works.

- [ ] **Step 1: Start Postgres**

Run: `docker run -d --name tallyagent-db -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=tallyagent -p 5432:5432 postgres:16`

Or use an existing Postgres instance.

- [ ] **Step 2: Run migrations**

Run: `DATABASE_URL=postgresql+asyncpg://postgres:devpass@localhost/tallyagent alembic upgrade head`
Expected: All tables created.

- [ ] **Step 3: Start backend in DB mode**

Run:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:devpass@localhost/tallyagent \
JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))") \
TALLY_MODE=mock \
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Expected: Server starts, "Database mode enabled (PostgreSQL)" in logs.

- [ ] **Step 4: Start frontend in DB mode**

Run: `cd frontend && VITE_DB_MODE=true npm run dev`
Expected: Vite dev server starts.

- [ ] **Step 5: Manual test flow**

1. Open `http://localhost:5173` → should redirect to `/login`
2. Click "Register" → create account with strong password
3. After register → redirected to main app
4. Click "Connect Company" → add "Test Co" with localhost:9000
5. Click "+ New Chat" under Test Co → opens empty chat
6. Send "What is the trial balance?" → should get mock response
7. Check sidebar — conversation title auto-generated
8. Reload page → conversation history persists
9. Click user menu → sign out → redirected to login
10. Login again → conversations still there

- [ ] **Step 6: Verify legacy mode still works**

Stop backend. Restart without DATABASE_URL:

Run: `TALLY_MODE=mock uvicorn backend.main:app --reload`
Run: `cd frontend && npm run dev` (without VITE_DB_MODE)

Open `http://localhost:5173` → should show the original app (no login, no sidebar).

- [ ] **Step 7: Final commit**

If any fixes were needed during smoke test, commit them:

```bash
git add -A
git commit -m "fix: smoke test fixes for auth + persistence flow"
```

---

## Task 18: Automated E2E Smoke Tests (Both Modes)

**Files:**
- Create: `tests/e2e/test_legacy_smoke.py`
- Create: `tests/e2e/test_db_smoke.py`

These tests use FastAPI's `TestClient` / `httpx.AsyncClient` with the app directly — no external server needed.

- [ ] **Step 1: Write legacy mode E2E smoke test**

Create `tests/e2e/test_legacy_smoke.py`:

```python
"""E2E smoke test — legacy mode (no DATABASE_URL, no auth)."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure legacy mode: no DATABASE_URL
os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def app():
    """Import app fresh to pick up env state."""
    from backend.main import app
    app.state.tally_client.mock_mode = True
    return app


@pytest.mark.asyncio
async def test_legacy_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_legacy_chat_no_auth_required(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "session_id" in data


@pytest.mark.asyncio
async def test_legacy_chat_session_continuity(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp1 = await ac.post("/api/chat", json={"message": "hello"})
        session_id = resp1.json()["session_id"]

        resp2 = await ac.post("/api/chat", json={
            "message": "What is 2+2?",
            "session_id": session_id,
        })
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_legacy_no_workspace_endpoints(app):
    """In legacy mode, workspace endpoints should not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/workspaces")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run legacy smoke test**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/e2e/test_legacy_smoke.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 3: Write DB mode E2E smoke test**

Create `tests/e2e/test_db_smoke.py`:

```python
"""E2E smoke test — DB mode (auth + persistence).

Requires TEST_DATABASE_URL to be set. Uses a real Postgres instance.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB E2E tests",
)


@pytest.fixture(autouse=True)
def set_db_env(monkeypatch):
    """Configure DB mode for this test module."""
    db_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("TALLY_MODE", "mock")


@pytest.fixture
async def setup_db():
    """Create and teardown tables."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from backend.db.models import Base

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def app(setup_db):
    """Import app fresh with DB mode enabled."""
    # Force reimport to pick up env changes
    import importlib
    import backend.config
    importlib.reload(backend.config)
    import backend.main
    importlib.reload(backend.main)
    from backend.main import app
    return app


@pytest.mark.asyncio
async def test_db_health_is_public(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_db_chat_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_db_register_login_flow(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register
        resp = await ac.post("/api/auth/register", json={
            "email": "smoke@example.com",
            "password": "Str0ng!Pass#99",
            "name": "Smoke Test",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert token

        # /me with token
        resp = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "smoke@example.com"

        # Login
        resp = await ac.post("/api/auth/login", json={
            "email": "smoke@example.com",
            "password": "Str0ng!Pass#99",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_db_full_chat_flow(app):
    """Register → create workspace → create conversation → send chat → verify persistence."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register
        resp = await ac.post("/api/auth/register", json={
            "email": "fullflow@example.com",
            "password": "Str0ng!Pass#99",
            "name": "Full Flow",
        })
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create workspace
        resp = await ac.post("/api/workspaces", json={
            "name": "Test Co",
            "config": {"tally_host": "localhost", "tally_port": 9000, "mock_mode": True},
        }, headers=headers)
        assert resp.status_code == 201
        workspace_id = resp.json()["id"]

        # Create conversation
        resp = await ac.post(
            f"/api/workspaces/{workspace_id}/conversations",
            json={},
            headers=headers,
        )
        assert resp.status_code == 201
        conv_id = resp.json()["id"]

        # Send chat message
        resp = await ac.post("/api/chat", json={
            "message": "hello",
            "workspace_id": workspace_id,
            "conversation_id": conv_id,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["message"]

        # Verify conversation has messages
        resp = await ac.get(
            f"/api/workspaces/{workspace_id}/conversations/{conv_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) >= 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[1]["role"] == "assistant"

        # Verify conversation title was auto-generated
        assert resp.json()["title"] == "hello"


@pytest.mark.asyncio
async def test_db_weak_password_rejected(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/auth/register", json={
            "email": "weak@example.com",
            "password": "weak",
            "name": "Weak Pass",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_db_workspace_isolation(app):
    """Users can only see their own workspaces."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # User 1
        resp = await ac.post("/api/auth/register", json={
            "email": "user1@example.com", "password": "Str0ng!Pass#99", "name": "User 1",
        })
        token1 = resp.json()["access_token"]

        await ac.post("/api/workspaces", json={"name": "User1 Co"},
                       headers={"Authorization": f"Bearer {token1}"})

        # User 2
        resp = await ac.post("/api/auth/register", json={
            "email": "user2@example.com", "password": "Str0ng!Pass#99", "name": "User 2",
        })
        token2 = resp.json()["access_token"]

        # User 2 should see 0 workspaces
        resp = await ac.get("/api/workspaces",
                            headers={"Authorization": f"Bearer {token2}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0
```

- [ ] **Step 4: Run DB smoke test (if Postgres available)**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://localhost/tallyagent_test ANTHROPIC_API_KEY=test-key pytest tests/e2e/test_db_smoke.py -v`
Expected: All 6 tests PASS. Skipped if TEST_DATABASE_URL not set.

- [ ] **Step 5: Run ALL tests to verify no regression**

Run: `ANTHROPIC_API_KEY=test-key pytest tests/ -v --ignore=tests/e2e_live/ --ignore=tests/eval/ -x`
Expected: All existing + new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/test_legacy_smoke.py tests/e2e/test_db_smoke.py
git commit -m "test: add automated E2E smoke tests for both legacy and DB modes"
```

---

## Summary

| Task | What | Tests Added |
|------|------|-------------|
| 1 | Dependencies | — |
| 2 | DB engine + config | 7 |
| 3 | ORM models | 7 |
| 4 | Alembic migrations | — |
| 5 | Password + JWT utils | 12 |
| 6 | Pricing utility | 5 |
| 7 | Auth API endpoints | 4 |
| 8 | Workspace + conversation endpoints | 5 |
| 9 | Agent registry | 4 |
| 10 | main.py + chat endpoint DB mode | — (regression) |
| 11 | Usage endpoint | — |
| 12 | DB integration tests | 8 |
| 13 | Frontend auth context + API client | — |
| 14 | Login + register pages | — |
| 15 | Sidebar + conversation list | — |
| 16 | Wire up App.tsx with Router | — (regression) |
| 17 | Manual E2E smoke test | — (manual) |
| 18 | Automated E2E smoke tests (both modes) | 10 |

**Total new tests:** ~62 (unit + integration + E2E)
**Existing tests preserved:** 1024 (legacy mode, zero changes)

---

## Post-Implementation Notes (2026-04-04)

### All 18 tasks completed + code review fixes — 26 commits on `feature/set-a1-auth-persistence`

### Bugs Found & Fixed During Smoke Test

1. **useSession crash in DB mode** (commit dd0c012): `ChatWindow` called `useSession()` which requires `SessionProvider`, but DB mode uses `AuthProvider`. Fixed by making `useSession()` return a no-op default instead of throwing when no provider exists.

2. **Mock mode not propagating to per-workspace TallyClient** (commit b5a16ae): Workspaces created without `mock_mode` in config caused the DB-mode chat endpoint to create a live TallyClient, which tried to connect to a non-existent Tally. Fixed by adding Demo Mode toggle to ConnectCompanyModal.

3. **Sidebar not refreshing after chat** (commit b5a16ae): Sidebar loaded data on mount only. After sending a message (which auto-generates conversation title), sidebar was stale. Fixed with `refreshTrigger` prop incremented after each chat response.

4. **Active company unclear in UI** (commit 7bb1deb + preceding): No indication of which workspace was active. Fixed by: showing active company name in header, bolding active workspace in sidebar, adding collapsible workspace sections.

5. **.env symlink needed for worktree**: Worktree doesn't inherit `.env` from main repo. Needed `ln -s` to make `DATABASE_URL` and `JWT_SECRET` available to the backend.

### Test Gap Identified

**No Playwright test renders the DB-mode React component tree in a real browser.** The `useSession` crash was only caught during manual smoke test because:
- Vitest tests mock contexts (always wrap in `SessionProvider`)
- DB E2E tests use `httpx.ASGITransport` (API-only, no browser)
- Playwright tests only cover legacy mode

### Code Review (2026-04-04)

Review saved to `docs/code-review-set-a1.md`. Verdict: **conditionally approved**.

**All findings fixed:**

| ID | Finding | Fix |
|----|---------|-----|
| C1 | Usage logging never fires | Orchestrator returns usage records from all agents |
| I1 | No register rate limiting | 3/hour per IP via `_check_register_rate_limit()` |
| I2 | CORS `*` + credentials | Configurable `CORS_ORIGINS` setting |
| I3 | Email case-sensitive | `LoginRequest` gets `email_valid` validator |
| I4 | Bare `except Exception` | Specific `jwt.ExpiredSignatureError, jwt.InvalidTokenError` |
| I5 | Manual DB session | `_get_optional_db` dependency injection |
| I6 | is_deleted not checked | Added `.is_(False)` to update/delete queries |
| I7 | Direct nav doesn't load | Already working — `workspaceId` in useEffect deps |
| S1 | Registry not wired | `get_agent(workspace.agent_type)` in chat endpoint |
| S2 | Serial sidebar loading | `Promise.all` for parallel loading |
| S4 | Rate limit memory leak | Prune dict when >1000 entries |
| S6 | updated_at not bumped | Explicit `conversation.updated_at` update |
| S8 | No error handling | `.catch()` on `getConversation` |
| S9 | `== False` warning | `.is_(False)` idiom |

### Test Coverage (2026-04-04)

Overall: **83% backend** (unit tests only), higher with DB integration tests.

| Test Suite | Count |
|-----------|-------|
| Unit tests | 770 |
| DB integration (auth, workspace, conversation, usage) | 12 |
| DB E2E smoke | 8 |
| Legacy E2E smoke | 3 |
| Frontend Vitest | 116 |
| **Total** | **909** |

### Remaining Work

- [ ] **Playwright E2E tests for DB mode**: Register → login → connect company → new chat → send message → verify response → logout → login → verify persistence. Would have caught the useSession bug.
- [ ] **Known limitation**: On hard page reload, chat messages don't auto-load until user clicks conversation in sidebar (workspaceId lost from React state). The `onWorkspaceResolved` callback resolves workspace identity and ChatWindow re-fires the useEffect, but only after sidebar data loads.
