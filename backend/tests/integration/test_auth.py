from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.user import User


@pytest.mark.asyncio
async def test_post_auth_session_creates_user(client, integration_sessionmaker) -> None:
    response = await client.post(
        "/api/auth/session",
        json={
            "googleSub": "google-sub-auth-create",
            "email": "auth-create@example.com",
            "gmailAddress": "auth-create@gmail.com",
            "refreshToken": "refresh-token",
            "accessToken": "access-token",
            "accessTokenExpiresAt": "2026-04-06T12:00:00Z",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "auth-create@example.com"
    assert body["gmailAddress"] == "auth-create@gmail.com"

    async with integration_sessionmaker() as session:
        result = await session.execute(
            select(User).where(User.google_sub == "google-sub-auth-create")
        )
        user = result.scalar_one()
        assert user.refresh_token_enc != "refresh-token"
        assert user.access_token_enc != "access-token"


@pytest.mark.asyncio
async def test_post_auth_session_updates_existing_user(client, integration_sessionmaker) -> None:
    first_payload = {
        "googleSub": "google-sub-auth-update",
        "email": "before@example.com",
        "gmailAddress": "before@gmail.com",
        "refreshToken": "refresh-before",
        "accessToken": "access-before",
        "accessTokenExpiresAt": "2026-04-06T12:00:00Z",
        "timezone": "UTC",
    }
    second_payload = {
        "googleSub": "google-sub-auth-update",
        "email": "after@example.com",
        "gmailAddress": "after@gmail.com",
        "refreshToken": "refresh-after",
        "accessToken": "access-after",
        "accessTokenExpiresAt": "2026-04-07T12:00:00Z",
        "timezone": "Asia/Tokyo",
    }

    first_response = await client.post("/api/auth/session", json=first_payload)
    second_response = await client.post("/api/auth/session", json=second_payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == second_response.json()["id"]

    async with integration_sessionmaker() as session:
        result = await session.execute(
            select(User).where(User.google_sub == "google-sub-auth-update")
        )
        users = result.scalars().all()
        assert len(users) == 1
        assert users[0].email == "after@example.com"
        assert users[0].gmail_address == "after@gmail.com"
        assert users[0].timezone == "Asia/Tokyo"
