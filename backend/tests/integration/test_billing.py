from __future__ import annotations

import pytest

from app.integrations import stripe_client


@pytest.mark.asyncio
async def test_checkout_requires_auth(client) -> None:
    response = await client.post("/api/billing/checkout", json={"plan": "monthly"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_checkout_returns_redirect_url(
    client,
    user_factory,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await user_factory()
    monkeypatch.setattr(
        stripe_client,
        "create_checkout_session",
        lambda user_id, plan: f"https://checkout.stripe.test/{plan}/{user_id}",
    )

    response = await client.post(
        "/api/billing/checkout",
        json={"plan": "monthly"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.stripe.test/monthly/")


@pytest.mark.asyncio
async def test_portal_returns_not_found_without_customer(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory()

    response = await client.post("/api/billing/portal", headers=auth_headers(user.id))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_stripe_webhook_rejects_missing_signature(client) -> None:
    response = await client.post("/api/webhook/stripe", content=b"{}")

    assert response.status_code == 400
    assert response.json() == {"error": "Missing stripe-signature header."}
