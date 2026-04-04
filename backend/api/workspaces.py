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
        select(Workspace).where(Workspace.user_id == user_id, Workspace.is_deleted.is_(False))
        .order_by(Workspace.created_at)
    )
    return [
        WorkspaceResponse(
            id=str(ws.id), name=ws.name, agent_type=ws.agent_type,
            config=ws.config, memory=ws.memory,
            created_at=ws.created_at.isoformat(), updated_at=ws.updated_at.isoformat(),
        )
        for ws in result.scalars().all()
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
    workspace_id: str, req: WorkspaceUpdateRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.user_id == user_id,
            Workspace.is_deleted.is_(False),
        )
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
        select(Workspace).where(
            Workspace.id == workspace_id, Workspace.user_id == user_id,
            Workspace.is_deleted.is_(False),
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.is_deleted = True
    await db.commit()
