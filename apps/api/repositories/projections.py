"""
Projection repository — fetches player_projections rows joined with all
context needed by the aggregation service.

Join shape (each row):
  {
    "player_id": str,
    "season": str,
    "g": int | None, "a": int | None, ... (all stat columns),
    "sources": {
        "name": str,          # machine key e.g. "dobber"
        "default_weight": float | None,
        "is_paid": bool,
        "user_id": str | None,
    },
    "players": {
        "name": str,
        "team": str | None,
        "position": str | None,   # NHL.com canonical
    },
    "player_platform_positions": [{"positions": list[str]}],  # 0 or 1 element
    "schedule_scores": [{"schedule_score": float, "off_night_games": int}],  # 0 or 1
  }
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client

_STAT_COLUMNS = (
    "g, a, plus_minus, pim, ppg, ppa, ppp, shg, sha, shp, "
    "sog, fow, fol, hits, blocks, gp, "
    "gs, w, l, ga, sa, sv, sv_pct, so, otl"
)


class ProjectionRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def get_by_season(
        self,
        season: str,
        platform: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return all projection rows for a season with joined context.

        Filters sources to those visible to user_id:
          - system sources (user_id IS NULL)
          - the requesting user's own custom sources
        Platform is used to join player_platform_positions.
        """
        result = (
            self._db.table("player_projections")
            .select(
                f"player_id, season, {_STAT_COLUMNS}, "
                "sources!inner(name, default_weight, is_paid, user_id), "
                "players!inner(name, team, position), "
                "player_platform_positions(positions), "
                "schedule_scores(schedule_score, off_night_games)"
            )
            .eq("season", season)
            .execute()
        )
        # Privacy filter: RLS on `sources` may not be enforced via the join.
        # Post-query: keep only system sources (user_id IS NULL) or the requesting user's own.
        return [
            row for row in result.data
            if row["sources"]["user_id"] is None
            or row["sources"]["user_id"] == user_id
        ]
