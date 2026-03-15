from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class LeagueProfileRepository:
    def __init__(self, db: "Client") -> None:
        self._db = db

    def list(self, user_id: str) -> list[dict[str, Any]]:
        result = (
            self._db.table("league_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return result.data

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        result = self._db.table("league_profiles").insert(data).execute()
        return result.data[0]

    def get(self, profile_id: str, user_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("league_profiles")
            .select("*")
            .eq("id", profile_id)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None
