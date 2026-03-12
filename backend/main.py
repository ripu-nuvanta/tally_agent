"""FastAPI application — main entry point for the TallyPrime AI Agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from backend.config import settings

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agents.context import SessionStore
from backend.api import chat, companies, health, reports, tally_mode
from backend.api.models import ErrorResponse
from backend.config import settings
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tally_client = TallyClient(settings.TALLY_HOST, settings.TALLY_PORT)
    app.state.tally_client.mock_mode = settings.TALLY_MODE == "mock"
    app.state.session_store = SessionStore(ttl_minutes=settings.SESSION_TTL_MINUTES)
    if settings.LANGFUSE_PUBLIC_KEY:
        import base64

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        auth = base64.b64encode(
            f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()
        ).decode()
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.LANGFUSE_BASE_URL}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}"},
        )
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))

        from opentelemetry import trace
        trace.set_tracer_provider(provider)

        AnthropicInstrumentor().instrument(tracer_provider=provider)
        app.state.tracer_provider = provider
        logger.info("Langfuse instrumentation enabled (OTLP → %s)", settings.LANGFUSE_BASE_URL)
    yield
    if hasattr(app.state, "tracer_provider"):
        app.state.tracer_provider.shutdown()
    await app.state.tally_client.close()


app = FastAPI(
    title="TallyPrime AI Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(tally_mode.router, prefix="/api")


@app.exception_handler(TallyConnectionError)
async def tally_connection_error_handler(
    request: Request, exc: TallyConnectionError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(error=str(exc)).model_dump(),
    )


@app.exception_handler(TallyResponseError)
async def tally_response_error_handler(
    request: Request, exc: TallyResponseError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(error=str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="Internal server error").model_dump(),
    )
