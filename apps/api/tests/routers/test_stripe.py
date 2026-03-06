"""Integration tests for POST /stripe/create-checkout-session and /stripe/webhook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

CHECKOUT_BODY = {
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel",
}


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
            data = client.post(
                "/stripe/create-checkout-session", json=CHECKOUT_BODY
            ).json()

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


class TestStripeWebhook:
    def test_returns_503_when_webhook_secret_not_configured(
        self, client: TestClient
    ) -> None:
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
