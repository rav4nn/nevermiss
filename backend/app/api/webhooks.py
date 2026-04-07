from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.db import UserTier, get_db
from app.core.errors import AppError
from app.core.logging import get_logger
from app.integrations import dodo_client
from app.models.user import User

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])
logger = get_logger("api.webhooks")


@router.post("/dodo")
async def dodo_webhook(
    request: Request,
    webhook_id: Annotated[str | None, Header(alias="webhook-id")] = None,
    webhook_timestamp: Annotated[str | None, Header(alias="webhook-timestamp")] = None,
    webhook_signature: Annotated[str | None, Header(alias="webhook-signature")] = None,
) -> JSONResponse:
    """
    Receive and verify DodoPayments webhook events.

    IMPORTANT: request.body() must be called before any JSON parsing.
    Raw bytes are required for HMAC signature verification.
    This endpoint is intentionally excluded from JWT auth.
    """
    if not webhook_id or not webhook_timestamp or not webhook_signature:
        logger.warning("dodo_webhook_missing_headers")
        return JSONResponse(status_code=400, content={"error": "Missing webhook headers."})

    raw_body: bytes = await request.body()

    try:
        dodo_client.verify_webhook_signature(
            payload=raw_body,
            webhook_id=webhook_id,
            webhook_timestamp=webhook_timestamp,
            webhook_signature=webhook_signature,
        )
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    try:
        event = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON payload."})

    event_type: str = event.get("type", "")
    logger.info("dodo_webhook_received", event_type=event_type)

    async for db in get_db():
        try:
            await _handle_event(db, event)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("dodo_webhook_handler_error", event_type=event_type, error=str(exc))

    return JSONResponse(status_code=200, content={"received": True})


async def _handle_event(db, event: dict) -> None:  # type: ignore[type-arg]
    event_type: str = event.get("type", "")
    data: dict = event.get("data", {})  # type: ignore[type-arg]

    if event_type == "subscription.active":
        await _on_subscription_active(db, data)
    elif event_type in ("subscription.cancelled", "subscription.expired"):
        await _on_subscription_ended(db, data)
    else:
        logger.debug("dodo_webhook_unhandled_event", event_type=event_type)


async def _on_subscription_active(db, data: dict) -> None:  # type: ignore[type-arg]
    """
    subscription.active — set tier=pro, store Dodo customer/subscription IDs.
    metadata.user_id is our internal UUID set when creating the checkout session.
    """
    metadata: dict = data.get("metadata", {})  # type: ignore[type-arg]
    user_id_str: str | None = metadata.get("user_id")
    if not user_id_str:
        logger.warning("dodo_subscription_active_missing_user_id")
        return

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        logger.warning("dodo_subscription_active_invalid_user_id", ref=user_id_str)
        return

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        logger.warning("dodo_subscription_active_user_not_found", user_id=user_id_str)
        return

    user.tier = UserTier.PRO
    user.dodo_customer_id = data.get("customer_id")
    user.dodo_subscription_id = data.get("subscription_id")

    logger.info(
        "user_upgraded_to_pro",
        user_id=user_id_str,
        subscription_id=user.dodo_subscription_id,
    )


async def _on_subscription_ended(db, data: dict) -> None:  # type: ignore[type-arg]
    """
    subscription.cancelled / subscription.expired — downgrade to free.
    """
    customer_id: str | None = data.get("customer_id")
    if not customer_id:
        return

    result = await db.execute(select(User).where(User.dodo_customer_id == customer_id))
    user: User | None = result.scalar_one_or_none()
    if not user:
        logger.warning("dodo_subscription_ended_user_not_found", customer_id=customer_id)
        return

    user.tier = UserTier.FREE
    user.dodo_subscription_id = None

    logger.info("user_downgraded_to_free", user_id=str(user.id))
