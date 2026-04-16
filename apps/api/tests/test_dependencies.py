"""Tests for core dependency providers."""

from __future__ import annotations

from unittest.mock import MagicMock

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
