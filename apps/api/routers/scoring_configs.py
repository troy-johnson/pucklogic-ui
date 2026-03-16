from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, get_scoring_config_repository
from models.schemas import ScoringConfigCreate, ScoringConfigOut
from repositories.scoring_configs import ScoringConfigRepository
from services.scoring_validation import validate_scoring_config

router = APIRouter(prefix="/scoring-configs", tags=["scoring-configs"])


@router.get("/presets", response_model=list[ScoringConfigOut])
async def list_preset_scoring_configs(
    repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
) -> list[ScoringConfigOut]:
    """Return all preset scoring configs. Public — no authentication required."""
    return [ScoringConfigOut(**row) for row in repo.list_presets()]


@router.get("", response_model=list[ScoringConfigOut])
async def list_scoring_configs(
    user: dict[str, Any] = Depends(get_current_user),
    repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
) -> list[ScoringConfigOut]:
    return repo.list(user_id=user["id"])


@router.post("", response_model=ScoringConfigOut, status_code=201)
async def create_scoring_config(
    body: ScoringConfigCreate,
    user: dict[str, Any] = Depends(get_current_user),
    repo: ScoringConfigRepository = Depends(get_scoring_config_repository),
) -> ScoringConfigOut:
    try:
        validate_scoring_config(body.stat_weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row = repo.create({
        **body.model_dump(),
        "user_id": user["id"],
        "is_preset": False,
    })
    return ScoringConfigOut(**row)
