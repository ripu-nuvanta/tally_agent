"""Tally mode switching — toggle between live and mock Tally."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import TallyModeRequest, TallyModeResponse
from backend.tally_bridge.client import TallyClient

router = APIRouter()


@router.get("/tally-mode", response_model=TallyModeResponse)
async def get_tally_mode(
    client: TallyClient = Depends(get_client),
) -> TallyModeResponse:
    return TallyModeResponse(mode="mock" if client.mock_mode else "live")


@router.post("/tally-mode", response_model=TallyModeResponse)
async def set_tally_mode(
    body: TallyModeRequest,
    client: TallyClient = Depends(get_client),
) -> TallyModeResponse:
    client.mock_mode = body.mode == "mock"
    return TallyModeResponse(mode=body.mode)
