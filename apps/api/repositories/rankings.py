"""
Rankings repository — fetches per-source player rankings from the DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class RankingsRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def get_by_season(
        self,
        season: str,
        source_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all rankings for a season, optionally filtered to specific sources.

        Each row includes player and source info via join.
        """
        query = (
            self._db.table("player_rankings")
            .select(
                "rank, season, "
                "players!inner(id, name, team, position), "
                "sources!inner(name, display_name)"
            )
            .eq("season", season)
        )
        if source_names:
            query = query.in_("sources.name", source_names)
        result = query.execute()
        return result.data

    def get_sources_for_season(self, season: str) -> list[str]:
        """Return distinct source names that have data for the given season."""
        result = (
            self._db.table("player_rankings")
            .select("sources!inner(name)")
            .eq("season", season)
            .execute()
        )
        seen: set[str] = set()
        names: list[str] = []
        for row in result.data:
            name = row["sources"]["name"]
            if name not in seen:
                seen.add(name)
                names.append(name)
        return names
