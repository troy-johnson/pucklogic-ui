"""Unit tests for entitlement state shaping."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.entitlements import EntitlementsService


def test_returns_active_kit_pass_shape() -> None:
    sub_repo = MagicMock()
    sub_repo.get_kit_pass_state.return_value = {"active": True, "season": 2026}

    service = EntitlementsService(subscription_repo=sub_repo)
    result = service.get_entitlements(user_id="user-1", current_season=2026)

    assert result == {
        "kit_pass": {
            "active": True,
            "season": 2026,
            "purchase_url": None,
        }
    }
    sub_repo.get_kit_pass_state.assert_called_once_with("user-1", current_season=2026)


def test_returns_stale_kit_pass_shape_with_purchase_url() -> None:
    sub_repo = MagicMock()
    sub_repo.get_kit_pass_state.return_value = {"active": False, "season": 2025}

    service = EntitlementsService(
        subscription_repo=sub_repo,
        frontend_url="https://app.example.com",
    )
    result = service.get_entitlements(user_id="user-1", current_season=2026)

    assert result == {
        "kit_pass": {
            "active": False,
            "season": 2025,
            "purchase_url": "https://app.example.com/checkout",
        }
    }


def test_returns_no_pass_shape_with_purchase_url() -> None:
    sub_repo = MagicMock()
    sub_repo.get_kit_pass_state.return_value = {"active": False, "season": None}

    service = EntitlementsService(
        subscription_repo=sub_repo,
        frontend_url="https://app.example.com",
    )
    result = service.get_entitlements(user_id="user-1", current_season=2026)

    assert result == {
        "kit_pass": {
            "active": False,
            "season": None,
            "purchase_url": "https://app.example.com/checkout",
        }
    }
