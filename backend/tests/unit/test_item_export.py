from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import items as items_api
from app.core.db import ConfidenceLevel, DateType, ItemCategory, get_db
from app.deps import get_current_user
from app.services import items as items_service


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timezone: str = "UTC"
    refresh_token_enc: str | None = "enc-refresh"
    access_token_enc: str | None = "enc-access"
    access_token_expires_at: datetime | None = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


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
async def test_export_item_to_gcal_stores_event_id(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user = _FakeUser()
    item = _FakeItem(user_id=user.id)

    async def fake_get_owned_item(
        _session: _FakeSession,
        _user: _FakeUser,
        _item_id: str,
    ) -> _FakeItem:
        return item

    monkeypatch.setattr(items_service, "_get_owned_item", fake_get_owned_item)
    monkeypatch.setattr(items_service, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        items_service,
        "insert_calendar_event",
        lambda _user, _item: {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"},
    )

    result = await items_service.export_item_to_gcal(session, user, str(item.id))

    assert result == {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"}
    assert item.gcal_event_id == "evt-1"
    assert item.exported_to_gcal is True
    assert session.commit_count == 1
    assert session.refreshed == [item]


@pytest.mark.asyncio
async def test_export_items_batch_returns_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user = _FakeUser()
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())

    async def fake_export(_session: _FakeSession, _user: _FakeUser, item_id: str) -> dict[str, str]:
        if item_id == first_id:
            return {"gcalEventId": "evt-1", "htmlLink": "https://calendar/1"}
        raise items_service.AppError(
            items_service.ErrorCode.NOT_FOUND,
            "Item not found.",
            status_code=404,
        )

    monkeypatch.setattr(items_service, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(items_service, "_export_item_without_rate_limit", fake_export)

    result = await items_service.export_items_batch(session, user, [first_id, second_id])

    assert result.exported == 1
    assert result.failed == 1
    assert result.results[0].gcal_event_id == "evt-1"
    assert result.results[1].error == "Item not found."


@pytest.mark.asyncio
async def test_build_ics_includes_valarms(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _FakeUser()

    async def fake_get_items(*args, **kwargs) -> dict[str, object]:
        return {
            "items": [
                items_service.ExtractedItemResponse.model_validate(
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "user_id": str(user.id),
                        "name": "Canva Pro",
                        "category": "subscription",
                        "expiry_date": "2026-01-01",
                        "date_type": "expiry",
                        "confidence": "high",
                        "notes": None,
                        "source_sender": "sender@example.com",
                        "source_date": "2026-04-06T12:00:00Z",
                        "source_message_id": "msg-1",
                        "dismissed": False,
                        "dismissed_at": None,
                        "exported_to_gcal": False,
                        "gcal_event_id": None,
                        "urgency": "critical",
                        "days_remaining": 1,
                        "created_at": "2026-04-06T12:00:00Z",
                        "updated_at": "2026-04-06T12:00:00Z",
                    }
                )
            ],
            "total": 1,
        }

    monkeypatch.setattr(items_service, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(items_service, "get_items", fake_get_items)

    ics_content = await items_service.build_ics(object(), user)

    assert "BEGIN:VCALENDAR" in ics_content
    assert "BEGIN:VEVENT" in ics_content
    assert "BEGIN:VALARM" in ics_content
    assert "TRIGGER:-P7D" in ics_content
    assert "TRIGGER:-P1D" in ics_content


def test_export_routes_return_expected_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(items_api.router)
    user = _FakeUser()

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> object:
        return object()

    async def fake_single_export(_db: object, _user: _FakeUser, _item_id: str) -> dict[str, str]:
        return {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"}

    async def fake_batch_export(
        _db: object,
        _user: _FakeUser,
        _item_ids: list[str],
    ) -> items_service.ExportBatchResult:
        return items_service.ExportBatchResult(
            exported=1,
            failed=0,
            results=[
                items_service.ExportBatchItemResult(
                    item_id=_item_ids[0],
                    gcal_event_id="evt-1",
                    error=None,
                )
            ],
        )

    async def fake_build_ics(*args, **kwargs) -> str:
        return "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(items_api, "export_item_to_gcal", fake_single_export)
    monkeypatch.setattr(items_api, "export_items_batch", fake_batch_export)
    monkeypatch.setattr(items_api, "build_ics", fake_build_ics)

    client = TestClient(app)

    single = client.post(f"/api/items/{uuid.uuid4()}/export")
    assert single.status_code == 200
    assert single.json() == {"gcalEventId": "evt-1", "htmlLink": "https://calendar/event"}

    batch = client.post(
        "/api/items/export-batch",
        json={"itemIds": ["11111111-1111-1111-1111-111111111111"]},
    )
    assert batch.status_code == 200
    assert batch.json()["exported"] == 1

    ics = client.get("/api/items/export.ics")
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar; charset=utf-8")
