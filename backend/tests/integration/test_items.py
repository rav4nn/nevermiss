from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.db import ItemCategory
from app.services import items as items_service


@pytest.mark.asyncio
async def test_list_items_returns_owned_items(
    client,
    user_factory,
    item_factory,
    auth_headers,
) -> None:
    user = await user_factory()
    await item_factory(user, name="Canva Pro", category=ItemCategory.SUBSCRIPTION)

    response = await client.get("/api/items", headers=auth_headers(user.id))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Canva Pro"


@pytest.mark.asyncio
async def test_dismiss_item_forbidden_for_other_user(
    client,
    user_factory,
    item_factory,
    auth_headers,
) -> None:
    owner = await user_factory()
    other_user = await user_factory()
    item = await item_factory(owner)

    response = await client.post(
        f"/api/items/{item.id}/dismiss",
        headers=auth_headers(other_user.id),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_export_item_returns_calendar_response(
    client,
    user_factory,
    item_factory,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await user_factory()
    item = await item_factory(user, expiry_date=date.today() + timedelta(days=5))

    monkeypatch.setattr(
        items_service,
        "insert_calendar_event",
        lambda _user, _item: {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"},
    )

    response = await client.post(
        f"/api/items/{item.id}/export",
        headers=auth_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json() == {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"}


@pytest.mark.asyncio
async def test_export_item_returns_not_found_for_missing_item(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory()

    response = await client.post(
        "/api/items/11111111-1111-1111-1111-111111111111/export",
        headers=auth_headers(user.id),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
