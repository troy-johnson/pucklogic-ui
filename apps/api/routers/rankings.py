from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_league_profile_repository,
    get_projection_repository,
    get_scoring_config_repository,
    get_source_repository,
    get_subscription_repository,
)
from models.schemas import RankedPlayer, RankingsComputeRequest, RankingsComputeResponse
from repositories.league_profiles import LeagueProfileRepository
from repositories.projections import ProjectionRepository
from repositories.scoring_configs import ScoringConfigRepository
from repositories.sources import SourceRepository
from repositories.subscriptions import SubscriptionRepository
from services.cache import CacheService
from services.projections import aggregate_projections

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.post("/compute", response_model=RankingsComputeResponse)
async def compute_rankings(
    req: RankingsComputeRequest,
    user: dict[str, Any] = Depends(get_current_user),
    proj_repo: ProjectionRepository = Depends(get_projection_repository),
    lp_repo: LeagueProfileRepository = Depends(get_league_profile_repository),
    sc_repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
    src_repo: SourceRepository = Depends(get_source_repository),
    sub_repo: SubscriptionRepository = Depends(get_subscription_repository),
    cache: CacheService = Depends(get_cache_service),
) -> RankingsComputeResponse:
    # 1. Cache check
    cached_data = cache.get_rankings(
        req.season,
        req.source_weights,
        req.scoring_config_id,
        req.platform,
        req.league_profile_id,
    )
    if cached_data is not None:
        return RankingsComputeResponse(
            season=req.season,
            computed_at=datetime.now(UTC),
            cached=True,
            rankings=[RankedPlayer(**p) for p in cached_data],
        )

    # 1b. Batch-validate source_weights keys (single DB query)
    source_names = list(req.source_weights.keys())
    sources_by_name = src_repo.get_by_names(source_names)
    for key in source_names:
        source = sources_by_name.get(key)
        if source is None:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")
        if source.get("user_id") is not None and source.get("user_id") != user["id"]:
            raise HTTPException(status_code=400, detail=f"Unknown source key: {key}")

    # 1c. Enforce paid source access
    has_subscription = sub_repo.is_active(user["id"])
    for key, source in sources_by_name.items():
        if source.get("is_paid") and source.get("user_id") is None and not has_subscription:
            raise HTTPException(
                status_code=403,
                detail=f"Source '{key}' requires an active subscription",
            )

    # 2. Fetch scoring config (ownership-scoped)
    sc_row = sc_repo.get(req.scoring_config_id, user_id=user["id"])
    if sc_row is None:
        raise HTTPException(status_code=404, detail="Scoring config not found")
    scoring_config = sc_row["stat_weights"]

    # 3. Optionally fetch league profile for VORP
    league_profile: dict[str, Any] | None = None
    if req.league_profile_id:
        league_profile = lp_repo.get(req.league_profile_id, user["id"])
        if league_profile is None:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this league profile",
            )

    # 4. Fetch projections and run pipeline
    rows = proj_repo.get_by_season(req.season, req.platform, user["id"])
    ranked = aggregate_projections(rows, req.source_weights, scoring_config, league_profile)

    # 5. Cache result
    cache.set_rankings(
        req.season,
        req.source_weights,
        req.scoring_config_id,
        req.platform,
        req.league_profile_id,
        ranked,
    )

    return RankingsComputeResponse(
        season=req.season,
        computed_at=datetime.now(UTC),
        cached=False,
        rankings=[RankedPlayer(**p) for p in ranked],
    )
