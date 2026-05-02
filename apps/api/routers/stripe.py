from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
import stripe as stripe_sdk
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from core.config import settings
from core.dependencies import get_current_user, get_subscription_repository
from models.schemas import CheckoutSessionRequest, CheckoutSessionResponse
from repositories.subscriptions import SubscriptionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    req: CheckoutSessionRequest,
    current_user: dict = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for a one-time purchase."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    price_id = (
        settings.stripe_price_kit_pass if req.product == "kit_pass" else settings.stripe_price_id
    )

    stripe.api_key = settings.stripe_secret_key

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        client_reference_id=current_user["id"],
        metadata={
            "user_id": current_user["id"],
            "product": req.product,
            "season": settings.current_season,
        },
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

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe_sdk.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid payload") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        event_id = event.get("id")
        user_id = session.get("client_reference_id")
        payment_status = session.get("payment_status")
        metadata = session.get("metadata") or {}
        product = metadata.get("product")
        season_raw = metadata.get("season")
        created_epoch = session.get("created", event.get("created"))
        purchased_at = None
        if isinstance(created_epoch, int | float):
            purchased_at = datetime.fromtimestamp(created_epoch, tz=UTC)
        unknown_product_msg = (
            "Unknown or missing Stripe product/season metadata for event %s: product=%s season=%s"
        )
        logger.info(
            (
                "Checkout completed: event_id=%s session_id=%s user_id=%s "
                "payment_status=%s product=%s season=%s"
            ),
            event_id,
            session.get("id"),
            user_id,
            payment_status,
            product,
            season_raw,
        )
        if payment_status != "paid":
            logger.info(
                "Skipping draft pass credit: payment_status=%s for event %s",
                payment_status,
                event_id,
            )
            return {"received": True}
        if user_id:
            if event_id:
                if product == "kit_pass":
                    if season_raw is None:
                        logger.warning(unknown_product_msg, event_id, product, season_raw)
                        return {"received": True}
                    if purchased_at is None:
                        logger.warning(
                            "Missing created timestamp for kit-pass event %s; skipping credit",
                            event_id,
                        )
                        return {"received": True}
                    outcome = repo.credit_kit_pass_for_stripe_event(
                        event_id,
                        user_id,
                        season_raw,
                        purchased_at,
                    )
                    logger.info("Stripe event %s kit pass credit outcome=%s", event_id, outcome)
                elif product == "draft_pass":
                    credited = repo.credit_draft_pass_for_stripe_event(event_id, user_id)
                    logger.info("Stripe event %s draft pass credited=%s", event_id, credited)
                else:
                    logger.warning(unknown_product_msg, event_id, product, season_raw)
            else:
                logger.error(
                    "checkout.session.completed missing event id for user %s; skipping credit",
                    user_id,
                )

    return {"received": True}
