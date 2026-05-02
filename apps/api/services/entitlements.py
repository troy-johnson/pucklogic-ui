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

    def get_entitlements(self, user_id: str, current_season: int) -> dict:
        state = self._subscription_repo.get_kit_pass_state(
            user_id,
            current_season=current_season,
        )
        active = bool(state.get("active"))
        season = state.get("season")

        purchase_url = None
        if not active:
            purchase_url = f"{self._frontend_url}/checkout"

        return {
            "kit_pass": {
                "active": active,
                "season": season,
                "purchase_url": purchase_url,
            }
        }
