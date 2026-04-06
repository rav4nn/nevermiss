from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.core.db import UserTier, get_db
from app.core.errors import register_exception_handlers
from app.deps import get_current_user


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tier: UserTier = UserTier.FREE
    api_key_enc: str | None = None
    timezone: str = "UTC"
    digest_day_of_week: int = 1


class _FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.refreshed: list[_FakeUser] = []

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, user: _FakeUser) -> None:
        self.refreshed.append(user)


def _build_app(user: _FakeUser, session: _FakeSession) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(settings_api.router)

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> _FakeSession:
        return session

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db
    return TestClient(app)


def test_get_settings_returns_has_api_key_false() -> None:
    client = _build_app(_FakeUser(api_key_enc=None), _FakeSession())

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "tier": "free",
        "hasApiKey": False,
        "timezone": "UTC",
        "digestDayOfWeek": 1,
    }


def test_patch_settings_with_valid_key_stores_encrypted_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUser(api_key_enc=None)
    session = _FakeSession()
    client = _build_app(user, session)

    monkeypatch.setattr(settings_api, "_validate_gemini_api_key", lambda api_key: None)
    monkeypatch.setattr(settings_api.crypto, "encrypt", lambda value: f"enc::{value}")

    response = client.patch("/api/settings", json={"apiKey": "sk-valid"})

    assert response.status_code == 200
    assert user.api_key_enc == "enc::sk-valid"
    assert response.json()["hasApiKey"] is True
    assert session.commit_count == 1


def test_patch_settings_with_invalid_key_returns_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUser(api_key_enc=None)
    session = _FakeSession()
    client = _build_app(user, session)

    def fail_validation(_api_key: str) -> None:
        raise settings_api.AppError(
            settings_api.ErrorCode.VALIDATION_ERROR,
            "Invalid Gemini API key.",
            status_code=422,
        )

    monkeypatch.setattr(settings_api, "_validate_gemini_api_key", fail_validation)

    response = client.patch("/api/settings", json={"apiKey": "sk-invalid"})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid Gemini API key.",
        }
    }


def test_patch_settings_with_null_key_clears_stored_key() -> None:
    user = _FakeUser(api_key_enc="enc::old")
    session = _FakeSession()
    client = _build_app(user, session)

    response = client.patch("/api/settings", json={"apiKey": None})

    assert response.status_code == 200
    assert user.api_key_enc is None
    assert response.json()["hasApiKey"] is False
    assert session.commit_count == 1
