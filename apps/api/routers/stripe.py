from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from core.config import settings
from core.dependencies import get_subscription_repository
from models.schemas import CheckoutSessionRequest, CheckoutSessionResponse
from repositories.subscriptions import SubscriptionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    req: CheckoutSessionRequest,
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for a one-time draft-kit purchase."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe.api_key = settings.stripe_secret_key

    extra: dict = {}
    if req.user_id:
        extra["client_reference_id"] = req.user_id

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        **extra,
    )
    return CheckoutSessionResponse(checkout_url=session.url, session_id=session.id)


@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    repo: SubscriptionRepository = Depends(get_subscription_repository),
) -> dict:
    """Handle Stripe webhook events (signature-verified)."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook not configured")

    stripe.api_key = settings.stripe_secret_key
    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        logger.info(
            "Checkout completed: session_id=%s user_id=%s",
            session.get("id"),
            user_id,
        )
        if user_id:
            repo.credit_draft_pass(user_id)

    return {"received": True}
