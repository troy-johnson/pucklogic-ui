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


class TestHasDraftPass:
    def _chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value  # noqa: E501

    def test_returns_true_when_balance_positive(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = {"draft_pass_balance": 2}
        assert repo.has_draft_pass("user-1") is True

    def test_returns_false_when_balance_zero(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = {"draft_pass_balance": 0}
        assert repo.has_draft_pass("user-1") is False

    def test_returns_false_when_no_row(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._chain(mock_db).data = None
        assert repo.has_draft_pass("user-1") is False


class TestDeductDraftPass:
    def _select_chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value  # noqa: E501

    def test_decrements_balance(self, repo: SubscriptionRepository, mock_db: MagicMock) -> None:
        self._select_chain(mock_db).data = {"id": "sub-1", "draft_pass_balance": 3}

        repo.deduct_draft_pass("user-1")

        update_call = mock_db.table.return_value.update.call_args.args[0]
        assert update_call["draft_pass_balance"] == 2

    def test_raises_when_balance_zero(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._select_chain(mock_db).data = {"id": "sub-1", "draft_pass_balance": 0}

        with pytest.raises(PermissionError, match="active draft pass"):
            repo.deduct_draft_pass("user-1")

    def test_raises_when_no_row(self, repo: SubscriptionRepository, mock_db: MagicMock) -> None:
        self._select_chain(mock_db).data = None

        with pytest.raises(PermissionError, match="active draft pass"):
            repo.deduct_draft_pass("user-1")


class TestCreditDraftPass:
    def _select_chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value  # noqa: E501

    def test_increments_existing_balance(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._select_chain(mock_db).data = {"id": "sub-1", "draft_pass_balance": 1}

        repo.credit_draft_pass("user-1")

        update_call = mock_db.table.return_value.update.call_args.args[0]
        assert update_call["draft_pass_balance"] == 2

    def test_inserts_row_when_none_exists(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._select_chain(mock_db).data = None

        repo.credit_draft_pass("user-1")

        insert_call = mock_db.table.return_value.insert.call_args.args[0]
        assert insert_call["draft_pass_balance"] == 1
        assert insert_call["user_id"] == "user-1"
        assert insert_call["status"] == "active"

    def test_reactivates_existing_inactive_row(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._select_chain(mock_db).data = {"id": "sub-1", "draft_pass_balance": 0}

        repo.credit_draft_pass("user-1")

        update_call = mock_db.table.return_value.update.call_args.args[0]
        assert update_call["status"] == "active"

    def test_clears_expires_at_on_existing_row(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._select_chain(mock_db).data = {"id": "sub-1", "draft_pass_balance": 0}

        repo.credit_draft_pass("user-1")

        update_call = mock_db.table.return_value.update.call_args.args[0]
        assert update_call["expires_at"] is None


class TestStripeEventIdempotency:
    def _upsert_chain(self, mock_db: MagicMock) -> MagicMock:
        return mock_db.table.return_value.upsert.return_value.execute.return_value

    def test_try_mark_returns_true_when_newly_inserted(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._upsert_chain(mock_db).data = [{"event_id": "evt_abc"}]
        assert repo.try_mark_stripe_event_processed("evt_abc") is True

    def test_try_mark_returns_false_when_already_processed(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._upsert_chain(mock_db).data = []
        assert repo.try_mark_stripe_event_processed("evt_abc") is False

    def test_try_mark_uses_stripe_processed_events_table(
        self, repo: SubscriptionRepository, mock_db: MagicMock
    ) -> None:
        self._upsert_chain(mock_db).data = [{"event_id": "evt_abc"}]
        repo.try_mark_stripe_event_processed("evt_abc")
        mock_db.table.assert_called_with("stripe_processed_events")
