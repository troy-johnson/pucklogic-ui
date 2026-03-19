from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class ScoringConfigRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def list_presets(self) -> list[dict[str, Any]]:
        """Return all preset scoring configs (public, no user scoping)."""
        result = self._db.table("scoring_configs").select("*").eq("is_preset", True).execute()
        return result.data

    def list(self, user_id: str) -> list[dict[str, Any]]:
        """Return all presets + this user's custom configs."""
        result = (
            self._db.table("scoring_configs")
            .select("*")
            .or_(f"is_preset.eq.true,user_id.eq.{user_id}")
            .execute()
        )
        return result.data

    def get(self, config_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        """Fetch a scoring config by ID.

        When user_id is provided, restricts results to presets or configs owned
        by that user — preventing access to another user's custom configs.
        """
        query = self._db.table("scoring_configs").select("*").eq("id", config_id)
        if user_id is not None:
            query = query.or_(f"is_preset.eq.true,user_id.eq.{user_id}")
        result = query.maybe_single().execute()
        return result.data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._db.table("scoring_configs").insert(data).execute()
        return result.data[0]
