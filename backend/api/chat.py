"""Chat endpoint — main conversational interface to the agent pipeline."""

import logging
import os
import time as time_module
import uuid as uuid_mod
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context import SessionContext, SessionStore
from backend.agents.orchestrator import Orchestrator
from backend.api.dependencies import get_client, get_current_user, get_session_store
from backend.api.models import ChatRequest, ChatResponse, ChartSpec, VoucherActionRequest
from backend.config import settings
from backend.tally_bridge.client import TallyClient

logger = logging.getLogger(__name__)
router = APIRouter()

_tracer = trace.get_tracer(__name__)


async def _get_optional_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield DB session if available, None otherwise."""
    if not settings.db_mode:
        yield None
        return
    from backend.db.engine import get_db
    async for session in get_db():
        yield session


_SAFE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".pdf", ".csv", ".xlsx", ".xls"}


async def _verify_workspace_ownership(
    workspace_id: str, user_id: str, db: AsyncSession,
):
    """Load workspace and verify it belongs to the current user.

    Raises HTTPException(404) if not found or not owned.
    """
    from backend.db.models import Workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == user_id,
            Workspace.is_deleted.is_(False),
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: TallyClient = Depends(get_client),
    session_store: SessionStore = Depends(get_session_store),
    user_id: str = Depends(get_current_user),
    db: AsyncSession | None = Depends(_get_optional_db),
) -> ChatResponse:
    if settings.db_mode:
        return await _chat_db_mode(request, client, user_id, db)
    else:
        return await _chat_legacy_mode(request, client, session_store)


@router.post("/chat/upload", response_model=ChatResponse)
async def chat_with_file(
    file: UploadFile = File(...),
    message: str = Form(default=""),
    workspace_id: str = Form(default=""),
    conversation_id: str = Form(default=""),
    client: TallyClient = Depends(get_client),
    user_id: str = Depends(get_current_user),
    db: AsyncSession | None = Depends(_get_optional_db),
) -> ChatResponse:
    """Upload a document (receipt/invoice) for data entry.

    Validates and saves the file. Task 12 will replace the placeholder
    response with the full data entry pipeline (parse → map → review card).
    """
    from backend.services.document_parser import detect_file_type

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_type = detect_file_type(file.filename, file.content_type or "")
    if file_type == "unsupported":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.filename}",
        )

    # Read and validate size
    contents = await file.read()
    file_size = len(contents)
    max_bytes = settings.FILE_MAX_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large ({file_size} bytes). "
                f"Max: {settings.FILE_MAX_SIZE_MB}MB"
            ),
        )
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # In DB mode, verify workspace ownership before running the pipeline.
    if settings.db_mode:
        if not workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id is required in DB mode")
        if db is None:
            raise HTTPException(status_code=500, detail="Database session not available")
        await _verify_workspace_ownership(workspace_id, user_id, db)

    # Save to local storage — sanitize the extension to a safe whitelist to
    # avoid stashing arbitrary user-supplied suffixes (e.g. ".jpg.php").
    os.makedirs(settings.FILE_STORAGE_PATH, exist_ok=True)
    file_id = str(uuid_mod.uuid4())
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _SAFE_EXTS:
        ext = ""  # no extension is safer than trusting random input
    storage_path = os.path.join(settings.FILE_STORAGE_PATH, f"{file_id}{ext}")
    with open(storage_path, "wb") as f:
        f.write(contents)

    # Run the data entry pipeline via the orchestrator.
    orchestrator = Orchestrator()
    session = SessionContext(session_id=conversation_id or file_id)

    try:
        result = await orchestrator.process_file_upload(
            file_path=storage_path,
            filename=file.filename,
            mime_type=file.content_type or "",
            user_message=message,
            client=client,
            session=session,
            file_id=file_id,
        )
    except HTTPException:
        # Clean up the uploaded file on pipeline failure.
        try:
            os.remove(storage_path)
        except OSError:
            pass
        raise
    except Exception as e:
        # Clean up the uploaded file on pipeline failure.
        try:
            os.remove(storage_path)
        except OSError:
            pass
        logger.exception("Data entry pipeline failed")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    return ChatResponse(
        message=result["message"],
        data=result.get("data"),
        session_id=conversation_id or file_id,
    )


@router.post("/chat/voucher-action", response_model=ChatResponse)
async def voucher_action(
    request: VoucherActionRequest,
    client: TallyClient = Depends(get_client),
    user_id: str = Depends(get_current_user),
    db: AsyncSession | None = Depends(_get_optional_db),
) -> ChatResponse:
    """Handle voucher approve/edit/discard actions from the review card.

    approve/edit both write to Tally (edit means user already modified the
    entry in the EditForm before confirming). discard just acknowledges.
    """
    from backend.tally_bridge.writer import TallyWriter, ValidationError

    entry = request.entry
    session_id = request.session_id

    # In DB mode, verify workspace ownership and prefer the workspace's
    # configured company over the client-supplied value. This prevents a
    # user from targeting another workspace's Tally company.
    if settings.db_mode:
        if not request.workspace_id:
            raise HTTPException(status_code=400, detail="workspace_id is required in DB mode")
        if db is None:
            raise HTTPException(status_code=500, detail="Database session not available")
        workspace = await _verify_workspace_ownership(request.workspace_id, user_id, db)
        ws_config = workspace.config or {}
        company = ws_config.get("tally_company") or workspace.name or "Default"
        # Re-configure TallyClient from workspace config if present.
        if ws_config.get("tally_host"):
            client = TallyClient(
                ws_config["tally_host"],
                ws_config.get("tally_port", 9000),
            )
            if ws_config.get("mock_mode"):
                client.mock_mode = True
    else:
        company = request.company or "Default"

    if request.action == "discard":
        return ChatResponse(
            message="Entry discarded.",
            data={"type": "voucher_discarded", "entry_id": entry.get("id")},
            session_id=session_id,
        )

    # approve and edit both write to Tally
    if request.action in ("approve", "edit"):
        if not settings.TALLY_WRITE_ENABLED:
            return ChatResponse(
                message="Tally write is disabled. Set TALLY_WRITE_ENABLED=true to create vouchers.",
                data={"type": "voucher_error", "entry_id": entry.get("id")},
                session_id=session_id,
            )

        writer = TallyWriter(client=client, company=company)

        # Create new ledger first if the review card marked it as new
        if entry.get("is_new_ledger"):
            ledger_name = entry.get("debit_ledger")
            parent = entry.get("suggested_parent") or "Indirect Expenses"
            if not ledger_name:
                return ChatResponse(
                    message="Cannot create new ledger: debit_ledger is empty.",
                    data={"type": "voucher_error", "entry_id": entry.get("id")},
                    session_id=session_id,
                )
            try:
                ledger_result = await writer.create_ledger(name=ledger_name, parent=parent)
            except Exception as e:
                logger.exception("Failed to create new ledger")
                return ChatResponse(
                    message=f"Failed to create new ledger '{ledger_name}': {e}",
                    data={"type": "voucher_error", "entry_id": entry.get("id")},
                    session_id=session_id,
                )
            if not ledger_result["success"]:
                return ChatResponse(
                    message=(
                        f"Failed to create new ledger '{ledger_name}': "
                        f"{ledger_result.get('error_message', 'Unknown error')}"
                    ),
                    data={"type": "voucher_error", "entry_id": entry.get("id")},
                    session_id=session_id,
                )

        # Create the voucher
        try:
            gst_entries = entry.get("gst_entries") or None
            result = await writer.create_payment_voucher(
                date=entry["date"],
                debit_ledger=entry["debit_ledger"],
                credit_ledger=entry["credit_ledger"],
                amount=entry["amount"],
                narration=entry["narration"],
                gst_entries=gst_entries,
            )
        except ValidationError as e:
            return ChatResponse(
                message=f"Validation failed: {'; '.join(e.errors)}",
                data={"type": "voucher_error", "entry_id": entry.get("id")},
                session_id=session_id,
            )
        except KeyError as e:
            return ChatResponse(
                message=f"Voucher entry is missing required field: {e}",
                data={"type": "voucher_error", "entry_id": entry.get("id")},
                session_id=session_id,
            )

        if result["success"]:
            vch_id = result.get("last_vch_id") or ""
            return ChatResponse(
                message=f"Payment voucher written to Tally successfully. Voucher ID: {vch_id}",
                data={
                    "type": "voucher_written",
                    "entry_id": entry.get("id"),
                    "tally_voucher_id": vch_id,
                },
                session_id=session_id,
            )
        else:
            return ChatResponse(
                message=f"Failed to write to Tally: {result.get('error_message', 'Unknown error')}",
                data={"type": "voucher_error", "entry_id": entry.get("id")},
                session_id=session_id,
            )

    # Should be unreachable thanks to Literal[...] on VoucherActionRequest.action
    raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")


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
    db: AsyncSession | None = None,
) -> ChatResponse:
    """DB-backed conversation flow — used when DATABASE_URL is set."""
    from backend.agents.registry import get_agent
    from backend.db.models import Conversation, Message, UsageLog, Workspace
    from backend.utils.pricing import compute_cost

    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required in DB mode")
    if not request.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required in DB mode")
    if db is None:
        raise HTTPException(status_code=500, detail="Database session not available")

    # Load workspace
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == request.workspace_id,
            Workspace.user_id == user_id,
            Workspace.is_deleted.is_(False),
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
            Conversation.is_deleted.is_(False),
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

        # S1: Wire agent registry to chat — use workspace.agent_type
        agent_class = get_agent(workspace.agent_type)
        agent = agent_class()
        result = await agent.process_query(request.message, client, session)

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

    # S6: Bump conversation.updated_at on new message
    conversation.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return ChatResponse(
        message=result["message"],
        data=result.get("data"),
        chart=chart,
        session_id=str(conversation.id),
    )
