from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_league_profile_repository, require_kit_pass
from models.schemas import LeagueProfileCreate, LeagueProfileOut
from repositories.league_profiles import LeagueProfileRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/league-profiles", tags=["league-profiles"])


@router.get("", response_model=list[LeagueProfileOut])
async def list_league_profiles(
    user: dict[str, Any] = Depends(get_current_user),
    repo: LeagueProfileRepository = Depends(get_league_profile_repository),
) -> list[LeagueProfileOut]:
    return repo.list(user_id=user["id"])


@router.post("", response_model=LeagueProfileOut, status_code=201)
async def create_league_profile(
    body: LeagueProfileCreate,
    user: dict[str, Any] = Depends(get_current_user),
    repo: LeagueProfileRepository = Depends(get_league_profile_repository),
    _: None = Depends(require_kit_pass),
) -> LeagueProfileOut:
    try:
        row = repo.create({**body.model_dump(), "user_id": user["id"]})
    except Exception as exc:
        logger.exception("Failed to create league profile: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to create league profile")
    return LeagueProfileOut(**row)
