from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)

from core.dependencies import get_current_user, get_draft_session_service
from models.schemas import DraftManualPickRequest, DraftSessionStartRequest
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


@router.post("/{session_id}/manual-picks")
async def add_manual_pick(
    session_id: str,
    req: DraftManualPickRequest,
    user: dict[str, Any] = Depends(get_current_user),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> dict[str, Any]:
    try:
        return service.accept_pick(
            session_id=session_id,
            user_id=user["id"],
            pick_number=req.pick_number,
            now=datetime.now(UTC),
            player_id=req.player_id,
            player_name=req.player_name,
            player_lookup=req.player_lookup,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _authenticate_websocket_user(token: str | None) -> dict[str, Any]:
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    return await get_current_user(authorization=f"Bearer {token}")


@router.websocket("/{session_id}/ws")
async def draft_session_ws(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
    service: DraftSessionService = Depends(get_draft_session_service),
) -> None:
    await websocket.accept()

    try:
        user = await _authenticate_websocket_user(token)
        sync_state = service.attach_socket(
            session_id=session_id,
            user_id=user["id"],
            now=datetime.now(UTC),
        )
        await websocket.send_json({"type": "sync_state", "payload": sync_state})
    except (HTTPException, PermissionError, LookupError) as exc:
        message = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await websocket.send_json({"type": "error", "payload": {"message": message}})
        await websocket.close(code=1008)
        return

    while True:
        try:
            message = await websocket.receive_json()
        except WebSocketDisconnect:
            break

        event_type = message.get("type")
        if event_type == "pick":
            payload = message.get("payload") or {}
            pick_number = payload.get("pick_number")
            if not isinstance(pick_number, int) or pick_number < 1:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "message": "pick event requires a positive integer pick_number"
                        },
                    }
                )
                continue

            try:
                result = service.accept_pick(
                    session_id=session_id,
                    user_id=user["id"],
                    pick_number=pick_number,
                    now=datetime.now(UTC),
                    ingestion_mode="auto",
                    player_id=payload.get("player_id"),
                    player_name=payload.get("player_name"),
                    player_lookup=payload.get("player_lookup"),
                )
            except (ValueError, LookupError, PermissionError) as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"message": str(exc)},
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "state_update",
                    "payload": {
                        "status": "pick_received",
                        "session_id": session_id,
                        "pick_number": pick_number,
                        "sync_state": result["sync_state"],
                    },
                }
            )
            continue

        if event_type == "sync_state":
            try:
                sync_state = service.reconnect_sync_state(
                    session_id=session_id,
                    user_id=user["id"],
                    now=datetime.now(UTC),
                )
            except (PermissionError, LookupError) as exc:
                await websocket.send_json({"type": "error", "payload": {"message": str(exc)}})
                continue

            await websocket.send_json({"type": "sync_state", "payload": sync_state})
            continue

        await websocket.send_json(
            {
                "type": "error",
                "payload": {"message": f"unsupported event type: {event_type}"},
            }
        )
