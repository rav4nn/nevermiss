from __future__ import annotations

import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import UserTier, get_db
from app.core.errors import AppError
from app.core.logging import get_logger
from app.integrations import stripe_client
from app.models.user import User

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])
logger = get_logger("api.webhooks")


async def _get_db_session() -> AsyncSession:
    async for session in get_db():
        return session
    raise RuntimeError("Could not obtain DB session")  # pragma: no cover


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
) -> JSONResponse:
    """
    Receive and verify Stripe webhook events.

    IMPORTANT: request.body() must be called before any JSON parsing.
    The raw bytes are required for HMAC signature verification.
    This endpoint is intentionally excluded from JWT auth.
    """
    if not stripe_signature:
        logger.warning("stripe_webhook_missing_signature")
        return JSONResponse(status_code=400, content={"error": "Missing stripe-signature header."})

    # Read raw bytes — must happen before any JSON decode
    raw_body: bytes = await request.body()

    try:
        event = stripe_client.construct_webhook_event(
            payload=raw_body,
            sig_header=stripe_signature,
        )
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    event_type: str = event["type"]
    logger.info("stripe_webhook_received", event_type=event_type, event_id=event["id"])

    async for db in get_db():
        try:
            await _handle_event(db, event)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("stripe_webhook_handler_error", event_type=event_type, error=str(exc))
            # Return 200 so Stripe does not retry events we received but failed to process.
            # Failed events should be investigated via Stripe dashboard.

    return JSONResponse(status_code=200, content={"received": True})


async def _handle_event(db: AsyncSession, event: stripe.Event) -> None:
    event_type: str = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _on_checkout_completed(db, data)
    elif event_type == "customer.subscription.updated":
        await _on_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        await _on_subscription_deleted(db, data)
    else:
        logger.debug("stripe_webhook_unhandled_event", event_type=event_type)


async def _on_checkout_completed(db: AsyncSession, session: dict) -> None:  # type: ignore[type-arg]
    """
    checkout.session.completed — set tier=pro, store stripe IDs.

    client_reference_id is our internal user UUID, set when creating the session.
    """
    client_ref: str | None = session.get("client_reference_id")
    if not client_ref:
        logger.warning("checkout_completed_missing_client_reference_id")
        return

    try:
        user_id = uuid.UUID(client_ref)
    except ValueError:
        logger.warning("checkout_completed_invalid_client_reference_id", ref=client_ref)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        logger.warning("checkout_completed_user_not_found", user_id=str(user_id))
        return

    user.tier = UserTier.PRO
    user.stripe_customer_id = session.get("customer")
    user.stripe_subscription_id = session.get("subscription")

    logger.info(
        "user_upgraded_to_pro",
        user_id=str(user_id),
        subscription_id=user.stripe_subscription_id,
    )


async def _on_subscription_updated(db: AsyncSession, subscription: dict) -> None:  # type: ignore[type-arg]
    """
    customer.subscription.updated — sync subscription ID.
    """
    customer_id: str | None = subscription.get("customer")
    subscription_id: str | None = subscription.get("id")
    if not customer_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        logger.warning("subscription_updated_user_not_found", customer_id=customer_id)
        return

    user.stripe_subscription_id = subscription_id
    logger.info("subscription_updated", user_id=str(user.id), subscription_id=subscription_id)


async def _on_subscription_deleted(db: AsyncSession, subscription: dict) -> None:  # type: ignore[type-arg]
    """
    customer.subscription.deleted — downgrade to free, clear subscription ID.
    """
    customer_id: str | None = subscription.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user: User | None = result.scalar_one_or_none()
    if not user:
        logger.warning("subscription_deleted_user_not_found", customer_id=customer_id)
        return

    user.tier = UserTier.FREE
    user.stripe_subscription_id = None

    logger.info("user_downgraded_to_free", user_id=str(user.id))
