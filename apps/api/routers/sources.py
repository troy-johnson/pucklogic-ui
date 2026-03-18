"""Sources router — list, custom upload, and delete endpoints."""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from rapidfuzz import fuzz
from rapidfuzz import process as fuzz_process

from core.config import settings
from core.dependencies import (
    get_cache_service,
    get_current_user,
    get_db,
    get_source_repository,
    get_subscription_repository,
)
from models.schemas import CustomSourceOut, SourceOut, UnmatchedPlayer, UploadResponse
from repositories.sources import SourceRepository
from repositories.subscriptions import SubscriptionRepository
from scrapers.matching import PlayerMatcher
from scrapers.projection import apply_column_map, upsert_projection_row
from services.cache import CacheService

router = APIRouter(prefix="/sources", tags=["sources"])

FREE_SLOT_LIMIT = 2  # Must match UploadResponse.slots_total in models/schemas.py
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}

_SAFE_NAME_RE = re.compile(r"[^a-z0-9]+")


def _make_safe_name(name: str) -> str:
    """Collapse all non-alphanumeric characters into underscores."""
    return _SAFE_NAME_RE.sub("_", name.lower()).strip("_")


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
    player_name_column: str | None = Form(
        None,
        description="Column containing player names. Defaults to first column not in column_map.",
    ),
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    sub_repo: SubscriptionRepository = Depends(get_subscription_repository),
    cache: CacheService = Depends(get_cache_service),
    db: Any = Depends(get_db),
) -> UploadResponse:
    """Upload a CSV or Excel projection file as a custom source.

    - Max 5 MB file size
    - Max 2 custom source slots per user
    - Paywalled sources require an active subscription
    - Existing projections for (source_id, season) are cleared before reimport
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

    # Derive the internal source name early so we can check whether this is a new upload
    safe_name = _make_safe_name(source_name)
    internal_name = f"custom_{user['id'][:8]}_{safe_name}"
    is_new_source = repo.get_by_name(internal_name) is None

    # Pre-check slot limit (only blocks new sources; re-uploads of existing names are fine)
    slots_used = repo.count_custom(user["id"])
    if is_new_source and slots_used >= FREE_SLOT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Custom source slot limit reached ({FREE_SLOT_LIMIT} slots). "
                "Delete an existing custom source to upload a new one."
            ),
        )

    # Paywalled-source gate: uploading data attributed to a registered paywalled source
    # requires an active PuckLogic subscription.
    registered = repo.get_by_name(safe_name)
    if registered and registered.get("is_paid") and not sub_repo.is_active(user["id"]):
        raise HTTPException(
            status_code=403,
            detail="A paid subscription is required to upload data from paywalled sources.",
        )

    # Parse column_map JSON
    try:
        col_map: dict[str, str] = json.loads(column_map)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid column_map JSON: {exc}") from exc

    # Parse file BEFORE upserting the source row — prevents orphaned rows when the
    # file is malformed or unreadable.
    try:
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        df.columns = [str(c).strip() for c in df.columns]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    # Upsert source row — only reached if the file parsed successfully
    source_id = repo.upsert_custom(
        user_id=user["id"],
        source_name=internal_name,
        display_name=source_name,
    )

    # Post-upsert TOCTOU guard: two concurrent uploads with different names can both
    # pass the pre-check above. Re-counting after the upsert catches that case.
    # A DB-level per-user count constraint would be the definitive fix.
    if is_new_source and repo.count_custom(user["id"]) > FREE_SLOT_LIMIT:
        repo.delete_custom(source_id, user["id"])
        raise HTTPException(
            status_code=400,
            detail=(
                f"Custom source slot limit reached ({FREE_SLOT_LIMIT} slots). "
                "Delete an existing custom source to upload a new one."
            ),
        )

    # Clear stale projections for this source+season so a corrected re-upload
    # doesn't leave rows for players omitted from the new file.
    db.table("player_projections").delete().eq("source_id", source_id).eq(
        "season", season
    ).execute()

    # Build player matcher
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
    matcher = PlayerMatcher(players, aliases)
    player_names = [p["name"] for p in players]

    # Process rows
    rows_upserted = 0
    unmatched: list[UnmatchedPlayer] = []

    # Resolve the player name column. An explicit caller-provided value is used
    # when provided and present in the file; otherwise fall back to the first column
    # not listed in column_map. The fallback can misfire when files include metadata
    # columns (Team, Pos, ID) before the player name — callers should supply
    # player_name_column explicitly for those files.
    if player_name_column and player_name_column in df.columns:
        player_name_col = player_name_column
    else:
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
        slots_used=slots_used + (1 if is_new_source else 0),
    )


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    repo: SourceRepository = Depends(get_source_repository),
    cache: CacheService = Depends(get_cache_service),
) -> None:
    """Delete a custom source. Only the owning user may delete."""
    # Capture seasons before the DELETE cascades and removes player_projections rows.
    seasons = repo.get_seasons_for_source(source_id)
    deleted = repo.delete_custom(source_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    # Invalidate rankings for every season that had projections from this source.
    # Fall back to current_season if the source had no projections yet.
    for season in seasons or [settings.current_season]:
        cache.invalidate_rankings(season)
