"""Usage aggregation endpoint for billing/dashboard."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
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
    """Get aggregated usage data for the current user.

    Query parameters:
    - from_date: Filter logs from this date (inclusive)
    - to_date: Filter logs until this date (inclusive)
    - workspace_id: Filter by workspace UUID

    Returns:
    - total_input_tokens: Sum of input tokens across all logs
    - total_output_tokens: Sum of output tokens across all logs
    - total_cost_usd: Sum of costs with 6 decimal precision
    - by_workspace: List of {workspace_id, name, cost_usd, message_count}
    - by_day: List of {date, cost_usd, message_count}, sorted chronologically
    """
    query = select(UsageLog).where(UsageLog.user_id == user_id)

    if from_date:
        query = query.where(
            UsageLog.created_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
        )
    if to_date:
        query = query.where(
            UsageLog.created_at <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc)
        )
    if workspace_id:
        query = query.where(UsageLog.workspace_id == workspace_id)

    result = await db.execute(query)
    logs = result.scalars().all()

    # Aggregate totals
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

    # Enrich with workspace names
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
