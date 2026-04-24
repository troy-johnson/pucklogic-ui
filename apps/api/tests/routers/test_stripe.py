"""Integration tests for POST /stripe/create-checkout-session and /stripe/webhook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.dependencies import get_current_user, get_subscription_repository
from main import app

CHECKOUT_BODY = {
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel",
}

AUTHED_USER = {"id": "user-abc-123", "email": "user@example.com"}


@pytest.fixture
def mock_sub_repo() -> MagicMock:
    repo = MagicMock()
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_sub_repo: MagicMock) -> None:
    app.dependency_overrides[get_subscription_repository] = lambda: mock_sub_repo
    app.dependency_overrides[get_current_user] = lambda: AUTHED_USER
    yield
    app.dependency_overrides.clear()


class TestCreateCheckoutSession:
    def test_returns_503_when_stripe_not_configured(self, client: TestClient) -> None:
        with patch("routers.stripe.settings") as mock_settings:
            mock_settings.stripe_secret_key = ""
            resp = client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY)
        assert resp.status_code == 503

    def test_returns_200_when_configured(self, client: TestClient) -> None:
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"
        mock_session.id = "cs_test_abc"

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_price_id = "price_123"
            mock_stripe.checkout.Session.create.return_value = mock_session
            resp = client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY)

        assert resp.status_code == 200

    def test_returns_401_when_unauthenticated(self, client: TestClient) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        with patch("routers.stripe.settings") as mock_settings:
            mock_settings.stripe_secret_key = "sk_test_123"
            resp = client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY)
        assert resp.status_code == 401

    def test_response_has_checkout_url(self, client: TestClient) -> None:
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"
        mock_session.id = "cs_test_abc"

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_price_id = "price_123"
            mock_stripe.checkout.Session.create.return_value = mock_session
            data = client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY).json()

        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_abc"
        assert data["session_id"] == "cs_test_abc"

    def test_stripe_session_created_with_correct_urls(self, client: TestClient) -> None:
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"
        mock_session.id = "cs_test_abc"

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_price_id = "price_123"
            mock_stripe.checkout.Session.create.return_value = mock_session
            client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY)

        call_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs["success_url"] == CHECKOUT_BODY["success_url"]
        assert call_kwargs["cancel_url"] == CHECKOUT_BODY["cancel_url"]

    def test_stripe_session_always_uses_authed_user_as_client_reference_id(
        self, client: TestClient
    ) -> None:
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_abc"
        mock_session.id = "cs_test_abc"

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_price_id = "price_123"
            mock_stripe.checkout.Session.create.return_value = mock_session
            client.post("/stripe/create-checkout-session", json=CHECKOUT_BODY)

        call_kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs.get("client_reference_id") == AUTHED_USER["id"]


class TestStripeWebhook:
    def test_returns_503_when_webhook_secret_not_configured(self, client: TestClient) -> None:
        with patch("routers.stripe.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = ""
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )
        assert resp.status_code == 503

    def test_returns_400_on_invalid_signature(self, client: TestClient) -> None:
        import stripe as stripe_lib

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.error.SignatureVerificationError = (
                stripe_lib.error.SignatureVerificationError
            )
            mock_stripe.Webhook.construct_event.side_effect = (
                stripe_lib.error.SignatureVerificationError("bad sig", "sig_header")
            )
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "bad"},
            )
        assert resp.status_code == 400

    def test_returns_200_on_valid_event(self, client: TestClient) -> None:
        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "payment_intent.created",
                "data": {"object": {}},
            }
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"received": True}

    def test_webhook_credits_draft_pass_on_checkout_completed(
        self, client: TestClient, mock_sub_repo: MagicMock
    ) -> None:
        mock_sub_repo.credit_draft_pass_for_stripe_event.return_value = True

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "id": "evt_new",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_xyz",
                        "client_reference_id": "user-abc-123",
                    }
                },
            }
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )

        assert resp.status_code == 200
        mock_sub_repo.credit_draft_pass_for_stripe_event.assert_called_once_with(
            "evt_new", "user-abc-123"
        )

    def test_webhook_skips_credit_when_no_client_reference_id(
        self, client: TestClient, mock_sub_repo: MagicMock
    ) -> None:
        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "checkout.session.completed",
                "data": {"object": {"id": "cs_test_xyz"}},  # no client_reference_id
            }
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )

        assert resp.status_code == 200
        mock_sub_repo.credit_draft_pass_for_stripe_event.assert_not_called()

    def test_webhook_ignores_other_event_types(
        self, client: TestClient, mock_sub_repo: MagicMock
    ) -> None:
        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "payment_intent.created",
                "data": {"object": {"client_reference_id": "user-xyz"}},
            }
            client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )

        mock_sub_repo.credit_draft_pass_for_stripe_event.assert_not_called()

    def test_webhook_skips_credit_on_duplicate_event(
        self, client: TestClient, mock_sub_repo: MagicMock
    ) -> None:
        mock_sub_repo.credit_draft_pass_for_stripe_event.return_value = False

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "id": "evt_duplicate",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_xyz",
                        "client_reference_id": "user-abc-123",
                    }
                },
            }
            resp = client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )

        assert resp.status_code == 200
        mock_sub_repo.credit_draft_pass_for_stripe_event.assert_called_once_with(
            "evt_duplicate", "user-abc-123"
        )

    def test_webhook_credits_when_atomic_event_credit_succeeds(
        self, client: TestClient, mock_sub_repo: MagicMock
    ) -> None:
        mock_sub_repo.credit_draft_pass_for_stripe_event.return_value = True

        with (
            patch("routers.stripe.settings") as mock_settings,
            patch("routers.stripe.stripe") as mock_stripe,
        ):
            mock_settings.stripe_secret_key = "sk_test_123"
            mock_settings.stripe_webhook_secret = "whsec_test"
            mock_stripe.Webhook.construct_event.return_value = {
                "id": "evt_new",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_xyz",
                        "client_reference_id": "user-abc-123",
                    }
                },
            }
            client.post(
                "/stripe/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )

        mock_sub_repo.credit_draft_pass_for_stripe_event.assert_called_once_with(
            "evt_new", "user-abc-123"
        )
