"""Chat endpoint — main conversational interface to the agent pipeline."""

from fastapi import APIRouter, Depends
from opentelemetry import trace

from backend.agents.context import SessionStore
from backend.agents.orchestrator import Orchestrator
from backend.api.dependencies import get_client, get_session_store
from backend.api.models import ChatRequest, ChatResponse, ChartSpec
from backend.tally_bridge.client import TallyClient

router = APIRouter()

# Module-level tracer — creates root spans that Langfuse uses for session grouping.
# Without this, trace.get_current_span() returns a no-op span (FastAPI has no
# built-in OTel instrumentation), so langfuse.session.id was never actually set.
_tracer = trace.get_tracer(__name__)


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

    session_id = request.session_id or session.session_id

    # Create an explicit root span so that:
    # 1. Langfuse reads langfuse.session.id / langfuse.user.id from this root span
    # 2. Anthropic SDK spans (from AnthropicInstrumentor) become children of this
    #    span via OTel context propagation, grouping everything into one trace
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
