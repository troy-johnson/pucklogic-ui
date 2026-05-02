from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from core.config import settings
from core.dependencies import get_current_user, get_entitlements_service
from services.entitlements import EntitlementsService

router = APIRouter(tags=["entitlements"])


@router.get("/entitlements")
async def get_entitlements(
    response: Response,
    current_user: dict = Depends(get_current_user),
    service: EntitlementsService = Depends(get_entitlements_service),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return service.get_entitlements(
        user_id=current_user["id"],
        current_season=settings.current_season,
    )
