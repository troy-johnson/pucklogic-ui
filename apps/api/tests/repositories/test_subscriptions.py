"""Unit tests for SubscriptionRepository."""

from __future__ import annotations

from datetime import UTC, datetime
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


class TestConsumeDraftPass:
    def _rpc_chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.rpc.return_value.execute.return_value

    def test_returns_subscription_id_when_pass_consumed(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        now = datetime(2026, 4, 24, tzinfo=UTC)
        self._rpc_chain(mock_db).data = [{"subscription_id": "sub-1"}]

        subscription_id = repo.consume_draft_pass("user-1", now=now)

        assert subscription_id == "sub-1"
        mock_db.rpc.assert_called_once_with(
            "consume_draft_pass",
            {"p_user_id": "user-1", "p_now": now.astimezone(UTC).isoformat()},
        )

    def test_raises_when_no_eligible_pass_exists(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._rpc_chain(mock_db).data = []

        with pytest.raises(PermissionError, match="active draft pass"):
            repo.consume_draft_pass("user-1", now=datetime.now(UTC))


class TestRestoreDraftPass:
    def test_calls_restore_rpc_with_subscription_id(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        repo.restore_draft_pass("sub-1")

        mock_db.rpc.assert_called_once_with(
            "restore_draft_pass",
            {"p_subscription_id": "sub-1"},
        )
        mock_db.rpc.return_value.execute.assert_called_once()


class TestCreditDraftPassForStripeEvent:
    def _rpc_chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.rpc.return_value.execute.return_value

    def test_returns_true_when_event_credit_applied(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._rpc_chain(mock_db).data = True

        assert repo.credit_draft_pass_for_stripe_event("evt_1", "user-1") is True
        mock_db.rpc.assert_called_once_with(
            "credit_draft_pass_for_stripe_event",
            {"p_event_id": "evt_1", "p_user_id": "user-1"},
        )

    def test_returns_false_when_event_already_processed(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._rpc_chain(mock_db).data = False

        assert repo.credit_draft_pass_for_stripe_event("evt_1", "user-1") is False
