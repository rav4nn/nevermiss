from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.deps import CurrentUser
from app.integrations import stripe_client

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger("api.billing")


class CheckoutRequest(BaseModel):
    plan: Literal["monthly", "yearly"]


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_user: CurrentUser,
) -> CheckoutResponse:
    url = stripe_client.create_checkout_session(
        user_id=str(current_user.id),
        plan=body.plan,
    )
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(current_user: CurrentUser) -> PortalResponse:
    if not current_user.stripe_customer_id:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "No billing account found for this user.",
            status_code=404,
        )

    url = stripe_client.create_billing_portal_session(
        stripe_customer_id=current_user.stripe_customer_id,
    )
    return PortalResponse(url=url)
