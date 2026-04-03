"""Integration tests for workspace CRUD — real Postgres."""
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
    ws = Workspace(user_id=test_user.id, name="Bharat Traders", config={"tally_host": "192.168.1.5", "tally_port": 9000})
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
