"""Unit tests for entitlement state shaping."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.entitlements import EntitlementsService


def test_returns_active_kit_pass_shape() -> None:
    sub_repo = MagicMock()
    sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 2,
        "active": True,
        "season": "2026-27",
        "purchased_at": "2026-08-14T19:22:00Z",
    }

    service = EntitlementsService(subscription_repo=sub_repo)
    result = service.get_entitlements(user_id="user-1", current_season="2026-27")

    assert result == {
        "draft_pass_balance": 2,
        "kit_pass": {
            "active": True,
            "season": "2026-27",
            "purchased_at": "2026-08-14T19:22:00Z",
            "purchase_url": None,
        },
    }
    sub_repo.get_entitlements_state.assert_called_once_with("user-1", current_season="2026-27")


def test_returns_stale_kit_pass_shape_with_purchase_url() -> None:
    sub_repo = MagicMock()
    sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": False,
        "season": "2025-26",
        "purchased_at": "2025-08-01T00:00:00Z",
    }

    service = EntitlementsService(
        subscription_repo=sub_repo,
        frontend_url="https://app.example.com",
    )
    result = service.get_entitlements(user_id="user-1", current_season="2026-27")

    assert result == {
        "draft_pass_balance": 0,
        "kit_pass": {
            "active": False,
            "season": "2025-26",
            "purchased_at": "2025-08-01T00:00:00Z",
            "purchase_url": "https://app.example.com/stripe/create-checkout-session?product=kit_pass",
        },
    }


def test_returns_no_pass_shape_with_purchase_url() -> None:
    sub_repo = MagicMock()
    sub_repo.get_entitlements_state.return_value = {
        "draft_pass_balance": 0,
        "active": False,
        "season": None,
        "purchased_at": None,
    }

    service = EntitlementsService(
        subscription_repo=sub_repo,
        frontend_url="https://app.example.com",
    )
    result = service.get_entitlements(user_id="user-1", current_season="2026-27")

    assert result == {
        "draft_pass_balance": 0,
        "kit_pass": {
            "active": False,
            "season": None,
            "purchased_at": None,
            "purchase_url": "https://app.example.com/stripe/create-checkout-session?product=kit_pass",
        },
    }
