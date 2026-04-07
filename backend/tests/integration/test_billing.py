from __future__ import annotations

import pytest

from app.integrations import dodo_client


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
        dodo_client,
        "create_checkout_session",
        lambda user_id, user_email, plan: f"https://checkout.dodo.test/{plan}/{user_id}",
    )

    response = await client.post(
        "/api/billing/checkout",
        json={"plan": "monthly"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.dodo.test/monthly/")


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
async def test_dodo_webhook_rejects_missing_headers(client) -> None:
    response = await client.post("/api/webhook/dodo", content=b"{}")

    assert response.status_code == 400
    assert response.json() == {"error": "Missing webhook headers."}
