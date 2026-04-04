"""Integration tests for usage logging — real Postgres."""
import os
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Conversation, Message, UsageLog, User, Workspace

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


@pytest_asyncio.fixture
async def test_conversation(db_session: AsyncSession):
    """Create user → workspace → conversation → message chain."""
    user = User(email="usage-test@example.com", password_hash="hash", name="Usage Test")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    ws = Workspace(user_id=user.id, name="Usage Test Co")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    conv = Conversation(user_id=user.id, workspace_id=ws.id, title="Usage Test Chat")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg = Message(conversation_id=conv.id, role="assistant", content="Test response")
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)

    return user, ws, conv, msg


@pytest.mark.asyncio
async def test_create_usage_log(db_session: AsyncSession, test_conversation):
    user, ws, conv, msg = test_conversation

    usage = UsageLog(
        message_id=msg.id,
        user_id=user.id,
        workspace_id=ws.id,
        conversation_id=conv.id,
        total_input_tokens=5000,
        total_output_tokens=1200,
        total_cost_usd=Decimal("0.033000"),
        model_primary="claude-sonnet-4-6",
        latency_ms=14500,
        agent_calls=[
            {"agent": "classifier", "model": "claude-haiku-4-5-20251001", "input_tokens": 800, "output_tokens": 50},
            {"agent": "query", "model": "claude-sonnet-4-6", "input_tokens": 4200, "output_tokens": 1150},
        ],
    )
    db_session.add(usage)
    await db_session.commit()
    await db_session.refresh(usage)

    assert usage.id is not None
    assert usage.total_input_tokens == 5000
    assert usage.total_output_tokens == 1200
    assert float(usage.total_cost_usd) == pytest.approx(0.033, abs=1e-6)
    assert usage.latency_ms == 14500
    assert len(usage.agent_calls) == 2
    assert usage.agent_calls[0]["agent"] == "classifier"


@pytest.mark.asyncio
async def test_usage_log_unique_per_message(db_session: AsyncSession, test_conversation):
    """One usage log per message — unique constraint."""
    from sqlalchemy.exc import IntegrityError

    user, ws, conv, msg = test_conversation

    usage1 = UsageLog(
        message_id=msg.id, user_id=user.id, workspace_id=ws.id,
        conversation_id=conv.id, total_input_tokens=100, total_output_tokens=50,
        total_cost_usd=Decimal("0.001"), model_primary="claude-sonnet-4-6",
        latency_ms=1000, agent_calls=[],
    )
    db_session.add(usage1)
    await db_session.commit()

    usage2 = UsageLog(
        message_id=msg.id, user_id=user.id, workspace_id=ws.id,
        conversation_id=conv.id, total_input_tokens=200, total_output_tokens=100,
        total_cost_usd=Decimal("0.002"), model_primary="claude-sonnet-4-6",
        latency_ms=2000, agent_calls=[],
    )
    db_session.add(usage2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_usage_log_query_by_user(db_session: AsyncSession, test_conversation):
    """Usage logs queryable by user_id."""
    user, ws, conv, msg = test_conversation

    usage = UsageLog(
        message_id=msg.id, user_id=user.id, workspace_id=ws.id,
        conversation_id=conv.id, total_input_tokens=3000, total_output_tokens=800,
        total_cost_usd=Decimal("0.021"), model_primary="claude-sonnet-4-6",
        latency_ms=8000, agent_calls=[{"agent": "query", "model": "claude-sonnet-4-6", "input_tokens": 3000, "output_tokens": 800}],
    )
    db_session.add(usage)
    await db_session.commit()

    result = await db_session.execute(
        select(UsageLog).where(UsageLog.user_id == user.id)
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].total_input_tokens == 3000
