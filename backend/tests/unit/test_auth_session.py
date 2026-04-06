from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.core.db import UserTier, get_db
from app.schemas.user import SessionCreateRequest
from app.services import users


@dataclass
class _FakeUser:
    email: str
    gmail_address: str
    google_sub: str
    refresh_token_enc: str
    access_token_enc: str
    access_token_expires_at: datetime
    timezone: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    digest_day_of_week: int = 1
    last_scan_at: datetime | None = None
    created_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    tier: UserTier = UserTier.FREE


class _FakeSession:
    def __init__(self) -> None:
        self.user: _FakeUser | None = None
        self.commit_count = 0
        self.refresh_count = 0

    def add(self, user: _FakeUser) -> None:
        self.user = user

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, _user: _FakeUser) -> None:
        self.refresh_count += 1


@pytest.mark.asyncio
async def test_create_or_update_user_session_creates_new_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    payload = SessionCreateRequest(
        google_sub="google-sub-1",
        email="user@example.com",
        gmail_address="user@gmail.com",
        refresh_token="refresh-token",
        access_token="access-token",
        access_token_expires_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        timezone="UTC",
    )

    async def fake_get_user_by_google_sub(_session: _FakeSession, _google_sub: str) -> None:
        return None

    monkeypatch.setattr(users, "_get_user_by_google_sub", fake_get_user_by_google_sub)
    monkeypatch.setattr(users.crypto, "encrypt", lambda value: f"enc::{value}")
    monkeypatch.setattr(users, "User", _FakeUser)

    user = await users.create_or_update_user_session(session, payload)

    assert user.google_sub == "google-sub-1"
    assert user.refresh_token_enc == "enc::refresh-token"
    assert user.access_token_enc == "enc::access-token"
    assert user.refresh_token_enc != payload.refresh_token
    assert session.commit_count == 1
    assert session.refresh_count == 1


@pytest.mark.asyncio
async def test_create_or_update_user_session_updates_existing_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_user = _FakeUser(
        email="old@example.com",
        gmail_address="old@gmail.com",
        google_sub="google-sub-1",
        refresh_token_enc="old-refresh",
        access_token_enc="old-access",
        access_token_expires_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
        timezone="America/New_York",
    )
    session = _FakeSession()
    payload = SessionCreateRequest(
        google_sub="google-sub-1",
        email="new@example.com",
        gmail_address="new@gmail.com",
        refresh_token="refresh-token",
        access_token="access-token",
        access_token_expires_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        timezone="Asia/Tokyo",
    )

    async def fake_get_user_by_google_sub(_session: _FakeSession, _google_sub: str) -> _FakeUser:
        return existing_user

    monkeypatch.setattr(users, "_get_user_by_google_sub", fake_get_user_by_google_sub)
    monkeypatch.setattr(users.crypto, "encrypt", lambda value: f"enc::{value}")

    user = await users.create_or_update_user_session(session, payload)

    assert user is existing_user
    assert user.email == "new@example.com"
    assert user.gmail_address == "new@gmail.com"
    assert user.refresh_token_enc == "enc::refresh-token"
    assert user.access_token_enc == "enc::access-token"
    assert user.timezone == "Asia/Tokyo"
    assert session.user is None
    assert session.commit_count == 1
    assert session.refresh_count == 1


def test_post_auth_session_returns_user_response(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(auth_api.router)

    async def fake_service(_db: object, payload: SessionCreateRequest) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email=payload.email,
            gmail_address=payload.gmail_address,
            tier=UserTier.FREE,
            timezone=payload.timezone,
            digest_day_of_week=1,
            last_scan_at=None,
            created_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        )

    async def fake_get_db() -> object:
        return object()

    monkeypatch.setattr(auth_api, "create_or_update_user_session", fake_service)
    app.dependency_overrides[get_db] = fake_get_db

    client = TestClient(app)
    response = client.post(
        "/api/auth/session",
        json={
            "googleSub": "google-sub-1",
            "email": "user@example.com",
            "gmailAddress": "user@gmail.com",
            "refreshToken": "refresh-token",
            "accessToken": "access-token",
            "accessTokenExpiresAt": "2026-04-06T12:00:00Z",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "gmailAddress": "user@gmail.com",
        "tier": "free",
        "timezone": "UTC",
        "digestDayOfWeek": 1,
        "lastScanAt": None,
        "createdAt": "2026-04-06T12:00:00Z",
    }
