from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class ScoringConfigRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def list(self, user_id: str) -> list[dict[str, Any]]:
        """Return all presets + this user's custom configs."""
        result = (
            self._db.table("scoring_configs")
            .select("*")
            .or_(f"is_preset.eq.true,user_id.eq.{user_id}")
            .execute()
        )
        return result.data

    def get(self, config_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("scoring_configs")
            .select("*")
            .eq("id", config_id)
            .maybe_single()
            .execute()
        )
        return result.data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._db.table("scoring_configs").insert(data).execute()
        return result.data[0]
