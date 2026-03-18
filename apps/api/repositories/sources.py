"""
Source repository — all source data access is isolated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class SourceRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def list(self, active_only: bool = True) -> list[dict[str, Any]]:
        """Return system (non-custom) sources only; never leaks user-owned uploads."""
        query = self._db.table("sources").select("*")
        if active_only:
            query = query.eq("active", True)
        # Restrict to system sources (user_id IS NULL). The backend uses the
        # service-role key which bypasses RLS, so this filter is mandatory.
        query = query.is_("user_id", "null")
        result = query.order("display_name").execute()
        return result.data

    def get(self, source_id: str) -> dict[str, Any] | None:
        result = self._db.table("sources").select("*").eq("id", source_id).maybe_single().execute()
        return result.data

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        result = self._db.table("sources").select("*").eq("name", name).maybe_single().execute()
        return result.data

    def get_by_names(self, names: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch multiple sources by name in a single query.

        Returns a dict mapping source name → source row.
        Names not found in the database are absent from the returned dict.
        """
        if not names:
            return {}
        result = self._db.table("sources").select("*").in_("name", names).execute()
        return {row["name"]: row for row in result.data}

    def list_custom(self, user_id: str) -> list[dict[str, Any]]:
        """Return custom sources owned by user_id, with player projection count."""
        # TODO: N+1 queries below are acceptable at the 2-slot limit but should be
        # replaced with a single JOIN or aggregation query if the limit is raised.
        result = (
            self._db.table("sources")
            .select("id, name, display_name, user_id, active, created_at")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        sources = result.data
        for source in sources:
            count_result = (
                self._db.table("player_projections")
                .select("id", count="exact")
                .eq("source_id", source["id"])
                .execute()
            )
            source["player_count"] = count_result.count or 0
            source["season"] = ""
            if count_result.data:
                season_result = (
                    self._db.table("player_projections")
                    .select("season")
                    .eq("source_id", source["id"])
                    .limit(1)
                    .execute()
                )
                if season_result.data:
                    source["season"] = season_result.data[0]["season"]
        return sources

    def get_seasons_for_source(self, source_id: str) -> list[str]:
        """Return distinct seasons that have projections for this source."""
        result = (
            self._db.table("player_projections")
            .select("season")
            .eq("source_id", source_id)
            .execute()
        )
        seen: set[str] = set()
        seasons: list[str] = []
        for row in result.data:
            s = row["season"]
            if s not in seen:
                seen.add(s)
                seasons.append(s)
        return seasons

    def delete_custom(self, source_id: str, user_id: str) -> bool:
        """Delete a custom source (and cascade player_projections via FK).

        Returns True if a row was deleted, False if not found or not owned by user.
        """
        result = (
            self._db.table("sources").delete().eq("id", source_id).eq("user_id", user_id).execute()
        )
        return bool(result.data)

    def count_custom(self, user_id: str) -> int:
        """Count active custom sources owned by user_id."""
        result = (
            self._db.table("sources")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        return result.count or 0

    def upsert_custom(self, user_id: str, source_name: str, display_name: str) -> str:
        """Create or update a custom source row for user_id. Returns source UUID.

        Conflicts on ``name`` only because the internal name already encodes the
        user ID prefix (``custom_<uid8>_<safe_name>``), making it globally unique
        and matching the existing UNIQUE(name) constraint on the sources table.
        """
        result = (
            self._db.table("sources")
            .upsert(
                {
                    "name": source_name,
                    "display_name": display_name,
                    "user_id": user_id,
                    "is_paid": False,
                    "active": True,
                },
                on_conflict="name",
            )
            .execute()
        )
        return result.data[0]["id"]
