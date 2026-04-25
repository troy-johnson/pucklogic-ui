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

    def get_subscription_id(self, user_id: str) -> str | None:
        """Return the id of the active subscription row for *user_id*, or None."""
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
            .select("draft_pass_balance, expires_at")
            .eq("user_id", user_id)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )
        if result.data is None:
            return False
        expires_at = result.data.get("expires_at")
        if expires_at is not None and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
            return False
        return (result.data.get("draft_pass_balance") or 0) > 0

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
