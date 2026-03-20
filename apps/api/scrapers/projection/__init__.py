# apps/api/scrapers/projection/__init__.py
"""
Shared helpers for projection scrapers.

Each projection scraper calls these helpers rather than duplicating
DB interaction logic.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def upsert_source(
    db: Any,
    source_name: str,
    display_name: str,
    is_paid: bool = False,
) -> str:
    """Get or create a source row; return the source UUID."""
    result = (
        db.table("sources")
        .upsert(
            {
                "name": source_name,
                "display_name": display_name,
                "active": True,
                "is_paid": is_paid,
            },
            on_conflict="name",
        )
        .execute()
    )
    return result.data[0]["id"]


def fetch_players_and_aliases(db: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (players, aliases) for building a PlayerMatcher."""
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
    return players, aliases


def upsert_projection_row(
    db: Any,
    player_id: str,
    source_id: str,
    season: str,
    stats: dict[str, Any],
) -> None:
    """Upsert a single player_projections row.

    ``stats`` should only contain non-None values — callers should strip
    None-valued keys before calling this function.
    """
    db.table("player_projections").upsert(
        {"player_id": player_id, "source_id": source_id, "season": season, **stats},
        on_conflict="player_id,source_id,season",
    ).execute()


def log_unmatched(db: Any, source_name: str, raw_name: str, season: str) -> None:
    """Insert a scraper_logs row for a player name that could not be matched."""
    try:
        db.table("scraper_logs").insert(
            {
                "source": source_name,
                "event": "unmatched_player",
                "detail": f"season={season} raw_name={raw_name!r}",
            }
        ).execute()
    except Exception as exc:
        logger.warning("Failed to log unmatched player %r: %s", raw_name, exc)


def update_last_successful_scrape(db: Any, source_id: str) -> None:
    """Stamp sources.last_successful_scrape with the current UTC time."""
    now = datetime.now(UTC).isoformat()
    db.table("sources").update({"last_successful_scrape": now}).eq("id", source_id).execute()


def apply_column_map(
    raw_row: dict[str, str],
    column_map: dict[str, str],
) -> dict[str, Any]:
    """Map raw column headers to stat schema using column_map.

    Only maps columns present in column_map; everything else is dropped.
    Values that are empty strings, "-", or "N/A" are treated as None.
    """
    MISSING = {"", "-", "n/a", "na", "—"}
    result: dict[str, Any] = {}
    for raw_col, stat_key in column_map.items():
        val = raw_row.get(raw_col)
        if val is None:
            continue
        cleaned = str(val).strip().lower()
        if cleaned in MISSING:
            result[stat_key] = None
        else:
            try:
                # Most stats are integers; sv_pct is float
                result[stat_key] = float(val) if stat_key == "sv_pct" else int(float(val))
            except (ValueError, TypeError):
                result[stat_key] = None
    # Strip None values — null stat means "not projected"
    return {k: v for k, v in result.items() if v is not None}
