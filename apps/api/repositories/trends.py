from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from models.schemas import TrendedPlayer, TrendsResponse

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)


def _normalize_position(position: str | None) -> str | None:
    """Normalize legacy/variant position codes to API schema literals.

    API contract allows: C, LW, RW, D, G.
    Data may still contain single-letter wing values (L/R) from legacy sources.
    """
    if not position:
        return None

    p = position.strip().upper()
    if p in {"L", "LW"}:
        return "LW"
    if p in {"R", "RW"}:
        return "RW"
    if p in {"C", "D", "G"}:
        return p
    return None


class TrendsRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def _fetch_all_players(self) -> list[dict[str, Any]]:
        """Fetch all players with pagination (Supabase defaults to 1000 rows)."""
        page_size = 1000
        offset = 0
        rows: list[dict[str, Any]] = []
        while True:
            result = (
                self._db.table("players")
                .select("id, name, position, team")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = result.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return rows

    def _fetch_all_trends(self, season: str) -> list[dict[str, Any]]:
        """Fetch all player_trends rows for a season with pagination."""
        page_size = 1000
        offset = 0
        rows: list[dict[str, Any]] = []
        while True:
            result = (
                self._db.table("player_trends")
                .select(
                    "player_id, breakout_score, regression_risk, confidence, "
                    "shap_values, shap_top3, updated_at"
                )
                .eq("season", season)
                .order("player_id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = result.data or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return rows

    def get_trends(self, season: str) -> TrendsResponse:
        """Return trends for all players for a season.

        Performs two queries and merges in Python to achieve a LEFT JOIN
        (all players, with null scores for those lacking a player_trends row).

        Args:
            season: Season string, e.g. "2025-26".

        Returns:
            TrendsResponse with has_trends=False when no player_trends rows
            exist yet (valid pre-training state).
        """
        players_rows = self._fetch_all_players()
        trends_rows = self._fetch_all_trends(season)

        trends_by_pid: dict[str, dict[str, Any]] = {t["player_id"]: t for t in trends_rows}
        has_trends = bool(trends_rows)
        updated_at: datetime | None = None
        if has_trends:
            latest = max(trends_rows, key=lambda t: t["updated_at"])
            updated_at = datetime.fromisoformat(latest["updated_at"])

        trended: list[TrendedPlayer] = []
        for p in players_rows:
            t = trends_by_pid.get(p["id"])
            trended.append(
                TrendedPlayer(
                    player_id=p["id"],
                    name=p["name"],
                    position=_normalize_position(p.get("position")),
                    team=p.get("team"),
                    breakout_score=t["breakout_score"] if t else None,
                    regression_risk=t["regression_risk"] if t else None,
                    confidence=t["confidence"] if t else None,
                    shap_top3=t.get("shap_top3") if t else None,
                )
            )

        # Sort: breakout_score DESC, nulls last
        trended.sort(
            key=lambda p: (
                p.breakout_score is None,
                -(p.breakout_score or 0.0),
            )
        )

        return TrendsResponse(
            season=season,
            has_trends=has_trends,
            updated_at=updated_at,
            players=trended,
        )
