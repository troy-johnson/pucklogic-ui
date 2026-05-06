"""Entitlement read service."""

from __future__ import annotations

from core.config import settings
from repositories.subscriptions import SubscriptionRepository


class EntitlementsService:
    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        frontend_url: str | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._frontend_url = frontend_url or settings.frontend_url

    def get_entitlements(self, user_id: str, current_season: str) -> dict:
        state = self._subscription_repo.get_entitlements_state(
            user_id,
            current_season=current_season,
        )
        active = bool(state.get("active"))
        season = state.get("season")
        purchased_at = state.get("purchased_at")
        draft_pass_balance = int(state.get("draft_pass_balance") or 0)

        purchase_url = None
        if not active:
            purchase_url = f"{self._frontend_url}/stripe/create-checkout-session?product=kit_pass"

        return {
            "draft_pass_balance": draft_pass_balance,
            "kit_pass": {
                "active": active,
                "season": season,
                "purchased_at": purchased_at,
                "purchase_url": purchase_url,
            },
        }
