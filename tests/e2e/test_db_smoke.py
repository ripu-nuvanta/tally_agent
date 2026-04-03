"""E2E smoke test — DB mode (auth + persistence). Requires TEST_DATABASE_URL."""
import importlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping DB E2E tests",
)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest_asyncio.fixture
async def db_app(monkeypatch):
    """
    Stand up a full FastAPI app in DB mode for one test.

    Because httpx ASGITransport does NOT trigger ASGI lifespan events, we
    manually wire up app.state (tally_client, session_store) and call
    init_engine() ourselves — exactly what the lifespan would do.
    """
    # 1. Set env vars before any module reload
    monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("TALLY_MODE", "mock")
    monkeypatch.setenv("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key"))

    # 2. Reload config so db_mode=True is reflected
    import backend.config
    importlib.reload(backend.config)
    backend.config.settings = backend.config.Settings()

    # 3. Reload engine module (it reads settings at import time)
    import backend.db.engine
    importlib.reload(backend.db.engine)

    # 4. Create test DB tables
    from backend.db.models import Base
    setup_engine = create_async_engine(_TEST_DB_URL)
    async with setup_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await setup_engine.dispose()

    # 5. Reload API modules that hold a stale reference to settings.
    #    Only dependencies.py controls auth enforcement for all endpoints.
    import backend.api.dependencies
    importlib.reload(backend.api.dependencies)
    import backend.api.chat
    importlib.reload(backend.api.chat)
    import backend.api.auth
    importlib.reload(backend.api.auth)
    import backend.api.workspaces
    importlib.reload(backend.api.workspaces)
    import backend.api.conversations
    importlib.reload(backend.api.conversations)
    import backend.api.usage
    importlib.reload(backend.api.usage)

    # Reload main.py — with db_mode=True the auth/workspace/conversation
    #    routers are registered at module level (the if settings.db_mode block)
    import backend.main
    importlib.reload(backend.main)
    from backend.main import app

    # 6. Manually initialise what lifespan would do (ASGITransport skips lifespan)
    from backend.agents.context import SessionStore
    from backend.tally_bridge.client import TallyClient
    from backend.db.engine import init_engine

    tally_client = TallyClient(host="localhost", port=9000)
    tally_client.mock_mode = True
    app.state.tally_client = tally_client
    app.state.session_store = SessionStore(ttl_minutes=60)
    init_engine(_TEST_DB_URL)

    yield app

    # 7. Teardown
    await tally_client.close()
    from backend.db.engine import close_engine
    await close_engine()

    teardown_engine = create_async_engine(_TEST_DB_URL)
    async with teardown_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await teardown_engine.dispose()

    # 8. Restore modules to legacy state so other test files aren't affected
    monkeypatch.delenv("DATABASE_URL", raising=False)
    importlib.reload(backend.config)
    backend.config.settings = backend.config.Settings()
    importlib.reload(backend.db.engine)
    importlib.reload(backend.api.dependencies)
    importlib.reload(backend.api.chat)
    importlib.reload(backend.api.auth)
    importlib.reload(backend.api.workspaces)
    importlib.reload(backend.api.conversations)
    importlib.reload(backend.api.usage)
    importlib.reload(backend.main)


async def test_db_health_is_public(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200


async def test_db_chat_requires_auth(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        resp = await ac.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 401


async def test_db_register_login_flow(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        # Register
        resp = await ac.post("/api/auth/register", json={
            "email": "smoke@example.com", "password": "Str0ng!Pass#99", "name": "Smoke Test",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        assert token

        # /me with token
        resp = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "smoke@example.com"

        # Login
        resp = await ac.post("/api/auth/login", json={
            "email": "smoke@example.com", "password": "Str0ng!Pass#99",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]


async def test_db_full_chat_flow(db_app):
    """Register → create workspace → create conversation → chat → verify persistence."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        # Register
        resp = await ac.post("/api/auth/register", json={
            "email": "fullflow@example.com", "password": "Str0ng!Pass#99", "name": "Full Flow",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create workspace
        resp = await ac.post("/api/workspaces", json={
            "name": "Test Co",
            "config": {"tally_host": "localhost", "tally_port": 9000, "mock_mode": True},
        }, headers=headers)
        assert resp.status_code == 201, resp.text
        workspace_id = resp.json()["id"]

        # Create conversation
        resp = await ac.post(f"/api/workspaces/{workspace_id}/conversations", json={}, headers=headers)
        assert resp.status_code == 201, resp.text
        conv_id = resp.json()["id"]

        # Send chat message
        resp = await ac.post("/api/chat", json={
            "message": "hello",
            "workspace_id": workspace_id,
            "conversation_id": conv_id,
        }, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"]

        # Verify conversation has messages
        resp = await ac.get(f"/api/workspaces/{workspace_id}/conversations/{conv_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        messages = resp.json()["messages"]
        assert len(messages) >= 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "hello"
        assert messages[1]["role"] == "assistant"

        # Verify title auto-generated
        assert resp.json()["title"] == "hello"


async def test_db_weak_password_rejected(db_app):
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        resp = await ac.post("/api/auth/register", json={
            "email": "weak@example.com", "password": "weak", "name": "Weak Pass",
        })
    assert resp.status_code == 422


async def test_db_workspace_isolation(db_app):
    """Users can only see their own workspaces."""
    async with AsyncClient(transport=ASGITransport(app=db_app), base_url="http://test") as ac:
        # User 1
        resp = await ac.post("/api/auth/register", json={
            "email": "user1@example.com", "password": "Str0ng!Pass#99", "name": "User 1",
        })
        assert resp.status_code == 200, resp.text
        token1 = resp.json()["access_token"]
        await ac.post("/api/workspaces", json={"name": "User1 Co"},
                      headers={"Authorization": f"Bearer {token1}"})

        # User 2
        resp = await ac.post("/api/auth/register", json={
            "email": "user2@example.com", "password": "Str0ng!Pass#99", "name": "User 2",
        })
        assert resp.status_code == 200, resp.text
        token2 = resp.json()["access_token"]

        # User 2 should see 0 workspaces
        resp = await ac.get("/api/workspaces", headers={"Authorization": f"Bearer {token2}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0
