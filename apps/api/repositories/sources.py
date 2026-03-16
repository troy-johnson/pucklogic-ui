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
        query = self._db.table("sources").select("*")
        if active_only:
            query = query.eq("active", True)
        result = query.order("display_name").execute()
        return result.data

    def get(self, source_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("sources")
            .select("*")
            .eq("id", source_id)
            .maybe_single()
            .execute()
        )
        return result.data

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        result = (
            self._db.table("sources")
            .select("*")
            .eq("name", name)
            .maybe_single()
            .execute()
        )
        return result.data

    def get_by_names(self, names: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch multiple sources by name in a single query.

        Returns a dict mapping source name → source row.
        Names not found in the database are absent from the returned dict.
        """
        if not names:
            return {}
        result = (
            self._db.table("sources")
            .select("*")
            .in_("name", names)
            .execute()
        )
        return {row["name"]: row for row in result.data}
