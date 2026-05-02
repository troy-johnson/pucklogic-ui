"""Tests for core dependency providers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from core import dependencies


def test_get_draft_session_service_is_singleton(monkeypatch) -> None:
    original_service = dependencies._draft_session_service
    dependencies._draft_session_service = None
    monkeypatch.setattr(dependencies, "get_draft_session_repository", lambda: MagicMock())
    monkeypatch.setattr(dependencies, "get_subscription_repository", lambda: MagicMock())
    try:
        first = dependencies.get_draft_session_service()
        second = dependencies.get_draft_session_service()

        assert first is second
    finally:
        dependencies._draft_session_service = original_service


def test_require_kit_pass_allows_active_subscription() -> None:
    sub_repo = MagicMock()
    sub_repo.is_active.return_value = True

    dependencies.require_kit_pass(
        current_user={"id": "user-1", "email": "u@example.com"},
        subscription_repo=sub_repo,
    )

    sub_repo.is_active.assert_called_once_with("user-1")


def test_require_kit_pass_returns_403_when_inactive() -> None:
    sub_repo = MagicMock()
    sub_repo.is_active.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        dependencies.require_kit_pass(
            current_user={"id": "user-1", "email": "u@example.com"},
            subscription_repo=sub_repo,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "active draft pass required"
    sub_repo.is_active.assert_called_once_with("user-1")
