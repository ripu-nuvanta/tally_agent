"""Conversation CRUD and message retrieval endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.dependencies import get_current_user
from backend.api.models import (
    ConversationCreateRequest, ConversationDetailResponse,
    ConversationSummaryResponse, ConversationUpdateRequest, MessageResponse,
)
from backend.db.engine import get_db
from backend.db.models import Conversation, Message, Workspace

router = APIRouter(prefix="/workspaces/{workspace_id}/conversations", tags=["conversations"])


async def _verify_workspace_access(workspace_id: str, user_id: str, db: AsyncSession) -> Workspace:
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.user_id == user_id, Workspace.is_deleted.is_(False),
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
        select(Conversation).where(
            Conversation.workspace_id == workspace_id, Conversation.user_id == user_id,
            Conversation.is_deleted.is_(False),
        ).order_by(Conversation.updated_at.desc())
    )
    return [
        ConversationSummaryResponse(
            id=str(c.id), title=c.title, tag=c.tag,
            created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
        )
        for c in result.scalars().all()
    ]


@router.post("", response_model=ConversationSummaryResponse, status_code=201)
async def create_conversation(
    workspace_id: str, req: ConversationCreateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    await _verify_workspace_access(workspace_id, user_id, db)
    conv = Conversation(user_id=user_id, workspace_id=workspace_id, title=req.title, tag=req.tag)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationSummaryResponse(
        id=str(conv.id), title=conv.title, tag=conv.tag,
        created_at=conv.created_at.isoformat(), updated_at=conv.updated_at.isoformat(),
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    workspace_id: str, conversation_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    await _verify_workspace_access(workspace_id, user_id, db)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id, Conversation.is_deleted.is_(False),
        ).options(selectinload(Conversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailResponse(
        id=str(conv.id), title=conv.title, tag=conv.tag,
        messages=[
            MessageResponse(
                id=str(m.id), role=m.role, content=m.content,
                data=m.data, chart=m.chart, created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
async def update_conversation(
    workspace_id: str, conversation_id: str, req: ConversationUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSummaryResponse:
    await _verify_workspace_access(workspace_id, user_id, db)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id, Conversation.is_deleted.is_(False),
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
    workspace_id: str, conversation_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _verify_workspace_access(workspace_id, user_id, db)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.workspace_id == workspace_id,
            Conversation.user_id == user_id, Conversation.is_deleted.is_(False),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.is_deleted = True
    await db.commit()
