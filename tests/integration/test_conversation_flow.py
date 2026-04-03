"""Integration tests for conversation and message persistence — real Postgres."""
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
async def test_workspace(db_session: AsyncSession) -> tuple:
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
    msg1 = Message(conversation_id=conv.id, role="user", content="What are total sales?")
    msg2 = Message(
        conversation_id=conv.id, role="assistant", content="Total sales are 12,34,567.",
        data={"headers": ["Ledger", "Amount"], "rows": [["Sales", 1234567]]},
    )
    db_session.add_all([msg1, msg2])
    await db_session.commit()
    result = await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
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
    chart_spec = {"chart_type": "bar", "title": "Sales by Month", "data": [{"month": "Apr", "amount": 100000}], "config": {"y_axis_label": "Amount"}}
    msg = Message(conversation_id=conv.id, role="assistant", content="Here are the sales.", chart=chart_spec)
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    assert msg.chart["chart_type"] == "bar"
    assert msg.chart["data"][0]["amount"] == 100000
