from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_rankings_repository,
)
from models.schemas import RankedPlayer, RankingsComputeRequest, RankingsComputeResponse
from repositories.rankings import RankingsRepository
from services.cache import CacheService
from services.rankings import compute_weighted_rankings, flatten_db_rankings

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.post("/compute", response_model=RankingsComputeResponse)
async def compute_rankings(
    req: RankingsComputeRequest,
    user: dict[str, Any] = Depends(get_current_user),
    repo: RankingsRepository = Depends(get_rankings_repository),
    cache: CacheService = Depends(get_cache_service),
) -> RankingsComputeResponse:
    """Compute composite rankings for a season using user-defined source weights.

    Results are cached in Redis for 6 hours. Identical (season, weights) pairs
    return the cached result without hitting the database.
    """
    cached_data = cache.get_rankings(req.season, req.weights)
    if cached_data is not None:
        return RankingsComputeResponse(
            season=req.season,
            computed_at=datetime.now(UTC),
            cached=True,
            rankings=[RankedPlayer(**p) for p in cached_data],
        )

    rows = repo.get_by_season(req.season)
    source_rankings = flatten_db_rankings(rows)
    ranked = compute_weighted_rankings(source_rankings, req.weights)
    cache.set_rankings(req.season, req.weights, ranked)

    return RankingsComputeResponse(
        season=req.season,
        computed_at=datetime.now(UTC),
        cached=False,
        rankings=[RankedPlayer(**p) for p in ranked],
    )
