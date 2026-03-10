"""Standalone smoke-test for Langfuse OTLP tracing.

Run from the project root:
    PYTHONPATH=. uv run python scripts/test_langfuse.py

The script:
  1. Reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_BASE_URL from .env
  2. Configures the OTLPSpanExporter pointing at <LANGFUSE_BASE_URL>/api/public/otel/v1/traces
  3. Creates a TracerProvider with a custom SpanExporter that prints export results
  4. Makes a real Anthropic API call (needs ANTHROPIC_API_KEY)
  5. Force-flushes the provider
  6. Prints whether each span was exported successfully

Typical usage:
    PYTHONPATH=. uv run python scripts/test_langfuse.py
    # then check https://cloud.langfuse.com for a trace named "langfuse-test"
"""

import base64
import logging
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_langfuse")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Load settings from .env (reuse the existing pydantic-settings config)
    # ------------------------------------------------------------------
    from backend.config import settings

    if not settings.LANGFUSE_PUBLIC_KEY:
        logger.error(
            "LANGFUSE_PUBLIC_KEY is not set — add it to .env and retry."
        )
        sys.exit(1)
    if not settings.ANTHROPIC_API_KEY:
        logger.error(
            "ANTHROPIC_API_KEY is not set — add it to .env and retry."
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Build the OTLP exporter
    #    IMPORTANT: the endpoint MUST end with /v1/traces.
    #    OTLPSpanExporter uses the `endpoint` value verbatim (no path appended).
    #    Langfuse returns HTTP 404 for the bare /api/public/otel path.
    # ------------------------------------------------------------------
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        SpanExportResult,
        SpanExporter,
    )
    from opentelemetry.sdk.trace import ReadableSpan
    from typing import Sequence

    auth = base64.b64encode(
        f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    endpoint = f"{settings.LANGFUSE_BASE_URL}/api/public/otel/v1/traces"
    logger.info("OTLP endpoint: %s", endpoint)

    # Wrap OTLPSpanExporter so we can print the result of each export call
    class LoggingExporter(SpanExporter):
        def __init__(self, inner: SpanExporter) -> None:
            self._inner = inner

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            logger.info("Exporting %d span(s) to Langfuse...", len(spans))
            result = self._inner.export(spans)
            if result == SpanExportResult.SUCCESS:
                logger.info("  SUCCESS — spans accepted by Langfuse")
            else:
                logger.error(
                    "  FAILURE — Langfuse rejected the spans "
                    "(check the DEBUG logs above for the HTTP status code)"
                )
            return result

        def shutdown(self) -> None:
            self._inner.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return self._inner.force_flush(timeout_millis)

    otlp_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={"Authorization": f"Basic {auth}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(LoggingExporter(otlp_exporter)))

    # Register as global provider so AnthropicInstrumentor picks it up
    from opentelemetry import trace
    trace.set_tracer_provider(provider)

    # ------------------------------------------------------------------
    # 3. Instrument Anthropic
    # ------------------------------------------------------------------
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    AnthropicInstrumentor().instrument(tracer_provider=provider)
    logger.info("AnthropicInstrumentor active")

    # ------------------------------------------------------------------
    # 4. Make a minimal Anthropic API call to produce a span
    # ------------------------------------------------------------------
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    tracer = trace.get_tracer("langfuse-test")
    with tracer.start_as_current_span("langfuse-test") as root_span:
        logger.info("Sending test message to Anthropic...")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{"role": "user", "content": "Say 'Langfuse tracing works!' and nothing else."}],
        )
        answer = response.content[0].text if response.content else "(empty)"
        logger.info("Anthropic replied: %s", answer)
        root_span.set_attribute("test.answer", answer)

    # ------------------------------------------------------------------
    # 5. Flush — BatchSpanProcessor batches spans and exports periodically.
    #    force_flush ensures all pending spans are exported before exit.
    # ------------------------------------------------------------------
    logger.info("Flushing provider...")
    provider.force_flush(timeout_millis=10_000)
    provider.shutdown()
    logger.info(
        "Done. Check https://cloud.langfuse.com (or your self-hosted instance) "
        "for a trace named 'langfuse-test'."
    )


if __name__ == "__main__":
    main()
