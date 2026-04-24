"""Repository for the `subscriptions` table."""

from __future__ import annotations

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

    def get_subscription_id(self, user_id: str) -> str | None:
        """Return the id of the active subscription row for *user_id*, or None."""
        from datetime import UTC, datetime

        result = (
            self._db.table("subscriptions")
            .select("id, expires_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return None
        expires_at = result.data.get("expires_at")
        if expires_at is not None and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            return None
        return result.data.get("id")

    def has_draft_pass(self, user_id: str) -> bool:
        """Return True if user_id has at least one unconsumed draft pass."""
        result = (
            self._db.table("subscriptions")
            .select("draft_pass_balance")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return False
        return (result.data.get("draft_pass_balance") or 0) > 0

    def deduct_draft_pass(self, user_id: str) -> None:
        """Decrement draft_pass_balance by 1. Raises PermissionError if balance is 0."""
        result = (
            self._db.table("subscriptions")
            .select("id, draft_pass_balance")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None or (result.data.get("draft_pass_balance") or 0) <= 0:
            raise PermissionError("active draft pass required")
        (
            self._db.table("subscriptions")
            .update({"draft_pass_balance": result.data["draft_pass_balance"] - 1})
            .eq("id", result.data["id"])
            .execute()
        )

    def credit_draft_pass(self, user_id: str) -> None:
        """Increment draft_pass_balance by 1, creating the subscription row if needed."""
        result = (
            self._db.table("subscriptions")
            .select("id, draft_pass_balance")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if result.data is None:
            self._db.table("subscriptions").insert(
                {
                    "user_id": user_id,
                    "plan": "draft_pass",
                    "status": "active",
                    "draft_pass_balance": 1,
                }
            ).execute()
        else:
            current = result.data.get("draft_pass_balance") or 0
            (
                self._db.table("subscriptions")
                .update(
                    {
                        "draft_pass_balance": current + 1,
                        "status": "active",
                        "expires_at": None,
                    }
                )
                .eq("id", result.data["id"])
                .execute()
            )

    def try_mark_stripe_event_processed(self, event_id: str) -> bool:
        """Atomically claim a Stripe event. Returns True if newly inserted (credit should proceed).
        Returns False if the event_id was already present (duplicate delivery — skip credit).
        Uses INSERT ON CONFLICT DO NOTHING so concurrent duplicate deliveries cannot both win.
        """
        result = (
            self._db.table("stripe_processed_events")
            .upsert({"event_id": event_id}, on_conflict="event_id", ignore_duplicates=True)
            .execute()
        )
        return bool(result.data)

    def is_active(self, user_id: str) -> bool:
        """Return True if user_id has an active, non-expired subscription."""
        from datetime import UTC, datetime

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
