from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import me as me_api
from app.core.db import UserTier, get_db
from app.deps import get_current_user
from app.services import users


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    email: str = "user@example.com"
    gmail_address: str = "user@gmail.com"
    tier: UserTier = UserTier.FREE
    timezone: str = "UTC"
    digest_day_of_week: int = 1
    last_scan_at: datetime | None = None
    created_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    refresh_token_enc: str = "encrypted-refresh"


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flush_count = 0
        self.commit_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.mark.asyncio
async def test_delete_user_deletes_even_when_google_revoke_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    user = _FakeUser()

    monkeypatch.setattr(users.crypto, "decrypt", lambda value: "refresh-token")

    def fail_revoke(_refresh_token: str) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(users, "_revoke_google_refresh_token", fail_revoke)

    await users.delete_user(session, user)

    assert len(session.added) == 1
    assert session.added[0].event == "user_deleted"
    assert session.deleted == [user]
    assert session.flush_count == 1
    assert session.commit_count == 1


def test_get_me_returns_user_response() -> None:
    app = FastAPI()
    app.include_router(me_api.router)
    user = _FakeUser()

    async def fake_current_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_current_user] = fake_current_user

    client = TestClient(app)
    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "user@example.com",
        "gmailAddress": "user@gmail.com",
        "tier": "free",
        "timezone": "UTC",
        "digestDayOfWeek": 1,
        "lastScanAt": None,
        "createdAt": "2026-04-06T12:00:00Z",
    }


def test_delete_me_returns_204() -> None:
    app = FastAPI()
    app.include_router(me_api.router)
    user = _FakeUser()

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> object:
        return object()

    async def fake_delete_user(_db: object, current_user: _FakeUser) -> None:
        assert current_user is user

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db

    original_delete_user = me_api.delete_user
    me_api.delete_user = fake_delete_user
    try:
        client = TestClient(app)
        response = client.delete("/api/me")
    finally:
        me_api.delete_user = original_delete_user

    assert response.status_code == 204
    assert response.text == ""
