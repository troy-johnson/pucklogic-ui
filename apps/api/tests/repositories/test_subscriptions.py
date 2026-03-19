"""Unit tests for SubscriptionRepository."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from repositories.subscriptions import SubscriptionRepository


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_db: MagicMock) -> SubscriptionRepository:
    return SubscriptionRepository(mock_db)


class TestSubscriptionRepositoryUpsert:
    def test_upsert_calls_table_subscriptions(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        repo.upsert(user_id="user-1", plan="draft_kit")
        mock_db.table.assert_called_with("subscriptions")

    def test_upsert_calls_execute(self, repo: SubscriptionRepository, mock_db: MagicMock) -> None:
        repo.upsert(user_id="user-1", plan="draft_kit")
        mock_db.table.return_value.upsert.return_value.execute.assert_called_once()

    def test_upsert_passes_user_id_and_plan(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        repo.upsert(user_id="user-abc", plan="draft_kit")
        upsert_call = mock_db.table.return_value.upsert.call_args
        data = upsert_call.args[0] if upsert_call.args else upsert_call.kwargs.get("json", {})
        assert data["user_id"] == "user-abc"
        assert data["plan"] == "draft_kit"

    def test_upsert_uses_user_id_conflict_target(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        repo.upsert(user_id="user-1", plan="draft_kit")
        upsert_call = mock_db.table.return_value.upsert.call_args
        # on_conflict kwarg should target user_id column
        assert upsert_call.kwargs.get("on_conflict") == "user_id"

    def test_upsert_different_plan(self, repo: SubscriptionRepository, mock_db: MagicMock) -> None:
        repo.upsert(user_id="user-2", plan="premium")
        upsert_call = mock_db.table.return_value.upsert.call_args
        data = upsert_call.args[0] if upsert_call.args else upsert_call.kwargs.get("json", {})
        assert data["plan"] == "premium"


class TestIsActive:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        chain = mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value  # noqa: E501
        return chain

    def test_returns_true_when_active_no_expiry(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = {"status": "active", "expires_at": None}
        assert repo.is_active("user-1") is True

    def test_returns_false_when_no_row(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = None
        assert repo.is_active("user-1") is False

    def test_returns_true_when_expires_in_future(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = {
            "status": "active",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
        assert repo.is_active("user-1") is True

    def test_returns_false_when_expired(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = {
            "status": "active",
            "expires_at": "2000-01-01T00:00:00+00:00",
        }
        assert repo.is_active("user-1") is False

    def test_queries_subscriptions_table(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = None
        repo.is_active("user-1")
        mock_db.table.assert_called_with("subscriptions")
