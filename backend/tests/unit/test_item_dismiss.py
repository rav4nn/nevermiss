from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import items as items_api
from app.core.db import ConfidenceLevel, DateType, ItemCategory, get_db
from app.core.errors import AppError, ErrorCode, register_exception_handlers
from app.deps import get_current_user
from app.services import items as items_service


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timezone: str = "UTC"


@dataclass
class _FakeItem:
    user_id: uuid.UUID
    name: str = "Canva Pro"
    category: ItemCategory = ItemCategory.SUBSCRIPTION
    expiry_date: date = date(2026, 1, 1)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    date_type: DateType = DateType.EXPIRY
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    notes: str | None = None
    source_sender: str = "sender@example.com"
    source_date: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    source_message_id: str = "msg-1"
    dismissed: bool = False
    dismissed_at: datetime | None = None
    exported_to_gcal: bool = False
    gcal_event_id: str | None = None
    created_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    updated_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


class _FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.refreshed: list[_FakeItem] = []

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, item: _FakeItem) -> None:
        self.refreshed.append(item)


@pytest.mark.asyncio
async def test_dismiss_item_sets_flags_and_adds_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    user = _FakeUser()
    item = _FakeItem(user_id=user.id)
    recorded: dict[str, object] = {}

    async def fake_get_owned_item(
        _session: _FakeSession,
        _user: _FakeUser,
        _item_id: str,
    ) -> _FakeItem:
        return item

    async def fake_add_dismissed(
        _session: _FakeSession,
        user_id: uuid.UUID,
        signature: str,
    ) -> None:
        recorded["user_id"] = user_id
        recorded["signature"] = signature

    monkeypatch.setattr(items_service, "_get_owned_item", fake_get_owned_item)
    monkeypatch.setattr(items_service.signatures, "compute_signature", lambda *args: "sig-1")
    monkeypatch.setattr(items_service.signatures, "add_dismissed", fake_add_dismissed)
    monkeypatch.setattr(
        items_service,
        "_to_item_response",
        lambda current_item, _timezone: items_service.ExtractedItemResponse.model_validate(
            {
                "id": current_item.id,
                "user_id": current_item.user_id,
                "name": current_item.name,
                "category": current_item.category,
                "expiry_date": current_item.expiry_date,
                "date_type": current_item.date_type,
                "confidence": current_item.confidence,
                "notes": current_item.notes,
                "source_sender": current_item.source_sender,
                "source_date": current_item.source_date,
                "source_message_id": current_item.source_message_id,
                "dismissed": current_item.dismissed,
                "dismissed_at": current_item.dismissed_at,
                "exported_to_gcal": current_item.exported_to_gcal,
                "gcal_event_id": current_item.gcal_event_id,
                "urgency": "critical",
                "days_remaining": 1,
                "created_at": current_item.created_at,
                "updated_at": current_item.updated_at,
            }
        ),
    )

    response = await items_service.dismiss_item(session, user, str(item.id))

    assert response.dismissed is True
    assert item.dismissed is True
    assert item.dismissed_at is not None
    assert recorded == {"user_id": user.id, "signature": "sig-1"}
    assert session.commit_count == 1
    assert session.refreshed == [item]


@pytest.mark.asyncio
async def test_undismiss_item_clears_flags_and_removes_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    user = _FakeUser()
    item = _FakeItem(
        user_id=user.id,
        dismissed=True,
        dismissed_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
    )
    recorded: dict[str, object] = {}

    async def fake_get_owned_item(
        _session: _FakeSession,
        _user: _FakeUser,
        _item_id: str,
    ) -> _FakeItem:
        return item

    async def fake_remove_dismissed(
        _session: _FakeSession,
        user_id: uuid.UUID,
        signature: str,
    ) -> None:
        recorded["user_id"] = user_id
        recorded["signature"] = signature

    monkeypatch.setattr(items_service, "_get_owned_item", fake_get_owned_item)
    monkeypatch.setattr(items_service.signatures, "compute_signature", lambda *args: "sig-2")
    monkeypatch.setattr(items_service.signatures, "remove_dismissed", fake_remove_dismissed)
    monkeypatch.setattr(
        items_service,
        "_to_item_response",
        lambda current_item, _timezone: items_service.ExtractedItemResponse.model_validate(
            {
                "id": current_item.id,
                "user_id": current_item.user_id,
                "name": current_item.name,
                "category": current_item.category,
                "expiry_date": current_item.expiry_date,
                "date_type": current_item.date_type,
                "confidence": current_item.confidence,
                "notes": current_item.notes,
                "source_sender": current_item.source_sender,
                "source_date": current_item.source_date,
                "source_message_id": current_item.source_message_id,
                "dismissed": current_item.dismissed,
                "dismissed_at": current_item.dismissed_at,
                "exported_to_gcal": current_item.exported_to_gcal,
                "gcal_event_id": current_item.gcal_event_id,
                "urgency": "critical",
                "days_remaining": 1,
                "created_at": current_item.created_at,
                "updated_at": current_item.updated_at,
            }
        ),
    )

    response = await items_service.undismiss_item(session, user, str(item.id))

    assert response.dismissed is False
    assert item.dismissed is False
    assert item.dismissed_at is None
    assert recorded == {"user_id": user.id, "signature": "sig-2"}
    assert session.commit_count == 1
    assert session.refreshed == [item]


@pytest.mark.asyncio
async def test_get_owned_item_raises_for_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _FakeUser()
    other_user = _FakeUser()
    item = _FakeItem(user_id=other_user.id)

    async def fake_get_item_by_id(_session: object, _item_id: str) -> _FakeItem:
        return item

    monkeypatch.setattr(items_service, "_get_item_by_id", fake_get_item_by_id)

    with pytest.raises(AppError) as exc_info:
        await items_service._get_owned_item(object(), user, str(item.id))

    assert exc_info.value.code == ErrorCode.FORBIDDEN
    assert exc_info.value.status_code == 403


def test_dismiss_route_returns_forbidden_for_other_users(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(items_api.router)
    user = _FakeUser()

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> object:
        return object()

    async def fake_dismiss_item(_db: object, _user: _FakeUser, _item_id: str) -> object:
        raise AppError(ErrorCode.FORBIDDEN, "You do not have access to this item.", status_code=403)

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(items_api, "dismiss_item", fake_dismiss_item)

    client = TestClient(app)
    response = client.post(f"/api/items/{uuid.uuid4()}/dismiss")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "FORBIDDEN",
            "message": "You do not have access to this item.",
        }
    }
