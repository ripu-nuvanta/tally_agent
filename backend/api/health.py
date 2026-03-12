"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import HealthResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(client: TallyClient = Depends(get_client)) -> HealthResponse:
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
    )
