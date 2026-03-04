"""Chat endpoint — main conversational interface to the agent pipeline."""

from fastapi import APIRouter, Depends

from backend.agents.context import SessionStore
from backend.agents.orchestrator import Orchestrator
from backend.api.dependencies import get_client, get_session_store
from backend.api.models import ChatRequest, ChatResponse, ChartSpec
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    client: TallyClient = Depends(get_client),
    session_store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    session = session_store.get_or_create(
        session_id=request.session_id,
        company=request.company,
    )

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
