from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.config import settings
from core.dependencies import get_trends_repository
from models.schemas import TrendsResponse
from repositories.trends import TrendsRepository

router = APIRouter(prefix="/trends", tags=["trends"])


def _get_guarded_repo(request: Request) -> TrendsRepository:
    """Dependency: raise 503 if ML models are not loaded, else return repo.

    FastAPI resolves all Depends() before executing the route function, so
    the model availability check must live inside the dependency — not in
    the route body — to avoid calling get_db() when models are unavailable.
    """
    if request.app.state.models is None:
        raise HTTPException(
            status_code=503,
            detail="Trends model not available for this season",
        )
    return get_trends_repository()


@router.get("", response_model=TrendsResponse)
async def get_trends(
    season: str | None = Query(None, description="Season string, e.g. '2025-26'"),
    repo: TrendsRepository = Depends(_get_guarded_repo),
) -> TrendsResponse:
    """Return pre-computed breakout and regression scores for all skaters.

    Returns HTTP 503 if model artifacts failed to load at startup (deployment
    error — check ml-artifacts bucket in Supabase Storage).

    Returns has_trends=False when model has not been run for this season yet
    (valid pre-training state — not an error).
    """
    resolved_season = season or settings.current_season
    return repo.get_trends(resolved_season)
