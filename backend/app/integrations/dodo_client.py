from __future__ import annotations

import base64
import hashlib
import hmac

import httpx

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

logger = get_logger("integrations.dodo")

_BASE_URL = "https://live.dodopayments.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_settings().dodo_api_key}",
        "Content-Type": "application/json",
    }


async def create_checkout_session(user_id: str, user_email: str, plan: str) -> str:
    """
    Create a DodoPayments subscription checkout and return the hosted URL.
    plan must be "monthly" or "yearly".
    """
    settings = get_settings()
    product_id = (
        settings.dodo_product_monthly if plan == "monthly" else settings.dodo_product_yearly
    )

    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=15) as client:
        response = await client.post(
            "/subscriptions",
            headers=_headers(),
            json={
                "product_id": product_id,
                "quantity": 1,
                "customer": {"customer_create": {"email": user_email}},
                "metadata": {"user_id": user_id},
                "payment_link": True,
                "return_url": "https://nevermiss.my/dashboard?checkout=success",
            },
        )

    if response.status_code not in (200, 201):
        logger.error(
            "dodo_checkout_failed",
            status=response.status_code,
            body=response.text[:400],
        )
        raise AppError(ErrorCode.INTERNAL, "Failed to create checkout session.", status_code=500)

    data = response.json()
    url: str | None = data.get("payment_link")
    if not url:
        raise AppError(ErrorCode.INTERNAL, "Dodo did not return a payment link.", status_code=500)

    logger.info("dodo_checkout_created", user_id=user_id, plan=plan)
    return url


async def create_billing_portal_session(dodo_customer_id: str) -> str:
    """
    Create a DodoPayments customer portal session and return the URL.
    """
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=15) as client:
        response = await client.post(
            f"/customers/{dodo_customer_id}/portal-session",
            headers=_headers(),
            json={"return_url": "https://nevermiss.my/settings"},
        )

    if response.status_code not in (200, 201):
        logger.error(
            "dodo_portal_failed",
            status=response.status_code,
            body=response.text[:400],
        )
        raise AppError(ErrorCode.INTERNAL, "Failed to create portal session.", status_code=500)

    data = response.json()
    url: str | None = data.get("url")
    if not url:
        raise AppError(ErrorCode.INTERNAL, "Dodo did not return a portal URL.", status_code=500)

    logger.info("dodo_portal_created", customer_id=dodo_customer_id)
    return url


def verify_webhook_signature(
    payload: bytes,
    webhook_id: str,
    webhook_timestamp: str,
    webhook_signature: str,
) -> None:
    """
    Verify a DodoPayments webhook using the Standard Webhooks HMAC-SHA256 scheme.
    Raises AppError(400) if verification fails.
    """
    settings = get_settings()
    secret = settings.dodo_webhook_secret

    # Standard Webhooks: secret may be prefixed with "whsec_"
    raw_secret = base64.b64decode(secret.removeprefix("whsec_"))
    signed_content = f"{webhook_id}.{webhook_timestamp}.{payload.decode()}".encode()
    expected = base64.b64encode(
        hmac.new(raw_secret, signed_content, hashlib.sha256).digest()
    ).decode()

    # webhook-signature header may contain multiple space-separated sigs: "v1,<base64>"
    valid = any(
        sig.split(",", 1)[1] == expected
        for sig in webhook_signature.split(" ")
        if "," in sig
    )

    if not valid:
        logger.warning("dodo_webhook_signature_invalid")
        raise AppError(ErrorCode.INTERNAL, "Invalid webhook signature.", status_code=400)
