"""
Player repository — all player data access is isolated here.

Routers call methods on this class; nothing outside this module touches
the database client directly. Swapping the underlying DB means changing
only this file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client


class PlayerRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def list(self) -> list[dict[str, Any]]:
        result = self._db.table("players").select("*").execute()
        return result.data

    def get(self, player_id: str) -> dict[str, Any] | None:
        result = (
            self._db.table("players")
            .select("*")
            .eq("id", player_id)
            .maybe_single()
            .execute()
        )
        return result.data
