from __future__ import annotations

import stripe

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

logger = get_logger("integrations.stripe")


def _client() -> stripe.StripeClient:
    return stripe.StripeClient(api_key=get_settings().stripe_secret_key)


def create_checkout_session(user_id: str, plan: str) -> str:
    """
    Create a Stripe Checkout Session and return the hosted URL.

    plan must be "monthly" or "yearly". Uses PRICE_MONTHLY or PRICE_YEARLY
    env vars. client_reference_id is set to user.id so the webhook can
    resolve the user on checkout.session.completed.
    """
    settings = get_settings()
    price_id = settings.price_monthly if plan == "monthly" else settings.price_yearly

    session = _client().checkout.sessions.create(
        params={
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": user_id,
            "success_url": "https://nevermiss.my/dashboard?checkout=success",
            "cancel_url": "https://nevermiss.my/pricing?checkout=cancelled",
        }
    )

    if not session.url:
        raise AppError(
            ErrorCode.INTERNAL,
            "Stripe did not return a checkout URL.",
            status_code=500,
        )

    logger.info("checkout_session_created", user_id=user_id, plan=plan)
    return session.url


def create_billing_portal_session(stripe_customer_id: str) -> str:
    """
    Create a Stripe Billing Portal session and return the URL.
    """
    session = _client().billing_portal.sessions.create(
        params={
            "customer": stripe_customer_id,
            "return_url": "https://nevermiss.my/settings",
        }
    )

    logger.info("portal_session_created", stripe_customer_id=stripe_customer_id)
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """
    Verify the Stripe webhook signature and return the parsed Event.

    MUST receive the raw request bytes — not a decoded string or dict.
    Raises AppError(INTERNAL, 400) if signature verification fails.
    """
    settings = get_settings()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.stripe_webhook_secret,
        )
    except stripe.SignatureVerificationError as exc:
        logger.warning("stripe_webhook_signature_invalid", error=str(exc))
        raise AppError(
            ErrorCode.INTERNAL,
            "Invalid webhook signature.",
            status_code=400,
        )
    except ValueError as exc:
        logger.warning("stripe_webhook_payload_invalid", error=str(exc))
        raise AppError(
            ErrorCode.INTERNAL,
            "Invalid webhook payload.",
            status_code=400,
        )

    return event
