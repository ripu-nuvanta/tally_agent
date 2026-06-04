"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import HealthResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    host: str | None = None,
    port: int = 9000,
    client: TallyClient = Depends(get_client),
) -> HealthResponse:
    """Health check. With host[/port], probes that Tally instance ad hoc
    (used by the per-workspace heartbeat badge); otherwise uses the app client."""
    if host:
        ad_hoc = TallyClient(host, port)
        try:
            connected = await ad_hoc.health_check()
        finally:
            await ad_hoc.close()
        return HealthResponse(
            status="healthy" if connected else "degraded",
            tally_connected=connected,
            tally_url=ad_hoc.base_url,
            mode="live",
        )
    if client.mock_mode:
        return HealthResponse(
            status="healthy",
            tally_connected=True,
            tally_url="mock://bharat-traders",
            mode="mock",
        )
    connected = await client.health_check()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        tally_connected=connected,
        tally_url=client.base_url,
        mode="live",
    )
