from fastapi import APIRouter, Depends

from core.dependencies import get_source_repository
from models.schemas import SourceOut
from repositories.sources import SourceRepository

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
async def list_sources(
    active_only: bool = True,
    repo: SourceRepository = Depends(get_source_repository),
) -> list[SourceOut]:
    """Return registered ranking sources."""
    rows = repo.list(active_only=active_only)
    return [SourceOut(**row) for row in rows]
