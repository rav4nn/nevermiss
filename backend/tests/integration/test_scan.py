from __future__ import annotations

import pytest

from app.core.db import ScanKind, ScanStatus, UserTier


@pytest.mark.asyncio
async def test_scan_endpoints_require_auth(client) -> None:
    response = await client.post("/api/scan/start", json={"kind": "initial"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_scan_status_returns_not_found_when_no_jobs(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory()

    response = await client.get("/api/scan/status", headers=auth_headers(user.id))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_scan_start_rejects_manual_for_free_tier(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory(tier=UserTier.FREE)

    response = await client.post(
        "/api/scan/start",
        json={"kind": "manual"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "TIER_REQUIRED"


@pytest.mark.asyncio
async def test_scan_start_rejects_when_job_already_active(
    client,
    user_factory,
    scan_job_factory,
    auth_headers,
) -> None:
    user = await user_factory(tier=UserTier.PRO)
    await scan_job_factory(user, kind=ScanKind.INITIAL, status=ScanStatus.QUEUED)

    response = await client.post(
        "/api/scan/start",
        json={"kind": "initial"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCAN_IN_PROGRESS"


@pytest.mark.asyncio
async def test_scan_start_requires_gmail_reauth_when_refresh_token_missing(
    client,
    user_factory,
    auth_headers,
) -> None:
    user = await user_factory(refresh_token_enc="")

    response = await client.post(
        "/api/scan/start",
        json={"kind": "initial"},
        headers=auth_headers(user.id),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "GMAIL_REAUTH_REQUIRED"
