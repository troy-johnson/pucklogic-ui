from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from models.schemas import TrendedPlayer, TrendsResponse

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)


class TrendsRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

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
        players_result = self._db.table("players").select("id, name, position, team").execute()
        trends_result = (
            self._db.table("player_trends")
            .select(
                "player_id, breakout_score, regression_risk, confidence, "
                "shap_values, shap_top3, updated_at"
            )
            .eq("season", season)
            .execute()
        )

        trends_by_pid: dict[str, dict[str, Any]] = {t["player_id"]: t for t in trends_result.data}
        has_trends = bool(trends_result.data)
        updated_at: datetime | None = None
        if has_trends:
            latest = max(trends_result.data, key=lambda t: t["updated_at"])
            updated_at = datetime.fromisoformat(latest["updated_at"])

        trended: list[TrendedPlayer] = []
        for p in players_result.data:
            t = trends_by_pid.get(p["id"])
            trended.append(
                TrendedPlayer(
                    player_id=p["id"],
                    name=p["name"],
                    position=p.get("position"),
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
