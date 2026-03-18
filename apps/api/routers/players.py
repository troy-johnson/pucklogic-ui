from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_player_repository
from models.schemas import PlayerOut
from repositories.players import PlayerRepository

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
async def list_players(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    repo: PlayerRepository = Depends(get_player_repository),
) -> list[PlayerOut]:
    """Return NHL players with optional pagination."""
    rows = repo.list(limit=limit, offset=offset)
    return [PlayerOut(**row) for row in rows]


@router.get("/{player_id}", response_model=PlayerOut)
async def get_player(
    player_id: str,
    repo: PlayerRepository = Depends(get_player_repository),
) -> PlayerOut:
    """Return a single player by UUID."""
    row = repo.get(player_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerOut(**row)
