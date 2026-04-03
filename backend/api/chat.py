"""Chat endpoint — main conversational interface to the agent pipeline."""

import logging
import time as time_module

from fastapi import APIRouter, Depends, HTTPException
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context import SessionContext, SessionStore
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
    from backend.db.engine import async_session_factory
    from backend.db.models import Conversation, Message, UsageLog, Workspace
    from backend.utils.pricing import compute_cost

    if not request.workspace_id:
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
