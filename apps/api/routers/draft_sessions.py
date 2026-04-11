from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from core.dependencies import get_current_user, get_draft_session_service
from models.schemas import DraftSessionStartRequest
from services.draft_sessions import DraftSessionService

router = APIRouter(prefix="/draft-sessions", tags=["draft-sessions"])


@router.post("/start")
async def start_draft_session(
    req: DraftSessionStartRequest,
    user: dict[str, Any] = Depends(get_current_user),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> dict[str, Any]:
    try:
        return service.start_session(
            user_id=user["id"],
            platform=req.platform,
            now=datetime.now(UTC),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{session_id}/resume")
async def resume_draft_session(
    session_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> dict[str, Any]:
    try:
        return service.resume_session(
            session_id=session_id,
            user_id=user["id"],
            now=datetime.now(UTC),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/end", status_code=204)
async def end_draft_session(
    session_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> Response:
    try:
        service.end_session(
            session_id=session_id,
            user_id=user["id"],
            now=datetime.now(UTC),
        )
        return Response(status_code=204)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/sync-state")
async def get_sync_state(
    session_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> dict[str, Any]:
    try:
        return service.get_sync_state(
            session_id=session_id,
            user_id=user["id"],
            now=datetime.now(UTC),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
