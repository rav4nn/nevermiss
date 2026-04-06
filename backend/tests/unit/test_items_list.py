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


@dataclass
class _FakeItem:
    user_id: uuid.UUID
    name: str
    category: ItemCategory
    expiry_date: date
    dismissed: bool
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    date_type: DateType = DateType.EXPIRY
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    notes: str | None = None
    source_sender: str = "sender@example.com"
    source_date: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    source_message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dismissed_at: datetime | None = None
    exported_to_gcal: bool = False
    gcal_event_id: str | None = None
    created_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)
    updated_at: datetime = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


class _ScalarResult:
    def __init__(self, items: list[_FakeItem]) -> None:
        self._items = items

    def scalars(self) -> _ScalarResult:
        return self

    def all(self) -> list[_FakeItem]:
        return self._items


class _FakeSession:
    def __init__(self, items: list[_FakeItem]) -> None:
        self.items = items

    async def execute(self, statement: object) -> _ScalarResult:
        compiled = statement.compile()
        params = compiled.params
        query_text = str(statement)

        filtered = [
            item
            for item in self.items
            if item.user_id == params["user_id_1"]
        ]

        if "extracted_items.dismissed IS false" in query_text:
            filtered = [item for item in filtered if item.dismissed is False]
        elif "extracted_items.dismissed IS true" in query_text:
            filtered = [item for item in filtered if item.dismissed is True]

        categories = params.get("category_1")
        if categories is not None:
            filtered = [item for item in filtered if item.category in categories]

        filtered.sort(key=lambda item: item.expiry_date)
        return _ScalarResult(filtered)


@pytest.mark.asyncio
async def test_get_items_filters_categories_urgency_and_excludes_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUser()
    other_user = _FakeUser()
    session = _FakeSession(
        [
            _FakeItem(
                user_id=user.id,
                name="critical-subscription",
                category=ItemCategory.SUBSCRIPTION,
                expiry_date=date(2026, 4, 7),
                dismissed=False,
            ),
            _FakeItem(
                user_id=user.id,
                name="urgent-insurance",
                category=ItemCategory.INSURANCE,
                expiry_date=date(2026, 4, 10),
                dismissed=False,
            ),
            _FakeItem(
                user_id=user.id,
                name="too-old",
                category=ItemCategory.SUBSCRIPTION,
                expiry_date=date(2025, 1, 1),
                dismissed=False,
            ),
            _FakeItem(
                user_id=user.id,
                name="dismissed-item",
                category=ItemCategory.SUBSCRIPTION,
                expiry_date=date(2026, 4, 8),
                dismissed=True,
            ),
            _FakeItem(
                user_id=other_user.id,
                name="other-user-item",
                category=ItemCategory.SUBSCRIPTION,
                expiry_date=date(2026, 4, 9),
                dismissed=False,
            ),
        ]
    )

    def fake_compute_urgency(expiry_date: date, _timezone: str) -> tuple[str, int] | None:
        mapping = {
            date(2026, 4, 7): ("critical", 1),
            date(2026, 4, 10): ("urgent", 4),
            date(2025, 1, 1): None,
            date(2026, 4, 8): ("critical", 2),
            date(2026, 4, 9): ("critical", 3),
        }
        return mapping[expiry_date]

    monkeypatch.setattr(items_service, "compute_urgency", fake_compute_urgency)

    result = await items_service.get_items(
        session,
        user,
        dismissed=False,
        categories=[ItemCategory.SUBSCRIPTION, ItemCategory.INSURANCE],
        urgency={"critical", "urgent"},
        limit=1,
        offset=1,
    )

    assert result["total"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0].name == "urgent-insurance"


def test_list_items_route_parses_filters_and_returns_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(items_api.router)
    user = _FakeUser()

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> object:
        return object()

    async def fake_get_items(
        _db: object,
        current_user: _FakeUser,
        *,
        dismissed: bool,
        categories: list[ItemCategory] | None,
        urgency: set[str] | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        assert current_user is user
        assert dismissed is True
        assert categories == [ItemCategory.SUBSCRIPTION, ItemCategory.INSURANCE]
        assert urgency == {"critical", "urgent"}
        assert limit == 10
        assert offset == 5
        return {
            "items": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "user_id": str(user.id),
                    "name": "Item One",
                    "category": "subscription",
                    "expiry_date": "2026-04-07",
                    "date_type": "expiry",
                    "confidence": "high",
                    "notes": None,
                    "source_sender": "sender@example.com",
                    "source_date": "2026-04-06T12:00:00Z",
                    "source_message_id": "msg-1",
                    "dismissed": True,
                    "dismissed_at": None,
                    "exported_to_gcal": False,
                    "gcal_event_id": None,
                    "urgency": "critical",
                    "days_remaining": 1,
                    "created_at": "2026-04-06T12:00:00Z",
                    "updated_at": "2026-04-06T12:00:00Z",
                }
            ],
            "total": 1,
        }

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(items_api, "get_items", fake_get_items)

    client = TestClient(app)
    response = client.get(
        "/api/items?dismissed=true&categories=subscription,insurance&urgency=critical,urgent&limit=10&offset=5"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "Item One"
