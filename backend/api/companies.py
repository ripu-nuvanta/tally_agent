"""Companies endpoint."""

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_client
from backend.api.models import CompaniesResponse, CompanyItem
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.queries.masters import list_companies

router = APIRouter()


@router.get("/companies", response_model=CompaniesResponse)
async def get_companies(
    client: TallyClient = Depends(get_client),
) -> CompaniesResponse:
    companies = await list_companies(client)
    return CompaniesResponse(
        companies=[CompanyItem(name=c.name) for c in companies],
    )
