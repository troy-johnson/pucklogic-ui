"""Sources router — list, custom upload, and delete endpoints."""

from __future__ import annotations

import io
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_db,
    get_source_repository,
)
from models.schemas import CustomSourceOut, SourceOut, UnmatchedPlayer, UploadResponse
from repositories.sources import SourceRepository
from services.cache import CacheService

router = APIRouter(prefix="/sources", tags=["sources"])

FREE_SLOT_LIMIT = 2  # Custom source slots for free users
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


@router.get("", response_model=list[SourceOut])
async def list_sources(
    active_only: bool = True,
    repo: SourceRepository = Depends(get_source_repository),
) -> list[SourceOut]:
    """Return registered ranking sources."""
    rows = repo.list(active_only=active_only)
    return [SourceOut(**row) for row in rows]


@router.get("/custom", response_model=list[CustomSourceOut])
async def list_custom_sources(
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
) -> list[CustomSourceOut]:
    """Return the authenticated user's custom projection sources."""
    rows = repo.list_custom(user_id=user["id"])
    return [CustomSourceOut(**row) for row in rows]


@router.post("/upload", response_model=UploadResponse)
async def upload_custom_source(
    file: UploadFile = File(...),
    source_name: str = Form(...),
    season: str = Form(...),
    column_map: str = Form(..., description="JSON: {their_col: our_stat}"),
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    cache: CacheService = Depends(get_cache_service),
    db: Any = Depends(get_db),
) -> UploadResponse:
    """Upload a CSV or Excel projection file as a custom source.

    - Max 5 MB file size
    - Max 2 custom source slots per user
    - Unmatched players returned in response (not an error)
    - Cache invalidated on success
    """
    # Validate file extension
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 5MB limit")

    # Check slot limit
    slots_used = repo.count_custom(user["id"])
    if slots_used >= FREE_SLOT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Custom source slot limit reached ({FREE_SLOT_LIMIT} slots). "
                "Delete an existing custom source to upload a new one."
            ),
        )

    # Parse column_map JSON
    try:
        col_map: dict[str, str] = json.loads(column_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid column_map JSON: {exc}") from exc

    # Parse file with pandas
    try:
        import pandas as pd

        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    # Upsert source row
    safe_name = source_name.lower().replace(" ", "_")
    internal_name = f"custom_{user['id'][:8]}_{safe_name}"
    source_id = repo.upsert_custom(
        user_id=user["id"],
        source_name=internal_name,
        display_name=source_name,
    )

    # Build player matcher
    from scrapers.matching import PlayerMatcher
    from scrapers.projection import apply_column_map, upsert_projection_row

    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
    matcher = PlayerMatcher(players, aliases)
    player_names = [p["name"] for p in players]

    # Process rows
    from rapidfuzz import fuzz
    from rapidfuzz import process as fuzz_process

    rows_upserted = 0
    unmatched: list[UnmatchedPlayer] = []

    # Determine the player name column: first column not in col_map keys
    player_name_col = next(
        (col for col in df.columns if col not in col_map),
        df.columns[0],
    )

    for row_idx, row in enumerate(df.to_dict("records")):
        player_name = str(row.get(player_name_col, "")).strip()
        if not player_name:
            continue

        player_id = matcher.resolve(player_name)
        if player_id is None:
            closest = fuzz_process.extractOne(
                player_name, player_names, scorer=fuzz.token_sort_ratio
            )
            unmatched.append(
                UnmatchedPlayer(
                    row_number=row_idx + 2,  # +2: 1-indexed + header row
                    original_name=player_name,
                    closest_match=closest[0] if closest else None,
                    match_score=closest[1] if closest else None,
                )
            )
            continue

        stats = apply_column_map({str(k): str(v) for k, v in row.items()}, col_map)
        if stats:
            upsert_projection_row(db, player_id, source_id, season, stats)
            rows_upserted += 1

    cache.invalidate_rankings(season)

    return UploadResponse(
        source_id=source_id,
        rows_upserted=rows_upserted,
        unmatched=unmatched,
        slots_used=slots_used + 1,
    )


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    cache: CacheService = Depends(get_cache_service),
) -> None:
    """Delete a custom source. Only the owning user may delete."""
    deleted = repo.delete_custom(source_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    from core.config import settings

    cache.invalidate_rankings(settings.current_season)
