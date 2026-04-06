from __future__ import annotations

import pytest

from app.api import settings as settings_api


@pytest.mark.asyncio
async def test_get_settings_returns_expected_shape(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory(timezone="Asia/Tokyo")

    response = await client.get("/api/settings", headers=auth_headers(user.id))

    assert response.status_code == 200
    assert response.json() == {
        "tier": "free",
        "hasApiKey": False,
        "timezone": "Asia/Tokyo",
        "digestDayOfWeek": 1,
    }


@pytest.mark.asyncio
async def test_patch_settings_rejects_invalid_timezone(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory()

    response = await client.patch(
        "/api/settings",
        json={"timezone": "Mars/OlympusMons"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_settings_accepts_api_key_when_validator_passes(
    client,
    user_factory,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await user_factory()
    monkeypatch.setattr(settings_api, "_validate_gemini_api_key", lambda api_key: None)

    response = await client.patch(
        "/api/settings",
        json={"apiKey": "gemini-test-key", "digestDayOfWeek": 2},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 200
    assert response.json()["hasApiKey"] is True
    assert response.json()["digestDayOfWeek"] == 2
