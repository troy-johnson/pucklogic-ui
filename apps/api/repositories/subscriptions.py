"""Repository for the `subscriptions` table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


class SubscriptionRepository:
    def __init__(self, db: Client) -> None:
        self._db = db

    def upsert(self, user_id: str, plan: str) -> None:
        """Insert or update the subscription row for *user_id*."""
        self._db.table("subscriptions").upsert(
            {"user_id": user_id, "plan": plan},
            on_conflict="user_id",
        ).execute()

    def consume_draft_pass(self, user_id: str, *, now: datetime) -> str:
        """Atomically consume one eligible draft pass and return its subscription id."""
        result = self._db.rpc(
            "consume_draft_pass",
            {"p_user_id": user_id, "p_now": now.astimezone(UTC).isoformat()},
        ).execute()
        rows = result.data or []
        if not rows:
            raise PermissionError("active draft pass required")
        return rows[0]["subscription_id"]

    def restore_draft_pass(self, subscription_id: str) -> None:
        """Restore a previously consumed draft pass when session creation fails."""
        self._db.rpc(
            "restore_draft_pass",
            {"p_subscription_id": subscription_id},
        ).execute()

    def credit_draft_pass_for_stripe_event(self, event_id: str, user_id: str) -> bool:
        """Atomically claim a Stripe event and credit one pass when newly processed."""
        result = self._db.rpc(
            "credit_draft_pass_for_stripe_event",
            {"p_event_id": event_id, "p_user_id": user_id},
        ).execute()
        return bool(result.data)

    def credit_kit_pass_for_stripe_event(self, event_id: str, user_id: str, season: str) -> str:
        """Claim a Stripe event and apply kit-pass credit semantics for the given season.

        Returns an outcome token from the backing RPC, e.g.:
        - "applied"
        - "noop_same_season"
        - "overwrite_newer_season"
        - "stale_earlier_season"
        """
        result = self._db.rpc(
            "credit_kit_pass_for_stripe_event",
            {"p_event_id": event_id, "p_user_id": user_id, "p_season": season},
        ).execute()
        return str(result.data)

    def get_entitlements_state(
        self, user_id: str, current_season: str
    ) -> dict[str, int | bool | str | None]:
        """Return draft-pass balance + kit-pass state from a single row read."""
        result = (
            self._db.table("subscriptions")
            .select("draft_pass_balance, kit_pass_season, kit_pass_purchased_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        if result.data is None:
            return {
                "draft_pass_balance": 0,
                "active": False,
                "season": None,
                "purchased_at": None,
            }

        season = result.data.get("kit_pass_season")
        purchased_at = result.data.get("kit_pass_purchased_at")
        return {
            "draft_pass_balance": result.data.get("draft_pass_balance") or 0,
            "active": bool(season and season == current_season),
            "season": season,
            "purchased_at": purchased_at,
        }

    def get_kit_pass_state(self, user_id: str, current_season: str) -> dict[str, str | bool | None]:
        """Return current kit-pass state for entitlement reads.

        Shape:
            {"active": bool, "season": str | None, "purchased_at": str | None}
        """
        result = (
            self._db.table("subscriptions")
            .select("kit_pass_season, kit_pass_purchased_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return {"active": False, "season": None, "purchased_at": None}

        season = result.data.get("kit_pass_season")
        if season is None:
            return {"active": False, "season": None, "purchased_at": None}

        return {
            "active": season == current_season,
            "season": season,
            "purchased_at": result.data.get("kit_pass_purchased_at"),
        }

    def get_draft_pass_balance(self, user_id: str) -> int:
        """Return the user's current draft pass balance (0 if no row)."""
        result = (
            self._db.table("subscriptions")
            .select("draft_pass_balance")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return 0
        return result.data.get("draft_pass_balance") or 0

    def is_active(self, user_id: str) -> bool:
        """Return True if user_id has an active, non-expired subscription."""
        result = (
            self._db.table("subscriptions")
            .select("status, expires_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return False
        expires_at = result.data.get("expires_at")
        if expires_at is None:
            return True
        return datetime.fromisoformat(expires_at) > datetime.now(UTC)
